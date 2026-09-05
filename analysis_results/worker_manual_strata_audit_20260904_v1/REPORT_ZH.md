# Manual-only worker 分层审计

## 裁决

**当前 Manual 数据不支持冻结成稳定的 good/sloppy worker 类型。**

上一版 9/5/6 使用 P1 Semi proposal-response，只能回答预标注反应差异，不能作为本问题的 worker 分类；该结果在这里不再使用。

本审计只使用 Manual：

- 分类：C1 `Calibration_core`，当前20人共 350 条 Manual，正式 Q_GT 可用 303 条、67 题、13 个 building。
- 评价：41张有 reference 的高密度 Manual 图；C1 12张 public frozen GT 为主，P1 29张 expert hard-single reference 为敏感性。
- 每个评价 building 都从自己的分类训练集中排除；分类题与评价题重叠为0。

## 分类规则

对每一评价 building，使用其他 building 的 Core Manual 拟合：

`Q_GT = worker fixed effect + task fixed effect + error`

沿用既有 Q_GT 合同的 building→task 两层 bootstrap；每个重采样还须保留20人支持齐全且 worker–task 图连通：

- `P(相对当前20人均值的中心化 worker effect > 0) >= 0.80`：H，较高 Manual 参考质量证据；
- 上述概率 `<= 0.20`：L，较低 Manual 参考质量证据；
- 其余：U，暂不分类。

H/L/U 是**折内证据状态**，不是人格标签。不会为了凑人数降低阈值。全 Core 当前授权版本的描述性人数为 H=3、L=2、U=15；W034 original-only 后为 H=5、L=3、U=12。这种整体变化本身说明固定类型不稳定；重放使用逐 building 重新计算的标签。

## k=3 无放回混合重放

下表为 `2H+1L` 减去 `1H+2L`；每图枚举现有 worker ID 的全部组合，每人最多一票。质量池外的历史票不会被另一名工人顶替，少于3个合格几何时记为本重放不可评价。这里的“合格”包含独立性与质量门，**不等于真实未提交或标注失败**。

| 分类版本 | 分层 | Δ 三票全合格率 | Δ eligibility-resolved | Δ eligibility-adjusted quality | Δ resolved-only quality |
|---|---|---:|---:|---:|---:|
| 当前授权版本 | C1_primary_12 | +0.0278 [+0.0000, +0.0556] | +0.0301 [-0.0917, +0.1111] | +0.0336 [-0.0699, +0.1107] | +0.0183 [-0.0067, +0.0375] (n=10/12) |
| 当前授权版本 | P1_reference_sensitivity_29 | -0.0862 [-0.1780, +0.0233] | -0.0891 [-0.1799, +0.0060] | -0.0812 [-0.1620, +0.0011] | +0.0099 [-0.0019, +0.0230] (n=25/29) |
| 当前授权版本 | pooled_reference_sensitivity_41 | -0.0528 [-0.1380, +0.0241] | -0.0542 [-0.1455, +0.0151] | -0.0476 [-0.1346, +0.0130] | +0.0123 [+0.0023, +0.0184] (n=35/41) |
| W034 original-only | C1_primary_12 | +0.0278 [+0.0000, +0.0556] | +0.0056 [-0.0800, +0.0500] | +0.0146 [-0.0471, +0.0495] | +0.0236 [-0.0011, +0.0466] (n=10/12) |
| W034 original-only | P1_reference_sensitivity_29 | -0.1807 [-0.2379, -0.1259] | -0.1777 [-0.2451, -0.1243] | -0.1569 [-0.2246, -0.1077] | +0.0132 [-0.0012, +0.0291] (n=24/29) |
| W034 original-only | pooled_reference_sensitivity_41 | -0.1197 [-0.2016, -0.0624] | -0.1241 [-0.2191, -0.0643] | -0.1067 [-0.1909, -0.0533] | +0.0163 [+0.0062, +0.0246] (n=34/41) |

C1 主层与 P1 敏感性层都没有显示“增加 H 占比可稳定改善实际交付质量”。P1 的 580 条历史行中有 127 条不进入质量池，其中 116 条涉及 non-independent；P1 的负 eligibility-resolved/adjusted 差与三票合格率差高度一致，但这不是正式因果分解，也不得解释成 H 工人更差或更少交付。pooled resolved-only quality 约有1个百分点的小幅正差，但不足以冻结类型。W034 original-only 是必报敏感性，不用于结果后挑选版本。

`k=3` 时第二个模式不可能同时获得至少2票，supported-multimodal 恒为0是定义上的机械结果，不用于判断“没有多峰”。

## 为什么不能再硬分2–3类

- Core task-adjusted worker quality 与 dense41 Manual worker quality的 task-disjoint 描述性 Spearman 仅 0.173；两者仍有 building 重叠，不作独立验证或显著性检验解释。
- 跨11个留一 building 折和两个 W034 数据版本始终保持 H 的只有 1 人，始终保持 L 的只有 2 人；不足以形成可复用的人群类型。
- 若干折的 bootstrap 概率贴近0.80/0.20边界，具体成员和重放点估计必须保持探索性；不为凑人数移动阈值。
- Core 的 peer 与 Q_GT 不是同一维度；peer 若用于定义类别再检验共识，会形成循环。
- Core 的 307 次结构机会中只有 2 次 worker-caused failure，复发者为 0 人，不能据此造出“风险型”。
- 因此现有差异更适合保留为连续、任务依赖的 Q_GT/R_peer/F_struct，而不是固定 worker taxonomy。

## 后续最小方案

如果还要模拟混合人群，可以保留这里的 cross-fitted H/L/U 作为探索性组成分析；若要在论文中主张稳定类型，必须在新 building 结果不可见前冻结 Manual 分类规则，并用新的独立 Manual 任务复核。现有证据不能证明某类人在12–20人处收敛。

本审计不修改正式 worker profile、eligibility、routing、SAP 或方法合同。
