本轮追加：[Pro质心与区域文献调研纯文字提示词](thesis_main/PRO_CENTROID_LITERATURE_PROMPT_20260923.md)，不提供ZIP。


本轮入口：[执行与交付说明](../analysis_results/consensus_research_20260923/README.md)、[Pro任务书](thesis_main/PRO_CONSENSUS_RESEARCH_TASK_20260923.md)、[保留的v23合同](thesis_main/PAPER_A_METHOD_CONTRACT_20260811_v23.json)。新数值工具：`tools/thesis_main/analysis/{consensus_region,build_consensus_handoff,summarize_consensus_pilot}_20260923.py`；对应检查位于`tests/test_consensus_*20260923.py`。
**当前人工清查页：**[多通道审核入口](../analysis_results/consensus_visual_review_20260923/index.html)，由`build_consensus_visual_review_20260923.py`构建；角点数量、3D诊断、顺序、单人/小簇独立召回，IoU仅辅助。字段和边界见同目录README，测试`test_consensus_visual_review_20260923.py`。
<!-- CURRENT_RESEARCH: consensus_research_20260923_v1 -->
当前研究规范：`docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`；2026-09-23的区域共识、人员组合、难度与同房预测使用新版研究SOP。下列旧Calibration/T1/V1材料仅解释历史流程，其机器合同已绑定 `PAPER_A_METHOD_CONTRACT_20260811_v23.json`。

<!-- PAPER_A_MACHINE_STATUS: normative -->

**导师新方向独立研究（2026-09-22，探索）：**[独立判断与GT敏感性](../analysis_results/supervisor_independent_20260922/独立研究判断.md)、[复算及字段](../analysis_results/supervisor_independent_20260922/README.md)。分开二维墙带/地面表示、原始MP3D/人工修订GT，含固定人员聚合曲线、人员排序和模型难度诊断；不要求二维研究先恢复三维顺序，不修改正式方法。

**任务8准备文件（2026-09-22）：**[中文9人首批10图导入与分发表](../import_json/cn_first10_20260922/使用说明.md)，19张导入图、90份分配；9姓名sheet沿用任务7格式，尚待线上导入和运行时绑定。

**中文9人首批10图（2026-09-22）：**[具体安排与缺口](../analysis_results/cn_first10_20260922/分配说明.md)、[逐人原图预览](../analysis_results/cn_first10_20260922/分配预览.html)。90份包含74份旧图补标、16份新图，使用最新终审人数与接触排除；候选未派发。

**共享x四条件复算（2026-09-22）：**[完整结果与原因诊断](../analysis_results/shared_x_reanalysis_20260922/README.md)比较原始／共享x×完整链接／全局亲近度，同房预测、人数稳定及强主簇／少量尾部单列；[通俗讲稿](thesis_main/导师汇报简明讲稿_20260922.md)和[详细问答](thesis_main/导师汇报讲解与问答_20260922.md)已同步。新入口`tools/thesis_main/analysis/shared_x_reanalysis_20260922.py`，检查`tests/test_shared_x_reanalysis_20260922.py`；展示适配`research_dashboard/shared_x.py`保留独立版本，不改原始点或正式方法。

**导师口头讲稿：**[完整通俗版](thesis_main/导师汇报简明讲稿_20260922.md)保留ABC、瓶颈、全资产、分簇、各种人员分类与子类稳定、配比和删人、同房／同场景、难度及后续采集，逐项用口头语言解释；[详细问答](thesis_main/导师汇报讲解与问答_20260922.md)补计算及版本边界。[展示完整性复核](../analysis_results/presentation_inventory_20260922/展示完整性复核_20260922.md)登记已发现遗漏和数值依据。

**导师汇报准备（2026-09-22）：**[真实数据展示](../analysis_results/research_dashboard_20260922/index.html)、[离线包](../analysis_results/research_dashboard_20260922.zip)与[讲解及问答](thesis_main/导师汇报讲解与问答_20260922.md)分开交付。后者单列导师“迭代瓶颈/质量上限”与当前人数重放、分布稳定的对应边界；[全资产盘点](../analysis_results/presentation_inventory_20260922/README.md)纳入Manual/OOS/Semi、GT、HoHoNet/Bi/uLayout/DINOv3/DA3。展示接口见[说明](thesis_main/OFFLINE_RESEARCH_DASHBOARD.md)。

**新分簇同房预测对照（2026-09-22）：**[固定人员、阈值和同房面板的复算](../analysis_results/room_partition_comparison_20260922/README.md)。全局亲近度分区未改善预测MAE，覆盖指标仍有同房信息，成对分歧完全不变；保持探索，不替换默认方法。

**分簇核验Pro返回（2026-09-22）：**[原件、全阶段独立复算与采用意见](../analysis_results/cluster_validation_received_20260922/README.md)，补查单人簇下界、新候选共享x敏感性及重放抽样误差；保持探索身份，不替换现行方法。

**Pro分簇核验新交接（2026-09-22）：**[资料与隔离复算](thesis_main/Pro云端资料入口_分簇核验_20260922.md)、[可复制提示词](thesis_main/Pro提示词_分簇核验与不确定性_20260922.md)。保留人工判断可误差、阈值待研究、GT／模型仅辅助的最新边界。

**24图审核接收（2026-09-22）：**[用户原件、未决项及GT/阈值/x对齐分析](../analysis_results/cluster_screen_reviewed_20260922/README.md)，保留9同簇／12分开／3未决；未自动改点或合簇。

**分簇工作版人工筛查：**[24图离线审核](../analysis_results/cluster_screen_20260921/README.md)，沿用结构增减应分簇规则，核对定位与整簇问题；导出独立审核JSON，不覆盖既有裁决。

