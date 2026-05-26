# Manhattan Constrained Fit Plan v1

Status: M14 dev-only prototype plan. This is an experiment-outside /
sandbox-only design note. It is not a formal protocol amendment, not a routing
input, not formal `g_t`, not a correctness metric, and not a
`P1/C1/C2/T1/V1` artifact. No writeback is allowed.

## Motivation

The M13 guide-band display exposed a geometry problem: global horizontal
ceiling/floor median guide bands are visually convenient, but they are invalid
as geometric guidance for equirectangular panoramas. In a panorama, image-space
`y` is an elevation angle, not a shared Euclidean height line. Two ceiling
points from different viewing directions can have different image `y` values
even when they are physically consistent with the same ceiling plane. Therefore
a global median ceiling band or global median floor band can look precise while
pointing the expert tester toward the wrong local adjustment.

The only direct 2D check that remains safe without a layout fit is vertical
corner consistency: for the same physical corner, paired ceiling/floor points
should share the same panorama `u` / Label Studio `x` coordinate within the
current preview tolerance. Directional modification hints beyond that should
come from a constrained Manhattan layout fit, not from global image-space median
bands.

## HoHoNet / MatterportLayout Geometry Reminder

`README_prepare_data_mp3d_layout.md` is referenced by the repository but is not
present in the current checkout. The relevant HoHoNet geometry pattern is still
visible in code paths such as `lib/misc/panostretch.py` and
`lib/dataset/dataset_layout.py`: layout boundaries are not treated as straight
global image-space lines. HoHoNet-style preparation uses camera height, layout
height, floor/ceiling distance, `atan2`, and connected boundary curves such as
`pano_connect_points` to trace the equirectangular projection of adjacent layout
corners.

This matters for M14:

- A Label Studio point `(x, y)` must first be interpreted as panorama angular
  coordinates `(u, v)`.
- Floor or ceiling observations imply geometry through camera height / layout
  height and trigonometric projection, not through a global median image row.
- Wall boundaries should be considered connected boundary curves. A local
  candidate should be consistent with `pano_connect_points`-style projection
  semantics before it is trusted as UI guidance.

## Three Different Outputs

1. Residual audit:
   - Measures how unstable or non-Manhattan-like a submitted layout appears.
   - Produces `fit_status`, `fit_residual`, or component residuals for review.
   - Does not propose a correction and does not write to Label Studio.

2. Manhattan constrained candidate:
   - Estimates a nearby layout candidate under explicit Manhattan constraints.
   - Preserves pair count and pair order.
   - Enforces vertical corner `x/u` consistency, alternating orthogonal wall
     directions, and polygon closure in a top-down approximation.
   - Produces `fitted_points`, `per_point_delta`, and `direction_label` as
     sandbox-only review evidence.

3. Correction / writeback:
   - Would modify annotation data or become an official worker-facing action.
   - This is out of scope for M14. M14 has no writeback, no submit, no official
     userscript integration, and no formal experiment integration.

## M14 Prototype Contract

Input:

- Ordered paired corners in Label Studio 0-100 coordinates.
- Each pair represents one physical vertical corner with a ceiling/top point and
  a floor/bottom point.
- Optional metadata may identify out-of-scope cases.

Processing:

- Convert LS `x` to panorama `u`: `u = x / 100 * 2*pi - pi`.
- Convert LS `y` to elevation `v`: `v = pi/2 - y / 100 * pi`.
- Estimate a lightweight top-down point from `u` and floor elevation using
  camera height.
- Reject odd, duplicate, seam-ambiguous, too-small, self-crossing, open-boundary,
  non-Manhattan, or split-level inputs.
- Fit a closed Manhattan candidate by constraining alternating edges to
  orthogonal axes and solving grouped coordinate means.
- Project the fitted candidate back to LS 0-100 `x` while preserving the original
  ceiling/floor `y` values. This avoids pretending that a global `y` band is a
  valid correction.

Output:

- `fit_status`
- `fit_residual`
- `fit_confidence`
- `fitted_points`
- `per_point_delta`
- `direction_label`
- `warnings`

Fail-safe reasons include:

- `odd_pair_count`
- `duplicate_keypoints`
- `pair_count_lt_4`
- `oos_open_boundary`
- `oos_split_level`
- `oos_geometry`
- `not_manhattan_assumable`
- `wrap_seam_unresolved`
- `self_crossing_input`
- `self_crossing_candidate`
- `fit_residual_too_high`
- `candidate_moves_points_too_far`

## Boundary

This M14 work is dev-only / sandbox-only / no writeback. It does not modify
`tools/dev_only/*.user.js`, the official userscript, Label Studio config,
`vis_3d.html`, `ls_3d_logic.js`, `import_json/`, `export_label/`,
`analyze_quality.py`, routing, protocol, schema, or SOP files. It is a pure
Python fitting core and synthetic test layer for future review before any UI
integration is considered.
