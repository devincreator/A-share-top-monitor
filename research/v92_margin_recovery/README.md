# V92 分批核对交易所融资历史缺口（自动研究，不发交易信号）

## 研究目的

V90于2026-10-20为止的820个中证全指观察交易日中，金十沪深融资数据缺182日，且深圳`2024-08-08`原始值为0，造成过去756个融资增长率样本中267个值无法准确计算。V91云端五日抽检在三段缺口分别获取上交所、深交所候选汇总数据（但2024-08-08深圳首次连接失败，近日报价也有源间差异）。

V92不伪造这些记录、不删除交易日凑窗口，而是逐日**读取交易所来源原始汇总**，长期积累可验证证据。该工作流不能认证历史可见性，也不能自动修改任何正式策略。

## 取数策略

- 每次读取最新一次实际成功V89原始源附件`candidate_inputs.json`，以`000985.CSI`最近820个观察交易日为基准，找到金十未给出或融资余额不合法的日期，目标初始约183日。
- 每次最多8个日期，逐个调用AKShare的交易所汇总接口，不发起182日高并发请求。针对网络临时断连最多重试3次，研究任务可单独失败并记录原因。
- 已有上海+深圳首次原始数据且SHA256可读的日期，不再次补入。没有成功的交易所延后重试，单日失败不会阻挡其余日期。
- 每日研究触发为北京时间工作日11:15；可由`workflow_dispatch`手动启动；实际运行时间由GitHub Actions决定。
- 成功原始CSV及日期/交易所元数据**永久提交到仓库**，路径为`research/v92_margin_recovery/raw/{SSE,SZSE}/YYYY-MM-DD.csv`和`research/v92_margin_recovery/records/YYYY-MM-DD/{SSE,SZSE}.json`，首次写入不可覆盖。每次请求的成功或失败记录保存在`attempts/YYYY-MM-DD/<run_id>.json`。原始任务附件另保留30天。
- 自动记录新来源证据，不等于因子验收通过。上交所报元，深交所报**亿元**且通常仅2位小数，无法自动替换需要精确元数值的原始模型输入。深交所汇总仅由请求参数关联日期时，标记`REQUEST_PARAMETER_ONLY`，不宣称独立完成PIT公告时点证明。

## 质量门禁

即使某日期沪深两市都获得候选数据，仍需逐项完成：官方日期归属、原始精度、源间差异、官方公布时间、完整820交易日窗口、历史排名不含当日及同口径复现旧版公式。缺任何一项时`PIT_certified=false`、`formal_signal_allowed=false`。不将候选融资金额合入生产`data/latest_state.json`，不发布新TOP/BOTTOM信号。

## 验证方法

```bash
python -m unittest discover -s research/v91_exchange_margin -p 'test_*.py' -v
python -m unittest discover -s research/v92_margin_recovery -p 'test_*.py' -v
python research/v92_margin_recovery/recover_batch.py \
  --candidate v89_source_audit_output/candidate_inputs.json \
  --ledger research/v92_margin_recovery --out v92_exchange_batch \
  --max-dates 8 --retry-days 2
```

[云端运行入口](../../.github/workflows/v92-margin-gap-catchup.yml)。

## 新增独立来源完整性审计

`audit_coverage.py`在每一轮受控采集后重新读取已经永久保存的每一份交易所原始CSV，与首次`records`中的SHA256、源交易日期（仅沪市响应内置）、单位、余额值、身份证据和未放行的PIT标志进行逐项比对。将各类日期明确区分为**双来源有原始证据**、仅单来源和仍未取到的日期。每轮云端执行生成永久`checkpoints/YYYY-MM-DD/<run_id>.json`，保留首次证据与研究覆盖的推进过程，绝不因代码改动自动改写首次取数。即使全部183日补采完成，如果SZSE值精度、日期或发布时点未获独立验证，仍必须保持`finance_growth63_prior756_rank_certified=false`。
