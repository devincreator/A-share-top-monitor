# 自动研究进度记录（GitHub Actions）

> 仅代表 **任务执行状态**，不是市场数据历史可得性(PIT)认证，更不是四任务双80成绩。
> 研究数据门禁的唯一授权状态见 [quality_gates.json](../status/quality_gates.json)。

已记录 2 条研究任务完成记录。按最近时间显示前30条。新AI必须查阅失败结果及相应原始附件。

| 完成时间(UTC) | 研究任务 | 运行结论 | 证据 |
|---|---|---|---|
| 2026-10-20T07:42:22Z | Research handoff - verify 2005 release + metadata | success | [查看证据](https://github.com/devincreator/A-share-top-monitor/actions/runs/39388256388) |
| 2026-10-20T07:37:04Z | Research handoff - verify 2005 release + metadata | success | [查看证据](https://github.com/devincreator/A-share-top-monitor/actions/runs/39387666416) |

## 如何接续

1. 先读根目录 [AI_RESEARCH_HANDOFF.md](../../AI_RESEARCH_HANDOFF.md) 与 [执行手册](../NEXT_AI_RUNBOOK.md)。
2. 从 [latest.json](latest.json) 核对任务结论；逐次记录保存在 [runs/](runs/)，包含Jobs和Artifacts链接。
3. 仓库里用于历史数据质量认证的 `research/status/quality_gates.json` **不会**被本工作流自动改为PASS。
4. AI完成聊天内或本地研究（不是Actions）后，必须主动写入带数据证据的完成记录，或用手动触发本进度工作流的 task_title、summary、evidence_url 参数登记。
