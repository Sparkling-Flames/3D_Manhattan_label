# M15.20 Local Candidate Report — task218_ann3741

> 仅供专家本地只读审查。候选不是最终修复，不写回 Label Studio，不进入 routing 或正式 artifact。
> No candidate is authorized as final fix unless all required edges are resolved and no short-wall/collapse risk is worsened.

## Scope

- Local window: `[5, 6, 7, 8]`
- Generated / retained: `42` / `12`
- coordinate_mode: `ls_percent`（显式固定）
- Hard gates: introduced self-intersection；5/6/7 collapse risk

## Case-level Verdict

- Case verdict: No candidate is authorized as final fix.
- Best executable candidate: `candidate_1` (`partial_diagnostic`)
- Why not direct LS apply: Best numeric executable candidate is still partial; required local geometry remains unresolved.
- Primary unresolved local structure: `['6-7']`; persistent dynamic short-wall risk: `['5-6', '6-7']`.
- Recommended next step: Continue with local joint search or expert assertion workflow; do not apply directly in LS.

## Baseline walls

| edge | residual (deg) | floor length | short wall | threshold |
|---|---:|---:|---|---:|
| 4-5 | 1.451 | 4.385 | False | 0.502 |
| 5-6 | 11.560 | 0.234 | True | 0.502 |
| 6-7 | 35.368 | 0.309 | True | 0.502 |
| 7-8 | 1.048 | 0.784 | False | 0.502 |

## Executable candidates ranking

## candidate_1 — height_aware_y_probe

- Label: `pair_6_top_+1.00_bottom_-1.00`
- Changed pairs: `[6]`
- Score: `-20.714` (lower is better)
- Disposition: `partial_neutral_review`
- manual_ls_try_recommended: `False`
- direct_ls_trial_allowed: `False`
- Height worsened / short wall / hard gate: `False` / `True` / `False`
- edge_missing_after: `[]`
- primary_unresolved_edges: `['6-7']`
- all_unresolved_required_edges: `['6-7']`
- short_wall_edges_after: `['5-6', '6-7']`
- short_wall_worsened / below_dynamic_short_threshold: `True` / `True`
- Short-wall preservation explanation: `None`
- decision_class: `partial_diagnostic`
- triage_summary: partial_diagnostic: 6-7 residual improves 35.368 -> 25.030; 6-7 remains unresolved: 35.368 -> 25.030.
- improves: `['6-7 residual improves 35.368 -> 25.030', '5-6 residual improves 11.560 -> 8.305', 'local height residual improves']`
- fails_because: `['6-7 remains unresolved: 35.368 -> 25.030', 'dynamic short-wall risk remains at 5-6 and 6-7', 'dynamic short-wall risk worsens']`
- next_expert_check: Inspect the 6-7-8 window before considering direct LS application.

### 2D coordinate changes

| pair | field | before | after | delta | changed |
|---:|---|---:|---:|---:|---|
| 6 | top_x | 43.860 | 43.860 | 0.000 | False |
| 6 | top_y | 12.283 | 13.283 | 1.000 | True |
| 6 | bottom_x | 43.860 | 43.860 | 0.000 | False |
| 6 | bottom_y | 90.476 | 89.476 | -1.000 | True |

### 3D coordinates

| pair | variant | floor (x,y,z) | ceiling (x,y,z) | wall height |
|---:|---|---|---|---:|
| 6 | original | (-0.186, -1.600, -0.457) | (-0.186, 1.215, -0.457) | 2.815 |
| 6 | candidate | (-0.207, -1.600, -0.509) | (-0.207, 1.239, -0.509) | 2.839 |

### Required wall residuals

| edge | before | after | delta | present | missing | floor length | short wall | threshold | below dynamic threshold |
|---|---:|---:|---:|---|---|---:|---|---:|---|
| 4-5 | 1.451 | 1.451 | 0.000 | True | False | 4.385 | no | 0.502 | no |
| 5-6 | 11.560 | 8.305 | -3.255 | True | False | 0.179 | yes | 0.502 | yes |
| 6-7 | 35.368 | 25.030 | -10.338 | True | False | 0.302 | yes | 0.502 | yes |
| 7-8 | 1.048 | 1.048 | 0.000 | True | False | 0.784 | no | 0.502 | no |

## candidate_2 — height_aware_y_probe

