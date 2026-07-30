# Paper A 新版完整论文提纲与方法合同草案

## 可审计的全景布局标注：高信息 PreScreen、双波 Calibration、Semi-Auto 条件效应与支持度感知路由

**文档性质：** 论文正文与实验执行的统一新版提纲  
**版本定位：** 以当前新方案为唯一主线；旧提纲仅保留经过复核后仍有效的方法模块  
**固定执行链：**

```text
Pilot
→ P1 PreScreen
→ C1 Calibration Wave A
→ C2 Calibration Wave B / Precision Completion
→ T1 Semi-Auto Effect Test
→ V1 Routing Validation
→ V2 External Support Audit（可选）
```

**不进入 Paper A 一级贡献：**

- HoHoNet 模型重训练；
- Bi-Layout；
- Manhattan A-line 工具；
- worker-facing Manhattan correction；
- 自动 OOS 模型；
- 大规模 GT 重建。

---

# 摘要

本文研究一种面向全景房间布局标注的数据生产与工人路由框架。研究主要沿用公开数据集已有布局 GT，仅对极少量经复核确认的问题样本进行人工纠错。方法主线由高信息 PreScreen、双波 Calibration、Semi-Auto 条件效应试验和前瞻路由验证构成。

P1 不仅承担准入，还用于形成高信息的工人诊断证据和跨阶段预测因子。C1 在较自然任务中分别测量任务难度校正后的外部 GT 质量、worker-specific Geometry LOO 同行一致性和工人造成的结构性失败。C2 根据 C1 的方差、任务图结构和功效模拟确定共同风险桥接任务的数量与组成，并通过层级收缩和精度自适应补测形成支持度感知的风险韧性画像。T1 采用 Manual/Semi × ordinary/stress_assist 设计，检验 Semi-Auto 是否在保持交付质量的同时降低完整任务时间。V1 将任务随机分配至强 Global 或 Full-Integrated，在共享有限工人池中使用对称容量账本、相同 offer/替补规则、相同动态冗余和相同 GT-blind 聚合合同，检验条件画像是否在强 Global 之上产生前瞻路由增量。支持不足、任务侧激活模糊或政策输出多峰时，系统显式 fallback 或进入 unresolved，而非强制个体化或无限追加。

本文的核心贡献不是提出新的布局模型，而是建立一套能够区分外部正确性、同行一致性、结构有效性、模型辅助风险和画像支持范围的可审计标注协议，并检验高信息 PreScreen 证据是否具有跨阶段预测和路由价值。

---

# 1 引言

## 1.1 研究背景

全景房间布局标注需要工人同时处理：

- 相机所在空间的识别；
- Scope/OOS 判断；
- 房间边界和角点几何；
- 模型初始化的识别与纠正；
- 遮挡、开放边界和邻接空间；
- 任务过程与完整性。

Semi-Auto 初始化可能降低操作负担，但也可能诱发：

- blind trust；
- correction failure；
- over-correction；
- undercoverage；
- 结构性无效提交。

不同工人在一般任务、高风险任务和模型错误条件下的表现并不一定相同。单一的全局工人排名可能无法充分利用这种差异，但高维个人画像又容易受到小样本和支持不足影响。

## 1.2 研究缺口

现有方案通常存在以下不足：

1. 把 PreScreen 仅视为准入，而没有检验其跨阶段预测价值；
2. 将工人与同行一致性等同于外部正确性；
3. 忽略结构性无效提交导致的选择性可计算问题；
4. 在不同难度任务分发下直接按原始平均质量排名工人；
5. 在小样本下无条件发布个体条件画像；
6. 将路由简化为一个评分公式，而未定义 offer、容量、追加、聚合和终态；
7. 只在 resolved 子集评价质量，忽视 unresolved 的选择性分母；
8. 使用平衡试验分布替代真实生产任务分布。

## 1.3 方法路线

本文采用：

```text
高信息 P1
→ 较自然 C1
→ 共同风险桥接与精度补齐 C2
→ Semi 条件效应 T1
→ 强 Global 对比支持度感知 Full V1
→ 外部域支持审计 V2
```

并始终分离：

```text
公开/纠错 GT 外部正确性
Geometry LOO 同行一致性
worker-caused structural failure
模型辅助风险
Calibration 支持范围
```

## 1.4 一级贡献

### 贡献一：高信息 PreScreen 到跨阶段预测的证据链

P1 同时承担：

- 准入；
- 高信息 failure-family 诊断；
- blind-trust、Scope 和 process 风险识别；
- P1→C1/C2/T1 的预测分析；
- 经验证后进入 Full-Integrated 的条件画像来源。

### 贡献二：双波 Calibration 与三轨工人测量

C1/C2 分别建立：

- 任务难度校正后的 GT 外部质量；
- worker-specific LOO 同行一致性；
- 工人造成的结构性失败；
- 层级收缩的风险韧性；
- 支持状态和 fallback。

### 贡献三：完整、可执行的支持度感知路由政策

V1 不仅冻结评分，还冻结：

- task risk；
- worker eligibility；
- capacity；
- offer；
- replacement；
- dynamic redundancy；
- GT-blind aggregation；
- resolved/unresolved/failure；
- ITT outcome。

## 1.5 研究问题

### RQ1：Semi-Auto 条件效应

Semi-Auto 是否在不降低交付质量的前提下降低 active time？其效果是否随 `risk_assist` 改变？

### RQ2：P1 与工人状态的跨阶段效度

P1 高信息证据能否预测 C1/C2/T1 中的外部质量、同行一致性、纠错行为和风险脆弱性？

### RQ3：条件画像的路由价值

