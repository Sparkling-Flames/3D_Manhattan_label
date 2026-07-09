# Local 3D Projection Review

## Input Provenance

- Review schema: `local_3d_projection_review_m15_27_1_bridge_v1`
- Projection schema: `local_3d_projection_m15_19_v1`
- Input file: `hypothesis_review_bridge_manifest.json`
- Input SHA-256: `9c5b531968637570aba5bb3a082728153cf292d0f55d91d5b8d33d5ec9c193a1`
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

### m_anchor_3b_candidate_0016 | m_anchor_3b_local_chain_footprint_solver | review_available

- decision_class: `review_available`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `False`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - source pair 5 (solver position 6): bottom_y 87.573→87.073
- wall residual sum: 36.741 -> 33.569
- Preview only; this is not correctness evidence and cannot write back.

### m_anchor_3b_candidate_0101 | m_anchor_3b_local_chain_footprint_solver | review_available

- decision_class: `review_available`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `False`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - source pair 8 (solver position 7): bottom_y 87.857→88.357
  - source pair 7 (solver position 8): bottom_y 76.621→76.121
- wall residual sum: 36.741 -> 33.055
- Preview only; this is not correctness evidence and cannot write back.

### m_anchor_3b_candidate_0034 | m_anchor_3b_local_chain_footprint_solver | review_available

- decision_class: `review_available`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `False`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - source pair 6 (solver position 5): bottom_y 81.509→82.009
- wall residual sum: 36.741 -> 35.300
- Preview only; this is not correctness evidence and cannot write back.

### m_anchor_3b_candidate_0095 | m_anchor_3b_local_chain_footprint_solver | review_available

- decision_class: `review_available`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `False`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - source pair 6 (solver position 5): bottom_y 81.509→82.009
  - source pair 5 (solver position 6): bottom_y 87.573→87.073
- wall residual sum: 36.741 -> 31.911
- Preview only; this is not correctness evidence and cannot write back.

### m_anchor_3b_candidate_0047 | m_anchor_3b_local_chain_footprint_solver | review_available

- decision_class: `review_available`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `False`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - source pair 6 (solver position 5): bottom_y 81.509→82.009
  - source pair 5 (solver position 6): bottom_y 87.573→87.323
- wall residual sum: 36.741 -> 32.013
- Preview only; this is not correctness evidence and cannot write back.

## Candidate Metric Summary

| variant | wall residual sum | corner residual sum | height residual sum | vertical x residual sum | min wall | self-intersection |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| original | 36.741 | 11.843 | 1.995 | 0.000 | 0.202 | False |
| m_anchor_3b_candidate_0016 | 33.569 | 21.943 | 2.074 | 0.000 | 0.202 | False |
| m_anchor_3b_candidate_0101 | 33.055 | 24.200 | 2.131 | 0.000 | 0.202 | False |
| m_anchor_3b_candidate_0034 | 35.300 | 13.856 | 2.055 | 0.000 | 0.202 | False |
| m_anchor_3b_candidate_0095 | 31.911 | 21.943 | 2.134 | 0.000 | 0.202 | False |
| m_anchor_3b_candidate_0047 | 32.013 | 16.955 | 2.094 | 0.000 | 0.202 | False |

## Pair 3D Coordinates — original

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 2 | (-0.159, -1.600, 0.409) | (-0.159, 0.919, 0.409) | 2.519 | -0.840 | none |
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
| 12 | 11 | (0.043, -1.600, 0.418) | (0.043, 1.015, 0.418) | 2.615 | -0.743 | none |

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

## Pair 3D Coordinates — m_anchor_3b_candidate_0016

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 2 | (-0.159, -1.600, 0.409) | (-0.159, 0.919, 0.409) | 2.519 | -0.840 | none |
| 2 | 1 | (-0.141, -1.600, 6.556) | (-0.141, 1.759, 6.556) | 3.359 | 0.000 | none |
| 3 | 3 | (-4.401, -1.600, 6.813) | (-4.401, 1.759, 6.813) | 3.359 | 0.000 | none |
| 4 | 4 | (-4.857, -1.600, -0.741) | (-4.857, 1.759, -0.741) | 3.359 | 0.000 | none |
| 5 | 6 | (-0.252, -1.600, -1.020) | (-0.252, 1.759, -1.020) | 3.359 | 0.000 | none |
| 6 | 5 | (-0.238, -1.600, -0.645) | (-0.238, 1.838, -0.645) | 3.438 | 0.079 | none |
| 7 | 8 | (0.083, -1.600, -0.636) | (0.083, 1.759, -0.636) | 3.359 | -0.000 | none |
| 8 | 7 | (0.034, -1.600, -1.444) | (0.034, 1.759, -1.444) | 3.359 | 0.000 | none |
| 9 | 9 | (1.825, -1.600, -1.553) | (1.825, 1.561, -1.553) | 3.161 | -0.197 | none |
| 10 | 10 | (1.988, -1.600, 1.151) | (1.988, 1.620, 1.151) | 3.220 | -0.138 | none |
| 11 | 12 | (0.087, -1.600, 1.265) | (0.087, 1.683, 1.265) | 3.283 | -0.076 | none |
| 12 | 11 | (0.043, -1.600, 0.418) | (0.043, 1.015, 0.418) | 2.615 | -0.743 | none |

