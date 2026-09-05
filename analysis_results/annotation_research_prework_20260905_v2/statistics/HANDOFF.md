# HANDOFF

- 统计入口：`tools/thesis_main/analysis/materialize_annotation_research_prework_statistics_20260905.py`
- 字段合同：`FIELD_CONTRACT.json`
- 核心表：`feature_records.csv`, `worker_task_components.csv`, `directional_worker_profiles.csv`, `bootstrap_diagnostics.csv`, `continuous_volatility.csv`, `quality_time_coexisting_axes.csv`, `holdout_evaluation.csv`, `continuous_vs_classified_summary.csv`, `structure_sensitivity_tasks.csv`, `structure_sensitivity_summary.csv`, `strict_medoid_replay_replicates.csv`, `strict_medoid_replay_summary.csv`, `directional_group_replay.csv`
- QA：`QA.json`；报告：`REPORT_ZH.md`
- 计算：全历史动态 roster；1000 次 building→task draw（不拒绝/不重抽）；held-out task + LOBO；strict >20 nested k15–20 × 200；q=.93/.95/.97；旧42回归。
- 边界：audit/sensitivity only；不改协议、raw truth、旧产物；不把标签解释为人格；不拟合场景预测。
- 证据合同状态：`validated`；若 pending，主任务应在 Luna 文件到位后原命令复跑以完成最终证据 join QA。
