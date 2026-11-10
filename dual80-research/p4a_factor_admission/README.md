# P4a 非价格因子准入：先看披露时点，再决定是否允许比较

**Decision: `NO_FAMILY_ADMITTED`.** No candidate has a structured disclosure timestamp on every research session, with observation_date strictly before D and the clock strictly before 09:15 Asia/Shanghai on D. Financing covers the 3659 sessions in the provider table, and its lineage statuses are PROVIDER_HISTORY_NOT_PIT 3659 and PROVIDER_HISTORY_REACQUIRED_NOT_PIT 3659. The exchange capture covers 34 sessions, PIT_certified values are False 68, capture-clock fields are first_captured_at_utc 64, source_run_started_at_utc 4, and those clocks run from 2026-10-21T03:55:49Z to 2026-10-26T08:48:48.991185+00:00; 0 of those capture times fall before the next pre-open, and a capture time would not count as disclosure anyway. Turnover is historical_publication_times_certified=False, constituents independently verified=False, and both the native-rate request and a float-A repair still say 最新. Market-breadth filename search found no files. Index amount and the 000300/000852 controls are OFFICIAL_HISTORY_NOT_PIT; the 000985 receipt clock is 2026-10-30T08:04:37.740882+00:00 to 2026-10-30T08:04:39.744425+00:00. Amount and style were already compared and are not re-run: 5_TOP price 23.6%/44.7% versus amount+style 18.3%/39.5%; 5_BOTTOM price 33.9%/51.3% versus amount+style 31.1%/48.7%; 9_TOP price 15.2%/38.9% versus amount+style 20.5%/50.0%; 9_BOTTOM price 15.7%/42.1% versus amount+style 17.3%/47.4%. The displayed baseline stayed on the price group. Official peg and consNumber are unused raw fields on that same receipt. The next step is to collect certified per-session disclosure timestamps for the Shanghai and Shenzhen financing balances. That collection is not done here. No family was fit. formal_signal_allowed stays false. This is not PIT, not a blind test, and not a signal. P1 remains BLOCKED_NO_CONCENTRATION. P1b remains GO_PRE_PIVOT_COORDINATE. P1c remains BLOCKED_NO_WINDOW_PEAK. P1d remains GO_NEW_FACTORS.

**结论：`NO_FAMILY_ADMITTED`。** 没有任何候选家族在全部研究日上带有结构化披露时点，并且观察日严格早于 D、时钟严格早于 D 日上海时间 09:15。融资余额的供应商表覆盖 3659 个研究日，谱系状态是 PROVIDER_HISTORY_NOT_PIT 3659 和 PROVIDER_HISTORY_REACQUIRED_NOT_PIT 3659。交易所原始捕获覆盖 34 个交易日，PIT_certified 的取值是 False 68，捕获时钟字段是 first_captured_at_utc 64, source_run_started_at_utc 4，时间从 2026-10-21T03:55:49Z 到 2026-10-26T08:48:48.991185+00:00；其中 0 个捕获时间早于下一交易日开盘前，而且捕获时间本来就不是披露时点。换手率的 historical_publication_times_certified 是 False，历史成分独立认证是 False，原生换手率请求和一份流通 A 股修复回执仍然写着“最新”。市场广度文件名检索没有命中文件。成交额和 000300/000852 对照的谱系是 OFFICIAL_HISTORY_NOT_PIT；000985 回执时钟是 2026-10-30T08:04:37.740882+00:00 到 2026-10-30T08:04:39.744425+00:00。 成交额和风格已经比较过，本轮不重跑：5_TOP price 23.6%/44.7% versus amount+style 18.3%/39.5%; 5_BOTTOM price 33.9%/51.3% versus amount+style 31.1%/48.7%; 9_TOP price 15.2%/38.9% versus amount+style 20.5%/50.0%; 9_BOTTOM price 15.7%/42.1% versus amount+style 17.3%/47.4%。展示基线仍是价格组。官方回执上的 peg 和 consNumber 没有被研究代码用作特征。 下一步是为沪深融资余额收集逐日、带时区、并且早于下一交易日 09:15 的披露时点。这一步没有实施。没有拟合任何家族。 formal_signal_allowed 仍为 false。这不是 PIT，不是盲测，也不是信号。 P1 仍是 BLOCKED_NO_CONCENTRATION。P1b 仍是 GO_PRE_PIVOT_COORDINATE。P1c 仍是 BLOCKED_NO_WINDOW_PEAK。P1d 仍是 GO_NEW_FACTORS。

