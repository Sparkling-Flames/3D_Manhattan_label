# Local 3D Projection Review

## Input Provenance

- Review schema: `local_3d_projection_review_m15_27_1_bridge_v1`
- Projection schema: `local_3d_projection_m15_19_v1`
- Input file: `hypothesis_review_bridge_manifest.json`
- Input SHA-256: `2cda1aab65cea7bf65a2a9ddab3a8c78682d92f1186708a983cc8828f17df0c9`
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

### m_anchor_4_candidate_0002_sum_first | m_anchor_4_staged_vertical_height_solver | review_available

- decision_class: `review_available`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `False`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - source pair 2 (solver position 1): top_x 5.890→6.290, top_y 14.187→11.187, bottom_x 5.890→6.290, bottom_y 91.479→91.229
  - source pair 1 (solver position 2): top_x 0.343→0.443, top_y 41.659→42.597, bottom_x 0.343→0.443, bottom_y 57.618→57.368
  - source pair 4 (solver position 4): top_x 27.411→28.211, top_y 39.059→39.181, bottom_x 27.411→28.211, bottom_y 60.020→60.770
  - source pair 6 (solver position 5): top_y 17.137→16.924, bottom_y 81.509→83.009
  - source pair 5 (solver position 6): top_x 44.367→44.567, top_y 11.402→12.621, bottom_x 44.367→44.567, bottom_y 87.573→87.323
  - source pair 8 (solver position 7): top_x 52.067→52.167, top_y 11.138→12.090, bottom_x 52.067→52.167
  - source pair 7 (solver position 8): top_x 50.378→50.878, top_y 21.890→24.301, bottom_x 50.378→50.878, bottom_y 76.621→75.621
  - source pair 9 (solver position 9): top_x 63.781→64.181, top_y 31.617→31.437, bottom_x 63.781→64.181, bottom_y 68.741→68.491
  - source pair 10 (solver position 10): top_x 83.350→83.650, top_y 30.445→30.061, bottom_x 83.350→83.650, bottom_y 69.366→69.866
  - source pair 12 (solver position 11): top_x 98.901→99.401, top_y 20.556→19.763, bottom_x 98.901→99.401, bottom_y 78.664→80.164
  - source pair 11 (solver position 12): top_y 12.486→9.486
- wall residual sum: 36.741 -> 2.196
- Preview only; this is not correctness evidence and cannot write back.

### m_anchor_4_candidate_0001_max_first | m_anchor_4_staged_vertical_height_solver | review_available

- decision_class: `review_available`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `False`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - source pair 2 (solver position 1): top_x 5.890→6.290, top_y 14.187→11.187, bottom_x 5.890→6.290, bottom_y 91.479→91.229
  - source pair 1 (solver position 2): top_y 41.659→42.526, bottom_y 57.618→57.368
  - source pair 4 (solver position 4): top_x 27.411→28.211, top_y 39.059→39.081, bottom_x 27.411→28.211, bottom_y 60.020→60.770
  - source pair 6 (solver position 5): top_y 17.137→17.034, bottom_y 81.509→82.759
  - source pair 5 (solver position 6): top_x 44.367→44.467, top_y 11.402→12.509, bottom_x 44.367→44.467, bottom_y 87.573→87.323
  - source pair 8 (solver position 7): top_x 52.067→52.367, top_y 11.138→11.981, bottom_x 52.067→52.367
  - source pair 7 (solver position 8): top_x 50.378→50.978, top_y 21.890→24.143, bottom_x 50.378→50.978, bottom_y 76.621→75.621
  - source pair 9 (solver position 9): top_x 63.781→64.381, top_y 31.617→31.543, bottom_x 63.781→64.381, bottom_y 68.741→68.241
  - source pair 10 (solver position 10): top_x 83.350→83.650, top_y 30.445→30.412, bottom_x 83.350→83.650
  - source pair 12 (solver position 11): top_x 98.901→99.401, top_y 20.556→20.111, bottom_x 98.901→99.401, bottom_y 78.664→79.664
  - source pair 11 (solver position 12): top_y 12.486→9.486
- wall residual sum: 36.741 -> 2.724
- Preview only; this is not correctness evidence and cannot write back.

### m_anchor_4_candidate_0003_turn_aware | m_anchor_4_staged_vertical_height_solver | review_available

