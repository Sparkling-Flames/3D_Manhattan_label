# trap集说明

本目录保存当前 `PreScreen` 阶段相关的人工筛选任务。它现在最准确的定位是：

- `manual` 候选池
- `semi` 候选池
- `OOS` gate 候选池

它不是已经完成 final binding 的 Stage 1 executable pool。

## 当前使用边界

当前请优先相信下面这个顺序：

1. 最新 `project-20` 人工精标导出
2. 当前 `trap集` 实际目录结构
3. 各子目录或 task 下的 `特别注意.md` / `特别说明.md`
4. `analysis_results/truth_layer_extraction_20260324/` 下的 truth-layer extraction 结果
5. 旧的 `task_inventory_20260320.md`、`trap.md`、`复核总表_20260307.md`

第 5 类文件现在只应视为历史背景，不应覆盖最新 export 与当前目录。

## 当前 geometry / metadata 合同

- 当前 authoritative geometry source 是 latest `project-20` export 里的 Label Studio `kp`
- `poly` 只保留为 raw residue，不进入 thesis-facing 主 geometry contract
- task 目录里的 `.txt` 只保留为 `legacy_mp3d_reference`
- `scope` 决定 `in_scope / oos`，不由目录名字单独决定

## 当前括号说明的解释

- 只有明确带 `低优先` 的 task，才默认不进入人工锚点集
- 其他括号说明，例如 `高难度`、`较为困难`、`略微有点遮挡`、`可能有歧义`、`同时是一角多点`、`同时是角点错位`，默认只视为 review annotation，不自动降级
- `task711(中低优先,难标注)` 是当前人工保留的例外：它不作为默认 expert-anchor，但在遮罩 family 内保留，且优先级高于 `696`

## 当前状态提醒

基于当前 latest export 与 truth-layer extraction：

- `trap ∩ latest export = 58`
- 当前目录分布是 `manual=30 / semi=18 / OOS=10`
- 当前 working-consensus snapshot 已可稳定抽取
- 但它仍然不是 final adjudicated gold

因此，本目录当前最强表述只能是：

> **working-consensus candidate pool**

而不是 `Stage 1 ready` 或 `final gold`。
