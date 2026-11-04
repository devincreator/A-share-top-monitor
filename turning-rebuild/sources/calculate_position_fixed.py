import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# A股拐点系统：当前正式执行层增量计算
#
# 目标：
# 1. 用 latest.json 的历史净值曲线确认 2026-08-04 冻结仓位
# 2. 从 2026-08-05 开始读取已经100%复现的正式信号
# 3. 按当前正式执行规则计算 0% / 25% / 40% / 100% 仓位
# 4. 输出每天的执行状态与当前仓位
#
# 本脚本不会修改：
# production_history.json
# latest.json
# calculated_signals_20260805_to_latest.json
# ============================================================

HISTORY_FILE = "production_history.json"
LATEST_FILE = "latest.json"
SIGNALS_FILE = "calculated_signals_20260805_to_latest.json"

FREEZE_DATE = "2026-08-04"
START_DATE = "2026-08-05"

COST = 0.001

OUTPUT_CSV = "calculated_position_20260805_to_latest.csv"
OUTPUT_JSON = "calculated_position_20260805_to_latest.json"
OUTPUT_TXT = "calculated_position_summary.txt"


# ============================================================
# 工具函数
# ============================================================

def rolling_percentile_average(series, window):
    x = pd.to_numeric(
        series,
        errors="coerce"
    ).to_numpy(dtype=float)

    out = np.full(
        len(x),
        np.nan
    )

    for i in range(
        window - 1,
        len(x)
    ):
        a = x[
            i - window + 1:
            i + 1
        ]

        if not np.isfinite(a).all():
            continue

        current = a[-1]

        less = np.sum(
            a < current
        )

        equal = np.sum(
            a == current
        )

        average_rank = (
            less +
            (equal + 1) / 2.0
        )

        out[i] = (
            average_rank /
            window *
            100.0
        )

    return pd.Series(
        out,
        index=series.index
    )


def load_json(path):
    path = Path(path)

    if not path.exists():
        print(
            f"错误：找不到 {path.name}"
        )
        sys.exit(1)

    with path.open(
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)


def as_rows(obj):
    if isinstance(obj, list):
        return obj

    if (
        isinstance(obj, dict)
        and
        "data" in obj
    ):
        return obj["data"]

    print(
        "错误：production_history.json 格式无法识别。"
    )
    sys.exit(1)


# ============================================================
# 1. 读取三个正式文件
# ============================================================

history_obj = load_json(
    HISTORY_FILE
)

latest = load_json(
    LATEST_FILE
)

signals_obj = load_json(
    SIGNALS_FILE
)


# 必须先确认上一阶段四模块已经100%复现
verification = signals_obj.get(
    "history_verification",
    {}
)

required_modules = [
    "Top-5",
    "Top-9",
    "Bottom-5",
    "Bottom-9",
]

bad_modules = []

for name in required_modules:
    info = verification.get(
        name,
        {}
    )

    if not info.get(
        "pass",
        False
    ):
        bad_modules.append(
            name
        )

if bad_modules:
    print(
        "错误：正式信号安全复核没有全部PASS："
    )
    print(
        bad_modules
    )
    sys.exit(2)


# ============================================================
# 2. 读取原始市场价格
# ============================================================

df = pd.DataFrame(
    as_rows(
        history_obj
    )
).copy()

required_fields = [
    "date",
    "all_a_close",
]

for c in required_fields:
    if c not in df.columns:
        print(
            f"错误：production_history.json 缺少 {c}"
        )
        sys.exit(3)

df = df.sort_values(
    "date"
).reset_index(
    drop=True
)

df["all_a_close"] = pd.to_numeric(
    df["all_a_close"],
    errors="coerce"
)

if (
    df.loc[
        df["date"] >= START_DATE,
        "all_a_close"
    ].isna().any()
):
    print(
        "错误：8月5日以后存在缺失收盘价。"
    )
    sys.exit(4)


# ============================================================
# 3. 计算执行层需要的三个因果指标
# ============================================================

