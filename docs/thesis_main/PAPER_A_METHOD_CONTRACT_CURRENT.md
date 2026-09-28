<!-- PAPER_A_MACHINE_STATUS: generated -->
# 当前共识研究方法合同（自动生成）

来源：`PAPER_A_METHOD_CONTRACT_CURRENT.json`；合同版本：`consensus_research_20260923_v1`。
状态：`current_research_protocol`；方法选择：`comparison_protocol_not_final_algorithm`。

真实人员构成、进入顺序与区域共识接近GT；图片难度及同房预测继续研究

## 研究问题

- 图片差异调整后的人员质量、类别稳定性及真实人员组合规律
- 共识准确性、增人稳定性和同人数成员差异随人数的变化
- HoHoNet结构与错误、BiLayout双头差异对应的图片难度
- 同房及跨建筑预测；不明确结果保留记录，论文主文呈现另定

## 数据与清洗

- `data.source`：原始export_label，经已有canonical版本和人工裁决生成计算视图
- `data.accepted_snapshot`：analysis_results/new_manual_reviewed_20260921/responses.jsonl.gz
- `data.expected_accepted_responses`：3019
- `data.expected_images`：259
- `data.expected_manual_oos_responses`：2481
- `data.conditions`：manual/oos/semi分别计算；Manual与OOS合并主线时同时报告各自覆盖
- `data.existing_worker_exclusions`：W019；W026
- `data.unit`：canonical作答；同人同图同条件多版本只保留已确认当前版
- `data.borrowed_points`：保留来源和描述用途，独立组合/预测不计为独立票
- `data.unbound`：保留，列为待审/不可评价，不猜配对或补点
- `data.raw_mutation`：False
- `data.preprocessed_source`：analysis_results/shared_x_baseline_20260928/preprocessed_source.json
- `data.preprocessed_source_scope`：全量3152份人员标注及287份去重GT来源；后续分簇、质量、共识及排序共用。当前有效点完整配对后周期共享x，y不变；无可用配对者preprocessed_points=null，不回退到未平均点；分析资格与预处理状态分开。历史结果不追改。
- `cleaning.review_continuation_20260928`：明确后续说明与续审issue优先于旧表单pending；仅覆盖涉及对象。原件保留，机器全量台账3152份含133份历史未纳入，不自动恢复资格。改善建议不授权修复。
- `cleaning.review_sop`：docs/thesis_main/两人审核归并与二次复核SOP_20260925.md
- `cleaning.review_scope_20260925`：两份用户JSON为主；一正独审图和任一作者全部排除作答必须复核；补点请求、同图图片背景和相似标法处理差异保留来源。作者选项含义分开，不直接合并。
- `cleaning.review_return_20260927`：二审JSON独立保存，图级场景可由同图未重填成员共享，但不覆盖个人问题；待定不等于漏审或排除。旧簇评论按当时默认affinity固定到worker、canonical作答ID、条件与点位版本，不随重分簇改指。
- `cleaning.retained_variation`：本轮仅用户明确确认排除者作清洗剔除，既有排除另保留来源；保留的执行误差、局部结构简化与大块空间取舍进入主研究，不预拆簇改善曲线。待定和待修复不自动排除。
- `cleaning.confirmed_oos_point_rule`：仅已确认OOS的当前有效点少于8默认建议排除，用户确认后应用；跨8点的已修复版本先核验，未应用提案不计点数。门洞不自动套用此阈值。
- `cleaning.difficult_scene_review`：确认OOS或难标门洞，偶数且可配对不只因场景难/范围不同而排除；奇数或疑似完全不能配对须核查修复。等价解、角色限制或顺序失败不等于完全无法配对。
- `cleaning.shared_x`：每对上下点的周期最短弧中点，原y保持；用已有审核配对
- `cleaning.screen`：目标为非墙角、乱标等明显无效标注；角点数量、配对、现有环序3D几何、顺序线索、异常/单人小簇、表示失败与参考/同行IoU辅助通道取并集，逐份保留触发证据及覆盖；不以IoU作为唯一入口。范围不同和少数结构解释必须视觉裁决，点击次序不视为真实连接顺序
- `cleaning.machine_decision`：pending_manual_review_only
- `cleaning.exclusion`：按明确人工证据裁决；不由单人簇、低IoU、模型失败、未知GT或未决意见自动排除
- `cleaning.outputs`：纳入前后口径；逐人无效作答数量与比例；历史裁决及有效点版本；完整排序及缺失参考状态
- `cleaning.order_review_20260928`：正式工作台接入45图90候选，读取全研究共享x基线的子集。原始Matterport与人工修订GT分别绑定。当前次序独立保存，点位匹配错误单列后审，不自动重配、不判无效；下一份遍历同图所有候选。原图/排序首屏，3D下方；标签20%不透明并可只看点位。
- `cleaning.review_coverage_20260928`：24张覆盖补审仅更新图片维度；原件及wc-61只勾选scope的用户更正分别留存。最新明确分类优先，同房仅比较不自动传播。pRb-16按原话暂缓全部分析，不作人员无效。排除统计区分明确个人排除、历史未纳入与图片分析资格限制；GT下拉别名不替代实际参考来源。

## 区域、参考与人员质量

