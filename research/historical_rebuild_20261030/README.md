# 2026-10-30 历史研究数据归档

本轮用户确认的数据基线：价格、成交额优先中证指数官方源；融资采用新获取的沪深序列；换手率采用官方成交股数除以 iFinD 当日历史流通 A 股本的可复算研究口径。

主表覆盖 **2011-08-02 至 2026-08-25，共 3659 个日期、六项数值输入**。

- [当前六项输入主表](turning-research-canonical/tables/research_inputs.csv)
- [换手率逐日分子、分母及复算结果](turning-research-canonical/tables/turnover_rate_recomputed.csv)
- [采用口径和核验说明](turning-research-canonical/README.md)
- [换手率模型敏感性核查](turning-research-canonical/turnover_signal_sensitivity.json)
- [独立重新获取的六项原始序列](turning-raw-reacquired/tables/raw_six_fields.csv)
- [沪深融资余额分项](turning-raw-reacquired/tables/financing_sh_sz.csv)
- [全量文件清单和 SHA256](upload_manifest.json)

## 归档范围

共归档 860 个原有文件，约 47 MB，包括以下五个目录的原始数据、回执、逐字段来源、异常记录、旧输入存档、复建脚本和本地模型核查结果：

|目录|用途|
|---|---|
|turning-research-canonical|当前采用的研究主表、官方价格与成交额回执、换手率分母与核验|
|turning-raw-reacquired|独立重取的供应商六项原始输入和差异审计|
|A-share-top-monitor-history|融资补数、交易所原始记录和数据需求清单|
|html-data-audit|原始 HTML 内嵌数据及事件提取|
|turning-rebuild|旧输入、规则恢复、本地研究页面及复算结果|

保留失败、截断或弃用的取数回执用于审计；这些文件的存在不表示其数值进入主表。upload_manifest.json 的 excluded 列明 8 个排除项，仅包括 Python 缓存和下载的网站实现文件，不排除研究数据。旧压缩包属于这些文件的重复副本，不另重复上传。

## 适用边界

本批为 **RESEARCH_ONLY / 非 PIT 认证**。历史发布时点、全部历史成分范围没有独立认证，不能直接宣称严格开盘前回测通过或策略达到双80。

换手率是项目自行构造的研究变量，不是中证直接发布的换手率。2012-12-07 存在成交股数来源差异，该日优先官方值并留痕。只替换换手率的对照中，四类正式信号日期未改变；这不属于收益表现认证。

生产网页、生产数据服务、collector、工作流及全局质量门禁均未在本次上传中修改。turning-rebuild 内网页和结果仅为历史研究存档。

## 校验和复建

在本目录运行 `python verify_upload.py`，仅使用 Python 标准库验证全部归档文件 SHA256、主表日期与数值完整性。

保留原始回执时，可在 turning-research-canonical 内顺序运行 `python build.py`、`python finalize_turnover.py`，再运行 `node check_turnover_signal_sensitivity.cjs`。最后一步依赖相邻 turning-rebuild/model_core.cjs。取数脚本中的 iFinD 技能路径属于原运行环境，需要在新环境配置供应商连接；归档不包含 API 密钥。
