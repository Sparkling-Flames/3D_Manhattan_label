# 特殊图片条件与当前评价覆盖核验

> 当前图片难度已由[v3及GT排除](../difficulty_review_update_20261015/README.md)接续，本页保留旧目标/旧分类绑定。新增空间按整个空间体竖向边界解释；下游还须应用至少3名有效标注者规则，旧计数不可直接作为最新分析分母。


> 2026-10-15接续说明：本报告中的原12图特殊条件覆盖判断保留；其后另补6图特殊层，见[接续结果](../../fusion/wall_consensus_quality_20261015/special/README.md)。特殊条件、粗难度、可标性和参考资格仍为不同字段。 当前统一状态见[资料核对](../../../docs/thesis_main/四线程成果与论文主线核对_20261015.md)。该句原属文档整理阶段；后续已获授权并完成描述统计，当前版本见统一状态入口。


本版只投影已有证据，保留 `scope_preferred_difficulty_20261011_v2` 的259图分类，不重新定级，不裁决人员能力，不改变正式资格。数据入口与质量评分所用快照逐项相等；没有重跑融合。

## 已核验的覆盖

|既有条件分层|图片数|当前作答数|现有质量覆盖|12图融合面板|
|---|---:|---:|---|---:|
|门洞，不含OOS交集|17|217|115条件完整评分；10范围诊断；92暂缓|0|
|OOS，不含门洞交集|23|381|当前WQ标记不适用|0|
|OOS与门洞交集|2|23|当前WQ标记不适用|0|
|OOS待定|1|2|当前WQ标记不适用|0|

前三行对应42张既有“单列”，第四行仍属于原5张待复核之一，不能宣称已有43张单列。OOS计25张，门洞计19张，交集2张；不能将两者相加当作独立图片数。当前作答数来自3152记录账本，包含各类角色，不是独立人员数或合格样本数。

125份门洞记录进入1145联合比较，不代表全部可作人员主质量证据：115份仍是特殊场景条件分析，10份范围诊断维持hold。其余OOS当前WQ不适用也不意味着不可标、低质量或能力差。

## 文件和消费合同

- [image_coverage_259.csv](image_coverage_259.csv)：全量逐图连接表。主键 `image_id`，当前难度目标为 `target_id`；同时保留难度版本、原特殊条件、可标性明确标签、评分使用层、历史S覆盖与12图融合覆盖。
- [special_coverage_43.csv](special_coverage_43.csv)：上述表的特殊条件及待定子集。
- [reference_targets.csv](reference_targets.csv)：292个既有候选目标（259 selected_gt、33 confirmed_scope），保留采用状态。`selected_gt`是候选角色名，不保证该候选最终被采用。GT几何存在不等于已验证正确；33个确认范围只给底面，上边界仍未定。
- [evidence.json](evidence.json)：逐图保留已有难度理由、用户回执字段、参考限制、当前数据入口的空间描述/分类来源、GT证据、历史S裁决类别和后续hold。文本是来源材料，不是本版新增结论。
- [CHECKS.json](CHECKS.json)：数量、绑定完整性和状态差异检查。

`markability_from_explicit_label`仅转录已有明确类别：非正交可标、门洞可标，其他全部保留unknown。`doorway_status=difficult`不能推导为不可标；`not_recorded`也不等于无门洞或非OOS。本版没有新造“不可标”标签。历史OOS细类另行保存，不能自动晋升为当前不可标性裁决。

`ledger_score_status_counts`是当前质量账本原状态的计数，`joint_use_counts`来自已完成的目标一致性核验。两者含义不同，不能相互替代。`reference_ids_available_not_certified`只列参考存在性，不能据此宣称参考可信或适用完整三维指标。需要完整参考时，仍需核对对应目标、参考限制以及同目标/上边界条件。

N05/B6ByNegPMKs-37、N28/UwV83HsGsw3-10 的新范围增量继续读取 [new_target_addendum.json](../difficulty_target_integration_20261015/new_target_addendum.json)。两者仅底面确认；原28份作答仍待绑定新范围。没有以高Q、图ID或旧参考ID替代范围裁定，也没有覆盖旧259标签。

## 历史S：保留原问题含义，不改造成范围偏好

历史S是当时标注规则下的可标性/规则判断，不是“喜欢标哪个空间”。1013条历史回答均在现有对象清单中有绑定。本版只核验覆盖，不重算对错，不用当前难度替换历史裁决。

可复用来源：

1. `analysis_results/worker_four_block_exploration_20260910_v1/scope_responses.csv`：保留 `raw_scope`、`worker_scope`、`final_scope`、`final_scope_alias`、`final_task_id`、`scope_source`、`later_hold`、原导出与原annotation id。
2. `research/worker_classification_progress_20261014/source_inventory.csv`：1013条当前对象绑定，`scope_historical_*`字段保留回答与裁决；历史原worker id不得当作当前W/P身份。
3. `analysis_results/worker_four_block_exploration_20260910_v1/SCOPE_SOURCE_AUDIT.json`：原题源与裁决来源，含task696后续修订说明。
4. `analysis_results/prescreen_closeout_final_gold_v2_20260701/final_gold_records_v2_p1_closeout_corrected.jsonl`：当时裁决及source、notes、scope/geometry readiness，保留原字面，不用后来的GT或难度判断覆盖。

原类别包括 `normal`、`oos_geometry`、`oos_open_boundary`、`oos_split_level`、`oos_insufficient`。尤其 `oos_geometry` 指历史几何假设不适用，不能据此认定非正交空间在其他表示下不可标。历史题意的规则边界与现代“按指定范围画布局”的任务不同。

未逐条绑定当时部署的题面配置版本。仓库中的 `tools/label_studio/config_history/scope_instruction_v1_pre_block2/zh/label_studio_view_config_manual.xml` 可查规则表述，但不宣称这就是全部历史S作答实际看到的题面。若研究需要解释每条历史S正确率，必须先完成题面版本与裁决适用性的核查；当前表仅供条件描述与辅助分析。

## 状态差异与下一步边界

`uNb9QFRL6hY-63`：难度表为OOS，当前loader为`not_recorded`，历史S为`normal`；当前质量账本又按OOS不适用处理。三者并不构成互相验证。本版保留原值、指出差异；若要把该图纳入OOS对错或人员表现分析，须追溯当时规则与当前裁决，不能静默统一成一方。

论文可讨论三条轴：指定目标范围下的粗难度、场景条件（门洞/OOS/交集）、规则与表示的适用性/可标性。门洞和OOS可作为辅助条件讨论人员表现；不能把其中失败直接解释为人员能力低。现有12图融合没有特殊场景覆盖，不能报告门洞/OOS融合效果。以后选例需要另行明确目标和可用评价对象，当前没有补跑实验。

全259图各类原图与旧/新范围对照仍在 [原复核工作台](../../../analysis_results/difficulty_scope_preferred_20261011/review.html)，本版不生成第二份人工标签真源。

## 复现与核验

`python -m tools.thesis_main.analysis.difficulty_special_coverage_20261015`

`python -m pytest tests/test_difficulty_special_coverage_20261015.py -q -p no:cacheprovider`

3项语义边界测试通过；生成时检查259图、3152唯一作答、1145联合记录、1013历史S绑定和特殊层数量。只新增本模块工具、测试和成果目录。已检查公共地图/索引；按本轮模块隔离要求不改共享文档，入口登记交给统筹线程。没有提交或推送，没有新建截图。
