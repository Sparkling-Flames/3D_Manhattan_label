# Paper B: Ambiguity-aware enclosed HoHoNet Research Plan v1

> Status: Paper B / non-thesis-facing research planning
>
> Scope: planning only. This document does not implement training code, change the current A-line protocol, change Label Studio production imports, or generate any routing artifact.

## 0. Paper B positioning and A-line boundaries

This document serves a second research line, hereafter **Paper B: Ambiguity-aware enclosed HoHoNet**.

Paper B is independent from the current A-line annotation-process paper. It is not an official protocol extension for the A-line thesis-facing workflow.

The A-line HOHONET main protocol remains unchanged:

`Pilot -> PreScreen -> Calibration -> Main(Test + Validation)`

This document does not modify `P1 / C1 / C2 / T1 / V1`, does not alter worker admission, `w_max`, `r_u`, `r_u^(s)`, `tau_d`, Score, worker tier, routing freeze, `k0/kmax`, or stop rules, and must not use A-line Main/Test/Validation outcomes to revise those contracts.

Paper B target:

- Train an enclosed-only HoHoNet layout predictor.
- Add auxiliary supervision for ambiguity and overextend risk.
- At inference time, output only an enclosed layout plus risk cues.
- Use risk cues for relabel audit, candidate mining, and possible annotator caution support.

Paper B is explicitly not:

- a runtime nesting of Bi-Layout inside HoHoNet;
- a final two-layout `enclosed + extended` prediction system;
- a replacement for the current enclosed-only annotation protocol;
- a replacement for the A-line OOS gate;
- an OOS classifier;
- a formal `g_t` implementation or a source of formal `g_t` fields;
- a thesis-facing V1 routing artifact;
- a source of A-line main conclusions.

Bi-Layout-style data and relabeling ideas are used only as sources for ambiguity supervision, GT cleaning, and overextend-risk learning.

## 1. Paper B research questions

### RQ-B1: Bi-Layout relabel audit

Does Bi-Layout-style relabeling reduce cross-door overextension and enclosed/extended policy mixing in MP3D / MatterportLayout-style annotations?

Primary focus:

- whether relabeled enclosed targets stop at the intended room boundary more consistently than original mixed-policy labels;
- whether relabeling reduces `overextend_adjacent` cases;
- whether relabeling creates a usable supervised signal for opening ambiguity.

This RQ must be answered before training. If relabeling does not reduce cross-door overextension, Paper B should not proceed to model claims based on those labels.

### RQ-B2: Ambiguity-aware enclosed HoHoNet

Can an ambiguity-aware enclosed HoHoNet reduce `overextend_adjacent` while preserving enclosed layout accuracy?

Primary focus:

- enclosed-only layout quality;
- reduced cross-door expansion;
- auxiliary ambiguity and overextend heads as regularizers / risk estimators;
- comparison against an enclosed-only fine-tuning baseline.

### RQ-B3: Risk cue as candidate mining, not OOS classification

Can ambiguity / overextend cues serve as candidate miners for human relabeling and caution review, rather than as an OOS classifier?

Primary focus:

- precision of mined relabel candidates;
- false positive burden from cue exposure;
- false negative cases where overextend risk was missed;
- evidence that cues enrich ambiguity cases without becoming automatic `scope` or OOS labels.

## 2. B0 data audit priority: Bi-Layout relabel audit

Before any training, Paper B must run **B0: Bi-Layout relabel audit**.

Goal:

- verify that the relabeled data genuinely reduces cross-door overextension;
- verify that relabeled data reduces `overextend_adjacent` / cross-door expansion under the project's enclosed-only annotation policy;
- measure negative side effects, especially under-coverage and over-conservative truncation;
- separate reliable enclosed targets from uncertain or weakly derived targets;
- determine whether ambiguity and overextend labels are strong enough for auxiliary supervision.

B0 is not model training. Its output is an audit table and a filtered training-candidate list, not an automatic GT replacement.

Planned output directory:

`analysis_results/bilayout_relabel_audit/`

Planned outputs:

- `relabel_inventory.csv`
- `overextend_reduction_audit.csv`
- `ambiguity_case_contact_sheets/`
- `relabel_audit_report.md`

These outputs are Paper B research artifacts only. They are not A-line P1/C1/C2/T1/V1 artifacts and must not be consumed by the A-line routing contract.

### 2.0 Latest visual audit observations to convert into B0 checks

The HoHoNet-vs-Bi-Layout relabel contact sheets suggest the following working hypotheses. B0 must turn these visual observations into descriptive audit counts rather than assume they are true globally.

`hard_prediction_failure`:

- Bi-Layout-style relabel often reduces HoHoNet cross-door expansion and over-parsing.
- The improvement is visually substantial in many samples.
- Some cases remain wrong for both HoHoNet and Bi-Layout.
- A small number of cases show Bi-Layout introducing new errors that HoHoNet did not show, including new cross-door expansion or over-parsing.

`highest_g_score`:

- Similar to `hard_prediction_failure`.
- Bi relabel often pulls the layout back toward the camera room and reduces `overextend_adjacent` / over-parsing.
- This group may overlap with or duplicate `hard_prediction_failure`; B0 must deduplicate by `task_id`, `image_id`, and `scene_id` before reporting group-level statistics.

`nominal_prediction_structure`:

- HoHoNet and Bi relabel are mostly similar.
- Bi relabel may slightly reduce cross-door labeling in some cases.
- This group is primarily a safety check: it tests whether Bi-style enclosed relabel does not damage already-normal samples.

`soft_prediction_complexity`:

- This is the key counterexample group.
- Some samples are OOS or possible OOS, and some are extremely complex.
- Bi relabel can reduce cross-door expansion extent, but it can also become too conservative.
- Several samples show major under-coverage where Bi ignores room regions that should probably be labeled as part of the camera room.
- Some samples have strange or unstable Bi relabels.
- These cases should be separated into holdout / ambiguity audit bank, not blindly used as enclosed training targets.

### 2.1 `relabel_inventory.csv`

Recommended row grain:

- one row per image / layout instance.

Recommended fields:

- `sample_id`
- `image_id`
- `scene_id`
- `original_label_ref`
- `relabel_enclosed_ref`
- `extended_reference_ref`
- `has_enclosed_target`
- `has_extended_reference`
- `has_ambiguity_mask`
- `has_overextend_risk_label`
- `target_source`
- `review_status`
- `review_notes`

### 2.2 `overextend_reduction_audit.csv`

Purpose:

- compare original labels and relabeled enclosed targets for cross-door expansion.

Recommended fields:

- `sample_id`
- `original_overextend_adjacent_flag`
- `relabel_overextend_adjacent_flag`
- `overextend_reduced`
- `opening_region_present`
- `boundary_stop_changed`
- `manual_review_required`
- `audit_decision`
- `audit_reason`

Primary B0 audit question:

- Among samples with original cross-door expansion, what fraction does relabeling correct without damaging enclosed-room geometry?

### 2.3 B0 audit schema

B0 should materialize one audit row per deduplicated sample. The preferred table is CSV for inspection plus optional JSONL for richer notes.

Minimum required fields:

- `task_id`
- `image_id`
- `scene_id`
- `source_group`
- `hohonet_corner_count`
- `bilayout_corner_count`
- `hohonet_crossdoor_score`
- `bilayout_crossdoor_score`
- `overextend_reduced`
- `overparse_reduced`
- `bilayout_undercoverage`
- `bilayout_new_error`
- `both_wrong`
- `oos_suspect`
- `open_boundary_ambiguity`
- `expert_verdict`
- `usable_for_B1`
- `audit_notes`

Fixed `source_group` vocabulary:

- `hard_prediction_failure`
- `highest_g_score`
- `nominal_prediction_structure`
- `soft_prediction_complexity`

Fixed `expert_verdict` vocabulary:

- `accept_bilayout_enclosed`
- `accept_with_minor_fix`
- `reject_undercoverage`
- `reject_ambiguous_or_oos`

