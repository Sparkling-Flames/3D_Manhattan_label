# Manhattan Geometry Diagnostic Smoke Outputs

This directory contains smoke/probe sidecar outputs for the experiment-outside /
post-hoc Manhattan toolchain.

Generated source:

- `export_label/project-23-at-2026-05-07-06-06-980da9dc.json`

Generated files:

- `smoke_probe_summary_2026-05-07.json`
- `smoke_probe_summary_validation_2026-05-07.json`
- `smoke_probe_report_2026-05-07.md`
- `smoke_probe_contact_sheet_2026-05-07.html`

Boundary:

- These are smoke/probe sidecar outputs.
- They are not `P1/C1/C2/T1/V1` artifacts.
- They are not formal `g_t`.
- They are not routing input.
- They are not worker quality labels.
- They are not correctness labels.
- They are not current worker-facing experiment material.
- They were generated from the 2026-05-07 smoke export only.
- The 2026-05-06 smoke export is the same smoke batch with one fewer annotator, so the 2026-05-07 export is preferred for this probe.

Validation:

- `smoke_probe_summary_validation_2026-05-07.json` is a smoke/probe validation report for the summary JSON.
- The validator checks summary fields and count invariants only.
- The validator does not open `source_export` and does not read `export_label/` directly.