- Label: `pair_7_top_-1.00_bottom_+1.00`
- Changed pairs: `[7]`
- Score: `-16.623` (lower is better)
- Disposition: `partial_neutral_review`
- manual_ls_try_recommended: `False`
- direct_ls_trial_allowed: `False`
- Height worsened / short wall / hard gate: `False` / `True` / `False`
- edge_missing_after: `[]`
- primary_unresolved_edges: `['6-7']`
- all_unresolved_required_edges: `['6-7']`
- short_wall_edges_after: `['5-6', '6-7']`
- short_wall_worsened / below_dynamic_short_threshold: `True` / `True`
- Short-wall preservation explanation: `None`
- decision_class: `partial_diagnostic`
- triage_summary: partial_diagnostic: 6-7 residual improves 35.368 -> 26.315; 6-7 remains unresolved: 35.368 -> 26.315.
- improves: `['6-7 residual improves 35.368 -> 26.315', '7-8 residual improves 1.048 -> 0.568']`
- fails_because: `['6-7 remains unresolved: 35.368 -> 26.315', 'dynamic short-wall risk remains at 5-6 and 6-7', 'dynamic short-wall risk worsens']`
- next_expert_check: Inspect the 6-7-8 window before considering direct LS application.

### 2D coordinate changes

| pair | field | before | after | delta | changed |
|---:|---|---:|---:|---:|---|
| 7 | top_x | 51.660 | 51.660 | 0.000 | False |
| 7 | top_y | 12.695 | 11.695 | -1.000 | True |
| 7 | bottom_x | 51.660 | 51.660 | 0.000 | False |
| 7 | bottom_y | 87.891 | 88.891 | 1.000 | True |

### 3D coordinates

| pair | variant | floor (x,y,z) | ceiling (x,y,z) | wall height |
|---:|---|---|---|---:|
| 7 | original | (0.067, -1.600, -0.636) | (0.067, 1.518, -0.636) | 3.118 |
| 7 | candidate | (0.061, -1.600, -0.579) | (0.061, 1.513, -0.579) | 3.113 |

### Required wall residuals

| edge | before | after | delta | present | missing | floor length | short wall | threshold | below dynamic threshold |
|---|---:|---:|---:|---|---|---:|---|---:|---|
| 4-5 | 1.451 | 1.451 | 0.000 | True | False | 4.385 | no | 0.502 | no |
| 5-6 | 11.560 | 11.560 | 0.000 | True | False | 0.234 | yes | 0.502 | yes |
| 6-7 | 35.368 | 26.315 | -9.053 | True | False | 0.275 | yes | 0.502 | yes |
| 7-8 | 1.048 | 0.568 | -0.480 | True | False | 0.841 | no | 0.502 | no |

## candidate_3 — height_aware_y_probe

- Label: `pair_6_top_-0.50_bottom_-0.50`
- Changed pairs: `[6]`
- Score: `-11.091` (lower is better)
- Disposition: `partial_neutral_review`
- manual_ls_try_recommended: `False`
- direct_ls_trial_allowed: `False`
- Height worsened / short wall / hard gate: `False` / `True` / `False`
- edge_missing_after: `[]`
- primary_unresolved_edges: `['6-7']`
- all_unresolved_required_edges: `['6-7']`
- short_wall_edges_after: `['5-6', '6-7']`
- short_wall_worsened / below_dynamic_short_threshold: `True` / `True`
- Short-wall preservation explanation: `None`
- decision_class: `partial_diagnostic`
- triage_summary: partial_diagnostic: 6-7 residual improves 35.368 -> 30.292; 6-7 remains unresolved: 35.368 -> 30.292.
- improves: `['6-7 residual improves 35.368 -> 30.292', '5-6 residual improves 11.560 -> 10.155', 'local height residual improves']`
- fails_because: `['6-7 remains unresolved: 35.368 -> 30.292', 'dynamic short-wall risk remains at 5-6 and 6-7', 'dynamic short-wall risk worsens']`
- next_expert_check: Inspect the 6-7-8 window before considering direct LS application.

### 2D coordinate changes

| pair | field | before | after | delta | changed |
|---:|---|---:|---:|---:|---|
| 6 | top_x | 43.860 | 43.860 | 0.000 | False |
| 6 | top_y | 12.283 | 11.783 | -0.500 | True |
| 6 | bottom_x | 43.860 | 43.860 | 0.000 | False |
| 6 | bottom_y | 90.476 | 89.976 | -0.500 | True |

### 3D coordinates

| pair | variant | floor (x,y,z) | ceiling (x,y,z) | wall height |
|---:|---|---|---|---:|
| 6 | original | (-0.186, -1.600, -0.457) | (-0.186, 1.215, -0.457) | 2.815 |
| 6 | candidate | (-0.196, -1.600, -0.483) | (-0.196, 1.343, -0.483) | 2.943 |

### Required wall residuals

