# HOHONET 研究资料总目录

目录版本：research_catalog_20261016_v1；盘点日期：2026-10-16。

登记主题包、结果快照、关键文档、规范输入和已知本地外部来源。原始标注、GT审核原件、统一输入和合同留在真源位置；历史包未迁移的仍按原路径检索。按包或关键文件登记，不表示逐文件内容均已独立复核。

机器可读真源为 [CATALOG.json](CATALOG.json)。本目录只定位资料，不改变其方法、数据资格或采用状态。原路径保留在迁移映射中；原始标注、审核回执、规范合同与统一输入未迁移。

## 按主题查找

|主题|入口|资料数|说明|
|---|---|---:|---|
|研究统筹|[打开主题入口](../../docs/thesis_main/topics/coordination/README.md)|74|原意、跨模块关系、进度、版本采用与交接。|
|数据与参考|[打开主题入口](../../docs/thesis_main/topics/data/README.md)|5|输入版本、人数门槛、GT/空间绑定和排除状态。|
|质量评分|[打开主题入口](../../docs/thesis_main/topics/quality/README.md)|84|公式、参数、实现、校准、人评、反例与模型比较；算法身份和模块采用状态分开。|
|图片难度|[打开主题入口](../../docs/thesis_main/topics/difficulty/README.md)|20|固定目标空间下的粗分难度、结构/操作负担、人工复核和标签版本。|
|人员研究|[打开主题入口](../../docs/thesis_main/topics/workers/README.md)|32|Q/T/S/B画像、分类、组合与换人实验；记录质量版本及训练/评价集合。|
|融合研究|[打开主题入口](../../docs/thesis_main/topics/fusion/README.md)|24|Lee区域投票与墙线对应、全池投票、定位、连接和人数过程。|
|同房研究|[打开主题入口](../../docs/thesis_main/topics/same_room/README.md)|4|同房直接关系证据、共同人员、质量/融合曲线和迁移比较。|
|描述统计|[打开主题入口](../../docs/thesis_main/topics/statistics/README.md)|5|各批次覆盖、分母、分层结果、表格、图表与扩展复算。|
|文献与跨模块资料|[打开主题入口](../../docs/thesis_main/topics/literature/README.md)|3|文献阅读和跨模块共同基础；跨模块整包保持原结构并通过引用关联。|
|历史归档与未分类快照|[打开主题入口](../../docs/thesis_main/topics/archive/README.md)|256|保留原位且不属于当前主题入口的旧结果和历史快照；按原路径及日期回溯，不代表当前方法或待办。|

## 质量分项与单位

|分项|单位|测量含义|
|---|---|---|
|`I`|比例0–1|固定参考下的底面IoU；I=0时完整质量分为0。|
|`Sb`|度|冻结实现的双向球面底边平均距离；不是必要墙面结构完整性。|
|`D`|度|作答自身最优共同正交轴下、按边长加权的方向残差RMS；不是相对参考墙角误差。|
|`Hm`|输入几何坐标单位|整体均高偏差。|
|`Hc`|输入几何坐标单位|基于底边对应的中心化局部高度残差。|
|`F,d,H`|无量纲|F=(1/I-1)+Sb²/32；d_c=1.5D²/(D²+c²)，c以度计；H=(Hm/0.8)²+(Hc/0.25)²。分数0–100、越高越好。|

## 质量算法身份与采用地位

