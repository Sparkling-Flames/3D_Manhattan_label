# Local 3D Projection Review

## Input Provenance

- Review schema: `local_3d_projection_review_m15_23_v1`
- Projection schema: `local_3d_projection_m15_19_v1`
- Input file: `task218_ann3741_m1516_stabilized_input.json`
- Input SHA-256: `a0646242b9e0f07a29282906e20c6c67a7bcc05cd704d6b7db209957576eaef7`
- Ordered-pair source: `build_single_image_assist.ordered_pairs`
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

Local-only diagnostic. No annotation changes are produced.

### candidate_1 | height_aware_y_probe | partial | 6-7 35.368→26.315

- decision_class: `partial_diagnostic`
- improves: `['6-7 residual improves 35.368 -> 26.315', '7-8 residual improves 1.048 -> 0.568']`
- fails_because: `['6-7 remains unresolved: 35.368 -> 26.315', 'allowed existing short-wall risk remains at 5-6; allowance is not a correctness claim', 'dynamic short-wall risk remains at 6-7', 'dynamic short-wall risk worsens']`
- direct_ls_trial_allowed: `False`
- primary_unresolved_edges: `['6-7']`
- short_wall_edges_after: `['5-6', '6-7']`
- Applied coordinate changes:
  - pair 7: top_y 12.695→11.695, bottom_y 87.891→88.891
- wall residual sum: 115.116 -> 105.583
- Preview only; this is not correctness evidence and cannot write back.

### candidate_2 | joint_5_6_7_dense_footprint | partial | 6-7 35.368→25.403

- decision_class: `partial_diagnostic`
- improves: `['6-7 residual improves 35.368 -> 25.403', '4-5 residual improves 1.451 -> 1.108', '7-8 residual improves 1.048 -> 0.999', 'local height residual improves']`
- fails_because: `['6-7 remains unresolved: 35.368 -> 25.403', 'allowed existing short-wall risk remains at 5-6; allowance is not a correctness claim', 'dynamic short-wall risk remains at 6-7', 'dynamic short-wall risk worsens']`
- direct_ls_trial_allowed: `False`
- primary_unresolved_edges: `['6-7']`
- short_wall_edges_after: `['5-6', '6-7']`
- Applied coordinate changes:
  - pair 5: top_x 44.612→44.462, top_y 14.787→14.287, bottom_x 44.987→44.837, bottom_y 86.466→85.966
  - pair 6: top_x 43.860→44.010, top_y 12.283→11.783, bottom_x 43.860→44.010, bottom_y 90.476→89.976
  - pair 7: top_x 51.660→51.735, top_y 12.695→13.195, bottom_x 51.660→51.735, bottom_y 87.891→88.391
- wall residual sum: 115.116 -> 107.351
- Preview only; this is not correctness evidence and cannot write back.

### candidate_3 | height_aware_y_probe | partial | 6-7 35.368→31.083

- decision_class: `partial_diagnostic`
- improves: `['6-7 residual improves 35.368 -> 31.083', '7-8 residual improves 1.048 -> 0.798', 'local height residual improves']`
- fails_because: `['6-7 remains unresolved: 35.368 -> 31.083', 'allowed existing short-wall risk remains at 5-6; allowance is not a correctness claim', 'dynamic short-wall risk remains at 6-7', 'dynamic short-wall risk worsens']`
- direct_ls_trial_allowed: `False`
- primary_unresolved_edges: `['6-7']`
- short_wall_edges_after: `['5-6', '6-7']`
- Applied coordinate changes:
  - pair 7: top_y 12.695→13.195, bottom_y 87.891→88.391
- wall residual sum: 115.116 -> 110.582
- Preview only; this is not correctness evidence and cannot write back.

### candidate_4 | height_aware_y_probe | partial | 6-7 35.368→31.083

- decision_class: `partial_diagnostic`
- improves: `['6-7 residual improves 35.368 -> 31.083', '7-8 residual improves 1.048 -> 0.798']`
- fails_because: `['6-7 remains unresolved: 35.368 -> 31.083', 'allowed existing short-wall risk remains at 5-6; allowance is not a correctness claim', 'dynamic short-wall risk remains at 6-7', 'dynamic short-wall risk worsens']`
- direct_ls_trial_allowed: `False`
- primary_unresolved_edges: `['6-7']`
- short_wall_edges_after: `['5-6', '6-7']`
- Applied coordinate changes:
  - pair 7: top_y 12.695→12.195, bottom_y 87.891→88.391
