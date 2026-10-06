# Turn-event / arc-length search exploration

Bounded extension of `structure_paths_20261006`, preserving all source observations and votes. Read `REPORT_ZH.md` for exact scope, outcomes and limitations. This is a search-representation experiment, not an identity or layout estimator.

## Run

Requires the delivered source package and its Python dependencies (NumPy, SciPy, Shapely; Numba optional, pytest for tests). No network or GT needed.

```bash
export PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
# Optional when the source package is not at the original sibling path:
export STRUCTURE_SOURCE=/absolute/path/to/structure_paths_20261006
python run_exploration.py --out NEW_results
python -m pytest test_event_search.py -q
```

The output directory must not exist. Default source: `../oct6-structure-intake/extracted/structure_paths_20261006`. Do not merge probe records into a voting roster: each probe is the same worker's same curve, with synthetic samples.

`results/` is the primary saved execution. `replay_verification.json` records exact equality of all 235 files in a second execution. `results_replay/` is an optional redundant replay directory, not required to use the deliverable.

## Result

- Original fixed-hop square counterexample exactly reproduced; event-domain search restores the 5° witness
- Seven fixed real windows plus one synthetic window; 72 base settings, 504 total settings
- 432 subdivision comparisons retain full candidate/leg/witness signatures
- 14 targeted tests pass; 235 replay files byte-identical
- No original source modification, no GT construction, no identity/vote updates

The finite result does not certify noisy subdivision, tiny or degenerate arcs, true anchor identity, top/bottom interior pairing, or downstream consensus quality. Pair-mode RPC AC/BC still lack 5° witnesses.
