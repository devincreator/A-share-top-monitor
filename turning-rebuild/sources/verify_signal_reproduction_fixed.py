import json
import numpy as np
import pandas as pd

SOURCE = "a_share_5_9_daily_reconstruction.csv"
LATEST = "latest.json"

START = "2015-01-05"
END = "2026-08-04"

df_all = pd.read_csv(SOURCE)
df_all = df_all[df_all["date"] <= END].copy()
df_all = df_all.sort_values("date").reset_index(drop=True)

NUMERIC_FIELDS = [
    "up20_pct","up60_pct","up120_pct",
    "dd20_pct","dd60_pct",
    "distance20_high_pct","ret5_pct",
    "rv_ratio","rv_p756_pct","ret63_p756_pct",
    "turnover_amt_p252_pct","turnover_rate_p252_pct",
    "style_dd20_pct","finance_63d_growth_p756_pct"
]

for c in NUMERIC_FIELDS:
    df_all[c] = pd.to_numeric(df_all[c], errors="coerce")

def rolling_percentile_average(series, window):
    x = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    result = np.full(len(x), np.nan)

    for i in range(window - 1, len(x)):
        a = x[i - window + 1:i + 1]

        if not np.isfinite(a).all():
            continue

        current = a[-1]
        less = np.sum(a < current)
        equal = np.sum(a == current)
        average_rank = less + (equal + 1) / 2
        result[i] = average_rank / window * 100

    return result

# Bottom-5 早期历史不足时的 RV252 预热
df_all["rv_p252_fallback"] = rolling_percentile_average(
    df_all["rv_ratio"],
    252
)

# 正式信号状态机从 2015-01-05 开始
df = df_all[
    (df_all["date"] >= START) &
    (df_all["date"] <= END)
].copy().reset_index(drop=True)

df["phase5"] = df["phase5"].fillna("UNKNOWN").astype(str).str.upper()
df["phase9"] = df["phase9"].fillna("UNKNOWN").astype(str).str.upper()

# ---------------- Top-5 ----------------
df["top5_A_new"] = (
    (df["phase5"] == "UP") &
    (df["up60_pct"] >= 8) &
    (df["turnover_amt_p252_pct"] >= 79) &
    (df["distance20_high_pct"] <= 1) &
    (df["ret5_pct"] >= 1)
)

df["top5_B_new"] = (
    (df["phase5"] == "UP") &
    (df["rv_p756_pct"] >= 60) &
    (df["ret63_p756_pct"] <= 20) &
    (df["up20_pct"] >= 4) &
    (df["ret5_pct"] >= 0)
)

df["top5_hard_new"] = df["top5_A_new"] | df["top5_B_new"]
df["top5_formal_new"] = False

last_signal = None
last_phase = None

for i in range(len(df)):
    phase = df.at[i, "phase5"]

    if phase != last_phase:
        last_signal = None
        last_phase = phase

    if phase == "UP" and bool(df.at[i, "top5_hard_new"]):
        if last_signal is None or i - last_signal > 15:
            df.at[i, "top5_formal_new"] = True
            last_signal = i

# ---------------- Top-9 ----------------
df["top9_A_new"] = (
    (df["turnover_rate_p252_pct"] >= 75) &
    (df["up120_pct"] >= 10)
)

df["top9_B_new"] = (
    (df["rv_p756_pct"] >= 50) &
    (df["style_dd20_pct"] >= 2)
)

df["top9_C_new"] = (
    (df["turnover_amt_p252_pct"] >= 85) &
    (df["up120_pct"] >= 10) &
    (df["style_dd20_pct"] >= 2)
)

df["top9_F_new"] = (
    df["finance_63d_growth_p756_pct"].notna() &
    (df["finance_63d_growth_p756_pct"] <= 85)
)

raw_top9 = []

for i in df.index[df["top5_formal_new"]].tolist():
    A = bool(df.at[i, "top9_A_new"])
    B = bool(df.at[i, "top9_B_new"])
    C = bool(df.at[i, "top9_C_new"])
    F = bool(df.at[i, "top9_F_new"])

    if A or B or C:
        if F:
            raw_top9.append({"index": i, "from": i, "deferred": False})
        continue

    # 只有 B 可在同一 UP phase5 内延迟最多 6 个交易日
    for j in range(i + 1, min(i + 7, len(df))):
        if df.at[j, "phase5"] != "UP":
            break

        if bool(df.at[j, "top9_B_new"]) and bool(df.at[j, "top9_F_new"]):
            raw_top9.append({"index": j, "from": i, "deferred": True})
            break

raw_by_index = {}
for x in raw_top9:
    raw_by_index.setdefault(x["index"], x)

raw_top9 = [raw_by_index[k] for k in sorted(raw_by_index)]

df["top9_formal_new"] = False
last_signal = None

for x in raw_top9:
    i = x["index"]

    if last_signal is None or i - last_signal > 15:
        df.at[i, "top9_formal_new"] = True
        last_signal = i

# ---------------- Bottom-5 ----------------
df["bottom5_rv_effective"] = df["rv_p756_pct"].where(
    df["rv_p756_pct"].notna(),
    df["rv_p252_fallback"]
)

A_nonphase = (
    (df["dd20_pct"] <= -4) &
    (df["ret5_pct"] <= -2.4) &
    (df["bottom5_rv_effective"] >= 40)
)

df["bottom5_A_base_new"] = (
    (df["phase5"] == "DOWN") &
    A_nonphase
)