在强 Global 基线、相同容量和相同生产合同下，Full-Integrated 是否提高交付调整质量或降低预算？

### RQ4（可选）：外部支持失效

在 ZInD 等外部域中，系统能否识别画像不受支持的任务并安全 fallback？

---

# 2 相关工作

## 2.1 全景布局估计与一维布局表示

介绍 HorizonNet 的 ceiling–wall、floor–wall、wall–wall 一维表示，以及 HoHoNet 的 Latent Horizontal Feature。说明本文使用这些表示构造标注前模型风险，而非改进模型本身。

## 2.2 模型辅助标注与 automation bias

区分：

- issue recognition；
- geometry correction；
- blind trust；
- over-correction。

说明工人勾选 Model Issue 不等于已成功纠正。

## 2.3 众包工人建模与共识

讨论：

- 工人全局能力；
- 条件能力；
- 小样本收缩；
- disagreement；
- LOO independence；
- 多峰共识。

## 2.4 自适应任务分配与动态冗余

讨论：

- worker selection；
- capacity；
- offer/acceptance；
- stopping；
- unresolved；
- policy evaluation。

## 2.5 可审计证据与信息时序

强调：

- 决策时只能读取当时已到达信息；
- 任务结果不能回填首次路由；
- 同一 submission 对不同 estimand 可以具有不同资格；
- 旧数据、修订 GT 和 worker state 必须版本化。

---

# 3 总体协议与数据生命周期

## 3.1 阶段职责

| 阶段 | 核心职责 | 允许用途 | 禁止用途 |
|---|---|---|---|
| P1 | 准入、高信息诊断、预测因子 | admission、failure-family、P1→后续预测 | 正式 Global、未经验证的路由画像 |
| C1 | 基础能力、风险发现、方差估计 | provisional worker state、C2 设计、功效模拟 | 最终政策、Main 结论 |
| C2 | 共同桥接、支持补齐、正式冻结 | Global/Full、risk、support、fallback | 根据 Main 结果回调 |
| T1 | Semi 条件效应 | RQ1 | 修改 worker state |
| V1 | 路由前瞻验证 | RQ3 | 重新调权重和阈值 |
| V2 | 外部支持审计 | RQ4 | 回流修改 V1 |

## 3.2 冻结边界

P1、C1 已发生的 admission、assignment 和 raw submission 不回改。

C2 后冻结：

```text
reference registry
Global policy
Full-Integrated
risk_assist
risk_route
support thresholds
capacity
offer/replacement
dynamic redundancy
aggregation
terminal states
statistical analysis
```

## 3.3 信息时序

### 首次路由可读取

```text
公开任务 metadata
HoHoNet feature/output risk
Calibration worker state
availability
capacity
历史 process eligibility
```

### 响应到达后才可读取

```text
当前任务的合法提交
几何相似度
结构有效性
Scope state
冲突状态
已到达响应数
```

### 禁止回填首次路由

```text
当前任务 Difficulty
当前任务 Model Issue 票
最终 crowd consensus
最终 GT 评价
事后专家裁决
```

## 3.4 Estimand-specific inclusion

同一 submission 分别保存：

```text
eligible_for_active_time
eligible_for_GT_quality
eligible_for_LOO
eligible_for_structural_failure
eligible_for_semi_correction
eligible_for_predictive_validity
eligible_for_routing_feature
```

不存在一个全局 `valid` 字段替代所有分析。

---

## 3.5 失败归因、外部事故与重跑合同

所有阶段将异常先按冻结证据规则区分为：

    worker_caused_structural_failure
    policy_caused_failure
    external_system_failure
    not_evaluable

worker-caused structural failure 是可归责于提交的重复角点、非法 pair 数、自交、拓扑坍塌等；它进入对应 worker/condition 的结构机会分母。policy-caused failure 包括 candidate exhaustion、替补规则失败和容量耗尽，归责于原政策臂而非工人。external system failure 仅限有时间窗、服务端/平台/导出证据和影响范围记录支持的整站宕机、平台不可用或导出损坏；缺少该证据的异常为 not evaluable，不得事后改称系统事故。

C2 freeze 前必须锁定事故类别词表、证据要求、判定人/时间、每任务最多一次重跑、T1 配对重跑、V1 同臂同版本对称容量重跑和行政删失规则。分类、重跑或删失决定必须在查看受影响 T1 条件结果或 V1 政策结果前完成，保留 incident ID、原任务、重跑任务、证据 SHA 和 disposition。外部事故不降低 worker reliability，也不计为 policy failure；若无法按冻结规则重跑，则行政删失并按条件/臂报告原始、重跑、删失数量及原因。

# 4 数据来源与单一 operational reference

## 4.1 GT 组成

正式参考池由以下构成：

```text
绝大多数：
公开数据集原始 GT

极少数：
经人工复核后纠错的 GT
```

论文不得声称大规模重建 GT。

## 4.2 Reference 状态

```text
reference_ready
reference_corrected
pending_adjudication
oos_geometry_not_applicable
```

### `reference_ready`

直接使用公开原始 GT。

### `reference_corrected`

极少量明确问题经复核后冻结修订版本。

### `pending_adjudication`

尚未完成单一 operational reference 裁决，不进入几何主分母。

### `oos_geometry_not_applicable`

当前相机房间协议无法形成合法单一布局，不进入普通几何评价。

## 4.3 单一 operational reference

正式表述为：

> 每张 in-scope、geometry-evaluable 任务，在冻结的 enclosed camera-room 协议下只保留一个 operational reference；无法唯一收口的任务进入 pending adjudication 或 OOS。

不使用：

