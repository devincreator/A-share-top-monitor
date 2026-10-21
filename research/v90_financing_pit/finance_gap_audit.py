#!/usr/bin/env python3
"""V90: forensic financing coverage vs CSI 000985 session calendar.

No missing-date interpolation, no zero-value repair, no formal signal. A
secondary rounded report corroborates source error but is NOT exact/PIT data.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

LAG=63
RANK_HISTORY=756

def positive_balance(row):
    if not isinstance(row,dict):
        return None
    try:
        sh,sz=float(row["balance_sh_yuan"]),float(row["balance_sz_yuan"])
        return sh+sz if math.isfinite(sh) and math.isfinite(sz) and sh>0 and sz>0 else None
    except (KeyError,ValueError,TypeError):
        return None

def ranges(indices,days):
    indices=set(indices)
    found=[]
    start=None
    for n in range(len(days)+1):
        if n in indices:
            if start is None:
                start=n
        elif start is not None:
            found.append({"start":days[start],"end":days[n-1],
                          "trading_sessions":n-start})
            start=None
    return sorted(found,key=lambda x:-x["trading_sessions"])

def audit(candidate,asof=None):
    market=candidate.get("indices",{}).get("000985") or []
    dates=[r["date"] for r in market]
    if not dates or dates!=sorted(set(dates)):
        raise ValueError("missing or unordered 000985 index trading calendar")
    asof=asof or dates[-1]
    if asof not in dates:
        raise ValueError("asof not in verified index calendar")
    dates=dates[:dates.index(asof)+1]
    financing=candidate.get("financing",[])
    by_date={}
    for r in financing:
        day=r.get("date")
        if not day or day in by_date:
            raise ValueError("finance records contain missing or duplicate dates")
        by_date[day]=r
    missing=[i for i,d in enumerate(dates) if d not in by_date]
    invalid=[i for i,d in enumerate(dates)
             if d in by_date and positive_balance(by_date[d]) is None]
    balances=[positive_balance(by_date.get(d)) for d in dates]
    growth=[None]*len(dates)
    for i in range(LAG,len(dates)):
        if balances[i] is not None and balances[i-LAG] is not None:
            growth[i]=100*(balances[i]/balances[i-LAG]-1)
    t=len(dates)-1
    prior_start=max(0,t-RANK_HISTORY)
    prior_unusable=[dates[i] for i in range(prior_start,t) if growth[i] is None]
    rank_valid=(t-prior_start==RANK_HISTORY and
                not prior_unusable and growth[-1] is not None)
    return {"schema_version":1,"asof":asof,"status":"RESEARCH_DIAGNOSTICS_ONLY",
            "formal_signal_allowed":False,"finance_PIT_certified":False,
            "imputed_rows":0,"price_index_sessions":len(dates),
            "raw_financing_intersection_rows":len(financing),
            "market_sessions_missing_financing":len(missing),
            "missing_session_ranges":ranges(missing,dates),
            "invalid_nonpositive_dates":[dates[i] for i in invalid],
            "asof_balance_valid":balances[-1] is not None,
            "asof_balance_sh_sz_yuan":balances[-1],
            "growth63_status":"RESEARCH_ARITHMETIC_ONLY" if growth[-1] is not None else "BLOCKED",
            "growth63_pct":growth[-1],
            "prior756_rank_status":"RESEARCH_ARITHMETIC_ONLY" if rank_valid else "BLOCKED",
            "prior756_unusable_growth_sessions":len(prior_unusable),
            "prior756_unusable_sample_dates":prior_unusable[:15],
            "warning":"A current 63-session growth can be calculable while the fixed 756-session prior factor is blocked. Never delete sessions, reindex by data availability or fill zero without altering the frozen model."}

def corroborate_quote(q):
    if q.get("exchange")!="SZ" or q.get("trade_date")!="2024-08-08":
        raise ValueError("quote is not the specific invalid source observation")
    value,precision=float(q["value_yi_yuan"]),float(q["precision_yi_yuan"])
    if not 0<precision<=1 or q.get("first_supported_publication_date","")<=q["trade_date"]:
        raise ValueError("not a bounded secondary report published after trade day")
    return {"date":q["trade_date"],"value_yi_yuan":value,
            "lower_yuan_inclusive":round((value-precision/2)*1e8),
            "upper_yuan_exclusive":round((value+precision/2)*1e8),
            "first_supported_publication_date":q["first_supported_publication_date"],
            "sources":q["urls"],"official_exact_data":False,
            "usable_as_of_trade_close":False,
            "state":"SECONDARY_ROUNDED_EVIDENCE_ONLY"}

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--candidate",required=True)
    p.add_argument("--quote",required=True)
    p.add_argument("--asof")
    p.add_argument("--output",required=True)
    args=p.parse_args(argv)
    blob=Path(args.candidate).read_bytes()
    report=audit(json.loads(blob),asof=args.asof)
    report["raw_candidate_sha256"]=hashlib.sha256(blob).hexdigest()
    try:
        report["corroboration"]=corroborate_quote(
            json.loads(Path(args.quote).read_text(encoding="utf8")))
    except (OSError,ValueError,KeyError,TypeError) as e:
        report["corroboration_error"]=str(e)[:180]
    target=Path(args.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({k:report[k] for k in
          ("asof","market_sessions_missing_financing","invalid_nonpositive_dates",
           "growth63_status","prior756_rank_status","prior756_unusable_growth_sessions")},ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