df["bottom5_B_new"] = (
    (df["phase5"] == "DOWN") &
    (df["dd60_pct"] <= -9) &
    (df["ret63_p756_pct"] <= 60) &
    (df["rv_p756_pct"] >= 70) &
    (df["ret5_pct"] <= 0)
)

df["bottom5_C_new"] = (
    (df["phase5"] == "DOWN") &
    (df["dd60_pct"] <= -8) &
    (df["ret63_p756_pct"] <= 50) &
    (df["rv_p756_pct"] <= 15) &
    (df["ret5_pct"] <= -4.5)
)

df["bottom5_M_new"] = False
df["bottom5_A_new"] = False

phase_age = 0
previous_phase = None

for i in range(len(df)):
    phase = df.at[i, "phase5"]

    if phase != previous_phase:
        phase_age = 1
    else:
        phase_age += 1

    B = bool(df.at[i, "bottom5_B_new"])
    C = bool(df.at[i, "bottom5_C_new"])
    A = bool(df.at[i, "bottom5_A_base_new"])

    # 纯 A 重复信号治理
    if A:
        pure_A = (not B) and (not C)

        if pure_A and phase_age >= 2:
            A = (
                pd.notna(df.at[i, "dd60_pct"]) and
                df.at[i, "dd60_pct"] <= -7.5
            )

    df.at[i, "bottom5_A_new"] = A

    # 新 DOWN phase 第一日：继承前 5 个交易日的 A 证据
    new_down = (
        phase == "DOWN" and
        (
            i == 0 or
            df.at[i - 1, "phase5"] != "DOWN"
        )
    )

    if new_down:
        start = max(0, i - 5)
        inherited = False

        for j in range(start, i):
            if bool(A_nonphase.iloc[j]):
                inherited = True
                break

        df.at[i, "bottom5_M_new"] = inherited

    previous_phase = phase

df["bottom5_hard_new"] = (
    df["bottom5_A_new"] |
    df["bottom5_B_new"] |
    df["bottom5_C_new"] |
    df["bottom5_M_new"]
)

df["bottom5_formal_new"] = False
last_signal = None
last_phase = None

for i in range(len(df)):
    phase = df.at[i, "phase5"]

    if phase != last_phase:
        last_signal = None
        last_phase = phase

    if phase == "DOWN" and bool(df.at[i, "bottom5_hard_new"]):
        if last_signal is None or i - last_signal > 22:
            df.at[i, "bottom5_formal_new"] = True
            last_signal = i

# ---------------- Bottom-9 ----------------
df["bottom9_A_new"] = (
    (df["phase9"] == "DOWN") &
    (df["dd20_pct"] <= -4) &
    (df["ret5_pct"] <= -3.8) &
    (df["rv_p756_pct"] >= 55)
)

df["bottom9_B_new"] = (
    (df["phase9"] == "DOWN") &
    (df["dd60_pct"] <= -12.5) &
    (df["ret63_p756_pct"] <= 60) &
    (df["rv_p756_pct"] >= 50) &
    (df["ret5_pct"] <= 0)
)

df["bottom9_C_new"] = (
    (df["phase9"] == "DOWN") &
    (df["dd60_pct"] <= -9) &
    (df["ret63_p756_pct"] <= 60) &
    (df["rv_p756_pct"] <= 15) &
    (df["ret5_pct"] <= -2)
)

df["bottom9_hard_new"] = (
    df["bottom9_A_new"] |
    df["bottom9_B_new"] |
    df["bottom9_C_new"]
)

df["bottom9_formal_new"] = False
last_signal = None
last_phase = None

for i in range(len(df)):
    phase = df.at[i, "phase9"]

    if phase != last_phase:
        last_signal = None
        last_phase = phase

    if phase == "DOWN" and bool(df.at[i, "bottom9_hard_new"]):
        if last_signal is None or i - last_signal > 15:
            df.at[i, "bottom9_formal_new"] = True
            last_signal = i

# ---------------- 与当前生产版比较 ----------------
with open(LATEST, "r", encoding="utf-8") as f:
    latest = json.load(f)

def target_dates(key):
    formal = latest["strategies"][key]["formal"]

    return set(
        x["date"]
        for x in formal
        if START <= x["date"] <= END
    )

def compare_latest(name, key, new_col):
    old_dates = target_dates(key)

    new_dates = set(
        df.loc[
            df[new_col] &
            (df["date"] >= START) &
            (df["date"] <= END),
            "date"
        ].tolist()
    )

    missed = sorted(old_dates - new_dates)
    extra = sorted(new_dates - old_dates)

    print()
    print("==========", name, "==========")
    print("当前生产版信号数:", len(old_dates))
    print("重新计算信号数:", len(new_dates))
    print("漏掉:", missed)
    print("多出:", extra)

    passed = old_dates == new_dates
    print("结果:", "PASS" if passed else "FAIL")

    return passed

results = [
    compare_latest("Top-5", "top5", "top5_formal_new"),
    compare_latest("Top-9", "top9", "top9_formal_new"),
    compare_latest("Bottom-5", "bottom5", "bottom5_formal_new"),
    compare_latest("Bottom-9", "bottom9", "bottom9_formal_new"),
]

print()
print("========== 最终判断 ==========")

if all(results):
    print("PASS：当前生产版四模块100%复现")
else:
    print("FAIL：仍有模块需要检查")
