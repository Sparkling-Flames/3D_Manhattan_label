# Paper A 论文提纲与写作合同 v5

版本日期：2026-07-16  
状态：正式提纲 v5；与当前 Overleaf 主文迁移合同配套；不表示正文、C1 closeout、C2 freeze 或 PDF 已完成。  
历史边界：保留 v3/v4 作为历史审计版本；本文件不回写历史预注册、protocol freeze、assignment、routing、统计计划、XML、数据、代码、测试或原始工件。

## 0. 论文定位与证据状态

Paper A 的定位是：**面向全景布局数据生产的、阶段化、可审计的自适应标注基础设施**。本文建立证据账本、worker state、task-condition map 和反例/挑战库的合同与评价路径，但不宣称四项资产已经全部生成或完成长期部署验证。

正式执行主线固定为：

```text
Pilot -> PreScreen -> Calibration -> Main(Test + Validation)
P1 -> C1 -> C2 -> T1 -> V1
```

Manual 与 Semi 的角色必须分开：Manual Calibration 估计相对模型无关的基础能力；Semi-Auto 审计模型介入后的 issue recognition、geometry correction、blind trust 和 over-correction。正式 (R_u) 只来自 eligible C1/C2 `Calibration_manual`；Semi evidence 只能形成经过 gate 的诊断 component，不回流 (R_u)。

当前实现状态：三状态 sidecar、seam-aware Geometry LOO 和 event-driven replay 已有代码/候选脚手架；正式 C1 closeout、formal worker state、RQ3a predictive artifact、RQ3b thesis-facing replay 结果仍为 pending。旧 majority 产物只能作为 legacy descriptive proxy。

## 1. 一级贡献、二级创新与边界

### 1.1 一级贡献

1. 阶段化、轮次化、带 provenance、validity gate、missingness 和 freeze boundary 的可审计标注协议。
2. 来源分离且支持度感知的 worker state：Manual 基础 (R_u)、Scope/process、model-version-bound Semi correction 与条件性 profile，并规定 fallback、refresh 和失效标志。
3. 只读取决策时已到达证据的时序化预算路由，以及 Random/Global/Full 的 image-level cross-fitted replay 评价。

### 1.2 二级创新

三状态 task-condition evidence、global/family-specific Semi correction feasibility、support-aware scene fallback、failure-family/counterexample bank、active-time integrity、weighted consensus ablation、worker-state bridge/refresh contract 均为二级或审计性创新。

### 1.3 禁止作为 Paper A 一级贡献

模型重训练、Bi-Layout 改造、A-line Manhattan 工具、自动 OOS 模型、worker-facing Manhattan correction、GT 全面重建和数据集重标注模型论文只进入讨论、附录或未来工作。

## 2. 研究问题

### 2.1 RQ1：效率

**回答什么问题：** 半自动初始化是否降低 owner-valid exact active time，同时不以低质量、blind trust 或异常低编辑为代价？  
**使用什么证据：** exact annotation-level browser log、最终质量、blind-trust/correction risk。  
**Primary：** annotation-level exact active-time。  
**Sensitivity / audit：** task-level log、lead_time、known-only 可疑 session、fallback、unknown annotation、parent-derived timing、fast-low-quality 与 fast-blind-trust。  
**禁止主张：** 更快自动等于更可靠；active-time 本身等于 worker quality。

### 2.2 RQ2：质量、纠错与行为影响

**回答什么问题：** Semi-Auto 是否影响最终几何质量、IAA/consistency、issue recognition、geometry correction、blind trust、undercoverage 与 failure-family 分布？  
**使用什么证据：** Manual/Semi 配对 task/image、三状态 Difficulty/Model Issue、最终 geometry、专家 adjudication 和 process evidence。  
**Primary：** SAP v1 已冻结的 Manual/Semi 质量、时间和行为终点。  
**Sensitivity / audit：** weighted consensus、balanced subsampling、failure-family、counterexample、global Semi profile feasibility。  
**禁止主张：** 选择 `model_issue` 等于完成几何纠错；加权共识替代主要终点。

