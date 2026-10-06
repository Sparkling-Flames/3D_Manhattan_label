# Fixed-domain exact-coordinate block sensitivity

This folder is a runnable, independent sensitivity experiment on the delivered `point_correspondence_20261006` snapshot. It does not modify production code, inputs, eligibility, votes, or source rings.

## Run without the original archive

Python 3.10+ and NumPy are required. From this directory:

```sh
python -m pip install -r requirements.txt
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -X utf8 run_sensitivity.py --source portable_source --out NEW_results
```

The output directory must not already exist. Paths are explicit and can be relative or absolute. No network, GT, image, repository checkout, or original large candidate ledger is needed after the supplied portable fixture is present.

The same script also accepts `--source /path/to/point_correspondence_20261006` to verify directly against the original JSONL ledgers. `prepare_portable_reference.py --source ORIGINAL --out NEW_fixture` reconstructs the supplied compact fixture from that archive. The fixture keeps all original rpc records and the full human-review file, the frozen 30 domain definitions, and each original candidate's canonical membership mask, ID, and W. It is an upstream validation reference, never semantic truth or additional independent data. Original and compact SHA-256 provenance is in `portable_source/REFERENCE_PROVENANCE.json`.

## What is tested

For all 30 original rpc domains across 1°, 2.5°, 5°, 7.5°, 10° and pair/bottom/top distances, compare:

1. Original geometric diameter and one-worker constraints
2. Those constraints plus preserving each baseline-coassigned block of exactly equal full point-pair coordinates
3. Original constraints plus the existing explicitly reviewed rpc relations
4. Existing human relations plus the equality-preservation sensitivity constraint

Every worker observation retains its original vote. Full-coordinate equality does not establish semantic identity. Equality preservation is an additional hypothetical restriction, not a recommendation to automatically infer identity. No tolerance, threshold, or unknown semantic label is fitted.

`run_sensitivity.py` implements its own unit-vector spherical distances and parity union-find solver; it imports no upstream solver. All exact assignment sets are checked against the upstream reference with independent filtering. The 18-node paired 5° domain is also checked by direct enumeration of all 131,072 canonical binary assignments, including the empty-group code that is rejected. Exhaustive three-node parity systems provide a small solver unit check.

## Results and interpretation

- `REPORT_ZH.md`: findings and limitations
- `PREREGISTERED_SCOPE.json`: finite scope written before computing the new outcomes, with disclosure of earlier report exposure
- `verified_results/`: full run against original source ledgers, with enriched selected-member fields
- `portable_replay.log`: log of the completed compact-fixture run; its duplicate data files are omitted from this combined delivery, and REPLAY_CHECK.json records their 64 matching hashes
- `REPLAY_CHECK.json`: numerical/result equality between the two input routes
- `*_masks.npz`: every feasible canonical assignment for each tested condition; bit j names node `union[j]`, bit 0 is fixed to zero to remove arbitrary group-label exchange
- `all_domains.json` and individual domain JSON: counts, minimum edit then W selections, target-support ranges, membership invariants, center extrema, moved observations and changed relations
- `verification.json`: scope and exact-set checks
- `node_lookup.json`: observation identity and original source coordinates for every mask

Only the selected candidates are semantically named by their source observations; none of their unreviewed memberships are declared correct. A feasible support range is not a credible interval. Candidate counts or fractions are not posterior probabilities. Center extrema are conditional coordinate-median extrema, not uncertainty confidence bounds. In a top-only or bottom-only domain, coordinates on the other endpoint are merely source-pair proxies, not a newly inferred common upper/lower target.

The original 24-worker denominator and all 224 observations remain fixed. Nodes outside the declared two-group union stay in their original groups by construction. This experiment does not solve general multigroup matching, 2-versus-3 local-path equivalence, semantic target choice, or full-layout topology.

The earlier `results/` and duplicate `portable_replay/` data directories are omitted from this combined delivery; `verified_results/` contains the final enriched numerical results. `initial_syntax_failure.log` preserves a corrected print-statement syntax error; no experiment ran during that failed invocation. The analytical scope and outcome definitions were not changed in response to results.

## 2026-10-06 repository publication note

The 30 complete `*_masks.npz` output witnesses are preserved in the private historical archive; their original hashes are in the repository archive index. The full 30 compact input reference NPZ files remain here. The command above regenerates all output masks into NEW_results. Keep the original author manifests for original delivery verification; do not interpret an archived output path as lost evidence.