- hard-multi；
- soft ambiguous reference；
- max-over-reference。

## 4.4 GT 冲突两步审查

### 第一步：盲法初步裁决

只查看：

```text
原始全景图
公开 GT
冻结协议
```

不查看工人身份、支持人数和工人等级。

### 第二步：冲突解释

初步裁决冻结后，再查看匿名提交，用于：

- 解释 undercoverage；
- 解释 overextension；
- 识别协议误解；
- 建立反例类别。

若第二步揭示明确遗漏并导致重新修订，标记：

```text
submission_informed_reference_revision = true
```

触发修订的原提交不使用该修订 GT 进入自身 primary GT-quality 评价，只进入敏感性或后续独立评价。

## 4.5 数据切分

硬要求：

- C2、T1、V1 image-disjoint；
- 同一 image 的 Manual/Semi 在同一 T1 任务内；
- 同一 worker 不看同一 image 两种模式；
- T1/V1 尽量 building-disjoint；
- ZInD 仅用于 V2。

---

# 5 四类证据与三类共识

## 5.1 四类证据

```text
Scope/OOS
Difficulty
Model Issue
Geometry
```

四类证据分别进入不同 gate。

## 5.2 三类共识

### 任务描述共识

描述场景或问题是否被多名工人主张。

### 评价参考

由公开 GT 或冻结人工裁决提供。

### 停止共识

用于决定是否继续追加、是否 resolved。

三者不得共用一个多数阈值。

## 5.3 三状态任务标签

对 task–tag 保存：

```text
positive assertion
explicit negative
unasserted
not evaluable
```

以及：

```text
a = positive count
e = explicit negative count
u = unasserted count
```

若：

```text
a >= 2 且 e >= 2
```

记为显式冲突，不转成普通 positive/negative task truth。

## 5.4 Scope/OOS 与 undercoverage

- OOS：任务是否适合当前协议；
- undercoverage：任务可标，但工人未完整覆盖相机所在空间。

undercoverage 不归入 OOS。

## 5.5 Model Issue

严格分开：

```text
issue recognition
geometry correction
blind trust
over-correction
```

Model Issue 反馈栏耗时不单独扣除，完整任务 active time 仍为 RQ1 的真实使用成本。

---

# 6 P1：高信息准入、诊断与预测

## 6.1 P1 的四层作用

### 第一层：准入

筛除明显不具备基础能力或完整性条件的工人。

### 第二层：高信息诊断

观察：

```text
geometry failure
blind trust
correction failure
Scope misunderstanding
structural failure
process-integrity risk
failure-family vulnerability
```

### 第三层：跨阶段预测

主要链路：

```text
P1 → C1
P1 → C2-B
P1 → T1
```

报告：

- Spearman/Kendall；
- worker bootstrap CI；
- directional consistency；
- discrepancy workers；
- support；
- range restriction。

### 第四层：Full 条件画像候选

只有满足以下条件的 P1 分量才可进入 Full：

1. evidence 合法；
2. 在 C1/C2-B 方向复现；
3. support 达标；
4. 能由标注前任务特征激活；
5. 使用收缩估计；
6. V1 前冻结；
7. 不使用 V1 outcome 选择。

## 6.2 双链路

### 全局基础链

```text
C1/C2 Manual
→ task-adjusted GT quality
→ LOO consistency
→ structural failure
→ Global
```

### P1 条件诊断链

```text
P1 high-information evidence
→ C1 predictive validation
→ C2-B common bridge
→ C2-A precision completion
→ validated conditional component
→ Full-Integrated
```

两条链不能直接按原始任务数池化。

## 6.3 P1 retrospective integrity amendment

- parent-derived 或其他 non-independent P1 submission 不进入 capability 主证据，也不进入正式 timing 主证据；
- 这些记录可保留为 process-integrity 负证据，但不回改已经完成的 admission；
- P1→C1/C2-B/T1 预测分析只使用 independent 且 estimand-eligible 的 P1 证据；
- support 不足、独立性不明或跨阶段未复现的 P1 component 不进入 Full。

---

# 7 C1：基础能力、任务调整与设计参数估计

## 7.1 C1 目标

C1 不是最终画像冻结，而是：

- 基础能力估计；
- 任务难度校正；
- 风险发现；
- worker/task/building 方差估计；
- C2 数量与结构设计；
- T1/V1 功效模拟。

## 7.2 GT 外部质量

\[
Q^{GT}_{t,u}=IoU(A_{t,u},G_t)
\]

保存 raw 工人中位数，但正式全局能力应校正任务组成。

## 7.3 Task-adjusted global ability

推荐交叉分类模型：

\[
Q^{GT}_{t,u}
=
\mu+\alpha_u+b_{\text{building}(t)}+b_t+\eta_{\text{stage}}+\epsilon_{t,u}.
\]

其中：

- \(\alpha_u\)：工人全局质量；
- \(b_{\text{building}(t)}\) 与 \(b_t\)：building/task random intercept；
- \(\eta_{\text{stage}}\)：阶段固定效应，仅在跨阶段共同 anchor 或随机效应结构可识别时解释。

C1-only 分析使用 task effect 且不同时估计 stage effect。若 task 与 stage 完全嵌套且缺少共同 anchor，则合并模型中的 stage effect 标为不可识别，禁止把被 task effect 吸收的差异解释为阶段效应。

输出：

```text
Q_u_GT_raw
Q_u_GT_task_adjusted
CI / LCB
support
```

审计 worker–task 二部图：

```text
任务图连通性
共同任务数量
每任务有效工人数
anchor/core 覆盖
工人任务难度组成
```

## 7.4 Geometry LOO