- wall residual sum: 115.116 -> 110.582
- Preview only; this is not correctness evidence and cannot write back.

### candidate_5 | column_x_align_translate | partial | 6-7 35.368→35.368

- decision_class: `partial_diagnostic`
- improves: `['5-6 residual improves 11.560 -> 6.086', '4-5 residual improves 1.451 -> 1.353']`
- fails_because: `['6-7 remains unresolved: 35.368 -> 35.368', 'allowed existing short-wall risk remains at 5-6; allowance is not a correctness claim', 'dynamic short-wall risk remains at 6-7']`
- direct_ls_trial_allowed: `False`
- primary_unresolved_edges: `['6-7']`
- short_wall_edges_after: `['5-6', '6-7']`
- Applied coordinate changes:
  - pair 5: top_x 44.612→45.299, bottom_x 44.987→45.299
- wall residual sum: 115.116 -> 109.545
- Preview only; this is not correctness evidence and cannot write back.

## Candidate Metric Summary

| variant | wall residual sum | corner residual sum | height residual sum | vertical x residual sum | min wall | self-intersection |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| original | 115.116 | 196.339 | 2.521 | 0.936 | 0.234 | False |
| candidate_1 | 105.583 | 179.193 | 2.515 | 0.936 | 0.234 | False |
| candidate_2 | 107.351 | 175.820 | 2.499 | 0.936 | 0.235 | False |
| candidate_3 | 110.582 | 188.269 | 2.506 | 0.936 | 0.234 | False |
| candidate_4 | 110.582 | 188.269 | 2.518 | 0.936 | 0.234 | False |
| candidate_5 | 109.545 | 196.143 | 2.521 | 0.560 | 0.237 | False |

## Pair 3D Coordinates — original

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 2 | (-0.170, -1.600, 0.419) | (-0.170, 0.815, 0.419) | 2.415 | -0.656 | none |
| 2 | 1 | (-0.350, -1.600, 4.076) | (-0.350, 0.691, 4.076) | 2.291 | -0.779 | none |
| 3 | 3 | (-4.617, -1.600, 7.293) | (-4.617, 1.759, 7.293) | 3.359 | 0.289 | none |
| 4 | 4 | (-4.616, -1.600, -0.797) | (-4.616, 1.759, -0.797) | 3.359 | 0.288 | none |
| 5 | 6 | (-0.233, -1.600, -0.686) | (-0.233, 1.446, -0.686) | 3.046 | -0.024 | none |
| 6 | 5 | (-0.186, -1.600, -0.457) | (-0.186, 1.215, -0.457) | 2.815 | -0.255 | none |
| 7 | 8 | (0.067, -1.600, -0.636) | (0.067, 1.518, -0.636) | 3.118 | 0.048 | none |
| 8 | 7 | (0.052, -1.600, -1.420) | (0.052, 1.342, -1.420) | 2.942 | -0.128 | none |
| 9 | 9 | (1.897, -1.600, -1.565) | (1.897, 1.495, -1.565) | 3.095 | 0.024 | none |
| 10 | 10 | (1.919, -1.600, 1.215) | (1.919, 1.498, 1.215) | 3.098 | 0.028 | none |

## Wall Metrics — original

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 3.661 | 92.823 | 90.000 | 2.823 | False |
| 2 | 2-3 | 5.344 | 142.980 | 180.000 | 37.020 | False |
| 3 | 3-4 | 8.091 | 270.004 | 270.000 | 0.004 | False |
| 4 | 4-5 | 4.385 | 1.451 | 0.000 | 1.451 | False |
| 5 | 5-6 | 0.234 | 78.440 | 90.000 | 11.560 | True |
| 6 | 6-7 | 0.309 | 324.632 | 0.000 | 35.368 | True |
| 7 | 7-8 | 0.784 | 268.952 | 270.000 | 1.048 | False |
| 8 | 8-9 | 1.850 | 355.486 | 0.000 | 4.514 | False |
| 9 | 9-10 | 2.781 | 89.535 | 90.000 | 0.465 | False |
| 10 | 10-1 | 2.236 | 200.863 | 180.000 | 20.863 | False |

