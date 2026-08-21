# Paper A：导师版客观发现与不确定性分析（v4）

## 结论先行

当前 25 个 Manual/Semi 同图任务覆盖 9 个 building。精确方向为：收敛 10、完全不变 4、扩散 11。平均 ΔH=-0.010005，building bootstrap 95% CI [-0.219446, 0.176604]，精确 building sign-flip p=0.914062。证据支持“总体接近零、图像间异质”，不支持统一的净收敛或净扩散。

采用预先固定的 ±0.05 近零带时，收敛/近零/扩散为 10/4/11。因此，论文最稳妥的研究对象不是‘Semi 是否普遍更好’，而是 proposal 如何改变标注分布、在哪类图像上收敛或扩散，以及标签—操作—几何之间何时不一致。

## 1. 已复核的新增客观发现

| finding_id                        | evidence_class                 |   n_tasks |     estimate |    ci_lower |    ci_upper |       p_value | secondary_counts                                                                 | interpretation_zh                                                             |
|:----------------------------------|:-------------------------------|----------:|-------------:|------------:|------------:|--------------:|:---------------------------------------------------------------------------------|:------------------------------------------------------------------------------|
| paired_entropy_overall            | current_outcome                |        25 |  -0.0100053  |  -0.219446  |   0.176604  |   0.914062    | {"convergence": 10, "no_change": 4, "expansion": 11}                             | 总体均值接近零且 building 区间跨零；当前没有净收敛或净扩散方向。              |
| formal_preassignment_risk         | frozen_preassignment           |        22 | nan          | nan         | nan         | nan           | {"n_ready": 0}                                                                   | 正式冻结的标注前 predictor 当前不可用；结论是不可评价，不是没有关系。         |
| legacy_gt_pair_count              | legacy_preoutcome_proxy        |        22 |   0.296676   |  -0.103803  |   0.646562  |   0.180009    |                                                                                  | 旧代理与当前结果的探索性相关；未检出稳定关系。                                |
| legacy_occlusion                  | legacy_preoutcome_proxy        |        22 |   0.580043   |   0.0967111 |   1.06261   |   0.198381    | {"present_n": 11, "absent_n": 11, "present_expansion": 7, "absent_expansion": 3} | 旧代理仅作候选线索。                                                          |
| manual_worker_tag__occlusion      | worker_postresponse_tag        |        22 |  -0.00275354 |  -0.179721  |   0.22722   |   1           | {"present_n": 21, "absent_n": 1, "present_expansion": 10, "absent_expansion": 0} | 工人响应后标签不是独立标注前图像特质。                                        |
| manual_worker_tag__seam           | worker_postresponse_tag        |        22 |  -0.418832   |  -0.839189  |   0.0587156 |   0.204334    | {"present_n": 8, "absent_n": 14, "present_expansion": 2, "absent_expansion": 8}  | 工人响应后标签不是独立标注前图像特质。                                        |
| manual_worker_tag__trivial        | worker_postresponse_tag        |        22 |   0.124555   |  -0.375085  |   0.854836  |   1           | {"present_n": 17, "absent_n": 5, "present_expansion": 8, "absent_expansion": 2}  | 工人响应后标签不是独立标注前图像特质。                                        |
| manual_worker_tag__reflection     | worker_postresponse_tag        |        22 |  -0.00203014 |  -0.545158  |   0.467176  |   0.347634    | {"present_n": 6, "absent_n": 16, "present_expansion": 4, "absent_expansion": 6}  | 工人响应后标签不是独立标注前图像特质。                                        |
| manual_worker_tag__low_texture    | worker_postresponse_tag        |        22 |  -0.150196   |  -0.694511  |   0.278887  |   1           | {"present_n": 9, "absent_n": 13, "present_expansion": 4, "absent_expansion": 6}  | 工人响应后标签不是独立标注前图像特质。                                        |
| manual_entropy_algebraic_coupling | algebraically_coupled_baseline |        25 |  -0.688208   | nan         | nan         |   0.000143165 |                                                                                  | ΔH 含有 -H_Manual，存在代数耦合、地板效应和回归均值；不能解释为独立难度效应。 |

正式冻结的标注前风险变量目前 n_ready=0，因此只能写‘不可评价’，不能写‘没有关系’。旧版 22-task proxy 已重新连接到当前 v4 ΔH，未继承旧文件中的过时 outcome 列。

旧 occlusion proxy 的 present−absent 平均 ΔH 差为 0.580043，但样本仅 22 个任务、区间宽且 Fisher p=0.198381，只能作为后续预注册候选。Manual entropy 与 ΔH 的 Spearman ρ=-0.688208（p=0.000143165）主要受 ΔH=H_Semi−H_Manual 的代数耦合影响，不能解释为独立难度效应。

## 2. Proposal 编辑行为

| predictor                    | outcome               |   n_tasks |   n_buildings |   spearman_rho |   cluster_ci_lower |   cluster_ci_upper |   unadjusted_p | evidence_class          | interpretation_zh                                                       |
|:-----------------------------|:----------------------|----------:|--------------:|---------------:|-------------------:|-------------------:|---------------:|:------------------------|:------------------------------------------------------------------------|
| edit_rate                    | delta_shannon_entropy |        25 |             9 |      0.401714  |         -0.0211248 |          0.709509  |     0.046537   | posttreatment_mechanism | 共现/机制描述，不能作为首次分配前 predictor，也不能解释为编辑导致扩散。 |
| edit_rmse_mean               | delta_shannon_entropy |        21 |             9 |      0.0229133 |         -0.408696  |          0.365659  |     0.921468   | posttreatment_mechanism | 共现/机制描述，不能作为首次分配前 predictor，也不能解释为编辑导致扩散。 |
| negative_metric_change_count | delta_shannon_entropy |        25 |             9 |      0.532615  |          0.2404    |          0.78459   |     0.00612532 | posttreatment_mechanism | 共现/机制描述，不能作为首次分配前 predictor，也不能解释为编辑导致扩散。 |
| delta_quality_iou            | delta_shannon_entropy |        22 |             9 |     -0.42416   |         -0.794092  |         -0.0594277 |     0.0491388  | concurrent_outcome      | 共现/机制描述，不能作为首次分配前 predictor，也不能解释为编辑导致扩散。 |

