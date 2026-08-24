<!-- PAPER_A_MACHINE_STATUS: normative -->
<!-- PAPER_A_METHOD_CONTRACT_CURRENT.json paper_a_method_20260811_v23 SHA-256 f3c1ea58d0857a40aa2240b4680b674c76fe2cec8f048f61a643d9e4b74b0588 -->
# docs 鐩綍绱㈠紩

> 2026-07-18锛歅aper A 姝ｅ紡鏂囨湰宸茶縼绉诲埌 vFinal銆傚綋鍓嶆鏂囧叆鍙ｄ负
> `thesis_main/manuscript/overleaf_project/main.tex`锛涙寮忔墽琛屽悎鍚屼负
> `PAPER_A_METHOD_CONTRACT_CURRENT.json`
> 涓?`STATISTICAL_ANALYSIS_PLAN_v1.md`銆傛棫鎻愮翰浠呬綔鍘嗗彶瀹¤锛屼笉鍐嶅畾涔?C2/T1/V1銆?> 瀛楁鐪熸簮鍚屾涓?`C1_C2_ARTIFACT_FIELD_CONTRACT_v1.md`銆?> `WORKER_PROFILE_ARTIFACT_FIELD_CONTRACT_v1.md` 涓?`ANALYSIS_DATA_FLOW.md`銆?
`docs/` 鎸夎鏂囩嚎鍜屽叡浜繍琛屽眰缁勭粐銆傛牴鐩綍鍙繚鐣欐湰绱㈠紩鍜岄」鐩湴鍥撅紱鏂板涓婚鏂囨。涓嶈鐩存帴鏀惧湪鏍圭洰褰曘€?
## 鏍圭洰褰曞叆鍙?
- [PROJECT_MAP_CLEAN_20260308.md](PROJECT_MAP_CLEAN_20260308.md)锛氫粨搴撳湴鍥撅紝鏂板銆佸垹闄ゃ€佺Щ鍔ㄦ枃浠跺悗蹇呴』妫€鏌ャ€?- [README_INDEX.md](README_INDEX.md)锛氭湰鏂囨。銆?
## 璁烘枃涓荤嚎

鐩綍锛歔thesis_main/](thesis_main/)

