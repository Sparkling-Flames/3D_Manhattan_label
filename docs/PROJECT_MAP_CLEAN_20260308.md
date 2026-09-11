<!-- PAPER_A_MACHINE_STATUS: normative -->
<!-- PAPER_A_METHOD_CONTRACT_CURRENT.json paper_a_method_20260811_v23 SHA-256 f3c1ea58d0857a40aa2240b4680b674c76fe2cec8f048f61a643d9e4b74b0588 -->
# HOHONET 仓库地图

## 当前研究速查（2026-09-09）

新接手先读交接，再按SOP读取当前结果；已有building预测保留为基线，后续按原图确认同房间并探索跨房间类型。

| 想找什么 | 入口 | 状态或用途 |
|---|---|---|
| 图片分类的目的与当前复核规则 | [图片分类与同房间预测SOP v5](thesis_main/图片分类与同房间收敛预测研究SOP.md) | 旧空间页仅41张意见不一致图亲审；本次260个同房组已看；收敛和持续分歧均研究，非正式合同 |
| 整组复核后的选图与历史人数 | [机器关联表](../analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_20260912.json)、[逐条评论解释](../analysis_results/scene_image_exploration_20260910_v1/group_comment_interpretation_20260912.json) | materialize_same_room_selection.py；原组/子集、空间来源、交界、OOS、难图及历史人数分层；排序是探索安排，不是预测结论 |
| 同房研究的逐对建议 | [整组填写页](../analysis_results/scene_image_exploration_20260910_v1/同房研究_整组复核_v3.html)、[汇总数据](../analysis_results/scene_image_exploration_20260910_v1/same_room_pair_audit_20260912.json) | 全量检索、直接比较、预期范围与信息条件分层；含小幅歧义选项，人工交界只读保留；生成器build_same_room_pair_review.py，不自动传递合组或证明预测有效 |
| 新标准全量原图复核 | [可填写页面](../analysis_results/scene_image_exploration_20260910_v1/室内空间_新标准复核_v3.html)、[报告及填写说明](../analysis_results/scene_image_exploration_20260910_v1/新标准全量复核报告_20260911.md) | 648图主审/讨论沿用、独立交叉意见及人工填写分层；[本地文件/Git说明](../analysis_results/scene_image_exploration_20260910_v1/本地文件与Git保存说明_20260911.md)；生成器build_scene_open_layout_review.py；不覆盖旧页面或源JSON |
| 争议图的批量反馈 | [B01—B15最新决定](../analysis_results/scene_image_exploration_20260910_v1/批量反馈整理_20260911.md)、[原可填写批量页](../analysis_results/scene_image_exploration_20260910_v1/争议图批量快速复核.html) | 2026-09-11；四个低优先级交界候选、B06／B08不同房更正；旧AI建议及用户原始填写保留 |
| 具体人群子类是否进入稳定阶段 | [人员分类与具体子类更新报告](../analysis_results/worker_four_block_exploration_20260910_v1/subtype_stage_validation/README_ZH.md) | `worker_subtype_stages_20260910.py`；303分类配置，按行为含义对应子类、单独回放、参考偏差与多簇；探索SOP第9节；非正式资格结论 |
| 人员组数不固定为二 | [多组补充探索](../analysis_results/worker_four_block_exploration_20260910_v1/group_count_extension/README_ZH.md) | `worker_group_count_exploration_20260910.py`；15指标组合×可行组数；人数、名单、重复性与收敛资料充足性；尚非新的收敛回放 |
| 四类信息组合与质量粗分对照 | [人数与名单修订报告](../analysis_results/worker_four_block_exploration_20260910_v1/report_revision_v2/README_ZH.md)、[原实验](../analysis_results/worker_four_block_exploration_20260910_v1/README_ZH.md) | `worker_four_block_exploration_20260910.py`及同名测试；15组合、各组人数与平均特征、同图同人数稳定性；含Word；非规范探索 |
| 接手研究与下一步 | [研究交接](thesis_main/研究交接_20260909.md) | 意图、结果、待解决问题和两条分析线差异 |
| 后续独立分析整理 | [两轮分析整理](thesis_main/研究交接与独立分析整理_20260909.md) | 非规范补充；第一轮包可读，第二轮仅有粘贴文字，区分新增证据与待核验主张 |
| 新假说的现有数据支持 | [收敛／人员／特征核对](../analysis_results/convergence_hypothesis_review_20260909_v1/README_ZH.md) | 探索支撑；楼内不同稳定过程、候选分档、HoHoNet缓存覆盖与来源差异 |
| uNb预测的实际检验 | [高低人数与特征配平检验](../analysis_results/unb_prediction_check_20260909_v1/README_ZH.md) | 高人数多图留出、特征距离/人数配平及27图混合短窗，含脚本、基线和覆盖 |
| 研究主线与新人验证 | [研究逻辑说明](thesis_main/研究主线与新增标注验证说明_20260909.md) | 讨论稿；导师原文依据、候选问题、新人桥接与新图验证，不冻结RQ或实验安排 |
| 当前方法 | [相似场景SOP](thesis_main/相似场景标注稳定性分析SOP.md) | 全阶段无辅助、硬点数分簇、稳定多簇、并列人员口径 |
| 原图房间/场景初分 | [可填写核对页](../analysis_results/scene_image_exploration_20260910_v1/图片初分核对.html)、[探索说明](../analysis_results/scene_image_exploration_20260910_v1/探索说明.md)、[争议图片复核](../analysis_results/scene_image_exploration_20260910_v1/争议图片复核.html) | valid/test共648图的AI目视候选；门洞内拍摄属性独立，最终由用户分类；生成器build_scene_image_exploration.py、build_scene_user_audit.py |
| 持续阶段、特征与人员组合 | [研究验证报告](../analysis_results/research_validation_20260909_v2/研究验证报告.md)、[客观Word](../analysis_results/research_validation_20260909_v2/相似场景标注稳定阶段与人员组合_客观数据报告.docx) | 最新持续至H、合法k≥2、10楼50图留出、98低人数图待验证；6种层表示与人员复用实算 |
| 局部窗口回放基线 | [分析结果](../analysis_results/multibuilding_threshold_stability_20260909_v1/分析结果.md) | 读revised；根目录geometry/replay/transfer为早期快照，不与新持续阶段人数混算 |
| uNb实际标注人工核对 | [按簇叠加对照表](../analysis_results/research_validation_20260909_v2/annotation_review/uNb标注对照表.html) | 12张高人数图、q=.95现有簇、两个人员范围；候选多解与未归簇明确标注，保留单人查看和观察记录，生成器build_unb_annotation_review_20260910.py |
| 局部窗口计算与核查 | [revised](../analysis_results/multibuilding_threshold_stability_20260909_v1/revised/) | 历史with_workers、without_workers、comparison及QA |
| 有效点集与人工修复 | [reviewed视图](../analysis_results/confirmed_point_calculation_view_20260909_v1/reviewed/) | 原始／有效点、精确身份、处理审计 |
| 人工删点／补点依据 | [用户决定](../analysis_results/multibuilding_threshold_stability_20260909_v1/geometry_audit/USER_DECISIONS.json) | 不凭奇数或人员名自动修改 |
| 输入身份、模型和参考 | [便携输入包](../analysis_results/uncertainty_cloud_inputs_20260906_v1/README_ZH.md) | 214历史图、166候选图和原始来源 |
| 评论和初始化连接 | [连接说明](../analysis_results/uncertainty_decision_ready_20260908_v1/README_ZH.md) | 事实资料及历史精度审查 |
| building数量、版本、人员排列 | [census](../analysis_results/building_holdout_exploration_20260908_v1/census/README_ZH.md) | 保持原路径，当前回放有依赖 |
| 人员类型与组合研究 | [类型人数探索](../analysis_results/type_convergence_exploration_20260909_v1/README_ZH.md)、[参考偏差](../analysis_results/worker_reference_feasibility_20260909_v1/pooled/README_ZH.md)、[Semi行为及复审](../analysis_results/semi_subtype_exploration_20260909_v1/README_ZH.md) | 粗／细类尚未确认；旧人数曲线未落实硬点数约束，不能直接拼接当前结果 |
| 最新粗类验证 | [26人／20人粗类验证](../analysis_results/worker_coarse_validation_20260910_v1/README_ZH.md) | `tools/thesis_main/analysis/validate_worker_coarse_20260910.py`；留楼分型、硬点数持续阶段及同人数对照，测试 `tests/test_validate_worker_coarse_20260910.py` |
| 可解释速度与执行偏差 | [速度两轴画像](../analysis_results/worker_behavior_time_20260910_v1/README_ZH.md) | `tools/thesis_main/analysis/worker_behavior_time_20260910.py`；原日志审计、加秒排除与跨阶段验证，测试 `tests/test_worker_behavior_time_20260910.py`；探索用途 |
| 规则执行与三指标分型 | [规则／三指标报告](../analysis_results/worker_rule_triad_20260910_v1/README_ZH.md) | `tools/thesis_main/analysis/worker_rule_triad_20260910.py`；修改、时间、参考质量同面板与迁移检验；测试 `tests/test_worker_rule_triad_20260910.py`；候选类别 |
| 计算代码与测试 | [analysis](../tools/thesis_main/analysis/)、[data_prep](../tools/thesis_main/data_prep/)、[tests](../tests/) | 本轮命令与字段见研究验证报告附录D；交付检查见research_validation_20260909_v2/DELIVERY_CHECKS.json；旧命令保留于交接 |
| 已撤下的旧结果 | [历史归档](../analysis_results/research_history_archive_20260909_v1/README_ZH.md) | 原路径、ZIP成员和恢复说明 |
| 正式实验合同 | [方法合同JSON](thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json) | 历史探索不改变正式协议 |

