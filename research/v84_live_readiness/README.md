# V84 交易日资料就绪度（研究版）

> 目标：每天能够审计数据的可用程度，不把旧价格快照当成新正式信号。非正式交易模型，禁止直接推送策略结论。

## 已接入的自动流程

- GitHub Actions: [V84 research daily source readiness](../../.github/workflows/v84-readiness-research.yml)。
- 每个工作日北京时间19:30（UTC 11:30）尝试执行，交易所休市或第三方数据未发布时写入 DATA_UNAVAILABLE。
- 自动读取两份**现存**的生产 JSON，独立标注价格核心、市场快照、完整四模块模型的日期和状态，输出 readiness.json。
- 另从第三方原始每日股票日线源抓取**当天**沪深股票的价格记录，核验日期、数据格式、重复、OHLC 与 SHA-256，输出 probe.json 和原始 CSV（仅工作流临时附件，30天保留）。
- 源响应 RAW_DAILY_INTEGRITY_PASS 只代表该来源**当天原始记录内部格式**通过，绝不代表官方指数、历史股票池的PIT认证、融资数据认证或模型可以发出正式信号。
- 失败时保留明确的 DATA_UNAVAILABLE，不回退到旧日期冒充新数据。工作流运行成功不等于数据源成功。

## 当前初始基线（2026-10-20）

- 完整四模块最近日期：2026-08-04；
- 已核验价格核心最近日期：2026-09-21；
- 独立市场快照最近日期：2026-10-08；
- 三者不可互相替代。最终正式状态应为 DATA_PENDING，而不是“今天新发出顶部/底部预警”。

## 本地复算

```bash
python -m unittest discover -s research/v84_live_readiness -p 'test_*.py' -v
python -m unittest discover -s research/v86_event_models -p 'test_*.py' -v
python research/v84_live_readiness/readiness.py --today 2026-10-20 --output /tmp/readiness.json
python research/v84_live_readiness/daily_probe.py --date 20261020 --output-dir /tmp/probe
```

不运行最后一行也能完成离线状态审计；最后一行涉及外部请求与数据费用/可用性风险。默认不提交公网原始行情到主仓。

## 尚未实现

* 并未恢复完整四模块策略的真实每日计算；旧模型和正式策略不变。
* 尚未对新日期指数行情、成交额、换手率和融资进行完整同口径交叉认证。
* 后续只有在这些数据门禁真正达标后，才能讨论正式发布或更改首页现有快照。
