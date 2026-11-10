# P1b 六个价格特征在拐点收盘之前有没有移动

**Decision: `GO_PRE_PIVOT_COORDINATE`.** GO. The presence rule clears on every listed task inside offsets -6..0 for: return20_scaled, distance_to_20day_high_scaled, distance_to_20day_low_scaled, position63. On the presence-passing cells their window departure is -1.174 to +1.038 ordinary SD and the isolated pivot-close jump is -0.522 to +0.306. The window average is more than half of the offset-+1 departure, which is the presence rule. Offset +1 is still the farther level on 21 of 24 cells, so the pivot close adds a further increment; it does not create those four levels. Build passes that are not presence passes: return3_scaled on 5_TOP, 9_TOP (build +0.541 to +0.661); change_in_return3_scaled on 5_TOP, 9_TOP (build +0.393 to +0.638). return3_scaled clears presence on 1 of 4 tasks, short of the two-task rule. On 5_BOTTOM, its window departure is -0.805 and its isolated jump is -0.829. presence passes 17 of 24 cells; build passes 18 of 24. Samples: 5_TOP 38 complete of 38 eligible at offset 0, 5_BOTTOM 38 complete of 38 eligible at offset 0, 9_TOP 16 complete of 16 eligible at offset 0, 9_BOTTOM 15 complete of 15 eligible at offset 0. A later experiment may pre-register the presence-passing features, and the named build cells only as build coordinates. It may not refit the six-feature model, open Phase P2, or raise the frozen score's threshold. The P1 score peak at offset +1 remains. formal_signal_allowed stays false. This is not PIT, not a blind test, and not a signal.

**结论：`GO_PRE_PIVOT_COORDINATE`。** 放行。存在检验在列出的任务上通过，坐标在可命中窗口 −6..0 内：20日收益、距20日高点、距20日低点、63日区间位置。这些通过存在检验的格子，窗口偏离是 -1.174 to +1.038 个普通日标准差，孤立的拐点收盘跳跃是 -0.522 to +0.306。窗口均值超过偏移 +1 偏离的一半，这是存在检验的规则。偏移 +1 仍然是更远的水平，这样的格子有 21 / 24。拐点收盘在原有水平上再推进一步，不是从零造出这些坐标。只通过推移、没有通过存在检验的是：3日收益在5_TOP、9_TOP；3日收益变化在5_TOP、9_TOP。3日收益通过存在检验的任务数是 1 / 4，没有达到两个任务的规则。在 5_BOTTOM 上，它的窗口偏离是 -0.805，孤立跳跃是 -0.829。presence passes 17 of 24 cells; build passes 18 of 24。样本：5_TOP 38 complete of 38 eligible at offset 0, 5_BOTTOM 38 complete of 38 eligible at offset 0, 9_TOP 16 complete of 16 eligible at offset 0, 9_BOTTOM 15 complete of 15 eligible at offset 0。后续实验可以预注册通过存在检验的特征；只通过推移的格子只能作为推移坐标预注册。不能重训六个价格特征的模型，不能打开 P2 发报压缩，也不能提高冻结分数的阈值。P1 的分数峰值仍在偏移 +1。formal_signal_allowed 仍为 false。这不是 PIT，不是盲测，也不是信号。

这是冻结基线的特征时点审计，不是新模型，不是发报实验。`formal_signal_allowed` 仍为 false。没有 PIT 认证，没有盲测，没有生产信号。P1 的 `BLOCKED_NO_CONCENTRATION` 不改写。

## 冻结与时钟

标签 close，特征 price，指数 000985.CSI，决策时钟为 D 日开盘前。特征行用到的最后收盘是 D−1。六个特征沿用 `label_clock_v4` 已经算好的价格矩阵，公式与 `broad_experiments_v2` 的 `make_features` 价格块一致，审计开始前用逐行比对锁住。不重训，不搜索阈值，不新增因子。

| 偏移 | 决策日 | 最后输入 | 能否打中该拐点 |
|---:|---|---|---|
| −6..0 | 拐点前 6 日至拐点当天 | 拐点前 7 日至拐点前 1 日 | 能。窗口内。 |
| +1 | 拐点后第 1 日 | 拐点当天收盘 | 不能。拐点收盘第一次进入特征。 |
| +2 | 拐点后第 2 日 | 拐点后第 1 日收盘 | 不能。肩部，只报告。 |

