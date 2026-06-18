# M15.20 Local Candidate Report — task218_ann3741

> 仅供专家本地只读审查。候选不是最终修复，不写回 Label Studio，不进入 routing 或正式 artifact。

## Scope

- Local window: `[5, 6, 7, 8]`
- Generated / retained: `42` / `12`
- coordinate_mode: `ls_percent`（显式固定）
- Hard gates: introduced self-intersection；5/6/7 collapse risk

## Baseline walls

| edge | residual (deg) | floor length |
|---|---:|---:|
| 4-5 | 1.451 | 4.385 |
| 5-6 | 11.560 | 0.234 |
| 6-7 | 35.368 | 0.309 |
| 7-8 | 1.048 | 0.784 |

## candidate_1 — local_order_topology_hypothesis

- Label: `swap_pair_5_6`
- Changed pairs: `[5, 6]`
- Score: `-35.873` (lower is better)
- Disposition: `neutral_review_topology_hypothesis`
- Recommend manual LS try: `False`
- Height worsened / short wall / hard gate: `False` / `False` / `False`
- Unresolved required edges: `['6-7']`

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

| edge | before | after | delta | length after | present |
|---|---:|---:|---:|---:|---|
| 4-5 | 1.451 | — | — | — | False |
| 5-6 | 11.560 | — | — | — | False |
| 6-7 | 35.368 | — | — | — | False |
| 7-8 | 1.048 | 1.048 | 0.000 | 0.784 | True |

## candidate_2 — height_aware_y_probe

- Label: `pair_6_top_+1.00_bottom_-1.00`
- Changed pairs: `[6]`
- Score: `-21.959` (lower is better)
- Disposition: `partial_neutral_review`
- Recommend manual LS try: `False`
- Height worsened / short wall / hard gate: `False` / `True` / `False`
- Unresolved required edges: `['6-7']`

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

| edge | before | after | delta | length after | present |
|---|---:|---:|---:|---:|---|
| 4-5 | 1.451 | 1.451 | 0.000 | 4.385 | True |
| 5-6 | 11.560 | 8.305 | -3.255 | 0.179 | True |
| 6-7 | 35.368 | 25.030 | -10.338 | 0.302 | True |
| 7-8 | 1.048 | 1.048 | 0.000 | 0.784 | True |

## candidate_3 — height_aware_y_probe

- Label: `pair_7_top_-1.00_bottom_+1.00`
- Changed pairs: `[7]`
- Score: `-17.662` (lower is better)
- Disposition: `partial_neutral_review`
- Recommend manual LS try: `False`
- Height worsened / short wall / hard gate: `False` / `False` / `False`
- Unresolved required edges: `['6-7']`

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

| edge | before | after | delta | length after | present |
|---|---:|---:|---:|---:|---|
| 4-5 | 1.451 | 1.451 | 0.000 | 4.385 | True |
| 5-6 | 11.560 | 11.560 | 0.000 | 0.234 | True |
| 6-7 | 35.368 | 26.315 | -9.053 | 0.275 | True |
| 7-8 | 1.048 | 0.568 | -0.480 | 0.841 | True |

## candidate_4 — height_aware_y_probe

- Label: `pair_6_top_-0.50_bottom_-0.50`
- Changed pairs: `[6]`
- Score: `-12.059` (lower is better)
- Disposition: `partial_neutral_review`
- Recommend manual LS try: `False`
- Height worsened / short wall / hard gate: `False` / `False` / `False`
- Unresolved required edges: `['6-7']`

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

| edge | before | after | delta | length after | present |
|---|---:|---:|---:|---:|---|
| 4-5 | 1.451 | 1.451 | 0.000 | 4.385 | True |
| 5-6 | 11.560 | 10.155 | -1.405 | 0.206 | True |
| 6-7 | 35.368 | 30.292 | -5.076 | 0.304 | True |
| 7-8 | 1.048 | 1.048 | 0.000 | 0.784 | True |

## candidate_5 — column_x_align_translate

- Label: `pair_5_align_dx_+0.50`
- Changed pairs: `[5]`
- Score: `-5.370` (lower is better)
- Disposition: `partial_neutral_review`
- Recommend manual LS try: `False`
- Height worsened / short wall / hard gate: `False` / `False` / `False`
- Unresolved required edges: `['6-7']`

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

| edge | before | after | delta | length after | present |
|---|---:|---:|---:|---:|---|
| 4-5 | 1.451 | 1.353 | -0.098 | 4.406 | True |
| 5-6 | 11.560 | 6.086 | -5.473 | 0.237 | True |
| 6-7 | 35.368 | 35.368 | 0.000 | 0.309 | True |
| 7-8 | 1.048 | 1.048 | 0.000 | 0.784 | True |

## candidate_6 — column_x_align_translate

- Label: `pair_6_align_dx_-0.50`
- Changed pairs: `[6]`
- Score: `-4.595` (lower is better)
- Disposition: `partial_neutral_review`
- Recommend manual LS try: `False`
- Height worsened / short wall / hard gate: `False` / `False` / `False`
- Unresolved required edges: `['6-7']`

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

| edge | before | after | delta | length after | present |
|---|---:|---:|---:|---:|---|
| 4-5 | 1.451 | 1.451 | 0.000 | 4.385 | True |
| 5-6 | 11.560 | 7.886 | -3.673 | 0.237 | True |
| 6-7 | 35.368 | 34.782 | -0.586 | 0.325 | True |
| 7-8 | 1.048 | 1.048 | 0.000 | 0.784 | True |