| edge | before | after | delta | present | missing | floor length | short wall | threshold | below dynamic threshold |
|---|---:|---:|---:|---|---|---:|---|---:|---|
| 4-5 | 1.451 | 1.451 | 0.000 | True | False | 4.385 | no | 0.502 | no |
| 5-6 | 11.560 | 10.155 | -1.405 | True | False | 0.206 | yes | 0.502 | yes |
| 6-7 | 35.368 | 30.292 | -5.076 | True | False | 0.304 | yes | 0.502 | yes |
| 7-8 | 1.048 | 1.048 | 0.000 | True | False | 0.784 | no | 0.502 | no |

## candidate_4 — column_x_align_translate

- Label: `pair_5_align_dx_+0.50`
- Changed pairs: `[5]`
- Score: `-5.477` (lower is better)
- Disposition: `partial_neutral_review`
- manual_ls_try_recommended: `False`
- direct_ls_trial_allowed: `False`
- Height worsened / short wall / hard gate: `False` / `True` / `False`
- edge_missing_after: `[]`
- primary_unresolved_edges: `['6-7']`
- all_unresolved_required_edges: `['6-7']`
- short_wall_edges_after: `['5-6', '6-7']`
- short_wall_worsened / below_dynamic_short_threshold: `False` / `True`
- Short-wall preservation explanation: `pre-existing dynamic short-wall risk preserved without increased deficit`
- decision_class: `partial_diagnostic`
- triage_summary: partial_diagnostic: 5-6 residual improves 11.560 -> 6.086; 6-7 remains unresolved: 35.368 -> 35.368.
- improves: `['5-6 residual improves 11.560 -> 6.086', '4-5 residual improves 1.451 -> 1.353']`
- fails_because: `['6-7 remains unresolved: 35.368 -> 35.368', 'dynamic short-wall risk remains at 5-6 and 6-7']`
- next_expert_check: Inspect the 6-7-8 window before considering direct LS application.

### 2D coordinate changes

| pair | field | before | after | delta | changed |
|---:|---|---:|---:|---:|---|
| 5 | top_x | 44.612 | 45.299 | 0.688 | True |
| 5 | top_y | 14.787 | 14.787 | 0.000 | False |
| 5 | bottom_x | 44.987 | 45.299 | 0.312 | True |
| 5 | bottom_y | 86.466 | 86.466 | 0.000 | False |

### 3D coordinates

| pair | variant | floor (x,y,z) | ceiling (x,y,z) | wall height |
|---:|---|---|---|---:|
| 5 | original | (-0.233, -1.600, -0.686) | (-0.233, 1.446, -0.686) | 3.046 |
| 5 | candidate | (-0.211, -1.600, -0.693) | (-0.211, 1.446, -0.693) | 3.046 |

### Required wall residuals

| edge | before | after | delta | present | missing | floor length | short wall | threshold | below dynamic threshold |
|---|---:|---:|---:|---|---|---:|---|---:|---|
| 4-5 | 1.451 | 1.353 | -0.098 | True | False | 4.406 | no | 0.502 | no |
| 5-6 | 11.560 | 6.086 | -5.473 | True | False | 0.237 | yes | 0.502 | yes |
| 6-7 | 35.368 | 35.368 | 0.000 | True | False | 0.309 | yes | 0.502 | yes |
| 7-8 | 1.048 | 1.048 | 0.000 | True | False | 0.784 | no | 0.502 | no |

## candidate_5 — column_x_align_translate

- Label: `pair_6_align_dx_-0.50`
- Changed pairs: `[6]`
- Score: `-5.157` (lower is better)
- Disposition: `partial_neutral_review`
- manual_ls_try_recommended: `False`
- direct_ls_trial_allowed: `False`
- Height worsened / short wall / hard gate: `False` / `True` / `False`
- edge_missing_after: `[]`
- primary_unresolved_edges: `['6-7']`
- all_unresolved_required_edges: `['6-7']`
- short_wall_edges_after: `['5-6', '6-7']`
- short_wall_worsened / below_dynamic_short_threshold: `False` / `True`
- Short-wall preservation explanation: `pre-existing dynamic short-wall risk preserved without increased deficit`
- decision_class: `partial_diagnostic`
- triage_summary: partial_diagnostic: 5-6 residual improves 11.560 -> 7.886; 6-7 remains unresolved: 35.368 -> 34.782.
- improves: `['5-6 residual improves 11.560 -> 7.886', '6-7 residual improves 35.368 -> 34.782']`
- fails_because: `['6-7 remains unresolved: 35.368 -> 34.782', 'dynamic short-wall risk remains at 5-6 and 6-7']`
- next_expert_check: Inspect the 6-7-8 window before considering direct LS application.

