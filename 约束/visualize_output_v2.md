# visualize_output_v2 约束规范（详细执行稿）

## 0. 文档定位

本文档不是 Notebook 使用说明，而是 Dev A 与 Dev B 之间的数据契约。

其目的有三项：
1. 锁死 visualize_output_v2.ipynb 与相关 plotting 脚本读取的单一真源字段。
2. 规定图 D、表 C、Type 1-4 统计、active_time 审计的最小输入列与披露口径。
3. 防止下游 Notebook 在绘图时临场推断字段含义、临时改名或混用旧口径。

---

## 1. 单一真源

### 1.1 SSOT 文件
唯一标准输入为 merged_all.csv。

要求：
- 每行表示一个 annotator 对一个 task 的一次最终提交记录。
- 所有论文主图表均从该文件读取，不允许每个 Notebook 再拼私有中间表作为隐性真源。
- 若某图只使用聚合表，该聚合表也必须由 merged_all.csv 可重建。

### 1.2 值域冻结
- condition 统一使用小写：manual / semi。
- type3_flag 的语义统一为几何合法性失败，不再使用“门控失败反例”旧表述。
- W_tot = 0 的记录在上游应记为 NA，并在下游图表或附表中披露频次，不允许 silently fallback。
- scope 原字段使用 XML raw alias：normal / oos_geometry / oos_open_boundary / oos_split_level / oos_insufficient / missing；若图注或正文使用 in_scope / oos_multi_plane，则必须由固定映射派生。

---

## 2. merged_all.csv 最小字段契约

### 2.1 基础标识

| 字段 | 类型 | 约束 |
|---|---|---|
| task_id | string | 当前导入任务唯一标识 |
| base_task_id | string | 同源任务去重主键 |
| annotator_id | string | 标注员唯一标识 |
| condition | string | 仅允许 manual / semi |
| dataset_group | string | 例如 Calibration_manual / Validation_semi / Manual_Test |
| subset | string | 如 core / reserve / audit |

说明：
- dataset_group 是发布层保留的阶段-条件联合标识，也是当前导入链路与分析脚本的主字段。
- 若下游 Notebook 需要更粗粒度的阶段汇总，可在读取时由 dataset_group 派生 stage_family，但不得把派生字段反写成新的主真源。

### 2.2 任务标签与审计标签

| 字段 | 类型 | 约束 |
|---|---|---|
| scope | string | normal / oos_geometry / oos_open_boundary / oos_split_level / oos_insufficient / missing |
| difficulty | string | 多选分号拼接；若 trivial 出现则必须互斥 |
| model_issue | string | 多选分号拼接；若 acceptable 出现则必须互斥 |
| scope_filled | bool | 上游是否正确拿到 scope |
| is_oos | bool | 由 scope 派生，不允许手工随意改写 |
| source_type | string | manual_anchor / synthetic_operator / natural_failure |
| worker_group | string | stable / vulnerable / noise / ungrouped |
| worker_group_reason | string | 记录进入该组的规则依据 |
| group_rule_version | string | 分组规则版本号 |

兼容说明：
- 若当前数据仍保留 `scope_missing` 兼容字段，Notebook 可将其视为 `not scope_filled` 的等价旧字段，但新代码不应再把 `scope_missing` 作为唯一真源。
- 若当前数据仍保留 `model_issue_types`，可仅作为兼容旧分析链的辅助列；主契约字段仍是 `model_issue` 与 `model_issue_primary`。

### 2.3 质量与一致性指标

| 字段 | 类型 | 约束 |
|---|---|---|
| iou | float | [0, 1] |
| iou_edit | float or NA | semi 下通常有效；manual 可为 NA |
| iou_to_consensus_loo | float or NA | [0, 1] 或 NA |
| IAA_t | float or NA | [0, 1] 或 NA |
| r_u | float or NA | 工人全局可靠度 |
| r_u_lcb | float or NA | 可靠度下界 |
| S_u | float or NA | spammer score |
| r_u_s | float or NA | 工人-场景特异可靠度 |
| r_u_s_lcb | float or NA | 若表 C 使用保守判定，建议同时保留 |
| W_tot | float or int | 共识权重总和；为 0 时相关派生量必须 NA |

### 2.4 Type 1-4 标志

| 字段 | 类型 | 语义 |
|---|---|---|
| type1_flag | bool | 低一致性反例 |
| type2_flag | bool | 异常编辑模式反例 |
| type3_flag | bool | 几何合法性失败反例 |
| type4_flag | bool | 流程 / 字段 / 格式失败反例 |

### 2.5 active_time 审计字段

| 字段 | 类型 | 约束 |
|---|---|---|
| active_time | float | 单位秒；非负 |
| session_count | int | 同一 task-annotator 聚合的 session 数 |
| has_short_time_flag | bool | active_time < 1s |
| has_long_time_flag | bool | active_time > 3600s |
| has_unknown_id_flag | bool | task_id 或 annotator_id 缺失 / unknown |
| project_id | string or NA | 审计日志关联项目标识 |
| script_version | string or NA | active_time 采集脚本版本 |

---

## 3. 图表输入契约

### 3.1 T / I / M 三口径分布图

最小输入列：
- condition
- scope
- is_oos
- type3_flag

固定口径：
1. T：全部记录。
2. I：is_oos = False。
3. M：is_oos = False 且 type3_flag = False。

