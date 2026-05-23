# B0 Partial Validation Report

Status: Paper B / non-thesis-facing validator output.

Input CSV: `analysis_results/bilayout_relabel_audit/b0_relabel_audit_worklist_v1.csv`

This report validates schema and vocabularies only. It does not infer visual judgments, does not compute final B0 descriptive metrics, and does not treat Bi-Layout cue as an OOS classifier.

## Counts

- total_rows: 120
- dedup_primary_rows: 90
- reviewed_primary_rows: 0
- unreviewed_primary_rows: 90
- usable_for_B1_true_rows: 0
- manual_relabel_candidate_rows: field not present

## Rows By Expert Verdict

- `<blank>`: 120

## Errors

- none

## Warnings

- none

## Boundary

- Paper B / B0 audit only.
- No model training.
- No A-line `P1 / C1 / C2 / T1 / V1` effect.
- No formal `g_t`, `d_t`, routing, OOS classifier, or Label Studio production UI effect.
