# A4 development outcome replay

Status: `stability_fail_no_go` for the frozen A4-S primary safety estimate; development descriptive only.

- Development buildings: 9; locked buildings consumed: 0.
- Public GT-primary paired denominator: 58; strict-conflict sensitivity denominator: 46.
- Candidate-only conflict pool hits across all pools: 30; paired public exclusions: 12.
- A4-S mean delta: -0.0033598089513616775; effect band: no_go; direction: direction_gate_fail_nonnegative_5_positive_1.
- A4-C/L are fixed exploratory variants and cannot upgrade A4-S: C=-0.008049451458339114, L=-0.0064601938428468205.
- Bootstrap: seed=20260817, replicates=5000, cluster_unit=building; no annotation-level p-value used.
- Operational corrected reference is `not_evaluable/source_absent`; public GT was not modified.
- Four locked buildings were excluded at split validation and their quality values were not consumed.

## Reproducibility

- Pre-outcome manifest inputs and outputs were independently SHA-verified before outcome joins.
- No action was recomputed; all A0/A4 action IDs came from the frozen action CSV.
