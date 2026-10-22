# V105: 冻结基线误报与漏报诊断研究合同（研究用）

状态：DESIGN_ONLY_NOT_BACKTESTED，2026-10-22。
依赖：V101 冻结模型、V102 独立回放、V103 前瞻数据完整性验证。

## 已核实的研究事实
- V101 总计产生 59 条新 FORMAL_START（四项任务分别为 21 / 22 / 10 / 6）。
- V102 复核：原始评分口径 FP=32、FN=28；其中 FN 中有 5 个历史开头观测期不足，允许完全观察的 FN=23。
- 在这23个可评价漏报中，21个对应“两个价格条件从未同时满足”，1个受冷却抑制，1个无新触发边缘。
- FP=32 中，有11个事后显示为 1—3 倍提前窗口以外的同向拐点前预警，剩余21个不在上述延长窗口内。
- 上述分类属于历史事后诊断，不能提前用于特征或交易信号。

## 必须完成的检验
1. 输入只允许使用已冻结的 V101 59条信号、原始目标拐点日期、V102 的独立事件审计文件。逐条用原始ID关联，未匹配的事件不能补造。
2. 定义四个互斥的回顾性误差标签：TOO_EARLY、NO_FUTURE_PIVOT_IN_EXTENDED_WINDOW、PRICE_GATE_NEVER_COINCIDENT、COOLDOWN_OR_EDGE。重叠情况需要记录优先级和原始各标志，不允许互相覆盖。
3. 按 5_TOP、5_BOTTOM、9_TOP、9_BOTTOM 分别出具 TP、FP、FN、pending、样本总数、成熟度和观测边界。
4. 将事后标签与当时可知特征严格分仓。任何 V106 特征生成必须额外提供特征 as-of 时刻和原始来源哈希，拒绝引用未来拐点信息。
5. 与冻结基线作增量比较时，使用连续时间切分和禁入期，避免重叠样本信息泄漏。候选阈值只能在开发片段选择，在冻结验证片段评估。
6. 保留未通过的候选与所有试验次数；报告置信区间、子时段波动和多重尝试带来的选择偏差。

## 阶段性决策
- V105 的目标是回答“漏掉了何种市场结构”，而不是立刻优化成80/80。
- 如果新增因子无法在未参与选择的数据上改善误报漏报，保留 V101 为基线，不合并新参数。
- 真实前瞻记录不存在时，科学验收继续 BLOCKED。

## 所需证据
- research/status/quality_gates.json 中 V101、V102 的冻结统计
- research/v101_fresh_start/observations/fresh_formal_start_events.csv
- research/v101_fresh_start/observations/matched_or_pending_event_audit.csv
- research/v102_fresh_forensics/observations/false_positives_descriptive.csv
- research/v102_fresh_forensics/observations/missed_mature_pivots.csv

本合同没有生成新的回测成绩，也不改变 production_updated=false。