以下为项目目录边界和历次登记。

> 2026-07-18 vFinal 鏇存柊锛歅aper A 姝ｅ紡涓荤嚎宸叉敼涓?C1 璁捐 C2-B
>锛坈ommon anchor + diverse bridge锛夈€丆2-A-RP 绮惧害琛ユ祴銆乀1 2脳2 鏉′欢璇曢獙锛?> 浠ュ強 Strong Global 瀵?Full-Integrated 鐨?V1 鍓嶇灮鍙岃噦鏀跨瓥璇曢獙銆?> `docs/thesis_main/manuscript/overleaf_project/main.tex` 鏄敮涓€璁烘枃鍏ュ彛锛?> 宸插垹闄よ宸ョ▼鍐呮湭寮曠敤鐨勬棫鐗堥噸澶嶇珷鑺傘€侰1 鍘熷 export銆乤ssignment 鍜屾爣娉ㄧ晫闈㈡湭鏀瑰彉銆?> 鏂版寮忓疄鐜颁綅浜?`tools/thesis_main/analysis/materialize_main_failure_outcomes.py`銆?> `build_c2_assignment_manifest_from_c1_gaps.py`銆乣c1_materialize_c2_gap_audits.py`
> 鍜?`routing/v1_policy.py`锛涘垎鍒礋璐ｅ畬鏁翠簨鏁呭缃笌 resolver銆丆2-B銆丆2-A-RP
> 浠ュ強 Strong Global/Full-Integrated 鐨?V1 鍓嶇灮鎵ц銆?> `tools/thesis_main/analysis/materialize_vfinal_main_analysis.py` 鍙秷璐?resolver
> 鏈€缁堣〃锛岀敓鎴?T1 pair estimand 涓?V1 ITT/璁捐鍜岀敓浜ф爣鍑嗗寲缁撴灉銆?
鏇存柊鏃堕棿锛?026-06-08

鏈湴鍥捐褰曞綋鍓嶄粨搴撶殑涓昏鐩綍杈圭晫銆傛柊澧炪€佸垹闄ゃ€佺Щ鍔ㄦ枃浠跺悗蹇呴』妫€鏌ユ湰鏂囨。鏄惁闇€瑕佸悓姝ャ€?
## 椤跺眰鐩綍

- `tools/`锛氳剼鏈拰杩愯璧勬簮锛屾寜璁烘枃绾夸笌鍏变韩杩愯灞傛媶鍒嗐€?- `docs/`锛氬崗璁€丼OP銆佸瓧娈靛悎鍚屻€佽鏂囩嚎鏂囨。鍜?agent 瑙勫垯锛涜鏂囨ā鏉?鍙傝€冭祫鏂欑瓑澶у潡鍐欎綔璧勪骇榛樿鎸?`.gitignore` 鐣欏湪鏈湴銆?- `import_json/`锛歱lanned import / planned split 鐪熸簮銆?  - `stage1_prescreen_foreign_https_20260609/`锛歋tage 1 / P1 澶栧浗鏍囨敞鍛?HTTPS Label Studio 瀵煎叆鍖咃紱浠呭皢姝ｅ紡涓枃鍖呯殑 `data.vis_3d` base URL 鏀逛负 `https://label.sparkle0825.top`锛屼换鍔℃睜銆侀『搴忋€乵etadata銆乸roposal 涓庡浘鐗?URL 淇濇寔涓嶅彉銆?- `export_label/`锛歀abel Studio 杩愯鏃舵爣娉ㄥ鍑虹湡婧愶紝涓嶄綔涓鸿剼鏈啓鍏ョ洰鏍囥€?- `active_logs/`锛氬師濮?`active_time` 鏃ュ織鐪熸簮锛沗operational_incidents/` 淇濆瓨 C1 璧蜂笉鍙彉鐨勮繍琛屼簨鏁呰瘉鎹紝涓嶄笌鍒嗘瀽杈撳嚭娣风敤銆?- `analysis_results/`锛氱敓鎴愮粨鏋溿€佸璁°€乵anifest銆佸浘琛ㄥ拰涓棿鍒嗘瀽浜х墿銆?- `tests/`锛歵ools 涓庡瓧娈靛悎鍚岀殑 pytest 瑕嗙洊锛汸aper A 姝ｅ紡閾炬柊澧炴寜 `contracts/`銆乣c1/`銆乣c2b/`銆乣e2e/` 鍒嗙被锛屾湭鍒嗙被鍘嗗彶娴嬭瘯缁х画淇濈暀鍦ㄦ牴鐩綍銆?- `data/`锛氭暟鎹祫浜с€?- `output/`锛欻oHoNet 鎺ㄧ悊涓庝腑闂翠骇鐗┿€?- `trap闆?`锛歵rap / manual 鍊欓€夌礌鏉愬眰銆?
## tools 甯冨眬

