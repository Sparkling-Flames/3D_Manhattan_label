# Pooled QA Summary

- This pack is for pooled QA only, not paper main figures.
- It does not replace formal analysis and does not output paper main figures.
- Every figure is stratified by `schema_version`.
- Active-time figures are additionally split by `active_time_source`.
- Dataset-group aggregation is filtered by trusted `dataset_group_source` values first.

## Coverage of this pack
- 主 registry：仅完成 `schema_version` 和 `active_time_source` 分层 QA。
- March 7 enriched：额外验证 `dataset_group_source` 审计与 trusted `dataset_group` 汇总。
- 本次输出对应：主 registry 可用范围：仅完成 `schema_version` 和 `active_time_source` 分层 QA。

## Join-status interpretation
- `task_join_status` 反映 planned/runtime bridge 状态，不能直接解释为标注员行为问题；`ambiguous` / `unmatched` 是为了避免静默强配而显式保留的 join 状态。 registry_suite_summary 当前计数：{'unmatched': 33, 'matched_by_title': 50, 'matched_by_title_condition': 41, 'ambiguous': 32}。

## Active-time interpretation
- `active_time_source=log` 表示 direct active log 命中；`lead_time_fallback` 只是回退到 Label Studio `lead_time`，不是 active log。

## Inputs
- merged_csv: analysis_results/registry_20260308/merged_all_v0.csv
- annotation_registry: analysis_results/registry_20260308/annotation_registry_v1.csv
- active_time_registry: analysis_results/registry_20260308/active_time_registry_v1.csv
- registry_suite_summary: analysis_results/registry_20260308/registry_suite_summary_v1.json

## High-level counts
- rows: 189
- tasks: 156
- annotators: 4
- mixed scope tasks: 3
- mixed scope multi-annotator tasks: 3

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
- 08_mixed_scope_tasks_by_schema_version.png

## Skipped figures
- 06_dataset_group_source_by_schema_version.png: missing required columns or no eligible rows
- 07_dataset_group_counts_trusted.png: missing required columns or no eligible rows

## Mixed scope audit
- Mixed scope means the same task has both in-scope and OOS votes across annotations.
- Audit table: table_mixed_scope_audit.csv
|   task_id | schema_version   |   n_rows |   n_annotators | scope_values            |   n_scope_values | scope_buckets   |   n_scope_buckets | join_statuses    | has_in_scope_vote   | has_oos_vote   | is_mixed_scope   | is_multi_annotator   |
|----------:|:-----------------|---------:|---------------:|:------------------------|-----------------:|:----------------|------------------:|:-----------------|:--------------------|:---------------|:-----------------|:---------------------|
|       498 | v2_structured    |        3 |              3 | normal; oos_split_level |                2 | in_scope; oos   |                 2 | unmatched        | True                | True           | True             | True                 |
|       500 | v2_structured    |        3 |              3 | normal; oos_geometry    |                2 | in_scope; oos   |                 2 | ambiguous        | True                | True           | True             | True                 |
|       501 | v2_structured    |        3 |              3 | normal; oos_geometry    |                2 | in_scope; oos   |                 2 | matched_by_title | True                | True           | True             | True                 |