# Complete v3 uncertainty-analysis delivery

This index points to files committed directly to branch `analysis/full-uncertainty-data-mining-20260821`. They are not only GitHub Actions artifacts.

## Primary advisor files

- [`FULL_UNCERTAINTY_DATA_REPORT_ZH_V3.md`](full_uncertainty_data_mining_20260821_v3/FULL_UNCERTAINTY_DATA_REPORT_ZH_V3.md)
- [`Paper_A_完整数据整理与不确定性分析报告_20260821_v3.docx`](full_uncertainty_data_mining_20260821_v3/Paper_A_完整数据整理与不确定性分析报告_20260821_v3.docx)
- [`Paper_A_完整数据整理与分析工作簿_20260821_v3.xlsx`](full_uncertainty_data_mining_20260821_v3/Paper_A_完整数据整理与分析工作簿_20260821_v3.xlsx)
- [`Paper_A_完整数据整理报告与全部分析结果_20260821_v3.zip`](full_uncertainty_data_mining_20260821_v3/Paper_A_完整数据整理报告与全部分析结果_20260821_v3.zip)
- [`full_uncertainty_data_mining_20260821_v2_results_snapshot.zip`](full_uncertainty_data_mining_20260821_v3/full_uncertainty_data_mining_20260821_v2_results_snapshot.zip)

## Required complete statistics

- [`SEMI_25_CONVERGENCE_EXPANSION_ALL_IMAGES.csv`](full_uncertainty_data_mining_20260821_v3/SEMI_25_CONVERGENCE_EXPANSION_ALL_IMAGES.csv): all 25 paired images, not selected examples.
- [`PROPOSAL_TASK_ANCHORING_AND_DISCOVERY.csv`](full_uncertainty_data_mining_20260821_v3/PROPOSAL_TASK_ANCHORING_AND_DISCOVERY.csv): proposal retention, revision, convergence/expansion, metric trade-offs and interpretation boundaries.
- [`TAG_BEHAVIOR_ALL_CASES.csv`](full_uncertainty_data_mining_20260821_v3/TAG_BEHAVIOR_ALL_CASES.csv): every detected acceptable-proposal/edit and trivial-tag/quality-consensus case.
- [`CROWD_GT_101_GEOMETRIC_CAUSE_AUDIT.csv`](full_uncertainty_data_mining_20260821_v3/CROWD_GT_101_GEOMETRIC_CAUSE_AUDIT.csv): all 101 crowd–GT task-condition records and observable geometry differences.
- [`DUAL_ANNOTATOR_GEOMETRY_SENSITIVITY_ALL.csv`](full_uncertainty_data_mining_20260821_v3/DUAL_ANNOTATOR_GEOMETRY_SENSITIVITY_ALL.csv): all 54 two-annotator sensitivity tasks.
- [`ALL_RECORDS_WITH_ORTHOGONAL_FLAGS.csv`](full_uncertainty_data_mining_20260821_v3/ALL_RECORDS_WITH_ORTHOGONAL_FLAGS.csv): complete records with overlapping administrative, assignment, scope, independence and computability flags.
- [`OUT_OF_TASK_AND_NONSELECTED_ROWS.csv`](full_uncertainty_data_mining_20260821_v3/OUT_OF_TASK_AND_NONSELECTED_ROWS.csv): out-of-task, unplanned, noncanonical and revision rows.
- [`ALL_IMAGE_INSTANCE_INDEX.csv`](full_uncertainty_data_mining_20260821_v3/ALL_IMAGE_INSTANCE_INDEX.csv): full task/image reference and repository-image resolution audit.
- [`case_galleries/`](full_uncertainty_data_mining_20260821_v3/case_galleries/): image contact sheets where source images are available in the repository.

## Validation and reproducibility

- [`VALIDATION_SUMMARY.json`](full_uncertainty_data_mining_20260821_v3/VALIDATION_SUMMARY.json)
- [`V3_PACKAGE_SHA256.txt`](full_uncertainty_data_mining_20260821_v3/V3_PACKAGE_SHA256.txt)
- [`OUTPUT_MANIFEST.csv`](full_uncertainty_data_mining_20260821_v3/OUTPUT_MANIFEST.csv)
- [`INPUT_PROVENANCE_V3.csv`](full_uncertainty_data_mining_20260821_v3/INPUT_PROVENANCE_V3.csv)
- [`DATA_DICTIONARY_ZH_V3.csv`](full_uncertainty_data_mining_20260821_v3/DATA_DICTIONARY_ZH_V3.csv)
- Analysis source is under [`tools/thesis_main/analysis/`](../tools/thesis_main/analysis/).

## Terminology boundary

A decrease in an operational GT/utility score is reported as `negative_metric_change`. It is not used as a direct claim that the worker's geometric revision was intrinsically damaging. Proposal anchoring, Manhattan forced-fit trade-offs, local precision edits, topology changes and final crowd modes are reported separately.
