# PreScreen、工人画像与冻结项重新审视（2026-03-08）

本文档基于最新思路，对以下问题做统一收束：

- manual 人工锚点数量与可做折数
- semi 锚点数量与用途边界
- 是否保留连续异常分数 `S_u`
- 若不保留 `S_u`，如何重设工人画像
- Pilot 时就要锁定什么
- 现在要锁定什么
- PreScreen 后要锁定什么
- 几何平均综合分应该如何定位

结论目标不是“把方案包装得更复杂”，而是把当前样本量下真正能 defend 的部分写清楚，并把不能过度声称的部分主动降级。

---

## 1. 总判断

### 1.1 manual anchors = 20 到 22，是否可行

可行，但要明确它支撑的是“保守版 prescreen + 弱交叉验证”，而不是高自由度的强统计调参。

在当前约束下，这个数量足以承担：

- `PreScreen_manual` 的基本 admission screening
- `r_u^(0)` 的粗估计
- `w_max` 或 reliability clipping 规则的保守锁定
- 对工人进行“可用/谨慎使用/不进入主池”的初步区分

它不足以承担：

- 高维权重搜索
- 稳定的 5 折交叉验证
- 很细粒度的 failure-family 特异阈值学习
- 很强的 per-family 工人建模

### 1.2 5 折是否合适

名义上可以做，实质上不建议做。

原因很直接：

- 20 到 22 个 anchors 若做 5 折，每折验证集只有 4 到 5 个样本。
- 你当前又要求这些 anchors 覆盖关键难度层和关键 failure family，那么每折里能否保留足够覆盖会很不稳定。
- 一旦某折刚好缺少某类困难样本，该折结果就会高度受个别题影响。

因此，5 折在论文里会很容易被质疑为“形式上做了 CV，实质上每折样本过薄”。

### 1.3 更合理的折数建议

当前最稳的建议是：

- 主方案：`2-fold repeated balanced split`
- 敏感性分析：`3-fold stratified split`
- 不建议：`5-fold`

具体建议如下。

#### 主方案：2 折重复平衡切分

把 20 到 22 个 anchors 按难度层与主 failure family 做平衡切分，形成两半，各半约 10 到 11 个样本。

优点：

- 每一折验证集还有基本可解释性。
- 每半都有机会保留低难、中高难、典型失败家族的覆盖。
- 更适合当前“小样本但必须讲 coverage”的情形。

推荐写法：

- 主分析用 2 折交叉拟合或重复平衡 half-split。
- 若要减少偶然性，可做多次重复平衡切分，但切分规则必须预注册固定，不能事后挑最好结果。

#### 附加敏感性：3 折分层切分

如果你确实希望在文中体现“不是只做一刀两半”，可以把 3 折作为附加敏感性分析。

但这里要明确：

- 3 折只是辅助证明方向稳定。
- 不能把 3 折当成主锁定依据。
- 每折约 6 到 7 个验证样本，仍然只是“勉强可用”，不是强证据。

### 1.4 semi = 18 个左右，是否可行

可行，而且与当前目标基本匹配。

semi 的目标不是再做一遍 manual admission test，而是测：

- 面对初始化时是否盲信
- 面对明显失败家族时是否会纠正
- 面对“看起来像对的但其实错”的初始化时是否会被带偏

因此，18 个左右是一个合理的保守规模，但前提是结构要克制，不能试图在这么小的样本上同时覆盖太多 family。

当前最稳的结构是：

- 6 个正常初始化对照样本
- 12 个误导性初始化样本

这 12 个误导性样本，建议优先覆盖 4 个 failure family，每类 3 个：

- 过度解析
- 角点错位
- 角点重复
- 跨门扩张

“模型预标注失败”可以作为替补 family 或并入上述结构中的复合难例。

当前 trap bank 中尚不稳定的 `漏标`、`拓扑崩溃`，不建议在这一版强行写成 prescreen 必须覆盖 family；如果后续自然案例补齐，再扩展。

