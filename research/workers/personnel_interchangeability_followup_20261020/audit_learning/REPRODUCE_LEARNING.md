# Portable reconstruction and evidence map

`reproduce_learning.py` takes explicit `--work-root`, `--bundle-root` and `--restored-root`; optional `--native-root` points to an existing replay directory. The bundle root contains `analysis/` and `interchangeability_20261020/`. The restored root contains `work_personnel_typing_A_20261019/`. No user-machine paths or credentials are needed. The staging command copies Python sources unchanged into the specified work root, links explicitly supplied scientific inputs, and refuses to replace divergent existing code.

Use Python with numpy, pandas, scipy, scikit-learn and shapely. All native computation retains frozen commit82c6164b0d4630de5316199c92aa405930973168, B8L2/D10 and N1 off.

Run stages in order, providing the same root arguments each time:

1. `--stage setup`: creates portable layout only. `--stage audit-definitions` independently rebuilds188 forward definitions/11,280 labels plus audit arithmetic; tested successfully at a different work root, with identical audit receipt.
2. `--stage forward`: independently reconstructs all60×328 features and training-fold Q/T controls.
3. `--stage legacy`: reconstructs legacy corner pairs, fits the six preregistered m1 candidates and computes label sensitivity.
4. `--stage mixed`: regenerates H20 native endpoints if absent, extracts them, refits original Rnew2/full/LOBO/inner controls, fits six mixed m1 candidates and evaluates paired original controls.
5. `--stage history-block-native`: generates the frozen metadata-only m2 panel and computes native outputs.
6. `--stage history-block-pairs`: computes all exact disjoint-block corner comparisons, retaining unavailable/mismatch outcomes.
7. `--stage block-fit`: runs synthetic objective tests and the fixed two-candidate block-level experiment.

Native runner directly accepts standard compact request payloads:

`python BUNDLE/analysis/composition/fusion_runner.py --restored RESTORED --requests REQUESTS.json.gz --out NATIVE_ROOT --jobs 3`

A new output directory forces actual fresh fusion. An existing matching-context output directory permits resumption; report cache reuse separately. Full native caches need not be committed because compact request files, restored-source hashes and this runner reproduce them.

## Frozen scientific records

- Original audit: `CLASS_LEARNING_AUDIT.md`, `AUDIT_RECEIPT.json`, full-forward receipt, original-Rnew2 refit receipt.
- m1 registration: `CORNER_LEARNING_REGISTRATION.json`; explicit extension: `MIXED_HISTORY_EXTENSION_REGISTRATION.json`.
- `corner_fit_legacy/` and `corner_fit_mixed/`: full member IDs/unknowns, all six candidates, five-fold labels, outcome/support ledgers, Q/T/capacity-random controls and original-Rnew2 comparisons.
- `BLOCK_PROBE_FREEZE.json`: legacy meanK3 discovery nomination fixed before reused-assessment block outputs. Its negative m2 transfer remains part of the results; later fits cannot replace it.
- `fresh_blocks/fresh_block_requests.json.gz`: class-specific nested n5–17 curves plus category-independent m2/m5 endpoint libraries; exact matched anchors only for cross-method ranking.
- `BLOCK_LEARNING_REGISTRATION.json`, `history_blocks/history_block_requests.json.gz`: finite direct m2 experiment using history only.
- `block_fit/`: direct block-level labels and training/CV/failure ledgers after completion.

Legacy/mixed m1 models use a single-person replacement representation. Direct m2 models compare exact exchanged-block class-count vectors and actual nonlinear final team outcomes. Neither construction establishes universal equivalence. Unique cyclic correspondence is an operational geometric candidate, not semantic proof. All target images already used in this research remain reused internal assessment, not a new blind holdout.