**人员移除与分簇敏感性（探索）：**[全员逐人对照、联合移除、阈值扫描与视觉核验](../analysis_results/worker_cluster_sensitivity_20260921/README.md)。保留全员基线，分开报告人员影响、几何孤立及分区造成的单人簇；不据改善收敛修改资格或冻结阈值。

**人员移除与分簇敏感性（探索）：**[全员逐人对照、联合移除、阈值扫描与视觉核验](../analysis_results/worker_cluster_sensitivity_20260921/README.md)。保留全员基线，分开报告人员影响、几何孤立及分区造成的单人簇；不据改善收敛修改资格或冻结阈值。

**Pro最新研究返回复核：**[原件、本地复算与独立审查](../analysis_results/panorama_research_received_20260921/README.md)。纳入探索证据，另存人员配比模型外层隔离修正；人工候选并列排序问题与数值复现差异显式保留，不替换正式方法或采集计划。

**新Pro开放研究入口：**[资料、分支与复算](thesis_main/Pro云端资料入口_20260921.md)、[可复制提示词](thesis_main/Pro提示词_人员构成与顺序重放_20260921.md)。最新终审数据与必要历史证据独立打包，研究执行顺序和方法保持开放。

**新增数据终审汇总：**[当前汇总](../analysis_results/new_manual_reviewed_20260921/汇总说明.md)已落实全批独立作答确认、两份补点、7272版本及三份上下对应；新增纳入636份，不借用补点预测视图240图2444份。旧父关联待定事项关闭，旧研究报告保留历史身份。 W006补交原分配的uNb-66／67／87已接入，原480份必做均已有非空提交并纳入；7502替代7111，不重复计票。

**离线研究仪表盘（结构版）：**[使用与展示接口](thesis_main/OFFLINE_RESEARCH_DASHBOARD.md)。`tools/thesis_main/analysis/research_dashboard/`按明确清单打包六模块离线网页，复用 Studio 与本机 Plotly；首版为空数据，不接入暂定结论，不修改研究方法。交付位于 `analysis_results/research_dashboard_structure_20260921/`，同名 ZIP 可独立发送。

**2026-09-21研究讨论交接：**[交接与必读资料](thesis_main/研究讨论线程交接_20260921.md)、[可复制Pro提示词](thesis_main/Pro提示词_人员构成与顺序重放_20260921.md)。按人独立采集，研究全部可用人员的类别／配比／成员／顺序重放；AABC非固定目标。保留top y／bottom y的3D职能研究；可视化与导师汇报等待用户通知。

**2026-09-21研究讨论交接：**[交接与必读资料](thesis_main/研究讨论线程交接_20260921.md)、[可复制Pro提示词](thesis_main/Pro提示词_人员构成与顺序重放_20260921.md)。按人独立采集，研究全部可用人员的类别／配比／成员／顺序重放；AABC非固定目标。保留top y／bottom y的3D职能研究；可视化与导师汇报等待用户通知。

**同房收敛人数与人员组合澄清：**[2026-09-21报告](../analysis_results/new_manual_analysis_20260921/convergence_and_composition/报告.md)穷举同房历史／预测图拆分，报告起点删失及六组未冻结上限；真实AABC覆盖与具体子类持续稳定分别检查。早先U(k)分析不能替代收敛人数预测。

**2026-09-21同房／同场景／人员综合：**[详细汇报](../analysis_results/new_manual_analysis_20260921/详细汇报.md)与[新增数据审核](../analysis_results/new_manual_analysis_20260921/审核/index.html)。用途粗类跨建筑均值预测未优于总体基线；同房支持为探索线索；人员旧留建筑名单接回新几何，未冻结最终类型。

**2026-09-21同房／同场景／人员综合：**[详细汇报](../analysis_results/new_manual_analysis_20260921/详细汇报.md)与[新增数据审核](../analysis_results/new_manual_analysis_20260921/审核/index.html)。用途粗类跨建筑均值预测未优于总体基线；同房支持为探索线索；人员旧留建筑名单接回新几何，未冻结最终类型。

**2026-09-21新增数据复算：**[分簇／同房预测探索报告](../analysis_results/new_manual_analysis_20260921/复算报告.md)。649条新导出包含分配外作答，父记录独立性另做敏感性；八组审核原文归档，G180条件暂缓，G234/G235视觉上倾向不同房间。未冻结停止规则。

**2026-09-21新增数据复算：**[分簇／同房预测探索报告](../analysis_results/new_manual_analysis_20260921/复算报告.md)。649条新导出包含分配外作答，父记录独立性另做敏感性；八组审核原文归档，G180条件暂缓，G234/G235视觉上倾向不同房间。未冻结停止规则。

**2026-09-21最新采集讨论：**[英文3—6人、人员分类与两批备选](../analysis_results/collection_plan_20260921_v4/英文人数分档与两批备选_初步测算.md)。旧图提前补12、新图首轮15、原6图仍20，首批新人15张；三批主方案另有两批备选，最新逐人名单待重排。[原v4](../analysis_results/collection_plan_20260921_v4/说明.md)保留历史，不再将其1052份及十月206份当作最新承诺。

**2026-09-21新增候选审核：**[八组39图采用审核](../analysis_results/collection_review_20260921/index.html)，复用 Panorama Studio 样式，按用途待定优先；既有原文只读，本轮决定默认留空，支持逐图例外和JSON备份。覆盖核算见[独立审查](../analysis_results/collection_plan_20260921_audit/审查与待审核事项.md)，不自动派发。

**分簇工作版与一致性入口：**[统一数据入口](thesis_main/分簇工作版_统一数据入口_20260920.md)及[本地审核与云端数值包](../analysis_results/clustering_release_local_20260920/README.md)。已确认奇数点补删按有效点集计算；正式合同不变，人工验收待完成。