close = df[
    "all_a_close"
]

ret1 = close.pct_change(
    fill_method=None
)

df["ret5_pct"] = (
    close /
    close.shift(5)
    - 1.0
) * 100.0


high20 = close.rolling(
    20,
    min_periods=20
).max()

df["dd20_pct"] = (
    close /
    high20
    - 1.0
) * 100.0


# 60日实现波动率
df["rv60"] = ret1.rolling(
    60,
    min_periods=60
).std(
    ddof=1
)

# 过去756交易日历史分位
df["rv60_p756"] = (
    rolling_percentile_average(
        df["rv60"],
        756
    )
)


# ============================================================
# 4. 从 latest.json 历史净值曲线反推出冻结仓位
#
# 不是重新猜仓位。
# 当前生产净值每天只可能对应：
# 0 / 25% / 40% / 100%
#
# 根据：
# 当日市场收益 + 已知0.10%调仓成本
# 可以逐日还原历史实际仓位。
# ============================================================

backtest = latest.get(
    "backtest",
    {}
)

curve_dates = backtest.get(
    "curve_dates",
    []
)

curves = backtest.get(
    "curves",
    {}
)

strategy_curve = curves.get(
    "最新拐点执行策略",
    []
)

if (
    not curve_dates
    or
    not strategy_curve
    or
    len(curve_dates)
    !=
    len(strategy_curve)
):
    print(
        "错误：latest.json 中缺少完整历史执行净值曲线。"
    )
    sys.exit(5)


price_map = dict(
    zip(
        df["date"],
        df["all_a_close"]
    )
)

states = [
    0.0,
    0.25,
    0.40,
    1.0,
]

# 当前正式回测起始仓位为100%
position = 1.0

inferred_positions = {
    curve_dates[0]: position
}

inferred_changes = []

fit_errors = []

for i in range(
    1,
    len(curve_dates)
):
    date0 = curve_dates[
        i - 1
    ]

    date1 = curve_dates[
        i
    ]

    if (
        date0 not in price_map
        or
        date1 not in price_map
    ):
        continue

    p0 = float(
        price_map[
            date0
        ]
    )

    p1 = float(
        price_map[
            date1
        ]
    )

    market_ret = (
        p1 /
        p0
        - 1.0
    )

    nav0 = float(
        strategy_curve[
            i - 1
        ]
    )

    nav1 = float(
        strategy_curve[
            i
        ]
    )

    observed_ratio = (
        nav1 /
        nav0
    )

    candidates = []

    for target in states:
        predicted_ratio = (
            1.0 +
            position *
            market_ret
        ) * (
            1.0 -
            COST *
            abs(
                target -
                position
            )
        )

        error = abs(
            predicted_ratio -
            observed_ratio
        )

        candidates.append(
            (
                error,
                target,
                predicted_ratio
            )
        )

    error, target, _ = min(
        candidates,
        key=lambda x: x[0]
    )

    fit_errors.append(
        error
    )

    if abs(
        target -
        position
    ) > 1e-12:
        inferred_changes.append({
            "date": date1,
            "from": position,
            "to": target,
        })

    position = target

    inferred_positions[
        date1
    ] = position


if FREEZE_DATE not in inferred_positions:
    print(
        f"错误：无法从历史净值恢复 {FREEZE_DATE} 仓位。"
    )
    sys.exit(6)


freeze_position = float(
    inferred_positions[
        FREEZE_DATE
    ]
)

historical_changes = [
    x
    for x in inferred_changes
    if x["date"] <= FREEZE_DATE
]

max_fit_error = (
    max(fit_errors)
    if fit_errors
    else None
)


print()
print(
    "========== 历史执行层冻结状态 =========="
)

print(
    f"{FREEZE_DATE} 收盘仓位:",
    f"{freeze_position * 100:.0f}%"
)

print(
    "截至冻结日历史调仓次数:",
    len(
        historical_changes
    )
)

print(
    "网页生产版标准调仓次数:",
    55
)

