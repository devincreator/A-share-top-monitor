# 沪深历史证券范围与信息时点认证（研究隔离）
2026-10-27。范围仅为沪深交易所，不包括北交所。本目录只做**证据核查**，不修改 V101/V103 模型、C50 计算、正式网页或生产数据。

## 已确认的历史底座（来自仓库已保存的研究审计，不是本轮新获取）
- 2005：242/242 个交易日，314838 条逐股原始日线；2005 年未解决的候选无日线 14665 条、特殊身份记录 2584 条（含同代码不同主体），证券身份 / 停复牌仍未 PIT 认证。
- 2006：241/241 个交易日，288399 条原始日线，**仅 RAW 文件完整性已验收，不等于 PIT**。
- 前瞻研究严格按 **D 日北京时间 09:20**：D 日最终日频指标一律未知；D-1 及更早数据仍须有早于决策的实际公开证据。
- 已有 V97 `preopen_clock.py` 提供先行时钟规则；此目录增加历史股票身份与缺日交叉结构检查，不覆盖原时钟模块。

## 审计输入
`python research/hs_pit_audit/audit.py input.json output.json`

`input.json` 必须有 `decision_at`（带时区），以及以下数组：
- `episodes`: `security_listing_id,symbol,listed_from,listed_through,listing_evidence_uri`；同代码新旧主体必须给不同片段 ID。
- `bars`: `security_listing_id,symbol,date,source_raw_sha256`；SHA 必须对应原始逐日文件。
- `missing`: `security_listing_id,date,classification,independent_evidence_uri`；分类值：CONFIRMED_SUSPENDED、SOURCE_GAP、NOT_YET_LISTED、DELISTED、UNRESOLVED。不得以没有行情推断停牌。
- `features`: `name,observation_date,published_at,source_uri,source_raw_sha256,publication_evidence_uri,publication_provenance`；所有历史最终日频输入必须在决策前确实发布。

输出 `BLOCKED` 或 `SCHEMA_CANDIDATE_NOT_PIT_CERTIFIED`。即使结构校验无错误，也**不自动**置 PIT=true，因为证据 URI 的真实性、原始数据 SHA 与全市场覆盖率必须另行独立核验。当前脚本没有承诺可以认证公开时间真伪，且不会产出正式信号。

测试：`cd research/hs_pit_audit && python -m unittest -v test_audit.py`

## 下一项有实际数据价值的工作
针对 V82 的 14665 条无日线候选做按证券片段和日期的独立公告证据归因；先抽取 600018.SH 历史不同主体及其法定变更时点，避免仅依交易记录反推上市主体。保持 `research/status/quality_gates.json` 中 PIT=false，直到真实历史源完成独立认证。
