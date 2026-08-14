<!-- PAPER_A_MACHINE_STATUS: normative -->
<!-- PAPER_A_METHOD_CONTRACT_CURRENT.json paper_a_method_20260811_v23 SHA-256 f3c1ea58d0857a40aa2240b4680b674c76fe2cec8f048f61a643d9e4b74b0588 -->
# Paper A C1-A -> C2-B 本地运行手册

本手册只描述本地 batch workflow，不调用 Label Studio API，不证明 Label Studio UI 可见性。机器规范字段只来自当前 JSON 方法合同。

## 正式顺序

`rehearse-c1 -> freeze-c1-batch -> design-c2b -> build-c2b --assignment-batch C2B_BATCH_A -> bind-c2b-runtime-mapping`

旧的全局 closeout 入口不是当前 Batch A 正式入口；最终 pooled closeout 与 Stage 3 另行执行。

## 0. C1-A scope

从同目录的 [PAPER_A_C1_BATCH_SCOPE.template.json](PAPER_A_C1_BATCH_SCOPE.template.json) 复制并填写 `$scope`。`original_completion_exception_task_ids` 必须为空；授权 repair 必须按 `(worker_id, base_task_id, condition)` 精确匹配，W034 为 17 条，W001 为 3 条。W014 永久排除。scope 之外的 late-entry、outside、未登记和其他批次证据不得进入 C1-A。

## 1. Rehearse C1-A

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py rehearse-c1 `
  --export-dir export_label/stage2_English --export-dir export_label/stage2_Chinese `
  --active-log $active --manual-assignment $manual --semi-assignment $semi `
  --worker-distribution $distribution --gt-export $gt --p1-closeout-dir $p1 `
  --output-root analysis_results `
  --annotation-independence-disposition $independence `
  --project-independence-disposition $projectIndependence `
  --duplicate-adjudication $duplicate --structural-disposition $structural `
  --scope-initial-review $scopeInitialReview --scope-adjudication $scopeAdjudication --reference-amendment $reference `
  --outside-assignment-disposition $outside --completion-disposition $completion `
  --authorized-reassignment-manifest $authorized --calibration-enrollment-registry $enrollment `
  --building-registry $building
```

人工处置文件可缺省；传入时必须被 rehearsal 实际消费。没有 reference amendment 时记录 `reference_approval_status=not_provided`，继续只做 provisional 分析。C1 timing 按 formal-assignment `(project_id, runtime_task_id, worker_id)` 聚合：每 session 取最大正累计秒数，再对合格 session 求和；annotation-level identity 仅用于 forensic audit。无合格 task-worker context 的行统一为 `task_worker_time_analysis_eligible=false`、`timing_status=not_evaluable`，不补零、不使用 lead time 作为逐行 fallback。Timing 不影响 `Q_GT`、`R_peer`、`F_struct`、C1-A snapshot、C2-B roster、正式排序、T1 分配或 V1 路由。W034 的 17 条 authorized replacement 可由通过的原 sentinel，或 SHA 绑定的事前人工确认回溯声明加逐 task-worker 日志审计获得 timing 资格；后一条路径必须记录 `eligible_with_protocol_deviation`、`time_basis=operator_recollection`、`timestamp_precision=unavailable`（无同时期日期证据时）及 `annotation_exact_validated=false`，不得表述为 fully verified。统一定义的 lead time 只允许另行输出为 post-hoc exploratory elapsed-time，不得与 active time 混合或进入画像、资格、排名和路由。summary 必须报告 export project IDs、active-log project IDs、overlap IDs、annotation-exact audit coverage、task-worker timing coverage 和 project mismatch count，并生成 `analysis_dependency_manifest.json`。

Current closeout policy: independence defaults from the formal protocol and only machine-detected anomalies require manual review; ordinary completion is computed from frozen assignment/export; project-level independence disposition and ordinary completion signatures are not formal blockers. When no GT issue is explicitly declared, the SHA-bound existing public GT is used as-is and no empty reference-amendment artifact is required.

### Scope two-pass closeout

`$scopeInitialReview` covers all 67 base tasks. The first rehearsal writes `c1_scope_consensus_audit.csv`, `c1_scope_secondary_review_queue.csv`, and `c1_scope_adjudication_template.csv`; complete only the conflict or `no_consensus` rows, then rerun with the complete `$scopeAdjudication`. The resulting `c1_task_scope_final_disposition.csv` is the only scope input that may freeze C1-A. `unresolved` is terminal and audit-retained, but excluded from primary geometry.

## 2. Freeze C1-A snapshot

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py freeze-c1-batch `
  --c1-output-dir $c1out --batch-scope-manifest $scope `
  --authorized-reassignment-manifest $authorized --output $snapshot