## candidate_7 — column_x_align_translate

- Label: `pair_7_align_dx_+0.50`
- Changed pairs: `[7]`
- Score: `-4.522` (lower is better)
- Disposition: `partial_neutral_review`
- Recommend manual LS try: `False`
- Height worsened / short wall / hard gate: `False` / `False` / `False`
- Unresolved required edges: `['6-7']`

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

| edge | before | after | delta | length after | present |
|---|---:|---:|---:|---:|---|
| 4-5 | 1.451 | 1.451 | 0.000 | 4.385 | True |
| 5-6 | 11.560 | 11.560 | 0.000 | 0.234 | True |
| 6-7 | 35.368 | 32.982 | -2.386 | 0.325 | True |
| 7-8 | 1.048 | 2.498 | 1.450 | 0.787 | True |

## candidate_8 — dense_corner_preservation_joint_xy

- Label: `pairs_5_6_separate_0.15_y_-0.50`
- Changed pairs: `[5, 6]`
- Score: `-1.718` (lower is better)
- Disposition: `partial_neutral_review`
- Recommend manual LS try: `False`
- Height worsened / short wall / hard gate: `False` / `False` / `False`
- Unresolved required edges: `['6-7']`

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

| edge | before | after | delta | length after | present |
|---|---:|---:|---:|---:|---|
| 4-5 | 1.451 | 1.108 | -0.343 | 4.368 | True |
| 5-6 | 11.560 | 14.151 | 2.591 | 0.235 | True |
| 6-7 | 35.368 | 30.430 | -4.938 | 0.299 | True |
| 7-8 | 1.048 | 1.048 | 0.000 | 0.784 | True |

## candidate_9 — dense_corner_preservation_joint_xy

- Label: `pairs_5_6_separate_0.30_y_-0.50`
- Changed pairs: `[5, 6]`
- Score: `7.712` (lower is better)
- Disposition: `neutral_review`
- Recommend manual LS try: `False`
- Height worsened / short wall / hard gate: `False` / `False` / `False`
- Unresolved required edges: `['6-7']`

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

| edge | before | after | delta | length after | present |
|---|---:|---:|---:|---:|---|
| 4-5 | 1.451 | 1.141 | -0.310 | 4.361 | True |
| 5-6 | 11.560 | 17.078 | 5.518 | 0.234 | True |
| 6-7 | 35.368 | 30.582 | -4.786 | 0.295 | True |
| 7-8 | 1.048 | 1.048 | 0.000 | 0.784 | True |

## candidate_10 — dense_corner_preservation_joint_xy

- Label: `pairs_5_6_separate_0.50_y_-0.50`
- Changed pairs: `[5, 6]`
- Score: `17.949` (lower is better)
- Disposition: `neutral_review`
- Recommend manual LS try: `False`
- Height worsened / short wall / hard gate: `False` / `False` / `False`
- Unresolved required edges: `['6-7']`

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

| edge | before | after | delta | length after | present |
|---|---:|---:|---:|---:|---|
| 4-5 | 1.451 | 1.186 | -0.265 | 4.352 | True |
| 5-6 | 11.560 | 21.005 | 9.445 | 0.234 | True |
| 6-7 | 35.368 | 30.806 | -4.562 | 0.288 | True |
| 7-8 | 1.048 | 1.048 | 0.000 | 0.784 | True |

## candidate_11 — local_order_topology_hypothesis

- Label: `swap_pair_7_8`
- Changed pairs: `[7, 8]`
- Score: `27.895` (lower is better)
- Disposition: `neutral_review_topology_hypothesis`
- Recommend manual LS try: `False`
- Height worsened / short wall / hard gate: `False` / `False` / `False`
- Unresolved required edges: `['6-7', '7-8']`

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

| edge | before | after | delta | length after | present |
|---|---:|---:|---:|---:|---|
| 4-5 | 1.451 | 1.451 | 0.000 | 4.385 | True |
| 5-6 | 11.560 | 11.560 | 0.000 | 0.234 | True |
| 6-7 | 35.368 | — | — | — | False |
| 7-8 | 1.048 | — | — | — | False |

## candidate_12 — local_order_topology_hypothesis

- Label: `swap_pair_6_7`
- Changed pairs: `[6, 7]`
- Score: `69.497` (lower is better)
- Disposition: `suppressed_hard_risk`
- Recommend manual LS try: `False`
- Height worsened / short wall / hard gate: `False` / `False` / `True`
- Unresolved required edges: `['6-7', '7-8']`

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

| edge | before | after | delta | length after | present |
|---|---:|---:|---:|---:|---|
| 4-5 | 1.451 | 1.451 | 0.000 | 4.385 | True |
| 5-6 | 11.560 | — | — | — | False |
| 6-7 | 35.368 | — | — | — | False |
| 7-8 | 1.048 | — | — | — | False |

## Interpretation boundary

- `partial_neutral_review` 表示局部评分下降，但 6–7 或 7–8 仍未解决，不能视为最终修复。
- topology hypothesis 只供人工理解局部顺序，不授权自动 reorder、merge 或 delete。
- 所有候选均需人工结合全景与 3D 视觉判断；本报告不生成 annotation patch。
