<!-- PAPER_A_MACHINE_STATUS: superseded -->
# RQ3 Minimal Evidence-Chain Contract v1

> Last updated: 2026-07-17

## 0. Purpose

This document defines the minimum preconditions for the `RQ3` comparable evidence chain while `P1` is still running and `C1/C2` are not yet executed.

The goal is to prepare the minimum contracts needed for:

- `offline_replay`
- `dt` reference freezing
- meta-label consensus sidecar
- task-risk manifest materialization

It does **not** build the full online routing service.

## 1. Evidence Hierarchy

For the thesis-facing main line:

- primary comparable evidence for `RQ3` comes from `Calibration_manual` on offline replay / shadow support
- `V1` reports deployed frozen-strategy behavior
- `V1` alone must not be used as the only main comparative evidence source

## 2. Minimal Contract Set

The waiting-window minimum is the set below:

1. `dt_reference_summary_C1.json`
2. `meta_label_consensus_summary_v1.csv`
3. `offline_replay_run_config_v1.json`
4. `task_risk_rule_manifest_v1.json`
5. `failure_disposition_rule_manifest_v1.json`

## 3. `dt_reference_summary_C1.json`

This file is provisional in `C1` and becomes input to the final risk rule in `C2`.

It must at least tell downstream consumers:

- which calibration-only reference pool was used
- which embedding backend and model version were used
- which `K`, metric, and `q` were used
- which provisional `tau_d` candidate was formed
- whether any reference extraction failures occurred
- and the frozen `reference_pool` snapshot must be sufficient for deterministic recomputation of the thesis-facing `d_t` primary path

The summary must not read human labels, worker labels, or quality metrics into the `dt` calculation path.
Once materialized, the thesis-facing `d_t` primary scorer should prefer this contract artifact directly, rather than rely on an undeclared side manifest outside the round-based contract.

## 4. `meta_label_consensus_summary_v1.csv`

Purpose:

- provide a stable, auditable task-level consensus sidecar for `difficulty` and `model_issue`
- support scene candidate summaries, post-hoc non-IID audits, and later route-attribution explanation

Row grain:

- one row per `task_id`

Primary key:

- `task_id`

Required fields:

- `task_id`
- `base_task_id`
- `base_task_id_source`
- `dataset_group`
- `dataset_group_source`
- `n_annotations`
- `n_unique_annotators`
- `n_duplicate_annotator_rows`
- `n_difficulty_conflicted_annotators`
- `n_model_issue_conflicted_annotators`
- `difficulty_consensus`
- `difficulty_consensus_confidence`
- `model_issue_consensus`
- `model_issue_consensus_confidence`
- `consensus_method`
- `consensus_version`

Nullable fields:

- `secondary_difficulty_labels`
- `secondary_model_issue_labels`
- `consensus_notes`
- `dataset_group_conflict_values`
- `base_task_id_conflict_values`

Constraints:

- consensus is descriptive and audit-facing
- consensus must not be used to redefine scene taxonomy after `C1`
- consensus must not leak into `dt` computation
- sidecar materialization must audit `dataset_group` / `base_task_id` conflicts per `task_id`, and may fail fast when a thesis-facing export requires strict consistency
- thesis-facing default must first deduplicate to one vote unit per `(task_id, annotator_id)` before per-tag consensus
- if duplicate rows from the same annotator disagree on a field, that annotator must be excluded from that field's consensus denominator and counted in the audit layer, rather than silently counted multiple times

## 5. `offline_replay_run_config_v1.json`

Purpose:

- define a stable replay config without implementing the full service

Required keys:

- `meta`
- `split`
- `strategies`
- `candidate_pool_filters`
- `sequential_rule`
- `output_contract`

Required `meta` keys:

- `config_version`
- `seed`
- `created_from_round`

Required `split` keys:

- `split_mode`
- `source_split`
- `task_manifest_ref`

Required `strategies` values:

- `Random`
- `Global`
- `Full`

Required `sequential_rule` keys:

- `k0`
- `k_max`
- `stop_rule_version`
- `stop_threshold`

Required `output_contract` keys:

- `replay_results_path`
- `required_columns`

## 6. `task_risk_rule_manifest_v1.json`

Purpose:

- define the final task-side risk contract that later Validation and replay must read instead of notebook-only logic

Required keys:

- `meta`
- `dt_rule`
- `ood_trigger_rule`
- `g_trigger_rule`
- `risk_bucket_rule`
- `fallback_rule`

Required `dt_rule` keys:

- `source_artifact`
- `metric`
- `k`
- `q`
- `tau_d`

Required `risk_bucket_rule` keys:

- `bucket_names`
- `bucket_definition`
- `assignment_logic`
- `r3_default_policy`

Task-side bucket definition:

- bucket names must represent the cross-product of `I_t^{OOD}` and `g_t_triggered`
- worker-side tiers `R0 / R1 / R2 / R3` are not task buckets and must not be used as `bucket_names`

Recommended main-line bucket names:

- `ood0_g0`
- `ood0_g1`
- `ood1_g0`
- `ood1_g1`

Required `fallback_rule` keys:

- `scene_specific_unavailable_action`
- `dt_unavailable_action`
- `g_unavailable_action`

## 7. `failure_disposition_rule_manifest_v1.json`

Purpose:

- freeze the pre-result rule that distinguishes worker-caused structural failure, policy-caused failure, and external system failure across `C1/C2/T1/V1`
- make rerun and administrative-censoring decisions reproducible rather than outcome-selected

Required keys:

- `meta`
- `allowed_attributions`
- `external_evidence_requirements`
- `t1_rerun_rule`
- `v1_rerun_rule`
- `administrative_censor_rule`

`allowed_attributions` must contain exactly:

- `worker_caused_structural_failure`
- `policy_caused_failure`
- `external_system_failure`

`external_evidence_requirements` must require an incident identifier, occurrence/recovery time window, affected task/project scope, immutable evidence reference or digest, and record timestamp before outcome inspection. Missing evidence must resolve to `not_evaluable`, never silently to external failure.

`t1_rerun_rule` must require at most one rerun of the complete same-image `Manual/SemiAuto` pair; an incomplete pair is administratively censored as a pair. `v1_rerun_rule` must require at most one rerun in the same policy arm, same frozen version, and pre-reserved symmetric capacity. `administrative_censor_rule` must exclude qualifying external incidents from the delivery-adjusted quality denominator while requiring counts, reruns, censoring, and arm distributions in the audit output.

## 8. What Is Ready After This Document

After these contracts and templates exist, the repo is ready for:

- filling `C1` artifacts once calibration data arrives
- materializing replay config without changing protocol core
- building `task_risk_rule_manifest_v1.json` in `C2`
- freezing failure attribution, rerun, and censoring before Main outcomes exist

## 9. What Is Still Intentionally Deferred

Still deferred:

- actual `offline_replay.py`
- full `meta_label_consensus.py` engine
- live routing backend
- shadow deployment automation

Current status:

- a minimal formal `compute_dt_score.py` primary-path implementation may exist
- a minimal `meta_label_consensus_summary_v1.csv` materializer may exist before the full consensus engine is implemented

This is intentional. The current goal is to remove schema ambiguity and stand up minimal primary-path tooling before the data arrives. These materialized entry points do not imply that replay, full consensus, or live routing are already analysis-ready.
