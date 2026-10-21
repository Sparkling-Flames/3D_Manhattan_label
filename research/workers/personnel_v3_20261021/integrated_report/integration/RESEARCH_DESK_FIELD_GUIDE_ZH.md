# 接入研究台：人员类别、团队、事件和用途结果

本轮保留不同方法和不同阶段的身份。旧 M/SP/A2、Rnew2、F01、多变量 QTD / QTscopeSemi，以及本轮 `V3_BEHAVIOR`、`V3_JOINT_QT` 是并列方法；它们不是一套可互换编号的统一树。本文件解释最重要的连接键和口径，全部数值仍以原始完整表为准。

## 1. 人员标签：先选择方法、条件与验证折

入口为 `taxonomy/MANUAL_LABELS_EXPLAINED.csv`、`SEMI_LABELS_EXPLAINED.csv`；完整楼外标签为 `ALL_METHOD_LABELS_LOBO.csv.gz`，全数据描述标签为 `ALL_METHOD_LABELS_ALL_DATA.csv`。

|字段|使用方式|
|---|---|
|`worker_id`|人员标识。须与 `condition`、`method` 一起连接，不能将 Manual 标签直接当作 Semi 分类|
|`method` / 事件中的 `method_id`|分类方法身份，显示名之外必须保留|
|`label_stage`|区分全数据最终描述与目标建筑排除后的验证标签|
|`heldout_building`|验证目标建筑；对目标图片只能连接该建筑对应折，不可回填 ALL 标签|
|`selected_family`、`coarse_k`、`fine_k`|该折实际输入族和层级规模。不同折会选出不同切割|
|`coarse_label`、`fine_label`|仅在本方法、本条件、本折内部解释；`.1` 不必表示有额外细分。粗细分区相同时不能计算“细分增量”|
|`known`、`missing_reason`|没有机会、历史不足或时间缺失保持未知，不归入零值或常规类|
|`n_records`、`n_images`、`n_buildings` 及各域机会字段|实际证据支持；近共线非零机会另见人员解释表，不以全部历史图片数冒充该行为的重复次数|
|`turn_history`、`short_history`、`redundancy_history`|同图相对表达的楼外历史，分别为有效转折、短转折边和近共线节点；不能把三者合成“点越多越细”|
|`area_history`、`height_history`|面积、高度对数的同图相对历史；是尺度倾向，不是直接正确率|
|`q_history`、`q_downside`、`t_history`|本条件合格质量、低尾和来源内对数记录时间历史。它们与旧连续基线的 `q_effect` 等字段具有各自明确的输入定义|

`OUTER_CLASS_ROLE_MAP.csv.gz` 把每折的高/低表达等训练角色单独记录。跨建筑汇总可用这个角色或训练侧连续均值，不能直接将所有 `M1`、`S1` 视为同一种几何含义。`CLASS_DEFINITIONS.csv` 与 `CLASS_MEMBERS_AND_FEATURES.csv` 则用于呈现最终 ALL 名单。

普通行为建模、门洞/特殊范围观察、GT暂停及人员筛除保留在 `RESEARCH_INPUT_INVENTORY.csv`。人员有行为标签不代表取得该图片的评分或正式组队资格。

## 2. 团队端点：同一个实际集合只连接一次

每批 `ENDPOINT_SCALARS.csv.gz` 是质量、结构、时间和状态的完整端点；`ENDPOINT_GEOMETRY.csv.gz` 保存相同 `team_key` 的几何。最终交付的合并分片与批次 ZIP 是替代下载方式，不能相加计数。

|字段组|含义|
|---|---|
|`team_key`|冻结任务池加排序后的实际成员集合身份。确定性融合中，不因加入顺序不同而重复终点|
|`pool_id`、`image_id`、`condition`、`reference_id` / `reference_version`|任务、条件及参考绑定，不跨参考版本拼同队|
|`k`（设计表为 `n`）|实际总人数；`member_workers`、`member_object_ids` 是完整成员和原答对象|
|`endpoint_origin` 及批次回执|区分历史复用、补导缺失几何和本轮新原生端点|
|`complete_evaluable`、`score_status`、`geometry_status`、`below_four`、`connection_available`、`location_unresolved`|成功、失败与不适用状态；缺分数不补零，失败仍进入事件分母|
|`minimum_support`、`node_supports`、`identity_groups_n`、`nodes`|实际投票门槛、选中组支持、身份组数和输出节点数；节点总数相同不代表保留相同局部结构|
|`source_time_total_seconds`|全部成员来源标注记录时间之和，缺任一成员则未知|
|`source_time_known_n`、`source_time_known_sum_seconds`|已知人数与已知部分之和；部分和不能当完整总工时|
|`time_source_kinds`、`time_source_table`|时间来源和单位解释；混合来源不自动进入兼容时间的主比较|
|`target_time_*` 与 `source_time_*`|分别保存，不因来源记录可用就声称重放了目标图原始日志|

## 3. 质量分项和几何单位