对工人 \(u\)：

\[
q^{LOO}_{t,u}=IoU(A_{t,u},C_t^{(-u)}).
\]

工人自己的提交不得进入 reference。

输出：

```text
peer_support
medoid_identity
medoid_margin
largest_cluster_support
second_mode_support
leave-one/two-out sensitivity
consensus_status
metric compatibility
```

### LOO 状态

```text
stable
weak
multimodal
insufficient
metric_incompatible
```

- stable：进入 primary；
- weak：进入 sensitivity；
- multimodal：不强行选择单一 crowd consensus；
- insufficient：不计算；
- metric_incompatible：进一步判断责任来源。

## 7.5 Worker-caused structural failure

\[
F_u^{struct}
=
\frac{
n_{\text{worker-caused invalid geometry}}
}{
n_{\text{structural-evaluable opportunities}}
}.
\]

包括：

```text
duplicate corner
invalid pair count
self-intersection
pair fold
invalid polygon
worker-caused topology collapse
```

排除：

```text
external_system_failure
parser/export failure
reference failure
OOS
unknown attribution
```

其中 parser/export failure 只有满足第 3.5 节的外部事故证据要求时才可标为 external system failure；否则为 not evaluable，不进入 worker-caused structural failure 分母。

## 7.6 三轨工人基础状态

```text
Q_u_GT_task_adjusted
R_u_peer
F_u_struct
```

分别表示：

- 外部正确性；
- 同行一致性；
- 结构有效性。

---

# 8 HoHoNet/HorizonNet 任务风险

## 8.1 三个变量

```text
d_model_feat
g_model_struct
d_cal_support
```

## 8.2 `d_model_feat`

基于 HoHoNet LHFeat：

\[
d^{feat}_t
=
kNNDist\left(
\phi(H_t),
\{\phi(H_i):i\in B_{\text{train-ref}}\}
\right).
\]

处理：

- checkpoint 固定；
- preprocess 固定；
- PCA/whitening 只在参考库拟合；
- 处理 circular shift 和 seam；
- 保存 global 与 local-max 距离。

## 8.3 `g_model_struct`

基于一维布局输出：

```text
ceiling/floor curve
wall-wall peaks
corner/pair count
topology
seam stability
postprocess validity
```

保存可解释 flags，不只保留单一风险分。

## 8.4 `d_cal_support`

### \(d_{\text{cal}}^A\)

只基于 C1，用于设计 C2。

### \(d_{\text{cal}}^F\)

C2 后计算，用于 V1 激活和 fallback。

不得用最终版本反向解释 C2 选择。

## 8.5 两类风险

### `risk_assist`

服务 T1，预测模型初始化与纠正风险。

### `risk_route`

服务 V1，预测 Manual 外部质量下降、LOO disagreement、结构失败或 worker ranking instability。

C1 用于候选筛选，C2-B 用于共同确认，C2-A 只补精度，不重新搜索新风险。

---

# 9 C2：共同桥接、层级收缩与精度补齐

## 9.1 C2 数量由 C1 决定

C1 closeout 后通过模拟决定：

```text
每人工人 C2-B 数量
共同 anchor 数
多样化 bridge 数
unique task 数
每图 worker support
worker–task 图连通性
```

不是预先机械固定 6+6。

## 9.2 C2-B 的结构

推荐结构：

### 共同 anchor

所有工人共同完成少量 ordinary/stress，用于横向可比与波次校正。

### 多样化 bridge

从更大任务池按平衡不完全区组分配，增加 unique image 和任务外推能力。

C2-B 总量可以是：

```text
每人 12–16 张仅作为当前预算规划候选区间
```

正式数量由 C1 冻结模拟选择；若该区间内所有候选均不能满足精度、任务多样性和政策可行性门，
不得机械限制在 12–16 张。

## 9.3 风险韧性层级模型

\[
Q^{GT}_{u,t}
=
\alpha_u+\gamma I_t^{route}
+b_uI_t^{route}
+\eta_{\text{stage}}
+r_t+\epsilon_{u,t}.
\]

其中：

\[
b_u\sim N(0,\tau_b^2).
\]

定义收缩后的：

\[
\widetilde B_u^{risk}=E[b_u\mid data].
\]

输出：

```text
posterior/EB mean
interval width
leave-one-task-out stability
leave-one-block-out stability
routing_activation_allowed
```

## 9.4 C2-A-RP：精度自适应补测

对以下工人补充：

- 当前区间过宽；
- 少量任务可能改变 routing eligibility；
- 无 process/independence blocker。

每次补充：

```text
1 ordinary + 1 stress
```

每人最多 1–3 个 block，即 0–6 张。

选择依据是预期减少决策不确定性，不是当前结果是否有利于 Full。

每次补测必须冻结并保存 target component、gap reason、候选任务池、历史任务排除、
选择规则、随机种子、selection probability、support before/after、任务总 support、
building balance 与 worker--task overlap。C2-A-RP 不能把无权重任务池直接并入 Global，
只更新预声明的条件分量；达到上限仍不稳定时 adjustment=0。不得为了让 Full 显著而继续补题。

## 9.5 支持不足的降级

达到补测上限仍不稳定：

```text
B_u_routing_eligible = false
B_u adjustment = 0
fallback = Global
```

可将个体状态降为：

```text
risk_resilient
risk_vulnerable
uncertain
```

避免小样本下发布过细连续排名。

## 9.6 C2-S

仅在 Semi correction support 明显不足时追加，不进入 Manual Global 或 V1 主要 Full。

## 9.7 C2 冻结门

启动 V1 前必须满足或明确降级：