### 2D coordinate changes

| pair | field | before | after | delta | changed |
|---:|---|---:|---:|---:|---|
| 6 | top_x | 43.860 | 43.360 | -0.500 | True |
| 6 | top_y | 12.283 | 12.283 | 0.000 | False |
| 6 | bottom_x | 43.860 | 43.360 | -0.500 | True |
| 6 | bottom_y | 90.476 | 90.476 | 0.000 | False |

### 3D coordinates

| pair | variant | floor (x,y,z) | ceiling (x,y,z) | wall height |
|---:|---|---|---|---:|
| 6 | original | (-0.186, -1.600, -0.457) | (-0.186, 1.215, -0.457) | 2.815 |
| 6 | candidate | (-0.200, -1.600, -0.451) | (-0.200, 1.215, -0.451) | 2.815 |

### Required wall residuals

| edge | before | after | delta | present | missing | floor length | short wall | threshold | below dynamic threshold |
|---|---:|---:|---:|---|---|---:|---|---:|---|
| 4-5 | 1.451 | 1.451 | 0.000 | True | False | 4.385 | no | 0.502 | no |
| 5-6 | 11.560 | 7.886 | -3.673 | True | False | 0.237 | yes | 0.502 | yes |
| 6-7 | 35.368 | 34.782 | -0.586 | True | False | 0.325 | yes | 0.502 | yes |
| 7-8 | 1.048 | 1.048 | 0.000 | True | False | 0.784 | no | 0.502 | no |

## candidate_6 — column_x_align_translate

- Label: `pair_7_align_dx_+0.50`
- Changed pairs: `[7]`
- Score: `-4.977` (lower is better)
- Disposition: `partial_neutral_review`
- manual_ls_try_recommended: `False`
- direct_ls_trial_allowed: `False`
- Height worsened / short wall / hard gate: `False` / `True` / `False`
- edge_missing_after: `[]`
- primary_unresolved_edges: `['6-7']`
- all_unresolved_required_edges: `['6-7']`
- short_wall_edges_after: `['5-6', '6-7']`
- short_wall_worsened / below_dynamic_short_threshold: `False` / `True`
- Short-wall preservation explanation: `pre-existing dynamic short-wall risk preserved without increased deficit`
- decision_class: `partial_diagnostic`
- triage_summary: partial_diagnostic: 6-7 residual improves 35.368 -> 32.982; 6-7 remains unresolved: 35.368 -> 32.982.
- improves: `['6-7 residual improves 35.368 -> 32.982']`
- fails_because: `['6-7 remains unresolved: 35.368 -> 32.982', 'dynamic short-wall risk remains at 5-6 and 6-7']`
- next_expert_check: Inspect the 6-7-8 window before considering direct LS application.

### 2D coordinate changes

| pair | field | before | after | delta | changed |
|---:|---|---:|---:|---:|---|
| 7 | top_x | 51.660 | 52.160 | 0.500 | True |
| 7 | top_y | 12.695 | 12.695 | 0.000 | False |
| 7 | bottom_x | 51.660 | 52.160 | 0.500 | True |
| 7 | bottom_y | 87.891 | 87.891 | 0.000 | False |

### 3D coordinates

| pair | variant | floor (x,y,z) | ceiling (x,y,z) | wall height |
|---:|---|---|---|---:|
| 7 | original | (0.067, -1.600, -0.636) | (0.067, 1.518, -0.636) | 3.118 |
| 7 | candidate | (0.087, -1.600, -0.634) | (0.087, 1.518, -0.634) | 3.118 |

### Required wall residuals

| edge | before | after | delta | present | missing | floor length | short wall | threshold | below dynamic threshold |
|---|---:|---:|---:|---|---|---:|---|---:|---|
| 4-5 | 1.451 | 1.451 | 0.000 | True | False | 4.385 | no | 0.502 | no |
| 5-6 | 11.560 | 11.560 | 0.000 | True | False | 0.234 | yes | 0.502 | yes |
| 6-7 | 35.368 | 32.982 | -2.386 | True | False | 0.325 | yes | 0.502 | yes |
| 7-8 | 1.048 | 2.498 | 1.450 | True | False | 0.787 | no | 0.502 | no |

## candidate_7 — dense_corner_preservation_joint_xy

