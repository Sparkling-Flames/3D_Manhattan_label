# 按新增空间更新图片难度（2026-10-15）

> 已由[后续版本](../difficulty_review_update_20261015/README.md)接续。用户澄清范围是整个空间体竖向切分；本文“底面确认”是旧文件字段说明，不应再解释为只切地面。当前39图新范围与GT错误排除请使用后续版本，以下为历史快照。

当前规则：**凡有用户已确认的新增空间，一律以新增空间判断图片难度；旧范围仅作对照。** 先固定目标，再评价转折数量与必要的定位／推断负担，不因旧GT较复杂而把新空间判难。OOS、门洞和可标性仍为独立条件；本轮未调整难度阈值、未使用质量分数校准标签。

## 当前结果

入口：[复核工作台](review.html)、[259图表](current_259.csv)、[完整记录](current_259.json)、[37图新增范围采用清单](new_scope_adoption_37.csv)。全表为 **148简单、31中等、33困难、5待复核、42特殊单列**。37张已确认新增范围全部被采用，其中24简单、13中等。

本轮检查4张新范围照片和几何，其余沿用既有逐图审核；不能把这次更新描述为259张重新盲审。

| 图片 | 上一版 | 当前 | 依据 |
| --- | --- | --- | --- |
| uNb9QFRL6hY-86 | 待复核 | 简单 | 本次确认主体矩形空间，4个转折、H=0；主要角位可由墙线推断 |
| q9vSo1VnCiC-34 | 待复核 | 简单 | 本次确认主体矩形空间，4个转折、H=0；旧小分支不属于新目标 |
| B6ByNegPMKs-37 | 困难 | 简单 | 采用此前已确认但仅存于增量记录的新矩形范围 |
| UwV83HsGsw3-10 | 简单 | 简单 | 将此前增量范围正式绑定进当前难度表，等级不变 |

4图均为有效、包含相机的底面。H是实墙几何自遮挡量，不是照片中所有遮挡的计数；本次简单判断还结合照片的定位线索，不是仅凭H=0。家具挡住部分底角并不自动等于难以推断。此前7y3sRwLe3Va-03中等、7y3sRwLe3Va-26用户纠错GT及简单判断继续保留。

## 主数据接入与来源

本次回执原文件已原样保存于[主数据包](../../../analysis_results/research_input_20260929/scope_receipt_20261015.json)，其新增两图保存为[floor_scope_update](../../../analysis_results/research_input_20260929/floor_scope_update_20261015.json)，由主manifest登记。消费者使用 `load_current_bundle()['floor_scope_update']['records']`。该入口新增已确认底面参照，不覆盖原GT对象或人员作答，也不伪造完整上下点对。

回执是261条的整表快照，其中部分旧记录落后于已接受版本，因此仅接收本次补充的两图，不能用整表覆盖历史状态。此前另两图源自 `research/quality_scope_model_handoff_20261015/TWO_IMAGE_SCOPE_DELTA.json`，与 `research/difficulty_target_integration_20261015/new_target_addendum.json` 精确核对底面坐标；其余33图保留已有确认来源。37图采用清单并不表示这37图全部来自本次回执。

增量字段合同 `confirmed_floor_scope_update_v1`：

- `image_id`与`reference_id`绑定图片和新增底面；`original_reference_id`与`original_points_1024x512`核对被编辑原参照，禁止错图接入。
- `floor_xz_h`为相机高度归一化XZ底面；要求有限坐标、有效正面积多边形且相机在内部。
- `floor_region_confirmed=true`及`confirmed_at`记录显式确认；`source_receipt`、`source_pointer`、`confirmed_snapshot`保留回执来源。
- `top_boundary_pending=true`、`reference_ready=false`表示只确认了底面，不能当作完整GT。此限制不阻止当前条件式粗分类。
- `answer_to_candidate_assignments=[]`不推断人员作答采用了哪个空间。

难度表沿用既有字段：`target_version`对应`selected.target_id`，N/H由该目标底面计算，`current_class`为当前粗类，`conditional_difficulty`保留特殊图的条件式等级，`evidence`与`question`分别记录判断依据和未决问题。旧候选、旧审核及图片均保留在JSON/工作台中。当前机器入口为 `analysis_results/image_difficulty_full_review_20261010/CURRENT.json`。

## 复现与核验

运行 `python -m tools.thesis_main.analysis.difficulty_scope_received_20261015` 重建难度表和页面。构建包含37图全采用、259图计数、4图几何和既有增量坐标一致性断言，结果见[CHECKS.json](CHECKS.json)。新范围导入入口为 `tools/thesis_main/data_prep/floor_scope_update_20261015.py`。

针对性验证：`tests/test_floor_scope_update_20261015.py`及`tests/test_consolidate_research_input.py`，7项通过。另一个既有测试 `tests/test_current_research_input.py`仍断言旧环序数量1295，当前主数据已有1312，故该旧断言失败；本次未修改无关历史计数。没有运行全库测试。

本轮只更新图片难度及其必要输入；没有重算质量、共识曲线或按质量成绩改标签。分类仍包含照片人工辅助判断，不能在论文中称为纯机器分类或已验证的难度真值。
