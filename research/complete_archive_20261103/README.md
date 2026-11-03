# 当前完整研究档案 · 2026-11-03

本目录集中保存本地全部相关数据、来源回执、方法、源码、实验结果、失败记录、口径变更和图表。原有历史归档保留；这是独立的完整快照。

**收录 1062 个原有文件，120.62 MB。双80尚未达到，历史发布时点/PIT及历史成分认证未全部完成，未更换生产模型。** 上传成功只表示研究档案完整同步，不表示模型通过。

## 从这里开始

|内容|入口|
|---|---|
|最新标签抽查、32项新对照、结论和限制|[label_clock_v4报告](dual80-research/label_clock_v4/README.md)|
|当前开盘前时钟与研究口径|[ACTIVE_RESEARCH_CONTRACT.json](workspace_metadata/ACTIVE_RESEARCH_CONTRACT.json)|
|标签最终决定及撤回中间决定的依据|[最终决定](dual80-research/label_clock_v4/label_decision_final.json)、[逐条极值审计](dual80-research/label_clock_v4/local_extreme_audit.json)|
|3659日六项研究主表，2011-08-02至2026-08-25|[research_inputs.csv](turning-research-canonical/tables/research_inputs.csv)|
|官方价量、融资新序列、换手率口径|[数据基线说明](turning-research-canonical/README.md)、[独立重取](turning-raw-reacquired)|
|三指数全部顶底与图|[顶底说明](turning-label-comparison/charts/README.md)、[全景图PNG](turning-label-comparison/charts/all_pivots_preview.png)、[三指数全部标签CSV](turning-label-comparison/charts/three_indices_all_pivots.csv)|
|离线交互图，可切指数、口径、时间范围|[all_pivots.html](turning-label-comparison/charts/all_pivots.html)，下载到本地浏览器打开；GitHub文件页不执行交互代码|
|原警报不变的两标签/时间窗重评|[比较报告](turning-label-comparison/README.md)、[全部评分CSV](turning-label-comparison/all_rescored_metrics.csv)|
|10个差异行情片段|[抽查图](dual80-research/label_clock_v4/label_case_atlas.png)|
|36配置实验与失败归因|[实验](dual80-research/broad_experiments_v2/README.md)、[失败原因](dual80-research/broad_experiments_v2/失败原因与优化建议_20261102.md)|
|全部原始文件SHA256与排除清单|[upload_manifest.json](upload_manifest.json)|
|用户最初提供的HTML|[原始材料](original_user_material)|

## 当前采用的判断标准

- D日开盘前发出警报，命中窗为D到D+6，共7个交易日；相同指数、幅度、方向一一对应。5%顶、5%底、9%顶、9%底分别要求精确率和覆盖率达到80%。
- 中证全指是全市场研究主标准；沪深300、中证1000作大小盘风格对照，不按事后分数更换预测对象。
- 收盘标签暂作可复算基准，混合盘中标签仅作实验对照。5%盘中混合标签14处、9%6处不等于相邻反向拐点间的实际高低点，两个任务可能涉及同一行情；不能称20个独立行情。更高的重评分数不证明标签更正确。
- 保留最初决定、撤回依据及失败模型；旧文档可能说1—7日或其他旧窗口，只用于历史复算，以当前合同和最终决定为准。仓库其他旧研究/定时工作流仍各有历史合同，不自动视为本目录新口径。
- 原价格规则仍是控制基线。最新同一价格模型采用过去分数90分位后，收盘5%底部精确率33.9%、覆盖率51.3%；没有四任务整体替换依据。全部历史已经反复研究，不称独立盲测。

## 目录与数据流

官方OHLC/成交额、供应商融资与流通股本回执 → 六项研究主表及换手率复算 → 事后标签/确认日 → D-1可观测特征 → 只使用此前已确认标签训练 → 连续发报台账 → D..D+6一对一评价 → 成熟结果与PENDING分开。

turning-research-canonical、turning-raw-reacquired、A-share-top-monitor-history保存源数据及核验；html-data-audit、turning-rebuild保存旧页面提取和规则恢复；turning-7day-preopen及dual80-research保存全部后续实验；turning-label-audit、turning-label-comparison保存标签核查和图；A-share-top-monitor-review是早期仓库审阅快照，其中旧进度/门禁不是当前权威状态。strategies、references、skills及workspace_metadata补充本地量化学习、其他策略和方法材料，不算本顶底模型效果。

## 完整性核验与复算

在本目录运行 `python -B verify_archive.py`：只用标准库核对全部原文件SHA256、六字段主表和标签计数，不发起取数或重新训练。文件按原字节保存，局部.gitattributes关闭文本换行转换。

模型研究用Python 3与NumPy，规则恢复另有Node.js脚本。源文件保留原Windows E盘路径及供应商技能路径，未冒充无配置的一键复现；迁移环境时需将 `E:\Codex\量化` 映射到本目录，并配置自身供应商连接。可以先复制本目录到独立工作目录，再调整路径，不修改本归档证据。`.py` 方法保留原样，有些历史脚本运行会重写其计划/结果，核验时仅运行verify_archive.py，不要为了浏览归档批量执行实验脚本。

主要复算顺序：数据口径见turning-research-canonical；旧规则见turning-rebuild/model_core.cjs；标签比较见turning-label-comparison/compare.py；最新季度训练和新7日目标见dual80-research/label_clock_v4/run.py；历史分数90分位发报见同目录rank_replay.py。label_clock_v4/freeze_labels.py保留的是已撤回的中间决定，不能单独运行它覆盖最终合同。

排除浏览器会话/缓存、Python缓存、版本控制内部文件及下载的第三方网站实现文件；未排除研究原始回执、失败结果或方法。排除路径及理由逐条保存在manifest。旧ZIP是已归档原文件的重复打包，不重复提交；完整本地校验ZIP另保存在E盘。

生产页面、数据服务、collector、工作流及全局质量门禁不在本次修改范围。
