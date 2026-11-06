#!/usr/bin/env python3
"""V112 immutable research acceptance, no invented exact values."""
import argparse,csv,json,hashlib,math
from pathlib import Path

def audit(daily,bridge,source_manifest):
    rows=list(csv.DictReader(Path(daily).open(newline="",encoding="utf-8")))
    if not rows:raise ValueError("EMPTY_DAILY")
    b=list(csv.DictReader(Path(bridge).open(newline="",encoding="utf-8"))) if Path(bridge).is_file() else []
    dates=[r["source_trade_date"] for r in rows]
    if dates!=sorted(set(dates)):raise ValueError("DUPLICATE_OR_UNSORTED_DAY")
    gaps={r["source_trade_date"] for r in rows if r["financing_status"]!="OK"}
    okay={r["source_trade_date"] for r in rows if r["financing_status"]=="OK"}
    for r in rows:
        if r["financing_status"] not in ("OK","MISSING","INVALID"):raise ValueError("BAD_FINANCING_STATUS")
        if r["financing_status"]!="OK" and r["balance_total_yuan"] not in ("",None):raise ValueError("GAP_IMPUTATION")
    supplement={r["date"] for r in b}
    if len(supplement)!=len(b) or not supplement.issubset(gaps):raise ValueError("BRIDGE_OVERLAP_OR_NON_GAP")
    for r in b:
        if r["status"]!="DUAL_EXCHANGE_SOURCE_RESEARCH_ROUNDED_SZSE" or r["may_replace_exact_financing_factor"]!="False":
            raise ValueError("BRIDGE_PRECISION_CLAIM")
        if not (float(r["total_lower_bound_yuan"])<=float(r["total_display_yuan_not_exact"])<=float(r["total_upper_bound_yuan"])):
            raise ValueError("BAD_BRIDGE_BOUNDS")
    n=len(rows);research=len(okay|supplement)
    # V112 acceptance 99% of fixed trading-date denominator. Fraction not rounded for PASS.
    cover=research/n
    enough=research*100>=99*n
    source=json.loads(Path(source_manifest).read_text(encoding="utf-8"))
    source_count=source.get("row_count")
    if source_count!=n:raise ValueError("MANIFEST_ROW_COUNT_MISMATCH")
    return {"version":"V112","status":"PASS" if enough else "PARTIAL",
        "research_coverage_pass":enough,"required_coverage_percent":99,
        "calendar_denominator":n,"exact_original_financing_days":len(okay),
        "rounded_bounds_gap_days":len(supplement),"research_usable_days":research,
        "research_coverage_fraction":round(cover,8),
        "remaining_missing_or_invalid_days":n-research,
        "exact_amount_available_from_gap_bridge":False,
        "rolling_63_756_percentile_certified":False,
        "rolling_63_756_status":"BLOCKED_UNTIL_COMPLETE_DEPENDENCY_WINDOWS_VERIFIED",
        "assumed_margin_delay_trading_sessions":2,
        "historical_pit_certified":False,"formal_signal_allowed":False,
        "inputs_sha256":{str(Path(p).name):hashlib.sha256(Path(p).read_bytes()).hexdigest()
            for p in [daily,bridge,source_manifest] if Path(p).is_file()}}
def main():
    p=argparse.ArgumentParser()
    for key in ("daily","bridge","manifest","out"):p.add_argument("--"+key,required=True)
    a=p.parse_args()
    result=audit(a.daily,a.bridge,a.manifest)
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
