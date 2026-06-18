# Local 3D Projection Review

## Input Provenance

- Review schema: `local_3d_projection_review_m15_19_2_v1`
- Projection schema: `local_3d_projection_m15_19_v1`
- Input file: `task238_ann2389_m1516_stabilized_input.json`
- Input SHA-256: `31c093cc1148c65b7e2235b8a4058b7070b8038d674c2ba00a9622e19c3d8fc3`
- Ordered-pair source: `build_single_image_assist.ordered_pairs`
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

Local-only diagnostic. No annotation changes are produced.

No eligible align-then-translate candidate was supplied. Review covers original geometry only.

## Candidate Metric Summary

| variant | wall residual sum | corner residual sum | height residual sum | vertical x residual sum | min wall | self-intersection |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| original | 23.154 | 39.239 | 0.637 | 0.000 | 0.889 | False |

## Pair 3D Coordinates — original

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | 1 | (-0.775, -1.600, 4.968) | (-0.775, 0.939, 4.968) | 2.539 | 0.002 | none |
| 2 | 2 | (-0.526, -1.600, -1.627) | (-0.526, 0.935, -1.627) | 2.535 | -0.002 | none |
| 3 | 3 | (0.363, -1.600, -1.618) | (0.363, 0.940, -1.618) | 2.540 | 0.003 | none |
| 4 | 4 | (0.316, -1.600, -0.196) | (0.316, 1.399, -0.196) | 2.999 | 0.462 | none |
| 5 | 5 | (2.703, -1.600, -0.105) | (2.703, 0.835, -0.105) | 2.435 | -0.102 | none |
| 6 | 6 | (2.670, -1.600, 3.989) | (2.670, 0.871, 3.989) | 2.471 | -0.066 | none |

## Wall Metrics — original

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 6.600 | 272.165 | 270.000 | 2.165 | False |
| 2 | 2-3 | 0.889 | 0.599 | 0.000 | 0.599 | False |
| 3 | 3-4 | 1.422 | 91.874 | 90.000 | 1.874 | False |
| 4 | 4-5 | 2.389 | 2.179 | 0.000 | 2.179 | False |
| 5 | 5-6 | 4.094 | 90.464 | 90.000 | 0.464 | False |
| 6 | 6-1 | 3.582 | 164.125 | 180.000 | 15.875 | False |

## Corner Metrics — original

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 6 | 1 | 71.961 | 18.039 | True |
| 2 | 1 | 2 | 91.566 | 1.566 | False |
| 3 | 2 | 3 | 88.724 | 1.276 | False |
| 4 | 3 | 4 | 90.304 | 0.304 | False |
| 5 | 4 | 5 | 91.715 | 1.715 | False |
| 6 | 5 | 6 | 106.338 | 16.338 | True |

## Safety Boundary

This report is expert-side, offline, local-only, sidecar, and dry-run only. It does not edit annotations, optimize coordinates, reorder corners, score workers, or create formal experiment artifacts.
