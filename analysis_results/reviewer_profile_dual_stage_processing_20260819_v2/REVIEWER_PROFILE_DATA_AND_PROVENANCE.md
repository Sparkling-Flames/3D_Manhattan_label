# Reviewer 画像双阶段诊断数据与来源

- `diagnostic_pre_stage3=true`
- `development_only=true`
- `scientific_conclusion_prohibited=true`
- `formal_profile_frozen=false`
- `reviewer_policy_frozen=false`
- `main_launch_authorized=false`

## 边界

本包仅用于 Stage 3 前的开发诊断：PreScreen 形成画像，Calibration 仅作固定行为映射验证。跨阶段 reviewer 能力验证为 NOT READY，专家/M1 escalation 为 NO-GO。不得据此作科学结论、宣称能力稳定、筛选专家、冻结 reviewer 政策、生成 score/top-k/tier，或授权 Main 启动。

## 关键分母

- PreScreen：468 canonical / 469 raw，26×18；trap=312，control=156；C1 合格 23 人支持=414；当前 20 人支持=360。
- Calibration：106 canonical / 108 raw，25 base task，23 人；formal-assignment eligible=104；semi-correction eligible=88。
- 88 条 semi-correction eligible 中，ΔU 可计算 82 条、缺失 6 条（仅初始缺失 3、仅最终缺失 2、两侧均缺失 1）；跨阶段有效 worker=22/23，W14 为零支持。缺失不补零。

## 初始化绑定解释

C1 初始化不是 source absent，而是既有消费者未绑定。此包只在新 sidecar 内通过 `base_task_id + language cohort + runtime project/task + canonical annotation` 唯一 crosswalk，并逐 annotation 核对 import prediction payload SHA 与 runtime annotation 内嵌 prediction payload SHA 后，标记 observed canonical binding 为 recovered。原正式 C1 工件未改写。

两个 C1 import 均为 25/25 且各任务唯一 prediction。Project 72 运行时实际部署 24 个任务；未部署的第 25 个 import 任务没有 canonical submission，因此标记为 `not_deployed_no_runtime_task`，不计入 106 条 observed binding 的恢复声明。

## 数据真值说明

PreScreen 多出的第 469 条 raw annotation 在冻结 duplicate audit 中是 `duplicate_same_geometry`，不是几何 revision；它仅进入 reconciliation audit，未重复计数。Synthetic trap 的 family 使用人工 `reviewed_primary_issue`；与 planned operator 冲突时不回填预期 family。

P1 不调用 C1-only 孤立点修复。C1 `U_final` 直接消费冻结 quality/failure/reference disposition；reference failure 与 not-evaluable 保持 missing，worker-caused structural invalid 才按 delivery-adjusted 规则记 0。

## 指标命名与构念限制

- `unmodified_trap_submission` 只表示 trap 几何未修改，不表示工人接受 proposal；真正的盲信使用 `strict_blind_trust=acceptable AND exact_geometry_equal`。
- `quality_improving_correction` 仅表示 `delta_U > epsilon`，不表示最终质量已达到可接受门槛。`non_harmful_handling` 包含未编辑提交；`non_harmful_control_handling` 不要求选择 acceptable。
- `issue_geometry_edit_concordant` 只比较是否报告 issue 与 exact geometry hash 是否改变；它不区分微小编辑和实质修正。
- P1 blind trust 与 C1 acceptable+unchanged 主要映射接受/少编辑倾向；P1 Youden 与 C1 issue/edit concordance 不是同一能力构念。四个映射均为行为诊断，不能解释为 reviewer 能力稳定。
- 12 个 P1 trap 的初始化 U 范围为 0.827842324011–0.999953764709；接近天花板的任务缺少 IoU 改善空间，因此未提高 IoU 不自动表示没有纠错能力。人工 reviewed family 的实际任务分配为 `{"corner_drift": 2, "corner_duplicate": 5, "over_parsing": 2, "overextend_adjacent": 3}`，family-specific rate 仅作 weak/support-gated 描述。

## 方法与可复现性

