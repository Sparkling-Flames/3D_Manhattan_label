# 冻结质量候选的当前条件数值视图

后续已完成[全量数据收尾及路由几何复算](../quality_data_closeout_20261013/README.md)。本页保留接入时的数值来源定义，不将后续复算冒称原接入步骤。

本视图只接入 Pro 已冻结的处理后几何指标和四个候选，不重建几何、不调参、不恢复人员资格。

覆盖922份旧输入（manual 589份，semi 333份）；与旧逐份CSV四候选最大差值为 2.84e-14。
全量manual仍为2344份；本输出不代表新增了包外manual评分。

## 评价对象与使用边界

- `scored_input=processed_mean_x_geometry`：评分对象为已有平均x处理后的条件几何；原始坐标、配对语义不由Q认证。
- `raw_input_penalty_included=false`：`raw_alignment`保留原始上下点经度差诊断，不加权进Q；大经度差本身也不等于语义配对错误。
- `conditional_diagnostic_use=true`：922份可在各自冻结参考条件下比较数值，并非都可作主校准、人员评级或独立检验。
- `old_applicability_confirmed=false`仅表示旧显式适用子层未确认，不自动等价于参考错误。当前账本numeric_barriers按原值留存，不能仅据其中这一状态封禁条件数值分析。
- `strict_old_admission_subset`要求当前账本full_q_calibration_ready且旧applicability_confirmed=true，供复核旧显式适用子层。它不是本工具重新授予资格。
- `admission`保留来源、人员gate、当前role、人员/上下文/数值限制及原留出。限制不改分；使用范围必须另行遵守，留出不能回流调参。
- 缺高度时完整score与高度损失为null，floor_score单列；不能将缺项补零或当完整质量。

## 分项与结果

`scores`下四候选均给出底面分、完整分、边界/方向/整体高度/局部高度损失及高度引起的降分。`SUMMARY.json`按来源和当前role描述分数变化；它们是同样本数值变化，不是有效性排名。

| 候选 | 922份均分 | 相对baseline均值变化 |
|---|---:|---:|
| baseline_quad08 | 67.680 | +0.000 |
| J_main_hill_tail12_g1_l025 | 66.949 | -0.730 |
| J_simple_power8_g1_l025 | 70.595 | +2.915 |
| J_local_joint_hinge10_w2_s8 | 70.077 | +2.397 |

旧严格视图共71份，仅保留历史筛选口径。

## 已有多空间路由结果的独立接入

`ROUTED_EXISTING_VIEW.json`原样复用Pro四方比较表的new_route_new_formula，按record_id/candidate/score_kind绑定routes中的selected_candidate_id。三个J候选分别保留floor/full，空值不补零，不移植其他参考的顶部。

路由共429份，覆盖：{'full': 131, 'floor_only': 286, 'unavailable': 12}。其中原922之外的普通manual开发候选覆盖：{'full': 95, 'floor_only': 217, 'unavailable': 1}。
此输出与922份冻结参考视图分开：两者参考可能不同，不覆盖或拼接为统一的完整分。保留原路由版本、人工影响、参考不确定性、当前用途限制与原始诊断。
参考沿用已有人工作答指定、候选族限制与局部结构优先/底面接近兜底；不按最高Q重选。执行时核对5项人工指定和2项候选族限制。四参考T30/R02962保留人工D；W031/W034仅限A/B族，不能称人工指定B。旧原始/修订GT的双版本敏感性列不等于此处多空间路由。
另有包外manual因原完整参考受限而单列：{'floor_only': 5}。q9vSo1VnCiC-16的5份替代底面结果不自动被原GT限制否定，但不能移植顶面或恢复原完整GT；原318份覆盖现分为313份普通候选与这5份参考条件不同的诊断。该summary历史字段名只统计现有完整参考限制，不表示所有替代底面也被禁用。
`numerical_provenance`明确这些是已有Pro结果，未在本地重建几何；核对的是记录身份、所选参考标识和空值边界，不授予正式资格或独立拟合资格。
[原始标注与处理后几何的证据核对](../quality_processed_input_20261013/README.md)。

## 复现与检查

`python -B -m tools.thesis_main.analysis.quality_current_candidate_view_20261013`

`python -B -m pytest tests/test_quality_current_candidate_view_20261013.py -q`

四个边界检查：原始诊断/资格变化不改变固定几何分数；缺高度不补零；旧适用子层未确认不取消条件计算；复用路由缺顶部仍为null。执行时另逐份核对922份与旧CSV和路由身份/参考绑定。

未重跑网格、未改变正式算法或历史输入；参考是否适合当前研究与指标是否符合人评，仍需独立证据。