## Wall Metrics — m_anchor_3b_candidate_0016

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.147 | 89.837 | 90.000 | 0.163 | False |
| 2 | 2-3 | 4.268 | 176.544 | 180.000 | 3.456 | False |
| 3 | 3-4 | 7.568 | 266.544 | 270.000 | 3.456 | False |
| 4 | 4-5 | 4.613 | 356.544 | 0.000 | 3.456 | False |
| 5 | 5-6 | 0.374 | 87.854 | 90.000 | 2.146 | False |
| 6 | 6-7 | 0.322 | 1.594 | 0.000 | 1.594 | True |
| 7 | 7-8 | 0.809 | 266.544 | 270.000 | 3.456 | False |
| 8 | 8-9 | 1.794 | 356.544 | 0.000 | 3.456 | False |
| 9 | 9-10 | 2.708 | 86.544 | 90.000 | 3.456 | False |
| 10 | 10-11 | 1.904 | 176.544 | 180.000 | 3.456 | False |
| 11 | 11-12 | 0.849 | 266.991 | 270.000 | 3.009 | False |
| 12 | 12-1 | 0.202 | 182.466 | 180.000 | 2.466 | True |

## Corner Metrics — m_anchor_3b_candidate_0016

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 12 | 1 | 87.371 | 2.629 | False |
| 2 | 1 | 2 | 93.293 | 3.293 | False |
| 3 | 2 | 3 | 90.000 | 0.000 | False |
| 4 | 3 | 4 | 90.000 | 0.000 | False |
| 5 | 4 | 5 | 88.690 | 1.310 | False |
| 6 | 5 | 6 | 93.740 | 3.740 | False |
| 7 | 6 | 7 | 84.950 | 5.050 | False |
| 8 | 7 | 8 | 90.000 | 0.000 | False |
| 9 | 8 | 9 | 90.000 | 0.000 | False |
| 10 | 9 | 10 | 90.000 | 0.000 | False |
| 11 | 10 | 11 | 89.554 | 0.446 | False |
| 12 | 11 | 12 | 95.475 | 5.475 | False |

## Pair 3D Coordinates — m_anchor_3b_candidate_0101

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 2 | (-0.159, -1.600, 0.409) | (-0.159, 0.919, 0.409) | 2.519 | -0.802 | none |
| 2 | 1 | (-0.141, -1.600, 6.556) | (-0.141, 1.759, 6.556) | 3.359 | 0.038 | none |
| 3 | 3 | (-4.401, -1.600, 6.813) | (-4.401, 1.759, 6.813) | 3.359 | 0.038 | none |
| 4 | 4 | (-4.857, -1.600, -0.741) | (-4.857, 1.759, -0.741) | 3.359 | 0.038 | none |
| 5 | 6 | (-0.252, -1.600, -1.020) | (-0.252, 1.759, -1.020) | 3.359 | 0.038 | none |
| 6 | 5 | (-0.228, -1.600, -0.618) | (-0.228, 1.759, -0.618) | 3.359 | 0.038 | none |
| 7 | 8 | (0.079, -1.600, -0.608) | (0.079, 1.679, -0.608) | 3.279 | -0.042 | none |
| 8 | 7 | (0.035, -1.600, -1.491) | (0.035, 1.815, -1.491) | 3.415 | 0.094 | none |
| 9 | 9 | (1.825, -1.600, -1.553) | (1.825, 1.561, -1.553) | 3.161 | -0.160 | none |
| 10 | 10 | (1.988, -1.600, 1.151) | (1.988, 1.620, 1.151) | 3.220 | -0.101 | none |
| 11 | 12 | (0.087, -1.600, 1.265) | (0.087, 1.683, 1.265) | 3.283 | -0.038 | none |
| 12 | 11 | (0.043, -1.600, 0.418) | (0.043, 1.015, 0.418) | 2.615 | -0.706 | none |

