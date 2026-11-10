# P1 分数是否落在 D..D+6

**Decision: `BLOCKED_NO_CONCENTRATION`.** BLOCKED. High scores do not concentrate inside D..D+6 under the pre-registered tests. Ordinary-day enrichment does pass on all four tasks: the inside-window tail rate is 2.35 to 4.20 times the ordinary rate, and inside-versus-ordinary AUC is 0.725 to 0.775. The pre-registered test still fails because the mean score and the causal tail rate both peak one session after the pivot (5_TOP +1, 5_BOTTOM +1, 9_TOP +1, 9_BOTTOM +1). That session is the first decision day whose last input is the pivot close, and an alert then cannot hit the pivot. Shoulder-average failures: 5_BOTTOM late shoulder, 9_TOP early shoulder. A second, independent gate also fails: only 21.1% of misses with a scoreable day entered the causal tail (12/57; cutoff 30%). 45 misses were never high. Do not only raise the threshold. The highest scores are already one session too late, so a higher quantile keeps the post-pivot spike and drops the weaker in-window days. Firing more is not compression: alert counts are already above the dual-80 band. Next diagnostic, not run here: compare the six frozen price features at offsets -6..0 with offset +1, without refitting, and see whether anything knowable before the pivot close moves inside the hit window. Median FP excess is at least the median TP excess on 5_TOP. A higher quantile alone is not supported there; a future fire rule would need a timing or persistence change to be informative.

**结论：阻断：高分没有集中在 D..D+6。** 相对普通日，四项任务的窗口内尾部都更密：尾部比例是普通日的 2.35 到 4.20 倍，窗口对普通日的 AUC 为 0.725 到 0.775。预注册检验仍然失败，因为四项任务的平均分数和因果尾部比例都在拐点后的第一个交易日达到峰值。这一天的最后输入刚好是拐点收盘，发出的警报已经打不中该拐点。肩部均值未通过：5_BOTTOM 晚肩、9_TOP 早肩。另一条独立门槛也没过：有可评分日的漏报里，只有 21.1% 进过因果尾部（12/57，下限 30%）。45 个漏报从未进入尾部。不要只提高阈值。最高分已经落在拐点后一天，提高分位会留下这个打不中的尖峰，并丢掉窗口内更弱的日子。多发报也不是压缩，警报数已经高于双80必要上限。下一步不做发报实验，而是在不重训的前提下，比较拐点前 6 日至当天、以及拐点后一天的六个价格特征，看拐点收盘进入特征之前，窗口内有没有真正移动的坐标。本 PR 不实现该比较。这些任务上，误报超额的中位数不低于真阳性：5_TOP。只提高分位没有依据，后续规则需要动触发时机或持续性。

这是冻结基线的对齐诊断，不是新模型。`formal_signal_allowed` 仍为 false。没有 PIT 认证，没有盲测，没有生产信号。

## 冻结与复算

标签 close，特征 price，发报 past_rank90，指数 000985.CSI，决策时钟为 D 日开盘前，命中窗 D..D+6，四任务同幅度同方向一对一。盘中混合标签不进入判定。规则写在 `plan.json`，测量开始前已落盘。

脚本按 `label_clock_v4/rank_replay.py` 重放因果 90 分位、锁定和重新武装，并与已保存的阈值、警报和指标逐项对齐。

| 任务 | 目标 | 警报 | TP | FP | FN | 精确率 | 覆盖率 | PENDING | 双80警报区间 | 区间之上 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5_TOP | 38 | 72 | 17 | 55 | 21 | 23.6% | 44.7% | 2 | 31–47 | 是 |
| 5_BOTTOM | 39 | 59 | 20 | 39 | 19 | 33.9% | 51.3% | 9 | 32–48 | 是 |
| 9_TOP | 18 | 46 | 7 | 39 | 11 | 15.2% | 38.9% | 9 | 15–22 | 是 |
| 9_BOTTOM | 19 | 51 | 8 | 43 | 11 | 15.7% | 42.1% | 11 | 16–23 | 是 |

