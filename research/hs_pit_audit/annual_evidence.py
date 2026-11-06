#!/usr/bin/env python3
"""Annual evidence inventory, explicitly not a full historical data downloader."""
import argparse,json
from pathlib import Path
def build():
    years=[]
    for y in range(2006,2027):
        record={"year":y,"raw_daily_bar_coverage":"NOT_INDEPENDENTLY_VERIFIED",
                "historical_listing_pit":"BLOCKED","source_publication_pit":"BLOCKED",
                "formally_usable_for_market_breadth":False,
                "formal_c50_allowed":False,"evidence":[]}
        if y==2006:
            record.update(raw_daily_bar_coverage="241/241 RAW_SHA_VERIFIED_NOT_PIT",raw_daily_records=288399)
            record["evidence"].append("research/status/quality_gates.json#versions.V85_2006")
        if 2022<=y<=2026:
            record["evidence"].append("research/v97_event_intake/observations/index_000985_prices_20220223_20261020.csv (index-only; partial first/last year; not stock-bars)")
        if y in (2023,2024,2025):
            record["evidence"].append("research/status/quality_gates.json#versions.V90 (financing source gap audit, not full stock-market universe)")
        if y in (2024,2025):
            record["evidence"].append("research/status/quality_gates.json#versions.V69_V75 (unverified market breadth)")
        if y==2026:
            record["evidence"].append("research/v88_daily_observations/ledger/ (isolated daily sample only)")
        years.append(record)
    return {"schema":"HS_YEAR_EVIDENCE_V1","min_year":2006,"max_year":2026,
            "scope":"SSE_SZSE_ORDINARY_A","no_absence_inference":True,
            "audit_not_finished":True,"years":years}
def main():
    p=argparse.ArgumentParser();p.add_argument("--output",required=True);a=p.parse_args()
    Path(a.output).write_text(json.dumps(build(),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":main()
