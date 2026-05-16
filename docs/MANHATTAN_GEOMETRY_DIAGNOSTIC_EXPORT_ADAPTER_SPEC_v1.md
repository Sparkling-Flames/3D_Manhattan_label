# Manhattan Geometry Diagnostic Export Adapter Spec v1

本文档定义 Paper A / A-line `M_geo` 工具在真实 Label Studio export 之前的 adapter contract / preflight 边界。它只说明如何把真实 export 的副本或后处理文件转换成 `tools/compute_mgeo_diagnostic.py` 所需的最小 JSONL 输入，不实现 adapter 代码，不修改正式分析链。

## 1. Adapter 定位

Adapter 的唯一职责是只读转换：

- 输入：真实 Label Studio export 的副本，或由真实 export 派生的后处理文件。
- 输出：`M_geo` MVP JSONL 输入，以及后续 `M_geo` sidecar / worker summary。
- 行粒度：one row per `(task_id, worker_id, submission_id)`。

Adapter 不得：

- 修改原始 export；
- 生成正式 `P1 / C1 / C2 / T1 / V1` required artifact；
- 接入 `tools/analyze_quality.py` 或 `tools/official/analyze_quality_formal.py`；
- 接入 routing、formal `g_t`、worker tier、admission、`w_max`、`tau_d`、Score、`k0/kmax` 或 stop rules；
- 写回 Label Studio export 或 worker-facing UI。

## 2. 输入真源

`export_label/` 是运行时标注真源。`M_geo` adapter 只允许消费 export 的副本或人工明确产生的 audit-only 后处理文件。

不得把 `analysis_results/` 当作输入真源。`analysis_results/` 只可作为 `M_geo` audit-side outputs 的落盘位置。

## 3. 输出位置建议

建议输出路径：

- `analysis_results/manhattan_geometry_diagnostic/mgeo_input_<round>.jsonl`
- `analysis_results/manhattan_geometry_diagnostic/mgeo_sidecar_<round>.jsonl`
- `analysis_results/manhattan_geometry_diagnostic/mgeo_summary_<round>.json`

这些文件都是 audit-side outputs，不是正式 round artifacts，不进入 `P1 / C1 / C2 / T1 / V1` artifact contract。

## 4. 目标 JSONL 字段合同

目标 JSONL row grain 为 one row per `(task_id, worker_id, submission_id)`。

必需字段：

- `task_id`
- `worker_id`
- `submission_id`
- `scope`
- `manhattan_assumable`
- `layout_corners` 或 `corners`

可选字段：

- `room_height`
- `source_geometry_version`

`scope` 只允许以下真实 export alias：

- `normal`
- `oos_geometry`
- `oos_open_boundary`
- `oos_split_level`
- `oos_insufficient`

Adapter 不做中文完整 choice value 兼容，不做 fuzzy matching。若真实 export 里只有完整 choice 文本，必须先通过已冻结、可审计的 choice-alias 映射得到上述 alias；无法映射时输出缺失/未知，让 `compute_mgeo_diagnostic.py` 产生 `scope_unknown_or_missing`。

## 5. `manhattan_assumable` 来源

`manhattan_assumable` 不能由 `M_geo` 工具或 adapter 自己猜。

允许来源仅包括：

- 专家 sidecar；
- 已冻结的人工复核字段；
- 明确标记为 audit-only 的 metadata。

如果真实 export 或其已审计后处理文件没有 `manhattan_assumable`，adapter 应保持该字段缺失，由 `compute_mgeo_diagnostic.py` 输出 `missing_manhattan_assumable`。不得自动填 `true`。

## 6. Geometry 字段风险

真实 Label Studio keypoint export 可能不是直接 polygon。实现 adapter 前必须人工确认：

- 点顺序是否可复原；
- floor/ceiling paired support 是否存在；
- 2D keypoints 是否足够构造 BEV polygon；
- 是否需要复用已有 layout normalization 工具；
- 是否存在重复点、闭合点、奇数点、空结果；
- `keypointlabels` 与 `polygonlabels` 的优先级；
- `value.points` 的坐标单位是否仍为百分比坐标，以及转换时需要的图像宽高。

当前仓库中 `tools/analyze_quality.py` 已有 Label Studio result 解析和 `_pair_keypoints_to_layout` / layout normalization 线索，但这不等于 `M_geo` adapter contract 已经确认。除非后续用真实 export 小样本完成 preflight，否则不得新增 adapter 代码或接入正式分析链。

## 7. Smoke Test 计划

后续人工执行的小样本验证建议：

1. 从真实 export 副本中选 5-10 条 annotation。
2. 手工或临时脚本转换为 MVP JSONL。
3. 运行 `tools/compute_mgeo_diagnostic.py`。
4. 检查每类 `scope` alias 是否正确 exclusion。
5. 检查 `normal` 样本是否能得到 sidecar。
6. 检查 `invalid_polygon` 是否不被误报为 OOS。
7. 检查 `missing_manhattan_assumable` 不会被自动填补。
8. 检查 summary counts 是否与 sidecar reason 对齐。

该 smoke test 只验证 adapter contract，不产生正式 round artifact。

## 8. 明确禁止

- 不把 adapter 输出接入正式 routing。
- 不把 `M_geo` 写回 export。
- 不把 `M_geo` 作为 correctness。
- 不把 `M_geo` 作为 formal `g_t`。
- 不用 Main-Test / Main-Validation outcome 调阈值或 component weight。
- 不修改 worker-facing UI。
- 不修改 import JSON、assignment manifest、routing artifact 或任何 `P1 / C1 / C2 / T1 / V1` schema。