上表与 `label_clock_v4/rank_metrics.csv` 的 close × price × past_rank90 行一致，也与原先展示的 23.6%/44.7%、33.9%/51.3%、15.2%/38.9%、15.7%/42.1% 在一位小数上一致。双80区间只说明现有警报数高于数学上限，不是用未来目标数去定配额。

## 窗口内、肩部、普通日

窗口内是能够击中该拐点的决策日：拐点前 6 日至拐点当天。早肩再往前 7 日，晚肩是拐点后 1 至 6 日。一天若落在任一目标窗口内，优先算窗口内。因果尾部指分数不低于当天过去 252 个已发分数的线性 90 分位。

| 任务 | 区域 | 天数 | 分数中位数 | 尾部比例 | 超额中位数 | 事后分位中位数 |
|---|---:|---:|---:|---:|---:|---:|
| 5_TOP | 窗口内 D..D+6 | 266 | 0.166 | 22.6% | -0.022 | 72.0 |
| 5_TOP | 早肩（提前7至13日） | 259 | 0.148 | 18.9% | -0.043 | 59.7 |
| 5_TOP | 晚肩（拐点后1至6日） | 216 | 0.146 | 14.4% | -0.043 | 57.5 |
| 5_TOP | 普通日 | 1655 | 0.126 | 9.6% | -0.066 | 42.2 |
| 5_BOTTOM | 窗口内 D..D+6 | 267 | 0.218 | 24.7% | -0.071 | 78.5 |
| 5_BOTTOM | 早肩（提前7至13日） | 273 | 0.133 | 12.5% | -0.141 | 56.2 |
| 5_BOTTOM | 晚肩（拐点后1至6日） | 209 | 0.195 | 23.9% | -0.108 | 74.1 |
| 5_BOTTOM | 普通日 | 1647 | 0.102 | 5.9% | -0.183 | 41.8 |
| 9_TOP | 窗口内 D..D+6 | 112 | 0.082 | 24.1% | -0.009 | 74.9 |
| 9_TOP | 早肩（提前7至13日） | 112 | 0.079 | 26.8% | -0.010 | 71.4 |
| 9_TOP | 晚肩（拐点后1至6日） | 96 | 0.076 | 18.8% | -0.015 | 67.8 |
| 9_TOP | 普通日 | 1737 | 0.062 | 7.6% | -0.031 | 44.8 |
| 9_BOTTOM | 窗口内 D..D+6 | 106 | 0.152 | 31.1% | -0.059 | 84.3 |
| 9_BOTTOM | 早肩（提前7至13日） | 112 | 0.064 | 12.5% | -0.124 | 60.6 |
| 9_BOTTOM | 晚肩（拐点后1至6日） | 87 | 0.109 | 26.4% | -0.086 | 75.3 |
| 9_BOTTOM | 普通日 | 1752 | 0.041 | 9.6% | -0.115 | 45.9 |

| 任务 | AUC | 尾部倍数 | 目标周命中 | 普通周命中 | 分数峰值偏移 | 尾部峰值偏移 | 集中度 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 5_TOP | 0.725 | 2.35 | 60.5% | 22.6% | 1 | 1 | FAIL |
| 5_BOTTOM | 0.760 | 4.20 | 56.4% | 16.5% | 1 | 1 | FAIL |
| 9_TOP | 0.766 | 3.17 | 56.2% | 17.4% | 1 | 1 | FAIL |
| 9_BOTTOM | 0.775 | 3.23 | 62.5% | 22.9% | 1 | 1 | FAIL |

AUC 只比较窗口内与普通日，肩部不进这一对。它和旧诊断里“正例对其余所有日子”的 0.70–0.77 不是同一个分母。目标周命中是“该目标的可评分窗口里至少有一天进入因果尾部”的比例；普通周命中是完全落在普通日上的连续 7 日块、步长 1、至少有一天进入尾部的比例。领先剖面的偏移 0 是拐点当天，-6 是窗口第一天。

分数在决策日 D 使用截至 D-1 的收盘。偏移 +1 的最后输入就是拐点当天的收盘，也是这个收盘第一次进入特征的决策日；警报窗口从这一天起算，已经不包含该拐点。下表是峰值附近，不是新的判定门槛。

