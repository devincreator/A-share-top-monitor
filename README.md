# A股波段顶底研究

中证全指5%与9%波段顶底的开盘前预警研究。**当前未达到精确率、覆盖率双80，历史时点可得性尚未全部认证。**

## 直接查看

|内容|入口|
|---|---|
|全部顶底图，切换三指数与两种口径|[交互图 index.html](index.html)，下载后用浏览器打开|
|全部顶底静态图|[全景图](turning-label-comparison/charts/all_pivots_preview.png)|
|最新方法、结果与失败分析|[当前研究报告](dual80-research/label_clock_v4/README.md)|
|P1：高分是否落在 D..D+6|[分数对齐诊断](dual80-research/p1_score_alignment/README.md)，结论为阻断|
|P1b：拐点收盘前六个价格特征是否已经移动|[特征时点审计](dual80-research/p1b_feature_timing/README.md)，慢变量在可命中窗口内已离开普通日|
|P1c：四个慢变量等权分数的峰值是否落在 −6..0|[慢变量分数](dual80-research/p1c_slow_feature_score/README.md)，结论为阻断|
|P1d：已有发报是推迟到拐点后一天，还是窗口内没有进尾部|[发报时点归因](dual80-research/p1d_fire_timing/README.md)，结论为转向价格家族之外的因子，本页不实现|
|采用的规则|[ACTIVE_RESEARCH_CONTRACT.json](ACTIVE_RESEARCH_CONTRACT.json)|
|研究主表：3659日、六项输入|[research_inputs.csv](turning-research-canonical/tables/research_inputs.csv)|
|数据来源与换手率口径|[数据说明](turning-research-canonical/README.md)|
|顶底标签、警报一一匹配结果|[标签比较](turning-label-comparison/README.md)|
|盘中标签问题的逐条证据|[极值审计](dual80-research/label_clock_v4/local_extreme_audit.json)|

## 当前约定

开盘前D日发报，只用当时已公布的数据。命中窗口为D至D+6，共7个交易日；同幅度、同方向警报与拐点一一对应。5%顶、5%底、9%顶、9%底分别要求精确率及覆盖率达到80%。

中证全指作主标准，沪深300和中证1000作大小盘对照。收盘标签暂作可复算研究基准；盘中极值、收盘确认的混合标签只作实验对照，因为它不能保证每个标记都是相邻反向拐点间的实际最高或最低点。

同一价格模型的新研究策略在收盘5%底部上达到精确率33.9%、覆盖率51.3%；其他任务仍有取舍，没有整体升级依据。P1 对齐诊断重放了这套收盘×价格×历史90分位分数：窗口内尾部高于普通日，但四项任务的峰值都在拐点后第一个交易日，有可评分日的漏报只有21%进过因果尾部。结论是阻断，不进入发报压缩，也不只提高阈值。P1b 不重训，只比较那六个价格特征：20日收益、距20日高点、距20日低点、63日区间位置在四个任务的可命中窗口里已经离开普通日，拐点收盘是在这个水平上再推进一步；3日收益的额外极端仍主要来自拐点收盘。结论是放行，只允许以后预注册这些坐标。P2 发报压缩保持关闭，分数峰值仍在拐点后一天。`formal_signal_allowed` 仍为 false。P1c 把这四个慢变量合成等权、符号对齐的因果标准化和，发报规则仍是 past_rank90。四项任务的平均分数和因果尾部都在偏移 +1 达到峰值，结论是 `BLOCKED_NO_WINDOW_PEAK`：合成分数的峰值仍落在打不中该拐点的那一天。窗口内分数仍高于普通日。精确率和覆盖率相对冻结基线只作对照，双80仍未达到。P1d 只归因这两条分数已经发出的 past_rank90：四项任务的漏报多数是可命中窗口里从未进入因果尾部，不是警报被推迟到偏移 +1。结论是 `GO_NEW_FACTORS`，不实现新的发报规则，也不把快变量加回。历史已经反复研究，不称独立盲测。图表是截至2026-08-25的历史研究图，不是实时交易信号。

## 数据与方法放在哪里

|目录|内容|
|---|---|
|turning-research-canonical|当前数据基线、官方原始回执、换手率复算|
|turning-raw-reacquired|供应商独立重取数据和字段差异核验|
|A-share-top-monitor-history|融资分项与补数来源证据|
|html-data-audit / turning-rebuild / original_user_material|原始页面、输入提取、原规则恢复和对照|
|turning-7day-preopen|最初7日窗基线与优化尝试，保留旧窗口说明|
|dual80-research|本轮模型实验、全部失败记录、最新标签/时钟迁移|
|turning-label-audit / turning-label-comparison|两种标签核验、三指数标签和图表|

保留影响结论的原始数据、方法和失败结果。旧V系列目录、旧网页/采集器、重复归档、旧门禁/交接和定时研究工作流已从当前分支清掉；第三方教材与其他无关策略不再放在本项目里。清理前内容可从Git历史恢复，见[整理记录](CLEANUP.md)。

## 核验与复算

运行 `python -B verify_repository.py` 核对文件SHA256、主表、标签、当前合同及目录一致性。这个命令不联网、不重训。GitHub仅保留一个只读完整性检查工作流，无定时取数、自动回写或旧版本研发任务。

最新模型入口：`dual80-research/label_clock_v4/run.py`，后续阈值对照：`dual80-research/label_clock_v4/rank_replay.py`。模型研究需要Python 3与NumPy；原规则恢复另有Node.js脚本。方法原样保留，一些旧辅助脚本仍引用原E盘工作路径，迁移时需调整；历史脚本会重写结果，不要批量运行。历史freeze_labels.py保留已撤回的中间决定，当前口径以根目录合同和最终决定为准。
