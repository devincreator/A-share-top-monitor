#!/usr/bin/env python3
"""V113 dated BaoStock membership vs retrospective IPO/outDate rows; no artificial repair."""
import argparse,csv,hashlib,json,time
from pathlib import Path
import baostock as bs
from audit_shsz_a_issuers import OFFICIAL,eligible
DAYS=("2022-12-30","2024-12-31","2025-04-30","2025-12-31","2026-09-30")
def inspect(basic,out):
 with open(basic,encoding="utf-8-sig",newline="") as f:
  stocks={r["code"]:r for r in csv.DictReader(f) if r["type"]=="1" and r["code"].startswith(("sh.","sz."))}
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 login=bs.login()
 if login.error_code!="0":raise RuntimeError(login.error_msg)
 reports=[]
 try:
  for day in DAYS:
   response=bs.query_all_stock(day=day)
   if response.error_code!="0":raise RuntimeError(response.error_msg)
   entries=[]
   while response.next():entries.append(dict(zip(response.fields,response.get_row_data())))
   if len(entries)<3000:raise ValueError("SHORT_HISTORY_"+day)
   if len(set(r["code"] for r in entries))!=len(entries):raise ValueError("DUPLICATED_DATE_CODES")
   p=out/("dated_"+day+".csv")
   with p.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=response.fields);w.writeheader();w.writerows(entries)
   dated={r["code"]:r["tradeStatus"] for r in entries if r["code"] in stocks}
   predicted={code for code,b in stocks.items() if eligible(b,day)}
   extras=sorted(predicted-set(dated))
   omitted=sorted(set(dated)-predicted)
   r={"date":day,"dated":len(dated),"basic":len(predicted),
    "basic_only_not_in_dated":extras,"dated_only_not_in_basic_interval":omitted,
    "dated_status":{"active":sum(s=="1" for s in dated.values()),
      "suspended":sum(s=="0" for s in dated.values())},
    "raw_sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
   for ex in ("sh","sz"):
    r[ex+"_dated"]=sum(k.startswith(ex+".") for k in dated)
    r[ex+"_basic"]=sum(k.startswith(ex+".") for k in predicted)
   if day in OFFICIAL:
    benchmark=dict(zip(("sh","sz"),OFFICIAL[day]))
    r["official_a_issuer_benchmark"]=benchmark
    r["delta_dated_minus_official"]={ex:r[ex+"_dated"]-benchmark[ex] for ex in ("sh","sz")}
   reports.append(r);print(json.dumps(r,ensure_ascii=False),flush=True)
   time.sleep(.3)
 finally:bs.logout()
 obj={"version":"V113-SHSZ","status":"SOURCE_DATED_RESEARCH_AUDIT",
   "snapshot_dates":len(reports),"reports":reports,
   "independent_exchange_stock_list_certified":False,
   "publication_pit_certified":False,"formal_signal_allowed":False}
 (out/"acceptance.json").write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--basic",required=True);p.add_argument("--out",required=True);a=p.parse_args()
 inspect(a.basic,a.out)
