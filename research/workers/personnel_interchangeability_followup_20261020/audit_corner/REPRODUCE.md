# Portable corner supplement

No script requires `/workspace/shared` or another machine-specific absolute path. Keep frozen Pro files separate from this follow-up. The pure API `corner_distance.corner_compare` depends only on NumPy/Shapely; no fusion or official labels are changed.

## Core replay and geometry metrics

`--bundle` denotes the directory containing both `analysis/` and `interchangeability_20261020/` from the frozen Pro package. `--native` denotes a newly reconstructed fusion output with `pools/*.json.gz`. First use the frozen package's `reproduce.py core` recovery instructions to reconstruct those pools from hash-checked inputs. Do not copy the large native pool cache into this follow-up.

```
python evaluate_corner_extension.py --bundle /path/to/frozen-pro --native /path/to/core_native --out /path/to/new-corner-core
python build_corner_deliverables.py --out /path/to/new-corner-core
```

For the newly nominated exploratory block probe, point to its separate frozen requests/native pools, and choose a separate output directory:

```
python evaluate_corner_extension.py --bundle /path/to/frozen-pro --requests /path/to/fresh_block_requests.json.gz --native /path/to/fresh_corner_blocks --source fresh_discovery_nominated_block_probe --out /path/to/new-corner-blocks
python build_corner_deliverables.py --out /path/to/new-corner-blocks
```

Omitting `--native` evaluates only embedded representative cases. The table key is `(source, replay_group, event_id)`, because W132 probe records reuse primary events. Do not pool them as independent observations. No geometries are selected based on measured distances before running; unavailable attempts remain in the tables.

## Tests and prior 451-panel parity

```
INTERCHANGEABILITY_BUNDLE=/path/to/frozen-pro python -m unittest -v test_corner_distance.py
python verify_prior_panel.py --inputs /path/to/retained-small-prior-inputs --out /path/to/PRIOR_451_PARITY.json
```

The small prior inputs are `prior_teams.json.gz`, `prior_events.csv.gz`, and `prior_pairs.csv.gz`, read from main commit ea7d77bb96b2954074d950fcc3db9ae8e832f518 in `research/workers/personnel_composition_followup_20261019/`. They are frozen evidence copies, not new fusion outputs. Their SHA256 values are recorded in `PORTABLE_INPUTS.json`.

## New-class discovery evaluation

For legacy-history endpoint extraction and fixed-background discovery comparisons, set `INTERCHANGEABILITY_WORK_ROOT` to a user-chosen reconstructed workspace containing:

- `unpacked/`: frozen Pro layout above
- `restored/work_personnel_typing_A_20261019/events/`: hash-verified original endpoints
- `audit_learning/`: published learning scripts, frozen new labels and fold artifacts

The discovery helpers write beside themselves, not into frozen Pro. Their runtime dependency is the companion learning script `learn_corner_types.py` (updated common-anchor evaluator) and its published package imports. Run the learning team's portable recovery setup before these helpers.

```
INTERCHANGEABILITY_WORK_ROOT=/path/to/work python extract_corner_discovery.py --jobs 2
INTERCHANGEABILITY_WORK_ROOT=/path/to/work python evaluate_corner_discovery.py
python plot_corner_discovery.py
```

The extraction emits pool-specific source/code hashes; discovery output records label and evaluator hashes. Q/T controls require finite supported history features. All six candidates remain in the results; no score/label threshold is optimized from four human examples. These discovery results concern m=1, not block interchangeability. The fresh block experiment is a separate exploratory probe, and method ranking requires its common-library design rather than unmatched class-specific panels.

The environment may need the scientific packages pinned by the frozen Pro `requirements.txt`, plus Matplotlib/Pandas for tables/figures. Use a writable Matplotlib/font cache; plotting scripts default to `/tmp` cache locations.

## Shared-library block comparison and history-only block metrics

These entrypoints are fully path-configurable and do not depend on the workspace layout:

```
python evaluate_common_library.py --requests /path/to/fresh_block_requests.json.gz --native /path/to/fresh_corner_blocks --out /path/to/common_library --jobs 2
python evaluate_common_library.py --requests /path/to/history_block_requests.json.gz --native /path/to/history_corner_blocks --out /path/to/history_block_metrics --pairs-only --jobs 2
```

The first command compares only the two frozen label maps embedded in the requests, checks which is the nominated primary method, and uses per-metric four-cell common-anchor support. The second only extracts continuous endpoint metrics and exact exchanged workers; it does not train labels or rank methods. Native endpoint pools can be reconstructed by the frozen Pro `analysis/composition/fusion_runner.py` with each exact request file. The history-only request has separate provenance and must never be relabeled as an assessment result.

Do not copy the huge native pool directory when publishing. Preserve the exact compressed requests, small labels/contracts and hashes, this code, and derived evidence tables. `COMMON_ENDPOINT_PAIRS.csv.gz` retains team keys, block indices and exchanged worker IDs so classification and aggregation can be checked without another fusion run.

## Entire frozen direct-m2 family (no assessment reselection)

Run `python audit_corner/evaluate_direct_block_family.py --root WORK_ROOT` after the frozen `audit_learning/block_fit` labels and `audit_corner/common_library/COMMON_ENDPOINT_PAIRS.csv.gz` are present. This only recategorizes cached endpoint outcomes, evaluates both K2/K3 against frozen Rnew2 on metric-specific four-cell common anchors, and retains all-attempt risk. Results are in `audit_corner/direct_block_assessment/`; the historical negative selection remains authoritative. `evaluate_common_library.py --phase` records this internal full-family check separately from the earlier nominated mean-K3 exploratory probe.
