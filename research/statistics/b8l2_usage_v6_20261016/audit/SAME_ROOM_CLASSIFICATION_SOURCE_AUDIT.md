# 同房原分类采用接口核验（2026-10-16）

用户本轮明确全部同房分类已看过，直接采用既有分类。正确采用应使用现有分类值及逐条评论，不以`explicit_confirmed`、status非空或完整唯一物理房间ID作为额外准入条件；同时“已看”不应改写原分类中不支持、待定、范围差异或争议的含义。

核查真源：`analysis_results/final_review_summary_20260929/同房分类_原始完整记录.json`、`tools/thesis_main/analysis/materialize_same_room_selection.py`，以及冻结`analysis_results/consensus_research_20260923/inputs/room_registry.json.gz`。原始JSON的groups、candidates、images三个数组与冻结登记完全一致，可直接关联，无需从图像或结果反推同房关系。

260展示组均viewed=True；review_state为52 explicit_confirmed、183 viewed_per_user_statement、25 explicit_discussion。raw_current.physical_same分别为支持156、不支持67、待定37。这是三个不同维度：审阅覆盖、分类内容、保留讨论，不能将前者替代后两者。

materialize脚本assemble未以review_state卡comparable，而依physical_same／main_visual_alignment／extent_alignment／scope。合并拆分后259候选，physical_same_supported为155：79旧comparable，76物理同房支持但范围／主视角等非旧comparable；其余104为不支持或待定。旧low_ambiguity_batch和selection_hold_reasons属于探索选图／预测可比性，不应成为全部同房描述统计的总门。

## 可直接消费的最小接口

每条采用单元保留candidate_id、source_group_codes、image_ids、numbers、subset_scope、excluded_from_this_subset；通过source_group_codes连接原groups的raw_current全部分类值、原评论及interpretation。另明确relation_use（同房总体／可比子组／不同范围对照／不支持／待定），不要只保存单个confirmed布尔值。

组内汇总以各人图记录为测量单位，并单列去重人员数、覆盖图数及图间共同人员；condition和质量用途门独立沿用当前新用途快照。组之间可能重叠，不相加冒充总样本。可直接按用户分类做同房及差异统计，无需先建立全库唯一physical_room_id。没有记录的关系不等价于不同房。

## 必须保留的具体分类含义

- G095：原评论明确同房，按页面顺序拆为12／19／21及22／41两组，分别“可以配对”。G095-S1和S2已正确保留成员；但旧comparable_for_prediction仍False，继承整组主视角不同／范围差异。不能用该旧bool阻断明确子组配对；跨子组保留信息条件差异。
- G155／156／157：用户明确六图11／12／15／16／21／25同一房间，合并为G155，只计一次采用单元。此为明确人工合并，可作同房总体，不是通过传递闭包猜测；跨三原子组的范围相近性仍单列未判，不能从同房推成同范围。
- G004：采用8／15／16，排除7；G174：采用28／44／80，排除2。不能恢复排除成员到可比子集。
- G196：仅61／82为评论支持子组；42被评论指出在房间外且疑OOS。G236：仅1／6／18明确可归一起；14为门洞、16范围不同。保留被排除成员作差异资料，不能当同范围样本。
- G172／189／214：原组保留，范围适用性不明；proposed_core是解释者建议，不是已明确采用子集，不应自动裁掉门洞或范围边界图。可按原同房分类描述并单列范围不确定。
- G184：67拍摄主空间在浴室，所标空间可能跨室；其余八图仅建议子集，未获明确同范围判断。G209：只有46可见门后凸墙，其余视角信息不足，保留信息差异。
- G176：原评论以历史06分簇少作为优先条件。不能查询实际分数／分歧后择优纳入；可作含结果暴露说明的同房描述，不能据此做无偏选样验证。

## 本次检查时的新采用文件状态

目前可见`research/same_room/same_room_b8l2_v6_20261016/usage_v3`，版本为same_room_usage_adopted_20261016_v3，已接入新质量1787但关系仍沿用旧confirmed分层：门洞candidate_edges23、scored19、direct_confirmed1、legal_quality_pairs0，B8L2 positive manual confirmed40。此文件并非本轮“全部既有分类采用”完成的证明。应等同房原线程的新明确采用文件落盘，再按上述原分类核对成员、关系用途、分母和统计，不能把v3旧关系结果改名为新采用结果。

本审查未改同房代码、源分类、资格或共享文档。地图与README沿用包内支撑审计，不新增全局入口，由主线程统一登记。下一步仅核查新采用输出与原分类的一致性；不新增人工审阅或唯一物理ID前置要求。
