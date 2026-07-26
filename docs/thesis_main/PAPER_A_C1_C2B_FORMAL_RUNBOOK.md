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
  --layout-dir output/layout_json `
  --c1-assignment analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_manual_draft_v3_1.csv `
  --c1-assignment analysis_results/calibration_rebuild_20260702/assignment_manifest_C1_semi_draft_v3_1.csv `
  --building-registry <evidence-root>/authoritative_building_registry.csv `
  --checkpoint ckpt/mp3d_layout_HOHO_layout_aug_efficienthc_Transen1_resnet34/ep300.pth `
  --config config/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34.yaml `
  --feature-audit-threshold-manifest docs/thesis_main/C2B_FEATURE_AUDIT_THRESHOLDS.json `
  --output-dir analysis_results/c2b_static_<sha> `
  --device cuda:0
```

首次尚无正式 building registry 时省略 `--building-registry`。入口只生成最多 15 个 scene key 的
`authoritative_building_scene_mapping_pilot.review_queue.csv`；history 直接从 P1/C1 真源推导，
scope/reference 只为缺失或冲突项生成最小队列。人工批准 scene 映射后再批量展开：

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py expand-building-registry `
  --inventory-csv analysis_results/calibration_rebuild_20260702/calibration_full_candidate_inventory_v3.csv `
  --approved-scene-mapping <evidence-root>/approved_scene_mapping.csv `
  --output-csv <evidence-root>/authoritative_building_registry.csv
```

只有 `formal_registry_ready=true` 的展开结果可用于重新运行 `prepare-c2b-static`。静态冻结产物为
`c2b_static_freeze_manifest.json`，并绑定 P1 integrity、feature cache、reference/candidate image/layout
清单、leakage audit、split proposals、环境与代码 SHA。split proposals 永远保持 `candidate_only`，
代码不得自动选择或生成 approval；候选摘要固定为 `c2b_source_holdout_split_proposals.summary.json`。

同一路径再次运行时，入口会先校验 reference listing、candidate inventory、checkpoint、config、cache 和 audit SHA；全部匹配时只刷新审批状态与环境 manifest，不重复运行 HoHoNet。

review queue 不是正式证据，不得直接改名冒充 approval。building_id 只能由人工批准的 scene mapping
精确展开；禁止从 image/task 前缀推断。source/holdout 必须由静态候选方案经人工选定后生成，并由两个独立
approval 文件分别绑定同一 `selected_proposal_id`、proposal summary SHA 与各自 evidence SHA。

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
  --c1-closeout-summary <audit-root>/c1_evidence_freeze_manifest.json `
  --inventory-csv analysis_results/calibration_rebuild_20260702/calibration_full_candidate_inventory_v3.csv `
  --layout-dir output/layout_json `
  --c1-task-feature-csv <static-root>/c1_preannotation_task_features.csv `
  --checkpoint ckpt/mp3d_layout_HOHO_layout_aug_efficienthc_Transen1_resnet34/ep300.pth `
  --building-registry <evidence-root>/authoritative_building_registry.csv `
  --source-split-evidence <evidence-root>/source_split_evidence.csv `
  --source-split-approval <approval-root>/source_split_approval.json `
  --future-holdout-evidence <evidence-root>/future_holdout_evidence.csv `
  --future-holdout-approval <approval-root>/future_holdout_approval.json `
  --history-overlap-audit <evidence-root>/history_overlap_audit.csv `
  --scope-registry <evidence-root>/scope_registry.csv `
  --reference-registry <evidence-root>/reference_registry.csv `
  --feature-freeze-manifest <static-root>/c2_feature_freeze_manifest.json `
  --static-freeze-manifest <static-root>/c2b_static_freeze_manifest.json `
  --threshold-manifest docs/thesis_main/C2B_DESIGN_SELECTION_THRESHOLDS.json `
  --output-dir <c2b-design-root> `
  --device cuda:0

# 人工审批后才允许执行；审批文件必须绑定实际 selected design/task set SHA。
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py build-c2b `
  --c1-closeout-summary <audit-root>/c1_evidence_freeze_manifest.json `
  --risk-summary <c2b-design-root>/c2_task_risk.summary.json `
  --task-pool <c2b-design-root>/c2_task_risk_inventory.csv `
  --task-eligibility-evidence <c2b-design-root>/c2b_task_eligibility_evidence.csv `
  --candidate-dir <c2b-design-root>/c2_candidates `
  --design-manifest <c2b-design-root>/c2b_candidate_design_manifest.json `
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

正式产物所有权固定如下：`audit-c1` 只写 `formal_audit_summary.json`、
`c1_measurement_freeze_manifest.json` 与待冻结 worker state；只有 `finalize-c1` 可以写
`c1_evidence_freeze_manifest.json`。`design-c2b` 写 `c2_task_risk.summary.json`、
`c2b_evidence_freeze_envelope.json`、`c2b_candidate_design_manifest.json`，并在
`c2_candidates/c2b_design.summary.json` 保存候选设计摘要。`build-c2b` 仅在 threshold、split、
feature、selected-task/reference、selected-design 与 capacity 审批均有效时写
`assignment_manifest_C2B.csv`；否则 assignment 必须为 0 行。
成功构建后的独立启动审计为 `c2b_launch_ready_report.json`。

交付前运行命令合同检查，防止手册输入引用不存在的上游产物：

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py check-command-contract `
  --runbook docs/thesis_main/PAPER_A_C1_C2B_FORMAL_RUNBOOK.md
```

保留上述细粒度命令用于审计。正式操作者也可准备
`paper_a_close_c1_plan_c2b_run_config_v1` JSON（从
`PAPER_A_CLOSE_C1_PLAN_C2B_RUN_CONFIG.template.json` 复制并替换占位符）后使用可恢复薄入口；它会依次验证 collection、
运行 formal audit、冻结 C1 evidence、校验 static/evidence envelope、生成 C2-B candidate designs，
并在 C1 adjudication 或 split approval 缺失时停止，只返回一条重跑命令：

```powershell
& $py tools/thesis_main/analysis/run_c1_closeout_launch.py close-c1-and-plan-c2b `
  --run-config <formal-root>/close_c1_and_plan_c2b_run_config.json `
  --state-output <formal-root>/close_c1_and_plan_c2b_state.json
```

该入口将状态与运行配置 SHA 绑定：在 C1 审批或 split 审批缺失时只返回同一条可重入命令；候选设计正式就绪后，`next_command` 只返回一条使用当前 Python 解释器的 `build-c2b` 命令。

## 5. Fail-closed 口径

- PreScreen active time 只绑定 `active_logs/prescreen` 或 P1 immutable snapshot；不得用 C1 日志替代。
- rehearsal 可以读取 live C1 日志但 `collection_window_closed=false`；正式分析只能读取 `active_logs/c1/<cutoff>_<sha>`。
- `support_limited` 不是失败，也不是成功估计；它只表示该 estimand 已终止但证据不足。
- threshold、feature、source/holdout、selected design 或 selected task approval 任一缺失时，assignment 必须为 0。
