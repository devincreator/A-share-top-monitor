# V94 融资数据精度、来源及PIT门禁（研究版）

## 任务

V92每次最多8个目标交易日补采交易所来源，SHA256及原始数据会永久留存。V94不重复调用行情接口，而是复用这些已保存的来源证据，对**精确上交所元金额**及**深交所亿元显示金额**进行独立审计。

- 交易日来源为V89原始指数观察日的820日窗口；这不等于独立官方交易所PIT交易日历认证。
- 必须对每个V92目标日期检查`raw/SSE`、`raw/SZSE`与`records`的首次SHA256完全一致，字段、身份证据和币种换算符合原始记录。
- 上交所原始人民币元值可记录为来源精确金额；深交所汇总通常只显示亿元的两位小数，不能视作精确元值。
- 对深交所的两位小数亿元，`bounds_audit.py`仅构造**假定“就近舍入或截断”两种规则之一**时的候选上下界。例如`6649.54`亿元映射`[664953500000, 664955000000)`元。没有官方显示规则证据，不能保证这个区间就是最终真实范围。
- 历史交易日期、当下首次取得原始页面的UTC时间、当时官方真实公布时间是三种不同含义。V92原始记录缺少已确认的真实历史`publication_timestamp`，因此所有原本缺失的日期都仍不得自动提升为PIT。
- 对此前不存在的Jin10行不以任何人为插值代替，候选区间不能按中心值喂给需要精确元的正式融资过滤。
- `formal_signal_allowed`和`complete_820_session_financing_history_PIT`恒为`false`。程序绿灯不等于模型四任务达标。

## 自动运行及可复算

V92原有受限交易所缺口采集工作流每次新增来源后，增加本V94质量审计。工作流附件新生成`v92_exchange_batch/v94_bounds_audit.json`，包括按日期状态、双源哈希完整数、条件性区间、冲突与历史信息时点阻塞。

本地测试：

```bash
python -m unittest discover -s research/v94_finance_bounds -p 'test_*.py' -v
python research/v94_finance_bounds/bounds_audit.py \
  --candidate v89_source_audit_output/candidate_inputs.json \
  --ledger research/v92_margin_recovery \
  --out v92_exchange_batch/v94_bounds_audit.json
```

**强制验收：** V94的研究代码只要在已归档源上生成真实、可复算的`PASS/BLOCKED`分项即可视为研究部署成功。完整融资因子正式放行必须另外满足：820日每一天两市原始精度/日期/时点一致、无缺口；任何区间不确定性必须用数学证明无法翻转对应阈值；独立重算历史`finance_growth63`及`finance_accel`两个不同定义。达不到这些要求，研究成果不能升为正式信号。
