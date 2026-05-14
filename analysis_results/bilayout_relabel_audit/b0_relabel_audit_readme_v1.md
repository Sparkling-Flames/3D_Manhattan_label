# B0 Relabel Audit Package v1

Status: Paper B / non-thesis-facing audit planning.

Scope: documentation and manually fillable audit templates only. This package does not train models, does not implement an audit tool, and does not change any A-line protocol or artifact.

## Purpose

B0 verifies whether Bi-Layout-style relabels actually reduce `overextend_adjacent` / cross-door expansion under the Paper B enclosed-only research question.

B0 is audit, not training. Its output is a manually reviewed audit table and a filtered candidate list for possible B1 enclosed-only fine-tuning. It is not an automatic GT replacement.

## A-line boundary

The A-line thesis-facing protocol remains:

`Pilot -> PreScreen -> Calibration -> Main(Test + Validation)`

This B0 package has no A-line `P1 / C1 / C2 / T1 / V1` effect. It must not change admission, `w_max`, `tau_d`, Score, worker tier, routing freeze, `k0/kmax`, stop rules, formal `g_t`, formal `d_t`, Label Studio production UI, assignment manifests, import JSON, export labels, or analysis contracts.

Bi-Layout cue is not an OOS classifier. B0 fields such as `oos_suspect` are manual audit flags only and do not replace A-line scope adjudication or OOS gate behavior.

## Files

- `b0_contact_sheet_inventory_template.csv`
  - Pre-filled from located source manifests under `analysis_results/bi_layout_vs_hohonet_20260514/`.
  - Contains available `task_id`, `image_id`, `scene_id`, contact sheet path, source manifest path, corner counts, and comparison status.
  - It does not contain visual judgments.

- `b0_relabel_audit_template_v1.csv`
  - Manually fillable audit table with the required B0 schema.
  - Contains header only. Reviewers should fill one row per deduplicated sample.

- `b0_relabel_audit_manifest_v1.json`
  - Machine-readable description of source manifests, expected schema, allowed vocabularies, and forbidden uses.

- `b0_relabel_audit_readme_v1.md`
  - This file.

## Located source manifests

The four contact-sheet source manifests were found:

- `analysis_results/bi_layout_vs_hohonet_20260514/hard_prediction_failure_hohonet_txt_vs_bilayout_manifest.csv`
- `analysis_results/bi_layout_vs_hohonet_20260514/highest_g_score_hohonet_txt_vs_bilayout_manifest.csv`
- `analysis_results/bi_layout_vs_hohonet_20260514/nominal_prediction_structure_hohonet_txt_vs_bilayout_manifest.csv`
- `analysis_results/bi_layout_vs_hohonet_20260514/soft_prediction_complexity_hohonet_txt_vs_bilayout_manifest.csv`

The inventory includes 120 source rows: 30 per group.

## Manual audit fields

`b0_relabel_audit_template_v1.csv` must keep exactly these fields:

```text
task_id,image_id,scene_id,source_group,hohonet_corner_count,bilayout_corner_count,hohonet_crossdoor_score,bilayout_crossdoor_score,overextend_reduced,overparse_reduced,bilayout_undercoverage,bilayout_new_error,both_wrong,oos_suspect,open_boundary_ambiguity,expert_verdict,usable_for_B1,audit_notes
```

Allowed `source_group` values:

- `hard_prediction_failure`
- `highest_g_score`
- `nominal_prediction_structure`
- `soft_prediction_complexity`

Allowed `expert_verdict` values:

- `accept_bilayout_enclosed`
- `accept_with_minor_fix`
- `reject_undercoverage`
- `reject_ambiguous_or_oos`

## Review rules

- Do not infer visual judgments automatically.
- Bi-Layout relabel is not automatically correct.
- Under-coverage and new errors must be reported, not hidden.
- `soft_prediction_complexity` should be treated as a stress / counterexample group unless expert review marks a sample usable.
- Deduplicate by `task_id / image_id / scene_id` before reporting group-level statistics, especially for overlap between `hard_prediction_failure` and `highest_g_score`.
- `usable_for_B1=true` should only be assigned after expert review and should normally require `expert_verdict` of `accept_bilayout_enclosed` or `accept_with_minor_fix`.

## Prohibited uses

- Do not use this package for model training without completed manual audit.
- Do not treat Bi-Layout cue as an OOS classifier.
- Do not automatically replace GT with Bi-Layout relabel.
- Do not add B-line caution cue to the A-line formal Semi-Auto condition.
- Do not merge Bi-Layout cue into formal A-line `g_t`.
- Do not use B-line findings to change A-line `P1 / C1 / C2 / T1 / V1`.
