# HOHONET 项目地图

## 2026-10-17 可视化交付位置

- 工作台源码、来源清单与核验材料：`research/statistics/research_explorer_20261017/`，见[说明](../research/statistics/research_explorer_20261017/README.md)。
- 构建工具：`tools/thesis_main/analysis/build_research_explorer_20261017.py`。
- 跨模块判断：[研究进度与独立建议](thesis_main/研究进度与独立建议_20261017.md)。
- 派生显示数据按固定哈希重建，不修改原始标注、参考、评分与资格；不将云端站点路径当作本地路径。

**本轮独立验收：** [跨线程核验与覆盖边界](thesis_main/跨线程接入与统计覆盖核对_20261016.md)：1911份质量覆盖136图；融合普通主比较7图，同范围可比同房完整曲线0。

**当前状态（2026-10-17）：** 当前输入为 [Project98 manifest](../analysis_results/research_input_20261017/manifest.json)，库存3222份作答、261张图；排除既定作答/人员后保留2991份、25人。新增批次70份已接入，7个账号映射到既有人员，任务人员时间5205秒已核验。

- **质量：** [B8L2/D10共同评分v2](../research/quality/quality_b8l2_d10_20261017/README.md)共1911份可用（1699普通、188门洞、24其它单列）；B8L2为主指标，D10为并列敏感性。原B8L2用途v2的1787份是冻结基线；1838份是已被v2接续的路由前中间快照。
- **难度与分层统计：** [难度v6当前261图](../research/difficulty/difficulty_current_20261017/README.md)保留人工粗分类；新增两图列中等，“偏简单”仅备注。质量与难度关联按条件及用途分层，不以均值改标签。完整逐人、逐图、场景及房间关系表见[当前描述统计](../research/statistics/b8l2_d10_statistics_20261017/README.md)。
- **人员：** [B8L2/D10当前画像](../research/workers/worker_b8l2_d10_20261017/README.md)接入更新后的质量覆盖，普通面板1048份；门洞专项并列，不强制固定人员类别。此前949份是旧面板。
- **融合：** [18图人数轨迹的双指标复核](../research/fusion/wall_consensus_d10_20261017/README.md)复用既有融合过程，没有重跑几何或将新增19图冒充新融合样本。
- **同房：** [现有分类下的当前结果](../research/same_room/same_room_update_20261017/README.md)为83对可比质量，其中78对共同人员不少于4人；其它范围15对单列。旧77对为先前阶段。
- **接入边界：** OOS分数只作诊断；`b8c-04`暂停分析但保留在24人库存。原始标注真源保留在`export_label/`，不得由目录或统计结果替代。

质量粗核验与冗余点研究见[三模型核验记录](../research/quality/quality_three_model_review_20261017/RECORD.md)和[多空间冗余点记录](../research/data/scope_redundant_vertices_20261016/README.md)。各版本、分母、来源及历史路径以[研究资料总目录](../research/catalog/INDEX.md)和主题入口为准。

## 研究资料统一查找

**2026-10-16 B8L2主线查阅：** [research/statistics/b8l2_mainline_status_20261016](../research/statistics/b8l2_mainline_status_20261016/README.md)包含14页工作簿和各路推进计划。整理工具为`tools/thesis_main/analysis/b8l2_mainline_status_20261016.py`，工作簿工具为同目录`b8l2_mainline_workbook_20261016.mjs`，定向测试为`tests/test_b8l2_mainline_status_20261016.py`；不修改评分实现或资格。

**2026-10-16质量新回执：** [research/quality/quality_three_routes_feedback_20261016](../research/quality/quality_three_routes_feedback_20261016/README.md)保存24例原始评论、固定几何、源分数和审查。当前安排为B8L2先用于主线、Pro并行研究整体新模型；收录实现是研究原件，未替换正式评分。

资料按主题、历史迁移、质量算法身份和结果快照查找，请从[研究资料总目录](../research/catalog/INDEX.md)进入；跨模块当前状态仍以[统一研究状态](thesis_main/四线程成果与论文主线核对_20261015.md)为准。下方日期条目保留其生成时的研究上下文，可能包含历史状态或旧路径；迁移映射可从总目录读取。

