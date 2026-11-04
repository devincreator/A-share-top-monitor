import json
import math
import numpy as np
import pandas as pd

SOURCE = "production_history_candidate.json"
OUTPUT_JSON = "production_history_recomputed.json"
OUTPUT_CSV = "increment_20260805_20260827_check.csv"
OUTPUT_TXT = "model_check_20260827.txt"

START = "2026-08-05"
END = "2026-08-27"

def num(s):
    return pd.to_numeric(s, errors="coerce")

def rolling_percentile_inclusive(s, window):
    """
    按当前 5%/9% 历史主表的实际预热长度重算：
    252日分位从第252个有效观察起产生；
    756日分位从第756个有效观察起产生。
    窗口包含当日，不使用未来数据。
    """
    a = num(s).to_numpy(dtype=float)
    out = np.full(len(a), np.nan)

    for i in range(len(a)):
        if not np.isfinite(a[i]):
            continue

        lo = i - window + 1
        if lo < 0:
            continue

        hist = a[lo:i + 1]
        if np.isfinite(hist).sum() != window:
            continue

        out[i] = (hist <= a[i]).sum() / window * 100.0

    return pd.Series(out, index=s.index)

def extend_phase_tail(df, col, threshold):
    """
    历史 phase5/phase9 已冻结到已有日期。
    仅对尾部缺失日期按固定反转尺度继续状态机。
    """
    phase = df[col].copy()
    valid = phase.notna()

    if not valid.any():
        return phase

    last_valid = valid[valid].index[-1]

    # 找到最后一个已知相位段的起点
    start = last_valid
    while start > 0:
        prev = phase.iloc[start - 1]
        cur = phase.iloc[start]
        if pd.isna(prev) or prev != cur:
            break
        start -= 1

    state = str(phase.iloc[last_valid]).upper()
    closes = num(df["all_a_close"])

    segment = closes.iloc[start:last_valid + 1].dropna()
    if len(segment) == 0:
        return phase

    peak = segment.max()
    trough = segment.min()

    for i in range(last_valid + 1, len(df)):
        c = closes.iloc[i]
        if not np.isfinite(c):
            phase.iloc[i] = state
            continue

        if state == "UP":
            peak = max(peak, c)
            if c <= peak * (1.0 - threshold):
                state = "DOWN"
                trough = c
        else:
            trough = min(trough, c)
            if c >= trough * (1.0 + threshold):
                state = "UP"
                peak = c

        phase.iloc[i] = state

    return phase

def b(v):
    return bool(v) if pd.notna(v) else False

with open(SOURCE, "r", encoding="utf-8") as f:
    history = json.load(f)

df = pd.DataFrame(history["data"]).copy()
df = df.sort_values("date").reset_index(drop=True)

# ---------- 数值列 ----------
for c in [
    "all_a_close", "hs300_close", "zz1000_close",
    "turnover", "turnover_rate", "financing_balance"
]:
    if c not in df.columns:
        df[c] = np.nan
    df[c] = num(df[c])

close = df["all_a_close"]

# ---------- 价格滚动指标 ----------
ret1 = close.pct_change(fill_method=None)

df["ret5_pct"] = (close / close.shift(5) - 1.0) * 100.0
df["ret63_pct"] = (close / close.shift(63) - 1.0) * 100.0

low20 = close.rolling(20, min_periods=20).min()
low60 = close.rolling(60, min_periods=60).min()
low120 = close.rolling(120, min_periods=120).min()

high20 = close.rolling(20, min_periods=20).max()
high60 = close.rolling(60, min_periods=60).max()

df["up20_pct"] = (close / low20 - 1.0) * 100.0
df["up60_pct"] = (close / low60 - 1.0) * 100.0
df["up120_pct"] = (close / low120 - 1.0) * 100.0

df["dd20_pct"] = (close / high20 - 1.0) * 100.0
df["dd60_pct"] = (close / high60 - 1.0) * 100.0
df["distance20_high_pct"] = -df["dd20_pct"]

rv20 = ret1.rolling(20, min_periods=20).std(ddof=1)
rv120 = ret1.rolling(120, min_periods=120).std(ddof=1)

df["rv20"] = rv20
df["rv120"] = rv120
df["rv_ratio"] = rv20 / rv120

