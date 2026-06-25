# Local 3D Projection Review

## Input Provenance

- Review schema: `local_3d_projection_review_m15_27_1_bridge_v1`
- Projection schema: `local_3d_projection_m15_19_v1`
- Input file: `local_review_manifest.json`
- Input SHA-256: `062307b2b52096ada705225e5df6481dd17c6ed718dc93941bdad4b46f15df62`
- Ordered-pair source: `input.ordered_pairs`
- coordinate_mode requested/effective: `ls_percent` / `ls_percent`
- W / H / CAM_H: `1024` / `512` / `1.6`
- Image source basename: `b8cTxDM8gDG_298a2386166a43c8a04e1c24433f7d15.jpg`
- Local image: `b8cTxDM8gDG_298a2386166a43c8a04e1c24433f7d15.jpg`
- Image exists: `True`
- Image SHA-256: `834bd4eff20f8779414467275b3c884a6c42e23bf2e9a6ea388aece81cdd796e`
- Viewer URL: `/tools/label_studio/vis_3d.html`
- Image URL for viewer: `/data/mp3d_layout/img_v/b8cTxDM8gDG_298a2386166a43c8a04e1c24433f7d15.jpg`
- Texture expected: `True`
- Network access used: `False`

## Human Review Summary

This is an expert-side local visual review.
Candidate previews are diagnostic only.
No automatic fix is claimed.
Texture toggle and ghost are display controls only.
No annotation patch or Label Studio writeback is produced.

### c6_5a_6_1_candidate_0001 | shift_pair2_vertical_band_down_0_25 | legacy_trial_blocked

- decision_class: `legacy_trial_blocked`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `None`
- evidence_status: `unavailable`
- evidence_warning: `candidate-specific C4 unavailable; visual comparison only`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - pair 2: top_y 10.183→10.433, bottom_y 93.279→93.529
- wall residual sum: 29.389 -> 29.132
- Preview only; this is not correctness evidence and cannot write back.

### c6_5a_6_1_candidate_0002 | shift_pair2_vertical_band_down_0_50 | legacy_trial_blocked

- decision_class: `legacy_trial_blocked`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `None`
- evidence_status: `unavailable`
- evidence_warning: `candidate-specific C4 unavailable; visual comparison only`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - pair 2: top_y 10.183→10.683, bottom_y 93.279→93.779
- wall residual sum: 29.389 -> 28.878
- Preview only; this is not correctness evidence and cannot write back.

### c6_5a_6_1_candidate_0003 | shift_pair2_vertical_band_down_0_75 | legacy_trial_blocked

- decision_class: `legacy_trial_blocked`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `None`
- evidence_status: `unavailable`
- evidence_warning: `candidate-specific C4 unavailable; visual comparison only`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - pair 2: top_y 10.183→10.933, bottom_y 93.279→94.029
- wall residual sum: 29.389 -> 28.625
- Preview only; this is not correctness evidence and cannot write back.

### c6_5a_6_1_candidate_0004 | shift_pair2_vertical_band_down_1_00 | legacy_trial_blocked

- decision_class: `legacy_trial_blocked`
- improves: `[]`
- fails_because: `[]`
- direct_ls_trial_allowed: `None`
- evidence_status: `unavailable`
- evidence_warning: `candidate-specific C4 unavailable; visual comparison only`
- primary_unresolved_edges: `[]`
- short_wall_edges_after: `[]`
- Applied coordinate changes:
  - pair 2: top_y 10.183→11.183, bottom_y 93.279→94.279
- wall residual sum: 29.389 -> 28.374
- Preview only; this is not correctness evidence and cannot write back.

## Candidate Metric Summary

| variant | wall residual sum | corner residual sum | height residual sum | vertical x residual sum | min wall | self-intersection |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| original | 29.389 | 55.635 | 0.268 | 0.611 | 2.396 | False |
| c6_5a_6_1_candidate_0001 | 29.132 | 55.409 | 0.203 | 0.611 | 2.407 | False |
| c6_5a_6_1_candidate_0002 | 28.878 | 55.183 | 0.141 | 0.611 | 2.419 | False |
| c6_5a_6_1_candidate_0003 | 28.625 | 54.956 | 0.126 | 0.611 | 2.430 | False |
| c6_5a_6_1_candidate_0004 | 28.374 | 54.730 | 0.182 | 0.611 | 2.442 | False |

## Pair 3D Coordinates — original

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 1 | (-0.775, -1.600, 4.968) | (-0.775, 0.939, 4.968) | 2.539 | 0.034 | none |
| 2 | 2 | (0.308, -1.600, -0.151) | (0.308, 1.035, -0.151) | 2.635 | 0.130 | none |
| 3 | 3 | (2.703, -1.600, -0.105) | (2.703, 0.835, -0.105) | 2.435 | -0.070 | none |
| 4 | 4 | (2.670, -1.600, 3.989) | (2.670, 0.871, 3.989) | 2.471 | -0.034 | none |

## Wall Metrics — original

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 5.233 | 281.943 | 270.000 | 11.943 | False |
| 2 | 2-3 | 2.396 | 1.108 | 0.000 | 1.108 | False |
| 3 | 3-4 | 4.094 | 90.464 | 90.000 | 0.464 | False |
| 4 | 4-1 | 3.582 | 164.125 | 180.000 | 15.875 | False |

## Corner Metrics — original

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 4 | 1 | 62.182 | 27.818 | True |
| 2 | 1 | 2 | 100.835 | 10.835 | False |
| 3 | 2 | 3 | 90.644 | 0.644 | False |
| 4 | 3 | 4 | 106.338 | 16.338 | True |

