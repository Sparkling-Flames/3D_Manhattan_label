# 3741 Human-guided 2D-guarded Segment Refit

- Rejected old candidate: `robust_all_long_edges` (`rejected_by_2d_review=true`).
- New top candidate: `pair2_anchored_height_clamped`.
- Source pair 2 movement: top `1.3787`, bottom `1.5229`; guard passed `true`.
- Right-half top_y guard passed: `true`; violations `[]`.
- Chain 5–6–7–8 preserved: `true`.
- Chain 12–11–1 preserved: `true`.
- Source pairs 9–10 require height review; 11–12 require seam-height review; source pair 7 requires chain-height review.
- Old candidate remains only as rejected diagnostic reference.
- 2D visual review is not candidate-specific C4 image evidence.
- 2D overlay: `analysis_results/paper_a_manhattan/segment_aware_manhattan_refit/task218_ann3741_2d_guarded/segment_aware_manhattan_refit_3741_2d_guarded_overlay.html`
- 3D review: `analysis_results/paper_a_manhattan/segment_aware_manhattan_refit/task218_ann3741_2d_guarded/segment_aware_manhattan_refit_3741_2d_guarded_review.html`
- accepted/downstream/preference/writeback/patch: `false/false/false/false/false`.
