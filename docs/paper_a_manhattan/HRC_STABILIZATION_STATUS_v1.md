# HRC Stabilization Status v1

> 冻结日期：2026-06-21。范围仅限 Manhattan Constrained Hypothesis Ranking Core（HRC）状态盘点；不新增算法、portfolio bucket、搜索器、UI/plugin 或 annotation writeback。

## 1. 当前主模块

- 主 evaluator：`tools/paper_a_manhattan/manhattan_constrained_hypothesis_evaluator.py`。
- portfolio/ranking：`tools/paper_a_manhattan/manhattan_hypothesis_portfolio.py`；独立 runner 为 `tools/paper_a_manhattan/run_manhattan_hypothesis_ranking_core.py`。
- candidate source：runner 仍调用 `tools/paper_a_manhattan/manhattan_m1528_semantic_action_library.py` 的 `run_action_library()`；即 legacy M15.28/action library 接入 HRC，不是新的 constrained candidate generator。
- legacy score：core 输出已把 `legacy_score_breakdown` / `local_score_total` 移出 `constrained_evaluations`，集中到 `legacy_diagnostics` 并标记 `diagnostic_only`。但 `build_hypothesis_ranking_key()` 仍把 `local_score_total` 作为末位 tie-breaker，因此“只作诊断”尚未在排序语义上完全成立；禁止继续调其权重。

## 2. C0–C10 状态

| 阶段 | 冻结状态 | 仓库实际状态 |
|---|---|---|
| C0 | 部分完成，待收口 | 输出合同已降级 legacy score；排序 key 仍使用 `local_score_total` 末位兜底，尚非严格 diagnostic only。 |
| C1 | 部分完成 | `manhattan_case_contract.py` 已有 case contract 与 projection-rule-based inferred contract，也保留无 metrics 时的 legacy fallback；不是完全脱离 legacy 默认值的通用 case analyzer。 |
| C2 | v1 diagnostic implemented | evaluator 已输出 hard feasibility、wall/turn/local residual、height consistency、layout plausibility、evidence interface、movement/edit cost 与 decision class；`direction_family_fit` / `parallel_family_residual` v1 已实现并由真实 projection artifacts 与 core runner 回归锁定，但仍只是可审计 diagnostic，不是 C4 Column Evidence Layer。 |
| C3 | 未实现新模块 | 当前只是 M15.28 action library 的 legacy candidate source 接入 core；不是新的 constrained candidate generator。 |
| C4 | 未实现 | 未发现独立 Column Evidence Layer。evaluator 只有 evidence 字段接口及 `top_bottom_x_residual` 派生列一致性指标，不等于 HoHoNet/HorizonNet column evidence 实现。 |
| C5 | C5-lite plane proxy v0 implemented | evaluator 已物化独立 `plane_proxy_metrics`：复用 direction-family、同族平行 residual、dominant height cluster 与 floorprint residual 形成 geometry proxy。它不是 depth model、不是 GeoLayout reproduction、不是 C4 evidence layer，也不进入 ranking。 |
| C6 | 部分存在，冻结 | `manhattan_hypothesis_portfolio.py` 已提供固定 bucket 外壳与 lexicographic 选择；因 C2/C5 仍是 diagnostic 且 C4 未实现，不扩展 bucket，不把当前外壳声明为稳定 ranker。 |
| C7 | blocked | legacy `manhattan_m1527_semantic_direct_search.py` 存在 Hooke–Jeeves 搜索，但新 geometry-normalized MADS/Hooke–Jeeves 在 evaluator 稳定前不得启动。 |
| C8 | 仅记录系统 | feedback ledger schema 与 `materialize_manhattan_feedback_ledger_entry.py` 可保留；不得进入训练、参数更新或自动应用系统。 |
| C9 | blocked | 未发现 Adaptive Parameter Update 实现；不得启动。 |
| C10 | blocked | 未发现 Lightweight Candidate Ranker 实现；不得启动。 |

## 3. 唯一允许的下一步

C5-lite 已物化并回归锁定 `plane_proxy_metrics` v0；它只增加 geometry diagnostic，不改变 ranking、decision 或 safety boundary。本状态同步不授权后续算法扩展：

- 不先做 C3/C4/C6/C7/C9/C10；
- 不继续调 `local_score_total` 权重；
- 不新增 portfolio bucket；
- 不自动写回 annotation。

## 4. 文件与依据

- `tools/paper_a_manhattan/manhattan_constrained_hypothesis_evaluator.py`：C2 字段、hard gate、ranking key 与 legacy score tie-breaker。
- `tools/paper_a_manhattan/manhattan_case_contract.py`：C1 inferred contract、legacy fallback 与安全边界。
- `tools/paper_a_manhattan/manhattan_hypothesis_portfolio.py`：C6 当前 portfolio 外壳。
- `tools/paper_a_manhattan/run_manhattan_hypothesis_ranking_core.py`：主 runner、M15.28 source 接线、core/legacy 输出隔离。
- `tools/paper_a_manhattan/manhattan_m1528_semantic_action_library.py`：实际 candidate source 与 constrained evaluator 接入。
- `tools/paper_a_manhattan/manhattan_m1527_semantic_direct_search.py`：legacy Hooke–Jeeves 依据；不是已批准的 C7。
- `docs/paper_a_manhattan/后续方针.md`：C0–C10 目标定义。
- `docs/paper_a_manhattan/M15_LEGACY_ARTIFACT_DEPENDENCY_INVENTORY_v1.md`：legacy source/compatibility chain 仍被 core 使用的依据。
- `docs/paper_a_manhattan/MANHATTAN_HYPOTHESIS_FEEDBACK_LEDGER_SCHEMA_v1.md` 与 `tools/paper_a_manhattan/materialize_manhattan_feedback_ledger_entry.py`：C8 只记录、不训练、不写回边界。
- 独立 C3 constrained generator、C4 Column Evidence Layer、C9 Adaptive Parameter Update、C10 Lightweight Candidate Ranker 文件：missing / not found。

本冻结不改变 Paper A 正式实验、`P1/C1/C2/T1/V1`、routing、worker-facing、协议或 Label Studio 数据。
