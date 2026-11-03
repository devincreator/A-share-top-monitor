import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# A股 5% / 9% 当前生产版：增量正式信号计算
#
# 用途：
# 1) 从 production_history.json 六项原始数据重新计算全部指标
# 2) 从原始收盘价重新计算 phase5 / phase9
# 3) 按已经通过 100% 历史复现的当前生产规则计算四模块正式信号
# 4) 先用 latest.json 自动复核 2015-01-05 ~ 2026-08-04
# 5) 只有复核通过，才输出 2026-08-05 之后的新信号
#
# 不会修改 production_history.json / latest.json
# ============================================================

SOURCE = "production_history.json"
LATEST = "latest.json"

MODEL_START = "2015-01-05"
VERIFY_END = "2026-08-04"
NEW_START = "2026-08-05"

OUTPUT_CSV = "calculated_signals_20260805_to_latest.csv"
OUTPUT_JSON = "calculated_signals_20260805_to_latest.json"
OUTPUT_TXT = "calculated_signals_summary.txt"


def numeric(s):
    return pd.to_numeric(s, errors="coerce")


def bool_value(v):
    return bool(v) if pd.notna(v) else False


# ============================================================
# 滚动分位：包含当日；并列值用平均名次
# 这就是之前基础指标 100% 复现时确认的口径
# ============================================================

def rolling_percentile_average(series, window):
    x = numeric(series).to_numpy(dtype=float)
    out = np.full(len(x), np.nan)

    for i in range(window - 1, len(x)):
        a = x[i - window + 1:i + 1]

        if not np.isfinite(a).all():
            continue

        current = a[-1]
        less = np.sum(a < current)
        equal = np.sum(a == current)

        average_rank = less + (equal + 1) / 2.0
        out[i] = average_rank / window * 100.0

    return pd.Series(out, index=series.index)


# ============================================================
# 因果相位状态机：只使用当日及以前收盘价
# ============================================================

def calculate_phase(close_series, threshold):
    x = numeric(close_series).to_numpy(dtype=float)

    out = []
    state = "UNKNOWN"

    running_high = np.nan
    running_low = np.nan

    swing_high = np.nan
    swing_low = np.nan

    for c in x:
        if not np.isfinite(c):
            out.append(state)
            continue

        if state == "UNKNOWN":
            if not np.isfinite(running_high):
                running_high = c
                running_low = c
            else:
                running_high = max(running_high, c)
                running_low = min(running_low, c)

            if c <= running_high * (1.0 - threshold):
                state = "DOWN"
                swing_low = c

            elif c >= running_low * (1.0 + threshold):
                state = "UP"
                swing_high = c

        elif state == "UP":
            if not np.isfinite(swing_high):
                swing_high = c
            else:
                swing_high = max(swing_high, c)

            if c <= swing_high * (1.0 - threshold):
                state = "DOWN"
                swing_low = c

        elif state == "DOWN":
            if not np.isfinite(swing_low):
                swing_low = c
            else:
                swing_low = min(swing_low, c)

            if c >= swing_low * (1.0 + threshold):
                state = "UP"
                swing_high = c

        out.append(state)

    return pd.Series(out, index=close_series.index)


# ============================================================
# 读取 production_history.json
# ============================================================

source_path = Path(SOURCE)

if not source_path.exists():
    print(f"错误：找不到 {SOURCE}")
    print("请确认脚本和 production_history.json 在同一个 jason 文件夹里。")
    sys.exit(1)

with source_path.open("r", encoding="utf-8") as f:
    history = json.load(f)

if isinstance(history, dict) and "data" in history:
    rows = history["data"]
elif isinstance(history, list):
    rows = history
else:
    print("错误：production_history.json 格式无法识别。")
    sys.exit(1)

df = pd.DataFrame(rows).copy()

required_raw = [
    "date",
    "all_a_close",
    "hs300_close",
    "zz1000_close",
    "turnover",
    "turnover_rate",
    "financing_balance",
]

missing_columns = [c for c in required_raw if c not in df.columns]

if missing_columns:
    print("错误：production_history.json 缺少字段：")
    print(missing_columns)
    sys.exit(1)

df = df.sort_values("date").reset_index(drop=True)

