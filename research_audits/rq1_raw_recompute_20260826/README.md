# RQ1 原始数据独立重算审计（2026-08-26，修正版）

## 状态与裁决边界

- **用途**：从原始 Label Studio 导出重新核验 RQ1 支持量、候选几何距离、人数下采样、cluster 阈值敏感性、20 人总体敏感性、formal active time，以及 60/72 图三臂设计的纯测量噪声下限。
- **性质**：审计性、只读、非规范；不自动替代方法合同、SAP 或导师讨论稿。
- **原始数据基线**：`main@f3c7b713c6cff6c08dc1fe231c7e84b8db1774ee`。
- **首次完整物化提交**：`c8344d84e0e548c88f88eae14164f5d9389b9696`。
- **修正审计物化提交**：`b731f7a2f1fd19e8ba1471e00db4288fdbb335c7`。
- **canonical 独立重选规则**：同一 `project_id × runtime_task_id × worker_id` 中，按 `updated_at`、`created_at`、数值 annotation ID 依次取最新非取消版本。2,261 个 acquisition key 中，2,260 个与冻结 canonical 选择一致；唯一不一致项是 annotation 6053 与冻结 6052，二者 `result_json` 完全相同，因此不改变几何结果。

## 对上一版公开审计的更正

上一版把 raw-strict parser 当成最终 C1 计算口径，并把 direct raw-log join 失败误写成 active-time 不存在。两项均已撤回：

1. C1 的正式派生几何计算受 `c1_geometry_parser_amendment_v1` 约束；满足唯一单点删除规则时，应应用 `recoverable_orphan_point_removed`。因此必须同时区分 raw-strict 与 amendment-compliant 口径。
2. 原始 active log 使用历史 project/annotator 身份，不能直接与最终 C1 runtime/worker 身份连接；正式分析必须使用已冻结、SHA 校验通过的 `c1_task_worker_active_time.csv` rebinding 表。

## 已由原始导出和冻结事实源重现的结果

### 1. 原始版本与 canonical 稳定性

- P1+C1 原始非取消 annotation version：**2,273**。
- 独立 acquisition key：**2,261**。
- 重复版本：**9** 组、**12** 条 excess version。
- 独立 latest-version 选择与冻结 canonical：**2,260/2,261** 完全一致；唯一 mismatch 是 exact-result duplicate。

### 2. 支持量：正式口径不是70，也不是71

P1 Manual 30图与 C1 anchor 12图组成 **42 个高密度 task context**，amendment-compliant 支持量均为 **23–26**。

C1 core 有 **75 个唯一 Manual task context**：

- raw-strict：`k=3:1, k=4:4, k=5:49, k=6:20, k=7:1`，所以 `k≥5=70`；
- C1 amendment-compliant：`k=3:1, k=4:2, k=5:51, k=6:20, k=7:1`，所以正式派生几何计算下 **`k≥5=72`**。

共应用3次唯一 orphan-point repair，其中2次发生在 C1 core Manual、1次发生在 C1 Semi。故 P1+C1 中 amendment-compliant Manual `k≥5` task context 为 **30 + 12 + 72 = 114**。C1 core 尚未逐图完成新的 Manhattan scope 审定，应称为 `assigned operational task sample`，不得写成已确认 in-scope 总体。

### 3. 三个候选连续距离必须分开

当前修正审计同时计算：

- `mask`：周期全景图中墙体区域带的 `1 − IoU`；
- `boundary`：周期 ceiling/floor boundary similarity 的 `1 − similarity`；
- `wall`：vertical wall-event 横坐标的对称 circular Chamfer distance。

其中 `mask` 最接近导师稿中想表达的“overall 1-IoU”，但它是 **panorama wall-region mask IoU**，不是俯视平面 IoU，也不是 3D IoU。它仍未冻结为 Primary，并且不能替代 cardinality/validity 轴。

42个高密度任务中，相对于全支持经验基准：

