#!/usr/bin/env python3
"""Observe latest actually published day; never infer or emit formal trading signals."""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"v84_live_readiness"))
from daily_probe import probe

def recent_weekdays(anchor, max_calendar_lookback=8):
    if isinstance(anchor,str):
        anchor=dt.date.fromisoformat(anchor)
    return [(anchor-dt.timedelta(days=i)).strftime("%Y%m%d")
            for i in range(max_calendar_lookback+1)
            if (anchor-dt.timedelta(days=i)).weekday()<5]

def run_recent(anchor, *, fetch=probe, output_dir="v88_observation_output",
               ledger_dir="research/v88_daily_observations/ledger", max_calendar_lookback=8,
               now_utc=None):
    if isinstance(anchor,str):
        anchor=dt.date.fromisoformat(anchor)
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    audit={"schema_version":1,"run_date_local":anchor.isoformat(),"status":"DATA_UNAVAILABLE",
           "latest_observed_date":None,"source_is_independent_PIT_verified":False,
           "formal_signal_allowed":False,"research_only":True,"attempts":[]}
    for day in recent_weekdays(anchor,max_calendar_lookback):
        try:
            result,raw=fetch(day)
        except Exception as exc:
            result={"date":day,"status":"DATA_UNAVAILABLE","error":type(exc).__name__+": "+str(exc)[:200]}
            raw=None
        audit["attempts"].append({"date":day,"status":result.get("status"),
                                  "error":result.get("error")})
        if result.get("status")!="RAW_DAILY_INTEGRITY_PASS" or raw is None:
            continue
        # A source observation is not a complete model price/turnover/financing record.
        age=(anchor-dt.datetime.strptime(day,"%Y%m%d").date()).days
        audit.update(status="RAW_OBSERVED_RESEARCH_ONLY",
                     latest_observed_date=dt.datetime.strptime(day,"%Y%m%d").date().isoformat(),
                     calendar_age_days=age,
                     day_source_status=result["status"],
                     source=result.get("source_url"),
                     raw_sha256=result.get("sha256"),
                     traded_count=result.get("unique_sh_sz_traded_bars"),
                     advancers=result.get("positive_raw_pct_chg_count"),
                     observed_traded_advance_share=result.get("observed_traded_advance_share"),
                     index_price_verified=False,financing_verified=False,
                     amount_turnover_verified=False)
        (out/(day+".csv")).write_bytes(raw)
        # Immutable by convention: retain the first observed evidence; do not rewrite a date.
        record={"schema_version":1,"observation_date":audit["latest_observed_date"],
                "first_retrieved_at_utc":(now_utc or dt.datetime.now(dt.timezone.utc)).isoformat(),
                "source_url":result.get("source_url"),"source_raw_sha256":result.get("sha256"),
                "raw_source_rows":result.get("source_rows"),
                "traded_sh_sz_records":result.get("unique_sh_sz_traded_bars"),
                "raw_positive_pct_records":result.get("positive_raw_pct_chg_count"),
                "raw_traded_advance_share":result.get("observed_traded_advance_share"),
                "source_format_verified":True,"historical_listing_universe_PIT_certified":False,
                "formal_trading_signals_generated":False,"production_changed":False,
                "raw_archive_scope":"GitHub Actions run artifact; retention limited"}
        ledger=Path(ledger_dir);ledger.mkdir(parents=True,exist_ok=True)
        p=ledger/(audit["latest_observed_date"]+".json")
        if not p.exists():
            p.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
            audit["ledger_status"]="NEW_EVIDENCE_RECORD"
        else:
            old=json.loads(p.read_text(encoding="utf8"))
            if old.get("source_raw_sha256")!=record["source_raw_sha256"]:
                audit["ledger_status"]="CONFLICT_WITH_FIRST_OBSERVATION"
                audit["existing_sha256"]=old.get("source_raw_sha256")
            else:
                audit["ledger_status"]="EXISTING_UNCHANGED"
        break
    (out/"probe_recent.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    return audit

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--anchor",default=dt.datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat())
    p.add_argument("--output-dir",default="v84_daily_probe_output")
    p.add_argument("--ledger-dir",default="research/v88_daily_observations/ledger")
    args=p.parse_args()
    report=run_recent(args.anchor,output_dir=args.output_dir,ledger_dir=args.ledger_dir)
    print(json.dumps({k:report.get(k) for k in
        ("run_date_local","status","latest_observed_date","calendar_age_days",
         "traded_count","observed_traded_advance_share","ledger_status")},ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
