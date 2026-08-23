# 标注不确定性复算：阈值、共享初始化与标注者潜在结构

## 核心裁决

1. **‘加人经常是在发现模式’不能作为无条件总体结论。**本次从冻结 pairwise geometry 重新聚类，并将阈值扩展至 0.90–0.98。应只在高支持、经过富集的任务中表述为：增加支持量会提高受支持少数模式的可检测性；同时也会增加聚类非唯一的机会。
2. **0.95 不是唯一产生该现象的阈值。**需要同时看跨阈值方向稳定性、分区失败率和高支持 prefix replay，不能只报告单一 q。
3. **现有数据观察到与共享初始化相伴的输出分布差异，但没有随机化反事实，不能断言共享初始化造成了这些差异，也不能把更高一致性自动解释为更正确或自动命名为锚定。**
4. **现有 P1 提供了正确与错误 proposal 的自然机制样本；C1 的 proposal 几乎全部接近 reference 上限，因此 C1 本身不能识别 Kiani 式的‘正确 AI 与错误 AI 方向相反’交互。**
5. **潜在标注者结构首先应被当作连续行为轴，而不是强行命名离散类型。**只有 split-half clustering 稳定性足够高时，离散类型才可进入后续验证。
6. **跨阈值稳定多峰仍只表示‘稳定观察到多个模式’；是否为多个合理解释必须经过不显示工人身份、支持人数和 GT 分数的专家盲审。**

## 1. 阈值敏感性

正式 22 个配对任务在 q=0.95 的 task-equal 熵差为 `0.033`，building-cluster 95% CI 为 `[-0.148, 0.218]`，exact building sign-flip p=`0.781`。
在 6 个 q≥0.90 阈值上，22 个任务中有 19 个在 ±0.01 规则下方向完全稳定，19 个在 ±0.05 规则下方向完全稳定。完整逐任务结果见 `THRESHOLD_TASK_ROBUSTNESS_FORMAL22.csv`。

熵差随阈值：

| q | n tasks | mean ΔH | 95% CI | p |
|---:|---:|---:|---:|---:|
| 0.9 | 22 | 0.033 | [-0.155, 0.212] | 0.781 |
| 0.925 | 22 | 0.033 | [-0.146, 0.216] | 0.781 |
| 0.93 | 22 | 0.033 | [-0.148, 0.224] | 0.781 |
| 0.95 | 22 | 0.033 | [-0.148, 0.218] | 0.781 |
| 0.97 | 21 | -0.006 | [-0.171, 0.183] | 0.953 |
| 0.98 | 22 | 0.049 | [-0.125, 0.221] | 0.648 |

高支持 k=22 富集样本的 prefix replay：

| q | k | supported-multimodal rate | not-evaluable rate |
|---:|---:|---:|---:|
| 0.95 | 5 | 0.154 | 0.077 |
| 0.95 | 8 | 0.443 | 0.080 |
| 0.95 | 12 | 0.524 | 0.118 |
| 0.95 | 16 | 0.524 | 0.167 |
| 0.95 | 20 | 0.503 | 0.224 |
| 0.95 | 22 | 0.500 | 0.250 |

这里的分母是 12 张高支持富集任务及其随机前缀，不是自然任务总体。q=0.95 的支持多峰检出率从 k=5 到 k=12 上升，之后约在 0.50 附近平台，同时 not-evaluable 增加；这既可能包含低频模式被发现，也包含 support≥2 判据和分区失败的机械性质，不能解读为单调的人数效应。

## 2. 共享初始化、proposal 正确性与结果分布

- `agreement_gain_with_quality_gain`: 8/25 tasks; building-cluster interval [0.129, 0.565].
- `productive_diversification_candidate`: 7/25 tasks; building-cluster interval [0.158, 0.385].
- `dispersion_without_quality_gain_candidate`: 3/25 tasks; building-cluster interval [0.000, 0.308].
- P1、correctness cutoff 0.95：正确 proposal 后跌破阈值 61 条；错误 proposal 被修正到阈值以上 61 条；错误 proposal 支持量为 182。
- C1、correctness cutoff 0.95：错误 proposal 支持量为 0；若该值接近零，则 C1 无法估计错误 proposal 条件效应。

`proposal_correctness_final_correctness_association_or` 是 proposal 正确性与最终正确性的观察性关联，不是 assistance treatment OR；`PROPOSAL_CORRECTNESS_MH_MANUAL_SEMI.csv` 只有在正确和错误 proposal 两层都有足够独立 building 时才允许解释。

## 3. 标注者潜在结构

Ward clustering 的最高 silhouette 为 0.201（k=3）。探索性选择的 k 记录在 `WORKER_LATENT_ASSIGNMENTS_CURRENT20.csv`，不构成正式工人类型。
任务 split-half 的 median ARI=0.120，IQR=[0.011, 0.266]。
若 median ARI 较低或跨过零，离散 cluster 只能作为探索性描述；应优先解释 PCA 连续轴及每个指标的支持量。
PCA 前两轴解释比例为 0.377, 0.207。

## 4. 多峰合理性边界

跨 prefix q=0.9, 0.925, 0.95, 0.98 满足稳定经验多峰筛选的任务有 2 张。它们进入 `ROBUST_OBSERVED_MULTIMODALITY_CANDIDATES.csv`。

该表只做审查优先级，不把稳定簇自动称为合理、多真值或固有 aleatoric uncertainty。正式 reasonableness audit 必须：隐藏 worker ID、模式人数、Manual/Semi 条件和 GT 质量；专家分别判定 protocol difference、legitimate alternative topology、continuous variation、clear error、representation mismatch、cluster artifact 或 reference issue。

## 5. 对后续实验的直接含义

- 下一轮 Semi 不应只增加同一 25 张图的重复人数；需要增加独立 building，并主动构造 proposal-correct / proposal-wrong 的可比反事实。
- 最强的下一步是 Protocol × Proposal 的因子实验，而不是把当前观察性数据包装成因果 anchoring 结论。
- 工人类型不能直接用于路由。先在 held-out tasks 验证：wrong-proposal correction、correct-proposal degradation、mode tendency 和 active-time residual 是否跨任务稳定。
- 稳定多峰任务应保留全部原始独立标注；不要把受到共享 proposal 影响的 Semi 输出作为额外独立票。

## 复现

运行：

```bash
python -m tools.thesis_main.analysis.full_uncertainty.analyze_threshold_anchoring_worker_types_20260823
```

源 commit（运行前）：`4fad7abf022fa5bf4376fd4371d4150e2ab82fdd`；分析源码 SHA-256：`cc47b71c90d6e5352b591564edda8971c4c29c3c6374da1b77a5ecf52b45f71b`。随机种子：`20260823`；prefix replicates：`100`；cluster bootstrap：`4000`。