普通日沿用 P1 的 ordinary 区域。z 是该任务普通日上的标准差单位，中心是普通日均值。检验只用完整样本：同一批拐点在 −6..+1 每天都可评分。对照“把拐点收盘换成前一日收盘”只用同一套公式，不产生分数。

## 检验

检验 P（存在）：偏移 +1 相对普通日的偏离至少 0.25 个标准差时，才有一个可解释的锚。窗口均值要与这个锚同号，绝对值至少 0.20，并且超过锚的一半；偏移 0 同号且至少 0.15；窗口均值还要超过孤立拐点收盘跳跃的一半；偏移 0 的中位数要严格落在锚的一侧；七个窗口偏移里至少四个的同号 z 达到 0.10。

检验 B（推移）：窗口后段（−2..0）减去前段（−6..−4）的绝对值至少 0.35，并且大于孤立跳跃，也大于从偏移 0 到 +1 的一步；后段本身离开普通日至少 0.20；偏移 0 的中位数落在推移方向上。

放行条件：同一特征在至少两个任务上通过检验 P，或在至少两个任务上通过检验 B，或在一个任务上两个检验都通过且窗口偏离的绝对值至少 0.50。否则，若有格子的孤立跳跃或偏移 +1 水平按预注册规则盖过窗口，结论是拐点收盘主导；都没有，则是没有边际移动。经济方向只作对照列，不参与判定。

## 结果

z 为完整样本上的普通日标准差单位。窗口是 −6..0 的平均。跳跃是把拐点收盘换成前一日收盘之后，偏移 +1 的变化。推移是窗口后段减前段。

| 任务 | 特征 | n | z(−6) | z(0) | z(+1) | z(+2) | 窗口 | 跳跃 | 推移 | 检验P | 检验B |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 5_TOP | return3_scaled | 38 | 0.435 | 0.871 | 1.110 | 0.182 | 0.546 | 0.440 | 0.541 | FAIL | PASS |
| 5_TOP | return20_scaled | 38 | 0.510 | 1.027 | 1.161 | 0.973 | 0.704 | 0.169 | 0.384 | PASS | PASS |
| 5_TOP | change_in_return3_scaled | 38 | 0.153 | 0.317 | 0.242 | -0.517 | 0.148 | 0.321 | 0.393 | FAIL | PASS |
| 5_TOP | distance_to_20day_high_scaled | 38 | 0.547 | 1.037 | 1.151 | 0.775 | 0.742 | 0.108 | 0.408 | PASS | PASS |
| 5_TOP | distance_to_20day_low_scaled | 38 | 0.663 | 1.253 | 1.551 | 1.073 | 0.887 | 0.280 | 0.486 | PASS | PASS |
| 5_TOP | position63 | 38 | 0.597 | 1.103 | 1.232 | 0.974 | 0.810 | 0.107 | 0.397 | PASS | PASS |
| 5_BOTTOM | return3_scaled | 38 | -0.429 | -1.277 | -1.695 | -0.713 | -0.805 | -0.829 | -0.379 | FAIL | FAIL |
| 5_BOTTOM | return20_scaled | 38 | -0.556 | -1.155 | -1.474 | -1.127 | -0.815 | -0.300 | -0.351 | PASS | PASS |
| 5_BOTTOM | change_in_return3_scaled | 38 | -0.073 | -0.396 | -0.549 | 0.097 | -0.194 | -0.618 | 0.024 | FAIL | FAIL |
| 5_BOTTOM | distance_to_20day_high_scaled | 38 | -0.742 | -1.776 | -2.314 | -1.564 | -1.174 | -0.522 | -0.625 | PASS | PASS |
| 5_BOTTOM | distance_to_20day_low_scaled | 38 | -0.504 | -1.143 | -1.286 | -0.878 | -0.802 | -0.149 | -0.380 | PASS | PASS |
| 5_BOTTOM | position63 | 38 | -0.427 | -1.043 | -1.357 | -1.029 | -0.708 | -0.301 | -0.371 | PASS | PASS |
| 9_TOP | return3_scaled | 16 | 0.523 | 1.192 | 1.380 | 0.331 | 0.573 | 0.472 | 0.661 | FAIL | PASS |
| 9_TOP | return20_scaled | 16 | 0.859 | 1.363 | 1.467 | 1.238 | 0.973 | 0.188 | 0.392 | PASS | PASS |
| 9_TOP | change_in_return3_scaled | 16 | 0.128 | 0.771 | 0.534 | -0.439 | 0.196 | 0.345 | 0.638 | FAIL | PASS |
| 9_TOP | distance_to_20day_high_scaled | 16 | 0.729 | 1.133 | 1.206 | 0.832 | 0.849 | 0.077 | 0.359 | PASS | PASS |
| 9_TOP | distance_to_20day_low_scaled | 16 | 0.914 | 1.398 | 1.734 | 1.308 | 1.002 | 0.306 | 0.455 | PASS | PASS |
| 9_TOP | position63 | 16 | 0.881 | 1.347 | 1.446 | 1.199 | 1.038 | 0.095 | 0.396 | PASS | PASS |
| 9_BOTTOM | return3_scaled | 15 | -0.438 | -1.238 | -1.432 | -0.469 | -0.855 | -0.698 | -0.496 | PASS | FAIL |
| 9_BOTTOM | return20_scaled | 15 | -0.581 | -1.241 | -1.453 | -1.081 | -0.862 | -0.275 | -0.333 | PASS | FAIL |
| 9_BOTTOM | change_in_return3_scaled | 15 | -0.182 | -0.273 | -0.216 | 0.238 | -0.255 | -0.526 | -0.034 | FAIL | FAIL |
| 9_BOTTOM | distance_to_20day_high_scaled | 15 | -0.749 | -1.738 | -2.199 | -1.308 | -1.173 | -0.446 | -0.658 | PASS | PASS |
| 9_BOTTOM | distance_to_20day_low_scaled | 15 | -0.481 | -1.016 | -1.131 | -0.659 | -0.733 | -0.121 | -0.309 | PASS | FAIL |
| 9_BOTTOM | position63 | 15 | -0.619 | -1.340 | -1.590 | -1.216 | -0.996 | -0.249 | -0.454 | PASS | PASS |

