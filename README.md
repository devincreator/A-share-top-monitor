# A-share-top-monitor

A股 5% / 9% 双尺度拐点监测与执行策略可视化项目。

## 最新状态

**行情核心状态已更新至 2026-09-10。**

- 当前方向：**寻找顶部**
- 5% 波段：**UP**
- 9% 波段：**UP**
- 当前执行仓位：**0% / 空仓**
- 最新 Top-5：**2026-08-05，Route B**
- 最新 Top-9：**2026-08-05，Route B**
- Top-9 价格转弱确认：**2026-08-19**
- T+1 退出执行：**2026-08-20**
- 最新中证全指收盘：**5851.83**

最新状态文件：`data/latest_state.json`

增量日度数据：`data/incremental_20260805_20260910.csv`

## 一键查看

### [▶ 一键打开可视化网页](https://devincreator.github.io/A-share-top-monitor/)

打开网页后，右下角有 **「微信分享」** 按钮，可直接：

- 复制微信摘要
- 生成微信竖版分享图
- 单独打开完整网页

## 当前内容

- `index.html`：网页入口 + 微信分享工具
- `app.html`：完整可视化静态页
- `data/latest_state.json`：最新市场方向、客观拐点、正式信号和执行状态
- `data/incremental_20260805_20260910.csv`：2026-08-05 至 2026-09-10 增量计算数据
- 页面展示当前市场方向、四模块状态、三层信号图、执行策略与最新历史回测指标

> 注：当前增量更新已覆盖中证全指与价格派生的核心状态；四模块完整全字段条件分数仍以最近一次完整字段快照为准，不用旧分数冒充最新值。

## 中国大陆访问：EdgeOne Pages

本项目是纯静态 HTML，可直接从 GitHub 仓库部署到腾讯 EdgeOne Pages。

[![使用 EdgeOne Pages 部署](https://cdnstatic.tencentcs.com/edgeone/pages/deploy.svg)](https://console.cloud.tencent.com/edgeone/pages/new?repository-url=https%3A%2F%2Fgithub.com%2Fdevincreator%2FA-share-top-monitor&project-name=a-share-top-monitor&root-directory=.%2F&output-directory=.%2F)

部署时建议：

- GitHub 仓库：`devincreator/A-share-top-monitor`
- 分支：`main`
- 根目录：`./`
- 输出目录：`./`
- 构建命令：留空
- 安装命令：留空

项目创建完成后，后续只要向 `main` 分支提交代码，EdgeOne Pages 即可自动触发新的部署。

## GitHub Pages

发布源：

- Source: `Deploy from a branch`
- Branch: `main`
- Folder: `/ (root)`

正式网页入口：

https://devincreator.github.io/A-share-top-monitor/

## 说明

历史表现用于说明模型特征，不代表未来一定重复。模型分数为规则完成度，不是预测概率。