- Label: `pairs_5_6_separate_0.15_y_-0.50`
- Changed pairs: `[5, 6]`
- Score: `-1.463` (lower is better)
- Disposition: `partial_neutral_review`
- manual_ls_try_recommended: `False`
- direct_ls_trial_allowed: `False`
- Height worsened / short wall / hard gate: `False` / `True` / `False`
- edge_missing_after: `[]`
- primary_unresolved_edges: `['6-7']`
- all_unresolved_required_edges: `['6-7']`
- short_wall_edges_after: `['5-6', '6-7']`
- short_wall_worsened / below_dynamic_short_threshold: `True` / `True`
- Short-wall preservation explanation: `None`
- decision_class: `partial_diagnostic`
- triage_summary: partial_diagnostic: 6-7 residual improves 35.368 -> 30.430; 6-7 remains unresolved: 35.368 -> 30.430.
- improves: `['6-7 residual improves 35.368 -> 30.430', '4-5 residual improves 1.451 -> 1.108', 'local height residual improves']`
- fails_because: `['6-7 remains unresolved: 35.368 -> 30.430', 'dynamic short-wall risk remains at 5-6 and 6-7', 'dynamic short-wall risk worsens']`
- next_expert_check: Inspect the 6-7-8 window before considering direct LS application.

### 2D coordinate changes

| pair | field | before | after | delta | changed |
|---:|---|---:|---:|---:|---|
| 5 | top_x | 44.612 | 44.462 | -0.150 | True |
| 5 | top_y | 14.787 | 14.287 | -0.500 | True |
| 5 | bottom_x | 44.987 | 44.837 | -0.150 | True |
| 5 | bottom_y | 86.466 | 85.966 | -0.500 | True |
| 6 | top_x | 43.860 | 44.010 | 0.150 | True |
| 6 | top_y | 12.283 | 11.783 | -0.500 | True |
| 6 | bottom_x | 43.860 | 44.010 | 0.150 | True |
| 6 | bottom_y | 90.476 | 89.976 | -0.500 | True |

### 3D coordinates

| pair | variant | floor (x,y,z) | ceiling (x,y,z) | wall height |
|---:|---|---|---|---:|
| 5 | original | (-0.233, -1.600, -0.686) | (-0.233, 1.446, -0.686) | 3.046 |
| 6 | original | (-0.186, -1.600, -0.457) | (-0.186, 1.215, -0.457) | 2.815 |
| 5 | candidate | (-0.249, -1.600, -0.713) | (-0.249, 1.568, -0.713) | 3.168 |
| 6 | candidate | (-0.192, -1.600, -0.485) | (-0.192, 1.343, -0.485) | 2.943 |

### Required wall residuals

| edge | before | after | delta | present | missing | floor length | short wall | threshold | below dynamic threshold |
|---|---:|---:|---:|---|---|---:|---|---:|---|
| 4-5 | 1.451 | 1.108 | -0.343 | True | False | 4.368 | no | 0.502 | no |
| 5-6 | 11.560 | 14.151 | 2.591 | True | False | 0.235 | yes | 0.502 | yes |
| 6-7 | 35.368 | 30.430 | -4.938 | True | False | 0.299 | yes | 0.502 | yes |
| 7-8 | 1.048 | 1.048 | 0.000 | True | False | 0.784 | no | 0.502 | no |

## candidate_8 — dense_corner_preservation_joint_xy

- Label: `pairs_5_6_separate_0.30_y_-0.50`
- Changed pairs: `[5, 6]`
- Score: `8.142` (lower is better)
- Disposition: `partial_neutral_review`
- manual_ls_try_recommended: `False`
- direct_ls_trial_allowed: `False`
- Height worsened / short wall / hard gate: `False` / `True` / `False`
- edge_missing_after: `[]`
- primary_unresolved_edges: `['6-7']`
- all_unresolved_required_edges: `['5-6', '6-7']`
- short_wall_edges_after: `['5-6', '6-7']`
- short_wall_worsened / below_dynamic_short_threshold: `True` / `True`
- Short-wall preservation explanation: `None`
- decision_class: `partial_diagnostic`
- triage_summary: partial_diagnostic: 6-7 residual improves 35.368 -> 30.582; 5-6 remains unresolved: 11.560 -> 17.078.
- improves: `['6-7 residual improves 35.368 -> 30.582', '4-5 residual improves 1.451 -> 1.141', 'local height residual improves']`
- fails_because: `['5-6 remains unresolved: 11.560 -> 17.078', '6-7 remains unresolved: 35.368 -> 30.582', 'dynamic short-wall risk remains at 5-6 and 6-7', 'dynamic short-wall risk worsens']`
- next_expert_check: Inspect the 6-7-8 window before considering direct LS application.

### 2D coordinate changes

