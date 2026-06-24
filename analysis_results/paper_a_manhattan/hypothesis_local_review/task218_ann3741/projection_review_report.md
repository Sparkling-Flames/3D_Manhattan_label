# Local 3D Projection Review

## Input Provenance

- Review schema: `local_3d_projection_review_m15_27_1_bridge_v1`
- Projection schema: `local_3d_projection_m15_19_v1`
- Input file: `hypothesis_review_bridge_manifest.json`
- Input SHA-256: `d65630925de486f1c14bb35401c74502e97d7f3d46aeee703eed4abd72796bf3`
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

### m1528_candidate_0017 | edge_6_7_floor_depth_balance | legacy_trial_blocked

- decision_class: `legacy_trial_blocked`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `None`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `['5-6', '6-7']`
- Applied coordinate changes:
  - pair 6: no numeric change
  - pair 7: no numeric change
- wall residual sum: 115.116 -> 90.753
- Preview only; this is not correctness evidence and cannot write back.

### m1528_candidate_0001 | vertical_column_align_x | hard_feasible_neutral

- decision_class: `hard_feasible_neutral`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `None`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `['5-6', '6-7']`
- Applied coordinate changes:
  - pair 5: no numeric change
- wall residual sum: 115.116 -> 115.116
- Preview only; this is not correctness evidence and cannot write back.

### m1528_candidate_0070 | azimuth_translate_keep_top_bottom_delta | hard_feasible_neutral

- decision_class: `hard_feasible_neutral`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `None`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `['5-6', '6-7']`
- Applied coordinate changes:
  - pair 5: no numeric change
- wall residual sum: 115.116 -> 115.822
- Preview only; this is not correctness evidence and cannot write back.

### m1528_candidate_0019 | edge_6_7_normal_slide_proxy | legacy_trial_blocked

- decision_class: `legacy_trial_blocked`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `None`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `['5-6', '6-7']`
- Applied coordinate changes:
  - pair 6: no numeric change
  - pair 7: no numeric change
- wall residual sum: 115.116 -> 101.165
- Preview only; this is not correctness evidence and cannot write back.

### m1528_candidate_0043 | preserve_5_6_length_with_6_7_fix | legacy_trial_blocked

- decision_class: `legacy_trial_blocked`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `None`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `['5-6', '6-7']`
- Applied coordinate changes:
  - pair 7: no numeric change
- wall residual sum: 115.116 -> 110.132
- Preview only; this is not correctness evidence and cannot write back.

## Candidate Metric Summary

| variant | wall residual sum | corner residual sum | height residual sum | vertical x residual sum | min wall | self-intersection |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| original | 115.116 | 196.339 | 2.521 | 0.936 | 0.234 | False |
| m1528_candidate_0017 | 90.753 | 156.042 | 2.375 | 0.936 | 0.179 | False |
| m1528_candidate_0001 | 115.116 | 196.339 | 2.521 | 0.560 | 0.234 | False |
| m1528_candidate_0070 | 115.822 | 196.365 | 2.521 | 0.936 | 0.233 | False |
| m1528_candidate_0019 | 101.165 | 173.962 | 2.384 | 0.936 | 0.208 | False |
| m1528_candidate_0043 | 110.132 | 184.687 | 2.452 | 0.936 | 0.234 | False |

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

## Pair 3D Coordinates — m1528_candidate_0017

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 2 | (-0.170, -1.600, 0.419) | (-0.170, 0.815, 0.419) | 2.415 | -0.599 | none |
| 2 | 1 | (-0.350, -1.600, 4.076) | (-0.350, 0.691, 4.076) | 2.291 | -0.723 | none |
| 3 | 3 | (-4.617, -1.600, 7.293) | (-4.617, 1.759, 7.293) | 3.359 | 0.345 | none |
| 4 | 4 | (-4.616, -1.600, -0.797) | (-4.616, 1.759, -0.797) | 3.359 | 0.345 | none |
| 5 | 6 | (-0.233, -1.600, -0.686) | (-0.233, 1.446, -0.686) | 3.046 | 0.032 | none |
| 6 | 5 | (-0.207, -1.600, -0.509) | (-0.207, 1.352, -0.509) | 2.952 | -0.062 | none |
| 7 | 8 | (0.061, -1.600, -0.579) | (0.061, 1.382, -0.579) | 2.982 | -0.032 | none |
| 8 | 7 | (0.052, -1.600, -1.420) | (0.052, 1.342, -1.420) | 2.942 | -0.072 | none |
| 9 | 9 | (1.897, -1.600, -1.565) | (1.897, 1.495, -1.565) | 3.095 | 0.081 | none |
| 10 | 10 | (1.919, -1.600, 1.215) | (1.919, 1.498, 1.215) | 3.098 | 0.084 | none |

