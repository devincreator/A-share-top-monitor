# P4b 融资余额披露时点

**Decision: `CLOCKS_UNAVAILABLE`.** The stored Shanghai and Shenzhen financing balances cover 3659 research dates from 2011-08-02 to 2026-08-25, which is 7318 exchange rows. Certified clocks: 0. Clocks found after the next 09:15 cutoff: 0. Stored official summary receipts, iFinD history, and v92 captures contributed 0 per-row disclosure clocks. Live checks of the pre-registered official sources: sse_2011-08-02 http 200, per-row clocks 0; szse_2011-08-02 transport URLError, per-row clocks 0; sse_2020-07-13 http 200, per-row clocks 0; szse_2020-07-13 transport URLError, per-row clocks 0; sse_2021-09-13 http 200, per-row clocks 0; szse_2021-09-13 transport URLError, per-row clocks 0; sse_2026-08-25 http 200, per-row clocks 0; szse_2026-08-25 transport URLError, per-row clocks 0; sse_html http 200, per-row clocks 0; szse_html http 200, per-row clocks 0; nbd_2021-09-14 http 200, per-row clocks 0. The Shanghai summary payload carries opDate and rzye and no publication time. retrieved_at on the stored receipt wrapper and the HTTP Date header are download times. The SSE page meta 页面生成时间 is the page shell. The 每日经济新闻 pubDate is the article's own time, and the article does not give a per-exchange financing-balance clock. The iFinD column publication_time_certified is false on every stored row. A reconstructed lag was not used. No missing date was interpolated. Financing was not admitted and was not fit. formal_signal_allowed stays false. This is not PIT and not dual-80. P4a remains NO_FAMILY_ADMITTED. P1 remains BLOCKED_NO_CONCENTRATION. P1b remains GO_PRE_PIVOT_COORDINATE. P1c remains BLOCKED_NO_WINDOW_PEAK. P1d remains GO_NEW_FACTORS.

**结论：`CLOCKS_UNAVAILABLE`。** 已保存的沪深融资余额覆盖 2011-08-02 至 2026-08-25 共 3659 个研究日、7318 条交易所行。认证披露时点 0 条。晚于下一交易日 09:15 的时点 0 条。已保存的交易所汇总回执、iFinD 历史和 v92 捕获没有逐行披露时点（逐行时点 0 条）。预先登记的官方来源检查：sse_2011-08-02 http 200, per-row clocks 0; szse_2011-08-02 transport URLError, per-row clocks 0; sse_2020-07-13 http 200, per-row clocks 0; szse_2020-07-13 transport URLError, per-row clocks 0; sse_2021-09-13 http 200, per-row clocks 0; szse_2021-09-13 transport URLError, per-row clocks 0; sse_2026-08-25 http 200, per-row clocks 0; szse_2026-08-25 transport URLError, per-row clocks 0; sse_html http 200, per-row clocks 0; szse_html http 200, per-row clocks 0; nbd_2021-09-14 http 200, per-row clocks 0。上交所汇总正文只有 opDate 和融资余额，没有公布时间。回执外壳上的 retrieved_at 和本次 HTTP Date 是下载时间。上交所页面 meta 里的页面生成时间是页面模板时间。每日经济新闻的 pubDate 是稿件自己的时间，稿件没有给出分交易所的融资余额披露时点。iFinD 列 publication_time_certified 在已保存的每一行都是 false。没有使用重构滞后，也没有插值。融资家族没有准入，也没有拟合。formal_signal_allowed 仍为 false。这不是 PIT，也不是双80。P4a 仍是 NO_FAMILY_ADMITTED。P1 仍是 BLOCKED_NO_CONCENTRATION。P1b 仍是 GO_PRE_PIVOT_COORDINATE。P1c 仍是 BLOCKED_NO_WINDOW_PEAK。P1d 仍是 GO_NEW_FACTORS。

这是披露时点的收集，不是准入，也不是新模型。`formal_signal_allowed` 仍为 false。没有拟合融资分数。P4a 的 `NO_FAMILY_ADMITTED` 不改写，准入门槛不放宽。

## 认证规则

一条时点要同时满足：它是该交易所自己公布该日融资余额的时间；原始回执已保存，并能复核 SHA256；观察日与台账日期一致；时间带时区，或同一份官方证据写明北京时间；它严格早于下一研究日上海时间 09:15。下一研究日只取 `research_inputs.csv` 的下一行。最后一天 2026-08-25 没有下一行，不为它编造交易日。

下载时间、iFinD 历史、`数据来源`、捕获时间、重构滞后、开盘前惯例、新闻稿的发表时间、以及只有交易日没有钟点的字段，都不认证。

## 覆盖

| 项目 | 数量 |
|---|---:|
| 研究日 | 3659 |
| 交易所行（沪、深各一行） | 7318 |
| 认证通过 | 0 |
| 日期范围 | 2011-08-02 至 2026-08-25 |

官方历史披露时点没有落到任何已保存研究日上。传输失败、没有拿到正文：szse_2011-08-02、szse_2020-07-13、szse_2021-09-13、szse_2026-08-25。没有改用镜像或供应商接口。上交所页面生成时间（页面模板，不是逐日披露）：页面生成时间 2023-11-03 14:38:37。新闻稿件自己的时间（不是交易所披露时点，也没有时区）：pubDate=2021-09-14T08:39:25、upDate=2021-09-14T08:39:25、pubDate=2021-09-14T08:38:04。同一页上的 08:39:25 和 08:38:04 都是稿件时间。即便早于 2021-09-14 09:15，也不能认证沪深融资余额。本次响应头里的文件时间，不是历史披露时点：szse_html Last-Modified Sat, 07 Nov 2026 15:09:11 GMT。

台账是 `ledger.csv`。每一行的结论和原因在 `reason` 列。检查过程、键名和原始回执哈希在 `coverage.json`。

## 没有做的事

- 没有把融资余额放进分数，也没有做 63 日变化。
- 没有写入 `turning-research-canonical/tables/disclosure_timestamps.csv`。那是以后的准入文件，本轮不建立。
- 没有把 D 日融资余额当作 D 日开盘前特征。
- 没有修改生产页面、采集器或正式信号，没有恢复旧 V 系列。
- 没有改写 P1、P1b、P1c、P1d、P4a 的结论。
- 不声称 PIT，不声称双80。

## 复算

```text
python -B dual80-research/p4b_financing_clocks/certify.py
```

`plan.json` 在取证之前写定。脚本只读计划，不改写它。再次运行会复用 `attempts/` 里已经保存的原始正文；`--refetch` 才会重新请求。