这是准入审计，不是新模型。`formal_signal_allowed` 仍为 false。没有 PIT 认证，没有盲测，没有生产信号。P1、P1b、P1c、P1d 的结论不改写，门槛不放宽。

## 预登记的门禁

观察日必须严格早于决策日 D。披露时点必须带时区，并且严格早于 D 日上海时间 09:15，也就是开盘集合竞价开始、连续竞价 09:30 之前。只有 CSV 列名或 JSON 键名落在预登记名单里，才算结构化披露时点。下载时间、请求时间、参数“最新”、谱系里的 NOT_PIT、交易所名称和序列起止日期都不算。

融资、换手率、市场广度没有豁免。000300 和 000852 仍然只是风格对照，不能改成正式目标。成交额和风格已经在 `label_clock_v4` 的 `price_amount_style` 里比较过，本轮只引用那张表，不重新拟合。缺文件、缺时点、只有一段时间的样本，默认都是 `RESEARCH_ONLY`。通过门禁的家族最多一个，顺序是融资余额、换手率、市场广度。

## 库存

| 家族 | 角色 | 状态 | 阻断 |
|---|---|---|---|
| `financing_balance` | candidate | `RESEARCH_ONLY` | NO_DISCLOSURE_COLUMN、LINEAGE_NOT_PIT、POLICY_PIT_FALSE、VENDOR_REPRINT_NOT_A_CLOCK、PARTIAL_COVERAGE、MISSING_FILE、AFTER_CLOSE_DERIVED |
| `turnover_rate` | candidate | `RESEARCH_ONLY` | POLICY_PIT_FALSE、CONSTITUENT_SCOPE_UNCERTIFIED、LATEST_PARAMETER、NO_DISCLOSURE_COLUMN、VENDOR_FORMULA_UNRESOLVED |
| `market_breadth` | candidate | `RESEARCH_ONLY` | MISSING_FILE、CONSTITUENT_SCOPE_UNCERTIFIED、NOT_THE_DOCUMENTED_BREADTH |
| `index_trading_amount` | cited_already_compared | `CITED_NOT_RERUN` | LINEAGE_NOT_PIT、CAPTURE_TIME_NOT_DISCLOSURE、NO_DISCLOSURE_COLUMN |
| `style_index_controls` | control_not_a_target | `CONTROL_NOT_A_TARGET` | LINEAGE_NOT_PIT、CAPTURE_TIME_NOT_DISCLOSURE、NO_DISCLOSURE_COLUMN、CONTROL_NOT_TARGET、BACKCAST_NOT_THEN_KNOWN |
| `official_peg` | raw_field_not_used | `NOT_A_CANDIDATE` | RAW_FIELD_UNUSED |
| `official_constituent_count` | raw_field_not_used | `NOT_A_CANDIDATE` | RAW_FIELD_UNUSED |
| `price_transforms` | excluded_price_family | `NOT_A_CANDIDATE` | EXCLUDED_PRICE_FAMILY |
| `named_outside_minimum_set` | out_of_scope | `NOT_A_CANDIDATE` | OUT_OF_SCOPE |

## 缺的证据

