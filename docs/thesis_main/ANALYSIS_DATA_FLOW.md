<!-- PAPER_A_MACHINE_STATUS: normative -->
<!-- PAPER_A_METHOD_CONTRACT_CURRENT.json paper_a_method_20260730_v8 SHA-256 a74ea709ec4a0a3a35f724521b8b2deb0f69f6b0e36191bac8b99c3517ae30df -->
# Paper A 本地分析数据流

## C1-A 到 C2-B Batch A

```text
C1 exports 66/67/68/69/71/72 + active_logs/c1 + assignment/disposition evidence
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

C1-A identity matching is `(worker_id, base_task_id, condition)` plus `authorized_replacement_assignment` and one canonical annotation. Outside, duplicate/revision, late-entry, undeclared-worker and other-batch evidence are excluded. W031 rows with no bindable active-time log remain canonical but have `time_analysis_eligible=false` and `active_time_integrity_status=not_evaluable`; timing never gates Q_GT, R_peer, F_struct or C2-B roster.

A provisional snapshot is materialized evidence only and must set `C1_A_ANALYSIS_SNAPSHOT_FROZEN=false`. A formal snapshot binds `WORKER_PROFILE`, `COMPLETION`, `Q_GT`, `STRUCTURAL_EB`, `MEASUREMENT_READINESS`, `CANONICAL_ELIGIBILITY`, `REFERENCE`, and `BUILDING`; design revalidates direct paths and SHA instead of using the snapshot parent directory.

## Rolling enrollment and final pooled closeout

Late entrants follow `P1 -> C1-B -> C2B_BATCH_B` and only append rows using the Batch A `selected_design_sha`, task pool, common anchor and bridge generator. Stage 3 remains closed until `CALIBRATION_ENROLLMENT_CLOSED`, `ALL_CALIBRATION_WORKERS_TERMINAL`, and `FINAL_POOLED_PROFILE_FROZEN` are all true.
