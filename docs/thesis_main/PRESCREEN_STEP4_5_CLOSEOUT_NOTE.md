# PreScreen Step 4-5 Closeout Note

Status: dry-run contract only. This note records the current Step 4-5 audit boundary; it is not a formal scoring, admission, routing, or C1 handoff artifact.

## Current Contract

- Step 4 resolves scope adjudication, synthetic scope binding, and synthetic source geometry GT binding evidence.
- Step 4 reads Label Studio raw exports, final gold records, and geometry GT only through the raw input manifest snapshot chain.
- Step 5 reads Step 4 audit outputs and produces geometry gold alignment / geometry eligibility dry-run labels.
- Step 5 may mark evidence roles, geometry gold status, validation level, manual-anchor dry-run eligibility, and mirror alignment status.
- `manual_anchor_primary_possible` and related Step 5 manual-anchor fields are dry-run geometry eligibility labels only. They are not worker admission decisions, reliability estimates, formal `r0` / `r_u` inputs, or C1 handoff material.
- Step 5 must not compute geometry score, worker admission, `r0`, `r_u`, `wmax`, routing profiles, or C1 handoff.

## Input Dependencies

- Frozen raw input manifest and snapshots under `analysis_results/prescreen_closeout/raw_inputs/`.
- File snapshots carry `sha256`; directory snapshots such as `active_logs` carry an aggregate digest over copied relative paths, file sizes, and file hashes.
- Source/snapshot SHA mismatch is provenance evidence that mutable source changed after freeze; Step 4 must still read the validated snapshot.
- Audit, control, and reference sidecar inputs used by this closeout are copied into the raw input snapshot directory when frozen, with their own `sha256`; they remain provenance inputs for dry-run audits, not formal scoring artifacts.
- Canonical PreScreen annotations and completion audit outputs.
- Step 4 outputs:
  - `prescreen_scope_adjudication.csv`
  - `prescreen_scope_response_audit.csv`
  - `prescreen_synthetic_scope_binding_audit.csv`
  - `prescreen_synthetic_geometry_gt_binding_audit.csv`
  - `prescreen_scope_summary.json`

Step 4 and Step 5 should read frozen snapshot / canonical / Step 4 audit outputs, not mutable Label Studio raw exports or mutable final-gold source files.

## Step 5 Outputs

Only these dry-run files are allowed:

- `analysis_results/prescreen_closeout/prescreen_geometry_gold_alignment_audit.csv`
- `analysis_results/prescreen_closeout/prescreen_geometry_eligibility_audit.csv`
- `analysis_results/prescreen_closeout/prescreen_gold_alignment_summary.json`

## Forbidden Outputs

Do not generate geometry score, admission, `r0`, `r_u`, `wmax`, `w_max`, routing, C1 handoff, or worker reliability profile artifacts from Step 4-5 dry-run.

## Readiness Gate

`tools/thesis_main/analysis/p1_closeout_readiness_audit.py` is a dry-run readiness gate before any formal P1 materialization. It reports blockers from existing closeout artifacts; it is not a formal P1 output, admission decision, reliability estimate, routing input, or C1 handoff.

## Internal Smoke Runner

Run `python tools/thesis_main/analysis/pipeline_smoke_runner.py` to rerun the local provisional pipeline smoke chain.
The runner reads `analysis_results/prescreen_closeout/` and writes stage outputs under `analysis_results/pipeline_smoke/`.
The only root-level runner state is `analysis_results/pipeline_smoke/pipeline_smoke_state.json`; all outputs remain dry-run/provisional only.

## Next Freeze Point

After Stage 1 annotation is complete, freeze raw inputs again, update the raw input manifest, and rerun Step 1-5 from the frozen snapshot chain before any formal analysis or downstream materialization.
