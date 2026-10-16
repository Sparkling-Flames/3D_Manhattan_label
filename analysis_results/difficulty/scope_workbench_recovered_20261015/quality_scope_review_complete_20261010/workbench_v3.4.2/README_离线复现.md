# v3.4.2 工作台：完整离线数据与回归输入

本目录保留已发布源码提交 `e44b52969f0d18a352773a83c4b9575f720bc5a7` 的选定源码、全部12个fixtures、`dist/data.json`、282份逐图records、全部catalogue/evidence和266个assets文件。为支持双击 `dist/index.html`，另有 `dist/data.js` 和282份按需详情脚本；HTTP模式仍读取JSON。没有省略测试需要的照片。站点发布回执在 `deployment_receipt.json`。

直接双击 `dist/index.html` 即可本地复核，不需要启动服务器。浏览器草稿保存在当前浏览器本地存储中；若浏览器策略禁用本地文件脚本，可改用下方 Python HTTP 方式。

本仓库副本在原发布快照上增加了 `file://` 加载兼容，仅供本地使用；未更改部署回执，也未重新发布在线工作台。

## 状态分层

- 这是用户导出最终回执时的已发布工作台快照，内置已接收确认仍为当时16图。
- 本次交回结果是35图确认，见整个交付包 `final_scope_receipt_validation/`；旧16不覆盖最新35。
- 可以通过网页的导入功能载入本包最终原回执，继续查看用户的实际操作。封包工作没有重新发布Site，没有修改已发布工作台的几何算法和初始数据。

## 可执行检查

需要Node.js（本次使用v24.19.0）和Python 3（运行便捷入口）。不需要安装npm依赖：

```sh
python run_offline_checks.py
```

该入口在自身目录运行以下8个原版检查，没有修改断言、没有跳过照片存在性检查：

```sh
node qa-geometry-v2.cjs
node qa-state.cjs
node qa-confirmed-receipt.cjs
node qa-gt-snap.cjs
node qa-space-regions.cjs
node qa-missing-room-queue.cjs
node qa-edge-drag.cjs
node qa-outside-gt.cjs
```

本次在封包副本实跑合计26,977项通过：几何49、状态与数据3,515、回执1,337、GT吸附444、多空间243、补漏队列13,726、边线拖动1,731、GT外扩展5,932。`QA.json`也列出几何49，汇总时未重复计数。日志位于 `verification/`。

这些是数据、几何、状态与模拟DOM/指针检查。真实浏览器视觉和实际交互没有验收。历史 `qa.cjs` 为早期浏览器场景，留作源码资料，不能直接当成当前v3.4.2浏览器验收入口。

## 本地查看

在仓库根目录 `D:\Work\HOHONET` 启动本地服务：

```powershell
python -m http.server 8765 --directory "analysis_results/difficulty/scope_workbench_recovered_20261015/quality_scope_review_complete_20261010/workbench_v3.4.2/dist"
```

然后在自己的浏览器打开 `http://127.0.0.1:8765/`。这是本机服务，照片与数据都从仓库内的 `dist/` 读取，不依赖远端工作台或原始下载目录。浏览器保存、缩放、移动端视觉等仍需独立验收；本说明不声称它们已经通过。

## 重建范围

现成 `dist/` 是完整静态快照；上述测试可独立复跑。历史构建/整合脚本保留原始阶段约定和路径，部分需要仓库或前序源资料，不能据此声称所有早期上游构建都已完全可离线重做。逐个文件来源见 `SOURCE_PROVENANCE.json`；额外的便捷检查入口及本说明不属于原发布提交。