| 任务 | 完整样本 | 偏移0可评分拐点 | 偏移+2 | 普通日 |
|---|---:|---:|---:|---:|
| 5_TOP | 38 | 38 | 38 | 1655 |
| 5_BOTTOM | 38 | 38 | 38 | 1647 |
| 9_TOP | 16 | 16 | 16 | 1737 |
| 9_BOTTOM | 15 | 15 | 15 | 1752 |

特征名称：`return3_scaled` 3日收益，`return20_scaled` 20日收益，`change_in_return3_scaled` 3日收益变化，`distance_to_20day_high_scaled` 距20日高点（小于等于 0），`distance_to_20day_low_scaled` 距20日低点（大于等于 0），`position63` 在 63 日高低区间的位置。

图：`fig_feature_lead.png` 是六个特征在 −6..+2 的路径，绿色带是可命中窗口，橙色点是偏移 +1，空心点是扣掉拐点收盘后的偏移 +1。`fig_window_vs_plus1.png` 比较窗口、偏移 +1 和孤立跳跃。`fig_hold_last_close.png` 把偏移 0、扣掉拐点收盘的 +1、以及真实 +1 放在一起。

## 对照，不是门槛

下表的路径比例是 (z(0)−z(−6)) / (z(+1)−z(−6))。比例接近 0 表示偏移 0 还停在窗口起点；接近 1 表示走到 +1 之前，这段位移已经完成。分数相关是完整样本上，偏移 +1 的分数减去偏移 0 的分数，与特征的同一步变化或孤立跳跃的 Pearson 相关。相关不用来判定。

