# 沪深 R1—R6 执行记录（2026-10-27；不等于全部完成认证）

## 执行范围及原始依据
本轮读取仓库已提交的 `AI_RESEARCH_HANDOFF.md`、`research/status/quality_gates.json`、`research/data/V78_24代码历史身份核验台账.csv`、`research/v88_daily_observations/ledger/2026-10-26.json`、`research/v103_forward_preopen/observations/2026-10-26/first_capture.json` 和 V101 开盘前合同。无任何补造上市/退市日期或历史披露时刻。所有输出 RESEARCH_ONLY。

## R1 历史身份：PARTIAL
- 24 条重点异常代码台账已实际读取；14 条 `full_lifecycle_verified=True`，10 条为 False；**24 条 `formal_pit_eligible=False`**。
- 需重点关注同代码多个上市主体及 600018.SH 已知历史特殊片段。原台账未提供全部上市片段的完整独立时点证据，不能自动产生正式 `listing_episodes.csv`。
- 研究代码 `audit.py` 已提交，拒绝重叠主体、上市区间外交易、无证据停牌。
- 云端验收需要查看本 PR `hs-pit-schema-tests.yml` 运行结果；未经实际读取成功日志不宣称其已通过。

## R2 2005 缺日报：BLOCKED_SOURCE_EVIDENCE
- 原 V82 审计：2005 年 242/242 交易日、314838 条原始日线；14665 条候选无日线尚未独立区分停牌与漏源；2584 条特殊身份记录仍需上市主体证据。
- 本轮**没有逐条实际独立核查 14665 条**；故认证通过数维持未确认，不把缺失误报为正常停牌。

## R3 2006 及跨年：RAW_ONLY
- 原 V85：2006 年 241/241、288399 条原始日线，日源哈希已在旧云端研究审计记录；研究仓库仍标 RAW_NOT_PIT。
- `coverage.py` 为可供下一次用真正的 `security_days` 明细和交易日历运行的日期/缺日检查；它不能从总数证明身份、停牌或全市场覆盖。

## R4 数据 09:20 信息截点：BLOCKED_PIT
- V103 2026-10-26 的官方指数尝试：`status=BLOCKED`，请求开始于 06:07:59 UTC，超出当天 09:00—09:20 捕获窗口，`forward_prediction_generated=false`。
- V88 2026-10-26 日线源首次记录于 17:28:51 UTC；此采集时刻不能用于证明历史首次公开时刻。
- 既有 `preopen_clock.py` 及新增 `coverage.py` 的 `feature_gate` 均拒绝 D 日最终日频因子和 D-1 迟发指标；但这只是规则校验，不是独立发布时点证明。

## R5 市场指标复算：BLOCKED_INPUT_UNIVERSE
- 2026-10-26 第三方源记录原始 5570 条，其中交易沪深 5217；不能据此证明完整上市股票池。
- 不能将 2026-10-26 这一日的样本视作正式 C50 或 PIT 宽度；不填造 504/756 日分位历史，也不把 `source_gap` 视为零成交。

## R6 端到端认证与冻结：PARTIAL_CODE_ONLY
- 已提交研究源代码、回归测试、独立 PR 工作流；没有改动 production。`PIT_certified=false`、`formal_training_allowed=false` 保持不变。
- 没有足够原始发布证据及按日身份主表，故本轮**不能提供正式认证 release**；保留证据不足状态，不改变质量门禁文件。

## 后续阻塞所需真实源
1. 每个历史代码的法定上市片段与交替生效日期，特别是复用代码情形；独立于历史行情源。
2. 2005 年 14665 条缺日报记录的当日公告或第二行情源、原始文件 SHA256，逐行归因。
3. 2006 年及后续年份同一口径完整日级上市状态与交易状态。
4. 每个候选历史因子在对应 D 09:20 前真实可见的原始公告或存档记录及 SHA256。

**裁决**：本轮完成 R1—R6 的代码/证据检查和阻塞定位；未完成 R2/R3/R4 所需的独立历史事实认证，因此 R5 正式复算及 R6 PIT release 不得放行。不能把六轮流程执行等同于六轮数据认证成功。
