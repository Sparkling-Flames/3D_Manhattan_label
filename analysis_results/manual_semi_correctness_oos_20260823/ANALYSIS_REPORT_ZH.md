# Manual–Semi、Proposal Correctness、OOS 与条件功效复核（严格测量版）

## 核心结论

1. 正式 efficacy estimand 必须比较最终 Semi 与独立 Manual；model-initial-to-Semi-final 只属于机制和安全分析。
2. 现有数据没有“视觉更接近真实”的独立专家变量，因此 `delta_U<0` 不能被解释成视觉更差，也不能被解释成视觉更好。
3. 对方给出的 n=60 条件功效计算成立；由于当前没有真实 correctness-interaction 方差，显著结果概率不能定量称为高。
4. Building 不是要加入的额外科学解释变量，但属于相关性单位：图内随机化可消除主要图片难度，仍应限制每 building 图片数并做 cluster sensitivity。
5. 648 张模型审计没有正式 Scope/reference 字段，Main 前必须完成 OOS/unresolved/reference gate。

## GT 指标下降候选

C1、正式 analysis-eligible 且 task-level in-scope：

- proposal 被工人标为 acceptable、发生编辑、`delta_U<-0.01`：**18 行 / 14 张任务**。
- 同一口径不限制 formal eligibility：**20 行 / 14 张任务**。
- 进一步要求 topology_changed 和 material_edit 均有显式记录、同 topology、edit RMSE 可计算、且为非-material micro edit：**0 行 / 0 张任务**。
- 不要求 acceptable 标签的全部 formal micro same-topology negative candidates：**0 行 / 0 张任务**。

P1 开发数据：

- acceptable + edited + negative：**72 行 / 15 张任务**。
- 严格可测的 acceptable + micro same-topology + negative：**6 行 / 4 张任务**。

这些只是“GT-based metric decline after editing”的可复核候选。要确认“Manhattan 强制拟合使 GT 偏离视觉墙角、人工微调视觉更合理”，必须对 candidate overlays 做 outcome-blind 双专家视觉边界审查，或建立独立 visual-boundary reference。

## Building 与数据域

- Test：458 张，15 个 buildings；每 building 中位数 26.0 张。
- Validation：190 张，10 个 buildings；每 building 中位数 16.5 张。

## 标签角色

- Difficulty 继续收集，但其正式名称应是 worker-perceived difficulty。它是 post-response mechanism/outcome，不能作为 proposal correctness truth，也不能用于同一任务首次分配。
- Model Issue 必须在编辑前填写，并拆成：material issue yes/no/unsure、issue family、required correction severity、confidence。
- Correct/Wrong treatment truth 必须来自独立、结果不可见的 researcher/expert stimulus manifest。