## Corner Metrics — original

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 10 | 1 | 71.960 | 18.040 | True |
| 2 | 1 | 2 | 129.844 | 39.844 | True |
| 3 | 2 | 3 | 52.976 | 37.024 | True |
| 4 | 3 | 4 | 88.553 | 1.447 | False |
| 5 | 4 | 5 | 103.011 | 13.011 | False |
| 6 | 5 | 6 | 66.192 | 23.808 | True |
| 7 | 6 | 7 | 124.320 | 34.320 | True |
| 8 | 7 | 8 | 93.467 | 3.467 | False |
| 9 | 8 | 9 | 85.950 | 4.050 | False |
| 10 | 9 | 10 | 68.672 | 21.328 | True |

## Pair 3D Coordinates — candidate_1

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 2 | (-0.170, -1.600, 0.419) | (-0.170, 0.815, 0.419) | 2.415 | -0.656 | none |
| 2 | 1 | (-0.350, -1.600, 4.076) | (-0.350, 0.691, 4.076) | 2.291 | -0.779 | none |
| 3 | 3 | (-4.617, -1.600, 7.293) | (-4.617, 1.759, 7.293) | 3.359 | 0.289 | none |
| 4 | 4 | (-4.616, -1.600, -0.797) | (-4.616, 1.759, -0.797) | 3.359 | 0.288 | none |
| 5 | 6 | (-0.233, -1.600, -0.686) | (-0.233, 1.446, -0.686) | 3.046 | -0.024 | none |
| 6 | 5 | (-0.186, -1.600, -0.457) | (-0.186, 1.215, -0.457) | 2.815 | -0.255 | none |
| 7 | 8 | (0.061, -1.600, -0.579) | (0.061, 1.513, -0.579) | 3.113 | 0.043 | none |
| 8 | 7 | (0.052, -1.600, -1.420) | (0.052, 1.342, -1.420) | 2.942 | -0.128 | none |
| 9 | 9 | (1.897, -1.600, -1.565) | (1.897, 1.495, -1.565) | 3.095 | 0.024 | none |
| 10 | 10 | (1.919, -1.600, 1.215) | (1.919, 1.498, 1.215) | 3.098 | 0.028 | none |

## Wall Metrics — candidate_1

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 3.661 | 92.823 | 90.000 | 2.823 | False |
| 2 | 2-3 | 5.344 | 142.980 | 180.000 | 37.020 | False |
| 3 | 3-4 | 8.091 | 270.004 | 270.000 | 0.004 | False |
| 4 | 4-5 | 4.385 | 1.451 | 0.000 | 1.451 | False |
| 5 | 5-6 | 0.234 | 78.440 | 90.000 | 11.560 | True |
| 6 | 6-7 | 0.275 | 333.685 | 0.000 | 26.315 | True |
| 7 | 7-8 | 0.841 | 269.432 | 270.000 | 0.568 | False |
| 8 | 8-9 | 1.850 | 355.486 | 0.000 | 4.514 | False |
| 9 | 9-10 | 2.781 | 89.535 | 90.000 | 0.465 | False |
| 10 | 10-1 | 2.236 | 200.863 | 180.000 | 20.863 | False |

## Corner Metrics — candidate_1

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 10 | 1 | 71.960 | 18.040 | True |
| 2 | 1 | 2 | 129.844 | 39.844 | True |
| 3 | 2 | 3 | 52.976 | 37.024 | True |
| 4 | 3 | 4 | 88.553 | 1.447 | False |
| 5 | 4 | 5 | 103.011 | 13.011 | False |
| 6 | 5 | 6 | 75.245 | 14.755 | False |
| 7 | 6 | 7 | 115.747 | 25.747 | True |
| 8 | 7 | 8 | 93.947 | 3.947 | False |
| 9 | 8 | 9 | 85.950 | 4.050 | False |
| 10 | 9 | 10 | 68.672 | 21.328 | True |

