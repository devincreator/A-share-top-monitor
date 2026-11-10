# P1c 四个慢变量的等权分数能否在 −6..0 达到峰值

**Decision: `BLOCKED_NO_WINDOW_PEAK`.** BLOCKED. The pre-registered slow-feature score does not clear the window-peak gate on a majority of tasks (0 of 4 pass; the rule requires 3). Peaks: 5_TOP mean +1 / tail +1, 5_BOTTOM mean +1 / tail +1, 9_TOP mean +1 / tail +1, 9_BOTTOM mean +1 / tail +1. The pre-pivot movement of the four slow features does not survive combination into this decision score. Inside-window medians and causal tail rates are strictly above ordinary days on all four tasks. Baseline comparison, reported and not optimized: 5_TOP 17.8%/21.1% versus baseline 23.6%/44.7%; 5_BOTTOM 30.0%/38.5% versus baseline 33.9%/51.3%; 9_TOP 12.8%/27.8% versus baseline 15.2%/38.9%; 9_BOTTOM 16.7%/42.1% versus baseline 15.7%/42.1%. Dual-80 is not claimed. The two fast features stay out of the score. P1 remains BLOCKED_NO_CONCENTRATION. P1b remains GO_PRE_PIVOT_COORDINATE. formal_signal_allowed stays false. This is not PIT, not a blind test, and not a signal.

**结论：`BLOCKED_NO_WINDOW_PEAK`。** 阻断。预注册的慢变量分数没有在多数任务上通过窗口峰值门槛（0 / 4 通过，规则要求 3 个）。峰值：5_TOP 平均 +1，尾部 +1；5_BOTTOM 平均 +1，尾部 +1；9_TOP 平均 +1，尾部 +1；9_BOTTOM 平均 +1，尾部 +1。四个慢变量在拐点前的移动，合成决策分数之后没有保住可命中窗口里的峰值。四项任务的窗口内中位数和因果尾部比例都严格高于普通日。与冻结基线的精确率/覆盖率对照（只报告）：5_TOP 17.8%/21.1%，基线 23.6%/44.7%；5_BOTTOM 30.0%/38.5%，基线 33.9%/51.3%；9_TOP 12.8%/27.8%，基线 15.2%/38.9%；9_BOTTOM 16.7%/42.1%，基线 15.7%/42.1%。不声称双80。两个快变量不进入这个分数。P1 仍是 BLOCKED_NO_CONCENTRATION。P1b 仍是 GO_PRE_PIVOT_COORDINATE。formal_signal_allowed 仍为 false。这不是 PIT，不是盲测，也不是信号。

这是一项预注册实验。`formal_signal_allowed` 仍为 false。没有 PIT 认证，没有盲测，没有生产信号。P1 的 `BLOCKED_NO_CONCENTRATION` 与 P1b 的 `GO_PRE_PIVOT_COORDINATE` 不改写。

## 冻结的分数

标签 close，指数 000985.CSI，决策时钟为 D 日开盘前。分数只用 P1b 存在检验在四个任务上都通过的四个慢变量：20日收益、距20日高点、距20日低点、63日区间位置。3日收益和3日收益变化不进入这个分数。

每个特征减去严格更早的扩展均值，再除以严格更早的样本标准差（ddof=1，至少 126 行，当天不进入）。顶部四个符号都是 +1，底部四个符号都是 −1，符号来自 P1b 计划里事先写好的经济方向。四项权重都是 1，没有截距，没有截断，没有系数搜索。5% 顶部和 9% 顶部共用同一条分数，两条底部共用它的相反数；任务之间的差别在目标、成熟前沿和可评分日。

发报规则与冻结基线相同：过去 252 个已发分数的线性 90 分位，至少 126 个历史分数，当天不参与阈值，向上越过时发报，锁定到 D+6，之后只有分数低于当天自身阈值才重新武装。分位没有搜索。

## 门槛