for c in required_raw[1:]:
    df[c] = numeric(df[c])


# ============================================================
# 先检查 2026-08-05 以后六项原始数据是否完整
# ============================================================

new_raw = df[df["date"] >= NEW_START].copy()

if len(new_raw) == 0:
    print(f"错误：{SOURCE} 里没有 {NEW_START} 之后的数据。")
    sys.exit(1)

incomplete_raw = new_raw[
    required_raw[1:]
].isna().any(axis=1)

if incomplete_raw.any():
    bad = new_raw.loc[
        incomplete_raw,
        ["date"] + required_raw[1:]
    ]

    print("错误：以下日期六项原始数据不完整，停止计算正式结果：")
    print(bad.to_string(index=False))
    sys.exit(1)


# ============================================================
# 1. 基础价格指标
# ============================================================

close = df["all_a_close"]

ret1 = close.pct_change(fill_method=None)

df["ret5_pct"] = (
    close / close.shift(5) - 1.0
) * 100.0

df["ret63_pct"] = (
    close / close.shift(63) - 1.0
) * 100.0


low20 = close.rolling(
    20, min_periods=20
).min()

low60 = close.rolling(
    60, min_periods=60
).min()

low120 = close.rolling(
    120, min_periods=120
).min()

high20 = close.rolling(
    20, min_periods=20
).max()

high60 = close.rolling(
    60, min_periods=60
).max()


df["up20_pct"] = (
    close / low20 - 1.0
) * 100.0

df["up60_pct"] = (
    close / low60 - 1.0
) * 100.0

df["up120_pct"] = (
    close / low120 - 1.0
) * 100.0

df["dd20_pct"] = (
    close / high20 - 1.0
) * 100.0

df["dd60_pct"] = (
    close / high60 - 1.0
) * 100.0

df["distance20_high_pct"] = (
    -df["dd20_pct"]
)


# ============================================================
# 2. 波动率与历史分位
# ============================================================

df["rv20"] = ret1.rolling(
    20, min_periods=20
).std(ddof=1)

df["rv120"] = ret1.rolling(
    120, min_periods=120
).std(ddof=1)

df["rv_ratio"] = (
    df["rv20"] /
    df["rv120"]
)

df["rv_p252_fallback"] = (
    rolling_percentile_average(
        df["rv_ratio"],
        252
    )
)

df["rv_p756_pct"] = (
    rolling_percentile_average(
        df["rv_ratio"],
        756
    )
)

df["ret63_p756_pct"] = (
    rolling_percentile_average(
        df["ret63_pct"],
        756
    )
)


# ============================================================
# 3. 成交额 / 换手率分位
# ============================================================

df["turnover_amt_p252_pct"] = (
    rolling_percentile_average(
        df["turnover"],
        252
    )
)

df["turnover_rate_p252_pct"] = (
    rolling_percentile_average(
        df["turnover_rate"],
        252
    )
)


# ============================================================
# 4. 风格指标
# ============================================================

df["style_rs_ratio"] = (
    df["zz1000_close"] /
    df["hs300_close"]
)

style_high20 = (
    df["style_rs_ratio"]
    .rolling(
        20,
        min_periods=20
    )
    .max()
)

df["style_dd20_pct"] = (
    1.0 -
    df["style_rs_ratio"] /
    style_high20
) * 100.0


# ============================================================
# 5. 融资指标
# ============================================================

df["finance_63d_growth_pct"] = (
    df["financing_balance"] /
    df["financing_balance"].shift(63)
    - 1.0
) * 100.0

df["finance_63d_growth_p756_pct"] = (
    rolling_percentile_average(
        df["finance_63d_growth_pct"],
        756
    )
)


# ============================================================
# 6. phase5 / phase9
# ============================================================

df["phase5"] = calculate_phase(
    df["all_a_close"],
    0.05
)

df["phase9"] = calculate_phase(
    df["all_a_close"],
    0.09
)


# ============================================================
# 正式信号状态机只从 MODEL_START 开始
# 2011~2014 仅用于滚动指标预热
# ============================================================

calc = df[
    df["date"] >= MODEL_START
].copy().reset_index(drop=True)


# ============================================================
# 7. Top-5
# ============================================================

