# Manual–Semi、Proposal Correctness、OOS 与条件功效复核（2026-08-23）

## 结论

1. 未来主效应必须比较最终 Semi 与独立 Manual；initial-to-final 变化只属于机制与安全结果。
2. `visual closer` 在现有数据中没有独立专家真值字段，不能由 `delta_U<0` 反推。当前只能给出候选数量。
3. 对 60 张 primary images 的条件功效计算成立，但没有真实 correctness-interaction 方差，因此不得将显著结果概率写成“高”。
4. Building 不应作为新的科学自变量堆入主模型，但相关性不能忽略；最简处理是图内随机化、限制每 building 图片数，并报告 building-cluster sensitivity。
5. 648 张模型审计表没有 task-level Scope/reference 字段；正式刺激池必须先做独立 OOS/unresolved/reference audit。

## 现有候选计数

C1、任务终态 in-scope 中：

- 工人报告 proposal acceptable、发生编辑且 GT-based `delta_U<-0.01`：**20 行 / 14 张任务**。
- 上述条件进一步限制为同 topology、非 material micro-edit：**10 行 / 9 张任务**。
- 不要求 acceptable 标签的全部同 topology、非 material micro-edit 且指标下降：**30 行 / 13 张任务**。

P1 开发数据中：

- acceptable + edited + negative metric change：**72 行 / 15 张任务**。
- acceptable + micro same-topology edit + negative metric change：**40 行 / 12 张任务**。

这些是“GT 指标下降但可能属于视觉/局部修订”的候选，不是视觉更接近真实的已确认案例。正式确认需要盲法 overlay 审查或独立 visual-boundary reference。

## 数据域与 Building

- Test：458 张，15 个 buildings；每 building 中位数 26.0 张。
- Validation：190 张，10 个 buildings；每 building 中位数 16.5 张。
- 模型审计表是否带正式 Scope/reference 字段：False。

## 建议的标签角色

- Difficulty：继续收集，但只作为 worker-perceived difficulty / mechanism outcome；不要作为 proposal correctness 真值或同任务首次分配变量。
- Model Issue：必须在编辑前收集，拆分为 `material issue yes/no/unsure`、issue family、required correction severity、confidence。
- Assignment truth：独立 researcher/expert manifest，不能由 worker 的 Model Issue 反推。

## 复现

```bash
python -m tools.thesis_main.analysis.full_uncertainty.analyze_manual_semi_correctness_oos_20260823
```