## Wall Metrics — m1528_candidate_0017

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 3.661 | 92.823 | 90.000 | 2.823 | False |
| 2 | 2-3 | 5.344 | 142.980 | 180.000 | 37.020 | False |
| 3 | 3-4 | 8.091 | 270.004 | 270.000 | 0.004 | False |
| 4 | 4-5 | 4.385 | 1.451 | 0.000 | 1.451 | False |
| 5 | 5-6 | 0.179 | 81.695 | 90.000 | 8.305 | True |
| 6 | 6-7 | 0.276 | 345.261 | 0.000 | 14.739 | True |
| 7 | 7-8 | 0.841 | 269.432 | 270.000 | 0.568 | False |
| 8 | 8-9 | 1.850 | 355.486 | 0.000 | 4.514 | False |
| 9 | 9-10 | 2.781 | 89.535 | 90.000 | 0.465 | False |
| 10 | 10-1 | 2.236 | 200.863 | 180.000 | 20.863 | False |

## Corner Metrics — m1528_candidate_0017

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 10 | 1 | 71.960 | 18.040 | True |
| 2 | 1 | 2 | 129.844 | 39.844 | True |
| 3 | 2 | 3 | 52.976 | 37.024 | True |
| 4 | 3 | 4 | 88.553 | 1.447 | False |
| 5 | 4 | 5 | 99.756 | 9.756 | False |
| 6 | 5 | 6 | 83.566 | 6.434 | False |
| 7 | 6 | 7 | 104.172 | 14.172 | False |
| 8 | 7 | 8 | 93.947 | 3.947 | False |
| 9 | 8 | 9 | 85.950 | 4.050 | False |
| 10 | 9 | 10 | 68.672 | 21.328 | True |

## Pair 3D Coordinates — m1528_candidate_0001

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

## Wall Metrics — m1528_candidate_0001

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

## Corner Metrics — m1528_candidate_0001

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

## Pair 3D Coordinates — m1528_candidate_0070

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 2 | (-0.170, -1.600, 0.419) | (-0.170, 0.815, 0.419) | 2.415 | -0.656 | none |
| 2 | 1 | (-0.350, -1.600, 4.076) | (-0.350, 0.691, 4.076) | 2.291 | -0.779 | none |
| 3 | 3 | (-4.617, -1.600, 7.293) | (-4.617, 1.759, 7.293) | 3.359 | 0.289 | none |
| 4 | 4 | (-4.616, -1.600, -0.797) | (-4.616, 1.759, -0.797) | 3.359 | 0.288 | none |
| 5 | 6 | (-0.235, -1.600, -0.685) | (-0.235, 1.446, -0.685) | 3.046 | -0.024 | none |
| 6 | 5 | (-0.186, -1.600, -0.457) | (-0.186, 1.215, -0.457) | 2.815 | -0.255 | none |
| 7 | 8 | (0.067, -1.600, -0.636) | (0.067, 1.518, -0.636) | 3.118 | 0.048 | none |
| 8 | 7 | (0.052, -1.600, -1.420) | (0.052, 1.342, -1.420) | 2.942 | -0.128 | none |
| 9 | 9 | (1.897, -1.600, -1.565) | (1.897, 1.495, -1.565) | 3.095 | 0.024 | none |
| 10 | 10 | (1.919, -1.600, 1.215) | (1.919, 1.498, 1.215) | 3.098 | 0.028 | none |

