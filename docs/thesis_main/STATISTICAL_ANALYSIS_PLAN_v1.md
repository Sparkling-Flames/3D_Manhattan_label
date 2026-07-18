# Statistical Analysis Plan v1

## 0. 适用范围与替代声明

本文覆盖 P1/C1/C2、T1 和 V1 的正式分析。它以 `Paper_A_新版完整论文提纲_vFinal_Draft.md` 为设计真源，并替换旧的：

- Calibration_manual 上 Random/Global/Full 离线 replay 作为 RQ3 主比较；
- reserve-only C2；
- 单臂 Full deployment V1；
- Geometry LOO 单独决定正式 Global。

Replay 只用于开发、消融、设计和功效，不替代前瞻 V1。

## 1. 通用原则

### 1.1 阶段隔离

- P1：admission、高信息诊断和预测候选；
- C1：基础能力、任务调整、C2/T1/V1 设计参数；
- C2：共同桥接、层级收缩、精度补齐和最终冻结；
- T1：RQ1 Semi 条件效应；
- V1：RQ3 Strong Global vs Full-Integrated 前瞻政策效应。

T1/V1 结果不得修改任何 Calibration 参数、policy、risk、threshold、capacity、stop rule 或分析计划。

### 1.2 分析资格

active-time、GT quality、LOO、structural failure、predictive validity 和 routing feature 分别使用自己的 eligibility。不得使用单一 `valid` 过滤全部分析。

### 1.3 Failure 与 missingness

行级 failure attribution 与 pair/task analysis disposition 分开。

- worker-caused structural failure：保留在原 worker/condition/arm 的结构机会中。
- policy-caused failure：保留在原政策臂 ITT。
- external system failure：只有不可变证据、SHA、范围、事故窗口和结果可见前登记均验证通过才成立。
- not evaluable：证据不足或关系验证失败，不得静默改作 complete case。

每项分析同时报告原始、worker failure、policy failure、external rerun、行政删失、not-evaluable 和最终可分析数量及两臂/条件分布。

### 1.4 功效与 MDE

C1 closeout 后使用 worker/image/building 方差、结构有效率、active-time missingness、policy divergence、capacity 和 timeout 模拟 C2、T1、V1。MDE、gate 和样本量在 Main outcome 可见前冻结。

## 2. C1/C2 worker state 与预测证据

### 2.1 三轴状态

正式基础状态为：

```text
Q_u_GT_task_adjusted
R_u_LOO_compatible
F_u_struct
```

GT quality 使用交叉分类模型校正 worker 的任务组成，例如：

```text
Q_GT(t,u) = mu + worker_u + task_t + stage + error
```

报告 raw 中位数、task-adjusted estimate、CI/LCB、support 和 worker-task 图审计。

LOO 使用排除工人自身的 reference，报告 peer support、medoid margin、最大/第二簇、leave-one/two-out sensitivity 和 `stable/weak/multimodal/insufficient/metric_incompatible` 状态。LOO 是一致性审计和 tie-break，不替代外部 GT quality。

结构失败率为：

```text
worker-caused invalid geometry
/
structural-evaluable opportunities
```

external、reference failure、OOS 和未知归因不进入分母。

### 2.2 P1 predictive chain

P1 component 分别评估 `P1 -> C1`、`P1 -> C2-B` 和 `P1 -> T1`：

- Spearman/Kendall；
- worker bootstrap CI；
- 方向一致性；
- discrepancy worker；
- support；
- range restriction。

只有 C1 predictive validation 和 C2-B confirmation 均通过、support 达标且可由标注前特征激活的 component 才进入 Full。C2-A-RP 只补精度，不用于发现或挑选新 component。

### 2.3 C2-B simulation 与层级模型

C1 后模拟 common anchor、diverse bridge、unique task、每图 support、worker-task 图连通性和风险韧性区间宽度，以冻结 C2-B 设计。

风险韧性使用层级收缩模型：

```text
Q_GT(u,t)
= global_worker_u
+ route_risk_t
+ worker_specific_route_slope_u
+ stage
+ task_effect
+ error
```

