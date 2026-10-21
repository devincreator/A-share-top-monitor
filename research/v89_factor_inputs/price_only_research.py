#!/usr/bin/env python3
"""Research-only source-cross-checked price features; no TOP/BOTTOM inference."""
import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

def percentile_before(series,index,window=756):
    """Historical rank against PRIOR observations, excluding today's value."""
    if index<window or not math.isfinite(series[index]):
        return None
    history=series[index-window:index]
    if len(history)!=window or not all(math.isfinite(x) for x in history):
        return None
    return 100*sum(x<=series[index] for x in history)/window


def compute(records, asof):
    rows=sorted(records,key=lambda x:x["date"])
    if len(rows)<900:
        raise ValueError("900 rows required for 120d-volatility + past 756 ranks")
    days=[r["date"] for r in rows]
    if len(set(days))!=len(days) or days[-1]!=asof:
        raise ValueError("duplicated or mismatched index dates")
    prices=[float(r["close"]) for r in rows]
    if not all(math.isfinite(x) and x>0 for x in prices):
        raise ValueError("invalid price history")
    returns=[float("nan")]+[prices[i]/prices[i-1]-1 for i in range(1,len(prices))]
    ret63=[float("nan") if t<63 else 100*(prices[t]/prices[t-63]-1)
           for t in range(len(prices))]
    rv_ratio=[]
    for t in range(len(prices)):
        if t<120:
            rv_ratio.append(float("nan"))
        else:
            r20=statistics.stdev(returns[t-19:t+1])
            r120=statistics.stdev(returns[t-119:t+1])
            rv_ratio.append(r20/r120 if r120>0 else float("nan"))
    t=len(rows)-1
    score={
        "date":asof,
        "index":"000985.CSI",
        "close":prices[t],
        "ret5_pct":100*(prices[t]/prices[t-5]-1),
        "ret63_pct":ret63[t],
        "dd20_pct":100*(prices[t]/max(prices[t-19:t+1])-1),
        "dd60_pct":100*(prices[t]/max(prices[t-59:t+1])-1),
        "rv20_to_rv120":rv_ratio[t],
        "rv_ratio_percentile_prior756":percentile_before(rv_ratio,t),
        "ret63_percentile_prior756":percentile_before(ret63,t),
        "first_observation_date":days[0],
        "historical_price_observations":len(rows),
        "market_price_index":True,
        "uses_information_after_asof":False,
        "formal_signal_allowed":False,
        "is_separate_verified_four_module_model":False,
    }
    if any(score[k] is None for k in ("rv_ratio_percentile_prior756","ret63_percentile_prior756")):
        raise ValueError("insufficient valid past-only factor history")
    return score


def research_report(source_dir):
    root=Path(source_dir)
    raw=(root/"candidate_inputs.json").read_bytes()
    inputs=json.loads(raw)
    audit=json.loads((root/"cross_provider_audit.json").read_text(encoding="utf-8"))
    asof=audit["asof"]
    if audit.get("cross_index_source_status")!="RESEARCH_PRICE_AMOUNT_CROSS_PROVIDER_PASS":
        raise ValueError("external price/amount source cross-check did not pass")
    for code in ("000985","000300","000852"):
        if audit["results"][code]["matched"]<10 or audit["results"][code]["mismatches"]:
            raise ValueError(f"source conflict in index {code}")
    allshare=[r for r in inputs["indices"]["000985"] if r["date"]<=asof]
    output=compute(allshare,asof)
    output["cross_provider_status"]=audit["cross_index_source_status"]
    output["candidate_input_sha256"]=hashlib.sha256(raw).hexdigest()
    output["data_gate"]="CROSS_PROVIDER_PRICE_AMOUNT_RESEARCH_ONLY"
    output["finance_input_passed"]=False
    output["turnover_independently_certified"]=False
    output["historical_listing_universe_PIT_certified"]=False
    output["old_production_price_core_overwritten"]=False
    return output


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source-dir",default="v89_source_audit_output")
    a=p.parse_args()
    root=Path(a.source_dir)
    try:
        report=research_report(root)
        target=root/"price_only_research.json"
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({"status":"RESEARCH_ONLY","date":report["date"],
            "close":report["close"],"ret5_pct":report["ret5_pct"],
            "ret63_pct":report["ret63_pct"],
            "formal_signal_allowed":False},ensure_ascii=False))
    except (OSError,ValueError,KeyError,TypeError) as exc:
        report={"status":"BLOCKED","reason":type(exc).__name__+": "+str(exc)[:300],
                "formal_signal_allowed":False}
        (root/"price_only_research.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
        print(json.dumps(report,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