if max_fit_error is not None:
    print(
        "历史净值反推最大单日误差:",
        f"{max_fit_error:.8f}"
    )


# 当前生产版必须满足：
# 8/4 已经空仓 + 55次历史调仓
if (
    abs(
        freeze_position -
        0.0
    ) > 1e-12
    or
    len(
        historical_changes
    ) != 55
):
    print()
    print(
        "FAIL：冻结执行状态与当前生产版不一致。"
    )
    print(
        "停止，不计算增量仓位。"
    )
    sys.exit(7)

print(
    "冻结状态校验: PASS"
)


# ============================================================
# 5. 读取 8月5日以后的正式信号
# ============================================================

formal = signals_obj.get(
    "formal_signals",
    {}
)


def signal_map(key):
    return {
        item["date"]: item
        for item in formal.get(
            key,
            []
        )
    }


top9_map = signal_map(
    "top9"
)

bottom9_map = signal_map(
    "bottom9"
)

bottom5_map = signal_map(
    "bottom5"
)


# ============================================================
# 6. 初始化 8月4日冻结执行状态
#
# 当前生产历史已经确认：
# 8/4 = 0%
# 没有核心多头仓位
#
# 增量计算从这个已经冻结的生产状态继续。
# ============================================================

current_position = 0.0
core_long = False

pending_sell = None
pending_buy = None
trial = None

scheduled_action = None

events = []


# ============================================================
# 7. 增量执行状态机
# ============================================================

inc = df[
    df["date"] >= START_DATE
].copy().reset_index(
    drop=True
)

result_rows = []


def add_event(
    date,
    event,
    detail,
    target=None
):
    item = {
        "date": date,
        "event": event,
        "detail": detail,
    }

    if target is not None:
        item[
            "target_position"
        ] = float(
            target
        )

    events.append(
        item
    )


