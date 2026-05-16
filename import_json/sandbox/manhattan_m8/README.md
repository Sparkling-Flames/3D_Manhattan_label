# Manhattan M8 Sandbox Import

This directory contains sandbox-only Label Studio import material for the experiment-outside Manhattan toolchain.

## Files

- `manhattan_m8_sandbox_smoke_import_2026-05-07.json`
  - Generated from the 2026-05-07 smoke export:
    `export_label/project-23-at-2026-05-07-06-06-980da9dc.json`
  - Contains 5 copied smoke tasks.

## Boundaries

- Sandbox-only import.
- Not a formal import.
- Not a `P1/C1/C2/T1/V1` artifact.
- Not thesis active_time evidence.
- Not worker-facing experiment material.
- Do not invite ordinary workers.
- Keep sandbox exports separate from formal `export_label/` data.
- Do not use sandbox active_time or behavior as thesis evidence.
- Do not use sandbox output for routing, formal `g_t`, worker tier, or correctness labels.

## Required Task Tags

Every task in the sandbox import must include:

- `sandbox_only=true`
- `sandbox_source="2026-05-07 smoke export"`
- `manhattan_m8_sandbox=true`

These tags are for sandbox identification only and do not create a formal round artifact contract.