| pair | field | before | after | delta | changed |
|---:|---|---:|---:|---:|---|
| 5 | top_x | 44.612 | 44.312 | -0.300 | True |
| 5 | top_y | 14.787 | 14.287 | -0.500 | True |
| 5 | bottom_x | 44.987 | 44.687 | -0.300 | True |
| 5 | bottom_y | 86.466 | 85.966 | -0.500 | True |
| 6 | top_x | 43.860 | 44.160 | 0.300 | True |
| 6 | top_y | 12.283 | 11.783 | -0.500 | True |
| 6 | bottom_x | 43.860 | 44.160 | 0.300 | True |
| 6 | bottom_y | 90.476 | 89.976 | -0.500 | True |

### 3D coordinates

| pair | variant | floor (x,y,z) | ceiling (x,y,z) | wall height |
|---:|---|---|---|---:|
| 5 | original | (-0.233, -1.600, -0.686) | (-0.233, 1.446, -0.686) | 3.046 |
| 6 | original | (-0.186, -1.600, -0.457) | (-0.186, 1.215, -0.457) | 2.815 |
| 5 | candidate | (-0.256, -1.600, -0.710) | (-0.256, 1.568, -0.710) | 3.168 |
| 6 | candidate | (-0.187, -1.600, -0.486) | (-0.187, 1.343, -0.486) | 2.943 |

### Required wall residuals

| edge | before | after | delta | present | missing | floor length | short wall | threshold | below dynamic threshold |
|---|---:|---:|---:|---|---|---:|---|---:|---|
| 4-5 | 1.451 | 1.141 | -0.310 | True | False | 4.361 | no | 0.502 | no |
| 5-6 | 11.560 | 17.078 | 5.518 | True | False | 0.234 | yes | 0.502 | yes |
| 6-7 | 35.368 | 30.582 | -4.786 | True | False | 0.295 | yes | 0.502 | yes |
| 7-8 | 1.048 | 1.048 | 0.000 | True | False | 0.784 | no | 0.502 | no |

## candidate_9 — dense_corner_preservation_joint_xy

- Label: `pairs_5_6_separate_0.50_y_-0.50`
- Changed pairs: `[5, 6]`
- Score: `18.583` (lower is better)
- Disposition: `partial_neutral_review`
- manual_ls_try_recommended: `False`
- direct_ls_trial_allowed: `False`
- Height worsened / short wall / hard gate: `False` / `True` / `False`
- edge_missing_after: `[]`
- primary_unresolved_edges: `['6-7']`
- all_unresolved_required_edges: `['5-6', '6-7']`
- short_wall_edges_after: `['5-6', '6-7']`
- short_wall_worsened / below_dynamic_short_threshold: `True` / `True`
- Short-wall preservation explanation: `None`
- decision_class: `partial_diagnostic`
- triage_summary: partial_diagnostic: 6-7 residual improves 35.368 -> 30.806; 5-6 remains unresolved: 11.560 -> 21.005.
- improves: `['6-7 residual improves 35.368 -> 30.806', '4-5 residual improves 1.451 -> 1.186', 'local height residual improves']`
- fails_because: `['5-6 remains unresolved: 11.560 -> 21.005', '6-7 remains unresolved: 35.368 -> 30.806', 'dynamic short-wall risk remains at 5-6 and 6-7', 'dynamic short-wall risk worsens']`
- next_expert_check: Inspect the 6-7-8 window before considering direct LS application.

### 2D coordinate changes

| pair | field | before | after | delta | changed |
|---:|---|---:|---:|---:|---|
| 5 | top_x | 44.612 | 44.112 | -0.500 | True |
| 5 | top_y | 14.787 | 14.287 | -0.500 | True |
| 5 | bottom_x | 44.987 | 44.487 | -0.500 | True |
| 5 | bottom_y | 86.466 | 85.966 | -0.500 | True |
| 6 | top_x | 43.860 | 44.360 | 0.500 | True |
| 6 | top_y | 12.283 | 11.783 | -0.500 | True |
| 6 | bottom_x | 43.860 | 44.360 | 0.500 | True |
| 6 | bottom_y | 90.476 | 89.976 | -0.500 | True |

### 3D coordinates

| pair | variant | floor (x,y,z) | ceiling (x,y,z) | wall height |
|---:|---|---|---|---:|
| 5 | original | (-0.233, -1.600, -0.686) | (-0.233, 1.446, -0.686) | 3.046 |
| 6 | original | (-0.186, -1.600, -0.457) | (-0.186, 1.215, -0.457) | 2.815 |
| 5 | candidate | (-0.265, -1.600, -0.707) | (-0.265, 1.568, -0.707) | 3.168 |
| 6 | candidate | (-0.181, -1.600, -0.489) | (-0.181, 1.343, -0.489) | 2.943 |