for i in range(
    len(inc)
):
    date = inc.at[
        i,
        "date"
    ]

    close_today = float(
        inc.at[
            i,
            "all_a_close"
        ]
    )

    # --------------------------------------------------------
    # A. 先执行前一交易日已经确认的 T+1 指令
    # --------------------------------------------------------

    action_today = ""

    if scheduled_action is not None:
        target = scheduled_action[
            "target"
        ]

        reason = scheduled_action[
            "reason"
        ]

        set_core = scheduled_action.get(
            "set_core"
        )

        old_position = (
            current_position
        )

        if set_core is not None:
            core_long = bool(
                set_core
            )

        current_position = float(
            target
        )

        action_today = (
            f"{old_position * 100:.0f}%"
            f" → "
            f"{current_position * 100:.0f}%"
            f"；{reason}"
        )

        if abs(
            old_position -
            current_position
        ) > 1e-12:
            add_event(
                date,
                "EXECUTION",
                action_today,
                current_position
            )
        else:
            add_event(
                date,
                "EXECUTION_NO_CHANGE",
                (
                    f"目标仍为"
                    f"{current_position * 100:.0f}%"
                    f"；{reason}"
                ),
                current_position
            )

        scheduled_action = None


    # --------------------------------------------------------
    # B. 读取当天正式9%信号，先处理反向冲突
    # --------------------------------------------------------

    top9_today = (
        date in top9_map
    )

    bottom9_today = (
        date in bottom9_map
    )

    bottom5_today = (
        bottom5_map.get(
            date
        )
    )


    # Top-9：
    # 取消待买 / 试仓；
    # 建立顶部待确认。
    if top9_today:

        if pending_buy is not None:
            add_event(
                date,
                "BUY_PENDING_CANCELLED",
                "Top-9反向信号出现，取消Bottom-9待买。"
            )

            pending_buy = None

        if trial is not None:
            add_event(
                date,
                "TRIAL_CANCELLED",
                "Top-9反向信号出现，取消40%试仓。"
            )

            # 下一交易日退出试仓
            if (
                current_position
                == 0.40
            ):
                scheduled_action = {
                    "target": 0.0,
                    "reason": (
                        "Top-9反向信号，"
                        "退出Bottom-5试仓"
                    ),
                    "set_core": False,
                }

            trial = None

        # 同向重复Top-9不重置计时
        if pending_sell is None:
            pending_sell = {
                "signal_date": date,
                "start_index": i,
            }

            add_event(
                date,
                "TOP9_PENDING_SELL",
                (
                    "Top-9正式信号；"
                    "进入顶部待确认，"
                    "最长观察30个交易日。"
                )
            )


    # Bottom-9：
    # 取消顶部待确认；
    # 若当前无核心多头，进入底部待确认。
    if bottom9_today:

        if pending_sell is not None:
            add_event(
                date,
                "SELL_PENDING_CANCELLED",
                "Bottom-9反向信号出现，取消Top-9待卖。"
            )

            pending_sell = None

        if (
            not core_long
            and
            pending_buy is None
        ):
            pending_buy = {
                "signal_date": date,
                "start_index": i,
                "low": close_today,
            }

            add_event(
                date,
                "BOTTOM9_PENDING_BUY",
                (
                    "Bottom-9正式信号；"
                    "开始记录信号后最低收盘价，"
                    "等待反弹7%。"
                )
            )

        if trial is not None:
            trial[
                "bottom9_seen"
            ] = True

            trial[
                "bottom9_date"
            ] = date


    # --------------------------------------------------------
    # C. Bottom-5 M 试仓
    # 只有 routes 中真正含 M 才参与执行
    # --------------------------------------------------------

    if bottom5_today is not None:

        route = str(
            bottom5_today.get(
                "route",
                ""
            )
            or
            ""
        )

        routes = [
            x.strip()
            for x in route.split(
                "/"
            )
            if x.strip()
        ]

        if (
            "M" in routes
            and
            not core_long
            and
            trial is None
            and
            not top9_today
        ):
            trial = {
                "signal_date": date,
                "start_index": i,
                "bottom9_seen": (
                    bottom9_today
                ),
            }

            scheduled_action = {
                "target": 0.40,
                "reason": (
                    "Bottom-5 相位记忆M，"
                    "建立40%试仓"
                ),
                "set_core": False,
            }

            add_event(
                date,
                "BOTTOM5_M_TRIAL",
                (
                    "Bottom-5 M成立；"
                    "下一交易日收盘目标40%。"
                )
            )


    # --------------------------------------------------------
    # D. Top-9 价格转弱确认
    #
    # 从信号后的下一交易日开始，
    # 最长30个交易日观察 ret5 <= -1.5%
    # --------------------------------------------------------

    if pending_sell is not None:
        age = (
            i -
            pending_sell[
                "start_index"
            ]
        )

        if (
            1 <= age <= 30
            and
            pd.notna(
                inc.at[
                    i,
                    "ret5_pct"
                ]
            )
            and
            inc.at[
                i,
                "ret5_pct"
            ] <= -1.5
        ):
            signal_date = (
                pending_sell[
                    "signal_date"
                ]
            )

            add_event(
                date,
                "TOP9_SELL_CONFIRMED",
                (
                    f"来源Top-9={signal_date}；"
                    f"ret5="
                    f"{inc.at[i, 'ret5_pct']:.4f}%"
                    " <= -1.5%；"
                    "下一交易日收盘目标0%。"
                ),
                0.0
            )

            scheduled_action = {
                "target": 0.0,
                "reason": (
                    "Top-9价格转弱确认"
                ),
                "set_core": False,
            }

            pending_sell = None

        elif age >= 30:
            add_event(
                date,
                "TOP9_SELL_EXPIRED",
                (
                    "Top-9待卖观察满30个交易日，"
                    "未完成价格转弱确认。"
                )
            )

            pending_sell = None


    # --------------------------------------------------------
    # E. Bottom-9 7%反弹确认
    # --------------------------------------------------------

    if pending_buy is not None:

        pending_buy[
            "low"
        ] = min(
            float(
                pending_buy[
                    "low"
                ]
            ),
            close_today
        )

        age = (
            i -
            pending_buy[
                "start_index"
            ]
        )

        rebound = (
            close_today /
            pending_buy[
                "low"
            ]
            - 1.0
        )

        if (
            1 <= age <= 30
            and
            rebound >= 0.07
        ):
            signal_date = (
                pending_buy[
                    "signal_date"
                ]
            )

            add_event(
                date,
                "BOTTOM9_BUY_CONFIRMED",
                (
                    f"来源Bottom-9={signal_date}；"
                    f"最低收盘="
                    f"{pending_buy['low']:.2f}；"
                    f"反弹="
                    f"{rebound * 100:.2f}%"
                    " >= 7%；"
                    "下一交易日收盘进入100%核心仓位。"
                ),
                1.0
            )

            scheduled_action = {
                "target": 1.0,
                "reason": (
                    "Bottom-9反弹7%确认，"
                    "进入核心仓位"
                ),
                "set_core": True,
            }

            pending_buy = None

            trial = None

        elif age >= 30:
            add_event(
                date,
                "BOTTOM9_BUY_EXPIRED",
                (
                    "Bottom-9待买观察满30个交易日，"
                    "未完成7%反弹确认。"
                )
            )

            pending_buy = None

            if (
                trial is not None
                and
                current_position
                == 0.40
            ):
                scheduled_action = {
                    "target": 0.0,
                    "reason": (
                        "Bottom-9确认超时，"
                        "退出40%试仓"
                    ),
                    "set_core": False,
                }

                trial = None


    # --------------------------------------------------------
    # F. Bottom-5 M：10日内没有Bottom-9则退出试仓
    # --------------------------------------------------------

    if (
        trial is not None
        and
        not trial.get(
            "bottom9_seen",
            False
        )
    ):
        age = (
            i -
            trial[
                "start_index"
            ]
        )

        if age >= 10:
            add_event(
                date,
                "BOTTOM5_TRIAL_EXPIRED",
                (
                    "Bottom-5 M试仓10个交易日内"
                    "没有Bottom-9升级；"
                    "下一交易日回到0%。"
                ),
                0.0
            )

            scheduled_action = {
                "target": 0.0,
                "reason": (
                    "Bottom-5 M试仓超时"
                ),
                "set_core": False,
            }

            trial = None


    # --------------------------------------------------------
    # G. 核心持有状态下的风险层
    #
    # 优先级：
    # dd20 <= -8% -> 0%
    # 否则 rv60_p756 >=90% -> 25%
    # 否则 ->100%
    #
    # 若当天已有更高优先级的买卖确认指令，
    # 不用风险层覆盖该指令。
    # --------------------------------------------------------

    risk_state = "非核心持有"

    if core_long:

        dd20 = inc.at[
            i,
            "dd20_pct"
        ]

        rv60p = inc.at[
            i,
            "rv60_p756"
        ]

        if (
            pd.notna(
                dd20
            )
            and
            dd20 <= -8.0
        ):
            risk_target = 0.0
            risk_state = (
                "一级保护：20日回撤<=-8%"
            )

        elif (
            pd.notna(
                rv60p
            )
            and
            rv60p >= 90.0
        ):
            risk_target = 0.25
            risk_state = (
                "二级保护：RV60历史分位>=90%"
            )

        else:
            risk_target = 1.0
            risk_state = (
                "正常核心仓位"
            )

        if scheduled_action is None:
            if abs(
                current_position -
                risk_target
            ) > 1e-12:
                scheduled_action = {
                    "target": risk_target,
                    "reason": risk_state,
                    "set_core": True,
                }


    # --------------------------------------------------------
    # H. 保存当天收盘后的状态
    # --------------------------------------------------------

    if pending_sell is not None:
        pending_sell_status = (
            pending_sell[
                "signal_date"
            ]
        )
    else:
        pending_sell_status = ""

    if pending_buy is not None:
        pending_buy_status = (
            pending_buy[
                "signal_date"
            ]
        )
    else:
        pending_buy_status = ""

    if trial is not None:
        trial_status = (
            trial[
                "signal_date"
            ]
        )
    else:
        trial_status = ""

    result_rows.append({
        "date": date,
        "all_a_close": close_today,
        "ret5_pct": (
            None
            if pd.isna(
                inc.at[
                    i,
                    "ret5_pct"
                ]
            )
            else float(
                inc.at[
                    i,
                    "ret5_pct"
                ]
            )
        ),
        "dd20_pct": (
            None
            if pd.isna(
                inc.at[
                    i,
                    "dd20_pct"
                ]
            )
            else float(
                inc.at[
                    i,
                    "dd20_pct"
                ]
            )
        ),
        "rv60_p756": (
            None
            if pd.isna(
                inc.at[
                    i,
                    "rv60_p756"
                ]
            )
            else float(
                inc.at[
                    i,
                    "rv60_p756"
                ]
            )
        ),
        "top9_signal": top9_today,
        "bottom9_signal": bottom9_today,
        "bottom5_signal": (
            bottom5_today is not None
        ),
        "position_after_close": float(
            current_position
        ),
        "core_long": bool(
            core_long
        ),
        "pending_sell_from": (
            pending_sell_status
        ),
        "pending_buy_from": (
            pending_buy_status
        ),
        "trial_from": (
            trial_status
        ),
        "risk_state": risk_state,
        "action_today": action_today,
        "next_day_scheduled_target": (
            None
            if scheduled_action is None
            else float(
                scheduled_action[
                    "target"
                ]
            )
        ),
        "next_day_scheduled_reason": (
            ""
            if scheduled_action is None
            else scheduled_action[
                "reason"
            ]
        ),
    })