|版本|定义|关键参数|测量目的|采用状态|版本关系|实现/证据入口|
|---|---|---|---|---|---|---|
|WQ前身 hill_global08 (`hill_global08`)|`100*I/(1+K), K=Sb^2/32+1.5D^2/(D^2+37.5)+(Hm/0.8)^2+(Hc/0.25)^2`|D scale=sqrt(37.5) degrees; H scales=.8/.25 input units|历史综合几何质量分|历史前身|前身实现；保留版本沿革。|[tools/thesis_main/analysis/quality_staged_calibration_20261014.py](../../tools/thesis_main/analysis/quality_staged_calibration_20261014.py), [research/quality/quality_model_closeout_20261014/README.md](../quality/quality_model_closeout_20261014/README.md)|
|WQ-LS08 (`WQ-LS08`)|`F=(1/I-1)+Sb^2/32; d=1.5*D^2/(D^2+37.5); H=(Hm/0.8)^2+(Hc/0.25)^2; Q=100/(1+F+d+H), I=0 -> 0`|c=sqrt(37.5) degrees; H scales=.8/.25 input units|历史WQ合成指数|历史工作版；部分下游仍使用|人员、融合、同房历史结果多使用WQ；新质量线B8L2不改写旧结果。|[research/quality/quality_combination_review_20261016/pro_original/src/mechanisms.py](../quality/quality_combination_review_20261016/pro_original/src/mechanisms.py), [research/quality/quality_model_closeout_20261014/README.md](../quality/quality_model_closeout_20261014/README.md), [research/quality/quality_ab_feedback_handoff_20261015/README.md](../quality/quality_ab_feedback_handoff_20261015/README.md)|
|A10 (`A10`)|`F=(1/I-1)+Sb^2/32; d10=1.5*D^2/(D^2+10^2); H=(Hm/0.8)^2+(Hc/0.25)^2; Q=100/(1+F+d10+H), I=0 -> 0`|c=10 degrees; H scales=.8/.25 input units|B8L2的并行加法敏感性|历史并行对照|保留作历史敏感性，不取代B8L2。|[research/quality/quality_combination_review_20261016/pro_original/src/mechanisms.py](../quality/quality_combination_review_20261016/pro_original/src/mechanisms.py), [research/quality/quality_ab_feedback_handoff_20261015/README.md](../quality/quality_ab_feedback_handoff_20261015/README.md)|
|S8 (`S8`)|`F=(1/I-1)+Sb^2/32; d8=1.5*D^2/(D^2+8^2); H=(Hm/0.8)^2+(Hc/0.25)^2; Q=100/(1+F+d8+H), I=0 -> 0`|c=8 degrees; H scales=.8/.25 input units|与B同方向尺度的加法控制|机制对照|用于隔离组合形状与方向尺度，不是替换方案。|[research/quality/quality_combination_review_20261016/pro_original/src/mechanisms.py](../quality/quality_combination_review_20261016/pro_original/src/mechanisms.py), [research/quality/quality_combination_review_20261016/README.md](../quality/quality_combination_review_20261016/README.md)|
|B8L2 (`B8L2`)|`F=(1/I-1)+Sb^2/32; d8=1.5*D^2/(D^2+8^2); H=(Hm/0.8)^2+(Hc/0.25)^2; Q=100/(1+sqrt(F^2+d8^2)+H), I=0 -> 0`|c=8 degrees; L2 pooling; H scales=.8/.25 input units|当前质量线几何工作指数，合并底面/边界负担与自身方向残差|当前质量线工作版；未全局重评下游|Pro机制研究推荐；用户30份粗核验整体更偏好；人员/融合/同房未全量改分。|[tools/thesis_main/analysis/scope_quality_scoring_20261016.py](../../tools/thesis_main/analysis/scope_quality_scoring_20261016.py), [research/quality/quality_combination_review_20261016/pro_original/src/mechanisms.py](../quality/quality_combination_review_20261016/pro_original/src/mechanisms.py), [research/quality/quality_ab_feedback_handoff_20261015/README.md](../quality/quality_ab_feedback_handoff_20261015/README.md), [research/quality/quality_combination_review_20261016/README.md](../quality/quality_combination_review_20261016/README.md)|
|C8 (`C8`)|`F=(1/I-1)+Sb^2/32; d8=1.5*D^2/(D^2+8^2); H=(Hm/0.8)^2+(Hc/0.25)^2; M=max(F,d8)+(sqrt(2)-1)*min(F,d8); Q=100/(1+M+H), I=0 -> 0`|c=8 degrees; lambda=sqrt(2)-1; H scales=.8/.25 input units|组合形状敏感性|候选敏感性；不取代B8L2|与B8L2轴和等分对角锚点匹配；不构成独立人评证据。|[research/quality/quality_combination_review_20261016/pro_original/src/mechanisms.py](../quality/quality_combination_review_20261016/pro_original/src/mechanisms.py), [research/quality/quality_combination_review_20261016/README.md](../quality/quality_combination_review_20261016/README.md)|
|均高棱柱3D IoU (`mean_height_prism_3d_iou`)|`底面交并与顶点平均墙高棱柱的重合度；非一般mesh/精确非平顶实体体积IoU`|无新拟合参数；固定现用几何构造|与固定参考的接近程度对照|并列参考指标/历史对照|与B8L2测量目标不同；局部高度可能被均高掩盖。|[tools/thesis_main/analysis/scope_quality_scoring_20261016.py](../../tools/thesis_main/analysis/scope_quality_scoring_20261016.py), [research/quality/quality_iou_examples_20261014/README.md](../quality/quality_iou_examples_20261014/README.md)|
|得分制与Q-Profile分档草案 (`quality-score-vs-qprofile`)|`没有新几何分公式；把来源连续分映射到描述性五档，阈值未冻结`|没有拟合几何参数；五档边界未冻结|人类可读等级展示，不替代几何测量|未采纳/待判断展示草案|不改变原始连续分排序或方向/结构误差。|[research/quality/quality_profile_independent_review_20261015/README.md](../quality/quality_profile_independent_review_20261015/README.md)|

