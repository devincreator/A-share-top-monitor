#!/usr/bin/env python3
"""V113 independent Beijing exchange provider pilot, with code migration checks."""
import json,hashlib,signal,time
from pathlib import Path
P=Path("v113_beijing_pilot");P.mkdir(exist_ok=True)
def alarm(_,__):raise TimeoutError("BJ_PROVIDER_TIMEOUT")
signal.signal(signal.SIGALRM,alarm)
records=[]
try:
 import akshare as ak
 for name in ("stock_info_bj_name_code","stock_bj_a_spot_em"):
  result={"kind":name,"status":"BLOCKED"}
  try:
   signal.alarm(40)
   df=getattr(ak,name)()
   signal.alarm(0)
   if df is None or df.empty:raise ValueError("NO_STOCKS")
   payload=df.to_csv(index=False).encode("utf-8-sig")
   (P/(name+".csv")).write_bytes(payload)
   result.update(status="OBSERVED_UNVERIFIED",rows=len(df),columns=list(df.columns),first=df.head(2).astype(str).to_dict("records"),sha256=hashlib.sha256(payload).hexdigest())
  except Exception as e:result["error"]=type(e).__name__+":"+str(e)[:160]
  finally:signal.alarm(0)
  records.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
 for code in ("920931","872931","920680","920305","920002"):
  result={"kind":"history","code":code,"status":"BLOCKED"}
  try:
   signal.alarm(35)
   df=ak.stock_zh_a_hist(symbol=code,period="daily",start_date="20220101",end_date="20261021",adjust="")
   signal.alarm(0)
   if df is None or df.empty:raise ValueError("NO_BARS")
   payload=df.to_csv(index=False).encode("utf-8-sig")
   (P/(code+".csv")).write_bytes(payload)
   days=df["日期"].astype(str).tolist()
   result.update(status="OBSERVED_UNVERIFIED",rows=len(df),first=days[0],last=days[-1],
      has_sep_2026=any(s.startswith("2026-09") for s in days),
      has_oct_2026=any(s.startswith("2026-10") for s in days),
      sha256=hashlib.sha256(payload).hexdigest())
  except Exception as e:result["error"]=type(e).__name__+":"+str(e)[:170]
  finally:signal.alarm(0)
  records.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
  time.sleep(.5)
except Exception as e:
 records.append({"fatal":type(e).__name__+":"+str(e)[:200]})
(P/"audit.json").write_text(json.dumps({"version":"V113","scope":"BSE_PILOT","records":records,"formal_signal_allowed":False},ensure_ascii=False,indent=2)+"\n")