### 2.3 RQ3：冻结 worker state 的效度与路由价值

RQ3 保持一个一级问题，下设 RQ3a 与 RQ3b。

#### 2.3.1 RQ3a：predictive association / validity

**回答什么问题：** 通过 independence/process-validity gate 的 P1-informed evidence 是否能解释或预测独立 C1/C2/Main 行为？  
**使用什么证据：** P1 geometry、P1 Semi correction/process warning 与独立后续 target。  
**Primary：** 小样本、跨阶段、支持度报告完整的 predictive association。  
**Sensitivity / audit：** Spearman/Kendall、worker bootstrap、directional consistency、discrepancy、missing/not_evaluable。  
**禁止主张：** P1 自证；confirmed non-independent 进入 capability；RQ3a 自动生成 routing profile。

#### 2.3.2 RQ3b：routing utility

**回答什么问题：** 固定预算下，C2 冻结的 Full 是否优于 Random 和 Calibration-only Global？  
**使用什么证据：** Calibration_manual image-level cross-fitted offline replay；V1 仅评价已冻结 policy 的部署审计。  
**Primary：** first-selected quality、budget efficiency、可用独立 reference 时的 final aggregate quality。  
**Sensitivity / audit：** arrival order、fixed random order、fallback、reference unavailable、(k_{used})、escalation rate 和 V1。  
**禁止主张：** 最终 crowd scene 回填首次路由；replay 外推为完整 worker pool 的无偏在线效果；V1 临时调参。

## 3. 正式章节结构与写作卡片

每个正式小节都必须回答五项：回答什么问题、使用什么证据、Primary、Sensitivity/audit、禁止主张。Markdown 直接打印五项；正文 LaTeX 将其保存为注释或用自然段表达。

### 第1章 引言

#### 1.1 数据生产背景与现实约束

问题：为什么全景布局生产同时需要效率、质量和审计性。证据：任务成本、模型初始化、worker 行为、provenance。Primary：问题定义。Sensitivity/audit：工程限制。禁止：把 Paper A 写成模型重训练论文。

#### 1.2 Manual/Semi 识别设计与研究缺口

问题：为什么 Manual ability 与 Semi correction ability 不能混为一谈。证据：同图双条件、automation bias 和 correction evidence。Primary：识别路线。Sensitivity/audit：条件差异与小样本限制。禁止：宣称已完成全面 Semi-specific routing。

#### 1.3 四项基础资产与方法路线

问题：论文输出如何沉淀为可审计、可复用和可失效的生产资产。证据：ledger、worker state、task-condition map、counterexample bank 合同。Primary：资产来源和冻结边界。Sensitivity/audit：future refresh/challenge layers。禁止：把 pending artifact 写成已生成资产。

#### 1.4 研究问题、贡献层级与研究边界

问题：RQ1/RQ2/RQ3 如何对应结果。证据：RQ 合同。Primary：三项一级贡献。Sensitivity/audit：二级创新。禁止：新增生命周期 RQ 或把 RQ3a/RQ3b 拆成一级 RQ。

### 第2章 相关工作

#### 2.1 全景布局估计与布局标注

问题：本文任务与布局标注文献的关系。证据：任务和几何表示文献。Primary：任务定位。Sensitivity/audit：metric compatibility。禁止：A-line Manhattan 成为主方法。

#### 2.2 模型辅助标注与 automation bias

问题：模型初始化如何同时影响速度、识别和纠错。证据：assisted annotation 与 automation bias 文献。Primary：RQ2 机制。Sensitivity/audit：blind trust/over-correction。禁止：少编辑等于高质量。

#### 2.3 众包可靠度、worker modeling 与共识

问题：为什么要拆分 (R_u)、诊断画像和 raw risk。证据：reliability、disagreement 和 worker-modeling 文献。Primary：双链路定位。Sensitivity/audit：weighted consensus。禁止：单一 confidence 是真值概率。

#### 2.4 自适应冗余、路由与预算评价

