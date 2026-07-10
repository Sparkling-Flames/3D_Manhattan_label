# Local 3D Projection Review

## Input Provenance

- Review schema: `local_3d_projection_review_m15_27_1_bridge_v1`
- Projection schema: `local_3d_projection_m15_19_v1`
- Input file: `hypothesis_review_bridge_manifest.json`
- Input SHA-256: `36eacf1cc2d76f1974bd383b8936193b16386117d308ecaba8b538e76d42255f`
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

### m_anchor_4_1_1_c_0487 | m_anchor_4_1_1_staged_micro_compensation_probe | neutral_geometry_tradeoff

- decision_class: `neutral_geometry_tradeoff`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `False`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - source pair 4 (solver position 4): no numeric change
  - source pair 9 (solver position 9): no numeric change
  - source pair 10 (solver position 10): no numeric change
- wall residual sum: 36.741 -> 34.566
- Preview only; this is not correctness evidence and cannot write back.

### m_anchor_4_1_1_c_1136 | m_anchor_4_1_1_staged_micro_compensation_probe | neutral_geometry_tradeoff

- decision_class: `neutral_geometry_tradeoff`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `False`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - source pair 4 (solver position 4): no numeric change
  - source pair 7 (solver position 8): no numeric change
  - source pair 9 (solver position 9): no numeric change
  - source pair 10 (solver position 10): no numeric change
- wall residual sum: 36.741 -> 32.827
- Preview only; this is not correctness evidence and cannot write back.

### m_anchor_4_1_1_c_1192 | m_anchor_4_1_1_staged_micro_compensation_probe | neutral_geometry_tradeoff

- decision_class: `neutral_geometry_tradeoff`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `False`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - source pair 1 (solver position 2): no numeric change
  - source pair 4 (solver position 4): no numeric change
  - source pair 7 (solver position 8): no numeric change
  - source pair 9 (solver position 9): no numeric change
  - source pair 10 (solver position 10): no numeric change
- wall residual sum: 36.741 -> 32.716
- Preview only; this is not correctness evidence and cannot write back.

### m_anchor_4_1_1_a_0106 | m_anchor_4_1_1_staged_micro_compensation_probe | neutral_geometry_tradeoff

- decision_class: `neutral_geometry_tradeoff`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `False`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - source pair 1 (solver position 2): no numeric change
  - source pair 4 (solver position 4): no numeric change
  - source pair 7 (solver position 8): no numeric change
  - source pair 9 (solver position 9): no numeric change
  - source pair 10 (solver position 10): no numeric change
- wall residual sum: 36.741 -> 34.058
- Preview only; this is not correctness evidence and cannot write back.

### m_anchor_4_1_1_c_1071 | m_anchor_4_1_1_staged_micro_compensation_probe | neutral_geometry_tradeoff

- decision_class: `neutral_geometry_tradeoff`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `False`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - source pair 3 (solver position 3): no numeric change
  - source pair 4 (solver position 4): no numeric change
  - source pair 9 (solver position 9): no numeric change
  - source pair 10 (solver position 10): no numeric change
- wall residual sum: 36.741 -> 31.021
- Preview only; this is not correctness evidence and cannot write back.

## Candidate Metric Summary

| variant | wall residual sum | corner residual sum | height residual sum | vertical x residual sum | min wall | self-intersection |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| original | 36.741 | 11.843 | 1.995 | 0.000 | 0.202 | False |
| m_anchor_4_1_1_c_0487 | 34.566 | 15.370 | 1.995 | 0.000 | 0.202 | False |
| m_anchor_4_1_1_c_1136 | 32.827 | 16.062 | 2.051 | 0.000 | 0.202 | False |
| m_anchor_4_1_1_c_1192 | 32.716 | 16.062 | 2.051 | 0.000 | 0.202 | False |
| m_anchor_4_1_1_a_0106 | 34.058 | 12.593 | 2.049 | 0.000 | 0.202 | False |
| m_anchor_4_1_1_c_1071 | 31.021 | 15.370 | 1.995 | 0.000 | 0.202 | False |

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

