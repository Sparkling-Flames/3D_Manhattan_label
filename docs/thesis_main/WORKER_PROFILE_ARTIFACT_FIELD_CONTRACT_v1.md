# WORKER_PROFILE_ARTIFACT_FIELD_CONTRACT_v1

> Status: thesis-facing artifact field contract
> Scope: Paper A worker-profile sidecar / C1-C2 closeout
> Date: 2026-07-04
> Intended repository path: `docs/thesis_main/WORKER_PROFILE_ARTIFACT_FIELD_CONTRACT_v1.md`

## 0. Purpose

This document is the field-level companion contract for:

```text
docs/thesis_main/WORKER_PROFILE_AND_THESIS_OUTLINE_AMENDMENT_v1.md
```

The amendment document defines the thesis-outline and analysis logic. This document defines the concrete artifact schemas, inclusion flags, support-status rules, and required tests.

This file does not authorize any change to the already-launched C1 distribution.

---

## 1. Required artifacts

C1 sidecar outputs:

```text
worker_task_evidence_table_C1.csv
worker_profile_main_matrix_C1.csv
worker_failure_family_response_C1.csv
worker_subfamily_response_C1.csv
worker_profile_sidecar_C1.summary.json
p1_to_c1_predictive_validity.csv
p1_to_c1_predictive_validity_report.md
```

C2 final outputs:

```text
worker_task_evidence_table_C2_final.csv
worker_profile_main_matrix_C2_final.csv
worker_failure_family_response_C2_final.csv
worker_subfamily_response_C2_final.csv
worker_profile_sidecar_C2_final.summary.json
```

Optional C2b diagnostic-extension outputs:

```text
assignment_manifest_C2b_diagnostic_extension.csv
worker_profile_c2b_extension_audit.csv
c2b_exclusion_from_primary_r_u_calib_audit.json
```

---

## 2. Vocabulary contracts

### 2.1 Stage

Allowed values:

```text
P1
C1
C2
C2b
T1
V1
```

For this contract, C1 sidecar generation should only consume:

```text
P1
C1
```

C2 final sidecar may consume:

```text
P1
C1
C2
```

C2b may be appended only as diagnostic evidence and must not enter primary `r_u^calib`.

### 2.2 Dataset group

Allowed values:

```text
PreScreen_manual
PreScreen_semi
PreScreen_oos
Calibration_anchor
Calibration_core
Calibration_reserve
Calibration_semi
C2b_diagnostic_extension
```

### 2.3 Condition

Allowed values:

```text
manual
semi
oos_gate
diagnostic_extension
unknown
```

### 2.4 Scope binary

Allowed values:

```text
in_scope
oos
unknown
```

OOS subtype is expert audit metadata only and must not be used as the worker main correctness target.

Allowed OOS subtype metadata:

```text
oos_geometry
oos_open_boundary
oos_split_level
oos_insufficient
oos_unspecified
none
unknown
```

### 2.5 Worker scope response

Allowed values:

```text
correct_in_scope
correct_oos
scope_false_positive
scope_false_negative
unknown_or_missing
not_evaluable
```

### 2.6 Geometry reference status

Allowed values:

```text
expert_hard_single
expert_hard_multi
consensus_reference
soft_ambiguous
scope_ambiguous
audit_only
unavailable
```

### 2.7 Failure family

First-level vocabulary is frozen:

```text
geometry_quality_failure
scope_oos_failure
semi_correction_failure
undercoverage_failure
process_failure
```

### 2.8 Subfamily

Allowed second-level subfamily vocabulary:

```text
normal_geometry_degraded
occlusion_geometry_degraded
seam_or_stretch_geometry_degraded
low_texture_geometry_degraded
open_boundary_geometry_degraded
topology_or_pairing_failure
dense_corner_or_short_wall_failure

scope_false_positive
scope_false_negative
mixed_scope_disagreement
unresolved_scope_case

blind_trust
failed_correction
semi_corner_drift_not_fixed
semi_corner_duplicate_not_fixed
semi_overextend_not_fixed
semi_over_parsing_not_fixed
semi_underextend_not_fixed
successful_correction

partial_undercoverage
inner_space_only
minimal_space_bias
full_room_compliance_failure
overextended_adjacent_when_in_scope

active_time_missing_or_ineligible
duplicate_same_geometry
revision_time_ambiguous
schema_invalid
assignment_mismatch
outside_manifest_submission
```

