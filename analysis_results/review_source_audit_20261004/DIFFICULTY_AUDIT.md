# 图片粗难度来源审查

2026-10-04。本页核对已接收的人工证据与当前259张研究图片，不重算融合、不改旧标签或样本资格。**9/13原件中的73张明确等级不是全部已有人工作答，也不是全部可用难度证据。后续图级补充难度已进入当前预处理包，却被旧盘点程序遗漏；另有明确自由原话不能因未填写difficulty字段而忽视。**本轮最终明确来源口径为53简单、31中等、17困难、6未定、152未记录：101张明确等级之外仍有人工定性意见，不等于其余图片都没审过。

## 1. 审核覆盖与难度字段是两件事

[最终审核说明](../review_final_20260928/README.md)已有259图全量来源核查：221张有结构化图片判断，38张有旧逐份审核，0张完全不在上传审核中。其明确说明“难度缺失不算漏审”。这不能反过来解释成259图都有三档难度；也不能把难度空白的图重新叫“尚未审查”。

本次读取27个已接收来源，含9/13选图原件、9/18双方39图审核及最终裁决、9/19—22追加审核、新采集采用、9/25—28初审/二审/续审/补审。检索及证据种类见[difficulty/source_catalog.json](difficulty/source_catalog.json)。同房包中的`difficulty_similarity`是相对相似判断，`prefill/AI`不是人工三档等级；旧每份作答自报难度、模型候选难度和AI推断没有被提升为本次图级标签。

## 2. 明确遗漏的结构化来源

| 来源 | 原件内容 | 与当前259图的关系 |
|---|---|---|
| [9/13选图原件v2](../candidate_selection_review_20260913_v2/用户审查原始记录.json) | 112个逐图决定；v1与v2原件内容相同 | 精确image_id匹配78图：36简单、23中等、14困难、5未定。其余34不在当前研究图片中；73只是明确三档数 |
| [9/27定向补审接收](../review_closeout_20260928/evidence/returned_review.json)、[终审latest原件](../review_final_20260928/evidence/latest.json) | `traits/image:<image_id>/difficulty`：20 easy、10 medium、4 hard | 34图全部精确绑定；33条resolved，UwV83HsGsw3-17一条pending |
| [续审原件](../review_final_20260928/evidence/continuation.json) | 3个图级difficulty：S9h-04、uNb-32、uNb-51 | 已包含在上述34图中，不能再加3张 |
| 当前[preprocessed_source](../research_input_20260929/preprocessed_source.json) | 每份annotation的`review_evidence.image_traits` | 同图所有作答的traits逐值一致；34条difficulty/status与latest原件全部一致，不是缺少接收或需要重审 |

旧`research_panel_inventory_20261003`只读9/13文件，因此漏读后续图级traits。33条已确认记录中，28张新增明确等级，4张与旧明确等级一致，uNb9QFRL6hY-47由旧“中等”更新为“困难”。Uw-17原来没有9/13标签，pending easy只作“未定”候选，不能称已确认简单。`unrecorded`或没有difficulty字段不撤销旧明确值。

结构化来源与下一节明确文字合并后的最终结果，已重新读取当前`corrected_inventory/input.json`逐图核对：53简单、31中等、17困难、6未定、152未记录，259图与独立预期零差异。旧records、references及图片所有既有非difficulty字段逐值不变。仅traits的54／30／17历史中间结果单独命名为`intermediate_traits_only`，不代表当前盘点文件。

## 3. 自由原话还包含一次明确覆盖和额外困难判断

[图级原话逐条表](difficulty/image_comment_interpretations.json)保留28条关键词命中的图级原文、status、时间和image_id；[完整有限检索](difficulty/commentary_candidates.json)另外保留逐作答评论及9/18双方图级笔记。关键词仅用于查找，不自动评级。

最重要的五条均出自`review_final_20260928/evidence/latest.json`的`image_decisions`，status为resolved：

| 图片 | 已核实原话 | 与结构化来源的关系 |
|---|---|---|
| uNb9QFRL6hY-07 | “中等难度,存在右边柜子停止点的问题…” | 9/13为简单，后续没有traits.difficulty。它在旧45图内，是明确覆盖，不能继续无条件称简单 |
| UwV83HsGsw3-09 | “属于很难的图片…” | 原结构化未记录；是全图难度陈述，不只是某个点难定位 |
| rPc6DW4iMge-06 | “这图很难标…” | 原结构化未记录；同时保留玻璃内外范围与参考细节说明 |
| yqstnuAEVhm-32 | “这图很难,标注空间范围不同…” | 原结构化未记录；同时保留原GT和修改GT范围差异说明 |
| uNb9QFRL6hY-26 | “这图属于困难图…” | 与旧困难一致，提供一致性证据 |

本轮最终只采用uNb-07逐字“中等难度”覆盖旧简单，uNb-26逐字“属于困难图”作一致性核验。其他三条“很难”作为用户全图定性意见单列，**没有临时建立“很难→困难”的自动评级规则**；原句、source、JSON pointer、status及时间保留在机器表。旧45图因此有1图改级，最终为21简单／14中等／10困难；旧22／13／10结果仍是当时标签版本的历史描述。