- **2026-10-16质量结构续研与本地归档：** [当前统计、算法讨论和Pro任务](../research/quality/quality_structure_handoff_20261016/README.md)、[多版本定义与未决项](../research/quality/quality_structure_handoff_20261016/ALGORITHMS_AND_DECISIONS.md)、[组合机制Pro精简原件](../research/quality/quality_combination_review_20261016/README.md)。重点区分自身正交与参考结构完整性；B8L2为可调整工作版，未改评分或推送远端。

- **2026-10-16 Downloads来源核对与回收：** [核对结果和去向](../research/catalog/local_path_audit_20261016/DOWNLOADS_RECONCILIATION.md)、[逐项恢复清单](../research/catalog/local_path_audit_20261016/DOWNLOADS_RECOVERY_MANIFEST.json)。只回收当前有用且缺少仓库副本的回执、历史证据与研究原包；原图包和重复/大型历史包留在Downloads，来源文件未删除。

- **2026-10-16当前重算统计：** [891份完整质量与关键图](../research/statistics/descriptive_statistics_rescored_20261016/README.md)、[41图506份审计与接入](../research/data/scope_quality_rescore_20261016/README.md)。新增工具 `tools/thesis_main/analysis/scope_reference_reconstruction_20261016.py`、`scope_quality_binding_20261016.py`、`scope_quality_scoring_20261016.py`、`scope_quality_rescore_20261016.py`分别负责参考、绑定、冻结评分和独立快照；对应 `tests/test_scope_reference_reconstruction_20261016.py`、`test_scope_quality_binding_20261016.py`、`test_scope_quality_scoring_20261016.py`、`test_scope_quality_rescore_20261016.py`。上一阶段807份统计保留，派生结果不成为源标注。

- **2026-10-15当前统计：** [新版报告、清单与工作簿](../research/statistics/descriptive_statistics_current_20261015/README.md)、[六组新图](../research/statistics/descriptive_statistics_current_20261015/figures/FIGURES.md)。v3、同条件至少3真人、GT／既有暂停及参考匹配已落实；manual完整Q768条／67图，semi39条／3图。206为门前候选，旧统计保留历史身份。口径见[统一第3.1节](thesis_main/四线程成果与论文主线核对_20261015.md)。

当前统计生成器为 `tools/thesis_main/analysis/descriptive_statistics_current_20261015.py`；同目录 `descriptive_pool_gate_20261015.py`、`descriptive_reference_audit_20261015.py`、`descriptive_statistics_current_report_20261015.py`、`descriptive_statistics_current_figures_20261015.py`、`descriptive_statistics_current_workbook_20261015.mjs`分别负责人数门、参考审计、报告、图与工作簿；对应 `tests/test_descriptive_pool_gate_20261015.py`、`test_descriptive_reference_audit_20261015.py`、`test_descriptive_statistics_current_20261015.py`、`test_descriptive_statistics_current_figures_20261015.py`。清单由新报告及字段合同索引，不把派生输出升格为源标注。

2026-10-15当前难度：[局部复核与GT排除](../research/difficulty/difficulty_review_update_20261015/README.md)；构建入口 `tools/thesis_main/analysis/difficulty_review_update_20261015.py`，测试 `tests/test_difficulty_review_update_20261015.py`。范围语义为整空间竖向边界，普通难度分析须使用排除错误GT后的表。

2026-10-15图片难度入口：[新增空间接入与259图](../research/difficulty/difficulty_scope_received_20261015/README.md)；导入工具 `tools/thesis_main/data_prep/floor_scope_update_20261015.py`，难度构建工具 `tools/thesis_main/analysis/difficulty_scope_received_20261015.py`，主manifest新增 `floor_scope_update` 底面增量组件。

现有数据描述统计已获后续新授权并实际执行，见[统计报告与筛选明细](../research/statistics/descriptive_statistics_20261015/README.md)。上一轮仅整理文档的历史保留；不固定论文大纲。最新状态统一见[四线程资料核对](thesis_main/四线程成果与论文主线核对_20261015.md)。

