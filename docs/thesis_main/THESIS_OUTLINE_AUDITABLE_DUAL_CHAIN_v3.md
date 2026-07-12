# Paper A 正式论文提纲与写作合同 v3

> 版本日期：2026-07-12
> 状态：正式写作主轴与章节审计合同；不是实际 manuscript 真源。
> 边界：本文件不回写历史预注册、`ROUND_BASED_EXECUTION_PROTOCOL_v1.md`、`ROUND_BASED_ASSIGNMENT_SOP_v1.md`、P1 admission、C1/C2 assignment、routing、统计执行参数或任何原始工件。当前 Overleaf 正文尚未按本提纲迁移。

实际 manuscript 的 LaTeX `main.tex + sections/*.tex` 是正文真源；本 Markdown 是章节与主张审计合同；同目录 `.tex` 只是 standalone LaTeX outline prototype，不可直接代替或输入当前 manuscript。展示符号另见 `WORKER_PROFILE_THESIS_DISPLAY_CONTRACT_v1.md`。

## 0. 核心判断与论文主轴

Paper A 的核心不是某个模型、几何工具或单一加权分数，而是一条在 Validation 前可冻结、可审计、可复核的证据链：

```text
协议证据
  -> evidence validity gate
  -> Calibration-only protocol reliability R_u
     + P1-informed multi-dimensional diagnostic profile D_u
  -> C2 frozen worker state
  -> predictive validity
  -> Random / Calibration-only Global / Full routing evaluation
```

正式执行主线固定为：

```text
Pilot -> PreScreen -> Calibration -> Main(Test + Validation)
P1 -> C1 -> C2 -> T1 -> V1
```

论文不得把 P1 画像写成正式 routing profile，不得把 V1 结果回流 C2，不得将模型重训练、Bi-Layout 改造、A-line Manhattan 工具、自动 OOS 模型、worker-facing Manhattan correction 或“数据集重标注模型”写成 Paper A 一级贡献。

## 1. 贡献层级、边界与禁止主张

### 1.1 一级贡献

1. 阶段化、轮次化、带 provenance 和 validity gate 的半自动全景布局标注协议。
2. 双链路 worker modeling：Calibration-only protocol reliability `R_u`，以及 P1-informed 多维诊断画像 `D_u`。
3. 在 Validation 前冻结 worker state 后进行的预算感知路由评价。

### 1.2 二级创新

- support-aware 场景特异可靠度与 support 不足时的 Global fallback；
- 加权共识消融；
- failure-family / counterexample bank；
- P1→C1/C2/Main 的 predictive validity；
- active-time integrity audit。

### 1.3 明确排除

以下内容只能在讨论、附录或未来工作中出现，不能作为 Paper A 主实验或一级贡献：模型重训练、Bi-Layout 模型改造、A-line Manhattan 工具、自动 OOS 模型、worker-facing Manhattan correction、数据集重标注模型论文。若正文引用这些材料，必须标为支线、post-hoc、audit-only 或 deferred。

## 2. 研究问题合同

### 2.1 RQ1：效率

**问题：**半自动初始化是否降低 owner-valid exact active time，同时不以低质量、盲信或异常低编辑为代价？

**证据与用途：**exact annotation-level owner-valid browser log 是 primary；known-only 但完整性可疑 session、task-level log 和 `lead_time` 是 sensitivity/audit；`unknown_annotation` 不分配给任务进入 primary；parent-derived timing 仅 forensic audit。必须报告 primary exact coverage、missing/fallback count、script version、condition-specific time、quality-adjusted interpretation，以及 fast-low-quality / fast-blind-trust 检查。

**禁止主张：**active-time 不是 worker quality 本身；更快不能直接解释为更可靠；不得把 `lead_time` 静默混入 primary；system collection bug 不得惩罚 worker process reliability。

### 2.2 RQ2：质量、纠错与行为影响

**问题：**半自动初始化是否影响最终几何质量、IAAt/consistency、issue recognition、geometry correction、blind trust、undercoverage 和 failure-family 分布？