| 任务 | 偏移 | 样本 | 尾部比例 | 平均分数 | 平均超额 | 是否在命中窗 |
|---|---:|---:|---:|---:|---:|---:|
| 5_TOP | -1 | 38 | 34.2% | 0.181 | -0.010 | 是 |
| 5_TOP | 0 | 38 | 39.5% | 0.184 | -0.007 | 是 |
| 5_TOP | 1 | 38 | 57.9% | 0.197 | 0.006 | 否 |
| 5_TOP | 2 | 38 | 13.2% | 0.160 | -0.031 | 否 |
| 5_BOTTOM | -1 | 38 | 28.9% | 0.254 | -0.046 | 是 |
| 5_BOTTOM | 0 | 38 | 44.7% | 0.295 | -0.006 | 是 |
| 5_BOTTOM | 1 | 38 | 63.2% | 0.362 | 0.060 | 否 |
| 5_BOTTOM | 2 | 38 | 39.5% | 0.255 | -0.049 | 否 |
| 9_TOP | -1 | 16 | 31.2% | 0.091 | -0.001 | 是 |
| 9_TOP | 0 | 16 | 43.8% | 0.095 | 0.003 | 是 |
| 9_TOP | 1 | 16 | 75.0% | 0.101 | 0.009 | 否 |
| 9_TOP | 2 | 16 | 18.8% | 0.085 | -0.007 | 否 |
| 9_BOTTOM | -1 | 15 | 33.3% | 0.186 | -0.014 | 是 |
| 9_BOTTOM | 0 | 15 | 53.3% | 0.221 | 0.021 | 是 |
| 9_BOTTOM | 1 | 15 | 73.3% | 0.275 | 0.073 | 否 |
| 9_BOTTOM | 2 | 15 | 40.0% | 0.163 | -0.041 | 否 |

图：`fig_score_ecdf.png`，`fig_tail_rate_by_region.png`，`fig_lead_profile.png`，`fig_lead_mean_score.png`。

## 漏报有没有进过尾部

| 任务 | FN | 可评分 | 进过尾部 | 从未进入 | 进过尾部的比例 | 从未进入者的最高事后分位中位数 | 其最高超额中位数 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 5_TOP | 21 | 21 | 6 | 15 | 28.6% | 82.1 | -0.009 |
| 5_BOTTOM | 19 | 19 | 2 | 17 | 10.5% | 80.9 | -0.078 |
| 9_TOP | 11 | 9 | 2 | 7 | 22.2% | 85.4 | -0.002 |
| 9_BOTTOM | 11 | 8 | 2 | 6 | 25.0% | 72.0 | -0.082 |

四项合并：进过尾部 12 / 57 = 21.1%。预注册下限是 30%。 从未进入的漏报里，最高事后分位低于 80 的比例是 37.8%，落在 [80, 90) 的比例是 44.4%。 事后分位使用了全部可评分日，只用来看漏报离尾部有多远，不参与发报。

类别计数：

| 任务 | 从未进入因果尾部 | 进过尾部，被锁定期挡住 | 进过尾部，锁后没有重新武装 | 进过尾部，锁定与未武装都有 | 窗口内发过报，但没配到该目标 | 没有可评分决策日 |
|---|---:|---:|---:|---:|---:|---:|
| 5_TOP | 15 | 2 | 1 | 3 | 0 | 0 |
| 5_BOTTOM | 17 | 0 | 2 | 0 | 0 | 0 |
| 9_TOP | 7 | 1 | 0 | 1 | 0 | 2 |
| 9_BOTTOM | 6 | 0 | 2 | 0 | 0 | 3 |

图：`fig_fn_breakdown.png`，`fig_window_max_excess.png`。后一张图里的普通周是互不重叠的步长 7，只作图示；判定用的是步长 1。

## 误报结构

分桶使用事后拐点与事后价格，解释误报，不能当作特征。互斥优先级见 `plan.json`。结构检验把“击中成熟队列外拐点”拿出分母，因为它是队列边界，不是行情机制。原始旗标允许重叠，见 `fp_flag_rates.csv`。

