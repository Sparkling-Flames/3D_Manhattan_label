# Segment-aware Manhattan Refit 3741

- Top candidate: `robust_all_long_edges`
- Method: deterministic weighted Manhattan wall-line offsets/intersections.
- Main adjustment scope: pair 2, chain 5–6–7–8, chain 12–11–1.
- Strong anchor 3–4 movement: `0.5807` (basically preserved).
- Chain 5–6–7–8 preserved: `true`.
- Chain 12–11–1 preserved: `true`.
- ID semantics: all segment/weight/report labels use source_pair_id; geometry uses solver_position after explicit mapping.
- Source pair 2 maps to solver position `1`.
- Source pair 2 movement: `8.4608`.
- Pairs 9–10 height was reprojected from the 3–4 height anchor; manual confirmation remains required.
- Self-intersection: `false`.
- Recommendation: `recommended_for_human_review`.
- Automatic writeback is forbidden because this is an expert-side candidate and image evidence remains incomplete.
- accepted/downstream/preference/writeback: `false/false/false/false`.
