# C1/C2 Artifact Field Contract v1

> Last updated: 2026-03-28

## 0. Scope

This document defines the minimum field contract for the round-based Calibration artifacts that are already frozen at the protocol level but not yet fully materialized as scripts.

It does **not**:

- freeze `Score`
- freeze `N_{u,s,min}`
- freeze `tau_d`
- decide which workers pass `P1`

It only turns the existing round contract into explicit file-level schemas.

## 1. General Rules

- All `C1` artifacts are provisional.
- All `C2` artifacts are final for the thesis-facing main line.
- `P1` outputs may be referenced, but `C1/C2` must not rewrite `P1` admission or `w_max`.
- `C2` may only use `Calibration_reserve` for worker-side insufficiency correction.
- No artifact may depend on future `T1/V1` outcomes.

Recommended upstream input manifest:

- `calibration_round_input_manifest_v1.json`

Its role is to freeze the admitted worker snapshot plus the `Calibration_anchor/core/reserve` task lists that the later `assignment_manifest_C1.csv` and `assignment_manifest_C2.csv` must read from, rather than rebuilding these inputs ad hoc in notebooks.

## 2. C1 Artifacts

### 2.1 `worker_state_snapshot_C1.csv`

Purpose:

- one-row-per-worker provisional worker state after `Calibration_anchor + Calibration_core`

Row grain:

- `worker_id`

Primary key:

- `worker_id`

Required fields:

- `worker_id`
- `round_id`
- `admission_status`
- `r0_prescreen`
- `w_max_locked`
- `n_anchor_completed`
- `n_core_completed`
- `n_calib_completed`
- `r_u_hat`
- `r_u_ci_low`
- `r_u_ci_high`
- `r_u_h`
- `needs_c2_ci_fill`
- `needs_c2_scene_fill`
- `worker_state_version`

Nullable fields:

- `blind_trust_pre_flag`
- `notes`

Field provenance:

- from `P1`: `admission_status`, `r0_prescreen`, `w_max_locked`, `blind_trust_pre_flag`
- from `C1`: completion counts, `r_u_hat`, CI fields, `needs_c2_*`

### 2.2 `scene_candidate_summary_C1.csv`

Purpose:

- provisional scene-level summary used to form `S_core` candidates after `C1`

Row grain:

- `scene_label`

Primary key:

- `scene_label`

Required fields:

- `scene_label`
- `round_id`
- `n_tasks`
- `n_workers_exposed`
- `scene_frequency`
- `scene_consistency_kappa`
- `rank_by_frequency`
- `rank_by_consistency`
- `is_provisional_core_candidate`
- `candidate_reason`

Nullable fields:

- `notes`

### 2.3 `dt_reference_summary_C1.json`

Purpose:

- provisional summary of the calibration-only reference pool and leave-one-out threshold sidecar

Required top-level keys:

- `meta`
- `reference_pool`
- `loo_summary`
- `failure_audit`

Required `meta` keys:

- `round_id`
- `source_split`
- `pool_size`
- `dedup_key`
- `model_version`
- `embedding_backend`
- `distance_metric`
- `k`
- `q`
- `provisional_tau_d`
- `reference_pool_hash`
- `frozen_at`
- `selection_strategy`

Required `reference_pool[*]` keys:

- `task_id`
- `base_task_id`
- `image_id`
- `image_path`
- `source_split`
- `inclusion_rank`
- `embedding_hash`

Required `loo_summary` keys:

- `n_ref_success`
- `n_ref_fail`
- `loo_score_min`
- `loo_score_median`
- `loo_score_max`
- `provisional_tau_d`

Required `failure_audit` keys:

- `extract_fail_count`
- `embed_dim_error_count`
- `knn_runtime_error_count`
- `ref_hash_mismatch`
- `leakage_check_failed`

Contract note:

- `task_risk_rule_manifest_v1.json` must not be initialized from a `dt_reference_summary_C1.json` whose `failure_audit` indicates an unhealthy upstream state, unless an exploratory-only override is made explicit outside thesis-facing frozen outputs.
- `dt_reference_summary_C1.json` is not only descriptive; it must be sufficient for deterministic reuse by the thesis-facing `d_t` primary path once `C1` materializes.

### 2.4 `ci_precision_audit_C1.csv`

Purpose:

- worker-level precision audit for deciding `C2` CI补派

Row grain:

- `worker_id`

Required fields:

- `worker_id`
- `round_id`
- `n_calib_completed`
- `r_u_ci_low`
- `r_u_ci_high`
- `r_u_h`
- `epsilon_r`
- `needs_c2_ci_fill`
- `ci_fill_reason`

### 2.5 `scene_coverage_gap_C1.csv`

Purpose:

- worker-by-scene gap table for deciding `C2` scene coverage补派

Row grain:

- `worker_id + scene_label`

Primary key:

- `worker_id`
- `scene_label`

Required fields:

- `worker_id`
- `scene_label`
- `round_id`
- `n_u_s`
- `n_u_s_min_candidate`
- `coverage_gap`
- `activation_candidate`
- `needs_c2_scene_fill`
- `scene_fill_reason`

### 2.6 `assignment_manifest_C1.csv`

Purpose:

- auditable record of which `Calibration_anchor/core` tasks were assigned to which admitted worker in `C1`

Row grain:

- one row per `(round_id, worker_id, task_id)`

Primary key:

- `round_id`
- `worker_id`
- `task_id`

Required fields:

- `round_id`
- `worker_id`
- `task_id`
- `base_task_id`
- `dataset_group`
- `assignment_batch`
- `assignment_reason`
- `is_common_anchor`
- `expected_completion_order`
- `manifest_version`

Allowed `assignment_reason` values:

- `common_anchor`
- `balanced_core`

### 2.7 `calibration_round1_report.md`

Required sections:

- inputs used
- admitted worker count
- completion summary
- provisional worker reliability summary
- provisional scene candidate summary
- provisional `tau_d` summary
- `C2` fill list overview
- known failures / degradations

## 3. C2 Artifacts

### 3.1 `worker_state_snapshot_C2_final.csv`

Purpose:

- final one-row-per-worker state after reserve-only补齐

Required fields:

- `worker_id`
- `round_id`
- `r_u_hat_final`
- `r_u_ci_low_final`
- `r_u_ci_high_final`
- `r_u_h_final`
- `worker_risk_tier`
- `worker_group_reason`
- `c2_fill_applied`
- `c2_fill_type`
- `state_locked`

Nullable fields:

- `r_u_s_status_summary`
- `notes`

### 3.2 `scene_contract_locked_v1.json`

Purpose:

- final locked scene contract after `C2`

Required keys:

- `meta`
- `core_scenes`
- `activation_rules`
- `degeneration_rules`

Required `meta` keys:

- `round_id`
- `contract_version`
- `locked_at`
- `max_core_scene_count`

Required `core_scenes[*]` keys:

- `scene_label`
- `rank_final`
- `included_in_core`
- `n_u_s_min_locked`
- `activation_rate`
- `degeneration_rate`

### 3.3 `task_risk_rule_manifest_v1.json`

Purpose:

- final task-side risk contract consumed by later Validation routing and replay

Required keys:

- `meta`
- `dt_rule`
- `ood_trigger_rule`
- `g_trigger_rule`
- `risk_bucket_rule`
- `fallback_rule`

Required `g_trigger_rule` keys:

- `source`
- `definition`
- `missing_policy`

### 3.4 `assignment_manifest_C2.csv`

Purpose:

- auditable reserve-only补派 record

Row grain:

- one row per `(round_id, worker_id, task_id)`

Required fields:

- `round_id`
- `worker_id`
- `task_id`
- `base_task_id`
- `dataset_group`
- `assignment_batch`
- `fill_type`
- `fill_reason`
- `manifest_version`

Allowed `fill_type` values:

- `ci_precision_fill`
- `scene_coverage_fill`

### 3.5 `reserve_usage_audit_C2.csv`

Purpose:

- explicit proof that `C2` stayed inside reserve-only, worker-side补齐

Row grain:

- one row per `worker_id + fill_type`

Required fields:

- `worker_id`
- `fill_type`
- `n_reserve_tasks_assigned`
- `trigger_metric`
- `trigger_threshold`
- `task_side_pool_modified`
- `reserve_misuse_flag`

### 3.6 `calibration_freeze_report_v1.md`

Required sections:

- `C1 -> C2` carry-over summary
- reserve usage summary
- final worker-state freeze summary
- final scene-contract freeze summary
- final task-risk-rule summary
- downgrade cases and reasons

## 4. Deliberately Deferred

This contract intentionally does **not** define:

- a live routing service
- online shadow deployment
- final `V1` automation
- notebook-specific intermediate tables

Those are downstream engineering layers, not the minimum waiting-window deliverable.
