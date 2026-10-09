#!/usr/bin/env python3
"""v27 数据来源采集与审计；绝不输出未经核验的四模块正式评分。"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ASOF = os.getenv("V27_ASOF", "2026-10-08")
START = "2022-01-01"
OUT = Path("out")
OUT.mkdir(parents=True, exist_ok=True)
ANCHORS = {"2026-08-04": 5766.33, "2026-09-30": 5648.25, "2026-10-08": 5560.01}
CODES = ("000985", "000300", "000852")


def pct_prior(values, window):
    """每个 t 只与 t 之前的 window 个值相比。"""
    v = np.asarray(values, dtype=float)
    out = np.full(len(v), np.nan)
    for t in range(window, len(v)):
        ref = v[t-window:t]
        if np.isfinite(v[t]) and np.isfinite(ref).all():
            out[t] = 100 * np.mean(ref <= v[t])
    return out


def normalize_frame(raw, symbol):
    required = {"日期", "收盘", "成交额", "换手率"}
    if not required.issubset(raw.columns):
        raise ValueError(f"{symbol}: missing {sorted(required-set(raw.columns))}; got {list(raw.columns)}")
    z = raw.rename(columns={"日期":"date","收盘":"close","成交额":"amount","换手率":"turnover"})
    z = z[["date","close","amount","turnover"]].copy()
    z["date"] = pd.to_datetime(z["date"]).dt.strftime("%Y-%m-%d")
    for c in ("close","amount","turnover"):
        z[c] = pd.to_numeric(z[c],errors="coerce")
    z = z.drop_duplicates("date").sort_values("date").reset_index(drop=True)
    if z.empty or z["close"].isna().any() or (z["close"] <= 0).any():
        raise ValueError(f"{symbol}: invalid price series")
    if z[["amount","turnover"]].isna().any().any():
        raise ValueError(f"{symbol}: amount or turnover missing")
    if symbol == "000985":
        for day, expected in ANCHORS.items():
            row = z.loc[z.date == day, "close"]
            if len(row) != 1 or abs(float(row.iloc[0]) - expected) > 1:
                raise ValueError(f"000985.CSI price index mismatch {day}: actual {row.tolist()}, expected {expected}")
        for day in ("2026-09-24", "2026-09-28"):
            if day not in set(z.date):
                raise ValueError(f"000985: missing close {day}")
        if len(z[z.date <= "2026-08-04"]) < 756:
            raise ValueError("000985: insufficient pre-update 756 day history")
    if z.date.max() < ASOF:
        raise ValueError(f"{symbol}: last date {z.date.max()} before {ASOF}")
    return z


def obtain_index(ak, code):
    raw = ak.index_zh_a_hist(symbol=code,period="daily",
                            start_date=START.replace("-",""),
                            end_date=ASOF.replace("-",""))
    return normalize_frame(raw, code)


def finance_from_jin10(ak, place):
    fname = "macro_china_market_margin_sh" if place == "sh" else "macro_china_market_margin_sz"
    df = getattr(ak, fname)().copy().reset_index()
    # Jin10 多版本中日期可能为索引/普通字段、融资余额列名略有不同。
    dt = "日期" if "日期" in df.columns else df.columns[0]
    candidates = [x for x in df.columns if "融资余额" in str(x) and "融券" not in str(x)]
    if len(candidates) != 1:
        raise ValueError(f"{place}: ambiguous financing columns {list(df.columns)}")
    x = df[[dt,candidates[0]]].copy()
    x.columns = ["date",f"balance_{place}"]
    x["date"] = pd.to_datetime(x["date"]).dt.strftime("%Y-%m-%d")
    x[f"balance_{place}"] = pd.to_numeric(x[f"balance_{place}"],errors="coerce")
    x = x.drop_duplicates("date").sort_values("date")
    return x.loc[(x.date >= START)&(x.date <= ASOF)].reset_index(drop=True)


def collect_finance(ak):
    sh = finance_from_jin10(ak, "sh")
    sz = finance_from_jin10(ak, "sz")
    merged = sh.merge(sz,on="date",validate="one_to_one",how="inner")
    merged["balance_sh_sz"] = merged.balance_sh + merged.balance_sz
    if len(merged) < 850 or merged.date.max() < ASOF:
        raise ValueError(f"finance too short/stale: {len(merged)} days through {merged.date.max()}")
    if merged[["balance_sh","balance_sz"]].isna().any().any() or (merged[["balance_sh","balance_sz"]] <= 0).any().any():
        raise ValueError("invalid financing balance observations")
    # 元是官方原始口径，2026年两市合计应为数万亿元，不可把亿元直接当元。
    latest = merged.iloc[-1].balance_sh_sz
    if not 1e12 < latest < 1e13:
        raise ValueError(f"finance unit mismatch: latest yuan {latest}")
    return merged


def build_features(index_data, finance):
    a = index_data["000985"].copy()
    a["amount_p252"] = pct_prior(a.amount,252)
    a["turnover_p252"] = pct_prior(a.turnover,252)
    a["ret5"] = a.close.pct_change(5)*100
    a["ret63"] = a.close.pct_change(63)*100
    a["rv20"] = a.close.pct_change().rolling(20).std()
    a["rv120"] = a.close.pct_change().rolling(120).std()
    a["rv_ratio"] = a.rv20/a.rv120
    a["rv_p756"] = pct_prior(a.rv_ratio,756)
    a["ret63_p756"] = pct_prior(a.ret63,756)
    for code in ("000300","000852"):
        a = a.merge(index_data[code][["date","close"]].rename(columns={"close":f"close_{code}"}),on="date",how="left",validate="one_to_one")
    a = a.merge(finance[["date","balance_sh_sz"]],on="date",how="left",validate="one_to_one")
    a["finance_growth63"] = (a.balance_sh_sz/a.balance_sh_sz.shift(63)-1)*100
    a["finance_growth63_p756"] = pct_prior(a.finance_growth63,756)
    recent = a[(a.date >= "2026-08-05")&(a.date <= ASOF)]
    expected = {"amount_p252","turnover_p252","rv_p756","ret63_p756","close_000300","close_000852","finance_growth63_p756"}
    if recent.empty or recent[list(expected)].isna().any().any():
        raise ValueError("recent input factors contain missing or insufficient history")
    return a


def main():
    audit = {"asof":ASOF, "status":"INCOMPLETE", "scope":"raw data and primitive features, NOT v27 official signals",
             "sources":{}, "errors":[]}
    indices = {}
    financing = None
    try:
        import akshare as ak
        audit["akshare_version"] = getattr(ak,"__version__","unknown")
        for code in CODES:
            try:
                indices[code] = obtain_index(ak,code)
                indices[code].to_csv(OUT/f"index_{code}.csv",index=False)
                audit["sources"][code] = {"rows":len(indices[code]),"last_date":indices[code].date.max()}
            except Exception as e:
                audit["errors"].append(f"index {code}: {type(e).__name__}: {str(e)[:250]}")
        try:
            financing = collect_finance(ak)
            financing.to_csv(OUT/"financing_sh_sz.csv",index=False)
            audit["sources"]["financing"]={"rows":len(financing),"last_date":financing.date.max()}
        except Exception as e:
            audit["errors"].append(f"finance: {type(e).__name__}: {str(e)[:250]}")
        if not audit["errors"]:
            try:
                features = build_features(indices,financing)
                features.to_csv(OUT/"factors_all.csv",index=False)
                audit["sources"]["features"]={"rows":len(features),"last_date":features.date.max()}
                audit["status"]="RAW_FEATURES_VERIFIED_ONLY"
            except Exception as e:
                audit["errors"].append(f"features: {type(e).__name__}: {str(e)[:250]}")
    except Exception as e:
        audit["errors"].append(f"setup: {type(e).__name__}: {str(e)[:250]}")
    finally:
        (OUT/"audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(audit,ensure_ascii=False))
    return 0 if audit["status"]=="RAW_FEATURES_VERIFIED_ONLY" else 2


if __name__ == "__main__":
    sys.exit(main())