## 有代表性的结果快照

|快照|实际分母及用途|批次与输入|目标/参考|纳入规则与标签|方法版本|结果与成员名单|来源证据|复现入口/状态|
|---|---|---|---|---|---|---|---|---|
|807旧完整质量快照 (`quality_807_legacy`)|807个旧快照合格评分；名单以对应历史输入为准|2026-10-15参考重算前的统计阶段；按旧统计包冻结的输入|重算前参考绑定；历史快照|历史纳入和排除规则，不回填当前状态；按来源快照的难度/特殊标签|当时列示的WQ/A10/B8L2/均高棱柱IoU|[结果](../statistics/descriptive_statistics_current_20261015/quality_records.csv) / [成员名单](../statistics/descriptive_statistics_current_20261015/quality_records.csv)|[research/statistics/descriptive_statistics_current_20261015/README.md](../statistics/descriptive_statistics_current_20261015/README.md), [research/statistics/descriptive_statistics_current_20261015/HANDOFF.md](../statistics/descriptive_statistics_current_20261015/HANDOFF.md), [research/statistics/descriptive_statistics_current_20261015/INDEPENDENT_AUDIT.md](../statistics/descriptive_statistics_current_20261015/INDEPENDENT_AUDIT.md), [research/statistics/descriptive_statistics_current_20261015/inventory_all.csv](../statistics/descriptive_statistics_current_20261015/inventory_all.csv)|[tools/thesis_main/analysis/descriptive_statistics_current_20261015.py](../../tools/thesis_main/analysis/descriptive_statistics_current_20261015.py)；冻结输出、名单和历史输入审计可定位；本轮只整理目录，未重跑。|
|891当前完整质量统计 (`quality_891_current`)|891份：828 manual/73图/24人；63 semi/4图/24人|当前3152份/259图库存统计阶段；CURRENT v3输入和2026-10-16参考重算增量|41图审查：39新空间+2修订GT，逐作答绑定|每个图片×条件至少3有效真人及GT错误/既有排除规则；CURRENT v3难度；1—2人图片暂不纳入；特殊层分开|WQ/A10/B8L2/现用均高棱柱IoU|[结果](../statistics/descriptive_statistics_rescored_20261016/quality_records.csv) / [成员名单](../statistics/descriptive_statistics_rescored_20261016/quality_records.csv)|[research/statistics/descriptive_statistics_rescored_20261016/README.md](../statistics/descriptive_statistics_rescored_20261016/README.md), [research/statistics/descriptive_statistics_rescored_20261016/inventory_all.csv](../statistics/descriptive_statistics_rescored_20261016/inventory_all.csv), [research/statistics/descriptive_statistics_rescored_20261016/record_targets.csv](../statistics/descriptive_statistics_rescored_20261016/record_targets.csv), [research/statistics/descriptive_statistics_rescored_20261016/space_reference_catalog.csv](../statistics/descriptive_statistics_rescored_20261016/space_reference_catalog.csv), [research/data/scope_quality_rescore_20261016/INPUT_MANIFEST.json](../data/scope_quality_rescore_20261016/INPUT_MANIFEST.json), [research/data/scope_quality_rescore_20261016/rescore_comparisons.csv](../data/scope_quality_rescore_20261016/rescore_comparisons.csv)|[tools/thesis_main/analysis/descriptive_statistics_current_20261015.py](../../tools/thesis_main/analysis/descriptive_statistics_current_20261015.py), [tools/thesis_main/analysis/scope_quality_rescore_20261016.py](../../tools/thesis_main/analysis/scope_quality_rescore_20261016.py), [tools/thesis_main/analysis/scope_quality_scoring_20261016.py](../../tools/thesis_main/analysis/scope_quality_scoring_20261016.py)；统计包含名单与逐作答参考目录，空间修订有输入清单和评分脚本；本轮未重跑。|
|931人员当前画像面板 (`worker_931_panel`)|931条：24人、112图、113参考单元、21栋；见面板字段|2026-10-15人员四轴更新；当前loader投影及对应人员输入|固定/条件绑定参考，按面板逐行记录|28份范围待绑定先暂缓；人员分析口径；不等同当前891完整统计|WQ-LS08人员画像，尚未用B8L2重拟合|[结果](../workers/worker_four_axis_update_20261015/quality_panel_931.csv) / [成员名单](../workers/worker_four_axis_update_20261015/quality_panel_931.csv)|[research/workers/worker_four_axis_update_20261015/README.md](../workers/worker_four_axis_update_20261015/README.md), [research/workers/worker_four_axis_update_20261015/FIELD_CONTRACT.json](../workers/worker_four_axis_update_20261015/FIELD_CONTRACT.json), [research/workers/worker_four_axis_update_20261015/scope_records.csv](../workers/worker_four_axis_update_20261015/scope_records.csv)|[tools/thesis_main/analysis/worker_four_axis_update_20261015.py](../../tools/thesis_main/analysis/worker_four_axis_update_20261015.py)；按WQ-LS08冻结的人员面板；脚本可定位，本轮未重跑或改用B8L2拟合。|
|959人员旧条件面板 (`worker_959_history`)|959条旧人员面板记录|2026-10-15之前阶段；旧人员输入和绑定|按旧面板记录|暂缓28份之前的旧纳入层；按旧人员画像标签|WQ-LS08旧画像|[结果](../workers/worker_wq_integration_20261015/quality_panel.csv) / [成员名单](../workers/worker_wq_integration_20261015/quality_panel.csv)|[research/workers/worker_wq_integration_20261015/README.md](../workers/worker_wq_integration_20261015/README.md), [research/workers/worker_wq_integration_20261015/FIELD_CONTRACT.json](../workers/worker_wq_integration_20261015/FIELD_CONTRACT.json)|[tools/thesis_main/analysis/worker_wq_integration_20261015.py](../../tools/thesis_main/analysis/worker_wq_integration_20261015.py)；旧WQ人员面板；脚本和来源说明可定位，本轮未重跑。|
|836旧同目标manual子集 (`manual_836_subset`)|836份ordinary manual；95图|历史同目标统计批次；旧版same-target筛选|原固定目标关系|普通manual同目标条件；实际资格随行保存；旧难度/目标兼容标签|按旧统计包列示的质量分|[结果](../statistics/descriptive_statistics_20261015/records.csv) / [成员名单](../statistics/descriptive_statistics_20261015/records.csv)|[research/statistics/descriptive_statistics_20261015/README.md](../statistics/descriptive_statistics_20261015/README.md), [research/statistics/descriptive_statistics_20261015/HANDOFF.md](../statistics/descriptive_statistics_20261015/HANDOFF.md), [research/statistics/descriptive_statistics_20261015/INDEPENDENT_AUDIT.md](../statistics/descriptive_statistics_20261015/INDEPENDENT_AUDIT.md), [research/statistics/descriptive_statistics_20261015/SNAPSHOT_INPUTS.json](../statistics/descriptive_statistics_20261015/SNAPSHOT_INPUTS.json)|[tools/thesis_main/analysis/descriptive_statistics_20261015.py](../../tools/thesis_main/analysis/descriptive_statistics_20261015.py)；历史同目标集合及输入快照可定位；本轮未重跑。|
|1145历史完整数值评分 (`quality_1145_history`)|1145：1097 manual、48 semi；含多用途/特殊条件|历史评分池；prior_AB冻结分数与来源|逐行固定/条件参考；保留原资格字段|不等于统一正式资格集合；ordinary、semi、门洞、严重例外/历史层分列|WQ/A10/B8L2历史比较|[结果](../quality/quality_ab_feedback_handoff_20261015/prior_AB/results/SCORES_1145.csv) / [成员名单](../quality/quality_ab_feedback_handoff_20261015/prior_AB/results/SCORES_1145.csv)|[research/quality/quality_ab_feedback_handoff_20261015/README.md](../quality/quality_ab_feedback_handoff_20261015/README.md), [research/quality/quality_ab_feedback_handoff_20261015/manifest.json](../quality/quality_ab_feedback_handoff_20261015/manifest.json), [research/quality/quality_ab_feedback_handoff_20261015/quality_ab_human_review_20261015_v1.json](../quality/quality_ab_feedback_handoff_20261015/quality_ab_human_review_20261015_v1.json), [research/quality/quality_ab_feedback_handoff_20261015/BINDING_AUDIT.json](../quality/quality_ab_feedback_handoff_20261015/BINDING_AUDIT.json), [research/quality/quality_ab_feedback_handoff_20261015/prior_AB/REPORT_ZH.md](../quality/quality_ab_feedback_handoff_20261015/prior_AB/REPORT_ZH.md)|[research/quality/quality_ab_feedback_handoff_20261015/prior_AB/src/working_models.py](../quality/quality_ab_feedback_handoff_20261015/prior_AB/src/working_models.py)；保留历史评分、模型源码、人工回执和绑定审计；完整上游生成链未核验为一键复现，本轮未重跑。|
|空间修订影响与重算 (`quality_scope_rescore_20261016`)|506份作答审计；90份完整重算，84份纳入当前质量|2026-10-16空间/参考增量；CURRENT loader及41图审核输入|39新空间+2修订GT；27处缺完整参考；371待绑定|保留原人员/图片门和排除状态；逐作答scope binding状态；缺失原因分列|冻结当前评分；90重算，84加入891|[结果](../data/scope_quality_rescore_20261016/rescore_comparisons.csv) / [成员名单](../data/scope_quality_rescore_20261016/affected_records.csv)|[research/data/scope_quality_rescore_20261016/README.md](../data/scope_quality_rescore_20261016/README.md), [research/data/scope_quality_rescore_20261016/HANDOFF.md](../data/scope_quality_rescore_20261016/HANDOFF.md), [research/data/scope_quality_rescore_20261016/INDEPENDENT_AUDIT.md](../data/scope_quality_rescore_20261016/INDEPENDENT_AUDIT.md), [research/data/scope_quality_rescore_20261016/INPUT_MANIFEST.json](../data/scope_quality_rescore_20261016/INPUT_MANIFEST.json), [research/data/scope_quality_rescore_20261016/record_targets.csv](../data/scope_quality_rescore_20261016/record_targets.csv), [research/data/scope_quality_rescore_20261016/reference_catalog.csv](../data/scope_quality_rescore_20261016/reference_catalog.csv), [research/data/scope_quality_rescore_20261016/rescore_comparisons.csv](../data/scope_quality_rescore_20261016/rescore_comparisons.csv)|[tools/thesis_main/analysis/scope_quality_rescore_20261016.py](../../tools/thesis_main/analysis/scope_quality_rescore_20261016.py), [tools/thesis_main/analysis/scope_quality_scoring_20261016.py](../../tools/thesis_main/analysis/scope_quality_scoring_20261016.py)；空间修订输入、逐作答绑定和评分脚本可定位；本轮未重跑。|