calc["top5_A"] = (
    (calc["phase5"] == "UP")
    &
    (calc["up60_pct"] >= 8)
    &
    (
        calc[
            "turnover_amt_p252_pct"
        ] >= 79
    )
    &
    (
        calc[
            "distance20_high_pct"
        ] <= 1
    )
    &
    (calc["ret5_pct"] >= 1)
)

calc["top5_B"] = (
    (calc["phase5"] == "UP")
    &
    (calc["rv_p756_pct"] >= 60)
    &
    (
        calc[
            "ret63_p756_pct"
        ] <= 20
    )
    &
    (calc["up20_pct"] >= 4)
    &
    (calc["ret5_pct"] >= 0)
)

calc["top5_hard"] = (
    calc["top5_A"] |
    calc["top5_B"]
)

calc["top5_formal"] = False
calc["top5_route"] = ""

last_signal = None
last_phase = None

for i in range(len(calc)):
    phase = calc.at[i, "phase5"]

    if phase != last_phase:
        last_signal = None
        last_phase = phase

    if (
        phase == "UP"
        and
        bool_value(
            calc.at[
                i,
                "top5_hard"
            ]
        )
    ):
        if (
            last_signal is None
            or
            i - last_signal > 15
        ):
            calc.at[
                i,
                "top5_formal"
            ] = True

            routes = []

            if bool_value(
                calc.at[
                    i,
                    "top5_A"
                ]
            ):
                routes.append("A")

            if bool_value(
                calc.at[
                    i,
                    "top5_B"
                ]
            ):
                routes.append("B")

            calc.at[
                i,
                "top5_route"
            ] = "/".join(routes)

            last_signal = i


# ============================================================
# 8. Top-9
# ============================================================

calc["top9_A"] = (
    (
        calc[
            "turnover_rate_p252_pct"
        ] >= 75
    )
    &
    (calc["up120_pct"] >= 10)
)

calc["top9_B"] = (
    (calc["rv_p756_pct"] >= 50)
    &
    (
        calc[
            "style_dd20_pct"
        ] >= 2
    )
)

calc["top9_C"] = (
    (
        calc[
            "turnover_amt_p252_pct"
        ] >= 85
    )
    &
    (calc["up120_pct"] >= 10)
    &
    (
        calc[
            "style_dd20_pct"
        ] >= 2
    )
)

calc["top9_F"] = (
    calc[
        "finance_63d_growth_p756_pct"
    ].notna()
    &
    (
        calc[
            "finance_63d_growth_p756_pct"
        ] <= 85
    )
)

raw_top9 = []

top5_indices = calc.index[
    calc["top5_formal"]
].tolist()

for i in top5_indices:
    A = bool_value(
        calc.at[
            i,
            "top9_A"
        ]
    )

    B = bool_value(
        calc.at[
            i,
            "top9_B"
        ]
    )

    C = bool_value(
        calc.at[
            i,
            "top9_C"
        ]
    )

    F = bool_value(
        calc.at[
            i,
            "top9_F"
        ]
    )

    # 候选日已经存在 A/B/C：
    # 只能候选日升级。
    # 如果融资门失败，未来不能延期绕过。
    if A or B or C:
        if F:
            routes = []

            if A:
                routes.append("A")
            if B:
                routes.append("B")
            if C:
                routes.append("C")

            raw_top9.append({
                "index": i,
                "candidate_index": i,
                "deferred": False,
                "route": "/".join(routes),
            })

        continue

    # 候选日 A/B/C 都没有：
    # 只允许 Route B 延迟最多 6 个交易日；
    # 且 phase5 必须继续为 UP。
    for j in range(
        i + 1,
        min(
            i + 7,
            len(calc)
        )
    ):
        if (
            calc.at[
                j,
                "phase5"
            ] != "UP"
        ):
            break

        if (
            bool_value(
                calc.at[
                    j,
                    "top9_B"
                ]
            )
            and
            bool_value(
                calc.at[
                    j,
                    "top9_F"
                ]
            )
        ):
            raw_top9.append({
                "index": j,
                "candidate_index": i,
                "deferred": True,
                "route": "B",
            })

            break


# 同一天可能由多个候选指向，只保留一次
raw_top9_by_day = {}