输出收缩 estimate、interval、leave-one-task/block-out stability 和 routing eligibility。达到 C2-A-RP 上限仍不稳定时，该调整为 0 并 fallback Strong Global。

## 3. Strong Global 与 Full 选择合同

### 3.1 Strong Global

正式 Global 的 eligibility 基于 process/independence、GT support、结构失败 gate 和 task-adjusted GT quality floor。排序分数为：

```text
S_Global(u) = LCB(Q_u_GT_task_adjusted)
```

LOO 仅用于冻结 tie-break 或 compatibility 审计。

### 3.2 Full-Integrated

Full 在 Global 基线之上增加：

- `risk_route` 激活的收缩 worker risk-resilience；
- 经 P1→C1→C2-B 验证、且由标注前任务 family 唯一激活的 P1 component。

权重只在 image/base-task 分 fold 的 nested cross-fitting 中选择，使用小型离散集合、总调整上限和 one-standard-error 原则。评价 fold 不得参与 feature、weight、support、fallback 或 stopping 的选择。

### 3.3 政策差异可行性 gate

Main 前报告 activation、fallback、推荐首选不同率、初始 worker 集不同率、supported candidate count 和 capacity 后差异。若未达到预注册阈值，V1 不启动并报告政策不可区分；不得用 V1 outcome 放宽阈值。

## 4. RQ1：T1 Semi-Auto 条件效应

### 4.1 设计

```text
Manual / Semi
x
ordinary / stress_assist
```

每图 `2 Manual + 2 Semi`。分析 `pair_id` 恰好包含一条 Manual 和一条 Semi；同一图两条 pair 均进入 image-level 汇总。工人不得看到同图两种模式，worker 内平衡 mode/risk，并保存 assignment probability。

### 4.2 Primary outcomes

submission-level delivery-adjusted quality：

```text
U(t,u) = I(structurally_valid) * IoU(annotation, GT)
```

worker-caused structural failure 的 `U=0`。

每个 image-condition 的两条合法 submission 取均值：

```text
U_bar(t,c) = mean_u U(t,u,c)
D(t) = U_bar(t,Semi) - U_bar(t,Manual)
```

主要质量 estimand 是 image-level paired `D(t)`。两名工人没有天然多数；未冻结融合算法时，不把双标注聚合 IoU 作为主结果。

### 4.3 External pair resolver

若 pair 中任一行有合规 external incident：

- 未受影响行仍保持 `row_failure_attribution=none`；
- 完整 Manual/Semi pair 在原条件、原 freeze version 和 worker-image 隔离下最多重跑一次；
- resolver 使用合法 rerun pair 替代 original pair；
- 无法完整重跑时整对行政删失；
- 非法证据/关系则整对 `not_evaluable`。

行政删失不是零值，且不得只删除某一条件。所有决定在条件 outcome 可见前冻结。

### 4.4 推断层级

1. 结构有效率与 delivery-adjusted quality 的非劣/安全门；
2. owner-valid active time；
3. mode × `risk_assist` interaction；
4. blind trust、correction failure、over-correction、Model Issue recognition。

主推断尊重 image pairing，并用 worker/image/building 层级 bootstrap、permutation 或相应 mixed model；不得把 naive annotation-level 独立样本检验作为唯一主检验。

### 4.5 Active-time downgrade

Primary 只使用 owner-valid active time，不使用 Label Studio `lead_time`，不固定扣除估算的 Model Issue 时间。

若某 mode/risk cell 的 owner-valid coverage 未达到冻结阈值：

- active-time 从确认性降为 descriptive/sensitivity；
- 不影响质量与结构主分析；
- 报告 coverage、缺失模式和 downgrade 原因。

## 5. RQ2：P1 跨阶段预测效度

RQ2 以 worker-level 预测关联、效应量、方向一致性和支持为主，不把 exploratory family 结果升级为因果结论。

如果保留预先冻结的 paired counterexample subset，使用 image-paired permutation/bootstrap；反例类型分布使用 paired/multilevel 方法，不用普通 chi-square 作为唯一主检验。

