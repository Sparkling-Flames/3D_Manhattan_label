# Paper A C1→C2-B 正式运行手册

## 1. 隔离环境

```powershell
D:\anaconda\python.exe -m venv .venv-paper-a-gpu
.\.venv-paper-a-gpu\Scripts\python.exe -m pip install -r config\paper_a_analysis_requirements.lock.txt
.\.venv-paper-a-gpu\Scripts\python.exe -m pip install -r config\paper_a_torch_requirements.lock.txt --index-url https://download.pytorch.org/whl/cu128
```

正式环境为 Python 3.11、CUDA PyTorch、float32、`cuda:0`、physical batch 4。特征推理不允许自动 CPU、AMP 或 batch fallback。

## 2. C1 结束前完成的静态准备

```powershell
$py = ".\.venv-paper-a-gpu\Scripts\python.exe"
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py prepare-c2b-static `
  --p1-closeout-dir analysis_results/prescreen_closeout_final_gold_v2_20260701 `
  --inventory-csv analysis_results/calibration_rebuild_20260702/calibration_full_candidate_inventory_v3.csv `
  --legacy-manifest import_json/paper_a_c2b/legacy_reverse_v3_1_manifest.csv `
  --reference-dir data/mp3d_layout/train/img `
  --checkpoint ckpt/mp3d_layout_HOHO_layout_aug_efficienthc_Transen1_resnet34/ep300.pth `
  --config config/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34.yaml `
  --feature-audit-threshold-manifest docs/thesis_main/C2B_FEATURE_AUDIT_THRESHOLDS.json `
  --output-dir analysis_results/c2b_static_<sha> `
  --device cuda:0
```

同一路径再次运行时，入口会先校验 reference listing、candidate inventory、checkpoint、config、cache 和 audit SHA；全部匹配时只刷新审批状态与环境 manifest，不重复运行 HoHoNet。

静态准备同时生成六份 `*.review_queue.csv`。它们只用于提前补齐 building、source split、future holdout、history、Scope 和 reference 证据，所有正式字段均保持空值或 `pending_review`。不得把 review queue 直接改名冒充审批工件；复核后应在 `<evidence-root>` 另存正式 CSV，并由 reviewer、时间和审批 manifest 绑定其 SHA。尤其禁止用 image/task 字符串前缀生成 `building_id`。

随后运行静态 preflight：

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py preflight-calibration `
  --static-dir analysis_results/c2b_static_<sha> `
  --threshold-manifest docs/thesis_main/C2B_DESIGN_SELECTION_THRESHOLDS.json `
  --feature-audit-threshold-manifest docs/thesis_main/C2B_FEATURE_AUDIT_THRESHOLDS.json `
  --output analysis_results/c2b_static_<sha>/preflight_calibration.json
```

设计阈值或 feature audit 阈值仍为 null 时，preflight 必须失败；不得在查看正式 C1 estimand 后补选阈值。

feature audit 阈值获批后，先用同一 `prepare-c2b-static` 命令复用缓存并刷新 manifest，再从缓存生成 C1 任务侧特征：

```powershell
& $py tools/thesis_main/analysis/materialize_c1_preannotation_task_features.py `
  --assignment-csv analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_manual_draft_v3_1.csv `
  --assignment-csv analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_semi_draft_v3_1.csv `
  --inventory-csv analysis_results/calibration_rebuild_20260702/calibration_full_candidate_inventory_v3.csv `
  --building-registry-csv <evidence-root>/authoritative_building_registry.csv `
  --layout-dir output/layout_json `
  --checkpoint ckpt/mp3d_layout_HOHO_layout_aug_efficienthc_Transen1_resnet34/ep300.pth `
  --config config/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34.yaml `
  --feature-freeze-manifest <static-root>/c2_feature_freeze_manifest.json `
  --output-dir <static-root> `
  --device cuda:0
```

该命令只读取缓存和模型输出，不读取 crowd geometry；输出 `<static-root>/c1_preannotation_task_features.csv`。

## 3. C1 collection freeze

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py freeze-c1 `
  --source-live-root active_logs/new_server `
  --frozen-root active_logs/c1/<cutoff>_<aggregate-sha> `
  --collection-cutoff-server-time <ISO-8601-server-time> `
  --operator <operator> `
  --late-submission-policy reject_post_cutoff `
  --active-log-freeze-manifest <formal-root>/c1_active_log_freeze_manifest.json `
  --collection-closure-manifest <formal-root>/c1_collection_closure_manifest.json `
  --export-dir export_label/stage2_Chinese `
  --export-dir export_label/stage2_English `
  --manual-assignment analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_manual_draft_v3_1.csv `
  --semi-assignment analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_semi_draft_v3_1.csv
```

## 4. 五步正式链