Field interpretation:

- `hohonet_crossdoor_score` and `bilayout_crossdoor_score` are descriptive risk scores, not accuracy values unless expert GT comparison is available.
- `overextend_reduced=true` means Bi relabel reduced cross-door expansion relative to HoHoNet or original mixed-policy label.
- `overparse_reduced=true` means Bi relabel reduced extra fragments, spurious corners, or over-parsed structures.
- `bilayout_undercoverage=true` means Bi relabel appears too conservative and misses part of the camera room.
- `bilayout_new_error=true` means Bi relabel introduces a visible error not present in HoHoNet or the original candidate.
- `both_wrong=true` means neither HoHoNet nor Bi relabel is acceptable as an enclosed target.
- `oos_suspect=true` is an audit flag only; it is not an OOS classifier and does not replace A-line scope adjudication.
- `usable_for_B1=true` is allowed only for `accept_bilayout_enclosed` and carefully reviewed `accept_with_minor_fix` rows.

### 2.4 B0 descriptive metrics

B0 should report descriptive rates over deduplicated samples:

- `overextend_reduction_rate`
- `overparse_reduction_rate`
- `undercoverage_introduction_rate`
- `new_error_rate`
- `both_wrong_rate`
- `usable_enclosed_target_rate`
- `ambiguous_or_oos_holdout_rate`

Suggested definitions:

- `overextend_reduction_rate = mean(overextend_reduced)`
- `overparse_reduction_rate = mean(overparse_reduced)`
- `undercoverage_introduction_rate = mean(bilayout_undercoverage)`
- `new_error_rate = mean(bilayout_new_error)`
- `both_wrong_rate = mean(both_wrong)`
- `usable_enclosed_target_rate = mean(usable_for_B1)`
- `ambiguous_or_oos_holdout_rate = mean(expert_verdict == reject_ambiguous_or_oos OR oos_suspect)`

These should be called descriptive audit metrics, not accuracy metrics, unless expert GT comparison is actually available.

All metrics should be reported:

- overall;
- by `source_group`;
- on a deduplicated `hard_prediction_failure + highest_g_score` union;
- separately for `nominal_prediction_structure`;
- separately for `soft_prediction_complexity`.

### 2.5 Group-specific interpretation

`hard_prediction_failure` and `highest_g_score`:

- Primary evidence source for potential overextend reduction.
- Must be deduplicated before group-level claims.
- Positive B0 signal: `overextend_reduced` and `overparse_reduced` are common, while `bilayout_new_error` remains uncommon.

`nominal_prediction_structure`:

- Safety check group.
- Expected effect is small.
- Main question: does Bi relabel avoid damaging already-normal samples?
- A high `reject_undercoverage` or `bilayout_new_error` rate in this group should block naive relabel adoption.

`soft_prediction_complexity`:

- Stress / counterexample group.
- Main question: how often does Bi relabel become too conservative or unstable?
- These samples should preferentially enter holdout / ambiguity audit bank unless expert review explicitly marks them usable.
- This group is where under-coverage and OOS contamination risk must be reported, not hidden.

### 2.6 B1 gate conditions

Proceed from B0 to B1 only if all conditions hold:

- Deduplicated `hard_prediction_failure + highest_g_score` samples show `overextend_reduced` clearly more often than `bilayout_new_error`.
- `nominal_prediction_structure` samples have low `reject_undercoverage` / `bilayout_undercoverage` rate.
- `soft_prediction_complexity` samples can be cleanly split into `usable_for_B1=false` holdout cases rather than being forced into training.
- The audit table can identify enough `accept_bilayout_enclosed` and `accept_with_minor_fix` samples to build a clean enclosed-only fine-tuning set.

B1 remains:

- enclosed-only HoHoNet fine-tuning baseline;
- no ambiguity head yet;
- no overextend-risk auxiliary head yet;
- no dual-head model yet;
- no Label Studio caution cue yet.

### 2.7 `ambiguity_case_contact_sheets/`

Purpose:

