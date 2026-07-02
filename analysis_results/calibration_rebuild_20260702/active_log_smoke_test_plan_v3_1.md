# C1 v3.1 active_log smoke test plan

Status: planned only. Do not launch C1 and do not send worker messages.

## Scope

- Chinese entry: one test worker.
- Overseas entry: one test worker.
- Projects: `C1_anchor_all`, `C1_core_all`, `C1_semi`.
- Reserve is excluded; `C2_reserve_draft_only` is not tested as C1 worker-facing flow.

## Checks

1. Open the assigned task by `inner_id` from `worker_distribution_internal_manifest_v3_1.csv`.
2. Confirm task identity fields are recorded: `task_id`, `inner_id`, `worker_id`.
3. Confirm active-log identity fields are recorded: `active_time`, `session_id`, `script_version`.
4. Exercise pause/resume and verify paused time is not counted as active time.
5. Exercise tab switch away/back and verify inactive time is not counted as active time.
6. Submit one test annotation and confirm the final active-time event is flushed.
7. Check log landing path and filename convention.
8. Match emitted log manifest rows back to assignment manifest and internal worker distribution.

## Pass Criteria

- `task_id`, `inner_id`, `worker_id`, `active_time`, `session_id`, and `script_version` are present.
- Pause/resume and tab-switch behavior match active-time rules.
- Submit flushes a final active-time event.
- Log path and manifest rows align with the assigned worker/task pair.
