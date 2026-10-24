#!/usr/bin/env python3
"""V113 historical stock-level archive pilot: bounded AKShare Eastmoney symbol batching.

Research-only source acquisition. Explicit no-survivorship certification.
"""
import csv,hashlib,json,time,re,signal
from pathlib import Path
from datetime import date
import akshare as ak
ROOT=Path("v113_akshare_multiyear");ROOT.mkdir(exist_ok=True)
SYMBOLS=["600519","000001","300750","600000","000002","002594","688981","601318","600036","300059","000858","603259"]
FIELDS=["日期","股票代码","开盘","收盘","最高","最低","成交量","成交额","涨跌幅"]
def timed_out(_sig,_frame):raise TimeoutError("AKSHARE_REQUEST_TIMEOUT")
signal.signal(signal.SIGALRM,timed_out)
seen=set();manifest=[]
for idx,code in enumerate(SYMBOLS):
 rec={"stock":code,"source":"AKSHARE_EASTMONEY","adjust":"","date_requested":["2022-01-01","2026-10-21"],"status":"BLOCKED"}
 try:
  signal.alarm(30)
  df=ak.stock_zh_a_hist(symbol=code,period="daily",start_date="20220101",end_date="20261021",adjust="")
  signal.alarm(0)
  if df is None or df.empty:raise ValueError("EMPTY_HISTORY")
  if not set(FIELDS).issubset(df.columns):raise ValueError("SCHEMA_MISMATCH")
  dates=df["日期"].astype(str).tolist()
  if len(dates)!=len(set(dates)) or dates!=sorted(dates):raise ValueError("DUPLICATE_OR_UNSORTED_DATE")
  if any(d<"2022-01-01" or d>"2026-10-21" for d in dates):raise ValueError("DATE_LEAK")
  if any(str(v)!=code for v in df["股票代码"].astype(str)):raise ValueError("SYMBOL_MISMATCH")
  raw=df.to_csv(index=False).encode("utf-8-sig")
  (ROOT/(code+".csv")).write_bytes(raw)
  rec.update(status="SOURCE_BARS_VALIDATED_RESEARCH",rows=len(df),min_date=dates[0],max_date=dates[-1],
       found_sep_2026=any("2026-09" in x for x in dates),
       found_oct_2026=any("2026-10" in x for x in dates),
       sha256=hashlib.sha256(raw).hexdigest())
 except Exception as e:rec["error"]=type(e).__name__+":"+str(e)[:150]
 finally:signal.alarm(0)
 manifest.append(rec);print(json.dumps(rec,ensure_ascii=False),flush=True)
 time.sleep(.7)
summary={"version":"V113","pilot_count":len(SYMBOLS),"valid_symbols":sum(r["status"]=="SOURCE_BARS_VALIDATED_RESEARCH" for r in manifest),
 "date_coverage_2022_2026_full_market_certified":False,"historical_listed_universe_certified":False,
 "delisted_and_suspended_certified":False,"formal_signal_allowed":False,"symbol_reports":manifest}
(ROOT/"manifest.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({k:v for k,v in summary.items() if k!="symbol_reports"},ensure_ascii=False))
