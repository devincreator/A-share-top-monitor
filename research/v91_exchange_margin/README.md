# V91 交易所融资余额：缺口逐日核验（研究探针）

## 为什么要另开来源

V90对`000985.CSI`最近820个价格指数观察交易日核对金十融资：2026-10-20前最近64/253日的历史表面完整，但长期分位必需的820日窗口存在**182个缺失日、2024-08-08深圳融资余额一个零值**，造成**267/756期**63日融资增长因子缺少真实基础数据。

本模块尝试与金十不同的数据链路：AKShare封装上交所`stock_margin_sse(start_date,end_date)`与深交所`stock_margin_szse(date)`的交易所融资汇总。官方交易所数据的原始研究页面分别为：
- 上交所 https://www.sse.com.cn/market/othersdata/margin/sum/
- 深交所 https://www.szse.cn/disclosure/margin/margin/index.html

**重要单位差异**：AKShare上交所汇总`融资余额`按**元**报告；深交所汇总`融资余额`按**亿元**报告。必须乘`100000000`转换深市报价，不能把深市融资融券余额当作融资余额，也不能假装两位小数亿元是精确到元的交易所值。

## 本次抽查的五个日期

- 2024-08-08：已发现的金十深圳异常零值，检验第二来源是否可以提供非零的独立数据；
- 2023-09-22：第一个历史缺口；
- 2024-06-20：第二个历史缺口；
- 2025-01-07：第三个历史缺口；
- 2026-10-20：最近已有金十基准日，检验单位量纲与一致性。

每个日期只读分别请求两个交易所，不批量发起数百次请求。原始接口返回CSV、独立源状态、单位及摘要保留GitHub Actions附件30天。接口失败、响应日期不明、额度四舍五入、金额不合理均不会自动补入PIT或生产模型。

## 重要限制

深交所汇总接口可能只有数值字段，而没有独立的交易日期字段：记录只能标记`REQUEST_PARAMETER_ONLY`，不能仅凭请求参数认为其官方发布日期或PIT时间已经得到独立证明。上交所记录若有`信用交易日期`则逐日校对。不同源报价差异须保留，不进行隐藏的前值填充或均值合成。无论探针成功与否，`formal_signal_allowed=false`。

## 执行与审计

```bash
python -m unittest discover -s research/v91_exchange_margin -p 'test_*.py' -v
python research/v91_exchange_margin/probe_official.py \
  --input v89_source_audit_output/candidate_inputs.json \
  --out v91_exchange_pilot
```

云端入口：[V91研究工作流](../../.github/workflows/v91-exchange-finance-pilot.yml)。自动下载近期成功的V89原始证据附件，每次在相同候选数据上复核，**不会修改旧版正式模型、网页、仓位和既有质量门禁**。
