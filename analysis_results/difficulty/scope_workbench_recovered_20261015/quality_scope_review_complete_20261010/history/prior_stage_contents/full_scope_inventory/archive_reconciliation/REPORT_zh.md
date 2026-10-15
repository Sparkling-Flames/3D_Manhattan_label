# 恢复审核包：范围评论增量与来源核查

日期：2026-10-10。比较基线为 scope_full_inventory_20261010 的1648条文本、local_scope_verified 的69条已核实当前图绑定及19条基集外绑定。本文仅审阅已返回资料，不重新裁定图像或修改正式输入。

## 核心结论

这次补齐的是历史证据与来源，尚无据此新增的最终范围裁决。应保留以下不同层次，等下一批图片到达后按精确 image_id 对接：

- 21条当前259图内的早期图级用户原话，此前不在1648＋69条接受库存中。多为门口位置、OOS、同房、可见性问题，并非21张“范围不同”。原记录位于 user_group_review_20260912.json 内嵌的9/10用户原始表，已逐条匹配原字段。
- 55条9/11组评论记录，去重文字为50段；45条组记录关联当前基集，共103个图关联。组评论均在 current/note 和 user_revision/note 逐字一致。关联不是逐图范围判断，也不是103次独立投票。
- 先前待核的9段组历史原记录全部找回，原先35个跨图关联只对应9段文字。来源缺口可关闭，逐图指向与语义仍须谨慎解释。
- 3段逐组讨论文字新增4个当前图片绑定；包括2段有用的范围/模型归因说明，另1段为同房与交界否定说明。
- 39条9/17历史图级原话全部已在既有库存中。此次是来源再次核验，不新增39条。
- 完整 comments.json 的3121组文本中，按精确“image_id＋原文”只有20条不在基线；其内容均为配对、删补点、OOS可计算性、历史处理状态或一般政策说明，没有新增目标范围原评语。

## 最值得保留的增量

以下路径均相对审核资料包根目录 extracted；JSON Pointer 为零起始数组索引。

### 新补到的组级门口范围线索

文件：图片分类与复审来源/analysis_results/scene_image_exploration_20260910_v1/user_group_review_20260912.json

位置：/group_reviews/178/current/note；同文 /group_reviews/178/user_revision/note。

原文：

> uNb9QFRL6hY · 02 / 28 / 44 / 80  和这个是极其类似的房间,甚至可以放在一起预测.可能就是门口那里标不标有点歧义,29优先级低

记录关联uNb-08/10/19/29/55/65/68/81/86；其中8图在当前259基集。状态为“仍需讨论”，是历史同房预测/候选选择语境。不能将这段文字分摊成每张图各一次范围错误，也不能把“极其类似”改写成已经确认同一房间。

### 逐组讨论中需要区分的两件事

文件：图片分类与复审来源/analysis_results/scene_image_exploration_20260910_v1/batch_user_decisions_20260911_v1.json

- /rows/6/source_comment：原文“b07 的02是 14图片左边的房间, 但是他们的标注有显著区别, 这个不优先作为后续标注图片的候选(研究同房预测,不影响研究类似场景的图片选择)”。准确绑定jh4-02、jh4-14，属于跨图范围/视点可比性与候选优先级，不能转为单图GT错误。
- /rows/4/source_comment：原文“b05确实同房,39是典型的 model issue 跨门扩张,不算交界处”。当前图新增绑定e9z-39；这是对模型跨门扩张的归因及交界否定，不是认可另一种人工目标范围。
- /rows/10/source_comment：原文“b11同房建议没问题,也不算交界处先”。当前图新增绑定pa4-11，保留否定语义。

### 9段待核组历史已恢复

同一 user_group_review_20260912.json 中，可直接复查：

