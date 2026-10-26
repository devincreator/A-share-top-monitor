#!/usr/bin/env python3
"""V113 BaoStock: test historical listings, suspensions and three nonadjacent stock date ranges."""
import hashlib,json,os,csv,io
from pathlib import Path
import baostock as bs
ROOT=Path("v113_baostock_pilot");ROOT.mkdir(exist_ok=True)
def capture_result(rs,name):
    if rs.error_code!="0":raise RuntimeError(name+":"+str(rs.error_code)+":"+rs.error_msg)
    rows=[]
    while rs.next():rows.append(rs.get_row_data())
    if not rows:raise ValueError(name+":EMPTY")
    data=io.StringIO();w=csv.writer(data);w.writerow(rs.fields);w.writerows(rows)
    raw=data.getvalue().encode("utf-8")
    (ROOT/(name+".csv")).write_bytes(raw)
    return {"name":name,"rows":len(rows),"fields":rs.fields,
            "sha256":hashlib.sha256(raw).hexdigest(),"sample":rows[:2]}
reports=[]
s=bs.login()
try:
    if s.error_code!="0":raise RuntimeError("LOGIN:"+s.error_code+":"+s.error_msg)
    for date in ("2022-06-20","2025-01-02","2026-09-21","2026-10-21"):
        try:
            r=capture_result(bs.query_all_stock(day=date),"stocks_"+date)
            r["date"]=date;r["status"]="OBSERVED_NOT_AUDITED"
            reports.append(r)
            print(json.dumps(r,ensure_ascii=False),flush=True)
        except Exception as e:
            report={"date":date,"status":"FAILED","error":str(e)[:250]}
            reports.append(report);print(json.dumps(report,ensure_ascii=False),flush=True)
    for code in ("sh.600000","sz.000001","sh.600519"):
        try:
            r=capture_result(bs.query_history_k_data_plus(code,
              "date,code,open,high,low,close,preclose,volume,amount,tradestatus,isST",
              start_date="2022-01-01",end_date="2026-10-21",frequency="d",adjustflag="3"),
              "history_"+code.replace(".","_"))
            r["code"]=code;r["status"]="OBSERVED_NOT_AUDITED";reports.append(r)
            print(json.dumps({k:v for k,v in r.items() if k!="sample"},ensure_ascii=False),flush=True)
        except Exception as e:
            report={"code":code,"status":"FAILED","error":str(e)[:250]}
            reports.append(report);print(json.dumps(report,ensure_ascii=False),flush=True)
    r=capture_result(bs.query_stock_basic(),"stock_basic")
    reports.append({**r,"status":"OBSERVED_NOT_AUDITED"})
    print(json.dumps({k:v for k,v in r.items() if k!="sample"},ensure_ascii=False),flush=True)
finally:
    bs.logout()
(ROOT/"audit.json").write_text(json.dumps(reports,ensure_ascii=False,indent=2)+"\n")