for item in raw_top9:
    raw_top9_by_day.setdefault(
        item["index"],
        item
    )

raw_top9 = [
    raw_top9_by_day[k]
    for k in sorted(
        raw_top9_by_day
    )
]

calc["top9_formal"] = False
calc["top9_route"] = ""
calc["top9_deferred"] = False
calc["top9_candidate_date"] = ""

last_signal = None

for item in raw_top9:
    i = item["index"]

    if (
        last_signal is None
        or
        i - last_signal > 15
    ):
        calc.at[
            i,
            "top9_formal"
        ] = True

        calc.at[
            i,
            "top9_route"
        ] = item["route"]

        calc.at[
            i,
            "top9_deferred"
        ] = item["deferred"]

        calc.at[
            i,
            "top9_candidate_date"
        ] = calc.at[
            item[
                "candidate_index"
            ],
            "date"
        ]

        last_signal = i


# ============================================================
# 9. Bottom-5
# ============================================================

# 早期历史不足：
# rv_p756 有值时使用 756；
# rv_p756 尚未形成时临时使用 RV252。
calc["bottom5_rv_effective"] = (
    calc["rv_p756_pct"].where(
        calc[
            "rv_p756_pct"
        ].notna(),
        calc[
            "rv_p252_fallback"
        ]
    )
)

bottom5_A_nonphase = (
    (calc["dd20_pct"] <= -4)
    &
    (calc["ret5_pct"] <= -2.4)
    &
    (
        calc[
            "bottom5_rv_effective"
        ] >= 40
    )
)

calc["bottom5_A_base"] = (
    (calc["phase5"] == "DOWN")
    &
    bottom5_A_nonphase
)

calc["bottom5_B"] = (
    (calc["phase5"] == "DOWN")
    &
    (calc["dd60_pct"] <= -9)
    &
    (
        calc[
            "ret63_p756_pct"
        ] <= 60
    )
    &
    (calc["rv_p756_pct"] >= 70)
    &
    (calc["ret5_pct"] <= 0)
)

calc["bottom5_C"] = (
    (calc["phase5"] == "DOWN")
    &
    (calc["dd60_pct"] <= -8)
    &
    (
        calc[
            "ret63_p756_pct"
        ] <= 50
    )
    &
    (calc["rv_p756_pct"] <= 15)
    &
    (calc["ret5_pct"] <= -4.5)
)

calc["bottom5_A"] = False
calc["bottom5_M"] = False

phase_age = 0
previous_phase = None

for i in range(len(calc)):
    phase = calc.at[
        i,
        "phase5"
    ]

    if phase != previous_phase:
        phase_age = 1
    else:
        phase_age += 1

    A = bool_value(
        calc.at[
            i,
            "bottom5_A_base"
        ]
    )

    B = bool_value(
        calc.at[
            i,
            "bottom5_B"
        ]
    )

    C = bool_value(
        calc.at[
            i,
            "bottom5_C"
        ]
    )

    # 纯 A：DOWN 相位第2日及以后，
    # 还必须满足 dd60 <= -7.5
    if A:
        pure_A = (
            not B
            and
            not C
        )

        if (
            pure_A
            and
            phase_age >= 2
        ):
            A = (
                pd.notna(
                    calc.at[
                        i,
                        "dd60_pct"
                    ]
                )
                and
                calc.at[
                    i,
                    "dd60_pct"
                ] <= -7.5
            )

    calc.at[
        i,
        "bottom5_A"
    ] = A

    # M：新 DOWN phase 第一日，
    # 前5个交易日出现过 Route A 非相位条件即可继承一次
    new_down = (
        phase == "DOWN"
        and
        (
            i == 0
            or
            calc.at[
                i - 1,
                "phase5"
            ] != "DOWN"
        )
    )

    if new_down:
        start = max(
            0,
            i - 5
        )

        inherited = False

        for j in range(
            start,
            i
        ):
            if bool_value(
                bottom5_A_nonphase.iloc[j]
            ):
                inherited = True
                break

        calc.at[
            i,
            "bottom5_M"
        ] = inherited

    previous_phase = phase


calc["bottom5_hard"] = (
    calc["bottom5_A"]
    |
    calc["bottom5_B"]
    |
    calc["bottom5_C"]
    |
    calc["bottom5_M"]
)