- /group_reviews/183/current/note：uNb-67站在浴室内，与其余视点标注空间不同；记得有人标外面。特指67，不是九图各自与GT不同。
- /group_reviews/35/current/note：B6-33/37走廊闭合方式“可能略有不同”。
- /group_reviews/235/current/note：yqst-14交界，16范围不同，1/6/18可归一起。是跨视点比较。
- /group_reviews/3/current/note：2t7-07交界，8/15/16范围一致；候选标注时考虑排除07，不是自动改变当前资格。
- /group_reviews/51/current/note：Uw-20可能漏右侧角。该组不在当前259图内。
- /group_reviews/255/current/note：zs-13视角信息不足，容易遗漏门口。
- /group_reviews/213/current/note：wc-41处在标注交界，其他视点不标门口。
- /group_reviews/91/current/note：e9z-06/09“可能”有范围歧义。
- /group_reviews/104/current/note：jh4-04/07/10复杂难标，不建议优先；并未明确判范围不同。

## 重复、传播和版本不能当新意见

1. 原清单002_confirmed_user_decisions.json与003_USER_DECISIONS.json字节完全相同，SHA256为881db0a99df208cf262bcc85601fe3c7ae11eae00f6506c588f148cb0d490dbc。记录9/9九项点处理决定及个别回应排除；不是新增范围决定。001_confirmed_processing_audit.csv为16条执行/历史修补记录。补点为计算副本插补，不应改称原始人员作答；W19/W26的历史说明明确保留包含/排除两种情景，不能据此创设永久人员排除。
2. 原清单004_same_room_selection_registry_v2_20260912.json与9/29 final_review/同房分类_原始完整记录.json的groups（260）、candidates（259）、images（648）三个数组内容完全相同。后者路径日期较晚，不意味着又有一轮人工判断。
3. 完整冻结comments.json已读到108,396,834字节正文，含3121组文本、32462处来源，其中1102组标记为解释/派生语境。这1102组的同图原文均已存在基线，不能转成新增用户原话。
4. 统一空object_id的图级表示后，另有135条已有“图＋原文”被挂到额外object_id的上下文记录。多数来源是全量复核CSV的scene_dimension_evidence等引用字段，是图级/他人评论在记录上的传播，不能记成对应worker的独立意见。例如comment_001179绑定W028，但embedded_source指向W030的原决定。
5. 原先仅在1157条索引里找到的4条排除文字，如今能追到冻结表的汇总来源记录；这是追溯层增强，仍不是直接重新鉴定原始提交人。详见source_resolved_index_only_comments_4.json。
6. 冻结表新增20条中，12条是配对/点位/OOS计算相关原文、1条政策说明、7条历史处理引文或状态说明。不得用旧“补点”说明覆盖之后的当前排除决定。例如wc-67的R00035既有历史补点引文，也有后续排除记录，须保持时序。

## 旧C1和早期候选的正确用法

123条原路径按SHA256只有51份不同内容；其中119条C1/预筛旧路径对应48份不同内容。这些旧文件不是一律无关，但用途不同：

- prescreen_scope_*主要记录in_scope/OOS判断与分母，不是“小空间/大空间目标范围”的直接评论。
- calibration_full_candidate_inventory_v3.csv有46条非空notes，涉及当前图36条、基集外10条。已单独保留全部原字段，证据层级为“旧候选汇总，未证实为用户逐字原话”。例如B6-11、b8-04、uNb-06/63、wc-56的跨门扩张属于旧模型问题/候选摘要；wc-20“漏标；边界需讨论”标记model_issue_only=true；不可直接当人工范围差异。
- wc-14的旧候选文字“可保留为高难候选，但需先确认 GT 稳定性”，不能解除10/10现行质量参考暂缓。
- yqst-04的旧“拉伸+scope歧义候选”不能覆盖之后玻璃门停止位置的人工修订。
- dry-run欠覆盖比例、候选类别、旧人工范围标签与正式研究的现行reference/quality gate须分层保留，不能用旧快照重建当前资格。

## 正式决定与剩余缺口

