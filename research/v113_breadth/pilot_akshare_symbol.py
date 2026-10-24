#!/usr/bin/env python3
"""Bounded AKShare Eastmoney history probe, never promotes unverifiable observations."""
import hashlib,json,signal,sys
from pathlib import Path
ROOT=Path("v113_akshare_symbol_pilot");ROOT.mkdir(exist_ok=True)
def timeout(_sig,_frame):raise TimeoutError("provider took >35 seconds")
signal.signal(signal.SIGALRM,timeout)
reports=[]
try:
 import akshare as ak
 for code in ("600519","000001","300750"):
  rec={"provider":"AKSHARE_EASTMONEY","code":code,"status":"BLOCKED"}
  signal.alarm(35)
  try:
   df=ak.stock_zh_a_hist(symbol=code,period="daily",start_date="20260101",end_date="20261021",adjust="")
   if df is None or df.empty:raise ValueError("EMPTY")
   datecol="日期"
   dates=set(df[datecol].astype(str).tolist())
   raw=df.to_csv(index=False).encode("utf-8-sig")
   (ROOT/(code+".csv")).write_bytes(raw)
   rec.update(status="SOURCE_BYTES_OBSERVED",rows=len(df),has_2026_september=any(d.startswith("2026-09") for d in dates),
      has_2026_october=any(d.startswith("2026-10") for d in dates),
      earliest=str(df.iloc[0][datecol]),latest=str(df.iloc[-1][datecol]),
      columns=list(df.columns),raw_sha256=hashlib.sha256(raw).hexdigest())
  except Exception as e:rec["error"]=type(e).__name__+":"+str(e)[:200]
  finally:signal.alarm(0)
  reports.append(rec);print(json.dumps(rec,ensure_ascii=False),flush=True)
except Exception as e:
 reports.append({"provider":"AKSHARE_EASTMONEY","status":"FAILED_TO_INITIALIZE","error":str(e)[:230]})
(ROOT/"audit.json").write_text(json.dumps(reports,ensure_ascii=False,indent=2)+"\n")