**证据与用途：**最终几何、任务内一致性、semi correction、coverage/full-room compliance、failure-family 是主证据；加权共识只作辅助消融；counterexample 只能作为经过 expert review 的解释性证据。

**禁止主张：**选择 `model_issue` 只能证明 issue recognition，不等于完成 geometry correction；undercoverage 不属于 OOS；process issue 不自动变成 geometry failure；加权共识不得成为主干预或唯一质量证据。

### 2.3 RQ3：冻结 worker state 的效度与路由价值

RQ3 是第三个一级研究问题，下设 RQ3a 与 RQ3b。`RQ3a predictive validity` 成立不等于 `RQ3b routing utility` 成立；二者使用不同的 evaluation unit、gate 和 estimand。

#### 2.3.1 RQ3a：画像效度

**问题：**经过 independence/process-validity gate 的 P1-informed diagnostic evidence 是否能解释或预测独立 C1/C2/Main 行为？

**证据与用途：**P1 capability 只有通过 independence gate 才能进入预测变量；`confirmed non-independent` 不进入 capability，`suspected` 保留 pending；独立 C1/C2/Main 行为是跨阶段验证目标。

**禁止主张：**P1 不能自证 predictive validity；P1 不能生成正式 `R_u`；不能把 confirmed non-independent 记录自动转成 geometry failure。

#### 2.3.2 RQ3b：路由效用

**问题：**在固定预算下，C2 冻结后的 Full worker state 是否优于 Random 与 Calibration-only Global？

**证据与用途：**Random / Global / Full 的主比较来自 `Calibration_manual` offline replay；V1 只评价已冻结 policy 的部署表现、fallback、activation、stop 和审计结果，不作为重新调参或主因果比较场。场景特异可靠度仅在 support 达标时启用，否则退化为 Global。

**禁止主张：**不得用 V1 临时并跑未注册策略补主比较；不得以 V1 结果反推 C2；不得将场景-specific 结果推广到 support 不足的场景。

## 3. 完整论文章节结构

每个节都必须按“回答什么问题—使用什么证据—primary—sensitivity/audit—禁止主张”五项写作卡片落笔。下列内容是正式章节边界，不是对旧稿的追加说明。

### 第1章 引言

#### 1.1 问题背景与现实约束

回答：为什么全景布局标注同时需要效率、质量和审计性。证据：任务成本、模型初始化、worker 行为和数据 provenance 的问题定义。Primary：研究动机和问题边界。Sensitivity/audit：工程背景和数据收集限制。禁止把模型重训练或 Manhattan 工具写成问题定义。

#### 1.2 研究缺口与本文路线

回答：现有工作为何不能同时保证阶段隔离、worker state 冻结和预算路由可比性。证据：相关工作对比和协议缺口。Primary：协议证据链。Sensitivity/audit：历史方案和失败案例。禁止声称已有论文正文已经完成迁移。

#### 1.3 研究问题与贡献

回答：三个一级 RQ 及其 RQ3a/RQ3b 子问题如何对应后续章节。证据：RQ1/RQ2/RQ3 合同和贡献层级。Primary：三项一级贡献。Sensitivity/audit：二级创新。禁止将 weighted consensus、Manhattan、重训练升级为一级贡献。

### 第2章 相关工作

#### 2.1 全景布局估计与布局标注

回答：本文测量对象与已有 layout annotation 工作的关系。证据：文献与任务定义。Primary：定位 Paper A。Sensitivity/audit：指标兼容性讨论。禁止把 A-line 工具当作本文主方法。

#### 2.2 模型辅助标注与 automation bias

回答：为什么 blind trust、issue recognition、correction 必须分开。证据：相关 bias 与 assisted annotation 文献。Primary：RQ2 概念基础。Sensitivity/audit：model_issue 标签解释。禁止用 model_issue 选择替代几何纠错证据。

#### 2.3 众包可靠度与 worker modeling

回答：为什么要拆分 protocol reliability 与 diagnostic profile。证据：可靠度、worker profiling、consensus 文献。Primary：双链路概念定位。Sensitivity/audit：weighted consensus。禁止把 P1 或 semi 直接写成 `R_u`。

