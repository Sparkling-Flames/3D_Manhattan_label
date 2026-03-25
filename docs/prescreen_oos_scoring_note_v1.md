# PreScreen OOS Scoring Note v1

This note hardens the Stage 1 OOS scoring semantics without changing pool quotas, selection-freeze conclusions, or any existing JSON readiness status.

## 1. Scope of this note

- This note clarifies how OOS items are interpreted in `PreScreen_manual` and `PreScreen_semi`.
- This note does not declare a final OOS Stage 1 quota.
- This note does not change `r_u^(0)`, `w_max`, or any current blocked/ready conclusion.

## 2. Primary semantics

- OOS remains part of Stage 1 PreScreen only as a small separately scored scope/gate or stress subset.
- For OOS items, the primary scored signal is the `scope` decision.
- `difficulty` may be retained for descriptive audit, risk explanation, and error attribution.
- `model_issue` is not used as the correctness criterion for OOS scoring.

## 3. Manual vs semi roles

- `PreScreen_manual`: the small OOS subset is scored by scope/gate correctness rather than geometry IoU.
- `PreScreen_manual`: `difficulty` is auxiliary only; `model_issue` is not used for OOS correctness.
- `PreScreen_semi`: the smaller OOS stress subset is used for separate scope/blind-trust audit.
- `PreScreen_semi`: OOS stress items are still scored primarily by `scope`; `difficulty` remains auxiliary; `model_issue` is not required for OOS adjudication.

## 4. Exclusions from the geometry chain

- OOS items do not enter `r_u^(0)` estimation.
- OOS items do not enter `w_max` locking.
- OOS items do not enter geometry-based fold or replay analyses.
- OOS items remain separately reported rather than merged into the main geometry reliability estimand.

## 5. Current repository boundary

- Current OOS artifacts remain a candidate bank rather than a final frozen Stage 1 quota or dedicated binding.
- Current scoring semantics should therefore be understood as protocol boundary clarification rather than execution completion.
