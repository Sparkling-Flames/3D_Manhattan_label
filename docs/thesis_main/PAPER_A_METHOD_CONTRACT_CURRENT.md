<!-- PAPER_A_MACHINE_STATUS: generated -->
# Paper A current method contract (generated)

This file is generated from `PAPER_A_METHOD_CONTRACT_CURRENT.json`; normative fields are not defined by hand.
- contract_version: `paper_a_method_20260802_v14`
- JSON SHA-256: `182ec9e22ed9c17f5f565bfa42a36da597720d5bdb0ccb53f6237dc512143439`
- formal_launch_default: `false`

## Formal measurement and freeze roles

- The three formal axes are `Q_GT`, `R_peer`, and `F_struct`. `R_LOO_medoid` and `R_LOO_strict` are separate sensitivity/tie-break states.
- C1 active time is a `task_worker`-level auxiliary operational measurement (`task_worker_time_analysis_eligible`), not a fourth capability axis. It does not change Q_GT/R_peer/F_struct, eligibility, C2-B roster, formal rank, T1 assignment, or V1 routing.
- Annotation-exact active-log identity is retained for forensic audit; it is not required for the task-worker timing measurement. W034 authorized replacements require either the original sentinel or a SHA-bound retrospective operator attestation, plus the same task-worker log audit.
- `C1_EVIDENCE_FROZEN` contains C1 canonical evidence, eligibility, peer evidence, structural EB, W034 sensitivity, and this method binding only.
- `FINAL_POOLED_PROFILE_FROZEN` is an independent artifact binding C1, C2-B, C2-A-RP, the final C1+C2 Q_GT model, pooled worker profile, enrollment, and this method binding.
- Stage 3 validates C1 evidence, final pooled profile, enrollment closure, and terminal-worker closure as separate roles.

## C2-B and runtime

- C2-B consumes `worker_profile_v2.c2_risk_model_eligible` and the selected design manifest.
- Batch B reuses the selected design ID, common anchors, bridge pool, task pool, and method SHA; it never infers bridge count from Batch A rows.
- Runtime mapping is a local planned/runtime audit. It does not claim Label Studio UI visibility.