|分项|单位及解释|
|---|---|
|`B8L2`、`D10`|冻结质量分，0–100；B8L2为主，D10为敏感性|
|`iou_2d`|底面面积交并比，0–1；只看它会遗漏形状、方向与局部结构变化|
|`IoU3D100`|冻结的角点均高三维代理 IoU×100；不是实测三维体积的认证|
|`S_bottom_deg`|底面边界的球面双向距离，度|
|`dir`|候选相对其自身最佳正交轴的方向残差，度；不是相对GT的整体旋转角|
|`Hmean`、`Hcenter`|沿周长平均高度比的绝对残差、中心化局部高度残差，无量纲|
|`omission`、`extension`|相对冻结参考底面的遗漏比例、扩展比例；不自动完成范围政策或真实细节的语义裁定|
|`height_mean_ratio`|冻结引擎平均高度比，无量纲；与 `height_mean_h` 不同|
|`height_mean_h`、`height_min_h`、`height_max_h`|由上下射线推导的地面至顶面总高，以相机高度为单位|
|`centroid_*_h`、`bounds_*_h`、BEV/顶部距离|相机高度单位；面积为相机高度平方，不是米/平方米|
|`top_y_mean_px`、`bottom_y_mean_px`|预处理ERP坐标的像素位置；图中应保留对应图像尺寸|
|`ref_node_recall_5/9`、`ref_edge_recall_5/9`|既有5°/9°参考节点、边诊断召回。不能与整份原答9°/12°分簇或融合内部7.5°对应参数混用|
|`fusion_turn_n`、`fusion_short_turn_edges`、`fusion_redundancy_n`|从已冻结输出几何提取的有效转折、短转折边、近共线节点；这些是新增观察字段，不改变融合与评分|

结构派生沿用本轮记录的5°近共线定义；短边长度小于周长4%，两端转折各至少15°。原生分数的公式和参数仍来自现有合同；代码身份见 `NATIVE_CONTRACT_MAIN_IDENTITY.json`。旧完整事件字段字典也单独交付，并保留其历史阶段身份。

## 4. 替换事件：稳定性与方向收益分开

ABC事件中，A是原队，B保持类别人数构成换成员，C改变构成。`common_background`、`outgoing_block_X`、`same_count_block_Y`、`changed_count_block_Z` 给出实际背景与三个块。

- `m_AB`、`m_AC` 是两次相对A的真实换人数；严格比较要求共同背景、n和m相同。
- `m_BC` 是B与C的净换人数，常更小，不能偷换成原来的m。
- `composition_turnover_AC` 是类别席位改变数，与实际换人m不同。本轮 `PURE_BLOCK` 明确要求单类到另一类、席位转移=m；普通大m事件不自动满足。
- `A_counts`、`B_counts`、`C_counts` 是完整类别人数向量，保留零项；`*_parent_counts` 与 `within_parent_fine_change` 用来识别真正固定父类的细分增量。
- `event_id` 标识方法/层级事件；`physical_triple_id` 用于识别跨方法或层级重复使用同一实际三元团队的情况。方法间重复不等于多次独立实验。
- `same_*` 为B−A或A/B距离，`cross_*` 为C−A或A/C距离，`net_*` 为C−B或B/C距离。
- `common_quality_within_abs`、`common_quality_cross_abs` 使用同一三臂成功分母；`abs_Q_change_advantage` 为跨构成绝对变化减同构成绝对变化。正值只表示前者变化更大，不表示更好。
- `common_geometry_*`、`common_expression_*` 对几何/结构也使用共同可比较分母。不可对应、节点数不相同等机会单列，不把它们当零距离。
- `A_failure`、`B_failure`、`C_failure`、大质量损失及失败细型保留。不能只筛 `all_complete` 后宣布失败风险小。

单独跨类块只有A/C，仍可估计其有方向作用；不能凭不存在的B构造同类可互换结论。

## 5. 配置覆盖、成员覆盖和顺序覆盖

配置ID必须包含方法、层级、任务池、实际合法已知成员域和n；同一向量在不同成员域下容量可能不同。完整成员数为各类 `C(容量,配额)` 的乘积；总池规模为 `C(U,n)`，以精确十进制整数字符串保存。超大整数不要经浮点数再写回。

主面板固定背景后完整枚举12选6，共924组；F01补充在自己的合法域完整枚举全部 `C(U,12)`。二者都与整个原池的全部成员组合分开。全员集合或某个只有一支实际队伍的构成，不提供类内成员波动证据。加入顺序只在已有嵌套人数路径上研究，未枚举全部排列；确定性相同终点只计算一次。

## 6. 实际选队与响应模型

`utility/` 保存每面板的全部候选集合、各策略选择概率、人数向量分布、实际端点及时间。类别策略遇到并列最优构成时，对其全部实际成员集合均匀积分，不挑一支最好队代表构成。`cross_panel_LOBO` 与 `historical_only` 的训练身份分开；目标建筑均排除。

质量均值是成功条件均值；若某策略在一个面板全部失败，该格Q保持未知，但完整失败和时间仍在原分母。比较时须同时读质量可比较面板数、全部候选失败分母和兼容时间支持。

`response/` 的组间方差占比是有限面板描述；细分会机械增加这个量。楼外预测R²则检验迁移表达能力。两者均不能换算为实际节时比例；节时只来自 `utility/` 实际选择的记录秒数。

## 7. 恢复顺序

先取得独立下载目录与输入/标签清单，再下载需要的完整事件和对应端点分片。无需下载全部ZIP才能读取核心表。按每个回执检查SHA256、完整EOF、行数及主键集合后再合并；未完成临时文件、运行缓存、重复格式和原图全集不纳入研究台数据层。