涓荤嚎瑕嗙洊姝ｅ紡鎵ц鍗忚銆丳reScreen銆丆alibration銆丮ain(Test + Validation)銆佺粺璁¤鍒掋€佸瓧娈靛悎鍚屻€乫inal-gold銆乺egistry 鍜岃鏂囦富绾垮啓浣滄潗鏂欍€?
鍏抽敭鏂囦欢锛?
- [PAPER_A_METHOD_CONTRACT_CURRENT.json](thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json)
- [C2B_PREDISPATCH_METHOD_AMENDMENT_v1.json](thesis_main/C2B_PREDISPATCH_METHOD_AMENDMENT_v1.json)：C2-B 在任何工人结果产生前批准的统一候选生成与 gate 语义修订。
- [C2A_RP_PRECISION_CAP_EXTENSION_20260807_v1.json](thesis_main/C2A_RP_PRECISION_CAP_EXTENSION_20260807_v1.json)：C2-A-RP outcome 可见前冻结的最多 5 个平衡 block 精度上限修订。
- [C2A_RP_BLOCK2_CAPACITY_AMENDMENT_20260811_v3.json](thesis_main/C2A_RP_BLOCK2_CAPACITY_AMENDMENT_20260811_v3.json)：统一冻结 slope uncertainty 实现后确认 Block 2--5 `max_task_support=4` 与 20 人 roster；不预分配未来 block。
- [C2B_HISTORICAL_EVIDENCE_ACCEPTANCE_20260811_v1.json](thesis_main/C2B_HISTORICAL_EVIDENCE_ACCEPTANCE_20260811_v1.json)：以 SHA 接管已结束的 v18 C2-B，供 C2-A-RP closeout 与 final profile 使用；不重开数据采集或改写历史结果。
- [FULL_MATERIALIZATION_PROCEDURE_v1.json](thesis_main/FULL_MATERIALIZATION_PROCEDURE_v1.json)：Block 2 outcome 前冻结的 Full 数值物化程序；最终数值仅在 C2-A-RP 终态后由 Calibration 数据机械产生。
- [ROUND_BASED_ASSIGNMENT_SOP_v1.md](thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.md)
- [P1_PRESCREEN_LAUNCH_CHECKLIST_v1.md](thesis_main/P1_PRESCREEN_LAUNCH_CHECKLIST_v1.md)
- [PRESCREEN_STAGE1_OPERATIONAL_GUIDE_20260327.md](thesis_main/PRESCREEN_STAGE1_OPERATIONAL_GUIDE_20260327.md)
- [PAPER_A_C1_C2_FORMAL_ARCHITECTURE.md](thesis_main/PAPER_A_C1_C2_FORMAL_ARCHITECTURE.md)锛欳1 鏃ュ織鍐荤粨銆佷笁杞磋瘉鎹€丆2-B 椋庨櫓/妯℃嫙/瀹℃壒/assignment 鐨勫崟涓€鐢熶骇 DAG 涓庣姸鎬?owner
- [PAPER_A_C1_C2B_FORMAL_RUNBOOK.md](thesis_main/PAPER_A_C1_C2B_FORMAL_RUNBOOK.md)锛欸PU 闈欐€佺壒寰佸噯澶囥€丆1 collection freeze 涓?C2-B 姝ｅ紡鍛戒护椤哄簭
- [C1_PRECLOSEOUT_AUDIT_FIELD_CONTRACT_v1.md](thesis_main/C1_PRECLOSEOUT_AUDIT_FIELD_CONTRACT_v1.md)
- [WORKER_PROFILE_ARTIFACT_MIGRATION_AMENDMENT_v1.md](thesis_main/WORKER_PROFILE_ARTIFACT_MIGRATION_AMENDMENT_v1.md)
- [WORKER_PROFILE_AND_THESIS_OUTLINE_AMENDMENT_v1.md](thesis_main/WORKER_PROFILE_AND_THESIS_OUTLINE_AMENDMENT_v1.md)
- [WORKER_PROFILE_THESIS_DISPLAY_CONTRACT_v1.md](thesis_main/WORKER_PROFILE_THESIS_DISPLAY_CONTRACT_v1.md)
- [WORKER_PROFILE_AMENDMENT_COMPATIBILITY_BRIDGE_v1.md](thesis_main/WORKER_PROFILE_AMENDMENT_COMPATIBILITY_BRIDGE_v1.md)
- [PAPER_A_VFINAL_ANALYSIS_ARTIFACT_AMENDMENT_v1.md](thesis_main/PAPER_A_VFINAL_ANALYSIS_ARTIFACT_AMENDMENT_v1.md)锛歅aper A vFinal sidecar銆乨ry-run 涓庢寮忔暟鎹竟鐣?- `PAPER_A_VFINAL_EXECUTION_CONTRACT.json`锛堝凡褰掓。鑷?`docs/legacy/paper_a_method_contract_superseded_20260730/`锛屼笉鍐嶆槸姝ｅ紡鍚堝悓锛夛細C1鈫扖2 涓荤嚎 DAG銆佷笁娈?freeze gate銆侀闄╅€氶亾涓?legacy 闅旂鍚堝悓
- [C2B_RISK_DESIGN_CONTRACT_v1.json](thesis_main/C2B_RISK_DESIGN_CONTRACT_v1.json)锛欳2-B 鍞竴椋庨櫓閫氶亾銆佸垎灞傘€佹ā鎷熶笌鍐荤粨鐘舵€佸悎鍚?- [C2B_DESIGN_SELECTION_THRESHOLDS.json](thesis_main/C2B_DESIGN_SELECTION_THRESHOLDS.json)锛欳1 closeout 鍓嶅喕缁撶殑 C2-B design threshold 鍏紡銆佸父鏁般€佽緭鍏ュ瓧娈典笌鏂瑰悜鍚堝悓锛涙寮忔暟鍊肩敱 SHA 缁戝畾杈撳叆鏈烘娲剧敓
- `PAPER_A_METHOD_CONTRACT_CURRENT.json`锛歅aper A 鍞竴瑙勮寖鏂规硶鐪熸簮锛沗Paper_A_鏂扮増瀹屾暣璁烘枃鎻愮翰_vFinal_Draft.md` 宸?superseded锛屼粎浣滈潪瑙勮寖鎬у啓浣滆儗鏅€?- [meta_label_three_state_rule_manifest_v1.json](thesis_main/meta_label_three_state_rule_manifest_v1.json)锛氫笁鐘舵€?meta-label 鍊欓€夎鍒?- [geometry_loo_candidate_rule_manifest_v1.json](thesis_main/geometry_loo_candidate_rule_manifest_v1.json)锛欸eometry LOO 鍊欓€夎鍒?- [geometry_peer_candidate_rule_manifest_v1.json](thesis_main/geometry_peer_candidate_rule_manifest_v1.json)銆乕GLOBAL_POLICY_THRESHOLDS.json](thesis_main/GLOBAL_POLICY_THRESHOLDS.json)銆乕P1_COMPONENT_SUPPORT_THRESHOLDS.json](thesis_main/P1_COMPONENT_SUPPORT_THRESHOLDS.json)銆乕GT_CONFLICT_REVIEW_RULES.json](thesis_main/GT_CONFLICT_REVIEW_RULES.json)锛氬悓琛屻€丟lobal銆丳1 component 涓?GT 鍐茬獊鐨?candidate-only 鏁板€煎悎鍚?- [sequential_routing_candidate_rule_manifest_v1.json](thesis_main/sequential_routing_candidate_rule_manifest_v1.json)锛氬巻鍙插喕缁撶殑鏃跺簭 routing 鍊欓€夎鍒?- [sequential_routing_candidate_rule_manifest_v2.json](thesis_main/sequential_routing_candidate_rule_manifest_v2.json)锛氱粺涓€ temporal replay 鐘舵€佹満涓庡€欓€夎鍒欏悎鍚?- [model_issue_harmonization_rule_manifest_v1.json](thesis_main/model_issue_harmonization_rule_manifest_v1.json)锛歮odel issue 鎶栧姩瀹瑰繊涓?harmonization 鍊欓€夎鍒?- [RQ3_MINIMAL_EVIDENCE_CHAIN_CONTRACT_v1.md](thesis_main/RQ3_MINIMAL_EVIDENCE_CHAIN_CONTRACT_v1.md)
- [STATISTICAL_ANALYSIS_PLAN_v1.md](thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md)
- [PAPER_A_REFERENCES_NEEDED_CHECKLIST.md](thesis_main/PAPER_A_REFERENCES_NEEDED_CHECKLIST.md)锛氱浉鍏冲伐浣滀笌寮曠敤鏍搁獙寰呭姙
- [TEST_MANUAL_GT_CORRECTIONS_20260823.md](thesis_main/TEST_MANUAL_GT_CORRECTIONS_20260823.md)：Test 人工 GT 相对官方原始 GT 的 30 张实质修订、顺序与历史审计说明。
- [ANALYSIS_DATA_FLOW.md](thesis_main/ANALYSIS_DATA_FLOW.md)
- [PRESCREEN_STEP4_5_CLOSEOUT_NOTE.md](thesis_main/PRESCREEN_STEP4_5_CLOSEOUT_NOTE.md)

瀵瑰簲宸ュ叿锛?
- `tools/thesis_main/analysis/`
- `tools/thesis_main/registry/`
- `tools/thesis_main/data_prep/`
- `tools/thesis_main/foreign_recruitment/`

## 璁烘枃 B 绾?
鐩綍锛歔paper_b/](paper_b/)

B-line covers ambiguity-aware HoHoNet, ZInD mapping, B0 relabel audit, later training, cue, bilayout, and model audit. It is maintained separately from thesis main protocol.

鍏抽敭鏂囦欢锛?
- [AMBIGUITY_AWARE_HOHONET_EXTENSION_PLAN_v1.md](paper_b/AMBIGUITY_AWARE_HOHONET_EXTENSION_PLAN_v1.md)
- [PAPER_B_MODEL_ARCHITECTURE_SPEC_v1.md](paper_b/PAPER_B_MODEL_ARCHITECTURE_SPEC_v1.md)
- [ZIND_MAPPING_AUDIT_PROTOCOL_v1.md](paper_b/ZIND_MAPPING_AUDIT_PROTOCOL_v1.md)
- [B_FREEZE_V2_1_CONTRACT_AUDIT_20260317.md](paper_b/B_FREEZE_V2_1_CONTRACT_AUDIT_20260317.md)
- [B_SELECTION_FREEZE_RERUN_20260317.md](paper_b/B_SELECTION_FREEZE_RERUN_20260317.md)

瀵瑰簲宸ュ叿锛歚tools/paper_b/`