- decision_class: `review_available`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `False`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - source pair 2 (solver position 1): top_x 5.890→6.290, top_y 14.187→11.187, bottom_x 5.890→6.290, bottom_y 91.479→91.229
  - source pair 1 (solver position 2): top_y 41.659→42.481, bottom_y 57.618→57.368
  - source pair 4 (solver position 4): top_x 27.411→28.211, top_y 39.059→39.018, bottom_x 27.411→28.211, bottom_y 60.020→60.770
  - source pair 6 (solver position 5): top_x 46.137→46.037, top_y 17.137→17.194, bottom_x 46.137→46.037, bottom_y 81.509→82.509
  - source pair 5 (solver position 6): top_x 44.367→44.067, top_y 11.402→12.192, bottom_x 44.367→44.067
  - source pair 8 (solver position 7): top_x 52.067→51.467, top_y 11.138→11.421, bottom_x 52.067→51.467, bottom_y 87.857→88.357
  - source pair 7 (solver position 8): top_x 50.378→50.678, top_y 21.890→23.045, bottom_x 50.378→50.678
  - source pair 9 (solver position 9): top_x 63.781→64.581, top_y 31.617→30.947, bottom_x 63.781→64.581
  - source pair 10 (solver position 10): top_x 83.350→83.650, top_y 30.445→29.815, bottom_x 83.350→83.650, bottom_y 69.366→69.866
  - source pair 12 (solver position 11): top_x 98.901→99.301, top_y 20.556→19.519, bottom_x 98.901→99.301, bottom_y 78.664→80.164
  - source pair 11 (solver position 12): top_x 98.371→98.071, top_y 12.486→9.486, bottom_x 98.371→98.071
- wall residual sum: 36.741 -> 3.425
- Preview only; this is not correctness evidence and cannot write back.

### m_anchor_4_candidate_0004_bottom_only | m_anchor_4_staged_vertical_height_solver | review_available

- decision_class: `review_available`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `False`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - source pair 2 (solver position 1): top_y 14.187→11.187, bottom_y 91.479→90.729
  - source pair 1 (solver position 2): top_y 41.659→42.347, bottom_y 57.618→57.368
  - source pair 4 (solver position 4): top_y 39.059→39.347, bottom_y 60.020→60.270
  - source pair 6 (solver position 5): top_y 17.137→16.447, bottom_y 81.509→83.009
  - source pair 5 (solver position 6): top_y 11.402→11.991
  - source pair 8 (solver position 7): top_y 11.138→11.473, bottom_y 87.857→88.107
  - source pair 7 (solver position 8): top_y 21.890→24.252, bottom_y 76.621→75.121
  - source pair 9 (solver position 9): top_y 31.617→31.183, bottom_y 68.741→68.241
  - source pair 10 (solver position 10): top_y 30.445→29.283, bottom_y 69.366→70.116
  - source pair 12 (solver position 11): top_y 20.556→19.246, bottom_y 78.664→80.164
  - source pair 11 (solver position 12): top_y 12.486→9.486, bottom_y 91.828→91.328
- wall residual sum: 36.741 -> 14.876
- Preview only; this is not correctness evidence and cannot write back.

## Candidate Metric Summary

| variant | wall residual sum | corner residual sum | height residual sum | vertical x residual sum | min wall | self-intersection |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| original | 36.741 | 11.843 | 1.995 | 0.000 | 0.202 | False |
| m_anchor_4_candidate_0002_sum_first | 2.196 | 2.239 | 0.765 | 0.000 | 0.217 | False |
| m_anchor_4_candidate_0001_max_first | 2.724 | 2.249 | 0.781 | 0.000 | 0.217 | False |
| m_anchor_4_candidate_0003_turn_aware | 3.425 | 3.213 | 0.791 | 0.000 | 0.225 | False |
| m_anchor_4_candidate_0004_bottom_only | 14.876 | 15.375 | 0.659 | 0.000 | 0.219 | False |

