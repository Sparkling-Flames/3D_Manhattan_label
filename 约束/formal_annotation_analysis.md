# 正式标注分析契约（新服务器 / 正式实验专用）

## 0. 定位

本文档用于正式实验开始后的主分析链。

它与兼容性文件的关系是：
- [约束/merged_all.md](约束/merged_all.md)：发布层 schema 真源，允许说明旧字段兼容。
- [约束/visualize_output_v2.md](约束/visualize_output_v2.md)：当前下游绘图契约，仍保留少量兼容说明。
- 本文件：正式实验专用契约，不再为旧服务器旧导出字段保留主路径兼容。

换言之，正式实验阶段应优先遵守本文，而不是继续围绕旧导出做兼容设计。

---

## 1. 适用前提

1. 数据来自新服务器、正式标注项目、正式 userscript 版本。
2. Label Studio XML 已冻结为当前 ontology。
3. 主分析只接受新的发布层字段，不再依赖旧兼容列推断语义。

---

## 2. 正式实验主字段

### 2.1 必须直接消费的字段
- task_id
- base_task_id
- image_id
- annotator_id
- dataset_group
- condition
- subset
- scope
- is_oos
- difficulty
- model_issue
- has_model_issue
- model_issue_primary
- scope_filled
- difficulty_filled
- difficulty_conflict
- model_issue_required
- model_issue_missing_required
- model_issue_conflict
- iou
- iou_edit
- IAA_t
- iou_to_consensus_loo
- boundary_rmse
- corner_rmse_match
- W_tot
- r_u
- r_u_lcb
- r_u_ucb
- h_u
- r_u_s
- r_u_s_lcb
- S_u
- worker_group
- worker_group_reason
- group_rule_version
- core_scene
- d_t
- d_t_status
- d_t_k
- d_t_ref_hash
- d_t_model_ver
- d_t_metric
- d_t_pool_size
- d_t_failure_reason
- d_t_compute_ts
- g_t_triggered
- g_t_status
- active_time
- session_count
- has_short_time_flag
- has_long_time_flag
- has_unknown_id_flag
- project_id
- script_version
- type1_flag
- type2_flag
- type3_flag
- type4_flag

### 2.2 兼容字段的正式地位
以下字段允许存在于 CSV 中，但正式分析主链不应再把它们当作主输入：
- scope_missing
- difficulty_missing
- model_issue_missing
- model_issue_types
- difficulty_conflict_v2
- model_issue_conflict_v2
- is_normal

这些字段只能作为：
1. 历史对账辅助。
2. 旧分析脚本迁移期的临时桥接。

不得作为：
1. 新图表的主过滤条件。
2. 新统计表的真源。
3. 新论文图注中的定义依据。

---

## 3. 正式实验值域冻结

### 3.1 scope
正式实验中，scope 原字段保留 XML raw alias：
- normal
- oos_geometry
- oos_open_boundary
- oos_split_level
- oos_insufficient
- missing

论文/图注映射固定为：
- normal -> in_scope
- oos_split_level -> oos_multi_plane

### 3.2 condition
仅允许：
- manual
- semi

### 3.3 model_issue
仅允许：
- acceptable
- overextend_adjacent
- underextend
- over_parsing
- corner_drift
- corner_duplicate
- topology_failure
- fail

---

## 4. 正式实验图表原则

1. 所有主图只读取主字段，不再通过兼容字段兜底。
2. 若主字段缺失，应直接进入审计披露，而不是由兼容字段补推。
3. T / I / M、图 D、表 C、active_time 审计均按正式字段解释。
4. W_tot = 0 只记 NA，不补值。

---

## 5. 对调试 / 旧数据的态度

1. 旧服务器旧导出数据可以单独保留历史分析脚本或兼容链。
2. 但正式实验主结论不应再建立在兼容字段兜底之上。
3. 若必须回放旧数据，建议显式标记为 legacy replay，而不是混入正式实验主表。

---

## 6. 建议执行方式

1. 正式实验发布时继续产出 merged_all.csv。
2. 同时在 release manifest 中声明：本批数据遵循 formal_annotation_analysis.md。
3. Notebook / plotting scripts 逐步切换到只消费主字段。
4. 旧兼容字段保留一段迁移期后再删除。

---

## 7. 当前结论

正式实验开始后，最佳实践不是“继续无限兼容旧字段”，而是：

保留旧字段用于迁移，但主分析链只认冻结后的正式字段集合。