### 1.5 小结

在你无法再扩大人工精标规模的前提下，最稳的组合是：

- `PreScreen_manual = 30`
  - `20 到 22 manual anchors`
  - `8 到 10 random non-anchors`
- `PreScreen_semi = 18`
- `OOS gate` 独立成小池，不并入 manual anchors
- 折数：主方案 `2-fold repeated balanced split`，附加 `3-fold sensitivity`，不做 `5-fold`

---

## 2. 不保留 `S_u` 后，工人画像该怎么设

### 2.1 为什么不建议保留当前连续 `S_u`

当前版本的 `S_u` 最大问题不是“有 5 个分量”，而是：

- 样本量偏小，难以支撑稳定的连续标量化
- 各分量性质并不等价
- 其中有些分量更像系统侧/过程侧异常，而不是 worker 核心风险
- 一旦做成加权和，审稿人会追问权重为何如此设定、是否事后调参、是否把不同性质的量混在一起

特别是：

- `p_NA` 更接近字段缺失或系统侧问题，不适合作为核心 worker 风险分量
- `p_idle` 只能是弱辅助，不能当画像主轴
- `p_var` 若不做条件化，会把任务异质性误判为 worker 随机性

因此，在当前样本量与论文定位下，更严苛也更干净的做法是：

- 保留“可靠度主轴”
- 取消连续 `S_u`
- 把风险轴改成“离散风险层级 + 风险签名”

### 2.2 新画像总框架：主轴 + 风险轴

建议把工人画像改成：

- 纵轴：`Reliability main axis`
- 横轴：`Risk tier axis`
- 颜色或标签：`Dominant risk signature`

其中：

#### 主轴：可靠度主轴

主轴保留为：

`LCB(r_u)`

即只用 `Calibration_manual` 估计得到的全局可靠度置信下界作为纵轴。

理由：

- 这是最容易 defend 的量
- 它与 Kara 式“保守估计 worker 可靠度”的精神一致
- 它不依赖 semi 的误导性初始化设计
- 它可直接服务于 routing 和 weighted consensus

#### 风险轴：离散风险层级，而不是连续加权总分

不再定义一个连续 `S_u in [0,1]`。

改为定义 4 级风险层：

- `R0 Stable`
- `R1 Trust-vulnerable`
- `R2 Condition-fragile`
- `R3 Unusable / Noisy`

这样做的优点：

- 避免小样本下伪精确的连续分数
- 每一级都有明确的规则触发依据
- 更符合 reviewer 对“可解释、可审计、可路由”的偏好

### 2.3 风险层级的定义

建议使用三项核心风险指标，不再做一个总和分：

#### 核心风险 1：`T_u`，盲信初始化风险

定义来源：`PreScreen_semi`

含义：

- 当初始化看似合理或改动成本较高时，工人是否倾向于“几乎不改就提交”
- 即便初始化明显偏离专家参考，也不进行必要纠正

这项是你当前体系里最该保留的 semi 维度，因为它是人机协同场景特有风险。

#### 核心风险 2：`C_u`，条件性脆弱风险

定义来源：`Calibration_manual`

含义：

- 工人不是全局都差，而是在高风险桶、困难层或特定结构问题上明显崩溃

建议用“条件落差”来定义，而不是原始全局波动：

`C_u = high-risk bucket reliability gap`

也就是比较 worker 在低风险桶与高风险桶中的可靠度差异，或直接看其在高风险桶是否跌破保守阈值。

这比原始 `p_var` 更接近 Liu 式的 partial spammer / selective failure 思路。

#### 核心风险 3：`G_u`，可计算失败倾向

定义来源：`PreScreen_manual + Calibration_manual`

含义：

- 工人是否频繁产生无法渲染、无法闭合、无法归一化等提交

这项不该被写成“恶意风险”，而应被写成“工程可用性风险”。

它不证明工人坏，但直接影响系统成本和可用性，所以必须进风险轴。

### 2.4 弱辅助项：不进主风险轴，只进审计列

