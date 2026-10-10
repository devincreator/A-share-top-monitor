#!/usr/bin/env python3
"""Consolidate paginated true daily CSI All Share turnover rate from a secondary free API.
Use provider's real turnover field (not volume). Reject if v27 2026-08-04 252 rank differs.
"""
import requests,json,time
from pathlib import Path
import pandas as pd
P=Path("out");P.mkdir(exist_ok=True)
URL="https://api.ashareapi.com/v1/kline"
blocks=[]
audit={"asof":"2026-10-08","status":"UNVERIFIED","pages":[],"source":"ashareapi sh000985 turnover"}
s=requests.Session()
for end in ["2026-10-08","2025-09-18","2024-09-10"]:
    row={"end":end}
    try:
        r=s.get(URL,params={"code":"sh000985","period":"day","count":250,"end":end},timeout=25)
        r.raise_for_status()
        p=r.json()
        a=p.get("data",None)
        if not p.get("ok") or not isinstance(a,list) or not a:raise ValueError("API returned no historical bars")
        z=pd.DataFrame(a)
        cols=["date","last","turnover","amount"]
        if not set(cols).issubset(z.columns):raise ValueError("missing columns "+str(z.columns))
        z=z[cols].copy()
        z["date"]=pd.to_datetime(z.date).dt.strftime("%Y-%m-%d")
        for c in ("last","turnover","amount"):z[c]=pd.to_numeric(z[c],errors="raise")
        z=z.sort_values("date")
        row.update(status="downloaded",count=len(z),min_date=z.date.min(),max_date=z.date.max())
        blocks.append(z)
    except Exception as e:row.update(status="failed",error=f"{type(e).__name__}:{str(e)[:200]}")
    audit["pages"].append(row)
    print(json.dumps(row,ensure_ascii=False),flush=True)
    time.sleep(.3)
if blocks:
    all=pd.concat(blocks).drop_duplicates("date").sort_values("date").reset_index(drop=True)
    all.to_csv(P/"index_000985_turnover_historical_raw.csv",index=False)
    audit["records_unique"]=len(all)
    audit["latest_date"]=all.date.max()
    snap=all[all.date=="2026-08-04"]
    if len(snap)==1:
        i=snap.index[0]
        prev=all.iloc[i-252:i]
        audit["anchor"]={"date":"2026-08-04","close":float(snap.iloc[0]["last"]),"turnover":float(snap.iloc[0]["turnover"]),
            "previous_days":len(prev),
            "p252_less_or_equal":float((prev.turnover<=float(snap.iloc[0]["turnover"])).sum()/252*100) if len(prev)==252 else None,
            "p252_less":float((prev.turnover<float(snap.iloc[0]["turnover"])).sum()/252*100) if len(prev)==252 else None,
            "frozen_reference":14.2857}
        anchor=audit["anchor"]
        if len(prev)==252 and abs(anchor["close"]-5766.33)<.1 and abs(anchor["turnover"]-1.64)<.03 and abs(anchor["p252_less_or_equal"]-14.2857)<.01:
            audit["status"]="VERIFIED_FROZEN_P252"
    print(json.dumps(audit,ensure_ascii=False),flush=True)
(P/"turnover_pagination_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf8")