- `representation.primary_candidate`：ERP二维顶底曲线所夹墙带；空间直线的全景投影
- `representation.sensitivity`：周期二维直线墙带
- `representation.coordinate_frame`：1024x512像素中心坐标；改变栅格用(x+0.5)*scale-0.5
- `representation.pilot_raster`：512；256
- `representation.resolution_check`：1024；512
- `representation.horizontal_boundary`：periodic
- `representation.failure`：同方位多边界、退化、非法曲线明确记录，不等同人员错误
- `representation.postprocessing`：首轮不几何规整；后处理作为单独比较，不强制Manhattan
- `references.original`：data/mp3d_layout/test/label_cor；data/mp3d_layout/valid/label_cor
- `references.manual_revision`：export_label/groudTruth.json
- `references.revision_comparison`：原始与人工修订版本分别报告；点集变化审计沿既有1px实质修订定义
- `references.not_gt`：HoHoNet；BiLayout enclosed；BiLayout extended
- `references.reference_conflicts`：历史scope/GT意见按具体对象保留，未知项不升级为统一真值
- `references.detail_and_scope_variation`：参考省略局部细节与合理不同空间范围分别记录，可同时存在，不自动标为GT错误或从主研究剔除。明确指出参考实质错误才单列原始/人工修订版本核验；固定参考距离不直接等于人员错误。
- `quality.overlapping_scene_dimensions`：OOS为任务适用性，门洞为拍摄位置/边界条件，允许共存并保留评论证据；原单选category不覆盖原话。not_recorded不是否定，raw condition=oos不是研究者确认。并集分母按canonical作答去重。
- `quality.review_use_separation`：清洗裁决、场景适用性、参考状态、范围政策和几何可计算性分开。明确暂不进主分析同时限制主共识面板与人员主质量；明确仅内侧空间须披露事后人工范围政策，不自动恢复GT质量，也不由簇号批量改判。
- `quality.manual_scene_exclusions`：确认OOS与确认难标门洞不纳入人员主质量分析；可标门洞单列核对GT/范围后决定恢复，历史疑似分类不自动等于确认。保留场景分歧、可用表示上的分簇/共识探索。
- `quality.scene_subtypes`：OOS区分非正交但稳定可标、结构/高度等约束不适用、拍摄/遮挡导致边界难定，允许共存且门洞另记；非正交稳定组共识单列，人员主质量暂不纳入。保留不等于分析资格，难度缺失记未记录。
- `quality.primary`：GT区域IoU
- `quality.centroid`：面积质心；ERP坐标均值与圆周质心/R分别报告，低R角度不得直接作位移权重
- `quality.centroid_role`：整体位置诊断，不能代替局部结构，也不先验保证改善IoU
- `quality.worker_adjustment`：同图比较及人员/图片效应；按建筑留出检验，不从单图STAPLE参数推出跨图人员能力
- `quality.combination_weights`：待数值和视觉审查；IoU-only与IoU+centroid分开比较
- `quality.failure_denominator`：按方法保留失败行/覆盖；共同可评价集比较及全范围失败率并报

## 共识构造与算法比较

- `consensus.lee_source`：https://ceur-ws.org/Vol-2173/paper10.pdf
- `consensus.construction`：重叠区域的成员投票→tile/pixel支持→区域选择
- `consensus.core_methods`：mv50；mv_strict；medoid；em_correct_probability；greedy_empirical；staple
- `consensus.em_greedy_status`：明确适配版本，不宣称完整复现未取得的Lee技术报告
- `consensus.extended_methods`：MACCHIatO-Jaccard(源码及周期适配待核)；MAP-STAPLE(实现和先验待核)
- `consensus.calibrated_methods`：GT-IoU人员加权；GT-IoU+质心人员加权；外建筑GT性能先验
- `consensus.information_sets`：当前k份标注独立一组；外建筑校准另组；目标GT仅评价，oracle单列
- `consensus.clustering`：全体与最大簇聚合的额外对照；不作为共识前提；保留全部簇支持
- `consensus.outputs_distinct`：观察到的人员支持率；模型后验或优化软场(注明含义)；聚合区域；GT质量
- `consensus.unavailable_method`：显式unavailable，不替换算法、不伪造结果

## 真实人员组合与重放

- `replay.same_inputs`：所有方法共用人员子集、顺序、图片面板和区域定义
- `replay.prefix`：仅当前k人的标注与事先可用外部校准；固定栅格无未来信息
- `replay.k`：实际收集的不同真人数；最大簇使用人数另记
- `replay.permutations`：真实人员无放回；相同完整成员集最终一致不是收敛上限证据
- `replay.inference_unit`：同图配对方法差；建筑分组，不把像素或重放次数当独立样本
- `replay.classification`：分类仅由训练建筑得到；未知/不稳定类别保留，不为AABC复制真人
- `replay.stopping_thresholds`：尚未冻结；不显著改善不等于达到平台

## 交付与复核

- `delivery.pro_task`：docs/thesis_main/PRO_CONSENSUS_RESEARCH_TASK_20260923.md
- `delivery.results`：analysis_results/consensus_research_20260923
- `delivery.pro_role`：数值清查、指标比较、共识实验；不得替代视觉错误裁决
- `delivery.final_review`：用户与本地助手复算并查看原图后确认清洗与方法

## 验收与历史边界

完全一致；两人平票；共同漏画；同质心异形；接缝循环平移；分辨率变化；非法区域与缺失不静默丢行；目标GT隔离；人工修订GT敏感性

历史合同：`docs/thesis_main/PAPER_A_METHOD_CONTRACT_20260811_v23.json`。v23只解释既往Calibration/T1/V1流程及其历史复算，不定义本研究的纳入或算法。
历史合同内容与历史脚本绑定保持独立；本合同不追溯改写既往裁决。
