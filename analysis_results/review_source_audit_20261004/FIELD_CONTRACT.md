# 本次审查输出的字段和边界

本目录是已有原件和保存输入的审计及修正盘点，不是新的人工裁决或正式资格真源。当前完整数据仍从`analysis_results/research_input_20260929/manifest.json`读取。

- `summary.json`：259图覆盖、对象级审核计数、新旧难度、旧盘点一致性、新预选和高人数覆盖。`individually_reviewed_annotations`仅表示特定逐份裁决字段；`structured_image_history`为存在图级历史，不要求所有问题resolved。
- `review_coverage.json`：每研究图一行。`annotation_n`包含该图保存的全部人员记录；`individually_reviewed_n`、`confirmed_annotation_rings`可重叠，不能相加当人数。`image_history_sources`为冻结证据来源；`any_review_record`不表示每份作答或每个维度全部确认。
- `high_manual_pools.json`：全部Manual N≥20候选池，以及其中未进入33图主曲线的14图。`affected_records`只列已有质量/BEV限制记录；其为空也须读图级共识gate。`reference_quality_compatible`要求池内所有候选均满足既有质量候选条件，不能等同于视觉GT正确与否。
- `historical_image_notes.json`：39条9/18用户原话，精确image_id绑定，`source_pointer`指向原件，`saved_at`是文件保存时间而非逐条审查时间。`verbatim_in_frozen_comment_table`仅检查同图原文/子串存在性，不判断后来裁决是否吸收过这些意见。历史文字不重设当前资格或等级。
- `corrected_inventory/`：复用原盘点schema与字段合同；新增图字段`difficulty_legacy`、`difficulty_later_review`、`difficulty_text_review`和来源说明。`difficulty`使用9/13既有等级叠加当前resolved图级traits，pending保留较早有效等级，无旧等级则未定；未填写不会抹掉旧等级。uNb-07额外按逐字“中等难度”的已核验图级评论纠正，保留完整原话并检查源记录与当前证据一致；冲突或源漂移报错。不同作者的二审意见、逐作答等级和一般词语推测不自动合并。
- `difficulty/`：独立难度来源审查、逐图前后对照及来源事件，解释见`DIFFICULTY_AUDIT.md`。
- `pipeline/`：逐对象/实际名单/点供体绑定检查，字段细节见该目录`FIELD_CONTRACT.md`。

`check_review_coverage.py`可重新验证旧/新盘点的非难度字段一致，并再生本层JSON。`corrected_inventory`由已有盘点工具读取当前完整包生成；不是把审计结果反写为上游人工证据。所有历史冻结研究输入维持原状。
