# P1d 已有 past_rank90 发报是推迟到 +1，还是窗口内根本没进尾部

**Decision: `GO_NEW_FACTORS`.** A miss is delay-to-+1 only when an eligible day in -6..0 is already in the causal tail and an unmatched past_rank90 fire occurs at offset +1..+6. A miss is in-window-too-weak when no eligible day in -6..0 is in that tail. A task class requires count * 2 > FN; a score requires 3 of 4 tasks. Both scores must agree. Frozen six-feature score class: WEAK. Slow-feature score class: WEAK. 5_TOP frozen six-feature delay 3 / weak 15 / other 3 of 21 misses (WEAK) 5_BOTTOM frozen six-feature delay 1 / weak 17 / other 1 of 19 misses (WEAK) 9_TOP frozen six-feature delay 2 / weak 9 / other 0 of 11 misses (WEAK) 9_BOTTOM frozen six-feature delay 0 / weak 9 / other 2 of 11 misses (WEAK) 5_TOP slow-feature delay 4 / weak 22 / other 4 of 30 misses (WEAK) 5_BOTTOM slow-feature delay 1 / weak 22 / other 1 of 24 misses (WEAK) 9_TOP slow-feature delay 3 / weak 8 / other 2 of 13 misses (WEAK) 9_BOTTOM slow-feature delay 1 / weak 9 / other 1 of 11 misses (WEAK) Delay does not explain the gap. The next step is features outside this price family, each gated on point-in-time availability. That work is not implemented here, and the two fast price features are not added back. P1 remains BLOCKED_NO_CONCENTRATION. P1b remains GO_PRE_PIVOT_COORDINATE. P1c remains BLOCKED_NO_WINDOW_PEAK. formal_signal_allowed stays false. This is not PIT, not a blind test, and not a signal.

**结论：`GO_NEW_FACTORS`。** 漏报算作推迟到 +1，必须是 −6..0 里已有可评分因果尾部日，并且 +1..+6 有一次没有配给其他拐点的 past_rank90 发报。窗口内没有任何可评分日进入因果尾部，就算窗口内太弱。任务类别要求计数的两倍大于漏报数；一条分数要 4 项里至少 3 项同类。两条分数必须一致。冻结六特征是 WEAK。四慢变量是 WEAK。5_TOP 冻结六特征：推迟 3，窗口内太弱 15，其他 3，漏报 21（WEAK） 5_BOTTOM 冻结六特征：推迟 1，窗口内太弱 17，其他 1，漏报 19（WEAK） 9_TOP 冻结六特征：推迟 2，窗口内太弱 9，其他 0，漏报 11（WEAK） 9_BOTTOM 冻结六特征：推迟 0，窗口内太弱 9，其他 2，漏报 11（WEAK） 5_TOP 四慢变量：推迟 4，窗口内太弱 22，其他 4，漏报 30（WEAK） 5_BOTTOM 四慢变量：推迟 1，窗口内太弱 22，其他 1，漏报 24（WEAK） 9_TOP 四慢变量：推迟 3，窗口内太弱 8，其他 2，漏报 13（WEAK） 9_BOTTOM 四慢变量：推迟 1，窗口内太弱 9，其他 1，漏报 11（WEAK）。推迟发报解释不了这个缺口。下一步是价格家族之外、并且先过披露时点门禁的特征。本 PR 不实现，也不把两个快变量加回来。P1 仍是 BLOCKED_NO_CONCENTRATION。P1b 仍是 GO_PRE_PIVOT_COORDINATE。P1c 仍是 BLOCKED_NO_WINDOW_PEAK。formal_signal_allowed 仍为 false。这不是 PIT，不是盲测，也不是信号。

这是归因，不是新的发报规则。`formal_signal_allowed` 仍为 false。没有 PIT 认证，没有盲测，没有生产信号。P1、P1b、P1c 的结论不改写，门槛不放宽。

## 预登记的分桶

两条分数用同一成熟队列、同一因果 past_rank90：冻结的六个价格特征逻辑回归分数，以及 P1c 四个慢变量的等权符号对齐标准化和。分位、锁定和重新武装都不改。

偏移 0 的最后输入是拐点前一日收盘，这一天的警报还能打中该拐点。偏移 +1 的最后输入才是拐点收盘，这一天的警报打不中该拐点。真阳性的发报偏移因此只能落在 −6..0；出现 +1 命中会中止，而不是放进推迟桶。

漏报的三个互斥合计：

- **推迟到 +1**：−6..0 里已有可评分因果尾部日，窗口内没有发报，并且 +1..+6 有一次没有配给其他拐点的发报。
- **窗口内太弱**：−6..0 里没有可评分日进入因果尾部。即便 +1 进入尾部或在 +1 发报，也不改这个桶。
- **其他**：窗口内发了但没配上，尾部日被锁定或尚未重新武装且 +1..+6 没有未配对发报，或者 +1..+6 的发报其实命中了另一个拐点。