## Label Studio 涓庝簯绔繍琛?
鐩綍锛歔label_studio/](label_studio/)

璇ョ洰褰曚繚瀛樹笁鏉＄嚎鍏变韩鐨?Label Studio CE-only銆乤ctive-time銆佷簯绔儴缃层€佹爣娉ㄥ憳鍜屽紑鍙戣€呰鏄庛€備簯鏈嶅姟鍣ㄨ繍琛屾椂 URL `/tools/vis_3d.html` 淇濇寔鍏煎锛涜繖鏄儴缃茶矾鐢憋紝涓嶈〃绀烘簮鐮佷粛鍦?`tools/` 鏍圭洰褰曘€?
鍏抽敭鏂囦欢锛?
- [LS_CE_ONLY_OPERATION_SOP_v1.md](label_studio/LS_CE_ONLY_OPERATION_SOP_v1.md)
- [label studio娉ㄦ剰浜嬮」.md](label_studio/label%20studio%E6%B3%A8%E6%84%8F%E4%BA%8B%E9%A1%B9.md)
- [ACTIVE_TIME_README.md](label_studio/ACTIVE_TIME_README.md)
- [COS_涓婁紶涓庡鍏ヤ腑鏂囪鏄?md](label_studio/COS_%E4%B8%8A%E4%BC%A0%E4%B8%8E%E5%AF%BC%E5%85%A5%E4%B8%AD%E6%96%87%E8%AF%B4%E6%98%8E.md)
- [README_ANNOTATOR.md](label_studio/README_ANNOTATOR.md)
- [README_DEVELOPER.md](label_studio/README_DEVELOPER.md)
- `tools/label_studio/label_studio_xml_instruction_manifest_v2.json`：未部署即被取代的 Paper A Annotation v2 冻结快照及其历史边界。
- `tools/label_studio/label_studio_uncertainty_meta_manifest_v1.json`：不确定性元标签 v1 的本地待部署入口；修改前配置位于 `tools/label_studio/config_history/uncertainty_meta_v1_prechange_20260824/`。
- [SOP_labelstudio_experiment.md](label_studio/SOP_labelstudio_experiment.md)

