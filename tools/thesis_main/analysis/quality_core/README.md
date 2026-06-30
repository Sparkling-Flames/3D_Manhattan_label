# quality_core

`analyze_quality.py` is the legacy-compatible CLI entrypoint.
`quality_core/` contains the split parser, active-time, geometry, consensus, and report components used by that entrypoint.

This does not mean formal C1/C2/T1/V1 is implemented.
Formal Paper A flow should still use frozen snapshots, canonicalization, closeout audits, readiness gates, and separate formal P1/C1/C2/T1/V1 modules.
HoHoNet latent features and `d_t / I_t^{OOD}` reference construction are out of scope here; they belong in a future calibration feature-reference module.
