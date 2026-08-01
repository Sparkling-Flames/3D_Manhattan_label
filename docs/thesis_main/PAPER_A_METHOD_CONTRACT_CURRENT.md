<!-- PAPER_A_MACHINE_STATUS: generated -->
# Paper A current method contract (generated)

This file is generated from `PAPER_A_METHOD_CONTRACT_CURRENT.json`; normative fields are not defined by hand.
- contract_version: `paper_a_method_20260801_v12`
- JSON SHA-256: `115ba6eaf771b4fa079289f17d1f491498d9cea910d12aeb4e66d192817c7ee8`
- formal_launch_default: `false`

## Formal measurement and freeze roles

- The three formal axes are `Q_GT`, `R_peer`, and `F_struct`. `R_LOO_medoid` and `R_LOO_strict` are separate sensitivity/tie-break states.
- `C1_EVIDENCE_FROZEN` contains C1 canonical evidence, eligibility, peer evidence, structural EB, W034 sensitivity, and this method binding only.
- `FINAL_POOLED_PROFILE_FROZEN` is an independent artifact binding C1, C2-B, C2-A-RP, the final C1+C2 Q_GT model, pooled worker profile, enrollment, and this method binding.
- Stage 3 validates C1 evidence, final pooled profile, enrollment closure, and terminal-worker closure as separate roles.

## C2-B and runtime

- C2-B consumes `worker_profile_v2.c2_risk_model_eligible` and the selected design manifest.
- Batch B reuses the selected design ID, common anchors, bridge pool, task pool, and method SHA; it never infers bridge count from Batch A rows.
- Runtime mapping is a local planned/runtime audit. It does not claim Label Studio UI visibility.