- `tools/thesis_main/data_prep/prepare_c2b_validation_inputs.py`: builds the validation-only C2-B input bundle; C1 and legacy rows remain support-only.
- `tools/thesis_main/registry/build_c2b_worker_distribution_release.py` and `build_c2b_worker_distribution_workbook.mjs`: derive the redacted C2-B worker-facing `D / 任务4` lists and per-Chinese-worker workbook from the frozen assignment/planned import; the external assignment manifest remains authoritative.

- `tools/README.md`锛歵ools 鎬诲叆鍙ｏ紱鏍圭洰褰曚笉鍐嶄繚鐣欐棫鑴氭湰 wrapper銆?- `tools/thesis_main/`
  - 璁烘枃涓荤嚎宸ュ叿銆?  - `analysis/`锛氳川閲忓垎鏋愩€乤ctive-time audit銆乻tage-aware 鍒嗘瀽銆佸浘琛ㄣ€佺粺璁℃眹鎬汇€?    - `c1_live_collection_monitor.py`銆乣c1_canonicalize_exports.py`銆乣failure_disposition.py`銆乣materialize_main_failure_outcomes.py`銆乣c1_materialize_quality_table.py`銆乣c1_materialize_worker_state.py`銆乣c1_materialize_worker_profile_sidecar.py`銆乣c1_materialize_c2_gap_audits.py`銆乣build_c2_assignment_manifest_from_c1_gaps.py`銆乣materialize_c2b_task_eligibility.py`銆乣materialize_p1_post_closeout_evidence_correction.py` 涓?`materialize_p1_post_closeout_geometry_scores.py`锛欳1 live 鐩戞帶銆乧anonicalization銆佸け璐ュ綊鍥犮€侀€愯酱璇佹嵁銆丆2-B 涓ユ牸浠诲姟璧勬牸銆佸€欓€夎璁′笌鍐荤粨 assignment 娑堣垂锛屼互鍙婂彧璇?P1 post-closeout evidence/geometry correction銆?    - `rebuild_stage1_chinese_completion_excel.py`锛氭寜鏈€鏂?`鏍囨敞浜哄憳.xlsx`銆乣閫€鍑烘爣娉?xlsx`銆丼tage 1 涓枃 LS JSON 瀵煎嚭鍜?active logs 閲嶇畻涓枃 P1 瀹屾垚鎯呭喌宸ヤ綔绨裤€?  - `registry/`锛歳egistry銆乵anifest銆乫reeze銆乫inal-gold銆乼rap/materialization銆乺isk-rule銆丆2 failure-disposition manifest銆乣d_t/g_t` dry-run銆乪xport inventory銆?  - `data_prep/`锛氭暟鎹泦鍑嗗鍜?MP3D smoke/import 鐢熸垚銆?  - `foreign_recruitment/`锛歅1/PreScreen 澶栧浗鏍囨敞鍛?HTTPS 鑻辨枃閫傞厤鍖呫€?- `tools/paper_b/`
  - Paper B 宸ュ叿銆傚綋鍓嶅寘鎷?`validate_b0_relabel_audit.py`锛涘悗缁?B0/B1/B2 璁粌銆乧ue銆乥ilayout銆佸璁¤剼鏈彧杩涙湰鐩綍銆?- `tools/label_studio/`
  - 涓夋潯绾垮叡浜殑 Label Studio XML銆?D viewer銆乻erver/CORS銆丆OS/upload銆乮mport/build helper 鍜?`official/`銆傚巻鍙?C1 XML 淇濇寔鍘熻涔夛紱C2/Stage3 鏈潵璇箟浣跨敤 `label_studio_view_config_c2_future.xml` 涓庤嫳鏂囧搴旀枃浠讹紱鍐荤粨 SHA 璁板綍鍦?`tools/label_studio/label_studio_xml_instruction_manifest_v2.json`銆?  - `vis_3d_pre_m15_19_2_backup.html`锛歝ommit `f6d53b0` 鐨?viewer 鍘熸牱澶囦唤锛屼粎鐢ㄤ簬鍥炴粴/瀵圭収锛屼笉鏄繍琛屾椂鍏ュ彛銆?  - 浜戞湇鍔″櫒杩愯鏃?URL `/tools/vis_3d.html` 淇濇寔鍏煎锛岃繖鏄儴缃茶矾鐢憋紝涓嶄唬琛ㄦ簮鐮佷粛鍦?`tools/` 鏍圭洰褰曘€?- `tools/legacy/`銆乣tools/legacy_server/`銆乣tools/backups/`
  - 鍘嗗彶鎴栧浠界洰褰曪紝榛樿涓嶈縼绉汇€佷笉淇銆?
## docs 甯冨眬