- **2026-10-15详细描述统计：** [报告、工作簿与字段合同](../research/statistics/descriptive_statistics_20261015/README.md)；生成入口 `tools/thesis_main/analysis/descriptive_statistics_20261015.py`，库存/时间、直接同房、中文报告及工作簿采用同目录 `descriptive_inventory_20261015.py`、`descriptive_same_room_20261015.py`、`descriptive_statistics_report_20261015.py`、`descriptive_statistics_workbook_20261015.mjs`；关键连接/分母测试为 `tests/test_descriptive_*_20261015.py`。复用3152库存、1145评分、931人员及836同目标集合，分层保留时间缺失与参考限制。

- **统计核验与后续接入：** [核验报告](../research/statistics/descriptive_statistics_20261015/INDEPENDENT_AUDIT.md)、[关键图及图表数据](../research/statistics/descriptive_statistics_20261015/figures/FIGURES.md)、[接入指南与manifest](../research/statistics/descriptive_statistics_20261015/EXTENSION_GUIDE.md)。对应工具 `verify_descriptive_statistics_20261015.py`、`descriptive_statistics_figures_20261015.py`、`descriptive_snapshot_inputs_20261015.py`，对应测试位于 `tests/`；新接入口实际演示输出为 `research/statistics/descriptive_statistics_extension_20261015/`，不覆盖历史统计，不把派生快照升格为原始数据真源。


- **2026-10-15模块接续报告：** [图片目标绑定](../research/difficulty/difficulty_target_integration_20261015/README.md)、[特殊条件覆盖](../research/difficulty/difficulty_special_coverage_20261015/README.md)、[人员四轴更新](../research/workers/worker_four_axis_update_20261015/README.md)、[融合质量与特殊层](../research/fusion/wall_consensus_quality_20261015/README.md)、[同房Q/T模式](../research/same_room/same_room_personnel_patterns_20261015/README.md)。前阶段[人员接入](../research/workers/worker_wq_integration_20261015/README.md)及[同房曲线](../research/same_room/same_room_quality_curves_20261015/README.md)保留接续说明。

- **2026-10-16全研究统筹核对：** [各条线进度与版本边界](thesis_main/四线程成果与论文主线核对_20261015.md)第0节连接当前891份统计、质量续研及难度/人员/融合/同房结果；旧模块实验不自动升级为新评分、新参考结论。资料目录和迁移映射见统一总目录；正式合同与参数不因资料归档改变。

- **2026-10-15 A/B质量反馈：** `research/quality/quality_ab_feedback_handoff_20261015/`保存30份原始回执、绑定合并表、前轮必要证据与Pro研究提示词；核验反馈与组合机制研究，不升级为评分合同。

- **2026-10-15跨模块收尾交接：** [现有数据收尾与模块接入](thesis_main/现有数据收尾与模块接入交接_20261015.md)，记录WQ工作版接口、两版研究、参考匹配缺口及新数据后置；此为接入前记录，最新结果以上方统一入口为准。
- **2026-10-14三模块成果：** `research/difficulty/difficulty_coarse_closeout_20261014/`、`research/workers/worker_classification_progress_20261014/`、`research/fusion/wall_consensus_population_20261014/`，对应工具位于`tools/thesis_main/analysis/`同名Python入口，后两者有同名测试。包含259图粗类消费表、24人条件画像、12图冻结人数轨迹，非正式人员分类或全库融合验证。

- **2026-10-15 Q-Profile路线复审：** [quality_profile_independent_review_20261015](../research/quality/quality_profile_independent_review_20261015/README.md)，含独立判断、普通30份候选补算与复现差异；展示映射不升级为评分合同，复现与生成页面留在analysis_results。

- **2026-10-15质量建模独立复审：** [quality_scope_independent_review_20261015](../research/quality/quality_scope_independent_review_20261015/README.md)，含数学与执行审查、两图最小当前快照、补充诊断、文献检索及后续Pro任务。研究证据入口，不升级为正式评分合同；重复原图与可再生复现不入该目录。

- **2026-10-15新增范围及质量模型交接：** [quality_scope_model_handoff_20261015](../research/quality/quality_scope_model_handoff_20261015/README.md)，含原始回执、两图范围增量、核验记录、当前对象与旧账本、Pro提示词。派生参考仅用于交接比较，未替换正式loader；可再生的恢复工作台与上传ZIP不重复归档。