支持不足、range restriction 或 multiple-testing 风险必须报告。未经 C1 和 C2-B 双重验证的 P1 component 保持 diagnostic-only。

## 6. RQ3：V1 前瞻政策试验

### 6.1 设计与 ITT

V1 在 task/block 层将任务随机分配至 Strong Global 或 Full-Integrated。原始随机化任务是 ITT 单位。

两臂共享 worker pool、候选 roster 和 availability snapshot，使用对称 worker quota 与独立容量账本。offer、timeout、replacement、candidate exhaustion、dynamic redundancy、GT-blind aggregation 完全相同；唯一差异是推荐排序。

### 6.2 Rerun resolver

external task 可在同 policy arm、同 freeze version、对称预留容量下最多重跑一次。必须关系验证 original/rerun task、reservation ID、reservation arm、sequence 和 capacity before/after。

- 合法 rerun outcome 替代 original outcome，但仍归原随机化臂 ITT；
- 无法合规 rerun 时行政删失，不进入质量分母；
- `external_system_failure_pending_disposition` 不能作为最终政策终态；
- policy-caused failure 保留原臂 ITT；
- worker invalid 后若按相同替补规则 resolved，不把最终任务质量改为 0。

### 6.3 Outcomes

最终终态为 `resolved`、`unresolved`、`severe_failure`。

主要指标：

```text
severe failure
unresolved + severe failure
delivery-adjusted quality
resolved-only GT quality
k_used
owner-valid active time
completion time
policy x risk_route interaction
```

delivery-adjusted quality：

```text
U_task = I(resolved) * IoU(policy_output, GT)
```

unresolved/severe failure 的 `U_task=0`，表示未交付正式布局，不声称真实几何 IoU 为零。

### 6.4 检验层级

1. severe failure 不劣；
2. unresolved + severe failure 不劣；
3. delivery-adjusted policy quality；
4. resolved-only output quality；
5. `k_used`、active time、completion time；
6. policy × `risk_route` interaction。

同时报告 recommendation、offer、accept、timeout、replacement、candidate exhaustion、worker failure、policy failure 和 capacity 流程。事后专家审查不得替换冻结政策输出。

## 7. 实验分布与生产标准化

ordinary/stress 分层报告后，计算：

```text
V_design = 0.5 * V_ordinary + 0.5 * V_stress
```

该结果只代表 50:50 balanced experimental mixture。

生产标准化使用独立自然任务池给出的 `p_ordinary` 和 `p_stress`：

```text
V_prod = p_ordinary * V_ordinary + p_stress * V_stress
```

不得从 50:50 试验样本估计生产比例。没有唯一比例时，报告预注册情景分析，例如 80:20、60:40、50:50 和 30:70。

## 8. Replay、缺失与稳健性

- Cross-fitted replay 用于 policy development、消融、C2/T1/V1 功效和可行性，不替代 V1。
- 报告 complete-case 与冻结 missingness sensitivity；行政删失不能编码为零。
- 对层级 bootstrap/permutation 固定 seed，并保存 fold、cluster unit、抽样次数和代码 commit。
- 对 worker pass-count 不足使用预注册 contingency：缩减 interaction/family 解释或停止 V1，而不是降低准入后宣称同等证据。
- 任何 schema drift、缺失 manifest SHA、active-time source mismatch 或事故证据失败均 fail closed。

## 9. 正式报告清单

正式表格必须至少包含：

- 各轮 planned/actual task、worker、submission；
- 三轴 worker state 与 support；
- C2-B 设计和 C2-A-RP 停止情况；
- P1 component validation/confirmation；
- Global/Full activation、fallback 和政策差异；
- T1 原始、rerun、删失、not-evaluable 和最终 pair；
- V1 两臂 ITT、终态、质量、容量、流程失败和 rerun；
- external incident 数量、原因和两臂/条件分布；
- 50:50 与生产标准化结果；
- 所有 downgrade、deviation、freeze version、manifest SHA 和 code commit。

不得虚构、插补或提前填写尚未产生的正式 C1/T1/V1 结果。
