#!/usr/bin/env python3
"""Audit observed BaoStock historical securities and daily bars.

Does not assume exchange list rows are all equities or certify source publication PIT.
"""
import csv,json,hashlib,collections
from pathlib import Path
BASE=Path("v113_baostock_pilot")
OUT=Path("v113_baostock_audit");OUT.mkdir(exist_ok=True)
def load(name):
 p=BASE/(name+".csv")
 with p.open(newline="",encoding="utf-8-sig") as f:return list(csv.DictReader(f))
basics=load("stock_basic")
code_to_basic={}
for x in basics:
 if x["code"] in code_to_basic:raise ValueError("DUPLICATE_BASIC_CODE")
 code_to_basic[x["code"]]=x
equity={k:v for k,v in code_to_basic.items() if v["type"]=="1"}
sessions={}
for day in ("2022-06-20","2025-01-02","2026-09-21","2026-10-21"):
 rows=load("stocks_"+day)
 only=[r for r in rows if r["code"] in equity]
 eligible=[r for r in only if (not equity[r["code"]]["ipoDate"] or equity[r["code"]]["ipoDate"]<=day)
    and (not equity[r["code"]]["outDate"] or equity[r["code"]]["outDate"]>=day)]
 unexpected=[r for r in only if r not in eligible]
 stats=collections.Counter(r["tradeStatus"] for r in eligible)
 sessions[day]={"raw_all_security_list_rows":len(rows),"equity_type1_in_basic":len(only),
    "listed_universe_filtered":len(eligible),"basic_date_conflicts":len(unexpected),
    "trade_status":dict(stats),"sha256":hashlib.sha256((BASE/("stocks_"+day+".csv")).read_bytes()).hexdigest()}
history={}
for code in ("sh.600000","sz.000001","sh.600519"):
 rows=load("history_"+code.replace(".","_"))
 count=collections.Counter(r["tradestatus"] for r in rows)
 missing=collections.Counter(r["isST"] for r in rows)
 actual={r["date"] for r in rows}
 if len(actual)!=len(rows):raise ValueError("HIST_DATE_DUPLICATES")
 assert all(r["code"]==code for r in rows),"CODE_MISMATCH"
 history[code]={"days":len(rows),"first":rows[0]["date"],"last":rows[-1]["date"],
    "trade_status":dict(count),"st_flags":dict(missing),
    "sha256":hashlib.sha256((BASE/("history_"+code.replace(".","_")+".csv")).read_bytes()).hexdigest()}
report={"version":"V113","observed_historical_sessions":sessions,
    "full_basic_rows":len(basics),"equity_type1_basic_count":len(equity),
    "pilot_stock_histories":history,"source":"BAOSTOCK","source_day_availability_proven":True,
    "all_days_2022_2026_captured":False,"full_universe_pit_certified":False,
    "production_updates_allowed":False,"formal_v113_pass":False}
(OUT/"audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(report,ensure_ascii=False),flush=True)
