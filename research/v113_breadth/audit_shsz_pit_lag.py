#!/usr/bin/env python3
"""V113 SH/SZ release-lag audit: verify T-1 as-of mechanism, not provider's historic publishing clock."""
import argparse,csv,hashlib,json
from datetime import datetime,time,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import baostock as bs
def decide(trading_dates):
 if trading_dates!=sorted(set(trading_dates)):raise ValueError("NON_MONOTONIC_TRADING_CALENDAR")
 rows=[];local=ZoneInfo("Asia/Shanghai")
 for i in range(1,len(trading_dates)):
  observed=trading_dates[i-1]; decision=trading_dates[i]
  cutoff=datetime.combine(datetime.fromisoformat(observed).date(),time(15,0),local)
  used=datetime.combine(datetime.fromisoformat(decision).date(),time(9,30),local)
  if not cutoff<used or not observed<decision:raise ValueError("FUTURE_LEAK")
  rows.append({"decision_date":decision,"latest_allowed_bar_date":observed,
    "bar_session_close_cn":cutoff.isoformat(),
    "decision_time_cn":used.isoformat(),"time_check_pass":True,
    "historical_actual_publish_time_verified":False,
    "source_revision_free_asof_snapshot_verified":False})
 return rows
def run(out):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 s=bs.login()
 if s.error_code!="0":raise RuntimeError(s.error_msg)
 try:
  r=bs.query_trade_dates(start_date="2022-02-23",end_date="2026-10-21")
  if r.error_code!="0":raise RuntimeError(r.error_msg)
  all_rows=[]
  while r.next():all_rows.append(dict(zip(r.fields,r.get_row_data())))
 finally:bs.logout()
 if not all_rows:raise ValueError("EMPTY_OFFICIAL_CALENDAR_CANDIDATE")
 p=out/"baostock_trade_calendar_raw.csv"
 with p.open("w",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=list(all_rows[0]));w.writeheader();w.writerows(all_rows)
 days=[r["calendar_date"] for r in all_rows if r["is_trading_day"]=="1"]
 if len(days)!=1129 or days[0]!="2022-02-23" or days[-1]!="2026-10-21":
  raise ValueError("CALENDAR_NOT_SAME_FROZEN_TARGET")
 rows=decide(days)
 with (out/"decision_asof_lag_evidence.csv").open("w",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 result={"version":"V113-SHSZ","trade_dates":len(days),"decision_dates":len(rows),
   "lag_policy":"T_BAR_15:00_CN_NOT_EARLIER_THAN_T_PLUS_1_09:30_CN",
   "asof_time_boundary_violations":0,
   "mechanical_no_future_price_use_pass":True,
   "historical_publication_timestamp_observations":0,
   "historical_actual_release_pit_certified":False,
   "historical_source_versions_asof_each_day_certified":False,
   "source_reconstruction_collection_is_retrospective":True,
   "time_certification_status":"ASSUMED_LAG_MECHANISM_PASS_ACTUAL_PIT_BLOCKED",
   "formal_signal_allowed":False,
   "calendar_sha256":hashlib.sha256(p.read_bytes()).hexdigest(),
   "asof_csv_sha256":hashlib.sha256((out/"decision_asof_lag_evidence.csv").read_bytes()).hexdigest()}
 (out/"acceptance.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--out",required=True);a=p.parse_args();run(a.out)
