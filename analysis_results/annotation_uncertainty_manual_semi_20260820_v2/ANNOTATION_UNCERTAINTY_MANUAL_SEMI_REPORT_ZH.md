# Manual / Semi-Auto 标注不确定性复核与重算（v2）

## 最终回答

- **[可复现事实]** 在 22 个 C1 配对任务中，q=.95 的任务等权 Shannon entropy 差（Semi−Manual）为 0.032866，9-building 整组 bootstrap 95% CI [-0.153023, 0.217089]，building exact sign-flip p=0.781250。未检出总体不确定性降低。
- **[不可评价]** 该区间不是预设等效性区间，不能证明‘没有降低’或支持等效性。
- **[不可评价]** 冻结 pre-assignment feature manifest 的 `formal_ready=false`、`n_ready=0`；高难度优势目前无法确认。

## 可复现事实

- 主样本固定为 22 个任务、9 个 building；21 个公共支持量 k=4，1 个 k=3。完整 equal-k 重聚类共 411 行（q=.93/.95/.97）。
- q=.95 中非唯一或不可评价的任务-条件子集记录数：0；这些记录未被静默填值或混入 partition 指标平均。
- 正式同图跨条件 worker overlap 总数为 0。分配是事前确定但不是标准随机试验，结果仅描述关联/差异。
- 主推断按任务等权；置信区间按 building 整组 bootstrap；p 值按 9 个 building exact sign-flip；任务级 exact sign-flip 仅列为敏感性；同阈值多指标采用 Holm 校正。
- 旧固定分区/task-level 结果已从冻结 sidecar 精确重算，仅作为审计基线，不作为 v2 正式结论。
- 旧 `p=0.578` 来自 `association_matrix.csv` 的 `all_observed` C1 IoU 扫描（207 rows、22 support units、overlap denominator=25），不是本 22-task entropy 结论；旧混合 eligibility 的 `p=0.000145` 不作为正式质量证据。
- 冻结 evidence manifest 的 16 个依赖引用中有 11 个缺失或 SHA 不匹配；直接分析输入 SHA 均通过，但 manifest 闭环不足，因此本包仍是诊断包。

## 探索性线索

- 仅保留 legacy difficulty、GT 角点数、Manual-only difficulty 票和 proposal 初始质量等不与 Manual 最终熵代数耦合的描述；不发布显著性 p 值。
- 原先按 Manual 最终熵二分的 high/low 交互已撤回，未进入任何 inferential 输出。
- 作为撤回理由的复算事实：旧分组中所谓高/低 Manual 熵组的 Semi 熵均值分别为 0.393526 与 0.432755，未呈现同向分层。该分组不再用于推断。

## 不可评价与辅助结局

- 确认性难度状态：not_evaluable（formal_ready_false_n_ready_0）。
- 冻结 active-time 状态：not_evaluable（frozen_task_worker_table_or_manifest_missing）；`lead_time_used=false`，未读取 raw event fragment 回填。
- 质量仅使用 `gt_primary_analysis_eligible=true`；Semi 在该正式 eligibility 下为 0 行，因此 Manual/Semi 质量差不可评价。编辑机制与时间均为独立辅助结局。

## 审计边界

- 代码基线 HEAD：`59e697aa8dcc3d3c037ccfa6c5da47c102608c48`。输入逐文件路径、大小、SHA 与 schema 见 `INPUT_MANIFEST.csv`；代码/测试 SHA 见 `analysis_manifest.json`。
- 本报告只给出差异与关联，不作因果解释，不用于冻结 reviewer 画像或筛选专家。

## 旧固定分区基线摘要

| metric                  |   mean_difference |   task_exact_sign_flip_p | status                            |
|:------------------------|------------------:|-------------------------:|:----------------------------------|
| shannon_entropy         |        0.0328664  |                 0.80035  | legacy_fixed_partition_audit_only |
| gini_simpson            |        0.0208333  |                 0.794353 | legacy_fixed_partition_audit_only |
| largest_mode_share      |       -0.00681818 |                 0.944649 | legacy_fixed_partition_audit_only |
| supported_multimodality |       -0.0363636  |                 0.5      | legacy_fixed_partition_audit_only |
| mode_count              |        0.0727273  |                 0.802471 | legacy_fixed_partition_audit_only |