## Wall Metrics — m1528_candidate_0070

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 3.661 | 92.823 | 90.000 | 2.823 | False |
| 2 | 2-3 | 5.344 | 142.980 | 180.000 | 37.020 | False |
| 3 | 3-4 | 8.091 | 270.004 | 270.000 | 0.004 | False |
| 4 | 4-5 | 4.382 | 1.464 | 0.000 | 1.464 | False |
| 5 | 5-6 | 0.233 | 77.747 | 90.000 | 12.253 | True |
| 6 | 6-7 | 0.309 | 324.632 | 0.000 | 35.368 | True |
| 7 | 7-8 | 0.784 | 268.952 | 270.000 | 1.048 | False |
| 8 | 8-9 | 1.850 | 355.486 | 0.000 | 4.514 | False |
| 9 | 9-10 | 2.781 | 89.535 | 90.000 | 0.465 | False |
| 10 | 10-1 | 2.236 | 200.863 | 180.000 | 20.863 | False |

## Corner Metrics — m1528_candidate_0070

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 10 | 1 | 71.960 | 18.040 | True |
| 2 | 1 | 2 | 129.844 | 39.844 | True |
| 3 | 2 | 3 | 52.976 | 37.024 | True |
| 4 | 3 | 4 | 88.540 | 1.460 | False |
| 5 | 4 | 5 | 103.717 | 13.717 | False |
| 6 | 5 | 6 | 66.885 | 23.115 | True |
| 7 | 6 | 7 | 124.320 | 34.320 | True |
| 8 | 7 | 8 | 93.467 | 3.467 | False |
| 9 | 8 | 9 | 85.950 | 4.050 | False |
| 10 | 9 | 10 | 68.672 | 21.328 | True |

## Pair 3D Coordinates — m1528_candidate_0019

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 2 | (-0.170, -1.600, 0.419) | (-0.170, 0.815, 0.419) | 2.415 | -0.633 | none |
| 2 | 1 | (-0.350, -1.600, 4.076) | (-0.350, 0.691, 4.076) | 2.291 | -0.757 | none |
| 3 | 3 | (-4.617, -1.600, 7.293) | (-4.617, 1.759, 7.293) | 3.359 | 0.311 | none |
| 4 | 4 | (-4.616, -1.600, -0.797) | (-4.616, 1.759, -0.797) | 3.359 | 0.311 | none |
| 5 | 6 | (-0.233, -1.600, -0.686) | (-0.233, 1.446, -0.686) | 3.046 | -0.002 | none |
| 6 | 5 | (-0.204, -1.600, -0.480) | (-0.204, 1.283, -0.480) | 2.883 | -0.165 | none |
| 7 | 8 | (0.073, -1.600, -0.606) | (0.073, 1.450, -0.606) | 3.050 | 0.002 | none |
| 8 | 7 | (0.052, -1.600, -1.420) | (0.052, 1.342, -1.420) | 2.942 | -0.106 | none |
| 9 | 9 | (1.897, -1.600, -1.565) | (1.897, 1.495, -1.565) | 3.095 | 0.047 | none |
| 10 | 10 | (1.919, -1.600, 1.215) | (1.919, 1.498, 1.215) | 3.098 | 0.050 | none |

## Wall Metrics — m1528_candidate_0019

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 3.661 | 92.823 | 90.000 | 2.823 | False |
| 2 | 2-3 | 5.344 | 142.980 | 180.000 | 37.020 | False |
| 3 | 3-4 | 8.091 | 270.004 | 270.000 | 0.004 | False |
| 4 | 4-5 | 4.385 | 1.451 | 0.000 | 1.451 | False |
| 5 | 5-6 | 0.208 | 82.044 | 90.000 | 7.956 | True |
| 6 | 6-7 | 0.304 | 335.400 | 0.000 | 24.600 | True |
| 7 | 7-8 | 0.814 | 268.532 | 270.000 | 1.468 | False |
| 8 | 8-9 | 1.850 | 355.486 | 0.000 | 4.514 | False |
| 9 | 9-10 | 2.781 | 89.535 | 90.000 | 0.465 | False |
| 10 | 10-1 | 2.236 | 200.863 | 180.000 | 20.863 | False |

