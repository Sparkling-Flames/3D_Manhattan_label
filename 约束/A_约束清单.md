# 标注者 A 约束清单（硬约束，总门槛版）

说明：本文件是 Dev A 在 Phase 1 负责 `merged_all.csv`、可靠度估计、Type 1–4 标记与最终合并发布时的总门槛文件。
它不是 C1/C2/C3/可视化详细稿的替代品，而是 Dev A 在提交前必须逐项核对的 release gate。

上游真源与优先级：

1. 论文方法与报告：`01_研究问题.tex`、`02_方法.tex`、`03_实验设置.tex`、`04_报告与可审计输出.tex`
2. 附录：`A1_扰动算子库.tex`
3. 详细约束：`merged_all.md`、`visualize_output_v2.md`、`C1`、`C2`
4. 现有实现：`tools/analyze_quality.py`、`tools/meta_label_guard.py`、`tools/ls_userscript.js`

若本文件与上述详细规范冲突，以论文正文/附录和详细约束为准；本文件只负责把 Dev A 需要执行的门槛写清楚。

## 1. Dev A 交付的最低字段集合

### 1.1 主键与基础标识

- `task_id`
- `image_id`
- `annotator_id`
- `dataset_group`
- `condition`
- `subset`

### 1.2 元标签与合规审计字段

- `scope`
- `is_oos`
- `difficulty`
- `model_issue`
- `has_model_issue`
- `model_issue_primary`
- `scope_filled`
- `difficulty_filled`
- `difficulty_conflict`
- `model_issue_required`
- `model_issue_missing_required`
- `model_issue_conflict`
- `source_type`

### 1.3 质量与可靠度字段

- `iou`
- `iou_edit`
- `IAA_t`
- `iou_to_consensus_loo`
- `boundary_rmse`
- `corner_rmse_match`
- `W_tot`
- `r_u`
- `r_u_lcb`
- `r_u_ucb`
- `h_u`
- `r_u_s`
- `r_u_s_lcb`

### 1.4 路由与画像字段

- `S_u`
- `worker_group`
- `worker_group_reason`
- `group_rule_version`
- `core_scene`
- `d_t`
- `d_t_status`
- `d_t_k`
- `d_t_ref_hash`
- `d_t_model_ver`
- `d_t_metric`
- `d_t_pool_size`
- `d_t_failure_reason`
- `d_t_compute_ts`
- `g_t_triggered`
- `g_t_status`

### 1.5 反例与审计输出字段

- `type1_flag`
- `type2_flag`
- `type3_flag`
- `type4_flag`
- `active_time`
- `session_count`
- `has_short_time_flag`
- `has_long_time_flag`
- `has_unknown_id_flag`
- `script_version`

说明：

- `annotator_id` 是统一字段名；本项目发布层不再使用 `worker_id` 作为主字段名。
- `worker_group_reason` 与 `group_rule_version` 为论文正文已锁定的可追溯字段，不能省略。
- `d_t*` 状态字段必须与 C2 详细稿一致，不能只留一个裸 `d_t` 数值。
- `type3_flag` 的语义已锁定为“几何合法性失败”，不再使用“门控失败反例”旧口径。
- `dataset_group` 是发布层阶段字段真源；若下游需要粗粒度阶段汇总，只能派生，不得回写覆盖。

## 2. P0 阻断门槛（不满足即不能合并）

1. 单一真源：`merged_all.csv` 是 Single Source of Truth。任何图表、统计、路由模拟、审计输出都必须可由该表追溯；若关键字段缺失，不允许“先出图后补数据”。
2. 字段命名一致：发布表必须使用 `annotator_id`、`worker_group_reason`、`group_rule_version`、`d_t_status` 等最终字段名；不得在主表中混用 `worker_id`、`group_reason`、`dt_status` 等别名。
3. 元标签合规性兜底：即使前端 required 和 userscript 已启用，Dev A 仍必须在清洗层生成 `scope_filled` / `difficulty_filled` / `difficulty_conflict` / `model_issue_missing_required` / `model_issue_conflict`，并据此计算 `type4_flag`。不得以“前端已拦截”为理由省略离线审计字段。
4. OOS 值域一致：`scope` 的发布层 raw alias 必须与 XML 和 `tools/analyze_quality.py` 一致，即 `normal / oos_geometry / oos_open_boundary / oos_split_level / oos_insufficient / missing`。若报告层需要使用 `in_scope / oos_multi_plane` 等论文标签，必须通过冻结映射 `normal -> in_scope`、`oos_split_level -> oos_multi_plane` 派生，不得直接覆写原字段。
5. Type 4 过程证据不可丢：主分析输入可以只用 accepted 记录，但必须同时保留 reject/rejection 统计的证据链，包括：
   - `meta_label_guard.py` 的 accepted/rejected 清单与原因统计
   - `ls_userscript.js` / 本地审计日志中的提交拦截计数（如已聚合）
   - 系统侧 NA/导出缺损在 `merged_all.csv` 中的残余标记
6. `d_t` 零泄漏：Dev A 不得将任何人工标注派生字段（角点、IoU、worker group 等）用于 `d_t` 计算；若 `d_t` 无法计算，只能记录 `NA + d_t_status + d_t_failure_reason`，并在下游显式降级，不得静默替代 embedding 或补零。
7. 可靠度与分组可追溯：`worker_group` 必须可由 `r_u`、`r_u_lcb`、`S_u`、风险桶条件和冻结阈值重现；每条发布记录必须能追溯到 `worker_group_reason` 与 `group_rule_version`。
8. 预注册冻结不可事后漂移：`perturbation_plan_frozen.json`、`reference_pool_manifest.json`、分组规则版本、阈值版本必须写入版本/哈希/时间戳；任何主结论所用结果都必须能定位到唯一的 frozen artifact。

