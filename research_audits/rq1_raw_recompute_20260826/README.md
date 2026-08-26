# RQ1 原始数据独立重算审计（2026-08-26）

## 状态

- **用途**：从原始 Label Studio 导出重新核验 RQ1 支持量、几何距离下采样、cluster 阈值敏感性，以及 60/72 图三臂设计的纯测量噪声下限。
- **性质**：审计性、只读、非规范；不自动替代当前方法合同、SAP 或导师讨论稿。
- **原始数据基线**：`main@f3c7b713c6cff6c08dc1fe231c7e84b8db1774ee`。
- **首次完整物化提交**：`c8344d84e0e548c88f88eae14164f5d9389b9696`。
- **canonical 重选规则**：同一 `project_id × runtime_task_id × worker_id` 中，按 `updated_at`、`created_at`、数值 annotation ID 依次取最新非取消版本；未读取历史 canonical authority 来决定入选版本。

## 已经由原始导出重现的事实

1. P1+C1 原始非取消 annotation version 共 **2,273** 条；独立 acquisition key 共 **2,261** 个。存在 **9** 个重复版本组、合计 **12** 条多余版本。
2. P1 Manual 30 图与 C1 anchor 12 图组成 **42 个高密度 task context**；严格可计算支持量均为 **23–26**。
3. C1 core 实际为 **75 个唯一 Manual task context**，严格几何支持量分布为：`k=3: 1`、`k=4: 4`、`k=5: 49`、`k=6: 20`、`k=7: 1`。因此严格 `k≥5` 是 **70**，不是 71。
4. C1 core 的 image-equal-weight boundary distance：均值 **0.020814**，中位数 **0.013971**，P10 **0.006945**，P90 **0.046004**。这描述的是 assigned operational task sample，不等于已经逐图 scope 审定后的 Manhattan 总体。
5. 高密度集内，`1-boundary_similarity` 对全支持结果的下采样恢复：
   - `k=5`：Spearman 中位数 **0.8556**，Top-20% 召回中位数 **0.7778**；
   - `k=8`：Spearman **0.9161**，Top-20% 召回 **0.8889**；
   - `k=10`：Spearman **0.9367**；
   - `k=15`：Spearman **0.9695**。
6. `1-wallwall_similarity` 的稳定性低于 boundary：`k=5/8/15` 的 Spearman 中位数分别为 **0.8116 / 0.8704 / 0.9472**。两个通道不得未经冻结权重直接合并。
7. 42 个高密度任务中，完整样本下有 **37** 个出现不止一种 vertical-boundary count。条件于这 37 个任务，随机抽样看到多种 count 的平均概率为：`k=5: 0.6306`、`k=8: 0.7298`、`k=15: 0.8844`、`k=20: 0.9537`。
8. 当前 complete-link / maximum-clique cluster 结果对阈值高度敏感：
   - 阈值 0.90：21/42 被标为 supported multimodal，4/42 not evaluable；
   - 0.925：20/42 supported multimodal，5/42 not evaluable；
   - 0.95：21/42 supported multimodal，5/42 not evaluable；
   - 0.98：14/42 supported multimodal，19/42 not evaluable。
   因此该 cluster 分类不能直接作为“真实多峰 prevalence”的 Primary 证据。
9. 在每图从同一历史人群随机拆成 5/5/5、并强制零处理效应的回放中，60 与 72 图的 boundary 对比 80% 条件 MDE 下限约为 **0.00563–0.00570** 与 **0.00514–0.00520**；wall 通道约为 **0.00873–0.00881** 与 **0.00797–0.00804**。这些只是**抽样噪声下限**，排除了 treatment heterogeneity、building correlation、worker superpopulation、无效结果和新刺激变化，不能被解释成正式功效或成功概率。
10. 旧 difficulty 标签在 82 个 C1 Manual `k≥5` 任务、648 个 worker-task response 中，没有支持“总体非简单”或“遮挡”与几何离散存在稳定关系。仅 seam/stretch 任务级选择率与 boundary dispersion 呈中等正关联（Spearman **0.3840**，building bootstrap 95% 区间约 **0.1016–0.5530**）。但 difficulty 是完成标注时填写的 post-response appraisal，不是预先冻结的客观任务真值。
11. 独立 raw active-time 连接目前仍未成功：648 个 C1 worker-task 行均未获得可用 formal active time。该轴在修复原始日志身份连接前必须记为 **not established**，不能使用 lead time 代替。

## 对研究方向的直接约束

- 历史数据足以支持一个审慎的 RQ1：连续几何 reproducibility、cardinality disagreement、computability，以及人数支持量校准。
- 每臂 5 人可以估计跨图片平均几何离散；不能可靠证明单张图“无多峰”，也不能承担单图多峰 prevalence。
- 三臂 Main 的核心价值只能来自 proposal truth 对几何分歧、最终质量和无效率的前瞻处理效应；历史下采样不能替代该效应。
- 60 与 72 图的差异只带来约 8.7% 的理论标准误下降。未获得可信处理效应分布前，72 不能被描述为“高把握”，60 也不能被描述为“已足够”。
- RQ3 的 appraisal 可以保留为 protocol-requested pathway evidence；当前配置明确没有 technical time lock 或 phase event persistence，因此不能表述为已技术证明的编辑前识别或正式因果中介。

## 可复现入口

### 脚本

- [`raw_rq1_audit_20260826.py`](../../tools/thesis_main/analysis/raw_rq1_audit_20260826.py)
- [`raw_rq1_recompute_20260826.py`](../../tools/thesis_main/analysis/raw_rq1_recompute_20260826.py)
- [`raw_rq2_null_replay_20260826.py`](../../tools/thesis_main/analysis/raw_rq2_null_replay_20260826.py)
- [`raw_difficulty_time_recompute_20260826.py`](../../tools/thesis_main/analysis/raw_difficulty_time_recompute_20260826.py)
- [GitHub Actions workflow](../../.github/workflows/rq1-raw-audit-20260826.yml)

### 关键结果

- [RQ1 总结](../../analysis_results/rq1_raw_recompute_20260826/SUMMARY.json)
- [支持量下采样汇总](../../analysis_results/rq1_raw_recompute_20260826/support_calibration_summary.csv)
- [count 多样性检出汇总](../../analysis_results/rq1_raw_recompute_20260826/boundary_count_detection_summary.csv)
- [cluster 前缀回放汇总](../../analysis_results/rq1_raw_recompute_20260826/high_density_cluster_prefix_summary.csv)
- [cluster 阈值敏感性](../../analysis_results/rq2_null_replay_20260826/cluster_threshold_count_summary.csv)
- [60/72 图纯测量噪声下限](../../analysis_results/rq2_null_replay_20260826/null_replay_sample_size_scenarios.csv)
- [difficulty/active-time 审计总结](../../analysis_results/rq1_difficulty_time_raw_20260826/SUMMARY.json)
- [difficulty 关联结果](../../analysis_results/rq1_difficulty_time_raw_20260826/associations.csv)

## 尚未解决

1. Primary geometry distance 尚未冻结；当前 boundary 与 wall-wall 只能作为分开的候选通道。
2. 严格 validity 是当前 image-plane serialization contract，不是物理 floor-plan topology validity。
3. scope 尚未对 C1 core 逐图重新审定。
4. active-time 原始身份连接未建立。
5. Correct/Wrong proposal 的实际处理效应分布尚无可用于正式功效计算的前瞻数据。