calc["bottom5_formal"] = False
calc["bottom5_route"] = ""

last_signal = None
last_phase = None

for i in range(len(calc)):
    phase = calc.at[
        i,
        "phase5"
    ]

    if phase != last_phase:
        last_signal = None
        last_phase = phase

    if (
        phase == "DOWN"
        and
        bool_value(
            calc.at[
                i,
                "bottom5_hard"
            ]
        )
    ):
        if (
            last_signal is None
            or
            i - last_signal > 22
        ):
            calc.at[
                i,
                "bottom5_formal"
            ] = True

            routes = []

            if bool_value(
                calc.at[
                    i,
                    "bottom5_A"
                ]
            ):
                routes.append("A")

            if bool_value(
                calc.at[
                    i,
                    "bottom5_B"
                ]
            ):
                routes.append("B")

            if bool_value(
                calc.at[
                    i,
                    "bottom5_C"
                ]
            ):
                routes.append("C")

            if bool_value(
                calc.at[
                    i,
                    "bottom5_M"
                ]
            ):
                routes.append("M")

            calc.at[
                i,
                "bottom5_route"
            ] = "/".join(routes)

            last_signal = i


# ============================================================
# 10. Bottom-9
# ============================================================

calc["bottom9_A"] = (
    (calc["phase9"] == "DOWN")
    &
    (calc["dd20_pct"] <= -4)
    &
    (calc["ret5_pct"] <= -3.8)
    &
    (calc["rv_p756_pct"] >= 55)
)

calc["bottom9_B"] = (
    (calc["phase9"] == "DOWN")
    &
    (calc["dd60_pct"] <= -12.5)
    &
    (
        calc[
            "ret63_p756_pct"
        ] <= 60
    )
    &
    (calc["rv_p756_pct"] >= 50)
    &
    (calc["ret5_pct"] <= 0)
)

calc["bottom9_C"] = (
    (calc["phase9"] == "DOWN")
    &
    (calc["dd60_pct"] <= -9)
    &
    (
        calc[
            "ret63_p756_pct"
        ] <= 60
    )
    &
    (calc["rv_p756_pct"] <= 15)
    &
    (calc["ret5_pct"] <= -2)
)

calc["bottom9_hard"] = (
    calc["bottom9_A"]
    |
    calc["bottom9_B"]
    |
    calc["bottom9_C"]
)

calc["bottom9_formal"] = False
calc["bottom9_route"] = ""

last_signal = None
last_phase = None

for i in range(len(calc)):
    phase = calc.at[
        i,
        "phase9"
    ]

    if phase != last_phase:
        last_signal = None
        last_phase = phase

    if (
        phase == "DOWN"
        and
        bool_value(
            calc.at[
                i,
                "bottom9_hard"
            ]
        )
    ):
        if (
            last_signal is None
            or
            i - last_signal > 15
        ):
            calc.at[
                i,
                "bottom9_formal"
            ] = True

            routes = []

            if bool_value(
                calc.at[
                    i,
                    "bottom9_A"
                ]
            ):
                routes.append("A")

            if bool_value(
                calc.at[
                    i,
                    "bottom9_B"
                ]
            ):
                routes.append("B")

            if bool_value(
                calc.at[
                    i,
                    "bottom9_C"
                ]
            ):
                routes.append("C")

            calc.at[
                i,
                "bottom9_route"
            ] = "/".join(routes)

            last_signal = i


# ============================================================
# 11. 安全闸门：先与当前生产版历史正式信号复核
# ============================================================

def production_dates(latest_data, key):
    formal = (
        latest_data[
            "strategies"
        ][key]["formal"]
    )

    return set(
        item["date"]
        for item in formal
        if (
            MODEL_START
            <= item["date"]
            <= VERIFY_END
        )
    )


def calculated_dates(column):
    return set(
        calc.loc[
            calc[column]
            &
            (
                calc["date"]
                <= VERIFY_END
            ),
            "date"
        ].tolist()
    )


verify_results = {}
latest_path = Path(LATEST)

