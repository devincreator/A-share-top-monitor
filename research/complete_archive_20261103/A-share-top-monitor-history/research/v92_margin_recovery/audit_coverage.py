#!/usr/bin/env python3
"""Audit V92 raw-SHA integrity and gap-source coverage; never promote to a model."""
import argparse
import csv
import datetime as dt
import decimal
import hashlib
import io
import json
import os
from pathlib import Path

from recover_batch import target_gaps

EXCHANGES=("SSE","SZSE")


def inspect_one(root,day,exchange):
    meta=Path(root)/"records"/day/(exchange+".json")
    csvfile=Path(root)/"raw"/exchange/(day+".csv")
    if not meta.exists() and not csvfile.exists():
        return {"status":"UNOBSERVED"}
    if not meta.is_file() or not csvfile.is_file():
        return {"status":"INTEGRITY_FAILED","reason":"record/raw pair incomplete"}
    try:
        doc=json.loads(meta.read_text(encoding="utf-8"))
        raw=csvfile.read_bytes()
        sha=hashlib.sha256(raw).hexdigest()
        if sha!=doc["source_raw_sha256"]:
            raise ValueError("sha256 of original raw CSV changed")
        if (doc["date"]!=day or doc["exchange"]!=exchange or
            doc["source_raw_path"]!=str(csvfile)):
            raise ValueError("metadata identity / source raw path mismatch")
        if doc["formal_signal_allowed"] is not False or doc["PIT_certified"] is not False:
            raise ValueError("source record illegally promoted")
        reader=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        if len(reader)!=1 or "融资余额" not in reader[0]:
            raise ValueError("not exactly one market summary")
        value=decimal.Decimal(reader[0]["融资余额"])
        if not value.is_finite() or value<=0:
            raise ValueError("invalid raw financing balance")
        if exchange=="SSE":
            if doc["source_unit"]!="CNY" or not doc["source_response_date_verified"]:
                raise ValueError("SSE source unit/date proof missing")
            if reader[0].get("信用交易日期")!=day.replace("-",""):
                raise ValueError("SSE actual response trading day mismatch")
            yuan=value
        else:
            if (doc["source_unit"]!="100M_CNY" or
                doc["date_provenance"]!="REQUEST_PARAMETER_ONLY" or
                doc["display_value_not_exact_yuan"] is not True):
                raise ValueError("SZSE must remain a rounded request-date-only value")
            yuan=value*decimal.Decimal(100000000)
        if yuan!=decimal.Decimal(str(doc["balance_yuan_from_display"])):
            raise ValueError("source balance changed after capture")
        return {"status":"SOURCE_HASH_AND_SCHEMA_MATCH_RESEARCH_ONLY",
                "sha256":sha,
                "source_date_provenance":doc["date_provenance"],
                "rounded_source":exchange=="SZSE",
                "PIT_certified":False}
    except (KeyError,ValueError,TypeError,ArithmeticError,UnicodeError,
            decimal.InvalidOperation,csv.Error,OSError) as exc:
        return {"status":"INTEGRITY_FAILED","reason":str(exc)[:240]}


def audit_all(candidate,root):
    gaps=target_gaps(candidate)
    states={}
    both=0
    failures=[]
    partial=0
    for day in gaps:
        a={ex:inspect_one(root,day,ex) for ex in EXCHANGES}
        states[day]=a
        good=sum(x["status"]=="SOURCE_HASH_AND_SCHEMA_MATCH_RESEARCH_ONLY"
                 for x in a.values())
        if good==2:
            both+=1
        elif good==1:
            partial+=1
        for ex,x in a.items():
            if x["status"]=="INTEGRITY_FAILED":
                failures.append({"day":day,"exchange":ex,"reason":x["reason"]})
    result={
        "status":"SOURCE_INTEGRITY_FAILED" if failures else "RESEARCH_CANDIDATE_EVIDENCE_ONLY",
        "asof":candidate["indices"]["000985"][-1]["date"],
        "original_source_gap_or_invalid_days":len(gaps),
        "raw_source_both_exchanges_sha_valid_days":both,
        "raw_source_one_exchange_only_days":partial,
        "raw_source_not_both_observed_days":len(gaps)-both,
        "source_integrity_failures":failures,
        "source_PIT_certified_days":0,
        "finance_growth63_prior756_rank_certified":False,
        "formal_signal_allowed":False,
        "production_updated":False,
        "purpose":"Number of immutable, source-consistent observations only; not PIT/date/precision proof."
    }
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--candidate",required=True)
    p.add_argument("--ledger",default="research/v92_margin_recovery")
    p.add_argument("--out",default="v92_exchange_batch/coverage_audit.json")
    args=p.parse_args()
    content=Path(args.candidate).read_bytes()
    report=audit_all(json.loads(content),args.ledger)
    report["source_candidate_sha256"]=hashlib.sha256(content).hexdigest()
    report["audit_created_at_utc"]=dt.datetime.now(dt.timezone.utc).isoformat()
    dest=Path(args.out)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    stamp=os.getenv("GITHUB_RUN_ID")
    if stamp:
        archive=Path(args.ledger)/"checkpoints"/report["audit_created_at_utc"][:10]/(stamp+".json")
        archive.parent.mkdir(parents=True,exist_ok=True)
        if archive.exists():
            raise ValueError("checkpoint must be append-only")
        archive.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({key:report[key] for key in (
        "status","original_source_gap_or_invalid_days","raw_source_both_exchanges_sha_valid_days",
        "raw_source_not_both_observed_days","formal_signal_allowed")},ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
