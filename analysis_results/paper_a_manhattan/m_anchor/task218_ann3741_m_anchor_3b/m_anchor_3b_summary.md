# M-Anchor.3b task218_ann3741

M-Anchor.3b tests whether local-chain x/bottom_y constrained footprint adjustments can reduce affected BEV Manhattan residuals while preserving visual anchors and local topology. top_y remains fixed and height is not entered.

- Existing M-Anchor.3 is retained as `s6 bottom_y` sensitivity diagnostic.
- Geometry residual decides review worthiness only; visual hard anchors and local topology outrank residual sum.
- raw_candidates_evaluated: `113`
- candidate_count: `5`

| candidate | moved pairs | local max before->after | local sum before->after | global sum after | movement | decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| m_anchor_3b_candidate_0016 | [5] | 3.456->2.146 | 6.912->3.740 | 33.569 | 0.500 | review_available |
| m_anchor_3b_candidate_0101 | [7, 8] | 3.456->2.849 | 10.368->6.682 | 33.055 | 1.000 | review_available |
| m_anchor_3b_candidate_0034 | [6] | 3.456->3.022 | 6.912->5.471 | 35.300 | 0.500 | review_available |
| m_anchor_3b_candidate_0095 | [5, 6] | 3.456->3.022 | 10.368->5.538 | 31.911 | 1.000 | review_available |
| m_anchor_3b_candidate_0047 | [5, 6] | 3.456->3.022 | 10.368->5.640 | 32.013 | 0.750 | review_available |
