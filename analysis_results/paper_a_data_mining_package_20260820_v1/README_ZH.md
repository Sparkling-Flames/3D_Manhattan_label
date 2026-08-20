# Paper A 数据查阅与挖掘包

本包同时保留原始数据与客观物化结果，不包含 Paper B，不构造 T1/V1 outcome，也不提供主观价值或证据等级排序。

## 内容

- `raw/`：142 个原始文件；来源为冻结 raw package manifest。
  - 29 个 Label Studio export：正式分析使用其中 18 个（2,513 条 annotation）；其余 11 个历史/非正式 export 只供追溯。
  - 104 个 active-time 文件：其中 99 个 JSONL 共 34,417 条 event，另 5 个为 audit JSON。
  - 9 个 ground-truth export；本次关联扫描未静默把它们当作 worker outcome。
- `curated/`：14 个整理结果，包括 submission/task/worker/review facts、2,513 条 raw annotation、34,417 条 raw event、3,735 个 session context、3,668 条字段账本、关系矩阵及审计 manifest。
- `contracts/`：方法合同与统计分析计划。
- `reproduction/`：物化脚本、打包脚本和回归测试。
- `PACKAGE_MANIFEST.csv`：包内每个文件的来源、大小和 SHA-256。

## 查阅顺序

1. 先读 `curated/PAPER_A_DATA_DISCOVERY_REPORT_ZH.md`。
2. 用 `curated/raw_field_usage_ledger.csv` 查字段覆盖。
3. 用 `curated/raw_annotation_fact.csv`、`raw_active_event_fact.csv` 和 `raw_active_session_fact.csv` 做数据挖掘。
4. 需要核对原记录时，再按 `source_path` 回到 `raw/`。

## 关键边界

- canonical submission 为 2,501；另外保留 P1 4 条、C1 8 条 raw-only 版本记录。
- C1 raw join 使用 `project + ls_runtime_task_id + worker_id + annotation_id`。
- 6,546 条阶段外日志事件已显式标记，不能按所在目录静默归入阶段。
- Label Studio `lead_time`、event fragment 与正式 owner-valid active time 相互独立。
- 缺失值不是零；`analysis_results/` 是输出，不是输入真源。

## 数据访问

包内含 worker/annotation ID、session、时间戳、任务数据和原始回答。仅向获授权的研究协作者提供；二次共享前应按实际伦理与隐私要求处理。
