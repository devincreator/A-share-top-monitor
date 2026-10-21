> **用户最新执行偏好（2026-10-21）**：V97研发自行规划、执行与验收，**不主动发送研究日报或通知**。已启用每日静默研究自动任务及只读GitHub定时历史证据扫描；每次研究仅写GitHub研究证据和质量门禁。若真实原始FORMAL_START缺失，不得从事后拐点反推报警，也不得开展未经来源时点认证的正式TP/FP/FN回测；不得修改生产版。触发GitHub Actions成功仅说明采集/测试代码成功，不说明E1科学门禁已通过。

> **当前唯一主动研究任务（2026-10-21）：** [V97真实事件重建与严格开盘前时钟](research/FOCUS_V97_PREOPEN_EVENT_RECONSTRUCTION.md)。除真实预警事件恢复、时点审计、成熟事件回测和误报归因外，暂不主动新开发其他模型或因子。**在D交易日开盘前预测，D日各项日级指标全部未知；D-1及更早指标也必须核查披露时间已经不晚于决策时刻。** 禁止在因果特征、市场阶段归因中引用D日收盘，禁止把旧V63聚合回测成绩等同于preopen成绩。所有后续AI必须按此覆盖下面旧版多阶段顺序。

# AGENTS.md — 后续 AI / 自动化接手规则（2026-10-20）

## 每次开始研究前

必须先读取 [AI_RESEARCH_HANDOFF.md](AI_RESEARCH_HANDOFF.md)、[research/NEXT_AI_RUNBOOK.md](research/NEXT_AI_RUNBOOK.md)、[research/status/quality_gates.json](research/status/quality_gates.json) 和 [research/progress/README.md](research/progress/README.md)。

**2026-10-20 基线**：四个顶底任务的正式信号精确率与拐点覆盖率尚未达到双80。2005年242个交易日原始文件核验完成；2005历史证券身份和缺行情/停复牌的时点真实性未通过门禁；2006全年尚未完整验收。禁止编造数据已通过PIT认证、正式模型成绩、未知工作流结果。

## 每次研究结束后，必须写入GitHub进度

**一项任务做完（包括失败、阻塞、部分完成），必须在同一轮工作结束前留下持久记录。**

### 任务由 GitHub Actions 运行

进度工作流 [Research progress auto journal](.github/workflows/research-progress-autojournal.yml) 在**已登记的研究工作流完成**后，自动把真实的 `success/failure/cancelled/timed_out`、Job信息、附件链接、Run ID、commit等保存到 [research/progress/runs/](research/progress/runs/)，并更新 [进度索引](research/progress/README.md) 与 `latest.json`。

自动日志**仅认证任务运行状态**；GitHub显示绿灯 ≠ 数据质量通过 ≠ 模型精确率达到80%。不可让自动日志擅自修改 `quality_gates.json` 为PASS。

如果研究工作流名称或文件命名体系升级，需同时检查该自动记录工作流的 `on.workflow_run.workflows` glob及 Python `ELIGIBLE_PATH` 的涵盖范围。

### 任务由 AI 在聊天或本地执行（不属于 GitHub Actions）

**不存在自动感知聊天外部执行的后台守护进程。** 接手AI在本任务完成时，**必须主动写入** `research/progress/manual/YYYYMMDDTHHMMSSZ-<short-id>.json`（用 GitHub 文件创建API、git push或相应连接器）。该文件**至少**包含：

```json
{
  "record_type": "manually_reported_research_milestone",
  "recorded_at_utc": "2026-10-20T08:00:00Z",
  "workflow_name": "V83: 本轮具体目标",
  "conclusion": "success|failure|blocked|partial",
  "summary": "实际做了什么，数据量与真实计算指标，不编造",
  "evidence_url": "https://github.com/devincreator/A-share-top-monitor/issues/1",
  "data_gate": "RESEARCH_ONLY|BLOCKED|PIT_CERTIFIED",
  "dual80_achieved": null,
  "next_action": "下轮具体步骤"
}
```

手动文件写入会触发自动进度索引刷新工作流。也可手动运行上述进度工作流 `workflow_dispatch`，用 `task_title`、`summary`、`evidence_url` 等记录；手工记录仍属于**待独立验证**。

**无论成功还是失败，都要写进度；不得只回复用户完成而不持久写入。** 如果写入GitHub失败，用户答复中必须明确指出同步失败，保留本地证据，绝不假称自动同步成功。

### 真实质量门禁更新

- 如果严谨的审计确实改变数据来源/PIT门禁，**另外更新** `research/status/quality_gates.json` 与相应报告；自动进度日志永不代替学术/金融数据认证。
- 每轮记录输入版本/原始文件SHA256、运行日期、测试次数、成功或失败的证据URL、是否独立样本、正式通知数/命中数/成熟拐点数、遗留问题、下一项待办。
- 只在 `research/` 或独立研究工作流做更改。**未经用户明确允许，不改生产 `app.html`、`index.html`、`collector/`、`assets/`、`data/`。**

## 接手提示

交接从根目录开始：`AI_RESEARCH_HANDOFF.md → research/NEXT_AI_RUNBOOK.md → research/progress/README.md → research/status/quality_gates.json`。

2005年原始数据永久归档在 [V82 Release](https://github.com/devincreator/A-share-top-monitor/releases/tag/research-v82-2005-20261020)。继续研发优先读取 [V83跟踪Issue](https://github.com/devincreator/A-share-top-monitor/issues/1)。