问题：为什么首次发放、追加、停止和冲突解决必须时序化。证据：sequential routing/stopping 文献。Primary：RQ3b。Sensitivity/audit：arrival order。禁止：固定 (k_0/k_{max}) 作为当前冻结事实。

#### 2.5 Provenance、数据审计与可复用生命周期

问题：为什么状态需要版本、适用域、support 和失效标志。证据：provenance、dataset audit、challenge set 文献。Primary：生命周期设计边界。Sensitivity/audit：future bridge/refresh。禁止：把未来维护机制写成当前实证结果。

### 第3章 研究协议、证据类型与数据生命周期

#### 3.1 阶段、轮次与冻结点

问题：谁在何时冻结什么。证据：正式 protocol/SOP。Primary：Pilot→P1→C1→C2→T1→V1 职责。Sensitivity/audit：当前 launched/valid 状态。禁止：回写历史 admission、assignment 或 freeze boundary。

#### 3.2 Manual/Semi 证据角色与四类证据

问题：不同 evidence 进入哪些 estimand。证据：Scope/OOS、Difficulty、Model Issue、Geometry 及 Manual/Semi pool。Primary：来源分离。Sensitivity/audit：历史 schema harmonization。禁止：用一套多数阈值承担三类 consensus。

#### 3.3 三类共识与任务条件图谱

问题：任务描述共识、评价参考共识和停止共识如何分开。证据：task outcome reference、LOO reference、online snapshot。Primary：三类用途。Sensitivity/audit：soft ambiguous/unresolved。禁止：共识 confidence 作为 truth probability。

#### 3.4 任务池、assignment 与 provenance

问题：task/image/condition/stage/pool 如何隔离。证据：manifest、assignment、artifact path/SHA/rule version。Primary：数据生命周期。Sensitivity/audit：system collection issue。禁止：将 planned、launched、valid 混写。

#### 3.5 Evidence validity and post-closeout integrity gate

问题：哪些 evidence 可进入哪个 estimand。证据：independence、owner-valid active-time、reference、scope、process、missingness。Primary：inclusion flags。Sensitivity/audit：forensic audit、not_evaluable。禁止：missing evidence = success；dry-run risk = worker failure。

#### 3.6 P1 retrospective integrity amendment 与当前 C1 状态

问题：历史 P1 如何审计而不改写执行。证据：P1 closeout audit、C1 launched/valid/completed status。Primary：保守状态说明。Sensitivity/audit：legacy bridge。禁止：把 C1 ongoing 写成 closeout 完成。

### 第4章 测量模型与双链路工人画像

#### 4.1 符号、方向与 estimand-specific inclusion

问题：哪些符号代表 reliability，哪些代表 raw risk。证据：artifact contract。Primary：(R_u)、(D_u)、CI/LCB/support。Sensitivity/audit：legacy aliases。禁止：混用 failure rate 与 reliability。

#### 4.2 三状态 task-tag 观测模型

问题：如何表示 positive、explicit negative、unasserted 和 not_evaluable。证据：(Y_{tus}in{+,-,0,NA})、(a/e/u/k)。Primary：三状态 evidence。Sensitivity/audit：LOO pivotality。禁止：未选中 = 反对；多数阈值 = 真值概率。

#### 4.3 Difficulty 分析合同

问题：Difficulty 如何表示 worker 报告阈值。证据：raw response、trivial harmonization、UI/instruction version。Primary：trivial/specific/multi-select 指标。Sensitivity/audit：组合分布。禁止：trivial = 客观无困难；建立“爱多选型 worker”分数。

#### 4.4 Model Issue 分析合同

问题：如何区分 issue recognition、correction、blind trust 和 over-correction。证据：raw issue、行为 harmonization、model artifact provenance。Primary：recognition/correction 分离。Sensitivity/audit：legacy schema。禁止：model_issue 选择 = correction success。

#### 4.5 三层 task-condition map 与 worker-scene profile

问题：客观条件、worker Difficulty 和 model-version failure 如何共存。证据：task condition、worker×task tag、task×model-version issue。Primary：global profile 与 support gate。Sensitivity/audit：broad/strict、family-specific、fallback。禁止：不同 worker 因 LOO 获得不同正式 scene task set；单图形成正式可靠度。