## Pair 3D Coordinates — m_anchor_4_1_1_c_0487

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | None | (-0.159, -1.600, 0.409) | (-0.159, 0.919, 0.409) | 2.519 | -0.840 | none |
| 2 | 1 | (-0.141, -1.600, 6.556) | (-0.141, 1.759, 6.556) | 3.359 | 0.000 | none |
| 3 | 3 | (-4.401, -1.600, 6.813) | (-4.401, 1.759, 6.813) | 3.359 | 0.000 | none |
| 4 | 4 | (-4.860, -1.600, -0.726) | (-4.860, 1.759, -0.726) | 3.359 | 0.000 | none |
| 5 | 6 | (-0.252, -1.600, -1.020) | (-0.252, 1.759, -1.020) | 3.359 | 0.000 | none |
| 6 | 5 | (-0.228, -1.600, -0.618) | (-0.228, 1.759, -0.618) | 3.359 | 0.000 | none |
| 7 | 8 | (0.083, -1.600, -0.636) | (0.083, 1.759, -0.636) | 3.359 | -0.000 | none |
| 8 | 7 | (0.034, -1.600, -1.444) | (0.034, 1.759, -1.444) | 3.359 | 0.000 | none |
| 9 | 9 | (1.820, -1.600, -1.558) | (1.820, 1.561, -1.558) | 3.161 | -0.197 | none |
| 10 | 10 | (1.951, -1.600, 1.212) | (1.951, 1.620, 1.212) | 3.220 | -0.138 | none |
| 11 | 12 | (0.087, -1.600, 1.265) | (0.087, 1.683, 1.265) | 3.283 | -0.076 | none |
| 12 | None | (0.043, -1.600, 0.418) | (0.043, 1.015, 0.418) | 2.615 | -0.743 | none |

## Wall Metrics — m_anchor_4_1_1_c_0487

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.147 | 89.837 | 90.000 | 0.163 | False |
| 2 | 2-3 | 4.268 | 176.544 | 180.000 | 3.456 | False |
| 3 | 3-4 | 7.553 | 266.520 | 270.000 | 3.480 | False |
| 4 | 4-5 | 4.617 | 356.357 | 0.000 | 3.643 | False |
| 5 | 5-6 | 0.403 | 86.544 | 90.000 | 3.456 | False |
| 6 | 6-7 | 0.312 | 356.544 | 0.000 | 3.456 | True |
| 7 | 7-8 | 0.809 | 266.544 | 270.000 | 3.456 | False |
| 8 | 8-9 | 1.789 | 356.352 | 0.000 | 3.648 | False |
| 9 | 9-10 | 2.774 | 87.293 | 90.000 | 2.707 | False |
| 10 | 10-11 | 1.864 | 178.374 | 180.000 | 1.626 | False |
| 11 | 11-12 | 0.849 | 266.991 | 270.000 | 3.009 | False |
| 12 | 12-1 | 0.202 | 182.466 | 180.000 | 2.466 | True |

## Corner Metrics — m_anchor_4_1_1_c_0487

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 12 | 1 | 87.371 | 2.629 | False |
| 2 | 1 | 2 | 93.293 | 3.293 | False |
| 3 | 2 | 3 | 90.024 | 0.024 | False |
| 4 | 3 | 4 | 90.163 | 0.163 | False |
| 5 | 4 | 5 | 89.813 | 0.187 | False |
| 6 | 5 | 6 | 90.000 | 0.000 | False |
| 7 | 6 | 7 | 90.000 | 0.000 | False |
| 8 | 7 | 8 | 90.192 | 0.192 | False |
| 9 | 8 | 9 | 89.059 | 0.941 | False |
| 10 | 9 | 10 | 88.919 | 1.081 | False |
| 11 | 10 | 11 | 91.383 | 1.383 | False |
| 12 | 11 | 12 | 95.475 | 5.475 | False |