1. `risk_route` 在 C2-B 获得确认；
2. 足够工人具有可用 \(B_u^{risk}\)；
3. P1 family 可由标注前任务特征激活；
4. Full 与 Global 存在足够政策差异；
5. V1 对主要结果具有可接受功效。

---

# 10 强 Global 与 Full-Integrated

## 10.1 Global 候选审计

C1/C2 cross-fitted replay 比较：

```text
Global-LOO
Global-GT
Global-GT-gated-LOO
```

报告：

```text
corr(Q_u_GT, R_u_LOO)
ranking overlap
top-k overlap
rank displacement
discrepancy workers
replay quality
```

## 10.2 正式 Global

推荐默认：

### Eligibility

```text
process valid
independence valid
Q_u_GT support sufficient
F_u_struct <= threshold
LCB(Q_u_GT_task_adjusted) >= quality floor
```

### Ranking

\[
S_u^G=LCB(Q_{u,\text{task-adjusted}}^{GT}).
\]

### Tie-break

```text
LCB(R_u_LOO)
availability
capacity
frozen random rule
```

若另一候选 Global 在提前冻结的 cross-fitted 选择程序下稳定更强，可采用该候选，但不得使用 V1 outcome。

## 10.3 Full 评分

\[
S^F_{u,t}
=
S^G_u
+
I_t^{route}\lambda_B\widetilde B_u^{risk}
+
I_{t,f^*}\lambda_P\widetilde H_{u,f^*}^{P1}.
\]

其中：

- \(I_t^{route}\)：冻结 `risk_route`；
- \(f^*\)：由标注前任务信息激活的固定 failure family；
- 每张任务最多激活一个 P1 family；
- 总调整有上限。

## 10.4 P1 family 词表与激活

固定少量可路由族，例如：

```text
adjacent-space overextension risk
undercoverage / underextension risk
corner-localization instability
topology / over-parsing risk
```

任务侧激活：

\[
f^*=\arg\max_f a_{t,f}.
\]

只有最高分超过阈值且与第二名 margin 足够时激活；否则关闭 P1 分量。

## 10.5 权重与稳定性

- 使用小型离散权重集；
- image-level nested cross-fitting；
- 先满足 severe/unresolved 和质量 floor；
- 再最大化交付调整质量；
- 使用 one-standard-error 原则选择更简单权重；
- 冻结总调整上限。

## 10.6 Full fallback

### 关闭单一分量

```text
P1 component unsupported
B_u unsupported
```

### 整体退化 Global

```text
d_cal_F out of support
task family activation ambiguous
缺少至少两名 conditional-supported 工人
ranking 对小扰动不稳定
profile version incompatible
```

## 10.7 政策差异可行性

C2 freeze 后报告：

```text
profile activation rate
fallback rate
Full/Global 推荐首选不同率
初始工人集合不同率
supported candidate count
capacity 后差异
```

若两政策几乎不产生不同决策，不强行运行无信息 V1。

---

# 11 T1：Semi-Auto 条件效应

## 11.1 设计

\[
2\times2:
\quad
Manual/Semi
\times
ordinary/stress_{assist}.
\]

50:50 是实验设计分布，不代表生产分布。

## 11.2 工人随机分配

每图：

```text
2 Manual
2 Semi
```

四个 slot 在合格工人中约束随机分配：

- 同一工人不看同图两种模式；
- 每名工人 Manual/Semi 平衡；
- ordinary/stress 平衡；
- workload cap；
- 保存 candidate set、seed 和 assignment probability。

## 11.3 结构有效性

每条提交先判：

```text
structurally_valid
worker_caused_structural_failure
external_system_failure
not_evaluable
```

worker-caused structural failure 取 structurally_valid=0，且在其原 Manual/Semi 条件内保留。external system failure 不归责工人或条件；仅在冻结证据规则确认、结果尚不可见时，才触发第 3.5 节的处置。其他无法归因异常为 not evaluable，不静默并入任一失败类别。

## 11.4 Primary quality estimand

对每条提交：

\[
U_{t,u}
=
I(structurally\ valid)\times IoU(A_{t,u},G_t).
\]

worker-caused structural failure 的 submission-level delivery-adjusted quality 取 0。确认的 external system failure 不进入该提交质量分母：必须重跑同一 image 的完整 Manual/Semi 配对一次，且保持原条件、冻结版本和 worker-image 隔离；无法完成完整配对重跑时，整对行政删失。行政删失不是零值，也不得只删去某一条件的不利结果。

图片–条件层：

\[
\bar U_{t,c}
=
\frac{1}{2}\sum_{u\in c}U_{t,u}.
\]

图片内差：

\[
D_t=\bar U_{t,Semi}-\bar U_{t,Manual}.
\]

这是主要 image-level paired quality estimand。

`pair_id` 只用于随机化平衡、事故重跑和 provenance，不是正式独立统计单位。
每图预先冻结两个 pair；pair-level 重跑结束后仍映射回原 image，两个 pair 合并成唯一
image-level outcome。主要推断以 image 为单位，并按 building/image 及重复 worker 结构采用冻结的聚类方法。

每个 T1 条件及其配对结果同时报告原始提交/配对数、worker-caused structural failure 数、external incident 重跑数、行政删失数和原因。所有这些处理在结果不可见时冻结，不能根据质量差异重分类。

## 11.5 Secondary outcomes

```text
structurally valid rate
valid-only GT IoU
pairwise agreement
worst individual GT quality
blind trust
correction failure
over-correction
Model Issue recognition
```

两人没有天然多数，因此除非预先冻结双标注融合算法，否则不把“两人聚合 GT IoU”作为正式主结果。

