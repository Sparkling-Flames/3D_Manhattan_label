# WORKER_PROFILE_AND_THESIS_OUTLINE_AMENDMENT_v1

> Status: thesis-facing analysis contract / outline amendment  
> Scope: Paper A mainline only  
> Date: 2026-07-04  
> Intended repository path: `docs/thesis_main/WORKER_PROFILE_AND_THESIS_OUTLINE_AMENDMENT_v1.md`

## 0. Purpose

This document freezes the revised worker-profile and thesis-outline plan after the shift from a single reliability score to a dual-chain, multi-evidence worker state.

The purpose is not to change the already-launched C1 assignment. The purpose is to update the thesis-facing analysis contract and make the downstream implementation consistent with the current C1 reality.

Core decision:

```text
Do not replace the original calibration-only reliability chain.
Add a P1-informed worker-profile chain and explicitly amend the thesis outline to reflect it.
```

This document should be treated as an analysis and writing contract. It does not authorize any change to the C1 task pool, C1 worker-facing distribution, C1 assignment manifest, or P1 admission decision.

## 2026-07-12 post-closeout amendment

The authoritative thesis structure is now `THESIS_OUTLINE_AUDITABLE_DUAL_CHAIN_v3.md`. The paper's primary axis is protocol evidence -> evidence-validity gate -> dual-chain worker state -> freeze -> predictive validity and routing evaluation.

This amendment is retrospective. P1 capability evidence requires an independence/process-validity gate before entering geometry, scope, correction or coverage profiles. Confirmed cross-worker parent-derived submissions are excluded from capability dimensions and retained as `non_independent_submission` process evidence; suspected rows remain pending review. This correction does not rewrite P1 admission or frozen C1 assignment. Owner-valid exact browser logs are primary timing evidence; task-level and `lead_time` fallbacks remain sensitivity/audit only.

---

## 1. Non-negotiable protocol boundaries

The formal mainline remains:

```text
Pilot -> PreScreen -> Calibration -> Main(Test + Validation)
P1 -> C1 -> C2 -> T1 -> V1
```

The role split remains:

```text
PreScreen:
  admission
  r_u^(0)
  w_max
  blind-trust early evidence
  scope / meta-label / active-time audit evidence

Calibration:
  formal r_u
  LCB(r_u)
  candidate r_u^(s)
  tau_d
  scene-routing and OOD-risk freeze

Main-Test:
  RQ1 / RQ2 execution and reporting

Main-Validation:
  RQ3 frozen-policy execution and audit reporting
```

Hard constraints:

```text
1. Do not modify the already-launched C1 distribution.
2. Do not replace C1 tasks, worker-facing tables, or assignment manifests.
3. Do not use C1 interim performance to reassign C1.
4. Do not rewrite P1 admission after seeing C1 outcomes.
5. Do not merge PreScreen_semi, OOS gate, and manual geometry into one raw correctness score.
6. Do not let worker consensus override expert GT in P1 expert-anchor scoring.
7. Do not let Validation outcomes revise C2-frozen routing, tau_d, Score, k0/kmax, or worker tiers.
```

If an additional diagnostic round is needed, it must be labeled as `C2b diagnostic extension` and must not enter the primary calibration-only reliability estimator.

---

## 2. Current C1 fact source

The current thesis-facing C1/C2 analysis should use the actual frozen distribution artifacts, not a vague directory assumption.

Recommended wording:

```text
C1/C2 analysis uses the actually distributed and frozen v3.1 worker-facing distribution,
`worker_distribution_internal_manifest_v3_1.csv`, assignment manifests, and corresponding
mapping/readiness audits as the distribution truth. The current artifact directory is
`analysis_results/calibration_rebuild_20260702/`.

The deprecated `analysis_results/calibration_c1_prep/` artifacts are kept only as provenance
and must not be used for thesis-facing C1/C2 analysis.
```

This distinction matters because the distribution truth is the manifest contract, not the directory name.

---

## 3. Thesis outline amendments

The existing outline already contains the right high-level structure, including:

```text
2.1 Overall framework
2.2 Annotation object and metadata
2.3 Multi-label consensus
2.4 Quality and reliability evaluation
2.6 PreScreen and worker profile
2.7 Scene-specific reliability
2.8 Routing strategy
2.9 OOS statistics and mixed adjudication
2.10 Counterexample screening
3.5 Pre-registered protocol
4. Reporting and auditable outputs
```

The amendment should not rewrite the whole paper. It should patch the relevant sections.

### 3.1 Section 1 / RQ wording

RQ3 should explicitly say that worker profiling uses both protocol reliability and diagnostic risk signatures.

Suggested amendment:

```text
RQ3 evaluates whether a frozen worker state can improve budget allocation under non-IID / OOD
conditions. The worker state contains a calibration-only protocol reliability estimate and a
separate multi-evidence diagnostic profile. The diagnostic profile is used for interpretation,
risk stratification, and routing support only after it is frozen before Validation.
```

Add this clarification:

```text
The primary routing comparison remains Random / Global / Full on Calibration_manual offline replay.
Any profile-enhanced Validation use must be frozen before Validation and accompanied by a
calibration-only sensitivity comparison.
```

### 3.2 Section 2.1 Overall framework

Add a paragraph distinguishing protocol estimates from profile estimates:

```text
The analysis distinguishes protocol reliability from integrated worker profiling. Protocol
reliability is estimated within Calibration and is used for C1/C2 statistics, LCB, CI-gap
diagnostics, and freeze decisions. Integrated worker profiling uses staged evidence from
PreScreen and Calibration to characterize domain-specific worker behavior, but does not replace
the calibration-only protocol reliability estimator.
```

### 3.3 Section 2.2 Metadata and expert reference status

Add `expert_reference_status` / `geometry_reference_status`:

```text
geometry_reference_status:
  expert_hard_single
  expert_hard_multi
  consensus_reference
  soft_ambiguous
  scope_ambiguous
  audit_only
  unavailable
```

Use rules:

```text
expert_hard_single:
  may enter expert-GT geometry scoring

expert_hard_multi:
  may enter max-over-reference geometry scoring

consensus_reference:
  may enter Calibration LOO / consensus-based reliability estimation

soft_ambiguous:
  sensitivity or audit only

scope_ambiguous / audit_only / unavailable:
  excluded from hard geometry reliability scoring
```

Purpose:

```text
This prevents a single expert polygon from being treated as the only valid answer when multiple
reasonable enclosed interpretations exist, while also preventing worker consensus from overwriting
expert GT in P1.
```

### 3.4 Section 2.4 Quality and reliability evaluation

Split the reliability definitions:

```text
r_u^calib:
  Calibration-only protocol reliability.

r_geometry_u:
  P1-informed geometry profile, using only manual geometry-relevant evidence.

r_scope_u:
  Binary in-scope / OOS judgment reliability.

T_u:
  Semi-auto correction / blind-trust risk.

U_u:
  Undercoverage / minimal-space bias risk.

process_reliability:
  Active-time coverage, duplicate/revision behavior, schema/process integrity.
```

Add the following rule:

```text
r_u^calib remains the protocol estimator. r_geometry_u is a diagnostic profile estimator and
does not replace r_u^calib.
```

### 3.5 Section 2.6 PreScreen and worker profile

Replace the old single-score worker profile with a multi-evidence worker state.

Final worker state:

```text
worker_state = {
  r_u^calib,
  r_geometry_u,
  r_scope_u,
  T_u,
  U_u,
  process_reliability,
  profile_confidence
}
```

Interpretation:

```text
r_u^calib:
  main calibration-only reliability axis

r_geometry_u:
  manual geometry reliability profile informed by P1 and Calibration

r_scope_u:
  binary in-scope / OOS judgment reliability

T_u:
  model-initialization trust vulnerability and semi-auto correction ability

U_u:
  undercoverage / minimal-space bias risk

process_reliability:
  logging, duplicate/revision, schema, and assignment-integrity signal

profile_confidence:
  support-aware confidence based on n_observed, support status, CI width, and stage coverage
```

Add the following conceptual contribution:

```text
Instead of treating worker reliability as a single accuracy-like score, this paper constructs a
failure-family-aware worker state for structured panoramic layout annotation. The profile extends
class-confusion-style worker characterization to spatial layout annotation, where failures may
come from geometry degradation, scope/OOS misjudgment, blind trust in semi-automatic prelabels,
undercoverage, or process anomalies.
```

### 3.6 Section 2.7 Scene-specific reliability

Keep `r_u^(s)` separate from the new worker profile.

Add:

```text
Scene-specific reliability is still a Calibration-derived candidate statistic and is activated
only when C1/C2 support thresholds are met. Failure-family profile signals may explain or flag
worker weakness, but they do not automatically activate scene-specific routing unless the formal
scene-support contract is satisfied.
```

### 3.7 Section 2.8 Routing strategy

Clarify three routing layers:

```text
Random:
  no worker reliability information

Global:
  uses r_u^calib / LCB(r_u^calib)

Full:
  uses frozen C2 worker state, including r_u^calib, activated scene-specific reliability,
  OOD/task-risk signals, and pre-specified diagnostic profile features if frozen before Validation
```

Add sensitivity requirement:

```text
If r_geometry_u or other diagnostic profile features are used in Full routing, a calibration-only
Full-Global sensitivity comparison must be reported.
```

### 3.8 Section 2.9 OOS statistics and mixed adjudication

Use binary OOS for main worker scoring.

Main variable:

```text
scope_binary = in_scope / OOS
```

Worker response types:

```text
correct_in_scope
correct_oos
scope_false_positive
scope_false_negative
unknown_or_missing
```

OOS subtype remains expert audit metadata only:

```text
oos_geometry
oos_open_boundary
oos_split_level
oos_insufficient
oos_unspecified
```

Rules:

```text
1. OOS subtype is not a worker main correctness target.
2. OOS gate is not mixed into manual geometry reliability.
3. Undercoverage is not an OOS subtype.
4. Scope error does not automatically erase geometry evidence if valid geometry was submitted.
```

### 3.9 Section 2.10 Counterexample screening

Keep Type 1–5, but tighten Type 4 and Type 5.

```text
Type 1:
  low-consensus / consensus-GT conflict

Type 2:
  abnormal edit / blind trust

Type 3:
  geometry validity failure

Type 4:
  process or schema integrity sentinel

Type 5:
  in-scope undercoverage / minimal-space submission
```

Type 4 should not be the main counterexample source in Calibration if front-end constraints are reliable. It remains a process-integrity sentinel.

Type 5 is only evaluated when:

```text
task_final_scope = in_scope
worker geometry valid = true
geometry_reference_status in {expert_hard_single, expert_hard_multi, consensus_reference}
```

Type 5 is not OOS.

### 3.10 Section 3.5 Pre-registered protocol

Add dual-chain reporting to the pre-registered protocol:

```text
Primary protocol reliability:
  r_u^calib from Calibration_manual only.

Diagnostic worker profile:
  r_geometry_u / r_scope_u / T_u / U_u / process_reliability, generated as frozen sidecar
  evidence and used for interpretation, predictive validity, and optional Validation support.

Sensitivity:
  report calibration-only vs P1-informed profile differences and rank correlation.
```

### 3.11 Section 4 Reporting and auditable outputs

Add these required artifacts:

```text
worker_profile_main_matrix_C1.csv
worker_failure_family_response_C1.csv
worker_subfamily_response_C1.csv
worker_task_evidence_table_C1.csv
worker_profile_sidecar_C1.summary.json
p1_to_c1_predictive_validity_report.md
```

For C2:

```text
worker_profile_main_matrix_C2_final.csv
worker_failure_family_response_C2_final.csv
worker_subfamily_response_C2_final.csv
worker_task_evidence_table_C2_final.csv
worker_profile_sidecar_C2_final.summary.json
```

For optional C2b:

```text
assignment_manifest_C2b_diagnostic_extension.csv
worker_profile_c2b_extension_audit.csv
c2b_exclusion_from_primary_r_u_calib_audit.json
```