## Wall Metrics — m_anchor_3b_candidate_0101

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.147 | 89.837 | 90.000 | 0.163 | False |
| 2 | 2-3 | 4.268 | 176.544 | 180.000 | 3.456 | False |
| 3 | 3-4 | 7.568 | 266.544 | 270.000 | 3.456 | False |
| 4 | 4-5 | 4.613 | 356.544 | 0.000 | 3.456 | False |
| 5 | 5-6 | 0.403 | 86.544 | 90.000 | 3.456 | False |
| 6 | 6-7 | 0.308 | 1.853 | 0.000 | 1.853 | True |
| 7 | 7-8 | 0.884 | 267.151 | 270.000 | 2.849 | False |
| 8 | 8-9 | 1.791 | 358.020 | 0.000 | 1.980 | False |
| 9 | 9-10 | 2.708 | 86.544 | 90.000 | 3.456 | False |
| 10 | 10-11 | 1.904 | 176.544 | 180.000 | 3.456 | False |
| 11 | 11-12 | 0.849 | 266.991 | 270.000 | 3.009 | False |
| 12 | 12-1 | 0.202 | 182.466 | 180.000 | 2.466 | True |

## Corner Metrics — m_anchor_3b_candidate_0101

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 12 | 1 | 87.371 | 2.629 | False |
| 2 | 1 | 2 | 93.293 | 3.293 | False |
| 3 | 2 | 3 | 90.000 | 0.000 | False |
| 4 | 3 | 4 | 90.000 | 0.000 | False |
| 5 | 4 | 5 | 90.000 | 0.000 | False |
| 6 | 5 | 6 | 95.309 | 5.309 | False |
| 7 | 6 | 7 | 85.298 | 4.702 | False |
| 8 | 7 | 8 | 89.131 | 0.869 | False |
| 9 | 8 | 9 | 91.476 | 1.476 | False |
| 10 | 9 | 10 | 90.000 | 0.000 | False |
| 11 | 10 | 11 | 89.554 | 0.446 | False |
| 12 | 11 | 12 | 95.475 | 5.475 | False |

## Pair 3D Coordinates — m_anchor_3b_candidate_0034

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 2 | (-0.159, -1.600, 0.409) | (-0.159, 0.919, 0.409) | 2.519 | -0.810 | none |
| 2 | 1 | (-0.141, -1.600, 6.556) | (-0.141, 1.759, 6.556) | 3.359 | 0.030 | none |
| 3 | 3 | (-4.401, -1.600, 6.813) | (-4.401, 1.759, 6.813) | 3.359 | 0.030 | none |
| 4 | 4 | (-4.857, -1.600, -0.741) | (-4.857, 1.759, -0.741) | 3.359 | 0.030 | none |
| 5 | 6 | (-0.244, -1.600, -0.985) | (-0.244, 1.699, -0.985) | 3.299 | -0.030 | none |
| 6 | 5 | (-0.228, -1.600, -0.618) | (-0.228, 1.759, -0.618) | 3.359 | 0.030 | none |
| 7 | 8 | (0.083, -1.600, -0.636) | (0.083, 1.759, -0.636) | 3.359 | 0.030 | none |
| 8 | 7 | (0.034, -1.600, -1.444) | (0.034, 1.759, -1.444) | 3.359 | 0.030 | none |
| 9 | 9 | (1.825, -1.600, -1.553) | (1.825, 1.561, -1.553) | 3.161 | -0.168 | none |
| 10 | 10 | (1.988, -1.600, 1.151) | (1.988, 1.620, 1.151) | 3.220 | -0.109 | none |
| 11 | 12 | (0.087, -1.600, 1.265) | (0.087, 1.683, 1.265) | 3.283 | -0.046 | none |
| 12 | 11 | (0.043, -1.600, 0.418) | (0.043, 1.015, 0.418) | 2.615 | -0.714 | none |

## Wall Metrics — m_anchor_3b_candidate_0034

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.147 | 89.837 | 90.000 | 0.163 | False |
| 2 | 2-3 | 4.268 | 176.544 | 180.000 | 3.456 | False |
| 3 | 3-4 | 7.568 | 266.544 | 270.000 | 3.456 | False |
| 4 | 4-5 | 4.620 | 356.978 | 0.000 | 3.022 | False |
| 5 | 5-6 | 0.368 | 87.550 | 90.000 | 2.450 | True |
| 6 | 6-7 | 0.312 | 356.544 | 0.000 | 3.456 | True |
| 7 | 7-8 | 0.809 | 266.544 | 270.000 | 3.456 | False |
| 8 | 8-9 | 1.794 | 356.544 | 0.000 | 3.456 | False |
| 9 | 9-10 | 2.708 | 86.544 | 90.000 | 3.456 | False |
| 10 | 10-11 | 1.904 | 176.544 | 180.000 | 3.456 | False |
| 11 | 11-12 | 0.849 | 266.991 | 270.000 | 3.009 | False |
| 12 | 12-1 | 0.202 | 182.466 | 180.000 | 2.466 | True |