### Required wall residuals

| edge | before | after | delta | present | missing | floor length | short wall | threshold | below dynamic threshold |
|---|---:|---:|---:|---|---|---:|---|---:|---|
| 4-5 | 1.451 | 1.186 | -0.265 | True | False | 4.352 | no | 0.502 | no |
| 5-6 | 11.560 | 21.005 | 9.445 | True | False | 0.234 | yes | 0.502 | yes |
| 6-7 | 35.368 | 30.806 | -4.562 | True | False | 0.288 | yes | 0.502 | yes |
| 7-8 | 1.048 | 1.048 | 0.000 | True | False | 0.784 | no | 0.502 | no |

## Read-only topology hypotheses

> Topology hypotheses are not executable candidate rankings.

## topology_1 — local_order_topology_hypothesis

- Label: `swap_pair_5_6`
- Changed pairs: `[5, 6]`
- Diagnostic score: `-49.680`. Not executable; not ranked with candidate_N.
- Disposition: `neutral_review_topology_hypothesis`
- manual_ls_try_recommended: `False`
- direct_ls_trial_allowed: `False`
- Height worsened / short wall / hard gate: `False` / `False` / `False`
- edge_missing_after: `['4-5', '5-6', '6-7']`
- primary_unresolved_edges: `['6-7']`
- all_unresolved_required_edges: `['4-5', '5-6', '6-7']`
- short_wall_edges_after: `[]`
- short_wall_worsened / below_dynamic_short_threshold: `False` / `False`
- Short-wall preservation explanation: `None`

### 2D coordinate changes

| pair | field | before | after | delta | changed |
|---:|---|---:|---:|---:|---|
| 5 | top_x | 44.612 | 44.612 | 0.000 | False |
| 5 | top_y | 14.787 | 14.787 | 0.000 | False |
| 5 | bottom_x | 44.987 | 44.987 | 0.000 | False |
| 5 | bottom_y | 86.466 | 86.466 | 0.000 | False |
| 6 | top_x | 43.860 | 43.860 | 0.000 | False |
| 6 | top_y | 12.283 | 12.283 | 0.000 | False |
| 6 | bottom_x | 43.860 | 43.860 | 0.000 | False |
| 6 | bottom_y | 90.476 | 90.476 | 0.000 | False |

### 3D coordinates

| pair | variant | floor (x,y,z) | ceiling (x,y,z) | wall height |
|---:|---|---|---|---:|
| 5 | original | (-0.233, -1.600, -0.686) | (-0.233, 1.446, -0.686) | 3.046 |
| 6 | original | (-0.186, -1.600, -0.457) | (-0.186, 1.215, -0.457) | 2.815 |
| 6 | candidate | (-0.186, -1.600, -0.457) | (-0.186, 1.215, -0.457) | 2.815 |
| 5 | candidate | (-0.233, -1.600, -0.686) | (-0.233, 1.446, -0.686) | 3.046 |

### Required wall residuals

| edge | before | after | delta | present | missing | floor length | short wall | threshold | below dynamic threshold |
|---|---:|---:|---:|---|---|---:|---|---:|---|
| 4-5 | 1.451 | — | — | False | True | — | — | — | — |
| 5-6 | 11.560 | — | — | False | True | — | — | — | — |
| 6-7 | 35.368 | — | — | False | True | — | — | — | — |
| 7-8 | 1.048 | 1.048 | 0.000 | True | False | 0.784 | no | 0.502 | no |

## topology_2 — local_order_topology_hypothesis

- Label: `swap_pair_7_8`
- Changed pairs: `[7, 8]`
- Diagnostic score: `22.129`. Not executable; not ranked with candidate_N.
- Disposition: `neutral_review_topology_hypothesis`
- manual_ls_try_recommended: `False`
- direct_ls_trial_allowed: `False`
- Height worsened / short wall / hard gate: `False` / `True` / `False`
- edge_missing_after: `['6-7', '7-8']`
- primary_unresolved_edges: `['6-7']`
- all_unresolved_required_edges: `['6-7', '7-8']`
- short_wall_edges_after: `['5-6']`
- short_wall_worsened / below_dynamic_short_threshold: `False` / `True`
- Short-wall preservation explanation: `pre-existing dynamic short-wall risk preserved without increased deficit`

### 2D coordinate changes

