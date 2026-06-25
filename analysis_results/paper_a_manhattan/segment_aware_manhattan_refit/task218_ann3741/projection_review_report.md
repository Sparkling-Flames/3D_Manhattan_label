# Local 3D Projection Review

## Input Provenance

- Review schema: `local_3d_projection_review_m15_27_1_bridge_v1`
- Projection schema: `local_3d_projection_m15_19_v1`
- Input file: `_review_input.json`
- Input SHA-256: `a0c9023204abb7fedb64d0239afa4673571c896ff1455a7e0424d60e3c3119bf`
- Ordered-pair source: `input.ordered_pairs`
- coordinate_mode requested/effective: `ls_percent` / `ls_percent`
- W / H / CAM_H: `1024` / `512` / `1.6`
- Image source basename: `q9vSo1VnCiC_9c9fb1fccf4e46a597a9510a1938c8b4.jpg`
- Local image: `q9vSo1VnCiC_9c9fb1fccf4e46a597a9510a1938c8b4.jpg`
- Image exists: `True`
- Image SHA-256: `2c2f9794ddc2bcb70fc54ceb303614eba35a018b5693d89717e7e61e8241f220`
- Viewer URL: `/tools/label_studio/vis_3d.html`
- Image URL for viewer: `/data/mp3d_layout/img_v/q9vSo1VnCiC_9c9fb1fccf4e46a597a9510a1938c8b4.jpg`
- Texture expected: `True`
- Network access used: `False`

## Human Review Summary

This is an expert-side local visual review.
Candidate previews are diagnostic only.
No automatic fix is claimed.
Texture toggle and ghost are display controls only.
No annotation patch or Label Studio writeback is produced.

### robust_all_long_edges | segment_aware_manhattan_wall_line_refit | review

- decision_class: `None`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `None`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - source pair 2 (solver position 1): no numeric change
  - source pair 1 (solver position 2): no numeric change
  - source pair 3 (solver position 3): no numeric change
  - source pair 4 (solver position 4): no numeric change
  - source pair 6 (solver position 5): no numeric change
  - source pair 5 (solver position 6): no numeric change
  - source pair 8 (solver position 7): no numeric change
  - source pair 7 (solver position 8): no numeric change
  - source pair 9 (solver position 9): no numeric change
  - source pair 10 (solver position 10): no numeric change
  - source pair 12 (solver position 11): no numeric change
  - source pair 11 (solver position 12): no numeric change
- wall residual sum: 93.464 -> 41.470
- Preview only; this is not correctness evidence and cannot write back.

## Candidate Metric Summary

| variant | wall residual sum | corner residual sum | height residual sum | vertical x residual sum | min wall | self-intersection |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| original | 93.464 | 173.124 | 2.258 | 0.000 | 0.087 | False |
| robust_all_long_edges | 41.470 | 0.000 | 0.000 | 0.000 | 0.312 | False |

## Pair 3D Coordinates — original

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 2 | (-0.159, -1.600, 0.409) | (-0.159, 0.876, 0.409) | 2.476 | -0.594 | none |
| 2 | 1 | (-0.350, -1.600, 4.076) | (-0.350, 1.376, 4.076) | 2.976 | -0.095 | none |
| 3 | 3 | (-4.617, -1.600, 7.293) | (-4.617, 1.759, 7.293) | 3.359 | 0.289 | none |
| 4 | 4 | (-4.616, -1.600, -0.797) | (-4.616, 1.759, -0.797) | 3.359 | 0.288 | none |
| 5 | 6 | (-0.211, -1.600, -0.693) | (-0.211, 1.446, -0.693) | 3.046 | -0.024 | none |
| 6 | 5 | (-0.250, -1.600, -0.615) | (-0.250, 1.635, -0.615) | 3.235 | 0.165 | none |
| 7 | 8 | (0.067, -1.600, -0.636) | (0.067, 1.518, -0.636) | 3.118 | 0.048 | none |
| 8 | 7 | (0.052, -1.600, -1.420) | (0.052, 1.342, -1.420) | 2.942 | -0.128 | none |
| 9 | 9 | (1.897, -1.600, -1.565) | (1.897, 1.495, -1.565) | 3.095 | 0.024 | none |
| 10 | 10 | (1.919, -1.600, 1.215) | (1.919, 1.498, 1.215) | 3.098 | 0.028 | none |
| 11 | 12 | (0.072, -1.600, 1.145) | (0.072, 1.427, 1.145) | 3.027 | -0.044 | none |
| 12 | 11 | (0.046, -1.600, 0.450) | (0.046, 0.939, 0.450) | 2.539 | -0.531 | none |

## Wall Metrics — original

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 3.672 | 92.986 | 90.000 | 2.986 | False |
| 2 | 2-3 | 5.344 | 142.980 | 180.000 | 37.020 | False |
| 3 | 3-4 | 8.091 | 270.004 | 270.000 | 0.004 | False |
| 4 | 4-5 | 4.406 | 1.353 | 0.000 | 1.353 | False |
| 5 | 5-6 | 0.087 | 116.655 | 90.000 | 26.655 | True |
| 6 | 6-7 | 0.317 | 356.198 | 0.000 | 3.802 | True |
| 7 | 7-8 | 0.784 | 268.952 | 270.000 | 1.048 | False |
| 8 | 8-9 | 1.850 | 355.487 | 0.000 | 4.513 | False |
| 9 | 9-10 | 2.781 | 89.536 | 90.000 | 0.464 | False |
| 10 | 10-11 | 1.848 | 182.187 | 180.000 | 2.187 | False |
| 11 | 11-12 | 0.695 | 267.859 | 270.000 | 2.141 | False |
| 12 | 12-1 | 0.209 | 191.290 | 180.000 | 11.290 | True |

