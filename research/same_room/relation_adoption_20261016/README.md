# 全部已有用户同房分类：统一关系采用交付

2026-10-16。**已冻结**共同入口[CROSS_MODULE_RELATIONS.json](CROSS_MODULE_RELATIONS.json)，最终版本`same_room_user_working_classification_20261016_v2`，替代早期v1开发交付。统计与同房分析应消费同一[relations.json](relations.json)，不各自根据状态字符串定义纳入规则。本版本的关系采用规则不再继续修改。

用户已明确全部同房组都看过，直接按已有分类完成。260原组全部保留，原字段与CSV逐项核对：物理同房支持156组、不支持67组、待定37组。52个`explicit_confirmed`、183个`viewed_per_user_statement`、25个`explicit_discussion`仅为原始状态来源，不是新的排除门。没有把全部260组自动确认为同房。

## 信息损失与修正

旧`same_room_similarity_20261003.relation_index`仅让`explicit_confirmed`进入可比主层；同房后续`confirmed_relation`又在该状态上二次筛选。原候选层没有丢失全部人工分类，但主分析硬门挡住了已有正向工作分类。旧40图对和门洞新增0保留为旧严格层历史，不能继续代表当前全部分类。

仅因状态被挡住、原候选已支持同房且范围可比、非OOS待定的24个候选为：G002、G003、G004、G027、G063、G067、G068、G071、G076、G080、G091、G092、G108、G109、G117、G168、G197、G201、G202、G222、G228、G234、G235、G249。其中18个原状态为`viewed_per_user_statement`，另6个为`explicit_discussion`。见[逐组清单与原话](status_string_blocked_candidates.csv)。

G002保留02、03、05、10、17五图为用户同房组；原话明确“虽然房间一致，但是视角导致难标”，困难视角不因此成为物理异房或禁止比较。此处采用既有工作分类，不重新要求用户确认。

候选层还存在拆分后的字段继承损失：G095-S1/S2原话明确两个子组内部可配对，但仍继承原大组“视觉不同、范围不同”，已恢复子组工作可比性；G196保留61/82厕所子组，42按原话“可能在房外”保存实质争议，不补成同房；G236保留明确可归一起的01/06/18工作子组，14门洞及16范围不同单列。后两组采用的是评论支持的工作分组，不冒称精确几何范围已认证。

同时恢复原字段本身已有的信息：G172原视觉一致、范围预期相近，备注71站在门洞不单独否定范围；G209视角可见信息不同不等于标注目标范围不同。G214涉及41的范围例外保留，其余直接组内配对按原字段工作分类；不是要求用户再次核验。G155/156/157明确合并六图为同物理房间，原三对子组的范围分类仍保留，跨原子组不外推范围相同。

## 独立保存的判断轴

- **物理同房工作分类**：使用原组正向字段与原话；否定、待定、实质相反证据仍保留。原组与候选子组各有来源，不以不存在全库稳定物理room_id为由丢弃用户分组。
- **范围可比**：已有视觉/预计范围字段或明确子组配对评论；与物理同房分开。原物理组中被排出比较子集的视角仍留在物理组，不能因范围不同自动改为异房。
- **难度相似或不同**：原样保存，不要求难度相似才能比较。困难、不优先、存在明显信息差异分别留记录。
- **OOS与实验评分**：关系OOS待定单列；主可比采用层暂不包含该关系条件。最终质量还必须经过共同用途表的`quality_usable`、固定参考、同条件共同人员等门。合法时间和几何稳定性不由质量门一并删除。

`scope_comparable`仅表示工作范围判断；`analysis_layer=user_classified_comparable`还要求关系无OOS待定。`user_classified_other_scope`保存已采用物理同房、但比较范围不同/未明或OOS待定的层。`content_disputed`、`not_supported`、`physical_pending`均保留具体原因；它们不是“未人工分类”。

所有关系只由直接列出的用户原组、明确子组或原话直接合并的G155/156/157六图组生成，不通过不同用户组的关系链扩张。G编号是版本化用户分组身份，可能重叠，不宣布为全库唯一物理房间ID。不同来源的相反判断保留冲突，不能取分数较高的一边。

## 文件和复现

- [original_groups.json](original_groups.json)：260原组、原字段、原话、看过依据、解释和原图号。
- [candidate_adoption.json](candidate_adoption.json) / [CSV](candidate_adoption.csv)：259个候选的原/新工作判断及子集修正理由。
- [relations.json](relations.json) / [CSV](pair_adoption.csv)：直接图对及逐条来源，物理/范围/难度/OOS/实质冲突分开。
- [SUMMARY.json](SUMMARY.json)、[字段合同](FIELD_CONTRACT.json)：实际计数与消费者含义。

复现：`python -m tools.thesis_main.analysis.same_room_relation_adoption_20261016`。测试为`tests/test_same_room_relation_adoption_20261016.py`，涵盖状态与难度不作门、原否定/待定保留、无跨组传递、子组可比与原物理组分离。未改人工原始文件、共同评分、参数或全局目录。

同房实际重算见[工作分类实证报告](../same_room_b8l2_v6_20261016/working_relations_v4/README.md)。统计可立即消费本统一冻结关系文件，质量/时间需另接各自真实分母；不能把关系数量当作有评分的图对数量。
