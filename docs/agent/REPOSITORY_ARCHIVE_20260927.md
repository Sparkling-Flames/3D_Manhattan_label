# 仓库历史分支归档（2026-09-27）

当前远程仅保留 `main` 与 `codex/pro-layout-research-20260927`。本地另保留当前 `codex/workspace-organize-20260927`。19个旧远程分支已转为归档标签，删除分支前逐一核对标签指向；不重写历史，不丢弃未合并成果。

## 2026-09-28 主分支整合

本轮将最新整理、全量复核与共享 x 预处理成果压缩合并到 main，并合入 Pro 研究分支历史。下方 9/27 的分支清单是历史快照。完成远端同步后，本地及远端活动分支只保留 main；已有独立 detached worktree 不作清理。

原工作分支提交保留在本地标签 `archive/20260928/local/workspace-before-main`，不上传该标签：其中包含超过 GitHub 普通文件限制的历史 blob。199 MB 的 `analysis_results/research_dashboard_20260922/assets/data.js` 改由 Git LFS 保存，文件内容不变；新克隆须安装 Git LFS 并执行 `git lfs pull`。其他源码、原始导出、审核和预处理数据保持最新用户提交的内容。

Pro 研究目录入口改为 main；旧分支删除不影响已合入的提交历史。原压缩归档按最新用户提交保留，远端旧结果仍可从 Git 历史追溯。未重跑研究实验；合并验证为排序/复核相关 16 项测试及机器合同渲染检查。

## 历史文件入口

旧分支包含的文件均可通过下表打开。旧的 `/tree/分支名/路径` 链接需换成 `/tree/归档标签名/路径`；删除分支不会自动重定向旧URL。各历史文件仍保持原来的目录结构。

| 原远程分支 | 可浏览的归档 |
|---|---|
| `A-line` | [归档文件](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/archive/20260927/remote/A-line) |
| `codex/-paper-a` | [归档文件](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/archive/20260927/remote/codex/-paper-a) |
| `codex/image-portrait-20260914` | [归档文件](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/archive/20260927/remote/codex/image-portrait-20260914) |
| `codex/paper` | [归档文件](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/archive/20260927/remote/codex/paper) |
| `codex/pro-cluster-validation-20260922` | [归档文件](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/archive/20260927/remote/codex/pro-cluster-validation-20260922) |
| `codex/pro-clustering-ready-20260920` | [归档文件](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/archive/20260927/remote/codex/pro-clustering-ready-20260920) |
| `codex/pro-research-20260921` | [归档文件](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/archive/20260927/remote/codex/pro-research-20260921) |
| `codex/simulated-annotators` | [归档文件](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/archive/20260927/remote/codex/simulated-annotators) |
| `research/clustering-release-20260920` | [归档文件](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/archive/20260927/remote/research/clustering-release-20260920) |
| `research/clustering-visual-20260918` | [归档文件](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/archive/20260927/remote/research/clustering-visual-20260918) |
| `research/full-corpus-clustering-20260918` | [归档文件](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/archive/20260927/remote/research/full-corpus-clustering-20260918) |
| `research/local-point-audit-20260920` | [归档文件](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/archive/20260927/remote/research/local-point-audit-20260920) |
| `research/local-point-coverage-20260919` | [归档文件](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/archive/20260927/remote/research/local-point-coverage-20260919) |
| `research/pairing-time-audit-20260919` | [归档文件](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/archive/20260927/remote/research/pairing-time-audit-20260919) |
| `research/personnel-replay-20260921` | [归档文件](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/archive/20260927/remote/research/personnel-replay-20260921) |
| `research/rc2-pairing-audit-20260920` | [归档文件](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/archive/20260927/remote/research/rc2-pairing-audit-20260920) |
| `research/recovery-export-20260918` | [归档文件](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/archive/20260927/remote/research/recovery-export-20260918) |
| `research/supervisor-consensus-20260922` | [归档文件](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/archive/20260927/remote/research/supervisor-consensus-20260922) |
| `research/uncertainty-independent-20260918` | [归档文件](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/archive/20260927/remote/research/uncertainty-independent-20260918) |

## 恢复方式

例如需要继续旧分支时（只创建本地分支，不自动推送）：

```sh
git fetch origin --tags
git switch -c restored-pro-research archive/20260927/remote/codex/pro-research-20260921
```

本地旧分支另外保存于 `archive/20260927/local/<原分支名>`，这些标签没有公开上传；其中可能有仅本地成果。机器清单在本地 `analysis_results/repository_archive_20260927/archive_manifest.json`。

## 文件清理边界

归档的是历史版本与分支入口，不是声称磁盘体积已经减少。原始导出、标注、GT、协议、可复算结果及当前脚本引用的路径未批量删除或搬迁。现有4份正式方法文件修改和1项原始导出删除保持原状。

没有打开的PR，因此没有关闭PR。最新研究目录继续使用展开文件，旧Release作为历史快照保留。归档标签可恢复；当前工作分支的WIP仍只在本地。