**最新局部点位数值返回：**[接收、审查与复算入口](../analysis_results/clustering_numeric_received_20260920/README.md)、[本地验收](../analysis_results/clustering_numeric_local_20260920/README.md)。[原云端任务](thesis_main/Pro新对话_局部点位分簇与影响核查_20260920.md)及[独立审核页](../analysis_results/local_point_clustering_20260920/README.md)保留；方法和容差未冻结，方法确定后逐图验收全部214张历史图片（239条件单元）。

**历史全量视觉验证范围：**[214图筛查队列与新增8图初核](../analysis_results/paired_split_research_received_20260920/history_visual_review/README.md)。不再局限39图；8图已查看指定作答对，余下保留状态与优先级，用户裁决空白。

**2026-09-20 Pro返回已核验：**[按x绑定/分开研究的独立审查](../analysis_results/paired_split_research_received_20260920/独立审查与研究方向.md)、[数据与复算入口](../analysis_results/paired_split_research_received_20260920/README.md)。25表复现一致，独立核验237416条端点距离；保留对应歧义与中点并列边界，尚未冻结最终分簇或人员判断。

**2026-09-20 Pro续研：**[按序局部比较、分区与人员诊断任务](../analysis_results/local_point_research_received_20260919/pro_followup_20260920/README.md)，6张补充视觉证据、独立专项复核页及云端数值资料；两个子代理独立复核，新增裁决留空。

**当前研究入口：**[真人标注不确定性研究：当前状态](thesis_main/真人标注不确定性研究_当前状态.md)。两份旧线程交接已移入`docs/thesis_main/archive_20260918/`，仅作历史追溯。
**2026-09-18两轮研究接收：**[仓库接收与当前视觉复核](../analysis_results/full_corpus_research_received_20260918/仓库接收与视觉复核.md)串联全量报告、239单元图册、复算输入和前序39图研究；本轮复看39原图、29组作答对与B6-22全部24份Semi，未冻结新算法或应用待确认修正。

**2026-09-19局部点研究复核：**[数值接收与本地执行](../analysis_results/local_point_research_received_20260919/README.md)，包括前轮配对/时间诊断、局部比较、有限池事件含义和跨环境差异；不冻结分簇或停止规则。

**六图点对审核已完成：**[用户原件、结论与按x顺序澄清](../analysis_results/local_point_research_received_20260919/pair_pilot/README.md)；自由匹配初验不等于按序方案验证，不改历史分区。[探索SOP](thesis_main/相似场景标注稳定性分析SOP.md)补充单人支持讨论及审核流程；以后复用示范基础制作专用页。

**2026-09-19补充视觉复核：**[39图之外12图审核](../analysis_results/cluster_review_extra_20260919/README.md)，24组点集对照、局部方法核对及待用户裁决页面；发现配对伪差异，未修改冻结结果。

**最新研究定位：**OOS、漏标、多标、定位偏差均有研究价值；规范偏好不作为排除指令。用户26项新回答（4项暂缓）已原文归档，点数分簇允许讨论。见[开放式Pro研究入口](../analysis_results/pro_cluster_review_20260918/README.md)。


**39图裁决已准备：**[逐图视觉报告与审核入口](../analysis_results/human_review_reconciliation_20260918/39图视觉复核与裁决说明.md)。39张原图已实际核查，26项问题由用户裁决，8份旧奇数点单列；两项新版导出更正仅待应用，历史分簇和收敛结果冻结。


**候选整理状态：**用户确认原480份进度尚未核实，先整理候选；77张旧候选已给出逐图处理，新增量未定。[查看清单](../analysis_results/human_review_reconciliation_20260918/问题1与3_处理结论.md)。

**本次接续：**[原疑问1与3的处理结论](../analysis_results/human_review_reconciliation_20260918/问题1与3_处理结论.md)与[Pro分簇数据入口](../analysis_results/pro_cluster_review_20260918/README.md)已准备。39图843份作答原始核对、45个分区复现通过；本界面实际为d_mask完整链接0.10，旧0.95不直接适用。

**2026-09-18更新：**[39图双方文字对照与选图处理](../analysis_results/human_review_reconciliation_20260918/审核对照与选图处理说明.md)已记录。11图旧选项不构成最终决定，全部按文字及新增必要性重审；撤回22张高人数图统一追加15人的默认建议，922份保留为待重排的历史候选快照。用户39条文字均为实质审核意见；后续两轮分簇研究已接收，当前结果见顶部入口。

11图[既有审查界面](../analysis_results/full_history_coverage_20260916/11图采集采用审核.html)保留供查阅；其历史“采用”选项不自动更改分配。

**当前入口（2026-09-16，main）：[研究主线与采集交接](thesis_main/真人标注不确定性研究_当前状态.md)。**独立真人采集、人员组合及不确定性／收敛为主线；更多人手尚未确认，不扩大既有922份候选。假说研究暂停，完整实验保留在`codex/image-portrait-20260914`与`codex/simulated-annotators`。

9月16日候选快照（现待重排）：[覆盖执行说明](../analysis_results/full_history_coverage_20260916/执行说明.md)、[人员×图片工作簿](../analysis_results/full_history_coverage_20260916/图片名单与人员覆盖.xlsx)、[独立复核](thesis_main/全历史覆盖方案独立复核_20260916.md)。11图待复核涉及首批165份，新人身份为空，未派发；原480份进度须按最新导出另核对。

支撑资料：[人员预算](../analysis_results/worker_sample_budget_20260916/人员样本量与耗时建议.md)、[池外库存](../analysis_results/unassigned_room_inventory_20260915/盘点说明.md)、[较早英文追加候选](../analysis_results/english_followup_pool_20260915/追加候选说明.md)。较早候选不自动成为本轮新增英文任务。[39图审核入口](../analysis_results/image_portrait_20260914_v1/review_workflow_20260915/key39/README.md)保留回查；用户39条文字意见与一正意见已完成对照整理；[历史研究导航](../analysis_results/image_portrait_20260914_v1/PRO_START_HERE.md)用于查阅，不作为续跑指令。

