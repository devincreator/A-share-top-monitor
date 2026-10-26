#!/usr/bin/env python3
"""V113 SH/SZ-only: audit 24 BaoStock archives and repair documented gaps with TDX .day.

TDX does not expose explicit suspension flags or exchange publication timestamp.
Only actual positive-volume TDX bars can repair missing original stock dates.
No replacement of original BaoStock rows, no forward-fill, no Beijing data.
"""
import argparse,csv,gzip,hashlib,itertools,json,struct,zipfile
from collections import Counter
from datetime import date
from pathlib import Path
from baostock_shard import basic_list, listed_on_session

TDX_SHA="07aab2f1166a794cebfa380cda058417499c4f74049a5fe36fe029f5c803d400"
TDX_SIZE=549908719
RECORD=struct.Struct("<IIIIIfII")

def sha256_path(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for c in iter(lambda:f.read(4_194_304),b""):h.update(c)
    return h.hexdigest()

def unpack_tdx(raw):
    if len(raw)%32:raise ValueError("TDX_BAD_LENGTH")
    out={};last=None
    for pos in range(0,len(raw),32):
        d,op,hi,lo,cl,amount,vol,_=RECORD.unpack_from(raw,pos)
        ds=f"{d:08d}";day=ds[:4]+"-"+ds[4:6]+"-"+ds[6:]
        date.fromisoformat(day)
        if last and day<=last:raise ValueError("TDX_UNSORTED_OR_DUPLICATE")
        out[day]={"open":op/100,"high":hi/100,"low":lo/100,"close":cl/100,
            "amount":amount,"volume":vol,"previous_close":out[last]["close"] if last else None}
        last=day
    return out

def select_gap_fill(code,gaps,existing,archive_raw,*,min_checks=2):
    """Only close-compatible overlap history and actual traded TDX rows can backfill gaps."""
    tdx=unpack_tdx(archive_raw)
    common=sorted(set(existing)&set(tdx))
    check_dates=common[::max(1,len(common)//25)] if common else []
    if common and common[-1] not in check_dates:check_dates.append(common[-1])
    mismatches=[(d,existing[d],tdx[d]["close"]) for d in check_dates
        if abs(existing[d]-tdx[d]["close"])>0.031]
    if len(check_dates)<min_checks or mismatches:
        return [],list(sorted(gaps)),{"code":code,"reason":"TDX_OVERLAP_DISAGREES_OR_INSUFFICIENT",
            "checks":len(check_dates),"mismatches":mismatches[:4]}
    rescued=[];left=[]
    for d in sorted(gaps):
        row=tdx.get(d)
        if not row or row["volume"]<=0 or row["amount"]<=0 or row["previous_close"] is None:
            left.append(d);continue
        if row["close"]<=0 or row["previous_close"]<=0 or row["high"]<row["low"]:
            left.append(d);continue
        direction="up" if row["close"]>row["previous_close"] else (
            "down" if row["close"]<row["previous_close"] else "flat")
        rescued.append({"code":code,"date":d,"direction":direction,"close":row["close"],
            "previous_tdx_close":row["previous_close"],"volume":row["volume"],
            "amount":row["amount"],"tdx_stock_file_sha256":hashlib.sha256(archive_raw).hexdigest(),
            "provenance":"TDX_RAW_TRADING_BAR_DIRECTION_APPROX_RAW_PREVIOUS_CLOSE",
            "historical_pit_certified":False})
    return rescued,left,{"code":code,"reason":"CROSS_SOURCE_CHECKED",
        "checks":len(check_dates),"mismatches":0}

def load_calendar(path):
    with open(path,newline="",encoding="utf-8") as f:
        cal=[r["source_trade_date"] for r in csv.DictReader(f)]
    if len(cal)!=1129 or cal!=sorted(set(cal)):raise ValueError("FROZEN_CALENDAR_CHANGED")
    return cal

def run(args):
    cal=load_calendar(args.anchor)
    symbols=basic_list(args.basic)
    with open(args.baseline_daily,newline="",encoding="utf-8") as f:
        baseline={r["date"]:r for r in csv.DictReader(f)}
    if set(baseline)!=set(cal):raise ValueError("BASELINE_CALENDAR_MISMATCH")
    archive=Path(args.archive)
    if archive.stat().st_size!=TDX_SIZE or sha256_path(archive)!=TDX_SHA:
        raise ValueError("ORIGINAL_TDX_ARCHIVE_NOT_VERIFIED")
    bydate=Counter();rescued=[];unresolved=[];source_stats=Counter()
    stock_seen=set()
    with zipfile.ZipFile(archive) as z:
        members={x.filename.replace("\\","/").split("/")[-1].lower():x
                 for x in z.infolist() if x.filename.lower().endswith(".day")}
        for shard in range(24):
            f=Path(args.shard_dir)/("stock_bars_shard_%02d.csv.gz"%shard)
            m=Path(args.shard_dir)/("manifest_%02d.json"%shard)
            if not f.is_file() or not m.is_file():raise ValueError("MISSING_BAOSTOCK_SHARD_%02d"%shard)
            manifest=json.loads(m.read_text(encoding="utf-8"))
            if sha256_path(f)!=manifest["raw_archive_sha256"]:raise ValueError("BAOSTOCK_SHA_MISMATCH")
            with gzip.open(f,"rt",encoding="utf-8",newline="") as h:
                reader=csv.DictReader(h)
                for code,group in itertools.groupby(reader,key=lambda x:x["code"]):
                    if code in stock_seen:raise ValueError("DUPLICATE_SECURITY_ACROSS_SHARDS")
                    stock_seen.add(code)
                    if code not in symbols:raise ValueError("UNEXPECTED_SECURITY")
                    rawrows=list(group)
                    source_dates={}
                    for r in rawrows:
                        if r["date"] in source_dates:raise ValueError("DUPLICATE_ORIGINAL_BAR")
                        source_dates[r["date"]]=float(r["close"]) if r["close"] else None
                    b=symbols[code]
                    expected={d for d in cal if listed_on_session(b,d)}
                    gaps=expected-set(source_dates)
                    if not gaps:continue
                    key=code.replace(".","").lower()+".day"
                    member=members.get(key)
                    if member is None:
                        unresolved.extend({"date":d,"code":code,"reason":"TDX_SECURITY_FILE_ABSENT"}
                            for d in sorted(gaps))
                        source_stats["tdx_missing_symbol"]+=1
                        continue
                    tdxraw=z.read(member)
                    if len(tdxraw)!=member.file_size:raise ValueError("TDX_UNCOMPRESSED_SIZE_MISMATCH")
                    filled,left,check=select_gap_fill(code,gaps,
                        {d:v for d,v in source_dates.items() if v is not None},tdxraw)
                    rescued.extend(filled)
                    bydate.update(r["date"] for r in filled)
                    unresolved.extend({"date":d,"code":code,"reason":check["reason"]
                        if check["reason"]!="CROSS_SOURCE_CHECKED" else "TDX_NO_VALID_TRADING_BAR"}
                        for d in left)
                    source_stats[check["reason"]]+=1
                    source_stats["overlap_checks"]+=check["checks"]
    if stock_seen!=set(symbols):raise ValueError("MISSING_BASIC_SECURITIES")
    result=[]
    for d in cal:
        old=baseline[d]
        expected=int(old["expected_listed_shsz"])
        original=int(old["security_days_with_status"])
        repaired=bydate[d]
        left=expected-original-repaired
        if left<0:raise ValueError("RECOVERED_OVER_EXPECTED")
        r={"date":d,"expected_listed_shsz":expected,"original_status_observed":original,
            "tdx_repaired_days":repaired,"all_observed":original+repaired,
            "up":int(old["up"]),"down":int(old["down"]),"flat":int(old["flat"]),
            "suspended_baostock":int(old["suspended"]),"unresolved":left,
            "fully_observed":int(left==0)}
        for rescue in (x for x in rescued if x["date"]==d):
            r[rescue["direction"]]+=1
        result.append(r)
    exact=sum(x["fully_observed"] for x in result)
    if sum(x["unresolved"] for x in result)!=len(unresolved):
        raise ValueError("UNRESOLVED_MANIFEST_MISMATCH")
    if sum(x["tdx_repaired_days"] for x in result)!=len(rescued):
        raise ValueError("RECOVERY_MANIFEST_MISMATCH")
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    with (out/"daily_shsz_merged.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(result[0]))
        w.writeheader();w.writerows(result)
    with (out/"tdx_recovered_only.csv").open("w",newline="",encoding="utf-8") as f:
        fields=("code","date","direction","close","previous_tdx_close","volume","amount",
            "tdx_stock_file_sha256","provenance","historical_pit_certified")
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rescued)
    with (out/"still_missing.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["code","date","reason"]);w.writeheader()
        for r in unresolved:w.writerow({k:r[k] for k in ("code","date","reason")})
    stats={"version":"V113-SHSZ","scope":"SHANGHAI_AND_SHENZHEN_ONLY",
        "beijing_included":False,"target_days":len(cal),"total_stocks":len(symbols),
        "original_full_days":sum(int(x["fully_observed"]) for x in baseline.values()),
        "recovered_stock_dates":len(rescued),"still_missing_stock_dates":len(unresolved),
        "merged_full_days":exact,"full_date_coverage_fraction":round(exact/len(cal),8),
        "scoped_98pct_date_coverage_gate":(exact*100>=98*len(cal)),
        "source_checks":dict(source_stats),"original_tdx_zip_sha256":TDX_SHA,
        "membership_official_month_end_reconciled":False,
        "historical_publication_pit_certified":False,
        "SHSZ_FORMAL_PASS":False,
        "ALL_A_PASS":False,"formal_signal_allowed":False}
    stats["merged_csv_sha256"]=sha256_path(out/"daily_shsz_merged.csv")
    (out/"acceptance.json").write_text(json.dumps(stats,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(stats,ensure_ascii=False),flush=True)
    return stats

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for key in ("anchor","basic","baseline-daily","shard-dir","archive","out"):
        p.add_argument("--"+key,required=True)
    run(p.parse_args())