以下两项建议不再做主轴或主风险轴定义：

- `E_u`：低努力代理（极短 `active_time` 等）
- `M_u`：缺失/NA 事件

理由：

- `E_u` 的解释太弱，容易与熟练度或任务简单度混淆
- `M_u` 在前端硬校验完善后，应更接近流程质量审计量，而不是 worker 本体风险量

因此它们更适合出现在 worker card 或附录审计表里，而不是主画像定义里。

### 2.5 推荐的分组规则

建议按顺序判定，避免重叠：

#### `R3 Unusable / Noisy`

满足任一条件即可进入：

- `LCB(r_u)` 低于 prescreen/calibration 预注册底线
- `G_u` 高，说明工程可用性差
- 在 manual anchor 上已明显不达最低 admission 标准

这是“不能进入主路由池”的组。

#### `R2 Condition-fragile`

满足以下任一条件：

- `C_u` 高，即高风险桶显著掉队
- 在特定高风险桶上的 `LCB(r_u^(b))` 跌破阈值

这是“不能参与其脆弱场景”的组。

#### `R1 Trust-vulnerable`

满足以下条件：

- 全局可靠度尚可
- `T_u` 高，即 semi 中盲信初始化倾向明显

这是“可以参与 manual 常规任务，但不应优先派给依赖纠错的人机协同任务”的组。

#### `R0 Stable`

不触发上述风险，且 `LCB(r_u)` 达到主池标准。

这是默认主路由池。

### 2.6 最终画像怎么画

如果取消连续 `S_u`，图上不要硬画一个伪连续横轴。

建议这样画：

- 纵轴：`LCB(r_u)`
- 横轴：`Risk tier`，取离散位置 `R0/R1/R2/R3`
- 点颜色：主风险类型
  - 蓝：Stable
  - 黄：Trust-vulnerable
  - 橙：Condition-fragile
  - 红：Unusable / Noisy
- 点旁或附表：给出 `T_u / C_u / G_u / E_u / M_u` 的审计签名

这样比“一个连续 `S_u`”更理性，也更符合当前样本量约束。

### 2.7 这一改法的理论收益

改成“可靠度主轴 + 离散风险轴”后，你得到的不是更花哨的图，而是更干净的逻辑：

- 主轴负责“能不能信”
- 风险轴负责“在哪种意义上要谨慎使用”

这和 Kara、Liu 的角色分工是兼容的：

- Kara 更偏向可靠度、共识和追加停止
- Liu 更偏向 worker type、instance uncertainty 和验证优先级

你这里不再需要强造一个“所有风险都可压成一个数”的总分。

---

## 3. 各实验集内容的最新建议

### 3.1 `PreScreen_manual`

目标：测基本人工几何能力。

结构：

- 总数 30
- 其中 20 到 22 为人工锚点
- 8 到 10 为随机非锚点

manual 锚点应覆盖：

- 非常简单
- 遮挡明显但仍可闭合
- 拼接缝及拉伸
- 玻璃/反光但仍可稳定给几何参考

manual 集合中不应混入：

- OOS gate 样本
- 本身无法稳定给出几何专家参考的证据不足样本

### 3.2 `PreScreen_semi`

目标：测纠错与盲信初始化风险。

结构：

- 总数约 18
- 6 个正常初始化对照
- 12 个误导性初始化样本

优先 family：

- 过度解析
- 角点错位
- 角点重复
- 跨门扩张

若自然失败不足：

- 用规则化扰动补足
- 但 family 列表与补足规则必须现在写死，不能事后按结果增删

### 3.3 `OOS gate`

目标：测是否能正确拒绝继续几何闭合。

当前应独立成池，不与 `PreScreen_manual` 混算。

优先 family：

- 边界不可判定
- 证据不足
- 错层/多平面
- 几何假设不成立（如弧形墙）

### 3.4 `Calibration_manual`

目标：估计真正进入 routing 的 `r_u` 与 `LCB(r_u)`，并评估条件性脆弱风险 `C_u`。

