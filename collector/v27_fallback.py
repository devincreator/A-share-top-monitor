#!/usr/bin/env python3
"""独立于东方财富的指数历史归档探测。保留原始数据与拒绝原因。"""
import json
from pathlib import Path

import pandas as pd

OUT=Path("out")
OUT.mkdir(exist_ok=True)
ANCHORS={"2026-08-04":5766.33,"2026-09-30":5648.25,"2026-10-08":5560.01}
END="2026-10-08"
REPORT={"asof":END,"purpose":"alternate-source validation only; no official model scores","attempts":[],"verified":[]}

def check(df, name, code):
    if not {"date","close"}.issubset(df.columns):
        raise ValueError("missing date/close columns")
    x=df.copy()
    x["date"]=pd.to_datetime(x["date"]).dt.strftime("%Y-%m-%d")
    x["close"]=pd.to_numeric(x["close"],errors="coerce")
    x=x.drop_duplicates("date").sort_values("date")
    if x.close.isna().any() or len(x)<850 or x.date.max()<END:
        raise ValueError(f"stale/invalid dates: n={len(x)} max={x.date.max()}")
    if code=="000985":
        for day,value in ANCHORS.items():
            q=x.loc[x.date==day,"close"]
            if len(q)!=1 or abs(float(q.iloc[0])-value)>1:
                raise ValueError(f"wrong price index anchor {day}: {q.to_list()}")
        for day in ("2026-09-24","2026-09-28"):
            if day not in set(x.date): raise ValueError("missing "+day)
    return x

def probe(ak, name, fn, code):
    row={"source":name,"symbol":code,"status":"failed"}
    try:
        result=fn()
        if result is None or result.empty: raise ValueError("empty response")
        data=check(result,name,code)
        path=OUT/f"fallback_{name}_{code}.csv"
        data.to_csv(path,index=False)
        row.update(status="verified_price",rows=len(data),last_date=data.date.max(),
                   target_dates={d:float(data.loc[data.date==d,"close"].iloc[0])
                        for d in ("2026-09-24","2026-09-28") if d in set(data.date)})
        REPORT["verified"].append(str(path))
    except Exception as e:
        row["error"]=f"{type(e).__name__}: {str(e)[:220]}"
    REPORT["attempts"].append(row)
    print(json.dumps(row,ensure_ascii=False),flush=True)

def main():
    try:
        import akshare as ak
        for code in ("000985","000300","000852"):
            sym="sh"+code
            probe(ak,"sina",lambda sym=sym:ak.stock_zh_index_daily(symbol=sym),code)
            probe(ak,"tencent",lambda sym=sym:ak.stock_zh_index_daily_tx(
                symbol=sym,start_date="20220101",end_date="20261008"),code)
            probe(ak,"eastmoney_alt",lambda code=code:ak.stock_zh_index_daily_em(
                symbol="csi"+code,start_date="20220101",end_date="20261008"),code)
        # 融资接口另行保留分交易所清洗前后的日期与缺失规模，用于选取替代源。
        for exchange in ("sh","sz"):
            name="macro_china_market_margin_"+exchange
            row={"source":name,"status":"failed"}
            try:
                raw=getattr(ak,name)()
                raw.to_csv(OUT/f"finance_probe_{exchange}_raw.csv",index=True)
                row.update(status="raw_saved",rows=len(raw),columns=[str(x) for x in raw.columns],
                           sample_tail=raw.tail(2).to_dict(orient="records"))
            except Exception as e:
                row["error"]=f"{type(e).__name__}: {str(e)[:220]}"
            REPORT["attempts"].append(row)
    except Exception as e:
        REPORT["setup_error"]=str(e)
    finally:
        (OUT/"fallback_audit.json").write_text(json.dumps(REPORT,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
        print("Fallback probes complete",len(REPORT["verified"]),flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