| 每图人数 | mask Spearman中位数 | mask MAE中位数 | mask Top-20%召回中位数 | boundary Spearman | wall Spearman |
|---:|---:|---:|---:|---:|---:|
| 2 | 0.689 | 0.0590 | 0.556 | 0.651 | 0.625 |
| 3 | 0.792 | 0.0439 | 0.667 | 0.760 | 0.722 |
| 5 | 0.882 | 0.0313 | 0.778 | 0.858 | 0.809 |
| 8 | 0.927 | 0.0230 | 0.778 | 0.913 | 0.871 |
| 10 | 0.948 | 0.0194 | 0.778 | 0.936 | 0.901 |
| 15 | 0.975 | 0.0125 | 0.889 | 0.968 | 0.947 |
| 20 | 0.991 | 0.0068 | 0.889 | 0.987 | 0.978 |

结论：每臂5人可用于跨图片平均处理效应，但不能把单图估计当成稳定真值；Primary 指标选择会显著改变误差量纲与样本量判断。

### 4. 20人工人总体不是主要损失源，k=5才是

在12张 C1 anchor 上随机从共同23人中抽20人：

- 20人全支持相对23人全支持的任务排序 Spearman 中位数：mask **0.986**；
- 再从该20人中每图抽5人后，mask Spearman 中位数降为 **0.867**，5%分位数仅 **0.517**。

因此，从23人缩到20人本身影响较小；每臂只有5人的图级测量噪声才是主要限制。该回放仅覆盖12张 anchor，不能替代最终具名20人 roster 的预先冻结。

### 5. cardinality 与多峰不能混为一谈

42个高密度任务中，完整支持样本有 **37** 个出现不止一种 vertical-boundary count。条件于这37个任务，随机抽样观察到多种 count 的平均概率约为：`k=5:0.63`、`k=8:0.73`、`k=15:0.88`、`k=20:0.95`。所以 `k=5` 下未观察到 count 多样性，只是弱负证据。

当前 complete-link / maximum-clique cluster 对阈值高度敏感：

- 0.90：21/42 supported multimodal，4/42 not evaluable；
- 0.925：20/42 supported multimodal，5/42 not evaluable；
- 0.95：21/42 supported multimodal，5/42 not evaluable；
- 0.98：14/42 supported multimodal，19/42 not evaluable。

因此 `supported_multimodal prevalence` 不能作为冻结 Primary；只能是历史高密度探索或案例分析。

### 6. 60/72图的理想化噪声下限

在每图从同一历史人群随机拆成5/5/5，并强制零处理效应的回放中：

| 候选通道 | 60图条件80% MDE下限 | 72图条件80% MDE下限 |
|---|---:|---:|
| wall-region mask `1-IoU` | 0.02686–0.02715 | 0.02452–0.02478 |
| boundary distance | 0.00569–0.00571 | 0.00519–0.00521 |
| wall-event distance | 0.00872–0.00879 | 0.00796–0.00802 |

这些数值只是**抽样噪声下限**，排除了 treatment heterogeneity、building correlation、worker superpopulation、无效结果和新刺激分布偏移；不能解释成正式功效或“显著结果概率”。72相对60仅减少约8.7%的理论标准误。

### 7. formal active time 可以使用，但只能作次要轴

冻结 active-time 表：

- SHA 与 summary 完全一致；
- 780 个 C1 task-worker context；
- 701 个冻结 eligible context；
- 在 amendment-compliant Manual `k≥5` 分析中：84个任务、658个 worker-task 行，594行具有可用 formal active time，覆盖22名工人。

描述性关联：

- task-level mask dispersion 与 median active time：Spearman **0.244**，building bootstrap 95%区间 **0.031–0.372**；
- 排除焦点工人自身几何后的 worker-fixed 关联：within-worker correlation **0.198**。

因此 active time 对任务/工人画像有信息，但效应不强、不是随机化结果，不能成为 Primary 或因果证据，也不能用 Label Studio `lead_time` 替代。

