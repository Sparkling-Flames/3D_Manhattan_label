# Local 3D Projection Review

## Input Provenance

- Review schema: `local_3d_projection_review_m15_27_1_bridge_v1`
- Projection schema: `local_3d_projection_m15_19_v1`
- Input file: `_review_input.json`
- Input SHA-256: `8e888a8ea174f9fa37b6dfa548b734baa211b3f0f6c527d19f66b7a9cd254b4d`
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

### pair2_anchored_height_clamped | rejected_9_3_diagnostic_reference | diagnostic_only

- decision_class: `diagnostic_only`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `None`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - source pair 2 (solver position 1): top_x 5.890→7.174, top_y 14.787→14.286, bottom_x 5.890→7.174, bottom_y 91.479→90.660
  - source pair 1 (solver position 2): top_x 1.363→0.343, top_y 39.675→41.659, bottom_x 1.363→0.343, bottom_y 61.867→57.618
  - source pair 3 (solver position 3): top_x 8.981→9.128, top_y 43.602→43.203, bottom_x 8.981→9.128, bottom_y 55.834→56.199
  - source pair 4 (solver position 4): top_x 27.722→27.411, top_y 38.568→39.059, bottom_x 27.722→27.411, bottom_y 60.477→60.020
  - source pair 6 (solver position 5): top_x 45.299→46.137, top_y 14.787→17.137, bottom_x 45.299→46.137, bottom_y 86.466→81.509
  - source pair 5 (solver position 6): top_x 43.860→44.367, top_y 12.283→11.402, bottom_x 43.860→44.367, bottom_y 87.476→87.573
  - source pair 8 (solver position 7): top_x 51.660→52.067, top_y 12.695→11.138, bottom_x 51.660→52.067, bottom_y 87.891→87.857
  - source pair 7 (solver position 8): top_x 50.586→50.378, top_y 25.911→23.911, bottom_x 50.586→50.378, bottom_y 76.886→76.621
  - source pair 9 (solver position 9): top_x 64.019→63.781, top_y 32.617→31.417, bottom_x 64.019→63.781, bottom_y 68.359→68.741
  - source pair 10 (solver position 10): top_x 83.984→83.350, top_y 31.445→30.245, bottom_x 83.984→83.350, bottom_y 69.531→69.366
  - source pair 12 (solver position 11): top_x 98.997→98.901, top_y 21.556→20.056, bottom_x 98.997→98.901, bottom_y 80.201→78.664
  - source pair 11 (solver position 12): top_x 98.371→98.645, top_y 14.286→12.786, bottom_x 98.371→98.645, bottom_y 91.228→91.373
- wall residual sum: 93.464 -> 37.013
- Preview only; this is not correctness evidence and cannot write back.

### s2_s11_height_pair_repair | baseline_x_anchored_y_targeted_refit | manual_review_candidate

- decision_class: `manual_review_candidate`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `None`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - source pair 2 (solver position 1): top_y 14.787→11.787, bottom_y 91.479→92.279
  - source pair 1 (solver position 2): top_x 1.363→0.343, top_y 39.675→41.659, bottom_x 1.363→0.343, bottom_y 61.867→57.618
  - source pair 3 (solver position 3): top_x 8.981→9.128, top_y 43.602→43.203, bottom_x 8.981→9.128, bottom_y 55.834→56.199
  - source pair 4 (solver position 4): top_x 27.722→27.411, top_y 38.568→39.059, bottom_x 27.722→27.411, bottom_y 60.477→60.020
  - source pair 6 (solver position 5): top_y 14.787→17.137, bottom_y 86.466→81.509
  - source pair 5 (solver position 6): top_y 12.283→11.402, bottom_y 87.476→87.573
  - source pair 8 (solver position 7): top_x 51.660→52.067, top_y 12.695→11.138, bottom_x 51.660→52.067, bottom_y 87.891→87.857
  - source pair 7 (solver position 8): top_x 50.586→50.378, top_y 25.911→23.911, bottom_x 50.586→50.378, bottom_y 76.886→76.621
  - source pair 9 (solver position 9): top_x 64.019→63.781, top_y 32.617→31.417, bottom_x 64.019→63.781, bottom_y 68.359→68.741
  - source pair 10 (solver position 10): top_x 83.984→83.350, top_y 31.445→30.245, bottom_x 83.984→83.350, bottom_y 69.531→69.366
  - source pair 12 (solver position 11): top_x 98.997→98.901, top_y 21.556→20.056, bottom_x 98.997→98.901, bottom_y 80.201→78.664
  - source pair 11 (solver position 12): top_y 14.286→11.286
