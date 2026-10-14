#!/usr/bin/env python3
"""Third-party market breadth 2015-2026 provenance and historical completeness audit.
No user strategy, no private trading parameters, and no signals are uploaded.
Never promote these fields to production without independent cross-source verification.
"""
from pathlib import Path
import json, requests, pandas as pd, re
from urllib.parse import quote
OUT=Path("out");OUT.mkdir(exist_ok=True)
BASE="https://raw.githubusercontent.com/bulletforyou/AShareMarketReview/main/"
KEYS=["日期","上涨家数","下跌家数","涨停家数","跌停家数","封板率","成交额(亿)"]
results=[];blocks=[]
for year in range(2015,2027):
    name=f"市场复盘表_{year}全表.xlsx"
    item={"year":year,"source":"bulletforyou/AShareMarketReview","file":name}
    try:
        r=requests.get(BASE+quote(name),timeout=35)
        r.raise_for_status()
        file=OUT/f"raw_market_{year}.xlsx"
        file.write_bytes(r.content)
        # calamine avoids dependency on Microsoft Office and LibreOffice
        frame=pd.read_excel(file,engine="calamine",sheet_name=0)
        frame.columns=[str(x).strip() for x in frame.columns]
        item["head_columns"]=list(frame.columns)
        if not {"日期","上涨家数","下跌家数"}.issubset(frame.columns):raise ValueError("required columns missing")
        frame=frame[frame["日期"].astype(str).str.match(r"^20\d{2}[-/]\d{2}[-/]\d{2}$",na=False)].copy()
        frame["date"]=pd.to_datetime(frame["日期"]).dt.strftime("%Y-%m-%d")
        frame["up"]=pd.to_numeric(frame["上涨家数"],errors="coerce")
        frame["down"]=pd.to_numeric(frame["下跌家数"],errors="coerce")
        for src,key in [("涨停家数","limit_up"),("跌停家数","limit_down"),("成交额(亿)","value_yi"),("封板率","seal_rate_pct")]:
            if src in frame:
                frame[key]=pd.to_numeric(frame[src].astype(str).str.replace("%","",regex=False),errors="coerce")
            else:frame[key]=pd.NA
        frame=frame[["date","up","down","limit_up","limit_down","value_yi","seal_rate_pct"]]
        frame=frame.sort_values("date").drop_duplicates("date")
        if len(frame)<150 or ((frame.up<=0)|(frame.down<=0)).mean()>.05: raise ValueError(f"insufficient rows or widespread impossible counts n={len(frame)}")
        frame.to_csv(OUT/f"breadth_{year}.csv",index=False)
        blocks.append(frame)
        item.update(status="retrieved_unverified",rows=len(frame),start=frame.date.min(),end=frame.date.max(),
                    null_pct={k:round(float(frame[k].isna().mean()),3) for k in ["up","down","limit_up","limit_down","value_yi","seal_rate_pct"]},
                    first_row=frame.iloc[0].to_dict())
        file.unlink()
    except Exception as e:item.update(status="FAILED",error=f"{type(e).__name__}: {str(e)[:200]}")
    print(json.dumps(item,ensure_ascii=False,default=str),flush=True)
    results.append(item)
if blocks:
    union=pd.concat(blocks).drop_duplicates("date").sort_values("date").reset_index(drop=True)
    union.to_csv(OUT/"breadth_2015_2026_source_unverified.csv",index=False)
summary={"source":"Public third-party TDX-based market review; user must independently verify",
"retrieved_years":sum(x.get("status")=="retrieved_unverified" for x in results),
"attempted_years":12,
"rows":sum(x.get("rows",0) for x in results),
"results":results}
(OUT/"breadth_source_audit.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
