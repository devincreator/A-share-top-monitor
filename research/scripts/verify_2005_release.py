#!/usr/bin/env python3
"""Verify archived 2005 raw daily source. RAW_VERIFIED != PIT_CERTIFIED.

Usage: python research/scripts/verify_2005_release.py /path/to/v82_2005_raw_242days.zip
Only Python 3 standard library needed.
"""
import argparse
import collections
import csv
import hashlib
import io
import json
import pathlib
import sys
import zipfile

EXPECTED_DAYS=242
EXPECTED_SOURCE_ROWS=314838

def verify(filename):
    zpath=pathlib.Path(filename)
    result={"source":str(zpath),"status":"IN_PROGRESS",
            "raw_source_sha256":hashlib.sha256(zpath.read_bytes()).hexdigest(),
            "PIT_CERTIFIED":False,"FORMAL_MODEL_ALLOWED":False,"issues":[]}
    with zipfile.ZipFile(zpath,"r") as z:
        if z.testzip() is not None:
            raise ValueError("ZIP CRC validation failed")
        files=sorted(n for n in z.namelist() if n.startswith("raw/") and n.endswith(".csv"))
        manifest=json.loads(z.read("source_manifest_2005.json"))
        sha=manifest["file_sha256"]
        if len(files)!=EXPECTED_DAYS or len(sha)!=EXPECTED_DAYS:
            raise ValueError(f"Expected {EXPECTED_DAYS} distinct trading dates")
        days=set(); records=0; bad_ohlc=0; dup_tick=0; bad_dates=0
        exchanges=collections.Counter(); invalid_pcts=0
        for name in files:
            day=pathlib.PurePosixPath(name).stem
            if len(day)!=8 or not day.isdigit() or day[:4]!="2005" or day in days:
                raise ValueError(f"Bad or duplicate trading date {name}")
            days.add(day)
            data=z.read(name)
            if hashlib.sha256(data).hexdigest()!=sha.get(day):
                raise ValueError(f"SHA256 mismatch {day}")
            rows=list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
            if not rows:raise ValueError(f"Empty day {day}")
            required={"symbol","trade_date","open","high","low","close","pct_chg","vol"}
            if not required.issubset(rows[0]):
                raise ValueError(f"Schema mismatch {day}")
            seen=set()
            for r in rows:
                records+=1
                sym=r["symbol"]
                if r["trade_date"]!=day:bad_dates+=1
                if sym in seen:dup_tick+=1
                seen.add(sym)
                exchanges[sym.split(".")[-1]]+=1
                try:
                    o,h,l,c=[float(r[k]) for k in ("open","high","low","close")]
                    pct=float(r["pct_chg"]); v=float(r["vol"])
                    if not (l>0 and l<=min(o,c)<=max(o,c)<=h and v>=0):
                        bad_ohlc+=1
                    if pct<=-100 or pct>=300: invalid_pcts+=1
                except (ValueError,KeyError):
                    bad_ohlc+=1
        result.update(dates=len(days),records=records,duplicate_tickers=dup_tick,
                      invalid_trade_dates=bad_dates,invalid_ohlc_or_vol=bad_ohlc,
                      unreasonable_returns=invalid_pcts,exchanges=dict(exchanges),
                      release_embedded_source_daily_sha256_matched=True)
        if records != EXPECTED_SOURCE_ROWS:
            result["issues"].append(f"Expected {EXPECTED_SOURCE_ROWS} rows; got {records}")
        if dup_tick or bad_dates or bad_ohlc or invalid_pcts:
            result["issues"].append("Raw schema/price integrity failed")
        result["status"]="RAW_VERIFIED" if not result["issues"] else "RAW_FAILED"
    return result

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("archive")
    parser.add_argument("--json",default=None)
    args=parser.parse_args()
    data=verify(args.archive)
    text=json.dumps(data,ensure_ascii=False,indent=2)
    print(text)
    if args.json:pathlib.Path(args.json).write_text(text+"\n",encoding="utf-8")
    if data["status"]!="RAW_VERIFIED":sys.exit(1)
