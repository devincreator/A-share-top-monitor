# 旧版研究包完整性清单（严格区分已入库与未入库）

**目的**：防止后续AI误以为“GitHub有报告”就代表Github已存放全部原版ZIP和训练源码。以下研究包是在2026-10-20本地工作区检验过的文件；这些ZIP的**完整二进制内容尚未归档本GitHub**，仅报告/重要CSV/2005历史原始行情分别同步到 `research/` 和GitHub Release。若必须逐字节重现某轮原始代码，应向用户索取对应研究ZIP或从原会话附件恢复，然后按下表SHA256核验。

| 历史研究包文件名 | 预计大小 | 原ZIP SHA256 | GitHub持久化范围 |
|---|---:|---|---|
| `V63_V68_2005长历史双向顶底_完整实测研究包.zip` | 3.4MB | `756a2bcb0907c2ec8527d0fd1a40ac7fe77ee8731eb443fdb4086e3db7162b59` | 实测报告、四任务指标与验证合同已摘要入GitHub，原ZIP尚未入库 |
| `V69_V75_实际执行_研究与审计完整包.zip` | 1.1MB | `0f6c006558ded42eb19f2199ba1fedb9c56c1363b93ab4379302da586d1341e8` | 全部文字实测报告及主要状态摘要已入GitHub，原ZIP尚未入库 |
| `V76_历史退市股与市场广度_完整采集工程.zip` | 121KB | `bb3edbea63425ede8a011522ce282501a06be86754762c1553b48dc92eebeabb` | 报告和在线数据研究工作流已入库，原ZIP尚未入库 |
| `V77_云端历史广度数据_完整阶段研究包.zip` | 2.4MB | `6b7dd4519810b917d439ab78b628f02bab25fbe42b9ccee77425435b128836ca` | 报告和GitHub历史运行可见，原ZIP尚未入库 |
| `V78_V82_2005全市场广度_可复算研究包.zip` | 9.6MB | `6ea7e6a47af12a387f008c6c3e0ea67c79bdd478d2e61a8a6febd25e7c24b826` | 2005原始242天可从永久Release恢复、原审计报告/部分研究CSV/复算检查脚本已入库，原ZIP内部完整派生结果和全部源码仍需原ZIP |

## 已永久可恢复的核心原始数据

- [2005年242日逐股原始行情ZIP](https://github.com/devincreator/A-share-top-monitor/releases/download/research-v82-2005-20261020/v82_2005_raw_242days.zip)
- [研究版数据报告](reports/V78_V82_实测报告.md)
- [一键验证脚本](scripts/verify_2005_release.py)
- [逐日涨跌家数重新计算核对](scripts/check_2005_breadth_against_raw.py)
- [机器门禁](status/quality_gates.json)

**解释**：这次 GitHub 同步的重点是让后续AI可以从现有可靠的原始日线、研究规范、验证程序与具体待办继续推进。**没有把本地旧研究ZIP全部声称为已备份。** 要重跑之前某轮原始训练脚本，请先取回对应原ZIP，验证SHA后再运行，不要虚构等价实现或已执行结果。
