<!-- PAPER_A_MACHINE_STATUS: generated -->
# Paper A current method contract (generated)

This file is generated from `PAPER_A_METHOD_CONTRACT_CURRENT.json`; normative fields are not defined by hand.
- contract_version: `paper_a_method_20260811_v22`
- JSON SHA-256: `1aa447e48edfdcf3b2c61a304a7ae37e69c9cb1bfdc1b09ec0acf952a1ac899f`
- formal_launch_default: `false`

## Formal measurement and freeze roles

- The three formal axes are `Q_GT`, `R_peer`, and `F_struct`. `R_LOO_medoid` and `R_LOO_strict` are separate sensitivity/tie-break states.
- Formal canonical non-outside, non-W014 rows default to independence by protocol assumption. Machine anomaly signals require manual review and never establish non-independence by themselves; exact geometry equality is diagnostic only.
- Ordinary completion is computed from frozen assignment and export. Existing public GT is used as-is unless the researcher explicitly declares a GT issue.
- Crowd modes use complete-link edges only when both similarity channels reach `0.95` and pointwise topology is compatible; `[0.93, 0.97]` are sensitivity-only. `R_peer_task` remains continuous, and worker bootstrap resamples tasks using the task-equal median.
- C1 active time is a `task_worker`-level auxiliary operational measurement (`task_worker_time_analysis_eligible`), not a fourth capability axis. It does not change Q_GT/R_peer/F_struct, eligibility, C2-B roster, formal rank, T1 assignment, or V1 routing.
- Annotation-exact active-log identity is retained for forensic audit; it is not required for the task-worker timing measurement. W034 authorized replacements require either the original sentinel or a SHA-bound retrospective operator attestation, plus the same task-worker log audit.
- `C1_EVIDENCE_FROZEN` contains C1 canonical evidence, eligibility, peer evidence, structural EB, W034 sensitivity, and this method binding only.
- `FINAL_POOLED_PROFILE_FROZEN` is an independent artifact binding C1, C2-B, C2-A-RP, the final C1+C2 Q_GT model, pooled worker profile, enrollment, and this method binding.
- Stage 3 validates C1 evidence, final pooled profile, enrollment closure, and terminal-worker closure as separate roles.

## C2-B and runtime

- C2-B consumes `worker_profile_v2.c2_risk_model_eligible` and the selected design manifest.
- Batch B reuses the selected design ID, common anchors, bridge pool, task pool, and method SHA; it never infers bridge count from Batch A rows.
- C2-A-RP's only formal dispatch goal is `risk_slope_precision`; `top_k_boundary_precision, component_eligibility_precision` remain diagnostic-only and cannot be dispatched.
- The formal interval is `normal_95_max_unified_slope_sd` at level `0.95`, with its target read from the `frozen_pre_c2b_threshold_manifest` field `thresholds.risk_slope_ci_half_width`. Each block is refit from canonical eligible risk-slope evidence before another block is assigned.
- A C2-A-RP block contains one ordinary and one stress task; the legal totals are `0, 2, 4, 6, 8, 10`. Terminal states are `target_met, fallback_strong_global, not_evaluable`; cap fallback sets risk adjustment to `0` and uses `STRONG_GLOBAL`.
- Historical Block 1 keeps task support cap `2`; Blocks 2--5 use cap `4`. Future blocks are never preassigned and require the preceding block's real closeout and refit.
- C2-A-RP Blocks 1--5 keep `scope_instruction_v1`. Annotation v2 begins at `T1`.
- Full numeric inputs follow `docs/thesis_main/FULL_MATERIALIZATION_PROCEDURE_v1.json`, use Calibration only, and are materialized `after_C2A_RP_terminal_closeout_before_T1_or_V1_outcome`.
- C2-A-RP CSV schemas are `c2a_rp_precision_plan_v2` for the precision plan and `c2a_rp_assignment_manifest_v2` for the assignment manifest; formal closeout rejects legacy schemas and requires `target_component`/`gap_reason` in the CSV headers.
- Runtime mapping is a local planned/runtime audit. Its identity fields are `deployment_id, language_group, server_instance_id, planned_import_path, project_id, planned_import_sha256, assignment_sha256, selected_design_sha, worker_registry_sha256`; it does not claim Label Studio UI visibility.

## Stage 3 gate separation

- T1 requires exactly: `CALIBRATION_ENROLLMENT_CLOSED, ALL_CALIBRATION_WORKERS_TERMINAL, C1_EVIDENCE_FROZEN, C2_B_FROZEN, C2_A_RP_CLOSED, FINAL_POOLED_PROFILE_FROZEN, T1_ROSTER_FROZEN, T1_TASK_POOL_FROZEN, T1_RANDOMIZATION_PLAN_FROZEN, T1_SAP_FROZEN`. It does not require `STRONG_GLOBAL_FROZEN`, `FULL_POLICY_FROZEN`, or `VALIDATION_ROSTER_FROZEN`.
- V1 requires exactly: `CALIBRATION_ENROLLMENT_CLOSED, ALL_CALIBRATION_WORKERS_TERMINAL, C1_EVIDENCE_FROZEN, C2_B_FROZEN, C2_A_RP_CLOSED, FINAL_POOLED_PROFILE_FROZEN, STRONG_GLOBAL_FROZEN, FULL_POLICY_FROZEN, VALIDATION_ROSTER_FROZEN, V1_SAP_FROZEN`.
- Gate dependencies must bind the declared artifact role, method SHA, and recursive child dependencies; adding a role string without its frozen artifact is invalid.