Additional subfamilies may be added only with a contract update and must be marked as exploratory unless frozen before C1 closeout.

2026-07-12 contract amendment adds `non_independent_submission` to `process_failure`. Process reliability uses all worker-attributable `process_evaluable` tasks as its denominator and `process_failure_observed` as its numerator; zero denominator is NA. System collection issues and unattributable timing gaps are excluded from the denominator.

P1 task evidence additionally carries formal scope, semi-response and undercoverage provenance plus their SHA-256 values. Missing dimension artifacts are `not_evaluable` and never implicit success. P1 geometry components must declare metric name, direction and normalization; only compatible stage/pool components may be combined, and fewer than two compatible components leaves the integrated geometry reliability empty.

2026-07-12 follow-up: `undercoverage_risk_level` is a dry-run candidate/audit proxy only. It cannot create `undercoverage_response`, `undercoverage_subfamily`, `undercoverage_failure_observed`, or `included_in_U_u` without an explicit expert verdict. Allowed verdicts are `confirmed_full_room_attempt`, `confirmed_partial_undercoverage`, `confirmed_inner_space_only`, `confirmed_minimal_space_bias`, `confirmed_overextended_adjacent`, `rejected_proxy_false_positive`, `pending_review`, and `not_evaluable`.

Main-matrix directions are fixed: `r_geometry_u`, `r_scope_u`, `correction_reliability_u`, `coverage_reliability_u`, and `process_reliability` are higher-is-better. `blind_trust_or_correction_failure_rate` and `undercoverage_failure_rate` are higher-is-worse. Legacy `T_u` and `U_u` retain the latter risk-rate meaning and emit explicit direction fields; they are not components of the all-positive diagnostic vector.

`process_ok` is permitted only as a process-evaluable success label in the evidence/subfamily output. It is not a failure taxonomy member and never increments `n_fail`.

### 2.9 Support status

Allowed values:

```text
insufficient
weak
moderate
sufficient
not_evaluable
```

Default thresholds:

```text
insufficient: n_observed < 3
weak:         3 <= n_observed < 5
moderate:     5 <= n_observed < 10
sufficient:   n_observed >= 10
```

Second-level subfamily reportable condition:

```text
n_observed >= 8
and task_count >= 4
and subfamily_global_worker_coverage >= 6
```

Threshold sensitivity may be reported, but raw evidence rows must not change.

### 2.10 Interpretation level

Allowed values:

```text
none
weak_descriptive
moderate_descriptive
sufficient_descriptive
```

Default mapping:

```text
n_observed < 3:       none
3 <= n_observed < 5:  weak_descriptive
5 <= n_observed < 10: moderate_descriptive
n_observed >= 10:     sufficient_descriptive
```

---

## 3. Inclusion flags

Every worker-task evidence row must explicitly state whether it contributes to each estimator/profile dimension.

Fields:

```text
included_in_r_u_calib
included_in_r_geometry
included_in_r_scope
included_in_T_u
included_in_U_u
included_in_process_reliability
```

All inclusion flags must be serialized as lowercase strings:

```text
true
false
```

### 3.1 `included_in_r_u_calib`

True only if:

```text
stage in {C1, C2}
dataset_group in {Calibration_anchor, Calibration_core, Calibration_reserve}
condition = manual
task_final_scope = in_scope
geometry_reference_status in {consensus_reference, expert_hard_single, expert_hard_multi}
geometry_valid = true
process_invalid = false
used_for_r_u = true
```

False if:

```text
dataset_group = Calibration_semi
dataset_group in {PreScreen_manual, PreScreen_semi, PreScreen_oos}
stage = C2b
task_final_scope = oos
condition != manual
process_invalid = true
geometry_reference_status in {soft_ambiguous, scope_ambiguous, audit_only, unavailable}
```

### 3.2 `included_in_r_geometry`

True only if:

```text
dataset_group in {PreScreen_manual, Calibration_anchor, Calibration_core, Calibration_reserve}
condition = manual
task_final_scope = in_scope
geometry_reference_status in {expert_hard_single, expert_hard_multi, consensus_reference}
geometry_valid = true
process_invalid = false
```

False if:

