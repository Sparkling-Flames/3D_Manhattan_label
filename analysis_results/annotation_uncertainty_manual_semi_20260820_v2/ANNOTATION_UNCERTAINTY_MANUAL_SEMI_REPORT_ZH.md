# C1 Manual / Semi-Auto 标注不确定性全量数据挖掘报告（修复版）

## 数据挖掘主结果

- 本报告的主数据挖掘总体是 25 个已有 Manual/Semi 候选的同图任务，使用全部几何可计算 canonical 标注；中途退出、行政排除、外部分配和不进入后续阶段的工人没有因这些身份被删除。
- q=.95 时，全量 25-task 总体的任务等权 Shannon entropy 差（Semi−Manual）为 -0.010005，building-cluster bootstrap 95% CI [-0.219446, 0.176604]，building exact sign-flip p=0.914062。这是全量描述性数据挖掘结果，不是随机化因果效应。
- 22-task 正式资格样本仅保留为协议参照：差值 0.032866，95% CI [-0.153023, 0.217089]，building p=0.781250；该参照未检出总体不确定性降低。加入 3 个 paired OOS 任务但保持其全量几何后，25-task 差值为 0.021230。
- 上述区间不是预设等效性区间；不能把‘未检出降低’解释成‘两种方法相同’。
- q=.95 的四个总体不可互换，完整对照如下：

| population             | inference_role                            |   n_tasks |   n_buildings |   mean_difference |   ci_lower |   ci_upper |   building_exact_sign_flip_p |
|:-----------------------|:------------------------------------------|----------:|--------------:|------------------:|-----------:|-----------:|-----------------------------:|
| formal_primary         | protocol_reference_only                   |        22 |             9 |        0.0328664  |  -0.153023 |   0.217089 |                     0.78125  |
| formal_plus_oos_tasks  | scope_sensitivity                         |        25 |             9 |        0.0212301  |  -0.165973 |   0.183739 |                     0.867188 |
| all_canonical_in_scope | inclusive_worker_sensitivity              |        22 |             9 |       -0.00262838 |  -0.218654 |   0.205707 |                     0.976562 |
| all_canonical_planned  | primary_data_mining_inclusive_descriptive |        25 |             9 |       -0.0100053  |  -0.219446 |   0.176604 |                     0.914062 |

## 全量数据分类

- 任务层：87 个 C1 任务；25 个有 Semi 候选，其中 22 个协议参照任务、3 个 paired OOS；其余 62 个为 Manual-only。最终 OOS 共 8 个。
- 标注层：780 个 canonical task-worker-condition context、23 名工人。25 个 paired 任务共有 241 个 context：协议参照几何 197、OOS 28、行政排除 9、外部分配 6、几何不可计算 1。最后一类只进入缺失性审计，其余可计算行进入相应全量/敏感性分析。
- 工人 14 的 32 个 C1 context 全部保留；其中 31 个几何可用于全量不确定性分析。工人是否继续后续阶段不作为本报告的删除条件。
- 25 个 paired 任务中有 44 个 context 处于‘非正式参照但保留’状态；逐行原因见 `ROW_INCLUSION_CLASSIFICATION.csv`。
- `primary_exclusion_class` 是按分析优先级生成的互斥主分类，不是完整原因集合；每行的正交原因保存在 `secondary_exclusion_flags`，机械汇总见 `EXCLUSION_REASON_AUDIT.csv`。

## 被排除任务与工人的信息

- 8 个 OOS 任务没有删除：3 个 paired OOS 同时给出 Manual/Semi 熵差，5 个 Manual-only OOS 给出图像自身的 Manual 多解性目录；结果见 `EXCLUDED_TASK_UNCERTAINTY.csv`。
- q=.95 的 3 个 paired OOS 任务差值（Semi−Manual）为：`UwV83HsGsw3_0f1385fc03994285ad8253b49516d77b` -0.346574；`uNb9QFRL6hY_6c4fa6dfddc1499db228854454bfc61d` +0.562335；`uNb9QFRL6hY_ce88ee8b7ee84fca92c13ab16599d90e` -0.408071。
- 行政排除、外部分配等工人与同任务中标准分配且几何可计算工人的逐对一致性另列于 `EXCLUDED_WORKER_PEER_COMPARISONS.csv`；它用于观察这些数据是否改变分布，不用于恢复正式资格。

## 几何指标与兼容性

- 每个阈值同时输出 Shannon entropy、Gini-Simpson、最大模态占比、支持型多模态、模态数，以及两种含义不同的 pairwise 距离。
- 正式参照原始配对中，metric-compatible 对为 349，其中 pointwise-correspondence-compatible 为 232，另有 117 对只能用于通用 metric dissimilarity，不能混入逐点对应差异。
- q=.95 中非唯一或不可评价的任务-条件子集记录数为 0；没有填零后混入 partition 指标。

## 质量、时间和难度

- 质量的条件特异资格对比覆盖 22 个任务，Semi−Manual IoU=0.055774，building p=0.015625；这是不同条件各自资格口径下的辅助关联。
- 另将全部 IoU 可计算 context（不按后续资格删除）组成质量挖掘总体；25 个候选任务中有 22 个形成可评价配对，差值为 0.056359，building p=0.019531；完整 780 行及不可计算原因仍保留在 `QUALITY_DATA_MINING_CONTEXTS.csv`。
- active time 只使用冻结 task-worker 文件：780 个 context 中 701 个满足冻结时间资格，其中 184 个属于 22-task 正式时间参照。正式参照的任务均值差为 37.095455 秒；25-task 全量 observed frozen-time 差为 39.190000 秒。没有使用 Label Studio `lead_time` 或 raw event 回填。
- 冻结 pre-assignment 难度特征 `n_ready=0`（c1_frozen_preassignment_n_ready_0），因此‘高难度图像上是否更有优势’仍不可评价；没有用最终 Manual 熵反向定义高难度。

## 推断边界与文件导航

- 同图跨条件 worker overlap 为 0。分配并非标准随机试验，所以所有 Manual/Semi 差异只报告为分布差异或关联。
- `TASK_INCLUSION_CLASSIFICATION.csv`、`ROW_INCLUSION_CLASSIFICATION.csv`、`WORKER_COVERAGE.csv` 给出任务—标注—工人三级盘点；`POPULATION_SENSITIVITY.csv` 给出正式参照、加入 OOS、加入非正式工人和全量计划任务四个总体。
- `MANUAL_TASK_UNCERTAINTY_CATALOG.csv` 覆盖全部 87 个任务，用于发现图像自身歧义；不能把 Manual-only 任务误写成 Semi 的效果。
- 旧固定分区结果仅作可复现审计基线：

| metric                  |   mean_difference |   task_exact_sign_flip_p | status                            |
|:------------------------|------------------:|-------------------------:|:----------------------------------|
| shannon_entropy         |        0.0328664  |                 0.80035  | legacy_fixed_partition_audit_only |
| gini_simpson            |        0.0208333  |                 0.794353 | legacy_fixed_partition_audit_only |
| largest_mode_share      |       -0.00681818 |                 0.944649 | legacy_fixed_partition_audit_only |
| supported_multimodality |       -0.0363636  |                 0.5      | legacy_fixed_partition_audit_only |
| mode_count              |        0.0727273  |                 0.802471 | legacy_fixed_partition_audit_only |
