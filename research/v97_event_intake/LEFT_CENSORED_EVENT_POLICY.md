# V97 E1/E3 研究边界修复：截断样本左边界与误报计数

2022-02-23至2026-10-20归档的中证全指1128个观察交易日包含58个事后派生的5%/9%反转端点，每个尺度的首个端点标有`first_segment_left_censored=true`。在2022-02-23之前没有完整价格及历史趋势状态，因此无法证明第一个端点就是全历史的同一拐点。

## 修复前

`preopen_event_audit.py`检测到一个左边界不完整的标签，就拒绝整批输入。这阻碍原始事件恢复后将部分真实数据用于科学评价；如果粗暴删除此行，又可能把该端点提前窗口里的有效历史报警算成FP。

## 修复后

- 输入允许每个尺度**仅一个**且必须位于该尺度全部端点最前面的`first_segment_left_censored=true`标签；两个以上或晚于其他端点则拒绝，避免任意事后撤销差绩效标签。
- 左截断标签既不计TP，也不计客观拐点分母和FN；若有历史报警处于该标签的1—10日(5%)或1—20日(9%)提前范围，并且未被独立的成熟正常端点匹配，该报警计`EXCLUDED_LEFT_CENSORED`，不计FP、TP、PENDING。
- 增加每任务`excluded_left_censored_pivots`、`excluded_left_censored_alerts`、`scored_formal_alerts`，保留`formal_alerts`原始报警数量。正式精确率只用可评分`TP/(TP+FP)`，覆盖率只用成熟可评分正常端点。
- 原有确认后140指数交易日成熟门禁、真实D开盘前可得时点、未成熟`PENDING`都保持不变。
- 该变更支持未来导入真实事件证据，但**不是已重新计算历史真实TP/FP/FN**；原V63/V68`FORMAL_START`事件仍然缺失。

## 验收

```bash
python -m unittest discover -s research/v97_event_intake -p 'test_preopen_event_audit.py' -v
```

新增覆盖：左截断事件不入Precision/Recall分母，正常成熟事件仍能评分，晚于正常端点的伪左截断标记被拒绝，一个尺度多个左截断标记被拒绝，5%和9%不会相互污染。

本研究修复仅允许保存审计记录，不会放行正式交易信号。**没有原始报警、独立披露时间与PIT源，四任务精确率/覆盖率仍BLOCKED。**
