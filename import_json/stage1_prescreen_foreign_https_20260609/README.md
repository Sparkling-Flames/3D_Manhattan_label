# Stage 1 Foreign HTTPS Label Studio Imports

This directory contains HTTPS-only Label Studio import files for foreign Stage 1 / P1 annotation.

## Formal Stage 1 Source

Formal P1 files are derived from:

`import_json/stage1_prescreen_final_20260325`

## Formal Transform Contract

Only `data.vis_3d` is changed:

- from `http://175.178.71.217:8000`
- to `https://label.sparkle0825.top`

Everything else is kept identical to the Chinese Stage 1 imports, including task order, `image`, `task_id`, `base_task_id`, metadata fields, and `predictions`.

## Formal Foreign HTTPS Imports

- `stage1_prescreen_manual_import_v2_foreign_https.json` - 30 tasks
- `stage1_prescreen_semi_import_v5_foreign_https.json` - 18 tasks
- `stage1_prescreen_oos_import_v2_foreign_https.json` - 9 tasks
- `stage1_prescreen_oos_audit_only_import_v1_foreign_https.json` - 1 audit-only OOS task

## MP3D TXT Smoke-Test Imports

These smoke-test files are derived from the Chinese smoke-test files in:

`import_json/mp3d_txt_smoke_test_20260328`

- `mp3d_txt_manual_smoke_import_v1_foreign_https.json` - mirrors `mp3d_txt_manual_smoke_import_v1.json` with only `data.vis_3d` rewritten to HTTPS.
- `mp3d_txt_semi_smoke_import_v1_foreign_https.json` - mirrors `mp3d_txt_semi_smoke_import_v1.json` with only `data.vis_3d` rewritten to HTTPS.

Use the MP3D TXT smoke-test imports only for temporary HTTPS smoke testing. They are not the formal P1 package.

## Boundary

These files do not change Stage 1 selection, pool membership, proposals, final-gold binding, or scoring contracts. They are URL-adapted imports for the HTTPS foreign worker-facing Label Studio path.