## Pair 3D Coordinates — m_anchor_4_1_1_c_1136

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | None | (-0.159, -1.600, 0.409) | (-0.159, 0.919, 0.409) | 2.519 | -0.840 | none |
| 2 | 1 | (-0.141, -1.600, 6.556) | (-0.141, 1.759, 6.556) | 3.359 | 0.000 | none |
| 3 | 3 | (-4.401, -1.600, 6.813) | (-4.401, 1.759, 6.813) | 3.359 | 0.000 | none |
| 4 | 4 | (-4.860, -1.600, -0.726) | (-4.860, 1.759, -0.726) | 3.359 | 0.000 | none |
| 5 | 6 | (-0.252, -1.600, -1.020) | (-0.252, 1.759, -1.020) | 3.359 | 0.000 | none |
| 6 | 5 | (-0.228, -1.600, -0.618) | (-0.228, 1.759, -0.618) | 3.359 | 0.000 | none |
| 7 | 8 | (0.083, -1.600, -0.636) | (0.083, 1.759, -0.636) | 3.359 | -0.000 | none |
| 8 | 7 | (0.035, -1.600, -1.491) | (0.035, 1.815, -1.491) | 3.415 | 0.056 | none |
| 9 | 9 | (1.820, -1.600, -1.558) | (1.820, 1.561, -1.558) | 3.161 | -0.197 | none |
| 10 | 10 | (1.951, -1.600, 1.212) | (1.951, 1.620, 1.212) | 3.220 | -0.138 | none |
| 11 | 12 | (0.087, -1.600, 1.265) | (0.087, 1.683, 1.265) | 3.283 | -0.076 | none |
| 12 | None | (0.043, -1.600, 0.418) | (0.043, 1.015, 0.418) | 2.615 | -0.743 | none |

## Wall Metrics — m_anchor_4_1_1_c_1136

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.147 | 89.837 | 90.000 | 0.163 | False |
| 2 | 2-3 | 4.268 | 176.544 | 180.000 | 3.456 | False |
| 3 | 3-4 | 7.553 | 266.520 | 270.000 | 3.480 | False |
| 4 | 4-5 | 4.617 | 356.357 | 0.000 | 3.643 | False |
| 5 | 5-6 | 0.403 | 86.544 | 90.000 | 3.456 | False |
| 6 | 6-7 | 0.312 | 356.544 | 0.000 | 3.456 | True |
| 7 | 7-8 | 0.856 | 266.804 | 270.000 | 3.196 | False |
| 8 | 8-9 | 1.786 | 357.831 | 0.000 | 2.169 | False |
| 9 | 9-10 | 2.774 | 87.293 | 90.000 | 2.707 | False |
| 10 | 10-11 | 1.864 | 178.374 | 180.000 | 1.626 | False |
| 11 | 11-12 | 0.849 | 266.991 | 270.000 | 3.009 | False |
| 12 | 12-1 | 0.202 | 182.466 | 180.000 | 2.466 | True |

## Corner Metrics — m_anchor_4_1_1_c_1136

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 12 | 1 | 87.371 | 2.629 | False |
| 2 | 1 | 2 | 93.293 | 3.293 | False |
| 3 | 2 | 3 | 90.024 | 0.024 | False |
| 4 | 3 | 4 | 90.163 | 0.163 | False |
| 5 | 4 | 5 | 89.813 | 0.187 | False |
| 6 | 5 | 6 | 90.000 | 0.000 | False |
| 7 | 6 | 7 | 90.260 | 0.260 | False |
| 8 | 7 | 8 | 88.973 | 1.027 | False |
| 9 | 8 | 9 | 90.538 | 0.538 | False |
| 10 | 9 | 10 | 88.919 | 1.081 | False |
| 11 | 10 | 11 | 91.383 | 1.383 | False |
| 12 | 11 | 12 | 95.475 | 5.475 | False |

