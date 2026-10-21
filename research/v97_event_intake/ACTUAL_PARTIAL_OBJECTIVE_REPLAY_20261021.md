# V97 首次真实数据重建证据｜中证全指部分客观拐点（2026-10-21）

## 执行与结论

**已用实际下载并通过原始SHA256核验的中证全指行情重建客观标签，尚未恢复任何旧的真实提前预警。**

- GitHub Actions **[39556170202](https://github.com/devincreator/A-share-top-monitor/actions/runs/39556170202) SUCCESS**：运行V86/V97防未来函数测试；从已归档V89源运行 [39540193090](https://github.com/devincreator/A-share-top-monitor/actions/runs/39540193090) 下载**真实1128条**中证全指历史观察收盘数据，逐日期构造5%/9%交替ZigZag客观顶部/底部。
- 初次测试中，左边界初始化的单元测试设定错误，GitHub Actions [39555920435](https://github.com/devincreator/A-share-top-monitor/actions/runs/39555920435) 与 [39556060236](https://github.com/devincreator/A-share-top-monitor/actions/runs/39556060236) **失败**，在修正“首个未确定行情方向”测试口径后重新执行，保留两次失败记录。
- 原始输入`candidate_inputs.json` SHA256：`00fde1c9602b02be19b4c061f80041a9eda9d114addd845644c770ea3ceabce9`。
- 独立重建使用的指数`000985.CSI`，从2022-02-23至2026-10-20；**不是**历史2015—2026全部V52行情和157个完整标签。
- 5%标签39个，9%标签19个；其中各有**1个左边界不完整的初始标签**，明确标`LEFT_CENSORED`，不能计入回测覆盖分母。其余5% 38个、9% 18个仅为这段历史的独立重建候选；不同于原V52完整历史全标签。
- 与仓库已保存的原V52审计摘要相符的最近确认顶部：
  - **5% TOP：极值2026-08-17，首次确认2026-09-11**；
  - **9% TOP：极值2026-08-17，首次确认2026-10-08**。
  这只是上述两个末端锚点成功复核，不是全部157个V52端点逐条一致的认证。
- 重建价格CSV SHA256：`f18bb93b38e6648fbd72bad53dc7fa06333cd63a01858063e1dfa50b14e7fc41`；
  客观端点CSV SHA256：`39648f066b515c6ddc5b5853f9d1f691e3439fa04393a81e36b4c19e649262b1`。

## 可复算永久资产

- [冻结的1128条真实价序列](observations/index_000985_prices_20220223_20261020.csv)
- [独立反转规则生成的58条客观拐点与各自首次确认日](observations/partial_v52_derived_objective_pivots.csv)
- [实际数据源及输出哈希、完整限制](observations/partial_v52_pivot_manifest.json)
- [重建代码](reconstruct_partial_pivots.py)和[单元测试](test_reconstruct_partial_pivots.py)
- [云端成功任务](https://github.com/devincreator/A-share-top-monitor/actions/runs/39556170202)

## 关键反未来函数说明

1. 顶底极值日只能在以后行情反向跨越5%/9%阈值时**事后标记**，故反转确认日`confirmation_date`不是极值当天可预知的状态。
2. 对D日开盘前预测，D日收盘价和D日确认的客观标签均**禁止作为D日已知特征**；无独立发布证据时，标签可用时间不能早于确认日后的下一个真实可观察交易日，即使该“次日”也只是不可早于的下界，不等于PIT已证实。
3. 旧V63—V68原始`FORMAL_START`预警记录仍未在仓库、现有两个Release、文件检索及有关Git历史/分支搜索中找回；原始历史报警时间、实际决策时点和模型输入时点缺失，不能从这些事后客观标签倒推真实历史报警。
4. 研究模型精确率、Recall、误报事件归因、双80**全未更新**；不可将`58`个事后拐点说成提前命中或正式买卖预警。
5. 未改变正式监测网页、既有生产策略或发布参数。

## 下一项严格串行任务

仍停留在**E1 原始事件恢复**：寻找V63—V68的FORMAL_START历史逐日通知或原始参数与代码版本的可信复制，并保留来源SHA256、真实决策时刻。如果原始清单最终无法找到，只能将完整复算另记为**重新生成的历史研究**，不能冒充当年原始预警，且必须重新按开盘前`D-1已公布数据`条件计算。其后才进入E2时钟认证、E3实际回测、E4误报类型统计。

## 最后一次严格时点门禁核验

[GitHub Actions 39556794398](https://github.com/devincreator/A-share-top-monitor/actions/runs/39556794398)运行代码单元测试成功，机器实际输出`BLOCKED_BUNDLE_MISSING`与`BLOCKED_ORIGINAL_EVENTS_OR_AVAILABILITY_MISSING`，4个必需的旧原始CSV/可得性文件均未存在，`tasks={}`且`formal_signal_allowed=false`。来源附件ID `12325223549`。禁止当日日级因子及所属交易日收盘前的伪造最终指标发布时间的新增测试已通过；这一代码成功**不等于历史正式报警重建成功**。
