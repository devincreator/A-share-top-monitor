#!/usr/bin/env python3
"""Independent V113 combined historical mainland A-stock breadth gate; no future values."""
import argparse,csv,hashlib,json
from pathlib import Path
def read(path,key):
 with open(path,newline="",encoding="utf-8") as f:
  rows=list(csv.DictReader(f))
 result={}
 for r in rows:
  if r[key] in result:raise ValueError("DUPLICATE_DATE_IN_CSV")
  result[r[key]]=r
 return result
def build(sh, bj, cal, *, sh_report=None,bj_report=None):
 if set(sh)-set(cal) or set(bj)-set(cal):raise ValueError("UNEXPECTED_DATE")
 days=[]
 for d in cal:
  a=sh.get(d);b=bj.get(d)
  if not a or not b:
   days.append({"date":d,"status":"SOURCE_MISSING","market_up":"","market_down":"",
     "market_flat":"","shsz_suspended":"","unknown":""})
   continue
  su=int(a["up"]);sd=int(a["down"]);sf=int(a["flat"]);ss=int(a["suspended"])
  bu=int(b["bj_up"]);bd=int(b["bj_down"]);bf=int(b["bj_flat"])
  shsz_gap=int(a["unresolved"]);bj_gap=int(b["bj_unknown_not_traded"])
  if shsz_gap<0 or bj_gap<0:raise ValueError("NEGATIVE_GAP")
  iscomplete=shsz_gap==0 and bj_gap==0
  days.append({"date":d,"status":"ALL_OBSERVED_NO_UNKNOWN" if iscomplete else "PARTIAL_UNKNOWN",
    "market_up":su+bu,"market_down":sd+bd,"market_flat":sf+bf,
    "shsz_suspended":ss,"unknown":shsz_gap+bj_gap,
    "shsz_expected":int(a["expected_listed_shsz"]),
    "beijing_expected":int(b["bj_expected_listed"]),
    "observed_stock_bars":int(a["security_days_with_status"])+int(b["bj_trading_bars"]),
    "bse_suspended_certified":False})
 clean=sum(x["status"]=="ALL_OBSERVED_NO_UNKNOWN" for x in days)
 maybe_pit=bool(sh_report and bj_report and
  sh_report.get("all_shsz_ticker_archives_present") and
  sh_report.get("failed_stock_codes")==0 and
  sh_report.get("missing_shsz_security_date_observations")==0 and
  not sh_report.get("issues") and
  bj_report.get("registry_count")==bj_report.get("captured_tickers") and
  bj_report.get("unresolved_beijing_security_days")==0 and
  bj_report.get("issue_count")==0)
 checks={
   "calendar_98pct_full_stock_observations":clean*100>=len(cal)*98,
   "shsz_archive_complete":bool(sh_report and sh_report.get("all_shsz_ticker_archives_present")),
   "bse_archive_complete":bool(bj_report and bj_report.get("registry_count")==bj_report.get("captured_tickers")),
   "all_stock_dates_without_unresolved":maybe_pit,
   "beijing_suspension_vs_flat_certified":False,
   "historical_universe_independently_reconciled":False,
 }
 accepted=all(checks.values())
 return days,{"version":"V113","status":"PASS" if accepted else ("PARTIAL" if sh and bj else "BLOCKED"),
    "target_days":len(cal),"all_observed_without_unknown_days":clean,
    "observed_day_fraction":round(clean/len(cal),8),
    "checks":checks,"production_updated":False,"formal_signal_allowed":False,
    "source_scope":"SH_SZ_BJ_WITH_EXPLICIT_QUALITY_LIMITATIONS"}
if __name__=="__main__":
 p=argparse.ArgumentParser()
 for n in ("anchor","shsz","beijing","shsz-audit","beijing-audit","out"):p.add_argument("--"+n,required=True)
 args=p.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
 with open(args.anchor,newline="",encoding="utf-8") as f:
  cal=[r["source_trade_date"] for r in csv.DictReader(f)]
 if len(cal)!=1129 or cal!=sorted(set(cal)):raise ValueError("NON_FROZEN_CALENDAR")
 daily,report=build(read(args.shsz,"date"),read(args.beijing,"date"),cal,
  sh_report=json.loads(Path(args.shsz_audit).read_text()),
  bj_report=json.loads(Path(args.beijing_audit).read_text()))
 with (out/"all_a_daily_breadth_research.csv").open("w",newline="",encoding="utf-8") as f:
  cols=list(dict.fromkeys(k for d in daily for k in d))
  w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(daily)
 report["csv_sha256"]=hashlib.sha256((out/"all_a_daily_breadth_research.csv").read_bytes()).hexdigest()
 (out/"acceptance.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(report,ensure_ascii=False))
