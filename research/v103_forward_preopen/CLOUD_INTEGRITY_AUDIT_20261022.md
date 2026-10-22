# V103 首次盘前行情证据部署与完整性增强验收（2026-10-22，北京时间）

## 本次真实核实的状态

- 远端仓库：`devincreator/A-share-top-monitor`，代码文件 `research/v103_forward_preopen/first_capture.py`，正式定时采集工作流 `.github/workflows/v103-forward-first-capture.yml`，均在 `main`。
- 初版代码GitHub云端测试：[39707502379](https://github.com/devincreator/A-share-top-monitor/actions/runs/39707502379) **9/9 PASS**，触发事件为`push`，`Record official... `步骤是`skipped`。
- V103数据完整性加固的GitHub云端测试：[39709012813](https://github.com/devincreator/A-share-top-monitor/actions/runs/39709012813) **22/22 PASS**；这是**合成原始响应+文件读写测试**，不是当天真实盘前源。
- 加装schedule回读核验步骤后：[39709209527](https://github.com/devincreator/A-share-top-monitor/actions/runs/39709209527) **22/22 PASS**，该次仍由`push`触发，真实数据下载、重新读取和正式归档三个步骤均`skipped`。
- 今日2026-10-22 09:00—09:20北京时间的首次真实采集窗口已过；没有从GitHub仓库确认到符合窗口的数据。不能声称今天完成真实采集。工作流计划未来工作日09:10北京时间尝试一次，第一档是2026-10-23；云端`schedule`可能延迟，只要超过09:20就必须BLOCKED并留下原始失败痕迹。
- [中证指数日度行情历史查询](https://www.csindex.com.cn/csindex-home/perf/index-perf)是本阶段候选直连原始端点：`indexCode=000985`；原始HTTP响应、索引代码、日期、127个有效历史价格、SHA与时点全部需真实数据通过后才可将**首次观测证据**标PASS。资料中接口名称和结构可参考AKShare的中证指数行情实现，但文档与模拟接口结构无法代替直播源响应验证。

## 本次发现并修复的真实缺陷

1. **时钟倒退**：若用来记录响应完成的时钟早于请求开始时钟，旧版仅比较它们与09:20截止，可能误标PASS。现在`completed < started`会标记`INVALID_NON_MONOTONIC_CAPTURE_CLOCK`、阻止任何合格原始证据。
2. **跨站HTTP重定向**：`urllib.request.urlopen`可能自动跟随重定向。新规则把最终URL限定在`https://www.csindex.com.cn`，不接受其他站点发来的伪官方JSON。
3. **首采归档损坏**：旧版检测到`first_capture.json`或`official_index_raw.json`存在就返回“已归档”，但未确认内容没损坏。现在再次读取必须验证manifest、原始文件字节SHA、原始URL响应记录是否有完整证据，原始raw缺失、manifest无效或仅有部分文件都阻塞，不能覆盖。
4. **归档自称PASS但时间造假**：即使manifest存在、raw SHA一致，也重新检查北京本地开始/结束均在09:00—09:20，完成不早于开始、`first_observed_at_utc`确实等于记录的完成时间；失败则不能重放成合法盘前证据。
5. **归档自称PASS但收盘价或历史窗口不一致**：以原样保留的raw JSON重新解析指数、日期、前127个收盘SHA，并与首次manifest宣称的最后交易日、最新收盘、隔离异常日期等逐字段对照，不一致即BLOCKED。
6. **实际工作流缺少回读检查**：现在`schedule`采集后、归档commit前，先调用`verify_first_capture`核验一次实写文件；若状态BLOCKED则在Actions记录warning并归档失败证据，不将Action job的测试成功等同于数据科学通过。研究模板工作流已与实际工作流同步。

## 验收状态矩阵

| 门禁 | 截至本报告 |
|---|---|
| GitHub正式代码与schedule工作流已部署 | PASS |
| 22项源码/时间/归档合成测试 | PASS，见上述runs |
| schedule真实开始于D 09:00—09:20 | 未确认（下一工作日尚未到来） |
| 官方原始JSON合格、实际SHA可存取 | BLOCKED，尚无真实首次源 |
| 原发布者首次公开发布时间PIT | BLOCKED；即使实际捕获也只能证明捕获时已可见 |
| 已认证中国实际交易日历 | BLOCKED；周末/上一个工作日校验不等于权威交易所开市日历 |
| V101开盘前边缘/冷却连续状态及真实前瞻报警 | 未启动 |
| 四任务独立双80、正式模型升级 | 未达到；正式网站与仓位不变 |

## 下一步唯一优先事项

核实**真实2026-10-23 09:10北京时间**的`schedule`日志是否实际发出HTTP请求、完成于09:20之前，是否取得官方`000985`源的合格127期以上数据，是否生成可独立重新计算的原始文件SHA及首次不可覆盖manifest。如果由于工作流延迟或端点异常BLOCKED，就优先解决真实数据源时点/Schema，不要按历史数字“补写”10月23日成功记录。没有达到首次有效原始证据之前，不启动正式V101新预警或前瞻胜率统计。

附注：本地早期文件`LOCAL_TEST_REPORT.json`及其9项测试是当时的**历史记录**，应保留原状；新的GitHub状态以本文件和质量门禁为准。
