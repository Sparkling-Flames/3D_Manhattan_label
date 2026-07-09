# M-Anchor.3 task218_ann3741

M-Anchor.3 verifies whether bottom_y-only adjustment can improve BEV footprint Manhattan consistency under fixed/limited expert visual x anchors, while avoiding visual drift.

- candidate_count: `2`
- Variables: `bottom_y` only; `top_y` fixed; reorder/merge/delete/new corner forbidden.
- Safety: accepted/downstream/writeback/ranking/portfolio all remain `false`.

| candidate | s6 bottom_y delta | wall sum before | wall sum after | wall max after | decision |
| --- | ---: | ---: | ---: | ---: | --- |
| m_anchor_3_s6_bottom_y_p025 | 0.25 | 36.741 | 36.040 | 3.456 | review_available |
| m_anchor_3_s6_bottom_y_p05 | 0.50 | 36.741 | 35.300 | 3.456 | review_available |
