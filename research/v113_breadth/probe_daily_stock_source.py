#!/usr/bin/env python3
"""V113 zero-auth per-trade-date daily stock bars: bounded independent free provider pilot."""
import argparse,csv,hashlib,io,json,urllib.request
from pathlib import Path
BASE="https://money-tree.eyunzhu.com"
def probe(day,out,*,open_url=urllib.request.urlopen):
    ymd=day.replace("-","")
    if len(ymd)!=8 or not ymd.isdigit():raise ValueError("INVALID_DAY")
    link=BASE+"/daily_kline/date/"+ymd+".csv"
    req=urllib.request.Request(link,headers={"User-Agent":"Mozilla/5.0 (noncommercial research evidence)"})
    result={"date":day,"source":link,"status":"FAILED","research_only":True,
            "formal_signal_allowed":False}
    try:
        with open_url(req,timeout=25) as r:
            content=r.read(3_000_001)
            if len(content)>3_000_000:raise ValueError("OVERSIZE")
            if r.status!=200:raise ValueError("HTTP_"+str(r.status))
        text=content.decode("utf-8-sig")
        rows=list(csv.DictReader(io.StringIO(text)))
        if not rows or len(rows)>20000:raise ValueError("EMPTY_OR_IMPLAUSIBLE_ROWS")
        headers=list(rows[0])
        dest=Path(out);dest.mkdir(parents=True,exist_ok=True)
        (dest/("daily_"+ymd+".csv")).write_bytes(content)
        result.update(status="SOURCE_BYTES_OBSERVED_NOT_YET_VALIDATED",raw_sha256=hashlib.sha256(content).hexdigest(),
            total_rows=len(rows),columns=headers[:32],
            first_sample={k:str(v)[:40] for k,v in rows[0].items()})
    except Exception as exc:
        result["error"]=type(exc).__name__+":"+str(exc)[:170]
    return result
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);p.add_argument("--dates",nargs="+",required=True);a=p.parse_args()
    reports=[probe(d,a.out) for d in a.dates]
    target=Path(a.out)/"provider_probe.json";target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(reports,ensure_ascii=False,indent=2)+"\n")
    for x in reports:print(json.dumps(x,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
