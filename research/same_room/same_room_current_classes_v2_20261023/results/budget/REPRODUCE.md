# Compact supplement: runnable paths

The package keeps code and data separate. From the package root, leave
`HOHONET_WORK_ROOT` unset; scripts use `design/`, `results/native/`,
`results/budget/`, `cases/budget/`, `cases/mechanisms/`, and `source_index/`.
Set `HOHONET_WORK_ROOT=/path/restored/work` to read a full original work tree
instead. Set `HOHONET_REPO` to the frozen GitHub checkout, and `HOHONET_PHOTOS`
to selectively fetched Release images for redrawing photos. The code directory
is never used as the data work root.

```bash
python code/budget_effects/analyze_budget.py --require-complete --out /tmp/hohonet-budget-intermediate
python code/budget_effects/compact_budget.py --source /tmp/hohonet-budget-intermediate --out /tmp/hohonet-budget-rebuilt
HOHONET_REPO=/path/checkout HOHONET_PHOTOS=/path/photos HOHONET_FONT=/path/cjk.otf python code/budget_effects/build_budget_artifacts.py
HOHONET_REPO=/path/checkout HOHONET_PHOTOS=/path/photos HOHONET_FONT=/path/cjk.otf python code/mechanisms/build_exact_case_figures.py
python code/mechanisms/analyze_case_states.py G078_current_m1 G057_n18_m1 G057_n13_m1 G015_current_same_class
HOHONET_REPO=/path/checkout python code/mechanisms/score_transition_diagnostics.py G078_current_m1 G057_n18_m1 G057_n13_m1 G015_current_same_class
```

Aggregation uses delivered native scalar columns; saved exact states suffice
for case tables and figures. Full-state *new replay* scripts additionally need
the parent frozen engine and reconstructed full pool lookup/native pool tree,
which is intentionally not duplicated in this compact supplement. Use a
restored `HOHONET_WORK_ROOT` for those optional replays. Their exact member
keys, qualified observations, frozen references, and successful replay receipts
are already delivered under `cases/`.

Python 3.12; pandas/numpy for aggregate calculation; matplotlib/Pillow for
figures, and the parent's frozen dependencies for replay. CJK font and raw
photos are external inputs, not bundled. See the original detailed method
notes and `BUDGET_RECEIPT.json`; code changes in this delivery only adapt paths
and inline the identical two aggregation helpers, with no research-rule change.


# Original working-tree method notes and field contract

The packaged commands above take precedence for paths; the following records the original computation layout.

# Budget supplement reproduction and field contract

Repository: `Sparkling-Flames/3D_Manhattan_label`, input main commit
`72a44e80c344975962e1071bd54d894dd86bb4b4`.
Same-room relation version: `same_room_user_working_classification_20261016_v2`.
Design: `SRCC23_paired_finite_panels_v1`; ordinary Manual, replicate 0 only.

## Inputs and code

This directory is intended to sit next to the study's `design/`, `native/`,
`taxonomy_response/`, `engine/`, `taxonomy/`, and `mechanisms/` directories.
`analyze_budget.py` imports the explicit hierarchy and CSV helper from
`taxonomy_response/analyze_response.py`. It reads:

- `design/PANELS.csv` and `design/PANEL_TEAM_LINKS.csv.gz`;
- preferably `native/ENDPOINT_SCALARS.csv.gz`, otherwise the saved endpoint
  dictionaries in `native/pools/*.json.gz`;
- no images or fusion library for the aggregate budget calculation.

Python 3.12, pandas, numpy are sufficient for the aggregate calculation;
matplotlib and Pillow are needed for figures. The frozen HOHONET dependency
environment is needed only for the optional four-state G117 replay.

Run from any directory with the parent study layout intact:

```bash
python budget_effects/analyze_budget.py --require-complete --out budget_effects/intermediate
python budget_effects/compact_budget.py --source budget_effects/intermediate --out budget_effects/final
python budget_effects/build_budget_artifacts.py
```

The intermediate full addition matrix need not be delivered. The provided
`final/ADDITION_LINKS.csv.gz` retains exact endpoint/member keys plus primary
effects, flags and costs. Parent saved endpoint scalars reconstruct omitted
metric columns. No quality or geometry changes are made by these scripts.

Figures read the exact selected G117 states under `cases/`, not a rerun. Original
images are referenced from `mechanisms/photos/` or `HOHONET_PHOTOS`. They were
actually read from Release `quality-original-images-20261015`; ZIP members,
checksums and provenance are in the shared
`mechanisms/RELEASE_IMAGE_SOURCES.csv`. The two image stems are:

- `jtcxE69GiFV_c90412ad99334d3aa7a1ec74d8e543a1` (jtc26)
- `jtcxE69GiFV_dce110162b244b2ab76a0804fc830a9e` (jtc28)

