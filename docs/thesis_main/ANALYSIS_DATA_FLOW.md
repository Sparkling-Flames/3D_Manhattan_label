<!-- PAPER_A_MACHINE_STATUS: normative -->
<!-- PAPER_A_METHOD_CONTRACT_CURRENT.json paper_a_method_20260731_v9 SHA-256 de7d99f4d119a87a48cfaa4e5c30c9d11161da43f8c1c37e34a6550c8b68f86c -->
# Paper A 本地分析数据流

## C1-A -> C2-B Batch A

```text
C1 exports + active_logs/c1 + assignment/disposition evidence
  -> rehearse-c1
  -> canonical eligibility, Q_GT, R_peer, LOO sensitivity, structural EB, worker_profile_v2
  -> freeze-c1-batch
  -> C1-A identity manifest: original cohort + exact W034 17 + exact W001 3
  -> SHA-bound C1-A snapshot
  -> design-c2b candidate designs and manual approvals
  -> build-c2b Batch A package
  -> manual Label Studio import
  -> bind-c2b-runtime-mapping audit
```

C1-A identity matching uses `(worker_id, base_task_id, condition)` plus `authorized_replacement_assignment` and one canonical annotation. Outside, duplicate/revision, late-entry, undeclared-worker and other-batch evidence are excluded. Any row without an annotation-level active-time join is `time_analysis_eligible=false` and `active_time_integrity_status=not_evaluable`; timing never gates Q_GT, R_peer, F_struct or C2-B roster.

The rehearsal summary reports export project IDs, active-log project IDs, overlapping project IDs, exact annotation join count and project mismatch count. With no overlap, timing stays not evaluable and no lead_time proxy is used.

A provisional snapshot is materialized evidence only and must set `C1_A_ANALYSIS_SNAPSHOT_FROZEN=false`. A formal snapshot binds worker profile, completion, Q_GT, structural EB, measurement readiness, canonical eligibility, reference and building dependencies by path and SHA.

## Rolling enrollment and final pooled closeout

Late entrants follow `P1 -> C1-B -> C2B_BATCH_B` and append rows using the Batch A selected design manifest, task pool, common anchor and bridge generator. Stage 3 remains closed until the independent roles `C1_EVIDENCE_FROZEN`, `FINAL_POOLED_PROFILE_FROZEN`, `CALIBRATION_ENROLLMENT_CLOSED` and `ALL_CALIBRATION_WORKERS_TERMINAL` are all true.

`C1_EVIDENCE_FROZEN` proves only C1 evidence. `FINAL_POOLED_PROFILE_FROZEN` separately binds C1, C2-B, C2-A-RP, the final C1+C2 Q_GT model, pooled worker profile and enrollment registry.
