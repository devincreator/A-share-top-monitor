# V97 E1 补充验收：独立枚举事后客观拐点，检查是否漏标

本工具不是原始历史预警的重建。前一轮`verify_archived_pivot_chronology.py`只核对**已经写进CSV的58个拐点**是否满足日线的首次确认与顶底交替条件，不能检查是不是漏掉了其他满足规则的极值。

本次`independent_label_completeness.py`在**不导入原reconstruct_partial_pivots.py标签生成器**的前提下，直接逐日扫描归档的1,128条`000985.CSI`中证全指收盘价，使用单独的`Decimal`流式状态机枚举整个2022-02-23至2026-10-20窗口的全部5%/9%交替收盘反转事件，并与冻结CSV逐条对比：

- 检验两项阈值、时间顺序、首次触发反转时点，避免遗漏满足规则的客观标签。
- 拒绝缺失、额外、重复、错误极值价格/日期、错误首次确认日期和左边界标注。
- 尚未反转确认的右侧候选极值只能标记`UNCONFIRMED_TRAILING_EXTREME`，不能当成历史客观拐点。
- 归档CSV的原始SHA256与manifest必须一致，代码不能覆盖首次研究报告。
- 即使两套实现对照全部一致，仍只代表**这个1128日截断样本内的规则一致性**。既不能证明原始2015—2026完整V52 157个极值无遗漏，也不能证明历史行情PIT，更不代表已经得到原V63/V68`FORMAL_START`报警。

机器审计输出：`research/v97_event_intake/observations/independent_label_completeness_20261021.json`。运行：

```bash
python -m unittest discover -s research/v97_event_intake -p 'test_independent_label_completeness.py' -v
python research/v97_event_intake/independent_label_completeness.py \
  --observations research/v97_event_intake/observations \
  --output research/v97_event_intake/observations/independent_label_completeness_20261021.json
```

云端：[V97 独立标签完整性检查工作流](../../.github/workflows/v97-label-chronology-independent.yml)。

**本版本对用户预测当日数据的约束不变**：D日开盘前不可使用D的任何日级指标；D-1也须有已实际公布的时点证据。事后标签永远不是预测当时已知特征。本阶段只推进E1，真正旧正式报警来源缺失时E2、E3和E4的历史评价仍保持BLOCKED。
