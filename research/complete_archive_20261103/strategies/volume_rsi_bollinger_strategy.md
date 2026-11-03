# Volume + RSI + Bollinger Band Strategy

This is a research/backtest template, not a live trading recommendation.

## Core Rules

- Indicator set:
  - RSI period: 10
  - Bollinger Band window: 20
  - Bollinger Band width: 2 standard deviations
  - Volume baseline: prior 20-day average volume by default
- Buy signal:
  - `RSI(10)` is between `40` and `60`
  - `volume / prior_20_day_avg_volume >= 1.02`
  - intraday `low <= Bollinger lower band`
- Sell/exit signal:
  - `RSI(10)` is between `40` and `60`
  - `volume / prior_20_day_avg_volume >= 1.02`
  - intraday `high >= Bollinger upper band`
- If the same bar touches both upper and lower bands, the script ignores that bar's signal.
- Signals are generated after the bar completes and executed at the next bar's open.
- If you want "volume expands 2%" to mean "2% above yesterday's volume", run with `--volume-baseline previous`.

## Expected CSV Format

```csv
date,open,high,low,close,volume
2024-01-02,10.00,10.40,9.90,10.20,1000000
2024-01-03,10.20,10.35,10.00,10.10,1050000
```

## Run

```powershell
python .\strategies\volume_rsi_bollinger_strategy.py --csv .\data\your_ohlcv.csv --out .\output\signals.csv
```

## Parameter Examples

```powershell
python .\strategies\volume_rsi_bollinger_strategy.py `
  --csv .\data\your_ohlcv.csv `
  --out .\output\signals.csv `
  --rsi-period 10 `
  --rsi-lower 40 `
  --rsi-upper 60 `
  --boll-window 20 `
  --boll-std 2 `
  --volume-window 20 `
  --volume-boost 0.02 `
  --volume-baseline ma `
  --fee-bps 3 `
  --slippage-bps 2
```

## Research Checks

- Compare results across different markets, not just one symbol.
- Run sensitivity tests around `RSI(10)`, Bollinger window, and the 2% volume threshold.
- Track turnover, max drawdown, win/loss distribution, and performance before/after costs.
- Avoid using same-day signals for same-day execution unless the strategy is explicitly intraday.