#### 2.4 自适应冗余、路由与预算评价

回答：为什么 Random/Global/Full 必须在固定预算和离线 replay 中比较。证据：routing 和 sequential redundancy 文献。Primary：RQ3b 方法学定位。Sensitivity/audit：V1 shadow/deployment evidence。禁止以 V1 单独承担主比较。

#### 2.5 Provenance、完整性与可审计协议

回答：为什么 annotation independence、scope、timing 和 final-gold provenance 是测量前提。证据：数据治理与审计链。Primary：evidence validity gate。Sensitivity/audit：post-closeout correction。禁止把缺失 evidence 当成功。

### 第3章 研究协议与数据生命周期

#### 3.1 阶段、轮次与冻结点

回答：Pilot/P1/C1/C2/T1/V1 各自做什么、何时冻结什么。证据：protocol 和 assignment SOP。Primary：四阶段主线与 P1→C2→T1/V1 边界。Sensitivity/audit：extension/replication cohort。禁止修改 protocol freeze。

#### 3.2 任务池、条件、worker 与数据流

回答：各 pool、condition、worker assignment 如何隔离。证据：manifest、task pool 和 provenance。Primary：阶段—数据—允许用途矩阵。Sensitivity/audit：弃用/降级路径。禁止改变 assignment 或 routing。

#### 3.3 Scope、reference 与 final-gold provenance

回答：哪些任务可以进入 hard geometry、scope 或 OOS evidence。证据：scope 响应、hard-single/hard-multi/soft ambiguous reference、final-gold path/SHA。Primary：reference-gated 指标资格。Sensitivity/audit：soft ambiguous 与 unavailable。禁止将单一 reference 强行视为所有任务的唯一真值。

#### 3.4 Active-time identity 与时间降级

回答：什么时间证据可进入 RQ1 primary。证据：owner-valid exact annotation-level browser log、script version、source identity 和 fallback 审计。Primary：exact active time。Sensitivity/audit：known-only session、task-level、lead_time、parent-derived、unknown。禁止 system collection issue 记为 worker process failure。

#### 3.5 Evidence validity and post-closeout integrity gate

回答：哪些 evidence 可以用于哪条链路。证据：artifact path、SHA、rule version、inclusion flags 和 validity 状态。

Gate 必须覆盖：

- annotation independence：`independent`、`confirmed non-independent`、`suspected`、`not evaluable`；
- owner-valid active-time identity；
- scope/final-gold provenance；
- hard-single、hard-multi、soft ambiguous reference；
- `process_evaluable` 与 system collection issue 分离；
- dry-run risk proxy 不自动升级为 worker failure；
- undercoverage 先经 expert adjudication 才能进入正式 `V_u/U` evidence；
- missing evidence = `not_evaluable`，不是 success。

同一 submission 不使用一个总 validity flag 决定全部用途；必须逐一记录以下 estimand-specific flags：

```text
eligible_for_RQ1_time
eligible_for_R_u
eligible_for_G_u
eligible_for_S_u
eligible_for_C_u
eligible_for_V_u
eligible_for_P_u
eligible_for_predictive_validity
eligible_for_routing_feature
```

每个 flag 都要说明来源、inclusion/exclusion、missing/not_evaluable、primary/sensitivity/audit 和是否允许进入冻结画像。时间证据失效不自动使 geometry evidence 失效；scope 不可评价不自动使 process evidence 失效；process failure 不自动变成 geometry failure。Primary：进入各 estimand 的资格。Sensitivity/audit：pending、system issue、forensic rows。禁止静默过滤、自动补成功或跨链路复用未经 gate 的 evidence。

#### 3.6 Post-closeout 修正与不回写边界

回答：P1 closeout 后发现的 integrity evidence 如何处理。证据：只读 correction layer 和 audit report。Primary：P1 diagnostic validity。Sensitivity/audit：confirmed/suspected non-independence。禁止回写 admission、C1 assignment、reserve、routing、raw export、active-time server 或 userscript。

