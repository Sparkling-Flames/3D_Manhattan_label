<!-- PAPER_A_MACHINE_STATUS: superseded -->
# Final Gold Rebinding Contract v1

本说明只定义一件事：当项目自己的 `final adjudicated gold` 到位后，如何把当前已经冻结的 Stage 1 selection manifest 重新绑定到 final gold，而不是重做 selection 设计。

## 当前入口

- 脚本：
  [rebind_stage1_to_final_gold.py](d:\Work\HOHONET\tools\thesis_main\registry\rebind_stage1_to_final_gold.py)
- 当前被重绑的 freeze：
  - [prescreen_manual_final_selection_v1.json](d:\Work\HOHONET\analysis_results\phase1_progress_20260324\prescreen_manual_final_selection_v1.json)
  - [prescreen_semi_final_selection_v5.json](d:\Work\HOHONET\analysis_results\phase1_progress_20260324\prescreen_semi_final_selection_v5.json)
  - [oos_final_quota_binding_v1.json](d:\Work\HOHONET\analysis_results\phase1_progress_20260324\oos_final_quota_binding_v1.json)

## final gold 输入格式

脚本当前接受：

- `CSV`
- `JSONL`

每条 row 至少需要这些字段：

- `task_id`
- `final_scope_alias`
- `final_scope_binary`
  - 只允许 `in_scope` 或 `oos`
- `geometry_gold_ready`
  - 对 manual / semi 的 in-scope row 有效
- `scope_gold_ready`
  - 对 OOS row 有效
- `adjudication_status`
  - 当前必须等于 `final_adjudicated_gold`

可选字段：

- `base_task_id`
- `notes`

## 当前重绑规则

### manual

- 复用当前已经冻结的 `22 anchors + 8 non-anchor`
- 若 final gold 中：
  - task 缺失
  - scope 不再是 `in_scope`
  - `geometry_gold_ready != true`
  则该 row 视为 rebinding failed

### semi

- 复用当前已经冻结的 `6 control + 12 trap`
- `control` 和 `natural trap` 必须在 final gold 里通过 in-scope + geometry-ready 检查
- synthetic trap 不去 latest export 里找人工 annotation，而是按当前 frozen synthetic asset 直接 carry-forward

### OOS

- 复用当前已经冻结的 `9 gate + 1 audit-only`
- 进入 OOS gate 的 row 必须在 final gold 中通过：
  - `final_scope_binary = oos`
  - `scope_gold_ready = true`

## 输出文件

脚本会生成：

- `manual_binding_audit_v2.json`
- `prescreen_semi_final_selection_v6.json`
- `oos_final_quota_binding_v2.json`
- `stage1_final_binding_audit_v2.json`

## 当前边界

- 这一步是 `rebind`，不是 `reselect`
- 如果 final gold 推翻了当前 freeze 中的个别样本，应先显式暴露 `missing / mismatch / not_ready`
- 只有在 rebinding failed 的前提下，才进入最小替换，而不是回头重做 family policy