## Pair 3D Coordinates — candidate_2

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 2 | (-0.170, -1.600, 0.419) | (-0.170, 0.815, 0.419) | 2.415 | -0.627 | none |
| 2 | 1 | (-0.350, -1.600, 4.076) | (-0.350, 0.691, 4.076) | 2.291 | -0.751 | none |
| 3 | 3 | (-4.617, -1.600, 7.293) | (-4.617, 1.759, 7.293) | 3.359 | 0.317 | none |
| 4 | 4 | (-4.616, -1.600, -0.797) | (-4.616, 1.759, -0.797) | 3.359 | 0.317 | none |
| 5 | 6 | (-0.249, -1.600, -0.713) | (-0.249, 1.568, -0.713) | 3.168 | 0.126 | none |
| 6 | 5 | (-0.192, -1.600, -0.485) | (-0.192, 1.343, -0.485) | 2.943 | -0.098 | none |
| 7 | 8 | (0.066, -1.600, -0.607) | (0.066, 1.388, -0.607) | 2.988 | -0.053 | none |
| 8 | 7 | (0.052, -1.600, -1.420) | (0.052, 1.342, -1.420) | 2.942 | -0.100 | none |
| 9 | 9 | (1.897, -1.600, -1.565) | (1.897, 1.495, -1.565) | 3.095 | 0.053 | none |
| 10 | 10 | (1.919, -1.600, 1.215) | (1.919, 1.498, 1.215) | 3.098 | 0.056 | none |

## Wall Metrics — candidate_2

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 3.661 | 92.823 | 90.000 | 2.823 | False |
| 2 | 2-3 | 5.344 | 142.980 | 180.000 | 37.020 | False |
| 3 | 3-4 | 8.091 | 270.004 | 270.000 | 0.004 | False |
| 4 | 4-5 | 4.368 | 1.108 | 0.000 | 1.108 | False |
| 5 | 5-6 | 0.235 | 75.849 | 90.000 | 14.151 | True |
| 6 | 6-7 | 0.286 | 334.597 | 0.000 | 25.403 | True |
| 7 | 7-8 | 0.813 | 269.001 | 270.000 | 0.999 | False |
| 8 | 8-9 | 1.850 | 355.486 | 0.000 | 4.514 | False |
| 9 | 9-10 | 2.781 | 89.535 | 90.000 | 0.465 | False |
| 10 | 10-1 | 2.236 | 200.863 | 180.000 | 20.863 | False |

## Corner Metrics — candidate_2

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 10 | 1 | 71.960 | 18.040 | True |
| 2 | 1 | 2 | 129.844 | 39.844 | True |
| 3 | 2 | 3 | 52.976 | 37.024 | True |
| 4 | 3 | 4 | 88.896 | 1.104 | False |
| 5 | 4 | 5 | 105.259 | 15.259 | True |
| 6 | 5 | 6 | 78.748 | 11.252 | False |
| 7 | 6 | 7 | 114.404 | 24.404 | True |
| 8 | 7 | 8 | 93.515 | 3.515 | False |
| 9 | 8 | 9 | 85.950 | 4.050 | False |
| 10 | 9 | 10 | 68.672 | 21.328 | True |

## Pair 3D Coordinates — candidate_3

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 2 | (-0.170, -1.600, 0.419) | (-0.170, 0.815, 0.419) | 2.415 | -0.602 | none |
| 2 | 1 | (-0.350, -1.600, 4.076) | (-0.350, 0.691, 4.076) | 2.291 | -0.726 | none |
| 3 | 3 | (-4.617, -1.600, 7.293) | (-4.617, 1.759, 7.293) | 3.359 | 0.342 | none |
| 4 | 4 | (-4.616, -1.600, -0.797) | (-4.616, 1.759, -0.797) | 3.359 | 0.342 | none |
| 5 | 6 | (-0.233, -1.600, -0.686) | (-0.233, 1.446, -0.686) | 3.046 | 0.029 | none |
| 6 | 5 | (-0.186, -1.600, -0.457) | (-0.186, 1.215, -0.457) | 2.815 | -0.202 | none |
| 7 | 8 | (0.064, -1.600, -0.608) | (0.064, 1.388, -0.608) | 2.988 | -0.029 | none |
| 8 | 7 | (0.052, -1.600, -1.420) | (0.052, 1.342, -1.420) | 2.942 | -0.075 | none |
| 9 | 9 | (1.897, -1.600, -1.565) | (1.897, 1.495, -1.565) | 3.095 | 0.078 | none |
| 10 | 10 | (1.919, -1.600, 1.215) | (1.919, 1.498, 1.215) | 3.098 | 0.081 | none |

