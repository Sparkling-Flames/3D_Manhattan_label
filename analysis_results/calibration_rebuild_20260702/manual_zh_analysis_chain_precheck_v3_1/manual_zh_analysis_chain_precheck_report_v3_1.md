# manual_zh analysis-chain precheck v3.1

本检查只是 manual_zh smoke fixture，用于验证 analysis-chain integration，不是 C1 statistical closeout。

- passed: False
- statistical_interpretation_allowed: False
- full_c1_smoke_test_passed: False
- annotation_id_present_count: 4
- annotation_level_log_match_count: 0
- task_level_fallback_count: 4
- outside_assignment_submission_count: 1
- duplicate_worker_task_submission_count: 0
- worker_facing_bare_inner_id_ambiguity_detected: True

已检查字段方向：annotation_id 保留、canonical_annotation_id 生成、active-log 不使用 lead_time 作为 primary、planned_inner_id 不替代 LS runtime task id。

待 full C1 export 后验证：全 worker 覆盖、全部项目导出、正式 realized-vs-assigned、完整 active-log 行为事件。

## Blockers
- outside_assignment_submission_detected

## Warnings
- active_log_task_level_fallback_only
- bare_inner_id_ambiguous_across_projects_use_entry_plus_inner_id
- behavior_not_strictly_verified_for_some_rows
