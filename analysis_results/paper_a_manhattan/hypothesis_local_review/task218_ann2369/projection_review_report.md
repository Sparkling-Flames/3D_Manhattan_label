# Local 3D Projection Review

## Input Provenance

- Review schema: `local_3d_projection_review_m15_27_1_bridge_v1`
- Projection schema: `local_3d_projection_m15_19_v1`
- Input file: `task218_ann2369_m1516_stabilized_input.json`
- Input SHA-256: `eeb4bcd6b6546b61069904b03e4e28cddd7fe15ea76832194b270e0085669541`
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

This is an expert-side local visual review.
Candidate previews are diagnostic only.
No automatic fix is claimed.
Texture toggle and ghost are display controls only.
No annotation patch or Label Studio writeback is produced.

No eligible executable candidate was supplied. Review covers original geometry only.

## Candidate Metric Summary

| variant | wall residual sum | corner residual sum | height residual sum | vertical x residual sum | min wall | self-intersection |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| original | 32.302 | 61.802 | 1.470 | 0.560 | 1.078 | False |

## Pair 3D Coordinates — original

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 2 | (-0.170, -1.600, 0.419) | (-0.170, 0.815, 0.419) | 2.415 | -0.944 | none |
| 2 | 1 | (-0.338, -1.600, 7.293) | (-0.338, 1.759, 7.293) | 3.359 | 0.000 | none |
| 3 | 3 | (-4.617, -1.600, 7.293) | (-4.617, 1.759, 7.293) | 3.359 | 0.000 | none |
| 4 | 4 | (-4.616, -1.600, -0.797) | (-4.616, 1.759, -0.797) | 3.359 | -0.000 | none |
| 5 | 6 | (0.059, -1.600, -0.797) | (0.059, 1.759, -0.797) | 3.359 | 0.000 | none |
| 6 | 5 | (0.059, -1.600, -1.875) | (0.059, 1.759, -1.875) | 3.359 | 0.000 | none |
| 7 | 7 | (1.897, -1.600, -1.565) | (1.897, 1.495, -1.565) | 3.095 | -0.264 | none |
| 8 | 8 | (1.919, -1.600, 1.215) | (1.919, 1.498, 1.215) | 3.098 | -0.261 | none |

## Wall Metrics — original

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.876 | 91.401 | 90.000 | 1.401 | False |
| 2 | 2-3 | 4.279 | 179.991 | 180.000 | 0.009 | False |
| 3 | 3-4 | 8.091 | 270.004 | 270.000 | 0.004 | False |
| 4 | 4-5 | 4.675 | 359.998 | 0.000 | 0.002 | False |
| 5 | 5-6 | 1.078 | 270.000 | 270.000 | 0.000 | False |
| 6 | 6-7 | 1.864 | 9.559 | 0.000 | 9.559 | False |
| 7 | 7-8 | 2.781 | 89.535 | 90.000 | 0.465 | False |
| 8 | 8-1 | 2.236 | 200.863 | 180.000 | 20.863 | False |

## Corner Metrics — original

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 8 | 1 | 70.538 | 19.462 | True |
| 2 | 1 | 2 | 91.410 | 1.410 | False |
| 3 | 2 | 3 | 89.988 | 0.012 | False |
| 4 | 3 | 4 | 90.006 | 0.006 | False |
| 5 | 4 | 5 | 90.002 | 0.002 | False |
| 6 | 5 | 6 | 80.441 | 9.559 | False |
| 7 | 6 | 7 | 100.023 | 10.023 | False |
| 8 | 7 | 8 | 68.672 | 21.328 | True |

## Safety Boundary

This report is expert-side, offline, local-only, sidecar, and dry-run only. It does not edit annotations, optimize coordinates, reorder corners, score workers, or create formal experiment artifacts.