编辑率、编辑幅度、负向指标变化数和质量变化均是看到 proposal 之后产生的机制/并发量，不是首次派发前 predictor。相关关系不能证明‘编辑导致扩散’，也不能把指标下降定性成错误修改。

`acceptable` 后仍移动角点算残余调整证据；只有当变化较大、改变拓扑、进入非主模式或与冻结参考明显分离时，才是较强的标签—几何不一致证据。小幅、同拓扑、仍在主模式的调整更接近局部精度修正。

## 3. Crowd、少数模式与 GT

| cause_code                                        |   task_condition_count |   unique_task_count |   manual_review_priority_count |   median_GT_gap |
|:--------------------------------------------------|-----------------------:|--------------------:|-------------------------------:|----------------:|
| visibility_or_appearance_evidence                 |                     98 |                  79 |                             49 |       0         |
| scope_or_adjacent_space_extent                    |                     60 |                  54 |                             38 |       0         |
| different_wall_count_or_topology                  |                     58 |                  52 |                             37 |       0         |
| panorama_seam_boundary                            |                     47 |                  42 |                             27 |       0         |
| room_height_or_vertical_extent                    |                     42 |                  40 |                             26 |       0         |
| floor_boundary_interpretation                     |                     25 |                  25 |                             18 |       0.0406725 |
| ceiling_boundary_interpretation                   |                     17 |                  17 |                              7 |       0         |
| horizontal_wall_boundary_placement                |                      7 |                   7 |                              5 |       0         |
| mixed_or_not_identifiable_from_available_geometry |                      2 |                   2 |                              0 |       0         |

101 个 Crowd–GT task-condition 全部保留。多数模式、受支持少数模式和 operational GT 之间的冲突是审计对象，不自动判定任一方为真实几何；差异只按墙数/拓扑、顶边、底边、高度、水平边界、接缝、Scope 与可见性作可观察分类。

## 4. 数据语义与可追溯性

raw 记录 2513 条，selected/canonical 记录 2501 条，raw-only 可审计版本 12 条。raw-only 只按 stage/project/task/worker 上下文映射到 selected 记录，不推断版本时间先后。

| time_measurement_lane         |   record_count |   active_time_observed_count |   lead_time_observed_count | script_versions                                                                                                                                                                                                                                                                                                                                                                                                                                | interpretation_zh                                                   |
|:------------------------------|---------------:|-----------------------------:|---------------------------:|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:--------------------------------------------------------------------|
| c1_active_time_missing        |             79 |                            0 |                         79 | not_recorded;stage1_active_time_annotation_hardening_20260701_v1;stage3_active_time_page_gate_20260711_v2                                                                                                                                                                                                                                                                                                                                      | Active time 按冻结来源保留；脚本版本未记录时明确标为 not_recorded。 |
| c1_formal_active_log          |            701 |                          701 |                        701 | 0.24-official;c2plus_task_worker_active_time_20260802_v1;stage1_active_time_annotation_hardening_20260701_v1;stage1_helper_ordercache_hotfix_20260617_v1                                                                                                                                                                                                                                                                                       | Active time 按冻结来源保留；脚本版本未记录时明确标为 not_recorded。 |
| lead_time_proxy_excluded      |            353 |                            0 |                        353 | 0.24-official;not_recorded;stage1_helper_ordercache_hotfix_20260617_v1                                                                                                                                                                                                                                                                                                                                                                         | 仅有 Label Studio 经过时间；不得进入 Active time 汇总。             |
| other_stage_formal_active_log |           1368 |                         1368 |                       1368 | 0.24-official;0.26-foreign-https-en-standalone;0.26-official;0.27-foreign-https-en-standalone;0.28-foreign-https-en-standalone;0.29-foreign-https-en-debug;0.29-foreign-https-en-standalone;0.30-foreign-https-en-debug;0.30-foreign-https-en-standalone;c2plus_task_worker_active_time_20260802_v1;c2plus_task_worker_active_time_20260802_v2;stage1_active_time_annotation_hardening_20260701_v1;stage1_helper_ordercache_hotfix_20260617_v1 | Active time 按冻结来源保留；脚本版本未记录时明确标为 not_recorded。 |

Lead time 始终与 Active time 分开。所有 214 个涉及任务均保留远程引用；本机可找到的图片与 Git 跟踪图片分别标记，不把未提交的本机原图误写成仓库证据。

## 5. 研究判断

当前数据足以支持一篇以‘异质性、残余不确定性与 proposal 响应机制’为核心的探索性分析，也足以给出完整的质量/共识/时间审计；但不足以对 Semi 的总体因果效应、某类图像的稳定预测效应或真实 GT 错误率下定论。增加独立图片和 building 比只在现有少量图片上增加工人更能缩小总体效应的不确定性。

后续正式验证应在标注前独立冻结图像特质、proposal 诊断、分配概率和 worker 暴露，并把 final geometry、tags、active time、lead time 与 edit trace 保持为标注后结果/机制字段。

## 交付索引

完整逐行证据在同目录 CSV 与工作簿中；方法、变量定义和全量 25/101/54 实例在《复核证据附录》中。v4 不包含 ZIP、原图或缩略图分页。
