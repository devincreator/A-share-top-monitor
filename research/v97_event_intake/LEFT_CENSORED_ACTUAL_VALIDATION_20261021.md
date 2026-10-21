# V97：截断历史标签与误报计算修复，2026-10-21

**研究结论：代码门禁PASS，真实旧预警事件来源仍BLOCKED。**

## 原缺陷

2022-02-23—2026-10-20归档的中证全指1128个真实价格观察日包含58个事后推导的5%/9%客观拐点，每尺度最早一个属于`first_segment_left_censored=true`。该标签之前的历史未知，不能证实它属于完整历史序列。旧事件审计器只要遇到一个左截断标签就拒绝全部输入；如果直接删除它，则对应提前窗口中的原始报警又可能被误计为FP。

## 已完成的修复

1. 每尺度仅允许一个、且必须位于该尺度最前方的左截断拐点；晚期或重复的左截断标记一律拒绝，防止人为剔除不利标签。
2. 左截断拐点不计入客观标签分母、TP或FN。处于该左截断端点正常提前窗口且未匹配其他成熟标签的报警标记`EXCLUDED_LEFT_CENSORED`，而不是FP。
3. 新增`excluded_left_censored_pivots`、`excluded_left_censored_alerts`与`scored_formal_alerts`记录；正常成熟拐点与其他报警继续按一对一规则计分。
4. 保持确认日后140指数交易日成熟门禁、未成熟`PENDING`及预测D日开盘前不能使用任何D日日级指标的规定。

## 真正执行的云端测试

[GitHub Actions 39568900654](https://github.com/devincreator/A-share-top-monitor/actions/runs/39568900654)结论SUCCESS。V86回归14项、V97回归70项均通过。新增真实数据集成测试直接SHA核验冻结的1128日价格CSV、58条客观拐点CSV和manifest，并验证两条左截断标签可通过严格输入校验；其他测试人为注入错误左截断标签和污染FP分母的情况。

原始事件接收工具仍输出`BLOCKED_BUNDLE_MISSING`；真实历史事件回放仍输出`BLOCKED_ORIGINAL_EVENTS_OR_AVAILABILITY_MISSING`。没有重建出旧V63—V68的`FORMAL_START`日期，历史TP/FP/FN、Precision/Recall和双80未产生新的真实结果。

**接下来的唯一主动研究任务仍是E1：恢复有原始日期、来源哈希、代码版本和历史信息时点的FORMAL_START报警。** 本次不调整模型、仓位或生产网页。