- **2026-10-15 WQ粗质量核验：** [44份分阶段核验材料](../research/quality/quality_coarse_review_20261015/README.md)及[人工反馈与方向项诊断](../research/quality/quality_coarse_review_20261015/FEEDBACK_REVIEW.md)；构建工具`tools/thesis_main/analysis/quality_coarse_review_20261015.py`及配套HTML/JS，测试`tests/test_quality_coarse_review_20261015.py`。已接收44份回执，诊断不更改工作参数或授予资格；所需原图副本可重建、不重复入Git。

- **2026-10-15两份Pro联合审查：** [来源核验、组合比较、下游敏感性和粗分档](../research/quality/quality_joint_closeout_review_20261015/README.md)；工具`tools/thesis_main/analysis/quality_joint_closeout_review_20261015.py`。复用已有READY归档，保留原Pro增量与1145份联合表；不调参、不改变正式资格。

- **2026-10-14 3D IoU适用边界示例：** [6组合成控制与P01真人旁证](../research/quality/quality_iou_examples_20261014/README.md)，可旋转展示；区分均高棱柱、真实体积与参考范围，不调参。

- **2026-10-14分项得分研究审查：** [原交付归档、独立公式核验与完整比较](../research/quality/quality_component_return_review_20261014/README.md)；工具`tools/thesis_main/analysis/quality_component_return_review_20261014.py`。补齐冻结718条，不等于3152全量；正式评分、资格、原始几何不变。

- **2026-10-14质量模型收尾交接：** [当前资料与目标导向任务书](../research/quality/quality_model_closeout_20261014/README.md)。复用既有冻结输入和全量账本，接入最新人工回执；完成Pro分析后再组织批量图片核验，不自动改变评分与资格。

- **2026-10-14九组质量案例复核：** [可旋转三维与可展开分数的审核页](../research/quality/quality_candidate_review_20261014/README.md)。8卡覆盖9组、15份作答；回执独立，T20/P04仅比较高度，不调参或修改资格。

- **2026-10-14质量Pro返回审查：** [独立结论、复现回执与增量归档](../research/quality/quality_pro_return_review_20261014/README.md)；独立核验工具`tools/thesis_main/analysis/quality_pro_return_review_20261014.py`。复用READY的119个不变输入，保留108个新增交付文件；仅纳入研究候选与证据，正式评分和资格不变。

- **2026-10-14质量补充与Pro离线包：** [三维审核及交接入口](../research/quality/quality_pro_handoff_20261014/README.md)。沿用旧三维查看器并标注相机；3例回执已接收、16组备查，217门洞账本和151控制可追溯；新回执与修订见入口，唯一推荐READY包；目标导向任务书保留粗调后门洞细调，具体方法由Pro决定，尚未自动发送Pro。

- **2026-10-14质量分阶段研究工作版：** [普通粗调、门洞邻近比较与回归](../research/quality/quality_staged_calibration_20261014/README.md)；工具`tools/thesis_main/analysis/quality_staged_calibration_20261014.py`及同名测试。去尾项、整体0.8/局部0.25仅为研究决定；门洞125份可条件评分、92份暂缓，正式算法与资格不变。

- **2026-10-14研究审查与质量接手：** [四模块审查记录](thesis_main/四模块审查与不确定性论文收束记录_20261014.md)、[质量诊断及调参交接](thesis_main/topics/quality/质量两轮Pro诊断复核与调参交接_20261014.md)。研究支撑记录；普通粗调、门洞细调、普通回归顺序不变，无新算法或正式资格变更。

- **2026-10-13整体质量调参前准备：** [输入、证据、固定基线、底点控制与选择规则](../research/quality_calibration_preparation_20261013/README.md)；工具`tools/thesis_main/analysis/quality_calibration_preparation_20261013.py`及同名测试。单独使用已审严重例外，保留高度适度加重方向，不搜索参数或改正式算法。

- **2026-10-13质量研究日结与归档：** [当日汇总](../research/quality_data_closeout_20261013/DAY_SUMMARY.md)，统一串联用途账本、Pro选择性快照、人工回执与高度比较；不重复原始ZIP或大网格。

- **2026-10-13高度校准准备与小范围比较：** [设计、账本与结果](../research/quality_height_calibration_ready_20261013/README.md)；工具`tools/thesis_main/analysis/quality_height_calibration_ready_20261013.py`及同名测试。复用48份控制、补62份形态控制，只比较五组高度尺度；保留正式合同、旧数据和融合。

