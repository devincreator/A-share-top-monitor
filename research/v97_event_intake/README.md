> **已取得真实部分标签证据：** [V97 2022—2026中证全指58个事后拐点独立重建报告](ACTUAL_PARTIAL_OBJECTIVE_REPLAY_20261021.md)，[价格源/标签哈希](observations/partial_v52_pivot_manifest.json)。这不是旧`FORMAL_START`预警的恢复；模型预警日期及真实误报分析仍阻塞。

> **2026-10-21 当前唯一主动研究任务：** [真实事件重建与开盘前因果门禁](../FOCUS_V97_PREOPEN_EVENT_RECONSTRUCTION.md)。预测交易日D任何D日价格、成交额、融资、广度及其他日线指标一概不可用；用D之前已正式公布的信息，并保留公布时间证据。未找到原V68事件包时只报BLOCKED，不编造日期。旧CSI300的2015—2021聚合基准不能等同于开盘前信号。

# V97 V63—V68旧事件级证据源恢复入口（研究专用）

2026-10-21的GitHub仓库全树与所有现存Release资产逐项检查发现：2005和2006两个归档包可见，**没有V63—V68逐日正式预警/客观拐点原始研究ZIP**。仓库`V63_V68_实测报告.md`只有历史TP/FP聚合成绩，不包含可独立匹配的逐事件日期。

因此，V97不能拿`21/70`聚合比例倒推出70条正式报警，也不能用混合指数替代真实主指数。

新增`bundle_gate.py`是**原始证据接收门**：未来找到旧ZIP后，须先归一化为只含四个文件的明确审计输入：

- `alerts.csv`：标准`id,date,scale,direction,event_type`；每行必须是`FORMAL_START`，不能把`ACTIVE`日更新重复计数。
- `pivots.csv`：`id,date,scale,direction,confirmation_date`；必须保留事后确认时点，不可拿未来标签冒充当时因子。
- `prices.csv`：`date,close`且按对应指数真实交易日排序。
- `manifest.json`：标明`index_instrument`（只允许明确的`000985.CSI`或独立的`000300.CSI`轨道）、冻结标签引擎`label_version`、原始版本`source_code_commit`以及三个CSV的SHA256。

严格检查ZIP路径穿越、压缩文件大小、文件哈希、日期、重复事件、正式报警类型，以及中证全指/沪深300不混同。即使ZIP结构通过，也只到`MAIN_INDEX_BUNDLE_INTAKE_SCHEMA_VALID_NOT_PIT`，**还没有真实回测或正式信号许可**。

每次GitHub运行仅执行单元测试并输出机器可读的`source_status.json`；由于原ZIP目前缺失，实际结果应为`BLOCKED_BUNDLE_MISSING`而非绿灯模型或虚构事件。

```bash
python -m unittest discover -s research/v97_event_intake -p 'test_*.py' -v
python research/v97_event_intake/bundle_gate.py --output v97_event_intake_output/source_status.json
```

另外，V86事件审计器若直接输入未成熟的末端正式报警，会错误把尚有未来评价窗口的报警当作FP。后续引入真实逐事件数据时还需要添加`PENDING`成熟日期隔离，不通过时不能计算正式双80。
