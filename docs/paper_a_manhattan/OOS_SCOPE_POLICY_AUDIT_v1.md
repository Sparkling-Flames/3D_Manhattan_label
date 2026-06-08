# OOS Scope Policy Audit v1

Status: audit policy note for smoke/debug tools. This document does not modify
formal protocol, routing, schema, SOP, Label Studio UI, or official analysis
behavior.

## Core Rule

A scope vote is not adjudicated OOS.

In Label Studio exports, `scope` is an annotator observation. It records how one
annotator interpreted the current image/task boundary. It is not task-level
truth, not a final OOS label, and not proof that the image is impossible to
annotate.

## Task-level OOS

Task-level OOS requires one of the following:

- expert adjudication;
- an explicit adjudication artifact;
- a frozen protocol-defined task-level decision.

Without that, one OOS vote, multiple OOS votes, or majority OOS votes are only
scope_distribution / disagreement evidence. They can guide review, but they must
not be silently promoted into task truth.

## Audit Eligibility vs Geometry Debug

Audit eligibility is not task truth.

For M_geo / Manhattan constrained fitting audits, an audit may choose a narrow
eligibility rule such as `scope=normal` so that primary audit summaries are not
mixed with OOS-labeled submissions. That rule is a reporting filter only. It
does not say that OOS-voted annotations are geometrically meaningless.

Geometry-debug can run regardless of scope if keypoints are parseable. The debug
pass answers a different question: "What does the geometry parser/fitter do with
these points?" It does not adjudicate OOS, does not score correctness, does not
write annotation corrections, and does not feed formal `g_t`, routing, worker
tier, or `P1/C1/C2/T1/V1` artifacts.

## M15.2 Smoke Audit Convention

`tools/paper_a_manhattan/audit_manhattan_constrained_fit_smoke.py` keeps two separate layers:

- audit candidate summary: normal-only, plus any future explicit
  `manhattan_assumable=true` gate;
- `geometry_debug`: scope-independent, parseable-keypoint debug.

Summary counts must remain separated:

- `audit_ineligibility_counts`: scope or metadata filters that keep an
  annotation out of the normal-only audit candidate summary;
- `preview_incompatibility_counts`: current-preview parser failures such as odd
  keypoints, duplicate pairs, or unresolved seam order;
- `fit_failure_counts`: constrained-fit failures after preview-compatible
  keypoints are available.

OOS scope belongs in `audit_ineligibility_counts`, not
`preview_incompatibility_counts`. Missing or unknown scope is separate from OOS.

All geometry-debug outputs must carry:

- `geometry_debug_not_oos_adjudication=true`

This explicitly prevents scope-independent geometry-debug from being misread as
task-level OOS adjudication.