- **2026-10-13质量范围核查与场景用途修正：** [51融合终点/5图6高度案例及场景分步安排](../research/quality_scope_resolution_20261013/README.md)。普通先定参数，门洞逐图后小幅调整，OOS不调参；uNb-63的23份隔离，工具`quality_scope_resolution_20261013.py`及HTML模板、同名测试。

- **2026-10-13质量数据收尾：** [统一核查入口](../research/quality_data_closeout_20261013/README.md)、[高度对应](../research/quality_height_correspondence_20261013/README.md)、[人员/融合审计](../research/quality_downstream_audit_20261013/README.md)。工具`tools/thesis_main/analysis/quality_data_closeout_20261013.py`、`quality_height_correspondence_20261013.py`、`quality_downstream_audit_20261013.py`及同名测试；输出保留来源与受限原因，不更改正式合同或融合算法。

- **2026-10-13质量分歧研究：** [条件结果与解释边界](../research/quality_candidate_disagreement_20261013/README.md)；工具`tools/thesis_main/analysis/quality_candidate_disagreement_20261013.py`及同名测试。保留144份历史参考摘录与范围限制，分解冻结公式响应；不改规范评分或资格。

- **2026-10-13质量并行核对与视图接入：** [参考覆盖](../research/quality_reference_coverage_20261013/README.md)、[冻结候选及路由视图](../research/quality_current_candidate_view_20261013/README.md)、[处理后输入定义](../research/quality_processed_input_20261013/README.md)、[749份manual条件补算](../research/quality_manual_expansion_20261013/README.md)、[多参考筛选依据](../research/quality_reference_selection_20261013/README.md)。工具`tools/thesis_main/analysis/quality_reference_coverage_20261013.py`、`quality_current_candidate_view_20261013.py`、`quality_manual_expansion_20261013.py`，后两者有同名测试；用途审计v2纠正显式适用标志与条件开发授权的混淆，不更改正式资格。

- **2026-10-13质量Pro选择性归档与下一阶段：** [当前方案](thesis_main/topics/quality/质量研究推进方案_20261013.md)；[97份冻结研究文件及清单](../research/quality_pro_joint_archive_20261013/README.md)，验证`tests/test_quality_pro_joint_archive_20261013.py`。`source/`是外部研究快照，不替换正式算法；只承诺已验证的指标到分数复算。

- **2026-10-13质量全量用途审计：** [研究入口及字段约定](../research/quality_data_admission_audit_20261013/README.md)；工具`tools/thesis_main/analysis/quality_data_admission_20261013.py`及同名测试。覆盖3152份作答，区分2344份manual与旧包589份；保留排除人员的逐份严重反例，不恢复正式资格。

- **2026-10-13质量校准来源分层与J02更正：** [最新反馈及来源账本](../research/quality_joint_calibration_feedback_20261013/README.md)；工具`tools/thesis_main/analysis/quality_calibration_cohorts_20261013.py`及同名测试。manual优先，semi trap/未改预标注单列；不更改正式资格或旧搜索结果。

- **2026-10-13冻结质量候选应用：** [研究入口](../research/quality_parallel_local_20261012/README.md)；工具 `tools/thesis_main/analysis/quality_parallel_local_20261013.py`、`quality_frozen_fusion_rescore_20261013.py`，对应两个同名测试文件。原包只读、本地保留；Git登记逐份结果和资格/曝光/复算锚点，不重复归档网格或图片分包。

- **2026-10-12顶部与高度研究当前入口：** [候选决策、阶段证据与待判断问题](../research/quality_top_height_response_20261012/DECISION_STATUS.md)。统一登记响应形状、底点敏感性、顶部残差、局部形状及组合诊断；本轮定向复核/审核材料工具 `tools/thesis_main/analysis/quality_decision_check_20261012.py`，测试 `tests/test_quality_decision_check_20261012.py`。16参考复核已完成，两题二维意见已收、三维高度待续审；不以控制性质或测试通过宣称质量有效。 已完成[13候选约束/代价比较及四候选收敛](../research/quality_top_height_response_20261012/CANDIDATE_DIRECTION.md)。 工具 `tools/thesis_main/analysis/quality_candidate_matrix_20261012.py`，对应单项测试 `tests/test_quality_candidate_matrix_20261012.py`。 已核实[真实影响与L01已收回执](../research/quality_top_height_response_20261012/REAL_IMPACT.md)。 工具 `tools/thesis_main/analysis/quality_real_impact_20261012.py`，测试 `tests/test_quality_real_impact_20261012.py`；可旋转材料位于研究目录 `impact_review/`。

