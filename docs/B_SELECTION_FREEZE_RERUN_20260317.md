# B 线 Selection Freeze 绑定重跑记录（2026-03-17）

## 本轮目标

仅做 selection freeze 口径收口，不扩 B 线功能面：
1. 显式 selection manifest 绑定重跑。
2. Main-facing selection 口径校正。
3. 新增 selection provenance gate，防止把 autogen 派生选择误写为 thesis-ready。

## 输入

1. `analysis_results/selection_freeze_20260317/thesis_selection_manifest_v1_20260317.json`
2. `analysis_results/selection_freeze_20260317/thesis_selection_main_facing_v1_20260317.json`

说明：当前仓库数据仍是测试数据，且含旧版本数据。

## 输出目录

1. `analysis_results/stage_aware_analysis_freeze_v2_1_selection_v1_20260317/`
2. `analysis_results/stage_aware_analysis_freeze_v2_1_main_facing_v1_20260317/`

## 修复动作（代码级）

1. 修正 `apply_selection_manifest` 的匹配语义：从“列级 OR 宽匹配”改为“行级 AND + 行间 OR”严格匹配，避免 Main-facing selection 被无关行放大。
2. 新增 `selection_provenance_audit_v2_1.json`，输出 source chain 与 autogen 派生状态。
3. 将 provenance gate 接入 `thesis_readiness_status` / `thesis_readiness_blockers`。

## 关键状态核验（最终以 main-facing 重跑为准）

1. selection 来源与模式
   - `selection_manifest_mode = provided`
   - `selection_manifest_path = analysis_results/selection_freeze_20260317/thesis_selection_main_facing_v1_20260317.json`
2. Main-facing gate
   - `selection_main_facing_passed = true`
   - `dataset_group_counts = {SemiAuto_Test:41, Validation_semi:23, Gold_manual:9}`
   - `non_main_groups_present = []`
3. provenance gate
   - `selection_derived_from_autogen_default_gate = true`
   - `selection_source_independent_from_autogen = false`
   - `source_chain_depth = 3`
4. stage1 alignment
   - `stage1_alignment_passed = false`
   - blockers: `stage1_manual_anchor_not_aligned`, `stage1_prescreen_semi_not_aligned`
5. thesis readiness blockers
   - `thesis_selection_ready = false`
   - `thesis_readiness_status = blocked_selection_not_independent_from_autogen_and_stage1_protocol_not_aligned`
   - `thesis_readiness_blockers = ["selection_not_independent_from_autogen", "stage1_protocol_not_aligned"]`
6. active_time estimand
   - `active_time_endpoint_status = mixed_estimand_log_plus_fallback`
   - `primary_endpoint_ready = false`
   - `active_time_source_counts = {lead_time_fallback:50, log:23}`
7. consistency gate
   - `consistency_gate_passed = true`
   - `type4_in_m_row_audit = 0`
   - `type4_in_m_type4_evidence = 0`

## 结论

1. “selection 路径为空”问题已修复，且 Main-facing selection 过滤已变为严格匹配。
2. 当前 selection 仍是 autogen 链路派生，不可表述为独立 thesis-facing selection。
3. 口径必须保持：`B: partial / formal-prep-freeze-v2.1`，不得写成 formal analysis 完成或 thesis-facing 闭环。
