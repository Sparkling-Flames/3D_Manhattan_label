# Local 3D Review Artifact Policy v1

## Canonical review root

All human-openable A-line 3D/2D review entrypoints must live under:

`analysis_results/paper_a_manhattan/hypothesis_local_review/`

Each case or stage gets one subdirectory, for example:

`analysis_results/paper_a_manhattan/hypothesis_local_review/task218_ann3741_m_anchor_4/`

## Standard UI

The supported review UI is the current `local_3d_review.html` focus review:

- flexible 3D candidate compare grid;
- `2D Review` full-page focus mode;
- draggable 2D/3D placement: left, right, top, bottom;
- resizable 2D/3D panes;
- 2D panorama shown with fixed 2:1 aspect ratio;
- click-to-inspect LS percent and pixel coordinates;
- read-only only: no drag-point editing, annotation patch, Label Studio writeback, ranking, or portfolio selection.

## Directory rule

- `hypothesis_local_review/<case_or_stage>/local_3d_review.html` is the only supported human 3D entrypoint.
- `hypothesis_local_review/<case_or_stage>/open_local_3d_review.cmd` is the only supported launcher.
- `local_3d_projection/` may keep projection evidence such as `projection_metrics.json`, but must not be treated as a human 3D entrypoint directory.
- Solver/audit folders such as `segment_aware_manhattan_refit/` and `m_anchor/` may keep JSON, JSONL, Markdown, and 2D diagnostic overlays, but should not host canonical 3D review entrypoints.

## Deprecated preview archive

Old scattered 3D preview files are archived under:

`analysis_results/paper_a_manhattan/_deprecated_3d_review_archive/`

The archive is for traceability only. Do not link it from current status docs or use it for human review unless explicitly inspecting historical output.
