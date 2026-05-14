# B0 Inventory QA Report v1

Status: Paper B / non-thesis-facing audit materialization.

Scope: inventory QA and row-level manual audit worklist only. No visual judgments were inferred.

## A-line boundary

The A-line protocol remains unchanged: `Pilot -> PreScreen -> Calibration -> Main(Test + Validation)`.

This B0 QA package has no effect on A-line `P1 / C1 / C2 / T1 / V1`, routing, formal `g_t`, `d_t`, Label Studio production UI, import JSON, export labels, admission, `w_max`, `tau_d`, Score, worker tier, `k0/kmax`, or stop rules.

Bi-Layout cue is not an OOS classifier. Fields such as `oos_suspect` are manual audit flags only.

## Inventory row counts

- Total rows: 120
- Unique dedup keys: 90
- Primary rows for future descriptive statistics: 90
- Non-primary duplicate/secondary rows: 30

## Rows by source_group

- `hard_prediction_failure`: 30
- `highest_g_score`: 30
- `nominal_prediction_structure`: 30
- `soft_prediction_complexity`: 30

Allowed source_group vocabulary check: pass.

## Deduplication rule

Dedup key priority:

1. `scene_id + image_id` if both exist.
2. `image_id` if `scene_id` is missing.
3. `task_id` only as last-resort fallback.

Duplicate rows are not dropped. One `dedup_primary=true` row is marked per `dedup_key`; all other rows remain in the worklist as `dedup_primary=false`.

Primary-row selection order:

1. `hard_prediction_failure`
2. `highest_g_score`
3. `nominal_prediction_structure`
4. `soft_prediction_complexity`
5. Stable original inventory row order.

Rows marked `dedup_primary=true` are the rows intended for future descriptive statistics after manual audit. Non-primary rows remain available for traceability and cross-group overlap review.

## Duplicate summary

- Duplicate group count: 30
- Duplicate row count: 60

### Duplicate-group examples

- `DUP001` `scene_image::7y3sRwLe3Va::7y3sRwLe3Va_a775c7668ca9419daaf506e76851821e`: rows=2, primary_task_id=`587`, source_groups=hard_prediction_failure;highest_g_score, task_ids=587;587
- `DUP002` `scene_image::7y3sRwLe3Va::7y3sRwLe3Va_b564162b2c7d4033bfe6ef3dfb959c9e`: rows=2, primary_task_id=`698`, source_groups=hard_prediction_failure;highest_g_score, task_ids=698;698
- `DUP003` `scene_image::B6ByNegPMKs::B6ByNegPMKs_4b983544c13946e3a3a518c565ad1086`: rows=2, primary_task_id=`687`, source_groups=hard_prediction_failure;highest_g_score, task_ids=687;687
- `DUP004` `scene_image::UwV83HsGsw3::UwV83HsGsw3_71ada030981d4468b76dcebc1b6fb940`: rows=2, primary_task_id=`526`, source_groups=hard_prediction_failure;highest_g_score, task_ids=526;526
- `DUP005` `scene_image::UwV83HsGsw3::UwV83HsGsw3_7482b1a2655e4655ae4ab58749f43f65`: rows=2, primary_task_id=`470`, source_groups=hard_prediction_failure;highest_g_score, task_ids=470;470
- `DUP006` `scene_image::X7HyMhZNoso::X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9`: rows=2, primary_task_id=`460`, source_groups=hard_prediction_failure;highest_g_score, task_ids=460;460
- `DUP007` `scene_image::Z6MFQCViBuw::Z6MFQCViBuw_22fff6c74efb476592569c18718feb41`: rows=2, primary_task_id=`500`, source_groups=hard_prediction_failure;highest_g_score, task_ids=500;500
- `DUP008` `scene_image::b8cTxDM8gDG::b8cTxDM8gDG_298a2386166a43c8a04e1c24433f7d15`: rows=2, primary_task_id=`696`, source_groups=hard_prediction_failure;highest_g_score, task_ids=696;696

## Generated files

- `analysis_results/bilayout_relabel_audit/b0_inventory_qa_summary_v1.json`
- `analysis_results/bilayout_relabel_audit/b0_deduplication_report_v1.csv`
- `analysis_results/bilayout_relabel_audit/b0_relabel_audit_worklist_v1.csv`

## Manual audit notes

The worklist copies inventory identifiers and adds manual audit columns. Manual judgment columns are intentionally blank, including:

- `hohonet_crossdoor_score`
- `bilayout_crossdoor_score`
- `overextend_reduced`
- `overparse_reduced`
- `bilayout_undercoverage`
- `bilayout_new_error`
- `both_wrong`
- `oos_suspect`
- `open_boundary_ambiguity`
- `expert_verdict`
- `usable_for_B1`
- `audit_notes`

Allowed `expert_verdict` values, not prefilled:

- `accept_bilayout_enclosed`
- `accept_with_minor_fix`
- `reject_undercoverage`
- `reject_ambiguous_or_oos`

Under-coverage and new errors must be reported, not hidden.
