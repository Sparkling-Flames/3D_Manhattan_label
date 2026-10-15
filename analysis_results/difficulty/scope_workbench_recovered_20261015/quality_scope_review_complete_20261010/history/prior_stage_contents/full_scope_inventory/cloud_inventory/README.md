# 全图范围差异线索库存（2026-10-10）

## 结论与边界

- 已覆盖当前已标注基集的 **259 张图片、3152 条作答**。每张图均在 `all_259_images.csv` 中，包括未命中图片；不再限旧24图、多人或多数门槛。
- 完整读取1157条历史评语索引，并接入35份可解析JSON来源，共得到 **1648条按“图＋对象＋原文”去重的文本、6340处来源**。其中1607条属于259图基集，另41条属于21张基集外历史图，独立保留。
- 169图有宽关键词线索；加入任意一条历史作答相对当前选定GT的面积对称差不低于0.30后，203图进入宽复核队列。其余56图仍在全表与 `no_hit_images.csv` 中。
- **203是检索队列，不是已确认的真实目标范围差异数量。** 关键词会命中墙面细节、普通点位错误、历史已修正的GT问题；未命中也不能证明与GT同范围。未逐张重新人工裁定所有轮廓。
- 所有结果只来自云端已有资料与当前Git同步快照；未读取用户电脑。快照：`d905d7dbb31dccabb3b190cb317d38b034b7cd65`。

## 已找回用户记忆中的图片

**uNb9QFRL6hY-88**，`uNb9QFRL6hY_fd8d4da92ec14b668ed3d2986616bd14`。

原图级评论：

> 这图很困难,存在不同的标注区域,主要还是玻璃洗澡区域,标外面还是标里面的墙角,还有是否标马桶区域,这个gt标的范围很大,把左右两侧的走廊都标了,目前没有标注者这样标

精确来源：`analysis_results/review_final_20260928/evidence/latest.json`，JSON Pointer：`/image_decisions/uNb9QFRL6hY_fd8d4da92ec14b668ed3d2986616bd14/comment`；`second.json`、`previous_return.json`也保留同文。

W036的补充原文说GT范围偏大，较小范围是其认为正常且标得不错的区域。来源：同目录`user.json`，`/decisions/new_94_3645_7223_W036/comment`；作答记录`R03262`。

用户于2026-10-10 09:24:02 UTC回复“就是这个”，消息`Sentinel_0c62a95ab8708191801a77096c0d6e0f`。`memory_identity_confirmed=true`记录这次身份确认。**这不等于批准新的polygon、三维GT或顶边。** 此图仍需用户编辑/确认目标区域。

目前该图20条作答，其中19条manual/main_candidate几何有效，1条excluded几何无效。19条数值均达到0.30筛查阈值，但这不是19张“范围不同”的语义票；部分作答同时有遗漏和向外扩张，不能单用总面积大小解释原评论中的左右走廊差异。

其他值得查的原评论包括wc2JMjhGNzB-22、-29、-61的门口区域“所有人未标”；只支持特定区域被遗漏，不必然表示GT整体大很多。uNb9QFRL6hY-67、zsNo4HB9uLZ-13的原文明确有少数人同GT，已特别区分，不能说无人同范围。

## 文件入口

- `all_259_images.csv`：全图总表；原文摘要、对象ID、命中原因、当前/原始GT、确认/暂停状态、人数与数值分层。
- `broad_review_queue.csv`：203图宽队列，按建议复核优先级排序，包含单人/少数/已排除的历史证据。
- `unique_comments.csv`：1648条独立原文；原记录ID、worker、condition、当前gate、全部来源路径和JSON Pointer。相同原文重复导出不重复计为意见。
- `all_comment_occurrences.csv`：6340处来源逐条列出，保留当时verdict/category/time等上下文。
- `keyword_comment_candidates.csv`：747条宽关键词候选，其中726条属于259基集，21条在基集外；机器标签仅供筛查。
- `all_3152_geometry_records.csv`：逐条作答的完整分母、无效状态、选定/原始GT数值和来源。无效数值为空，不当成0。
- `condition_gate_groups.csv`：按图、condition、gate分层，不把Manual、Semi、OOS、excluded混成投票。
- `selected_vs_original_reference_pending.csv`：28张当前选定GT与原始GT不同的图片。
- `paused_reference_images.csv`：已知暂停语境总表（9图），按旧快照、当前用户质量参考、正式质量gate分层；不是完整重算的全库现行资格表。另有3张分层表。
- `no_hit_images.csv`：56张未命中图片，可继续查漏。
- `historical_outside_259_comments.csv`：21张基集外历史图的41条文本，不硬接入当前259图计数。
- `unresolved_comment_identities.csv`：当前为空，仅表头；身份对接已用精确源ID验证，不用模糊码或视觉相似强行匹配。
- `scope_by_image.json.gz`：按图聚合的页面数据，约329KB压缩。
- `inventory.json.gz`：全量机器可读库存，约1.3MB压缩。
- `summary.json`、`source_manifest.csv/json`、`verification.json`：计数、源文件状态/SHA256、校验结果。

CSV使用UTF-8 BOM。CSV中嵌套字段为JSON字符串；JSON Pointer遵循RFC6901，CSV来源以`/rows/零起始数据行序号`引用逻辑行，不冒称物理文本行号。

