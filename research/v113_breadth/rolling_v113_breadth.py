#!/usr/bin/env python3
"""Research as-of daily breadth factors from original daily bars, never future rows."""
import argparse,csv,gzip,hashlib,json
from collections import defaultdict,deque,Counter
from pathlib import Path
from decimal import Decimal
WINDOWS=(20,60,120,252)
def per_stock_features(rows):
 # Yield one original trading bar at a time. Suspended rows never enter a price window.
 history=deque(maxlen=252)
 prev=None
 for r in rows:
  d=r["date"]
  if prev is not None and d<=prev:raise ValueError("UNSORTED_STOCK_BAR_DATES")
  prev=d
  if r.get("status")=="SUSPENDED":
   yield d,{"suspended":1}
   continue
  close=float(r["close"])
  high=float(r["high"]);low=float(r["low"])
  if min(close,high,low)<=0 or low>high:raise ValueError("INVALID_PRICE_BAR")
  current=(close,high,low)
  prior=list(history)
  features={"traded":1}
  for n in (20,60,120):
   if len(prior)>=n-1:
    series=[x[0] for x in prior[-(n-1):]]+[close]
    features["ma_%d_eligible"%n]=1
    features["above_ma_%d"%n]=int(close>sum(series)/n)
  for n in (60,252):
   if len(prior)>=n-1:
    highs=[x[1] for x in prior[-(n-1):]]+[high]
    lows=[x[2] for x in prior[-(n-1):]]+[low]
    features["high_low_%d_eligible"%n]=1
    features["new_high_%d"%n]=int(high>=max(highs))
    features["new_low_%d"%n]=int(low<=min(lows))
  history.append(current)
  yield d,features
def iterate_shsz(src,shard):
 with gzip.open(src/("stock_bars_shard_%02d.csv.gz"%shard),"rt",encoding="utf-8",newline="") as f:
  current=None;rows=[]
  for r in csv.DictReader(f):
   if current is not None and current!=r["code"]:
    yield current,rows;rows=[]
   current=r["code"]
   rows.append({"date":r["date"],"status":"SUSPENDED" if r["tradestatus"]=="0" else "TRADING",
                "close":r["close"],"high":r["high"],"low":r["low"]})
  if current is not None:yield current,rows
def iterate_bj(src,shard):
 with gzip.open(src/("beijing_bars_%02d.csv.gz"%shard),"rt",encoding="utf-8",newline="") as f:
  current=None;rows=[]
  for r in csv.DictReader(f):
   if current is not None and current!=r["symbol"]:
    yield current,rows;rows=[]
   current=r["symbol"]
   rows.append({"date":r["date"],"status":"TRADING",
                "close":r["close"],"high":r["high"],"low":r["low"]})
  if current is not None:yield current,rows
def run(a):
 byday=defaultdict(Counter);seen=set()
 for folder,shards,source in [(Path(a.shsz_shards),range(24),"SHSZ"),
                               (Path(a.beijing_shards),range(8),"BSE")]:
  for s in shards:
   stream=iterate_shsz(folder,s) if source=="SHSZ" else iterate_bj(folder,s)
   for code,rows in stream:
    key=(source,code)
    if key in seen:raise ValueError("DUPLICATE_STOCK_IN_SHARDS")
    seen.add(key)
    for day,features in per_stock_features(rows):
     for field,value in features.items():byday[day][source+"_"+field]+=value
 with open(a.anchor,newline="",encoding="utf-8") as f:
  dates=[r["source_trade_date"] for r in csv.DictReader(f)]
 if len(dates)!=1129 or dates!=sorted(set(dates)):raise ValueError("BAD_ANCHOR")
 fields=sorted({k for c in byday.values() for k in c})
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 with (out/"breadth_rolling_research.csv").open("w",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=["date"]+fields);w.writeheader()
  for d in dates:
   w.writerow({"date":d,**{k:byday[d].get(k,"") for k in fields}})
 report={"version":"V113","status":"RESEARCH_FACTORS_ONLY",
  "strict_asof_windows":True,"no_future_observations_used":True,
  "security_series_processed":len(seen),"calendar_days":len(dates),
  "raw_sha256":hashlib.sha256((out/"breadth_rolling_research.csv").read_bytes()).hexdigest(),
  "formal_signal_allowed":False,
  "note":"MA windows count actual traded bars; suspension sessions are not silently forward-filled."}
 (out/"audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__":
 p=argparse.ArgumentParser()
 for key in ("shsz-shards","beijing-shards","anchor","out"):p.add_argument("--"+key,required=True)
 run(p.parse_args())
