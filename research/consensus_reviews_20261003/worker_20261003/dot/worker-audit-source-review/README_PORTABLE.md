# Portable B-line verification

Keep `worker-audit-original/` and `worker-audit-source-review/` beside each other. Run from their common parent directory. All audit scripts locate inputs relative to their own files; no network or user-specific paths are needed after extraction.

The saved results must remain separate from new outputs. Copy this bundle before rerunning the diagnostic scripts if you want to preserve every evidence file unchanged. Never point the upstream replay at the original result directory.

## Environments

These reproduce the two numerical stacks tested here on Python 3.12. They do **not** recreate the source author's complete Python 3.11.7/SciPy 1.11.4/OS environment. Only the first environment matches their NumPy and Shapely versions.

```bash
python3.12 -m venv .venv-old
.venv-old/bin/python -m pip install numpy==1.26.4 shapely==2.0.4 scipy==1.17.0 pandas==2.2.3 matplotlib==3.10.8 pytest==9.1.1
python3.12 -m venv .venv-new
.venv-new/bin/python -m pip install numpy==2.3.5 shapely==2.1.2 scipy==1.17.0 pandas==2.2.3 matplotlib==3.10.8 pytest==9.1.1
export MPLCONFIGDIR="$PWD/.cache/matplotlib"
export XDG_CACHE_HOME="$PWD/.cache"
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
```

On Windows use `.venv-old/Scripts/python.exe` and `.venv-new/Scripts/python.exe`; set the environment variables with your shell's syntax. The source `--out` guard rejects an existing `design.json`; choose a genuinely new directory for every replay.

## Verify original source bytes

```bash
python worker-audit-source-review/verify_source_hashes.py
```

Expected: 71/71 Git blob matches at commit `405f3041fdd76977f625d50c558c63dbf342699d`. This manifest validates the bounded materialized source tree, not the full repository or current raw/source bundle.

## Re-run all 23 relevant tests

```bash
cd worker-audit-original
../.venv-old/bin/python -B -m pytest -v -p no:cacheprovider \
  tests/test_worker_profiles_20261003.py \
  tests/test_research_panel_inventory_20261003.py \
  tests/test_lee_expanded_20261003.py \
  tests/test_lee_difficulty_20261003.py \
  tests/test_lee_tile_precision_20261003.py \
  tests/test_lee_tile_stage1_20261002.py \
  tests/test_consensus_contract_20260923.py
cd ..
```

Repeat with `.venv-new`. This is a scoped suite, not a full-repository pass. The included S2 `input.json` fixture is necessary for the inventory test.

## Fresh full ten-image replay

```bash
cd worker-audit-original
../.venv-old/bin/python -B -m tools.thesis_main.analysis.worker_profiles_20261003 \
  --input analysis_results/worker_profiles_20261003/input.json \
  --out ../fresh-worker-old
../.venv-new/bin/python -B -m tools.thesis_main.analysis.worker_profiles_20261003 \
  --input analysis_results/worker_profiles_20261003/input.json \
  --out ../fresh-worker-new
cd ..
.venv-old/bin/python -B worker-audit-source-review/compare_replay.py fresh-worker-old fresh-worker-old-comparison.json
.venv-new/bin/python -B worker-audit-source-review/compare_replay.py fresh-worker-new fresh-worker-new-comparison.json
```

This computes all 10626 four-person subsets per image and both rules, with original plus available revised references. Exact bytes across every environment are not promised. The recorded old stack produced all 30 arrays exactly and only floating-point last-bit differences in two CSVs; the new stack changed scores by at most 1.11e-15.

## Bounded source, point and direct-subset checks

```bash
.venv-old/bin/python -B worker-audit-source-review/check_bound_input.py
.venv-old/bin/python -B worker-audit-source-review/check_direct_subsets.py
```

The first compares all 274 B objects to frozen S2 metadata, reconstructs the 254 available footprints without changing their coordinates/order, keeps 20 unavailable records, and mutates target-building matrix rows to verify calibration isolation. The second independently cuts tiles for 30 selected four-person groups and checks 84 reference IoUs. It is not an exhaustive current-subset re-tiling of all groups.

## Reproduce and inspect the two warnings

```bash
.venv-old/bin/python -B worker-audit-source-review/instrument_warnings.py
.venv-old/bin/python -B worker-audit-source-review/check_warning_operands.py
.venv-new/bin/python -B worker-audit-source-review/check_warning_operands.py
```

Instrumentation wraps the unchanged Shapely method only to record its warning, operands, caller and result, and re-emits the warning to the original collector. It does not snap, repair, simplify or change source coordinates. Both source warnings occur at k=1 during shape-equivalence validation, not the k=4 score kernel. Diagnostic reevaluations add their own warnings; do not mix those counts with the two source-run warnings.

No original image review, identity adjudication, full current-bundle source-index rejoin, broad raw/comment corpus download, repository write, or source eligibility revision is performed.
