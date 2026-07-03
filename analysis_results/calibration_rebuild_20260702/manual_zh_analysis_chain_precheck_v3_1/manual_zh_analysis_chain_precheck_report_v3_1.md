# manual_zh analysis-chain precheck v3.1

本检查只覆盖 manual_zh smoke fixture，用于验证 analysis-chain integration，不是 C1 statistical closeout。

- passed: True
- statistical_interpretation_allowed: False
- full_c1_smoke_test_passed: False
- annotation_id_present_count: 3
- annotation_level_log_match_count: 0
- task_level_fallback_count: 3
- annotation_id_alignment_status: task_level_only_log_annotation_id_does_not_match_export_annotation_id
- outside_assignment_submission_count: 0
- duplicate_worker_task_submission_count: 0
- worker_facing_bare_inner_id_ambiguity_detected: False
- worker_facing_task_code_identity_passed: True

已检查字段方向：annotation_id 保留、canonical_annotation_id 生成、active-log 不使用 lead_time 作为 primary、planned_inner_id 不替代 LS runtime task id。

待 full C1 export 后验证：全 worker 覆盖、全部项目导出、正式 realized-vs-assigned、完整 active-log 行为事件。

## Warnings
- active_log_task_level_fallback_only
- log_annotation_id_does_not_match_export_annotation_id_primary_binding_is_task_session_level
- source_export_bare_inner_id_ambiguous_across_projects_task_code_required
- outside_assignment_rows_filtered_into_negative_guard_fixture
- behavior_not_strictly_verified_for_some_rows