```

`C1_A_ANALYSIS_SNAPSHOT_MATERIALIZED=true` 只表示 snapshot 已生成；只有无 blocker 且 20 条 repair 精确完成时，才可同时设置 `C1_A_ANALYSIS_SNAPSHOT_FROZEN=true` 和 `C2B_DESIGN_INPUT_FROZEN_FROM_C1_A=true`。这一步不要求关闭 rolling enrollment，不生成最终 pooled profile。

## 3. Design C2-B

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py design-c2b `
  --c1-closeout-summary $snapshot --inventory-csv <C2_INVENTORY.csv> `
  --layout-dir <LAYOUT_DIR> --c1-task-feature-csv <C1_FEATURES.csv> `
  --checkpoint <CHECKPOINT> --building-registry <BUILDING_REGISTRY.csv> `
  --source-split-evidence <SOURCE_SPLIT.csv> --source-split-approval <SOURCE_APPROVAL.json> `
  --future-holdout-evidence <HOLDOUT_SPLIT.csv> --future-holdout-approval <HOLDOUT_APPROVAL.json> `
  --history-overlap-audit <HISTORY_AUDIT.csv> --scope-registry <SCOPE_REGISTRY.csv> `
  --reference-registry <REFERENCE_REGISTRY.csv> --feature-freeze-manifest <FEATURE_FREEZE.json> `
  --static-freeze-manifest <STATIC_FREEZE.json> --threshold-formula-contract <FORMULA.json> `
  --threshold-input-approval <THRESHOLD_APPROVAL.json> --threshold-manifest <DERIVED_THRESHOLDS.json> `
  --capacity-manifest <CAPACITY.csv> --output-dir <C2B_DESIGN_DIR>
```

设计阶段只消费 C1-A snapshot 的 SHA-bound dependencies，停止在候选设计和人工审批边界，生成 `c1_a_analysis_snapshot.json`、`c2_task_risk.summary.json`、`c2b_evidence_freeze_envelope.json` 和 `c2b_design.summary.json`。

## 4. Build Batch A after approval

正式审批后必须提供 selected design manifest。它冻结设计 ID、common anchor、bridge pool、task pool 和方法合同 SHA。

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py build-c2b `
  --assignment-batch C2B_BATCH_A --c1-closeout-summary $snapshot `
  --risk-summary <RISK_SUMMARY.json> --task-pool <TASK_POOL.csv> `
  --design-manifest <CANDIDATE_DESIGN.json> --selected-design-manifest <SELECTED_DESIGN_MANIFEST.json> `
  --selected-design-approval <SELECTED_APPROVAL.json> --c2b-roster-manifest <ROSTER.json> `
  --capacity-manifest <CAPACITY.csv> --output-dir <C2B_OUTPUT_DIR> ...
```

本地生成 planned import 和 assignment CSV，不自动写入 Label Studio。

Formal C2-B binding supplies one planned import and one runtime export per frozen deployment; repeat the append-style arguments for every deployment and pass the frozen deployment manifest.

## 4A. D8 v17 to v18 repackage (migration only)

The historical D8 v17 single-deployment launch report and the two v17 imports are
source evidence only. Do not run `build-c2b` for this migration and do not
overwrite any v17 file. Supply an explicit deployment configuration containing
the actual Label Studio project IDs and server instances:

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py repackage-c2b-v17-to-v18 `
  --legacy-root analysis_results/c2b_build_20260802_v17_d8 `
  --worker-language-source <FROZEN_WORKER_LANGUAGE_ROSTER.csv> `
  --deployment-config <C2B_MIGRATION_DEPLOYMENT_CONFIG.json> `
  --output-dir analysis_results/c2b_migration_20260803_v17_to_v18_d8 `
  --target-import-dir import_json/c2b
```

This command preserves D8, the frozen task pool, `planned_task_id`, and all 176
assignment rows. It creates `c2b_selected_design_manifest_D8_v18.json`,
`c2b_worker_language_registry_v1.json`,
`c2b_worker_deployment_manifest_v1.json`,
`c2b_v17_to_v18_assignment_mapping.csv`,
`c2b_v17_to_v18_repackage_envelope_v1.json`, and the v4
`c2b_launch_ready_report.json`, together with the new
`c2b_D8_batch_a_import_zh_v18.json` and
`c2b_D8_batch_a_import_foreign_https_v18.json`. A static
`launch_ready=true` report is not runtime/formal ready; after manual import and
export, the binder must additionally produce
`c2b_v17_to_v18_runtime_evidence_v1.json`.

## 5. Bind runtime mapping after manual import

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py bind-c2b-runtime-mapping `
  --launch-report <c2b_launch_ready_report.json> --assignment-manifest <assignment_manifest_C2B.csv> `
  --worker-distribution <worker_distribution_C2B.csv> `
  --planned-import <label_studio_import_C2B_<deployment_id>.json> `
  --runtime-export <MANUAL_LABEL_STUDIO_EXPORT_<deployment_id>.json> `
  --deployment-manifest <c2b_worker_deployment_manifest_v1.json> `
  --output-dir <C2B_RUNTIME_AUDIT_DIR>
```

必须通过 `c2b_runtime_task_mapping.csv`、`c2b_worker_task_binding_audit.json` 和 `c2b_private_assignment_list_audit.json`。它们只证明 planned assignment、runtime mapping、batch/design SHA、GT 隔离、private list 完整性和重复行；不声称 worker isolation 或 CE UI visibility 已验证。

Batch B 必须复用 Batch A 的 selected design manifest，不从 Batch A 实际行数推断 bridge 数量。最终 pooled profile 必须由独立 `FINAL_POOLED_PROFILE_FROZEN` artifact 生成；C1 evidence freeze 不再携带 enrollment、terminal 或 pooled 状态。