### 3.12 Section 6 Limitations

Update the future-work wording. Fine-grained worker profiling should no longer be framed only as future work. The thesis now includes a primary descriptive worker-profile layer and can reserve only model-based or interactive visualization for future work.

Suggested wording:

```text
This study implements a support-aware descriptive worker-profile layer. Fine-grained causal
claims about each worker-failure-family cell remain limited by sample support and are reported
with support_status and interpretation_allowed fields. Interactive visualization and model-based
profile propagation are left for future work.
```

---

## 4. Dual-chain definitions

### 4.1 Chain A: `r_u^calib`

This is the protocol estimator.

Sources:

```text
Calibration_anchor
Calibration_core
```

Inclusion rule:

```text
condition = manual
task_final_scope = in_scope
geometry_reference_status usable for Calibration reliability
used_for_r_u = true
process_invalid = false
```

Exclusions:

```text
Calibration_semi
PreScreen_semi
OOS-only tasks
audit-only tasks
process-invalid submissions
```

Usage:

```text
C1 provisional worker statistics
C2 freeze
LCB(r_u)
CI precision gap
formal calibration report
calibration-only sensitivity baseline
```

C1 may produce provisional values. C2 is the freeze point.

### 4.2 Chain B: `r_geometry_u`

This is the P1-informed manual geometry profile.

Sources:

```text
PreScreen_manual
Calibration_anchor
Calibration_core
```

Inclusion rule:

```text
condition = manual
task_final_scope = in_scope
geometry_reference_status in {expert_hard_single, expert_hard_multi, consensus_reference}
geometry_valid = true
process_invalid = false
not semi
not OOS-only
```

Allowed implementation variants:

```text
Variant 1: support-aware descriptive score
Variant 2: fixed-weight staged score
Variant 3: task/stage/pool-adjusted model
```

Variant 1 is safest for first implementation. Variant 2 or 3 may be used as sensitivity or later formal estimator.

If a staged score is used:

```text
r_geometry_u =
  lambda * z(P1_manual)
  + mu * z(Calibration_anchor)
  + (1 - lambda - mu) * z(Calibration_core)
```

Additional rule:

```text
All z(.) components must be converted to a higher-is-better reliability scale before aggregation.
Failure/error metrics must be inverted or transformed before z-scoring.
```

Weights must be frozen before seeing Validation outcomes.

---

## 5. Failure-family system

### 5.1 First-level families

First-level failure families are fixed before C1 closeout:

```text
F1 geometry_quality_failure
F2 scope_oos_failure
F3 semi_correction_failure
F4 undercoverage_failure
F5 process_failure
```

These are broad enough to avoid false precision but specific enough to represent domain-specific layout failure.

### 5.2 Second-level subfamilies

Second-level subfamilies are exploratory and support-gated. They must be retained in audit tables even when support is insufficient.

Candidate subfamilies:

```text
geometry_quality_failure:
  normal_geometry_degraded
  occlusion_geometry_degraded
  seam_or_stretch_geometry_degraded
  low_texture_geometry_degraded
  open_boundary_geometry_degraded
  topology_or_pairing_failure
  dense_corner_or_short_wall_failure

scope_oos_failure:
  scope_false_positive
  scope_false_negative
  mixed_scope_disagreement
  unresolved_scope_case

semi_correction_failure:
  blind_trust
  failed_correction
  semi_corner_drift_not_fixed
  semi_corner_duplicate_not_fixed
  semi_overextend_not_fixed
  semi_over_parsing_not_fixed
  semi_underextend_not_fixed
  successful_correction

undercoverage_failure:
  partial_undercoverage
  inner_space_only
  minimal_space_bias
  full_room_compliance_failure
  overextended_adjacent_when_in_scope

process_failure:
  active_time_missing_or_ineligible
  duplicate_same_geometry
  revision_time_ambiguous
  schema_invalid
  assignment_mismatch
  outside_manifest_submission
```

Do not force all subfamilies into the main text. They are reported only when support is sufficient. Insufficient cells are retained but marked non-interpretable.

### 5.3 Support status

Every family/subfamily cell must include denominators.

