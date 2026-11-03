# 参考资料索引

这个文件记录当前量化学习模式可随时调用的参考书。后续你可以直接说“结合参考书讲一下均值回归”或“用 APM 的框架解释主动风险”，我会按下面的分区来组织回答。

## 01 机器学习量化

文件：

- `references/01_machine_learning/Machine Learning for Algorithmic Trading.pdf`

用途：

- 机器学习在量化中的完整流程。
- 数据获取、特征工程、模型训练、时间序列验证。
- 机器学习策略研究项目。
- Python 研究工程习惯。

适合阶段：

- 阶段 3：回测和研究工程。
- 阶段 4：机器学习和另类数据。

调用方式：

```text
结合 Machine Learning for Algorithmic Trading，讲一下特征工程。
```

```text
用这本书的思路，带我做一个机器学习择时实验。
```

## 02 策略研究

文件：

- `references/02_strategy_research/Algorithmic Trading - Winning Strategies and Their Rationale.pdf`

用途：

- 经典算法交易策略。
- 策略逻辑、收益来源和适用市场。
- 均值回归、动量、套利、事件类策略的研究入口。

适合阶段：

- 阶段 2：经典策略框架。
- 阶段 3：回测和研究工程。

调用方式：

```text
参考 Algorithmic Trading，讲一下均值回归策略。
```

```text
用这本书的风格，帮我设计一个 ETF 动量回测练习。
```

## 03 组合和风险

文件：

- `references/03_portfolio_risk/Active Portfolio Management - A Quantitative Approach.pdf`

用途：

- 主动投资组合管理。
- alpha、主动风险、信息比率、组合构建。
- 风险预算、约束优化、组合评估。

适合阶段：

- 阶段 1：量化研究的统计基础。
- 阶段 5：组合、风控和实盘前检查。

调用方式：

```text
结合 Active Portfolio Management，解释信息比率和主动风险。
```

```text
用 APM 的框架，帮我理解 alpha 预测和组合构建。
```

## 使用规则

1. 你问具体概念时，我优先把概念放回交易和组合语境。
2. 你问策略时，我会同时说明收益来源、风险来源、回测设计和失效条件。
3. 你问机器学习时，我会重点检查时间序列切分、特征泄露、过拟合和交易成本。
4. 你问组合管理时，我会重点连接 alpha、风险、约束、换手和信息比率。
5. 需要精确章节或原文时，我会先查 PDF，再给你概括，不凭记忆编页码。