- `docs/README_INDEX.md`锛歞ocs 鎬荤储寮曘€?- `docs/PROJECT_MAP_CLEAN_20260308.md`锛氭湰鏂囦欢锛屼粨搴撳湴鍥俱€?- `docs/thesis_main/`
  - 姝ｅ紡鎵ц涓荤嚎鏂囨。銆?  - 鍖呮嫭 protocol銆乤ssignment SOP銆丳reScreen銆丆alibration銆丮ain(Test + Validation)銆佺粺璁¤鍒掋€佸瓧娈靛悎鍚屻€亀orker-profile sidecar contract銆乫inal-gold銆乺egistry銆佽鏂囦富绾垮啓浣滄潗鏂欍€?  - Paper A 鍞竴瑙勮寖鏂规硶鐪熸簮涓?`PAPER_A_METHOD_CONTRACT_CURRENT.json`锛沗Paper_A_鏂扮増瀹屾暣璁烘枃鎻愮翰_vFinal_Draft.md` 宸叉爣涓?superseded 鐨勯潪瑙勮寖鎬у啓浣滆儗鏅€倂3-v5 鎻愮翰銆佽縼绉?map/audit 涓?standalone `.tex` 宸插綊妗ｅ埌 `docs/legacy/paper_a_pre_vfinal_20260724/`锛沗WORKER_PROFILE_ARTIFACT_FIELD_CONTRACT_v1.md` 绛夊瓧娈靛悎鍚岀户缁繚鐣欍€?  - `manuscript/` 鍙繚瀛?Overleaf 椤圭洰鍜屼富绾胯鏂囧啓浣滆祫浜э紝浣嗘寜鐜版湁 `.gitignore` 榛樿涓嶆彁浜ゃ€?  - `tools/thesis_main/analysis/materialize_c2b_closeout.py` 缁戝畾 C2-B submissions銆乸ost-C2-B profile銆乸rofile manifest 涓?design summary锛屽舰鎴?C2-A-RP formal 鎵€闇€鐨勭湡瀹?SHA closeout銆?  - `tools/thesis_main/analysis/materialize_frozen_routing_profiles.py` 浠?Manual GT submission銆佸喕缁?worker state 鍜岃法闃舵 component evidence 鐢熸垚 Strong Global 涓?Full component 鍐荤粨琛ㄣ€?  - Paper A vFinal 浠ｇ爜杩佺Щ鍚堝悓銆佸洓涓€欓€?rule manifest 涓庡璁¤褰曚繚瀛樺湪璇ョ洰褰曪紱杩欎簺鏂囦欢鍙畾涔夊彲瀹¤鐨勭粨鏋勫拰鍊欓€夎鍒欙紝涓嶆妸 dry-run 浜х墿鍗囩骇涓烘寮?C1 鏁版嵁銆傚搴旂殑 canonical鈫抍oncrete-tag銆丟eometry LOO 涓?temporal replay 浠ｇ爜浣嶄簬 `tools/thesis_main/analysis/`锛屼笖鏃犳寮?export 鏃跺彧鑳借緭鍑?dry-run/not-evaluable銆?  - Paper A vFinal 浠ｇ爜杩佺Щ鍚堝悓銆佸洓涓€欓€?rule manifest 涓庡璁¤褰曚繚瀛樺湪璇ョ洰褰曪紱杩欎簺鏂囦欢鍙畾涔夊彲瀹¤鐨勭粨鏋勫拰鍊欓€夎鍒欙紝涓嶆妸 dry-run 浜х墿鍗囩骇涓烘寮?C1 鏁版嵁銆?- `docs/paper_b/`
  - Paper B 鏀嚎鏂囨。銆?  - 鍖呮嫭 ambiguity-aware HoHoNet銆乑InD mapping銆丅-line freeze/audit銆佹ā鍨嬫灦鏋勫拰鍚庣画璁粌璁″垝銆?- `docs/label_studio/`
  - Label Studio CE-only銆乤ctive-time銆佷簯绔儴缃层€丆OS銆佹爣娉ㄥ憳/寮€鍙戣€呰鏄庛€?- `docs/agent/`
  - Agent 涓婁笅鏂囥€乸laybook銆佸啓鍏ヨ鍒欏拰缁?Codex 鐨勮ˉ鍏呰鏄庛€?  - 鍏抽敭鍏ュ彛锛歚AGENT_CONTEXT_INDEX.md`銆乣REPO_PATH_MAP.md`銆乣WRITE_RULES.md`銆乣playbooks/`銆?- `docs/shared/`
  - 璁烘枃妯℃澘銆佸弬鑰冭祫鏂欍€佸叡浜啓浣滆祫浜э紱鎸夌幇鏈?`.gitignore` 榛樿涓嶆彁浜ゃ€?- `docs/legacy/`
  - 鍘嗗彶鏉愭枡锛岄粯璁や笉杩佺Щ銆佷笉淇銆?
## 鐪熸簮涓庤緭鍑哄眰