| pair | field | before | after | delta | changed |
|---:|---|---:|---:|---:|---|
| 7 | top_x | 51.660 | 51.660 | 0.000 | False |
| 7 | top_y | 12.695 | 12.695 | 0.000 | False |
| 7 | bottom_x | 51.660 | 51.660 | 0.000 | False |
| 7 | bottom_y | 87.891 | 87.891 | 0.000 | False |
| 8 | top_x | 50.586 | 50.586 | 0.000 | False |
| 8 | top_y | 25.911 | 25.911 | 0.000 | False |
| 8 | bottom_x | 50.586 | 50.586 | 0.000 | False |
| 8 | bottom_y | 76.886 | 76.886 | 0.000 | False |

### 3D coordinates

| pair | variant | floor (x,y,z) | ceiling (x,y,z) | wall height |
|---:|---|---|---|---:|
| 7 | original | (0.067, -1.600, -0.636) | (0.067, 1.518, -0.636) | 3.118 |
| 8 | original | (0.052, -1.600, -1.420) | (0.052, 1.342, -1.420) | 2.942 |
| 8 | candidate | (0.052, -1.600, -1.420) | (0.052, 1.342, -1.420) | 2.942 |
| 7 | candidate | (0.067, -1.600, -0.636) | (0.067, 1.518, -0.636) | 3.118 |

### Required wall residuals

| edge | before | after | delta | present | missing | floor length | short wall | threshold | below dynamic threshold |
|---|---:|---:|---:|---|---|---:|---|---:|---|
| 4-5 | 1.451 | 1.451 | 0.000 | True | False | 4.385 | no | 0.502 | no |
| 5-6 | 11.560 | 11.560 | 0.000 | True | False | 0.234 | yes | 0.502 | yes |
| 6-7 | 35.368 | — | — | False | True | — | — | — | — |
| 7-8 | 1.048 | — | — | False | True | — | — | — | — |

## topology_3 — local_order_topology_hypothesis

- Label: `swap_pair_6_7`
- Changed pairs: `[6, 7]`
- Diagnostic score: `55.690`. Not executable; not ranked with candidate_N.
- Disposition: `suppressed_hard_risk`
- manual_ls_try_recommended: `False`
- direct_ls_trial_allowed: `False`
- Height worsened / short wall / hard gate: `False` / `False` / `True`
- edge_missing_after: `['5-6', '6-7', '7-8']`
- primary_unresolved_edges: `['6-7']`
- all_unresolved_required_edges: `['5-6', '6-7', '7-8']`
- short_wall_edges_after: `[]`
- short_wall_worsened / below_dynamic_short_threshold: `False` / `False`
- Short-wall preservation explanation: `None`

### 2D coordinate changes

| pair | field | before | after | delta | changed |
|---:|---|---:|---:|---:|---|
| 6 | top_x | 43.860 | 43.860 | 0.000 | False |
| 6 | top_y | 12.283 | 12.283 | 0.000 | False |
| 6 | bottom_x | 43.860 | 43.860 | 0.000 | False |
| 6 | bottom_y | 90.476 | 90.476 | 0.000 | False |
| 7 | top_x | 51.660 | 51.660 | 0.000 | False |
| 7 | top_y | 12.695 | 12.695 | 0.000 | False |
| 7 | bottom_x | 51.660 | 51.660 | 0.000 | False |
| 7 | bottom_y | 87.891 | 87.891 | 0.000 | False |

### 3D coordinates

| pair | variant | floor (x,y,z) | ceiling (x,y,z) | wall height |
|---:|---|---|---|---:|
| 6 | original | (-0.186, -1.600, -0.457) | (-0.186, 1.215, -0.457) | 2.815 |
| 7 | original | (0.067, -1.600, -0.636) | (0.067, 1.518, -0.636) | 3.118 |
| 7 | candidate | (0.067, -1.600, -0.636) | (0.067, 1.518, -0.636) | 3.118 |
| 6 | candidate | (-0.186, -1.600, -0.457) | (-0.186, 1.215, -0.457) | 2.815 |

### Required wall residuals

| edge | before | after | delta | present | missing | floor length | short wall | threshold | below dynamic threshold |
|---|---:|---:|---:|---|---|---:|---|---:|---|
| 4-5 | 1.451 | 1.451 | 0.000 | True | False | 4.385 | no | 0.502 | no |
| 5-6 | 11.560 | — | — | False | True | — | — | — | — |
| 6-7 | 35.368 | — | — | False | True | — | — | — | — |
| 7-8 | 1.048 | — | — | False | True | — | — | — | — |

## Interpretation boundary

- `partial_neutral_review` 表示局部评分下降，但 6–7 或 7–8 仍未解决，不能视为最终修复。
- topology hypothesis 只供人工理解局部顺序，不授权自动 reorder、merge 或 delete。
- 所有候选均需人工结合全景与 3D 视觉判断；本报告不生成 annotation patch。
