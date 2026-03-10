# Pooled QA Summary

- This pack is for pooled QA only, not paper main figures.
- Every figure is stratified by `schema_version`.
- Active-time figures are additionally split by `active_time_source`.
- Dataset-group aggregation is filtered by trusted `dataset_group_source` values first.

## Inputs
- merged_csv: analysis_results/registry_20260308/merged_all_v0.csv
- annotation_registry: analysis_results/registry_20260308/annotation_registry_v1.csv
- active_time_registry: analysis_results/registry_20260308/active_time_registry_v1.csv

## High-level counts
- rows: 189
- tasks: 156
- annotators: 4

## schema_version counts
| schema_version      |   rows |
|:--------------------|-------:|
| v2_structured       |    182 |
| legacy_quality_only |      7 |

## active_time_source by schema_version
| schema_version      | active_time_source   |   rows |   non_null_active_time |
|:--------------------|:---------------------|-------:|-----------------------:|
| legacy_quality_only | log                  |      7 |                      7 |
| v2_structured       | lead_time_fallback   |    133 |                    133 |
| v2_structured       | log                  |     49 |                     49 |

## dataset_group_source by schema_version
(empty)

## trusted dataset_group sources
planned_registry_match, export_task_data

## Saved figures
- 01_rows_by_schema_version.png
- 02_join_status_by_schema_version.png
- 03_active_time_hist_by_schema_and_source.png
- 04_active_time_box_by_schema_and_source.png
- 05_annotator_profile_by_schema_version.png

## Skipped figures
- 06_dataset_group_source_by_schema_version.png: missing required columns or no eligible rows
- 07_dataset_group_counts_trusted.png: missing required columns or no eligible rows