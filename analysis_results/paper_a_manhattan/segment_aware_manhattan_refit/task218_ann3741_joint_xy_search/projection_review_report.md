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

### robust_all_long_edges | diagnostic_old_good_3d | diagnostic_only

- decision_class: `diagnostic_only`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `None`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - source pair 2 (solver position 1): top_x 5.890→13.025, top_y 14.787→12.002, bottom_x 5.890→13.025, bottom_y 91.479→86.932
  - source pair 1 (solver position 2): top_x 1.363→0.343, top_y 39.675→41.659, bottom_x 1.363→0.343, bottom_y 61.867→57.618
  - source pair 3 (solver position 3): top_x 8.981→9.128, top_y 43.602→43.203, bottom_x 8.981→9.128, bottom_y 55.834→56.199
  - source pair 4 (solver position 4): top_x 27.722→27.411, top_y 38.568→39.059, bottom_x 27.722→27.411, bottom_y 60.477→60.020
  - source pair 6 (solver position 5): top_x 45.299→46.137, top_y 14.787→17.137, bottom_x 45.299→46.137, bottom_y 86.466→81.509
  - source pair 5 (solver position 6): top_x 43.860→44.367, top_y 12.283→11.402, bottom_x 43.860→44.367, bottom_y 87.476→87.573
  - source pair 8 (solver position 7): top_x 51.660→52.067, top_y 12.695→11.138, bottom_x 51.660→52.067, bottom_y 87.891→87.857
  - source pair 7 (solver position 8): top_x 50.586→50.378, top_y 25.911→21.890, bottom_x 50.586→50.378, bottom_y 76.886→76.621
  - source pair 9 (solver position 9): top_x 64.019→63.781, top_y 32.617→29.844, bottom_x 64.019→63.781, bottom_y 68.359→68.741
  - source pair 10 (solver position 10): top_x 83.984→83.350, top_y 31.445→29.200, bottom_x 83.984→83.350, bottom_y 69.531→69.366
  - source pair 12 (solver position 11): top_x 98.997→98.901, top_y 21.556→19.888, bottom_x 98.997→98.901, bottom_y 80.201→78.664
  - source pair 11 (solver position 12): top_x 98.371→98.645, top_y 14.286→7.881, bottom_x 98.371→98.645, bottom_y 91.228→91.373
- wall residual sum: 93.464 -> 41.470
- Preview only; this is not correctness evidence and cannot write back.

### height_plane_preserved_s2_s11_s1_adapter | diagnostic_previous_height_plane | diagnostic_only

- decision_class: `diagnostic_only`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `None`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - source pair 2 (solver position 1): top_y 14.787→7.416, bottom_y 91.479→91.879
  - source pair 1 (solver position 2): top_x 1.363→0.343, top_y 39.675→41.985, bottom_x 1.363→0.343, bottom_y 61.867→57.318
  - source pair 3 (solver position 3): top_x 8.981→9.128, top_y 43.602→43.203, bottom_x 8.981→9.128, bottom_y 55.834→56.199
  - source pair 4 (solver position 4): top_x 27.722→27.411, top_y 38.568→39.059, bottom_x 27.722→27.411, bottom_y 60.477→60.020
  - source pair 6 (solver position 5): top_x 45.299→46.137, top_y 14.787→17.137, bottom_x 45.299→46.137, bottom_y 86.466→81.509
  - source pair 5 (solver position 6): top_x 43.860→44.367, top_y 12.283→11.402, bottom_x 43.860→44.367, bottom_y 87.476→87.573
  - source pair 8 (solver position 7): top_x 51.660→52.067, top_y 12.695→11.138, bottom_x 51.660→52.067, bottom_y 87.891→87.857
  - source pair 7 (solver position 8): top_x 50.586→50.378, top_y 25.911→21.890, bottom_x 50.586→50.378, bottom_y 76.886→76.621
  - source pair 9 (solver position 9): top_x 64.019→63.781, top_y 32.617→29.844, bottom_x 64.019→63.781, bottom_y 68.359→68.741
  - source pair 10 (solver position 10): top_x 83.984→83.350, top_y 31.445→29.200, bottom_x 83.984→83.350, bottom_y 69.531→69.366
  - source pair 12 (solver position 11): top_x 98.997→98.901, top_y 21.556→19.888, bottom_x 98.997→98.901, bottom_y 80.201→78.664
  - source pair 11 (solver position 12): top_y 14.286→7.830, bottom_y 91.228→91.428
