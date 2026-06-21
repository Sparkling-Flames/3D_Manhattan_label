# HRC Scoring Layer Contract v1

HRC 使用分层判定，不使用加权总分。`bucket selection != accepted recommendation`。

| 层 | 语义 | 当前指标与规则 |
|---|---|---|
| L0 | Hard feasibility | topology、projection、self-intersection、pair fold、order mutation、protected pairs、keep-distinct collapse；失败直接 suppress。 |
| L1 | Structural Manhattan validity | direction/parallel family、turn residual、unresolved edge、local orthogonality、floor-ceiling column consistency；direction 单项不得主导。 |
| L2 | Primary geometry evidence | HoHoNet wall-wall/corner column、floor/ceiling boundary、seam/wrap evidence；缺失或 conflict 时不得 accepted。 |
| L3 | Plane / height consistency | C5 plane proxy、dominant height cluster、max height residual、height outlier；不是图像 evidence。 |
| L4 | Layout plausibility | short-wall preserved/collapsed/new、keep-distinct、dense-corner、protruding-pillar/manual plausibility。 |
| L5 | Edit cost | movement、changed pair、manual adjustment cost、legacy score；只能作为最后 tie-break。 |

## 排序与授权

- L0 失败候选只进入 `suppressed_candidates`。
- L1 使用多指标非劣关系；单个 direction residual 改善不能覆盖 unresolved、turn 或 local orthogonality 回归。
- L2 必须 available 且无 conflict，候选才可能成为 accepted recommendation。
- L2 unavailable/conflict 时 bucket 可保留 selected candidate，但只能标为 `needs_manual_review` / `diagnostic_only`，且 `accepted=false`、`downstream_recommendation=false`。
- L3/L4 仅在上游层不回归时继续比较；C5 不是 C4，不能进入 HoHoNet evidence bucket。
- L5 不得覆盖 L1–L4；`local_score_total` 永远是最后 fallback。
- 当前不引入局部阈值、加权总分、C3 generator、C7 search、learning 或 writeback。
