# HRC Stabilization Status v1

> 冻结日期：2026-06-21。范围仅限 Manhattan Constrained Hypothesis Ranking Core（HRC）状态盘点；不新增算法、portfolio bucket、搜索器、UI/plugin 或 annotation writeback。

## 1. 当前主模块

- 主 evaluator：`tools/paper_a_manhattan/manhattan_constrained_hypothesis_evaluator.py`。
- portfolio/ranking：`tools/paper_a_manhattan/manhattan_hypothesis_portfolio.py`；独立 runner 为 `tools/paper_a_manhattan/run_manhattan_hypothesis_ranking_core.py`。
- candidate source：runner 通过 C3.1 interface 与 legacy wrapper 调用 M15.28 action library；`legacy_m1528` 仍是唯一 active source，不是新的 constrained candidate generator。
- legacy score：core 输出已把 `legacy_score_breakdown` / `local_score_total` 移出 `constrained_evaluations`，集中到 `legacy_diagnostics` 并标记 `diagnostic_only`。但 `build_hypothesis_ranking_key()` 仍把 `local_score_total` 作为末位 tie-breaker，因此“只作诊断”尚未在排序语义上完全成立；禁止继续调其权重。

## 2. C0–C10 状态

| 阶段 | 冻结状态 | 仓库实际状态 |
|---|---|---|
| C0 | 部分完成，待收口 | 输出合同已降级 legacy score；排序 key 仍使用 `local_score_total` 末位兜底，尚非严格 diagnostic only。 |
| C1 | 部分完成 | `manhattan_case_contract.py` 已有 case contract 与 projection-rule-based inferred contract，也保留无 metrics 时的 legacy fallback；不是完全脱离 legacy 默认值的通用 case analyzer。 |
| C2 | v1 diagnostic implemented | evaluator 已输出 hard feasibility、wall/turn/local residual、height consistency、layout plausibility、evidence interface、movement/edit cost 与 decision class；`direction_family_fit` / `parallel_family_residual` v1 已实现并由真实 projection artifacts 与 core runner 回归锁定，但仍只是可审计 diagnostic，不是 C4 Column Evidence Layer。 |
| C3 | C3.1 interface/wrapper implemented；C3.2 contract drafted；C3.3 constrained_v0 shadow skeleton implemented | skeleton 只验证空 source contract、metadata 与 provenance，不生成 coordinate changes，也不接入 runner。real candidate generation 仍 missing，`legacy_m1528` 仍是唯一 active source。 |
| C4 | C4-lite implemented | runner 对已有 HoHoNet proposal 执行 source inventory/parser probe，并物化 corner column、floor/ceiling boundary 与 seam delta；缺失、歧义或合同异常时 fail-closed 为 unavailable，不训练模型、不写回。 |
| C5 | C5-lite plane proxy v0 implemented | evaluator 已物化独立 `plane_proxy_metrics`：复用 direction-family、同族平行 residual、dominant height cluster 与 floorprint residual 形成 geometry proxy。它不是 depth model、不是 GeoLayout reproduction、不是 C4 evidence layer；C6.2 仅把其中 geometry diagnostics 用于分层排序。 |
| C6 | C6.2 layered ranking implemented；post-change audit narrowly passed for selection drift | bucket 集合不变；L0 suppress、L1 多指标 Pareto、L2 HoHoNet evidence、L3/L4 diagnostics、L5 fallback 已分层。默认 case 选择 0017 的漂移通过窄范围人工核验，但不声明 stable ranker。 |
| C7 | blocked | legacy `manhattan_m1527_semantic_direct_search.py` 存在 Hooke–Jeeves 搜索，但新 geometry-normalized MADS/Hooke–Jeeves 在 evaluator 稳定前不得启动。 |
| C8 | 仅记录系统 | feedback ledger schema 与 `materialize_manhattan_feedback_ledger_entry.py` 可保留；不得进入训练、参数更新或自动应用系统。 |
| C9 | blocked | 未发现 Adaptive Parameter Update 实现；不得启动。 |
| C10 | blocked | 未发现 Lightweight Candidate Ranker 实现；不得启动。 |

## 3. 唯一允许的下一步

C6.1 audit、Scoring Layer Contract、C4-lite、C6.2、C3.1、C3.2 与 C3.3 shadow skeleton 已完成；`manual_post_change_audit = narrow_pass_for_selection_drift_only`。当前只允许核验 skeleton contract/metadata；不得生成真实候选，不得接入 active runner selection，不得替换 `legacy_m1528`；C7/C9/C10 继续 blocked。

`candidate_set.recommended_review_candidate` 只表示 diagnostic/bucket selection，不具有下游授权语义。下游必须同时读取 `overall_verdict.recommended_review_candidate_available`、bucket `accepted` 与 `downstream_recommendation`；当前仍保持 `accepted=false`、`downstream_recommendation=false`，0017 不是 accepted final fix。

- 不扩展 C4，不做 full image-edge evidence；C3.3 仅为无真实候选的 shadow skeleton，C7/C9/C10 仍 blocked；
- 不继续调 `local_score_total` 权重；
- 不新增 portfolio bucket；
- 不自动写回 annotation。

## 4. 文件与依据

- `tools/paper_a_manhattan/manhattan_constrained_hypothesis_evaluator.py`：C2 字段、hard gate、ranking key 与 legacy score tie-breaker。
- `tools/paper_a_manhattan/manhattan_case_contract.py`：C1 inferred contract、legacy fallback 与安全边界。
- `tools/paper_a_manhattan/manhattan_hypothesis_portfolio.py`：C6 当前 portfolio 外壳。
- `tools/paper_a_manhattan/manhattan_candidate_source_interface.py`：C3.1 candidate source 最小字段合同与校验。
- `tools/paper_a_manhattan/manhattan_legacy_m1528_candidate_source.py`：C3.1 legacy wrapper；仅调用既有 M15.28 action library。
- `tools/paper_a_manhattan/manhattan_constrained_v0_candidate_source.py`：C3.3 contract-only shadow skeleton；固定输出空 candidate set，无 active runner role。
- `tools/paper_a_manhattan/run_manhattan_hypothesis_ranking_core.py`：主 runner、M15.28 source 接线、core/legacy 输出隔离。
- `tools/paper_a_manhattan/manhattan_m1528_semantic_action_library.py`：实际 candidate source 与 constrained evaluator 接入。
- `tools/paper_a_manhattan/manhattan_m1527_semantic_direct_search.py`：legacy Hooke–Jeeves 依据；不是已批准的 C7。
- `docs/paper_a_manhattan/后续方针.md`：C0–C10 目标定义。
- `docs/paper_a_manhattan/M15_LEGACY_ARTIFACT_DEPENDENCY_INVENTORY_v1.md`：legacy source/compatibility chain 仍被 core 使用的依据。
- `docs/paper_a_manhattan/MANHATTAN_HYPOTHESIS_FEEDBACK_LEDGER_SCHEMA_v1.md` 与 `tools/paper_a_manhattan/materialize_manhattan_feedback_ledger_entry.py`：C8 只记录、不训练、不写回边界。
- C3.1 interface/wrapper、C3.2 contract 与 C3.3 shadow skeleton 已存在；`constrained_v0` real candidate generation、C9 Adaptive Parameter Update、C10 Lightweight Candidate Ranker：missing / not found。C4-lite 已实现，不在 missing 清单内。

本冻结不改变 Paper A 正式实验、`P1/C1/C2/T1/V1`、routing、worker-facing、协议或 Label Studio 数据。