| 任务 | FP | 经济误报 | 队列边界 | 主导桶 | 主导占比 | 前两桶 | 其他 | 结构 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 5_TOP | 55 | 55 | 0 | 趋势延续（距下次同向拐点至少14日） | 61.8% | 80.0% | 0.0% | pass |
| 5_BOTTOM | 39 | 39 | 0 | 趋势延续（距下次同向拐点至少14日） | 61.5% | 76.9% | 0.0% | pass |
| 9_TOP | 39 | 39 | 0 | 趋势延续（距下次同向拐点至少14日） | 56.4% | 74.4% | 0.0% | pass |
| 9_BOTTOM | 43 | 43 | 0 | 趋势延续（距下次同向拐点至少14日） | 65.1% | 86.0% | 0.0% | pass |

| 任务 | 击中成熟队列外的同向拐点 | 窗口内已有目标但被更早警报配走 | 过晚（同向拐点在前1至6日） | 过早（同向拐点在后7至13日） | 窗口内是反向拐点 | 趋势延续（距下次同向拐点至少14日） | 拐点已过且超过6日 | 随后7日振幅小于该档 | 其他 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5_TOP | 0 | 0 | 7 | 10 | 0 | 34 | 4 | 0 | 0 |
| 5_BOTTOM | 0 | 0 | 6 | 5 | 0 | 24 | 4 | 0 | 0 |
| 9_TOP | 0 | 0 | 5 | 5 | 0 | 22 | 7 | 0 | 0 |
| 9_BOTTOM | 0 | 0 | 3 | 3 | 0 | 28 | 9 | 0 | 0 |

| 任务 | TP超额中位数 | FP超额中位数 | 只提高分位缺乏依据 |
|---|---:|---:|---:|
| 5_TOP | 0.007 | 0.010 | 是 |
| 5_BOTTOM | 0.043 | 0.028 | 否 |
| 9_TOP | 0.007 | 0.002 | 否 |
| 9_BOTTOM | 0.042 | 0.040 | 否 |

图：`fig_fp_buckets.png`。

## 逐项判定