- **2026-10-12质量审核约束核查：** [研究报告及冻结证据](../research/quality_review_constraints_20261012/README.md)；工具 `tools/thesis_main/analysis/quality_review_constraints_20261012.py`，测试 `tests/test_quality_review_constraints_20261012.py`。只核查已有审核与候选，不改变正式算法、GT或资格。

- **2026-10-11图片难度当前版本：** [259图工作表](../analysis_results/difficulty_scope_preferred_20261011/current_259.csv)、[全部类型复审](../analysis_results/difficulty_scope_preferred_20261011/review.html)、[规则与OOS/门洞讨论](../analysis_results/difficulty_scope_preferred_20261011/REPORT.md)。144简单／30中等／38困难／5待核／42特殊。构建工具 `tools/thesis_main/analysis/difficulty_scope_preferred_20261011.py`；早版 `scope_difficulty_review_20261011.py` 与输出仅保留历史，不改正式GT/资格。

- 用户复审后[11图范围待裁定](../analysis_results/image_difficulty_full_review_20261010/user_review_20261010/scope_review.html)与[3份人员作答排序台](../analysis_results/image_difficulty_full_review_20261010/user_review_20261010/order_workbench/index.html)：三份顺序已采用主数据（有效确认1312）；GT不改，范围裁定后再审难度。

最新质量人工核验：[3张最小试审与24张候选来源对照](../analysis_results/quality_scope_human_review_20261010/README.md)。

- 质量研究最新：[正式输入与边界](thesis_main/topics/quality/质量研究正式输入与待研究问题_20261010.md)、[Pro独立研究资料](../research/quality_scope_handoff_20261010/README.md)。14份点位审核已接入正式loader；共同小范围和非正交质量方案仍待研究。

- 259图全量难度/范围复核：[分层标准与字段合同](thesis_main/topics/difficulty/图片难度全量复核与分层标准_20261010.md)、[全量报告](../analysis_results/image_difficulty_full_review_20261010/REPORT.md)、[人工粗审页](../analysis_results/image_difficulty_full_review_20261010/review.html)。259图3152份台账；25张分歧已重审（10改简单、8保留、7待核），当前115/18/24/60/42视觉建议；13张范围优先候选，旧工作表保留，待用户裁定。

更新：2026-10-09。仓库用于半自动全景布局标注与研究。当前方法版本为 `consensus_research_20260923_v1`；日期化实验结论以各自唯一报告为准。

## 当前研究入口

