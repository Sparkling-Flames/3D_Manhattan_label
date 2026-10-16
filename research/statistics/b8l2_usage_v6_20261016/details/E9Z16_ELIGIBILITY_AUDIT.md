# e9-16：简单标签与继承的普通资格待核

本页沿用旧共享v6的e9-16资格证据追溯。本用途版只调整已声明的门洞/OOS质量用途，未解除e9-16的表示待核门。历史机器证据见[旧审计JSON](../../b8l2_shared_v6_20261016/details/E9Z16_ELIGIBILITY_AUDIT.json)；其中其它人员与场景计数属于旧1622用途，不作为当前计数。当前27人覆盖和时间交集请读本目录的worker_inventory、worker_usage_summary及time_quality_focus。

## e9-16结论

**当前“简单但普通资格为false”有可追溯来源：早期由Codex提出的单底面表示待核，在v4采用人工简单等级时被明确的单向保留旧排除策略继续保留。没有找到用户明确要求把它列为特殊场景的指令；也不能把简单标签本身当作旧表示问题已经被解决的证据。**

因此它不是凭空出现的特殊类别，也不能准确地只称为“更新标签后漏同步的程序错误”。代码实际有意不解除旧排除；是否应解除这个旧机器问题，属于下一版本需要明确表达的资格政策。冻结v6继续保留24份semi的special_conditional_only，不在本轮静默改为ordinary。

## 证据链

|版本|当前等级|普通资格|来源|
|---|---|---|---|
|v1/v2|待复核|尚无该布尔字段|Codex原记录：GT四点跨楼梯开口、底面单层表示是否允许，问题未决|
|v3|待复核|false / special_or_pending|非简单/中等/困难类别统一进入special_or_pending；用户简单回执另存|
|v4|简单|仍false / special_or_pending|adopt()采用同目标人工等级；代码明确assert所有旧排除不解除|
|v5/v6|简单|仍false / special_or_pending|e9不在补充修正及新空间改动集合，字段原样继承|

关键来源：

- 原人工回执`research/difficulty/difficulty_review_update_20261015/user_review_receipt.json#/records/2`：同一目标，grade=简单，note为空；没有“特殊场景需单独讨论”文字。
- `tools/thesis_main/analysis/difficulty_review_update_20261015.py:117–119`：从待复核类派生special_or_pending。
- `tools/thesis_main/analysis/difficulty_user_adoption_20261016.py:29–35,59`：更新等级，同时明确保留旧排除；未清旧question。
- v5的修正集合及v6两新空间/7y-19修改均不包含e9-16。各版完整字段和JSON指针已存机器明细。

v6的scene=clear、oos_subtype=not_oos、doorway_status=none、GT错误标记false，研究层也未记录稳定非正交。旧待核依据是楼梯/开放区域与单底面表示问题，不能重新命名为已确认OOS或门洞困难。库存26份semi中2份继承历史不接受，24份来源有效且完整可计算；18份有效采集时间、6份时间缺失，当前目标匹配时间0。

建议在当前展示中明确写“人工等级已采用；表示待核门继承”，不要写“用户确认特殊”。若后续基于已有审核和统一表示政策解除门，应形成新版本、说明解除的是哪条旧疑问，并仅重分组；这24份已有分数无需为换类别重调算法。若仍未解决，继续保留条件测量，不能把程序保留排除解释为人工否定其可标性。
