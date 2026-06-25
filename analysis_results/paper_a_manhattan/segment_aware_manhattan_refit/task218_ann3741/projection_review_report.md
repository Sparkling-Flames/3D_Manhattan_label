# Local 3D Projection Review

## Input Provenance

- Review schema: `local_3d_projection_review_m15_27_1_bridge_v1`
- Projection schema: `local_3d_projection_m15_19_v1`
- Input file: `_review_input.json`
- Input SHA-256: `180789b0620ba11a07834762be66dd3a96a5da2ebff085035bc3248284ba7abf`
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

### anchor_34_plus_910 | segment_aware_manhattan_wall_line_refit | review

- decision_class: `None`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `None`
- evidence_status: `None`
- evidence_warning: `None`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - pair 1: no numeric change
  - pair 2: no numeric change
  - pair 3: no numeric change
  - pair 4: no numeric change
  - pair 5: no numeric change
  - pair 6: no numeric change
  - pair 7: no numeric change
  - pair 8: no numeric change
  - pair 9: no numeric change
  - pair 10: no numeric change
  - pair 11: no numeric change
  - pair 12: no numeric change
- wall residual sum: 93.464 -> 1.825
- Preview only; this is not correctness evidence and cannot write back.

## Candidate Metric Summary

| variant | wall residual sum | corner residual sum | height residual sum | vertical x residual sum | min wall | self-intersection |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| original | 93.464 | 173.124 | 2.258 | 0.000 | 0.087 | False |
| anchor_34_plus_910 | 1.825 | 0.000 | 0.000 | 0.000 | 0.170 | False |

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

## Pair 3D Coordinates — anchor_34_plus_910

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | None | (-0.187, -1.600, 0.430) | (-0.187, 1.759, 0.430) | 3.359 | -0.000 | none |
| 2 | None | (-0.169, -1.600, 7.185) | (-0.169, 1.759, 7.185) | 3.359 | -0.000 | none |
| 3 | None | (-4.606, -1.600, 7.196) | (-4.606, 1.759, 7.196) | 3.359 | 0.000 | none |
| 4 | None | (-4.627, -1.600, -0.784) | (-4.627, 1.759, -0.784) | 3.359 | -0.000 | none |
| 5 | None | (-0.231, -1.600, -0.796) | (-0.231, 1.759, -0.796) | 3.359 | -0.000 | none |
| 6 | None | (-0.230, -1.600, -0.625) | (-0.230, 1.759, -0.625) | 3.359 | 0.000 | none |
| 7 | None | (0.061, -1.600, -0.626) | (0.061, 1.759, -0.626) | 3.359 | 0.000 | none |
| 8 | None | (0.058, -1.600, -1.525) | (0.058, 1.759, -1.525) | 3.359 | 0.000 | none |
| 9 | None | (1.905, -1.600, -1.530) | (1.905, 1.759, -1.530) | 3.359 | -0.000 | none |
| 10 | None | (1.912, -1.600, 1.190) | (1.912, 1.759, 1.190) | 3.359 | 0.000 | none |
| 11 | None | (0.060, -1.600, 1.195) | (0.060, 1.759, 1.195) | 3.359 | 0.000 | none |
| 12 | None | (0.058, -1.600, 0.429) | (0.058, 1.759, 0.429) | 3.359 | -0.000 | none |

## Wall Metrics — anchor_34_plus_910

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.755 | 89.848 | 90.000 | 0.152 | False |
| 2 | 2-3 | 4.436 | 179.848 | 180.000 | 0.152 | False |
| 3 | 3-4 | 7.981 | 269.848 | 270.000 | 0.152 | False |
| 4 | 4-5 | 4.396 | 359.848 | 0.000 | 0.152 | False |
| 5 | 5-6 | 0.170 | 89.848 | 90.000 | 0.152 | True |
| 6 | 6-7 | 0.291 | 359.848 | 0.000 | 0.152 | True |
| 7 | 7-8 | 0.899 | 269.848 | 270.000 | 0.152 | False |
| 8 | 8-9 | 1.846 | 359.848 | 0.000 | 0.152 | False |
| 9 | 9-10 | 2.721 | 89.848 | 90.000 | 0.152 | False |
| 10 | 10-11 | 1.851 | 179.848 | 180.000 | 0.152 | False |
| 11 | 11-12 | 0.766 | 269.848 | 270.000 | 0.152 | False |
| 12 | 12-1 | 0.246 | 179.848 | 180.000 | 0.152 | True |

## Corner Metrics — anchor_34_plus_910

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
