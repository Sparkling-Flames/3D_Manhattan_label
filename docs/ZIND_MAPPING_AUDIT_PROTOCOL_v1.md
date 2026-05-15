# ZInD Mapping Audit Protocol v1

> Status: Paper B / non-thesis-facing data audit planning.
>
> Scope: documentation/specification only. This document does not implement training code, does not modify A-line protocol, and does not affect `P1 / C1 / C2 / T1 / V1`.

## 1. Purpose

This protocol audits whether ZInD layout labels can support Paper B layout-only pretraining and ambiguity supervision.

The audit asks:

- whether any ZInD label type can map to Paper B `Y_enc`;
- whether any ZInD label type can serve as `Y_ext_ref`;
- whether a ZInD sample can be marked `usable_for_B1Z`;
- whether a ZInD sample can provide paired auxiliary supervision and be marked `usable_for_B2_aux`.

## 2. Boundaries

ZInD is not a substitute for the MP3D / MatterportLayout B0 target-domain audit.

ZInD raw / visible labels are not assumed equivalent to this project's enclosed / extended policy. They must be audited before use.

ZInD-derived supervision must not:

- change A-line `P1 / C1 / C2 / T1 / V1`;
- enter formal A-line `g_t`;
- affect A-line routing, OOS gate, admission, `w_max`, `tau_d`, Score, worker tier, `k0/kmax`, or stop rules;
- become an OOS classifier;
- expose `P_ext` as a final Paper B output.

## 3. Proposed audit fields

Minimum row-level fields:

- `zind_sample_id`
- `panorama_ref`
- `raw_label_ref`
- `visible_label_ref`
- `candidate_Y_enc_source`
- `candidate_Y_ext_ref_source`
- `has_opening`
- `mapping_confidence`
- `mapping_failure_reason`
- `undercoverage_risk`
- `overextend_risk`
- `usable_for_B1Z`
- `usable_for_B2_aux`
- `audit_notes`

Fixed `mapping_confidence` values:

- `high`
- `medium`
- `low`
- `reject`

## 4. Mapping decisions

`candidate_Y_enc_source` should identify which ZInD label, if any, behaves like the Paper B enclosed target after audit.

`candidate_Y_ext_ref_source` should identify which ZInD label, if any, can serve as an extended reference for auxiliary disagreement supervision.

`usable_for_B1Z=true` requires a usable `Y_enc` mapping.

`usable_for_B2_aux=true` requires usable paired evidence for ambiguity or overextend-risk supervision. A sample may be usable for B1-Z but not B2 auxiliary supervision.

## 5. Required report

The B0-Z report must include:

- mapping acceptance rate;
- ambiguous-pair availability;
- mapping failure taxonomy;
- examples where raw / visible do not match the project enclosed policy;
- domain gap risks relative to MP3D / MatterportLayout.

The report must explicitly state when raw or visible labels are rejected, too conservative, overextended, or ambiguous under the project policy.

## 6. Evaluation relevance

B0-Z supports only Paper B ablations:

- B1b / B1-Z layout-only pretraining;
- B2 auxiliary ambiguity / overextend supervision when paired evidence is audited;
- data-source ablation against B1a.

It does not replace B0, does not define A-line artifacts, and does not provide OOS accuracy as a primary metric.

