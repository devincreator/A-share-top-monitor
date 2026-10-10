#!/usr/bin/env python3
"""Public market snapshot for 2026-10-09; no private trading logic."""
import json, traceback, time
from pathlib import Path
O=Path("out");O.mkdir(exist_ok=True)
DATE="2026-10-09"
r={"date":DATE,"sources":{},"failures":[]}
try:
 import requests
 payload=requests.get("https://api.ashareapi.com/v1/kline",params={"code":"sh000985","period":"day","count":5,"end":DATE},timeout=30).json()
 row=next((x for x in payload.get("data",[]) if x.get("date")==DATE),None)
 r["sources"]["ashareapi_sh000985"]=row
except Exception as e:r["failures"].append("ashareapi "+repr(e))
try:
 import akshare as ak
 r["akshare_version"]=getattr(ak,"__version__",None)
 for code in ["000985","000300","000852"]:
  try:
   df=ak.stock_zh_index_daily_tx(symbol="sh"+code,start_date="20261001",end_date="20261009")
   if not df.empty:
    row=df.iloc[-1].to_dict()
    r["sources"]["tx_"+code]=row
  except Exception as e:r["failures"].append("Tencent "+code+" "+repr(e))
 try:
  f=ak.stock_margin_bse(date="20261009")
  r["sources"]["bse_finance"]=f.iloc[0].to_dict() if not f.empty else None
 except Exception as e:r["failures"].append("BSE "+repr(e))
 for place in ["sh","sz"]:
  try:
   f=getattr(ak,"macro_china_market_margin_"+place)().reset_index()
   datecol=[x for x in f.columns if "日期" in str(x) or str(x).lower() in ("date","index")]
   r["sources"]["jin10_"+place]=f.tail(3).to_dict("records")
  except Exception as e:r["failures"].append("Jin10 "+place+" "+repr(e))
 for place in ["sh","sz"]:
  func="stock_margin_"+place+"se" if place=="sh" else "stock_margin_szse"
  try:
   f=getattr(ak,func)(date="20261009")
   r["sources"][func]={"columns":list(f.columns),"rows":len(f),"head":f.head(3).to_dict("records")}
  except Exception as e:r["failures"].append(func+" "+repr(e))
except Exception as e:r["failures"].append("AKShare "+repr(e))
try:
 import requests
 response=requests.get("https://www.csindex.com.cn/csindex-home/perf/index-perf",params={"indexCode":"000985","startDate":"20261009","endDate":"20261009"},timeout=25)
 r["sources"]["csi_official_1009"]={"http":response.status_code,"data":response.json() if response.status_code==200 else response.text[:200]}
except Exception as e:r["failures"].append("csindex "+repr(e))
(O/"v30_20261009_market_snapshot.json").write_text(json.dumps(r,ensure_ascii=False,indent=2,default=str),encoding="utf8")
print(json.dumps(r,ensure_ascii=False,default=str)[:15000])
