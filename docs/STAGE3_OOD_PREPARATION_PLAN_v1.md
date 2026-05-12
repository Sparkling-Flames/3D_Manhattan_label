# Stage 3 OOD Preparation Plan v1

> Last updated: 2026-05-07

## 0. Scope

This document prepares the Stage 3 / Main-Validation / OOD-aware routing evidence chain before formal V1 execution.

It is a readiness and contract-planning document. It does not start V1, freeze C2 outputs, create Label Studio projects, or generate thesis-facing V1 artifacts.

Hard boundaries:

- Keep `Pilot -> PreScreen -> Calibration -> Main(Test + Validation)`.
- Keep `P1 / C1 / C2 / T1 / V1` boundaries.
- Do not use mock Stage 2 dry-run results as formal C1/C2 inputs.
- Do not use Main/Test/Validation outcomes to modify admission, `w_max`, worker tier, `tau_d`, Score, routing freeze, `k0/kmax`, or stop rules.
- Do not use `difficulty` or `model_issue` as pre-annotation non-IID split truth.
- Do not treat `analysis_results/` as an input source of truth.

Required dry-run flags for any future exploratory artifact:

- `dry_run_only=true`
- `no_C2_freeze_yet=true`
- `tau_d_not_final=true`
- `not_thesis_facing_artifact=true`

## 1. Current Stage Preconditions

P1 has not produced real admission outputs yet. Therefore the following are not available:

- `prescreen_worker_admission.csv`
- `prescreen_r0_snapshot.csv`
- `w_max_locked.json`
- `prescreen_blind_trust_audit.csv`
- `prescreen_scope_gate_audit.csv`
- `prescreen_round_report.md`

C2 has not frozen the Main-Validation routing contract. Therefore the following are not final:

- `LCB(r_u)`
- `R0 / R1 / R2 / R3`
- Score
- `r_u^(s)` activation / degeneration rules
- `tau_d`
- `I_t^{OOD}`
- `g_t`
- `k0 / kmax / stop rule`
- Validation routing contract

Stage 2 mock dry-run outputs may be used only to understand tool feasibility. They must not become thesis-facing C1/C2 artifacts and must not be used to generate formal V1 manifests.

## 2. `d_t` Readiness

Current repository status:

- `tools/compute_dt_score.py` exists.
- `tests/test_compute_dt_score.py` exists.
- The current implementation declares the primary embedding backend as `hohonet.shared_pre_head_gapw_l2`.
- The primary path includes shared pre-head feature extraction through HoHoNet, width/global feature pooling, L2 normalization, Euclidean KNN distance, leave-one-out calibration scoring, and q=90% provisional `tau_d`.
- The scorer supports `dt_reference_summary_C1.json` as the contract-shaped source artifact.
- The scorer rejects blacklisted post-labeling fields by default, including `difficulty` and `model_issue`, to protect against leakage.

Current readiness:

- Procedure-level readiness is partial.
- Contract-level readiness exists for `dt_reference_summary_C1.json`.
- Real data readiness is blocked until C1 materializes the calibration-only reference pool.
- Formal `tau_d` is blocked until C2 freeze.

Required C1/C2 path:

1. C1 builds `dt_reference_summary_C1.json` from `Calibration_manual` only.
2. C1 may report `provisional_tau_d`.
3. C2 checks reference health and freezes final `tau_d` without expanding the task-side calibration pool.
4. V1 reads the frozen task-risk contract rather than recomputing undeclared thresholds.

## 3. `g_t` Structural Diagnostic Gap

`g_t` is currently a contract-level risk proxy, not an executable diagnostic engine.

Minimum future field contract:

- `task_id`
- `base_task_id`
- `prediction_source`
- `prediction_version`
- `g_t_triggered`
- `g_t_score`
- `g_t_status`
- `g_t_failure_reasons`
- `polygon_construction_failure`
- `self_intersection`
- `invalid_corner_count`
- `odd_corner_count`
- `duplicated_corner_cluster`
- `topology_closure_failure`
- `geometry_normalization_failure`
- `render_failure`
- `g_t_compute_ts`
- `g_t_rule_version`

Allowed input source:

- pre-annotation model prediction or initialization `P_t`
- geometry/rendering diagnostics derived before human labels

Forbidden input source:

