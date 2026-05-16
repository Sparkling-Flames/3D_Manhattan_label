# Manhattan Geometry Tool Roadmap v2

本文档是当前 Manhattan 工具工作的入口文档。它统一引用既有 `M_geo` audit-only 文档，并明确把当前 Paper A / A-line 实验内的 post-hoc diagnostic 与实验外 realtime Manhattan / 3D preview assistant 原型分开。

## 1. 当前结论

- Paper A / A-line 当前实验中的 Manhattan 检查只能是 post-hoc audit-only diagnostic。
- 当前实验中的 Manual / Semi-Auto worker-facing 标注流程不得显示 realtime Manhattan assistant、3D 方正性提示、snap suggestion 或 geometry guidance。
- Realtime Manhattan assistant 可以继续作为实验外工具迭代，但只能是 expert-side / lab-side prototype。
- Realtime assistant 不是当前论文主实验干预，不进入当前 `RQ1 / RQ2 / RQ3`，也不是新的 `Semi-Auto + Geometry Guidance` condition。

原因：若把 realtime Manhattan assistant 放入当前 A-line worker-facing 标注流程，会污染 `active_time`、自然错误分布和 worker 真实能力测量。

## 2. Track A: Post-hoc worker-profile diagnostic

Track A 保持在 Paper A 内，但只作为 audit-side post-hoc diagnostic。

定义：

- `M_geo(t,u)`：提交级 Manhattan residual。
- `J_u^geo`：worker-level summary。
- `M_u^geo`：worker profile card 中的 auxiliary Manhattan-discipline signature。

允许用途：

- `M_u^geo` 可以作为 worker profile 的辅助审计签名。
- `M_geo(t,u)` / `J_u^geo` / `M_u^geo` 可以与 Type-3 geometric failure、`IoU_LOO`、expert correction burden 做描述性或关联分析。
- 它们可以帮助解释 3D instability、renderability failure、refinement discipline 和 geometry process evidence。

硬边界：

- `M_u^geo` 不能进入主风险层级判定。
- `M_u^geo` 不能替代 `r_u`、`LCB(r_u)`、`r_u^(s)`、`T_u`、`C_u` 或 `G_u`。
- `M_geo(t,u)`、`J_u^geo`、`M_u^geo` 不能作为低质量 worker 的直接证据。
- 它们不能改变 admission、routing、`w_max`、`tau_d`、Score、`k0/kmax`、stop rules 或 Validation routing contract。
- 它们不能成为 correctness metric、formal `g_t`、formal OOS classifier 或 worker-facing hint。
- Track A 只在 `scope=normal` 且 `manhattan_assumable=true` 的提交上计算；excluded cases 必须保留 explicit reason，不能静默计为 geometry failure。

当前实现状态：

- `tools/compute_mgeo_diagnostic.py` 是 offline audit-only MVP。
- 输入为最小 JSONL schema。
- 输出为 optional sidecar/report，不是正式 `P1 / C1 / C2 / T1 / V1` required artifact。

## 3. Track C-lite: Realtime Manhattan assistant outside experiment

Track C-lite 是 Paper A 当前实验外的工具迭代方向。

定位：

- expert-side / lab-side prototype。
- 不进入当前 `RQ1 / RQ2 / RQ3`。
- 不是 `Semi-Auto + Geometry Guidance`。
- 不接入正式 Label Studio worker-facing 项目。
- 不用于测量当前实验中的 worker natural ability。
- 若未来要进入实验，必须单独设计 extension cohort，并在不改变 protocol core 的前提下单独报告。

功能目标：

- 实时检测当前 layout 是否符合 Manhattan-style 3D preview 约束。
- 解释 3D preview 为什么“不方正”。
- 给出 per-corner adjustment suggestion。
- 只生成 preview-only snapped candidate，不自动覆盖正式标注。
- 对 compatibility failure 保持保守：如果不能证明与当前 3D preview 坐标语义一致，就不输出 adjustment suggestion。

## 4. Deterministic-first, model-later

第一版 realtime assistant 不训练模型。优先实现确定性检查：

- dominant axis estimation；
- edge-to-axis angular residual；
- snap-to-axis suggestion；
- vertical pair alignment；
- polygon validity / self-intersection；
- duplicate / near-duplicate corner detection；
- closure check；
- current 3D preview compatibility check。

模型只能作为未来方向：

- lightweight suggestion ranker 可以作为 future work；
- 模型输出不得解释为 correctness；
- 模型不得自动改写 annotation；
- 模型不得在当前实验 worker-facing UI 中提供实时提示。

## 5. Relationship to existing docs

- `MANHATTAN_GEOMETRY_DIAGNOSTIC_PLAN_v1.md` 是原始 audit-only plan。
- `MANHATTAN_GEOMETRY_DIAGNOSTIC_IMPLEMENTATION_SPEC_v1.md` 是 offline CLI MVP contract。
- `MANHATTAN_GEOMETRY_DIAGNOSTIC_EXPORT_ADAPTER_SPEC_v1.md` 是 export adapter preflight contract。
- `VIS_3D_GEOMETRY_COMPATIBILITY_SPEC_v1.md` 是 Track C-lite 的 3D preview compatibility contract。
- 本 v2 roadmap 是当前 Manhattan 工具入口文档；旧文档保留为 supporting specs，不删除、不重写为 protocol core。

## 6. Explicit non-goals

- 不修改 Label Studio UI。
- 不修改 `tools/official/ls_userscript_annotator.js`。
- 不修改 `tools/label_studio_view_config.xml`。
- 不修改 `import_json/` 或 `export_label/`。
- 不接入 `tools/analyze_quality.py`。
- 不修改 routing artifact。
- 不修改 `P1 / C1 / C2 / T1 / V1` schema。
- 不修改正式 protocol / SOP。

