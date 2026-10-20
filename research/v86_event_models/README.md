# V86 一对一顶底事件回测及误报归因（研究工具）

对 5% TOP、5% BOTTOM、9% TOP、9% BOTTOM **分别**评估，采用最大匹配数的一对一匹配：5%预警必须早于客观拐点1—10个交易日；9%为1—20个交易日。一个正式预警只能对应一个客观拐点，反之亦然。

输入为三个 CSV：
* alerts.csv: `id,date,scale,direction`，只允许 FORMAL_START 通知，不得混入每日 ACTIVE 状态。
* pivots.csv: `id,date,scale,direction`，仅接收**已成熟、定义冻结**的客观拐点（标签允许事后使用未来数据，但不能用于当时特征）。
* prices.csv: `date,close`，完整、无重复、严格升序的交易观察日序列。不能将沪深300序列和中证全指标签混搭。

```bash
python research/v86_event_models/event_audit.py --alerts alerts.csv --pivots pivots.csv --prices prices.csv --output results.json
python -m unittest discover -s research/v86_event_models -p 'test_*.py' -v
```

输出 TP、FP、FN、Precision、Recall、提前交易日、错误报警的市场阶段归因。市场阶段的简单研究定义：截至报警日近60日跌幅超过10%且近120日为负，归类为 DOWNTREND_RALLY_RISK；近60日涨幅超过10%且近120日为正，归类 UPTREND；否则 MIXED_OR_RANGE。它是待验证**描述性诊断**，不得作为已经回测有效的正式因子。

尚缺 V68 原始逐事件 FORMAL_START 与已成熟拐点 CSV，所以现在不能计算 49 次5%顶部假警中究竟有几次属于熊市反弹，也不能宣称有任何新回测成绩。V68聚合历史成绩请以仓库 V63—V68 原始实测报告为准。

## 质量底线

* 2022—2026历史已被多次探索，不能伪称独立盲测。
* 同一指数、相同日期、相同事件预算下作未来对照。
* 市场阶段使用报警当天及过去的价格，不使用未来价格确认趋势。
* 非法日期、重复事件id及缺少日历的事件必须失败，不得静默补值。

## V87：回测输入前置审计

先执行 `python research/v86_event_models/input_inventory.py --alerts alerts.csv --pivots pivots.csv --prices prices.csv --output /tmp/v86_input_status.json`。

标准CSV需采用 `id,date,scale,direction`，价格日历采用 `date,close`。兼容读取旧输入的 `event_id`、`pivot_id`、`turning_date`、`confirmation_date`，但旧输入仍须先明确转换及审核，不能直接当正式模型证据。存在非FORMAL_START记录、重复ID、缺交易日或不合理标签确认日期时标记BLOCKED。

该前置检查只验证输入格式与数据一致性，**即便INPUT_SCHEMA_READY，也不说明PIT、历史模型精确率、未来验证已经通过**。正式回测仍需将原始数据单独转换为event_audit.py接受的标准格式，并保留哈希和来源。