#### 4.6 Geometry LOO 与指标层级

问题：如何保持 reference 独立并处理 metric compatibility。证据：worker-excluded LOO、seam-aware candidate、stability sidecar。Primary：当前 (R_u) 的 `iou_to_consensus_loo`。Sensitivity/audit：seam-aware components、legacy medoid、3D 条件指标。禁止：convex-hull medoid = 完整 geometry truth；pending metric = 已有结果。

#### 4.7 (R_u)、(D_u)、support、版本与失效状态

问题：如何形成可复用但可失效的 state。证据：Calibration evidence、Semi diagnostic evidence、domain/model/UI/version/support。Primary：C2 freeze candidate。Sensitivity/audit：active/watch/refresh_required/suspended/re-admission 设计。禁止：P1 直接成为 routing profile；生产数据无限回流验证。

#### 4.8 Failure-family 与四层 counterexample bank

问题：如何解释平均指标掩盖的系统失败。证据：五个 failure families、candidate/adjudication/provenance。Primary：candidate 与 adjudicated case analysis。Sensitivity/audit：challenge/retraining pool。禁止：反例估计总体 prevalence、自动改 GT、自动进训练或同时用于画像和最终评价。

### 第5章 路由策略与统计分析

#### 5.1 C2 冻结 worker state 与 task-side risk

问题：哪些状态可进入 routing。证据：C2 state、LCB/support、task/model risk。Primary：Frozen state。Sensitivity/audit：cross-fitted shadow state。禁止：P1 后见之明直接路由。

#### 5.2 首次发放、后续追加与冲突解决

问题：响应到达后如何追加和解决冲突。证据：decision snapshot、event batch、arrival order。Primary：信息时序。Sensitivity/audit：排序置换。禁止：最终 crowd scene 回填首次路由。

#### 5.3 动态冗余、停止和专家成本

问题：何时 stop、continue、escalate 或 unresolved。证据：(k_{dispatch_initial})、(k_{min_for_stop})、standard_cap、escalation_cap、expert logs。Primary：C2 前候选 stop contract。Sensitivity/audit：(k_{used})、expert time/cost。禁止：singleton final acceptance；把专家当免费 fallback。

#### 5.4 Random、Global、Full 与数据隔离

问题：三种 policy 使用哪些信息。证据：Calibration replay、T1、V1 separation。Primary：Random/Global/Full。Sensitivity/audit：V1 deployment。禁止：V1 临时重调参或承担主因果比较。

#### 5.5 Image-level cross-fitted replay 与 RQ3b estimands

问题：如何避免 image leakage 和 annotation-row averaging。证据：同 image 同 fold、当时 evidence snapshot、实际候选集 (U_t)。Primary：task-level policy outcome。Sensitivity/audit：arrival order、reference unavailable。禁止：外推完整 worker pool 无偏在线效果。

#### 5.6 RQ1、RQ2、RQ3a、RQ3b 统计合同

问题：RQ、数据、estimand、方法和降级规则如何对应。证据：SAP v1 与 additive amendment。Primary：冻结统计口径。Sensitivity/audit：weighted consensus、failure-family、counterexample。禁止：用 v5 覆写 SAP v1。

### 第6章 实验结果

#### 6.1 Evidence completeness 与 validity-gate 流量

**回答什么问题：** 证据在各 validity gate 的流量是什么。  
**使用什么证据：** planned/received/valid/evaluable/not_evaluable/unresolved registry。  
**Primary：** 各 RQ denominator 的 inclusion flags。  
**Sensitivity / audit：** missing、fallback、system issue、unresolved 原因。  
**禁止主张：** 不把 23×18 计划机会写成正式独立样本量。

#### 6.2 RQ1：效率

**回答什么问题：** Semi 是否降低 owner-valid exact active time。  
**使用什么证据：** exact annotation-level log、condition、最终质量和风险。  
**Primary：** exact active-time 与 quality-adjusted interpretation。  
**Sensitivity / audit：** coverage、missing/fallback、fast-low-quality、fast-blind-trust。  
**禁止主张：** 更快直接等于更可靠。