## Pair 3D Coordinates — c6_5a_6_1_candidate_0001

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 1 | (-0.775, -1.600, 4.968) | (-0.775, 0.939, 4.968) | 2.539 | 0.034 | none |
| 2 | 2 | (0.296, -1.600, -0.146) | (0.296, 0.970, -0.146) | 2.570 | 0.065 | none |
| 3 | 3 | (2.703, -1.600, -0.105) | (2.703, 0.835, -0.105) | 2.435 | -0.070 | none |
| 4 | 4 | (2.670, -1.600, 3.989) | (2.670, 0.871, 3.989) | 2.471 | -0.034 | none |

## Wall Metrics — c6_5a_6_1_candidate_0001

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 5.225 | 281.830 | 270.000 | 11.830 | False |
| 2 | 2-3 | 2.407 | 0.964 | 0.000 | 0.964 | False |
| 3 | 3-4 | 4.094 | 90.464 | 90.000 | 0.464 | False |
| 4 | 4-1 | 3.582 | 164.125 | 180.000 | 15.875 | False |

## Corner Metrics — c6_5a_6_1_candidate_0001

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 4 | 1 | 62.296 | 27.704 | True |
| 2 | 1 | 2 | 100.865 | 10.865 | False |
| 3 | 2 | 3 | 90.501 | 0.501 | False |
| 4 | 3 | 4 | 106.338 | 16.338 | True |

## Pair 3D Coordinates — c6_5a_6_1_candidate_0002

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 1 | (-0.775, -1.600, 4.968) | (-0.775, 0.939, 4.968) | 2.539 | 0.050 | none |
| 2 | 2 | (0.284, -1.600, -0.140) | (0.284, 0.908, -0.140) | 2.508 | 0.019 | none |
| 3 | 3 | (2.703, -1.600, -0.105) | (2.703, 0.835, -0.105) | 2.435 | -0.055 | none |
| 4 | 4 | (2.670, -1.600, 3.989) | (2.670, 0.871, 3.989) | 2.471 | -0.019 | none |

## Wall Metrics — c6_5a_6_1_candidate_0002

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 5.217 | 281.717 | 270.000 | 11.717 | False |
| 2 | 2-3 | 2.419 | 0.823 | 0.000 | 0.823 | False |
| 3 | 3-4 | 4.094 | 90.464 | 90.000 | 0.464 | False |
| 4 | 4-1 | 3.582 | 164.125 | 180.000 | 15.875 | False |

## Corner Metrics — c6_5a_6_1_candidate_0002

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 4 | 1 | 62.409 | 27.591 | True |
| 2 | 1 | 2 | 100.894 | 10.894 | False |
| 3 | 2 | 3 | 90.359 | 0.359 | False |
| 4 | 3 | 4 | 106.338 | 16.338 | True |

## Pair 3D Coordinates — c6_5a_6_1_candidate_0003

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 1 | (-0.775, -1.600, 4.968) | (-0.775, 0.939, 4.968) | 2.539 | 0.079 | none |
| 2 | 2 | (0.272, -1.600, -0.134) | (0.272, 0.849, -0.134) | 2.449 | -0.011 | none |
| 3 | 3 | (2.703, -1.600, -0.105) | (2.703, 0.835, -0.105) | 2.435 | -0.025 | none |
| 4 | 4 | (2.670, -1.600, 3.989) | (2.670, 0.871, 3.989) | 2.471 | 0.011 | none |

## Wall Metrics — c6_5a_6_1_candidate_0003

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 5.209 | 281.604 | 270.000 | 11.604 | False |
| 2 | 2-3 | 2.430 | 0.683 | 0.000 | 0.683 | False |
| 3 | 3-4 | 4.094 | 90.464 | 90.000 | 0.464 | False |
| 4 | 4-1 | 3.582 | 164.125 | 180.000 | 15.875 | False |

## Corner Metrics — c6_5a_6_1_candidate_0003

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 4 | 1 | 62.522 | 27.478 | True |
| 2 | 1 | 2 | 100.920 | 10.920 | False |
| 3 | 2 | 3 | 90.219 | 0.219 | False |
| 4 | 3 | 4 | 106.338 | 16.338 | True |

## Pair 3D Coordinates — c6_5a_6_1_candidate_0004

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 1 | (-0.775, -1.600, 4.968) | (-0.775, 0.939, 4.968) | 2.539 | 0.086 | none |
| 2 | 2 | (0.261, -1.600, -0.128) | (0.261, 0.793, -0.128) | 2.393 | -0.060 | none |
| 3 | 3 | (2.703, -1.600, -0.105) | (2.703, 0.835, -0.105) | 2.435 | -0.018 | none |
| 4 | 4 | (2.670, -1.600, 3.989) | (2.670, 0.871, 3.989) | 2.471 | 0.018 | none |

## Wall Metrics — c6_5a_6_1_candidate_0004

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 5.201 | 281.490 | 270.000 | 11.490 | False |
| 2 | 2-3 | 2.442 | 0.545 | 0.000 | 0.545 | False |
| 3 | 3-4 | 4.094 | 90.464 | 90.000 | 0.464 | False |
| 4 | 4-1 | 3.582 | 164.125 | 180.000 | 15.875 | False |

## Corner Metrics — c6_5a_6_1_candidate_0004

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 4 | 1 | 62.635 | 27.365 | True |
| 2 | 1 | 2 | 100.945 | 10.945 | False |
| 3 | 2 | 3 | 90.082 | 0.082 | False |
| 4 | 3 | 4 | 106.338 | 16.338 | True |

## Safety Boundary

This report is expert-side, offline, local-only, sidecar, and dry-run only. It does not edit annotations, optimize coordinates, reorder corners, score workers, or create formal experiment artifacts.