# ---------- 历史滚动分位 ----------
df["rv_p756_pct"] = rolling_percentile_inclusive(df["rv_ratio"], 756)
df["ret63_p756_pct"] = rolling_percentile_inclusive(df["ret63_pct"], 756)

df["turnover_amt_p252_pct"] = rolling_percentile_inclusive(
    df["turnover"], 252
)
df["turnover_rate_p252_pct"] = rolling_percentile_inclusive(
    df["turnover_rate"], 252
)

# ---------- 风格 ----------
df["style_rs_ratio"] = df["zz1000_close"] / df["hs300_close"]

style_high20 = df["style_rs_ratio"].rolling(
    20, min_periods=20
).max()

df["style_dd20_pct"] = (
    1.0 - df["style_rs_ratio"] / style_high20
) * 100.0

# ---------- 融资 ----------
df["finance_63d_growth_pct"] = (
    df["financing_balance"] /
    df["financing_balance"].shift(63) -
    1.0
) * 100.0

df["finance_63d_growth_p756_pct"] = rolling_percentile_inclusive(
    df["finance_63d_growth_pct"], 756
)

# ---------- 相位尾部续推 ----------
if "phase5" not in df.columns:
    df["phase5"] = np.nan
if "phase9" not in df.columns:
    df["phase9"] = np.nan

df["phase5"] = extend_phase_tail(df, "phase5", 0.05)
df["phase9"] = extend_phase_tail(df, "phase9", 0.09)

# ---------- 四模块硬条件 ----------
# Top-5
df["top5_A"] = (
    (df["phase5"] == "UP") &
    (df["up60_pct"] >= 8.0) &
    (df["turnover_amt_p252_pct"] >= 79.0) &
    (df["distance20_high_pct"] <= 1.0) &
    (df["ret5_pct"] >= 1.0)
)

df["top5_B"] = (
    (df["phase5"] == "UP") &
    (df["rv_p756_pct"] >= 60.0) &
    (df["ret63_p756_pct"] <= 20.0) &
    (df["up20_pct"] >= 4.0) &
    (df["ret5_pct"] >= 0.0)
)

df["top5_hard"] = df["top5_A"] | df["top5_B"]

# Top-9 融资门
df["top9_F"] = (
    df["finance_63d_growth_p756_pct"].notna() &
    (df["finance_63d_growth_p756_pct"] <= 85.0)
)

df["top9_A_core"] = (
    (df["turnover_rate_p252_pct"] >= 75.0) &
    (df["up120_pct"] >= 10.0) &
    df["top9_F"]
)

df["top9_B_core"] = (
    (df["rv_p756_pct"] >= 50.0) &
    (df["style_dd20_pct"] >= 2.0) &
    df["top9_F"]
)

df["top9_C_core"] = (
    (df["turnover_amt_p252_pct"] >= 85.0) &
    (df["up120_pct"] >= 10.0) &
    (df["style_dd20_pct"] >= 2.0) &
    df["top9_F"]
)

# Bottom-5
df["bottom5_A"] = (
    (df["phase5"] == "DOWN") &
    (df["dd20_pct"] <= -4.0) &
    (df["ret5_pct"] <= -2.4) &
    (df["rv_p756_pct"] >= 40.0)
)

df["bottom5_B"] = (
    (df["phase5"] == "DOWN") &
    (df["dd60_pct"] <= -9.0) &
    (df["ret63_p756_pct"] <= 60.0) &
    (df["rv_p756_pct"] >= 70.0) &
    (df["ret5_pct"] <= 0.0)
)

df["bottom5_C"] = (
    (df["phase5"] == "DOWN") &
    (df["dd60_pct"] <= -8.0) &
    (df["ret63_p756_pct"] <= 50.0) &
    (df["rv_p756_pct"] <= 15.0) &
    (df["ret5_pct"] <= -4.5)
)

df["bottom5_hard"] = (
    df["bottom5_A"] |
    df["bottom5_B"] |
    df["bottom5_C"]
)

# Bottom-9
df["bottom9_A"] = (
    (df["phase9"] == "DOWN") &
    (df["dd20_pct"] <= -4.0) &
    (df["ret5_pct"] <= -3.8) &
    (df["rv_p756_pct"] >= 55.0)
)