任务类别用整数比较：某一类计数的两倍大于该任务漏报数，才算这一类占多数。4 对 4 是 SPLIT，不是多数。一条分数要 4 项任务里至少 3 项同为 DELAY 才是 EARLY，至少 3 项同为 WEAK 才是 WEAK。两条分数都是 EARLY 才是 `GO_EARLY_FIRE_TRIAL`；都是 WEAK 才是 `GO_NEW_FACTORS`；样本门槛是每个任务、每条分数的漏报和误报都至少 8。其余是 `MIXED`。

## 漏报归因

合计一行只便于阅读，不进入门槛。

| 分数 | 任务 | 真阳性 | 漏报 | 推迟到 +1 | 其中恰好 +1 | 其中 +2..+6 | 窗口内太弱 | 其他 | 类别 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 冻结六特征 | 5_TOP | 17 | 21 | 3 | 2 | 1 | 15 | 3 | WEAK |
| 冻结六特征 | 5_BOTTOM | 20 | 19 | 1 | 1 | 0 | 17 | 1 | WEAK |
| 冻结六特征 | 9_TOP | 7 | 11 | 2 | 2 | 0 | 9 | 0 | WEAK |
| 冻结六特征 | 9_BOTTOM | 8 | 11 | 0 | 0 | 0 | 9 | 2 | WEAK |
| 四慢变量 | 5_TOP | 8 | 30 | 4 | 2 | 2 | 22 | 4 | WEAK |
| 四慢变量 | 5_BOTTOM | 15 | 24 | 1 | 1 | 0 | 22 | 1 | WEAK |
| 四慢变量 | 9_TOP | 5 | 13 | 3 | 1 | 2 | 8 | 2 | WEAK |
| 四慢变量 | 9_BOTTOM | 8 | 11 | 1 | 1 | 0 | 9 | 1 | WEAK |
| 冻结六特征 | 合计（非门槛） | 52 | 62 | 6 | 5 | 1 | 50 | 6 |  |
| 四慢变量 | 合计（非门槛） | 36 | 78 | 9 | 5 | 4 | 61 | 8 |  |

| 分数 | 任务 | 窗口内发了但未配上 | 晚发报属于别的拐点 | 锁定 | 未重新武装 | 锁定与未武装混合 | 无评分日 | 有评分日但从未进尾部 | 弱漏报里 +1 已在尾部 | 弱漏报里 +1 发了报 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 冻结六特征 | 5_TOP | 0 | 0 | 0 | 1 | 2 | 0 | 15 | 4 | 4 |
| 冻结六特征 | 5_BOTTOM | 0 | 0 | 0 | 1 | 0 | 0 | 17 | 4 | 3 |
| 冻结六特征 | 9_TOP | 0 | 0 | 0 | 0 | 0 | 2 | 7 | 3 | 3 |
| 冻结六特征 | 9_BOTTOM | 0 | 0 | 0 | 2 | 0 | 3 | 6 | 2 | 2 |
| 四慢变量 | 5_TOP | 0 | 0 | 1 | 3 | 0 | 0 | 22 | 1 | 1 |
| 四慢变量 | 5_BOTTOM | 0 | 0 | 0 | 1 | 0 | 0 | 22 | 8 | 8 |
| 四慢变量 | 9_TOP | 0 | 0 | 1 | 1 | 0 | 2 | 6 | 0 | 0 |
| 四慢变量 | 9_BOTTOM | 0 | 0 | 0 | 1 | 0 | 2 | 7 | 3 | 3 |

图 `fig_miss_buckets.png` 是每个任务的三段漏报计数。弱漏报里「+1 已在尾部」只说明拐点收盘进入特征后分数才到尾部，同一条阈值在可命中日不会发报。

## 真阳性发在哪一天

下表是命中这个拐点的警报偏移。有较早尾部日，表示发报之前窗口里已经有因果尾部日，但当天被锁定或尚未重新武装，后来仍在 −6..0 内再次越过并发报。+1 也在尾部，表示拐点后一天同样进入尾部；那一天打不中这个已经配对的拐点。

