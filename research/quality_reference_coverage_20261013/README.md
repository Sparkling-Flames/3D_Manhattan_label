# 普通manual候选参考覆盖核对

> 后续场景修正：uNb-63的23份OOS已移出普通开发层。当前1304普通候选、121份普通历史参考对照；旧1327/144/749等数字仅描述此前覆盖。最新资格及阶段安排见[范围核查](../quality_scope_resolution_20261013/README.md)。

2026-10-13。对全量用途账本的1332份普通manual开发候选逐份核对。**503份旧`applicability_confirmed=false`不能解释成503份参考错误，也不能据此停止条件描述重评分。** 本次没有新增GT验收、人员资格或参数拟合许可。

## 关键更正

旧输入的`gate.new_descriptive_development_allowed`是条件描述开发许可；`barriers`及`explicit_exposure_barriers`保留排除与曝光限制。`applicability_confirmed`仅标记旧显式适用子层；`reference_acceptance_newly_confirmed=false`明确没有新增参考验收。不得把这些字段合并成一个“可用/不可用”。当前人员限制、来源、逐参考版本限制及原留出另行检查。

旧审计`quality_parameter_calibration_20261012/evidence_audit/analyze_selected_candidates.py`已说明`applicability_flag_is_not_the_only_calibration_authorization=true`及false不等于不适用。历史文字与后来冻结输入存在阶段差别：当前24条旧等级实际为5条true、19条false，不能复述为全部false。

## 核对结果

|层|份数|图片|建筑|本次可自动推进|
|---|---:|---:|---:|---|
|已在旧922、显式适用|71|13|9|复用既有固定参考分数，保留条件边界|
|已在旧922、适用性未显式记录|503|57|19|全部具有旧条件描述许可、无旧gate/exposure barriers，可立即复用冻结指标重评分|
|旧922之外|758|62|14|599份单一既有参考可条件补算，150份双参考分别补算，9份暂缓完整分|

各层建筑有重叠，不相加当独立建筑数。503份全部几何`surface_valid`，全部图像`oos_status=not_recorded`；71份为`not_oos`。两者差别需要分层报告，不能默默把未知改成非OOS。574份可作**条件描述开发**，不是574份获完整人工认证或574条有效等级标签。

758份中：

- 599份有一个未受现有版本限制且几何可算的参考；150份有两个，需固定各自版本分别算，不能用较高分自动挑GT。
- 5份全部位于`q9vSo1VnCiC-16`：R01700、R02020、R01081、R00795、R00806。其原GT仍受`reference_evidence_conflicts_primary_research_quarantine:historical_explicit_error_later_scope_interpretation_unresolved`隔离。虽然参考对象的`worker_quality_gate=candidate_pending_geometry`且几何可算，也不能穿透参考限制。
- 4份标注表示受限：R01424（rPc6DW4iMge-22）、R01570/R02473/R01466（uNb9QFRL6hY-36），`representation_limited`，不能补成完整分。
- 318份/26图有Pro多空间材料，其中现有路由222份`unavailable_top_pending`、95份`available`、1份不可用。**按旧GT可条件计算，不等于新确认空间的顶面可用。** 保留这两套参考语义，底面确认不提升顶面；缺顶面输出空完整分。

全体1332份、分层图片及建筑的完整清单见[COVERAGE.json](COVERAGE.json)。其中749可补算是输入几何与已知版本限制核对结果，不是新主校准人数；仍需保持未知范围、旧开发曝光和参考条件记录。

## 旧24条人评怎么使用

24条全部具有旧条件描述开发许可；新来源政策下只有13条manual普通候选，另2条semi第二层、5条trap、4条来源未核。13条manual还须扣除T13/R03274较新边界意见对硬等级的暂停，以及T22/R02015已有`scope_confounded_latest=true`。因此最多11条旧manual弱等级可保留在条件开发比较中；不能称独立验证，不增加伪造标签。T13/T22的原回执继续保留，敏感性分析可明确展示，但不得装成无争议主池硬标签。

## 建议立即执行的顺序

1. 先修正用途账本字段解释，以“条件重评分允许、最终适用未认证、人工标签另审”拆开现有判据，恢复503份的条件描述覆盖。保持旧指标、冻结公式，不调参。
2. 为599份单参考候选建立明确对象ID与版本绑定并补算；150份双参考保留两个结果。先对照旧922的少数同条件记录验证指标实现一致，再扩展，不重新人工审核全部758份。
3. Pro多空间底面/完整结果单列，以变化来自参考还是公式分开归因；顶部未确认的222份不得当完整参考验收。
4. 只有上述结果揭示实际取舍且旧证据无法裁决时才请求少量人工介入。保持原房间留出及来源分层，不重跑大规模搜索，不更改融合算法。

## 复现与边界

运行`python -B -X utf8 -m tools.thesis_main.analysis.quality_reference_coverage_20261013`。读取当前完整manifest、全量用途账本、仓库Pro选择性归档及旧参数包的`inputs/calibration_records.json`。工具内断言核对1332份唯一性、71/503/758闭合、当前普通候选无人员/上下文barrier，以及未新增参考验收或校准授权；本地运行通过。

`COVERAGE.json`字段：`layer`为历史数值覆盖；`action`仅建议下一步计算；`existing_references.restrictions`按对象版本保留；`recorded_reference_gate`仅存来源对象字段，不能代替参考限制；`reusable_reference_ids`表示可作为条件几何输入，不能据此自动认证；`multispace_route`保留Pro历史输出，不修改路由。`images/buildings`聚合对应记录ID；`old24`保存旧gate与当前来源/标签限制。主用途账本可能进一步修正真正参考隔离的5份，因此本报告明确是修正前1332候选的定点审计，不构造新的正式资格层。

未逐图重新目视验收，未重新计算749份几何、未调参；本产物是可执行分层与来源核对。正式GT、原始作答、资格、旧结果均未改。项目地图与文档索引交主线程统一登记，避免并行改同一文件。