一个任务同时满足三条才算通过：在 −13..+6 且样本不少于 10 的偏移里，平均分数的全部并列峰值都落在 −6..0；因果尾部比例同样如此；窗口内分数中位数和尾部比例都严格高于普通日。四项里至少三项通过，结论才是 `GO_WINDOW_PEAK`。精确率和覆盖率只与 close × price × past_rank90 对照，不参与选择。

## 领先剖面

偏移 0 是拐点当天，最后输入是前一日收盘。偏移 +1 的最后输入才是拐点收盘，这一天的警报打不中该拐点。下表是峰值附近。完整的 −13..+6 在 `lead_profile.csv`。

| 任务 | 偏移 | 样本 | 慢变量平均分数 | 慢变量尾部 | 冻结六特征平均分数 | 冻结六特征尾部 | 在命中窗 |
|---|---:|---:|---:|---:|---:|---:|---|
| 5_TOP | -2 | 38 | 1.988 | 28.9% | 0.170 | 26.3% | 是 |
| 5_TOP | -1 | 38 | 2.526 | 34.2% | 0.181 | 34.2% | 是 |
| 5_TOP | +0 | 38 | 2.810 | 34.2% | 0.184 | 39.5% | 是 |
| 5_TOP | +1 | 38 | 3.394 | 42.1% | 0.197 | 57.9% | 否 |
| 5_TOP | +2 | 38 | 2.240 | 26.3% | 0.160 | 13.2% | 否 |
| 5_BOTTOM | -2 | 38 | 2.978 | 31.6% | 0.242 | 31.6% | 是 |
| 5_BOTTOM | -1 | 38 | 3.366 | 34.2% | 0.254 | 28.9% | 是 |
| 5_BOTTOM | +0 | 38 | 4.055 | 39.5% | 0.295 | 44.7% | 是 |
| 5_BOTTOM | +1 | 38 | 5.165 | 63.2% | 0.362 | 63.2% | 否 |
| 5_BOTTOM | +2 | 38 | 3.598 | 31.6% | 0.255 | 39.5% | 否 |
| 9_TOP | -2 | 16 | 2.648 | 43.8% | 0.084 | 25.0% | 是 |
| 9_TOP | -1 | 16 | 3.339 | 43.8% | 0.091 | 31.2% | 是 |
| 9_TOP | +0 | 16 | 3.639 | 50.0% | 0.095 | 43.8% | 是 |
| 9_TOP | +1 | 16 | 4.161 | 56.2% | 0.101 | 75.0% | 否 |
| 9_TOP | +2 | 16 | 3.009 | 37.5% | 0.085 | 18.8% | 否 |
| 9_BOTTOM | -2 | 15 | 3.952 | 46.7% | 0.189 | 40.0% | 是 |
| 9_BOTTOM | -1 | 15 | 4.141 | 46.7% | 0.186 | 33.3% | 是 |
| 9_BOTTOM | +0 | 15 | 4.926 | 46.7% | 0.221 | 53.3% | 是 |
| 9_BOTTOM | +1 | 15 | 5.839 | 73.3% | 0.275 | 73.3% | 否 |
| 9_BOTTOM | +2 | 15 | 3.958 | 40.0% | 0.163 | 40.0% | 否 |

| 任务 | 平均分数峰值 | 尾部峰值 | 窗口内中位数 | 普通日中位数 | 窗口内尾部 | 普通日尾部 | +1 减窗口内最高平均 | +1 减窗口内最高尾部 | 通过 |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| 5_TOP | +1 | +1 | 1.941 | -1.341 | 26.7% | 8.5% | 0.583 | 0.079 | FAIL |
| 5_BOTTOM | +1 | +1 | 3.213 | -0.633 | 24.0% | 6.0% | 1.111 | 0.237 | FAIL |
| 9_TOP | +1 | +1 | 2.462 | -1.160 | 38.4% | 8.3% | 0.521 | 0.062 | FAIL |
| 9_BOTTOM | +1 | +1 | 4.132 | -0.037 | 32.1% | 9.0% | 0.913 | 0.267 | FAIL |

四项任务的窗口内中位数和尾部比例都高于普通日。没有通过的是峰值位置：5_TOP 平均 +1、尾部 +1；5_BOTTOM 平均 +1、尾部 +1；9_TOP 平均 +1、尾部 +1；9_BOTTOM 平均 +1、尾部 +1。早肩和晚肩只列在下表，不进入门槛。

