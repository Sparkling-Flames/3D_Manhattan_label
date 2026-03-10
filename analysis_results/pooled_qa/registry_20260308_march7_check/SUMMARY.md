# Pooled QA Summary

- This pack is for pooled QA only, not paper main figures.
- Every figure is stratified by `schema_version`.
- Active-time figures are additionally split by `active_time_source`.
- Dataset-group aggregation is filtered by trusted `dataset_group_source` values first.

## Inputs
- merged_csv: analysis_results/registry_20260308_march7_check/merged_all_v0.csv
- annotation_registry: analysis_results/registry_20260308_march7_check/annotation_registry_v1.csv
- active_time_registry: analysis_results/registry_20260308_march7_check/active_time_registry_v1.csv

## High-level counts
- rows: 2
- tasks: 2
- annotators: 1

## schema_version counts
| schema_version   |   rows |
|:-----------------|-------:|
| v2_structured    |      2 |

## active_time_source by schema_version
| schema_version   | active_time_source   |   rows |   non_null_active_time |
|:-----------------|:---------------------|-------:|-----------------------:|
| v2_structured    | lead_time_fallback   |      2 |                      2 |

## dataset_group_source by schema_version
| schema_version   | dataset_group_source   |   rows |
|:-----------------|:-----------------------|-------:|
| v2_structured    | export_task_data       |      1 |
| v2_structured    | planned_registry_match |      1 |

## trusted dataset_group sources
planned_registry_match, export_task_data

## Saved figures
- 01_rows_by_schema_version.png
- 02_join_status_by_schema_version.png
- 03_active_time_hist_by_schema_and_source.png
- 04_active_time_box_by_schema_and_source.png
- 05_annotator_profile_by_schema_version.png
- 06_dataset_group_source_by_schema_version.png
- 07_dataset_group_counts_trusted.png

## Skipped figures
- (none)

## Trusted dataset_group counts
| schema_version   | dataset_group    | dataset_group_source   |   rows |
|:-----------------|:-----------------|:-----------------------|-------:|
| v2_structured    | PreScreen_manual | export_task_data       |      1 |
| v2_structured    | PreScreen_semi   | planned_registry_match |      1 |