- human labels
- worker labels
- `difficulty`
- `model_issue`
- post-submission `IAA`
- Validation outcomes

Missing policy:

- Missing or failed `g_t` computation must be recorded as NA and reported.
- Missing `g_t` must not silently filter tasks.
- Missing `g_t` may trigger the future task-risk fallback rule only if that fallback is frozen by C2.

Implementation status:

- No formal `g_t` tool is assumed ready.
- No formal `g_t` schema test is assumed ready.
- A future tool change must add tests for all trigger fields and leakage protection.

## 4. `task_risk_rule_manifest_v1.json`

Current repository status:

- `tools/init_task_risk_rule_manifest.py` exists.
- `tests/test_init_task_risk_rule_manifest.py` exists.
- `docs/RQ3_MINIMAL_EVIDENCE_CHAIN_CONTRACT_v1.md` defines the minimum `task_risk_rule_manifest_v1.json` keys.
- `docs/C1_C2_ARTIFACT_FIELD_CONTRACT_v1.md` places `task_risk_rule_manifest_v1.json` in C2 final artifacts.

Formal creation rule:

- The manifest must not be formal before C2.
- The manifest must be initialized from a healthy `dt_reference_summary_C1.json`.
- The manifest must require non-null `tau_d` for thesis-facing use.
- The manifest must keep task buckets as the cross-product of `I_t^{OOD}` and `g_t_triggered`.

Expected bucket names:

- `ood0_g0`
- `ood0_g1`
- `ood1_g0`
- `ood1_g1`

Current blocker:

- No formal C1 `dt_reference_summary_C1.json`.
- No C2 freeze.
- No executable `g_t` diagnostic path.

## 5. Validation Candidate Pool, `Validation_OOD`, and Hard Subset `H`

This section defines readiness checks only. It does not sample V1 tasks or generate formal V1 artifacts.

### 5.1 Distinct construction rules

`Validation_OOD` and Hard subset `H` use different construction rules.

`Validation_OOD`:

- Defined only by `I_t^{OOD}=1`.
- Equivalently, `d_t > tau_d`.
- It does not include tasks only because `g_t` is high.

Hard subset `H`:

- Defined by `I_t^{OOD}=1 OR high_g_t=1`.
- It may include tasks that are not in `Validation_OOD`.
- It is expected to partially overlap with `Validation_OOD`, not equal it.

Forbidden construction:

- Do not use `difficulty` or `model_issue` for pre-annotation `Validation_OOD` construction.
- Do not use `difficulty` or `model_issue` for pre-annotation `H` admission.
- Do not backfill `H` with post-labeling tags to satisfy `|H| >= 30`.

Allowed post-labeling audit:

- After labels exist, use `difficulty` and `model_issue` consensus only to audit whether the hard semantic set `S_hard` is enriched.
- Report `S_hard` share for explanation, not for split construction.

### 5.2 Required readiness counts

Future readiness reports must include:

- `n_validation_candidates`
- `n_validation_ood = |Validation_OOD|`
- `n_hard_subset = |H|`
- `n_overlap = |Validation_OOD intersection H|`
- `n_validation_ood_only = |Validation_OOD \ H|`
- `n_h_only = |H \ Validation_OOD|`
- `overlap_rate_over_validation_ood = |Validation_OOD intersection H| / |Validation_OOD|`
- `overlap_rate_over_h = |Validation_OOD intersection H| / |H|`

Readiness gate:

- `|H| >= 30` is required for the planned Hard subset `H`.
- If `|H| < 30`, report a blocker or pre-registered downgrade.
- Do not use post-labeling `difficulty/model_issue` to repair this gate.

### 5.3 V1 candidate pool constraints

Validation candidate construction must wait for:

- frozen P1 worker admission
- frozen C2 `tau_d`
- frozen C2 task-risk rule
- frozen `g_t` rule or explicit C2 fallback
- frozen `k0 / kmax / stop rule`
- frozen Validation routing contract

No `V1_full_batch_*` Label Studio project may be created from this preparation document alone.

## 6. V1 Audit Schema Draft

The following is a schema planning checklist only. It is not a generated V1 artifact.

### 6.1 `task_risk_snapshot_V1.csv`

Minimum planned fields:

- `task_id`
- `base_task_id`
- `validation_pool`
- `d_t`
- `tau_d`
- `I_t_OOD`
- `g_t_triggered`
- `g_t_status`
- `g_t_failure_reasons`
- `task_risk_bucket`
- `task_risk_rule_version`
- `is_validation_ood`
- `is_hard_subset_h`
- `dry_run_only`
- `no_C2_freeze_yet`
- `tau_d_not_final`
- `not_thesis_facing_artifact`

### 6.2 `assignment_manifest_V1.csv`

Minimum planned fields:

- `round_id`
- `assignment_batch`
- `worker_id`
- `task_id`
- `base_task_id`
- `task_risk_bucket`
- `worker_risk_tier`
- `assignment_reason`
- `k0`
- `kmax`
- `manifest_version`

### 6.3 `stopcheck_log_V1.csv`

Minimum planned fields:

- `task_id`
- `check_index`
- `n_valid_annotations`
- `disagree_t`
- `stop_threshold`
- `stop_decision`
- `append_reason`
- `field_missing_flag`
- `gate_failure_flag`
- `stop_rule_version`

### 6.4 `routing_event_log_V1.jsonl`

Minimum planned event keys:

- `event_ts`
- `round_id`
- `task_id`
- `worker_id`
- `event_type`
- `policy_name`
- `task_risk_bucket`
- `candidate_pool_size`
- `selected_worker_rank`
- `fallback_applied`
- `fallback_reason`
- `rule_versions`

### 6.5 `online_audit_summary_V1.json`

Minimum planned keys:

- `meta`
- `input_contracts`
- `task_risk_summary`
- `validation_ood_summary`
- `hard_subset_h_summary`
- `routing_summary`
- `stopcheck_summary`
- `fallback_summary`
- `ce_only_distribution_audit`
- `not_thesis_facing_if_dry_run`

### 6.6 `validation_round_report.md`

Required planned sections:

- inputs used
- frozen contracts checked
- forbidden updates checked
- Validation candidate summary
- `Validation_OOD` and `H` overlap summary
- routing / fallback summary
- stop-check summary
- OOD / Hard subset result summary
- CE-only distribution audit
- remaining risks

## 7. Readiness Gates and Blockers

Can be done now:

- Read-only readiness checks.
- Contract gap analysis.
- Dry-run planning.
- Drafting this preparation document.

Must wait for P1:

- formal worker admission
- formal `w_max`
- formal PreScreen audit inputs

Must wait for C1:

- real calibration reference pool
- `dt_reference_summary_C1.json`
- provisional `tau_d`
- provisional scene and worker statistics

Must wait for C2:

- frozen `tau_d`
- frozen Score
- frozen `r_u^(s)` activation / degeneration rules
- frozen worker risk tiers
- frozen task-risk manifest
- frozen `k0 / kmax / stop rule`
- frozen Validation routing contract

Must not be done from this document:

- generate `assignment_manifest_V1.csv`
- generate `task_risk_snapshot_V1.csv`
- generate `routing_event_log_V1.jsonl`
- create `V1_full_batch_*` Label Studio projects
- freeze `tau_d`
- freeze Score
- freeze `r_u^(s)` rules
- implement a live routing service

## 8. Verification Plan

For this documentation-only preparation step:

- `git status --short`
- `rg -n "Validation_OOD|Hard subset|I_t\^\{OOD\}|g_t|difficulty/model_issue|STAGE3_OOD_PREPARATION" docs/STAGE3_OOD_PREPARATION_PLAN_v1.md docs/README_INDEX.md docs/PROJECT_MAP_CLEAN_20260308.md`
- `rg -n "AGENT_CONTEXT_INDEX|agent_playbooks|STATISTICAL_ANALYSIS_PLAN|LS_CE_ONLY" AGENTS.md docs/README_INDEX.md docs/PROJECT_MAP_CLEAN_20260308.md docs/AGENT_CONTEXT_INDEX.md docs/agent_playbooks`

If future work changes `d_t` or task-risk tools:

- `pytest tests/test_compute_dt_score.py`
- `pytest tests/test_init_task_risk_rule_manifest.py`

If future work adds a `g_t` executable:

- add tests covering every trigger field
- add tests for missing policy
- add tests for schema completeness
- add tests proving no post-labeling `difficulty/model_issue` fields are accepted as pre-annotation split truth