## 结果分母的身份

|计数|含义|证据|
|---:|---|---|
|1145|历史数值评分集合，1097 manual和48 semi；含多用途/特殊层，不能当作正式资格或当前统计分母。|[research/statistics/descriptive_statistics_20261015/INDEPENDENT_AUDIT.md](../statistics/descriptive_statistics_20261015/INDEPENDENT_AUDIT.md)|
|931|人员画像主面板记录数；24人、112图的特定人员分析集合，不是完整质量库存分母。|[research/workers/worker_four_axis_update_20261015/README.md](../workers/worker_four_axis_update_20261015/README.md)|
|836|旧版ordinary manual同目标子集；其参考和纳入条件不同于931/891。|[research/statistics/descriptive_statistics_20261015/INDEPENDENT_AUDIT.md](../statistics/descriptive_statistics_20261015/INDEPENDENT_AUDIT.md)|
|807|空间重算前完整质量快照；之后84份新增合资格分数进入891，不能覆盖旧名单。|[research/statistics/descriptive_statistics_current_20261015/README.md](../statistics/descriptive_statistics_current_20261015/README.md)|
|891|当前完整质量统计集合：828 manual+63 semi；不是由1145简单增减得到。|[research/statistics/descriptive_statistics_rescored_20261016/README.md](../statistics/descriptive_statistics_rescored_20261016/README.md)|

## 版本比较约定

- 区分采集批次、研究输入、目标/参考、纳入规则、辅助标签、方法版本和具体结果快照。
- 只换质量算法时固定作答、输入、参考和可评价集合；新增人员/图片保留旧集合、新增集合和扩展集合。
- 参考/空间修订按同一作答并列旧/新评价条件；修改难度或纳入规则记录移入/移出名单。
- 人员模型记录训练资料、分类依据和评价集合；新增数据重新拟合不能冒称独立预测。
- 临时试跑不升级为正式版本；用于结论、人评、交接或后续依赖的快照需登记，中断结果标明状态。
- 至少3人只是一个必要规则；GT错误、排除、目标空间/参考绑定和完整质量资格仍单独审查。

## 迁移映射

按原路径检索的可读表见 [MIGRATION.md](MIGRATION.md)；机器映射见 [MIGRATION_MAP.json](MIGRATION_MAP.json)。迁移只改变组织路径，不将旧结果改称新版本；未迁移的历史资料仍在原位。

## 原线程与外部来源

线程摘要与可保存证据的对应关系见 [THREADS.md](THREADS.md)；摘要不冒充完整对话。

完整材料登记按主题分列于各主题入口；本页保留算法、代表结果与分母定义，避免重复生成长清单。