## Wall Metrics — candidate_3

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 3.661 | 92.823 | 90.000 | 2.823 | False |
| 2 | 2-3 | 5.344 | 142.980 | 180.000 | 37.020 | False |
| 3 | 3-4 | 8.091 | 270.004 | 270.000 | 0.004 | False |
| 4 | 4-5 | 4.385 | 1.451 | 0.000 | 1.451 | False |
| 5 | 5-6 | 0.234 | 78.440 | 90.000 | 11.560 | True |
| 6 | 6-7 | 0.291 | 328.917 | 0.000 | 31.083 | True |
| 7 | 7-8 | 0.812 | 269.202 | 270.000 | 0.798 | False |
| 8 | 8-9 | 1.850 | 355.486 | 0.000 | 4.514 | False |
| 9 | 9-10 | 2.781 | 89.535 | 90.000 | 0.465 | False |
| 10 | 10-1 | 2.236 | 200.863 | 180.000 | 20.863 | False |

## Corner Metrics — candidate_3

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 10 | 1 | 71.960 | 18.040 | True |
| 2 | 1 | 2 | 129.844 | 39.844 | True |
| 3 | 2 | 3 | 52.976 | 37.024 | True |
| 4 | 3 | 4 | 88.553 | 1.447 | False |
| 5 | 4 | 5 | 103.011 | 13.011 | False |
| 6 | 5 | 6 | 70.477 | 19.523 | True |
| 7 | 6 | 7 | 120.285 | 30.285 | True |
| 8 | 7 | 8 | 93.717 | 3.717 | False |
| 9 | 8 | 9 | 85.950 | 4.050 | False |
| 10 | 9 | 10 | 68.672 | 21.328 | True |

## Pair 3D Coordinates — candidate_4

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 2 | (-0.170, -1.600, 0.419) | (-0.170, 0.815, 0.419) | 2.415 | -0.656 | none |
| 2 | 1 | (-0.350, -1.600, 4.076) | (-0.350, 0.691, 4.076) | 2.291 | -0.779 | none |
| 3 | 3 | (-4.617, -1.600, 7.293) | (-4.617, 1.759, 7.293) | 3.359 | 0.289 | none |
| 4 | 4 | (-4.616, -1.600, -0.797) | (-4.616, 1.759, -0.797) | 3.359 | 0.288 | none |
| 5 | 6 | (-0.233, -1.600, -0.686) | (-0.233, 1.446, -0.686) | 3.046 | -0.024 | none |
| 6 | 5 | (-0.186, -1.600, -0.457) | (-0.186, 1.215, -0.457) | 2.815 | -0.255 | none |
| 7 | 8 | (0.064, -1.600, -0.608) | (0.064, 1.516, -0.608) | 3.116 | 0.045 | none |
| 8 | 7 | (0.052, -1.600, -1.420) | (0.052, 1.342, -1.420) | 2.942 | -0.128 | none |
| 9 | 9 | (1.897, -1.600, -1.565) | (1.897, 1.495, -1.565) | 3.095 | 0.024 | none |
| 10 | 10 | (1.919, -1.600, 1.215) | (1.919, 1.498, 1.215) | 3.098 | 0.028 | none |

## Wall Metrics — candidate_4

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 3.661 | 92.823 | 90.000 | 2.823 | False |
| 2 | 2-3 | 5.344 | 142.980 | 180.000 | 37.020 | False |
| 3 | 3-4 | 8.091 | 270.004 | 270.000 | 0.004 | False |
| 4 | 4-5 | 4.385 | 1.451 | 0.000 | 1.451 | False |
| 5 | 5-6 | 0.234 | 78.440 | 90.000 | 11.560 | True |
| 6 | 6-7 | 0.291 | 328.917 | 0.000 | 31.083 | True |
| 7 | 7-8 | 0.812 | 269.202 | 270.000 | 0.798 | False |
| 8 | 8-9 | 1.850 | 355.486 | 0.000 | 4.514 | False |
| 9 | 9-10 | 2.781 | 89.535 | 90.000 | 0.465 | False |
| 10 | 10-1 | 2.236 | 200.863 | 180.000 | 20.863 | False |