| 任务 | 检验 | 结果 | 实际值 | 预注册要求 |
|---|---:|---:|---:|---:|
| 5_TOP | n_inside | PASS | 266 | >= 30 |
| 5_TOP | n_ordinary | PASS | 1655 | >= 100 |
| 5_TOP | n_early_shoulder | PASS | 259 | >= 20 |
| 5_TOP | n_late_shoulder | PASS | 216 | >= 20 |
| 5_TOP | n_stride1_ordinary_blocks | PASS | 1440 | >= 30 |
| 5_TOP | n_targets_with_eligible_day | PASS | 38 | >= 10 |
| 5_TOP | median_inside_gt_ordinary | PASS | 0.1655 | > ordinary median 0.1259 |
| 5_TOP | median_inside_gt_early | PASS | 0.1655 | > early median 0.1482 |
| 5_TOP | median_inside_gt_late | PASS | 0.1655 | > late median 0.1459 |
| 5_TOP | auc_inside_vs_ordinary | PASS | 0.7251 | >= 0.60 |
| 5_TOP | tail_gap | PASS | 0.1295 | >= 0.05 |
| 5_TOP | tail_ratio | PASS | 2.3479 | >= 2, or inside >= 0.10 if ordinary tail rate is 0 |
| 5_TOP | tail_beats_early | PASS | 0.0364 | inside - early >= 0.02 |
| 5_TOP | tail_beats_late | PASS | 0.0820 | inside - late >= 0.02 |
| 5_TOP | target_vs_ordinary_block | PASS | 0.3789 | >= 0.10 |
| 5_TOP | mean_score_peak_inside_window | FAIL | 1 | all tied argmax offsets in -6..0 |
| 5_TOP | tail_rate_peak_inside_window | FAIL | 1 | all tied argmax offsets in -6..0 |
| 5_BOTTOM | n_inside | PASS | 267 | >= 30 |
| 5_BOTTOM | n_ordinary | PASS | 1647 | >= 100 |
| 5_BOTTOM | n_early_shoulder | PASS | 273 | >= 20 |
| 5_BOTTOM | n_late_shoulder | PASS | 209 | >= 20 |
| 5_BOTTOM | n_stride1_ordinary_blocks | PASS | 1451 | >= 30 |
| 5_BOTTOM | n_targets_with_eligible_day | PASS | 39 | >= 10 |
| 5_BOTTOM | median_inside_gt_ordinary | PASS | 0.2176 | > ordinary median 0.1019 |
| 5_BOTTOM | median_inside_gt_early | PASS | 0.2176 | > early median 0.1329 |
| 5_BOTTOM | median_inside_gt_late | PASS | 0.2176 | > late median 0.1948 |
| 5_BOTTOM | auc_inside_vs_ordinary | PASS | 0.7601 | >= 0.60 |
| 5_BOTTOM | tail_gap | PASS | 0.1883 | >= 0.05 |
| 5_BOTTOM | tail_ratio | PASS | 4.1972 | >= 2, or inside >= 0.10 if ordinary tail rate is 0 |
| 5_BOTTOM | tail_beats_early | PASS | 0.1226 | inside - early >= 0.02 |
| 5_BOTTOM | tail_beats_late | FAIL | 0.0080 | inside - late >= 0.02 |
| 5_BOTTOM | target_vs_ordinary_block | PASS | 0.3987 | >= 0.10 |
| 5_BOTTOM | mean_score_peak_inside_window | FAIL | 1 | all tied argmax offsets in -6..0 |
| 5_BOTTOM | tail_rate_peak_inside_window | FAIL | 1 | all tied argmax offsets in -6..0 |
| 9_TOP | n_inside | PASS | 112 | >= 30 |
| 9_TOP | n_ordinary | PASS | 1737 | >= 100 |
| 9_TOP | n_early_shoulder | PASS | 112 | >= 20 |
| 9_TOP | n_late_shoulder | PASS | 96 | >= 20 |
| 9_TOP | n_stride1_ordinary_blocks | PASS | 1642 | >= 30 |
| 9_TOP | n_targets_with_eligible_day | PASS | 16 | >= 10 |
| 9_TOP | median_inside_gt_ordinary | PASS | 0.0815 | > ordinary median 0.0615 |
| 9_TOP | median_inside_gt_early | PASS | 0.0815 | > early median 0.0790 |
| 9_TOP | median_inside_gt_late | PASS | 0.0815 | > late median 0.0764 |
| 9_TOP | auc_inside_vs_ordinary | PASS | 0.7658 | >= 0.60 |
| 9_TOP | tail_gap | PASS | 0.1651 | >= 0.05 |
| 9_TOP | tail_ratio | PASS | 3.1723 | >= 2, or inside >= 0.10 if ordinary tail rate is 0 |
| 9_TOP | tail_beats_early | FAIL | -0.0268 | inside - early >= 0.02 |
| 9_TOP | tail_beats_late | PASS | 0.0536 | inside - late >= 0.02 |
| 9_TOP | target_vs_ordinary_block | PASS | 0.3889 | >= 0.10 |
| 9_TOP | mean_score_peak_inside_window | FAIL | 1 | all tied argmax offsets in -6..0 |
| 9_TOP | tail_rate_peak_inside_window | FAIL | 1 | all tied argmax offsets in -6..0 |
| 9_BOTTOM | n_inside | PASS | 106 | >= 30 |
| 9_BOTTOM | n_ordinary | PASS | 1752 | >= 100 |
| 9_BOTTOM | n_early_shoulder | PASS | 112 | >= 20 |
| 9_BOTTOM | n_late_shoulder | PASS | 87 | >= 20 |
| 9_BOTTOM | n_stride1_ordinary_blocks | PASS | 1662 | >= 30 |
| 9_BOTTOM | n_targets_with_eligible_day | PASS | 16 | >= 10 |
| 9_BOTTOM | median_inside_gt_ordinary | PASS | 0.1521 | > ordinary median 0.0408 |
| 9_BOTTOM | median_inside_gt_early | PASS | 0.1521 | > early median 0.0645 |
| 9_BOTTOM | median_inside_gt_late | PASS | 0.1521 | > late median 0.1093 |
| 9_BOTTOM | auc_inside_vs_ordinary | PASS | 0.7752 | >= 0.60 |
| 9_BOTTOM | tail_gap | PASS | 0.2149 | >= 0.05 |
| 9_BOTTOM | tail_ratio | PASS | 3.2274 | >= 2, or inside >= 0.10 if ordinary tail rate is 0 |
| 9_BOTTOM | tail_beats_early | PASS | 0.1863 | inside - early >= 0.02 |
| 9_BOTTOM | tail_beats_late | PASS | 0.0470 | inside - late >= 0.02 |
| 9_BOTTOM | target_vs_ordinary_block | PASS | 0.3964 | >= 0.10 |
| 9_BOTTOM | mean_score_peak_inside_window | FAIL | 1 | all tied argmax offsets in -6..0 |
| 9_BOTTOM | tail_rate_peak_inside_window | FAIL | 1 | all tied argmax offsets in -6..0 |
| ALL | pooled_fn_entered_tail_share | FAIL | 0.2105 | >= 0.30 of FN with an eligible day |