注意：

- 最终 routing 的可靠度阈值，不应在 PreScreen 就全部锁死
- 需要在 Calibration 后再锁定高风险桶上的路由规则

---

## 4. 现在必须锁定什么

当前就应该锁定的是“协议与结构”，而不是所有数值。

### 4.1 必须现在锁定的内容

#### A. 各样本池的职责边界

- `PreScreen_manual` 只测几何人工能力
- `PreScreen_semi` 只测纠错与盲信风险
- `OOS gate` 单独测 scope/gate 能力

#### B. 样本池规模与组成规则

- `PreScreen_manual = 30`
- `manual anchors = 20 到 22`
- `manual non-anchors = 8 到 10`
- `PreScreen_semi = 18`
- `OOS gate` 单独成池

#### C. anchor 采样规则

- manual anchors 采用“覆盖关键难度层和关键 failure family”
- non-anchor 部分随机抽样
- semi 采用“正常初始化对照 + 误导性初始化 trap”
- OOS gate 不混入 manual geometry anchors

#### D. 折数协议

- 主方案：2 折重复平衡切分
- 敏感性：3 折
- 不做 5 折

#### E. 新工人画像的定义框架

- 主轴：`LCB(r_u)`
- 风险轴：`R0/R1/R2/R3`
- 核心风险指标：`T_u / C_u / G_u`
- `E_u / M_u` 只做辅助审计

#### F. 几何平均的定位

- 仅用于 `RQ3` 的辅助综合分
- 不作为主终点
- 维度和权重集合现在就冻结

### 4.2 几何平均现在应锁定的具体内容

建议现在锁定：

- 只在 `RQ3` 使用
- 主聚合：`GM`
- 敏感性：`AM`
- 权重集合固定为少量离散方案，不做搜索
- 不把 worker profile 变量、`r_u`、风险指标放进跑分

推荐维度：

- 质量
- 成本
- 时间

如果失败事件足够稳定，才考虑加入安全维度；否则单独报告。

---

## 5. PreScreen 后要锁定什么

PreScreen 后应锁定的是 admission 与初筛层面的阈值，而不是所有 routing 细节。

### 5.1 PreScreen 后可以锁定的内容

#### A. 准入结果

- 哪些 worker 进入 calibration/main 候选池
- 哪些 worker 被排除

#### B. prescreen admission thresholds

- manual 最低可靠度门槛
- semi 盲信初始化门槛
- 最低有效任务数门槛
- 工程可计算失败底线

#### C. `w_max` 或 reliability clipping 规则

应基于 manual anchors 的主方案切分协议锁定，不再改。

#### D. 风险层级中的 prescreen 部分

例如：

- `R3` 的初步剔除条件
- `R1` 的初步盲信风险条件

### 5.2 PreScreen 后不要提前锁死的内容

以下内容更适合等 `Calibration_manual` 后再最终冻结：

- 最终 `LCB(r_u)` 主池阈值
- 条件性脆弱风险 `C_u` 的高风险桶阈值
- 高风险任务的最终 routing 候选规则
- 场景/风险桶下的禁用或降级规则

原因是这些量真正依赖 `Calibration_manual` 的较稳定统计，而不是 PreScreen 的小样本 admission 数据。

因此可以写成：

- 现在锁协议
- PreScreen 后锁 admission
- Calibration 后锁 routing

---

## 4.5 你现在这个阶段（Pilot）就必须锁定什么

你现在不是在锁最终结果数值，而是在锁协议源头。Pilot 阶段最重要的是把“后面不能再随结果改”的边界先写死。

### A. 池边界与不重叠约束

- `PreScreen_manual`、`PreScreen_semi`、`OOS gate` 三池职责边界
- 同一 `base_task_id` 不跨池复用
- manual anchors 不混入 OOS 几何不可判定样本

### B. manual 抽样框架

