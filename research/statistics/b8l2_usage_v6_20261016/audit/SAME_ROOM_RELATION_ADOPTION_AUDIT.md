# 统一同房关系采用独立核验（2026-10-16）

**历史开发版本说明：** 本文件记录v1开发交付，已被正式冻结的`same_room_user_working_classification_20261016_v2`替代。当前关系tier为381可比／291其它范围／67不支持／36待定／2争议；当前消费与统计审计见`../details_room_adopted_v3/ADOPTION_STATISTICS_AUDIT.md`。下文v1计数仅保留审计过程，不作为当前分类入口。

新接口`research/same_room/relation_adoption_20261016/CROSS_MODULE_RELATIONS.json`（same_room_user_working_classification_20261016_v1）已独立核验通过。原260组完整内容与原始分类JSON一致，259采用候选、777唯一图对均有明确组／子组来源。

|关系层|图对数|
|---|---:|
|用户分类可比范围|306|
|用户分类同房、其它范围|366|
|不支持同房|67|
|物理关系待定|36|
|内容争议|2|

独立从原组成员及明确候选成员重建图对集合：原组内766唯一图对，加11条来自G155明确六图合并，恰为777。每条evidence的成员均在对应原组或采用候选内；未通过共享某张图而传递生成关系。G155跨原子组有物理同房采用依据，但不会自动升级为范围可比。

负例未被“全部看过”升级：仅有负面证据的图对保持not_supported；没有正／负判断的保持pending。2条content_disputed均为G196的42分别与61／82配对，保留评论与原整组支持的内容冲突。

四个scope修正与原评论一致：G095-S1、G095-S2组内可比，其六条跨子组边保持other_scope；G196仅61／82；G236仅1／6／18。原建议proposed_core未擅自变为采用子集。共28个非explicit_confirmed候选获正常采用（18 viewed_per_user_statement、10 explicit_discussion），旧status未继续卡门；这不改变原分类的负面或待定内容。

本核验仅确认关系采用与已有分类一致。质量仍需每条作答的当前quality_usable，OOS只诊断；时间按既有来源与目标时间门。不同范围可以作明确分层描述，不冒称同范围几何对应。唯一物理房间ID不是统计前置要求，组间重叠也不能直接相加为总样本。

机器结果及争议图对精确ID见`SAME_ROOM_RELATION_ADOPTION_AUDIT.json`。未修改采用规则、同房代码、源分类或共享文档；后续统计应只消费该统一采用接口，而不另建分类规则。
