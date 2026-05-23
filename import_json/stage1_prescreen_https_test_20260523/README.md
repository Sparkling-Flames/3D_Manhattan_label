# Stage 1 HTTPS Semi Smoke-Test Import

This directory contains a small HTTPS-only smoke-test import derived from:

`import_json/stage1_prescreen_final_20260325/stage1_prescreen_semi_import_v5.json`

It is not a formal P1 import package.

## File

- `stage1_prescreen_semi_import_v5_https_test_5tasks.json`

## Transform

- Keep the first 5 tasks from the original semi import.
- Keep `image`, `predictions`, `task_id`, `base_task_id`, and semi metadata unchanged.
- Replace only `data.vis_3d` base URL:
  - from `http://175.178.71.217:8000`
  - to `https://label.sparkle0825.top`

## Intended Use

Use this file only to create a temporary Label Studio HTTPS test project and
verify that the HTTPS entry path can load task pages without mixed-content
errors.

Do not merge this file into the frozen Stage 1 P1 package.