- `PreScreen_manual = 30`
- 其中 `20 到 22 anchors + 8 到 10 random non-anchors`
- anchor 的覆盖轴是什么
- non-anchor 的随机候选池是什么

### C. semi trap schema

- `PreScreen_semi ≈ 18`
- 正常初始化对照与误导性初始化 trap 的配额结构
- synthetic 为主、natural-failure 为辅的 source hierarchy
- failure family 候选集合与 realized quota 披露方式

### D. weighted consensus 的候选网格与切分协议

- 候选 `w_max` 网格
- 主锁定方案采用 `2-fold repeated balanced split`
- 3 折只是敏感性分析
- 5 折不采用
- 如果主方案跑不稳时，A/B split 的降级规则

### E. 工人画像定义框架

- 不再用连续 `S_u`
- 改为 `LCB(r_u) + 风险层级 R0/R1/R2/R3`
- 核心风险指标 `T_u/C_u/G_u`
- 辅助审计指标 `E_u/M_u`

### F. 审计协议与日志字段

- active time 协议
- blocked error / rejected submission 的日志字段
- NA 与字段缺失的披露方式
- `worker_group_reason`、`group_rule_version` 等输出字段

所以严格说，Pilot 阶段应锁定的是：

1. 抽样框架
2. 池边界
3. 候选网格
4. 定义与日志 schema
5. 不可变的随机种子与 split 规则

而不是在没有 PreScreen 数据时就去锁 `\tau_{fail}`、`\tau_r`、`\tau_{trust}` 这些最终 admission 数值。

这比试图在 PreScreen 一次性锁死所有参数更严谨。

---

## 6. 关于 weighted consensus 的最新站位

当前最稳的写法不是：

“我在小样本上精确学习每个 worker 的完备权重模型。”

而是：

“我用 PreScreen 与 Calibration 得到保守可靠度估计，并用其作为 weighted consensus 的约束性权重来源。”

因此：

- 权重应是保守、裁剪过的
- 不要允许少数高可靠工人无限制主导
- 不要把 worker 风险指标直接并入 consensus 权重主公式

更稳的是：

- `LCB(r_u)` 决定上限和基础权重
- 风险层级决定能否进入某类任务候选池

也就是：

- 可靠度决定“给多少权重”
- 风险轴决定“能不能参与、能参与哪类任务”

这比把所有信息揉进一个 `w_u` 更符合 Kara + Liu 的组合逻辑。

---

## 7. 最终推荐的落地版本

如果只保留一版最稳、最能写进论文的方法，我建议采用下面这版：

### 7.1 PreScreen

- `PreScreen_manual = 30`
  - `20 到 22 anchors`
  - `8 到 10 random non-anchors`
- `PreScreen_semi = 18`
- `OOS gate` 独立小池

### 7.2 折数

- 主方案：`2-fold repeated balanced split`
- 敏感性：`3-fold`
- 不做：`5-fold`

### 7.3 工人画像

- 主轴：`LCB(r_u)`
- 风险轴：`R0/R1/R2/R3`
- 核心风险：`T_u / C_u / G_u`
- 辅助审计：`E_u / M_u`

### 7.4 几何平均

- 只用于 `RQ3`
- 只做辅助综合分
- `GM` 为主，`AM` 为敏感性分析

### 7.5 锁定节奏

- 现在：锁协议、锁集合角色、锁样本组成规则、锁折数方案、锁画像定义、锁 GM 口径
- PreScreen 后：锁 admission thresholds、锁 `w_max`、锁候选工人池
- Calibration 后：锁最终 routing thresholds 与高风险任务的分配规则

---

## 8. 一句话总结

在当前资源约束下，最严谨的版本不是去硬做 5 折和连续 `S_u`，而是承认样本量边界，改用：

- `20 到 22 manual anchors + 2-fold repeated split`
- `18 semi anchors`
- `LCB(r_u) + 离散风险层级`
- `RQ3-only` 的几何平均辅助综合分

这套方案更保守，但更能过审，也更符合你现在真实能做出来的证据强度。