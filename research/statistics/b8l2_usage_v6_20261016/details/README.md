# 新用途版的人员、图片、场景、关系与时间查阅

**关系统计已由[按已有人工分类的新版](../details_room_adopted_v3/README.md)接续。** 本目录21页与数值保留为旧严格关系层；此前把全库物理ID缺失列为房间统计缺项的说明已纠正。已有260组人工分类完整，当前按版本化工作分组统计，无需用户重新分类或确认。

父级用途版本`b8l2_scene_usage_v6_20261016_v2`；输入固定v6，质量1787份。独立工作簿为[B8L2细致统计_人员图片与关系组.xlsx](B8L2细致统计_人员图片与关系组.xlsx)，视觉核验见`DETAILS_WORKBOOK_VERIFICATION.json`。全部28张机器表见[tables.json](tables.json)及[FIELD_CONTRACT.json](FIELD_CONTRACT.json)，需求/缺口与工作表位置见[coverage_matrix.csv](coverage_matrix.csv)。

`worker_inventory`保留全部27人，`image_inventory`保留全部259图；W019和W026的提交仍因原历史不接受而没有合格来源，不被填成低分。人员总览仅展示计数，质量与时间按条件及采用层分别描述，不把manual/semi/oos混成一个人员成绩。

`worker_condition_stats`、`image_condition_stats`、`worker_difficulty`、`worker_special_axes`分别提供人员/图片和条件、简单/中等/困难/专项、门洞/OOS等图轴的n、均值、中位数、样本SD和四分位数。无观察格n=0且估计为空；单值SD为空。来源n不等于完整质量n，完整质量也不等于独立人数。

`time_quality_focus`同时提供B8L2、来源秒、已核同目标秒的边际分布，以及实际非缺失交集的两侧分布。共有n分别为1107和440，不能把前者全部叫同目标耗时。质量不可用不自动删除合法时间，未使用lead_time补缺失。

`room_*`表保留候选关系、原始证据、逐视角贡献、直接图对及未关联图片。[ROOM_SEMANTICS.md](ROOM_SEMANTICS.md)解释为何不能把G编号称为已确认物理房间；作答等权与图片等权分别报告，同一人的多个视角不被当作多个独立人员，重叠组不能相加。

`calculation_ledger`、`record_lookup`、`worker_usage_summary`、`scene_usage`和原因表对应逐条实算/待定/不可算、用途、27人覆盖和多重排除。所有OOS的正常质量字段为空；诊断值不进入任何质量均值或画像。`worker_primary_reasons`每对象一个主原因；`worker_reason_hits`可重叠，不能加成排除总数。

[e9-16资格证据](E9Z16_ELIGIBILITY_AUDIT.md)只追溯该图人工简单标签与继承表示门的关系；旧审计中其它人员、门洞和时间计数保留历史身份，当前计数以本目录表为准。物理房间身份、完整参考和未绑定目标的缺口仍如实保留。
