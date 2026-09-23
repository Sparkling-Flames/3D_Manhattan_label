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
- `cleaning.shared_x`：每对上下点的周期最短弧中点，原y保持；用已有审核配对
- `cleaning.screen`：目标为非墙角、乱标等明显无效标注；角点数量、配对、现有环序3D几何、顺序线索、异常/单人小簇、表示失败与参考/同行IoU辅助通道取并集，逐份保留触发证据及覆盖；不以IoU作为唯一入口。范围不同和少数结构解释必须视觉裁决，点击次序不视为真实连接顺序
- `cleaning.machine_decision`：pending_manual_review_only
- `cleaning.exclusion`：按明确人工证据裁决；不由单人簇、低IoU、模型失败、未知GT或未决意见自动排除
- `cleaning.outputs`：纳入前后口径；逐人无效作答数量与比例；历史裁决及有效点版本；完整排序及缺失参考状态

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
