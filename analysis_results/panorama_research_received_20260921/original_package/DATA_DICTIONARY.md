# 输出字典与读数边界

## 通用字段

`image_id`为源全景规范ID；`code`或`a_code/b_code`通常使用完整building名称加序号，报告采用源习惯简称（例如S9h-06）；`worker`为真实W编号；canonical annotation ID保留在作答与案例表。`N`为该图可用于当前计算的独立真人数；`n`为团队人数；`k`为已经观察的人数；`tail`是持续起点检查所需的后续观察人数。缺失/空值表示不可算或没有结果，不当成零。

`pair_disagreement`/G是阈值外的作答对比例；`count_disagreement`是有效点数不等的比例，**不是错误率**。阈值25.6像素，1024×512投影，横向环绕。同点数对应保留上下绑定；不同点数的1e6值为不可相容哨兵，不代表实际100万像素。

`U5/U8`或`uncovered,k`是有限已见真人池中、无放回观察k人后下一份未被覆盖的概率，计算详见报告公式。它不是未来无限人群的缺失质量，也不表示布局正确。

## 文件族

| 文件 | 粒度／关键含义 |
|---|---|
|validation.json / floating_roundoff.csv.gz|源参考输出和独立复算核对；只容许已说明浮点尾差|
|eligibility_reconstructed.csv.gz|资格与几何可用性，不把描述池全部视作预测合格|
|response_metrics.csv|逐真人作答的同图分歧、点数、来源；含目标观察结果，不可直接当标注前特征|
|image_metrics.csv|逐图N、G、U(k)、不同方法／容差分区和单人表达指标|
|pair_diagnostics.csv.gz|19196个作答对；点数门、最大端点、局部超阈值、环序与自由匹配敏感性|
|current_memberships.csv|方法×容差×图的成员分区；同簇语义因完整链接／代表半径而不同|
|local_vs_joint.csv|同点数子池的局部和联合覆盖；不能忽略子池之外的不同点数作答|
|uNb21_endpoint_before_after.json|用户已确认对应带来的距离变化，不是新人工裁决|
|uNb47_local_stage_case.json / uNb47_local_coverage_curve.csv|选定实际局部案例的持续起点与无放回覆盖|
|replay_orders.json|200条完整25人无放回顺序，种子固定；各图只选实际有作答者|
|replay_image_cache/ / replay_cache_manifest.json|240个图缓存及原输入／算法校验信息；缓存不是新样本|
|replay_prefixes.csv.gz|实际前缀统计；每个前缀重新分簇，不用全池标签反推|
|replay_curves.json|L为稳定比例，U为稳定加未知比例；这里U不是未覆盖概率|
|replay_onsets.csv|图×方法×容差变化门槛×尾段×限制配置的起点及状态|
|replay_order_onsets.csv.gz / order_variability.csv|每条顺序的起点及条件分位数；条件分位数不忽略失败率|
|replay_reasons.csv.gz / replay_failure_reasons.json|成员、份额、新获重复支持等失败原因，原因可以重叠|
|permutation_MC_precision*.csv/json|200次重放导致的数值精度，非未来人群置信区间|
|worker_lobo_profiles.csv|每个heldout_building的训练图片／建筑和效应；目标建筑必须不在训练字段|
|worker_lobo_predictions.csv.gz|中心化几何／点数分歧的留建筑预测；value是标签，prediction是隔离预测|
|worker_prediction_summary.json|预测MSE、零基线MSE、相对改善、绝对改善的条件区间|
|worker_image_dependence.csv|单人跨图变化，不是同人重复作答的test–retest噪声|
|team_panels.csv|图×团队人数的可行组合数、实际唯一抽样数和结果分位|
|team_composition_variance.csv.gz|同配比成员方差＋配比间方差恒等分解；组合大量重叠|
|composition_summary.json|仅有变动面板的方差比例，同时保留全部面板分母|
|same_composition_member_examples.csv|观测极端团队的名单，非推荐最优人员或质量排序|
|room_inventory.csv|已有审核的房间关联、可比性与当前覆盖|
|room_scene_predictions.csv / room_scene_summary.json|物理同房、可比同房、同主空间类别的预测与建筑外基线|
|same_room_identical_workers.csv / common_worker_control_summary.json|两图仅使用完全相同真人，匹配前后差异；视角对不独立|
|same_room_onset_transfer*.csv/json|源／目标起点都可判、单侧可判、都不可判的完整分母|
|q9_preexisting_range_review.json / case_spatial_source_excerpts.json|用户此前空间／范围判断，不是按此次结果新分组|
|model_feature_lobo_predictions.csv / model_feature_summary.json|冻结模型特征的目标建筑外回归与预测|
|model_N_roster_controls*.csv/json|同面板上N、人员画像、模型角数与模型间差异的增量|
|frozen_time_panel.csv / time_summary.json|历史冻结时间；无本批未冻结时间，不作认真程度因果判断|
|ray_derivative_probes.csv.gz / geometry_summary.json|真实端点及±1像素机制探针；扰动不是人工作答|
|regularization_mechanism_panel.csv / regularization_mechanism_inputs_outputs.json|哈希选取46份真实作答的实际拟合、失败及残差|
|js_projector_inputs.json / js_projector_validation.json|真实角对输入、实际JS函数对照；不声称完成WebGLUI或物理GT验收|
|manual_semantic_case_queue.csv|五个新候选问题及已关闭对照，带点号／对应和明确问题|
|optional_new_common_panel_costs.csv|共同12/16/20人最少新增首次作答数，历史暴露限制；非已采集成果|
|retained_oos_lane.csv / oos_retention_summary.json|OOS来源保留记录，不等同语义真OOS已逐图裁定|

## 起点状态

`identified`：可能与保守起点重合；`bounded_unknown`：两者存在但不同；`possible_only`：只有可能起点；`not_reached`：本规则和观测窗口内未达标；`insufficient_tail`：尾段不足。具体配置及下／上界见表；不把未知填成成功、最大N或永不收敛。

## 统计与外推

训练／预测以建筑留出，不等于未见人员留出。画像、模型、房间三个模块的目标面板并非完全相同，禁止跨表直接排名优劣。画像预测为相对同图人群的中心化偏离；它不预测绝对质量。条件建筑重采样只重采已拟合后的建筑摘要，不全管线重新拟合，也没有完成所有探索性比较的多重校正。CSV中的全部小数保留可复核精度，不意味着该精度的统计确定性。
