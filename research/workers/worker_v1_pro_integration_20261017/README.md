# 数据v1：真实团队结果与人员Pro增量接入

2026-10-17，独立分析修订`worker_v1_pro_integration_20261017`。机器入口：[CROSS_MODULE_INPUTS.json](CROSS_MODULE_INPUTS.json)。本轮实际消费已完成的融合和统计结果，并修正Pro的两条审核措辞漏项；没有重训普通Q、改变人员资格、改参考/原标注或建立综合扣分。

旧[人员组合包](../worker_v1_composition_20261017/README.md)保留首交数据与当时证据定义。新接口采用[统筹独立审查](../../../docs/thesis_main/人员Pro与各模块独立审查及v1推进_20261017.md)的边界。数据始终为v1；B8L2主线，D10仅方向尺度敏感性。包名中的历史v2/v6不表示新增数据版本。

## 1. 真实组合结果已经返回

源为[融合TEAM_RESULTS](../../fusion/wall_consensus_v1_process_20261017/TEAM_RESULTS.csv)及[统计策略结果](../../statistics/v1_integrated_analysis_20261017/strategy_vs_matched_random.csv)。14845个请求中14603个完成，覆盖172图；242个请求来自rPc6DW4iMge-22整池输入阻塞，原因为`R01424:coordinates_outside_continuous_canvas`。它们是明确失败，待发布数为0；没有删掉此图或伪造输出。

“请求完成”不等于完整几何或主质量可评价。完整分母见[团队覆盖](team_coverage.csv)：

|图片层|计划/完成图片|请求/完成请求|完整几何|主用途质量数值|
|---|---:|---:|---:|---:|
|普通|156/155|13512/13270|11960|7832|
|门洞|17/17|1333/1333|1170|1111|

另有690个普通团队有数值但不属于主比较用途，不能混入主质量均值。门洞是当前正式场景层；本批门洞策略使用**普通Q/T画像迁移**，不是用门洞专项画像重选的实验。既有门洞专项另列在[doorway_specialist_profiles.csv](doorway_specialist_profiles.csv)，未混进普通Q训练。OOS没有进入这些请求。

### 三种比较的身份

1. **固定成员换评价指标**：[team_results.csv](team_results.csv)中，同一request_id的成员和几何不变，仅比较B8L2/D10；`fixed_member_D10_minus_B8L2`是尺度变化，不是标注或融合改善。图、参考和资格继承原结果。
2. **换指标后重新选成员**：[metric_reselection_contrasts.csv](metric_reselection_contrasts.csv)保留12174个计划比较，12030个双端已发布、7105个双端主用途可比；144个整池输入失败。先固定B8L2或D10作为终点评价，再比较选人变化。2331个成员集合发生变化，不能把这部分收益归因于评分公式本身。
3. **类别优先进入与纯类组合**：[strategy_vs_random.csv](strategy_vs_random.csv)接入24348个同图同k的策略/随机对照。`pure_class_prefix=true`须焦点组支持且该组人数≥k；超过该组人数后是类别优先的混合队伍。不存在某组时不称真实组别对照。完整率、输入失败和时间缺失单列，不只分析成功分数。

### k=3的实际纯类比较

下表复核了统计已有的共同可比面板；两侧都保留原随机对照及主用途资格。每行是同图同k的纯焦点组比较，不是全173图都有该组合。

|分类指标与纯组对照|共同图/建筑|固定B8L2评价均差|固定D10评价均差|B8L2正/负图|
|---|---:|---:|---:|---:|
|B8L2：Q高−Q低|66/16|+5.757|+5.047|46/20|
|B8L2：高Q快−高Q慢|15/7|+3.361|+3.811|6/9|
|B8L2：低Q快−低Q慢|46/12|−0.388|−0.369|21/25|
|D10：Q高−Q低|67/17|+6.709|+6.126|46/21|
|D10：高Q快−高Q慢|21/10|+1.397|+1.580|12/9|
|D10：低Q快−低Q慢|44/12|−0.273|−0.161|21/23|

