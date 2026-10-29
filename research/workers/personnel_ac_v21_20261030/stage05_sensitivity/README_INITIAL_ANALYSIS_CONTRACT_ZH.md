# 人员、背景、规模与完整类联盟敏感性

代码：`code/analyze_population_sensitivity.py`。算前合同见 `../stage01_design_review/SENSITIVITY_ANALYSIS_CONTRACT_ZH.md`。此目录只读取已保存的融合/评分结果，不新增融合、评分或人员分类。

## 输出与问题对应

| 输出表 | 回答的问题 | 控制与限制 |
|---|---|---|
| MEMBER_PANELS | 同构成或精确固定 D 下，换具体人波动多大 | 每队 Q/结构/状态及 AC 差范围；单事件面板只算覆盖，不纳入变异量均值 |
| BACKGROUND_CHANGES | 固定 X/Z、n/m 后，共同背景改变的作用 | 相同背景类计数的换人，与背景配比改变分开；同时保留意图策略和实际类计数 |
| FIXED_BLOCK_BACKGROUND_STEPS | 固定 X/Z 后加背景、加团队人数怎样响应 | D 为嵌套前缀，同时改变 n/支持门槛；含严格 ABC 共 n 的直接 AC 补桥 |
| FIXED_A_REPLACEMENT_STEPS | 同一个原队扩大 m 怎样响应 | A 身份完全固定，新增替换成员嵌套；与上一表分开 |
| UNEQUAL_DECOMPOSITION | 全小类→全大类的变化，怎样分成等量换类与剩余同类加入 | 三端精确串联；加性量同支持检验 total=equal+addition；父对照背景和加入腿实际公共人员分别保存 |
| COMPLETE_COALITIONS | 完整类别两两叠加或更大联盟怎样变化 | 完整有限联盟；真实 n/类计数/状态和未知共同背景单列，人数效应不假装已控制 |
| SAMPLING_BATCHES | 两批盲抽的方向和幅度有多一致 | 去重后的两个有限样本批次，不当独立总体试验 |
| MEMBER_USAGE | 是否依赖固定少数核心成员 | 每方法实际使用的唯一端点出现比例，以及 X/Z/D 事件曝光次数；不是总体随机抽样概率 |
| PHYSICAL_METHOD_OVERLAP | 不同方法有多少实际复用同实体 | 精确共享团队/物理 AC 对，避免把方法名重复当独立证据 |

每个分析族的 `_POOL_SUMMARY` 先平均面板/路径/父对照，再在图片池内汇总。`SENSITIVITY_IMAGE_BALANCED_SUMMARY` 按图片等权，同时给建筑等权、每指标有效图片与建筑、方向和经验低尾。完整逐事件数值仍引用 stage04_metrics，不重复 431 列总表。

另外按用户的 35 人、三类 8/17/10 示例，在看结果前以容量形状预选 OPPJOINT K3 的 pa4otMbVnkk-06、-42、-44、-11 四图。PRESELECTED_8_17_10_CASES.json 保存选择理由、精确类别成员和逐图成员差异；PRESELECTED_8_17_10_TEAMS 给每图全部 7 队（共 28 队），PRESELECTED_8_17_10_CONTRASTS 给每图全部 21 对（共 84 对），不按效果裁剪。四图同一楼、unknown=0；8 人 C3 的成员完全相同，17 人 C1 与 10 人 C2 各有少量跨图成员差异。不能把这四图写成四个独立建筑或完全相同的 35 人团队。

PRESELECTED_ALLIANCE_WHOLE_DECOMPOSITION 将每图 3 条双类联盟之间的比较，精确连到 B 的整类不等人数父对照：共同背景分别是完整 C1（17人）、C2（10人）、C3（8人），对应 8→10、8→17、10→17 的整类替换。每父对照保留 4 个既有等人数中间队，共 12 个父对照、48 条三端分解链。登记清单带 `_REGISTERED.csv`，不含目标分数；结果表给总差、等量换类、剩余同类加入的每一项，并保存联盟角色方向与 B 原始“小类→大类”方向转换。全 21 条联盟边仍完整保留，单类→双类的纯加入及其它人数变化不与三条交换边混为同一种操作。

## 方向和单位

大多数 `_CA` 指 canonical C−A；DESIGN_LINKS 的 input_orientation_sign 还原原始实验方向。Q 等加性差乘该符号；百分比反向采用比值倒数，无向几何距离不翻符号。

联盟输出另外按冻结角色集合的字典序确定跨楼一致的分析方向，同时保存登记原方向和 analysis_orientation_sign。Semi 没有主 Manual 角色映射，保留其既有类号作为集合标识。联盟 `raw_input_A/C_alliance` 是原登记名称，实际分析端点请读取 `input_A/C_team_key`、`n_A/n_C`、`coalition_A/C_roles`。

几何 BEV 距离为 1−IoU，无量纲；质心距离单位是归一化相机高度 h。背景/路径表的 `effect_difference` 或 `step_difference` 是“AC 差或距离”在两个设计条件之间的差；不能把距离之差误称为两个 C 端点的直接几何距离。

合法记录劳动使用测量器提供的同源字段。相同来源计数向量适用于严格匹配；单一相同来源还允许不等人数，但总劳动同时包含人数作用。记录劳动不是新的前瞻计时，也不是融合 CPU 用时。

背景差分另外保留四队全部已知且来源计数向量相同的严格劳动列。原每次 AC 各自合法的劳动差仍保留，四队控制不以 Q 或几何是否可评决定。对固定 X/Z，记录劳动的绝对秒数差等于同一换入/换出成员的秒数差，D 会抵消；两背景下它应相同，程序逐对核验。相对百分比可因原队 A 的劳动分母改变而变化，不能把这种百分比变化当成 X/Z 实际劳动量改变。预选案例表的合规单队总劳动/每人劳动带 `_single_source`；`known_record_time_total_seconds` 仅是可回连的原始已知日志和，不自动具备跨来源比较意义。

缺失指标始终留空。Q 缺失、观察到融合失败、输出不完整各自分析。不同指标的有效分母不得互相代替。

## 既有端点的精确外部背景匹配

`code/match_existing_outside_backgrounds.py` 另把主 A/B_equal 的 neutral_members_0 与 B_unequal_equal_size_anchor 相连。匹配必须满足同 pool、method、n、m 和完整 canonical X/Z 名单，且 D 实际不同；不是只按人数找类似例子。它保存两套 D 名单和实际类别计数，以及每个指标的两次 AC 差和其差分之差；类计数相同的背景换人与类计数变化分别汇总。先在固定 X/Z 内平均替代背景，再按池/图片等权。

范围是主 A/B_equal，F-only 的严格共同条件由 stage05_funnel_bridge 单列。共同 background_comparison_id 用池、方法、排序后的两个 AC event_id 计算，physical_background_comparison_id 用两个无向 physical_pair_id 计算；主事件兼属 F 时保留标记，最后不得把相同背景对在两个报告中相加当独立证据。D 相同的实体重叠不纳入背景效应。

## 完整性

逐池写入用显式 gzip 上下文和原子重命名；合并时读每个分片到 EOF。最终所有顶层 CSV.gz 再验证压缩完整性、CSV 列宽与 SHA256，生成 FINAL_TABLE_READABILITY.json。SENSITIVITY_RECEIPT.json 同时注明上游测量是否完整、是否处理所有可用池；部分运行不能冒充完整交付。
