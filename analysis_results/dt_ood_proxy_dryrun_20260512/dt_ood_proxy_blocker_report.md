# d_t OOD Proxy Dry-Run Blocker Report

Generated at: 2026-05-12

## Status flags

- `dry_run_only=true`
- `no_C2_freeze_yet=true`
- `tau_d_not_final=true`
- `not_thesis_facing_artifact=true`
- `do_not_use_for_split=true`

## Scope

- This is a readiness/blocker report only.
- No `d_t` score was generated.
- No `dt_scores_dryrun.csv`, Validation_OOD, Hard subset H, V1 manifest, assignment manifest, task-risk snapshot, or routing artifact was generated.
- This report must not be used as a split source or thesis-facing artifact.

## Readiness result

- `tools/compute_dt_score.py` exists and supports HoHoNet feature extraction, L2-normalized pooled embeddings, KNN distance, and leave-one-out provisional `tau_d`.
- HoHoNet config/checkpoint candidates exist in `config/` and `ckpt/`.
- No realized `embedding_features.npz` plus task manifest was found.
- No realized `dt_scores.csv` was found.
- No materialized `dt_reference_summary_C1.json` reference bank was found.
- `analysis_results/c_manifests_20260310/embedding_ood_protocol_v1.json` still records the reference pool materialization as blocked by the runtime bridge.

## Current blocker

The repository has the `d_t` scoring implementation and model assets, but it does not yet have the realized C1/C2-compatible input bundle required to compute a legitimate dry-run `d_t` contact sheet.

Required inputs before `d_t` dry-run materialization:

- candidate image manifest with `task_id` and `image_path`
- HoHoNet cfg and checkpoint selected for the intended feature backend
- feature extraction/runtime bridge that can call the expected HoHoNet shared pre-head latent path reproducibly
- Calibration_manual-only reference bank / `dt_reference_summary_C1.json`
- output schema for `dt_scores.csv` containing `d_t`, `d_t_status`, `d_t_k`, `d_t_ref_hash`, `d_t_model_ver`, `d_t_metric`, `d_t_pool_size`, `d_t_failure_reason`, `d_t_compute_ts`, `tau_d`, and `I_t_OOD`

## Formal-use prohibition

Do not use this report to freeze `tau_d`, define formal `I_t^{OOD}`, construct Validation_OOD, construct Hard subset H, tune K/q/embedding layer, initialize task-risk manifest, or update routing.