| 分数 | 任务 | 真阳性 | 窗口内第一个尾部日就发报 | 更早的尾部日之后才发报 | 命中且 +1 也在尾部 | 命中且 +1 也发了报 |
|---|---|---:|---:|---:|---:|---:|
| 冻结六特征 | 5_TOP | 17 | 15 | 2 | 12 | 0 |
| 冻结六特征 | 5_BOTTOM | 20 | 18 | 2 | 19 | 0 |
| 冻结六特征 | 9_TOP | 7 | 4 | 3 | 7 | 0 |
| 冻结六特征 | 9_BOTTOM | 8 | 7 | 1 | 8 | 0 |
| 四慢变量 | 5_TOP | 8 | 6 | 2 | 8 | 0 |
| 四慢变量 | 5_BOTTOM | 15 | 13 | 2 | 15 | 0 |
| 四慢变量 | 9_TOP | 5 | 3 | 2 | 5 | 0 |
| 四慢变量 | 9_BOTTOM | 8 | 8 | 0 | 8 | 0 |

| 分数 | 任务 | −6 | −5 | −4 | −3 | −2 | −1 | 0 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 冻结六特征 | 5_TOP | 0 | 1 | 0 | 6 | 3 | 4 | 3 |
| 冻结六特征 | 5_BOTTOM | 2 | 2 | 3 | 2 | 5 | 3 | 3 |
| 冻结六特征 | 9_TOP | 0 | 0 | 0 | 0 | 4 | 1 | 2 |
| 冻结六特征 | 9_BOTTOM | 1 | 2 | 2 | 1 | 0 | 0 | 2 |
| 四慢变量 | 5_TOP | 0 | 0 | 0 | 2 | 3 | 2 | 1 |
| 四慢变量 | 5_BOTTOM | 1 | 3 | 3 | 0 | 4 | 2 | 2 |
| 四慢变量 | 9_TOP | 0 | 0 | 0 | 1 | 3 | 0 | 1 |
| 四慢变量 | 9_BOTTOM | 1 | 2 | 3 | 0 | 1 | 0 | 1 |

图 `fig_hit_offsets.png` 是这张偏移计数。命中日本身的锁定会覆盖到拐点当天或更后，锁定结束后的第一个交易日不能在同一天既重新武装又发报，所以命中之后的 +1 不会再发一次。

有 1 次命中的发报日不在该任务的可评分集合里：9_BOTTOM 2016-01-28 的发报日 2016-01-22（偏移 -4）。四慢变量与 5% 共用分数，可以在 9% 冻结分数尚未有阈值的日期发报。偏移仍在 −6..0，按命中计入；窗口内没有更早的可评分尾部日。其余命中的发报日都在可评分集合里。

## 误报是拐点之后才发，还是窗口内的假警报

只计已评价的误报，不含 PENDING。同一幅度、同一方向的全部收盘拐点都用来判断时点，包括成熟队列之外的拐点；这些标签不进入特征。恰好 +1 表示最后输入就是某个同向拐点的收盘。+2..+6 表示最后输入已经晚于该拐点收盘。两类都算太晚。其余误报在警报前六个交易日里没有同向拐点，记为不是事后补发的假警报。

| 分数 | 任务 | 误报 | 最后输入就是拐点收盘 | 最后输入已经晚于拐点收盘 | 不是事后补发的假警报 | 精确率 | 覆盖率 |
|---|---|---:|---:|---:|---:|---:|---:|
| 冻结六特征 | 5_TOP | 55 | 6 | 1 | 48 | 23.6% | 44.7% |
| 冻结六特征 | 5_BOTTOM | 39 | 4 | 2 | 33 | 33.9% | 51.3% |
| 冻结六特征 | 9_TOP | 39 | 5 | 0 | 34 | 15.2% | 38.9% |
| 冻结六特征 | 9_BOTTOM | 43 | 1 | 2 | 40 | 15.7% | 42.1% |
| 四慢变量 | 5_TOP | 37 | 3 | 2 | 32 | 17.8% | 21.1% |
| 四慢变量 | 5_BOTTOM | 35 | 8 | 1 | 26 | 30.0% | 38.5% |
| 四慢变量 | 9_TOP | 34 | 1 | 2 | 31 | 12.8% | 27.8% |
| 四慢变量 | 9_BOTTOM | 40 | 3 | 1 | 36 | 16.7% | 42.1% |

精确率和覆盖率与冻结账本相同，没有重新搜索。图 `fig_fp_timing.png` 是这三段误报计数。

## 没有做的事

- 没有实现 `emit_on_suppressed_hittable_tail`，也没有搜索第二种发报规则。
- 没有重训六个价格特征，没有把 3 日收益或 3 日收益变化加回分数。
- 没有打开 P2，没有提高分位，没有用未来目标数做警报配额。
- 没有更换标签或指数，没有把 D 日收盘写进当日特征。
- 没有修改生产页面、采集器、正式信号，也没有恢复旧 V 系列。
- 不声称双80，不声称 PIT，不声称这是盲测。

## 复算

```text
python -B dual80-research/p1d_fire_timing/diagnose.py
```

缺少 `plan.json` 时测量会停止。`--write-plan-only` 只在文件不存在时写出计划，不读特征数值，也不读警报行。