## 以下保留既有阶段索引，旧计划状态须据最新交接核对

当前研究交接：[2026-09-13现状与阅读顺序](thesis_main/真人标注不确定性研究_当前状态.md)。全量历史196图1843份、55张高人数图；不能用本轮102张采用池替代历史总量。正文要求与执行说明已同步纠正。

第一阶段最新交付：[整房优先说明](../analysis_results/stage1_person_image_packages_20260913_v2/整房优先版交付说明.md)、[完成后可分析覆盖](../analysis_results/stage1_person_image_packages_20260913_v2/完成后可分析覆盖.md)。任务7、Project G、Project H的JSON独立存放；H已定稿20图。不提供ZIP，旧分发表及门洞空白复核页已清理。

第一阶段当前执行：[三项目安排与人员分类续研](thesis_main/第一阶段执行与人员分类续研说明_20260913.md)、[v2清单与工作簿](../analysis_results/stage1_person_image_packages_20260913_v2/第一阶段分配建议说明.md)。480份已按整房优先重新分配；H已定12门洞＋8同房。单项、联合及AABC人员组合研究继续保留，未导入或派发。

外部两阶段提案独立审查：[判断与差异](../analysis_results/two_stage_independent_review_20260913_v1/独立审查意见.md)。复核480行匹配、原始记录、逐组覆盖及转录差异；未采用外部方案或修改现行SOP。

探索研究要求核对：[长对话要求清单](thesis_main/用户研究要求核对清单_20260913.md)，逐项区分已记录要求、本次补齐、历史参数及未定事项；不代表对应实验均已完成。

2026-09-13空间分维度续审：[填写入口](../analysis_results/spatial_dimensions_review_20260913_v2/空间关系续审.html)、[人工历轮与OOS核对](../analysis_results/spatial_dimensions_review_20260913_v2/续审说明.md)。功能／主空间／逐对分隔关系分开，六阶段人工记录与OOS作用范围接续，旧“开放复合”仅作历史字段。

2026-09-13开放布局探索复核：[逐图查看](../analysis_results/open_layout_recheck_20260913_v1/开放复合空间复核查看.html)、[说明及待核实清单](../analysis_results/open_layout_recheck_20260913_v1/复核说明.md)。全648图与已选98图分开计数，原人工主区域、评论与新AI建议并列；改类意见需人工核实，不覆盖既有分类。

2026-09-13开放布局探索复核：[逐图查看](../analysis_results/open_layout_recheck_20260913_v1/开放复合空间复核查看.html)、[说明及待核实清单](../analysis_results/open_layout_recheck_20260913_v1/复核说明.md)。全648图与已选98图分开计数，原人工主区域、评论与新AI建议并列；改类意见需人工核实，不覆盖既有分类。

2026-09-13门洞记录：[人工确认整理](../analysis_results/scene_image_exploration_20260910_v1/门洞人工确认整理_20260913.md)、[人工与AI完整台账](../analysis_results/scene_image_exploration_20260910_v1/门洞人工与AI历轮核对_20260913.json)，接续早期全量分类、历轮修正及最新交界评论，非新增视觉裁决。

2026-09-13实际选用（接续两条人工确认）：[新版机器表](../analysis_results/candidate_selection_review_20260913_v2/选用复核机器表.json)、[样本量](../analysis_results/candidate_selection_review_20260913_v2/样本量与复算报告.md)、[收敛与门洞解释](../analysis_results/candidate_selection_review_20260913_v2/设计分析.md)。工具：`tools/thesis_main/analysis/summarize_candidate_decisions_20260913.py`；原话、确认、生效值分存；102图、按主要空间统计、OOS过滤后34张门洞补充候选，实际8人有效共识可判收敛；仅本轮探索设计，不派发。

<!-- PAPER_A_METHOD_CONTRACT_CURRENT.json paper_a_method_20260811_v23 SHA-256 f3c1ea58d0857a40aa2240b4680b674c76fe2cec8f048f61a643d9e4b74b0588 -->
# docs 文档索引

当前完整研究方向：[研究主线与房间／场景选图方案](thesis_main/研究主线与房间场景选图方案_20260912.md)。人数过程、同房预测、相似场景标注与跨房间预测、人员子类与组合；batch指房间／实际场景研究组，采用价值不指批次。候选页v5只填逐图采用与采集安排，全部完成计划标注后离线划分图片、重排人员验证预测，预期难度为简单／中等／困难，门洞覆盖缺口单列。

2026-09-12外部候选包整合：[独立审查与使用说明](../analysis_results/candidate_review_20260912_v2/README_整合审查.md)、[本地候选审查台](../analysis_results/candidate_review_20260912_v2/候选图片审查台.html)。22组112图，人数与预算默认未定；15人及380份仅为外部情景，非最终选图或派发。已回查2501份历史记录。

2026-09-12图片研究目的：[图片分类与同房间收敛预测研究SOP v7](thesis_main/图片分类与同房间收敛预测研究SOP.md)。早期648图分类及争议复核完整接续，41张仅指后续意见不一致图那一轮；本次260个同房组均已看。最新[说明](../analysis_results/research_direction_review_20260912_v1/人员范围与多视点选图_修订建议.md)及[稳定性SOP](thesis_main/相似场景标注稳定性分析SOP.md)明确：W11退出后续但历史保留，多视点优先、困难图保留、按实际人数观察，无统一追加5人要求；讨论版，不修改正式合同。

