#!/usr/bin/env python3
"""V113 strict historical point-in-time availability evidence ledger.
Past-only windows != independently verified historical provider publication time.
"""
import argparse,csv,hashlib,json
from pathlib import Path
def audit(anchor, evidence):
    days=[r["source_trade_date"] for r in anchor]
    if len(days)!=1129 or days!=sorted(set(days)):raise ValueError("BAD_FROZEN_CALENDAR")
    index={day:i for i,day in enumerate(days)}
    accepted={};rejected=[]
    for r in evidence:
        d=r["observation_date"]
        decision=r["earliest_available_decision_date"]
        released=r["provider_publication_timestamp"]
        source=r["publication_record_url"]
        sha=r["publication_record_sha256"]
        if d not in index or decision not in index:raise ValueError("DATE_OUTSIDE_ANCHOR")
        if d in accepted:raise ValueError("DUPLICATE_DATE_PUBLICATION")
        if not (source.startswith("https://") and len(sha)==64 and released and decision>d):
            rejected.append(d);continue
        # User-approved one-session delay is necessary but not sufficient.
        if index[decision]<index[d]+1:rejected.append(d);continue
        accepted[d]=r
    return {"version":"V113-SHSZ","status":"CERTIFIED" if len(accepted)==len(days) and not rejected else "BLOCKED",
      "required_observation_dates":len(days),"historical_publication_dates_certified":len(accepted),
      "dates_rejected":rejected,"assumed_D_minus_1_lag_still_only_assumption":len(accepted)!=len(days),
      "price_window_future_leak_test_not_publication_certificate":True,
      "formal_signal_allowed":False}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--anchor",required=True);p.add_argument("--evidence")
    p.add_argument("--out",required=True)
    a=p.parse_args()
    with open(a.anchor,newline="",encoding="utf-8") as f:days=list(csv.DictReader(f))
    entries=[]
    if a.evidence and Path(a.evidence).is_file():
        with open(a.evidence,newline="",encoding="utf-8") as f:entries=list(csv.DictReader(f))
    report=audit(days,entries)
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    report["anchor_sha256"]=hashlib.sha256(Path(a.anchor).read_bytes()).hexdigest()
    (out/"historical_pit_certificate.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__":main()