if latest_path.exists():
    with latest_path.open(
        "r",
        encoding="utf-8"
    ) as f:
        latest_data = json.load(f)

    checks = [
        (
            "Top-5",
            "top5",
            "top5_formal"
        ),
        (
            "Top-9",
            "top9",
            "top9_formal"
        ),
        (
            "Bottom-5",
            "bottom5",
            "bottom5_formal"
        ),
        (
            "Bottom-9",
            "bottom9",
            "bottom9_formal"
        ),
    ]

    all_pass = True

    print()
    print(
        "========== 历史生产版安全复核 =========="
    )

    for name, key, col in checks:
        target = production_dates(
            latest_data,
            key
        )

        got = calculated_dates(
            col
        )

        missed = sorted(
            target - got
        )

        extra = sorted(
            got - target
        )

        passed = (
            target == got
        )

        verify_results[name] = {
            "target_count": len(target),
            "calculated_count": len(got),
            "missed": missed,
            "extra": extra,
            "pass": passed,
        }

        print()
        print(
            f"{name}: "
            f"{len(got)}/{len(target)} "
            f"{'PASS' if passed else 'FAIL'}"
        )
        print(
            "漏掉:",
            missed
        )
        print(
            "多出:",
            extra
        )

        if not passed:
            all_pass = False

    if not all_pass:
        print()
        print(
            "停止：历史正式信号没有100%复现。"
        )
        print(
            "未输出 2026-08-05 之后的正式结果。"
        )
        sys.exit(2)

    print()
    print(
        "历史四模块复核：100% PASS"
    )

else:
    print()
    print(
        "警告：没有找到 latest.json，"
        "无法执行历史生产版安全复核。"
    )
    print(
        "为避免未经验证的结果进入正式使用，脚本停止。"
    )
    sys.exit(3)


# ============================================================
# 12. 输出 2026-08-05 以后逐日结果
# ============================================================

new = calc[
    calc["date"] >= NEW_START
].copy()

output_columns = [
    "date",
    "all_a_close",
    "phase5",
    "phase9",
    "ret5_pct",
    "up20_pct",
    "up60_pct",
    "up120_pct",
    "dd20_pct",
    "dd60_pct",
    "rv_p756_pct",
    "ret63_p756_pct",
    "turnover_amt_p252_pct",
    "turnover_rate_p252_pct",
    "style_dd20_pct",
    "finance_63d_growth_p756_pct",

    "top5_A",
    "top5_B",
    "top5_formal",
    "top5_route",

    "top9_A",
    "top9_B",
    "top9_C",
    "top9_F",
    "top9_formal",
    "top9_route",
    "top9_deferred",
    "top9_candidate_date",

    "bottom5_A",
    "bottom5_B",
    "bottom5_C",
    "bottom5_M",
    "bottom5_formal",
    "bottom5_route",

    "bottom9_A",
    "bottom9_B",
    "bottom9_C",
    "bottom9_formal",
    "bottom9_route",
]