df["bottom9_B"] = (
    (df["phase9"] == "DOWN") &
    (df["dd60_pct"] <= -12.5) &
    (df["ret63_p756_pct"] <= 60.0) &
    (df["rv_p756_pct"] >= 50.0) &
    (df["ret5_pct"] <= 0.0)
)

df["bottom9_C"] = (
    (df["phase9"] == "DOWN") &
    (df["dd60_pct"] <= -9.0) &
    (df["ret63_p756_pct"] <= 60.0) &
    (df["rv_p756_pct"] <= 15.0) &
    (df["ret5_pct"] <= -2.0)
)

df["bottom9_hard"] = (
    df["bottom9_A"] |
    df["bottom9_B"] |
    df["bottom9_C"]
)

# ---------- Top-5 正式信号冷却 ----------
# 当前页面冻结规则：同一连续 UP 相位内 15 个交易日冷却
df["top5_formal"] = False
last_signal_i = None
last_phase = None

for i in range(len(df)):
    phase = df.at[i, "phase5"]

    if phase != last_phase:
        last_signal_i = None
        last_phase = phase

    if phase == "UP" and b(df.at[i, "top5_hard"]):
        if last_signal_i is None or (i - last_signal_i) >= 15:
            df.at[i, "top5_formal"] = True
            last_signal_i = i

# ---------- Top-9：Top-5入口后最多6个交易日 ----------
df["top9_entry_open"] = False
df["top9_formal"] = False
df["top9_route"] = ""

top5_indices = [
    i for i in range(len(df))
    if b(df.at[i, "top5_formal"])
]

for t5_i in top5_indices:
    for i in range(t5_i, min(t5_i + 7, len(df))):
        df.at[i, "top9_entry_open"] = True

        route = ""
        if b(df.at[i, "top9_A_core"]):
            route = "A"
        elif b(df.at[i, "top9_B_core"]):
            route = "B"
        elif b(df.at[i, "top9_C_core"]):
            route = "C"

        if route:
            # 一个 Top-5 入口只升级一次
            already = df.loc[t5_i:i, "top9_formal"].any()
            if not already:
                df.at[i, "top9_formal"] = True
                df.at[i, "top9_route"] = route
            break

# ---------- 完整性检查 ----------
required = {
    "Top-5": [
        "phase5", "up60_pct", "turnover_amt_p252_pct",
        "distance20_high_pct", "ret5_pct",
        "rv_p756_pct", "ret63_p756_pct", "up20_pct"
    ],
    "Top-9": [
        "phase9", "turnover_rate_p252_pct", "up120_pct",
        "rv_p756_pct", "style_dd20_pct",
        "turnover_amt_p252_pct",
        "finance_63d_growth_p756_pct"
    ],
    "Bottom-5": [
        "phase5", "dd20_pct", "dd60_pct",
        "ret5_pct", "ret63_p756_pct", "rv_p756_pct"
    ],
    "Bottom-9": [
        "phase9", "dd20_pct", "dd60_pct",
        "ret5_pct", "ret63_p756_pct", "rv_p756_pct"
    ]
}

mask = (df["date"] >= START) & (df["date"] <= END)
sub = df.loc[mask].copy()

for module, fields in required.items():
    sub[module + "_complete"] = sub[fields].notna().all(axis=1)

def yn(x):
    return "Y" if bool(x) else "N"

# ---------- 输出检查表 ----------
cols = [
    "date", "all_a_close", "phase5", "phase9",
    "ret5_pct", "ret63_pct",
    "up20_pct", "up60_pct", "up120_pct",
    "dd20_pct", "dd60_pct",
    "rv_p756_pct", "ret63_p756_pct",
    "turnover_amt_p252_pct", "turnover_rate_p252_pct",
    "style_dd20_pct", "finance_63d_growth_p756_pct",
    "top5_A", "top5_B", "top5_formal",
    "top9_entry_open", "top9_A_core", "top9_B_core",
    "top9_C_core", "top9_F", "top9_formal", "top9_route",
    "bottom5_hard", "bottom9_hard",
    "Top-5_complete", "Top-9_complete",
    "Bottom-5_complete", "Bottom-9_complete"
]