#### 6.3 RQ2：质量、纠错与行为影响

**回答什么问题：** Semi 如何影响 quality、recognition、correction、blind trust、undercoverage 和 failure-family。  
**使用什么证据：** paired Manual/Semi task/image、最终 geometry、三状态 evidence 和 adjudication。  
**Primary：** SAP v1 冻结的质量、时间和行为终点。  
**Sensitivity / audit：** global Semi feasibility、weighted consensus、failure-family、counterexample。  
**禁止主张：** model issue 选择等于 correction success，或 weighted consensus 是主轴。

#### 6.4 RQ3a：画像 predictive association

**回答什么问题：** P1-informed evidence 是否解释独立后续行为。  
**使用什么证据：** 通过 independence/process-validity gate 的 predictor-target pair。  
**Primary：** support 足够的跨阶段 predictive association。  
**Sensitivity / audit：** bootstrap CI、directional consistency、discrepancy、missing/not_evaluable。  
**禁止主张：** P1 自证或把 RQ3a 自动升级为 routing profile。

#### 6.5 RQ3b：routing utility

**回答什么问题：** Full 是否在固定预算下优于 Random 和 Global。  
**使用什么证据：** image-level cross-fitted replay、实际 evidence snapshot、V1 deployment audit。  
**Primary：** first-selected quality、budget efficiency、可用 reference 时的 aggregate quality。  
**Sensitivity / audit：** fallback、escalation、arrival order、reference unavailable、k_used。  
**禁止主张：** replay 是完整 worker pool 的无偏在线效果，或 V1 可以临时调参。

#### 6.6 二级创新、failure-family 与 counterexample 审计

**回答什么问题：** failure-family 和 counterexample 如何解释平均结果。  
**使用什么证据：** 五个 failure families、candidate/adjudicated bank、provenance。  
**Primary：** 已审计的 candidate 与 adjudicated case。  
**Sensitivity / audit：** frozen challenge/regression、future relabel/retraining layer。  
**禁止主张：** 未冻结层级是结果；反例可估计总体 prevalence 或自动改 GT。

### 第7章 讨论与局限

#### 7.1 主要发现与基础设施意义

**回答什么问题：** Paper A 的方法学意义是什么。  
**使用什么证据：** RQ1/RQ2/RQ3 primary evidence 与 gate flow。  
**Primary：** 生产、证据和路由基础设施的贡献。  
**Sensitivity / audit：** Semi 小样本、support、专家成本。  
**禁止主张：** GT 全面重建、模型改造或长期在线部署已被验证。

#### 7.2 Manual/Semi 分工与小样本限制

**回答什么问题：** Manual 为主是否偏离半自动主线。  
**使用什么证据：** Manual/Semi 识别设计与 paired results。  
**Primary：** Manual 基础能力与 Semi correction audit 的分工。  
**Sensitivity / audit：** Semi global/family support、small-sample uncertainty。  
**禁止主张：** 414 行记录是 414 个独立 worker-level 样本。

#### 7.3 三状态 task-condition map 的测量局限

**回答什么问题：** task-condition map 何时有实际决策价值。  
**使用什么证据：** objective condition、worker Difficulty、task×model-version failure 与 quality/time/disagreement。  
**Primary：** 能改变追加、停止、fallback 或审计的条件。  
**Sensitivity / audit：** descriptive-only tags、富集偏差。  
**禁止主张：** worker 感知标签是客观 scene truth。

#### 7.4 Geometry LOO 与 metric compatibility

**回答什么问题：** Geometry LOO 和 metric compatibility 的边界是什么。  
**使用什么证据：** worker-excluded reference、stability sidecar、metric gate。  
**Primary：** current `iou_to_consensus_loo` contract。  
**Sensitivity / audit：** legacy medoid、seam-aware candidate、条件 2D/3D metric。  
**禁止主张：** convex-hull medoid 是完整 geometry truth，或 pending metric 已有结果。

#### 7.5 生命周期、refresh、missingness 与外部效度

