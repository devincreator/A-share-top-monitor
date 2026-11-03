"""Volume + RSI + Bollinger Band strategy.

CSV requirements:
    date, open, high, low, close, volume

Signal logic:
    Buy when:
        - RSI(10) is between 40 and 60
        - volume is at least 2% above the prior 20-day average volume
        - intraday low touches or breaks the lower Bollinger Band
    Sell/exit when:
        - RSI(10) is between 40 and 60
        - volume is at least 2% above the prior 20-day average volume
        - intraday high touches or breaks the upper Bollinger Band

Signals are generated after the bar is complete and are executed at the next
bar's open in the simple long-only backtest.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {"date", "open", "high", "low", "close", "volume"}
COLUMN_ORDER = ["date", "open", "high", "low", "close", "volume"]


@dataclass(frozen=True)
class StrategyConfig:
    rsi_period: int = 10
    rsi_lower: float = 40.0
    rsi_upper: float = 60.0
    boll_window: int = 20
    boll_std: float = 2.0
    volume_window: int = 20
    volume_boost: float = 0.02
    volume_baseline: str = "ma"
    fee_bps: float = 3.0
    slippage_bps: float = 2.0
    initial_cash: float = 100_000.0


def load_ohlcv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [column.strip().lower() for column in df.columns]

    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"CSV missing required columns: {missing_text}")

    df = df[COLUMN_ORDER].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates("date", keep="last")

    numeric_columns = ["open", "high", "low", "close", "volume"]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(subset=numeric_columns).reset_index(drop=True)
    return df


def calculate_rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def add_indicators(df: pd.DataFrame, config: StrategyConfig) -> pd.DataFrame:
    result = df.copy()
    close = result["close"]

    result[f"rsi_{config.rsi_period}"] = calculate_rsi(close, config.rsi_period)

    rolling_close = close.rolling(config.boll_window, min_periods=config.boll_window)
    result["boll_mid"] = rolling_close.mean()
    boll_std = rolling_close.std(ddof=0)
    result["boll_upper"] = result["boll_mid"] + config.boll_std * boll_std
    result["boll_lower"] = result["boll_mid"] - config.boll_std * boll_std

    # Compare today's volume against the prior rolling average to avoid
    # diluting the threshold with today's volume.
    prior_volume_ma = (
        result["volume"]
        .rolling(config.volume_window, min_periods=config.volume_window)
        .mean()
        .shift(1)
    )
    result["volume_ma"] = prior_volume_ma

    if config.volume_baseline == "ma":
        volume_reference = prior_volume_ma
    elif config.volume_baseline == "previous":
        volume_reference = result["volume"].shift(1)
    else:
        raise ValueError("volume_baseline must be 'ma' or 'previous'")

    result["volume_reference"] = volume_reference
    result["volume_ratio"] = result["volume"] / volume_reference
    return result


def generate_signals(df: pd.DataFrame, config: StrategyConfig) -> pd.DataFrame:
    result = add_indicators(df, config)
    rsi_column = f"rsi_{config.rsi_period}"

    neutral_rsi = result[rsi_column].between(
        config.rsi_lower,
        config.rsi_upper,
        inclusive="both",
    )
    volume_confirmed = result["volume_ratio"] >= 1.0 + config.volume_boost
    touch_lower = result["low"] <= result["boll_lower"]
    touch_upper = result["high"] >= result["boll_upper"]

    buy_condition = neutral_rsi & volume_confirmed & touch_lower
    sell_condition = neutral_rsi & volume_confirmed & touch_upper
    conflict = buy_condition & sell_condition

    result["buy_signal"] = buy_condition & ~conflict
    result["sell_signal"] = sell_condition & ~conflict
    result["signal"] = np.select(
        [result["buy_signal"], result["sell_signal"]],
        [1, -1],
        default=0,
    )

    return result


def build_target_position(signal: pd.Series) -> pd.Series:
    position = []
    current_position = 0

    for value in signal:
        if value == 1:
            current_position = 1
        elif value == -1:
            current_position = 0
        position.append(current_position)

    return pd.Series(position, index=signal.index, dtype=float)


def backtest_long_only(signals: pd.DataFrame, config: StrategyConfig) -> pd.DataFrame:
    result = signals.copy()

    target_after_signal = build_target_position(result["signal"])
    result["position"] = target_after_signal.shift(1).fillna(0.0)
    result["trade"] = result["position"].diff().fillna(result["position"])

    gross_next_open_return = result["open"].shift(-1) / result["open"] - 1.0
    one_way_cost = (config.fee_bps + config.slippage_bps) / 10_000.0
    trade_cost = result["trade"].abs() * one_way_cost

    result["strategy_return"] = result["position"] * gross_next_open_return - trade_cost
    result["strategy_return"] = result["strategy_return"].fillna(0.0)
    result["equity"] = config.initial_cash * (1.0 + result["strategy_return"]).cumprod()
    result["benchmark_equity"] = (
        config.initial_cash
        * (1.0 + gross_next_open_return.fillna(0.0)).cumprod()
    )
    return result


def summarize_backtest(backtest: pd.DataFrame) -> dict[str, float]:
    daily_return = backtest["strategy_return"]
    equity = backtest["equity"]
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0

    years = max(len(backtest) / 252.0, 1 / 252.0)
    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    annual_return = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1.0
    annual_vol = daily_return.std(ddof=0) * np.sqrt(252.0)
    sharpe = annual_return / annual_vol if annual_vol else np.nan

    return {
        "total_return": total_return,
        "annual_return": annual_return,
        "annual_vol": annual_vol,
        "sharpe_like": sharpe,
        "max_drawdown": drawdown.min(),
        "trade_count": float(backtest["trade"].abs().sum()),
        "buy_signals": float(backtest["buy_signal"].sum()),
        "sell_signals": float(backtest["sell_signal"].sum()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a volume + RSI + Bollinger Band long-only strategy.",
    )
    parser.add_argument("--csv", required=True, type=Path, help="Input OHLCV CSV path.")
    parser.add_argument("--out", type=Path, help="Optional output CSV path.")
    parser.add_argument("--rsi-period", type=int, default=10)
    parser.add_argument("--rsi-lower", type=float, default=40.0)
    parser.add_argument("--rsi-upper", type=float, default=60.0)
    parser.add_argument("--boll-window", type=int, default=20)
    parser.add_argument("--boll-std", type=float, default=2.0)
    parser.add_argument("--volume-window", type=int, default=20)
    parser.add_argument(
        "--volume-boost",
        type=float,
        default=0.02,
        help="2%% volume boost should be passed as 0.02.",
    )
    parser.add_argument(
        "--volume-baseline",
        choices=["ma", "previous"],
        default="ma",
        help="Use 'ma' for prior rolling average volume, or 'previous' for prior bar volume.",
    )
    parser.add_argument("--fee-bps", type=float, default=3.0)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = StrategyConfig(
        rsi_period=args.rsi_period,
        rsi_lower=args.rsi_lower,
        rsi_upper=args.rsi_upper,
        boll_window=args.boll_window,
        boll_std=args.boll_std,
        volume_window=args.volume_window,
        volume_boost=args.volume_boost,
        volume_baseline=args.volume_baseline,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
        initial_cash=args.initial_cash,
    )

    df = load_ohlcv(args.csv)
    signals = generate_signals(df, config)
    backtest = backtest_long_only(signals, config)
    summary = summarize_backtest(backtest)

    print("Backtest summary")
    for key, value in summary.items():
        print(f"{key}: {value:.4f}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        backtest.to_csv(args.out, index=False)
        print(f"Saved result CSV to: {args.out}")


if __name__ == "__main__":
    main()
