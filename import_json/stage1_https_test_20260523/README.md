# Stage 1 HTTPS Smoke-Test Imports

This directory contains small HTTPS-only smoke-test imports derived from the frozen Stage 1 / P1 imports.

These files are not formal P1 import packages.

## Files

- `stage1_prescreen_manual_import_v2_https_test_5tasks.json`
- `stage1_prescreen_semi_import_v5_https_test_5tasks.json`

## Transform

- Keep the first 5 tasks from the corresponding frozen Stage 1 import.
- Keep `image`, `predictions`, `task_id`, `base_task_id`, and metadata unchanged.
- Replace only `data.vis_3d` base URL:
  - from `http://175.178.71.217:8000`
  - to `https://label.sparkle0825.top`

## Intended Use

Use these files only to create temporary Label Studio HTTPS test projects and verify that the HTTPS entry path can load task pages without mixed-content errors.

Do not merge these files into the frozen Stage 1 P1 package.