## 11.6 Active time

使用完整 owner-valid active time。

不进行：

- 固定减去估算的 Model Issue 时间；
- 给 Manual 增加无意义对称表单。

## 11.7 统计层级

1. 结构有效与交付质量非劣；
2. active-time；
3. mode×risk_assist；
4. 行为机制。

---

# 12 V1：共享容量条件下的完整政策试验

## 12.1 试验臂

```text
Strong Global
vs
Full-Integrated
```

主要使用 Manual。

## 12.2 Block 级共享容量合同

每个 block 前冻结：

```text
availability_snapshot
worker_total_capacity
global_quota_per_worker
full_quota_per_worker
candidate_roster
offer_timeout
completion_timeout
max_offer_attempts
replacement_rule
invalid_submission_replacement_rule
candidate_exhaustion_rule
```

## 12.3 两套独立容量账本

```text
capacity_global[u]
capacity_full[u]
```

主分析不允许跨臂借用。

两臂必须共用：

```text
offer timeout
completion timeout
maximum offer attempts
decline/no-response replacement
invalid submission replacement
candidate exhaustion terminal rule
```

唯一差异是推荐排序。

## 12.4 调度证据

记录：

```text
block_id
policy_arm
candidate_set_at_decision
availability_snapshot_id
policy_recommended_worker
recommendation_rank
offered_worker
offer_sequence
accepted_worker
completed_worker
replacement_reason
timeout
capacity_before
capacity_remaining
candidate_exhausted
```

区分：

```text
recommended_not_offered
offered_declined
accepted_not_completed
completed_invalid
completed_valid
```

## 12.5 动态追加

初始与追加规则在两臂完全相同。

可冻结候选：

```text
k_initial = 2
standard_cap = 4
exceptional_cap = 5
```

实际数值由 C1/C2 replay 与功效/预算模拟冻结。

## 12.6 GT-blind 聚合

对截至当前的合法提交：

1. 将有冻结证据的 external system failure 移入重跑或行政删失处置，不作为工人或政策质量证据；
2. 将 worker-caused structural failure 记录为 worker failure event，不进入合法聚合候选；
3. 使用冻结几何相似度寻找最大内部一致簇；
4. 判断 largest cluster、second cluster、medoid margin 和结构有效性；
5. resolved 时选择主簇 medoid；
6. medoid tie 使用相同 Global 基础分和冻结随机规则；
7. 稳定多峰不强行输出；
8. 到上限仍不稳定则 unresolved。

## 12.7 运行中间状态与最终政策终态

```text
external_system_failure_pending_disposition
```

最终政策终态仅为：

```text
resolved
unresolved
severe_failure
```

### resolved

产生合法 GT-blind 输出 \(O_t^\pi\)。

### unresolved

存在合法提交，但未形成稳定单一输出。

### severe_failure

到上限仍没有可交付合法输出。

### external_system_failure_pending_disposition

外部事故确认后不直接成为可比较的政策终态：按第 3.5 节在盲态下同臂、同冻结版本、对称预留容量重跑一次；不满足任一条件则行政删失。重跑不得跨臂借容量、不得使用不同冻结版本，也不得由 V1 结果触发。

## 12.8 V1 outcomes

### 非交付指标

\[
D_t^\pi
=
I(unresolved\ or\ severe\ failure).
\]

### Severe failure

\[
H_t^\pi
=
I(severe\ failure).
\]

### Resolved-only quality

\[
Q_t^\pi=IoU(O_t^\pi,G_t).
\]

### 交付调整质量

\[
U_t^\pi
=
I(resolved)\times IoU(O_t^\pi,G_t).
\]

unresolved/severe failure 的 \(U_t^\pi=0\)，表示没有交付正式布局，不表示真实几何 IoU 必然为 0。

candidate exhaustion、替补规则失败和容量耗尽属于 policy-caused failure：保留在原政策臂 ITT，policy_failure=1；若任务终态为 unresolved 或 severe failure，则交付调整质量为 0。worker invalid submission 作为 worker failure event 保留；若按冻结替补后任务 resolved，不把最终任务交付调整质量改写为 0。external system failure 的成功重跑以重跑任务保留在原臂 ITT；无法合规重跑的行政删失不进入质量分母，但必须单列原始、重跑、删失和事故原因的两臂分布。

严格集合口径为：randomized set 包含全部随机化任务；primary modified-ITT（mITT）排除
预注册且臂盲确认的 external administrative censor；unresolved、severe failure 和
policy-caused failure 仍留在原臂 mITT，交付调整质量为 0。每臂同时报告 randomized、
rerun、administrative censor、mITT、resolved、unresolved 与 severe 数量。

## 12.9 检验层级

1. severe failure 不劣；
2. unresolved＋severe failure 不劣；
3. 交付调整质量；
4. resolved-only output quality；
5. \(k_{used}\)、active time 和完成时间；
6. policy×risk_route interaction。

## 12.10 事后审查

事后人工审查只用于：

- 解释 unresolved；
- 识别 GT 冲突；
- 形成反例；
- 判断 OOS。

不能用人工修订后的输出替换政策输出重新计算 V1 主效应。

也不得在查看 T1/V1 结果后把 worker 或 policy failure 重分类为 external system failure，或选择性重跑某一臂。事故证据、分类时间和重跑/删失决定是独立审计对象。

---

# 13 试验分布与生产标准化

## 13.1 分层结果

分别报告：

\[
V_{\pi,o},\qquad V_{\pi,s}.
\]

## 13.2 50:50 设计平均

\[
V_\pi^{design}
=
0.5V_{\pi,o}+0.5V_{\pi,s}.
\]

