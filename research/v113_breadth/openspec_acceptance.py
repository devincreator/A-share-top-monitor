#!/usr/bin/env python3
"""Machine-evaluated V113 quality gate; never confuse workflow success and data completeness."""
import argparse,csv,json,hashlib
from pathlib import Path

def evaluate(days,security_dates,aggregate_dates,*,universe_verified=False,suspensions_verified=False,duplicates=0):
    if len(days)!=len(set(days)) or not days:
        raise ValueError("INVALID_FROZEN_CALENDAR")
    reference=set(days)
    sec=set(security_dates)
    agg=set(aggregate_dates)
    if sec-reference or agg-reference:raise ValueError("OUT_OF_REFERENCE_DATE")
    if len(security_dates)!=len(sec):raise ValueError("DUPLICATE_SECURITY_DATE")
    if duplicates<0:raise ValueError("INVALID_DUPLICATE_COUNT")
    coverage=len(sec)/len(days)
    coverage_pass=(len(sec)*100>=len(days)*98)
    checks={"coverage_ge_98_percent":coverage_pass,
      "historical_listed_universe_verified":bool(universe_verified),
      "suspension_vs_flat_verified":bool(suspensions_verified),
      "zero_duplicate_security_date":duplicates==0}
    return {"version":"V113","state":"PASS" if all(checks.values()) else
            ("PARTIAL" if sec or agg else "BLOCKED"),
      "coverage_security_dates":len(sec),"coverage_aggregate_only_dates":len(agg-sec),
      "calendar_days":len(days),"security_coverage":round(coverage,8),
      "checks":checks,"formal_signal_allowed":False,
      "warning":"Aggregate-only dates do not count toward security-level acceptance."}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--anchor",required=True)
    p.add_argument("--securities",nargs="*")
    p.add_argument("--aggregate",nargs="*")
    p.add_argument("--out",required=True)
    args=p.parse_args()
    with open(args.anchor,newline="",encoding="utf-8") as f:
        days=[r["source_trade_date"] for r in csv.DictReader(f)]
    d=evaluate(days,args.securities or [],args.aggregate or [])
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    d["anchor_sha256"]=hashlib.sha256(Path(args.anchor).read_bytes()).hexdigest()
    target.write_text(json.dumps(d,indent=2)+"\n")
    print(json.dumps(d))
if __name__=="__main__":main()
