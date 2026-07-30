<!-- PAPER_A_MACHINE_STATUS: normative -->
<!-- PAPER_A_METHOD_CONTRACT_CURRENT.json paper_a_method_20260730_v8 SHA-256 a74ea709ec4a0a3a35f724521b8b2deb0f69f6b0e36191bac8b99c3517ae30df -->
# Paper A C1-A -> C2-B 本地运行手册

当前正式本地链路只有：`rehearse-c1 -> freeze-c1-batch -> design-c2b -> build-c2b --assignment-batch C2B_BATCH_A -> bind-c2b-runtime-mapping`。不调用 Label Studio API，不自动导入或开放任务。

## 固定输入

C1 export 目录必须只包含当前 6 个 C1 Label Studio export：66、67、68、69、71、72；不要直接传 `export_label/` 根目录，因为其中含 GT 和其他轮次 JSON。active-time 输入为 `active_logs/c1`。

```powershell
$py = 'python'
$manual = 'analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_manual_draft_v3_1.csv'
$semi = 'analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_semi_draft_v3_1.csv'
$distribution = 'analysis_results/calibration_rebuild_20260702/worker_distribution_internal_manifest_v3_1.csv'
$gt = 'export_label/groudTruth.json'
$p1 = 'analysis_results/prescreen_closeout_final_gold_v2_20260701'
$active = 'active_logs/c1'
$c1out = '<REHEARSAL_OUTPUT_DIR>'
$scope = '<C1_A_BATCH_SCOPE.json>'
$snapshot = '<C1_A_SNAPSHOT.json>'
```

`$scope` 从 `PAPER_A_C1_BATCH_SCOPE.template.json` 复制：`original_completion_exception_task_ids` 必须为空；W034 17 条及 W001 3 条均按 `(worker_id, base_task_id, condition)` 写入。若提供 addendum row identity/SHA，同时提供同一冻结 addendum CSV。

## 1. Rehearse C1-A

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py rehearse-c1 `
  --export-dir export_label/stage2_English --export-dir export_label/stage2_Chinese --active-log $active `
  --manual-assignment $manual --semi-assignment $semi `
  --worker-distribution $distribution --gt-export $gt `
  --p1-closeout-dir $p1 --output-root analysis_results
```

按已有审核证据追加相应的 `--annotation-independence-disposition`、`--project-independence-disposition`、`--duplicate-adjudication`、`--structural-disposition`、`--scope-adjudication`、`--reference-amendment`、`--outside-assignment-disposition`、`--completion-disposition`、`--authorized-reassignment-manifest`、`--calibration-enrollment-registry`、`--building-registry` 和 `--w034-active-time-validation-manifest`。

W031 的 4 条无可绑定 active-time 行保持 canonical，但必须是 `time_analysis_eligible=false`、`active_time_integrity_status=not_evaluable`；不补零，不影响 Q_GT、R_peer、F_struct 或 C2-B roster。产物：`analysis_dependency_manifest.json`。

## 2. Freeze C1-A snapshot

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py freeze-c1-batch `
  --c1-output-dir $c1out --batch-scope-manifest $scope `
  --authorized-reassignment-manifest <FROZEN_AUTHORIZED_ADDENDUM.csv> `
  --output $snapshot
```

产物：`c1_a_analysis_snapshot.json` 与同目录的 `c1_a_canonical_annotation_identity_manifest.csv`。`C1_A_ANALYSIS_SNAPSHOT_MATERIALIZED=true` 仅表示已生成；只有无 blocker 时 `C1_A_ANALYSIS_SNAPSHOT_FROZEN=true` 和 `C2B_DESIGN_INPUT_FROZEN_FROM_C1_A=true`。本步骤不关闭 rolling enrollment。

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

产物：`c2_task_risk.summary.json`、`c2b_evidence_freeze_envelope.json`、`c2b_design.summary.json`。设计只从 snapshot dependencies 读取 C1 工件；任一 SHA 漂移都 fail closed。该步骤止于候选设计/人工审批边界。

## 4. Build Batch A after approvals

人工审批完成后运行 `build-c2b --assignment-batch C2B_BATCH_A`，传入 design 输出、`c2_eligible_roster_C1.manifest.json`、selected task/reference/design approvals 与 capacity manifest。产物：`assignment_manifest_C2B.csv`、`c2b_launch_ready_report.json`、`label_studio_import_C2B.json`；仅生成本地包。

## 5. Bind runtime mapping after manual import

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py bind-c2b-runtime-mapping `
  --launch-report <c2b_launch_ready_report.json> --worker-distribution <worker_distribution_C2B.csv> `
  --planned-import <label_studio_import_C2B.json> --runtime-export <MANUAL_LABEL_STUDIO_EXPORT.json> `
  --output-dir <C2B_RUNTIME_AUDIT_DIR>
```

产物：`c2b_runtime_task_mapping.csv`、`c2b_worker_task_binding_audit.json`。audit 通过前不得开放任务。

## Global pooled closeout

?? `finalize-c1` ????? calibration worker terminal ?? pooled closeout ? Stage 3 gate?C1-A ? C2-B ???? runbook ??? batch ???