## Corner Metrics — original

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 12 | 1 | 81.696 | 8.304 | False |
| 2 | 1 | 2 | 130.006 | 40.006 | True |
| 3 | 2 | 3 | 52.976 | 37.024 | True |
| 4 | 3 | 4 | 88.650 | 1.350 | False |
| 5 | 4 | 5 | 64.698 | 25.302 | True |
| 6 | 5 | 6 | 59.542 | 30.458 | True |
| 7 | 6 | 7 | 92.755 | 2.755 | False |
| 8 | 7 | 8 | 93.465 | 3.465 | False |
| 9 | 8 | 9 | 85.951 | 4.049 | False |
| 10 | 9 | 10 | 87.349 | 2.651 | False |
| 11 | 10 | 11 | 94.329 | 4.329 | False |
| 12 | 11 | 12 | 103.431 | 13.431 | False |

## Pair 3D Coordinates — robust_all_long_edges

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 2 | (-0.508, -1.600, 0.476) | (-0.508, 1.759, 0.476) | 3.359 | 0.000 | none |
| 2 | 1 | (-0.141, -1.600, 6.556) | (-0.141, 1.759, 6.556) | 3.359 | -0.000 | none |
| 3 | 3 | (-4.401, -1.600, 6.813) | (-4.401, 1.759, 6.813) | 3.359 | 0.000 | none |
| 4 | 4 | (-4.857, -1.600, -0.741) | (-4.857, 1.759, -0.741) | 3.359 | 0.000 | none |
| 5 | 6 | (-0.252, -1.600, -1.020) | (-0.252, 1.759, -1.020) | 3.359 | -0.000 | none |
| 6 | 5 | (-0.228, -1.600, -0.618) | (-0.228, 1.759, -0.618) | 3.359 | 0.000 | none |
| 7 | 8 | (0.083, -1.600, -0.636) | (0.083, 1.759, -0.636) | 3.359 | -0.000 | none |
| 8 | 7 | (0.034, -1.600, -1.444) | (0.034, 1.759, -1.444) | 3.359 | 0.000 | none |
| 9 | 9 | (1.825, -1.600, -1.553) | (1.825, 1.759, -1.553) | 3.359 | -0.000 | none |
| 10 | 10 | (1.988, -1.600, 1.151) | (1.988, 1.759, 1.151) | 3.359 | 0.000 | none |
| 11 | 12 | (0.087, -1.600, 1.265) | (0.087, 1.759, 1.265) | 3.359 | -0.000 | none |
| 12 | 11 | (0.038, -1.600, 0.443) | (0.038, 1.759, 0.443) | 3.359 | -0.000 | none |

## Wall Metrics — robust_all_long_edges

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.091 | 86.544 | 90.000 | 3.456 | False |
| 2 | 2-3 | 4.268 | 176.544 | 180.000 | 3.456 | False |
| 3 | 3-4 | 7.568 | 266.544 | 270.000 | 3.456 | False |
| 4 | 4-5 | 4.613 | 356.544 | 0.000 | 3.456 | False |
| 5 | 5-6 | 0.403 | 86.544 | 90.000 | 3.456 | False |
| 6 | 6-7 | 0.312 | 356.544 | 0.000 | 3.456 | True |
| 7 | 7-8 | 0.809 | 266.544 | 270.000 | 3.456 | False |
| 8 | 8-9 | 1.794 | 356.544 | 0.000 | 3.456 | False |
| 9 | 9-10 | 2.708 | 86.544 | 90.000 | 3.456 | False |
| 10 | 10-11 | 1.904 | 176.544 | 180.000 | 3.456 | False |
| 11 | 11-12 | 0.824 | 266.544 | 270.000 | 3.456 | False |
| 12 | 12-1 | 0.547 | 176.544 | 180.000 | 3.456 | False |

## Corner Metrics — robust_all_long_edges

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 12 | 1 | 90.000 | 0.000 | False |
| 2 | 1 | 2 | 90.000 | 0.000 | False |
| 3 | 2 | 3 | 90.000 | 0.000 | False |
| 4 | 3 | 4 | 90.000 | 0.000 | False |
| 5 | 4 | 5 | 90.000 | 0.000 | False |
| 6 | 5 | 6 | 90.000 | 0.000 | False |
| 7 | 6 | 7 | 90.000 | 0.000 | False |
| 8 | 7 | 8 | 90.000 | 0.000 | False |
| 9 | 8 | 9 | 90.000 | 0.000 | False |
| 10 | 9 | 10 | 90.000 | 0.000 | False |
| 11 | 10 | 11 | 90.000 | 0.000 | False |
| 12 | 11 | 12 | 90.000 | 0.000 | False |

## Safety Boundary

This report is expert-side, offline, local-only, sidecar, and dry-run only. It does not edit annotations, optimize coordinates, reorder corners, score workers, or create formal experiment artifacts.
