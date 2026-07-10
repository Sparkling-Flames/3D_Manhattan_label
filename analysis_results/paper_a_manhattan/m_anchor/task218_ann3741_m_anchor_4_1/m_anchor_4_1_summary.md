# M-Anchor.4.1 human-guidance-bound footprint shadow probe

- Goal: M-Anchor.4.1 tests whether human-guided x/bottom_y footprint changes can be reviewed without violating visual anchors; top_y is forbidden and height is not entered.
- M4.2 height completion is not authorized here; it requires a future human `partial_accept_directionally_useful` verdict for one M4.1 candidate.
- raw_candidates_evaluated: `51`
- candidate_count: `5`

| candidate | moved pairs | L1 movement | local worst before->after | global sum before->after | decision |
| --- | --- | ---: | ---: | ---: | --- |
| m_anchor_4_1_candidate_0025 | [4, 9, 10] | 0.450 | 3.456->3.648 | 36.741->36.975 | review_available |
| m_anchor_4_1_candidate_0026 | [4, 9, 10] | 0.600 | 3.456->3.648 | 36.741->36.709 | review_available |
| m_anchor_4_1_candidate_0027 | [4, 9, 10] | 0.750 | 3.456->3.648 | 36.741->36.443 | review_available |
| m_anchor_4_1_candidate_0016 | [4, 9, 10] | 0.750 | 3.456->4.018 | 36.741->37.398 | review_available |
| m_anchor_4_1_candidate_0022 | [4, 9, 10] | 0.750 | 3.456->4.035 | 36.741->37.553 | review_available |