- wall residual sum: 93.464 -> 45.277
- Preview only; this is not correctness evidence and cannot write back.

### balanced_joint_xy_best_effort | balanced_joint_xy_best_effort | manual_review_candidate

- decision_class: `manual_review_candidate`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `None`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - source pair 2 (solver position 1): top_y 14.787→14.187
  - source pair 1 (solver position 2): top_x 1.363→0.343, top_y 39.675→41.659, bottom_x 1.363→0.343, bottom_y 61.867→57.618
  - source pair 3 (solver position 3): top_x 8.981→9.128, top_y 43.602→43.203, bottom_x 8.981→9.128, bottom_y 55.834→56.199
  - source pair 4 (solver position 4): top_x 27.722→27.411, top_y 38.568→39.059, bottom_x 27.722→27.411, bottom_y 60.477→60.020
  - source pair 6 (solver position 5): top_x 45.299→46.137, top_y 14.787→17.137, bottom_x 45.299→46.137, bottom_y 86.466→81.509
  - source pair 5 (solver position 6): top_x 43.860→44.367, top_y 12.283→11.402, bottom_x 43.860→44.367, bottom_y 87.476→87.573
  - source pair 8 (solver position 7): top_x 51.660→52.067, top_y 12.695→11.138, bottom_x 51.660→52.067, bottom_y 87.891→87.857
  - source pair 7 (solver position 8): top_x 50.586→50.378, top_y 25.911→21.890, bottom_x 50.586→50.378, bottom_y 76.886→76.621
  - source pair 9 (solver position 9): top_x 64.019→63.781, top_y 32.617→31.617, bottom_x 64.019→63.781, bottom_y 68.359→68.741
  - source pair 10 (solver position 10): top_x 83.984→83.350, top_y 31.445→30.445, bottom_x 83.984→83.350, bottom_y 69.531→69.366
  - source pair 12 (solver position 11): top_x 98.997→98.901, top_y 21.556→20.556, bottom_x 98.997→98.901, bottom_y 80.201→78.664
  - source pair 11 (solver position 12): top_y 14.286→12.486, bottom_y 91.228→91.828
- wall residual sum: 93.464 -> 36.741
- Preview only; this is not correctness evidence and cannot write back.

## Candidate Metric Summary

| variant | wall residual sum | corner residual sum | height residual sum | vertical x residual sum | min wall | self-intersection |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| original | 93.464 | 173.124 | 2.258 | 0.000 | 0.087 | False |
| robust_all_long_edges | 41.470 | 0.000 | 0.000 | 0.000 | 0.312 | False |
| height_plane_preserved_s2_s11_s1_adapter | 45.277 | 36.301 | 0.000 | 0.000 | 0.202 | False |
| balanced_joint_xy_best_effort | 36.741 | 11.843 | 1.995 | 0.000 | 0.202 | False |

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

## Pair 3D Coordinates — robust_all_long_edges

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | None | (-0.508, -1.600, 0.476) | (-0.508, 1.759, 0.476) | 3.359 | 0.000 | none |
| 2 | None | (-0.141, -1.600, 6.556) | (-0.141, 1.759, 6.556) | 3.359 | -0.000 | none |
| 3 | None | (-4.401, -1.600, 6.813) | (-4.401, 1.759, 6.813) | 3.359 | 0.000 | none |
| 4 | None | (-4.857, -1.600, -0.741) | (-4.857, 1.759, -0.741) | 3.359 | 0.000 | none |
| 5 | None | (-0.252, -1.600, -1.020) | (-0.252, 1.759, -1.020) | 3.359 | -0.000 | none |
| 6 | None | (-0.228, -1.600, -0.618) | (-0.228, 1.759, -0.618) | 3.359 | 0.000 | none |
| 7 | None | (0.083, -1.600, -0.636) | (0.083, 1.759, -0.636) | 3.359 | -0.000 | none |
| 8 | None | (0.034, -1.600, -1.444) | (0.034, 1.759, -1.444) | 3.359 | 0.000 | none |
| 9 | None | (1.825, -1.600, -1.553) | (1.825, 1.759, -1.553) | 3.359 | -0.000 | none |
| 10 | None | (1.988, -1.600, 1.151) | (1.988, 1.759, 1.151) | 3.359 | 0.000 | none |
| 11 | None | (0.087, -1.600, 1.265) | (0.087, 1.759, 1.265) | 3.359 | -0.000 | none |
| 12 | None | (0.038, -1.600, 0.443) | (0.038, 1.759, 0.443) | 3.359 | -0.000 | none |

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

