#!/usr/bin/env python3
"""Historically dated listed/security status probe on delisting effective days."""
import baostock as bs,json,hashlib,csv,io,time
from pathlib import Path
out=Path("v113_delist_effective_probe");out.mkdir(exist_ok=True)
checks={
 "2025-05-22":["sz.300630"],
 "2025-05-27":["sh.600705","sh.601028"],
 "2025-04-30":["sz.300117"],
 "2026-10-19":["sh.601059","sh.601198"]
}
r=bs.login()
if r.error_code!="0":raise RuntimeError("LOGIN_FAILED")
reports=[]
try:
 for d,codes in checks.items():
  obj={"date":d,"requested_codes":codes,"status":"SOURCE_FAILED"}
  try:
   result=bs.query_all_stock(day=d)
   if result.error_code!="0":raise RuntimeError(result.error_msg)
   rows=[]
   while result.next():rows.append(dict(zip(result.fields,result.get_row_data())))
   obj.update(status="SOURCE_OBSERVED",
    full_source_rows=len(rows),
    code_status={c:next((r.get("tradeStatus") for r in rows if r.get("code")==c),"NOT_IN_HISTORICAL_LIST")
     for c in codes},
    source_sha256=hashlib.sha256("\n".join(r["code"]+"|"+r.get("tradeStatus","") for r in rows).encode()).hexdigest())
  except Exception as exc:obj["error"]=type(exc).__name__+":"+str(exc)[:180]
  reports.append(obj)
  print(json.dumps(obj,ensure_ascii=False),flush=True)
finally:bs.logout()
(out/"audit.json").write_text(json.dumps({"version":"V113-SHSZ","status":"RESEARCH_DATED_MEMBERSHIP_PROBE",
  "snapshots":reports,"formal_signal_allowed":False},ensure_ascii=False,indent=2)+"\n")
