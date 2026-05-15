# Manhattan Geometry Diagnostic Implementation Spec v1

本文档定义 Paper A / A-line 的 Manhattan-aware geometry diagnostic 的最小实现边界。该能力只用于离线 audit-side post-hoc 诊断，不是新干预条件，不是 worker-facing guidance，不进入正式 routing policy，也不改变任何既有协议合同。

## 1. 定位

MVP 工具定位为 offline audit-only CLI，用于在人工提交、专家复核或后处理得到的 layout geometry 之上计算 `M_geo(t,u)`，并汇总 worker-level `J_u` / `M_geo,u`。

该诊断只回答一个审计问题：某个 in-scope、Manhattan-assumable 的提交在几何稳定性、renderability 和 refinement discipline 上是否呈现可解释的 residual signature。它不回答 annotation correctness，也不替代专家判断、LOO reliability 或正式 worker risk tier。

## 2. 输入范围

输入粒度为 one row per `(task_id, worker_id, submission_id)`。MVP 输入建议字段如下：

- `task_id`
- `worker_id`
- `submission_id`
- `scope`
- `manhattan_assumable`
- `layout_corners` 或 `corners`
- optional `room_height`
- optional `source_geometry_version`

MVP 只对同时满足以下条件的提交计算 diagnostic：

- `scope=normal`
- `manhattan_assumable=true`
- geometry 字段存在、可解析，并能形成基础 BEV polygon/layout representation

`scope` 只支持真实 export 中的以下 alias，不做中文完整 choice value 或 fuzzy matching：

- `normal`
- `oos_geometry`
- `oos_open_boundary`
- `oos_split_level`
- `oos_insufficient`

缺失或未知 `scope` 统一输出 `scope_unknown_or_missing`。

以下样本必须输出 exclusion reason，不能静默计为 geometry failure：

- `oos_geometry`；
- `oos_open_boundary`；
- `oos_split_level`；
- `oos_insufficient`；
- `scope_unknown_or_missing`；
- `missing_manhattan_assumable`；
- `not_manhattan_assumable`；
- `missing_geometry`；
- `unparseable_geometry`。

## 3. 输出合同

输出为可选 sidecar/report，不是正式 `P1 / C1 / C2 / T1 / V1` required artifact，不进入 import JSON、assignment manifest、routing artifact 或 Label Studio UI。

Sidecar 建议字段：

- `task_id`
- `worker_id`
- `submission_id`
- `geometry_diag_valid`
- `geometry_diag_exclusion_reason`
- `mgeo_vertical_residual`
- `mgeo_manhattan_angle_residual`
- `mgeo_height_residual`
- `mgeo_renderability_flag`
- `mgeo_snap_residual`
- `mgeo_composite_residual`
- `geometry_diag_version`

Worker summary 建议字段：

- `worker_id`
- `n_total_submissions`
- `n_geometry_diag_valid`
- `n_geometry_diag_excluded`
- `n_geometry_diag_ineligible`
- `n_geometry_diag_invalid_render`
- `n_geometry_diag_missing_or_unparseable`
- `mgeo_median`
- `mgeo_p90`
- `mgeo_invalid_render_count`
- `geometry_diag_version`

其中 `n_geometry_diag_excluded` 是 umbrella count，等于所有非 valid 行数，不代表单一原因类别。更细的分类为：

- `n_geometry_diag_ineligible`：`oos_geometry`、`oos_open_boundary`、`oos_split_level`、`oos_insufficient`、`scope_unknown_or_missing`、`missing_manhattan_assumable`、`not_manhattan_assumable`。
- `n_geometry_diag_invalid_render`：`invalid_polygon` 或 `mgeo_renderability_flag=false`。
- `n_geometry_diag_missing_or_unparseable`：`missing_geometry`、`unparseable_geometry`。

## 4. MVP component behavior

Component-wise 输出优先于 composite score。各 component 的解释边界如下：

- `mgeo_renderability_flag`：仅表示该 geometry 是否能被 MVP diagnostic 规范化到可检查 polygon/layout 表示。
- `mgeo_manhattan_angle_residual`：在简化 BEV 表示中估计 wall direction 对 nearest 90-degree structure 的偏离。
- `mgeo_vertical_residual`：仅在输入包含 paired ceiling/floor support 时计算；缺失时输出 null。
- `mgeo_height_residual`：仅在输入包含可解释 height data 时计算；缺失时输出 null。
- `mgeo_snap_residual`：只有当 nearest valid Manhattan layout snap 可被确定性定义时才计算；MVP 可输出 null。
- `mgeo_composite_residual`：如实现，只能作为 audit/sensitivity score，使用固定、可复现的 component normalization 与 equal-weight aggregation。它不是 primary score，也不是 correctness metric。

## 5. 禁止用途

`M_geo(t,u)`、`J_u` 或任何 `geometry_diag_*` / `mgeo_*` 字段不得用于：

- admission；
- `w_max`；
- `r_u`、`LCB(r_u)`、`r_u^(s)`；
- `tau_d`；
- Score；
- worker tier freeze；
- `k0/kmax`；
- stop rules；
- Validation routing contract；
- formal `g_t`；
- formal OOS classifier；
- Label Studio UI 或实时 hint；
- 新的 Semi-Auto + Geometry Guidance 条件。

不得使用 Main-Test 或 Main-Validation outcomes 调整 diagnostic threshold 或 component weights。

## 6. Reporting-only analyses

允许的 reporting / validation analyses 仅限审计解释：

- `M_geo` distribution；
- worker-level `J_u` distribution；
- high `J_u` 与 Type-3 geometric failures 的关联；
- high `J_u` 与较低 `IoU_LOO` 或 expert correction burden 的关联；
- 同一 task 上 low/high residual submissions 的 qualitative comparison；
- counterexamples：low residual but semantically wrong，high residual but scope/semantic boundary correct。

所有分析必须保持 post-hoc、audit-only，不能回流修改 A-line protocol、routing、worker-facing guidance 或正式 artifact contract。