只能解释为 balanced experimental mixture。

## 13.3 生产标准化

若目标生产池比例为 \(p_o,p_s\)：

\[
V_\pi^{prod}
=
p_oV_{\pi,o}+p_sV_{\pi,s}.
\]

比例来自独立自然任务池，不从 50:50 试验样本估计。

上式只直接适用于 delivery-adjusted quality、non-delivery/severe rate 和平均成本等
无条件指标。resolved-only quality 必须按分子与分母标准化：

\[
Q_{\pi,\mathrm{resolved}}^{prod}
=
\frac{p_o r_o q_o+p_s r_s q_s}{p_o r_o+p_s r_s},
\]

其中 \(r_o,r_s\) 为各层 resolved rate，不能机械加权两个条件性均值。

若没有唯一比例，报告：

```text
80:20
60:40
50:50
30:70
```

情景分析。

---

# 14 V2：外部支持与安全退化审计

## 14.1 目的

不再次比较 Global/Full 因果效应，而检验：

- profile 是否支持；
- fallback 是否正确；
- supported subset 是否低风险；
- unsupported subset 是否富集失败；
- 是否存在 false-safe。

## 14.2 指标

```text
supported coverage
risk among supported
unsupported failure enrichment
false-safe rate
catastrophic supported failure
coverage–risk curve
refresh_required rate
```

高 fallback 本身不等于成功。

---

# 15 统计分析与功效

## 15.1 C1 后模拟 C2-B

模拟：

```text
每人任务数
共同 anchor 数
多样化 bridge 数
unique image 数
worker–task graph
B_u interval width
routing activation rate
fallback rate
```

决定 C2-B 的最终结构。

## 15.2 T1 功效

模拟：

- worker/image/building 方差；
- structurally valid rate；
- delivery-adjusted quality；
- Manual/Semi correlation；
- active-time missingness；
- risk interaction。

## 15.3 V1 功效

模拟：

- profile activation；
- policy divergence；
- capacity；
- refusal/timeout；
- dynamic k；
- unresolved；
- delivery-adjusted quality；
- policy×risk interaction。

## 15.4 Cross-fitted replay

按 image/base_task 划 fold。

评价 fold不得参与：

```text
Global selection
risk feature selection
weight selection
support threshold
fallback
stopping
```

Replay 用于开发、消融和功效，不替代前瞻 V1。

## 15.5 多重终点层级

### T1 确认性

1. 结构有效与交付质量非劣；
2. active time；
3. risk interaction。

### V1 确认性

1. severe/unresolved 安全门；
2. delivery-adjusted policy quality；
3. budget；
4. risk interaction。

### RQ2

以预测关联、效应量和支持为主。

### V2

外部审计。

---

# 16 结果章节结构

## 16.1 数据完整性与参考组成

报告：

```text
公开原始 GT 数量
极少量纠错 GT 数量
pending/OOS 数量
各 estimand eligible 数量
```

## 16.2 P1 的诊断与预测价值

报告：

- P1→C1；
- P1→C2-B；
- P1→T1；
- failure-family discrepancy workers。

## 16.3 C1 三轨工人状态

报告：

- task-adjusted GT quality；
- LOO；
- structural failure；
- 三者相关与分歧。

## 16.4 C2 风险韧性与支持

报告：

- 群体 stress effect；
- 个体收缩斜率；
- C2-A-RP 补测；
- eligible/uncertain/fallback。

## 16.5 T1

报告：

- structurally valid rate；
- delivery-adjusted quality；
- valid-only GT IoU；
- active time；
- mode×risk_assist；
- blind trust/correction。

## 16.6 V1

报告：

- policy activation/divergence；
- scheduling flow；
- resolved/unresolved/severe；
- delivery-adjusted quality；
- resolved-only quality；
- k/time；
- policy×risk_route。

## 16.7 V2

报告 coverage–risk 与 false-safe。

---

# 17 讨论

## 17.1 P1 为何不仅是准入

讨论高信息挑战对后续自然任务行为的预测价值，以及 admission 后 range restriction。

## 17.2 外部正确性、同行一致性和结构有效性的差异

解释为什么：

```text
高 LOO 不一定高 GT
高 GT 不一定高同行一致性
valid-only IoU 会忽略结构失败
```

## 17.3 条件画像的价值与边界

Full 的价值不在于所有任务都个体化，而在于：

```text
有支持时有限调整
无支持时明确 fallback
```

## 17.4 平衡试验与生产分布

解释 50:50 设计用于识别交互，生产结论需标准化。

## 17.5 单一 operational reference 的协议性质

说明本文只保留一个 operational reference，但不把该协议性选择夸大为不可争议的客观真理。

## 17.6 共享工人池中的政策干扰

讨论对称 quota 和独立容量账本如何定义本文的目标部署制度。

## 17.7 局限

- 23 名已通过 PreScreen 的固定工人池；
- 条件画像支持有限；
- P1 admission 造成范围限制；
- 外部域 V2 样本有限；
- 部分任务最终 unresolved；
- Full 的增量依赖任务侧 risk activation 的准确性。

---

# 18 结论

本文建立了一条从高信息 PreScreen 到前瞻路由验证的完整证据链。P1 不仅筛选工人，也形成后续行为的预测因子；C1 将任务难度校正后的 GT 正确性、LOO 同行一致性和结构性失败分离；C2 依据 C1 结果确定共同桥接和精度补测规模，并通过层级收缩与支持门槛冻结风险韧性；T1 检验 Semi-Auto 在不同模型风险下的质量与效率；V1 则在严格控制共享容量、offer、替补、动态冗余和聚合终态后，比较 Full-Integrated 与强 Global。

