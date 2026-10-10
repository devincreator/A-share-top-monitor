#!/usr/bin/env python3
"""Explore token-free, rate-limited public index turnover history.
No market signal/scoring exposed or calculated. Data only accepted if frozen 2026-08-04 anchors match.
"""
from pathlib import Path
import datetime as dt
import json
import requests
import pandas as pd
OUT=Path('out');OUT.mkdir(exist_ok=True)
audit={"asof":"2026-10-08","scope":"index turnover rate source probe only",
"controls":{"2026-08-04":{"close":5766.33,"turnover_rate":1.64,"turnover_pct252":14.2857}},"attempts":[]}

def p252(v):
    vals=list(v)
    pos=next(i for i,x in enumerate(vals) if x[0]=="2026-08-04")
    if pos<252:return None
    today=vals[pos][1]
    return round(sum(x[1]<=today for x in vals[pos-252:pos])/252*100,4)

def parse(provider, rows, cols):
    outcome={"provider":provider,"status":"rejected"}
    try:
        z=pd.DataFrame(rows)
        if z.empty: raise ValueError("no rows")
        z=z.rename(columns=cols)
        for k in ["date","close","turnover_rate"]:
            if k not in z.columns:raise ValueError("missing "+k)
        z["date"]=pd.to_datetime(z["date"]).dt.strftime("%Y-%m-%d")
        for k in ["close","turnover_rate"]:
            z[k]=pd.to_numeric(z[k],errors="coerce")
        z=z.sort_values("date").drop_duplicates("date")
        r=z[z.date=="2026-08-04"]
        if len(r)!=1: raise ValueError("missing 2026-08-04 anchor")
        rate=float(r.turnover_rate.iloc[0]);close=float(r.close.iloc[0])
        outcome.update(rows=len(z),close=close,turnover=rate,reported_percentile=p252(list(zip(z.date,z.turnover_rate))))
        if abs(close-5766.33)>.06:raise ValueError("price anchor mismatch")
        if abs(rate-1.64)>.05:raise ValueError("turnover raw anchor mismatch")
        if z[z.date<="2026-08-04"].shape[0]<253:raise ValueError("less than 253 dates")
        if pd.isna(z.turnover_rate).any():raise ValueError("missing daily turnover rate")
        if abs(outcome["reported_percentile"]-14.2857)>.0002:raise ValueError("frozen percent-rank mismatch")
        f=OUT/f"turnover_verified_{provider}.csv";z.to_csv(f,index=False)
        outcome.update(status="VERIFIED_FROZEN_RANK",output=str(f))
    except Exception as e:
        outcome["reason"]=f"{type(e).__name__}: {str(e)[:230]}"
    audit["attempts"].append(outcome)
    print(json.dumps(outcome,ensure_ascii=False),flush=True)

session=requests.Session()
session.headers.update({"User-Agent":"Mozilla/5.0 (compatible; v27 source quality auditor/1.0)"})
providers=[
 ("databull_index_history",
  "https://api.databull.cn/cn/index/history",
  {"index_code":"000985","start_date":"20250401","end_date":"20261008"}),
]
for name,url,params in providers:
    outcome={"provider":name,"status":"failed"}
    try:
        r=session.get(url,params=params,timeout=25)
        outcome.update(http_code=r.status_code,bytes=len(r.content),content_type=r.headers.get("content-type",""))
        if r.status_code==200:
            payload=r.json()
            if isinstance(payload,list):
                parse(name,payload,{"turnover_rate":"turnover_rate"})
                outcome["status"]="parsed"; outcome["records"]=len(payload)
            else:
                outcome["body_sample"]=str(payload)[:240]
        else:outcome["body_sample"]=r.text[:200]
    except Exception as e:outcome["error"]=f"{type(e).__name__}: {str(e)[:200]}"
    audit["attempts"].append(outcome)
    print(json.dumps(outcome,ensure_ascii=False),flush=True)

# Inspect investor-facing published turnover for a small fixed anchor set:
# This is source cross-check, not a substitute for 252 dates.
for name,url in [
 ("stockstar_0804","https://stock.stockstar.com/RB2026080400030995.shtml"),
 ("stockstar_0731","https://stock.stockstar.com/RB2026073100030113.shtml")]:
    row={"provider":name,"status":"failed"}
    try:
        r=session.get(url,timeout=20); row["http_code"]=r.status_code
        row["has_1_64"] = "换手率1.64%" in r.text if name.endswith('0804') else None
        row["has_1_79"] = "换手率1.79%" in r.text if name.endswith('0731') else None
        row["status"]="anchor_only" if r.status_code==200 else "failed"
    except Exception as e:row["error"]=f"{type(e).__name__}:{str(e)[:200]}"
    audit["attempts"].append(row);print(json.dumps(row,ensure_ascii=False),flush=True)

(OUT/"turnover_source_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf8")
