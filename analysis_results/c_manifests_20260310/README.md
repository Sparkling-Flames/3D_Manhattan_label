# C-Line Manifest Bundle (2026-03-10)

This bundle materializes the current-week Dev C deliverables as joinable artifacts
anchored to the A-line planned registry.

Inputs used:

- `analysis_results/registry_20260308/task_registry_v2.csv`
- `import_json/outline_v2_seed20260228/label_studio_split_report_v2.json`
- `trap集/复核总表_20260307.md`
- current C1 / C2 contracts under `约束/`

Files in this bundle:

1. `trap_manifest_schema_v1.json`
   - schema contract for semi trap manifest rows
2. `natural_failure_bank_index_v1.csv`
   - reviewed natural-failure and OOS-gate exemplar bank with A-line join metadata
3. `embedding_ood_protocol_v1.json`
   - frozen procedure for the `d_t` / `I_t_OOD` pipeline
4. `trap_manifest_draft_v1.csv`
   - current draft for `PreScreen_semi` trap rows
5. `manual_anchor_bank_index_v1.csv`
   - unique base-task index for manual anchor coverage, collapsed from A-line anchor rows
5. `manifest_bundle_summary_v1.json`
   - high-level counts and status summary

Current status:

- trap manifest schema: `frozen_rule`
- natural failure bank: reviewed exemplars are `realized` as bank entries
- embedding OOD protocol: `frozen_rule`
- trap manifest draft: `2 realized natural exemplars + 13 frozen_rule synthetic rows`
- manual anchor bank: `realized`

Important boundary:

- This bundle does not yet materialize perturbation geometry outputs.
- Synthetic rows are frozen at the rule/selection layer, not yet at generated-corners layer.
- Manual anchors are now expanded into a dedicated joinable bank index, but not yet wired into downstream routing/service contracts.
