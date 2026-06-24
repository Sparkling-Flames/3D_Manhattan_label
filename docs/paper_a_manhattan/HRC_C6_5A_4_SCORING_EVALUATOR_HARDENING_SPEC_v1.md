# HRC C6.5a.4 Scoring / Evaluator Hardening Spec v1

## 1. Purpose and boundary

本规范把 C6.5a.3 scoring compliance audit 的五项 violation 转成后续可执行的改造合同。

本阶段是 spec-only：

- 不修改 evaluator；
- 不修改 `build_hypothesis_ranking_key()`；
- 不修改 portfolio bucket 或 bucket 数量；
- 不生成 proposal、candidate 或 geometry variant；
- 不接入 active runner，不替换 `legacy_m1528`；
- `accepted=false`、`downstream_recommendation=false`、`annotation_writeback=false`；
- C3/C7/C9/C10 继续 blocked。

本规范获审查通过也不等于 C6.5b 获授权。任何实现必须另行测试和 selection audit。

## 2. Required global layer order

未来 global ranking key 必须严格遵循以下词典序：

1. L0 hard feasibility；
2. L1 multi-metric Manhattan structure；
3. L2 evidence availability / conflict / candidate delta；
4. L3 plane and height consistency；
5. L4 layout plausibility and required manual evidence；
6. L5 movement tie-break。

不得使用加权总分折叠层级。下层改善不得覆盖上层失败或回归。

Legacy score 不属于 active ranking key；只保留 diagnostic output，不作为 active fallback。

## 3. L0 hard feasibility contract

L0 必须保持 ranking key 第一项，并在 portfolio 之前执行。

`hard_gate_passed=false` 必须：

- 进入 `suppressed_candidates`；
- 不进入任何 selectable bucket；
- 不因 direction、height、C4、C5、movement 或 legacy score 改善而恢复；
- 保持 `accepted=false`、`downstream_recommendation=false`。

L0 至少覆盖 topology、projection validity、self-intersection、pair fold、order
mutation、protected pair、keep-distinct collapse、unauthorized mutation 和 seam/wrap
hard failure。

## 4. L1 multi-metric Manhattan structure contract

L1 禁止由 direction max/median 单项主导。未来 L1 key 应先表达结构回归，再比较
direction-family 精度。

建议的 L1 词典序组为：

1. `unresolved_edge_count`；
2. turn residual availability；
3. `turn_residual_max`；
4. `turn_residual_median`；
5. local-window / local-orthogonality availability；
6. `local_window_residual`；
7. `floor_ceiling_column_consistency` availability 与 residual；
8. direction-family availability；
9. parallel-family availability；
10. direction-family residual summary；
11. parallel-family residual summary；
12. wall residual summary。

约束：

- direction/parallel available 不能覆盖 unresolved edge 增加；
- direction residual 小幅改善不能覆盖 turn 或 local-window 回归；
- missing turn/local metric 不能静默视为零；
- 缺失结构字段必须显式排序为 unavailable，不得误优于 available-but-bad；
- 不在本规范中发明 case-specific 阈值或权重。

该合同关闭：

- `L1_DIRECTION_PRECEDES_MULTI_METRIC_STRUCTURE`。

## 5. L2 primary geometry evidence contract

L2 不得继续压缩为单一 `evidence_regression`。未来必须拆成三个显式部分：

### 5.1 `evidence_available_gate`

- C4 evidence 必须来自已验证 proposal、明确 coordinate contract 和 candidate-specific
  geometry；
- evidence unavailable 时 bucket 可保留 diagnostic selection，但不得 accepted；
- baseline-to-baseline evidence 只证明 parser/input 可用，不证明 candidate evidence available。

### 5.2 `evidence_conflict_gate`

- 任一明确 `visual_conflict_flags` 或 contract conflict 必须阻断 accepted recommendation；
- conflict candidate 只能为 `needs_manual_review` / `diagnostic_only`；
- conflict 不得被 L3、L4 或 L5 改善覆盖。

### 5.3 `evidence_delta_key`

只有 candidate-specific projection variant 存在时，才允许比较：

- wall-wall/corner column delta；
- floor boundary RMSE delta；
- ceiling boundary RMSE delta；
- seam/wrap continuity delta。

2369/2389 当前 C4 是 baseline-to-baseline、delta 为零且 candidate projection variant
count 为零，因此：

- `candidate_preference_authorized=false`；
- 不得进入 evidence delta ranking；
- 不得据此声明 candidate supported。

