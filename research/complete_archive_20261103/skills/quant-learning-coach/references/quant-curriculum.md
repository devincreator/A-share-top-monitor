# Quant Curriculum

Choose the next topic from the earliest unfinished stage unless the user asks for a specific topic.

## Stage 0: Tools and Core Metrics

Goal: turn basic programming syntax into quant research ability.

Topics:
- Python functions and reusable metric code.
- pandas time series, returns, rolling windows, resampling.
- Simple return, log return, cumulative net value.
- Annualized return, volatility, Sharpe ratio.
- Maximum drawdown and drawdown curve.

Preferred cases:
- CSI 300 ETF net value curve.
- CSI 500 ETF drawdown comparison.
- Broad-index ETF return table.

## Stage 1: Statistics for Quant Research

Goal: understand uncertainty and avoid false confidence.

Topics:
- Mean, variance, covariance, correlation.
- Sampling error, confidence intervals, hypothesis tests.
- Regression, residuals, t-statistics, R-squared.
- Autocorrelation, stationarity, heteroskedasticity.
- Multiple testing and data mining bias.

Preferred cases:
- Factor IC and Rank IC.
- Momentum window comparison.
- Regression of ETF returns on benchmark returns.

## Stage 2: Classic Strategy Frameworks

Goal: understand what a strategy is trying to earn.

Topics:
- Trend following and moving averages.
- Momentum and ETF rotation.
- Mean reversion and z-score signals.
- Value, quality, momentum, low-vol, and size factors.
- Event and index rebalancing ideas.

Preferred cases:
- CSI 300/CSI 500/ChiNext ETF rotation.
- Industry ETF momentum.
- A-share factor grouping.

## Stage 3: Backtesting and Research Engineering

Goal: build believable research workflows.

Topics:
- Signal timing and avoiding lookahead.
- Transaction costs and slippage.
- T+1, suspensions, limit-up/limit-down.
- Benchmark selection.
- In-sample, out-of-sample, rolling validation.
- Parameter sensitivity.
- Research notes and experiment logs.

Preferred cases:
- Moving-average timing with next-day execution.
- Monthly ETF rotation with turnover.
- Cost sensitivity for high-turnover factors.

## Stage 4: Machine Learning for Trading

Goal: use ML as a disciplined prediction tool, not a black box.

Topics:
- Feature engineering with lagged and rolling features.
- Label construction from future returns.
- Time-series train/validation/test split.
- Leakage control.
- Linear models, tree models, random forest, gradient boosting.
- Classification, regression, and ranking.
- Feature importance and stability.

Preferred cases:
- Predict next-month ETF relative return.
- Rank A-share stocks by factor features.
- Compare model score with simple factor baseline.

## Stage 5: Portfolio and Risk

Goal: convert signals into controlled portfolios.

Topics:
- Position sizing and volatility targeting.
- Risk budgeting.
- Active risk, tracking error, information ratio.
- Exposure constraints.
- Drawdown control.
- Stress scenarios and capacity.

Preferred cases:
- Equal-weight ETF portfolio versus momentum rotation.
- Dividend/low-vol portfolio risk.
- Active portfolio versus CSI 300 or CSI 500 benchmark.