当前状态必须如实报告：P1 已完成并冻结；C1 已开始；P1 canonical annotations 的跨 worker parent-derived 非独立风险在 C1 开始后被发现；retrospective amendment 不回改 P1 admission、`w_max` 或已启动的 C1 assignment。相关 P1 capability evidence 排除出画像，但 non-independent rows 保留为 process-integrity evidence；正式 `R_u` 仍由独立 C1/C2 evidence 决定。P1 审计范围是所有 P1 worker 和所有 P1 canonical annotations。

C1 closeout 状态分为 `raw_pipeline_ready`、`provisional_sidecar_ready`、`thesis_facing_C1_closeout_ready`、`C2_decision_chain_ready`。在正式条件满足前，只允许 raw export、canonicalization、active-time audit、independence/process audit、provisional quality table 和 provisional sidecar；不得进行正式 C1 closeout pass、profile freeze、P1→C1 predictive-validity conclusion、C2 gap decision、C2 assignment materialization、Full profile readiness 或 routing freeze。

### 第4章 测量模型与双链路工人画像

#### 4.1 指标层级与方向

回答：工作量、质量、可靠度、风险率分别测什么。证据：指标字典。Primary：每个 estimand 的分子、分母、方向、support、gate、freeze stage。Sensitivity/audit：不可合并的 metric/direction/normalization。禁止把工作量或 raw failure rate 伪装成 reliability。

#### 4.2 Reference-gated geometry metric

回答：何时可以报告 P1 post-closeout geometry metric。证据：hard-single 单 reference、hard-multi max-over-reference、合法 pairing、范围、奇数点、歧义和 reference cardinality gate。Primary：满足兼容 gate 的连续、reference-gated `G_u` component；metric name、direction、normalization、stage/pool 和 support 必须记录。Sensitivity/audit：soft/ambiguous、不可配对和不兼容 metric。禁止未经预先冻结 threshold 把 geometry score 制造成二值 failure；禁止将几何分数作为 GT correctness 的唯一替代；A-line Manhattan 工具不进入主实验。

#### 4.3 链路 A：Calibration-only protocol reliability `R_u`

回答：worker 在正式 Calibration protocol 中的可靠度是多少。证据：仅 C1/C2 `Calibration_manual`，明确 stage/pool/condition/reference gate。Primary：`R_u`、LCB、CI、support 和 freeze。Sensitivity/audit：候选 `R_{u,s}`、precision gap。禁止使用 P1、Calibration_semi、C2b、Main/Test/Validation 回流。

#### 4.4 场景特异 `R_{u,s}` 与 Global fallback

回答：何时可使用场景特异 reliability。证据：C1/C2 calibration-only scene support、CI 和 activation rule。Primary：support 达标的 `R_{u,s}`；否则 Global `R_u`。Sensitivity/audit：activation/degeneration rate。禁止 support 不足时静默启用场景路由。

#### 4.5 链路 B：多维诊断画像 `D_u`

回答：worker 的可解释行为维度是什么。证据：经过 gate 的 P1-informed 与后续独立 evidence，按 stage/pool/condition 保留。主画像统一越高越好：

- `G_u`：geometry reliability；
- `S_u`：scope reliability；
- `C_u = 1 - semi correction failure rate`；
- `V_u = 1 - undercoverage failure rate`；
- `P_u = 1 - process failure rate`。

Raw risk-rate 单独保留：blind-trust/correction failure rate、undercoverage failure rate、process failure rate，均越低越好。Primary：支持充分的五维画像。Sensitivity/audit：component、subfamily、support 不足。禁止把失败率和 reliability 使用同一符号。

#### 4.6 Issue recognition 与 geometry correction

回答：worker 是否识别问题，和是否完成几何修正是否为同一能力。证据：`model_issue`、初始化/最终几何差异、reference-gated correction。Primary：有独立几何 evidence 时的 correction reliability。Sensitivity/audit：仅 issue-recognition rows。禁止把选择 `model_issue` 写成已完成 geometry correction。

#### 4.7 Failure-family 与 counterexample bank