sub[cols].to_csv(
    OUTPUT_CSV,
    index=False,
    encoding="utf-8-sig"
)

# ---------- 写回 JSON ----------
# 只把重算得到的模型字段更新回输出文件，不覆盖源文件
update_fields = [
    "phase5", "phase9",
    "ret5_pct", "ret63_pct",
    "up20_pct", "up60_pct", "up120_pct",
    "dd20_pct", "dd60_pct", "distance20_high_pct",
    "rv20", "rv120", "rv_ratio",
    "rv_p756_pct", "ret63_p756_pct",
    "turnover_amt_p252_pct", "turnover_rate_p252_pct",
    "style_rs_ratio", "style_dd20_pct",
    "finance_63d_growth_pct",
    "finance_63d_growth_p756_pct"
]

rows = history["data"]
by_date = {r["date"]: r for r in rows}

for _, x in df.loc[mask].iterrows():
    row = by_date[x["date"]]

    for field in update_fields:
        value = x.get(field)

        if pd.isna(value):
            row[field] = None
        elif isinstance(value, (np.integer,)):
            row[field] = int(value)
        elif isinstance(value, (np.floating, float)):
            row[field] = float(value)
        else:
            row[field] = value

history["meta"]["end"] = END
history["meta"]["rows"] = len(rows)
history["meta"]["recomputed_through"] = END
history["meta"]["rolling_recompute"] = "5_9_current_production_convention"

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(
        history,
        f,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False
    )

# ---------- 文本摘要 ----------
lines = []
lines.append("A股 5%/9% 增量滚动指标与四模块检查")
lines.append(f"区间: {START} ~ {END}")
lines.append("")

for module in ["Top-5", "Top-9", "Bottom-5", "Bottom-9"]:
    c = module + "_complete"
    ok = int(sub[c].sum())
    total = len(sub)
    bad_dates = sub.loc[~sub[c], "date"].tolist()

    lines.append(
        f"{module}: 完整 {ok}/{total}"
        + ("" if not bad_dates else "；不完整日期=" + ",".join(bad_dates))
    )

lines.append("")
lines.append("正式/硬条件事件：")

top5_days = sub.loc[sub["top5_formal"], ["date", "top5_A", "top5_B"]]
if len(top5_days):
    for _, r in top5_days.iterrows():
        routes = []
        if r["top5_A"]:
            routes.append("A")
        if r["top5_B"]:
            routes.append("B")
        lines.append(f"Top-5 正式信号 {r['date']} Route {'/'.join(routes)}")
else:
    lines.append("Top-5: 区间内无正式信号")

top9_days = sub.loc[sub["top9_formal"], ["date", "top9_route"]]
if len(top9_days):
    for _, r in top9_days.iterrows():
        lines.append(f"Top-9 正式信号 {r['date']} Route {r['top9_route']}")
else:
    lines.append("Top-9: 区间内无正式信号")

b5 = sub.loc[sub["bottom5_hard"], "date"].tolist()
b9 = sub.loc[sub["bottom9_hard"], "date"].tolist()

lines.append(
    "Bottom-5 硬条件日: " + (",".join(b5) if b5 else "无")
)
lines.append(
    "Bottom-9 硬条件日: " + (",".join(b9) if b9 else "无")
)

lines.append("")
lines.append("最新日 2026-08-27：")

latest = sub[sub["date"] == END]
if len(latest):
    r = latest.iloc[0]

    for field in [
        "phase5", "phase9",
        "ret5_pct", "up20_pct", "up60_pct", "up120_pct",
        "rv_p756_pct", "ret63_p756_pct",
        "turnover_amt_p252_pct", "turnover_rate_p252_pct",
        "style_dd20_pct", "finance_63d_growth_p756_pct",
        "top5_A", "top5_B", "top5_formal",
        "top9_entry_open", "top9_formal",
        "bottom5_hard", "bottom9_hard"
    ]:
        v = r[field]
        if pd.isna(v):
            v = "缺失"
        lines.append(f"{field}: {v}")

with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("\n".join(lines))
print("")
print("已生成:")
print(" ", OUTPUT_JSON)
print(" ", OUTPUT_CSV)
print(" ", OUTPUT_TXT)