## Corner Metrics — candidate_4

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 10 | 1 | 71.960 | 18.040 | True |
| 2 | 1 | 2 | 129.844 | 39.844 | True |
| 3 | 2 | 3 | 52.976 | 37.024 | True |
| 4 | 3 | 4 | 88.553 | 1.447 | False |
| 5 | 4 | 5 | 103.011 | 13.011 | False |
| 6 | 5 | 6 | 70.477 | 19.523 | True |
| 7 | 6 | 7 | 120.285 | 30.285 | True |
| 8 | 7 | 8 | 93.717 | 3.717 | False |
| 9 | 8 | 9 | 85.950 | 4.050 | False |
| 10 | 9 | 10 | 68.672 | 21.328 | True |

## Pair 3D Coordinates — candidate_5

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 2 | (-0.170, -1.600, 0.419) | (-0.170, 0.815, 0.419) | 2.415 | -0.656 | none |
| 2 | 1 | (-0.350, -1.600, 4.076) | (-0.350, 0.691, 4.076) | 2.291 | -0.779 | none |
| 3 | 3 | (-4.617, -1.600, 7.293) | (-4.617, 1.759, 7.293) | 3.359 | 0.289 | none |
| 4 | 4 | (-4.616, -1.600, -0.797) | (-4.616, 1.759, -0.797) | 3.359 | 0.288 | none |
| 5 | 6 | (-0.211, -1.600, -0.693) | (-0.211, 1.446, -0.693) | 3.046 | -0.024 | none |
| 6 | 5 | (-0.186, -1.600, -0.457) | (-0.186, 1.215, -0.457) | 2.815 | -0.255 | none |
| 7 | 8 | (0.067, -1.600, -0.636) | (0.067, 1.518, -0.636) | 3.118 | 0.048 | none |
| 8 | 7 | (0.052, -1.600, -1.420) | (0.052, 1.342, -1.420) | 2.942 | -0.128 | none |
| 9 | 9 | (1.897, -1.600, -1.565) | (1.897, 1.495, -1.565) | 3.095 | 0.024 | none |
| 10 | 10 | (1.919, -1.600, 1.215) | (1.919, 1.498, 1.215) | 3.098 | 0.028 | none |

## Wall Metrics — candidate_5

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 3.661 | 92.823 | 90.000 | 2.823 | False |
| 2 | 2-3 | 5.344 | 142.980 | 180.000 | 37.020 | False |
| 3 | 3-4 | 8.091 | 270.004 | 270.000 | 0.004 | False |
| 4 | 4-5 | 4.406 | 1.353 | 0.000 | 1.353 | False |
| 5 | 5-6 | 0.237 | 83.914 | 90.000 | 6.086 | True |
| 6 | 6-7 | 0.309 | 324.632 | 0.000 | 35.368 | True |
| 7 | 7-8 | 0.784 | 268.952 | 270.000 | 1.048 | False |
| 8 | 8-9 | 1.850 | 355.486 | 0.000 | 4.514 | False |
| 9 | 9-10 | 2.781 | 89.535 | 90.000 | 0.465 | False |
| 10 | 10-1 | 2.236 | 200.863 | 180.000 | 20.863 | False |

## Corner Metrics — candidate_5

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 10 | 1 | 71.960 | 18.040 | True |
| 2 | 1 | 2 | 129.844 | 39.844 | True |
| 3 | 2 | 3 | 52.976 | 37.024 | True |
| 4 | 3 | 4 | 88.650 | 1.350 | False |
| 5 | 4 | 5 | 97.440 | 7.440 | False |
| 6 | 5 | 6 | 60.719 | 29.281 | True |
| 7 | 6 | 7 | 124.320 | 34.320 | True |
| 8 | 7 | 8 | 93.467 | 3.467 | False |
| 9 | 8 | 9 | 85.950 | 4.050 | False |
| 10 | 9 | 10 | 68.672 | 21.328 | True |

## Safety Boundary

This report is expert-side, offline, local-only, sidecar, and dry-run only. It does not edit annotations, optimize coordinates, reorder corners, score workers, or create formal experiment artifacts.