## Corner Metrics — m_anchor_3b_candidate_0034

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 12 | 1 | 87.371 | 2.629 | False |
| 2 | 1 | 2 | 93.293 | 3.293 | False |
| 3 | 2 | 3 | 90.000 | 0.000 | False |
| 4 | 3 | 4 | 89.566 | 0.434 | False |
| 5 | 4 | 5 | 89.428 | 0.572 | False |
| 6 | 5 | 6 | 88.994 | 1.006 | False |
| 7 | 6 | 7 | 90.000 | 0.000 | False |
| 8 | 7 | 8 | 90.000 | 0.000 | False |
| 9 | 8 | 9 | 90.000 | 0.000 | False |
| 10 | 9 | 10 | 90.000 | 0.000 | False |
| 11 | 10 | 11 | 89.554 | 0.446 | False |
| 12 | 11 | 12 | 95.475 | 5.475 | False |

## Pair 3D Coordinates — m_anchor_3b_candidate_0095

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 2 | (-0.159, -1.600, 0.409) | (-0.159, 0.919, 0.409) | 2.519 | -0.810 | none |
| 2 | 1 | (-0.141, -1.600, 6.556) | (-0.141, 1.759, 6.556) | 3.359 | 0.030 | none |
| 3 | 3 | (-4.401, -1.600, 6.813) | (-4.401, 1.759, 6.813) | 3.359 | 0.030 | none |
| 4 | 4 | (-4.857, -1.600, -0.741) | (-4.857, 1.759, -0.741) | 3.359 | 0.030 | none |
| 5 | 6 | (-0.244, -1.600, -0.985) | (-0.244, 1.699, -0.985) | 3.299 | -0.030 | none |
| 6 | 5 | (-0.238, -1.600, -0.645) | (-0.238, 1.838, -0.645) | 3.438 | 0.109 | none |
| 7 | 8 | (0.083, -1.600, -0.636) | (0.083, 1.759, -0.636) | 3.359 | 0.030 | none |
| 8 | 7 | (0.034, -1.600, -1.444) | (0.034, 1.759, -1.444) | 3.359 | 0.030 | none |
| 9 | 9 | (1.825, -1.600, -1.553) | (1.825, 1.561, -1.553) | 3.161 | -0.168 | none |
| 10 | 10 | (1.988, -1.600, 1.151) | (1.988, 1.620, 1.151) | 3.220 | -0.109 | none |
| 11 | 12 | (0.087, -1.600, 1.265) | (0.087, 1.683, 1.265) | 3.283 | -0.046 | none |
| 12 | 11 | (0.043, -1.600, 0.418) | (0.043, 1.015, 0.418) | 2.615 | -0.714 | none |

## Wall Metrics — m_anchor_3b_candidate_0095

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.147 | 89.837 | 90.000 | 0.163 | False |
| 2 | 2-3 | 4.268 | 176.544 | 180.000 | 3.456 | False |
| 3 | 3-4 | 7.568 | 266.544 | 270.000 | 3.456 | False |
| 4 | 4-5 | 4.620 | 356.978 | 0.000 | 3.022 | False |
| 5 | 5-6 | 0.340 | 89.078 | 90.000 | 0.922 | True |
| 6 | 6-7 | 0.322 | 1.594 | 0.000 | 1.594 | True |
| 7 | 7-8 | 0.809 | 266.544 | 270.000 | 3.456 | False |
| 8 | 8-9 | 1.794 | 356.544 | 0.000 | 3.456 | False |
| 9 | 9-10 | 2.708 | 86.544 | 90.000 | 3.456 | False |
| 10 | 10-11 | 1.904 | 176.544 | 180.000 | 3.456 | False |
| 11 | 11-12 | 0.849 | 266.991 | 270.000 | 3.009 | False |
| 12 | 12-1 | 0.202 | 182.466 | 180.000 | 2.466 | True |

