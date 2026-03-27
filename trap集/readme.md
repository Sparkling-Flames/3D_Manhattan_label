# trap集说明

本目录保存当前 `PreScreen` 阶段相关的人工筛选任务。它现在最准确的定位是：

- `manual` 候选池
- `semi` 候选池
- `OOS` gate 候选池

它不是目录本身就等于最终 `Stage 1 executable import` 的那一层。

## 当前使用边界

当前请按下面顺序理解：

1. 最新 `project-20` 人工精标导出
2. 当前 `trap集/` 实际目录结构
3. 各子目录与 task 下的 `特别注意.md / 特别说明.md`
4. `analysis_results/truth_layer_extraction_20260324/` 与 `analysis_results/final_gold_layer_20260325/`
5. 更旧的 inventory / review 总表

其中第 5 类文件现在只应视为历史背景，不能覆盖最新 export 与当前目录。

## 当前 geometry / metadata 合同

- 当前 authoritative geometry source 是最新 `project-20` export 里的 Label Studio `kp`
- `poly` 只保留为 residue，不进入 thesis-facing geometry contract
- task 目录里的 `.txt` 只保留为 `legacy_mp3d_reference`
- `scope` 决定样本是 `in_scope` 还是 `oos`，不由目录名单独决定
- 对 `OOS` 样本，还要区分“目录 family”和“final scope subtype”
  - 目录 family 只用于 candidate bookkeeping
  - final scope subtype 以 latest verified export / final gold 为准
  - `task560` 是当前显式例子：目录在 `边界不可判定`，但执行层 `scope_target = oos_geometry`

## 当前括号说明的解释

- 只有明确带 `低优先` 的 task，默认不进入人工锚点集
- 其他括号说明，例如：
  - `高难度`
  - `较为困难`
  - `略微有点遮挡`
  - `可能有歧义`
  - `同时是一角多点`
  - `同时是角点错位`
  默认只视为 `review annotation`，不自动降级
- `task711(中低优先,难标注)` 是当前 `遮罩` family 的保留例外：
  - 不按普通 `低优先` 自动剔除
  - 但也不应直接理解为默认 `expert-anchor`
  - 当前仍是 `711 > 696`

## 当前目录层状态

基于最新 truth-layer extraction 与 final gold：

- `trap ∩ latest export = 61`
- 当前目录分布是：
  - `manual = 30`
  - `semi = 21`
  - `OOS = 10`
- 目录级 `working-consensus / final-gold truth layer` 已可稳定抽取
- 但本目录本身仍然不是正式导入清单

因此，本目录当前最准确的定位仍然是：

> **working candidate pool**

而不是“目录本身就是 Stage 1 导入文件”。

## 当前正式导入层

当前 thesis-facing `Stage 1` 以这些文件为准：

- [prescreen_manual_final_selection_v1.json](d:/Work/HOHONET/analysis_results/phase1_progress_20260324/prescreen_manual_final_selection_v1.json)
- [prescreen_semi_final_selection_v10.json](d:/Work/HOHONET/analysis_results/phase1_progress_20260324/prescreen_semi_final_selection_v10.json)
- [oos_final_quota_binding_v2.json](d:/Work/HOHONET/analysis_results/phase1_progress_20260324/oos_final_quota_binding_v2.json)
- [stage1_final_binding_audit_v6.json](d:/Work/HOHONET/analysis_results/phase1_progress_20260324/stage1_final_binding_audit_v6.json)
- [stage1_prescreen_import_summary_v4.json](d:/Work/HOHONET/import_json/stage1_prescreen_final_20260325/stage1_prescreen_import_summary_v4.json)

当前最强表述是：

> `trap集` 目录已经整理成可审计的 candidate pool；项目级 final gold、Stage 1 freeze 与 LS import 已在 `analysis_results/` 和 `import_json/` 中单独物化，但不应与目录层直接混写。
