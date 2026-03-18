# Anchor Gap Analysis and Supplement Notes (2026-03-15)

## Purpose

This note is a gap-analysis memo for B/C-line planning. It is not proof that the
thesis-facing Stage 1 target counts are already realized.

Two counts must stay separate:

- `joinable bank rows`: what currently exists in the anchor/trap bank files
- `thesis-facing realized anchors`: what the Stage 1 split/selection path can
  legitimately claim for the paper

Bank growth can improve coverage, but it does not by itself resolve split
alignment.

## Current state

- `manual_anchor_bank_index_v1.csv` currently contains a joinable bank snapshot
  that mixes:
  - `PreScreen_manual` anchor rows
  - `Calibration_anchor` common-item rows
- The thesis-facing Stage 1 target remains:
  - `PreScreen_manual` total = `30`
  - `PreScreen_manual` expert anchors = `20-22`
  - `PreScreen_semi` total ~= `18`
- Current repository planning is still misaligned with that target. See
  [phase1_target_vs_realized_manifest_v1.json](/d:/Work/HOHONET/analysis_results/phase1_progress_20260311/phase1_target_vs_realized_manifest_v1.json).

## Coverage gap candidates

The following base tasks are reasonable manual-bank supplements because they
cover difficulty families that are important for expert-anchor review:

| Task ID | Base task ID | Candidate value |
| :--- | :--- | :--- |
| `task497` | `uNb9QFRL6hY_d02f87bbb0414146a7a15070110a0384` | occlusion-heavy manual case |
| `task462` | `UwV83HsGsw3_8e9c912f525744eeaea21083a20a1596` | seam/stretch manual case |
| `task509` | `wc2JMjhGNzB_dc4a9f470b834de1983c7e605ff06b2e` | glass/reflection manual case |
| `task510` | `B6ByNegPMKs_b8e1ecf1bd044e7292581a66683e7993` | additional seam/distortion case |

These rows are useful as `bank supplements`.

They are not automatically equivalent to:

- thesis-facing `PreScreen_manual` realized expert anchors
- split-aligned Stage 1 counts
- registry-joinable expert-reference anchors

## Semi pool note

- `natural_failure_bank_index_v1.csv` remains a bank-level asset.
- Reaching the thesis-facing `PreScreen_semi ~= 18` still requires a separate
  selection/materialization decision.
- Natural-failure bank size must not be used as a substitute for the formal
  thesis-facing semi count.

## Operational conclusion

- Appending the four manual-bank supplement rows is acceptable as a bank
  coverage improvement.
- The paper path must still treat split alignment separately.
- The correct claim is:
  - "manual bank coverage improved"
- The incorrect claim is:
  - "Stage 1 expert-anchor target is now satisfied"