回答：失败如何作为诊断链解释结果。证据：worker-task evidence table 与 expert-reviewed counterexample。一级 family 固定为：`geometry_quality_failure`、`scope_oos_failure`、`semi_correction_failure`、`undercoverage_failure`、`process_failure`。

同一 worker-task 可贡献多个 evidence signals；process issue 不自动变 geometry failure；undercoverage 不属于 OOS；system collection issue 不惩罚 process reliability；insufficient cell 保留但 `interpretation_allowed=false`；auto candidate 必须 expert review 后才是 final counterexample。Primary：family 长表和 support。Sensitivity/audit：subfamily 与反例库。禁止将 failure-family 等同于 `R_u` 或作为唯一核心贡献。

#### 4.8 Predictive-validity gate

回答：P1-informed profile 是否预测独立后续行为。证据：跨阶段独立 C1/C2/Main rows。Primary：通过 independence/process-validity gate 的 P1 capability。Sensitivity/audit：suspected rows、not evaluable rows。禁止 P1 自证、confirmed non-independent 入 capability 或把 predictive validity 当 routing utility。

### 第5章 路由策略与统计分析

#### 5.1 冻结 worker state 与 task risk

回答：哪些 state 在 C2 后固定。证据：`worker_state_snapshot_C2_final`、scene contract、risk rule manifest。Primary：冻结的 worker state、support、fallback、stop rule。Sensitivity/audit：activation/degeneration。禁止 V1 改 tier、`tau_d`、Score、`k0/kmax` 或 stop rule。

#### 5.2 Random、Global、Full

回答：三种 policy 如何定义。证据：同一 candidate pool、同一预算、同一 sequential rule。Primary：Random、Calibration-only Global、Full。Sensitivity/audit：diagnostic-feature-assisted Full 的 calibration-only comparison。禁止把 P1 profile 未经过 validity gate 就直接升格为正式 routing estimator。

#### 5.3 Offline replay 与 V1 隔离

回答：如何避免用真实标签造成 routing 比较泄漏。证据：`Calibration_manual` offline replay/shadow support 与 V1 frozen deployment logs。Primary：offline Random/Global/Full 比较。Sensitivity/audit：V1 deployment。禁止在 V1 临时并跑未注册 policy 来补主证据。

每个 evaluation unit 的真实 outcome 不能用于构造该 unit 的 routing decision。正式执行需在统计计划允许的方案中预先选择并记录 `leave-one-task-out`、`leave-one-image-out`、cross-fitting 或 worker-state estimation split/evaluation split 隔离；在方案未冻结前，不得声称 unbiased routing estimate。Full 使用的 `D_u` feature set、normalization、support threshold、fallback 和 sequential rule 必须在评价前冻结。不得看完 RQ3a 后挑选最有效 profile component，再在同一 evaluation unit 上宣称 RQ3b primary；post-hoc feature selection 只能是 exploratory sensitivity。

#### 5.4 RQ1/RQ2/RQ3 统计合同（含 RQ3a/RQ3b 子合同）

回答：三个一级 RQ 及 RQ3a/RQ3b 子合同的 data、estimand、统计方法和 downgrade rule 是什么。证据：STATISTICAL_ANALYSIS_PLAN_v1 与本提纲表 3。Primary：保持已冻结的配对、bootstrap、permutation、MDE 和 missingness 口径。Sensitivity/audit：task-level timing、K-S、weighted consensus、exploratory failure distribution。禁止改变冻结统计核心口径。

### 第6章 实验结果

#### 6.1 Evidence completeness 与 gate 流量

报告每个阶段/池的 evidence count、validity status、missing/fallback、path/SHA/rule version。Primary：纳入主分析的 exact rows。Sensitivity/audit：pending、not evaluable、system issue。禁止把未通过 gate 的行计为成功。

#### 6.2 RQ1 结果

报告 exact active-time primary、condition-specific estimate、coverage、fallback、quality-adjusted interpretation、fast-low-quality 与 fast-blind-trust 检查。Task-level/lead_time 只在 sensitivity/audit。

#### 6.3 RQ2 结果

报告 final geometry、IAAt/consistency、issue recognition、geometry correction、blind trust、undercoverage 和 failure family；weighted consensus 置于辅助消融。

