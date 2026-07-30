<!-- PAPER_A_MACHINE_STATUS: normative -->
<!-- PAPER_A_METHOD_CONTRACT_CURRENT.json paper_a_method_20260730_v8 SHA-256 a74ea709ec4a0a3a35f724521b8b2deb0f69f6b0e36191bac8b99c3517ae30df -->
# Paper A C1-A -> C2-B 本地运行手册

正式本地链路只有：

```text
rehearse-c1 -> freeze-c1-batch -> design-c2b -> build-c2b --assignment-batch C2B_BATCH_A -> bind-c2b-runtime-mapping
```

不调用 Label Studio API，不自动导入或开放任务。

## 固定输入与 scope

当前 C1 export 只使用项目 `66`、`67`、`68`、`69`、`71`、`72` 对应目录；不要把 `export_label/` 根目录作为 export 输入。active-time 输入为 `active_logs/c1`。

```powershell
$py = 'python'
$manual = 'analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_manual_draft_v3_1.csv'
$semi = 'analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_semi_draft_v3_1.csv'
$distribution = 'analysis_results/calibration_rebuild_20260702/worker_distribution_internal_manifest_v3_1.csv'
$gt = 'export_label/groudTruth.json'
$p1 = 'analysis_results/prescreen_closeout_final_gold_v2_20260701'
$active = 'active_logs/c1'
$c1out = '<C1_A_REHEARSAL_OUTPUT_DIR>'
$scope = '<C1_A_BATCH_SCOPE.json>'
$snapshot = '<C1_A_SNAPSHOT.json>'
```

`$scope` 从 [PAPER_A_C1_BATCH_SCOPE.template.json](/D:/Work/HOHONET/docs/thesis_main/PAPER_A_C1_BATCH_SCOPE.template.json) 复制后填写。`original_completion_exception_task_ids` 必须为空；授权 repair 必须按 `(worker_id, base_task_id, condition)` 精确匹配，W034 为 17 条，W001 为 3 条。

## 1. Rehearse C1-A

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py rehearse-c1 `
  --export-dir export_label/stage2_English --export-dir export_label/stage2_Chinese `
  --active-log $active --manual-assignment $manual --semi-assignment $semi `
  --worker-distribution $distribution --gt-export $gt --p1-closeout-dir $p1 `
  --output-root analysis_results
```

如已有审核证据，追加对应的 `--annotation-independence-disposition`、`--project-independence-disposition`、`--duplicate-adjudication`、`--structural-disposition`、`--scope-adjudication`、`--reference-amendment`、`--outside-assignment-disposition`、`--completion-disposition`、`--authorized-reassignment-manifest`、`--calibration-enrollment-registry`、`--building-registry` 和 `--w034-active-time-validation-manifest`。

所有无可绑定 annotation-level active-time 的行必须为 `time_analysis_eligible=false`、`active_time_integrity_status=not_evaluable`；不补零、不估算，也不影响 `Q_GT`、`R_peer`、`F_struct` 或 C2-B roster。具体数量以本次 rehearsal 的 audit 输出为准。

产物为 `analysis_dependency_manifest.json`、三轴/LOO 工件、W034 sensitivity 和人工审核队列。

## 2. Freeze C1-A snapshot

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py freeze-c1-batch `
  --c1-output-dir $c1out --batch-scope-manifest $scope `
  --authorized-reassignment-manifest <FROZEN_AUTHORIZED_ADDENDUM.csv> `
  --output $snapshot
```

`C1_A_ANALYSIS_SNAPSHOT_MATERIALIZED=true` 只表示 snapshot 已生成；只有无 blocker 时才可为 `C1_A_ANALYSIS_SNAPSHOT_FROZEN=true` 和 `C2B_DESIGN_INPUT_FROZEN_FROM_C1_A=true`。这一步不要求关闭 rolling enrollment，也不产生最终 pooled profile。

本步骤正式输出文件名为 `c1_a_analysis_snapshot.json`。

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

只消费 C1-A snapshot 的 SHA-bound dependencies，输出 `c2_task_risk.summary.json`、`c2b_evidence_freeze_envelope.json` 和 `c2b_design.summary.json`，停在候选设计与人工审批边界。

## 4. Build Batch A after approval

人工审批完成后，运行 `build-c2b --assignment-batch C2B_BATCH_A`，绑定正式 roster、selected design/reference approval 和 capacity manifest。输出 `assignment_manifest_C2B.csv`、`worker_distribution_C2B.csv`、`label_studio_import_C2B.json` 和 `c2b_launch_ready_report.json`。

## 5. Bind runtime mapping after manual import

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py bind-c2b-runtime-mapping `
  --launch-report <c2b_launch_ready_report.json> `
  --worker-distribution <worker_distribution_C2B.csv> `
  --planned-import <label_studio_import_C2B.json> `
  --runtime-export <MANUAL_LABEL_STUDIO_EXPORT.json> `
  --output-dir <C2B_RUNTIME_AUDIT_DIR>
```

只有 `c2b_runtime_task_mapping.csv` 和 `c2b_worker_task_binding_audit.json` 通过一对一、设计 SHA、GT 隔离和 worker isolation 检查后，才允许人工开放任务。

全局 pooled closeout 和 Stage 3 另行等待所有 Calibration worker 终态；它们不阻断当前 C1-A Batch A 的分析与设计输入冻结。