## Pair 3D Coordinates — m_anchor_4_1_1_c_1192

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | None | (-0.159, -1.600, 0.409) | (-0.159, 0.919, 0.409) | 2.519 | -0.840 | none |
| 2 | 1 | (-0.162, -1.600, 6.555) | (-0.162, 1.759, 6.555) | 3.359 | 0.000 | none |
| 3 | 3 | (-4.401, -1.600, 6.813) | (-4.401, 1.759, 6.813) | 3.359 | 0.000 | none |
| 4 | 4 | (-4.860, -1.600, -0.726) | (-4.860, 1.759, -0.726) | 3.359 | 0.000 | none |
| 5 | 6 | (-0.252, -1.600, -1.020) | (-0.252, 1.759, -1.020) | 3.359 | 0.000 | none |
| 6 | 5 | (-0.228, -1.600, -0.618) | (-0.228, 1.759, -0.618) | 3.359 | 0.000 | none |
| 7 | 8 | (0.083, -1.600, -0.636) | (0.083, 1.759, -0.636) | 3.359 | -0.000 | none |
| 8 | 7 | (0.035, -1.600, -1.491) | (0.035, 1.815, -1.491) | 3.415 | 0.056 | none |
| 9 | 9 | (1.820, -1.600, -1.558) | (1.820, 1.561, -1.558) | 3.161 | -0.197 | none |
| 10 | 10 | (1.951, -1.600, 1.212) | (1.951, 1.620, 1.212) | 3.220 | -0.138 | none |
| 11 | 12 | (0.087, -1.600, 1.265) | (0.087, 1.683, 1.265) | 3.283 | -0.076 | none |
| 12 | None | (0.043, -1.600, 0.418) | (0.043, 1.015, 0.418) | 2.615 | -0.743 | none |

## Wall Metrics — m_anchor_4_1_1_c_1192

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.146 | 90.029 | 90.000 | 0.029 | False |
| 2 | 2-3 | 4.247 | 176.521 | 180.000 | 3.479 | False |
| 3 | 3-4 | 7.553 | 266.520 | 270.000 | 3.480 | False |
| 4 | 4-5 | 4.617 | 356.357 | 0.000 | 3.643 | False |
| 5 | 5-6 | 0.403 | 86.544 | 90.000 | 3.456 | False |
| 6 | 6-7 | 0.312 | 356.544 | 0.000 | 3.456 | True |
| 7 | 7-8 | 0.856 | 266.804 | 270.000 | 3.196 | False |
| 8 | 8-9 | 1.786 | 357.831 | 0.000 | 2.169 | False |
| 9 | 9-10 | 2.774 | 87.293 | 90.000 | 2.707 | False |
| 10 | 10-11 | 1.864 | 178.374 | 180.000 | 1.626 | False |
| 11 | 11-12 | 0.849 | 266.991 | 270.000 | 3.009 | False |
| 12 | 12-1 | 0.202 | 182.466 | 180.000 | 2.466 | True |

## Corner Metrics — m_anchor_4_1_1_c_1192

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 12 | 1 | 87.563 | 2.437 | False |
| 2 | 1 | 2 | 93.508 | 3.508 | False |
| 3 | 2 | 3 | 90.001 | 0.001 | False |
| 4 | 3 | 4 | 90.163 | 0.163 | False |
| 5 | 4 | 5 | 89.813 | 0.187 | False |
| 6 | 5 | 6 | 90.000 | 0.000 | False |
| 7 | 6 | 7 | 90.260 | 0.260 | False |
| 8 | 7 | 8 | 88.973 | 1.027 | False |
| 9 | 8 | 9 | 90.538 | 0.538 | False |
| 10 | 9 | 10 | 88.919 | 1.081 | False |
| 11 | 10 | 11 | 91.383 | 1.383 | False |
| 12 | 11 | 12 | 95.475 | 5.475 | False |