result = pd.DataFrame(
    result_rows
)


# ============================================================
# 8. 当前已知增量结果的安全复核
#
# 当前正式网页已经记录：
# 8/5 Top-9
# 8/19 首次满足5日收益转弱
# 8/20 维持0%
# ============================================================

top_confirm_events = [
    x
    for x in events
    if x[
        "event"
    ] == "TOP9_SELL_CONFIRMED"
]

print()
print(
    "========== 8月增量执行复核 =========="
)

if top_confirm_events:
    first_confirm = (
        top_confirm_events[
            0
        ][
            "date"
        ]
    )

    print(
        "8/5 Top-9后的首次价格转弱确认:",
        first_confirm
    )
else:
    first_confirm = None

    print(
        "8/5 Top-9后的首次价格转弱确认: 未出现"
    )


expected_confirm = (
    "2026-08-19"
)

if (
    "2026-08-19"
    in result["date"].values
    and
    first_confirm
    != expected_confirm
):
    print(
        "FAIL：与当前生产网页记录的8/19确认不一致。"
    )
    sys.exit(8)


row_820 = result[
    result["date"]
    == "2026-08-20"
]

if not row_820.empty:
    p820 = float(
        row_820.iloc[
            0
        ][
            "position_after_close"
        ]
    )

    print(
        "2026-08-20 收盘仓位:",
        f"{p820 * 100:.0f}%"
    )

    if abs(
        p820 -
        0.0
    ) > 1e-12:
        print(
            "FAIL：8/20仓位不是生产版记录的0%。"
        )
        sys.exit(9)


