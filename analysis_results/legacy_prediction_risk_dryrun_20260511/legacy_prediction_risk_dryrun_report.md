# Legacy HoHoNet Prediction-Risk Contact Sheet Dry-Run

Generated at: 2026-05-11T16:52:53Z

## Status flags

- `legacy_exploratory_dryrun=true`
- `not_thesis_facing_artifact=true`
- `not_embedding_cluster=true`
- `no_C2_freeze_yet=true`
- `do_not_use_for_split=true`

## Scope

- This is a legacy exploratory dry-run for HoHoNet_v1 prediction-side structural sanity checks.
- This is not an embedding, `d_t`, OOD cluster, Validation_OOD, Hard subset H, V1 manifest, or routing artifact.
- Project-2 export is not used as embedding / `d_t` / OOD cluster data.
- Human visual review is only for proxy sanity check.
- Manual review results must not be used to construct formal Validation_OOD or H.
- Manual review results must not modify `tau_d`, K, q, embedding layer, Validation split, H admission, `g_t` rule, task-risk manifest, or routing contract.
- `difficulty` and `model_issue` are not used as pre-label split truth.
- `lead_time` is preserved only in `lead_time_seconds_ignored` and is not used as `active_time`.
- The old-server active log directory is `active_logs/active_logs`; active time is not used for this visual dry-run.

## Input

- Source export: `C:\Users\ASUS\Downloads\project-2-at-2026-05-11-16-44-2daa004c.json`
- Parsed tasks: 258
- Prediction payload source: annotation-level `prediction` dict, model version `HoHoNet_v1` where present.
- Image source: `data.image` mapped to local `data/` path.

## Heuristic buckets

- Buckets are derived only from prediction-side keypoints, polygon geometry, and image render availability.
- The bucket priority is render/prediction missing, polygon missing/construction/invalidity, pairing/count/duplicate issues, high complexity, then nominal.

## Bucket counts

- `duplicated_corner_cluster`: 4
- `high_complexity_prediction`: 47
- `nominal_prediction_structure`: 198
- `self_intersection_or_invalid_polygon`: 5
- `topology_pairing_failure`: 4

## Flag counts

- `polygon_missing`: 0
- `polygon_construction_failure`: 0
- `self_intersection_or_invalid_polygon`: 5
- `topology_pairing_failure`: 8
- `odd_corner_count`: 0
- `duplicated_corner_cluster`: 7
- `high_complexity_prediction`: 53

## Outputs

- Sample manifest: `D:\Work\HOHONET\analysis_results\legacy_prediction_risk_dryrun_20260511\legacy_prediction_risk_sample_manifest.csv`
- Manual review template: `D:\Work\HOHONET\analysis_results\legacy_prediction_risk_dryrun_20260511\manual_prediction_risk_review_template.csv`
- Contact sheet `highest_risk_overall` (30 shown): `D:\Work\HOHONET\analysis_results\legacy_prediction_risk_dryrun_20260511\contact_sheets\contact_sheet_highest_risk_overall.png`
- Contact sheet `self_intersection_or_invalid_polygon` (5 shown): `D:\Work\HOHONET\analysis_results\legacy_prediction_risk_dryrun_20260511\contact_sheets\contact_sheet_self_intersection_or_invalid_polygon.png`
- Contact sheet `topology_pairing_failure` (4 shown): `D:\Work\HOHONET\analysis_results\legacy_prediction_risk_dryrun_20260511\contact_sheets\contact_sheet_topology_pairing_failure.png`
- Contact sheet `duplicated_corner_cluster` (4 shown): `D:\Work\HOHONET\analysis_results\legacy_prediction_risk_dryrun_20260511\contact_sheets\contact_sheet_duplicated_corner_cluster.png`
- Contact sheet `high_complexity_prediction` (30 shown): `D:\Work\HOHONET\analysis_results\legacy_prediction_risk_dryrun_20260511\contact_sheets\contact_sheet_high_complexity_prediction.png`
- Contact sheet `nominal_prediction_structure` (30 shown): `D:\Work\HOHONET\analysis_results\legacy_prediction_risk_dryrun_20260511\contact_sheets\contact_sheet_nominal_prediction_structure.png`

## Formal-use prohibition

Do not use this dry-run to freeze `tau_d`, define `I_t^{OOD}`, define `g_t`, create `task_risk_manifest`, define Validation_OOD, define Hard subset H, create V1 assignment, or update any routing contract.
