# Worker 行为分层与混合重放：探索性报告

## 结论先行

当前数据**不支持把 20 人宣布为稳定的 good/sloppy 或 2--3 种自然类型**。但在固定 6 人的事后重组中，把 A 从 2 人提高到 4 人，与 delivery-adjusted quality 提高 0.033 [0.008, 0.063]、resolved-only quality 提高 0.009 [0.002, 0.014] 同向关联。这个信号偏小且并不完整：P1 单层的 delivery-adjusted 差值为 0.020 [-0.003, 0.050]，区间仍跨 0。

因此可以保留一个明确但窄的候选问题：在既有 `U=0.95` 交付标准下，是否存在一批能修正错误 proposal、同时较少破坏正确 proposal 的标注者；以及提高这批人在组合中的比例是否改变聚合表现。它还不是稳定 worker taxonomy。

主分组只有两层：A（按 `U=0.95` 规则识别的选择性纠错候选）与非 A 比较池。第三层 C（过度修改倾向）只作机制敏感性；另有 U 为拒绝分类，不是第三种人格类型。

## 分类规则与人数

- 分类数据：P1 Semi 的 18 张共同校准图，20 人每人恰好 11 个正确 proposal 与 7 个错误 proposal。
- A：错误 proposal 至少修正 3/7，且正确 proposal 最多破坏 1/11。
- C：正确 proposal 至少破坏 3/11，且错误 proposal 最多修正 1/7；仅作敏感性。
- U：其余反应，保持未分类。
- 分类图与 Manual 评价图的 base task 重叠为 0；building 仍重叠 8 个，所以区间按 building 聚类。

人数：A=9、C=5、U=6；主比较为 A=9 与非 A=11。

- A：2, 8, 10, 13, 15, 17, 28, 33, 36
- C：1, 12, 34, 35, 37
- U：6, 11, 29, 30, 31, 32

## 防止重演旧分类失败的检查

1. 不再搜索聚类数，也不使用旧 10 维聚类；旧结果的 silhouette≈0.201、split-half ARI 中位数≈0.120，不足以支持自然类型。
2. 分类只看 P1 proposal-response；Manual 质量完全留作评价，避免用同一结果既分组又证明分组有效。
3. 允许 U 拒绝分类，不把所有人强塞进三类。
4. 留一任务复算中，A 保持原组 15--18/18 次，C 保持 15--18/18 次；边界成员仍需前瞻复核。
5. 类型名称绑定 `U=0.95`。阈值敏感性如下，说明它不是跨定义稳定人格；其他阈值也会改变正确/错误题的数量，因此仅作定义敏感性，不是同支持正式比较：

| U 阈值 | A 人数 | C 人数 | U 人数 |
|---:|---:|---:|---:|
| 0.925 | 5 | 4 | 11 |
| 0.930 | 5 | 4 | 11 |
| 0.950 | 9 | 5 | 6 |
| 0.970 | 1 | 8 | 11 |

因此，后续若采用这一路线，必须先冻结 `U=0.95` 的业务/交付含义；不能看过 Manual 结果再换阈值。

## 子群自身曲线（41 图 pooled 仅作敏感性）

以下是 GT-blind 聚合的 delivery-adjusted quality，区间为 building-cluster bootstrap。C1 12 图和 P1 29 图的分层结果在 `replay_summary.csv` 中，不能只引用 pooled 值。

| 人群 | k | 图数 | delivery-adjusted quality [95% CI] |
|---|---:|---:|---:|
| A_selective_corrector_u095 | 3 | 41 | 0.761 [0.740, 0.793] |
| A_selective_corrector_u095 | 4 | 41 | 0.813 [0.793, 0.845] |
| A_selective_corrector_u095 | 5 | 39 | 0.812 [0.771, 0.865] |
| B_non_A_comparison_pool | 3 | 41 | 0.697 [0.646, 0.766] |
| B_non_A_comparison_pool | 4 | 41 | 0.755 [0.717, 0.805] |
| B_non_A_comparison_pool | 5 | 41 | 0.739 [0.697, 0.795] |
| C_overmodifier_u095_sensitivity | 3 | 41 | 0.660 [0.597, 0.762] |
| C_overmodifier_u095_sensitivity | 4 | 41 | 0.714 [0.664, 0.807] |
| C_overmodifier_u095_sensitivity | 5 | 37 | 0.712 [0.644, 0.809] |

共同任务上的配对差值如下；正值表示 A 更高：

