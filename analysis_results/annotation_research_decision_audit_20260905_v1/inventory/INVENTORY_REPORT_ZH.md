# 标注研究决策审计：资产盘点与引用核对

生成日期：2026-09-05。此目录只做重复性资产清点、键/格式/引用核对和逻辑归档，不做视觉判断、不改原始数据、不代定实验结论。

## 关键计数

- machine manifest：314 条，唯一 image_id 314；历史记录层 148，无现有 annotation 记录层 166。
- human review export：30 条唯一记录；scope 原文计数为 `in_scope=26`、`out_of_scope=4`。
- 从无记录层扣除已审 30 条后，剩余候选池为 136 条；该池未因历史重叠或资产警告删减。
- 旧 image registry：214 条；42 高密图：42 条，42 集合属于 registry：True；两集合完全相等：False。

## 数据包与状态声明

`package_catalog.csv` 逐文件记录行数、字段、格式、主键候选、已出现的 status/role 声明和支持性角色。目录中的旧日期不作为作废依据；CURRENT/SUPPORTING/SUPERSEDED 只按文件中实际出现的声明记录，不替历史文件改名或升格。

| package | 文件数 | 盘点角色 |
|---|---:|---|
| `.uncertainty_substrate_20260823_v1_wg80m3p9` | 2 | 明确引用的上游文件 |
| `active_logs` | 42 | 明确引用的上游文件 |
| `annotation_uncertainty_batch1_broad_review_20260828_v1` | 143 | 旧研究者候选审图包；仅作重叠记录，非当前池 |
| `annotation_uncertainty_batch1_candidate_review_20260827_v2` | 31 | 旧研究者候选审图包；仅作重叠记录，非当前池 |
| `annotation_uncertainty_batch1_supplement_review_20260828_v1` | 11 | 旧研究者候选审图包；仅作重叠记录，非当前池 |
| `annotation_uncertainty_manual_semi_20260820_v2` | 1 | 明确引用的上游文件 |
| `annotation_uncertainty_prescreen_20260903_v1` | 171 | prescreen 机器/人工记录；成员当前可读但未冻结 |
| `c1_building_registry_review_20260801` | 35 | 明确引用的上游文件 |
| `c1_formal_audit_20260802_v16_final` | 17 | 明确引用的上游文件 |
| `c2a_rp_block1_reestimate_20260810_v1` | 2 | 明确引用的上游文件 |
| `c2a_rp_block2_distribution_20260810_v1` | 1 | 明确引用的上游文件 |
| `c2a_rp_block2_reestimate_20260814_v1` | 2 | 明确引用的上游文件 |
| `c2a_rp_local_launch_20260807_v4` | 1 | 明确引用的上游文件 |
| `c2a_rp_reference_review_20260811_v1` | 1 | 明确引用的上游文件 |
| `c2a_rp_terminal_closeout_20260817_v1` | 1 | 明确引用的上游文件 |
| `c2a_rp_terminal_declaration_20260817_v1` | 1 | 明确引用的上游文件 |
| `c2a_rp_terminal_reestimate_20260817_v1` | 1 | 明确引用的上游文件 |
| `c2b_closeout_20260806_final` | 2 | 明确引用的上游文件 |
| `c2b_validation_static_20260802_v16` | 15 | 明确引用的上游文件 |
| `calibration_dual_track_processing_20260815_v3` | 1 | 明确引用的上游文件 |
| `data` | 872 | 明确引用的上游文件 |
| `docs` | 6 | 明确引用的上游文件 |
| `export_label` | 45 | 明确引用的上游文件 |
| `external:Bi_layout/mp3d_dual_predictions` | 2596 | 明确引用的上游文件 |
| `external:C:/Users/ASUS/AppData/Local/Temp/historical_uncertainty_workbook_preview_20260829` | 1 | 明确引用的上游文件 |
| `final_calibration_profile_20260817_v1` | 1 | 明确引用的上游文件 |
| `full_uncertainty_data_mining_20260821_v5` | 182 | 全量派生数据整理；支持性/探索性输出 |
| `historical_uncertainty_recompute_20260829_v1` | 26 | 历史复算讨论包；支持性输出 |
| `import_json` | 21 | 明确引用的上游文件 |
| `manual_semi_correctness_oos_20260823` | 12 | Manual/Semi 与 OOS 探索性审计；不改 T1 |
| `model_initialization_audit_hybrid_gt_20260823_v4` | 1 | 明确引用的上游文件 |
| `output` | 686 | 明确引用的上游文件 |
| `post_block2_analysis_pack_20260817_v4` | 3 | 明确引用的上游文件 |
| `prescreen_closeout_final_gold_v2_20260701` | 70 | 明确引用的上游文件 |
| `reviewer_profile_dual_stage_processing_20260819_v2` | 1 | 明确引用的上游文件 |
| `rq1_corrections_20260826` | 11 | RQ1 修正与边界审计；支持性输出 |
| `rq1_raw_recompute_20260826` | 13 | RQ1 raw 复算；42 高密图成员来源 |
| `rq1_stratified_uncertainty_20260827_v1` | 17 | RQ1 分层探索性分析；支持性输出 |
| `stage_aware_analysis_freeze_v2_1_20260317` | 1 | 明确引用的上游文件 |
| `tests` | 1 | 明确引用的上游文件 |
| `tools` | 10 | 明确引用的上游文件 |
| `uncertainty_substrate_20260823_v1` | 21 | 不确定性事实底座；支持性数据，不是原始真源 |
| `worker_behavior_mixture_exploratory_20260904_v1` | 5 | worker mixture 探索性 replay；非正式 taxonomy |
| `worker_manual_strata_audit_20260904_v1` | 7 | worker strata 探索性审计；不支持离散 taxonomy |

