#!/usr/bin/env python3
"""Daily index traded amount and turnover probes; raw files only, no v27 strategy."""
from pathlib import Path
import json
import pandas as pd
import requests

OUT=Path("out"); OUT.mkdir(exist_ok=True)
audit=[]
for yr in range(2022,2027):
    a=max(f"{yr}0101","20220101")
    b=min(f"{yr}1231","20261008")
    try:
        url="https://www.csindex.com.cn/csindex-home/perf/index-perf"
        r=requests.get(url,params={"indexCode":"000985","startDate":a,"endDate":b},timeout=30)
        r.raise_for_status()
        payload=r.json()
        records=payload.get("data",[])
        if not isinstance(records,list):raise ValueError("invalid data type "+str(type(records)))
        pd.DataFrame(records).to_csv(OUT/f"csi_000985_{yr}_raw.csv",index=False)
        audit.append({"source":"csindex official","year":yr,"rows":len(records),"cols":list(records[0].keys())[:30] if records and isinstance(records[0],dict) else [], "status":"downloaded"})
    except Exception as e:
        audit.append({"source":"csindex official","year":yr,"status":"failed","error":f"{type(e).__name__} {str(e)[:200]}"})
try:
    import akshare as ak
    for name,sym in [("index_zh_a_hist","000985"),("stock_zh_index_hist_csindex","000985")]:
        try:
            if name=="index_zh_a_hist":
                df=getattr(ak,name)(symbol=sym,start_date="20250101",end_date="20261008")
            else:
                df=getattr(ak,name)(symbol=sym,start_date="20250101",end_date="20261008")
            df.to_csv(OUT/f"{name}_{sym}.csv",index=False)
            audit.append({"source":name,"status":"downloaded","rows":len(df),"cols":list(df.columns)})
        except Exception as e:
            audit.append({"source":name,"status":"failed","error":f"{type(e).__name__} {str(e)[:220]}"})
except Exception as e:
    audit.append({"source":"akshare","status":"failed","error":str(e)[:200]})
(OUT/"index_market_factor_probe.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
for row in audit:print(json.dumps(row,ensure_ascii=False),flush=True)
