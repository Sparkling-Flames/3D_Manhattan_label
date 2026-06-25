# HRC C6.5a.5 GT Correction Materialization and Diagnostic Audit

- Case: `task238_ann2389_4543gt`
- Corrected GT: `4543gt`
- Old GT: `deprecated_superseded_source`
- Candidate-specific: `false`
- Candidate preference authorized: `false`
- Accepted/downstream/writeback: `false/false/false`
- C6.5b/C3/C7/C9/C10: `blocked`

## Old vs corrected

- `pair_count`: `6` -> `4`
- `wall_residual_sum_deg`: `23.15423585045923` -> `29.38896184358896`
- `wall_residual_max_deg`: `15.874611251834466` -> `15.874611251834466`
- `turn_residual_sum_deg`: `39.23856857364639` -> `55.635075266545854`
- `turn_residual_max_deg`: `18.039339151940425` -> `27.81753763327292`
- `dominant_height`: `2.5356805161014138` -> `2.504874031260205`
- `height_mad`: `0.0036713174843827634` -> `0.05204932665301998`
- `height_residual_max`: `0.10083529153389348` -> `0.13028063936401502`
- `minimum_wall_length`: `0.8885206187463435` -> `2.3955698129032315`
- `short_wall_count`: `0` -> `0`

Manual review confirms explicit column identity and a sufficient four-corner topology. Short-wall/dense-corner preservation and keep-distinct evidence are not applicable.
