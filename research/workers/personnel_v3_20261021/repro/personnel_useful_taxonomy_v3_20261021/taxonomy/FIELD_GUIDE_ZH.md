# 分类交付字段与恢复入口

## 标签主表

`ALL_METHOD_LABELS_LOBO.csv.gz`：两方法×两条件×22个建筑×62人；其中Semi只有12栋实际目标建筑，另10折为统一接口而保存，不计入Semi验证分母。`ALL_METHOD_LABELS_ALL_DATA.csv`是最终描述标签，不能用于目标建筑验证。

| 字段 | 含义与使用规则 |
|---|---|
| method | V3_BEHAVIOR为结构类；V3_JOINT_QT为结构×本条件Q/T联合类。不可只凭M/S/J/K前缀合并方法。 |
| condition | manual / semi；分开形成和评价。 |
| heldout_building | 目标建筑；该楼被排除于特征、缩放、聚类和内侧选型。ALL只用于描述。 |
| worker_id | 原仓库匿名人员编号。 |
| coarse_label / fine_label | 每折同一输入、同一Ward树上的祖先/叶子切割；编号不保证跨折语义相同。 |
| coarse_k / fine_k | 实际选中类数。两者相等表示没有独立细分层。 |
| known / missing_reason | 机会不足或特征缺失时unknown；不能填0/常规类。 |
| selected_family | TURN / STRUCTURE / SCALE / JOINT / CONTEXT，或EQT / GEQT / CQT；见下表。 |
| label_stage | all_data_descriptive 或 outer_building_excluded_inner_selected。 |
| n_images / n_buildings / n_records | 目标楼之外的可比较普通行为历史支持量。 |
| base_supported | 至少12图、4楼，基础几何特征完整。 |
| context_supported | base基础上简单和复杂机会各至少3图、2楼。 |
| qt_supported | base基础上本条件Q至少8图Manual/4图Semi及3楼；T至少6图3楼。 |
| origin | 原来源，不作为新分组的心理/能力解释。 |

## 连续特征

所有结构残差均先按同图×条件×参考×层中心化，再个人建筑均值后建筑等权。

| 字段 | 定义 |
|---|---|
| turn_history | 点对数减近共线节点数后的相对残差；是表达代理，不是真实必要结构计数。 |
| short_history | 沿用原周长4%且两端转角至少15°的短边数残差。 |
| redundancy_history | 转角≤5°节点数残差；保留连续值及实际非零机会计数。 |
| area_history / height_history | 相机高度归一的底面面积/推导高度对数残差。不是实测米制体积。 |
| simple_turn_history | 同图人员转折中位数<6的机会中turn_history均值。 |
| complex_turn_history / complex_short_history | 中位数≥6的机会中的表达；这是结构条件C，不是五域D。 |
| q_history | 本条件、原资格合格B8L2减同图人员均值，再建筑等权。 |
| q_downside | q_history减每栋个人相对Q的10%分位数后建筑平均；不可与旧q_downside无说明混用。 |
| t_history | 原来源秒数取对数，在同图×origin×time_source_kind中心化，再建筑等权。 |

| family | 实际形成分类的域与字段 |
|---|---|
| TURN | E：turn、short |
| STRUCTURE | E + R：turn、short、redundancy |
| SCALE | G：area、height |
| JOINT | E + R + G |
| CONTEXT | C：simple_turn、complex_turn、complex_short；另加R、G |
| EQT | E + Q：q_history、q_downside；T：t_history |
| GEQT | E + G + Q + T |
| CQT | C + Q + T |

每域等权，域内字段分摊域权重；稳健中位数/IQR标准化、IQR退化时使用标准差、截断±3、Ward聚类。每类至少3人。每折实际连续对照列见 `RAW_PREDICTION_EXACT_FEATURES.csv`。

## 解释与证据表

| 文件 | 用途 |
|---|---|
| CLASS_DEFINITIONS.csv | 中文类名、完整成员、支持、粗细层级和缺失原因。 |
| PERSONNEL_LABELS_EXPLAINED.csv | 全数据人员标签，加旧Q/T/D/scope/Semi辅助变量、机会计数和原支持flag。 |
| MANUAL_LABELS_EXPLAINED.csv / SEMI_LABELS_EXPLAINED.csv | 可单独取得的条件人员表，增加中文类名、解释及是否有独立细层。 |
| CLASS_AUXILIARY_DOMAINS.csv | 仅在各域支持flag为真时计算解释均值；scope裁定正确率有独立机会分母。 |
| OUTER_SELECTION_DISTRIBUTION.csv / OUTER_STABILITY_SUMMARY.csv | 有实际目标建筑的族/类数分布、与ALL分区ARI；不把无目标Semi折计为验证。 |
| MEMBER_COASSIGNMENT_STABILITY.csv及JOINT版本 | 每人的同类成员集合在外折与ALL之间的Jaccard；不按编号匹配。 |
| OUTER_CLASS_ROLE_MAP.csv.gz | 每折训练中心高/低角色，用于跨建筑解释方向。 |
| RAW_GEOMETRIC_PAIRS.csv.gz | 137,480对原答的同点数角距离、底面差、点数及来源；对象ID可追回原答。 |
| RAW_GEOMETRIC_SIMILARITY_* | 类内减类间，负值表示更近；质量正确性与融合互换性另判。 |
| RAW_PREDICTION_* | 楼外原答/质量/时间响应预测；共同支持、建筑等权。R²或MSE变化不等于节省工时。 |
| SEMI_REDUNDANCY_SUPPORT.csv / SEMI_REDUNDANCY_VISIBLE_RECORDS.csv | 全数据近共线组的完整机会分母与非零实际原答；不以楼外known筛掉失败机会。 |
| RESEARCH_INPUT_INVENTORY.csv / INVENTORY_RECONCILIATION.json | 全部nonOOS对象闭合、不同层与资格切片；切片允许重叠。 |

`SEMI_REDUNDANCY_GROUP_RECORD_OPPORTUNITIES.csv`是早期按楼外known过滤的解释候选表，不用作完整机会分母；正式分母使用上述SUPPORT表。原初始化12条证据另有 `SEMI_REDUNDANCY_INITIALIZATION_SUPPORT.csv`，正式完整记录表也保存这些字段。

## 可复现与分批保存

`discover_behavior_classes.py`与`discover_joint_qt.py`按条件保存；正式结果再由`finalize_selection.py`统一冻结。最终标签文件SHA收在`LABEL_FREEZE.json`。评价和解释均为派生表，更新它们不会改冻结标签。

`DESIGN_BEFORE_FUSION.json`保存初始K2..8计算登记；`CAPACITY_RANGE_AMENDMENT.json`记录拓展到实际容量界，`CLASS_CAPACITY_LIMITS.csv`逐族逐折列最大支持K。初始暂存与partial不属于正式交付。

从已有内侧损失表恢复标签无需重跑融合或完整分类。输入清单及hash在`INPUTS_AND_CHECKSUMS.csv`，主脚本版本及特征合同随包保存；父目录的团队端点与事件由其独立恢复清单定位。本分类包不复制大型旧团队缓存和原图全集。