瀵瑰簲宸ュ叿锛歚tools/label_studio/`

- `tools/label_studio/vis_3d_pre_m15_19_2_backup.html` is the verbatim `vis_3d.html` snapshot from commit `f6d53b0`, retained only as a pre-M15.19.2 rollback/reference copy; runtime entry points continue to use `vis_3d.html`.

## Agent 涓庡啓鍏ヨ鍒?
鐩綍锛歔agent/](agent/)

- [AGENT_CONTEXT_INDEX.md](agent/AGENT_CONTEXT_INDEX.md)
- [REPO_PATH_MAP.md](agent/REPO_PATH_MAP.md)
- [WRITE_RULES.md](agent/WRITE_RULES.md)
- [playbooks/](agent/playbooks/)

鏍圭洰褰?[../AGENTS.md](../AGENTS.md) 鏄?agent 鐨勫伐浣滃叆鍙ｏ紱`docs/agent/WRITE_RULES.md` 鏄?tools/docs 鍐欏叆杈圭晫鐨勭粏鍖栬鏄庛€?
## 鏈湴鍏变韩鏉愭枡

鐩綍锛歔shared/](shared/)

淇濆瓨璁烘枃妯℃澘銆佸弬鑰冩潗鏂欏拰鍏变韩鍐欎綔璧勪骇銆傝鏂囦富绾?Overleaf 椤圭洰鍙斁鍏?`docs/thesis_main/manuscript/`銆?
杩欎簺璧勬枡鐩綍鎸夌幇鏈?`.gitignore` 榛樿涓嶇撼鍏ヤ粨搴撴彁浜わ紱闇€瑕佸叡浜椂鍏堢‘璁ゆ槸鍚﹀簲杩涘叆 Git銆佷簯鐩樻垨璁烘枃鍗忎綔骞冲彴銆?
## 鍘嗗彶鏉愭枡

鐩綍锛歔legacy/](legacy/)

鍘嗗彶鏉愭枡榛樿涓嶈縼绉汇€佷笉淇銆傝矾寰勬鏌ュ拰涔辩爜淇榛樿鎺掗櫎璇ョ洰褰曘€?## 2026-07-24 浠ｇ爜鍏ュ彛琛ュ厖

- C1 鍞竴 task-adjusted Q_GT 浼拌鍣細`tools/thesis_main/analysis/c1_task_adjusted_quality.py`锛坵orker fixed effect銆乼ask random intercept銆乼ask/building cluster bootstrap锛涗笉鐢熸垚鎺掑悕锛?- C2-B 闈欐€?evidence/leakage/split 宸ュ叿锛歚tools/thesis_main/analysis/c2b_static_evidence.py`锛圥1 integrity銆乺eference/candidate SHA audit銆乭istory 鎺ㄥ銆侀潪鏀厤 split 鍊欓€変笌闈欐€佸喕缁擄級
- C1 浜哄伐 task outcome / 鍗曚竴 GT reference锛歚tools/thesis_main/analysis/materialize_c1_operational_reference.py`
- P1鈫扖1鈫扖2-B component evidence锛歚tools/thesis_main/analysis/materialize_routing_component_evidence.py`
- T1/V1 姝ｅ紡鎺ㄦ柇锛歚tools/thesis_main/analysis/materialize_main_inference.py`
- C2 task-risk 涓庝弗鏍间换鍔¤祫鏍?materializer锛歚tools/thesis_main/analysis/materialize_c2_task_risk.py`銆乣tools/thesis_main/analysis/materialize_c2b_task_eligibility.py`
- C2 LHFeat reference/PCA/whitening freeze锛歚tools/thesis_main/analysis/freeze_c2_feature_reference.py`
- C1鈫扖2-B 椋庨櫓鏂滅巼/鏂瑰樊璁捐鍙傛暟锛歚tools/thesis_main/analysis/materialize_c1_c2_design_parameters.py`
- C1 variable-k / rolling enrollment锛歚materialize_c1_estimand_specific_task_support.py`銆乣materialize_w034_active_time_validation.py`銆乣materialize_stage3_freeze_gate.py` 涓?`registry/build_c1_late_entry_assignment_manifest.py`
- C1 authorized addendum / W034 sensitivity锛歚materialize_c1_authorized_reassignment_addendum.py`銆乣materialize_w034_authorized_extension_sensitivity.py`
- C2-B design threshold 鏈烘娲剧敓鍣細`tools/thesis_main/analysis/derive_c2b_design_thresholds.py`
- P1鈫扖1 predictive association锛歚tools/thesis_main/analysis/materialize_p1_c1_predictive_association.py`
- C1 缁撴瀯澶辫触 EB銆丟lobal/Full policy 涓庤交閲忓弽渚嬪簱锛歚tools/thesis_main/analysis/c1_structural_reliability_eb.py`銆乣materialize_global_policy.py`銆乣materialize_full_policy.py`銆乣materialize_counterexample_bank.py`
## Paper A 褰撳墠鏂规硶鍚堝悓

- `thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`锛氬敮涓€瑙勮寖鎬ф満鍣ㄧ湡婧愩€?- `thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.md`锛氱敱 JSON 鑷姩鐢熸垚骞舵惡甯?SHA 鐨勯暅鍍忋€?- `thesis_main/*_v2.json`锛氫簲涓叡浜?record schema銆?


- [PAPER_A_C1_BATCH_SCOPE.template.json](thesis_main/PAPER_A_C1_BATCH_SCOPE.template.json)：C1-A original roster、W034/W001 repair set 与 original cohort completion exception 的 SHA-bound 范围模板。

## 论文主线全量不确定性审计

- 中性 retrospective 数据底座入口：`tools/thesis_main/analysis/full_uncertainty/materialize_uncertainty_substrate.py`；冻结输出：`analysis_results/uncertainty_substrate_20260823_v1/`。该并行底座纳入全部 2,501 条 canonical 记录，旧 eligibility 仅保留为历史字段，不修改方法合同、SAP 或 C2-B/C2-A-RP closeout。
- 工具入口：`tools/thesis_main/analysis/full_uncertainty/materialize_full_uncertainty_data_mining_v5.py`（复用 v4 计算引擎）
- 当前生成目录：`analysis_results/full_uncertainty_data_mining_20260821_v5/`；v4 交付只保留在 Git 历史中。
- 该审计保留 Active time 与 Label Studio Lead time 的边界，不修改规范方法合同或已冻结阶段结果。
- Manual–Semi correctness/OOS 补充审计入口：`tools/thesis_main/analysis/full_uncertainty/analyze_manual_semi_correctness_oos_20260823_v3.py`；结果目录：`analysis_results/manual_semi_correctness_oos_20260823/`。其中资源方案仅为未生成 assignment manifest 的探索性资源算术，不改变正式 T1 的 2×2 设计。

## HoHoNet 初始化代理审计

- 生成工具：`tools/thesis_main/analysis/materialize_model_initialization_audit.py`
- 当前结果：`analysis_results/model_initialization_audit_hybrid_gt_20260823_v4/`（共享逐图 CSV；分别提供旧版 v1 阈值保留报告与角点数量主分析报告）
- v3 保留全景角点原始环序并与仓库 `eval_layout.py` 对齐；GPU 重跑、旧/新预测对照和完整解释见结果目录中的报告与 manifest。