## Corner Metrics — m_anchor_3b_candidate_0095

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 12 | 1 | 87.371 | 2.629 | False |
| 2 | 1 | 2 | 93.293 | 3.293 | False |
| 3 | 2 | 3 | 90.000 | 0.000 | False |
| 4 | 3 | 4 | 89.566 | 0.434 | False |
| 5 | 4 | 5 | 87.900 | 2.100 | False |
| 6 | 5 | 6 | 92.516 | 2.516 | False |
| 7 | 6 | 7 | 84.950 | 5.050 | False |
| 8 | 7 | 8 | 90.000 | 0.000 | False |
| 9 | 8 | 9 | 90.000 | 0.000 | False |
| 10 | 9 | 10 | 90.000 | 0.000 | False |
| 11 | 10 | 11 | 89.554 | 0.446 | False |
| 12 | 11 | 12 | 95.475 | 5.475 | False |

## Pair 3D Coordinates — m_anchor_3b_candidate_0047

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 2 | (-0.159, -1.600, 0.409) | (-0.159, 0.919, 0.409) | 2.519 | -0.810 | none |
| 2 | 1 | (-0.141, -1.600, 6.556) | (-0.141, 1.759, 6.556) | 3.359 | 0.030 | none |
| 3 | 3 | (-4.401, -1.600, 6.813) | (-4.401, 1.759, 6.813) | 3.359 | 0.030 | none |
| 4 | 4 | (-4.857, -1.600, -0.741) | (-4.857, 1.759, -0.741) | 3.359 | 0.030 | none |
| 5 | 6 | (-0.244, -1.600, -0.985) | (-0.244, 1.699, -0.985) | 3.299 | -0.030 | none |
| 6 | 5 | (-0.233, -1.600, -0.631) | (-0.233, 1.798, -0.631) | 3.398 | 0.069 | none |
| 7 | 8 | (0.083, -1.600, -0.636) | (0.083, 1.759, -0.636) | 3.359 | 0.030 | none |
| 8 | 7 | (0.034, -1.600, -1.444) | (0.034, 1.759, -1.444) | 3.359 | 0.030 | none |
| 9 | 9 | (1.825, -1.600, -1.553) | (1.825, 1.561, -1.553) | 3.161 | -0.168 | none |
| 10 | 10 | (1.988, -1.600, 1.151) | (1.988, 1.620, 1.151) | 3.220 | -0.109 | none |
| 11 | 12 | (0.087, -1.600, 1.265) | (0.087, 1.683, 1.265) | 3.283 | -0.046 | none |
| 12 | 11 | (0.043, -1.600, 0.418) | (0.043, 1.015, 0.418) | 2.615 | -0.714 | none |

## Wall Metrics — m_anchor_3b_candidate_0047

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.147 | 89.837 | 90.000 | 0.163 | False |
| 2 | 2-3 | 4.268 | 176.544 | 180.000 | 3.456 | False |
| 3 | 3-4 | 7.568 | 266.544 | 270.000 | 3.456 | False |
| 4 | 4-5 | 4.620 | 356.978 | 0.000 | 3.022 | False |
| 5 | 5-6 | 0.354 | 88.282 | 90.000 | 1.718 | True |
| 6 | 6-7 | 0.316 | 359.100 | 0.000 | 0.900 | True |
| 7 | 7-8 | 0.809 | 266.544 | 270.000 | 3.456 | False |
| 8 | 8-9 | 1.794 | 356.544 | 0.000 | 3.456 | False |
| 9 | 9-10 | 2.708 | 86.544 | 90.000 | 3.456 | False |
| 10 | 10-11 | 1.904 | 176.544 | 180.000 | 3.456 | False |
| 11 | 11-12 | 0.849 | 266.991 | 270.000 | 3.009 | False |
| 12 | 12-1 | 0.202 | 182.466 | 180.000 | 2.466 | True |

## Corner Metrics — m_anchor_3b_candidate_0047

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 12 | 1 | 87.371 | 2.629 | False |
| 2 | 1 | 2 | 93.293 | 3.293 | False |
| 3 | 2 | 3 | 90.000 | 0.000 | False |
| 4 | 3 | 4 | 89.566 | 0.434 | False |
| 5 | 4 | 5 | 88.697 | 1.303 | False |
| 6 | 5 | 6 | 90.818 | 0.818 | False |
| 7 | 6 | 7 | 87.444 | 2.556 | False |
| 8 | 7 | 8 | 90.000 | 0.000 | False |
| 9 | 8 | 9 | 90.000 | 0.000 | False |
| 10 | 9 | 10 | 90.000 | 0.000 | False |
| 11 | 10 | 11 | 89.554 | 0.446 | False |
| 12 | 11 | 12 | 95.475 | 5.475 | False |

## Safety Boundary

This report is expert-side, offline, local-only, sidecar, and dry-run only. It does not edit annotations, optimize coordinates, reorder corners, score workers, or create formal experiment artifacts.