## 3. P1 强烈建议（不阻断，但默认应满足）

1. 参考池与代表性披露：除 `d_t_ref_hash` 外，建议同步保留 reference pool 的代表性摘要（scene/difficulty 分布与对全池差异），以便报告层直接复用。
2. `core_scene` 与 `r_u_s` 附带支持信息：建议额外保留 `core_scene_rule_version`、`n_us` 或等价样本量字段，避免表 C 中的 `--` 仅能从外部脚本反推。
3. `active_time` 审计字段补齐：建议保留异常辅助字段或中间表，至少能支持报告中要求的 unknown ID、script_version 缺失、多 session 占比。
4. 反例规则版本化：建议为 `type1_flag`–`type4_flag` 增加 `counterexample_rule_version` 或在报告元数据中统一记录版本，避免后续规则微调无法追溯。

## 4. P2 优化项

1. `validation_report.json` 建议统一包含：字段完整性、NA 比例、类型检查、分号编码一致性、Type 4 分解、简单 leakage 检查。
2. `worker_group_reason` 建议绑定到具体统计触发项（如 `noise_low_lcb`、`vuln_gap`、`vuln_bucket_fail`），不要写自然语言长句。
3. 建议对 `difficulty` / `model_issue` 统一采用 alias 顺序排序，保证 CSV 稳定性与 diff 可读性。

## 5. Dev A 必做的一致性检查

### 5.1 与 `merged_all.md` 对齐

- `merged_all.csv` 中的字段集合、类型、缺失规则必须与 `merged_all.md` 一致。
- `condition` 统一使用项目锁定值（当前为 `manual` / `semi`），不得在同一主表中混入 `Manual` / `Semi` 大小写变体。
- `scope` 必须明确是原始 alias 还是发布层 canonical 值；若做了 canonical 映射，必须在 README/manifest 中写明映射规则。
- 当前主表约定：`scope` 保留 XML raw alias；论文标签仅在报告层映射使用。
- `dataset_group` 为主字段；若下游派生 stage_family，只能在图表层完成，不得反写覆盖主表。
- 当前 `tools/analyze_quality.py` 仍可能保留 `scope_missing`、`model_issue_types` 等兼容字段；允许保留，但不得让这些兼容字段替代 `scope_filled`、`model_issue_primary` 等主字段口径。

### 5.2 与 C1 / 扰动清单对齐

- `model_issue` 的 alias 集必须与 XML 和附录 A1 一致。
- `perturbation_operator_id`（若写回）必须等于 C1 锁定 alias，不得出现工程内部别名。
- L3 intentional invalid 样本若进入中间表，必须标明 `na_intentional`，不得在主质量指标上伪装成正常样本。

### 5.3 与 C2 / `d_t` 约束对齐

- `d_t_status`、`d_t_ref_hash`、`d_t_model_ver`、`d_t_failure_reason` 必须来自 C2 输出，不得由 Dev A 自行猜填。
- 若 `d_t` 不可用，降级策略只能体现在下游使用逻辑与审计披露，不得在主表里回填默认值。

### 5.4 与 `visualize_output_v2.md` 对齐

- 主表必须足以支持 T/I/M、IAA 分布、Type1–4、active_time、图 D、表 C 的全部输入。
- 若某图表还依赖表外中间文件，则必须在提交时明确写入依赖，不得默认“notebook 自己再算”。
- 若图表层需要按粗粒度阶段聚合，必须由 `dataset_group` 映射得到，映射表需冻结并公开。

## 6. 可验收测试（Dev A 侧最小集合）

- `tests/test_fields.py`
  - 验证主键、元标签、审计字段、可靠度字段、`d_t*` 状态字段、反例字段是否齐全。
  - 验证 `dataset_group`、`condition`、`scope` 值域是否落在冻结集合内。
- `tests/test_type4_audit.py`
  - 验证 `scope_filled` / `difficulty_filled` / `difficulty_conflict` / `model_issue_missing_required` / `model_issue_conflict` 能正确驱动 `type4_flag`。
- `tests/test_group_traceability.py`
  - 验证 `worker_group`、`worker_group_reason`、`group_rule_version` 三者不缺失且可通过规则重算。
- `tests/test_dt_fields.py`
  - 验证 `d_t=NA` 时 `d_t_status` 与 `d_t_failure_reason` 必填；成功样本 `d_t_ref_hash` 与 `d_t_model_ver` 必填。
- `tests/test_manifest_links.py`
  - 验证 `merged_all.csv`、`perturbation_plan_frozen.json`、reference pool manifest 的版本/哈希在 release 说明中能互相对上。

## 7. 提交流程（Dev A 执行版）

1. 先生成 `merged_all.csv` 与 `validation_report.json`。
2. 再核对上游 frozen artifacts：
   - `perturbation_plan_frozen.json`
   - reference pool manifest
   - 分组规则版本
3. 运行最小测试集合，确保 P0 项全部通过。
4. 在 PR / 交付说明中写明：
   - 当前 `merged_all.csv` 的 schema version
   - `worker_group` 规则版本
   - `d_t` 规则版本与 ref hash
   - Type 4 过程证据来源（userscript / guard / 系统侧 NA）

## 8. 最小 manifest 样例（发布层要求）

```json
{
  "schema_version": "merged-all-v1",
  "generated_at": "2026-03-06T00:00:00Z",
  "code_git_hash": "<commit>",
  "group_rule_version": "group-rule-v1",
  "dt_rule_version": "c2-v2026-detailed",
  "perturbation_manifest_hash": "sha256:...",
  "reference_pool_hash": "sha256:...",
  "notes": "主表字段与论文 1-4 章及附录 A1 对齐"
}
```