## 其他披露

- 5_TOP: 分数自 2015-04-01，因果阈值自 2015-10-08，可评分日 2396，分数日期间断 0，同向目标最短间隔 7，间隔≤6 的相邻对 0，被两个窗口同时覆盖的可评分日 0，早肩与窗口重叠后改记为窗口内的可评分日 7，拐点方向是否交替 是，事后前十分位倍数 2.01，步长7普通周尾部比例 21.9%（219 块），成熟边界 2025-11-21，右端 6 日内目标 0。
- 5_BOTTOM: 分数自 2015-04-01，因果阈值自 2015-10-08，可评分日 2396，分数日期间断 0，同向目标最短间隔 15，间隔≤6 的相邻对 0，被两个窗口同时覆盖的可评分日 0，早肩与窗口重叠后改记为窗口内的可评分日 0，拐点方向是否交替 是，事后前十分位倍数 5.37，步长7普通周尾部比例 15.0%（220 块），成熟边界 2025-11-21，右端 6 日内目标 1。
- 9_TOP: 分数自 2016-04-01，因果阈值自 2016-10-11，可评分日 2057，分数日期间断 0，同向目标最短间隔 24，间隔≤6 的相邻对 0，被两个窗口同时覆盖的可评分日 0，早肩与窗口重叠后改记为窗口内的可评分日 0，拐点方向是否交替 是，事后前十分位倍数 3.38，步长7普通周尾部比例 17.4%（241 块），成熟边界 2025-04-07，右端 6 日内目标 0。
- 9_BOTTOM: 分数自 2016-04-01，因果阈值自 2016-10-11，可评分日 2057，分数日期间断 0，同向目标最短间隔 17，间隔≤6 的相邻对 0，被两个窗口同时覆盖的可评分日 0，早肩与窗口重叠后改记为窗口内的可评分日 0，拐点方向是否交替 是，事后前十分位倍数 4.07，步长7普通周尾部比例 21.9%（242 块），成熟边界 2025-04-07，右端 6 日内目标 1。

下列目标在公布的 FN 里，但窗口内没有因果阈值，因此不进入 30% 漏报分母：9_TOP 2016-02-22，9_TOP 2016-04-14，9_BOTTOM 2016-01-28，9_BOTTOM 2016-02-29，9_BOTTOM 2016-05-18。9_TOP 的分数自 2016-04-01 起、因果阈值自 2016-10-11 起；9_BOTTOM 的分数自 2016-04-01 起、因果阈值自 2016-10-11 起。若把这些目标算作从未进入尾部，进尾比例只会更低。

## 边界

- 决策日重叠，分数自相关。预注册门槛是描述性规则，不是独立样本的显著性检验。
- 区域用的是事后才确认的评估拐点。这是对齐诊断，不是可交易信号。
- 因果尾部只用过去分数。事后分位和误报分桶用了后来的日子，已在表内分开。
- 历史被反复看过，不是新的盲测。历史公布时点与指数成分仍未完成全时期 PIT 认证。
- 没有修改生产页面、采集器、正式信号，也没有恢复旧 V 系列。
- 没有把 D 日价格写入特征。用到的分数行都满足 `last_input` 为前一交易日。

## 复算

```text
python -B dual80-research/p1_score_alignment/diagnose.py
```

缺少 `plan.json` 时，测量会停止。`--write-plan-only` 只在文件不存在时写出计划，不读分数分布。