## Pair 3D Coordinates — original

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | None | (-0.159, -1.600, 0.409) | (-0.159, 0.919, 0.409) | 2.519 | -0.840 | none |
| 2 | 1 | (-0.141, -1.600, 6.556) | (-0.141, 1.759, 6.556) | 3.359 | 0.000 | none |
| 3 | 3 | (-4.401, -1.600, 6.813) | (-4.401, 1.759, 6.813) | 3.359 | 0.000 | none |
| 4 | 4 | (-4.857, -1.600, -0.741) | (-4.857, 1.759, -0.741) | 3.359 | 0.000 | none |
| 5 | 6 | (-0.252, -1.600, -1.020) | (-0.252, 1.759, -1.020) | 3.359 | 0.000 | none |
| 6 | 5 | (-0.228, -1.600, -0.618) | (-0.228, 1.759, -0.618) | 3.359 | 0.000 | none |
| 7 | 8 | (0.083, -1.600, -0.636) | (0.083, 1.759, -0.636) | 3.359 | -0.000 | none |
| 8 | 7 | (0.034, -1.600, -1.444) | (0.034, 1.759, -1.444) | 3.359 | 0.000 | none |
| 9 | 9 | (1.825, -1.600, -1.553) | (1.825, 1.561, -1.553) | 3.161 | -0.197 | none |
| 10 | 10 | (1.988, -1.600, 1.151) | (1.988, 1.620, 1.151) | 3.220 | -0.138 | none |
| 11 | 12 | (0.087, -1.600, 1.265) | (0.087, 1.683, 1.265) | 3.283 | -0.076 | none |
| 12 | None | (0.043, -1.600, 0.418) | (0.043, 1.015, 0.418) | 2.615 | -0.743 | none |

## Wall Metrics — original

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

## Corner Metrics — original

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

## Pair 3D Coordinates — m_anchor_4_candidate_0002_sum_first

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | None | (-0.174, -1.600, 0.418) | (-0.174, 1.234, 0.418) | 2.834 | -0.374 | none |
| 2 | 1 | (-0.189, -1.600, 6.786) | (-0.189, 1.608, 6.786) | 3.208 | 0.000 | none |
| 3 | 3 | (-4.401, -1.600, 6.813) | (-4.401, 1.759, 6.813) | 3.359 | 0.151 | none |
| 4 | 4 | (-4.455, -1.600, -0.911) | (-4.455, 1.608, -0.911) | 3.208 | 0.000 | none |
| 5 | 6 | (-0.227, -1.600, -0.918) | (-0.227, 1.608, -0.918) | 3.208 | 0.000 | none |
| 6 | 5 | (-0.225, -1.600, -0.634) | (-0.225, 1.608, -0.634) | 3.208 | 0.000 | none |
| 7 | 8 | (0.087, -1.600, -0.636) | (0.087, 1.608, -0.636) | 3.208 | 0.000 | none |
| 8 | 7 | (0.085, -1.600, -1.536) | (0.085, 1.608, -1.536) | 3.208 | 0.000 | none |
| 9 | 9 | (1.895, -1.600, -1.532) | (1.895, 1.608, -1.532) | 3.208 | 0.000 | none |
| 10 | 10 | (1.902, -1.600, 1.149) | (1.902, 1.608, 1.149) | 3.208 | 0.000 | none |
| 11 | 12 | (0.043, -1.600, 1.149) | (0.043, 1.608, 1.149) | 3.208 | 0.000 | none |
| 12 | None | (0.043, -1.600, 0.418) | (0.043, 1.368, 0.418) | 2.968 | -0.240 | none |

## Wall Metrics — m_anchor_4_candidate_0002_sum_first

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.368 | 90.132 | 90.000 | 0.132 | False |
| 2 | 2-3 | 4.212 | 179.629 | 180.000 | 0.371 | False |
| 3 | 3-4 | 7.724 | 269.603 | 270.000 | 0.397 | False |
| 4 | 4-5 | 4.227 | 359.908 | 0.000 | 0.092 | False |
| 5 | 5-6 | 0.284 | 89.607 | 90.000 | 0.393 | True |
| 6 | 6-7 | 0.312 | 359.715 | 0.000 | 0.285 | True |
| 7 | 7-8 | 0.901 | 269.856 | 270.000 | 0.144 | False |
| 8 | 8-9 | 1.811 | 0.136 | 0.000 | 0.136 | False |
| 9 | 9-10 | 2.681 | 89.866 | 90.000 | 0.134 | False |
| 10 | 10-11 | 1.858 | 179.994 | 180.000 | 0.006 | False |
| 11 | 11-12 | 0.731 | 269.975 | 270.000 | 0.025 | False |
| 12 | 12-1 | 0.217 | 180.080 | 180.000 | 0.080 | True |

