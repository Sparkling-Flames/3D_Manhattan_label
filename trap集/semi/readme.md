# semi 目录说明

本目录保存当前 `PreScreen_semi` 的自然候选样本池。

## 当前解释规则

1. 目录里有某个 `task`，表示当前已经收集到一个对应 family 的自然候选。
2. 目录里暂时没有某个 family，不等于协议上没有这个 family；也可能只是当前还没有稳定自然样本，或尚未物化 synthetic asset。
3. 本目录始终只是 `semi candidate pool`，不等于最终的 `semi final selection` 或 Label Studio 导入文件。

## 当前 thesis-facing 默认理解

- `模型标注质量好`：当前主要对应 `control` 候选。
- `跨门扩张 / 过度解析 / 角点错位 / 角点重复`：当前默认主 `semi trap` 的 4 个核心 family。
- `漏标`：当前保留为正式 `extension family`，不进入默认主 12 张 trap 配额，但在附录算子库、natural-failure bank 和 lifecycle audit 中继续保留。
- `模型预标注失败`：当前只保留为 `low-priority / optional / holdout`，不进入活跃主包。
- `拓扑崩溃`：当前仍无已落盘任务；它可以作为后续 `audit-only / robustness-only synthetic family`，但不是当前启动 prescreen 的前提。

## 当前与导入层相关的补充说明

- 目录里的 `.txt` 只保留为 `legacy_mp3d_reference`，不作为 `semi` 初始化主源。
- `semi` 的 `control` 与 `natural trap` 初始化 proposal 来自：
  - `output/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34/*.txt`
- `semi synthetic trap` 继续沿用：
  - `analysis_results/trap_collection_freeze_20260320/semi_synthetic_disjoint_candidate_bank_v2.jsonl`

## 当前正式 freeze 口径

以 [prescreen_semi_final_selection_v10.json](d:/Work/HOHONET/analysis_results/phase1_progress_20260324/prescreen_semi_final_selection_v10.json) 为准：

- 主 `semi` 仍是 `6 control + 12 traps`
- natural `corner_drift` 已改为 `task625`
- `overextend_adjacent` 在主 trap 中已按 `natural-only` 收口
- 当前主包里的 natural `overextend_adjacent` 是：
  - `task493`
  - `task577`
  - `task668`
- `task580` 现在保留为：
  - `special_review reserve`
  - `multi-issue natural case`
  - `primary_family = overextend_adjacent`
- `task665` 现在作为新增 `underextend` 自然候选，继续留在 extension family 池中
- `task475` 当前不在活跃 `semi_audit_stress`，只保留在 `fail holdout`

对应当前导入文件是：
- [stage1_prescreen_semi_import_v5.json](d:/Work/HOHONET/import_json/stage1_prescreen_final_20260325/stage1_prescreen_semi_import_v5.json)
- [stage1_prescreen_semi_audit_stress_import_v3.json](d:/Work/HOHONET/import_json/stage1_prescreen_final_20260325/stage1_prescreen_semi_audit_stress_import_v3.json)
- [stage1_prescreen_semi_audit_holdout_v2.json](d:/Work/HOHONET/import_json/stage1_prescreen_final_20260325/stage1_prescreen_semi_audit_holdout_v2.json)

## 当前不应误读的地方

- 不要把 `semi` 理解成“全部都是误导性 trap”。
- 不要把当前目录直接当成最终 `semi` 导入清单。
- 不要把 `模型预标注失败` 自动抬成默认 core family。
- 不要把 `task580` 说成纯净 exemplar；它当前应被理解为带次级问题的复核样本。

## 当前最准确的说法

> `semi/` 现在表示的是 natural candidate registry。最终哪些进入 `control`、哪些进入主 `trap`、哪些只保留在 `holdout / audit`，应以后续 freeze 与导入文件为准。
