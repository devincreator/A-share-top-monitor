#!/usr/bin/env python3
"""BaoStock index price/amount probe and SZSE financing endpoint spot checks."""
import json
import pandas as pd
from pathlib import Path
OUT=Path("out");OUT.mkdir(exist_ok=True)
audit={"index":{},"szse":[]}
try:
 import baostock as bs
 login=bs.login()
 if login.error_code!="0": raise RuntimeError(login.error_msg)
 try:
  for symbol in ["sh.000985","sh.000300","sh.000852"]:
   line={"symbol":symbol}
   try:
    rs=bs.query_history_k_data_plus(symbol,"date,code,open,high,low,close,volume,amount",
      start_date="2022-01-01",end_date="2026-10-08",frequency="d",adjustflag="3")
    if rs.error_code!="0": raise ValueError(rs.error_msg)
    a=[]
    while rs.next(): a.append(rs.get_row_data())
    frame=pd.DataFrame(a,columns=rs.fields)
    if frame.empty: raise ValueError("no rows")
    frame["close"]=pd.to_numeric(frame.close,errors="coerce")
    frame["amount"]=pd.to_numeric(frame.amount,errors="coerce")
    f=OUT/f"baostock_{symbol.replace('.','_')}.csv";frame.to_csv(f,index=False)
    line.update(rows=len(frame),last_date=frame.date.max(),
      anchors={d:frame.loc[frame.date==d,["close","amount"]].to_dict("records")
        for d in ["2026-08-04","2026-09-24","2026-09-28","2026-10-08"]})
   except Exception as exc: line["error"]=f"{type(exc).__name__}: {str(exc)[:180]}"
   audit["index"][symbol]=line
 finally:
  bs.logout()
except Exception as e:
 audit["setup_error"]=str(e)
try:
 import akshare as ak
 for date in ["20240808","20250102","20250618"]:
  row={"date":date}
  try:
   data=ak.stock_margin_szse(date=date)
   row["cols"]=list(data.columns)
   row["rows"]=len(data)
   row["tail"]=data.tail(2).to_dict("records")
  except Exception as e:
   row["error"]=f"{type(e).__name__}: {str(e)[:180]}"
  audit["szse"].append(row)
except Exception as e:
 audit["szse_error"]=str(e)
(OUT/"baostock_probe_audit.json").write_text(json.dumps(audit,ensure_ascii=False,default=str,indent=2),encoding="utf-8")
print(json.dumps(audit,ensure_ascii=False,default=str))
