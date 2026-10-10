"""Audit public Beijing Stock Exchange financing history for v27 three-market consistency."""
from pathlib import Path
import json
import pandas as pd
import time
import akshare as ak
OUT=Path("out");OUT.mkdir(exist_ok=True)
DATES=["20230801","20230901","20231201","20240301","20240603","20240902","20241202","20250303","20250603","20250901","20251201","20260302","20260601","20260731","20260804","20260805","20260924","20260928","20261008"]
rows=[]
for date in DATES:
  try:
    f=ak.stock_margin_bse(date=date)
    if f is None or f.empty:raise ValueError("empty dataframe")
    obs={"date":date,"rows":len(f),"columns":list(f.columns),"raw":f.iloc[0].to_dict()}
    rows.append(obs)
    print(json.dumps({**obs,"raw":str(obs["raw"])[:250]},ensure_ascii=False,default=str),flush=True)
  except Exception as ex:
    obs={"date":date,"error":f"{type(ex).__name__}: {str(ex)[:180]}"}
    rows.append(obs);print(json.dumps(obs,ensure_ascii=False),flush=True)
  time.sleep(.35)
(OUT/"bse_financing_samples.json").write_text(json.dumps(rows,ensure_ascii=False,default=str,indent=2),encoding="utf8")