## Corner Metrics — m_anchor_4_candidate_0002_sum_first

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 12 | 1 | 90.052 | 0.052 | False |
| 2 | 1 | 2 | 90.503 | 0.503 | False |
| 3 | 2 | 3 | 90.026 | 0.026 | False |
| 4 | 3 | 4 | 89.695 | 0.305 | False |
| 5 | 4 | 5 | 90.301 | 0.301 | False |
| 6 | 5 | 6 | 90.108 | 0.108 | False |
| 7 | 6 | 7 | 90.141 | 0.141 | False |
| 8 | 7 | 8 | 89.720 | 0.280 | False |
| 9 | 8 | 9 | 90.271 | 0.271 | False |
| 10 | 9 | 10 | 89.871 | 0.129 | False |
| 11 | 10 | 11 | 90.019 | 0.019 | False |
| 12 | 11 | 12 | 90.105 | 0.105 | False |

## Pair 3D Coordinates — m_anchor_4_candidate_0001_max_first

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | None | (-0.174, -1.600, 0.418) | (-0.174, 1.234, 0.418) | 2.834 | -0.390 | none |
| 2 | 1 | (-0.146, -1.600, 6.787) | (-0.146, 1.624, 6.787) | 3.224 | 0.000 | none |
| 3 | 3 | (-4.401, -1.600, 6.813) | (-4.401, 1.759, 6.813) | 3.359 | 0.135 | none |
| 4 | 4 | (-4.455, -1.600, -0.911) | (-4.455, 1.624, -0.911) | 3.224 | 0.000 | none |
| 5 | 6 | (-0.231, -1.600, -0.934) | (-0.231, 1.624, -0.934) | 3.224 | 0.000 | none |
| 6 | 5 | (-0.229, -1.600, -0.633) | (-0.229, 1.624, -0.633) | 3.224 | 0.000 | none |
| 7 | 8 | (0.095, -1.600, -0.635) | (0.095, 1.624, -0.635) | 3.224 | 0.000 | none |
| 8 | 7 | (0.095, -1.600, -1.536) | (0.095, 1.624, -1.536) | 3.224 | 0.000 | none |
| 9 | 9 | (1.948, -1.600, -1.534) | (1.948, 1.624, -1.534) | 3.224 | -0.000 | none |
| 10 | 10 | (1.966, -1.600, 1.188) | (1.966, 1.624, 1.188) | 3.224 | 0.000 | none |
| 11 | 12 | (0.045, -1.600, 1.188) | (0.045, 1.624, 1.188) | 3.224 | 0.000 | none |
| 12 | None | (0.043, -1.600, 0.418) | (0.043, 1.368, 0.418) | 2.968 | -0.256 | none |

## Wall Metrics — m_anchor_4_candidate_0001_max_first

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.369 | 89.749 | 90.000 | 0.251 | False |
| 2 | 2-3 | 4.255 | 179.647 | 180.000 | 0.353 | False |
| 3 | 3-4 | 7.724 | 269.603 | 270.000 | 0.397 | False |
| 4 | 4-5 | 4.223 | 359.683 | 0.000 | 0.317 | False |
| 5 | 5-6 | 0.302 | 89.609 | 90.000 | 0.391 | True |
| 6 | 6-7 | 0.324 | 359.675 | 0.000 | 0.325 | True |
| 7 | 7-8 | 0.901 | 269.963 | 270.000 | 0.037 | False |
| 8 | 8-9 | 1.853 | 0.048 | 0.000 | 0.048 | False |
| 9 | 9-10 | 2.722 | 89.612 | 90.000 | 0.388 | False |
| 10 | 10-11 | 1.921 | 180.006 | 180.000 | 0.006 | False |
| 11 | 11-12 | 0.770 | 269.869 | 270.000 | 0.131 | False |
| 12 | 12-1 | 0.217 | 180.080 | 180.000 | 0.080 | True |