#### 6.4 RQ3a 结果

报告 P1-informed D_u 对独立 C1/C2/Main 行为的跨阶段解释/预测，并按 support 和 validity 分层。

#### 6.5 RQ3b 结果

报告 Calibration_manual offline replay 的 Random/Global/Full 主比较，以及 V1 冻结 policy 的 deployment/audit；分别报告 fallback 与 activation。

#### 6.6 二级创新与审计结果

报告 support-aware fallback、weighted consensus、failure-family/subfamily、counterexample bank、active-time integrity audit，不将其提升为一级主轴。

### 第7章 讨论与局限

#### 7.1 主要发现与协议意义

只解释有 primary evidence 支持的结论。

#### 7.2 双链路边界与 predictive validity

讨论为什么 `R_u` 与 `D_u` 互补但不可互换。

#### 7.3 路由效用与部署解释

区分 offline replay 主比较、V1 deployment 和 shadow/audit。

#### 7.4 支持度、缺失与外部效度

讨论 support 不足、`not_evaluable`、fallback 和小样本限制。

#### 7.5 支线内容与未来工作

将模型重训练、Bi-Layout、Manhattan、自动 OOS 和 worker-facing correction 明确降级。

### 第8章 结论

#### 8.1 三个一级 RQ 及 RQ3a/RQ3b 子问题的证据边界

逐项回答 RQ1、RQ2、RQ3（分别报告 RQ3a 与 RQ3b），明确哪些是 primary、sensitivity 或 audit。

#### 8.2 一级贡献与不主张事项

只保留三项一级贡献，并重申协议与冻结边界未改变。

## 4. 正式图表合同

- **图1：** `Pilot → P1 → C1 → C2 → T1 → V1`，标出 admission、C1 provisional、C2 freeze、T1、V1 freeze/use 点。
- **图2：** evidence source → validity gate → `R_u/D_u` → frozen worker state → routing。
- **图3：** Random/Global/Full、Calibration replay、T1、V1 的数据隔离。
- **表1：** 阶段—数据—允许用途矩阵，至少覆盖 P1 manual/semi/OOS、C1/C2 manual、C1 semi、C2b、T1、V1、admission、`R_u`、diagnostic、routing、primary/sensitivity/audit。
- **表2：** 指标字典：名称、符号、趋势方向、分子/分母、来源、inclusion gate、support、primary/sensitivity/audit、freeze stage。
- **表3：** RQ—数据—估计量—统计方法—降级规则。
- **表4：** worker profile main matrix：`G_u/S_u/C_u/V_u/P_u`、raw risk rates、support、stage/pool、inclusion flags、freeze stage，以及 `T_u/U_u` legacy alias 映射。
- **表5：** failure-family/subfamily 长表、`n_observed`、`n_fail`、support status、`interpretation_allowed` 和 expert-review status。

## 5. 写作与字段兼容规则

论文符号是展示层合同，现有 artifact 字段是兼容层合同。`T_u/U_u` 等旧物理字段不得删除或静默改义；在论文中标注为 raw risk-rate/legacy alias，必要时通过显式换算展示 `C_u/V_u/P_u`。本次不声称已有 CSV、sidecar 或代码已经完成 schema migration。

所有 evidence rows 保留 artifact path、SHA-256、rule version、stage、pool、condition、reference status、validity status 与 inclusion flags。缺失维度为 `not_evaluable`；不能用空值推断 success。

## 6. 不回写和实现状态

- 不改变 Pilot、P1、C1、C2、T1、V1 的职责、输入、允许更新、禁止事项、冻结点和工件。
- 不把 P1 画像写入 C1/C2 assignment 或正式 routing profile。
- 不把 V1 结果回流 C2。
- 不修改历史预注册或原始工件。
- 当前中文 Overleaf `main.tex` 和 section 文件仅作为迁移源，尚未实际迁移到本结构。
- 旧稿逐节动作、保留内容和删除/降级决定见 `THESIS_MANUSCRIPT_MIGRATION_MAP_v1.md`。