| 任务 | 特征 | 路径比例 | 老化 | 锚侧占比@0 | 锚侧占比@+1 | 分数步相关 | 跳跃与分数相关 | 经济方向与+1一致 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 5_TOP | return3_scaled | 0.646 | -0.201 | 86.8% | 100.0% | 0.811 | 0.441 | 是 |
| 5_TOP | return20_scaled | 0.795 | -0.036 | 89.5% | 94.7% | -0.045 | 0.446 | 是 |
| 5_TOP | change_in_return3_scaled | 1.831 | -0.395 | 65.8% | 55.3% | 0.726 | 0.430 | 否 |
| 5_TOP | distance_to_20day_high_scaled | 0.812 | 0.006 | 94.7% | 94.7% | 0.312 | 0.340 | 是 |
| 5_TOP | distance_to_20day_low_scaled | 0.665 | 0.018 | 100.0% | 100.0% | 0.672 | 0.444 | 是 |
| 5_TOP | position63 | 0.797 | 0.022 | 84.2% | 86.8% | 0.381 | 0.458 | 是 |
| 5_BOTTOM | return3_scaled | 0.670 | 0.411 | 94.7% | 100.0% | -0.654 | -0.782 | 是 |
| 5_BOTTOM | return20_scaled | 0.652 | -0.020 | 89.5% | 94.7% | -0.636 | -0.787 | 是 |
| 5_BOTTOM | change_in_return3_scaled | 0.677 | 0.465 | 60.5% | 71.1% | -0.404 | -0.746 | 否 |
| 5_BOTTOM | distance_to_20day_high_scaled | 0.658 | -0.016 | 97.4% | 100.0% | -0.584 | -0.546 | 是 |
| 5_BOTTOM | distance_to_20day_low_scaled | 0.818 | 0.007 | 92.1% | 94.7% | -0.278 | -0.279 | 是 |
| 5_BOTTOM | position63 | 0.662 | -0.014 | 84.2% | 92.1% | -0.679 | -0.681 | 是 |
| 9_TOP | return3_scaled | 0.780 | -0.284 | 100.0% | 100.0% | 0.673 | 0.351 | 是 |
| 9_TOP | return20_scaled | 0.829 | -0.084 | 100.0% | 100.0% | -0.189 | 0.339 | 是 |
| 9_TOP | change_in_return3_scaled | 1.584 | -0.583 | 75.0% | 62.5% | 0.562 | 0.347 | 否 |
| 9_TOP | distance_to_20day_high_scaled | 0.845 | -0.003 | 100.0% | 100.0% | 0.507 | 0.522 | 是 |
| 9_TOP | distance_to_20day_low_scaled | 0.591 | 0.030 | 100.0% | 100.0% | 0.768 | 0.320 | 是 |
| 9_TOP | position63 | 0.825 | 0.004 | 93.8% | 100.0% | 0.488 | 0.472 | 是 |
| 9_BOTTOM | return3_scaled | 0.805 | 0.504 | 100.0% | 100.0% | -0.418 | -0.779 | 是 |
| 9_BOTTOM | return20_scaled | 0.756 | 0.063 | 86.7% | 93.3% | -0.819 | -0.930 | 是 |
| 9_BOTTOM | change_in_return3_scaled | 2.715 | 0.584 | 60.0% | 60.0% | 0.089 | -0.737 | 否 |
| 9_BOTTOM | distance_to_20day_high_scaled | 0.682 | -0.016 | 100.0% | 100.0% | -0.790 | -0.838 | 是 |
| 9_BOTTOM | distance_to_20day_low_scaled | 0.822 | 0.006 | 93.3% | 93.3% | -0.738 | -0.723 | 是 |
| 9_BOTTOM | position63 | 0.743 | 0.000 | 86.7% | 93.3% | -0.911 | -0.911 | 是 |

经济方向是计划里事先写下的：顶部预期 3 日和 20 日收益为正、3 日收益变化为负、更接近 20 日高点、远离 20 日低点、63 日位置更高；底部相反。它不翻转任何一格的通过与否。

## 与 P1 分数的对齐

用 P1 的可评分日和目标，重算了 `lead_profile.csv` 里 −13..+6 的平均分数。最大绝对差是 4.914e-11。完整样本与全部可评分拐点的特征 z 最大绝对差是 0.075，出现在样本不完全重合的任务上；判定用完整样本。偏移 +1 的分数高于偏移 0 这一事实沿用 P1，不在这里重新判定。扣掉最新收盘之后的分数，就是已经发表的偏移 0 分数；本审计没有系数，不能在不重训的前提下改写逻辑回归。

## 边界

- 决策日重叠，特征自相关。门槛是描述规则，不是独立样本的显著性检验。
- 拐点是事后确认的收盘标签。这是时点审计，不是可交易信号。
- 历史被反复看过，不是新的盲测。历史公布时点与指数成分仍未完成全时期 PIT 认证。
- 没有把 D 日收盘写进当日特征。偏移 0 的最后输入是拐点前一日。
- 没有修改生产页面、采集器、正式信号，也没有恢复旧 V 系列。
- 没有把未来目标数当作配额。双80仍未达到。

## 复算

```text
python -B dual80-research/p1b_feature_timing/diagnose.py
```

缺少 `plan.json` 时测量会停止。`--write-plan-only` 只在文件不存在时写出计划，不读特征路径。
