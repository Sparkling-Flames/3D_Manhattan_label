# 方向可读表的字段支持

- 方案与角色：method + condition + source_role_key + target_role_key；role key含历史family/类数，跨折不按同编号拼接。
- 人员与背景：成员并集说明覆盖；每折名单与历史中心见FOLD_DIRECTION_ROLES_MEMBERS.csv。精确ABC及D/X/Y/Z通过背景索引的event_ids连接冻结设计。
- 原Q幅度：同一事件六端点Q共同可评，within=|B−A|、cross=(|C−A|+|C−B|)/2、extra=cross−within；有符号BA/CA/CB/CS另保留。
- 原转折、短转折、近共线、底面、方向和高度列：各分项自身六端点有限支持；这可以含Q不可评分的候选几何。不要直接把这些均值与Q均值当同样本机制对照。
- 新增“共同Q结构_”列：从QUALITY_STRUCTURE_COMMON_SUPPORT.csv按同方案/条件/层/两端role key精确连接；六队先均Q可评，再使用该分项有效值；events/pairs单列。无匹配联合行时为缺失，不回退成原较宽分项。
- Q/T：六端点Q及记录时间共同可用，且所有团队时间同一来源语义；劳动比为逐事件/配置/图对/楼的算术汇总，不是几何均值或并行时长。
- 失败与恢复：全部尝试分母；缺失Q不补零。降质>5分使用共同Q支持，与失败分母不同。
- 正向图对比例：先在图对内按配置汇总，再判断该图对额外幅度是否严格大于零；不同于原始事件的升质比例。

本补充只连接与说明已保存表，不改原事件、大表gzip或评分。