## Corner Metrics — m_anchor_4_candidate_0001_max_first

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 12 | 1 | 89.669 | 0.331 | False |
| 2 | 1 | 2 | 90.102 | 0.102 | False |
| 3 | 2 | 3 | 90.044 | 0.044 | False |
| 4 | 3 | 4 | 89.920 | 0.080 | False |
| 5 | 4 | 5 | 90.074 | 0.074 | False |
| 6 | 5 | 6 | 90.066 | 0.066 | False |
| 7 | 6 | 7 | 90.287 | 0.287 | False |
| 8 | 7 | 8 | 89.914 | 0.086 | False |
| 9 | 8 | 9 | 90.436 | 0.436 | False |
| 10 | 9 | 10 | 89.606 | 0.394 | False |
| 11 | 10 | 11 | 90.137 | 0.137 | False |
| 12 | 11 | 12 | 90.212 | 0.212 | False |

## Pair 3D Coordinates — m_anchor_4_candidate_0003_turn_aware

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | None | (-0.174, -1.600, 0.418) | (-0.174, 1.234, 0.418) | 2.834 | -0.400 | none |
| 2 | 1 | (-0.146, -1.600, 6.787) | (-0.146, 1.634, 6.787) | 3.234 | -0.000 | none |
| 3 | 3 | (-4.401, -1.600, 6.813) | (-4.401, 1.759, 6.813) | 3.359 | 0.125 | none |
| 4 | 4 | (-4.455, -1.600, -0.911) | (-4.455, 1.634, -0.911) | 3.234 | -0.000 | none |
| 5 | 6 | (-0.242, -1.600, -0.950) | (-0.242, 1.634, -0.950) | 3.234 | 0.000 | none |
| 6 | 5 | (-0.240, -1.600, -0.613) | (-0.240, 1.634, -0.613) | 3.234 | -0.000 | none |
| 7 | 8 | (0.056, -1.600, -0.610) | (0.056, 1.634, -0.610) | 3.234 | 0.000 | none |
| 8 | 7 | (0.062, -1.600, -1.443) | (0.062, 1.634, -1.443) | 3.234 | 0.000 | none |
| 9 | 9 | (1.901, -1.600, -1.459) | (1.901, 1.634, -1.459) | 3.234 | 0.000 | none |
| 10 | 10 | (1.902, -1.600, 1.149) | (1.902, 1.634, 1.149) | 3.234 | 0.000 | none |
| 11 | 12 | (0.050, -1.600, 1.149) | (0.050, 1.634, 1.149) | 3.234 | 0.000 | none |
| 12 | None | (0.051, -1.600, 0.417) | (0.051, 1.368, 0.417) | 2.968 | -0.267 | none |

## Wall Metrics — m_anchor_4_candidate_0003_turn_aware

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.369 | 89.749 | 90.000 | 0.251 | False |
| 2 | 2-3 | 4.255 | 179.647 | 180.000 | 0.353 | False |
| 3 | 3-4 | 7.724 | 269.603 | 270.000 | 0.397 | False |
| 4 | 4-5 | 4.213 | 359.476 | 0.000 | 0.524 | False |
| 5 | 5-6 | 0.336 | 89.710 | 90.000 | 0.290 | True |
| 6 | 6-7 | 0.296 | 0.577 | 0.000 | 0.577 | True |
| 7 | 7-8 | 0.833 | 270.353 | 270.000 | 0.353 | False |
| 8 | 8-9 | 1.839 | 359.521 | 0.000 | 0.479 | False |
| 9 | 9-10 | 2.608 | 89.976 | 90.000 | 0.024 | False |
| 10 | 10-11 | 1.851 | 180.003 | 180.000 | 0.003 | False |
| 11 | 11-12 | 0.732 | 270.026 | 270.000 | 0.026 | False |
| 12 | 12-1 | 0.225 | 179.853 | 180.000 | 0.147 | True |

## Corner Metrics — m_anchor_4_candidate_0003_turn_aware

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 12 | 1 | 89.896 | 0.104 | False |
| 2 | 1 | 2 | 90.102 | 0.102 | False |
| 3 | 2 | 3 | 90.044 | 0.044 | False |
| 4 | 3 | 4 | 90.127 | 0.127 | False |
| 5 | 4 | 5 | 89.766 | 0.234 | False |
| 6 | 5 | 6 | 90.866 | 0.866 | False |
| 7 | 6 | 7 | 89.777 | 0.223 | False |
| 8 | 7 | 8 | 90.833 | 0.833 | False |
| 9 | 8 | 9 | 89.545 | 0.455 | False |
| 10 | 9 | 10 | 89.973 | 0.027 | False |
| 11 | 10 | 11 | 89.977 | 0.023 | False |
| 12 | 11 | 12 | 89.826 | 0.174 | False |

