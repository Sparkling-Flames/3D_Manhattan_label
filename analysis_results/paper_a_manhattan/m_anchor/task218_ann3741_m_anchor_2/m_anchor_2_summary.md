# M-Anchor.2 task218_ann3741

- Reviewed candidate: `m_anchor_1_footprint_only_joint_xy`
- Expert verdict: `partial_accept_directionally_useful`
- Accept for next stage: `true`
- Accepted as final fix: `false`
- Downstream recommendation / writeback / patch / ranking: `false`

Human finding: footprint direction is slightly improved and useful for the next audit step, but height remains unresolved. `s6 bottom_y` should increase slightly; `s7-s12 top_y` may be too high. `s2` looks acceptable, but ceiling occlusion prevents precise wall-corner confirmation.

M-Anchor.3 authorization, if run next: footprint-only, `bottom_y` variables only, `top_y` fixed, `x` stays within anchor range, no writeback, no ranking.
