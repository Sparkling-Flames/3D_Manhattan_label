# Manhattan Constrained Fit Plan v1

Status: M14.1 / M14.2 dev-only prototype plan. This is an experiment-outside /
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
- Search deterministic Manhattan yaw candidates. Candidate yaws are derived from
  adjacent BEV edge angles modulo `pi/2` plus a small fixed grid over
  `[0, pi/2)`.
- For each yaw, rotate BEV points by `-yaw`, fit a closed axis-aligned Manhattan
  polygon by constraining alternating edges to orthogonal axes and solving
  grouped coordinate means, rotate the candidate back, and choose the lowest
  normalized residual.
- Estimate a global `layout_height_candidate` from the fitted BEV distances and
  observed ceiling elevations:
  `H_i = camera_height + cs_i * tan(v_ceiling_i)`.
- Use a robust median height candidate, report `layout_height_spread`, and fail
  safely if the height is outside the conservative 2.0-4.5 m plausible range or
  if the spread is too large.
- Project fitted floor and ceiling `y` values back to LS 0-100 with
  `atan2`: floor uses `atan2(-camera_height, cs_i)`, ceiling uses
  `atan2(layout_height_candidate - camera_height, cs_i)`.
- The resulting `fitted_points` and `per_point_delta` are dev-only review
  candidates, not correction instructions and not writeback payloads.

Output:

- `fit_status`
- `fit_residual`
- `fit_confidence`
- `fitted_points`
- `per_point_delta`
- `direction_label`
- `warnings`
- `manhattan_yaw_rad`
- `manhattan_yaw_deg`
- `yaw_search_count`
- `yaw_fit_residual`
- `selected_orientation_pattern`
- `layout_height_candidate`
- `layout_height_spread`
- `y_projection_model = "camera_height_layout_height_atan2_v1"`
- `camera_height`

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
- `implausible_layout_height`
- `layout_height_unstable`

## M14.1 Yaw-aware Fitting

The initial M14 skeleton assumed Manhattan axes were camera-aligned. M14.1
removes that assumption by searching over deterministic yaw candidates. This
keeps runtime small while allowing a room rotated relative to the camera frame to
fit cleanly. The selected yaw is reported as `manhattan_yaw_rad` /
`manhattan_yaw_deg`; the candidate count is reported as `yaw_search_count`.

The fitting still preserves pair count and order. It does not reorder corners,
does not infer a next corner, and does not output target coordinates.

## M14.2 Height-aware Reprojection

The M14 skeleton preserved original ceiling/floor `y`, which avoided invalid
global median bands but did not produce height-aware top/bottom candidates. M14.2
uses the fitted top-down distances and observed ceiling elevations to estimate a
single room height candidate. It then reprojects both ceiling and floor `y` using
the same angular `atan2` model:

- floor: `v_f = atan2(-camera_height, cs_i)`
- ceiling: `v_c = atan2(layout_height_candidate - camera_height, cs_i)`
- LS y: `y = (0.5 - v / pi) * 100`

The conservative plausible height range is 2.0-4.5 m. Values outside that range
fail with `implausible_layout_height`. Large cross-corner height spread fails or
warns before any UI integration is considered.

## Boundary

This M14 work is dev-only / sandbox-only / no writeback. It does not modify
`tools/paper_a_manhattan/dev_only/*.user.js`, the official userscript, Label Studio config,
`vis_3d.html`, `ls_3d_logic.js`, `import_json/`, `export_label/`,
`analyze_quality.py`, routing, protocol, schema, or SOP files. It is a pure
Python fitting core and synthetic test layer for future review before any UI
integration is considered.
