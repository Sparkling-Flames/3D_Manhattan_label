<!-- PAPER_A_MACHINE_STATUS: normative -->
<!-- PAPER_A_METHOD_CONTRACT_CURRENT.json paper_a_method_20260802_v14 SHA-256 182ec9e22ed9c17f5f565bfa42a36da597720d5bdb0ccb53f6237dc512143439 -->
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

C1-A identity matching uses `(worker_id, base_task_id, condition)` plus `authorized_replacement_assignment` and one canonical annotation. Outside, duplicate/revision, late-entry, undeclared-worker and other-batch evidence are excluded. C1 active time is separately aggregated at formal-assignment `(project_id, runtime_task_id, worker_id)` level: max positive cumulative seconds per eligible session, then sum sessions. Annotation-exact identity remains forensic audit only. A context failing the task-worker log rules is `task_worker_time_analysis_eligible=false`; timing never gates Q_GT, R_peer, F_struct, eligibility/rank, C2-B roster, T1 assignment or V1 routing.

The rehearsal summary reports export project IDs, active-log project IDs, overlapping project IDs, annotation-exact audit coverage, task-worker eligibility, and project mismatch count. With no usable formal task-worker context, timing stays not evaluable and no lead_time proxy is used. W034 authorized replacements additionally require their passed pre-assignment sentinel.

A provisional snapshot is materialized evidence only and must set `C1_A_ANALYSIS_SNAPSHOT_FROZEN=false`. A formal snapshot binds worker profile, completion, Q_GT, structural EB, measurement readiness, canonical eligibility, reference and building dependencies by path and SHA.

## Rolling enrollment and final pooled closeout

Late entrants follow `P1 -> C1-B -> C2B_BATCH_B` and append rows using the Batch A selected design manifest, task pool, common anchor and bridge generator. Stage 3 remains closed until the independent roles `C1_EVIDENCE_FROZEN`, `FINAL_POOLED_PROFILE_FROZEN`, `CALIBRATION_ENROLLMENT_CLOSED` and `ALL_CALIBRATION_WORKERS_TERMINAL` are all true.

`C1_EVIDENCE_FROZEN` proves only C1 evidence. `FINAL_POOLED_PROFILE_FROZEN` separately binds C1, C2-B, C2-A-RP, the final C1+C2 Q_GT model, pooled worker profile and enrollment registry.