Q高组平均更高，但有实质反例；快慢的质量方向随面板和汇总方式变化，不要求效率分类改善质量。上述是图等权描述。[逐图对照](pure_group_direct_by_image.csv)与[逐建筑汇总](pure_group_direct_by_building.csv)均已生成：例如B8L2低Q快−慢的图等权均差为−0.388，建筑等权却为+1.789，说明图片分布不均会改变结论。不能按期望挑权重。没有新增独立图，也没有用重叠团队数做独立样本显著性。

## 2. 初始化恢复与兼容净改善已接入

[initialization_evidence.csv](initialization_evidence.csv)覆盖全部574份Semi：427份实际改动、147份未改，均有初始化来源核对；这比旧定向审核的100条未改覆盖更广。413份原生初始化环序未确认、161份有既有确认环及点身份；保留实际来源和环序诊断，不把计量兼容性称为屏幕呈现几何已获验证。

[semi_initialization_scores.csv](semi_initialization_scores.csv)保留574次计量尝试、初始19份不可用、最终55份不可用及逐项原因。437份普通场景、同参考且可归因给人员的兼容净改善，B8L2初始均值82.106、最终79.488、均差−2.619；D10对应82.830、80.459、−2.371。该面板包含409份普通开发训练和28份原留出；不能把剩余137份删掉或填零。

用户/研究者点修订造成的项目视图变化与人员可归因净改善分开；原数组初始化与后处理final不兼容时出现的虚假增益不记给人。净增分不是某一语义缺陷已修复的标签。24份其它特殊条件另列，不并入普通Semi主训练；本数据门洞记录为Manual，没有借Semi模型声称门洞专项已验证。

采用Pro已有的[独立Semi效应及楼外结果](semi_lobo_performance.csv)，未重训模型：409份/11建筑开发楼外中，B8L2的普通Manual Q迁移相对MSE下降12.36%，Semi专项效应为34.03%；28份/2建筑原留出分别为−35.54%、−71.53%。D10对应开发11.47%/31.71%，留出−47.88%/−93.82%。不能用开发优势宣布普遍迁移成功。

[semi_final_gain_effect_equivalence.csv](semi_final_gain_effect_equivalence.csv)保留实算恒等检查：同一初始化/参考任务下减去初始分只减任务常数，final与gain的相对人员效应相同；二者不重复加权。普通Manual Q仍为1048份，普通Semi训练409份、门洞专项及普通画像向门洞迁移各保留身份。

## 3. 三条修改后仍有问题的评论修正

Pro原脚本只匹配“没改对”，漏掉两条“还是不太对”。本轮按稳定对象ID和正式输入中的原评论补齐：

|object_id|人员/图|核对评论|
|---|---|---|
|b62a4df9e1645fe7|W035/B6-10|这个改了一点模型的预标注,但是还是不太对|
|717840fe8221eba6|W037/B6-10|同上|
|28935ccbb578589d|W037/e9-39|这错误预标注他也没改对|

三条均为坐标已改、源裁决`usable`，全部不在156个强缺陷gold机会中。现在[纠错证据表](semi_correction_evidence.csv)保留Pro原匹配标记、修正标记、确切评论及来源；**只采用“审核者指出剩余问题、机制尚未完全指定”的证据**。没有改为invalid，没有加到强gold分母，也没有据此给该初始化所有作答贴失败标签。专门测试同时覆盖两条漏项、原有一条及不应匹配的对象/未改状态。Pro原件未修改。

## 4. 旧288/39与新156/25逐对象桥接

[correction_definition_bridge.csv](correction_definition_bridge.csv)574行，保留每份作答的两套机会定义和结局：

|关系|份数|解释|
|---|---:|---|
|旧288与强gold156共同|144|既有标签和实际专家缺陷证据同时存在|
|旧独有|144|自然trap标签线索，缺本次采用的实际缺陷gold；不是已证明无错|
|强gold独有|12|W019/W026各6份，仅作行为证据，不恢复主Q/融合资格|
|旧未改36与新未改25共同|20|同一对象，不算两次失误|
|旧未改独有|16|自然初始化线索|
|新未改独有|5|均W026|