Default support status:

```text
insufficient:
  n_observed < 3

weak:
  3 <= n_observed < 5

moderate:
  5 <= n_observed < 10

sufficient:
  n_observed >= 10
```

For second-level subfamily:

```text
subfamily_reportable:
  n_observed >= 8
  and task_count >= 4
  and subfamily_global_worker_coverage >= 6
```

These are default main-analysis thresholds. The thresholds may be reported with sensitivity bands such as `n>=5`, `n>=8`, and `n>=10`, but the raw evidence table must not change.

### 5.4 Interpretation rule

```text
interpretation_allowed = true
```

only when support status is sufficient or when the cell is explicitly framed as a weak descriptive signal.

Cells with insufficient support must remain in the table:

```text
interpretation_allowed = false
support_status = insufficient
```

Never delete insufficient cells from the audit tables.

---

## 6. Required artifact contracts

### 6.1 Main worker-profile matrix

File:

```text
worker_profile_main_matrix_C1.csv
```

Final C2 version:

```text
worker_profile_main_matrix_C2_final.csv
```

Recommended fields:

```text
worker_id
round_id
r_u_calib
r_u_calib_lcb
r_geometry_u
r_scope_u
T_u
U_u
process_reliability
profile_confidence
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
```

### 6.2 First-level failure-family response table

File:

```text
worker_failure_family_response_C1.csv
```

Recommended long-format fields:

```text
worker_id
round_id
family
n_observed
n_fail
failure_rate
support_status
interpretation_allowed
source_stages
profile_version
```

The fixed family vocabulary:

```text
geometry_quality_failure
scope_oos_failure
semi_correction_failure
undercoverage_failure
process_failure
```

### 6.3 Second-level subfamily table

File:

```text
worker_subfamily_response_C1.csv
```

