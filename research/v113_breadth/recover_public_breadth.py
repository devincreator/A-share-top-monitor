#!/usr/bin/env python3
"""V113 fallback: daily historical public breadth, not a replacement for security-level PIT."""
import argparse,csv,hashlib,json,re,time,urllib.request
from html import unescape
from pathlib import Path

def text_of(raw):
    s=unescape(raw.decode("utf-8","replace"))
    s=re.sub(r"(?is)<(script|style).*?</\1>"," ",s)
    s=re.sub(r"(?s)<[^>]*>"," ",s)
    return re.sub(r"\s+"," ",s)

def parse_counts(text):
    patterns=[
      (r"上涨\s*([\d,]{1,6})\s*家",r"下跌\s*([\d,]{1,6})\s*家"),
      (r"([\d,]{1,6})\s*只上涨",r"([\d,]{1,6})\s*只下跌"),
      (r"上涨家数\s*([\d,]{1,6})",r"下跌家数\s*([\d,]{1,6})"),
    ]
    for a,b in patterns:
        ups=list(re.finditer(a,text))
        downs=list(re.finditer(b,text))
        if not ups or not downs:continue
        pairs=sorted(((abs(x.start()-y.start()),x,y) for x in ups for y in downs),key=lambda v:v[0])
        for delta,up,down in pairs:
            if delta>300:continue
            u=int(up.group(1).replace(",",""));d=int(down.group(1).replace(",",""))
            if 0<u<8000 and 0<d<8000 and 3000<=u+d<=8000:
                return {"up":u,"down":d,"distance":delta,"context":text[max(0,min(up.start(),down.start())-45):max(up.end(),down.end())+55]}
    return None

def pull(url,path,day):
    obj={"url":url,"day":day,"status":"FAILED"}
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=17) as r:
            raw=r.read(1200001)
            if len(raw)>1200000:raise ValueError("LARGE_RESPONSE")
            if r.status!=200:raise ValueError("HTTP_"+str(r.status))
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        t=text_of(raw)
        if day not in t:raise ValueError("TARGET_DAY_NOT_IN_TEXT")
        result=parse_counts(t)
        if not result:raise ValueError("NO_UNAMBIGUOUS_BREADTH_PAIR")
        obj.update(result)
        obj.update(status="CANDIDATE_AGGREGATE_ONLY",sha256=hashlib.sha256(raw).hexdigest())
    except Exception as exc:obj["error"]=type(exc).__name__+":"+str(exc)[:100]
    return obj

def collect(anchor,root):
    with open(anchor,newline="",encoding="utf-8") as f:
        days=[r["source_trade_date"] for r in csv.DictReader(f) if "2026-09-01"<=r["source_trade_date"]<="2026-10-21"]
    if len(days)!=31:raise ValueError("EXPECTED_31_TARGET_DATES_"+str(len(days)))
    base=Path(root);base.mkdir(parents=True,exist_ok=True)
    results=[]
    for day in days:
        providers=[
            ("finews","https://a.finews.fyi/"+day),
            ("lianban","https://lianbanwang.com/days/"+day+".html")]
        candidates=[]
        for name,url in providers:
            attempt=pull(url,base/"raw"/(name+"_"+day+".html"),day)
            attempt["provider"]=name;candidates.append(attempt)
            time.sleep(0.4)
        good=[p for p in candidates if p["status"]=="CANDIDATE_AGGREGATE_ONLY"]
        status="MISSING"
        if len(good)==1:status="SINGLE_AGGREGATE_SOURCE_UNVERIFIED"
        if len(good)==2:
            status="AGGREGATE_SOURCES_DISAGREE" if (good[0]["up"]!=good[1]["up"] or good[0]["down"]!=good[1]["down"]) else "TWO_AGGREGATES_AGREE_NOT_PIT"
        chosen=good[0] if good else None
        results.append({"date":day,"status":status,"up":chosen["up"] if chosen else "",
            "down":chosen["down"] if chosen else "",
            "source":chosen["url"] if chosen else "",
            "raw_sha256":chosen["sha256"] if chosen else "",
            "all_sources":candidates})
        print(json.dumps({"date":day,"status":status,"up":chosen["up"] if chosen else None,
            "down":chosen["down"] if chosen else None},ensure_ascii=False),flush=True)
    with (base/"public_breadth_candidates.csv").open("w",newline="",encoding="utf-8") as f:
        keys=("date","status","up","down","source","raw_sha256")
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for r in results:w.writerow({k:r[k] for k in keys})
    detail={"version":"V113","target_days":len(results),"candidate_days":sum(bool(x["source"]) for x in results),
        "fully_certified_stock_universe_days":0,
        "two_sources_agreed_days":sum(x["status"]=="TWO_AGGREGATES_AGREE_NOT_PIT" for x in results),
        "source_disagreement_days":sum(x["status"]=="AGGREGATE_SOURCES_DISAGREE" for x in results),
        "individual_security_bars_complete":False,"full_v113_acceptance":"PARTIAL",
        "rows":results,"formal_signal_allowed":False}
    (base/"candidate_audit.json").write_text(json.dumps(detail,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in detail.items() if k!="rows"},ensure_ascii=False))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--anchor",required=True);p.add_argument("--out",required=True);a=p.parse_args()
    collect(a.anchor,a.out)
