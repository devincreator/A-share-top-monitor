#!/usr/bin/env python3
"""V113 Beijing historical A-shares via free stock-history provider; independent SHA evidence."""
import argparse,csv,gzip,hashlib,json,time,signal
from datetime import date
from pathlib import Path
from decimal import Decimal
COLS=["date","symbol","open","high","low","close","volume","amount","pct_change","source"]
def cutoff(_sig,_frame):raise TimeoutError("PROVIDER_QUERY_TIMEOUT")
signal.signal(signal.SIGALRM,cutoff)
def readregistry(path):
 with open(path,newline="",encoding="utf-8-sig") as f:raw=list(csv.DictReader(f))
 vals={}
 for r in raw:
  code=r["code"]
  if code in vals:raise ValueError("DUPLICATE_CODE")
  if r["listed"]:date.fromisoformat(r["listed"])
  if r["delisted"]:date.fromisoformat(r["delisted"])
  vals[code]=r
 return vals
def compute(args):
 import akshare as ak
 registry=readregistry(args.registry)
 codes=sorted(registry)
 selected=[c for i,c in enumerate(codes) if i%args.shards==args.shard]
 if args.limit:selected=selected[:args.limit]
 out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
 manifest=[]
 gz=out/("beijing_bars_%02d.csv.gz"%args.shard)
 with gzip.open(gz,"wt",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=COLS);w.writeheader()
  for i,code in enumerate(selected):
   b=registry[code]
   record={"code":code,"status":"FAILED","listed":b["listed"],"delisted":b["delisted"]}
   for attempt in range(3):
    try:
     signal.alarm(35)
     df=ak.stock_zh_a_hist(symbol=code,period="daily",start_date="20220223",end_date="20261021",adjust="")
     signal.alarm(0)
     if df is None or df.empty:
      raise ValueError("EMPTY_HISTORY")
     need={"日期","股票代码","开盘","最高","最低","收盘","成交量","成交额","涨跌幅"}
     if not need.issubset(df.columns):raise ValueError("SCHEMA_CHANGED")
     sourcecsv=df.to_csv(index=False).encode("utf-8-sig")
     dates=df["日期"].astype(str).tolist()
     if dates!=sorted(set(dates)):raise ValueError("DUPLICATE_OR_UNSORTED_DATE")
     if any(str(x)!=code for x in df["股票代码"]):raise ValueError("RETURNED_CODE_MISMATCH")
     filtered=[]
     for _,r in df.iterrows():
      d=str(r["日期"])
      if d<b["listed"] or (b["delisted"] and d>b["delisted"]):continue
      if d>"2026-10-21":raise ValueError("DATA_AFTER_CUTOFF")
      change=Decimal(str(r["涨跌幅"]))
      close=Decimal(str(r["收盘"]))
      amount=Decimal(str(r["成交额"]))
      if not all(x.is_finite() for x in (change,close,amount)) or close<=0 or amount<0:raise ValueError("INVALID_PRICE")
      filtered.append({"date":d,"symbol":code,
        "open":str(r["开盘"]),"high":str(r["最高"]),"low":str(r["最低"]),
        "close":str(r["收盘"]),"volume":str(r["成交量"]),"amount":str(r["成交额"]),
        "pct_change":str(r["涨跌幅"]),"source":"AKSHARE_EASTMONEY"})
     if not filtered:raise ValueError("NO_LISTED_DAY_ROWS")
     for x in filtered:w.writerow(x)
     record.update(status="OBSERVED_TRADING_BARS_ONLY",rows=len(filtered),
        original_rows=len(df),earliest=filtered[0]["date"],latest=filtered[-1]["date"],
        "raw_source_sha256":hashlib.sha256(sourcecsv).hexdigest(),
        "suspension_status_certified":False,"attempts":attempt+1)
     break
    except Exception as e:
     record["error"]=type(e).__name__+":"+str(e)[:150]
     time.sleep(2*(attempt+1))
    finally:signal.alarm(0)
   manifest.append(record)
   if (i+1)%10==0 or i==len(selected)-1:
    print(json.dumps({"shard":args.shard,"done":i+1,"requested":len(selected),
      "successful":sum(x["status"]=="OBSERVED_TRADING_BARS_ONLY" for x in manifest)},ensure_ascii=False),flush=True)
   time.sleep(args.delay)
 report={"version":"V113","scope":"BEIJING_2022_2026_RESEARCH",
  "shard":args.shard,"shards":args.shards,"requested":len(selected),
  "successful":sum(r["status"]=="OBSERVED_TRADING_BARS_ONLY" for r in manifest),
  "archive_sha256":hashlib.sha256(gz.read_bytes()).hexdigest(),
  "individual_stock_evidence":manifest,"suspension_status_certified":False,"formal_signal_allowed":False}
 (out/("beijing_manifest_%02d.json"%args.shard)).write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({k:v for k,v in report.items() if k!="individual_stock_evidence"},ensure_ascii=False))
if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("--registry",required=True);p.add_argument("--out",required=True)
 p.add_argument("--shard",type=int,required=True);p.add_argument("--shards",type=int,required=True)
 p.add_argument("--limit",type=int);p.add_argument("--delay",type=float,default=.5);a=p.parse_args()
 if a.shards<1 or a.shards>32 or a.shard<0 or a.shard>=a.shards:raise ValueError("BAD_SHARD")
 compute(a)