- [文档总索引](README_INDEX.md)：当前模型、术语、数据、难度和融合入口。
- 当前人员／图片研究：[统一研究模型](thesis_main/研究模型_人员图片与融合不确定性_20261006.md)、[术语](thesis_main/CONTEXT.md)、[数据说明](thesis_main/研究数据说明_来源预处理与用途_20261006.md)。
- 最新图片工作分类：[6点对低遮挡看图更新](../analysis_results/objective_difficulty_20261009/review_examples/SIX_PAIR_UPDATE_20261010.md)、[259图工作表](../analysis_results/objective_difficulty_20261009/review_examples/working_classification_20261010.csv)。6图改简单；特殊组继续单列；保留旧自动结构类与看图来源。
- 图片难度：[当前GT结构粗分类入口](thesis_main/topics/difficulty/图片客观难度评分_20261009.md)、[259图主表及原GT对照](../analysis_results/objective_difficulty_20261009/structure_classification/REPORT.md)、[旧d_model冻结补缺与有限比较](../analysis_results/objective_difficulty_20261009/d_model_expansion/REPORT.md)。新增`tools/thesis_main/analysis/difficulty_{structure,dmodel}_20261009.py`及对应测试／字段合同；OOS、门洞与可标性独立。历史工具`difficulty_{features,score,strata,model_probe,bilayout_probe,model_comparison,dino}_20261009.py`及其结果保留，12图事实核查为可选补充；Bi同源结果在`bilayout_probe/research_source/`。
- 图片难度审图：[21图原图与GT点位图集](../analysis_results/objective_difficulty_20261009/review_examples/index.html)、[样例名单、旧评分口径及场景交叉表](../analysis_results/objective_difficulty_20261009/review_examples/README.md)。特殊场景单列；一致／不一致／未评分目的性示例，不作为盲法验证，不改主分类。 最新[评分复核与使用解释](../analysis_results/objective_difficulty_20261009/review_examples/SCORE_RECHECK.md)：门洞／OOS独立评分待定，x8-01参考待核。
- 图片难度外部审查：[自包含讨论汇总与Pro任务](thesis_main/topics/difficulty/图片难度研究汇总与Pro深度研究任务_20261009.md)，补充旧HoHoNet特征／风险定义与方法取舍，属于支撑材料，不新增算法或协议。
- 墙线融合：[方法](thesis_main/topics/fusion/共识投票机制与三路线推进_20261007.md)、[操作 SOP](thesis_main/topics/fusion/融合共识操作SOP_20261008.md)、[当前交付](../analysis_results/consensus_delivery_20261008/REPORT.md)。
- GT结构条件：[环序与自遮挡审计](../analysis_results/gt_order_visibility_20261009/REPORT.md)；工具`tools/thesis_main/analysis/gt_order_visibility_20261009.py`，测试`tests/test_gt_order_visibility_20261009.py`。原／修订GT及循环接缝分开，不将几何条件当作已识别的人类难度或噪声量。
- [机器可读方法合同](thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json)是规范真源；Markdown 由合同生成。历史 v23 消费者仍固定读取其原版本合同。

## 目录地图

| 路径 | 职责 |
|---|---|
| `tools/thesis_main/` | 主研究线分析、registry、freeze、风险规则和数据准备 |
| `tools/paper_a_manhattan/` | Paper A Manhattan、sandbox、expert review 与 audit-only 工具 |
| `tools/paper_b/` | Paper B 训练、审计、cue、bilayout 与 B0/B1/B2 工具 |
| `tools/label_studio/` | 共享 Label Studio 配置、viewer、server、upload 与 import helper |
| `docs/thesis_main/` | 主研究线模型、方法、SOP、数据说明与状态 |
| `docs/paper_a_manhattan/`、`docs/paper_b/` | 对应论文支线资料 |
| `docs/label_studio/`、`docs/agent/`、`docs/shared/` | 运营、agent 规则与共享写作材料 |
| `docs/legacy/` | 历史文档；默认只追溯，不迁移或更新 |
| `import_json/`、`export_label/`、`active_logs/` | planned import、运行时标注和原始 active-time 真源 |
| `analysis_results/` | 派生结果、审计、manifest 与图表，不作为输入真源 |
| `research/` | 外部材料、独立复算和研究交接包，须按来源状态解释 |
| `tests/` | 工具、字段合同及边界测试 |
| `data/`、`output/` | 数据资产与模型推理／中间结果 |

## 真源和读取边界

- 后续分析从 `analysis_results/research_input_20260929/manifest.json` 和 `load_current_bundle()` 读取统一包；包名日期不代表补充审核都已写入。
- 不由分析结果反写 `export_label/`、`import_json/`、`active_logs/` 或原始标注；历史审核、输入坐标与来源映射保持可追溯。
- 当前合同、round-based SOP 和统计分析计划分别承担规范、执行与分析职责，不重复定义 eligibility 或字段语义。
- `tools/label_studio/create_labelstudio_split_by_outline.py` 的旧配额逻辑不得覆盖冻结协议或导入工件。
- `/tools/vis_3d.html` 是部署兼容路由，不代表仓库源码位于 `tools/` 根目录。

## 写入位置

- 新 Python 脚本按职责放进 `tools/thesis_main/analysis|registry|data_prep/`、`tools/paper_a_manhattan/`、`tools/paper_b/` 或 `tools/label_studio/`，不写入 `tools/` 根目录。
- 新主题文档放入对应 `docs/` 分类；根目录只保留 `README_INDEX.md` 与本项目地图。
- 新增、删除或移动文件后检查本页与文档总索引。协议、统计计划或 Label Studio 运营语义改动须按对应 playbook 核对。
- 不移动或修改 `export_label/`；未经授权不改变 protocol、schema、routing 或 SOP 语义。