### 8. 旧 difficulty 标签不是可靠的总体难度真值

84个 C1 Manual `k≥5` 任务中：

- overall nontrivial rate 与 mask dispersion：Spearman **0.017**；
- occlusion rate：**−0.064**；
- seam/stretch rate：**0.444**，building bootstrap 95%区间 **0.204–0.608**。

只有 seam/stretch 显示较稳定的特异性关联。旧 difficulty 是完成标注时填写的 post-response appraisal，不能作为预处理抽样真值或固有任务难度定义。

## 对研究方向的直接约束

- 历史数据足以支持一个审慎的 RQ1：operational reproducibility、cardinality disagreement、computability、formal active time，以及人数支持量校准。
- 每臂5人可以研究跨图片平均处理效应；不能可靠证明单图“没有多峰”，也不能承担单图多峰 prevalence。
- 三臂 Main 的核心创新只能来自 proposal truth 对人类输出分布与质量的前瞻因果效应；历史下采样不能替代该效应。
- `Correct−Manual`、`Wrong−Manual`、`Wrong−Correct` 不应全部作为同等级 Primary。建议只冻结 `Wrong−Correct` 为 confirmatory Primary contrast，另两项作为预注册 secondary contrasts。
- 当前配置没有 technical phase lock 或 phase-event persistence，因此 Model Issue 只能称为 `protocol-requested appraisal`，不能称为已技术证明的“编辑前识别”，也不能做正式因果中介。
- 研究可行，但目前没有数据支持“高概率显著”或“高把握Q2”。若最终 Primary 使用 mask distance，60图在理想化条件下对约0.027以下的平均效应已无充分把握；真实阈值只会更高，不会更低。

## 可复现入口

### 修正审计

- [`audit_rq1_corrections_20260826.py`](../../tools/thesis_main/analysis/audit_rq1_corrections_20260826.py)
- [修正审计 summary](../../analysis_results/rq1_corrections_20260826/SUMMARY.json)
- [raw-strict 与 C1 amendment 支持量对照](../../analysis_results/rq1_corrections_20260826/raw_vs_amendment_task_support.csv)
- [C1 orphan repair 审计](../../analysis_results/rq1_corrections_20260826/c1_geometry_repair_audit.csv)
- [三个候选距离的支持量回放](../../analysis_results/rq1_corrections_20260826/support_calibration_summary.csv)
- [20-of-23 roster 敏感性](../../analysis_results/rq1_corrections_20260826/c1_anchor_roster20_sensitivity.csv)
- [60/72图零效应下限](../../analysis_results/rq1_corrections_20260826/null_replay_sample_size_scenarios.csv)
- [formal active-time / difficulty 关联](../../analysis_results/rq1_corrections_20260826/formal_time_difficulty_associations.csv)
- [cluster 阈值敏感性](../../analysis_results/rq1_corrections_20260826/cluster_threshold_count_summary.csv)

### 初始审计（保留用于差异追踪，已被修正审计覆盖）

- [`raw_rq1_recompute_20260826.py`](../../tools/thesis_main/analysis/raw_rq1_recompute_20260826.py)
- [初始 RQ1 summary](../../analysis_results/rq1_raw_recompute_20260826/SUMMARY.json)
- [初始 difficulty/time summary](../../analysis_results/rq1_difficulty_time_raw_20260826/SUMMARY.json)

## 尚未解决

1. Primary geometry metric 仍未冻结；`mask` 只是当前最接近整体布局差异的候选。
2. 无效结果如何进入 Primary estimand 尚未冻结；不能只删除 invalid pair 后比较。
3. C1 core scope 尚未逐图重新审定。
4. Correct/Wrong proposal 的真实前瞻处理效应分布仍不存在，正式功效无法计算。
5. 最终具名20人 roster、building 配额、proposal severity 与独立 reference review 尚未冻结。