## Pair 3D Coordinates — height_plane_preserved_s2_s11_s1_adapter

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | None | (-0.151, -1.600, 0.389) | (-0.151, 1.759, 0.389) | 3.359 | -0.000 | none |
| 2 | None | (-0.147, -1.600, 6.835) | (-0.147, 1.759, 6.835) | 3.359 | -0.000 | none |
| 3 | None | (-4.401, -1.600, 6.813) | (-4.401, 1.759, 6.813) | 3.359 | 0.000 | none |
| 4 | None | (-4.857, -1.600, -0.741) | (-4.857, 1.759, -0.741) | 3.359 | 0.000 | none |
| 5 | None | (-0.252, -1.600, -1.020) | (-0.252, 1.759, -1.020) | 3.359 | 0.000 | none |
| 6 | None | (-0.228, -1.600, -0.618) | (-0.228, 1.759, -0.618) | 3.359 | 0.000 | none |
| 7 | None | (0.083, -1.600, -0.636) | (0.083, 1.759, -0.636) | 3.359 | -0.000 | none |
| 8 | None | (0.034, -1.600, -1.444) | (0.034, 1.759, -1.444) | 3.359 | 0.000 | none |
| 9 | None | (1.825, -1.600, -1.553) | (1.825, 1.759, -1.553) | 3.359 | 0.000 | none |
| 10 | None | (1.988, -1.600, 1.151) | (1.988, 1.759, 1.151) | 3.359 | 0.000 | none |
| 11 | None | (0.087, -1.600, 1.265) | (0.087, 1.759, 1.265) | 3.359 | -0.000 | none |
| 12 | None | (0.045, -1.600, 0.439) | (0.045, 1.759, 0.439) | 3.359 | 0.000 | none |

## Wall Metrics — height_plane_preserved_s2_s11_s1_adapter

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.446 | 89.968 | 90.000 | 0.032 | False |
| 2 | 2-3 | 4.254 | 180.294 | 180.000 | 0.294 | False |
| 3 | 3-4 | 7.568 | 266.544 | 270.000 | 3.456 | False |
| 4 | 4-5 | 4.613 | 356.544 | 0.000 | 3.456 | False |
| 5 | 5-6 | 0.403 | 86.544 | 90.000 | 3.456 | False |
| 6 | 6-7 | 0.312 | 356.544 | 0.000 | 3.456 | True |
| 7 | 7-8 | 0.809 | 266.544 | 270.000 | 3.456 | False |
| 8 | 8-9 | 1.794 | 356.544 | 0.000 | 3.456 | False |
| 9 | 9-10 | 2.708 | 86.544 | 90.000 | 3.456 | False |
| 10 | 10-11 | 1.904 | 176.544 | 180.000 | 3.456 | False |
| 11 | 11-12 | 0.827 | 267.065 | 270.000 | 2.935 | False |
| 12 | 12-1 | 0.202 | 194.368 | 180.000 | 14.368 | True |

## Corner Metrics — height_plane_preserved_s2_s11_s1_adapter

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 12 | 1 | 75.599 | 14.401 | False |
| 2 | 1 | 2 | 89.673 | 0.327 | False |
| 3 | 2 | 3 | 93.750 | 3.750 | False |
| 4 | 3 | 4 | 90.000 | 0.000 | False |
| 5 | 4 | 5 | 90.000 | 0.000 | False |
| 6 | 5 | 6 | 90.000 | 0.000 | False |
| 7 | 6 | 7 | 90.000 | 0.000 | False |
| 8 | 7 | 8 | 90.000 | 0.000 | False |
| 9 | 8 | 9 | 90.000 | 0.000 | False |
| 10 | 9 | 10 | 90.000 | 0.000 | False |
| 11 | 10 | 11 | 89.479 | 0.521 | False |
| 12 | 11 | 12 | 107.303 | 17.303 | True |

