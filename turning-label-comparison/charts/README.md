# 顶底图与指数标准建议

结论：固定旧警报后，盘中极值、收盘确认版精确率四项均较高；覆盖率三项较高，5%底部略低。两套均未双80。这是标签敏感性，不是重训后模型提升。精确率/覆盖率详见上层README与原始评分CSV。

全量图：all_pivots.html，可离线切换三指数、两套定义、日期范围，悬浮查看拐点与确认日。all_pivots_overview.svg及all_pivots_preview.png为中证全指四面板全量图。three_indices_all_pivots.csv为全部三指数标签。首个边界事件与末端未确认段不标；图中标签事后确认，不能当作拐点日已知信号。没有重训模型或更换正式标准。

建议基于项目仍以全市场风险预警为目标。主标准保留中证全指000985，沪深300和中证1000观察大小盘差异。若实际交易沪深300或中证1000产品，应另建与该标的一致的目标与收益评价。不能按历史命中率高低更换标准。三指数预测准确率尚未做同协议对照。

固定9%收盘反转、2011-08-02至2026-08-25，已确认顶底合计：沪深30038，中证全指65，中证1000 77。这说明同幅度并非相同波段尺度；不等于波动率测量或模型优劣证明。跨指数实验应同时报告固定百分比与预先冻结的历史波动调整阈值，不能事后调阈值追80。

中证1000发布日期2014-10-17；之前的指数值属于回溯历史，不能视为当时实时公布。指数历史沿用官方序列，未以当前成分股倒算；成分调整历史与所有数据历史发布时间仍未逐项完成PIT认证。

数据流：官方OHLC收据 → 对齐3659个交易日 → 5%/9%收盘或盘中极值收盘确认标签 → 首事件剔除与交替/日期顺序检查 → CSV与自包含交互图。新生成000985的全部443个标签与前次比较逐条完全相同。浏览器默认图实际渲染2个面板、243个盘中标签和243条明细；静态四面板包括两套全部443个标签。

官方依据：
- 中证全指编制方案：https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/20231208175438-000985_Index_Methodology_cn.pdf
- 中证1000编制方案：https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/20231208175402-000852_Index_Methodology_cn.pdf
- 中证1000事实表（发布日期）：https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000852factsheet.pdf

校验：validation.json含数据收据SHA256、各指数标签数和回归检查；browser_validation.json含默认浏览器渲染结果；build_charts.py可复算。

2026-11-02后续复核：混合盘中版不保证相邻反向拐点之间的实际最高/最低，5%有14处、9%有6处不一致。收盘标签暂作可复算研究基准，盘中版保留实验对照；本页旧重评结果保留不变。详见 E:/Codex/量化/dual80-research/label_clock_v4/README.md 与 local_extreme_audit.json。