Recommended fields:

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
interpretation_allowed
source_stages
profile_version
```

### 6.4 Worker-task evidence table

File:

```text
worker_task_evidence_table_C1.csv
```

This is the provenance-like audit layer.

Recommended fields:

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
worker_scope_response
geometry_reference_status
geometry_valid
quality_metric_name
quality_metric_value
family
subfamily
response_type
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

This table must be sufficient to reproduce the profile matrices.

---

## 7. P1-to-C1 predictive validity

The new worker profile is not only descriptive. It should also test whether P1 evidence predicts C1 behavior.

Required analyses:

```text
P1 r_u^(0) vs C1 r_u^calib
P1 geometry profile vs C1 geometry evidence
P1 scope-gate behavior vs C1 scope/OOS behavior
P1 semi blind-trust flag vs Calibration_semi correction behavior
P1 undercoverage watch vs C1 undercoverage evidence
P1 active-time/process warning vs C1 active-time/process reliability
```

Required outputs:

```text
p1_to_c1_predictive_validity_report.md
p1_to_c1_predictive_validity.csv
```

Recommended reporting:

```text
rank correlation
directional consistency
discrepancy cases
watch-flag persistence
support-aware interpretation
```

Do not claim strong causal stability when support is weak.

---

## 8. Calibration_semi role

Calibration_semi is separate from manual reliability.

Allowed use:

```text
RQ2 same-image manual/semi contrast
T_u
semi_correction_failure
blind-trust / correction-risk analysis
model_issue exposure and counterexample analysis
```

Forbidden use:

```text
r_u^calib
r_geometry_u
scene-specific manual reliability r_u^(s)
primary routing reliability estimator
```

Sampling position:

```text
Calibration_semi should come from Calibration_core, not anchor and not reserve.
```

Reason:

```text
Anchor has all-worker manual exposure and violates same-worker no-manual+semi constraints.
Reserve is C2-only and must remain available for worker-side insufficiency correction.
```

---

## 9. C2 and C2b policy

### 9.1 C2

C2 remains reserve-only.

Allowed C2 triggers:

```text
CI precision gap
scene coverage gap
worker-side insufficiency correction
```

Forbidden:

```text
task-side pool modification
new task-side expansion
using reserve as semi pool
changing C1 task distribution after observing C1
```

### 9.2 C2b diagnostic extension

C2b is optional and diagnostic only.

Trigger conditions:

```text
reserve_capacity_shortfall_count > 0
or critical worker/family support remains insufficient after C2
or P1 and C1 worker profile conflict requires diagnostic bridge evidence
```

Allowed task sources:

```text
C1 bridge/challenge repeat tasks
new diagnostic tasks
expert-confirmed stable reference tasks
```

Default recommendation:

```text
C2b may contain both C1 bridge/challenge repeat and new diagnostic tasks.
The exact ratio is determined by the C2 gap type and frozen in the C2b run config.
```

Forbidden:

```text
C2b does not enter primary r_u^calib.
C2b does not modify C1 or C2 assignment truth.
C2b does not retroactively change P1 admission.
C2b does not revise Validation rules after seeing Validation outcomes.
```

Required C2b audit:

```text
assignment_manifest_C2b_diagnostic_extension.csv
c2b_exclusion_from_primary_r_u_calib_audit.json
worker_profile_c2b_extension_audit.csv
```

---

## 10. Implementation plan

### 10.1 Thesis and documentation first

Before implementing new scripts, update the thesis-facing documentation.

Create:

```text
docs/thesis_main/WORKER_PROFILE_AND_THESIS_OUTLINE_AMENDMENT_v1.md
```

Optional companion field contract:

```text
docs/thesis_main/WORKER_PROFILE_ARTIFACT_FIELD_CONTRACT_v1.md
```

Update, if applicable:

```text
docs/PROJECT_MAP_CLEAN_20260308.md
docs/AGENT_CONTEXT_INDEX.md
docs/thesis_main/README_INDEX.md
```

### 10.2 Code sidecar second

Add a sidecar script:

```text
tools/thesis_main/analysis/c1_materialize_worker_profile_sidecar.py
```

This first implementation should prioritize audit tables and support counts, not final advanced modeling.

Inputs:

```text
C1 c1_quality_annotations.csv
C1 worker_state_snapshot_C1.csv
P1 closeout worker/admission/r0/watch artifacts
assignment manifest
optional expert reference status table
```

Outputs:

```text
worker_task_evidence_table_C1.csv
worker_profile_main_matrix_C1.csv
worker_failure_family_response_C1.csv
worker_subfamily_response_C1.csv
worker_profile_sidecar_C1.summary.json
```

### 10.3 Closeout chain third

Add or extend:

```text
tools/thesis_main/analysis/run_c1_closeout_dryrun_chain.py
```

The chain should call:

```text
c1_canonicalize_exports
c1_materialize_quality_table
c1_materialize_worker_state
c1_materialize_c2_gap_audits
build_c2_assignment_manifest_from_c1_gaps
c1_materialize_worker_profile_sidecar
```

Final output:

```text
c1_closeout_dryrun_gate_summary.json
c1_closeout_dryrun_gate_summary.md
```

### 10.4 Tests

Add:

```text
tests/test_c1_worker_profile_sidecar.py
tests/test_c1_closeout_dryrun_chain.py
```

Required test cases:

```text
Calibration_semi excluded from r_u_calib and r_geometry
OOS included only in r_scope
undercoverage not treated as OOS
insufficient subfamily cells retained with interpretation_allowed=false
second-level table includes n_observed / n_fail / support_status
worker-task evidence table preserves stage / pool / condition / inclusion flags
C2b excluded from primary r_u_calib
```

---

## 11. Reporting language

Recommended thesis-facing wording:

```text
This study distinguishes protocol reliability from diagnostic worker profiling. The primary
calibration reliability, r_u^calib, is estimated only from Calibration_manual and is used for
C1/C2 statistics, LCB, CI-gap diagnosis, and formal calibration reporting. In parallel, a
P1-informed geometry profile, r_geometry_u, integrates manual geometry evidence from PreScreen
and Calibration under explicit stage, pool, and support-status controls. Additional dimensions
capture binary scope/OOS judgment, semi-automatic correction vulnerability, undercoverage bias,
and process reliability. This produces a failure-family-aware worker state for panoramic layout
annotation rather than a single raw correctness score.
```

Chinese version:

```text
本文区分协议主可靠度与诊断性工人画像。协议主可靠度 r_u^calib 仅由
Calibration_manual 估计，用于 C1/C2 worker statistics、LCB、CI gap 和正式
calibration 报告。并行地，本文构建 P1-informed 的几何画像 r_geometry_u，在显式记录
stage、pool 与支持度的前提下整合 PreScreen 与 Calibration 中的 manual geometry
证据。同时，工人画像还包含 binary scope/OOS 判断能力、semi 初始化纠错/盲信风险、
undercoverage 偏差与过程可靠性。最终形成面向全景布局标注的 failure-family-aware
worker state，而不是单一 raw correctness score。
```

---

## 12. Final decision

Adopt this plan.

The next change should be documentation-first:

```text
1. Add this thesis-outline amendment and worker-profile contract.
2. Then add sidecar artifact schema.
3. Then add C1 worker-profile materializer.
4. Then add closeout-chain orchestration.
5. Then run tests and only after real C1 data arrives generate official C1 closeout artifacts.
```

Do not implement final advanced `r_geometry_u` modeling before the sidecar evidence layer is stable.

---

## 13. Versioned P1 post-closeout integrity amendment (2026-07-12)

This section is a post-closeout amendment. It records a newly discovered evidence-validity issue and is not presented as an original P1 admission rule.

### 13.1 Independence and provenance gate

P1 task evidence is corrected in a read-only layer before it enters diagnostic worker profiling. A cross-worker parent-derived submission is `non_independent_confirmed` only when the parent is on the same task, belongs to another worker, precedes the child, and has an exact geometry-hash match. Incomplete cross-worker parent evidence is `non_independent_suspected` and requires expert adjudication. A same-worker revision is not cross-worker copying.

Confirmed non-independent rows are excluded from geometry, scope, semi-correction, undercoverage, and P1 predictive capability evidence. They remain process-integrity evidence under the `non_independent_submission` subfamily. Suspected rows remain audit evidence and do not automatically become process failures. No row from P1 is written into `r_u_calib`.

### 13.2 Timing and process denominator

Primary timing uses only owner-valid, annotation-level browser active logs. Task-level log matching and `lead_time` are sensitivity/audit evidence; they are never mixed into primary worker totals or speed/routing inputs. Long-open draft flags use a worker-relative rule (`Q3 + 3*IQR` and at least three times the worker median), are listed for review, and do not automatically constitute a process failure.

Process reliability uses all process-evaluable tasks as its denominator, including process-ok rows:

```text
process_reliability = 1 - attributable_process_failures / process_evaluable_tasks
```

System collection problems, unknown-page evidence, and otherwise un-attributable active-time missingness are excluded from this denominator. A zero denominator is reported as unavailable, not as zero or one.

### 13.3 Geometry correction artifact

The post-closeout P1 geometry artifact uses a seam-aware `1024 x 512` layout-mask IoU against hard expert references. Hard-multi references use max-over-reference. Raw scores for non-independent rows are retained for forensic audit but excluded from worker capability profiles. Worker geometry components are summarized by stage/pool medians and require at least two valid components before a combined diagnostic component is materialized. This layer is descriptive and does not alter admission, frozen assignment, reserve policy, C1 routing, `tau_d`, worker tier, or `r_u_calib`.

The provenance chain is:

```text
P1 original admission
  -> post-closeout evidence correction
  -> task-level inclusion flags and timing status
  -> P1 geometry audit/profile
  -> C1/C2 diagnostic profile sidecar
```

The correction outputs are `p1_task_evidence_correction_v1.csv`, `p1_worker_evidence_status_v1.csv`, `p1_post_closeout_correction_summary_v1.json`, `p1_post_closeout_correction_report_v1.md`, `p1_geometry_task_scores_v1.csv`, `p1_worker_geometry_profile_v1.csv`, and their corresponding summary/audit files. None of these artifacts writes back to P1 admission, C1 assignment, worker-facing distribution, reserve manifests, raw exports, the active-time server, or the userscript.