不能顺手扩展的原话包括：q9-32“如果要标马桶所在的空间会很难标”（条件范围）、S9-21“角落有点难标”（局部）、yqst-04“门内简单、门外较难”（范围相关）、“中等大小的空间”和“简单标注”（不在评价图片等级）。e9-19“中等偏难”不能脱离其明确medium字段改成hard。

9/18另有两类需保留而不自动覆盖的证据：

- [用户文字原件](../human_review_reconciliation_20260918/用户_39图文字审核_原始.json)的36条condition review没有填写grade，但39条image_notes确有实质评语。例如rPc-05明确“这张图确实是难图”；笔记没有逐条resolved。没有grade不等于没有看过或没有难度判断。
- [一正原件](../human_review_reconciliation_20260918/一正_39图审核_原始.json)有30个不同图片的已审核condition级评级：13简单、14中等、3困难候选。它们是另一位人工审核者的意见，不是AI生成，也不是用户最终标签。[用户最终裁决原件](../human_review_reconciliation_20260918/用户_39图最终裁决_原始.json)中39个`final_difficulty_adjudication`均为空。本轮单独保存这些评级，没有把“困难候选”无条件当正式困难或自动覆盖最新用户记录。

## 4. 门洞和OOS不应丢失，也不应静默覆盖逐图原话

用户在当前对话明确门洞交界及OOS属于很难标的类型，后来又说明门洞可能局部无法合理标，OOS还涉及GT适用性。这是**场景层的用户规则**，不是259图逐一填写的三档标签。当前表已有24张confirmed OOS、17张difficult doorway，重叠2张；并保留1张OOS pending与2张annotatable doorway。原场景状态在本轮独立难度核对中不变。

建议报告同时列“粗难度等级及来源”和“OOS／难标门洞场景”，可依用户规则另作困难场景的描述分组，不改人员对错或GT适用性。不能把所有出现门的图都当门洞交界，也不能删除与三档不同的原记录：例如x8-09为confirmed OOS但用户另填medium；jtcx-12与uNb-47为可标门洞而另填hard。这说明必须保留维度和评价范围，不能用一个关键词覆盖所有字段。

## 5. 哪些既有面板受影响

以下均为当前最终明确来源口径，只核对名单和来源，不是重跑曲线：

- 原45图没有删图；uNb-07由简单改为中等，最终为21／14／10。后续汇总需记录这一标签版本变化，不能声称旧45完全不受影响。
- 在原相同选择规则下可由45扩至52图，新增B6-40（简单，22人）、Uw-10（中等，23人）、X7-13（简单，24人）、e9-19（中等，24人）、wc-60（中等，23人）、yqst-04（中等，22人）、yqst-31（困难，21人）。最终52候选为23简单／18中等／11困难。
- 扩展研究仍是137张来源尝试、136张已成功曲线，人员名单和可计算性未因难度来源修复改变。136图三档覆盖由57变67；最终为34简单／19中等／14困难，另外2未定、67未记录。

| 当前136成功图的人数窗 | 全部图数，未改变 | 旧明确三档图数 | 当前最终明确三档图数 |
|---|---:|---:|---:|
| N≥4 | 118 | 57 | 66 |
| N≥8 | 67 | 45 | 52 |
| N≥12 | 53 | 31 | 38 |
| N≥16 | 39 | 17 | 24 |
| N≥20 | 33 | 11 | 18 |
| N=24 | 10 | 1 | 3 |

这些人数由旧[rosters.json](../lee_expanded_20261003/rosters.json)直接数得，与旧报告一致。不能把其他筛选口径的47／44／33未经定义地当作本表12／16／20人窗。标签覆盖改善，人员池本身不变。

## 6. 文件和字段说明

- [image_difficulty_comparison.csv](difficulty/image_difficulty_comparison.csv)：259行，包含精确image_id、旧inventory、9/13、后续原始值/status/source/pointer、bundle值、旧45/新52/137来源/136成功面板与人数。`corrected_inventory`是重新读取当前最终盘点文件的实际值，与`final_explicit_expected`逐行一致；`intermediate_traits_only`单独保存明确文字纠正前的中间值，`final_text_override`仅uNb-07为true。相对旧inventory共有31图变化。
- [source_events.json](difficulty/source_events.json)：112条9/13记录、34条后续图级traits、30条一正独立评级、2条逐字明确等级证据，以及原房间note；source/pointer可回原件，一正评级和房间note不自动传播为当前标签。
- [summary.json](difficulty/summary.json)：`current_corrected_inventory_check`保存当前盘点路径、实际计数、逐行一致性检查及31图变化名单；`final_explicit`保存最终独立预期；历史中间结果仅在`intermediate_traits_only`中保存。未重新计算任何曲线。
- [source_catalog.json](difficulty/source_catalog.json)、[commentary_candidates.json](difficulty/commentary_candidates.json)、[image_comment_interpretations.json](difficulty/image_comment_interpretations.json)：有限来源扫描、原文检索及28条图级阅读解释；解释字段不是新人工裁决。

本次只在此目录新增审查报告和证据；未改原件、资格、坐标、环序和旧输出，未启动新的融合研究。主任务修复的当前`corrected_inventory/`已经独立逐图核对，与最终明确来源口径完全一致。地图和索引由主任务统一登记。核查为JSON/CSV逐值读取与来源绑定，不冒称重新看过原图或重新完成所有历史评论的视觉裁决。
