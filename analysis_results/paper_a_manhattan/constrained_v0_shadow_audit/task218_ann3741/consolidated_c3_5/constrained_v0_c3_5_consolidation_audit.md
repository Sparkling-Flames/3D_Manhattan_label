# Constrained v0 C3.5 Two-Family Consolidation Audit

- Case: `task218_ann3741`
- Implemented families: `['column_x_alignment', 'height_target_reproject']`
- Deferred families: `['short_wall_preserving_local', 'primary_edge_direction_family_repair', 'floor_depth_balance']`
- Authorization: shadow-only; accepted=false; downstream_recommendation=false.

## Per-family audit

- `column_x_alignment_real`: candidate_count=`0`, reasons=`['column_identity_unavailable', 'evidence_unavailable']`
- `height_target_reproject_real`: candidate_count=`0`, reasons=`['height_target_unavailable']`
- `height_target_reproject_positive_fixture`: candidate_count=`1`, reasons=`['pair_1:height_reproject_formula_unavailable', 'pair_1:y_permission_missing', 'pair_2:height_reproject_formula_unavailable', 'pair_2:y_permission_missing']`

## Warnings

- This audit does not authorize active source replacement.
- This audit does not prove final geometric correctness.
- C6 remains not stable ranker.
- C7/C9/C10 remain blocked.