- visually inspect cases where original and relabeled boundaries disagree;
- separate true opening ambiguity from noisy relabeling;
- provide qualitative evidence for Paper B data quality.

Each contact sheet should include:

- input panorama;
- original / extended reference boundary;
- relabeled enclosed target;
- opening-region candidate;
- optional current HoHoNet prediction;
- audit label and notes.

### 2.8 `relabel_audit_report.md`

Required sections:

- inventory summary;
- relabel source and provenance;
- overextend reduction summary;
- under-coverage / over-conservative truncation summary;
- new-error summary;
- group-level metrics with deduplication notes;
- ambiguity case taxonomy;
- exclusion criteria for weak targets;
- decision on whether B1/B2 training is justified;
- known limitations.

## 3. Training target construction from Bi-Layout-style relabeling

Bi-Layout should be interpreted conservatively. It does not provide a fully automatic MatterportLayout enclosed-vs-extended classifier. Its useful contribution for Paper B is a semi-automatic way to identify opening-induced ambiguity and to derive training signals around enclosed room-boundary stopping decisions.

### 3.1 Source objects

For each panorama image, Paper B may use:

- `G_orig`: original MatterportLayout / MP3D-style layout annotation, often closer to an extended-room or mixed-policy layout.
- `G_enc`: adjudicated or relabeled enclosed target.
- `G_ext`: extended reference.
- `Q_enc`: one or more enclosed proposals generated during relabeling.
- `opening_candidates`: columns, corners, or BEV regions suspected to contain openings or cross-room ambiguity.
- `P_hoho`: optional current HoHoNet prediction, used only for Paper B auxiliary analysis.

Minimum provenance fields:

- `target_source`: `manual_adjudicated`, `bilayout_relabel`, `original_as_extended`, `single_enclosed_only`, or `unknown`.
- `has_enclosed_target`: boolean.
- `has_extended_reference`: boolean.
- `has_ambiguity_mask`: boolean.
- `has_overextend_risk_label`: boolean.
- `review_required`: boolean.

### 3.2 `enclosed_target`

`enclosed_target` is the only layout target optimized by the main layout head.

Priority order:

1. Use manually adjudicated enclosed GT if available.
2. Use Bi-Layout-style selected enclosed proposal only when the selection step has human approval or an equivalent audited adjudication record.
3. If the dataset is already enclosed-only and no opening ambiguity is identified, use the existing enclosed annotation.
4. If only `G_orig` exists and its enclosed-vs-extended status is unclear, do not use it as a confident enclosed target unless B0 audit marks it as safe.

Recommended fields:

- `enclosed_target_cor`
- `enclosed_target_bon`
- `enclosed_target_valid`
- `enclosed_target_source`
- `enclosed_target_review_note`

Training implication:

- Samples with `enclosed_target_valid=true` participate in `L_layout_enclosed`.
- Samples without a reliable enclosed target must not train the main enclosed layout head as clean supervision.

### 3.3 `extended_reference`

`extended_reference` is not an output target of the final model. It is a reference used to derive ambiguity and overextend-risk supervision.

Possible sources:

- original MP3D / MatterportLayout annotation when it follows an extended or mixed policy;
- Bi-Layout raw / extended branch label;
- manually retained extended reference for the same image.

Training implication:

- Samples with both `enclosed_target` and `extended_reference` can provide strong auxiliary supervision.
- Samples with only `extended_reference` but no reliable `enclosed_target` should not train the enclosed layout head.
- `extended_reference` is not emitted at inference time and must not be shown as an authoritative alternative annotation.

### 3.4 `ambiguity_mask`

`ambiguity_mask` marks image columns or local regions where enclosed and extended boundaries diverge, especially around openings, doorways, or cross-room continuation cues.

Recommended construction:

1. Convert `enclosed_target` and `extended_reference` into aligned 1D boundary curves.
2. Compute per-column boundary disagreement:
   - ceiling difference;
   - floor difference;
   - optional corner-neighborhood difference.
