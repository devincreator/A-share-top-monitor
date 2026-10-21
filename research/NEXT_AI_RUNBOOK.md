> **2026-10-21执行顺序覆盖旧手册的第1—5步：先按 [E1—E4事件重建与开盘前时钟合同](FOCUS_V97_PREOPEN_EVENT_RECONSTRUCTION.md) 串行操作。D日开盘前预测不能使用D日任何日级指标，D-1及更早数据还必须证明确已公布。当前主动工作只能是事件来源恢复、时点验证、TP/FP/FN重放与误报归因；不得同时新开发融资精度、C50或正式联合模型。旧补源定时维护不算研发新任务。以下历史步骤作为后续待办保留。

# 后续 AI 操作手册（严格按序，勿跳过门禁）

## 0. 第一次运行前先检查

```bash
gh repo view devincreator/A-share-top-monitor
gh run view 39364428554 --repo devincreator/A-share-top-monitor
gh release view research-v82-2005-20261020 --repo devincreator/A-share-top-monitor
```

如果没有 `gh`，直接打开 [GitHub 2006 Actions](https://github.com/devincreator/A-share-top-monitor/actions/runs/39364428554) 和 [2005 Release](https://github.com/devincreator/A-share-top-monitor/releases/tag/research-v82-2005-20261020)。

## 1. 恢复2005数据（不是生产任务）

```bash
gh release download research-v82-2005-20261020 \
  --repo devincreator/A-share-top-monitor --dir recovered_v82
python - <<'PY'
import pathlib, zipfile, hashlib, json
p=pathlib.Path("recovered_v82/v82_2005_raw_242days.zip")
with zipfile.ZipFile(p) as z:
    assert z.testzip() is None
    names=[n for n in z.namelist() if n.startswith("raw/") and n.endswith(".csv")]
    assert len(names)==242, len(names)
    manifest=json.loads(z.read("source_manifest_2005.json"))
    assert len(manifest["file_sha256"])==242
    for n in names:
        day=pathlib.Path(n).stem
        assert hashlib.sha256(z.read(n)).hexdigest()==manifest["file_sha256"][day]
print("2005 original raw data: 242 SHA256 OK, but PIT NOT certified")
PY
```

这仅检验原始数据完整性。GitHub Release中的 `retrospective_master_2026_UNCERTIFIED.csv` 应作问题线索，不可用于独立证明2005每日股票池。

## 2. 恢复2006采集（任务已经发起但未验收）

`gh run view 39364428554 --repo devincreator/A-share-top-monitor --json status,conclusion,jobs`。最终一次查询结论：**2006Q1取消、Q2失败（50/60，缺20060619—20060630）、Q3在获取主表时HTTP429失败、Q4云端任务显示成功**。Q4也必须下载附件检查日级CSV和SHA256，不能把工作流绿灯等于数据门禁。全年目前仍不合格。

```bash
gh run download 39364428554 --repo devincreator/A-share-top-monitor --dir v79_2006_artifacts
```

读取每个附件的 `gate.json`：对每月比对指数交易日历的交易日全集与原始日文件；需要日级SHA256和有效日期列。缺日用现有 `.github/workflows/v78-gap-repair.yml` 工作流的 `workflow_dispatch` 指定单次最多5个日期（不能超过GitHub运行限制），然后合并并重新审计整季。**不能将未完成工作流的状态凭空改成成功**。

## 3. 2005第一轮重点不是调模型，而是身份 + 无日线归因

- 先查 `research/data/V78_24代码历史身份核验台账.csv`；注意此前24只均有历史行情，但有些缺法定起止日。
- 优先核对 `600018.SH`、`000638.SZ`、以及代码延续的 `000022.SZ→001872.SZ`、`000043.SZ→001914.SZ`，发布含公告链接、公告当时可见日、交易生效日、旧ID和新ID的事件表。
- 为每个上市片段指定 `security_listing_id`，关联每一日实际存在的交易记录；不得直接让当前 `symbol` 充当永久不变的上市主体。
- 把2005年14665条回溯候选无日线按另一来源及当日公告分类：`CONFIRMED_SUSPENDED` / `SOURCE_GAP` / `NOT_YET_LISTED` / `DELISTED` / `UNRESOLVED`。保留逐条证据、冲突与覆盖率。除非确有独立证明，不要将剩余 `UNRESOLVED` 自动计作停牌。
- 日线检索及历史发行/退市来源分开校验，避免第三方数据重复引用同一底层源冒充两源。

## 4. 数据认证之后才重新训练

对已证实的股票池，分别构造当天交易股票上涨占比、全部有资格上市股票上涨占比、MA60以上占比、252日新高新低比例。历史复权、停牌交易状态和IPO窗口明确禁止未来数据。

四任务分开评估：5% TOP / BOTTOM各1—10天窗口，9% TOP / BOTTOM各1—20天窗口；同尺度正式报警与拐点严格一对一，事件状态不能重复计通知；检查完整底→顶→底；新模型与原V68价格模型**相同日期、标签、年度训练隔离和年度通知预算**对照。无关的沪深300与中证全指轨道不许直接相加充样本。仍采用事先冻结策略，2022—2026年仅旧研究压力测试，真正前瞻日期从冻结以后开始。

## 5. 每次研发后的GitHub动作

1. 只在研究目录保存新代码、非PIT数据及审计报告，**不要更改生产策略和数据服务**。
2. 对原始CSV保存 `source_uri,retrieved_at,asof_claim,first_date,last_date,rows,sha256`；对重要因子额外保存 `feature_observation_date,publication_date,earliest_usable_date`。
3. 逐批输出 `RAW/RESEARCH/PIT` 三类状态、未解决问题、正式训练是否放行；失败要有错误日志和恢复点。
4. 更新根目录 `AI_RESEARCH_HANDOFF.md` 与 `research/status/quality_gates.json`，提交commit，确实运行测试和复算后附日志，而不是写“执行成功”就算验收。
5. 没有用户明确授权不得将研究模型、参数或未经认证的市场广度部署到当前正式监测网页。

## 6. 主要恢复URL

- [2005原始研究Release](https://github.com/devincreator/A-share-top-monitor/releases/tag/research-v82-2005-20261020)
- [V76 BaoStock错误运行](https://github.com/devincreator/A-share-top-monitor/actions/runs/39356967084)
- [V76 HTTPS成功运行](https://github.com/devincreator/A-share-top-monitor/actions/runs/39357394874)
- [V77 15日限流修复成功](https://github.com/devincreator/A-share-top-monitor/actions/runs/39358137081)
- [V78单日缺口补采成功](https://github.com/devincreator/A-share-top-monitor/actions/runs/39362355495)
- [V79 2006季度矩阵](https://github.com/devincreator/A-share-top-monitor/actions/runs/39364428554)

## 7. 每次结束强制写进度（无需用户催促）

以后每轮/每个任务结束时（包括失败、数据阻塞、限流），**必须在回应用户前保留 GitHub 持久进度**：

- GitHub Actions研究任务：自带 `workflow_run.completed` 自动写入脚本 `research/scripts/progress_autojournal.py` 监听 [工作流](../../.github/workflows/research-progress-autojournal.yml)，产生 `research/progress/runs/<run_id>-attempt-<n>.json`。检查 [进度索引](progress/README.md) 是否产生对应条目。自动记录成功/失败/取消/超时、证据和附件；不自动放行数据质量或双80。
- **不通过GitHub Actions执行的研究（ChatGPT、其他AI本地运行）**：当前聊天完成时**主动用GitHub创建文件接口**写入 `research/progress/manual/YYYYMMDDTHHMMSSZ-<unique>.json`，最少字段 `record_type: manually_reported_research_milestone`、`recorded_at_utc`、`workflow_name`、`conclusion: success|failure|partial|blocked`、`summary`、`evidence_url`、`data_gate`、`dual80_achieved: null`、`next_action`。注意符合JSON，而不是把状态写在聊天里就算同步；push触发索引自动刷新。若已有GitHub运行，也可以手动派发日志工作流并指定 `source_run_id`。
- 核验记录链接、run ID和至少一条真正可读的原始证据。不得把本地计划说成已执行；失败也应留痕。科学评价另改 `research/status/quality_gates.json`（仅证据成立时），不可通过日志工具偷偷修改。

可参照仓库根目录 [AGENTS.md](../../AGENTS.md)，它要求所有后续AI执行这项操作。
