# A4 candidate-image alignment substrate

- Status: **A4_ALIGNMENT_SUBSTRATE_PARTIAL**
- Status reason: **rejected-candidate acceptance policy not predefined**
- Raw-image branch: 79 unique panorama identities were resolved against real files, actual SHA, and dimensions.
- Spatial evidence: deterministic seam-wrapped `dI/dx`, `dI/dy`, x/y profiles in `SPATIAL_IMAGE_EVIDENCE.npz`; no global-statistics-only representation.
- Geometry semantics: `tools/thesis_main/analysis/geometry_consensus/representation.py` and `docs/thesis_main/geometry_loo_candidate_rule_manifest_v1.json` are reused. `point_count` is raw points; `layout_corner_count` is formal valid pair count only.
- Candidate geometry descriptors and candidate-image alignment are separate. Vertical-edge support samples formal wall-wall x events. Ceiling/floor support samples the formal piecewise-linear boundary between every adjacent pair, including the last-to-first-plus-width seam segment; no curve model is introduced.
- Alignment sampling coverage: 577 valid rows, 3083 segments, 41603 boundary samples, and 26189 seam samples.
- Development candidate alignment only: 577 valid rows; 3 invalid geometry row(s) fail closed with reason. Holdout candidate quality and outcome are not read or emitted.
- Optional model branch: `model_status=source_absent`, `model_ready=False`. Existing prediction paths are present but inference/model identity is not formally bound; this does not gate raw-image alignment readiness.
- I/O evidence: 410 input accesses recorded; denied projections consumed: 0; denied paths consumed: 0. CSV parsing may physically read complete rows, but only allowlisted projected values are consumed.

No A4 selector, threshold, training, performance estimate, GT evaluation, prospective annotation, contract, SAP, routing, or frozen input was changed.
