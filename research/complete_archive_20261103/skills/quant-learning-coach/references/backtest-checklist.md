# Backtest Checklist

Use this checklist for strategy, factor, portfolio, and machine learning sessions. Keep it educational and proportionate to the user's available time.

## Minimum Research Definition

Before testing, define:
- Universe.
- Data frequency.
- Signal.
- Portfolio rule.
- Execution timing.
- Costs.
- Benchmark.
- Evaluation period.

## Lookahead and Data Integrity

Check:
- Signal uses only data available before the trade.
- `shift(1)` or equivalent delay is used when needed.
- Financial statement and index constituent data respect release dates.
- Delisted and suspended securities are handled intentionally.
- Adjusted prices and dividends are treated consistently.

## China Market Frictions

Check when relevant:
- T+1 selling constraint.
- Limit-up/limit-down tradability.
- Suspensions.
- Stock stamp duty on sell trades.
- Commission and minimum fee assumptions.
- ETF fees, spreads, and slippage.
- Liquidity and capacity for small-cap names.

## Evaluation

Report at least:
- Annualized return.
- Annualized volatility.
- Sharpe ratio or information ratio.
- Maximum drawdown.
- Turnover.
- Win/loss by period or regime when useful.
- Benchmark-relative performance.

## Robustness

Ask:
- Does the result survive reasonable transaction costs?
- Does it depend on one parameter?
- Does it depend on one short market period?
- Does it work out of sample?
- What regime would make it fail?
- Is the strategy earning a plausible risk premium or exploiting a behavioral/structural effect?

## Machine Learning Additions

Check:
- Features are lagged and available at prediction time.
- Train/validation/test split follows time order.
- Labels are defined clearly.
- Cross-validation does not leak future data.
- Model is compared with a simple baseline.
- Performance is measured after portfolio construction and costs, not just prediction accuracy.
