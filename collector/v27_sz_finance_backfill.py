#!/usr/bin/env python3
"""按交易所日期定向补录 SZ 融资余额缺口；保留失败审计，不回填伪值。"""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

OUT=Path("out");OUT.mkdir(exist_ok=True)
LOG={"source":"AKShare/Jin10 + SZSE stock_margin_szse","unit":"CNY yuan","filled":[],"failed":[]}
def get_hist(ak, exchange):
 df=getattr(ak, "macro_china_market_margin_"+exchange)().reset_index()
 date="日期" if "日期" in df.columns else df.columns[0]
 df=df[[date,"融资余额"]].rename(columns={date:"date","融资余额":exchange})
 df["date"]=pd.to_datetime(df.date).dt.strftime("%Y-%m-%d")
 df[exchange]=pd.to_numeric(df[exchange],errors="coerce")
 return df.drop_duplicates("date").set_index("date")

try:
 import akshare as ak
 raw=ak.stock_zh_index_daily_tx(symbol="sh000985",start_date="20220101",end_date="20261008")
 dates=sorted(set(pd.to_datetime(raw.date).dt.strftime("%Y-%m-%d")))
 sh=get_hist(ak,"sh")
 sz=get_hist(ak,"sz")
 missing=[d for d in dates if d not in sz.index or not np.isfinite(sz.loc[d,"sz"]) or sz.loc[d,"sz"]<=0]
 LOG["expected_trading_days"]=len(dates)
 LOG["initial_missing_or_invalid"]=len(missing)
 failures_consecutive=0
 for day in missing:
  ok=False
  for attempt in range(2):
   try:
    data=ak.stock_margin_szse(date=day.replace("-",""))
    if data.empty or "融资余额" not in data.columns:
     raise ValueError("empty exchange response or no 融资余额")
    # SZSE AKShare 汇总余额单位为亿元，而 Jin10 的融资余额单位为元。
    y=float(pd.to_numeric(data["融资余额"]).iloc[0])*1e8
    if not 1e11 < y < 2e12: raise ValueError("invalid financing value or unit")
    sz.loc[day,"sz"]=y
    LOG["filled"].append({"date":day,"yuan":y})
    failures_consecutive=0
    ok=True
    break
   except Exception as e:
    if attempt==1:
     LOG["failed"].append({"date":day,"reason":f"{type(e).__name__}: {str(e)[:150]}"})
    else:
     time.sleep(1)
  if not ok: failures_consecutive+=1
  if failures_consecutive>=12:
   LOG["stopped_reason"]="12 consecutive failures; stopped to avoid overloading exchange"
   break
  time.sleep(.25)
 result=pd.DataFrame({"date":dates}).set_index("date").join(sh).join(sz)
 result["finance_sh_sz_yuan"]=result["sh"]+result["sz"]
 result.to_csv(OUT/"reconstructed_financing_sh_sz.csv")
 bad=result[["sh","sz"]].isna().any(axis=1)|(result[["sh","sz"]]<=0).any(axis=1)
 LOG["remaining_missing_or_invalid"]=int(bad.sum())
 LOG["verified_recent"] = bool(not bad.loc["2026-08-05":"2026-10-08"].any())
 LOG["status"]="FULL_RAW_CONTINUITY" if not bad.any() else "PARTIAL_HISTORY_ONLY"
 if not bad.any():
  z=result.finance_sh_sz_yuan
  growth=(z/z.shift(63)-1)*100
  vals=growth.to_numpy(float)
  per=np.full(len(vals),np.nan)
  for t in range(756,len(vals)):
   ref=vals[t-756:t]
   if np.isfinite(ref).all() and np.isfinite(vals[t]):
    per[t]=100*np.mean(ref<=vals[t])
  result["finance_growth63_p756"]=per
  result.to_csv(OUT/"reconstructed_financing_sh_sz.csv")
except Exception as e:
 LOG["fatal"]=f"{type(e).__name__}: {str(e)[:300]}"
finally:
 (OUT/"finance_backfill_audit.json").write_text(json.dumps(LOG,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({k:v for k,v in LOG.items() if k not in ("filled","failed")},ensure_ascii=False))
 raise SystemExit(0)
