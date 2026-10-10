#!/usr/bin/env python3
"""Probe free historical daily CSI index turnover sources; output is audit-only."""
import requests,json,math
from pathlib import Path
P=Path("out");P.mkdir(exist_ok=True)
BASE="https://api.ashareapi.com/v1/kline"
codes=["sh000985","000985.CSI","csi000985","000985"]
report=[]
for code in codes:
 r={"source":"ashareapi kline","code":code}
 try:
  resp=requests.get(BASE,params={"code":code,"period":"day","count":500,"end":"2026-10-08"},timeout=22)
  r.update(http_code=resp.status_code,bytes=len(resp.content))
  if resp.status_code==200:
   result=resp.json()
   r["type"]=type(result).__name__
   r["root_keys"]=list(result)[:18] if isinstance(result,dict) else []
   records=result.get("data") if isinstance(result,dict) else result
   if isinstance(records,dict):
    for k in ("data","list","items","klines","bars"):
     if isinstance(records.get(k),list): records=records[k];break
   if isinstance(records,list):
    r["rows"]=len(records)
    r["first"]=str(records[0])[:600] if records else ""
    r["last"]=str(records[-1])[:600] if records else ""
    P.joinpath("ashareapi_"+code.replace(".","_")+".json").write_text(json.dumps(records,ensure_ascii=False),encoding="utf8")
   else:r["payload"]=str(result)[:400]
  else:r["response"]=resp.text[:300]
 except Exception as e:r["error"]=str(e)[:200]
 report.append(r)
 print(json.dumps(r,ensure_ascii=False),flush=True)
P.joinpath("ashareapi_source_audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
