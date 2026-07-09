# M-Anchor.1 task218_ann3741

- Mode: human visual semantics anchor the layout; solver only fills geometry consistency.
- anchor_satisfaction_rate: `0.8542`
- candidate_available_rate: `0.3333`
- expert_accept@3: `None` (pending_human_review)
- rejected_false_drift_rate: `0.6667`
- available_false_drift_rate: `0.0000`

| candidate | scope | anchor rate | wall sum | height L1 | decision |
| --- | --- | ---: | ---: | ---: | --- |
| m_anchor_1_footprint_only_joint_xy | footprint_only | 1.0000 | 36.741 | 1.995 | review_available |
| m_anchor_1_height_only_plane_preserving | height_only | 0.8750 | 45.277 | 0.000 | rejected_false_visual_drift |
| m_anchor_1_false_drift_reference_robust_all_long_edges | diagnostic_reference | 0.6875 | 41.470 | 0.000 | rejected_hard_anchor_violation |

- Safety: accepted/downstream/preference/writeback/patch all remain `false`.
