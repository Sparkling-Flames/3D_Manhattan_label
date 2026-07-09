# M-Anchor.4 task218_ann3741 staged vertical+height review

- Goal: first make the footprint/wall directions more Manhattan with `x + bottom_y`; then keep footprint fixed and adjust `top_y` for height consistency.
- Geometry residual is still review triage only; no candidate is accepted or written back.
- allowed_source_pair_ids: `[1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12]`
- protected_source_pair_ids: `[3]`
- candidate_count: `4`

| candidate | changed pairs | wall max before->footprint | wall sum before->footprint | height L1 before->after | vertical x residual | decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| m_anchor_4_candidate_0002_sum_first | [1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12] | 3.456->0.397 | 36.741->2.196 | 1.995->0.765 | 0.000000 | review_available |
| m_anchor_4_candidate_0001_max_first | [1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12] | 3.456->0.397 | 36.741->2.724 | 1.995->0.781 | 0.000000 | review_available |
| m_anchor_4_candidate_0003_turn_aware | [1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12] | 3.456->0.577 | 36.741->3.425 | 1.995->0.791 | 0.000000 | review_available |
| m_anchor_4_candidate_0004_bottom_only | [1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12] | 3.456->2.741 | 36.741->14.876 | 1.995->0.659 | 0.000000 | review_available |
