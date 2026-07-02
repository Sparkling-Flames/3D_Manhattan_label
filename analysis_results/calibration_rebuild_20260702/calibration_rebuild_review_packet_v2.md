# Calibration C1/C2 v2 draft review packet

状态：draft_pending_human_review；未 launch，未导入 Label Studio，未生成 worker-facing distribution。

## 汇总
- manual pool: anchor=12, core=75, reserve=13
- manual assignment passed(draft audit only): True
- manual load min/max: 28/29
- semi assignment passed(draft audit only): True
- readiness passed: False

## 473 处理口径
- 基准：最新 `trap集/亲自复核.txt` 及其派生整理文件。
- 规则：473 只恢复 eligibility，不硬编码进入 anchor/manual。
- 已清理上一轮临时 GT sidecar 及其派生审计字段。

## Input Manifest
CSV: `analysis_results/calibration_rebuild_20260702/calibration_rebuild_input_manifest_v2.csv`

| path | bytes | sha256 | role | exists |
| --- | ---: | --- | --- | --- |
| docs/thesis_main/ROUND_BASED_EXECUTION_PROTOCOL_v1.md | 9269 | `31aba4e153ba1bab6ddc4f0a57f60f5e57a00ff2775ad379e0b0fbcdba66700c` | protocol_source | true |
| docs/thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.md | 8548 | `8170e76d02a550c1e432454fee6bc88dd0b723b724e911c38cd784a30a0f9b75` | assignment_sop_source | true |
| docs/thesis_main/C1_C2_ARTIFACT_FIELD_CONTRACT_v1.md | 8042 | `fcf56f74a98402c99a7d9c18e2a7cc7b7303a106f92228bcae885f54f8eaaa9c` | artifact_field_contract_source | true |
| docs/agent/playbooks/protocol_guard.md | 1254 | `ff2e917669610869ec73b8819edde1241661753975331073817382ee308189ac` | protocol_guard_source | true |
| docs/agent/playbooks/statistical_plan_guard.md | 1397 | `19ecc9d4cb1de3b1b4cef9d6a0bc16921888ad37b48bfbd836830e6828597cdc` | statistical_plan_guard_source | true |
| docs/agent/playbooks/label_studio_ce_guard.md | 1059 | `6407c8ab21d8e8c7bc3c121a9c917d5b6a7c14d1c9facd85960cbc8d89ffde3c` | label_studio_ce_guard_source | true |
| docs/agent/AGENT_CONTEXT_INDEX.md | 5504 | `5b0130d55684e12aa7b269d3df29992eba0eb5a9fc5e20488e755e47ca304ada` | agent_context_source | true |
| analysis_results/prescreen_closeout_final_gold_v2_20260701/prescreen_worker_admission.csv | 10638 | `8a8575d1229aab6e2cea4e49af7fab39de7aa308923c73875019bbba99b3b554` | p1_admission_source_final_closeout_v2 | true |
| analysis_results/prescreen_closeout_final_gold_v2_20260701/final_gold_records_v2_p1_closeout_corrected.jsonl | 121490 | `82dbcb1d08754476e4f2a447b70550bd297689c2c50df9f96aeb270b37f163d6` | p1_final_gold_v2_source | true |
| analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/project-41-at-2026-06-28-05-13-8641854f.json | 453267 | `307f6e6974a836a21193af64e93e72a0a907d7193be3bff6729f386aeac12fe2` | p1_raw_input_manifest_source | true |
| analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/project-40-at-2026-06-28-05-14-bb74a057.json | 1276775 | `1ce8a32e5708aa87c11f4e9957efebccd183b60e6d12066ceee69ce87d763305` | p1_raw_input_manifest_source | true |
| analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/project-39-at-2026-06-28-05-14-65ca3316.json | 1266031 | `f79fb49ae72195c4fbea4934f17ac6235d75da513fa8fbfc11c993ad726a84ae` | p1_raw_input_manifest_source | true |
| analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/project-30-at-2026-06-30-09-00-69d8051b.json | 474932 | `2f274f31c2ac9dd48128593357f1d0f4cae98dfc8fc62cf77a40e7df2641c4d7` | p1_raw_input_manifest_source | true |
| analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/project-29-at-2026-06-30-09-00-e7ea6931.json | 1478893 | `63b34e8adce3790c76f41f1e77302ea926dfdcbb0bc2950f6258a8d90d8ccdd1` | p1_raw_input_manifest_source | true |
| analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/project-28-at-2026-07-01-07-14-56a198ba.json | 1547456 | `a40ea344c04cc6259c5841f40a427cc82fa44258916dee672b4a7599d2cf8c69` | p1_raw_input_manifest_source | true |
| analysis_results/calibration_c1_prep/calibration_round_input_manifest_v1.json | 54428 | `722b394f138d473416c53ee1c3582490d02697e9558ee917287dcef98ffffd2d` | deprecated_random_c1_provenance_only | true |
| analysis_results/calibration_c1_prep/c1_launch_readiness_summary.json | 903 | `9bbc1397b4c7c32ddace0dbf86d2b6895888eec91f47a98b6c138721c169aef8` | deprecated_random_c1_readiness_source | true |
| analysis_results/calibration_c1_prep/C1作废说明_20260702.md | 1052 | `1421a940c2f533ec1d5d2232a61b148255e5c9eb5c7e0cc891b4b6fc6fb17be6` | deprecated_random_c1_note_source | true |
| export_label/project-2-at-2026-03-25-10-52-c04c6496.json | 4480511 | `3d03cec43488e2ab8b01a9016a30251805f29d0e2773f0107f8de3b2f872ca9f` | legacy_label_json_with_proxy_labels | true |
| trap集/亲自复核.txt | 1918 | `46d5870279be8cb05b215fade2a7d5691f38bccd6db92dfb9ad137519ae9864c` | latest_raw_human_review_source | true |
| trap集/亲自复核整理与分层_20260702.md | 4298 | `c50987cf0576bb0db78d213ac4022902b6bad4875fd48e5161093f9ab16348f7` | latest_human_review_derived_source | true |
| trap集/范围难度人工分层候选_20260702.md | 13751 | `d715764a72197d9e35b8566d5b3be4489d6e9c804d1ef651844cf48966e9e211` | scope_difficulty_manual_proxy_source | true |
| trap集/旧标注补充清单_20260702.md | 18635 | `9f72068d1ddf2562c6af3a30ef44ff9531b112956d7d62942e5e34c8a8393814` | legacy_label_proxy_supplement_source | true |
| trap集/纯模型问题任务记录_20260702.md | 4518 | `78cbef132eaec8991739b52bf7efed9677e7fe5789bbeef829c8fb66776503f5` | model_issue_only_source | true |
| trap集/校准semi模型问题整理_20260702.csv | 45901 | `de376c67b6fd76bf0aa74e5fe1bf5b9bbed8fc41ac70f55129d8ca3f2f2e5391` | semi_model_issue_proxy_source | true |
| trap集/校准semi模型问题整理_20260702.md | 1244 | `f04912c0f344260894dbe0240c9dc143b4e9b7d5ad823644cfdcd3391db359ab` | semi_model_issue_summary_source | true |