## Pair 3D Coordinates — m_anchor_4_1_1_a_0106

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | None | (-0.159, -1.600, 0.409) | (-0.159, 0.919, 0.409) | 2.519 | -0.840 | none |
| 2 | 1 | (-0.144, -1.600, 6.693) | (-0.144, 1.795, 6.693) | 3.395 | 0.037 | none |
| 3 | 3 | (-4.401, -1.600, 6.813) | (-4.401, 1.759, 6.813) | 3.359 | 0.000 | none |
| 4 | 4 | (-4.860, -1.600, -0.726) | (-4.860, 1.759, -0.726) | 3.359 | 0.000 | none |
| 5 | 6 | (-0.252, -1.600, -1.020) | (-0.252, 1.759, -1.020) | 3.359 | 0.000 | none |
| 6 | 5 | (-0.228, -1.600, -0.618) | (-0.228, 1.759, -0.618) | 3.359 | 0.000 | none |
| 7 | 8 | (0.083, -1.600, -0.636) | (0.083, 1.759, -0.636) | 3.359 | -0.000 | none |
| 8 | 7 | (0.035, -1.600, -1.458) | (0.035, 1.775, -1.458) | 3.375 | 0.017 | none |
| 9 | 9 | (1.820, -1.600, -1.558) | (1.820, 1.561, -1.558) | 3.161 | -0.197 | none |
| 10 | 10 | (1.977, -1.600, 1.169) | (1.977, 1.620, 1.169) | 3.220 | -0.138 | none |
| 11 | 12 | (0.087, -1.600, 1.265) | (0.087, 1.683, 1.265) | 3.283 | -0.076 | none |
| 12 | None | (0.043, -1.600, 0.418) | (0.043, 1.015, 0.418) | 2.615 | -0.743 | none |

## Wall Metrics — m_anchor_4_1_1_a_0106

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.284 | 89.868 | 90.000 | 0.132 | False |
| 2 | 2-3 | 4.259 | 178.379 | 180.000 | 1.621 | False |
| 3 | 3-4 | 7.553 | 266.520 | 270.000 | 3.480 | False |
| 4 | 4-5 | 4.617 | 356.357 | 0.000 | 3.643 | False |
| 5 | 5-6 | 0.403 | 86.544 | 90.000 | 3.456 | False |
| 6 | 6-7 | 0.312 | 356.544 | 0.000 | 3.456 | True |
| 7 | 7-8 | 0.823 | 266.624 | 270.000 | 3.376 | False |
| 8 | 8-9 | 1.788 | 356.790 | 0.000 | 3.210 | False |
| 9 | 9-10 | 2.732 | 86.702 | 90.000 | 3.298 | False |
| 10 | 10-11 | 1.892 | 177.089 | 180.000 | 2.911 | False |
| 11 | 11-12 | 0.849 | 266.991 | 270.000 | 3.009 | False |
| 12 | 12-1 | 0.202 | 182.466 | 180.000 | 2.466 | True |

## Corner Metrics — m_anchor_4_1_1_a_0106

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 12 | 1 | 87.402 | 2.598 | False |
| 2 | 1 | 2 | 91.489 | 1.489 | False |
| 3 | 2 | 3 | 91.859 | 1.859 | False |
| 4 | 3 | 4 | 90.163 | 0.163 | False |
| 5 | 4 | 5 | 89.813 | 0.187 | False |
| 6 | 5 | 6 | 90.000 | 0.000 | False |
| 7 | 6 | 7 | 90.080 | 0.080 | False |
| 8 | 7 | 8 | 89.834 | 0.166 | False |
| 9 | 8 | 9 | 90.089 | 0.089 | False |
| 10 | 9 | 10 | 89.613 | 0.387 | False |
| 11 | 10 | 11 | 90.098 | 0.098 | False |
| 12 | 11 | 12 | 95.475 | 5.475 | False |

