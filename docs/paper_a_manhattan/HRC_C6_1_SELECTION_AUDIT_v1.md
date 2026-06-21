# HRC C6.1 Selection Audit v1

## 结论

C6.1 状态冻结为 `audit_blocked`，不得解释为 stable selection。C6.1 的 `best_manhattan_feasible` 从 0017 漂移到 0019，暴露的是 scoring layer 尚未分层，不代表 C6.1 代码整体无效，也不代表 0019 更好。

## 0017 / 0019 反例

| 指标 | 0017 | 0019 | 解释 |
|---|---:|---:|---|
| direction-family max residual | 36.453° | 35.552° | 0019 略好，但不能单独主导 |
| unresolved edge count | 2 | 3 | 0019 更差 |
| turn residual median | 11.964° | 17.342° | 0019 更差 |
| local-window residual | 14.739° | 24.600° | 0019 更差 |
| parallel-family median residual | 9.267° | 9.370° | 0019 略差 |
| pair 6 projected height | 2.952 | 2.883 | 0019 离 dominant height 更远 |
| max height residual | 0.779 | 0.781 | 0019 略差 |

人工视觉 sanity check 认为 0019 的 local protruding pillar / short-wall shape 更差。现有 short-wall proxy 却给出更小 deficit 和更大 keep-distinct margin；这说明 proxy 未覆盖该视觉问题，不能把人工结论倒填为已有结构指标。

## 推荐边界

- C6.1 bucket selection 保留用于复现，candidate/evaluator diagnostics 不修改。
- runner-level `selection_status=audit_blocked`。
- `recommended_review_candidate_available=false`；0019 不是 accepted candidate，也不是 downstream recommendation。
- 不回退旧选择，不增加局部阈值，等待 Scoring Layer Contract、C4-lite 与 C6.2。
