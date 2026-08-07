# Local 3D Projection Review

## Input Provenance

- Review schema: `local_3d_projection_review_m15_27_1_bridge_v1`
- Projection schema: `local_3d_projection_m15_19_v1`
- Input file: `3416_public_gt_m413_input.json`
- Input SHA-256: `5fb4c843f4064019a8e7cb919f67ebb2089e53da3d0dab8a10acb9d7e65041ff`
- Ordered-pair source: `input.ordered_pairs`
- coordinate_mode requested/effective: `vis_pixels` / `vis_pixels`
- W / H / CAM_H: `1024` / `512` / `1.6`
- Image source basename: `VFuaQ6m2Qom_ad4c387f8175498491966703c8441e0d.png`
- Local image: `VFuaQ6m2Qom_ad4c387f8175498491966703c8441e0d.png`
- Image exists: `True`
- Image SHA-256: `9b7dda68f916111249b22a5731877299ab5d86992443a68aa3ded99a45c51782`
- 2D overlay image: `VFuaQ6m2Qom_ad4c387f8175498491966703c8441e0d.png`
- 2D overlay SHA-256: `9b7dda68f916111249b22a5731877299ab5d86992443a68aa3ded99a45c51782`
- Viewer URL: `/tools/label_studio/vis_3d.html`
- Image URL for viewer: `/data/mp3d_layout/valid_no_occ/img/VFuaQ6m2Qom_ad4c387f8175498491966703c8441e0d.png`
- Texture expected: `True`
- Network access used: `False`

## Human Review Summary

This is an expert-side local visual review.
Candidate previews are diagnostic only.
This review is audit-only; no candidate is accepted and M4.2 remains blocked.
No automatic fix is claimed.
Texture toggle and ghost are display controls only.
No annotation patch or Label Studio writeback is produced.

No eligible executable candidate was supplied. Review covers original geometry only.

## Candidate Metric Summary

| variant | wall residual sum | corner residual sum | height residual sum | vertical x residual sum | min wall | self-intersection |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| original | 56.707 | 87.545 | 0.177 | 0.000 | 0.150 | False |

## Pair 3D Coordinates — original

| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |
| ---: | ---: | --- | --- | ---: | ---: | --- |
| 1 | None | (-1.442, -1.600, 2.779) | (-1.442, 1.319, 2.779) | 2.919 | -0.014 | none |
| 2 | None | (-1.448, -1.600, 2.029) | (-1.448, 1.332, 2.029) | 2.932 | -0.001 | none |
| 3 | None | (-3.714, -1.600, 2.014) | (-3.714, 1.310, 2.014) | 2.910 | -0.023 | none |
| 4 | None | (-3.781, -1.600, -3.512) | (-3.781, 1.360, -3.512) | 2.960 | 0.027 | none |
| 5 | None | (-2.283, -1.600, -3.463) | (-2.283, 1.314, -3.463) | 2.914 | -0.019 | none |
| 6 | None | (-2.283, -1.600, -4.271) | (-2.283, 1.308, -4.271) | 2.908 | -0.025 | none |
| 7 | None | (-1.923, -1.600, -4.338) | (-1.923, 1.345, -4.338) | 2.945 | 0.012 | none |
| 8 | None | (-1.513, -1.600, -3.412) | (-1.513, 1.336, -3.412) | 2.936 | 0.002 | none |
| 9 | None | (-1.363, -1.600, -3.408) | (-1.363, 1.339, -3.408) | 2.939 | 0.006 | none |
| 10 | None | (-1.349, -1.600, -4.652) | (-1.349, 1.340, -4.652) | 2.940 | 0.007 | none |
| 11 | None | (0.484, -1.600, -4.626) | (0.484, 1.318, -4.626) | 2.918 | -0.015 | none |
| 12 | None | (0.504, -1.600, -3.400) | (0.504, 1.326, -3.400) | 2.926 | -0.007 | none |
| 13 | None | (0.660, -1.600, -3.430) | (0.660, 1.347, -3.430) | 2.947 | 0.014 | none |
| 14 | None | (0.660, -1.600, 1.997) | (0.660, 1.332, 1.997) | 2.932 | -0.001 | none |
| 15 | None | (0.400, -1.600, 2.011) | (0.400, 1.334, 2.011) | 2.934 | 0.001 | none |
| 16 | None | (0.397, -1.600, 2.796) | (0.397, 1.336, 2.796) | 2.936 | 0.003 | none |

## Wall Metrics — original

| wall | from-to | length | direction | nearest axis | residual | short |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 1-2 | 0.750 | 269.541 | 270.000 | 0.459 | False |
| 2 | 2-3 | 2.266 | 180.373 | 180.000 | 0.373 | False |
| 3 | 3-4 | 5.527 | 269.305 | 270.000 | 0.695 | False |
| 4 | 4-5 | 1.498 | 1.883 | 0.000 | 1.883 | False |
| 5 | 5-6 | 0.809 | 270.008 | 270.000 | 0.008 | False |
| 6 | 6-7 | 0.366 | 349.487 | 0.000 | 10.513 | False |
| 7 | 7-8 | 1.013 | 66.094 | 90.000 | 23.906 | False |
| 8 | 8-9 | 0.150 | 1.734 | 0.000 | 1.734 | True |
| 9 | 9-10 | 1.244 | 270.638 | 270.000 | 0.638 | False |
| 10 | 10-11 | 1.833 | 0.814 | 0.000 | 0.814 | False |
| 11 | 11-12 | 1.226 | 89.060 | 90.000 | 0.940 | False |
| 12 | 12-13 | 0.159 | 349.098 | 0.000 | 10.902 | True |
| 13 | 13-14 | 5.427 | 90.009 | 90.000 | 0.009 | False |
| 14 | 14-15 | 0.260 | 176.906 | 180.000 | 3.094 | False |
| 15 | 15-16 | 0.786 | 90.197 | 90.000 | 0.197 | False |
| 16 | 16-1 | 1.839 | 180.542 | 180.000 | 0.542 | False |

## Corner Metrics — original

| pair | prev wall | next wall | turn angle | residual to 90 | warning |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 16 | 1 | 91.001 | 1.001 | False |
| 2 | 1 | 2 | 90.831 | 0.831 | False |
| 3 | 2 | 3 | 91.067 | 1.067 | False |
| 4 | 3 | 4 | 87.423 | 2.577 | False |
| 5 | 4 | 5 | 88.125 | 1.875 | False |
| 6 | 5 | 6 | 100.521 | 10.521 | False |
| 7 | 6 | 7 | 103.393 | 13.393 | False |
| 8 | 7 | 8 | 115.640 | 25.640 | True |
| 9 | 8 | 9 | 88.904 | 1.096 | False |
| 10 | 9 | 10 | 89.824 | 0.176 | False |
| 11 | 10 | 11 | 91.754 | 1.754 | False |
| 12 | 11 | 12 | 80.038 | 9.962 | False |
| 13 | 12 | 13 | 79.089 | 10.911 | False |
| 14 | 13 | 14 | 93.103 | 3.103 | False |
| 15 | 14 | 15 | 93.292 | 3.292 | False |
| 16 | 15 | 16 | 89.655 | 0.345 | False |

## Safety Boundary

This report is expert-side, offline, local-only, sidecar, and dry-run only. It does not edit annotations, optimize coordinates, reorder corners, score workers, or create formal experiment artifacts.