2026-09-12完整复核结果：[机器关联表v2](../analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json)、[字段说明](../analysis_results/scene_image_exploration_20260910_v1/同房研究配对复核要求_20260912.md)、[55条评论解释](../analysis_results/scene_image_exploration_20260910_v1/group_comment_interpretation_20260912.json)。关联648图历轮分类、47条早期评论、原组/子集、门洞与一般交界、单图问题及Manual/Semi历史人数；采用值和未亲审AI建议分开，旧v1仅供追溯；生成器`materialize_same_room_selection.py`。

2026-09-12同房研究重新配对：[整组填写页](../analysis_results/scene_image_exploration_20260910_v1/同房研究_整组复核_v3.html)。全量图像检索后，逐对记录物理房间、主空间、预计标注范围及信息差异；AI建议预填，含小幅歧义选项，人工交界只读保留；生成器 `build_same_room_pair_review.py`。

2026-09-11新标准全量复核：[独立可填写页面](../analysis_results/scene_image_exploration_20260910_v1/室内空间_新标准复核_v3.html)、[复核报告与填写说明](../analysis_results/scene_image_exploration_20260910_v1/新标准全量复核报告_20260911.md)。648图主审/讨论沿用及独立交叉意见分层保留，最终由用户分类；生成器 `build_scene_open_layout_review.py`。 [本地文件/Git说明](../analysis_results/scene_image_exploration_20260910_v1/本地文件与Git保存说明_20260911.md)。

2026-09-11争议批量复核：[B01—B15最新反馈整理](../analysis_results/scene_image_exploration_20260910_v1/批量反馈整理_20260911.md)。含四个低优先级交界候选及B06／B08不同房更正；[原可填写批量页](../analysis_results/scene_image_exploration_20260910_v1/争议图批量快速复核.html)与[此前AI建议](../analysis_results/scene_image_exploration_20260910_v1/争议图批量复核说明.md)保留为历史，用户源未覆盖。