- wall residual sum: 93.464 -> 63.018
- Preview only; this is not correctness evidence and cannot write back.

## Candidate Metric Summary

| variant | wall residual sum | corner residual sum | height residual sum | vertical x residual sum | min wall | self-intersection |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| original | 93.464 | 173.124 | 2.258 | 0.000 | 0.087 | False |
| pair2_anchored_height_clamped | 37.013 | 10.523 | 1.991 | 0.000 | 0.249 | False |
| s2_s11_height_pair_repair | 63.018 | 63.282 | 1.799 | 0.000 | 0.206 | False |

## Pair 3D Coordinates — original

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | None | (-0.159, -1.600, 0.409) | (-0.159, 0.876, 0.409) | 2.476 | -0.594 | none |
| 2 | None | (-0.350, -1.600, 4.076) | (-0.350, 1.376, 4.076) | 2.976 | -0.095 | none |
| 3 | None | (-4.617, -1.600, 7.293) | (-4.617, 1.759, 7.293) | 3.359 | 0.289 | none |
| 4 | None | (-4.616, -1.600, -0.797) | (-4.616, 1.759, -0.797) | 3.359 | 0.288 | none |
| 5 | None | (-0.211, -1.600, -0.693) | (-0.211, 1.446, -0.693) | 3.046 | -0.024 | none |
| 6 | None | (-0.250, -1.600, -0.615) | (-0.250, 1.635, -0.615) | 3.235 | 0.165 | none |
| 7 | None | (0.067, -1.600, -0.636) | (0.067, 1.518, -0.636) | 3.118 | 0.048 | none |
| 8 | None | (0.052, -1.600, -1.420) | (0.052, 1.342, -1.420) | 2.942 | -0.128 | none |
| 9 | None | (1.897, -1.600, -1.565) | (1.897, 1.495, -1.565) | 3.095 | 0.024 | none |
| 10 | None | (1.919, -1.600, 1.215) | (1.919, 1.498, 1.215) | 3.098 | 0.028 | none |
| 11 | None | (0.072, -1.600, 1.145) | (0.072, 1.427, 1.145) | 3.027 | -0.044 | none |
| 12 | None | (0.046, -1.600, 0.450) | (0.046, 0.939, 0.450) | 2.539 | -0.531 | none |

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

## Pair 3D Coordinates — pair2_anchored_height_clamped

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | None | (-0.211, -1.600, 0.435) | (-0.211, 1.004, 0.435) | 2.604 | -0.745 | none |
| 2 | None | (-0.141, -1.600, 6.556) | (-0.141, 1.759, 6.556) | 3.359 | 0.010 | none |
| 3 | None | (-4.401, -1.600, 6.813) | (-4.401, 1.759, 6.813) | 3.359 | 0.010 | none |
| 4 | None | (-4.857, -1.600, -0.741) | (-4.857, 1.759, -0.741) | 3.359 | 0.010 | none |
| 5 | None | (-0.252, -1.600, -1.020) | (-0.252, 1.759, -1.020) | 3.359 | 0.010 | none |
| 6 | None | (-0.228, -1.600, -0.618) | (-0.228, 1.759, -0.618) | 3.359 | 0.010 | none |
| 7 | None | (0.083, -1.600, -0.636) | (0.083, 1.759, -0.636) | 3.359 | 0.010 | none |
| 8 | None | (0.034, -1.600, -1.444) | (0.034, 1.547, -1.444) | 3.147 | -0.202 | none |
| 9 | None | (1.825, -1.600, -1.553) | (1.825, 1.583, -1.553) | 3.183 | -0.166 | none |
| 10 | None | (1.988, -1.600, 1.151) | (1.988, 1.642, 1.151) | 3.242 | -0.107 | none |
| 11 | None | (0.087, -1.600, 1.265) | (0.087, 1.739, 1.265) | 3.339 | -0.010 | none |
| 12 | None | (0.038, -1.600, 0.443) | (0.038, 1.047, 0.443) | 2.647 | -0.702 | none |

## Wall Metrics — pair2_anchored_height_clamped

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.121 | 89.351 | 90.000 | 0.649 | False |
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
| 12 | 12-1 | 0.249 | 181.806 | 180.000 | 1.806 | True |