**回答什么问题：** worker state 如何复用、更新和失效。  
**使用什么证据：** version/domain/model/support/validity fields。  
**Primary：** 当前 freeze 与 fallback 边界。  
**Sensitivity / audit：** active/watch/refresh_required/suspended/re_admission lifecycle contract。  
**禁止主张：** 当前论文已完成长期 refresh 或 domain-transfer 验证。

#### 7.6 Counterexample/challenge bank 与 Paper B 边界

**回答什么问题：** counterexample 如何连接后续 GT 修正和 Paper B。  
**使用什么证据：** 四层 bank、adjudication、split/provenance。  
**Primary：** candidate/adjudicated case analysis。  
**Sensitivity / audit：** challenge/regression 与 future relabel/retraining。  
**禁止主张：** 反例自动成为 GT、训练样本或总体错误率估计。

### 第8章 结论

#### 8.1 三个一级 RQ 的证据边界

**回答什么问题：** 三个一级 RQ 的安全结论是什么。  
**使用什么证据：** 各 RQ primary、sensitivity、audit、not_evaluable、unresolved。  
**Primary：** gated evidence。  
**Sensitivity / audit：** fallback、missing、support 和 unresolved。  
**禁止主张：** 超出实际 evidence 或历史协议。

#### 8.2 三项一级贡献

**回答什么问题：** 一级贡献如何收束。  
**使用什么证据：** 协议、worker state 和 replay contract。  
**Primary：** 协议、来源分离 state、时序预算路由。  
**Sensitivity / audit：** 三状态 map、Semi feasibility、failure/counterexample、refresh。  
**禁止主张：** 将二级创新写成一级贡献。

#### 8.3 不超出证据的结论

**回答什么问题：** 哪些内容必须保留为 pending 或 future。  
**使用什么证据：** C1/C2 status、implementation labels、C2b amendment boundary。  
**Primary：** 不超出证据的结论。  
**Sensitivity / audit：** planned/candidate/dry-run artifacts。  
**禁止主张：** 未生成 artifact、未冻结 C2b 或未编译 PDF 被写成完成。

## 4. 统一符号与方向合同

[
R_u=\text{Calibration-only protocol reliability},
\quad D_u=(G_u,S_u,C_u,V_u,P_u).
]

五维 (D_u) 均 higher-is-better；raw blind-trust/correction failure rate、undercoverage failure rate 和 process failure rate 单独保存且 lower-is-better：

[
C_u=1-\text{semi correction failure rate},\quad
V_u=1-\text{undercoverage failure rate},\quad
P_u=1-\text{process failure rate}.
]

不引入未定义的 (B_u/F_u/Q_u)。旧字段 alias 只能标为 legacy。

## 5. 主文图表与附录 machine-readable contracts

主文核心图：

1. Pilot→P1→C1→C2→T1→V1 与 freeze points；
2. evidence source→validity gate→(R_u/D_u)→frozen worker state；
3. initial routing→arrival→replication/conflict→continuation/stop/escalation/unresolved→replay。

主文表：阶段—用途矩阵、指标字典、RQ 统计合同、worker state/support/fallback、failure-family/scene evidence。

附录 machine-readable 表：worker-task-tag observation、task-tag three-state evidence、worker-scene profile、online routing evidence、geometry stability；反例库另记录 candidate/adjudication/challenge/retraining layer、provenance 和 inclusion flags。

## 6. 迁移与实现状态

- v4 旧主轴：保留方法细节，重写上层定位、贡献和结果解释。
- 当前 active sections：重写为 v5 语义；inactive legacy sections 不迁移，只在 migration audit 登记。
- `THESIS_OUTLINE_AUDITABLE_DUAL_CHAIN_v5.tex` 是正式 standalone 提纲，不是 manuscript 真源。
- 实现状态只使用 `code_or_scaffold_implemented`、`candidate_dryrun_artifact_generated`、`formal_thesis_artifact_generated`。
- 本轮不修改协议、assignment、routing、tools、tests、data 或原始 artifacts；Overleaf 是唯一编译目标。