print(
    "增量执行复核: PASS"
)


# ============================================================
# 9. 输出文件
# ============================================================

result.to_csv(
    OUTPUT_CSV,
    index=False,
    encoding="utf-8-sig"
)


latest_row = result.iloc[
    -1
]


output = {
    "model": (
        "current_production_execution"
    ),
    "freeze_date": (
        FREEZE_DATE
    ),
    "freeze_position": (
        freeze_position
    ),
    "historical_execution_anchor": {
        "historical_changes": len(
            historical_changes
        ),
        "expected_changes": 55,
        "max_nav_inference_error": (
            max_fit_error
        ),
        "pass": True,
    },
    "incremental_validation": {
        "top9_signal_date": (
            "2026-08-05"
            if "2026-08-05"
            in top9_map
            else None
        ),
        "sell_confirmation_date": (
            first_confirm
        ),
        "pass": True,
    },
    "latest": {
        "date": latest_row[
            "date"
        ],
        "position": float(
            latest_row[
                "position_after_close"
            ]
        ),
        "core_long": bool(
            latest_row[
                "core_long"
            ]
        ),
        "pending_sell_from": (
            latest_row[
                "pending_sell_from"
            ]
            or None
        ),
        "pending_buy_from": (
            latest_row[
                "pending_buy_from"
            ]
            or None
        ),
        "trial_from": (
            latest_row[
                "trial_from"
            ]
            or None
        ),
        "risk_state": (
            latest_row[
                "risk_state"
            ]
        ),
        "next_day_scheduled_target": (
            None
            if pd.isna(
                latest_row[
                    "next_day_scheduled_target"
                ]
            )
            else float(
                latest_row[
                    "next_day_scheduled_target"
                ]
            )
        ),
        "next_day_scheduled_reason": (
            latest_row[
                "next_day_scheduled_reason"
            ]
            or None
        ),
    },
    "events": events,
    "daily": [
        {
            key: (
                None
                if pd.isna(value)
                else (
                    bool(value)
                    if isinstance(value, (bool, np.bool_))
                    else (
                        float(value)
                        if isinstance(value, (float, np.floating))
                        else (
                            int(value)
                            if isinstance(value, (int, np.integer))
                            else value
                        )
                    )
                )
            )
            for key, value in row.items()
        }
        for row in result.to_dict(
            orient="records"
        )
    ],
}


