# V87 六个月自动研究巡检（2026-10-20—2027-04-20）

这是**不发交易信号、不改生产参数、不主动向用户推送消息**的研究审计工作流。它按周检查现有数据和模型的真实就绪程度，不能代替AI在后台自主设计新策略，也不能根据时间流逝自动宣称达标。

### 运行机制

- [GitHub Actions 例行研究巡检](../../.github/workflows/v87-six-month-research.yml)：北京时间每周一20:30运行，2027-04-20后自动跳过计算。
- 每次先运行V84、V86、V87单元测试。未通过则该轮失败，不更改策略质量门禁。
- 审计三份快照：`data/latest_state.json`、`data/latest_verified_market.json`、`research/status/quality_gates.json`，为各文件记录SHA256。
- 检查V86实际事件文件是否具备标准字段、非重复ID、合理日期和交易日历。历史别名输入不能直接冒充已经认证的正式预警。
- 每周结果保留为GitHub Actions附件90天；每月第一次运行保存`research/v87_automation/checkpoints/YYYY-MM.json`，供长期核对。十月初始化检查可在2026-10-20写入。
- 所有状态仅为RESEARCH_ONLY。不能自动修改`app.html`、`index.html`、`collector/`、`data/`或`research/status/quality_gates.json`。

### 六个月工作重点

| 研究阶段 | 时间 | 必须满足的前置条件 |
|---|---|---|
| 恢复日度数据 | 2026-10—11 | 可信指数价格、成交量/额、换手率、融资记录均有一致可得日期；否则只记DATA_PENDING |
| 逐事件误报归因 | 2026-11—12 | 恢复真实FORMAL_START与已成熟客观拐点CSV，来源与哈希可核；否则只记BLOCKED |
| 固定预算模型对比 | 2026-12—2027-01 | 相同历史标签、样本窗口、正式报警预算、提前期与一对一配对 |
| 前瞻影子检验 | 2027-01—04 | 每日首次信号留档，不因未来结果改写；末端不成熟的拐点仍记PENDING |

**截至启动日的限制**：2006年241/241天原始交易文件完整性已核验，但2005年历史上市身份与停牌资料不符合PIT门禁；2026-08-04之后完整四模块模型未续算；V86逐事件原始研究包仍缺失。四任务双80目标未通过。即便工作流显示SUCCESS，也不能声称研究条件已经满足。

本地复现：

```bash
python -m unittest discover -s research/v84_live_readiness -p 'test_*.py' -v
python -m unittest discover -s research/v86_event_models -p 'test_*.py' -v
python -m unittest discover -s research/v87_automation -p 'test_*.py' -v
python research/v87_automation/weekly_review.py --repo . --today 2026-10-20 --output /tmp/v87.json
```