```text
dataset_group in {PreScreen_semi, Calibration_semi, PreScreen_oos}
condition in {semi, oos_gate}
task_final_scope = oos
```

C2b may contribute only to diagnostic extension fields, not to the main C1/C2 `r_geometry_u`, unless an explicit extension-only output is produced.

### 3.3 `included_in_r_scope`

True if the row contains a valid worker scope response and a final binary scope adjudication:

```text
task_final_scope in {in_scope, oos}
worker_scope_response in {
  correct_in_scope,
  correct_oos,
  scope_false_positive,
  scope_false_negative
}
```

OOS subtype must not affect correctness.

### 3.4 `included_in_T_u`

True for semi-auto correction and blind-trust evidence:

```text
dataset_group in {PreScreen_semi, Calibration_semi}
condition = semi
process_invalid = false
```

Typical response types:

```text
blind_trust
failed_correction
successful_correction
semi_corner_drift_not_fixed
semi_corner_duplicate_not_fixed
semi_overextend_not_fixed
semi_over_parsing_not_fixed
semi_underextend_not_fixed
```

### 3.5 `included_in_U_u`

True only for in-scope undercoverage behavior:

```text
task_final_scope = in_scope
geometry_valid = true
geometry_reference_status in {expert_hard_single, expert_hard_multi, consensus_reference}
response_type in {
  partial_undercoverage,
  inner_space_only,
  minimal_space_bias,
  full_room_compliance_failure,
  overextended_adjacent_when_in_scope
}
```

Undercoverage must not be encoded as OOS.

### 3.6 `included_in_process_reliability`

True for process-integrity evidence:

```text
active_time_missing_or_ineligible
duplicate_same_geometry
revision_time_ambiguous
schema_invalid
assignment_mismatch
outside_manifest_submission
```

Process evidence can affect `process_reliability`, but it must not be silently converted into geometry failure.

---

## 4. `worker_task_evidence_table_C1.csv`

Row grain:

```text
one row per worker-task-evidence signal
```

If one submission contributes to multiple failure-family signals, it may generate multiple rows. Each row must be traceable to the same `canonical_annotation_id`.

Required fields:

```text
worker_id
round_id
task_id
base_task_id
dataset_group
condition
stage
pool
task_final_scope
task_oos_subtype
worker_scope_response
geometry_reference_status
geometry_valid
process_invalid
quality_metric_name
quality_metric_value
family
subfamily
response_type
failure_observed
included_in_r_u_calib
included_in_r_geometry
included_in_r_scope
included_in_T_u
included_in_U_u
included_in_process_reliability
exclusion_reason
active_time_source
primary_active_time_eligible
assignment_expected
canonical_annotation_id
source_manifest_version
profile_rule_version
```

Type rules:

```text
failure_observed: true / false
geometry_valid: true / false
process_invalid: true / false
primary_active_time_eligible: true / false
assignment_expected: true / false
quality_metric_value: numeric string or empty if not applicable
```

No row should be dropped merely because it is insufficient for interpretation. Insufficiency is handled at the aggregated table level.

---

## 5. `worker_profile_main_matrix_C1.csv`

Row grain:

```text
one row per worker
```

Required fields:

```text
worker_id
round_id
r_u_calib
r_u_calib_lcb
r_u_calib_ci_low
r_u_calib_ci_high
r_geometry_u
r_scope_u
T_u
U_u
process_reliability
profile_confidence
protocol_confidence
diagnostic_profile_confidence
profile_confidence_notes
n_calib_support
n_geometry_support
n_scope_support
n_semi_support
n_undercoverage_support
n_process_support
calib_support_status
geometry_support_status
scope_support_status
semi_support_status
undercoverage_support_status
process_support_status
profile_version
profile_freeze_status
notes
```

Rules:

```text
r_u_calib may remain empty in C1 if formal estimation has not yet run.
r_geometry_u may remain empty in the first sidecar implementation if only support counts are materialized.
profile_confidence must not hide insufficient support; it must be explainable from support counts and statuses.
protocol_confidence reflects calibration / r_u_calib support only and must not be directly reduced by sparse semi, undercoverage, or process evidence.
diagnostic_profile_confidence reflects multi-dimensional support across geometry, scope, semi, undercoverage, and process evidence.
```

Recommended `profile_freeze_status` values:

```text
C1_provisional
C2_final
C2b_diagnostic_extension_only
not_freezable
```

---

## 6. `worker_failure_family_response_C1.csv`

Row grain:

```text
one row per worker × first-level family
```

Required fields:

```text
worker_id
round_id
family
n_observed
n_fail
failure_rate
support_status
interpretation_level
interpretation_allowed
source_stages
profile_version
```

Rules:

```text
failure_rate = n_fail / n_observed if n_observed > 0 else empty
interpretation_allowed = false if support_status = insufficient
interpretation_level = none if n_observed < 3
```

This table must be long-format, not an ultra-wide matrix.

---

## 7. `worker_subfamily_response_C1.csv`

Row grain:

```text
one row per worker × family × subfamily
```

Required fields:

```text
worker_id
round_id
family
subfamily
n_observed
n_fail
failure_rate
task_count
subfamily_global_worker_coverage
support_status
interpretation_level
interpretation_allowed
source_stages
profile_version
```

Rules:

```text
All observed subfamilies must be retained.
Insufficient cells must not be deleted.
Cells below reportable support must use interpretation_allowed=false.
interpretation_level = none if n_observed < 3.
Second-level interpretation_allowed remains controlled by n_observed >= 8, task_count >= 4, and subfamily_global_worker_coverage >= 6.
```

---

## 8. Summary JSON

File:

```text
worker_profile_sidecar_C1.summary.json
```

Required keys:

```json
{
  "profile_version": "worker_profile_sidecar_C1_v1",
  "input_quality_csv": "",
  "input_worker_state_csv": "",
  "input_p1_artifacts": [],
  "output_worker_task_evidence_table": "",
  "output_worker_profile_main_matrix": "",
  "output_worker_failure_family_response": "",
  "output_worker_subfamily_response": "",
  "n_workers": 0,
  "n_evidence_rows": 0,
  "n_profile_rows": 0,
  "n_family_rows": 0,
  "n_subfamily_rows": 0,
  "n_insufficient_family_cells": 0,
  "n_insufficient_subfamily_cells": 0,
  "family_interpretation_level_counts": {},
  "subfamily_interpretation_level_counts": {},
  "r_u_calib_estimated": false,
  "r_geometry_u_estimated": false,
  "profile_freeze_status": "C1_provisional",
  "blockers": [],
  "warnings": []
}
```

---

## 9. Predictive-validity outputs

### 9.1 `p1_to_c1_predictive_validity.csv`

Row grain:

```text
one row per worker × predictive check
```

Required fields:

```text
worker_id
check_name
p1_metric_name
p1_metric_value
c1_metric_name
c1_metric_value
directionally_consistent
support_status
interpretation_allowed
notes
```

Required checks:

```text
p1_r0_vs_c1_r_u_calib
p1_geometry_vs_c1_geometry
p1_scope_vs_c1_scope
p1_blind_trust_vs_calibration_semi
p1_undercoverage_watch_vs_c1_undercoverage
p1_process_warning_vs_c1_process_reliability
```

### 9.2 `p1_to_c1_predictive_validity_report.md`

Must report:

```text
rank correlation where support permits
directional consistency
watch-flag persistence
discrepancy workers
insufficient support warnings
```

Do not report unsupported predictive claims as stable worker types.

---

## 10. C2b exclusion audit

If C2b is used, produce:

```text
c2b_exclusion_from_primary_r_u_calib_audit.json
```

Required keys:

```json
{
  "c2b_used": true,
  "primary_r_u_calib_excludes_c2b": true,
  "c2b_assignment_manifest": "",
  "n_c2b_assignments": 0,
  "trigger_reasons": [],
  "excluded_from_primary_fields": [
    "r_u_calib",
    "LCB(r_u_calib)",
    "CI precision primary estimator"
  ],
  "allowed_uses": [
    "diagnostic worker profile extension",
    "support shortage analysis",
    "P1-C1 discrepancy follow-up",
    "Validation routing diagnostic support if frozen before use"
  ],
  "forbidden_uses": [
    "retroactive P1 admission change",
    "C1 assignment rewrite",
    "primary calibration-only r_u estimator",
    "post-Validation rule selection"
  ]
}
```

---

## 11. Required tests

Add or update:

```text
tests/test_c1_worker_profile_sidecar.py
tests/test_c1_closeout_dryrun_chain.py
```

Minimum test cases:

```text
1. Calibration_semi is excluded from r_u_calib and r_geometry.
2. PreScreen_semi is excluded from r_geometry and included only in T_u when appropriate.
3. OOS gate contributes only to r_scope / scope_oos_failure.
4. OOS subtype does not change worker main scope correctness.
5. Undercoverage is not treated as OOS.
6. Insufficient subfamily cells are retained with interpretation_allowed=false.
7. First-level family response table includes n_observed, n_fail, support_status.
8. Worker-task evidence table preserves stage, pool, condition, inclusion flags, and source_manifest_version.
9. C2b diagnostic rows are excluded from primary r_u_calib.
10. All boolean fields serialize as lowercase true / false.
```

---

## 12. Implementation order

Recommended implementation order:

```text
1. Add `WORKER_PROFILE_AND_THESIS_OUTLINE_AMENDMENT_v1.md`.
2. Add this artifact field contract.
3. Add `c1_materialize_worker_profile_sidecar.py`.
4. Add sidecar tests.
5. Add or extend `run_c1_closeout_dryrun_chain.py`.
6. Add chain tests.
7. Run existing C1 post-canonical materialization tests.
8. Wait for real C1 export/logs before generating official thesis-facing C1 closeout artifacts.
```

Do not implement advanced `r_geometry_u` modeling before the evidence table and support-aware summaries are stable.

---

## 13. Versioned P1 post-closeout artifact amendment (2026-07-12)

The following contract is an additive post-closeout correction layer. It does not revise the original P1 admission contract.

### 13.1 New P1 artifacts

```text
p1_task_evidence_correction_v1.csv
p1_worker_evidence_status_v1.csv
p1_post_closeout_correction_summary_v1.json
p1_post_closeout_correction_report_v1.md
p1_geometry_task_scores_v1.csv
p1_worker_geometry_profile_v1.csv
p1_geometry_score_summary_v1.json
p1_geometry_score_audit_v1.md
```

Each task row retains `source_export` and `source_sha256`. Geometry rows additionally retain final-gold and canonical source SHA-256 values, reference status/id/count, raw mask-IoU, within-task mid-rank percentile, inclusion flag, exclusion reason, and scoring rule version.

### 13.2 Required evidence semantics

`independence_status` is one of `independent`, `non_independent_confirmed`, `non_independent_suspected`, or `not_evaluable`. Only same-task, cross-owner, parent-precedes-child, exact-geometry-hash evidence can be confirmed automatically. Suspected evidence is pending review and cannot automatically create a process failure.

For confirmed non-independent rows, capability flags are false and `process_evaluable=true`, `process_failure_observed=true`, and `process_failure_subfamily=non_independent_submission`. Independent rows follow the existing stage/pool/condition/reference gates. All P1 rows have `included_in_r_u_calib=false`.

### 13.3 Timing fields

`primary_active_time_eligible` is true only for owner-valid exact annotation-level browser logs. `task_level_fallback` and `lead_time_fallback` remain sensitivity/audit-only. The worker summary must include `n_total_tasks`, `n_primary_active_time_tasks`, `n_fallback_tasks`, `n_missing_time_tasks`, `primary_active_time_coverage`, `fallback_only_flag`, `long_open_draft_count`, `parent_derived_timing_count`, and `timing_evidence_status`.

### 13.4 Process reliability fields

`process_evaluable` defines the denominator. Both `process_failure_observed=true` and `false` rows enter that denominator. System collection issue, unknown-page evidence, and un-attributable active-time missingness are `process_evaluable=false`. The materializer reports an empty reliability value when the denominator is zero. `non_independent_submission` is a process-integrity subfamily and must not be relabeled as geometry failure.

### 13.5 Profile and predictive gate

P1 geometry profiles report stage/pool component medians and require at least two valid components for a combined diagnostic component. For a worker whose P1 capability evidence is invalid, P1 geometry/scope/semi/undercoverage predictive rows are `support_status=not_evaluable`, `interpretation_allowed=false`, and `notes` include `p1_non_independent_submission`; the P1 process-warning versus C1 process-reliability row remains separately auditable. No P1 value is routed into C1/C2 assignment or `r_u_calib`.
