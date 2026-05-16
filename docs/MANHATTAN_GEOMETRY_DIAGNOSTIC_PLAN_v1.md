# Manhattan-aware Geometry Diagnostic Plan v1

> Status note (2026-05-15): `MANHATTAN_GEOMETRY_TOOL_ROADMAP_v2.md` is the current Manhattan tool entry point. This v1 document remains the original Paper A / A-line audit-only planning spec and is retained as supporting context.

> Status: Paper A / A-line audit-side planning.
>
> Scope: documentation only. This file does not implement a tool, change the Label Studio UI, create an annotation condition, change routing, or add any required `P1 / C1 / C2 / T1 / V1` artifact.

## 0. Positioning

The Manhattan-aware geometry diagnostic is a post-hoc audit signal for submitted layouts. It is intended to explain geometric stability, renderability, and refinement discipline after an annotation has already been submitted.

Recommended task-worker notation:

- `M_geo(t,u)` or `geometry_consistency_residual`: task-worker geometry residual.
- `J_u` or `M_geo,u`: worker-level summary of valid residuals.

It is explicitly not:

- an annotation correctness metric;
- a real-time hint shown to workers;
- a new `Semi-Auto + Geometry Guidance` condition;
- part of formal `g_t`;
- a formal OOS classifier;
- a replacement for `r_u`, `LCB(r_u)`, `r_u^(s)`, `T_u`, `C_u`, `G_u`, or the existing worker risk tier contract;
- a source for admission, `w_max`, `tau_d`, Score, worker tier freeze, `k0/kmax`, stop rules, or the Validation routing contract.

## 1. Eligibility

`M_geo(t,u)` is valid only for submitted layouts that are in-scope and Manhattan-assumable.

Exclude and report an explicit reason for:

- OOS samples;
- non-Manhattan rooms;
- split-level or multi-plane layouts;
- open-boundary ambiguity where the intended room envelope is not adjudicable;
- insufficient-evidence cases;
- submissions whose source geometry is missing or cannot be parsed.

Excluded cases must not be silently counted as geometry failures.

## 2. Diagnostic Components

When possible, report components separately:

- `mgeo_vertical_residual`: vertical alignment residual between paired ceiling/floor boundary support.
- `mgeo_manhattan_angle_residual`: deviation from Manhattan-consistent dominant wall directions.
- `mgeo_height_residual`: inconsistency in inferred layout height or floor/ceiling geometry.
- `mgeo_renderability_flag`: whether the submitted layout can be normalized and rendered.
- `mgeo_snap_residual`: residual to the nearest valid Manhattan layout under a fixed snap procedure.

If a composite score is used, it must be audit/sensitivity only. Its weights should be fixed or pre-registered before inspection of Main-Test or Main-Validation outcomes, and it must not become a primary score.

## 3. Proposed Audit Fields

The following fields are proposed audit fields only. They are not required fields for formal `P1 / C1 / C2 / T1 / V1` artifacts unless a future protocol amendment creates an explicit audit-only sidecar.

- `geometry_diag_valid`
- `geometry_diag_exclusion_reason`
- `mgeo_vertical_residual`
- `mgeo_manhattan_angle_residual`
- `mgeo_height_residual`
- `mgeo_renderability_flag`
- `mgeo_snap_residual`
- `geometry_diag_version`

Recommended reporting rule: retain component-level fields even when a composite is absent, NA, or downgraded to sensitivity-only.

## 4. Validation Analyses

Recommended validation analyses are descriptive or associational:

- distribution of `M_geo` over valid in-scope Manhattan-assumable submissions;
- worker-level `J_u` distribution;
- association between high `J_u` and Type-3 geometric failures;
- association with lower `IoU_LOO` or higher expert correction burden;
- qualitative examples comparing low- and high-residual submissions on the same task;
- counterexamples where residual and correctness diverge, including low residual but semantically wrong submissions and high residual but scope/semantic boundary-correct submissions.

These analyses support process evidence and attribution-chain validation. They do not tune routing thresholds, worker tiers, `tau_d`, `Score`, `k0/kmax`, or stop rules.

## 5. A-line Protocol Boundaries

This plan preserves the A-line main protocol:

`Pilot -> PreScreen -> Calibration -> Main(Test + Validation)`

It keeps `P1 / C1 / C2 / T1 / V1` unchanged. It also preserves the separation between `d_t`, `g_t`, and post-submission geometry residuals:

- `d_t` remains a feature-space OOD proxy.
- `g_t` remains prediction-side structural diagnostic based on HoHoNet prediction validity before human annotation.
- `M_geo(t,u)` is post-submission and human-label-derived, so it is audit-only.

The diagnostic must not be used to modify Label Studio production UI, import JSON, assignment manifests, worker-facing annotation conditions, or A-line routing policy.
