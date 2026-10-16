# 按已有人工分类的详细统计

本版直接采用已完成的260个人工原组分类与259个拆分/合并工作单元，关系版本为`same_room_user_working_classification_20261016_v2`。不以单独的explicit_confirmed状态或缺全库唯一物理房间ID阻挡已有分类；不同房、不同范围、明确待定与具体争议继续分层。准确口径见[ROOM_SEMANTICS.md](ROOM_SEMANTICS.md)。

当前工作簿为[B8L2细致统计_人员图片与关系组.xlsx](B8L2细致统计_人员图片与关系组.xlsx)，保留原人员、图片、难度、场景、时间和逐条用途查阅，并加入人工原组总体、人员×原组及260组完整登记。每组/每人×组/逐视角仍提供实际n、均值、中位数、样本SD、四分位数及质量/时间共有集合；没有当前库存的组明确n=0，估计为空。

|单位|全部登记|有当前库存|无当前库存|
|---|---:|---:|---:|
|人工原组|260|166|94|
|拆分/合并工作单元|259|163|96|
|直接关系图对|777|268对两端均有库存；274对仅一端|235对两端均无库存|

工作单元有76个按已有分类范围可比、79个同房其它范围、67个不支持、37个物理待定。逐对层为381可比、291同房其它范围、67不支持、36待定、2具体争议。这里只是不同单位的登记覆盖，不是全库唯一实体房间数，不能跨层相加。见[分类采用覆盖图](figures/人工房间分类与采用覆盖.png)及同名SVG/CSV。

机器表见[tables.json](tables.json)和[FIELD_CONTRACT.json](FIELD_CONTRACT.json)，覆盖导航见[coverage_matrix.csv](coverage_matrix.csv)。`room_group_*`是拆分/合并工作单元，`user_original_*`是原始人工分组，两种视图保留重叠，不相加；`room_direct_pair_*`为统一清单的直接边，没有跨组传递补边。完整采用冻结于[RELATION_ADOPTION_INPUTS.json](RELATION_ADOPTION_INPUTS.json)。

输入3152作答/259图/27人、质量用途1787、来源有效时间1750、已核目标时间440及质量/来源时间共有1107均保持。原B8L2公式、参考、分数、源分类及门洞/OOS用途规则不改。人员/图及质量字段仍分条件和用途，OOS诊断不进入正常质量均值。

[旧21页严格关系层](../details/README.md)另存，本目录为当前分类采用统计。未重新索要用户的完整分类，也未将260组全部改为同房确认。核验与工作簿视觉检查以本目录`CHECKS.json`和`DETAILS_WORKBOOK_VERIFICATION.json`为准；原始e9-16资格问题见[e9-16追溯](../details/E9Z16_ELIGIBILITY_AUDIT.md)。

23张工作子组外图片中，1张仍有原组分类，另22张无原组成员记录；`room_unlinked_images.original_user_group_ids`逐图列明。工作组外不等于没有分类，也不等于已确认异房。

最终交付采用冻结v2，24页及图表均已视觉核验，30张临时检查图片和预览目录已清理。独立核验见[ADOPTION_STATISTICS_AUDIT.md](ADOPTION_STATISTICS_AUDIT.md)：8张关系统计表共13050个分层单元的分母、均值、中位数、样本SD、分位数、视角权重及质量/时间共有集合全部匹配。15项定向测试通过；未扩展无关检查。关系原字节归档及只更新标签的回执见[RELATION_FREEZE_ADOPTION_AUDIT.json](RELATION_FREEZE_ADOPTION_AUDIT.json)。