## Corner Metrics — m1528_candidate_0019

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 10 | 1 | 71.960 | 18.040 | True |
| 2 | 1 | 2 | 129.844 | 39.844 | True |
| 3 | 2 | 3 | 52.976 | 37.024 | True |
| 4 | 3 | 4 | 88.553 | 1.447 | False |
| 5 | 4 | 5 | 99.407 | 9.407 | False |
| 6 | 5 | 6 | 73.356 | 16.644 | True |
| 7 | 6 | 7 | 113.132 | 23.132 | True |
| 8 | 7 | 8 | 93.046 | 3.046 | False |
| 9 | 8 | 9 | 85.950 | 4.050 | False |
| 10 | 9 | 10 | 68.672 | 21.328 | True |

## Pair 3D Coordinates — m1528_candidate_0043

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 2 | (-0.170, -1.600, 0.419) | (-0.170, 0.815, 0.419) | 2.415 | -0.633 | none |
| 2 | 1 | (-0.350, -1.600, 4.076) | (-0.350, 0.691, 4.076) | 2.291 | -0.757 | none |
| 3 | 3 | (-4.617, -1.600, 7.293) | (-4.617, 1.759, 7.293) | 3.359 | 0.311 | none |
| 4 | 4 | (-4.616, -1.600, -0.797) | (-4.616, 1.759, -0.797) | 3.359 | 0.311 | none |
| 5 | 6 | (-0.233, -1.600, -0.686) | (-0.233, 1.446, -0.686) | 3.046 | -0.002 | none |
| 6 | 5 | (-0.186, -1.600, -0.457) | (-0.186, 1.215, -0.457) | 2.815 | -0.233 | none |
| 7 | 8 | (0.073, -1.600, -0.606) | (0.073, 1.450, -0.606) | 3.050 | 0.002 | none |
| 8 | 7 | (0.052, -1.600, -1.420) | (0.052, 1.342, -1.420) | 2.942 | -0.106 | none |
| 9 | 9 | (1.897, -1.600, -1.565) | (1.897, 1.495, -1.565) | 3.095 | 0.047 | none |
| 10 | 10 | (1.919, -1.600, 1.215) | (1.919, 1.498, 1.215) | 3.098 | 0.050 | none |

## Wall Metrics — m1528_candidate_0043

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 3.661 | 92.823 | 90.000 | 2.823 | False |
| 2 | 2-3 | 5.344 | 142.980 | 180.000 | 37.020 | False |
| 3 | 3-4 | 8.091 | 270.004 | 270.000 | 0.004 | False |
| 4 | 4-5 | 4.385 | 1.451 | 0.000 | 1.451 | False |
| 5 | 5-6 | 0.234 | 78.440 | 90.000 | 11.560 | True |
| 6 | 6-7 | 0.299 | 330.037 | 0.000 | 29.963 | True |
| 7 | 7-8 | 0.814 | 268.532 | 270.000 | 1.468 | False |
| 8 | 8-9 | 1.850 | 355.486 | 0.000 | 4.514 | False |
| 9 | 9-10 | 2.781 | 89.535 | 90.000 | 0.465 | False |
| 10 | 10-1 | 2.236 | 200.863 | 180.000 | 20.863 | False |

## Corner Metrics — m1528_candidate_0043

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 10 | 1 | 71.960 | 18.040 | True |
| 2 | 1 | 2 | 129.844 | 39.844 | True |
| 3 | 2 | 3 | 52.976 | 37.024 | True |
| 4 | 3 | 4 | 88.553 | 1.447 | False |
| 5 | 4 | 5 | 103.011 | 13.011 | False |
| 6 | 5 | 6 | 71.597 | 18.403 | True |
| 7 | 6 | 7 | 118.494 | 28.494 | True |
| 8 | 7 | 8 | 93.046 | 3.046 | False |
| 9 | 8 | 9 | 85.950 | 4.050 | False |
| 10 | 9 | 10 | 68.672 | 21.328 | True |

## Safety Boundary

This report is expert-side, offline, local-only, sidecar, and dry-run only. It does not edit annotations, optimize coordinates, reorder corners, score workers, or create formal experiment artifacts.