以下命令中的 `<formal-root>`、`<static-root>`、`<audit-root>`、`<c2b-design-root>` 和审批文件必须替换为冻结后的真实路径。`audit-c1` 只能读取 `freeze-c1` 生成的 frozen root 和 manifest。

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py audit-c1 `
  --export-dir export_label/stage2_Chinese `
  --export-dir export_label/stage2_English `
  --active-log active_logs/c1/<cutoff>_<aggregate-sha> `
  --manual-assignment analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_manual_draft_v3_1.csv `
  --semi-assignment analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_semi_draft_v3_1.csv `
  --worker-distribution analysis_results/calibration_rebuild_20260702/worker_distribution_internal_manifest_v3_1.csv `
  --gt-export export_label/groudTruth.json `
  --p1-closeout-dir analysis_results/prescreen_closeout_final_gold_v2_20260701 `
  --p1-integrity-dir <static-root>/p1_integrity `
  --c1-preannotation-feature-csv <static-root>/c1_preannotation_task_features.csv `
  --c1-active-log-freeze-manifest <formal-root>/c1_active_log_freeze_manifest.json `
  --collection-closure-manifest <formal-root>/c1_collection_closure_manifest.json `
  --duplicate-adjudication <review-root>/duplicate_adjudication.csv `
  --structural-disposition <review-root>/structural_disposition.csv `
  --project-independence-disposition <review-root>/project_independence_disposition.csv `
  --scope-adjudication <review-root>/scope_adjudication.csv `
  --reference-amendment <review-root>/reference_amendment.csv `
  --outside-assignment-disposition <review-root>/outside_assignment_disposition.csv `
  --completion-disposition <review-root>/completion_disposition.csv `
  --output-root analysis_results

& $py tools/thesis_main/analysis/run_c1_closeout_launch.py finalize-c1 `
  --output-dir <audit-root> `
  --adjudication-manifest <review-root>/c1_adjudication_manifest.json

& $py tools/thesis_main/analysis/run_c1_closeout_launch.py design-c2b `
  --c1-closeout-summary <audit-root>/c1_closeout_freeze_envelope.json `
  --inventory-csv analysis_results/calibration_rebuild_20260702/calibration_full_candidate_inventory_v3.csv `
  --layout-dir output/layout_json `
  --c1-task-feature-csv <static-root>/c1_preannotation_task_features.csv `
  --checkpoint ckpt/mp3d_layout_HOHO_layout_aug_efficienthc_Transen1_resnet34/ep300.pth `
  --building-registry <evidence-root>/authoritative_building_registry.csv `
  --source-split-evidence <evidence-root>/source_split_evidence.csv `
  --future-holdout-evidence <evidence-root>/future_holdout_evidence.csv `
  --history-overlap-audit <evidence-root>/history_overlap_audit.csv `
  --scope-registry <evidence-root>/scope_registry.csv `
  --reference-registry <evidence-root>/reference_registry.csv `
  --feature-freeze-manifest <static-root>/c2_feature_freeze_manifest.json `
  --threshold-manifest docs/thesis_main/C2B_DESIGN_SELECTION_THRESHOLDS.json `
  --output-dir <c2b-design-root> `
  --device cuda:0

# 人工审批后才允许执行；审批文件必须绑定实际 selected design/task set SHA。
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py build-c2b `
  --c1-closeout-summary <audit-root>/c1_closeout_freeze_envelope.json `
  --risk-summary <c2b-design-root>/c2_task_risk_summary.json `
  --task-pool <c2b-design-root>/c2_task_risk_inventory.csv `
  --task-eligibility-evidence <c2b-design-root>/c2b_task_eligibility_evidence.csv `
  --candidate-dir <c2b-design-root> `
  --design-manifest <approval-root>/selected_c2b_design.json `
  --threshold-manifest docs/thesis_main/C2B_DESIGN_SELECTION_THRESHOLDS.json `
  --source-split-evidence <evidence-root>/source_split_evidence.csv `
  --source-split-approval <approval-root>/source_split_approval.json `
  --future-holdout-evidence <evidence-root>/future_holdout_evidence.csv `
  --future-holdout-approval <approval-root>/future_holdout_approval.json `
  --reference-registry <evidence-root>/reference_registry.csv `
  --selected-task-reference-manifest <approval-root>/selected_task_reference_approval.json `
  --selected-design-approval <approval-root>/selected_design_approval.json `
  --capacity-manifest <approval-root>/c2b_capacity_manifest.csv `
  --output-dir <c2b-build-root>
```

## 5. Fail-closed 口径

- PreScreen active time 只绑定 `active_logs/prescreen` 或 P1 immutable snapshot；不得用 C1 日志替代。
- rehearsal 可以读取 live C1 日志但 `collection_window_closed=false`；正式分析只能读取 `active_logs/c1/<cutoff>_<sha>`。
- `support_limited` 不是失败，也不是成功估计；它只表示该 estimand 已终止但证据不足。
- threshold、feature、source/holdout、selected design 或 selected task approval 任一缺失时，assignment 必须为 0。