new[
    output_columns
].to_csv(
    OUTPUT_CSV,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# 13. JSON 输出
# ============================================================

def clean_value(v):
    if pd.isna(v):
        return None

    if isinstance(
        v,
        (
            np.bool_,
            bool
        )
    ):
        return bool(v)

    if isinstance(
        v,
        (
            np.integer,
            int
        )
    ):
        return int(v)

    if isinstance(
        v,
        (
            np.floating,
            float
        )
    ):
        return float(v)

    return v


daily_records = []

for _, row in new[
    output_columns
].iterrows():
    daily_records.append({
        col: clean_value(
            row[col]
        )
        for col in output_columns
    })


formal_signals = {
    "top5": [],
    "top9": [],
    "bottom5": [],
    "bottom9": [],
}

for _, row in new.iterrows():
    date = row["date"]

    if bool_value(
        row["top5_formal"]
    ):
        formal_signals[
            "top5"
        ].append({
            "date": date,
            "route": (
                row[
                    "top5_route"
                ]
                or None
            ),
        })

    if bool_value(
        row["top9_formal"]
    ):
        formal_signals[
            "top9"
        ].append({
            "date": date,
            "route": (
                row[
                    "top9_route"
                ]
                or None
            ),
            "deferred": bool(
                row[
                    "top9_deferred"
                ]
            ),
            "candidate_date": (
                row[
                    "top9_candidate_date"
                ]
                or None
            ),
        })

    if bool_value(
        row["bottom5_formal"]
    ):
        formal_signals[
            "bottom5"
        ].append({
            "date": date,
            "route": (
                row[
                    "bottom5_route"
                ]
                or None
            ),
        })

    if bool_value(
        row["bottom9_formal"]
    ):
        formal_signals[
            "bottom9"
        ].append({
            "date": date,
            "route": (
                row[
                    "bottom9_route"
                ]
                or None
            ),
        })


latest_row = new.iloc[-1]

json_output = {
    "model_version": (
        "current_production_5_9_"
        "historically_reproduced"
    ),
    "source": SOURCE,
    "start": NEW_START,
    "end": str(
        new.iloc[-1]["date"]
    ),
    "history_verification": verify_results,
    "formal_signals": formal_signals,
    "latest": {
        "date": latest_row[
            "date"
        ],
        "all_a_close": clean_value(
            latest_row[
                "all_a_close"
            ]
        ),
        "phase5": latest_row[
            "phase5"
        ],
        "phase9": latest_row[
            "phase9"
        ],
        "top5_formal": bool(
            latest_row[
                "top5_formal"
            ]
        ),
        "top9_formal": bool(
            latest_row[
                "top9_formal"
            ]
        ),
        "bottom5_formal": bool(
            latest_row[
                "bottom5_formal"
            ]
        ),
        "bottom9_formal": bool(
            latest_row[
                "bottom9_formal"
            ]
        ),
    },
    "daily": daily_records,
}

with open(
    OUTPUT_JSON,
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        json_output,
        f,
        ensure_ascii=False,
        indent=2,
        allow_nan=False
    )


# ============================================================
# 14. 人工可读摘要
# ============================================================

lines = []

lines.append(
    "A股 5%/9% 当前生产版增量正式信号"
)

lines.append(
    f"计算区间: {NEW_START} ~ "
    f"{new.iloc[-1]['date']}"
)

lines.append(
    "历史安全复核: "
    "Top-5 / Top-9 / Bottom-5 / Bottom-9 全部 PASS"
)

lines.append("")

for key, title in [
    (
        "top5",
        "Top-5"
    ),
    (
        "top9",
        "Top-9"
    ),
    (
        "bottom5",
        "Bottom-5"
    ),
    (
        "bottom9",
        "Bottom-9"
    ),
]:
    signals = formal_signals[key]

    if not signals:
        lines.append(
            f"{title}: 区间内无正式信号"
        )

    else:
        for signal in signals:
            extra = ""

            if (
                key == "top9"
                and
                signal.get(
                    "deferred"
                )
            ):
                extra = (
                    "；延迟B"
                    f"；来源Top-5="
                    f"{signal.get('candidate_date')}"
                )

            lines.append(
                f"{title}: "
                f"{signal['date']} "
                f"Route "
                f"{signal.get('route')}"
                f"{extra}"
            )


lines.append("")
lines.append(
    "最新交易日:"
    f" {latest_row['date']}"
)

lines.append(
    f"phase5: "
    f"{latest_row['phase5']}"
)

lines.append(
    f"phase9: "
    f"{latest_row['phase9']}"
)

lines.append(
    f"Top-5 当日正式信号: "
    f"{bool(latest_row['top5_formal'])}"
)

lines.append(
    f"Top-9 当日正式信号: "
    f"{bool(latest_row['top9_formal'])}"
)

lines.append(
    f"Bottom-5 当日正式信号: "
    f"{bool(latest_row['bottom5_formal'])}"
)

lines.append(
    f"Bottom-9 当日正式信号: "
    f"{bool(latest_row['bottom9_formal'])}"
)

with open(
    OUTPUT_TXT,
    "w",
    encoding="utf-8"
) as f:
    f.write(
        "\n".join(lines)
    )


# ============================================================
# 15. CMD 输出
# ============================================================

print()
print(
    "========== 2026-08-05以后正式结果 =========="
)

print(
    "\n".join(lines)
)

print()
print(
    "已生成："
)

print(
    f"  {OUTPUT_CSV}"
)

print(
    f"  {OUTPUT_JSON}"
)

print(
    f"  {OUTPUT_TXT}"
)
