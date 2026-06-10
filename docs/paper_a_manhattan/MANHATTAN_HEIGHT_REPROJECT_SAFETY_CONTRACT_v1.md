# Manhattan Height Reproject Safety Contract v1

Status: M15.7 safety contract only.

Scope: Paper A Manhattan experiment-outside / expert-side assist prototype.

This document defines the safety contract, review fields, and summary metrics
required before any future pair-level height reproject operation is
implemented. It does not define or authorize a height reproject implementation.
It must not be used as a Label Studio UI integration, annotation writeback
contract, routing signal, formal `g_t`, worker quality metric, or
P1/C1/C2/T1/V1 artifact.

## Non-Goals

- Do not implement `reproject_pair_height()`.
- Do not generate y-coordinate candidates.
- Do not modify `candidate_pairs`.
- Do not add UI, ghost overlay, apply, snap, wall move, or writeback behavior.
- Do not connect to Label Studio official userscripts or view config.
- Do not modify `import_json/`, `export_label/`, routing, protocol, SOP, or
  P1/C1/C2/T1/V1 schema.
- Do not interpret height diagnostics as correctness.

## Required Inputs

Future height reproject evaluation must consume existing diagnostic surfaces:

- `RoomLayoutState` from `manhattan_layout_state.py`
- target pair diagnostics:
  - `height_residual`
  - `top_bottom_delta_y`
  - pair `warnings`
  - `is_anchor_candidate`
- global layout diagnostics:
  - `state_status`
  - `state_warnings`
  - `layout_height_candidate`
  - `layout_height_spread`
- optional metadata:
  - `scope`
  - `layout_type`
  - `manhattan_assumable`

## Applicability Preconditions

Height reproject may only be considered applicable when all conditions below
hold:

- `state_status == "ok"`
- scope is normal / enclosed-only
- `manhattan_assumable` is not false-like (`false`, `0`, `no`, or boolean
  `False`)
- no `wrap_seam_unresolved`
- no `layout_height_spread_high`
- no `floor_not_below_horizon_distance_fallback`
- no OOS / open-boundary / split-level / non-Manhattan exclusion metadata
- enough anchor candidates exist to support a stable layout-height estimate
- target pair exists and has parseable height diagnostics

Minimum anchor policy for a future implementation:

- At least 4 pairs must exist.
- At least 3 non-target anchor candidates should be available.
- Anchor candidates must have no pair warnings that affect vertical geometry.
- If the target pair is itself the only non-warning pair, height reproject must
  be blocked.

## Blocking And Review-Only Rules

Future height reproject must suppress or move to review-only under the following
conditions.

### Suppress

The operation must be suppressed when any of these are present:

- OOS / open-boundary / split-level / non-Manhattan / `oos_insufficient`
- `state_status` is `failed` or `excluded`
- `wrap_seam_unresolved`
- target pair missing
- target pair has `top_not_above_bottom`
- `max_y_delta > hard_fail_threshold`
- `max_y_delta` cannot be calculated and no safe review-only row can be formed

### Review-Only

The operation must not return a candidate and must require expert review when
any of these are present:

- `layout_height_spread_high`
- `height_residual_high` on the target pair
- `floor_not_below_horizon_distance_fallback`
- too few stable anchor candidates
- `max_y_delta` unavailable but diagnostics are otherwise inspectable
- `max_y_delta >= expert_review_threshold`
- low confidence in the layout-height estimate

Threshold names must be explicit in code before implementation. They may reuse
existing expert-review and hard-fail movement thresholds only if their unit and
semantics are confirmed to match y-coordinate movement in Label Studio
percentage space. If not, separate y-delta thresholds must be introduced with a
new review contract version.

## Future Review Row Fields

Any future height reproject review row must add these fields without removing
existing M15.6 pair-assist review fields:

- `height_reproject_applicable`
- `height_reproject_blocking_reasons`
- `estimated_layout_height`
- `layout_height_spread`
- `target_height_residual_before`
- `target_height_residual_after`
- `max_y_delta`
- `y_delta_gate_status`
- `manual_height_candidate_plausible`
- `manual_height_candidate_unsafe`

Required semantics:

- `height_reproject_applicable` is diagnostic eligibility, not permission to
  write annotation.
- `height_reproject_blocking_reasons` must be a list of stable tokens.
- `estimated_layout_height` must come from the same projection semantics as
  `RoomLayoutState`.
- `target_height_residual_after` may only be populated if a future preview-only
  candidate is computed; until then it must be absent or `None`.
- `max_y_delta` must be measured in Label Studio 0-100 percentage coordinates.
- `y_delta_gate_status` must distinguish retained candidate, review-only large
  y delta, suppressed y delta, and unavailable y delta.
- Manual fields must remain optional sidecar review fields; missing manual
  review must not be interpreted as safe.

## Future Summary Metrics

Any future height reproject summary must add:

- `n_height_reproject_applicable`
- `n_height_reproject_blocked`
- `n_y_delta_review_only`
- `n_y_delta_suppressed`
- `height_candidate_retention_rate`
- `height_unsafe_candidate_rate`
- `max_y_delta_p50`
- `max_y_delta_p90`
- `max_y_delta_max`

Required denominator rules:

- Count fields must be emitted alongside rate fields.
- `height_candidate_retention_rate` denominator is all evaluated records.
- `height_unsafe_candidate_rate` denominator is manual-reviewed returned height
  candidates only.
- If denominator is zero, the rate may remain `0.0` for compatibility, but the
  corresponding count fields must make the zero denominator visible.
- Missing manual review must never be treated as evidence of safety.

## Boundary Statement

This safety contract only serves the experiment-outside expert-side Manhattan
toolchain. It is not part of the A-line thesis-facing protocol. It does not
change formal `g_t`, routing, admission, worker profile, worker tier, or any
P1/C1/C2/T1/V1 artifact. It does not authorize worker-facing UI, annotation
writeback, or automatic correction.

## Implementation Gate

Before implementing height reproject, a future patch must add tests that prove:

- OOS and non-Manhattan metadata suppress the operation.
- `layout_height_spread_high` prevents candidate return.
- target `height_residual_high` prevents candidate return.
- `top_not_above_bottom` suppresses the operation.
- missing or unparseable `max_y_delta` does not return a candidate.
- expert-review y delta does not return a candidate.
- hard-fail y delta suppresses the operation.
- returned candidates, if ever implemented, do not alter x coordinates or other
  pairs.
- no test or implementation writes annotation, `import_json/`, `export_label/`,
  routing, protocol, SOP, or P1/C1/C2/T1/V1 artifacts.