- rule_version: `reviewer_profile_dual_stage_diagnostic_v2`；epsilon 全网格：0.0, 0.01, 0.02, 0.05；bootstrap seed=20260819，draws=1000。
- C1 partial task centering：在每个分析 cohort 内，对 eligible 行按 base_task_id 减去任务均值，再按 worker 取均值；worker bootstrap 每次重抽后重新估计任务均值。稀疏不平衡设计下它仍受同题 worker composition 影响，不等同于 worker+task 双向固定效应；正式使用前必须改用预先规定的双向固定效应或等价模型。未调整结果只保留为 descriptive sensitivity。
- 审计历史：v2 默认写入独立 `_v2` 目录。此前开发运行曾以 v2 规则覆盖 `_v1` 目录，原 v1 manifest 无法从本包恢复；后续版本不得继续复用既有版本目录。
- 复用仓库现有 geometry normalizer、C1-only repair、layout IoU、cyclic pointwise RMSE 与冻结 GT identity/SHA；未新增 scoring method。
- `analysis_manifest.json` 将处理脚本和本测试文件作为 code provenance 输入并记录 SHA，同时列出其余输入与除 manifest 自身外的输出 SHA；manifest 自身因递归哈希不可定义而明确排除。

## 输入 SHA

| role | path | sha256 |
|---|---|---|
| c1_canonical | `analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_canonical_annotations.csv` | `c6160151a1be468d16f83bb4397e7d09f8e8d43a2ce8725d35bb19d5c1bea724` |
| c1_eligibility | `analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_row_analysis_eligibility.csv` | `09d02115e6320d558d56b84eda9dbd850e4b29759e4708463c5eec9848ca6aaf` |
| c1_failure | `analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/failure_disposition.csv` | `23b2796cbe9198facbb3f824582aa2bfacaacce7cc00589c65dfb641f8e45acb` |
| c1_gt | `export_label/groudTruth.json` | `5ead984f15bdff3f08b31755a6017d007aa2fc33fbd0302b8cfcbc12a41604e0` |
| c1_harmonization | `analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/model_issue_harmonization_C1.csv` | `2144217ab0ccb7b7cb178517c9aedff5999a166b65c5321093e4de078bb883ca` |
| c1_import_en | `import_json/calibration_c1_v3_1_formal/c1_v3_1_semi_import_foreign_https.json` | `1938cd6c18bad9fe1efef21d14b23d01a001d4e8f2cb06ac07bcc5809c5c5bfa` |
| c1_import_zh | `import_json/calibration_c1_v3_1_formal/c1_v3_1_semi_import_zh.json` | `81dde50a0cf18bb5ad6e2d7d15dcf3bcffb012c72bffc04a2f3cedb8505c745c` |
| c1_outcome_reference | `analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_task_outcome_reference.csv` | `03cc8c97fef855682e7b5909a52f9ed62763616b26983e302da7613ab8ba666b` |
| c1_quality | `analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_gt_quality_analysis.csv` | `68c6d64cad77e09a21e5689d5bc20b26ad6484ba1fd63e1fbf00466ab9b23e5e` |
| c1_runtime_en | `export_label/stage2_English/project-68-at-2026-07-30-13-02-cf7d8306.json` | `455a0f2e543d9534f2e7d46c4572776fa334e455d8f60f9b1f0283d7224e9280` |
| c1_runtime_zh | `export_label/stage2_Chinese/project-72-at-2026-07-30-13-02-f69c5ac4.json` | `40f9dd7d1efbea185323b938e8e21a9700ae5e2040979a1c7506aa4a88952ce7` |
| c1_snapshot_en | `analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/raw_snapshots/exports/455a0f2e543d_project-68-at-2026-07-30-13-02-cf7d8306.json` | `455a0f2e543d9534f2e7d46c4572776fa334e455d8f60f9b1f0283d7224e9280` |
| c1_snapshot_zh | `analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/raw_snapshots/exports/40f9dd7d1efb_project-72-at-2026-07-30-13-02-f69c5ac4.json` | `40f9dd7d1efbea185323b938e8e21a9700ae5e2040979a1c7506aa4a88952ce7` |
| c2a_closeout | `analysis_results/c2a_rp_terminal_closeout_20260817_v1/c2a_rp_closeout_v2.json` | `73d3c4bdddcb11425e2a9b5b5d4aa1dca727b43b52a48cbf5c2af334a388a46a` |
| method_contract | `docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json` | `f3c1ea58d0857a40aa2240b4680b674c76fe2cec8f048f61a643d9e4b74b0588` |
| p1_admission | `analysis_results/prescreen_closeout_final_gold_v2_20260701/prescreen_worker_admission.csv` | `8a8575d1229aab6e2cea4e49af7fab39de7aa308923c73875019bbba99b3b554` |
| p1_canonical | `analysis_results/prescreen_closeout_final_gold_v2_20260701/prescreen_canonical_annotations.csv` | `ac216312875fd79a72efe0141a4a5dc88c3b0618e9720efdffe4b30331f8776d` |
| p1_duplicates | `analysis_results/prescreen_closeout_final_gold_v2_20260701/prescreen_duplicate_annotation_audit.csv` | `728c2de92d4459c7e64f4ae8c30fcf0f33e9e324534f590e842d7a52571ee357` |
| p1_final_gold | `analysis_results/prescreen_closeout_final_gold_v2_20260701/final_gold_records_v2_p1_closeout_corrected.jsonl` | `82dbcb1d08754476e4f2a447b70550bd297689c2c50df9f96aeb270b37f163d6` |
| p1_gold_status | `analysis_results/prescreen_closeout_final_gold_v2_20260701/prescreen_gold_status_audit.csv` | `983c4c7a879997286f308a5530c97847b4e39f660ffec5065cf6edfa6bdf47ff` |
| p1_import_en | `import_json/stage1_prescreen_foreign_https_20260609/stage1_prescreen_semi_import_v5_foreign_https.json` | `f01ae11cdfdd2485ae79826dc4e64f438618f958612042150d0d8b24dd1e5f26` |
| p1_import_zh | `import_json/stage1_prescreen_final_20260325/stage1_prescreen_semi_import_v5.json` | `7430abf1dea211abd799126fdd3f8883d52a0ae9598a326e7a11c5ad5cc6a014` |
| p1_runtime_en | `export_label/stage1_English/project-40-at-2026-06-28-05-14-bb74a057.json` | `1ce8a32e5708aa87c11f4e9957efebccd183b60e6d12066ceee69ce87d763305` |
| p1_runtime_zh | `export_label/stage1_chinese/project-29-at-2026-06-30-09-00-e7ea6931.json` | `63b34e8adce3790c76f41f1e77302ea926dfdcbb0bc2950f6258a8d90d8ccdd1` |
| p1_scope_summary | `analysis_results/prescreen_closeout_final_gold_v2_20260701/prescreen_scope_summary.json` | `f42ecbee33a6161f82c0c0cce8553df21bc4bf16fd8536416436185841a69988` |
| p1_selection | `analysis_results/phase1_progress_20260324/prescreen_semi_final_selection_v10.json` | `f9b0c279e4981778c5e61464e29385e847c665dacbfc7e268f01bdd8de04920e` |
| p1_synthetic_binding | `analysis_results/prescreen_closeout_final_gold_v2_20260701/prescreen_synthetic_geometry_gt_binding_audit.csv` | `13a893759e7bbd58170bbaaec79fc7a2a2b21729c8dcd6948c7fb9c0b1508a3e` |
| p1_synthetic_review | `analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/prescreen_semi_synthetic_trap_issue_review.csv` | `fcc16b76334897415cabc4ea850dad62a066c5ea9155c49ff930c04058ec6af7` |
| processing_script | `tools/thesis_main/analysis/materialize_reviewer_profile_dual_stage.py` | `5bcd95c857e5926524ec4e365066b5e165361f4784e1f0352a5990546d461914` |
| processing_test | `tests/test_materialize_reviewer_profile_dual_stage.py` | `945e0dae78a6d3a233c2b0db35c8f428b8a0ead16fc0031d032aa1ae7022310e` |
