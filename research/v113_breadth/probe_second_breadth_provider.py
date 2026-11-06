#!/usr/bin/env python3
"""Probe independent free daily published breadth as fallback, not per-stock verified evidence."""
import json,hashlib,urllib.request,argparse,re
from pathlib import Path
def probe(day,out):
    u="https://a.finews.fyi/"+day
    r={"date":day,"source_url":u,"status":"UNAVAILABLE","stock_universe_certified":False}
    try:
        req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=15) as response:
            b=response.read(1000001)
            if len(b)>1000000:raise ValueError("OVERSIZE_RESPONSE")
            if response.status!=200:raise ValueError("HTTP_"+str(response.status))
        text=b.decode("utf-8","replace")
        raw=Path(out)/("source_"+day+".html");raw.write_bytes(b)
        for term in ("上涨","下跌","平盘"):
            m=re.search(r".{0,120}"+term+r".{0,220}",text)
            r["sample_"+term]=re.sub("<[^>]+>"," ",m.group(0))[:220] if m else None
        r.update(status="RAW_HTML_CAPTURED_UNVERIFIED",sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))
    except Exception as e:r["error"]=type(e).__name__+":"+str(e)[:160]
    return r
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);a=p.parse_args()
    folder=Path(a.out);folder.mkdir(parents=True,exist_ok=True)
    records=[probe(d,folder) for d in ("2026-09-30","2026-09-21","2026-10-21")]
    (folder/"probe.json").write_text(json.dumps(records,ensure_ascii=False,indent=2)+"\n")
    for r in records:print(json.dumps(r,ensure_ascii=False),flush=True)