Set `HOHONET_REPO`, `HOHONET_FONT` and `HOHONET_PHOTOS` for relocated figures.
The original image collection and font are not included in this supplement.

## Design, denominators and missingness

`known_common_n` is the common eligible member capacity N; `k_selected` is the
fixed number selected from a common candidate roster. The four desired budgets
are `ceil(N/3)`, `floor(N/2)`, `floor(N/2)+1`, `ceil(2N/3)`, clipped to the actual
design capacity. `role_aliases` identifies equal-n clipped roles. Such aliases
are retained for provenance but excluded from real addition effects.

`series_id` joins the same direct pair, class pair, candidate identities and
selected candidate count across budgets. `selected_mask` and `selected_members`
identify the same concrete candidate subset. `core_before` is verified to be
a subset of `core_after`; `added_members` is their exact difference. There is
no target-Q ranking of added members. Additions change membership and class
composition together with n; this is an actual nested-core comparison.

- Quality means use finite quality at that budget.
- Quality deltas require finite before and after in the same view.
- `Q_lt70/80_joint_before/after` uses the exact same finite paired support.
- `complete_evaluable` is the frozen endpoint's complete+evaluable status;
  failure/incomplete and unavailable quality are not assigned zero Q.
- `crossview_Q_state_t1` classifies each side as up, down or small using ±1 Q;
  both-small, both-up, both-down, opposite, one-changes and quality-unavailable
  are separately retained before aggregation.
- `fusion_turn_n` is the frozen effective-turn count, not a guarantee of true
  physical structure. Reference 5° recall and detailed geometry accompany it.
- Labor ratios are finite only if both recorded totals are eligible and the
  time-source semantic kind is identical. They describe recorded active labor,
  not concurrent completion or monetary cost.

Mask-set means are calculated within a class-pair series. Series are then
averaged within direct pairs, pairs within each adopted declaration, declarations
within buildings, and buildings equally. Overlapping declarations remain
overlapping; no transitive room relation is introduced. Raw denominators are in
`TIMING_SUPPORT.csv`, while aggregate known-rates have this explicit weighting.

## Tables and keys

| File | Unit / use |
|---|---|
| `BUDGET_PANEL_ROLES.csv` | Exact four-budget design mapping, candidates, nested cores, n and clipping aliases |
| `ENDPOINT_AVAILABILITY.csv` | Requested vs available saved endpoints per role |
| `BUDGET_PANEL_RESULTS.csv` | Role-specific quality, failure, tails, geometry and cost summaries |
| `BUDGET_PAIR/GROUP/BUILDING/SUMMARY.csv` | Transparent aggregate levels |
| `ADDITION_LINKS.csv.gz` | `series_id+transition+selected_mask`; exact four endpoints and actual members |
| `ADDITION_PANEL_RESULTS.csv` | Per-series actual-addition outcomes and cross-view states |
| `ADDITION_PAIR/GROUP/BUILDING/SUMMARY.csv` | Weighted effect, tail, failure and labor summaries |
| `SINGLE_ADDITION_PARITY_*.csv` | Only real mid→mid+1, separated by parity |
| `TIMING_SUPPORT.csv` | Raw timing and joint-timing-quality counts, images, pairs, groups, buildings |
| `BUDGET_RECEIPT.json` | Input versions, complete coverage, denominators and replay scope |

`team_key` joins the parent saved endpoint/geometry tables. `image`, `pool_id`
and `reference_id` preserve task and reference identity. Class vectors are
current held-out-building Manual structure labels; class names are not
silently pooled across incompatible selected-family folds.

## G117 explanatory case

`cases/G117_LOW_HIGH_SELECTED.csv` fixes the exact event. Selection is
explanatory: both views lose Q and turns, with average Q effect close to the
G117 group mean. It does not define an unbiased event sample.

`replay_budget_case.py` performs only four frozen full-state replays, asserts
agreement in B8L2, D10, bottom, dir and Hmean to 1e-8, then uses the shared
`mechanisms/analyze_case_states.py` ledger generator. Receipt values are all 0.
`G117_LOW_HIGH_REPLAY.json.gz` contains exact qualified source observations,
reference, resulting geometry and full identity/vote state for those endpoints.

`LOCAL_GROUPS` is endpoint-local. `VOTE_OBSERVATIONS` preserves object and
`pair_index`; `WITHIN_VIEW_GROUP_LINKS` matches common original observations
within a camera view, never cross-view geometric identities. `KEY_VOTE_LEDGER`
contains the three necessary-turn support shortfalls and the two branches of
the jtc28 identity split. Coordinates are in the frozen 1024×512 annotation
frame, with per-view BEV in camera-height units.

This supplement contains no new bulk fusions or altered score. The G117 four
state replays supplement mechanism detail only. `DELIVERY_FILES.txt` excludes
full intermediate matrices, image originals, caches and environments.