图：`fig_lead_profile.png` 是 −13..+6 的平均分数和尾部比例，绿带是可命中窗口，橙线是偏移 +1。`fig_region_tail.png` 比较窗口、两肩和普通日的尾部比例。

## 区域

| 任务 | 区域 | 天数 | 分数中位数 | 尾部比例 |
|---|---|---:|---:|---:|
| 5_TOP | 窗口内 | 266 | 1.941 | 26.7% |
| 5_TOP | 早肩 | 259 | 1.030 | 19.3% |
| 5_TOP | 晚肩 | 216 | 1.533 | 20.4% |
| 5_TOP | 普通日 | 1655 | -1.341 | 8.5% |
| 5_BOTTOM | 窗口内 | 267 | 3.213 | 24.0% |
| 5_BOTTOM | 早肩 | 273 | 1.112 | 12.8% |
| 5_BOTTOM | 晚肩 | 209 | 3.056 | 22.5% |
| 5_BOTTOM | 普通日 | 1647 | -0.633 | 6.0% |
| 9_TOP | 窗口内 | 112 | 2.462 | 38.4% |
| 9_TOP | 早肩 | 112 | 2.324 | 28.6% |
| 9_TOP | 晚肩 | 96 | 2.166 | 24.0% |
| 9_TOP | 普通日 | 1737 | -1.160 | 8.3% |
| 9_BOTTOM | 窗口内 | 106 | 4.132 | 32.1% |
| 9_BOTTOM | 早肩 | 112 | 1.719 | 11.6% |
| 9_BOTTOM | 晚肩 | 87 | 3.471 | 28.7% |
| 9_BOTTOM | 普通日 | 1752 | -0.037 | 9.0% |

## 与冻结基线对照

下表是同一成熟队列、同一对一匹配、同一 past_rank90 规则下的计数。双80必要警报区间只说明警报数和目标数的算术关系，没有用来配额。

| 任务 | 分数 | 目标 | 警报 | TP | FP | FN | 精确率 | 覆盖率 | PENDING | 双80警报区间 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5_TOP | 四慢变量等权 | 38 | 45 | 8 | 37 | 30 | 17.8% | 21.1% | 3 | 31–47 |
| 5_TOP | 冻结六特征 | 38 | 72 | 17 | 55 | 21 | 23.6% | 44.7% | 2 | 31–47 |
| 5_BOTTOM | 四慢变量等权 | 39 | 50 | 15 | 35 | 24 | 30.0% | 38.5% | 5 | 32–48 |
| 5_BOTTOM | 冻结六特征 | 39 | 59 | 20 | 39 | 19 | 33.9% | 51.3% | 9 | 32–48 |
| 9_TOP | 四慢变量等权 | 18 | 39 | 5 | 34 | 13 | 12.8% | 27.8% | 9 | 15–22 |
| 9_TOP | 冻结六特征 | 18 | 46 | 7 | 39 | 11 | 15.2% | 38.9% | 9 | 15–22 |
| 9_BOTTOM | 四慢变量等权 | 19 | 48 | 8 | 40 | 11 | 16.7% | 42.1% | 7 | 16–23 |
| 9_BOTTOM | 冻结六特征 | 19 | 51 | 8 | 43 | 11 | 15.7% | 42.1% | 11 | 16–23 |

| 任务 | 有可评分窗口日且至少一天进入因果尾部的目标 | 目标数 |
|---|---:|---:|
| 5_TOP | 16 | 38 |
| 5_BOTTOM | 17 | 39 |
| 9_TOP | 10 | 18 |
| 9_BOTTOM | 9 | 19 |

## 逐项判定