| 家族 | 阻断 | 查过的路径 | 看到的结果 |
|---|---|---|---|
| `index_trading_amount` | `LINEAGE_NOT_PIT` | `turning-research-canonical/tables/field_lineage.csv` | {'OFFICIAL_HISTORY_NOT_PIT': 3659}。turnover lineage status counts are {'OFFICIAL_HISTORY_NOT_PIT': 3659} |
| `index_trading_amount` | `CAPTURE_TIME_NOT_DISCLOSURE` | `turning-research-canonical/raw/official/000985_20110802_20260825.receipt.json` | 2026-10-30T08:04:37.740882+00:00 -> 2026-10-30T08:04:39.744425+00:00。Receipt clocks are the 2026 download, not a historical disclosure time. |
| `index_trading_amount` | `NO_DISCLOSURE_COLUMN` | `turning-research-canonical/raw/official/000985_20110802_20260825.response.json` | none。Row keys are tradeDate, indexCode, indexNameCnAll, indexNameCn, indexNameEnAll, indexNameEn, open, high, low, close, change, changePct, tradingVol, tradingValue, consNumber, peg. tradeDate is the session date. |
| `style_index_controls` | `LINEAGE_NOT_PIT` | `turning-research-canonical/tables/field_lineage.csv` | {'OFFICIAL_HISTORY_NOT_PIT': 3659}。hs300_close lineage status counts are {'OFFICIAL_HISTORY_NOT_PIT': 3659} |
| `style_index_controls` | `LINEAGE_NOT_PIT` | `turning-research-canonical/tables/field_lineage.csv` | {'OFFICIAL_HISTORY_NOT_PIT': 3659}。zz1000_close lineage status counts are {'OFFICIAL_HISTORY_NOT_PIT': 3659} |
| `style_index_controls` | `CAPTURE_TIME_NOT_DISCLOSURE` | `turning-research-canonical/raw/official/000300_20110802_20260825.receipt.json` | 2026-10-30T08:05:39.314049+00:00 -> 2026-10-30T08:05:41.322073+00:00。Receipt clocks are the 2026 download, not a historical disclosure time. |
| `style_index_controls` | `NO_DISCLOSURE_COLUMN` | `turning-research-canonical/raw/official/000300_20110802_20260825.response.json` | none。Row keys are tradeDate, indexCode, indexNameCnAll, indexNameCn, indexNameEnAll, indexNameEn, open, high, low, close, change, changePct, tradingVol, tradingValue, consNumber, peg. tradeDate is the session date. |
| `style_index_controls` | `CAPTURE_TIME_NOT_DISCLOSURE` | `turning-research-canonical/raw/official/000852_20110802_20260825.receipt.json` | 2026-10-30T08:05:39.314874+00:00 -> 2026-10-30T08:05:41.207522+00:00。Receipt clocks are the 2026 download, not a historical disclosure time. |
| `style_index_controls` | `NO_DISCLOSURE_COLUMN` | `turning-research-canonical/raw/official/000852_20110802_20260825.response.json` | none。Row keys are tradeDate, indexCode, indexNameCnAll, indexNameCn, indexNameEnAll, indexNameEn, open, high, low, close, change, changePct, tradingVol, tradingValue, consNumber, peg. tradeDate is the session date. |
| `index_trading_amount` | `ALREADY_COMPARED` | `dual80-research/label_clock_v4/rank_metrics.csv` | cited。price_amount_style was already compared and did not replace the displayed price baseline. Not re-run. |
| `style_index_controls` | `CONTROL_NOT_TARGET` | `ACTIVE_RESEARCH_CONTRACT.json` | 000985.CSI, whole-market research; 000300/000852 style controls, not substituted by retrospective scores。000300 and 000852 stay style controls. They are not a new official target. |
| `style_index_controls` | `BACKCAST_NOT_THEN_KNOWN` | `turning-raw-reacquired/data_dictionary.json` | 000852 null consNumber 775 of 3660。The dictionary says pre-publication backcast values do not prove the level was known then. |
| `financing_balance` | `NO_DISCLOSURE_COLUMN` | `turning-research-canonical/tables/research_inputs.csv` | none。Main-table columns are date, closes, turnover (amount), turnover_rate, financing_balance. |
| `financing_balance` | `NO_DISCLOSURE_COLUMN` | `turning-raw-reacquired/tables/financing_sh_sz.csv` | none。Columns are date, balance_sh_yuan, balance_sz_yuan. Date coverage is 2011-08-02 to 2026-08-25, 3659 rows. |
| `financing_balance` | `LINEAGE_NOT_PIT` | `turning-research-canonical/tables/field_lineage.csv` | {'PROVIDER_HISTORY_NOT_PIT': 3659}。Canonical financing lineage is not a disclosure clock. |
| `financing_balance` | `LINEAGE_NOT_PIT` | `turning-raw-reacquired/tables/field_lineage.csv` | {'PROVIDER_HISTORY_REACQUIRED_NOT_PIT': 3659}。Reacquired financing lineage is not a disclosure clock. |
| `financing_balance` | `POLICY_PIT_FALSE` | `turning-research-canonical/source_policy.json` | False。The source policy says the adopted fields are not PIT-certified. |
| `financing_balance` | `VENDOR_REPRINT_NOT_A_CLOCK` | `A-share-top-monitor-history/ifind_financing` | 20 raw files; disclosure hits 0。Keys include 数据来源 plus 起始日期 and 终止日期. Those name a source and a coverage bound. |
| `financing_balance` | `PARTIAL_COVERAGE` | `A-share-top-monitor-history/research/v92_margin_recovery/records` | 34 of 3659 sessions。PIT_certified values are {'False': 68}. Capture-clock fields are {'first_captured_at_utc': 64, 'source_run_started_at_utc': 4}. Those clocks span 2026-10-21T03:55:49Z to 2026-10-26T08:48:48.991185+00:00. Capture times before the next pre-open: 0. |
| `financing_balance` | `NO_DISCLOSURE_COLUMN` | `A-share-top-monitor-history/research/v92_margin_recovery/raw` | SSE: ['信用交易日期,融资余额,融资买入额,融券余量,融券余量金额,融券卖出量,融资融券余额']; SZSE: ['融资买入额,融资余额,融券卖出量,融券余量,融券余额,融资融券余额']。CSV counts {'SSE': 34, 'SZSE': 34}. The SSE header starts with 信用交易日期, which is the observation date. The SZSE header has no date column; the date is the filename. Neither header has a disclosure timestamp. Same-day flow columns on this short window are not a separate family. |
| `financing_balance` | `MISSING_FILE` | `turning-research-canonical/tables/disclosure_timestamps.csv` | absent。Need one Shanghai row and one Shenzhen row per research date, with a timezone-aware disclosure timestamp before the next 09:15 Asia/Shanghai pre-open. |
| `turnover_rate` | `POLICY_PIT_FALSE` | `turning-research-canonical/turnover_selection_audit.json` | False。historical_publication_times_certified is false. |
| `turnover_rate` | `CONSTITUENT_SCOPE_UNCERTIFIED` | `turning-research-canonical/turnover_selection_audit.json` | False。The float-A denominator was not rebuilt from a certified constituent list. Timestamps alone would not admit this family. |
| `turnover_rate` | `LATEST_PARAMETER` | `turning-research-canonical/raw/turnover/ifind_definition_request.json` | True。The native-rate definition request still carries 交易日期 = 最新. |
| `turnover_rate` | `LATEST_PARAMETER` | `turning-research-canonical/raw/turnover/float_a_history/repair_2020-03-17_2020-03-17.json` | True。A float-A repair receipt still carries 截止日期 = 最新. |
| `turnover_rate` | `NO_DISCLOSURE_COLUMN` | `turning-research-canonical/tables/research_inputs.csv` | none。turnover_rate is populated on the main table. Population is not a disclosure clock. The official tradingVol numerator is on the same 2026 official receipt as tradingValue. |
| `turnover_rate` | `VENDOR_FORMULA_UNRESOLVED` | `turning-research-canonical/README.md` | sentence present。The project-selected rate is not the vendor native formula, and that native formula is unresolved. The README says publication time and revision history were not certified. |
| `market_breadth` | `MISSING_FILE` | `(filename search)` | none。No constituent, breadth, C50, advance/decline, new-high, new-low, or halt file is in the repository. |
| `market_breadth` | `CONSTITUENT_SCOPE_UNCERTIFIED` | `A-share-top-monitor-history/完整数据需求清单.md` | sentence present。Stock-level bars, the security master, and halt status are documented as not fully accepted. Today’s survivors must not be backfilled. |
| `market_breadth` | `NOT_THE_DOCUMENTED_BREADTH` | `turning-research-canonical/raw/official/000985_20110802_20260825.response.json` | consNumber nulls 0。consNumber is a constituent count on the official row, not an advance share or a new-low share. |
| `official_peg` | `RAW_FIELD_UNUSED` | `turning-research-canonical/raw/official/000985_20110802_20260825.response.json` | python mentions excluding this audit: none。peg is a row key. Disclosure keys: none. Null peg rows: 000985 54, 000300 54, 000852 221. |
| `official_constituent_count` | `RAW_FIELD_UNUSED` | `turning-research-canonical/raw/official/000985_20110802_20260825.response.json` | python mentions excluding this audit: none。consNumber is unused as a feature and has no disclosure key. It does not stand in for market breadth. |
| `price_transforms` | `EXCLUDED_PRICE_FAMILY` | `dual80-research/p1d_fire_timing/decision.json` | GO_NEW_FACTORS。Price transforms stay inside the frozen price family. This phase does not refit them and does not add the two fast features back. |
| `named_outside_minimum_set` | `OUT_OF_SCOPE` | `A-share-top-monitor-history/完整数据需求清单.md` | none。News, financial statements, macro, fund flow, level-2, and minute bars are named as outside the current minimum set. |
| `financing_balance` | `AFTER_CLOSE_DERIVED` | `turning-rebuild/sources/a_share_5_9_daily_reconstruction.csv` | header only。finance_63d_growth_p756_pct, turnover_amt_p252_pct, turnover_rate_p252_pct, and style_dd20_pct are transforms of families already inventoried. prepare_data.py marks that construction AFTER_CLOSE and not D-day pre-open. |