## Pair 3D Coordinates — m_anchor_4_candidate_0004_bottom_only

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | None | (-0.173, -1.600, 0.447) | (-0.173, 1.308, 0.447) | 2.908 | -0.356 | none |
| 2 | 1 | (-0.146, -1.600, 6.787) | (-0.146, 1.664, 6.787) | 3.264 | 0.000 | none |
| 3 | 3 | (-4.401, -1.600, 6.813) | (-4.401, 1.759, 6.813) | 3.359 | 0.094 | none |
| 4 | 4 | (-4.731, -1.600, -0.722) | (-4.731, 1.664, -0.722) | 3.264 | -0.000 | none |
| 5 | 6 | (-0.227, -1.600, -0.918) | (-0.227, 1.664, -0.918) | 3.264 | 0.000 | none |
| 6 | 5 | (-0.228, -1.600, -0.618) | (-0.228, 1.664, -0.618) | 3.264 | 0.000 | none |
| 7 | 8 | (0.081, -1.600, -0.622) | (0.081, 1.664, -0.622) | 3.264 | -0.000 | none |
| 8 | 7 | (0.038, -1.600, -1.587) | (0.038, 1.664, -1.587) | 3.264 | 0.000 | none |
| 9 | 9 | (1.888, -1.600, -1.607) | (1.888, 1.664, -1.607) | 3.264 | 0.000 | none |
| 10 | 10 | (1.892, -1.600, 1.095) | (1.892, 1.664, 1.095) | 3.264 | 0.000 | none |
| 11 | 12 | (0.079, -1.600, 1.147) | (0.079, 1.664, 1.147) | 3.264 | 0.000 | none |
| 12 | None | (0.046, -1.600, 0.445) | (0.046, 1.455, 0.445) | 3.055 | -0.209 | none |

## Wall Metrics — m_anchor_4_candidate_0004_bottom_only

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.340 | 89.754 | 90.000 | 0.246 | False |
| 2 | 2-3 | 4.255 | 179.647 | 180.000 | 0.353 | False |
| 3 | 3-4 | 7.543 | 267.495 | 270.000 | 2.505 | False |
| 4 | 4-5 | 4.508 | 357.511 | 0.000 | 2.489 | False |
| 5 | 5-6 | 0.300 | 90.171 | 90.000 | 0.171 | True |
| 6 | 6-7 | 0.309 | 359.189 | 0.000 | 0.811 | True |
| 7 | 7-8 | 0.966 | 267.419 | 270.000 | 2.581 | False |
| 8 | 8-9 | 1.851 | 359.406 | 0.000 | 0.594 | False |
| 9 | 9-10 | 2.701 | 89.936 | 90.000 | 0.064 | False |
| 10 | 10-11 | 1.813 | 178.339 | 180.000 | 1.661 | False |
| 11 | 11-12 | 0.703 | 267.259 | 270.000 | 2.741 | False |
| 12 | 12-1 | 0.219 | 179.340 | 180.000 | 0.660 | True |

## Corner Metrics — m_anchor_4_candidate_0004_bottom_only

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 12 | 1 | 90.414 | 0.414 | False |
| 2 | 1 | 2 | 90.107 | 0.107 | False |
| 3 | 2 | 3 | 92.152 | 2.152 | False |
| 4 | 3 | 4 | 89.984 | 0.016 | False |
| 5 | 4 | 5 | 87.340 | 2.660 | False |
| 6 | 5 | 6 | 89.018 | 0.982 | False |
| 7 | 6 | 7 | 88.230 | 1.770 | False |
| 8 | 7 | 8 | 88.013 | 1.987 | False |
| 9 | 8 | 9 | 89.471 | 0.529 | False |
| 10 | 9 | 10 | 91.596 | 1.596 | False |
| 11 | 10 | 11 | 91.080 | 1.080 | False |
| 12 | 11 | 12 | 92.081 | 2.081 | False |

## Safety Boundary

This report is expert-side, offline, local-only, sidecar, and dry-run only. It does not edit annotations, optimize coordinates, reorder corners, score workers, or create formal experiment artifacts.