3. Mark a column ambiguous if boundary disagreement exceeds a prespecified pixel threshold or if it lies in an audited opening proposal region.
4. Optionally dilate the mask around candidate openings to reflect annotation uncertainty.

Recommended fields:

- `ambiguity_mask_1d`
- `ambiguity_score_1d`
- `ambiguity_mask_source`
- `ambiguity_mask_valid`

Training implication:

- Strong labels exist when both enclosed and extended references are available or when opening regions are manually audited.
- Weak proposal-derived masks should be down-weighted.

### 3.5 `overextend_risk_label`

`overextend_risk_label` is an auxiliary task-level label predicting whether a model is likely to extend across a boundary that should be stopped under the enclosed-only protocol.

Recommended positive sources:

- large enclosed-vs-extended divergence near an opening;
- original annotation or model proposal crossing into adjacent room while enclosed target stops at doorway/wall boundary;
- manual review tags marking cross-door expansion risk;
- Paper B-specific overextend cases, not A-line P1 scoring outputs.

Recommended negative sources:

- enclosed target and extended reference agree within tolerance;
- no opening candidate and no cross-room continuation evidence;
- manually reviewed nominal enclosed room.

Recommended fields:

- `overextend_risk_label`: `0`, `1`, or `NA`.
- `overextend_risk_confidence`: `strong`, `weak`, or `unknown`.
- `overextend_risk_source`: `enc_ext_delta`, `manual_review`, `proposal_crossing`, or `none`.

Training implication:

- Strong binary labels train `L_overextend_risk`.
- Weak labels may train with reduced weight or be used only for validation.
- `overextend_risk_label` must not be interpreted as OOS truth.

### 3.6 `opening_region_candidate`

`opening_region_candidate` is a geometric or visual support region indicating where a doorway/opening may explain boundary ambiguity.

Recommended construction:

- BEV projection identifies visible candidate corners or interrupted wall segments.
- Enclosed proposal generation marks candidate stop points near openings.
- Boundary differences between enclosed and extended references localize a disagreement span.
- Optional manual audit confirms or rejects the opening region.

Training implication:

- Can supervise the ambiguity heatmap directly or support data filtering.
- Must not become an OOS gate or formal non-IID split truth.

## 4. Paper B staged route

### B0: relabel audit

Run the Bi-Layout relabel audit before any training.

Outputs:

- `analysis_results/bilayout_relabel_audit/relabel_inventory.csv`
- `analysis_results/bilayout_relabel_audit/overextend_reduction_audit.csv`
- `analysis_results/bilayout_relabel_audit/ambiguity_case_contact_sheets/`
- `analysis_results/bilayout_relabel_audit/relabel_audit_report.md`

Exit criterion:

- relabeling demonstrably reduces cross-door overextension more often than it introduces new errors;
- nominal samples show low under-coverage / new-error rates;
- soft-complexity samples are safely routed into holdout / ambiguity audit bank unless expert review marks them usable;
- the audit yields enough `accept_bilayout_enclosed` and `accept_with_minor_fix` rows for B1.

### B1: enclosed-only HoHoNet fine-tuning baseline

Train or fine-tune a baseline enclosed-only HoHoNet using only reliable `enclosed_target` samples.

Purpose:

- establish whether cleaned enclosed labels alone reduce overextension;
- establish enclosed 2D/3D accuracy baseline;
- avoid attributing gains to auxiliary heads before checking label quality.

B1 must remain enclosed-only:

- no ambiguity head yet;
- no overextend-risk auxiliary head yet;
- no dual-head model yet;
- no Label Studio caution cue yet.

### B2: ambiguity-aware enclosed HoHoNet

Add auxiliary heads:

- ambiguity heatmap head;
- overextend risk scalar/head.

Architecture:

```text
Panorama image
  -> shared HoHoNet trunk
      -> enclosed layout head
          -> enclosed boundary / corner prediction
      -> ambiguity heatmap head
          -> 1D ambiguity/opening-risk heatmap
      -> overextend risk head
          -> task-level scalar risk
```

Inference output:

- `enclosed_layout_prediction`
- `ambiguity_heatmap`
- `overextend_risk_score`
- `cue_level`
- `cue_reason`
- `model_version`
- `cue_version`

Inference output must not include final extended layout, automatic `scope`, automatic `model_issue`, formal `g_t`, or V1 routing buckets.

### B3: dual-head HoHoNet as ablation only

A dual-head HoHoNet that predicts enclosed and extended branches may be used only as an ablation.

Allowed use:

- compare whether explicit dual-branch prediction improves ambiguity representation;
- quantify whether B2 auxiliary-head design is sufficient;
- provide analysis figures for Paper B.

Forbidden use:

- make dual-head output the final Paper B deployment target;
- expose enclosed and extended predictions as final two-label output;
- route A-line tasks based on the dual-head output;
- merge dual-head disagreement into formal A-line `g_t`.

### B4: Label Studio caution cue pilot

Only after B1/B2 evidence exists, Paper B may run a caution-cue pilot.

Purpose:

- test whether `cue_level` and `cue_reason` help mine relabel candidates or prompt careful review;
- measure false positive burden and missed risk cases;
- evaluate user-facing decision support.

This pilot must remain outside A-line formal P1/C1/C2/T1/V1 execution.

## 5. Loss design

Total B2 loss:

```text
L = L_layout_enclosed
  + lambda_amb * L_ambiguity_mask
  + lambda_risk * L_overextend_risk
```

Weights must be selected on Paper B development data only. They must not be tuned using A-line P1/C1/C2/T1/V1 outcomes.

### 5.1 `L_layout_enclosed`

Purpose:

- train the main layout head to predict enclosed-only room boundaries.

Eligible samples:

- samples with `enclosed_target_valid=true`.

Excluded samples:

- samples with only ambiguous original GT and no reliable enclosed target;
- samples where enclosed selection was not audited and may encode a wrong stop boundary.

### 5.2 `L_ambiguity_mask`

Purpose:

- train the auxiliary head to localize ambiguous opening or cross-room continuation regions.

Eligible samples:

- strong: both `enclosed_target` and `extended_reference` exist;
- strong: manual opening-region candidate exists;
- weak: proposal-derived ambiguity mask exists but lacks human confirmation.

Possible terms:

- binary cross entropy;
- focal loss for sparse positives;
- soft Dice loss for sparse opening regions;
- lower sample weight for weak masks.

### 5.3 `L_overextend_risk`

Purpose:

- train a task-level scalar that predicts cross-door overextension risk.

Eligible samples:

- `overextend_risk_label in {0,1}`.

Possible terms:

- binary cross entropy;
- class-balanced BCE if positives are rare;
- reduced weights for weak labels.

### 5.4 Label availability matrix

| Sample type | `L_layout_enclosed` | `L_ambiguity_mask` | `L_overextend_risk` | Notes |
|---|---:|---:|---:|---|
| Manually adjudicated enclosed only | yes | no, unless mask exists | optional negative if reviewed | Clean enclosed supervision |
| Enclosed + extended paired label | yes | yes | yes | Strongest auxiliary supervision |
| Original extended only | no | weak only if proposal reviewed | weak/optional | Not clean enclosed supervision |
| Bi-Layout-style relabeled enclosed with audited proposal | yes | yes if extended reference kept | yes if risk adjudicated | Useful for opening ambiguity |
| Proposal-only candidate without human approval | no or weak only | weak only | weak only | Should not drive main target |
| A-line P1/C1/C2/T1/V1 formal data | no | no | no | Do not train or tune Paper B from A-line results |

## 6. Paper B evaluation metrics

### 6.1 Layout accuracy

Primary layout metrics:

- enclosed 2D IoU;
- enclosed 3D IoU.

These metrics evaluate enclosed layout accuracy only.

### 6.2 Overextend reduction

Primary overextend metric:

- `overextend_adjacent` error rate.

Recommended breakdown:

- all evaluated samples;
- samples with opening-region candidates;
- samples with relabeled enclosed/extended disagreement;
- high-risk cue subset.

