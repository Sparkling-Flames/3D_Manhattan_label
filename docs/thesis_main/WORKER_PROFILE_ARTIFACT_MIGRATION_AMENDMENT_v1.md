# Worker Profile Artifact Migration Amendment v1

日期：2026-07-12。此 amendment 不修改 `WORKER_PROFILE_ARTIFACT_FIELD_CONTRACT_v1.md` 的既有语义。

## 描述性方向检查迁移

新运行输出：

```text
p1_to_c1_descriptive_directional_check.csv
p1_to_c1_descriptive_directional_check_report.md
p1_to_c1_predictive_validity.deprecated.json
```

旧路径 `p1_to_c1_predictive_validity.csv` 与 `p1_to_c1_predictive_validity_report.md` 保留为历史 artifact 名称，不再由新运行生成。`*.deprecated.json` 记录替代路径和语义迁移。

新字段 `descriptive_directional_alignment` 仅表示 P1 与 C1 指标的描述性方向一致性；它不是正式 predictive validity。正式状态固定输出为 `formal_predictive_validity_status=not_run_blocked`，直到独立的正式分析获准运行。

## 新增 additive 字段

`parent_same_owner`、C1 expert-only undercoverage 字段、semi issue/correction 双信号、geometry component/failure-family 双链字段，以及 `p1_worker_dimension_readiness_C1.csv` 均为 additive 输出。连续且已标准化的正向 geometry component 可以进入 `r_geometry_u`；未冻结 failure threshold 的 geometry 行不进入二值 failure-family 分母。

`geometry_failure_observed`、`undercoverage_failure_observed` 与 `semi_correction_failure_observed` 采用严格三态：仅 `true` 是 failure，`false` 是 success，空值或非法值为 `not_evaluable`，不进入对应分母。readiness 同时输出 `pending_dimension_cell_count` 与按 annotation 去重的 `unique_pending_annotation_count`。
