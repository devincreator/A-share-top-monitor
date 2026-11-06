# 沪深历史研究数据按年归档（2006—2026）

**2026-10-27 实际导入结果：** 2026 年 73 个逐日 CSV、378609 条沪深股票记录，源文件下载/格式检查错误 0；GitHub Actions [40460536466](https://github.com/devincreator/A-share-top-monitor/actions/runs/40460536466) 成功。上游为 `guidebee/china-stock-data`，导入后按 `sh/sz` 代码过滤北交所，每日保存源原始 SHA256、Git blob SHA、筛选后 SHA256、URI 和行数，证据索引在 `import_result.json`。

## 年份
- `2006/manifest.json`：指向本仓库 V85 已有 **241 日原始 ZIP Release**，原始文件没有重复塞进 Git 树；RAW完整性已验收，上市身份及披露 PIT 未通过。
- `2007/—2025/`：已创建逐年 `manifest.json`；新导入的逐股 CSV 数量为 0，**仅表示这次选定的外部 GitHub 来源未覆盖，不能推断这些年份无数据**。部分其他原始数据可能仍在旧 Releases 或研究附件。
- `2026/daily/YYYY-MM-DD.csv`：本轮实际导入的 73 天研究级原始来源筛选副本；其中 `manifest.json` 给出每个源的双 SHA256。

## 不能宣称的内容
- 并非 2006—2026 的完整连续逐股日线，没有校验全部官方交易日，也没有纳入停牌的零交易/缺报上市证券；
- GitHub 提供者的文件不等于交易所官方历史、也不保证全部退市企业、证券同码历史主体及复权口径；
- `2026` 实际文件为第三方事后日频数据，不是 D 日 09:20 前可观测数据；`PIT_certified=false`；
- 其他仓库即使声称从 2016 起全量覆盖，本次检查当前 Git 树尚不能独立证实其实际 CSV 已齐，故不将其标为已下载。

## 复跑
`python research/hs_pit_audit/import_public_yearly.py --out research/historical_data`（需要外网）；或手动运行研究 Actions `hs-import-github-yearly.yml`。源码只写研究分支，不修改生产网页、正式信号或既有数据源。所有 PIT 认证仍由 `research/status/quality_gates.json` 控制。
