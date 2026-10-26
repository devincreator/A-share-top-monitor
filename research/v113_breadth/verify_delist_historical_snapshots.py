#!/usr/bin/env python3
"""V113-SHSZ date-scoped trade-status membership certification for outDate gaps."""
import argparse,csv,hashlib,json,time
from collections import defaultdict
from pathlib import Path
import baostock as bs
def collect(a):
 with open(a.gaps,newline="",encoding="utf-8") as f:rows=list(csv.DictReader(f))
 grouped=defaultdict(set)
 for x in rows:
  if x["date"]!=x.get("outDate"):raise ValueError("NOT_AT_DECLARED_DELISTING_DATE")
  grouped[x["date"]].add(x["code"])
 dates=sorted(grouped)
 if len(rows)!=41 or len(dates)!=32:raise ValueError("SOURCE_GAP_SET_CHANGED")
 chosen=[d for i,d in enumerate(dates) if i%a.shards==a.shard]
 result=[]
 login=bs.login()
 if login.error_code!="0":raise RuntimeError("BAOSTOCK_LOGIN_FAILED")
 try:
  for d in chosen:
   r={"date":d,"requested_codes":sorted(grouped[d]),"status":"FAILED"}
   try:
    src=bs.query_all_stock(day=d)
    if src.error_code!="0":raise RuntimeError("BAOSTOCK_QUERY_FAILED_"+src.error_msg[:100])
    listing={}
    digest=hashlib.sha256()
    count=0
    while src.next():
     line=dict(zip(src.fields,src.get_row_data()))
     code=line.get("code","");status=line.get("tradeStatus","")
     if code in listing:raise ValueError("DUPLICATE_SOURCE_SECURITY")
     listing[code]=status
     digest.update((code+"|"+status+"\n").encode("utf-8"))
     count+=1
    if count<3000:raise ValueError("IMPLAUSIBLY_SHORT_HISTORICAL_LIST")
    statuses={c:listing.get(c,"NOT_IN_HISTORICAL_LIST") for c in grouped[d]}
    if any(s not in ("0","1","NOT_IN_HISTORICAL_LIST") for s in statuses.values()):
     raise ValueError("UNKNOWN_HISTORICAL_TRADE_STATUS")
    r.update(status="VERIFIED_HISTORICAL_DATE_LIST",full_source_rows=count,
      code_status=statuses,raw_source_response_digest_sha256=digest.hexdigest())
   except Exception as e:r["error"]=type(e).__name__+":"+str(e)[:180]
   result.append(r)
   print(json.dumps(r,ensure_ascii=False),flush=True)
   time.sleep(.4)
 finally:bs.logout()
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 obj={"version":"V113-SHSZ","shard":a.shard,"shards":a.shards,
      "source_dates":len(chosen),"verified_dates":sum(x["status"]=="VERIFIED_HISTORICAL_DATE_LIST" for x in result),
      "historical_raw_source":"BAOSTOCK_QUERY_ALL_STOCK_DATED", "results":result,
      "formal_signal_allowed":False}
 (out/("dated_membership_shard_%02d.json"%a.shard)).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({k:v for k,v in obj.items() if k!="results"},ensure_ascii=False))
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--gaps",required=True);p.add_argument("--out",required=True)
 p.add_argument("--shard",type=int,required=True);p.add_argument("--shards",type=int,default=8)
 a=p.parse_args()
 if a.shards!=8 or not 0<=a.shard<8:raise ValueError("FIXED_EIGHT_SHARD_ONLY")
 collect(a)