## Corner Metrics — pair2_anchored_height_clamped

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 12 | 1 | 87.545 | 2.455 | False |
| 2 | 1 | 2 | 92.807 | 2.807 | False |
| 3 | 2 | 3 | 90.000 | 0.000 | False |
| 4 | 3 | 4 | 90.000 | 0.000 | False |
| 5 | 4 | 5 | 90.000 | 0.000 | False |
| 6 | 5 | 6 | 90.000 | 0.000 | False |
| 7 | 6 | 7 | 90.000 | 0.000 | False |
| 8 | 7 | 8 | 90.000 | 0.000 | False |
| 9 | 8 | 9 | 90.000 | 0.000 | False |
| 10 | 9 | 10 | 90.000 | 0.000 | False |
| 11 | 10 | 11 | 90.000 | 0.000 | False |
| 12 | 11 | 12 | 95.262 | 5.262 | False |

## Pair 3D Coordinates — s2_s11_height_pair_repair

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | None | (-0.143, -1.600, 0.369) | (-0.143, 1.020, 0.369) | 2.620 | -0.729 | none |
| 2 | None | (-0.141, -1.600, 6.556) | (-0.141, 1.759, 6.556) | 3.359 | 0.010 | none |
| 3 | None | (-4.401, -1.600, 6.813) | (-4.401, 1.759, 6.813) | 3.359 | 0.010 | none |
| 4 | None | (-4.857, -1.600, -0.741) | (-4.857, 1.759, -0.741) | 3.359 | 0.010 | none |
| 5 | None | (-0.306, -1.600, -1.005) | (-0.306, 1.759, -1.005) | 3.359 | 0.010 | none |
| 6 | None | (-0.248, -1.600, -0.610) | (-0.248, 1.759, -0.610) | 3.359 | 0.010 | none |
| 7 | None | (0.083, -1.600, -0.636) | (0.083, 1.759, -0.636) | 3.359 | 0.010 | none |
| 8 | None | (0.034, -1.600, -1.444) | (0.034, 1.547, -1.444) | 3.147 | -0.202 | none |
| 9 | None | (1.825, -1.600, -1.553) | (1.825, 1.583, -1.553) | 3.183 | -0.166 | none |
| 10 | None | (1.988, -1.600, 1.151) | (1.988, 1.642, 1.151) | 3.242 | -0.107 | none |
| 11 | None | (0.087, -1.600, 1.265) | (0.087, 1.739, 1.265) | 3.339 | -0.010 | none |
| 12 | None | (0.046, -1.600, 0.450) | (0.046, 1.222, 0.450) | 2.822 | -0.527 | none |

## Wall Metrics — s2_s11_height_pair_repair

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.187 | 89.982 | 90.000 | 0.018 | False |
| 2 | 2-3 | 4.268 | 176.544 | 180.000 | 3.456 | False |
| 3 | 3-4 | 7.568 | 266.544 | 270.000 | 3.456 | False |
| 4 | 4-5 | 4.559 | 356.688 | 0.000 | 3.312 | False |
| 5 | 5-6 | 0.399 | 81.645 | 90.000 | 8.355 | False |
| 6 | 6-7 | 0.332 | 355.440 | 0.000 | 4.560 | True |
| 7 | 7-8 | 0.809 | 266.544 | 270.000 | 3.456 | False |
| 8 | 8-9 | 1.794 | 356.544 | 0.000 | 3.456 | False |
| 9 | 9-10 | 2.708 | 86.544 | 90.000 | 3.456 | False |
| 10 | 10-11 | 1.904 | 176.544 | 180.000 | 3.456 | False |
| 11 | 11-12 | 0.816 | 267.104 | 270.000 | 2.896 | False |
| 12 | 12-1 | 0.206 | 203.142 | 180.000 | 23.142 | True |

## Corner Metrics — s2_s11_height_pair_repair

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 12 | 1 | 66.840 | 23.160 | True |
| 2 | 1 | 2 | 93.438 | 3.438 | False |
| 3 | 2 | 3 | 90.000 | 0.000 | False |
| 4 | 3 | 4 | 89.856 | 0.144 | False |
| 5 | 4 | 5 | 95.043 | 5.043 | False |
| 6 | 5 | 6 | 93.795 | 3.795 | False |
| 7 | 6 | 7 | 91.104 | 1.104 | False |
| 8 | 7 | 8 | 90.000 | 0.000 | False |
| 9 | 8 | 9 | 90.000 | 0.000 | False |
| 10 | 9 | 10 | 90.000 | 0.000 | False |
| 11 | 10 | 11 | 89.440 | 0.560 | False |
| 12 | 11 | 12 | 116.038 | 26.038 | True |

## Safety Boundary

This report is expert-side, offline, local-only, sidecar, and dry-run only. It does not edit annotations, optimize coordinates, reorder corners, score workers, or create formal experiment artifacts.
