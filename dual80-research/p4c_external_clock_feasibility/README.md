# P4c 扩大官方家族的披露时钟检索

**结论：`NO_CERTIFIABLE_FAMILY`。** 认证时钟 0/3658。研究日历 2011-08-02 至 2026-08-25 共 3659 日，最后一日没有下一交易日，可认证上限是 3658 日。检索 11 个家族，可认证时钟的家族是 0 个，本轮收集的家族是 0 个。

这一步只回答：现有仓库里的非价格家族已经过了 P4a 和 P4b 之后，官方来源里还有没有一个家族，能拿出发布者自己的、带时区的、严格早于下一研究日上海时间 09:15 的公布时间。`formal_signal_allowed` 仍为 false。没有拟合，没有准入。这不是 PIT，不是盲测，也不是正式信号。

## 时钟规则

时钟必须来自发布者自己的正文，或同一发布者的正式发布时间记录。它要带时区，或者同一份官方证据写明北京时间、北京时或 Asia/Shanghai。观察日必须早于决策日 D。公布时间必须严格早于 `research_inputs.csv` 下一行的上海时间 09:15。最后一日 2026-08-25 没有下一行，不为它编造交易日。

日程、2026 年的下载或捕获时间、HTTP Date、页面生成时间、供应商转载、数据来源、参数“最新”、插值日期，都不是时钟。

## 检索结果

| 家族 | 发布者 | 时钟 | 覆盖 |
|---|---|---|---|
| `northbound_connect` | SSE; HKEX | `NO_CERTIFIABLE_CLOCK` | 样本四日里上交所有一行的日期是 2026-08-25，其余三日 result 为空。港交所 2026-08-25 与 2026-11-06 返回日文件，2014-11-17、2021-09-13、2024-01-02、2025-11-06 为 404。认证 0/3658。 |
| `exchange_market_statistics` | SSE; SZSE | `NO_CERTIFIABLE_CLOCK` | 上交所样本四日里只有 2026-08-25 返回行。深交所数据接口没有连上。认证 0/3658。 |
| `csi_other_daily` | CSI | `NO_CERTIFIABLE_CLOCK` | 抽查 2021-09-13 单日。接口按交易日返回行情。认证 0/3658。 |
| `announcement_disclosure` | cninfo | `NO_CERTIFIABLE_CLOCK` | 2021-09-13 的一页返回 5 条公告，当日公告总数 702。没有收成研究日历上的逐日字段。认证 0/3658。 |
| `futures_options_daily` | SHFE; INE; CFFEX; CZCE; GFEX; DCE | `NO_CERTIFIABLE_CLOCK` | 上期所四个样本日和上海国际能源交易中心 2021-09-13 的日文件已保存。中金所 HTTPS 超时、HTTP 有 CSV。郑商所有当日行情表。广期所页面是壳。大商所 HTTPS 超时、HTTP 412。认证 0/3658。 |
| `news` | SSE | `NO_CERTIFIABLE_CLOCK` | 新闻在需求清单的最低集之外。已保存的是上交所媒体中心列表。认证 0/3658。 |
| `financial_statements` | cninfo | `NO_CERTIFIABLE_CLOCK` | 财报在需求清单的最低集之外。样本与 announcement_disclosure 相同。认证 0/3658。 |
| `macro` | NBS; PBOC | `NO_CERTIFIABLE_CLOCK` | 宏观不是研究日历上的每个交易日都发布。抽查了 2026 年 11 月三篇统计局稿件，2021 年 9 月的旧地址返回 404。认证 0/3658。 |
| `fund_flow` | SSE page scripts; no separate official flow field found | `NO_CERTIFIABLE_CLOCK` | 已保存的上交所查询脚本里没有另一套资金流向接口。认证 0/3658。 |
| `level2` | SSE public-data catalog | `NO_CERTIFIABLE_CLOCK` | 公开数据目录页没有历史 Level-2 的逐日公布时间。认证 0/3658。 |
| `minute_bars` | SSE public-data catalog | `NO_CERTIFIABLE_CLOCK` | 公开数据目录页没有历史分钟线的逐日公布时间。认证 0/3658。 |

各行的缺口写在 `inventory.csv` 的 `blocker` 列。原始正文、URL、HTTP 状态和 SHA256 在 `attempts/`，摘要在 `evidence.json`。

上期所日文件里能看到 `update_date` 和 `print_date`。2011-08-02 的两项都是 2015-06-05 15:33:53 与 2015-06-05 16:10:15，晚于该交易日多年，因此它们记录的是文件更新，不是该日行情的公布时间。其余样本日的钟点也没有时区，已保存的日周数据页和交易时间页没有“北京时间”。

巨潮 2021-09-13 的 `announcementTime` 是整数。正文没有说明时区。这些行是公司公告，不是中证全指的一个交易日字段，所以没有把历史公告全部收进来。

深交所数据接口、中金所 HTTPS、大商所 HTTPS 的传输失败都记在对应的 meta 里。没有换主机，也没有用非官方镜像代替。

## 没有做的事

- 没有改写 `plan.json`。计划在读取这些证据之前已经提交。
- 没有收集任何一个家族的全历史，因为没有任何一个家族通过时钟规则。
- 没有重查融资余额。P4b 已经得到 `CLOCKS_UNAVAILABLE`。没有重跑成交额和 000300/000852。
- 没有把换手率、成分广度、peg、consNumber 或价格变换重新打开。`return3` 和 `change_in_return3` 没有加回。
- 没有拟合分数，没有打开 P2，没有提高阈值。
- 没有写入 `turning-research-canonical/tables/disclosure_timestamps.csv`。
- 没有修改生产页面、采集器或正式信号，没有恢复旧 V 系列。
- P1 仍是 `BLOCKED_NO_CONCENTRATION`。P1b 仍是 `GO_PRE_PIVOT_COORDINATE`。P1c 仍是 `BLOCKED_NO_WINDOW_PEAK`。P1d 仍是 `GO_NEW_FACTORS`。P4a 仍是 `NO_FAMILY_ADMITTED`。P4b 仍是 `CLOCKS_UNAVAILABLE`。

## 复算

在仓库根目录运行：

```text
python -B dual80-research/p4c_external_clock_feasibility/survey.py --offline
```

脚本只读 `plan.json` 和 `attempts/` 里的原始正文，核对计划里的 SHA256，重写本目录的清单、证据、结论和本页。它不联网。`--offline` 与不加参数是同一条路径。原始回执已经保存在 `attempts/`，缺文件时脚本会停，不会补造时点。