| 配对差值 | k | 共同图数 | Δ delivery-adjusted quality | Δ resolved-only quality |
|---|---:|---:|---:|---:|
| A_minus_non_A | 3 | 41 | 0.064 [0.008, 0.110] | 0.024 [0.009, 0.034] |
| A_minus_non_A | 4 | 41 | 0.058 [0.013, 0.103] | 0.021 [0.005, 0.032] |
| A_minus_non_A | 5 | 39 | 0.078 [0.031, 0.137] | 0.027 [0.014, 0.036] |
| A_minus_C | 3 | 41 | 0.101 [0.015, 0.163] | 0.031 [0.014, 0.042] |
| A_minus_C | 4 | 41 | 0.100 [0.021, 0.144] | 0.024 [0.002, 0.037] |
| A_minus_C | 5 | 36 | 0.083 [-0.001, 0.165] | 0.028 [0.020, 0.035] |

只能把它称为“现有有限 roster 的支持曲线”。A 在所有 41 图只保证到 k=4；更高 k 会改变图像分母。任何用完该组全部成员后趋近 1 的恢复率都是机械端点，不是总体质量上限。

## 固定总人数 k=6 的混合重放

每次按 worker ID 无放回抽取，同一人每图最多一票；聚合器不读取 GT、worker 分组或 worker 质量。`B` 在主分析中是非 A 比较池，在敏感性中是 C 组。

| 分析 | 组成 | delivery-adjusted quality [95% CI] | resolved rate [95% CI] |
|---|---|---:|---:|
| primary_A_vs_non_A | 4A+2B | 0.734 [0.675, 0.811] | 0.794 [0.732, 0.881] |
| primary_A_vs_non_A | 3A+3B | 0.714 [0.660, 0.792] | 0.776 [0.719, 0.859] |
| primary_A_vs_non_A | 2A+4B | 0.700 [0.647, 0.775] | 0.764 [0.710, 0.842] |
| sensitivity_A_vs_C | 4A+2B | 0.725 [0.673, 0.796] | 0.783 [0.731, 0.855] |
| sensitivity_A_vs_C | 3A+3B | 0.704 [0.649, 0.774] | 0.764 [0.705, 0.837] |
| sensitivity_A_vs_C | 2A+4B | 0.689 [0.619, 0.769] | 0.753 [0.675, 0.837] |

极端组成差值 `4A+2B − 2A+4B`：

| 分析 | 分层 | Δ delivery-adjusted quality | Δ resolved rate | Δ resolved-only quality |
|---|---|---:|---:|---:|
| primary_A_vs_non_A | C1_primary_12 | 0.065 [0.017, 0.141] | 0.058 [0.005, 0.144] | 0.014 [-0.000, 0.025] |
| primary_A_vs_non_A | P1_reference_sensitivity_29 | 0.020 [-0.003, 0.050] | 0.019 [-0.008, 0.053] | 0.007 [0.002, 0.012] |
| primary_A_vs_non_A | pooled_reference_sensitivity_41 | 0.033 [0.008, 0.063] | 0.030 [0.000, 0.063] | 0.009 [0.002, 0.014] |
| sensitivity_A_vs_C | C1_primary_12 | 0.070 [-0.000, 0.186] | 0.068 [-0.013, 0.202] | 0.015 [0.001, 0.023] |
| sensitivity_A_vs_C | P1_reference_sensitivity_29 | 0.022 [-0.031, 0.097] | 0.015 [-0.044, 0.097] | 0.008 [0.001, 0.015] |
| sensitivity_A_vs_C | pooled_reference_sensitivity_41 | 0.036 [-0.010, 0.092] | 0.031 [-0.022, 0.094] | 0.010 [0.002, 0.016] |

这些差异是**有限历史 roster 的事后重组关联**，不是把人随机变成 A/C 的因果效应，也不能外推成每类 12--20 人的平台。

## 可以怎样继续

- 若 A 富集从 `2A+4B → 3A+3B → 4A+2B` 呈稳定同向变化，并且在 C1、P1 分层方向一致，可把该规则冻结后拿新图/新 building 做前瞻验证。
- 若 pooled 有差异但 C1/P1 方向相反，或排除边界成员后消失，只能判定历史组成混杂，不建立类型结论。
- 若没有稳定差异，就停止离散分类路线，改用连续的 proposal-response 分数建模；不要继续调阈值找显著性。
- 现有类内支持不足以回答“某类 12--20 人是否收敛”。要回答该问题必须新增同类 worker，而不是复制已有标注。

## 口径

- resolved：唯一主簇可交付；supported multimodal 与 not evaluable 均不算 resolved。
- resolved-only quality：只在已交付输出中计算的 reference IoU。
- delivery-adjusted quality：未交付记 0；这里的 0 表示没有交付输出，不表示真实几何 IoU 为 0。
- pooled full output recovery：相对当前 20 人完整聚合输出的兼容概率；仅在完整目标本身 resolved 的图上定义。

本报告为 exploratory replay，不修改 Q_GT/R_peer/F_struct、worker eligibility、routing、正式 SAP 或方法合同。