要求：
- 若 scope_filled = False 的记录存在，必须在图注或相邻附表中披露。
- 不允许把 missing scope 静默并入 in_scope。
- 若图中使用 in_scope / oos_multi_plane 等论文表述，必须显式声明映射：normal -> in_scope，oos_split_level -> oos_multi_plane。

### 3.2 IAA 直方图

最小输入列：
- IAA_t
- difficulty
- condition

要求：
- difficulty 为多选字符串时，Notebook 必须采用固定拆分规则。
- 若采用“主 difficulty”折叠规则，必须在图注中声明。

### 3.3 IoU_edit vs IoU_to_consensus_loo 散点图

最小输入列：
- condition
- iou_edit
- iou_to_consensus_loo
- type3_flag
- W_tot

要求：
- 默认只画 semi。
- W_tot = 0 导致的 NA 点不得伪造为 0。
- 图注必须说明去除了多少个 NA 点。

### 3.4 Type 1-4 反例频次图

最小输入列：
- dataset_group
- type1_flag
- type2_flag
- type3_flag
- type4_flag

要求：
- 频次统计必须能按 dataset_group 披露。
- 若论文正文或图注需要更粗层级汇总，可由 dataset_group 映射到 stage_family 后再聚合，但映射表必须固定并公开。
- 若某类频次来自 audit-only 子集，必须在图注或表注中说明。

### 3.5 active_time 审计图 / 表

最小输入列：
- annotator_id
- active_time
- session_count
- has_short_time_flag
- has_long_time_flag
- has_unknown_id_flag
- project_id
- script_version

强制披露：
1. 全体记录中 short / long / unknown 的数量与占比。
2. 每位 annotator 的 total_time、mean_time、median_time、p95_time、p99_time。
3. 多 session 记录数占比。
4. unknown task / annotator / project 的拆分数量与占比。
5. script_version 缺失或混杂版本的数量与占比。
6. 若存在裁剪、排除或 winsorize，必须说明，且主分析与审计分析分开。

---

## 4. 图 D 约束

### 4.1 最小输入列
- annotator_id
- r_u_lcb
- S_u
- worker_group
- worker_group_reason
- group_rule_version

### 4.2 固定语义
- 横轴：S_u
- 纵轴：r_u_lcb
- 颜色或形状：worker_group

### 4.3 强制披露
1. 分组阈值来自哪个预注册规则版本。
2. ungrouped 工人是否存在，若存在如何处理。
3. 若 worker_group 是回写字段，必须与 group_rule_version 一并冻结，不允许后续人工覆盖后不留痕。

---

## 5. 表 C 约束

### 5.1 最小输入列
- annotator_id
- core_scene
- r_u_s
- r_u_s_lcb 或等价保守判定字段
- worker_group
- n_us 或可由 merged_all.csv 稳定重建的场景样本数

### 5.2 表格语义
- 行：annotator_id
- 列：core_scene
- 单元格：r_u_s 或其保守版本

### 5.3 强制披露
1. 场景列集合是固定核心集还是 top-k 高频集。
2. 样本量不足时显示 NA / -- 的规则。
3. 若使用“LCB 低于阈值”或“CI 重叠”做标红，必须明确写出判定规则，不得只写“显著较差”。
4. 若某 annotator 在某 scene 样本数过少，不得输出貌似精确的小数。
5. 必须披露采用的最小样本量门槛，如 N_us_min，以及低于门槛时的降级规则。
6. 若正文使用局部失效标记，必须明确 failure_u_s 的判定规则，而不是仅靠颜色暗示。

---

## 6. Notebook 行为边界

### 6.1 允许的事情
- 从 merged_all.csv 读取。
- 做确定性的筛选、聚合、透视、绘图。
- 输出 PNG、CSV summary、LaTeX table fragments。

### 6.2 不允许的事情
1. 在 Notebook 里临时重定义 condition 值域。
2. 在 Notebook 里把 Manual / Semi 与 manual / semi 混用。
3. 在 Notebook 里把 W_tot = 0 的记录补成 0 或均值。
4. 在 Notebook 里重新推断 worker_group 却不写回规则版本。
5. 在 Notebook 里对 scope 缺失记录静默补全。

---

## 7. 输出物要求

### 7.1 figure exports
至少支持导出：
- T / I / M distribution figure
- IAA histogram
- IoU_edit scatter
- Type 1-4 summary
- worker profile figure
- active_time audit figure

### 7.2 table exports
至少支持导出：
- worker-scene matrix summary
- active_time audit summary
- missing / NA disclosure summary

### 7.3 export 命名
输出文件命名应包含：
- figure or table id
- date or run tag
- rule_version 或 data snapshot id

---

## 8. 验收清单

1. merged_all.csv 是否已覆盖本文规定的最小列。
2. condition 是否已统一为 manual / semi。
3. type3_flag 是否已统一为几何合法性失败语义。
4. worker_group 是否伴随 worker_group_reason 与 group_rule_version 一起冻结。
5. 表 C 是否写清楚 NA / 标红 / 样本量不足规则。
6. active_time 审计是否披露 short / long / unknown / multi-session。
7. 所有图表是否都能从 merged_all.csv 单独重建。

---

## 9. 当前结论

visualize_output_v2 的本质不是“画图脚本说明”，而是论文可复现输出的下游契约。主线要求只有一句话：

上游字段先冻结，下游 Notebook 只消费，不再发明口径。
