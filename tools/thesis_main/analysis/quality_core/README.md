# quality_core

`analyze_quality.py` remains the legacy-compatible monolithic analyzer.
`quality_core/` is only a boundary package for gradual decomposition; it does not implement formal C1/C2/T1/V1.

Future formal Paper A flow should still use frozen snapshots, canonicalization, closeout audits, readiness gates, and separate formal P1/C1/C2/T1/V1 modules.
This package is for reusable parser, active-time, geometry, consensus, and report components.
HoHoNet latent features and `d_t / I_t^{OOD}` reference construction are out of scope here and should live in a separate calibration feature-reference module.