## 怎样解释分类

各组是对历史文字和既有数值的检索整理，不是新增人工真值：

- 91图：文字明确涉及房间/跨门区域、玻璃内外、柜体与墙角、停止边；仍需当前图像与参考对照。
- 24图：存在范围措辞，但与细节/普通误差混合或方向不明确。
- 47图：细节、定位或宽上下文线索；不直接判成目标范围不同。
- 34图：仅数值候选。
- 2图：仅假设替代范围或当时结果未见该范围。尤其uNb9QFRL6hY-47的评论明确GT与人员都标完整空间，不能算已经观察到与GT不同。
- 5图：先前已确认的地面区域，单独标记：e9z-17、e9z-09、b8-18、q9-29、pRb-02。
- 56图：本次未命中。

每图同时保留多标签，方便区分“房间/区域选择”“玻璃边界”“柜子停止点”“墙面细节”和“普通坐标/参考几何”。同一图可同时存在真实范围选择与标注错误，不能二选一覆盖原文。

## GT版本、资格与计票

- 新复核默认使用`selected_gt_object_id`绑定的当前有效选定参考；原始GT仅作历史层。28张版本不同的图均标`historical_reference_version_pending=true`。即便两者相同，也不保证所有历史评语的浏览版本完全相同。
- yqstnuAEVhm-04的原GT向玻璃门外延伸，用户修订后停在玻璃门；e9zR4mvMWw7-16的原文明确人工修订后已无问题。不能把早期评论直接当成当前仍有范围问题。
- 保留4张旧几何快照暂停状态（historical_snapshot_hold，非全库现行政策）：jtcxE69GiFV-11、pRbA3pwrgk9-16为hold_all_analysis；uNb9QFRL6hY-32为hold_main_analysis；uNb9QFRL6hY-51为inner_space_only_reference_hold。几何可计算不等于参考获准使用。
- 当前用户明确质量参考暂缓另外两图：x8F5xyUWy9e-01、wc2JMjhGNzB-14，来源为《质量研究正式输入与待研究问题_20261010.md》第24–25行及对应用户消息。两项独立于旧gate，不修改个人资格、可标性或GT坐标。
- 当前record_evidence中另有jtcxE69GiFV-18、q9vSo1VnCiC-29、zsNo4HB9uLZ-13的formal quality gate=hold_scene_or_reference。q9-29地面范围已确认，也不解除该正式质量暂停。正式质量gate尚未从全3152表重新完整加载，因此这3图是已观察到的证据子集，不能宣称全库仅这3项。
- 上述9个已知暂停语境在hold_layers逐项保存来源；geometry旧gate和current_manual_pool只是原数据快照归组，不表示现行正式质量资格。
- 218条excluded历史作答保留原文与数值，单列，不加入合资格人员范围计票。2406条main_candidate也分condition；当前manual池1866条。
- 0.20/0.30/0.40均仅为既有几何敏感度线索。宽队列没有N≥3或多数条件，单条作答即可触发数值筛查。
- 5张先前地面范围确认与uNb-88的“记忆身份确认”是不同字段；均不自动替代完整GT审批。

## 检索完整性与已知限制

1. 当前259图/3152作答全覆盖；1157条完整历史评语索引全保留；8份`review_final_20260928/evidence/*.json`全读，另接入早期审查导出与文字解释。具体源清单见manifest。这是当前Git快照收录的历史资料，不是对所有Git历史commit、所有电脑文件或未同步材料的穷举。
2. `analysis_results/review_comments_20260929/comments.json`在当前克隆中只有Git LFS指针，108,396,834字节正文未取得，不将它计为已读。其完整1157条历史索引已取得；1153条索引文本另有本包已读JSON原文可追，余4条只追到索引，分别是3条rPc-09排除意见与1条wc-67排除意见，无范围关键词。
3. 原首版73条“未解析”经精确源ID复核：基集外图片单列；复合键中的完整image_id精确拆分；同文本多来源去重；移除field_contract字段说明。未使用近似图片代码、姓名或视觉相似匹配。最终没有待解身份，但基集外41条仍不纳入259基集。
4. 关键词会漏掉没有空间词的含蓄描述、错字、只留标签而无文字的意见；会误命中“空间细节”“范围一致”“不是空间问题”等。本包保留否定/同范围、细节、普通错误等标签以及全原文，供人工查阅。不存在“关键词未命中＝真实没有范围差异”的推断。
5. 历史评论中的“都没有”“大部分”是当时评论者的描述，不是对当前所有有效作答重新计算出的语义计数。记录ID和源评论可追，但不能拿重复版本或同一人的多条评论当独立票。
6. 本次没有修改原始GT、作答、gate、融合、旧评分或已确认polygon；数值来自已有`all_scope_evidence.json`，只校验内部一致性，没有重跑全套投影。

## 校验

`verification.json`为passed：259/3152唯一性、图级与condition/gate分母、1866当前manual、218 excluded、5区域确认、1记忆身份确认、28参考版本差异、4项旧快照暂停、2项当前用户质量暂缓与3项已观察正式质量gate分层均一致；6340处来源指针逐条回读原文全部匹配；3152条数值/空值状态逐条核验；所有注释级评论均精确连到原record_id。机器检索仍不能替代对真实范围的人工裁定。