## 人工 30 条的保留边界

`human_review_export_20260905_raw.json` 与 `HUMAN_REVIEW_RECORD_20260905_raw.md` 是输入原文的字节复制。`prescreen_asset_audit.csv` 中的 `human_scope_raw`、`human_prelabel_verdict_raw`、`human_notes_raw` 仅作连接字段，未替换原文。缺少 `prelabel_verdict` 或 `reference_verdict` 不被解释为“无问题”；本批没有自动补写 reference 裁决。

## 资产核对

`prescreen_asset_audit.csv` 覆盖 314 条 machine manifest；`high_density_asset_audit.csv` 覆盖 42 条高密图。原图、GT、HoHoNet txt/JSON 和 Bi extended/enclosed 分支分别记录存在、可解析和退化状态。Bi 的 `degenerate` 是 manifest/分支资产事实，不是视觉判断。

## 模型资产边界

`model_asset_summary.csv` 记录 HoHoNet、Bi-Layout 和 HorizonNet 的已有输出/权重/配置来源；当前只确认 HoHoNet test 输出与 Bi test/val manifest，HorizonNet 仅找到依赖实现/配置。Bi extended/enclosed 是一个模型的两个分支。

## 历史审图包重叠

`candidate_historical_review_overlap.csv` 记录剩余 136 池与三个旧研究者候选审图包的 55 条 package-image 重叠记录；仅记录，不改变 136 池。

## room/region 定位核查

`room_region_mapping_audit.csv` 记录有界元数据搜索结果；`room_region_mapping_records.csv` 保留本次214/42/136/30/50并集的实际 image_id→region_class 连接、来源与冲突。数值 region class 不是 room-instance/空间拓扑 ID；本次不从同楼栋或视觉相似性推断房间。

| pool | image 数 | 明确映射数 | 映射类型 | 状态 |
|---|---:|---:|---|---|
| `old_registry_214` | 214 | 81 | `region_class_only` | `found_region_class_only` |
| `high_density_42` | 42 | 16 | `region_class_only` | `found_region_class_only` |
| `candidate_remaining_136` | 136 | 32 | `region_class_only` | `found_region_class_only` |
| `human_reviewed_30` | 30 | 10 | `region_class_only` | `found_region_class_only` |
| `selected50` | 50 | 17 | `region_class_only` | `found_region_class_only` |

本次有界文件名搜索的根目录和模式保存在 `QA.json` 的 `room_region_mapping.search_scope`；结论仅适用于这些已检查来源。

## 引用与缺口

`reference_link_audit.csv` 共 43733 条去重后的消费者—引用记录，其中本地存在 40801 条、远程 URL 2930 条、缺失 2 条。缺失的历史临时路径保留在审计表中，未修复。

已知边界：

- 按用户要求未做 SHA-256 核查；manifest 中的 SHA 只作为输入声明保留，不作为本次 QA 结论。
- `Bi test` manifest 的 458 条中有 2 条状态为 `degenerate`；本次没有从 42 高密图或任何既定池删除它们。
- 外部 `D:/Work/Manhattan_3D/Bi_layout/exports/mp3d_dual_predictions` 只读核对，不复制、不修改。
- 本审计不判断 GT 谁对谁错，不把机器 prelabel 提示转换为人工结论。

## QA

`QA.json` 状态：`pass_with_known_gaps`；CSV/JSON/JSONL 格式检查 786 个，格式错误 0 个。

输出文件：`package_catalog.csv`、`reference_link_audit.csv`、`building_asset_coverage.csv`、`prescreen_asset_audit.csv`、`high_density_asset_audit.csv`、`candidate_historical_review_overlap.csv`、`room_region_mapping_audit.csv`、`room_region_mapping_records.csv`、`model_asset_summary.csv`、`QA.json`。