### 6.3 Ambiguity and candidate mining

Candidate-mining metrics:

- opening ambiguity candidate precision;
- relabel candidate mining precision;
- cue false positive burden;
- cue false negative cases.

Recommended definitions:

- `opening ambiguity candidate precision`: fraction of cue-positive opening candidates confirmed by human audit as true ambiguity / boundary-policy risk.
- `relabel candidate mining precision`: fraction of mined candidates that result in confirmed relabel or confirmed overextend-risk case.
- `cue false positive burden`: fraction of cue-positive cases that are easy nominal enclosed cases after audit.
- `cue false negative cases`: confirmed overextend or ambiguity cases not flagged by the cue.

### 6.4 Metrics not used as Paper B main metrics

Paper B must not use OOS accuracy as a primary metric.

Reasons:

- Paper B cue is not an OOS classifier.
- OOS validity is a separate A-line scope-gate problem.
- Overextend risk and opening ambiguity are narrower phenomena than OOS.

OOS-related observations may be reported only as descriptive audit notes if they arise during human review.

## 7. Label Studio caution-cue integration

Paper B may feed Label Studio only as decision support. It must not prefill, lock, or recommend final `scope`, `difficulty`, or `model_issue` values.

### 7.1 Task metadata fields

Recommended task-level fields:

- `cue_level`: `none`, `low`, `medium`, or `high`.
- `cue_reason`: list of reason codes.
- `warning_text_version`: warning text / UI copy version.
- `ambiguity_heatmap_ref`: optional reference to heatmap payload or preview asset.
- `overextend_risk_score`: numeric scalar for audit, optionally hidden from annotators.
- `cue_model_version`: model checkpoint or inference version.
- `cue_generated_at`: timestamp.

Recommended runtime fields:

- `cue_shown`: boolean.
- `cue_acknowledged`: boolean.
- `cue_acknowledged_at`: nullable timestamp.
- `cue_interaction_count`: optional integer.
- `cue_dismissed`: optional boolean.

### 7.2 UI behavior

Allowed:

- show a non-blocking caution card;
- show reason chips such as `possible_cross_door_extension`;
- show an ambiguity overlay or heatmap if available;
- ask the annotator to inspect the doorway/opening carefully;
- log whether the cue was shown and acknowledged.

Forbidden:

- auto-fill `scope`;
- auto-fill `model_issue`;
- auto-fill `difficulty`;
- force OOS selection;
- hide tasks without human review;
- treat `cue_level=high` as an OOS classifier;
- use cue values as formal CE-only task distribution truth.

Suggested warning copy:

```text
该样本可能存在开口边界或跨门扩张风险。请按 enclosed-only 标注规则独立判断：只标注相机所在房间，不自动采纳模型提示。
```

The exact text should be versioned through `warning_text_version`.

## 8. Prohibited uses

Paper B must not:

- use cue as an automatic OOS label;
- feed cue back into A-line routing;
- train or tune from A-line P1/C1/C2/T1/V1 outcomes;
- use A-line Main/Test/Validation results to reset Paper B thresholds;
- write Paper B results into the current A-line thesis main conclusion chain;
- modify A-line protocol/SOP/paper main text/P1 imports/tools/tests/analysis_results;
- merge Bi-Layout cue into formal A-line `g_t`;
- generate V1 routing artifacts;
- claim OOS gate replacement.
- assume Bi-Layout relabel is automatically correct;
- automatically replace GT with Bi-Layout relabels;
- add B-line caution cue to the A-line formal Semi-Auto condition;
- hide under-coverage or over-conservative truncation cases.

## 9. Acceptance criteria for this planning document

This document is complete only if future readers can tell that:

- Paper B is a separate research plan, not an A-line protocol extension;
- the A-line main protocol is unchanged;
- the final Paper B layout output is enclosed-only;
- Bi-Layout is used for relabel audit, supervision, and cleaning ideas, not runtime nested inference;
- risk cues are candidate-mining and caution signals, not OOS labels;
- no current formal HOHONET artifact is changed by this plan.
