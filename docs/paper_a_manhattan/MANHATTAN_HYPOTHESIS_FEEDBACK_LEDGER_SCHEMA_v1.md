# Manhattan Hypothesis Feedback Ledger Schema v1

## 定位与边界

本 ledger 记录专家对 Manhattan constrained hypothesis portfolio 的选择与后续人工修订，供未来参数自适应或轻量 ranker 使用。当前版本只定义 schema，不训练模型、不自动应用候选、不回写标注，也不进入 worker-facing、routing、论文主协议或 `P1/C1/C2/T1/V1` 工件。

## 顶层字段

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `state_before` | object | 候选生成前的布局状态、pair 顺序及投影配置快照。 |
| `case_contract` | object | 本 case 使用的结构化 contract，包括保护、可移动和短墙约束。 |
| `candidate_set` | array | 展示给专家的候选集合及稳定 candidate ID。 |
| `candidate_metrics` | object | candidate ID 到 constrained evaluation 的映射。 |
| `shown_rank` | array | 实际展示顺序；不得用事后顺序覆盖。 |
| `expert_selected_candidate` | string/null | 专家选择的 candidate ID；未选择时为 `null`。 |
| `expert_rejected_candidates` | array | 明确拒绝的 candidate ID。 |
| `manual_edit_after_candidate` | object/null | 选择候选后由专家进行的人工编辑 delta；没有则为 `null`。 |
| `final_layout` | object/null | 专家确认后的最终布局；未确认时为 `null`。 |
| `delta_candidate_to_final` | object/null | 所选候选到最终布局的字段级差异。 |
| `accepted_directly` | boolean | 候选是否未经坐标修改直接接受。 |
| `accepted_after_minor_edit` | boolean | 候选是否经小幅人工修改后接受。 |
| `rejected_reason_optional` | string/array/null | 可选拒绝原因，不强迫专家填写自由文本。 |
| `case_tags` | array | 可审计的 case 标签。 |
| `action_family` | string/null | 所选候选的 legacy action family 或新 action family。 |
| `parameter_snapshot` | object | 候选生成、projection 和阈值参数快照。 |
| `ranker_version` | string | 排序器版本。 |
| `evaluator_version` | string | evaluator 版本。 |

## 最小一致性规则

- `accepted_directly=true` 时，`expert_selected_candidate` 必须存在，且 `manual_edit_after_candidate` 与 `delta_candidate_to_final` 必须为空或零变更。
- `accepted_after_minor_edit=true` 时，必须存在 `expert_selected_candidate`、`manual_edit_after_candidate` 和 `delta_candidate_to_final`。
- 两个 accepted 字段不能同时为 `true`。
- `shown_rank`、`expert_selected_candidate` 和 `expert_rejected_candidates` 中的 ID 必须来自 `candidate_set`。
- `candidate_metrics` 必须保留 hard-gate 失败候选及失败原因，不能只记录获选候选。
- `state_before`、`final_layout` 和 delta 只用于专家侧离线审计；本 schema 不授权 annotation patch 或 writeback。

## 后续用途

人工判断不应长期只是流程阻塞点。积累后的 ledger 可用于评估固定阈值、调整 deterministic ranking 参数，或在单独审查后训练轻量 ranker；任何训练或上线均不属于本 v1 schema 的实现范围。

## Compatibility surface

M15.28 compatibility fields are deprecated for the Manhattan Constrained Hypothesis Ranking Core. 新代码只能消费 `portfolio_ranking` 与 `constrained_evaluations`；`portfolio_candidates`、`m15_28_gate`、`legacy_m15_28_gate` 和 `local_score_total` 不属于新 core 主输出合同，只能以 compact diagnostic summary 保存在 `legacy_diagnostics`。

## Materialization

`tools/paper_a_manhattan/materialize_manhattan_feedback_ledger_entry.py` 接收 `manhattan_constrained_hypothesis_ranking_core_v1` JSON 与 expert review JSON，验证 candidate ID 和 accepted 状态后输出单条 JSONL。该步骤只物化审计记录，不训练模型、不更新 ranker 参数、不应用候选，也不写回 annotation。

### Diagnostic-useful but not final

Ledger v1 also supports an expert selecting a candidate as a useful diagnostic direction without accepting it as a final correction:

- `expert_selected_candidate_role` records the diagnostic role.
- `candidate_verdicts` preserves per-candidate expert verdicts such as `reject_as_final_but_directionally_useful`.
- `final_layout_available=false` requires `final_layout=null`.
- Both `accepted_directly` and `accepted_after_minor_edit` remain `false`; this state must not be reinterpreted as acceptance.
