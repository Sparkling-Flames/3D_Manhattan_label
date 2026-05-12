# g_t Diagnostic Dry-Run Report

Generated at: 2026-05-12T15:53:14Z

## Status flags

- `dry_run_only=true`
- `no_C2_freeze_yet=true`
- `tau_d_not_final=true`
- `not_thesis_facing_artifact=true`
- `do_not_use_for_split=true`

## Scope

- This is an exploratory dry-run for prediction-side structural diagnostics.
- It is not a formal `g_t` rule, not a V1 artifact, not a routing artifact, and not a split source.
- `d_t` and `g_t` remain separate proxies: `d_t` is feature-space shift, while this `g_t` dry-run is prediction-side structural diagnostics.
- `legacy_risk_score` is retained only as an old baseline field and is not the main explanation.
- Manual review labels are only for visual sanity check and must not be used for split, `tau_d`, K, q, embedding layer, H admission, `g_t` freeze, or routing.
- `difficulty`, `model_issue`, `lead_time`, `active_time`, worker labels, and manual review fields are not used as pre-annotation risk inputs.

## Input

- Source JSON: `C:\Users\ASUS\Downloads\project-2-at-2026-05-11-16-44-2daa004c.json`
- Parsed tasks: 258

## Bucket counts

- `hard_prediction_failure`: 48
- `soft_prediction_complexity`: 30
- `nominal_prediction_structure`: 180
- `render_or_prediction_missing`: 0
- `manual_review_needed`: 0

## Reason counts

- `polygon_missing`: 0
- `polygon_construction_failure`: 0
- `self_intersection_or_invalid_polygon`: 1
- `topology_pairing_failure`: 47
- `invalid_corner_count`: 0
- `high_keypoint_count`: 53
- `high_polygon_point_count`: 53
- `duplicated_corner_cluster`: 25
- `abnormal_polygon_area`: 0
- `oversegmentation_candidate`: 53

## Ignored forbidden-field audit

- `completed_by`: 318
- `lead_time`: 338

## Outputs

- Sample manifest: `analysis_results\g_t_diagnostic_dryrun_20260512\g_t_diagnostic_sample_manifest.csv`
- Manual review template: `analysis_results\g_t_diagnostic_dryrun_20260512\manual_g_t_review_template.csv`
- Contact sheet: `analysis_results\g_t_diagnostic_dryrun_20260512\contact_sheets\contact_sheet_hard_prediction_failure.png`
- Contact sheet: `analysis_results\g_t_diagnostic_dryrun_20260512\contact_sheets\contact_sheet_soft_prediction_complexity.png`
- Contact sheet: `analysis_results\g_t_diagnostic_dryrun_20260512\contact_sheets\contact_sheet_nominal_prediction.png`
- Contact sheet: `analysis_results\g_t_diagnostic_dryrun_20260512\contact_sheets\contact_sheet_highest_g_score.png`

## Formal-use prohibition

Do not use this dry-run to define formal Validation_OOD, define Hard subset H, initialize V1 assignment, freeze `tau_d`, freeze `g_t`, create task-risk manifest, or update routing contract.

## Manual review labels

- `likely_structural_risk`
- `likely_prediction_artifact`
- `likely_visual_domain_shift`
- `likely_oos_or_boundary_ambiguous`
- `likely_easy_false_positive`
- `unclear`