with open(
    OUTPUT_JSON,
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        output,
        f,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
        default=str
    )


# ============================================================
# 10. CMD摘要
# ============================================================

latest_position = float(
    latest_row[
        "position_after_close"
    ]
)

summary_lines = [
    "A股拐点系统｜当前正式执行层",
    (
        f"计算区间: "
        f"{START_DATE} ~ "
        f"{latest_row['date']}"
    ),
    "",
    (
        f"{FREEZE_DATE}冻结仓位: "
        f"{freeze_position * 100:.0f}%"
    ),
    (
        f"历史生产调仓锚点: "
        f"{len(historical_changes)}/55 PASS"
    ),
    "",
]

for event in events:
    if event[
        "date"
    ] >= START_DATE:
        summary_lines.append(
            f"{event['date']} | "
            f"{event['event']} | "
            f"{event['detail']}"
        )


summary_lines.extend([
    "",
    (
        f"最新交易日: "
        f"{latest_row['date']}"
    ),
    (
        f"当前收盘仓位: "
        f"{latest_position * 100:.0f}%"
    ),
    (
        f"核心多头有效: "
        f"{bool(latest_row['core_long'])}"
    ),
    (
        f"顶部待确认: "
        f"{latest_row['pending_sell_from'] or '无'}"
    ),
    (
        f"底部待确认: "
        f"{latest_row['pending_buy_from'] or '无'}"
    ),
    (
        f"40%试仓: "
        f"{latest_row['trial_from'] or '无'}"
    ),
    (
        f"风险状态: "
        f"{latest_row['risk_state']}"
    ),
])

if pd.notna(
    latest_row[
        "next_day_scheduled_target"
    ]
):
    summary_lines.append(
        (
            "下一交易日已排定目标: "
            f"{float(latest_row['next_day_scheduled_target']) * 100:.0f}%"
            f"；"
            f"{latest_row['next_day_scheduled_reason']}"
        )
    )
else:
    summary_lines.append(
        "下一交易日已排定目标: 无"
    )


with open(
    OUTPUT_TXT,
    "w",
    encoding="utf-8"
) as f:
    f.write(
        "\n".join(
            summary_lines
        )
    )


print()
print(
    "========== 当前正式仓位结果 =========="
)

print(
    "\n".join(
        summary_lines
    )
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