## Pair 3D Coordinates — m_anchor_4_1_1_c_1071

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | None | (-0.159, -1.600, 0.409) | (-0.159, 0.919, 0.409) | 2.519 | -0.840 | none |
| 2 | 1 | (-0.141, -1.600, 6.556) | (-0.141, 1.759, 6.556) | 3.359 | 0.000 | none |
| 3 | 3 | (-4.613, -1.600, 6.672) | (-4.613, 1.759, 6.672) | 3.359 | 0.000 | none |
| 4 | 4 | (-4.860, -1.600, -0.726) | (-4.860, 1.759, -0.726) | 3.359 | 0.000 | none |
| 5 | 6 | (-0.252, -1.600, -1.020) | (-0.252, 1.759, -1.020) | 3.359 | 0.000 | none |
| 6 | 5 | (-0.228, -1.600, -0.618) | (-0.228, 1.759, -0.618) | 3.359 | 0.000 | none |
| 7 | 8 | (0.083, -1.600, -0.636) | (0.083, 1.759, -0.636) | 3.359 | -0.000 | none |
| 8 | 7 | (0.034, -1.600, -1.444) | (0.034, 1.759, -1.444) | 3.359 | 0.000 | none |
| 9 | 9 | (1.820, -1.600, -1.558) | (1.820, 1.561, -1.558) | 3.161 | -0.197 | none |
| 10 | 10 | (1.951, -1.600, 1.212) | (1.951, 1.620, 1.212) | 3.220 | -0.138 | none |
| 11 | 12 | (0.087, -1.600, 1.265) | (0.087, 1.683, 1.265) | 3.283 | -0.076 | none |
| 12 | None | (0.043, -1.600, 0.418) | (0.043, 1.015, 0.418) | 2.615 | -0.743 | none |

## Wall Metrics — m_anchor_4_1_1_c_1071

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.147 | 89.837 | 90.000 | 0.163 | False |
| 2 | 2-3 | 4.473 | 178.519 | 180.000 | 1.481 | False |
| 3 | 3-4 | 7.402 | 268.090 | 270.000 | 1.910 | False |
| 4 | 4-5 | 4.617 | 356.357 | 0.000 | 3.643 | False |
| 5 | 5-6 | 0.403 | 86.544 | 90.000 | 3.456 | False |
| 6 | 6-7 | 0.312 | 356.544 | 0.000 | 3.456 | True |
| 7 | 7-8 | 0.809 | 266.544 | 270.000 | 3.456 | False |
| 8 | 8-9 | 1.789 | 356.352 | 0.000 | 3.648 | False |
| 9 | 9-10 | 2.774 | 87.293 | 90.000 | 2.707 | False |
| 10 | 10-11 | 1.864 | 178.374 | 180.000 | 1.626 | False |
| 11 | 11-12 | 0.849 | 266.991 | 270.000 | 3.009 | False |
| 12 | 12-1 | 0.202 | 182.466 | 180.000 | 2.466 | True |

## Corner Metrics — m_anchor_4_1_1_c_1071

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 12 | 1 | 87.371 | 2.629 | False |
| 2 | 1 | 2 | 91.319 | 1.319 | False |
| 3 | 2 | 3 | 90.428 | 0.428 | False |
| 4 | 3 | 4 | 91.733 | 1.733 | False |
| 5 | 4 | 5 | 89.813 | 0.187 | False |
| 6 | 5 | 6 | 90.000 | 0.000 | False |
| 7 | 6 | 7 | 90.000 | 0.000 | False |
| 8 | 7 | 8 | 90.192 | 0.192 | False |
| 9 | 8 | 9 | 89.059 | 0.941 | False |
| 10 | 9 | 10 | 88.919 | 1.081 | False |
| 11 | 10 | 11 | 91.383 | 1.383 | False |
| 12 | 11 | 12 | 95.475 | 5.475 | False |

## Safety Boundary

This report is expert-side, offline, local-only, sidecar, and dry-run only. It does not edit annotations, optimize coordinates, reorder corners, score workers, or create formal experiment artifacts.
