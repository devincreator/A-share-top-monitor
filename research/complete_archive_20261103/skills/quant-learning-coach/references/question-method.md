# Question Method

Use questions to make the learner reason before receiving the explanation. Keep questions answerable, concrete, and connected to a decision a quant researcher must make.

## Question Types

## Phenomenon Question

Use to create curiosity.

Examples:
- Why might CSI 500 outperform CSI 300 in one regime but underperform sharply in another?
- Why can a low-volatility portfolio still suffer a large drawdown?
- Why might an ETF momentum strategy look strong before costs but weak after costs?

## Prediction Question

Use before explanation or code.

Examples:
- If we delay the signal by one trading day, do you expect performance to improve or worsen?
- If turnover doubles, what happens to net return after stamp duty, commission, and slippage?
- If the market is range-bound, which is more likely to work: trend following or mean reversion?

## Counterexample Question

Use to prevent shallow understanding.

Examples:
- What market environment would break this strategy?
- What data error would make this backtest look better than reality?
- What assumption is most fragile here?

## Data Question

Use to connect ideas to research design.

Examples:
- What is the minimum data needed to test this idea?
- Which timestamp matters: signal date, close date, or trade execution date?
- Which benchmark makes the comparison fair?

## Code Question

Use when turning an idea into an implementation.

Examples:
- What should this function take as input and return as output?
- Where do we need `shift(1)` to avoid future information?
- Which result should be a Series, DataFrame, scalar, or chart?

## Feedback Rules

- If the learner answers correctly, add one nuance rather than repeating the answer.
- If the learner is wrong, identify the exact broken assumption and give a small counterexample.
- If the learner is unsure, offer two options and ask them to choose before explaining.
- End with one active-recall prompt: "用你自己的话解释..." or "如果明天重做这个实验，你第一步会检查什么?"
