#!/usr/bin/env python3
"""Append-only research source recovery; NEVER feed these candidate balances into alerts."""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"v91_exchange_margin"))
from probe_official import run_pilot

EXCHANGES=("SSE","SZSE")


def target_gaps(inputs, *, n=820):
    index=inputs["indices"]["000985"]
    dates=[r["date"] for r in index]
    if len(set(dates))!=len(dates) or any(r["code"]!="000985" for r in index):
        raise ValueError("duplicate/wrong 000985 price calendar")
    if len(dates)<n:
        raise ValueError("index calendar shorter than long finance rank")
    finance={r["date"]:r for r in inputs.get("financing",[])}
    bad=[]
    for day in sorted(dates)[-n:]:
        row=finance.get(day)
        try:
            sh=float(row["balance_sh_yuan"])
            sz=float(row["balance_sz_yuan"])
            valid=math.isfinite(sh) and math.isfinite(sz) and sh>0 and sz>0
        except (TypeError,ValueError,KeyError):
            valid=False
        if not valid:
            bad.append(day)
    return bad


def last_attempt_date(folder):
    if not folder.is_dir():
        return None
    stamps=[]
    for f in folder.glob("*.json"):
        try:
            stamps.append(dt.date.fromisoformat(json.loads(
                f.read_text(encoding="utf-8"))["attempt_utc"][:10]))
        except (OSError,KeyError,ValueError,json.JSONDecodeError):
            continue
    return max(stamps) if stamps else None


def select_dates(gaps, ledger, attempts, *, today, max_dates=8, retry_days=2):
    if not 1<=max_dates<=16 or retry_days<0:
        raise ValueError("unsafe batch or retry configuration")
    day=dt.date.fromisoformat(today)
    chosen=[]
    for d in gaps:
        if all((Path(ledger)/d/(exchange+".json")).is_file() for exchange in EXCHANGES):
            continue
        last=last_attempt_date(Path(attempts)/d)
        if last is not None and (day-last).days<retry_days:
            continue
        chosen.append(d)
        if len(chosen)>=max_dates:
            break
    return chosen


def append_evidence(pilot, record_root, pilot_dir, *, run_id, timestamp):
    """Store raw CSV plus SHA metadata once; source revisions are reported, not overwritten."""
    root=Path(record_root)
    results=[]
    for rec in pilot.get("days",[]):
        day=rec["requested_date"]
        audit={"date":day,"attempt_utc":timestamp,"run_id":str(run_id),
               "research_only":True,"formal_signal_allowed":False,"sources":{}}
        for exchange, candidate in rec.get("sources",{}).items():
            source=candidate.get("source")
            if candidate.get("status")!="SOURCE_OBSERVED_CANDIDATE_NOT_PIT" or not source:
                audit["sources"][exchange]={"status":"SOURCE_UNAVAILABLE",
                                           "error":candidate.get("error","invalid source")}
                continue
            rawfile=Path(pilot_dir)/f"{exchange.lower()}_{day}_raw.csv"
            if not rawfile.is_file():
                audit["sources"][exchange]={"status":"RAW_FILE_MISSING"}
                continue
            raw=rawfile.read_bytes()
            sha=hashlib.sha256(raw).hexdigest()
            if sha!=candidate.get("raw_csv_sha256"):
                audit["sources"][exchange]={"status":"RAW_SHA256_MISMATCH"}
                continue
            dest=root/"raw"/exchange/(day+".csv")
            meta=root/"records"/day/(exchange+".json")
            if dest.exists() or meta.exists():
                if dest.is_file() and meta.is_file() and hashlib.sha256(dest.read_bytes()).hexdigest()==sha:
                    audit["sources"][exchange]={"status":"FIRST_CAPTURE_UNCHANGED"}
                else:
                    audit["sources"][exchange]={"status":"SOURCE_REVISION_CONFLICT_NO_OVERWRITE",
                                                "new_sha256":sha}
                continue
            info={
                "date":day,"exchange":exchange,
                "source":"AKShare wrapper of original exchange financing summary",
                "akshare_version":pilot.get("akshare_version"),
                "source_raw_path":str(dest),"source_raw_sha256":sha,
                "first_captured_at_utc":timestamp,
                "source_unit":source["reported_unit"],
                "balance_yuan_from_display":source["balance_yuan_from_source"],
                "source_response_date_verified":source["source_response_date_verified"],
                "date_provenance":source["date_provenance"],
                "display_value_not_exact_yuan":exchange=="SZSE",
                "Jin10_comparison":candidate.get("comparison_with_jin10",{}),
                "PIT_certified":False,"formal_signal_allowed":False}
            dest.parent.mkdir(parents=True,exist_ok=True)
            meta.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(raw)
            meta.write_text(json.dumps(info,ensure_ascii=False,indent=2)+"\n")
            audit["sources"][exchange]={"status":"FIRST_SOURCE_CAPTURED","sha256":sha}
        out=root/"attempts"/day/(str(run_id)+".json")
        out.parent.mkdir(parents=True,exist_ok=True)
        if out.exists():
            raise ValueError("attempt ledger collision; refusing overwrite")
        out.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n")
        results.append(audit)
    return results


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--candidate",required=True)
    p.add_argument("--ledger",default="research/v92_margin_recovery")
    p.add_argument("--out",default="v92_exchange_batch")
    p.add_argument("--max-dates",type=int,default=8)
    p.add_argument("--retry-days",type=int,default=2)
    args=p.parse_args()
    root=Path(args.ledger)
    out=Path(args.out)
    out.mkdir(parents=True,exist_ok=True)
    data=json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    gaps=target_gaps(data)
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    dates=select_dates(gaps,root/"records",root/"attempts",today=now[:10],
                       max_dates=args.max_dates,retry_days=args.retry_days)
    result={"timestamp_utc":now,"source_gap_dates":len(gaps),
            "selected_dates":dates,"formal_signal_allowed":False,"PIT_certified":False,
            "source_calendar_only_proxy":True,"research_only":True}
    if dates:
        pilot=run_pilot(args.candidate,out/"pilot",dates=dates)
        result["new_attempts"]=append_evidence(
            pilot,root,out/"pilot",run_id=os.getenv("GITHUB_RUN_ID","manual-"+now.replace(":","")),
            timestamp=now)
        result["sources_saved"]=sum(
            x["status"]=="FIRST_SOURCE_CAPTURED"
            for rec in result["new_attempts"] for x in rec["sources"].values())
        result["source_failures"]=sum(
            x["status"]=="SOURCE_UNAVAILABLE"
            for rec in result["new_attempts"] for x in rec["sources"].values())
    else:
        result["status"]="NO_UNTOUCHED_OR_RETRY_ELIGIBLE_DATES"
    (out/"batch_audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:result.get(k) for k in (
        "source_gap_dates","selected_dates","sources_saved","source_failures")},ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