2026-09-10人员探索续算：[具体子类的名单复现与稳定阶段更新报告](../analysis_results/worker_four_block_exploration_20260910_v1/subtype_stage_validation/README_ZH.md)。按[探索SOP第9节](thesis_main/相似场景标注稳定性分析SOP.md#9-人员分类与独立结果复用)执行，不强行均分；具名子类与组号审计分开，含Word、真实回放和同图同人数对照；尚无新人确认。

2026-09-10组数纠正：[不限定两组的补充探索](../analysis_results/worker_four_block_exploration_20260910_v1/group_count_extension/README_ZH.md)。15种指标组合同时变化组数；保留单人小组、名单重复性与收敛人数检查。原二分报告不能代替多组方案评价。

2026-09-10人员分类补充：[指标组合、各组人数与名单修订报告](../analysis_results/worker_four_block_exploration_20260910_v1/report_revision_v2/README_ZH.md)；[原实验数据说明](../analysis_results/worker_four_block_exploration_20260910_v1/README_ZH.md)。比较15种组合与质量粗分基线，分别检查全部人员和后续20人；仅为探索结果，不修改正式分类规则。

当前研究先读[研究交接](thesis_main/研究交接_20260909.md)，文件定位用[仓库地图顶部速查](PROJECT_MAP_CLEAN_20260308.md#当前研究速查2026-09-09)，旧结果见[历史归档](../analysis_results/research_history_archive_20260909_v1/README_ZH.md)。

本次研究验证见[全楼持续阶段、人员组合与图像特征报告](../analysis_results/research_validation_20260909_v2/研究验证报告.md)及[客观Word报告](../analysis_results/research_validation_20260909_v2/相似场景标注稳定阶段与人员组合_客观数据报告.docx)。已按[相似场景SOP](thesis_main/相似场景标注稳定性分析SOP.md)检验55张高人数图、10楼50图留图和98张低人数图的前瞻预测；人员组合采用reviewed无辅助作答与楼外分档，原始标注和正式合同未改。

2026-09-10补充：[uNb真实标注对照表](../analysis_results/research_validation_20260909_v2/annotation_review/uNb标注对照表.html)，12张高人数图、296份无辅助记录；默认按q=.95现有簇彩色叠加，支持单人突出与候选分区切换，单人组及q不可计算作答单列；保留候选房间/标法分组填写与导出。

2026-09-10原图初分：[648图房间/场景核对页](../analysis_results/scene_image_exploration_20260910_v1/图片初分核对.html)、[探索说明](../analysis_results/scene_image_exploration_20260910_v1/探索说明.md)及[用户分类后的争议图片复核](../analysis_results/scene_image_exploration_20260910_v1/争议图片复核.html)。仅AI目视候选，房间身份、图像类型与门洞内拍摄属性分开；最终分类由用户决定，尚未检验这些类别的预测效果。


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
- `tools/label_studio/label_studio_uncertainty_meta_manifest_v2.json`：不确定性元标签 v2 的本地待部署入口；使用原生 XML 必填/条件分支，Userscript 只补困难原因互斥，不改变 active time、分发或三臂样本量。
- `tools/label_studio/label_studio_uncertainty_meta_manifest_v1.json`：Project 86 开发测试 v1 的冻结清单，配置由 Git 修订 `e1038a9` 保留；非正式合同，既有响应不追溯重编码。更早基线仍位于 `tools/label_studio/config_history/uncertainty_meta_v1_prechange_20260824/`。
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

- [ANNOTATION_UNCERTAINTY_CURRENT_STATUS_HANDOFF_20260830.md](thesis_main/ANNOTATION_UNCERTAINTY_CURRENT_STATUS_HANDOFF_20260830.md)：当前标注不确定性研究的非规范交接入口；汇总42图历史复算、后续多人多轮候选实验、沟通歧义和 analysis_results 的 current/supporting/superseded 状态，不授权实验启动。
- 历史多人标注复算：`tools/thesis_main/analysis/materialize_historical_uncertainty_k_curves_20260829.py`；结果 `analysis_results/historical_uncertainty_recompute_20260829_v1/`。当前讨论交付为42图/1,055条规范标注，包含无reference恢复、reference-relative质量、整体分歧、少数结构和阈值敏感性；属于历史有限roster审计，不声称普适质量上限。
- Worker 行为分层与混合重放：`tools/thesis_main/analysis/analyze_worker_behavior_mixture_exploratory.py`；结果 `analysis_results/worker_behavior_mixture_exploratory_20260904_v1/`。仅以 P1 proposal-response 定义 `U=0.95` 下的操作性候选子群，并在零重叠 Manual 图片上精确重组；属于探索性 replay，不建立 good/sloppy 自然分类，也不修改正式 worker 三轴或 routing。
- Manual-only worker 分层审计：`tools/thesis_main/analysis/audit_worker_manual_strata_exploratory.py`；结果 `analysis_results/worker_manual_strata_audit_20260904_v1/`。仅用 C1 Calibration_core Manual 的 task-adjusted Q_GT 建立逐 building 的 H/L/U 证据状态，再于零任务重叠的 dense41 Manual 数据检验；当前裁决为不支持冻结稳定 good/sloppy 类型，不修改正式 worker 三轴或 routing。
- 导师定稿前图片初筛：`tools/thesis_main/data_prep/build_annotation_uncertainty_prescreen_review.py`；结果 `analysis_results/annotation_uncertainty_prescreen_20260903_v1/`。覆盖314张机器提示并生成来自166张无现有annotation记录池的30张极简人工审阅包；状态为非规范、未冻结、未分发。
- [ANNOTATION_UNCERTAINTY_EXPERIMENT_SUPERVISOR_DRAFT_v2.md](thesis_main/ANNOTATION_UNCERTAINTY_EXPERIMENT_SUPERVISOR_DRAFT_v2.md)：基于历史失败审计重新定位的导师讨论稿 v2；状态为 DRAFT / NON-NORMATIVE / NOT APPROVED，提出候选 RQ、24×3×4 三臂设计、最小元标注、离线几何环序/残差与统计成功判据，不修改正式方法合同、SAP、T1/V1、已关闭阶段、Label Studio 分发或历史数据。
- [ANNOTATION_UNCERTAINTY_EXPERIMENT_SUPERVISOR_DRAFT_v1.md](thesis_main/ANNOTATION_UNCERTAINTY_EXPERIMENT_SUPERVISOR_DRAFT_v1.md)：360°布局标注不确定性研究的导师讨论稿；当前为 `DRAFT / NON-NORMATIVE / NOT APPROVED`，提出全部Manual按支持数分层的Study 1与72图三臂候选Study 2。v2 元标签使用工人侧缺陷/修复多选并按集合分析，研究者侧保留主要缺陷与刺激纯度；20人可为全新cohort、active time仅作辅助，`R_vis`须先独立验证，完整topology signature与技术阶段锁不进入默认方案；不改变当前方法合同、SAP、T1或任何分发工件。
- [ANNOTATION_UNCERTAINTY_EXTERNAL_REVIEW_PROPOSAL_NOTE_v1.md](thesis_main/ANNOTATION_UNCERTAINTY_EXTERNAL_REVIEW_PROPOSAL_NOTE_v1.md)：单独记录外部审稿方案及其与导师讨论稿的差异；状态为 `EXTERNAL PROPOSAL / NON-NORMATIVE / NOT ADOPTED`，不代表本项目采纳。
- 历史 Model Issue 构念回放：`tools/thesis_main/analysis/analyze_historical_model_issue_construct.py`；输出 `analysis_results/historical_model_issue_construct_validation_20260827_v1/`。逐图并列历史 P1 初始标注、冻结参考、每图26名工人的实际旧标签和研究者新分类；结论为开发审计，不重编码历史数据或冻结新 truth。
- 候选Batch 1研究者审核：`tools/thesis_main/data_prep/build_annotation_uncertainty_batch1_review.py`；宽审核范围为 `analysis_results/annotation_uncertainty_batch1_broad_review_20260828_v1/review.html`，从混合GT v4的Test+Validation共同总体按客观中等差异带筛139张（Test 124、Validation 15），只排除研究者已经审过的28图以免重复操作。此前28张已有14张PASS，当前先使用 `analysis_results/annotation_uncertainty_batch1_supplement_review_20260828_v1/review.html` 审核8张无重合补充候选；非约束视觉意见不作自动排除，正式分发才执行same-worker×same-image历史暴露去重。所有审核包均未冻结、未分发且不是LS import。
- 现有 LS 标签开发测试：`import_json/uncertainty_meta_feasibility_20260824/`；仅含 5 张历史已标注 P1 Semi 图片，8 名中文标注者同图复测，共 40 条分配，不进入正式实验或论文分析。
- 中性 retrospective 数据底座入口：`tools/thesis_main/analysis/full_uncertainty/materialize_uncertainty_substrate.py`；冻结输出：`analysis_results/uncertainty_substrate_20260823_v1/`。该并行底座纳入全部 2,501 条 canonical 记录，旧 eligibility 仅保留为历史字段，不修改方法合同、SAP 或 C2-B/C2-A-RP closeout。
- RQ1 分层探索复算：`tools/thesis_main/analysis/analyze_rq1_stratified_uncertainty_20260827.py`；结果：`analysis_results/rq1_stratified_uncertainty_20260827_v1/`。主分析按 stage/batch/condition 分层，42 个 P1/C1 高密度单元用于支持数校准，C2-B 高支持单元只作独立复核。
- 工具入口：`tools/thesis_main/analysis/full_uncertainty/materialize_full_uncertainty_data_mining_v5.py`（复用 v4 计算引擎）
- 当前生成目录：`analysis_results/full_uncertainty_data_mining_20260821_v5/`；v4 交付只保留在 Git 历史中。
- 该审计保留 Active time 与 Label Studio Lead time 的边界，不修改规范方法合同或已冻结阶段结果。
- Manual–Semi correctness/OOS 补充审计入口：`tools/thesis_main/analysis/full_uncertainty/analyze_manual_semi_correctness_oos_20260823_v3.py`；结果目录：`analysis_results/manual_semi_correctness_oos_20260823/`。其中资源方案仅为未生成 assignment manifest 的探索性资源算术，不改变正式 T1 的 2×2 设计。

## 2026-09-05 研究数据与候选视觉审计

- [研究方向与数据决策说明](../analysis_results/annotation_research_decision_audit_20260905_v1/研究方向与数据决策说明.md)：导师讨论证据、历史数据口径、building 覆盖及候选研究建议；不定稿论文、实验、GT 或标注者类别。
- [50 张候选审查页](../analysis_results/annotation_research_decision_audit_20260905_v1/review50/review.html)：从剩余 136 图选取 50 图，排除已人工审核的 30 图；GT、HoHoNet、Bi-Layout 双输出并列，AI 建议与人工记录分开保存。
- `analysis_results/annotation_research_decision_audit_20260905_v1/`：资产索引、来源复算、building/独立性诊断与汇总工作簿。派生审计不覆盖原始导出、历史人工判断或正式协议。
- [第二轮研究前置材料](../analysis_results/annotation_research_prework_20260905_v2/)：补齐来源与同图证据，探索质量、时间与习惯的候选描述并进行留出诊断；[三轴与六篇文献对照](../analysis_results/annotation_research_prework_20260905_v2/三轴建模与文献对照.md)仅作解释和可行性讨论，不定义正式人员资格或新实验。
- [外部分析与第二轮材料的独立审查](../analysis_results/annotation_reanalysis_independent_audit_20260905_v1/独立审查报告.md)：2026-09-06完成；独立复算C1人员特征、版本/时间敏感性，诊断分类验证参照变化；不改写原包或最终人工判断。
- [前置分析包独立审查](../analysis_results/preflight_independent_audit_20260906_v1/独立审查报告.md)：原始坐标与建筑留出预测复现、固定15人面板穷举、去除合成初始化后的重拟合及几何指标解释；附[轨迹保存范围勘误](../analysis_results/preflight_20260906_v2/说明勘误_20260906.md)。只作研究决策支持。
- [不确定性研究云端输入包](../analysis_results/uncertainty_cloud_inputs_20260906_v1/README_ZH.md)：214图历史响应、166图候选、模型原始坐标、已有分簇及版本连接；附[云端接手说明](../analysis_results/uncertainty_cloud_inputs_20260906_v1/CLOUD_HANDOFF_ZH.md)。不重新分簇或定义歧义标签。
- [不确定性接手独立复核（2026-09-08）](../analysis_results/uncertainty_followup_analysis_20260908_v1/README_ZH.md)：读取敏感性及本地导出追溯；新增[用户点序确认后的深度分析](../analysis_results/uncertainty_followup_analysis_20260908_v1/深度分析_用户点序确认后.md)，包括非星形度量限制、经验分布恢复、building与人员组合诊断，不改原始标注或人工裁决。
- [研究交接（2026-09-09）](thesis_main/研究交接_20260909.md)：同building即当前相似场景；研究意图、已做计算、人员组合支线、口径差异与下一步。
- [研究交接与两轮独立分析整理（2026-09-09）](thesis_main/研究交接与独立分析整理_20260909.md)：非规范补充；区分两轮报告、人员与场景证据、稳定判据边界及第二轮材料缺失，不替代SOP或原结果。
- [收敛假说、人员分档与HoHoNet特征核对](../analysis_results/convergence_hypothesis_review_20260909_v1/README_ZH.md)：直接回读窗口、分组表和NPZ；同楼早／晚／未达标例子、候选人员档位、214图特征覆盖及缓存数值差异，未进行新的预测模型验证。
- [uNb预测检验：高低人数与特征配平](../analysis_results/unb_prediction_check_20260909_v1/README_ZH.md)：6→6、7→5及27图混合短窗；比较人数/DT配平、楼外基线和覆盖，区分旧d_t与d_model_feat，非正式协议。
- [研究主线与新增标注验证说明](thesis_main/研究主线与新增标注验证说明_20260909.md)：讨论稿；按导师原文区分明确要求与回忆，串联人数、人员组成和场景预测，并说明新人旧图桥接与同楼新图验证的职责。
- [数据连接与历史测量说明](../analysis_results/uncertainty_decision_ready_20260908_v1/README_ZH.md)：canonical、初始化、人工评论和Bi精度连接，保留历史测量边界。
- [历史结果归档](../analysis_results/research_history_archive_20260909_v1/README_ZH.md)：旧楼内留出、单楼试算、旧人员分层／组合及旧汇报稿，含逐文件清单和恢复方法；[逐楼普查](../analysis_results/building_holdout_exploration_20260908_v1/census/README_ZH.md)仍保留。
- [相似场景标注稳定性分析SOP（当前统一入口）](thesis_main/相似场景标注稳定性分析SOP.md)：按原始图像确认同房间，再探索跨房间类型；两级预测待执行，已有building结果保留为基线。全阶段无辅助手工统一，各图独立分簇，跨图预测稳定人数；已确认误点按记录排除后比较计算点数。支持人数m与几何/稳定阈值分开。
  - [局部窗口基线：多楼阈值与人数分析](../analysis_results/multibuilding_threshold_stability_20260909_v1/分析结果.md)：revised中并列包含／排除W19与W26，55高人数图及141低人数图回放、10楼共同预算留图／楼外对照、短窗延长检查与不补点敏感性；不与本轮持续阶段人数混算。
  - [26份q不可评价诊断](../analysis_results/multibuilding_threshold_stability_20260909_v1/分析结果.md#geometry-audit)：9项用户判断已应用reviewed计算副本，两份28点通过共享搜索修复恢复；geometry_audit保留修复前原图与确认记录，revised为当前计算。
- [移交包独立审查与50图辅助视觉检查](../analysis_results/uncertainty_visual_review_20260907_v1/README_ZH.md)：30历史＋20候选、22个building；原始/3D对照、初始化与bootstrap勘误、预览点序建议及反例。[三步问卷与保存说明](../analysis_results/uncertainty_visual_review_20260907_v1/QUESTIONNAIRE_ZH.md)提供独立人工填写入口，包含3D角点组顺序调整、OOS意见／理由及分别保存说明。[50图高清复看与点序勘误](../analysis_results/uncertainty_visual_review_20260907_v1/ORDER_REVIEW_ZH.md)说明W31连接假设及逐图保留意见。附[不完整原包归档记录](../analysis_results/uncertainty_handoff_received_20260907_v1/README_ZH.md)；不替代人工裁决。
- 上述50图入口已接入2048原始PNG、矢量标注叠图及新版交互3D；升级说明和复现命令随包保存。

## HoHoNet 初始化代理审计

- 生成工具：`tools/thesis_main/analysis/materialize_model_initialization_audit.py`
- 当前结果：`analysis_results/model_initialization_audit_hybrid_gt_20260823_v4/`（共享逐图 CSV；分别提供旧版 v1 阈值保留报告与角点数量主分析报告）
- v3 保留全景角点原始环序并与仓库 `eval_layout.py` 对齐；GPU 重跑、旧/新预测对照和完整解释见结果目录中的报告与 manifest。

## 独立全景 3D 预览

- [空间标本使用与验证说明](label_studio/PANORAMA_STUDIO_v1.md)：[统一入口](../analysis_results/panorama_studio_20260907_v3/index.html)支持组号查询、Manual/Semi历史分簇、逐人3D及手动角点组预览排序，不写回标注。历史数据由`build_room_history_studio.py`刷新，使用既有canonical快照。
- [人工问卷与视觉观察核对](../analysis_results/human_review_reconciliation_20260907_v1/README_ZH.md)：50条人工评语与选项核对、点序读取勘误及逐图待确认单；记录完成不代表确定，不填最终裁决。 补充原文enclosed／extended、潜在范围、质量与规则分离的逐条提取；旧候选题仅归档。

## 人员类型与组合探索（独立口径）

- [规则执行粗依据与修改—时间—质量三指标](../analysis_results/worker_rule_triad_20260910_v1/README_ZH.md)：最新Semi点处理、同面板消融、互斥分半、初始化敏感性与Manual迁移；20人中16人满足三指标支持，候选类型未确认。
- [速度与参考偏差的可解释粗类验证](../analysis_results/worker_behavior_time_20260910_v1/README_ZH.md)：26人／20人并列；日志重放、排除已知人工加秒、留楼与跨阶段验证、逐人两轴画像。速度可复现不等于质量或类内收敛。
- [粗类验证：全部26人／当前20人](../analysis_results/worker_coarse_validation_20260910_v1/README_ZH.md)：最新计算副本、留楼粗分、互斥分半、硬点数类内持续阶段与同图同人数对照；存在局部稳定案例，未确认普遍人员类型或新人收敛。
- [Manual粗依据＋Semi细行为探索](../analysis_results/semi_subtype_exploration_20260909_v1/README_ZH.md)：574条真实初始化连接；[9月10日复审](../analysis_results/semi_subtype_exploration_20260909_v1/分类要求与粗细分型复审_20260910.md)区分分类要求、附加行为信息、最新覆盖与计算版本；尚未确认类型或类内收敛。

- [两类/三类人员与人数收敛探索](../analysis_results/type_convergence_exploration_20260909_v1/README_ZH.md)：全历史合并、楼外分型、楼内固定验证人员；保留旧覆盖与曲线。旧OSPA分区未落实硬点数约束，不能直接用作当前粗／细类收敛证据。

- [人员三组及更多组的可行性](../analysis_results/worker_reference_feasibility_20260909_v1/pooled/groups/README_ZH.md)：合并历史标注的2–5档训练内分组、跨building预测、成员敏感性及ABC等人员组合覆盖；不预设认真/粗心语义，不确定最终类型数。

- [参考执行偏差可行性验证（2026-09-09）](../analysis_results/worker_reference_feasibility_20260909_v1/README_ZH.md)：人工复核优先、其他暂信GT；无序点集测量及跨building工人效应验证，保留参考疑问与计算失败，不生成最终工人类别。新增[全部阶段/条件合并分析](../analysis_results/worker_reference_feasibility_20260909_v1/pooled/README_ZH.md)，按图片与人组织，不按旧实验设置筛选或分组。
2026-09-13脚本更新：中英文正式／调试userscript为`manual_scope_only_20260913_v10`；新Manual检查Scope单选与表单一致性。三个LS可导入JSON独立在`import_json/scene_stability_stage1_20260913_v2/label_studio_import/`，管理材料在上一级；尚未线上安装或导入。
> 2026-09-13最新执行替换：用户确认480份内优先完整覆盖部分房间，采用后视角多者优先。当前必做G172/G184/G179/G178/G047/G237，44个采用视角中37张新增、7张仅历史；中文每人20张、英文每人30张。旧19组43图的分散配对及下文旧计数不再执行。G184五图最高19人、距20人目标各缺1人。H定稿12门洞＋8同房共20张，G178四张原选做转入必做；个人表标记已接触者跳过。现行说明在analysis_results/stage1_person_image_packages_20260913_v2/整房优先版交付说明.md，整房审计见同目录必做整房核查.json。下文过程性说明保留作历史，不覆盖本段及现行机器包。