旧39＝旧36个未改机会＋3条改后仍有问题评论；新25仅指强gold中明确初始坐标缺陷未改，不能把39→25当同分母更正。新156＝25个已知原样残留＋131个改后缺陷是否消除未知；不把131个记为修复成功。只有六个专家实际缺陷任务，不能在目标建筑外满足既有6任务支持后另造稳定“纠错人员类型”。

## 5. Scope与剔除归因的采用边界

[scope_evidence.csv](scope_evidence.csv)覆盖3222份，逐份保留原答卷绑定、历史任务gold及later hold。`historical_gold_current_clear_compatible`仅在**历史可用任务gold=in_scope、当前scene=clear且oos_subtype=not_oos**时为真；不是重新人工裁定当前每个目标空间。38/286 Manual、10/78 Semi的误拒只在这个兼容面板上解释；W030的9/11也只适用于该面板，不能推广成其普遍范围判断能力。

[exclusion_candidate_evidence.csv](exclusion_candidate_evidence.csv)保持85份原审核剔除。25条具体依据、68条宽不可接受都叫**历史审核文本候选编码**；25包含旧10，新增15不是新增观察。旧Pro字段`strict_specific_personal_severe`和`reviewer_personal_nonacceptance`在当前接口改名为`pro_candidate_specific_reason`和`pro_candidate_broad_nonacceptance`，不一律升级为独立严重失误gold。原裁决和原编码理由仍可追溯。

额外保留`subjective_magnitude_basis`、`OOS_geometry_policy_dispute`、`scope_context_ambiguity`：W031/7y-13“太歪”和W033/Uw-10“偏得离谱”带主观幅度判断，后者同时有停止范围差异。不能把审核接受解释为已证无错，也不能把被定向审核的比例当总体风险。未审核、未定因、GT/参考、OOS、非独立、历史整人排除继续分别解释；没有生成事件并集扣分。

### 最小人工问题

当前普通Q、门洞分析和真实团队结果接入**不需要新增人工裁决**。若要把某条OOS历史剔除计为个人几何失误，仅需核对1例：[HUMAN_REVIEW_CASES.json](HUMAN_REVIEW_CASES.json)中的W001/Uw-08，`f21c670566821ce7`。其历史scope结果为correct_rejection，但评语“oos,但是他只标了3个点”；当前说明允许OOS只提供足够的范围判断证据。需明确当时P1任务是否另要求完整成对布局，以及该invalid针对什么个人错误。保持原排除，归因待核，不因此恢复资格或扣新分。不要求重审全部131例。

## 6. 机器接口、来源与验证

- [record_evidence.csv](record_evidence.csv)：3222行，`object_id`唯一；原资格/Q/时间、scope历史与兼容标签、候选剔除归因、强缺陷机会、兼容净改善并列。非Semi或未审查的候选列为空，不能当零失误。
- [person_profiles_and_evidence.csv](person_profiles_and_evidence.csv)：54行，`worker_id × metric`唯一；原连续Q/T与组别、独立Semi效应、机会/未知/候选计数及普通兼容净改善并列，不改原类别。
- [person_evidence_summary.csv](person_evidence_summary.csv)：27行，包含历史排除者的行为证据，主Q/融合资格保持；scope按人和条件的机会/结果另见`scope_worker_opportunities.csv`与`scope_outcome_counts.csv`。
- [FIELD_CONTRACT.json](FIELD_CONTRACT.json)给字段清单、行数、主键和语义；[INPUTS.json](INPUTS.json)记录实际读取来源与文件状态，保存Pro原件本地忽略目录的身份；[CHECKS.json](CHECKS.json)记录本轮核验，不把统筹已有960效应/2096预测独立验证说成本轮重算。

复算：`python -m tools.thesis_main.analysis.worker_v1_pro_integration_20261017`。只消费已有计量、拟合与真实几何；没有调用Pro完整训练流水线或融合算法。完整运行成功；新增漏项/兼容性/纯类边界及既有人员相关测试13项通过。全局目录、模型和索引由统筹处理，详见[HANDOFF.md](HANDOFF.md)。

尚未完成的是131次强缺陷编辑后的逐项语义结局、f21的历史归因及rPc-22输入阻塞；这些都没有被改写成成功、正确或仍在排队。没有新增综合人员扣分、采集、全仓测试或Git提交/推送。
