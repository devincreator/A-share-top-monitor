#!/usr/bin/env python3
"""List exact SH/SZ stock-calendar missing pairs from 24 actual archived BaoStock source shards."""
import argparse,csv,gzip,itertools,json,hashlib
from collections import Counter
from pathlib import Path
from baostock_shard import basic_list, listed_on_session
def go(a):
 with open(a.anchor,newline="",encoding="utf-8") as f:
  dates=[r["source_trade_date"] for r in csv.DictReader(f)]
 if len(dates)!=1129 or dates!=sorted(set(dates)):raise ValueError("BAD_CALENDAR")
 stocks=basic_list(a.basic)
 found=set();gaps=[]
 for n in range(24):
  filename=Path(a.shards)/("stock_bars_shard_%02d.csv.gz"%n)
  if not filename.is_file():raise ValueError("MISSING_SHARD")
  with gzip.open(filename,"rt",newline="",encoding="utf-8") as f:
   for code,rs in itertools.groupby(csv.DictReader(f),key=lambda x:x["code"]):
    if code not in stocks or code in found:raise ValueError("DUPLICATE_STOCK")
    found.add(code)
    rows=list(rs)
    seen={r["date"] for r in rows}
    if len(seen)!=len(rows):raise ValueError("DUPLICATE_SOURCE_DAY")
    basic=stocks[code]
    for d in dates:
     if basic.get("ipoDate") and d<basic["ipoDate"]:continue
     if basic.get("outDate") and d>basic["outDate"]:continue
     if d not in seen:
      gaps.append({"date":d,"code":code,"ipoDate":basic.get("ipoDate"),
       "outDate":basic.get("outDate"),"code_name":basic.get("code_name"),
       "status":"UNKNOWN_NOT_CLASSIFIED_AS_SUSPENDED"})
 # Securities whose last day predates 2022-02-23 legitimately have no bar rows.
 no_bars=set(stocks)-found
 for code in no_bars:
  b=stocks[code]
  active=[d for d in dates if listed_on_session(b,d)]
  if active:raise ValueError("LISTED_WITHOUT_BAR_"+code)
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 with (out/"exact_shsz_missing_stock_days.csv").open("w",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=list(gaps[0]) if gaps else ["date","code"])
  w.writeheader();w.writerows(sorted(gaps,key=lambda x:(x["date"],x["code"])))
 count=Counter(x["date"] for x in gaps)
 report={"scope":"SH_SZ_ONLY","listed_symbols":len(stocks),"target_sessions":len(dates),
  "missing_stock_day_pairs":len(gaps),"affected_trading_dates":len(count),
  "dates_with_counts":dict(sorted(count.items())),
  "affected_symbols":len(set(x["code"] for x in gaps)),
  "out_of_window_registry_codes":len(no_bars),
  "missing_pairs":sorted(gaps,key=lambda x:(x["date"],x["code"])),
  "source_quality":"BAOSTOCK_HISTORIC_RAW_GAP_LIST_NOT_PROOF_OF_SUSPENSION",
  "formal_signal_allowed":False}
 (out/"audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":
 p=argparse.ArgumentParser()
 for name in ("anchor","basic","shards","out"):p.add_argument("--"+name,required=True)
 go(p.parse_args())
