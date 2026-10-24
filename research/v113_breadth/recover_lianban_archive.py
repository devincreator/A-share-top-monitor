#!/usr/bin/env python3
"""V113 alternate route: archived lianbanwang daily breadth and strict textual provenance."""
import argparse,csv,hashlib,json,re,time,urllib.request
from pathlib import Path
def one(day,root):
    url="https://lianbanwang.com/days/"+day+".html"
    report={"date":day,"source":url,"status":"MISSING","formal_signal_allowed":False}
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=18) as r:
            raw=r.read(1250000)
        (root/"raw"/(day+".html")).write_bytes(raw)
        s=raw.decode("utf-8","replace")
        # Capture the page and its reported date; reject pages that redirect to another day.
        if day not in s:raise ValueError("DATE_NOT_FOUND")
        matches=list(re.finditer(r"上涨\s*([0-9,]{1,6})\s*家\s*下跌\s*([0-9,]{1,6})\s*家",s))
        if not matches:
            matches=list(re.finditer(r"上涨\s*([0-9,]{1,6})家.{0,100}下跌\s*([0-9,]{1,6})家",s))
        if not matches:raise ValueError("NO_MATCH")
        vals=[(int(x.group(1).replace(",","")),int(x.group(2).replace(",",""))) for x in matches]
        vals=[x for x in vals if 3500<=sum(x)<=8000]
        if not vals:raise ValueError("IMPLAUSIBLE_COUNTS")
        up,down=vals[0]
        report.update(status="RESEARCH_AGGREGATE_UNVERIFIED",up=up,down=down,raw_sha256=hashlib.sha256(raw).hexdigest(),match_count=len(vals))
    except Exception as exc:report["reason"]=str(exc)[:150]
    return report
def main():
    p=argparse.ArgumentParser();p.add_argument("--daily",required=True);p.add_argument("--out",required=True);a=p.parse_args()
    root=Path(a.out);(root/"raw").mkdir(parents=True,exist_ok=True)
    with open(a.daily,newline="",encoding="utf-8") as f:
        dates=[r["source_trade_date"] for r in csv.DictReader(f) if "2026-09-01"<=r["source_trade_date"]<="2026-10-21"]
    results=[]
    for d in dates:
        item=one(d,root);results.append(item);print(json.dumps(item,ensure_ascii=False),flush=True)
        time.sleep(.3)
    with (root/"breadth_candidates.csv").open("w",newline="",encoding="utf-8") as f:
        fields=["date","source","status","up","down","raw_sha256","formal_signal_allowed"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in results:w.writerow({k:r.get(k,"") for k in fields})
    report={"target":len(results),"candidate":sum(r["status"]=="RESEARCH_AGGREGATE_UNVERIFIED" for r in results),
       "failed":[r["date"] for r in results if r["status"]!="RESEARCH_AGGREGATE_UNVERIFIED"],
       "PIT_certified":False,"security_universe_certified":False,"formal_signal_allowed":False}
    (root/"coverage.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__":main()
