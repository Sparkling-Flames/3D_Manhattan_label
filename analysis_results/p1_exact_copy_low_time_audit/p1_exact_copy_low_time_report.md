# P1 Exact-Copy Low-Time Process-Integrity Audit

## Scope

- This is a process-integrity audit, not a geometry quality metric.
- This is a high-precision exact-copy-low-time detector, not a complete collusion detector.
- It checks only exact canonical corner-geometry duplicates combined with anomalously low primary active_time.
- It does not implement near-duplicate, small-edit copy, IoU-similarity, or BoundaryRMSE-similarity detection.
- It does not silently delete annotations or workers; outputs are warning / manual_review / fail_recommended only.

## Timing Boundary

- `active_time` from active logs is the primary timing source.
- Label Studio `lead_time` is reported only as fallback/audit by default and is not mixed into the primary event rule.
- `lead_time` can enter primary events only if the CLI explicitly enables it.
- Active-log start/end bounds are recorded to prevent cross-round active_time accumulation.

## Conservative Worker-Level Rule

- A small number of low-time tasks does not trigger exclusion.
- Semi-auto tasks with high-quality initialization can legitimately be fast.
- Therefore review/fail decisions use worker-level event counts and rates, not a single-task low-time flag.

## Default Thresholds Used

- `min_valid_tasks_for_worker`: 10
- `event_active_time_ratio`: 0.25
- `event_active_time_floor_sec`: 10.0
- `manual_review_min_events`: 5
- `manual_review_rate`: 0.3
- `fail_recommended_rate`: 0.7
- `fail_if_all_valid`: True
- `geometry_round_px`: 0.5
- `assume_p1_export`: False
- `active_log_start`: 
- `active_log_end`: 

## Run Summary

- `n_tasks_in_export`: 114
- `n_tasks_included`: 114
- `n_tasks_filtered_out`: 0
- `n_annotation_rows`: 1485
- `parse_error_count`: 31
- `unknown_worker_count`: 0
- `stage_filter_task_breakdown`: `{"explicit_p1": 114}`
- `n_primary_exact_copy_low_time_events`: 25
- `n_fallback_low_time_duplicate_audit`: 34
- `n_workers_manual_review`: 3
- `n_workers_fail_recommended`: 0

## Protocol Boundary

- This audit does not change P1 manual / semi / OOS pool definitions.
- This audit does not change `r_u^(0)`, `w_max`, blind-trust, or scope-gate formulas.
- This audit does not upgrade PreScreen output into a formal routing profile.
- Final exclusion decisions must be made by manual review or downstream admission summary logic.
