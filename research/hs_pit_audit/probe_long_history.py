#!/usr/bin/env python3
"""Bounded historical all-stock daily source probe. Research, no PIT claims."""
import csv,hashlib,io,json,urllib.request
from pathlib import Path
DATES=["20070104","20080102","20090105","20100104","20110104","20120104","20130104","20140102","20150105","20160104","20170103","20180102","20190102","20200102","20210104","20220104","20230103","20240102","20250102"]
ROOT=Path("research/historical_data")
def main():
 report={"source":"https://money-tree.eyunzhu.com/daily_kline/date/YYYYMMDD.csv","status":"PILOT_RESEARCH_ONLY_NOT_PIT","results":[]}
 for d in DATES:
  url=f"https://money-tree.eyunzhu.com/daily_kline/date/{d}.csv"
  out={"date":d,"url":url}
  try:
   req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 A-share-research/1.0"})
   with urllib.request.urlopen(req,timeout=25) as r:
    b=r.read()
   rows=list(csv.DictReader(io.StringIO(b.decode("utf-8-sig"))))
   if len(rows)<100 or not {"symbol","trade_date","open","close"}.issubset(rows[0]):raise ValueError("invalid schema/short file")
   if any(r["trade_date"]!=d for r in rows):raise ValueError("date mismatch")
   if len({r["symbol"] for r in rows})!=len(rows):raise ValueError("duplicate symbol")
   chosen=[r for r in rows if r["symbol"].endswith((".SH",".SZ")) and len(r["symbol"])==9]
   if len(chosen)<100:raise ValueError("too few SSE/SZSE rows")
   dest=ROOT/d[:4]/"pilot";dest.mkdir(parents=True,exist_ok=True)
   p=dest/(d+".csv");p.write_bytes(b)
   out.update(status="RAW_SAMPLE_DOWNLOADED",rows=len(rows),hs_rows=len(chosen),sha256=hashlib.sha256(b).hexdigest(),relative_path=str(p))
  except Exception as e:out.update(status="BLOCKED",error=str(e))
  report["results"].append(out)
  print(out,flush=True)
 p=ROOT/"historical_source_probe_2007_2025.json"
 p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":main()