## 已经比较过的成交额和风格

下表是 `label_clock_v4/rank_metrics.csv` 里收盘标签、`past_rank90` 的原有结果。本轮没有重算。

| 任务 | 价格组 精确率/覆盖率 | 价格+成交额+风格 精确率/覆盖率 |
|---|---:|---:|
| 5_TOP | 23.6% / 44.7% | 18.3% / 39.5% |
| 5_BOTTOM | 33.9% / 51.3% | 31.1% / 48.7% |
| 9_TOP | 15.2% / 38.9% | 20.5% / 50.0% |
| 9_BOTTOM | 15.7% / 42.1% | 17.3% / 47.4% |

5% 两项的精确率和覆盖率都低于价格组。9% 两项都高于价格组。当时的规则是四项任务不分别挑赢家，展示基线留在价格组。这个对照不是本轮的准入门槛，也不构成重新拟合的理由。四项都没有双80。

## 下一步，本轮不实施

收集沪深融资余额的逐日披露时点。每个研究日、每一边交易所一行，字段是观察日、字段名、带时区的披露时点，并且该时点必须早于下一交易日上海时间 09:15。不要把 2026 年的捕获时间、iFinD 转载、`数据来源` 或一小段交易所文件当成这个表。换手率还差成分范围认证，所以只有时点也不够。广度还没有成分、停牌和涨跌文件，不能用今天的存续名单回填。成交额和风格不重新开题。

## 没有做的事

- 没有拟合融资、换手率、广度或任何其他家族，也没有搜索第二种变换。
- 没有重跑 `price_amount_style`，没有重训六个价格特征，没有把 3 日收益或 3 日收益变化加回。
- 没有实现提前发报，没有打开 P2，没有提高分位，没有用未来目标数做警报配额。
- 没有更换标签或指数，没有把 D 日行情写进当日特征。
- 没有下载新数据，没有修改生产页面、采集器、正式信号，也没有恢复旧 V 系列。
- 不声称双80，不声称 PIT，不声称这是盲测。

## 复算

```text
python -B dual80-research/p4a_factor_admission/audit.py --write-plan-only
python -B dual80-research/p4a_factor_admission/audit.py
```

缺少 `plan.json` 时审计会停止。`--write-plan-only` 只在文件不存在时写出计划，不解释来源字段。计划写出之后不再改写。