## Pair 3D Coordinates — balanced_joint_xy_best_effort

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | None | (-0.159, -1.600, 0.409) | (-0.159, 0.919, 0.409) | 2.519 | -0.840 | none |
| 2 | None | (-0.141, -1.600, 6.556) | (-0.141, 1.759, 6.556) | 3.359 | 0.000 | none |
| 3 | None | (-4.401, -1.600, 6.813) | (-4.401, 1.759, 6.813) | 3.359 | 0.000 | none |
| 4 | None | (-4.857, -1.600, -0.741) | (-4.857, 1.759, -0.741) | 3.359 | 0.000 | none |
| 5 | None | (-0.252, -1.600, -1.020) | (-0.252, 1.759, -1.020) | 3.359 | 0.000 | none |
| 6 | None | (-0.228, -1.600, -0.618) | (-0.228, 1.759, -0.618) | 3.359 | 0.000 | none |
| 7 | None | (0.083, -1.600, -0.636) | (0.083, 1.759, -0.636) | 3.359 | -0.000 | none |
| 8 | None | (0.034, -1.600, -1.444) | (0.034, 1.759, -1.444) | 3.359 | 0.000 | none |
| 9 | None | (1.825, -1.600, -1.553) | (1.825, 1.561, -1.553) | 3.161 | -0.197 | none |
| 10 | None | (1.988, -1.600, 1.151) | (1.988, 1.620, 1.151) | 3.220 | -0.138 | none |
| 11 | None | (0.087, -1.600, 1.265) | (0.087, 1.683, 1.265) | 3.283 | -0.076 | none |
| 12 | None | (0.043, -1.600, 0.418) | (0.043, 1.015, 0.418) | 2.615 | -0.743 | none |

## Wall Metrics — balanced_joint_xy_best_effort

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.147 | 89.837 | 90.000 | 0.163 | False |
| 2 | 2-3 | 4.268 | 176.544 | 180.000 | 3.456 | False |
| 3 | 3-4 | 7.568 | 266.544 | 270.000 | 3.456 | False |
| 4 | 4-5 | 4.613 | 356.544 | 0.000 | 3.456 | False |
| 5 | 5-6 | 0.403 | 86.544 | 90.000 | 3.456 | False |
| 6 | 6-7 | 0.312 | 356.544 | 0.000 | 3.456 | True |
| 7 | 7-8 | 0.809 | 266.544 | 270.000 | 3.456 | False |
| 8 | 8-9 | 1.794 | 356.544 | 0.000 | 3.456 | False |
| 9 | 9-10 | 2.708 | 86.544 | 90.000 | 3.456 | False |
| 10 | 10-11 | 1.904 | 176.544 | 180.000 | 3.456 | False |
| 11 | 11-12 | 0.849 | 266.991 | 270.000 | 3.009 | False |
| 12 | 12-1 | 0.202 | 182.466 | 180.000 | 2.466 | True |

## Corner Metrics — balanced_joint_xy_best_effort

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 12 | 1 | 87.371 | 2.629 | False |
| 2 | 1 | 2 | 93.293 | 3.293 | False |
| 3 | 2 | 3 | 90.000 | 0.000 | False |
| 4 | 3 | 4 | 90.000 | 0.000 | False |
| 5 | 4 | 5 | 90.000 | 0.000 | False |
| 6 | 5 | 6 | 90.000 | 0.000 | False |
| 7 | 6 | 7 | 90.000 | 0.000 | False |
| 8 | 7 | 8 | 90.000 | 0.000 | False |
| 9 | 8 | 9 | 90.000 | 0.000 | False |
| 10 | 9 | 10 | 90.000 | 0.000 | False |
| 11 | 10 | 11 | 89.554 | 0.446 | False |
| 12 | 11 | 12 | 95.475 | 5.475 | False |

## Safety Boundary

This report is expert-side, offline, local-only, sidecar, and dry-run only. It does not edit annotations, optimize coordinates, reorder corners, score workers, or create formal experiment artifacts.