- `import_json/` 鏄?planned import / planned split 鐪熸簮銆?- `export_label/` 鏄?Label Studio 杩愯鏃跺鍑虹湡婧愶紱鏈 tools/docs 杩佺Щ涓嶅啓鍏ャ€佷笉绉诲姩銆佷笉閲嶅懡鍚嶃€?- `active_logs/` 鏄師濮?active-time 鏃ュ織鐪熸簮锛沗active_logs/operational_incidents/` 鏄?C1 璧峰閮ㄧ郴缁熶簨鏁呯殑鍘熷璇佹嵁婧愩€?  - 浜戞湇鍔″櫒绔粛搴斾綅浜庝粨搴撴牴涓嬶紝渚嬪 `/home/ubuntu/workspace/HoHoNet/active_logs/`銆?  - 鑻ヤ簯绔缃?`ACTIVE_LOG_DIR="active_logs/new_server"`锛屾柊鏃ュ織搴旇繘鍏?`/home/ubuntu/workspace/HoHoNet/active_logs/new_server/`銆?  - `tools/label_studio/cors_server.py` 鐨勬簮鐮佽縼绉讳笉搴旀敼鍙樻棩蹇楀瓨鍌ㄦ牴鐩綍銆?- `analysis_results/` 鏄緭鍑恒€佸璁″拰鍥捐〃钀界洏鍖猴紝涓嶆槸杈撳叆鐪熸簮銆?
## 鍐欏叆涓庤縼绉昏鍒?
- 鏂板 `tools/` 鑴氭湰蹇呴』杩涘叆瀵瑰簲璁烘枃绾挎垨鍏变韩 Label Studio 鐩綍锛屼笉寰楃洿鎺ユ斁鍦?`tools/` 鏍圭洰褰曘€?- 鏂板 `docs/` 涓婚鏂囨。蹇呴』杩涘叆瀵瑰簲鍒嗙被鐩綍锛屼笉寰楃洿鎺ユ斁鍦?`docs/` 鏍圭洰褰曘€?- 涓荤嚎宸ュ叿鍜屾枃妗ｅ垎鍒繘鍏?`tools/thesis_main/` 涓?`docs/thesis_main/`銆?- Paper B 宸ュ叿鍜屾枃妗ｅ垎鍒繘鍏?`tools/paper_b/` 涓?`docs/paper_b/`銆?- Label Studio 鍏变韩璧勬簮鍜岃鏄庡垎鍒繘鍏?`tools/label_studio/` 涓?`docs/label_studio/`銆?- Agent 瑙勫垯鍜?playbook 杩涘叆 `docs/agent/`銆?- legacy 榛樿涓嶈縼绉汇€佷笉淇銆?- 涓嶆敼鍙?protocol銆乻chema銆乺outing銆丼OP 璇箟銆?## 2026-07-24 Paper A 鍒嗘瀽閾炬敹鍙ｈˉ鍏?
  鍒嗗眰鐗╁寲锛涚己 C2-B 鏃?Full 鑷姩绂佺敤銆?- `tools/thesis_main/analysis/materialize_main_inference.py`锛歍1 image-level 涓?V1 ITT 鐨?manifest/SHA 缁戝畾

`docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json` 鏄敮涓€瑙勮寖鏂规硶鐪熸簮锛涘悓鐩綍淇濆瓨鐢熸垚 MD 鍜屼簲涓?v2 schema銆傚叡浜獙璇併€乬eometry銆丼tage 3銆乀1/V1 online/replay 宸ュ叿浣嶄簬 `tools/thesis_main/analysis/`銆?
- docs/thesis_main/PAPER_A_REFERENCES_NEEDED_CHECKLIST.md锛氱浉鍏冲伐浣滀笌寮曠敤鏍搁獙寰呭姙锛涗笉鏋勬垚鏂规硶鍚堝悓銆?

## 2026-08-02 C2 closeout repair

- `tools/thesis_main/analysis/materialize_c2a_rp_closeout.py`：C2-A-RP 正式零任务/追加任务 closeout 与方法合同、输入工件 SHA 绑定。
- `tools/thesis_main/analysis/materialize_c2a_rp_block1_reestimate.py`：统一应用终态 reference exclusion、重拟合 Block 1 后 risk slope，并输出 SHA 绑定的 Block 2 routing 输入。
- `tools/thesis_main/analysis/materialize_c2a_rp_block2_evidence.py`：将 Block 2 原始导出、正式 GT、assignment、task pool 与冻结 active-time 绑定为可审计 evidence。
- `tools/thesis_main/analysis/materialize_c2a_rp_terminal_reestimate.py`：合并 C2-B、Block 1 与 Block 2 evidence，生成 C2-A-RP 终态 risk re-estimation。
- `tools/thesis_main/analysis/materialize_final_calibration_profile.py`：在 C2-A-RP 终止声明与 closeout 后生成最终 Calibration Q_GT 与 pooled worker profile 物化工件。
- `tools/thesis_main/data_prep/build_post_block2_analysis_pack_v3.py`：在终态 profile 可用后重建 QA-approved post-Block2 pack，并补齐 uncertainty 与 empirical variance 输入。
- `tools/thesis_main/data_prep/build_post_block2_analysis_pack_v4.py`：保留 v3 历史工件，使用冻结 building identity 真源修复 building support 与 worker-building incidence 后生成新版本 pack。
- `tools/thesis_main/analysis/analyze_post_block2_opportunities.py`：运行 post-Block2 aggregation、matched routing、clustered power 与 estimand 候选矩阵的 retrospective/development 审计。
- `tools/thesis_main/analysis/audit_c2a_capacity_power_amendment.py`：C2-A-RP 本地 capacity / V1 power 敏感性审计；不生成或授权正式派发。

## 2026-08-02 C2-B pre-dispatch amendment

- `docs/thesis_main/C2B_PREDISPATCH_METHOD_AMENDMENT_v1.json`：v17 绑定的 D8/D10/D12 统一候选生成与 gate 语义修订；不改变数值阈值。
- `docs/thesis_main/C2A_RP_PRECISION_CAP_EXTENSION_20260807_v1.json`：C2-A-RP outcome 可见前冻结的最多 5 个平衡 block 精度上限修订；不改变风险或 CI 阈值。
- `docs/thesis_main/C2A_RP_BLOCK2_CAPACITY_AMENDMENT_20260811_v3.json`：统一 slope uncertainty 实现后冻结 Block 2--5 的 `max_task_support=4` 和 20 人 roster；未来 block 仍须逐轮重估且不预分配。
- `docs/thesis_main/C2B_HISTORICAL_EVIDENCE_ACCEPTANCE_20260811_v1.json`：SHA 绑定已经结束的 v18 C2-B、修正后 Block 1 重估和 reference review，供后续 closeout/final profile 消费，不重开历史阶段。
- `docs/thesis_main/FULL_MATERIALIZATION_PROCEDURE_v1.json`：Full 的 risk/family shrinkage、同量纲转换、Calibration-only 权重/cap 选择和 task activation 时点规范；不含由未完成 C2-A 结果决定的最终数值。

## 2026-07-30 Paper A C1-A/C2-B batch boundary

- `tools/thesis_main/analysis/run_c1_closeout_launch.py` 统一提供 `freeze-c1-batch`、`design-c2b`、`build-c2b --assignment-batch` 和 `bind-c2b-runtime-mapping`；它们不连接 Label Studio API。
- PAPER_A_C1_BATCH_SCOPE.template.json 定义 C1-A scope：original cohort、W034 17 张、W001 3 张，以及如 W011 漏交任务的显式 completion exception。
- Stage 3 只读取全局 enrollment closed、all terminal 和 final pooled profile 状态；C1-A snapshot 不可替代该门。

## 2026-08-09 Paper A Scope v2 与 Label Studio 英文资产归位

- `tools/label_studio/localized/en/`：英文 XML 与 HTTPS userscript 的现行运行路径。
- `tools/label_studio/config_history/scope_instruction_v1_pre_block2/`：Block 2 前六份中英文 XML 与旧 freeze manifest 的 SHA 冻结快照。
- `tools/label_studio/label_studio_xml_instruction_manifest_v2.json`：v1/v2 路径、SHA、生效边界与“本地就绪/尚未部署”状态真源。
- `tools/thesis_main/foreign_recruitment/`：仅保留海外招募、安装、legacy 与私有运营说明，不再保存 Label Studio 活运行资产。

## 2026-08-24 标注不确定性候选实验讨论稿

- `docs/thesis_main/ANNOTATION_UNCERTAINTY_CURRENT_STATUS_HANDOFF_20260830.md`：当前标注不确定性研究的非规范交接入口；分开记录已确认历史证据、多人多轮候选路径、沟通反馈的可能解释和待确认歧义，并登记 uncertainty analysis 的 current/supporting/superseded 状态。本文件不修改方法合同、SAP、T1/V1 或授权实验启动。
- `tools/thesis_main/analysis/materialize_historical_uncertainty_k_curves_20260829.py`、`tools/thesis_main/analysis/build_historical_uncertainty_workbook_20260829.mjs` 与 `analysis_results/historical_uncertainty_recompute_20260829_v1/`：42图/1,055条规范历史标注的当前复算链；包含无reference恢复、reference-relative质量、整体分歧、少数结构和阈值敏感性，结果只适用于有限历史roster。其上游 `rq1_raw_recompute_20260826/` 与 `rq1_stratified_uncertainty_20260827_v1/` 保留原路径以维持manifest复现。
- `tools/thesis_main/analysis/audit_worker_manual_strata_exploratory.py` 与 `analysis_results/worker_manual_strata_audit_20260904_v1/`：仅用 C1 Calibration_core Manual 的 task-adjusted Q_GT 做逐 building 的 H/L/U 证据分层，并在 dense41 Manual 上作零任务重叠的混合重放；当前不支持冻结稳定 worker 类型，且不改变正式 worker profile、routing 或方法合同。
- `tools/thesis_main/data_prep/build_annotation_uncertainty_prescreen_review.py` 与 `analysis_results/annotation_uncertainty_prescreen_20260903_v1/`：导师定稿前的非规范图片准备链；审计314张正式链未提交Test图，并从166张无现有annotation记录池生成24张核心图+6张边界图的可撤回研究者审阅包。机器结论仅为提示，不冻结样本、不导入Label Studio、不修改方法合同或SAP。
- `docs/thesis_main/ANNOTATION_UNCERTAINTY_EXPERIMENT_SUPERVISOR_DRAFT_v2.md`：基于历史失败审计重新定位的导师讨论稿 v2；非规范、未批准，仅提出候选 RQ、24×3×4 三臂设计、最小元标注、离线几何环序/残差与统计成功判据，不改变正式合同、SAP、T1/V1、已关闭阶段、Label Studio 分发或历史真源。
- `docs/thesis_main/ANNOTATION_UNCERTAINTY_EXPERIMENT_SUPERVISOR_DRAFT_v1.md`：标注不确定性候选研究的导师讨论稿；非规范、未批准、不得直接启动。当前以全部Manual分层RQ1与72图三臂候选实验为主；v2 元标签将工人侧问题与修复改为多选集合比较，研究者侧仍保留主要缺陷与刺激纯度。候选连续主指标为periodic equirectangular `D_mask`，20人可为全新cohort，active time仅作辅助，`R_vis`须先独立验证，不采用完整topology signature或技术阶段锁；不修改当前方法合同、SAP、T1或 Label Studio 分发工件。
- `docs/thesis_main/ANNOTATION_UNCERTAINTY_EXTERNAL_REVIEW_PROPOSAL_NOTE_v1.md`：外部审稿方案的独立简要记录；非规范、未采纳，不覆盖导师讨论稿或任何方法真源。
- `tools/thesis_main/analysis/analyze_historical_model_issue_construct.py` 与 `analysis_results/historical_model_issue_construct_validation_20260827_v1/`：回放18张历史 P1 Semi proposal，以历史冻结 reference 和每图26名工人的旧 Model Issue 分布压力测试新分类；保留逐图预览、分布表与研究者新分类。属于开发审计，不重编码旧数据或冻结新 truth。
- `tools/thesis_main/data_prep/build_annotation_uncertainty_batch1_review.py`、`analysis_results/annotation_uncertainty_batch1_broad_review_20260828_v1/` 与 `analysis_results/annotation_uncertainty_batch1_supplement_review_20260828_v1/`：从混合GT v4的Test 458+Validation 190共同总体中，仅按manifest所列中等连续几何带形成139张宽候选（Test 124、Validation 15），并在此前28张已有14张PASS的基础上先生成8张无重合补充预审小批。自动量只形成机械覆盖层，AI意见只作优先核实提示；人工审核记录缺陷多选、主要缺陷、修复动作、修正范围、刺激纯度和结构QC。候选阶段不做图级历史排除，正式分发才执行same-worker×same-image去重；输出未冻结、未分发、不是LS import或正式刺激truth。此前审核包均保留作开发审计。
- `import_json/uncertainty_meta_feasibility_20260824/`：现有中文 LS 不确定性标签的开发测试导入包；仅使用 5 张已有 P1 Semi 标注图片，8 人同图复测，共 40 条本地分配，不进入正式分析。
- `analysis_results/uncertainty_meta_feasibility_20260824_v1/`：上述开发测试的本地中文任务表、外部分配真源与内部样本清单；含真实姓名的运营文件按 `.gitignore` 保持本地。

## 2026-08-21 Paper A 全量不确定性审计工具归位

- `tools/thesis_main/analysis/full_uncertainty/materialize_uncertainty_substrate.py`：P1–C2-A-RP 中性 retrospective 数据底座 v1 入口；从 raw export/active log/planned import 事实层出发，以阶段 canonical freeze 仅作身份与 provenance 对账。
- `analysis_results/uncertainty_substrate_20260823_v1/`：2,501 条 canonical、2,513 个原始版本及 geometry/meta/proposal/reference/time 分层交付；旧 eligibility 不作全局过滤，且不重开 C2-B/C2-A-RP。
- `tools/thesis_main/analysis/analyze_rq1_stratified_uncertainty_20260827.py` 与 `analysis_results/rq1_stratified_uncertainty_20260827_v1/`：RQ1 探索性分层复算入口与交付；直接重读 P1–C2-A-RP 原始导出，按批次/条件保留 218 个 Manual task-image 单元，以 42 个 P1/C1 高密度单元校准支持数，并将 C2-B 4 个高支持单元单列复核。该分析不改变正式方法合同或历史 closeout。
- `tools/thesis_main/analysis/full_uncertainty/`：论文主线的全阶段标注不确定性、Manual/Semi、Crowd–GT、proposal 与时间来源审计生成链；v5 编排入口为 `materialize_full_uncertainty_data_mining_v5.py`，计算引擎复用 v4。
- `analysis_results/full_uncertainty_data_mining_20260821_v5/`：当前全量生成交付目录；v4 交付只保留在 Git 历史中。该目录属于派生输出，不是输入真源，也不改变 C2-B/C2-A-RP 冻结状态。
- `tools/thesis_main/analysis/full_uncertainty/analyze_manual_semi_correctness_oos_20260823_v3.py`：Manual–Semi correctness、严格 observed-field 候选、OOS 缺口与条件功效的当前编排入口；v1/v2 是其顺序依赖层。
- `analysis_results/manual_semi_correctness_oos_20260823/`：上述补充审计的唯一 canonical 派生结果目录。资源核算表中的两臂/三臂方案仅为未生成 worker–image assignment manifest 的探索性资源算术，不替代正式 T1 的 `Manual/Semi × ordinary/stress_assist`、每图 2+2 与 image-level paired estimand。

## 2026-08-23 官方 MP3D GT 模型初始化代理审计

- `tools/thesis_main/analysis/materialize_model_initialization_audit.py`：以 Test 的“30 张确认人工 GT + 428 张官方原始 GT”和 Validation 的 190 张官方原始 GT（均排除 no-occ）评估 HoHoNet ep300 最终布局；角点对数量是拓扑硬门槛，ZInD-inspired 1% 图宽角点匹配与项目几何联合门共同定义初始化正确性。
- `docs/thesis_main/TEST_MANUAL_GT_CORRECTIONS_20260823.md`：记录 `export_label/groudTruth.json` 相对官方 Test GT 的 30 张用户确认人工修订；不改写运行时导出，也不替代本次官方 GT 主分析。
- `analysis_results/model_initialization_audit_hybrid_gt_20260823_v4/`：当前 648 张共享逐图 CSV、旧版 post-hoc v1 阈值保留报告、角点数量主分析报告与运行清单；GPU 重跑证据继续绑定 v3 清单。v3 修复了官方式 2D/3D 指标前错误按 x 重排全景角点的问题，v4 不改逐图数据，只拆分解释口径。`model_initialization_audit_hybrid_gt_20260823_v2/` 与 `model_initialization_audit_official_gt_20260823_v1/` 仅保留为已知旧口径对照。以上均属于派生审计输出，不改变 Paper A 正式协议或 T1/V1 estimand。

## 2026-08-28 Label Studio 不确定性元标签 v2

- `tools/label_studio/label_studio_uncertainty_meta_manifest_v2.json`：中英文 Manual/Semi/future XML 与四份 Userscript 的当前本地待部署入口；原生 XML 负责必填与条件分支，Userscript 仅补 `difficulty_reason` 的互斥规则，active time 不变。
- `tools/label_studio/label_studio_uncertainty_meta_manifest_v1.json`：Project 86 开发测试使用的 v1 清单，配置由 Git 修订 `e1038a9` 保留；非正式合同，旧响应不追溯重编码。
- `tools/label_studio/config_history/uncertainty_meta_v1_prechange_20260824/`：更早的十份修改前基线；旧元标签消费者固定读取历史 XML，不回写或重分类旧数据。

## 2026-09-05 研究数据与候选视觉审计

- Git 保留代码、报告、清单、人工记录和分析表；预筛/AI50 的批量预览、审计目录内 `recomputed_*` 副本及工作簿 inspect 日志留在本地，可由对应工具重建。新 checkout 查看审查页前需生成图片资产。
- `analysis_results/annotation_research_decision_audit_20260905_v1/`：研究方向与数据决策说明、资产/来源审计、building 与独立性诊断、50 张新候选 AI 初查和汇总工作簿；保留原始记录，不形成正式实验或最终人工判断。
- `analysis_results/annotation_research_prework_20260905_v2/`：独立第二轮证据链、同图比较、人员连续特征与候选分类留出诊断、历史人数/结构敏感性及三轴文献解释；复用第一轮审图，不修改运行时真源、人工判断或正式协议。
- 第二轮入口：`tools/thesis_main/data_prep/materialize_annotation_research_prework_evidence_20260905.py`（来源连接）；`tools/thesis_main/analysis/materialize_annotation_research_prework_statistics_20260905.py`（探索统计与验证）；`tools/thesis_main/analysis/build_annotation_research_prework_workbook_20260905.mjs`（中文工作簿）。字段合同随独立结果包保留，不升格为正式协议。
- `analysis_results/annotation_reanalysis_independent_audit_20260905_v1/`：外部分析及第二轮材料的独立审查、C1统计复算与口径敏感性、分类参照诊断；入口为`tools/thesis_main/analysis/audit_annotation_reanalysis_claims_20260905.py`，最小检查为`tests/test_audit_annotation_reanalysis_claims_20260905.py`。2026-09-06完成，保留启动日目录；不回写被审查包或正式协议。
- `analysis_results/preflight_independent_audit_20260906_v1/`：前置分析包独立审查、方差/固定面板核验、来源敏感性重拟合及几何表示反例；入口 `tools/thesis_main/analysis/audit_preflight_claims_20260906.py`，检查 `tests/test_audit_preflight_claims_20260906.py`。原包 `analysis_results/preflight_20260906_v2/` 保留，其 `说明勘误_20260906.md` 更正轨迹保存范围；不定义正式实验或替代人工裁决。
- `analysis_results/uncertainty_cloud_inputs_20260906_v1/`：云端可离线读取的不确定性研究输入，保留214历史图、166候选图、原始版本、模型坐标和已有分簇；生成入口 `tools/thesis_main/data_prep/build_uncertainty_cloud_inputs.py`，检查 `tests/test_build_uncertainty_cloud_inputs.py`。图片通过来源URL读取，疲劳与两倾向模拟分开留待研究，不修改原始资料或人工裁决。
- `analysis_results/uncertainty_followup_analysis_20260908_v1/`：独立接手复核及本地export_label来源检索；入口 `tools/thesis_main/analysis/analyze_uncertainty_handoff.py`，检查 `tests/test_analyze_uncertainty_handoff.py`。三份用户确认点序的派生几何及分布恢复、building留图、名单混合结果在 `confirmed_20260908/`；不修改正式协议、旧簇或原始资料。
- `docs/thesis_main/研究交接_20260909.md`：研究接手入口，明确同building即相似场景；当前场景结果与人员类型支线的计算口径尚未统一。
- `analysis_results/research_history_archive_20260909_v1/`：9组旧结果及旧汇报稿的13个ZIP，逐文件字节核对、原路径清单和恢复说明；原目录留归档指引。
- `analysis_results/building_holdout_exploration_20260908_v1/census/`：仍保留逐楼普查、canonical／版本身份和当前回放的200条全局人员顺序。
- `analysis_results/uncertainty_decision_ready_20260908_v1/`：响应、初始化、评论与几何连接；工具位于data_prep的prepare_uncertainty_decision_index、prepare_scope_evidence_20260908及analysis的prepare_human_bi_comparisons_20260908，对应测试保留。
- `analysis_results/independent_direction_worker_review_20260908_v1/`：Bi精度与旧人员分层的独立审查，保留audit_bilayout_precision代码及测试；不代替当前reviewed结果。
- 历史分析工具及同名测试继续保留：building准备／留出／证据、order_free、scene_similarity_revision、participant_support、unb9试算、worker_evidence与worker_mixture；完整运行旧流水线前按归档清单恢复输入。源码位于`tools/thesis_main/analysis/`与`tools/thesis_main/data_prep/`，不迁移模块以免破坏当前导入依赖。
- `docs/thesis_main/相似场景标注稳定性分析SOP.md`：当前历史探索的唯一解释/操作入口；按原始图像确认同房间并探索跨房间类型，两级预测待执行，已有building结果保留为基线。全阶段无辅助手工、图内分簇与跨图人数预测，已确认误点用计算副本排除，硬点数与支持门槛分开；不改Paper A正式合同。
- `analysis_results/confirmed_point_calculation_view_20260909_v1/`：reviewed为2501条当前原始／有效点集视图，累计8份删指定点、2份补点、5份逐份排除，18个来源导出逐条核对。工具 `tools/thesis_main/data_prep/prepare_confirmed_point_calculation_view_20260909.py` 与同名测试；补点标记派生来源，非全局奇数修复。
- `analysis_results/multibuilding_threshold_stability_20260909_v1/`：revised并列包含／排除W19与W26的55高人数及141低人数图，6q与硬点数OSPA、全人数及短窗回放、10楼共同预算预测、不补点敏感性。入口`分析结果.md`，方法由相似场景SOP维护；现有analyze_q_thresholds、replay_multibuilding_stability、transfer_multibuilding_stability、review_multibuilding_thresholds四个20260909脚本及测试复用；共享geometry_metrics配对搜索已修复，原始坐标及正式合同不改。
- `analysis_results/uncertainty_handoff_received_20260907_v1/`：不完整外部移交包原样归档及缺漏记录；原包代码/报告不回写。
- `tools/thesis_main/analysis/upgrade_uncertainty_review_hd.py`：为既有50图审查页接入2048原图、矢量叠图与现有Panorama Studio；显示升级不增加人工裁决或重算研究统计。
- `tools/thesis_main/analysis/review_questionnaire/`：50图三步问卷模板，旧版3D直接展示、高清/新版预览链接、独立浏览器暂存和JSON/CSV导出；由 `prepare_uncertainty_visual_review.py finalize` 生成，验证 `tests/uncertainty_review_questionnaire_browser.cjs`。填写不回写原始响应或正式裁决。
- `tools/thesis_main/analysis/audit_uncertainty_review_order.py`：50图280份展示布局的原坐标、组内角色、组间邻接和原导出来源核对；结果包 `ORDER_REVIEW_ZH.md` 区分数值核对与逐图高清视觉复看。问卷允许全部标注有疑问，独立记录OOS意见与依据（不自动排除），AI意见随时可读；预览工具开发单独交接后，已将角点组排序／恢复／独立导出接入50图；静态同步不重建原始数据。
- `analysis_results/uncertainty_visual_review_20260907_v1/`：独立复算、核心逻辑勘误、5图校准及50图实际辅助视觉检查、仅预览点序建议；入口 `tools/thesis_main/analysis/prepare_uncertainty_visual_review.py`，渲染帮助 `uncertainty_review_renderer.py`，数值勘误 `uncertainty_handoff_errata.py`（同目录）。检查 `tests/test_prepare_uncertainty_visual_review.py`、`tests/test_uncertainty_handoff_errata.py`；不改变原始响应、簇、正式协议或人工裁决。
- `tools/thesis_main/data_prep/build_annotation_research_review50_20260905.py`：从现有剩余 136 候选中按 building 覆盖与差异选取 50 图，排除人工已审 30 图；保留角点环序并用球面投影生成预览。
- `tools/thesis_main/data_prep/inventory_annotation_research_assets_20260905.py`：研究资产依赖、历史候选身份及 building/room 来源索引。
- `tools/thesis_main/analysis/audit_annotation_research_data_20260905.py`：原始来源分类、历史结果复算、独立性敏感性及同图人类/模型差异诊断。
- `tools/thesis_main/analysis/build_annotation_research_decision_workbook_20260905.mjs`：以上派生审计的中文汇总工作簿入口；不替代 CSV/JSON 和原始数据真源。
- `tools/thesis_main/analysis/plot_annotation_research_k15_20_20260905.py`：按阶段/条件固定 k20 图像支持的 15–20 人描述性恢复曲线，分别展示图像与建筑等权结果。
- `tools/label_studio/panorama_studio/`：独立全景布局重建与建筑展台预览；说明 `docs/label_studio/PANORAMA_STUDIO_v1.md`，当前示例 `analysis_results/panorama_studio_20260907_v3/index.html`（v1/v2 保留）；支持角点组预览排序，不写回标注。检查 `tests/test_panorama_studio.py` 与 `tests/panorama_studio_browser.cjs`，不替代现有预览或 A line 流程。
- `analysis_results/human_review_reconciliation_20260907_v1/`：问卷原附件、50图辅助核对及待确认单；入口 `tools/thesis_main/data_prep/reconcile_human_review_comments.py`，检查 `tests/test_reconcile_human_review_comments.py`；点序读取与作者邻接分开，保留原记录和空白裁决。 补充原文enclosed／extended、潜在范围、质量与规则分离的逐条提取；旧候选题仅归档。

- `tools/thesis_main/analysis/explore_semi_subtypes_20260909.py`：Manual参考执行粗依据与Semi附加修改行为的楼外训练/留出验证；结果 `analysis_results/semi_subtype_exploration_20260909_v1/README_ZH.md`，检查 `tests/test_explore_semi_subtypes_20260909.py`。真实初始化追溯、非线性Manual对照和细组收敛覆盖，不生成最终行为类别。

- `tools/thesis_main/analysis/explore_type_convergence_20260909.py`：合并历史资料的两类/三类人员与固定验证组收敛探索，复用无序点集分簇；结果 `analysis_results/type_convergence_exploration_20260909_v1/README_ZH.md`，检查 `tests/test_explore_type_convergence_20260909.py`。不强制单簇，不确定类型或停止人数。

- `tools/thesis_main/analysis/worker_reference_feasibility_20260909.py`：复核优先、其余暂信GT的参考点偏差探索；结果 `analysis_results/worker_reference_feasibility_20260909_v1/README_ZH.md`，检查 `tests/test_worker_reference_feasibility_20260909.py`。`--pooled`将所有阶段/条件合并，仅按图片与人组织，结果位于同包 `pooled/`；`--groups`验证2–5档分位数/Ward训练内分组及人员组合覆盖，结果位于 `pooled/groups/`。不依赖角点顺序，不生成正式工人类别或building停止人数。