quality_update_20261010.json明确采用选定GT进行质量研究，但保留已明确报告的参考问题；x8-01、wc-14质量参考暂缓，x8-09真实非正交不自动等于标注错误。共同较小范围须先筛查再人工核对，多数不是真值；玻璃两侧或微小凸起不自动创建替代GT。14份已接受点审核为另外一层输入增量，不是本次新增范围结论。

4条point109原话在本返回审核包中未找到完全相同文本，这只是该归档包的搜索结果。随后从最新main快照fae48e69aa4ae879b8268c34afb8f8221ee53022取得原始七列《109核验结果.csv》，4条均已恢复原行与原始时间字符串，详见下面的独立补充层；不能再写成全局仍缺原记录。

本次未重算质量、未修改原始GT/作答/资格、未形成最终范围名单。等后续图片到达后，按精确图片ID、评论对象、评论层级和当时参考版本合并，再逐图裁定。

## 可携带数据文件

- new_early_image_comments_21.json：21条新增当前图级历史原话、原记录、精确指针与SHA256。
- historical_group_comments_55.json：全部55条原始组评论；保留50种原文、组成员和待讨论状态，禁止摊为逐图票。
- source_resolved_pending_group_notes_9.json：关闭9段组历史原记录缺口。
- new_batch_discussion_records_3.json：3段新文字、4个当前图绑定。
- historical_c1_candidate_notes_46.json：旧候选摘要单独存放。
- frozen_new_text_records_20.json、frozen_known_text_new_object_contexts_135.json：冻结表新增文本与既有文本传播分别保存。
- source_resolved_index_only_comments_4.json：4条旧索引文字的新来源层。
- historical_image_notes_39_reconfirmed.json：39条已知历史原话重复核查。
- other_early_image_comments_outside259.json：基集外原话另存，不计入259。
- original_123_path_index.json、original_123_content_groups.json：原路径对照及重复内容分组。
- summary.json、FILE_MANIFEST.json、verification.json：统计、文件完整性与回读校验。

JSON中的file_sha256是原文件字节哈希；canonical_json_record_sha256是原记录经排序键、紧凑JSON重序列化后的内容哈希，不声称是原文件某一连续字节段。source_saved_at仅表示所在导出时间，不等同于单条评语的编辑时刻。

## 最新main补充：4条109审核来源已恢复

此节来源是最新main快照fae48e69aa4ae879b8268c34afb8f8221ee53022，不属于前面的返回审核归档包。原始文件 research/point_review_109_received_20261009/109核验结果.csv 的SHA256为 f0bb8b77efe8651763fd0cbef88ca6c61f6786cbcbbd57a288318122f78a7134，已与该目录的MANIFEST_SHA256.json和review_summary.json一致性核对。

- R00658／q9-15：逻辑数据行17，“点9，10不在正常范围内”；原时间“10/9/2026, 7:48:31 PM”，核验结论“需删点”。
- R00684／rPc-17：逻辑数据行19，“13，14，15，16超出范围”；原时间“10/9/2026, 7:53:04 PM”，核验结论“需删点”。
- R01184／yqst-31：逻辑数据行40，“缺少点 点标的超出房间范围”；原时间“10/9/2026, 8:07:02 PM”，核验结论“其他”。
- R01196／b8-04：逻辑数据行41，“缺少点 且标点范围不同”；原时间“10/9/2026, 8:07:30 PM”，核验结论“其他”。

行号均为零起始CSV数据行，不含表头。四条的记录、图片、canonical object、原标注者P013和原始点数已与109核心摘录、actionability表及既有3152作答库存交叉匹配。P013是原标注者，不能当成审核者；CSV没有审核者身份或时区，保留原时间字符串，不擅自转换UTC。

这是“原始审核行和记录时间字符串找回”，并不证明审核屏幕所见的坐标版本或点编号约定；两条删点指示也不自动执行。四条在该源快照的quality gate仍为excluded、独立投票资格为false，不把历史线索纳入合资格人数。未新增GT、范围最终裁决、点操作、资格或评分。机器文件为latest_main_source_resolved_point109_comments_4.json及latest_main_point109_verification.json。