## 历史文档

- [历史文档目录](thesis_main/history/README.md)区分已归档原文、旧版导航与仍因兼容而留在原路径的快照。
- [整理前的项目地图](thesis_main/history/项目地图历史快照_20261009.md)保留逐阶段结果和旧路径索引。
- 更早的研究清理包见 `analysis_results/repo_cleanup/`；外部材料按各归档下的 `README`、`MANIFEST` 或 `field_contract` 追溯。

## Agent 规则

参见 [Agent 上下文](agent/AGENT_CONTEXT_INDEX.md)、[文档同步](agent/playbooks/docs_sync.md)、[代码验证](agent/playbooks/code_change_verification.md)。协议和统计变更另读 `protocol_guard.md` 与 `statistical_plan_guard.md`；Label Studio 运营先读 CE-only SOP。

## 109条独立点复核工作台（2026-10-09）

- `tools/thesis_main/analysis/build_point_edit_review_20261009.py` 与 `serve_point_edit_review_20261009.py`：构建109队列并在本机提供绿色全景工作台；`point_edit_review_20261009*` 为伴随编辑器。
- [输出、操作与验证](../analysis_results/point_edit_review_20261009/README.md)位于 `analysis_results/point_edit_review_20261009/`；收到的对照包保留在 `research/point_review_109_received_20261009/`。
- `tests/test_point_edit_review_20261009.py`、`test_point_edit_review_20261009.cjs`、`point_edit_review_browser_20261009.cjs` 覆盖来源身份、编辑补丁和实际浏览器往返。审核返回不写正式数据或恢复资格。
- `tests/point_edit_review_ux_20261009.cjs` 验证绿色工作台鼠标操作、旧草稿保留与最近记录恢复；不操作用户日常浏览器缓存。
- `point_edit_review_20261009_sort.js` 适配旧完整点对拖动代码；`tests/test_point_sort_review_20261009.cjs`、`point_sort_review_browser_20261009.cjs` 与 `point_sort_visible_20261010.cjs` 验证周期x候选点对、排序留痕、卡片可见与实际拖动。
- `research/point_review_109_received_20261009/109份复核重筛清单_20261010.csv` 是重筛来源，`queue_resolution_20261010.json` 记录既有单条排除与OOS无法计算不重复召回；[范围与返回说明](thesis_main/109份点编辑审核范围与返回核对_20261010.md)及 `analysis_results/point_edit_review_20261009/109份审核范围与返回核对_20261010.csv`逐条说明109→14份／8图。该输出目录的`received_return_audit_20261010.json`保存18条返回与旧排序的核对，原件存`evidence/`；`tests/point_review_rescreen_browser_20261010.cjs`验证默认队列、全量查看和旧草稿保留。

- 2026-10-15整理：[入口阶段更新归档](thesis_main/history/入口阶段更新归档_20261015.md)、[旧共识推进方案](thesis_main/history/研究推进方案_共识可靠性与Pro深研_20261004.md)仅供追溯；现行执行见[融合SOP](thesis_main/topics/fusion/融合共识操作SOP_20261008.md)。

### 2026-10-15模块接续代码定位

上述接续报告对应 `tools/thesis_main/analysis/` 下同名日期脚本及 `tests/test_同名日期.py`：difficulty_target_integration、difficulty_special_coverage、worker_wq_integration、worker_four_axis_update、same_room_quality_curves、same_room_personnel_patterns、wall_consensus_quality。融合特殊层另有 `wall_consensus_special_20261015.py`，由融合质量相关测试覆盖。此处仅补齐已有文件导航，本次没有修改或运行这些程序。

- 2026-10-16融合文档整理：[旧回执操作与模型阶段统计](thesis_main/history/融合SOP与模型过时说明_20261016.md)归档；SOP保留现行操作，模型不重复维护版本分母。

- 2026-10-17融合：[18图B8L2／D10对照与新增批次桥接](../research/fusion/wall_consensus_d10_20261017/README.md)。复用真实人数过程，不重跑融合；工具与字段见包内说明。