| 任务 | 检验 | 结果 | 实际值 | 预注册要求 |
|---|---|---|---|---|
| 5_TOP | n_inside | PASS | 266 | >= 30 |
| 5_TOP | n_ordinary | PASS | 1655 | >= 100 |
| 5_TOP | n_targets | PASS | 38 | >= 10 |
| 5_TOP | offsets_n_at_least_10 | PASS | 38 | minimum n across offsets -13..+6 >= 10 |
| 5_TOP | mean_score_peak_inside_window | FAIL | +1 | all tied argmax offsets in -6..0 |
| 5_TOP | tail_rate_peak_inside_window | FAIL | +1 | all tied argmax offsets in -6..0 |
| 5_TOP | median_inside_gt_ordinary | PASS | 1.94147 | > ordinary median -1.34147 |
| 5_TOP | tail_inside_gt_ordinary | PASS | 0.266917 | > ordinary tail rate 0.0845921 |
| 5_BOTTOM | n_inside | PASS | 267 | >= 30 |
| 5_BOTTOM | n_ordinary | PASS | 1647 | >= 100 |
| 5_BOTTOM | n_targets | PASS | 39 | >= 10 |
| 5_BOTTOM | offsets_n_at_least_10 | PASS | 38 | minimum n across offsets -13..+6 >= 10 |
| 5_BOTTOM | mean_score_peak_inside_window | FAIL | +1 | all tied argmax offsets in -6..0 |
| 5_BOTTOM | tail_rate_peak_inside_window | FAIL | +1 | all tied argmax offsets in -6..0 |
| 5_BOTTOM | median_inside_gt_ordinary | PASS | 3.21322 | > ordinary median -0.632705 |
| 5_BOTTOM | tail_inside_gt_ordinary | PASS | 0.2397 | > ordinary tail rate 0.0601093 |
| 9_TOP | n_inside | PASS | 112 | >= 30 |
| 9_TOP | n_ordinary | PASS | 1737 | >= 100 |
| 9_TOP | n_targets | PASS | 18 | >= 10 |
| 9_TOP | offsets_n_at_least_10 | PASS | 16 | minimum n across offsets -13..+6 >= 10 |
| 9_TOP | mean_score_peak_inside_window | FAIL | +1 | all tied argmax offsets in -6..0 |
| 9_TOP | tail_rate_peak_inside_window | FAIL | +1 | all tied argmax offsets in -6..0 |
| 9_TOP | median_inside_gt_ordinary | PASS | 2.46219 | > ordinary median -1.15968 |
| 9_TOP | tail_inside_gt_ordinary | PASS | 0.383929 | > ordinary tail rate 0.0834773 |
| 9_BOTTOM | n_inside | PASS | 106 | >= 30 |
| 9_BOTTOM | n_ordinary | PASS | 1752 | >= 100 |
| 9_BOTTOM | n_targets | PASS | 19 | >= 10 |
| 9_BOTTOM | offsets_n_at_least_10 | PASS | 15 | minimum n across offsets -13..+6 >= 10 |
| 9_BOTTOM | mean_score_peak_inside_window | FAIL | +1 | all tied argmax offsets in -6..0 |
| 9_BOTTOM | tail_rate_peak_inside_window | FAIL | +1 | all tied argmax offsets in -6..0 |
| 9_BOTTOM | median_inside_gt_ordinary | PASS | 4.13218 | > ordinary median -0.0373537 |
| 9_BOTTOM | tail_inside_gt_ordinary | PASS | 0.320755 | > ordinary tail rate 0.0896119 |

## 边界

- 决策日重叠，分数自相关。门槛是描述规则。
- 拐点是事后确认的收盘标签。这是研究诊断，不是可交易信号。
- 历史被反复看过。历史公布时点与指数成分仍未完成全时期 PIT 认证。
- 标准化只用当天之前的特征行。偏移 0 的最后输入是拐点前一日。
- 没有重训六个价格特征的逻辑回归，没有打开 P2，没有提高冻结分数的阈值。
- 没有把 D 日收盘写进当日特征，没有更换标签或指数。
- 没有修改生产页面、采集器、正式信号，也没有恢复旧 V 系列。

## 复算

```text
python -B dual80-research/p1c_slow_feature_score/diagnose.py
```

缺少 `plan.json` 时测量会停止。`--write-plan-only` 只在文件不存在时写出计划，不读特征数值。
