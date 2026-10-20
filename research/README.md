# 量化研究资料索引：V52—V82（2026-10-20）

**先读仓库根目录 [AI_RESEARCH_HANDOFF.md](../AI_RESEARCH_HANDOFF.md)。**

## 目录与入口

| 类型 | 路径或链接 | 说明 |
|---|---|---|
| 总交接 | [../AI_RESEARCH_HANDOFF.md](../AI_RESEARCH_HANDOFF.md) | 四任务目标、当前状态、风险和后续步骤 |
| 机器状态 | [status/quality_gates.json](status/quality_gates.json) | 各项是否可正式入模 |
| 原版审计 V63—V68 | [reports/V63_V68_实测报告.md](reports/V63_V68_实测报告.md) | 长期指数、四任务实际成绩 |
| 原版审计 V69—V75 | [reports/V69_V75_实测报告.md](reports/V69_V75_实测报告.md) | 第三方汇总广度失真和受控消融 |
| 原版审计 V78—V82 | [reports/V78_V82_实测报告.md](reports/V78_V82_实测报告.md) | 2005年股票身份/停牌与未认证广度 |
| 完整研究ZIP保留状态 | [LEGACY_REPRO_PACKAGES.md](LEGACY_REPRO_PACKAGES.md) | 旧版完整二进制ZIP未全部进入GitHub，列出准确SHA256与恢复条件 |
| 数据质量 | [DATA_PROVENANCE_AND_GATES.md](DATA_PROVENANCE_AND_GATES.md) | 来源、不可混用口径和禁止泄漏 |
| 恢复执行 | [NEXT_AI_RUNBOOK.md](NEXT_AI_RUNBOOK.md) | 接手后顺序操作、实际验证、失败恢复 |
| 2005研究CSV | [data/](data/) | 2005年242日研究表，标题后缀标明不能正式使用 |
| 历史原始CSV完整备份 | [GitHub研究Release](https://github.com/devincreator/A-share-top-monitor/releases/tag/research-v82-2005-20261020) | 242日原始逐股行情ZIP、原样SHA256清单、回溯主表、逐股异常身份证据（查看Release实际附件） |
| 2006续采 | [Actions运行39364428554](https://github.com/devincreator/A-share-top-monitor/actions/runs/39364428554) | 四季度矩阵；**不可因触发了就宣称下载完成** |

## 与生产隔离

所有新研究材料均位于 `research/` 或单独 `.github/workflows/`。不要自动改写根 `app.html`、`collector/`、`assets/`、`data/`，也不要自动将研究指标推送到正式可视化网页。数据截至日期不代表模型训练/盲测截止日期。

## 对后续AI的要求

每次先读取机器状态和最新GitHub Actions真实结论，再落盘新的原始/清洗数据。每轮给出**输入、样本量、SHA256、数据门禁、执行命令、正式通知次数、命中次数、成熟端点数、是否真正前瞻**。质量不通过就记录BLOCKED，而不是以新版本号替代验证。

## 每次做完会自动更新进度

- [实时研究进度索引](progress/README.md)：研究 Actions 工作流完成（含失败）后自动追加。
- [最新一项研究完成记录](progress/latest.json)：机器可读，用于下一位 AI 恢复工作。
- [强制交接约定](../AGENTS.md)：聊天/本地完成的任务必须由执行AI主动提交 `research/progress/manual/`，然后自动刷新索引。只有 GitHub 工作流有自动完成事件；聊天任务没有后台可自动感知。
- 日志成功不等于数据门禁通过，正式质量认证仍以 `status/quality_gates.json` 和审计证据为准。