该合同关闭：

- `L2_AFTER_L3_IN_GLOBAL_KEY`；
- `L2_BASELINE_ONLY_CANNOT_PREFER_CANDIDATE`。

## 6. L3 plane / height contract

L3 仅在 L0、L1 和 L2 未失败/回归后比较。

L3 可包含：

- C5 `plane_proxy_metrics`；
- dominant height cluster；
- height MAD；
- max height residual；
- height outlier summary。

边界：

- C5 是 geometry proxy，不是 C4 image evidence；
- C5 不是 depth-plane truth，也不是 GeoLayout reproduction；
- C5 plane parallel/orthogonal proxy 必须从 `best_manhattan_feasible` 的 L1 key 移出；
- C5 可进入独立 L3 comparison group，或在 L0–L2 相等后作为 L3 tie-break；
- height 不得排在 L2 evidence gate/conflict 之前。

该合同关闭：

- `C5_MIXED_INTO_MANHATTAN_BUCKET_KEY`；
- global key 中 L3 早于 L2 的层序问题。

## 7. L4 layout plausibility and manual evidence contract

L4 独立表达：

- short-wall preserved / collapsed / newly created；
- keep-distinct margin 与 dense-corner preservation；
- protruding-pillar / local plausibility；
- manual evidence sidecar status。

以下 proposal family 必须先通过 manual sidecar gate：

- multi-pair x alignment；
- short-wall preserving floorprint balance；
- dense-corner adjustment。

Manual sidecar 必须：

- 符合 `hrc_manual_evidence_sidecar_v1`；
- 明确 case、evidence type、reviewer、verdict 与 supporting artifacts；
- 将 supporting artifacts 仅作为审查依据，不作为 manual verdict 本体；
- verdict unavailable/conflict 时阻断 accepted 和执行授权。

当前边界：

- 2369 的 keep-distinct pair 是 projection-derived，不等于 manual sidecar；
- 2389 的 explicit column identity 与 keep-distinct contract 均未完成；
- 缺失 manual gate 时 proposal family 必须 blocked。

该合同关闭：

- `L4_MANUAL_EVIDENCE_INCOMPLETE`。

## 8. L5 edit cost and legacy diagnostics

L5 只能在 L0–L4 完全相等或均无回归时使用。

允许的 active tie-break：

- movement L1；
- changed pair / endpoint count；
- manual adjustment cost proxy。

禁止：

- movement 覆盖 L1–L4；
- `local_score_total` 或 `legacy_score_breakdown` 重新进入 active ranking key；
- 调整 legacy score 权重；
- 把 legacy score 作为最后 active fallback。

Legacy score 继续输出：

- `legacy_score_breakdown`；
- `local_score_total`；
- `legacy_score_role=diagnostic_only`。

## 9. Portfolio contract

Bucket 名称和数量保持不变。

- `best_manhattan_feasible`：只消费 L0 + L1；不得消费 C5 plane proxy；
- `best_hohonet_consistent`：只消费 candidate-specific L2 evidence；
- `best_height_consistent`：消费 L3 height，但不构成 accepted authorization；
- `best_short_wall_preserving`：消费 L4；
- `best_low_movement`：消费 L5；
- `best_balanced`：使用完整 L0→L5 layered key。

Bucket selection 仍不等于 accepted recommendation。

## 10. Required implementation verification

未来实现至少必须证明：

- hard-gate failure 始终 suppress；
- unresolved/turn/local regression 不能被 direction 小幅改善覆盖；
- L2 unavailable/conflict 阻断 accepted；
- baseline-to-baseline C4 不产生 candidate preference；
- L3 height/C5 不位于 L2 前；
- C5 不进入 `best_manhattan_feasible` L1 key；
- manual sidecar 缺失阻断 multi-pair/short-wall/dense-corner proposal；
- movement 仅为最后 active tie-break；
- legacy score 改变不影响任何 active ranking key；
- bucket 名称保持不变；
- active runner recommendation 继续为 false，直到独立 audit 通过。

## 11. Status and next gate

C6 remains audit-blocked。

C6.5b remains unauthorized。

本规范审查通过后，下一步最多允许：

`C6.5a.5 minimal implementation plan and regression matrix`

它仍不是 evaluator/ranking 修改授权。任何实现必须另开范围，并先固定 selection
regression expectations。

C3 shadow expansion、C7 optimizer、C9/C10 learning/ranker 继续 blocked。
