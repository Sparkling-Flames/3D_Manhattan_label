<!-- PAPER_A_MACHINE_STATUS: normative -->
<!-- PAPER_A_METHOD_CONTRACT_CURRENT.json paper_a_method_20260731_v9 SHA-256 de7d99f4d119a87a48cfaa4e5c30c9d11161da43f8c1c37e34a6550c8b68f86c -->
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
  --scope-adjudication $scopeAdjudication --reference-amendment $reference `
  --outside-assignment-disposition $outside --completion-disposition $completion `
  --authorized-reassignment-manifest $authorized --calibration-enrollment-registry $enrollment `
  --building-registry $building --w034-active-time-validation-manifest $w034Active
```

人工处置文件可缺省；传入时必须被 rehearsal 实际消费。没有 reference amendment 时记录 `reference_approval_status=not_provided`，继续只做 provisional 分析。无可绑定 annotation-level active-time 的行统一为 `time_analysis_eligible=false`、`active_time_integrity_status=not_evaluable`，不补零、不使用 lead_time 代理，也不影响 `Q_GT`、`R_peer`、`F_struct` 或 C2-B roster。summary 必须报告 export project IDs、active-log project IDs、overlap IDs、exact join count 和 project mismatch count，并生成 `analysis_dependency_manifest.json`。

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

## 5. Bind runtime mapping after manual import

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py bind-c2b-runtime-mapping `
  --launch-report <c2b_launch_ready_report.json> --assignment-manifest <assignment_manifest_C2B.csv> `
  --worker-distribution <worker_distribution_C2B.csv> --planned-import <label_studio_import_C2B.json> `
  --runtime-export <MANUAL_LABEL_STUDIO_EXPORT.json> --output-dir <C2B_RUNTIME_AUDIT_DIR>
```

必须通过 `c2b_runtime_task_mapping.csv`、`c2b_worker_task_binding_audit.json` 和 `c2b_private_assignment_list_audit.json`。它们只证明 planned assignment、runtime mapping、batch/design SHA、GT 隔离、private list 完整性和重复行；不声称 worker isolation 或 CE UI visibility 已验证。

Batch B 必须复用 Batch A 的 selected design manifest，不从 Batch A 实际行数推断 bridge 数量。最终 pooled profile 必须由独立 `FINAL_POOLED_PROFILE_FROZEN` artifact 生成；C1 evidence freeze 不再携带 enrollment、terminal 或 pooled 状态。