论文的核心主张不是个体化必然优于全局策略，而是：

> 高信息诊断可以产生具有预测价值的条件假设；当这些假设在独立 Calibration 中得到支持并且任务侧可被可靠激活时，它们能够形成可审计的条件路由；当支持不足时，系统应明确退化为强 Global，而不是强行使用不稳定画像。

---

# 附录规划

## Appendix A：Reference registry

- 公开原始 GT；
- 极少量纠错 GT；
- blind preliminary adjudication；
- submission-informed revision。

## Appendix B：Geometry LOO

- similarity；
- medoid；
- margin；
- multimodality；
- structural failure attribution。

## Appendix C：P1 predictive evidence

- failure-family；
- P1→C1/C2/T1；
- range restriction；
- support。

## Appendix D：C2 design simulation

- common anchor；
- diverse bridge；
- C2-A-RP；
- worker–task graph。

## Appendix E：Global/Full policy specification

- eligibility；
- score；
- support；
- fallback；
- weights；
- activation。

## Appendix F：V1 scheduling state machine

- availability；
- quota；
- offer；
- timeout；
- replacement；
- capacity；
- exhaustion。

## Appendix G：V1 aggregation and terminal state

- valid submission；
- largest cluster；
- medoid；
- resolved；
- unresolved；
- severe/system failure。

## Appendix H：Statistical analysis plan

- T1；
- V1；
- production standardization；
- replay；
- power simulation。

## Appendix I：Machine-readable evidence schema

至少包括：

```text
task/reference
worker state
LOO
risk
assignment
offer
capacity
response
aggregation
terminal outcome
analysis inclusion
freeze version
```

---

# 新旧内容边界

## 以新方案为主并完整保留

- C1 决定 C2-B 数量和结构；
- common anchor＋diverse bridge；
- 层级收缩风险韧性；
- C2-A-RP 精度自适应补测；
- task-adjusted 强 Global；
- Full-Integrated；
- HoHoNet LHFeat 与结构风险；
- T1 delivery-adjusted quality；
- V1 完整政策输出；
- V1 共享容量调度合同；
- 50:50 与生产标准化；
- V2 coverage–risk。

## 从旧提纲中仅移植的有效模块

- Geometry LOO 独立性；
- P1 的准入、诊断和预测价值；
- 双链路；
- estimand-specific inclusion；
- 四类 evidence 和三类 consensus；
- 三状态 task-tag；
- Scope/OOS 与 undercoverage 分离；
- issue recognition 与 correction 分离；
- 信息时序；
- image-level cross-fitted replay；
- support/fallback/unresolved。

## 明确废弃的旧内容

- 旧 C2 reserve-only 合同；
- 旧 T1/V1 固定规模和流程；
- 只按 LOO 构造 Global；
- 多参考 GT；
- 高维 worker×scene 矩阵；
- P1 永久只做 shadow；
- 专家作为默认在线 fallback；
- 以离线 replay 替代前瞻 V1；
- 旧的动态冗余固定参数；
- 其他与当前新主线冲突的旧协议。

## 追加：C1 variable-k、滚动招募与 Stage 3 冻结合同

Stage 1=Pilot/PreScreen（P1），Stage 2=Calibration（C1、C2-B、C2-A-RP），Stage 3=Main（T1、V1）；Stage 3 不得提前启动。正式 C1 证据仅限 `original_assignment`、SHA 绑定的 `authorized_replacement_assignment`、预注册的 `late_entry_calibration_assignment` 和其 canonical submission；`outside_assignment_submission` 仅保留 raw、exposure 与 process-integrity 审计，永不进入 primary GT、peer、LOO、structural 或 timing。

W014 保留 raw evidence 但永久排除正式 estimand；W034 的 capability 为 original 与 17 条授权任务并集，W001 为 original 与 3 条授权任务并集。W034 的 B-004/B-022 属 outside submission；普通 outside 不得因 generic exception 进入正式池。任务支持为 task-condition-estimand-specific 的变量 k，不以全局 k=5 替代；peer 先形成 task-level 指标、再对 task 等权汇总，pairwise edge 数不增加统计权重，并报告 cluster absolute support、share 与 normalized margin。

W034 的 17 条任务仅在 owner-valid active-time sentinel 通过后提供 timing evidence，且不得回填旧缺失日志。rolling enrollment 默认 `activated=false`；若在 Stage 3 前激活，新人必须通过同版本 P1 并使用冻结 workload template，作为 late entry 而非 replacement，最终同时报告 original-only 与 pooled sensitivity。Stage 3 前一次性冻结 pooled profile、权重、阈值、fallback 与 Validation roster，之后禁止增补 worker 或修改这些对象。学习效应仅保留顺序、版本和 provenance 描述，不建立复杂主模型。

Strong Global 在冻结的 administratively eligible、Q_GT-estimable cohort 上以 `S_G=z(Q_GT_EB)` 排序；LCB 仅用于 safety gate 和 sensitivity。Structural 同时报 raw、EB 与区间；Full/V1 的正式 manifest 必须完整绑定 component、support、threshold、weight、fallback、输入 SHA 和 formal minimum worker/cluster rule，缺失即 fail closed，GT-blind aggregation 不读取政策质量分数。
# SUPERSEDED：历史设计提纲

> 当前唯一规范性方法真源为 `PAPER_A_METHOD_CONTRACT_CURRENT.json`（`paper_a_method_20260730_v4`；SHA-256 `fcf264fe1ef131da4df393f50faae4b364c5779a5df0931957e7275713036144`）。本文件不得再作为设计真源。
