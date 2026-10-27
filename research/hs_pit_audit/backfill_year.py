#!/usr/bin/env python3
"""Bounded daily backfill using pinned historical index calendar; not PIT-certified."""
import argparse,csv,hashlib,io,json,urllib.request,urllib.error,time
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
CAL="https://raw.githubusercontent.com/sky910140/financial-agent-takehome/e071088057946de60ba1622dec8a69acce1481cd/data/market/sse_composite.csv"
CAL_SHA="fc4bd4c4ee3b1659aec07e0622d8dc8ab7df95f8354b7b4f9230a3a05bfffd20"
ROOT=Path("research/historical_data")
def fetch(url):
 req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 A-share-research-data-audit"})
 with urllib.request.urlopen(req,timeout=35) as r:return r.read()
def run(year,max_days=35):
 cal=fetch(CAL)
 if hashlib.sha256(cal).hexdigest()!=CAL_SHA:raise ValueError("calendar hash conflict")
 sessions=sorted(r["date"].replace("-","") for r in csv.DictReader(io.StringIO(cal.decode("utf-8-sig"))) if r["date"].startswith(str(year)))
 if not (230<=len(sessions)<=250):raise ValueError(f"year {year} unexpected calendar sessions {len(sessions)}")
 day_dir=ROOT/str(year)/"daily";day_dir.mkdir(parents=True,exist_ok=True)
 report={"year":year,"calendar_sha256":CAL_SHA,"calendar_sessions":len(sessions),
         "data_source":"https://money-tree.eyunzhu.com/daily_kline/date/{yyyymmdd}.csv",
         "generated_at_utc":datetime.now(timezone.utc).isoformat(),
         "research_only":True,"universe_PIT_certified":False,"source_publication_PIT_certified":False,
         "formal_signal_allowed":False,"files":[],"failures":[]}
 for day in sessions:
  existing=day_dir/(day+".csv")
  if existing.exists():
   b=existing.read_bytes()
  elif max_days>0 and len([r for r in report["files"] if r.get("new_download")])>=max_days:
   continue
  else:
   try:b=fetch(report["data_source"].replace("{yyyymmdd}",day))
   except Exception as ex:
    report["failures"].append({"date":day,"error":str(ex)})\n    if isinstance(ex,urllib.error.HTTPError) and ex.code==429:\n     report["rate_limit_stopped_at"]=day\n     break\n    continue
  try:
   rows=list(csv.DictReader(io.StringIO(b.decode("utf-8-sig"))))
   if not rows or len(rows)<100 or not {"symbol","trade_date","open","close","vol"}.issubset(rows[0]):raise ValueError("invalid header/row_count")
   if any(x["trade_date"]!=day for x in rows):raise ValueError("mismatched dates")
   codes=[x["symbol"] for x in rows]
   if len(set(codes))!=len(codes):raise ValueError("duplicate ticker")
   hs=sum(s.endswith((".SH",".SZ")) for s in codes)
   if hs<100:raise ValueError("too few SSE/SZSE")
   isnew=not existing.exists()
   if isnew:existing.write_bytes(b)
   report["files"].append({"date":day,"rows_total":len(rows),"rows_sh_sz":hs,
          "sha256":hashlib.sha256(b).hexdigest(),"path":str(existing),"new_download":isnew})
  except Exception as ex:report["failures"].append({"date":day,"error":str(ex)})
 done={r["date"] for r in report["files"]}
 report["remaining_calendar_dates"]=[d for d in sessions if d not in done]
 report["all_days_raw_archived"]=not report["remaining_calendar_dates"] and not report["failures"]
 (ROOT/str(year)/"backfill_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
 print(json.dumps({"year":year,"done":len(done),"remaining":len(report["remaining_calendar_dates"]),"failures":len(report["failures"])}),flush=True)
 return report
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--year",type=int,required=True);p.add_argument("--max-days",type=int,default=35)
 a=p.parse_args();run(a.year,a.max_days)
