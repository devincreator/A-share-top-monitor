#!/usr/bin/env python3
"""Official CSI daily sector/size-index archive, for PIT cross-index divergence study.
Download only historical market index records, not portfolios/model rules.
"""
import requests,json,time
from pathlib import Path
import pandas as pd
O=Path("out/csi_size_hist"); O.mkdir(parents=True,exist_ok=True)
S=requests.Session()
S.headers.update({"User-Agent":"Mozilla/5.0","Referer":"https://www.csindex.com.cn/"})
audit=[]
for code in ["000300","000905","000852","000016"]:
    records=[]
    for year in range(2015,2027):
        entry={"code":code,"year":year}
        try:
            r=S.get("https://www.csindex.com.cn/csindex-home/perf/index-perf",
              params={"indexCode":code,"startDate":f"{year}0101","endDate":"20261013" if year==2026 else f"{year}1231"},timeout=35)
            r.raise_for_status()
            arr=r.json().get("data",[])
            if not isinstance(arr,list):raise ValueError("data not list")
            if arr:
                records.extend(arr)
            entry.update(status="downloaded",rows=len(arr),fields=list(arr[0])[:20] if arr else [])
        except Exception as e:entry.update(status="failed",error=f"{type(e).__name__}: {str(e)[:200]}")
        audit.append(entry)
        print(json.dumps(entry,ensure_ascii=False),flush=True)
        time.sleep(.2)
    if records:
        f=pd.DataFrame(records)
        if "tradeDate" not in f:raise RuntimeError(f"missing tradeDate {code}")
        f=f.drop_duplicates("tradeDate").sort_values("tradeDate")
        f.to_csv(O/f"official_csi_{code}_unfiltered.csv",index=False)
(O/"index_pit_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
