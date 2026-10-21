#!/usr/bin/env python3
"""V94: fail-closed exact-Yuan versus rounded-SZSE bounds research audit.

This computes a CONDITIONAL displayed-value interval, not a verified official
range or a historical publication-time certificate. Never promotes signals.
"""
import argparse
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"v92_margin_recovery"))
from audit_coverage import inspect_one
from recover_batch import target_gaps

MILLION=Decimal(1000000)
HUNDRED_MILLION=Decimal(100000000)
VALID_HASH="SOURCE_HASH_AND_SCHEMA_MATCH_RESEARCH_ONLY"


def precision_bounds(szse_display):
    """Union of nearest-rounding and truncation intervals; assumption only.

    For 6649.54 hundred-million CNY with 2 shown decimal digits, this
    corresponds to [664953500000, 664955000000) Yuan; the source does not
    specify which rounding convention it actually applies.
    """
    value=Decimal(str(szse_display).strip())
    if not value.is_finite() or value<=0:
        raise ValueError("invalid SZSE displayed financing balance")
    exponent=value.as_tuple().exponent
    if exponent>0 or exponent< -5:
        raise ValueError("unexpected displayed precision")
    quantum=HUNDRED_MILLION*(Decimal(10)**exponent)
    middle=value*HUNDRED_MILLION
    return {"display_value_100m_cny":str(value),
            "displayed_center_yuan":str(middle),
            "display_quantum_yuan":str(quantum),
            "conditional_low_yuan_inclusive":str(middle-quantum/2),
            "conditional_high_yuan_exclusive":str(middle+quantum),
            "interval_assumption":"UNION_NEAREST_AND_TRUNCATION_NOT_CERTIFIED",
            "exact_yuan_certified":False}


def parse_source_balance(root, day, exchange):
    file=Path(root)/"raw"/exchange/(day+".csv")
    with file.open(encoding="utf-8-sig",newline="") as fh:
        records=list(csv.DictReader(fh))
    if len(records)!=1:
        raise ValueError("expected exactly one exchange summary row")
    row=records[0]
    value=Decimal(row["融资余额"])
    if not value.is_finite() or value<=0:
        raise ValueError("invalid raw balance")
    if exchange=="SSE":
        if row.get("信用交易日期")!=day.replace("-",""):
            raise ValueError("source response date mismatch")
        if value!=value.to_integral_value():
            raise ValueError("SSE exact CNY is not an integer")
        return value
    return value


def published_before(publication_timestamp, decision_timestamp):
    """True only for verified explicit timezone-aware publication timestamps."""
    if not publication_timestamp or not decision_timestamp:
        return False
    try:
        p=datetime.fromisoformat(publication_timestamp.replace("Z","+00:00"))
        d=datetime.fromisoformat(decision_timestamp.replace("Z","+00:00"))
        if p.tzinfo is None or d.tzinfo is None:
            return False
        return p<=d
    except (TypeError,ValueError):
        return False


def audit_day(root, day, original=None, decision_timestamp=None):
    statuses={ex:inspect_one(root,day,ex) for ex in ("SSE","SZSE")}
    result={"date":day,"source_status":{k:v["status"] for k,v in statuses.items()},
            "status":"BLOCKED_SOURCE_INCOMPLETE","PIT_certified":False,
            "exact_yuan_certified":False,"formal_signal_allowed":False}
    if any(x["status"]=="INTEGRITY_FAILED" for x in statuses.values()):
        result["status"]="BLOCKED_SOURCE_INTEGRITY"
        result["failures"]={k:v.get("reason") for k,v in statuses.items()
                            if v["status"]=="INTEGRITY_FAILED"}
        return result
    if any(x["status"]!=VALID_HASH for x in statuses.values()):
        return result
    try:
        sh=parse_source_balance(root,day,"SSE")
        display=parse_source_balance(root,day,"SZSE")
        bounds=precision_bounds(display)
        low=sh+Decimal(bounds["conditional_low_yuan_inclusive"])
        high=sh+Decimal(bounds["conditional_high_yuan_exclusive"])
        result.update(status="ROUNDED_INTERVAL_ONLY_NOT_PIT",
                      sse_exact_yuan=str(sh),
                      szse_candidate_display_bounds=bounds,
                      sh_sz_conditional_low_yuan=str(low),
                      sh_sz_conditional_high_yuan_exclusive=str(high))
        if original is not None:
            try:
                jin10_sh=Decimal(str(original["balance_sh_yuan"]))
                jin10_sz=Decimal(str(original["balance_sz_yuan"]))
                if jin10_sh.is_finite() and jin10_sh>0:
                    result["SSE_equals_original_Jin10"]=jin10_sh==sh
                if jin10_sz.is_finite() and jin10_sz>0:
                    result["Jin10_SZ_inside_conditional_display_bounds"]=(
                        Decimal(bounds["conditional_low_yuan_inclusive"])<=jin10_sz
                        < Decimal(bounds["conditional_high_yuan_exclusive"]))
                    if result["Jin10_SZ_inside_conditional_display_bounds"] is False:
                        result["status"]="BLOCKED_CROSS_SOURCE_DISAGREEMENT"
            except (KeyError,TypeError,InvalidOperation):
                pass
        # Archived V92 data have capture UTC, not verified original release times.
        result["publication_timestamp_proven"]=False
        result["observable_at_decision"]=False
    except (ValueError,TypeError,KeyError,InvalidOperation,OSError,csv.Error) as exc:
        result["status"]="BLOCKED_INVALID_SOURCE_FIELDS"
        result["reason"]=f"{type(exc).__name__}: {str(exc)[:180]}"
    return result


def audit_all(candidate,root,decision_timestamp=None):
    gaps=target_gaps(candidate)
    originals={row["date"]:row for row in candidate.get("financing",[])}
    results=[audit_day(root,day,originals.get(day),decision_timestamp) for day in gaps]
    counts={state:sum(x["status"]==state for x in results)
            for state in sorted(set(x["status"] for x in results))}
    source_complete=sum(all(x["source_status"][ex]==VALID_HASH for ex in ("SSE","SZSE"))
                        for x in results)
    return {
        "schema_version":1,
        "asof":candidate["indices"]["000985"][-1]["date"],
        "target_missing_or_invalid_days":len(gaps),
        "exchange_raw_SHA_and_schema_both_pass_days":source_complete,
        "source_not_both_verified_days":len(gaps)-source_complete,
        "source_status_counts":counts,
        "days":results,
        "precision_model":"CONDITIONAL_DISPLAY_ONLY_NO_OFFICIAL_ROUNDING_CONVENTION",
        "publication_times_all_verified":False,
        "complete_820_session_financing_history_PIT":False,
        "formal_signal_allowed":False,
        "production_updated":False,
        "decision_timestamp":decision_timestamp,
        "conclusion":"RESEARCH_BOUNDS_ONLY_FACTORS_STILL_BLOCKED"
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--candidate",required=True)
    p.add_argument("--ledger",default="research/v92_margin_recovery")
    p.add_argument("--out",default="v92_exchange_batch/v94_bounds_audit.json")
    p.add_argument("--decision-at",default=None)
    args=p.parse_args()
    raw=Path(args.candidate).read_bytes()
    result=audit_all(json.loads(raw),args.ledger,args.decision_at)
    result["candidate_source_sha256"]=hashlib.sha256(raw).hexdigest()
    output=Path(args.out);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({k:result[k] for k in
      ("target_missing_or_invalid_days","exchange_raw_SHA_and_schema_both_pass_days",
       "source_not_both_verified_days","formal_signal_allowed")},ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
