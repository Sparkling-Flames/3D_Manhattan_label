# Paper A 正式论文提纲与写作合同 v4

> 版本日期：2026-07-16  
> 状态：v4 方法重构与主动 manuscript 迁移合同；不是实验结果、协议或物理 artifact schema。  
> 历史边界：保留 `THESIS_OUTLINE_AUDITABLE_DUAL_CHAIN_v3.md/.tex` 作为历史审计版本，不回写历史预注册。  
> 编译边界：本地无 LaTeX engine；实际 PDF 由 Overleaf 编译。本文件不声称 manuscript 已编译。

## 0. 权威层级与不回写边界

正式执行主线固定为：

```text
Pilot -> PreScreen -> Calibration -> Main(Test + Validation)
P1 -> C1 -> C2 -> T1 -> V1
```

权威顺序为：冻结 protocol/assignment 与实际执行状态 > 不冲突的分析澄清 > 代码/字段可证明的实现状态 > 旧 manuscript 表述。本文不修改 `ROUND_BASED_EXECUTION_PROTOCOL_v1.md`、`ROUND_BASED_ASSIGNMENT_SOP_v1.md`、P1 admission、`w_max`、C1/C2 assignment、Calibration pool、C1 XML、raw export、active logs、analysis_results、tools、tests、GT、Paper B 或 Paper A Manhattan。

三状态 task-tag、seam-aware Geometry LOO 与事件驱动 replay 已有 `code_or_scaffold_implemented` 的代码/脚手架；candidate dry-run 只在生成并通过 contract audit 后标为 `candidate_dryrun_artifact_generated`。由于正式 C1 closeout 尚未完成，`formal_thesis_artifact_generated`、frozen worker state 与 thesis-facing result 仍为 pending；旧多数共识产物只可作为 `legacy descriptive proxy`。

## 1. 贡献层级与研究边界

### 1.1 一级贡献

1. 阶段化、轮次化、带 provenance 与 validity gate 的可审计半自动全景布局标注协议。
2. 双链路 worker modeling：Calibration-only protocol reliability `R_u`、P1 diagnostic precursor `D_u^{P1}` 与 C2-frozen operational profile `D_u^{C2}`。
3. 在 Validation 前冻结 worker state 后进行的预算感知 Random/Global/Full 路由评价。

### 1.2 二级创新

support-aware 场景特异可靠度与 Global fallback、加权共识消融、failure-family/counterexample bank、predictive association、active-time integrity audit、时序追加/冲突解决审计。

### 1.3 明确排除的一级主张

模型重训练、Bi-Layout 改造、A-line Manhattan 工具、自动 OOS 模型、worker-facing Manhattan correction、数据集重标注模型均降级到讨论、附录或未来工作。

## 2. 研究问题

### 2.1 RQ1：效率

**回答什么问题：**半自动初始化是否降低 owner-valid exact active time，同时不以低质量、blind trust 或异常低编辑为代价？  
**使用什么证据：**exact annotation-level browser log、owner/independence/provenance gate、最终 geometry/quality 与风险信号。  
**Primary：**worker-task-annotation 级 exact active-time。  
**Sensitivity/audit：**known-only 可疑 session、task-level fallback、`lead_time`、unknown annotation、parent-derived timing、system collection issue。  
**禁止主张：**更快不等于更可靠；active-time 不是 worker quality 本身；fallback 不得静默进入 primary。

### 2.2 RQ2：质量、纠错与行为影响

**回答什么问题：**半自动初始化是否影响最终几何质量、IAA/consistency、issue recognition、geometry correction、blind trust、undercoverage 与 failure-family 分布？  
**使用什么证据：**Calibration_manual/semi 的固定有效冗余比较、独立 reference、三状态 meta-label、failure-family 与审计 provenance。  
**Primary：**最终 geometry/quality、issue recognition 与 correction performance 的预注册比较。  
**Sensitivity/audit：**weighted consensus、balanced subsampling、failure-family/counterexample、reference unavailable。  
**禁止主张：**`model_issue` 选择不等于纠错成功；undercoverage 不属于 OOS；weighted consensus 不是主干。

### 2.3 RQ3：冻结 worker state 的效度与路由价值

#### 2.3.1 RQ3a：predictive association / validity

**回答什么问题：**通过 independence/process-validity gate 的 P1 evidence 是否与独立后续 C1/C2/Main 行为呈方向一致的描述性预测关联？  
**使用什么证据：**P1 geometry → 后续 geometry、P1 semi-correction → 后续 `Calibration_semi` correction、P1 process warning → 后续 process reliability。  
**Primary：**有效 worker 数、support、Spearman/Kendall、worker bootstrap CI、directional consistency。  
**Sensitivity/audit：**suspected、missing、not_evaluable、discrepancy workers、`interpretation_allowed`。  
**禁止主张：**P1 自证 predictive validity；RQ3a 自动升级为 routing profile；复杂预测模型或正式 Bonferroni 主检验。

Scope→scope 与 undercoverage→coverage 因独立支持、专家 adjudication 或 denominator 稳定性不足，主动降级为 exploratory/pending；不进入正式 RQ3a 的三组 primary predictor--target 组合。

#### 2.3.2 RQ3b：routing utility

**回答什么问题：**在固定预算和冻结状态下，Full 是否优于 Random 与 Calibration-only Global？  
**使用什么证据：**Calibration_manual image-level cross-fitted offline replay；V1 只报告冻结 policy 部署与审计。  
**Primary：**first-selected worker quality、sequential budget efficiency、independent reference 可用时的 final aggregate quality。  
**Sensitivity/audit：**实际 arrival order、固定随机顺序、policy support/unsupported、fallback、escalation、reference unavailable。  
**禁止主张：**V1 临时重调参；把 replay 写成完整 worker pool 的无偏在线效应；最终 crowd scene 回填首次路由。

## 3. 正式章节结构与写作卡片

每个正式小节必须记录五项卡片：回答什么问题、使用什么证据、Primary、Sensitivity/audit、禁止主张。主动 LaTeX 以注释保存卡片，PDF 只呈现自然学术段落。

### 第1章 引言

#### 1.1 研究背景与现实约束

回答什么问题：说明半自动初始化的效率收益与 automation bias 风险。使用什么证据：协议边界和现实采集约束。Primary：研究动机。Sensitivity/audit：missingness、active-time integrity。禁止：把 Paper A 写成模型重训练论文。

#### 1.2 研究缺口与方法路线

回答什么问题：说明为什么需要 evidence-validity gate、双链路和冻结路由。使用什么证据：Pilot/P1/C1/C2/T1/V1 生命周期。Primary：主轴。Sensitivity/audit：历史 schema harmonization。禁止：用后验结果改写历史 admission 或 assignment。

#### 1.3 三个一级 RQ、RQ3a/RQ3b 与贡献层级

回答什么问题：固定 RQ1/RQ2/RQ3 层级。使用什么证据：RQ 合同和贡献表。Primary：三项一级贡献。Sensitivity/audit：二级创新。禁止：把 RQ3a、RQ3b 写成两个一级 RQ。

### 第2章 相关工作

#### 2.1 全景布局估计与布局标注

回答什么问题：界定任务与几何测量背景。使用什么证据：布局标注文献和本文任务。Primary：问题定位。Sensitivity/audit：几何 metric 兼容性。禁止：声称提出新的布局网络。

#### 2.2 模型辅助标注与 automation bias

回答什么问题：区分 issue recognition、correction、blind trust。使用什么证据：模型辅助标注文献与行为字段。Primary：行为机制。Sensitivity/audit：historical acceptable harmonization。禁止：把 model issue 票直接解释为 correction。

#### 2.3 众包可靠度、worker modeling 与共识

回答什么问题：说明 `R_u`、`D_u^{P1}`、`D_u^{C2}` 和三状态证据的概念边界。使用什么证据：Calibration LOO 与 worker profile。Primary：双链路。Sensitivity/audit：weighted consensus。禁止：把共识 confidence 写成 truth probability。

#### 2.4 自适应冗余、路由与预算评价

回答什么问题：说明时序追加与预算评价。使用什么证据：offline replay 和 cross-fitting 文献。Primary：Random/Global/Full。Sensitivity/audit：V1 deployment。禁止：用 V1 补做未注册主比较。

#### 2.5 Provenance、证据有效性与可审计协议

回答什么问题：说明 evidence validity gate 的必要性。使用什么证据：artifact path、SHA、rule version、inclusion flags。Primary：可追溯链。Sensitivity/audit：system collection issue。禁止：missing evidence = success。

### 第3章 研究协议、证据类型与数据生命周期

#### 3.1 阶段、轮次与冻结点

回答什么问题：谁在何时冻结什么。使用什么证据：正式 protocol/SOP。Primary：P1/C1/C2/T1/V1 职责。Sensitivity/audit：当前 C1 launched/valid/completed 状态。禁止：改变冻结边界。

#### 3.2 四类证据与三类共识

回答什么问题：区分 Scope/OOS、Difficulty、Model Issue、Geometry 四类证据与任务描述共识、评价参考共识、停止共识。使用什么证据：分层 artifact。Primary：各 estimand 独立 gate。Sensitivity/audit：legacy majority proxy。禁止：一套多数阈值承担三种共识功能。

#### 3.3 任务池、condition、assignment 与 provenance

回答什么问题：说明任务池和条件隔离。使用什么证据：assignment manifest、pool、condition、base image。Primary：合法任务集合。Sensitivity/audit：audit-only inventory。禁止：修改已启动 assignment。

#### 3.4 Scope、reference、active-time 与 estimand-specific gate

回答什么问题：决定一条 evidence 可进入哪些分母，并分离任务结果参考与 worker-specific LOO 参考。使用什么证据：independence、owner-valid time、scope/final-gold provenance、reference status。Primary：RQ-specific inclusion flags。Sensitivity/audit：fallback timing、ambiguous reference。禁止：一个 validity flag 决定所有用途，或把两类 reference 混成同一对象。

`task_outcome_reference` 只承载 final scope、expert/final-gold、hard-single、hard-multi、soft-ambiguous 与 expert-aligned quality；字段至少包括 `type`、`identity`、`sha256`、`cardinality`、`source`、`status`。`r_u_worker_specific_loo_reference` 只承载 worker-task 的 `q^R_{t,u}`；字段至少包括 `worker_id`、`task_id`、`mode`、`identity`、`sha256`、`excludes_worker`、`peer_support`、`status`。同一 task 的不同 worker 原则上不得共享后者的 reference identity。

RQ1 的正式时间 identity 固定为 `project_id + ls_runtime_task_id + worker_id + annotation_id`。同一 `annotation_id` 内，同一 session 取最大合法累计值，多个不重叠合法 session 才允许累加；同一 worker-task 出现多个 annotation ID 时，不自动累加或选择最新，进入 multiple-annotation review，裁决前 `eligible_for_RQ1_time=false`。Geometry/quality 与 active-time 必须绑定同一 `selected_annotation_id`。

#### 3.5 Evidence validity and post-closeout integrity gate

回答什么问题：保证 closeout 后仍不污染历史执行。使用什么证据：independent/confirmed non-independent/suspected/not evaluable、exact active-time identity、hard-single/hard-multi/soft ambiguous reference、process-evaluable/system issue、expert adjudication、artifact path/SHA/rule version。Primary：合法 evidence。Sensitivity/audit：dry-run risk proxy、missingness、pending sidecar。禁止：system issue 惩罚 worker；dry-run proxy 自动升级为 failure。

#### 3.6 P1 retrospective integrity amendment 与当前 C1 状态

回答什么问题：说明 retrospective audit 只影响 capability eligibility。使用什么证据：P1 provenance、C1 launched/closeout artifacts。Primary：当前状态透明披露。Sensitivity/audit：pending feasibility。禁止：P1 admission、C1 assignment 或 C2 reason 回写。

### 第4章 测量模型与双链路工人画像

#### 4.1 符号、方向与 estimand-specific inclusion

回答什么问题：统一符号方向。使用什么证据：display contract 与 artifact alias。Primary：`R_u`、`D_u^{P1}`、`D_u^{C2}`。Sensitivity/audit：raw risk rates、legacy `T_u/U_u` alias。禁止：同一符号混用失败率和 reliability。

#### 4.2 三状态 task-tag 观测模型

回答什么问题：表示正向、显式反向、未声明和不可评估。使用什么证据：合法独立响应。Primary：`Y_{tws}\in\{+,-,0,NA\}`、代码字段 `a/e/u/k` 与展示符号 `n_+,n_-,n_0,k=n_++n_-+n_0`、missingness fields、`unanimous_positive=(a=k)` 和 `unanimous_explicit_negative=(e=k)`。Sensitivity/audit：LOO influence。禁止：未选中 = 反对；多数 confidence = truth probability；把 `u` 同时当作 worker 下标和 unasserted 计数。

#### 4.3 Difficulty 分析合同

回答什么问题：因素是否达到 worker 报告阈值并造成实质困难。使用什么证据：raw response、UI/instruction version、多选诊断。Primary：trivial、specific labels、组合分布。Sensitivity/audit：multi-select diagnostics、measurement limitation。禁止：trivial = 物理上绝对不存在现象；建立“爱多选型 worker”好坏分数。

#### 4.4 Model Issue 分析合同

回答什么问题：区分 acceptable、issue recognition 与 correction performance。使用什么证据：raw issue response、edit behavior、model version/checkpoint/payload hash、expert/trap reference。Primary：harmonized legacy class。Sensitivity/audit：structural_edit_unresolved。禁止：显式 model issue = 几何纠错成功；行为推断 = 当时显式识别。

#### 4.5 task-tag 场景证据与 worker-scene profile

回答什么问题：从统一合法 evidence 形成 scene profile。使用什么证据：主要 `k\approx5` core、`a/e/u`、conflict 与 support。Primary：broad candidate `a\ge2,e<2`、strict candidate `a\ge3,e\le1`。Sensitivity/audit：`n_broad/n_strict`、CI/LCB、concordance、LOO pivotality。禁止：不同 worker 因 LOO 取得不同正式 scene task set；单图生成正式 reliability。

条件性 scene reliability 记为 `R_{u,s}`，只在 worker-scene support、CI/LCB、reference 和 interpretation gate 达标时作为候选；support 不足时 `profile_routing_eligible=false` 且退化为 `global_reliability`。`R_{u,s}` 不改变 primary `R_u` 的 Calibration-only 来源。

#### 4.6 Geometry LOO 与几何指标层级

回答什么问题：在不让 worker 进入自身 reference 的条件下描述几何稳定性。使用什么证据：`v\ne w` peer set、reference cardinality、pairing/range/ambiguity/computability gate。Primary：当前 `R_u` 的 `iou_to_consensus_loo`；candidate seam-aware `y_ceil(x),y_floor(x),w(x)` 与 `q_boundary/q_wallwall` 仅作 `G_u` diagnostic components/alternative-estimator comparison。Sensitivity/audit：cyclic RMSE、floor-plane 2D IoU、3D IoU/depth RMSE/\(\delta_1\)。禁止：convex-hull medoid 作为完整 truth；不兼容 metric/direction/normalization 合并；当前未实现的 candidate 写成结果。

若没有预先冻结的 component-selection/fusion 规则，不形成单一 integrated `G_u^{C2}`；各 Geometry component 独立报告。任何组合只能依据 metric-valid coverage、LOO stability、independent-reference alignment、support 与 direction consistency 在 C2 前 prospective 冻结，不能依据结果差异事后选择。

#### 4.7 `R_u`、`D_u^{P1}`、`D_u^{C2}`、support 与 failure-family

回答什么问题：形成正式 state 与诊断 profile。使用什么证据：C1/C2 `Calibration_manual` LOO、scope、semi correction、undercoverage、process。Primary：`R_u`、`D_u^{P1}` 与 C2-frozen `D_u^{C2}`，五维 higher-is-better。Sensitivity/audit：raw blind-trust/correction、undercoverage、process rates、support/fallback。禁止：P1/semi/Main/V1 回流 `R_u`。

#### 4.8 Scope/OOS、undercoverage 与 counterexample

回答什么问题：区分 scope response、task final scope、undercoverage 和 process。使用什么证据：expert adjudication、五个 failure families、counterexample review。Primary：合法 family signals。Sensitivity/audit：auto candidates、insufficient cells、`interpretation_allowed=false`。禁止：undercoverage = OOS；process/system issue 自动转 geometry failure；auto candidate 未 review 即为 final counterexample。

### 第5章 路由策略与统计分析

#### 5.1 C2 冻结的 worker state 与 task-side risk

回答什么问题：哪些 state 可进入冻结路由。使用什么证据：C2 final state、task risk manifest、support/fallback。Primary：operational frozen state。Sensitivity/audit：cross-fitted shadow state。禁止：P1 直接成为正式 routing profile。

#### 5.2 首次发放、后续追加与冲突解决

回答什么问题：保证信息时序。使用什么证据：`decision_step_index`、`n_responses_available_at_decision`、`current_a/e/u`、`evidence_snapshot_id`、`event_batch_id`、`event_batch_size`、`arrival_order_source`、`timestamp_precision`、`tie_policy`、`pre_batch_snapshot_id`、`post_batch_snapshot_id`。Primary：同一 annotation 的全部 tag 作为一个原子事件；同一 task 中相同 trusted timestamp 且无更高精度服务器顺序的 annotation 作为一个 atomic event batch；所有 tied annotation 读取同一 pre-batch state，批次内不得 stop 或选择下一名 worker，全部写入后只做一次 continuation/stop decision。首次仅使用 global `R_u`、pre-annotation task/model risk、metadata/load/fallback；追加和冲突才读取到达的 scene evidence。Sensitivity/audit：annotation ID 升序、降序和 seeded random permutations；annotation ID 不解释为真实到达顺序。禁止：最终 crowd scene 回填首次路由。

#### 5.3 动态冗余、停止和专家成本

回答什么问题：何时继续、停止、升级或 unresolved。使用什么证据：snapshot、support、conflict、expert logs。Primary：四参数 `k_dispatch_initial`、`k_min_for_stop`、`standard_cap`、`escalation_cap`；low-risk initial/final minimum 初步约 2，high-risk initial 约 2--3，stress initial 约 3，standard cap 候选 5，escalation cap 候选 7；统一输出 `family_evidence_stop_status`、`geometry_consensus_required`、`geometry_profile_eligible`、`task_completion_status`、`stop_block_reason`。Sensitivity/audit：`k_used`、expert count/time/cost。禁止：singleton final acceptance；无限加票解决协议歧义、非独立或稳定双峰；把候选值写成当前冻结事实。

停止按 task/evidence family 分支：Scope-only、resolved OOS、Difficulty evidence、Model Issue recognition 不以 Geometry 阻塞；Model Issue correction、Geometry production、worker-scene geometry profile 与 resolved in-scope whole-task completion 才要求 initial/final geometry 可比且 Geometry gate 通过。达到 escalation cap 仍不稳定可 unresolved。

#### 5.4 Random、Global、Full 与信息时序

回答什么问题：隔离三策略的信息来源。使用什么证据：Calibration replay、V1 frozen deployment。Primary：Random/Global/Full replay。Sensitivity/audit：V1 deployment/fallback。禁止：V1 临时并跑未注册策略。

#### 5.5 Image-level cross-fitted replay 与 RQ3b estimands

回答什么问题：避免 image leakage 和后验调参。使用什么证据：同一 `base_task_id/image_id` 同 fold、evaluation fold 排除 state/threshold/normalization/support/fallback/stopping/feature selection、atomic event ledger、terminal snapshot。Primary：first-selected quality、budget efficiency、independent-reference final aggregate。Sensitivity/audit：unsupported/reference unavailable、tie permutations。终止后才到达的 annotation/tag/geometry 写 `post_terminal_audit_only=true`，不改变 selected workers、`k_used`、stop reason、formal aggregate 或 policy outcome。禁止：按 annotation 行平均 policy outcome或外推完整 worker pool 无偏在线效应。

#### 5.6 RQ1、RQ2、RQ3a、RQ3b 统计合同

回答什么问题：把每个 RQ 绑定到 data、estimand、方法和降级规则。使用什么证据：SAP v1 与本合同。Primary：保留冻结配对、bootstrap、permutation、MDE、missingness 口径；SAP 已给出 RQ1 active-log coverage<90\% 或 condition coverage 差异>5 个百分点时的降级。Sensitivity/audit：weighted consensus、K-S、failure distribution。若 SAP v1 未给出 MDE/smallest effect、quality floor/non-inferiority margin 或 RQ2 multiplicity，则标为 prospective pending 并在结果前 additive amendment。禁止：用 v4 改写 SAP v1 primary estimand。

### 第6章 实验结果

#### 6.1 Evidence completeness 与 validity-gate 流量

回答什么问题：多少 evidence 进入各分母。使用什么证据：四类 evidence、三状态计数、gate flags、pending 状态。Primary：flow table。Sensitivity/audit：legacy proxy、missing/not_evaluable、system issue。禁止：虚构三状态或 geometry 结果。

#### 6.2 RQ1

回答什么问题：回答 exact active-time 与质量调整。使用什么证据：primary log 与 quality-adjusted audit。Primary：RQ1 estimand。Sensitivity/audit：fallback and fast-low-quality/fast-blind-trust。禁止：更快直接解释为可靠。

#### 6.3 RQ2

回答什么问题：回答质量、纠错和行为影响。使用什么证据：最终 geometry、issue recognition/correction、undercoverage、failure families。Primary：固定比较。Sensitivity/audit：weighted consensus、counterexample。禁止：把 issue recognition 写成 correction。

#### 6.4 RQ3a

回答什么问题：回答跨阶段描述性关联。使用什么证据：三组 predictor-target 与 gate。Primary：valid worker/support/association/CI。Sensitivity/audit：pending/not_evaluable/discrepancy。禁止：写成已完成 formal predictive validity。

#### 6.5 RQ3b

回答什么问题：回答冻结 policy 的路由效用。使用什么证据：cross-fitted replay、V1 audit。Primary：Random/Global/Full。Sensitivity/audit：arrival order、fallback、reference unavailable、V1。禁止：把 pending online routing table 当已实现。

#### 6.6 二级创新、failure-family、counterexample 与审计结果

回答什么问题：解释失败链而非替代主终点。使用什么证据：五个 family、专家 review、active-time/provenance audit。Primary：描述性诊断。Sensitivity/audit：auto candidates、legacy consensus、Manhattan proxy。禁止：将反例库写成唯一核心贡献。

### 第7章 讨论与局限

#### 7.1 主要发现与协议意义

**回答什么问题：**哪些发现可以被主证据支持。  
**使用什么证据：**各 RQ 的 primary estimand 与 gate report。  
**Primary：**协议、双链路与冻结路由的证据边界。  
**Sensitivity/audit：**support、missing、failure-family。  
**禁止主张：**把 RQ3a 写成 RQ3b，或把 V1 写成 replay 主比较。

#### 7.2 三状态 meta-label 的测量局限

**回答什么问题：**三状态是否可能引入解释歧义。  
**使用什么证据：**`a/e/u/k`、历史 schema harmonization、missingness。  
**Primary：**unasserted、explicit negative、NA 的边界。  
**Sensitivity/audit：**legacy majority proxy、conflict state。  
**禁止主张：**三状态 confidence = truth probability。

#### 7.3 Geometry LOO 与 metric compatibility

**回答什么问题：**Geometry LOO 与指标兼容性如何限制解释。  
**使用什么证据：**reference cardinality、pairing/range/ambiguity gate、stability sidecar。  
**Primary：**LOO 独立性与兼容 component。  
**Sensitivity/audit：**legacy medoid、2D/3D 条件指标、Manhattan audit。  
**禁止主张：**pending seam-aware metric 已产生结果，或 medoid 是完整 truth。

#### 7.4 离线 replay、时序和外部效度

**回答什么问题：**replay 是否能支持在线路由外部效度。  
**使用什么证据：**image-level cross-fitting、arrival snapshots、V1 deployment logs。  
**Primary：**observed candidate set 内的条件性效用。  
**Sensitivity/audit：**固定随机顺序、unsupported、V1 audit。  
**禁止主张：**完整 worker pool 的无偏在线部署效应。

#### 7.5 support、missingness、unresolved 与专家成本

**回答什么问题：**不确定性和专家成本如何进入解释。  
**使用什么证据：**support、not_evaluable、unresolved、expert review/time/cost。  
**Primary：**按 family 分支的合法停止与 unresolved 边界；不能用一个全局 Geometry gate 覆盖所有 evidence family。  
**Sensitivity/audit：**escalation rate、system issue、missing evidence。  
**禁止主张：**专家是免费 fallback，或无限加票可解决协议歧义。

停止矩阵：Scope-only、resolved OOS、Difficulty evidence、Model Issue recognition 不要求 Geometry；Model Issue correction、Geometry production、worker-scene geometry profile 与 resolved in-scope whole-task completion 要求 Geometry。矩阵字段为 `family_evidence_stop_status`、`geometry_consensus_required`、`geometry_profile_eligible`、`task_completion_status`、`stop_block_reason`。

#### 7.6 支线内容和未来工作

**回答什么问题：**哪些能力不属于当前 Paper A。  
**使用什么证据：**实现状态和协议边界审计。  
**Primary：**明确排除模型重训练、Bi-Layout、自动 OOS、worker-facing Manhattan correction。  
**Sensitivity/audit：**Manhattan、weighted consensus、counterexample。  
**禁止主张：**将支线或 pending 工具写成一级贡献。

### 第8章 结论

#### 8.1 三个一级 RQ 的证据边界

**回答什么问题：**三个一级 RQ 各自能安全回答到哪里。  
**使用什么证据：**RQ-specific primary/sensitivity/audit outputs。  
**Primary：**RQ1/RQ2/RQ3 的 gated evidence。  
**Sensitivity/audit：**not_evaluable、unresolved、pending。  
**禁止主张：**用辅助结果替代 primary。

#### 8.2 三项一级贡献

**回答什么问题：**论文真正贡献了什么。  
**使用什么证据：**协议合同、双链路定义、C2 freeze 后 policy contract。  
**Primary：**三项一级贡献。  
**Sensitivity/audit：**support-aware fallback、failure-family、active-time audit。  
**禁止主张：**把 weighted consensus、Manhattan 或重训练升格。

#### 8.3 不超出证据的结论

**回答什么问题：**哪些结论必须留在证据范围内。  
**使用什么证据：**实现状态、migration audit、Overleaf 编译后结果。  
**Primary：**已完成且 gate 通过的内容。  
**Sensitivity/audit：**pending implementation、not_evaluable、unresolved。  
**禁止主张：**虚构三状态、Geometry 或 routing 结果；回写历史 protocol。

## 4. 统一测量与符号合同

### 4.1 三状态 task-tag

对合法独立响应定义：

```text
Y_tws ∈ {+, -, 0, NA}
+ = positive_assertion; - = explicit_negative;
0 = unasserted; NA = not_evaluable.
```

每个 task-tag 保存代码字段 `a`、`e`、`u`、`k=a+e+u`，展示符号使用 `n_+`、`n_-`、`n_0`、`k=n_++n_-+n_0`，另存 `n_missing`、`n_invalid`、`n_nonindependent_excluded`、`n_schema_uninterpretable`、`unanimous_positive=(a=k)` 与 `unanimous_explicit_negative=(e=k)`。报告 `positive_coverage=a/k`、`explicit_negative_coverage=e/k`、`unasserted_rate=u/k`，以及支持充分时的 `explicit_balance=a/(a+e)`。`a=0/1/2/3/\ge4` 使用 none/isolated/replicated/convergent/high-replication-positive；反向状态同理；`a\ge2,e\ge2` 为 `replicated_explicit_conflict`，不形成 stable/strict positive task set。`loo_positive_nonempty=(a\ge2)`、`loo_positive_replicated=(a\ge3)` 只表示重复性/pivotality，不是 scene truth probability。

### 4.2 Difficulty 与 Model Issue

Difficulty 的 `trivial` 表示 worker 明确主张没有因素达到本次角点实质困难的报告阈值，因此映射为所有具体 tag 的 explicit negative，但不表示物理上绝对不存在该因素。Model Issue 的未来 `acceptable` 与具体 issue 互斥；旧 schema 通过 `behavior_inferred_corner_drift`、`harmonized_acceptable`、`structural_edit_unresolved` 保守 harmonize。每条 issue evidence 绑定 `model_name`、`model_version`、`checkpoint_hash`、`inference_config`、`preprocess_postprocess_version`、`initialization_artifact_id`、`prediction_payload_hash`。

### 4.3 双链路方向

```text
R_u = Calibration-only protocol reliability
D_u^{P1}=(G_u^{P1},S_u^{P1},C_u^{P1},V_u^{P1},P_u^{P1})
D_u^{C1,provisional}=(G_u^{C1},S_u^{C1},C_u^{C1},V_u^{C1},P_u^{C1})
D_u^{C2,frozen}=(G_u^{C2},S_u^{C2},C_u^{C2},V_u^{C2},P_u^{C2})
C_u = 1 - semi correction failure rate
V_u = 1 - undercoverage failure rate
P_u = 1 - process failure rate
```

`R_u` 只来自 eligible C1/C2 `Calibration_manual`，排除 P1、`Calibration_semi`、C2b、T1、V1；报告 CI、LCB、support 与 freeze stage。`G_u/S_u/C_u/V_u/P_u` 均 higher-is-better。blind-trust/correction、undercoverage、process failure rate 单独 lower-is-better；旧 `T_u/U_u` 仅作 legacy alias。摘要优先使用具体风险名称，不使用未定义风险符号。

### 4.4 Geometry LOO 状态

正式 `R_u` primary 为 `iou_to_consensus_loo`；candidate seam-aware 三通道一维表示及 `q_boundary/q_wallwall` 只作 `G_u` diagnostic/alternative components。每个 task 保存 `valid_k`、pairwise distribution、median peer agreement、LOO medoid/margin、leave-one/two-out sensitivity、multimodality、metric compatibility、consensus status。convex-hull medoid 只保留 legacy agreement proxy。兼容性不足即 `not_evaluable`，不拼接不兼容 component；若无 C2 前 prospective fusion rule，不形成 integrated `G_u^{C2}`。

## 5. 图表与 machine-readable artifact 合同

主文最多三张方法图：

1. 图1：`Pilot -> P1 -> C1 -> C2 -> T1 -> V1` 及 admission/provisional/freeze/test/validation。
2. 图2：四类 evidence → validity gate → `R_u` 与 `D_u^{P1}→D_u^{C1,provisional}→D_u^{C2,frozen}` → frozen worker state。
3. 图3：pre-annotation initial routing → arrival → replicated/conflict trigger → continuation → stop/escalation/unresolved → replay。

主文表：

1. 表1：阶段—数据—允许用途矩阵。
2. 表2：指标字典（名称、符号、方向、分子/分母、来源、gate、support、primary/sensitivity/audit、freeze stage）。
3. 表3：RQ—数据—estimand—统计方法—降级规则。
4. 表4：worker state、support 与 fallback。
5. 表5：failure-family、scene evidence 与 interpretation status。

附录 machine-readable contract 至少定义五类表：

1. worker-task-tag observation；
2. task-tag three-state evidence；
3. worker-scene profile；
4. online routing evidence；
5. geometry stability。

每类表均保留 artifact path、SHA-256、rule version、stage、pool、condition、reference status、validity status、inclusion flags；缺失写 `not_evaluable`，不推断 success。

## 6. 当前实现状态与迁移声明

- `materialize_meta_label_consensus_summary.py` 仍输出旧字段和旧 consensus method；不得改名伪装成三状态 evidence。
- 实现状态统一写为三态：`code_or_scaffold_implemented`、`candidate_dryrun_artifact_generated`、`formal_thesis_artifact_generated`。当前前两态只在对应代码/候选产物和审计证据存在时使用；正式 C1 closeout 尚未完成，因此 formal sidecar、frozen worker state 与 thesis-facing result 仍未生成。
- `c1_materialize_worker_profile_sidecar.py` 的五个 failure families、`n_observed/n_fail`、support、interpretation、raw risk rates 与 true/false/blank 语义继续复用。
- failure outcome 的 true/false/not_evaluable 与 task-tag 的 `+/-/0/NA` 是不同层次合同。
- 当前 C1 的 launched、valid/completed、closeout 状态分开报告；不把 ongoing 写成 closeout 完成。
- v4 不声称章节、结果或 PDF 已全面迁移；实际 section SHA、Overleaf 编译状态和冲突分类见 `THESIS_MANUSCRIPT_MIGRATION_AUDIT_v2.md`。

---

## 最终收口合同（2026-07-16）

本节是 v4 的收口性澄清，不回写历史 protocol、assignment、P1 admission、reserve pool 或已冻结阶段边界。

### 1. 正式 `R_u` 只使用当前 estimator

正式 thesis-facing per-task score 固定为 `iou_to_consensus_loo`：

\[
q^{R}_{t,u}=\operatorname{IoU}(A_{t,u},C_t^{(-u)}),
\qquad
\widehat R_u=\operatorname{median}_{t\in\mathcal E_u^R}q^{R}_{t,u}.
\]

其中 (A_{t,u}) 是选定的正式 annotation，(C_t^{(-u)}) 是明确排除 worker (u) 的 worker-specific LOO consensus。正式集合仅包含 C1/C2、eligible `Calibration_manual`、`task_final_scope=in_scope`、independence/process/capability/geometry/reference gates 全部通过且 `used_for_R_u=true` 的 task；`Calibration_semi`、P1、C2b、T1、V1 不进入 primary `R_u`。当前正式 reference mode 为 `worker_excluded_loo_consensus`，最小 peer support 为 2；代码字段保留现有 alias `r_u_reference_support`。

正式 evidence 必须绑定 `r_u_reference_mode`、`r_u_reference_identity`、`r_u_reference_sha256`、`r_u_reference_excludes_worker`、`r_u_reference_support` 和 `r_u_reference_status`。`task_outcome_reference` 与 `r_u_worker_specific_loo_reference` 是两个不同对象：前者用于 final scope、expert/final-gold、hard-single/hard-multi/soft-ambiguous 与 expert-aligned quality；后者只用于 (q^R_{t,u})，同一 task 的不同 worker 原则上不得共享 reference identity。

worker state 状态矩阵固定为：support=0 → `not_evaluable`、estimate/CI/LCB=NA、`interpretation_allowed=false`；(0<support<N_{R,min}) → `insufficient_support`、`routing_allowed=false`；support 达到当前正式最低要求且 gates 全通过 → `estimated`。CI/LCB 沿用代码当前 task-level bootstrap；当前默认参数为 1000 次重采样、95% percentile interval、seed=0。若执行命令显式覆盖参数，必须在 artifact manifest 中记录，不在论文另造数值。

### 2. P1 与 C2 profile 不再同名

P1 画像统一写为 (D_u^{P1}=(G_u^{P1},S_u^{P1},C_u^{P1},V_u^{P1},P_u^{P1}))，只用于 descriptive diagnostic、RQ3a predictor、watch/audit 与 discrepancy analysis；不得进入首次正式 routing、不得替代 Calibration、不得生成 C2 frozen state。

C2 operational profile 统一写为 (D_u^{C2}=(G_u^{C2},S_u^{C2},C_u^{C2},V_u^{C2},P_u^{C2}))。只有 C2 freeze 后通过 support、provenance、reference 和 interpretation gate 的 component 才具有 `routing_eligible=true`；不足时 `fallback=global_reliability`。C1 只形成 provisional evidence 与 gap list；C2 只在既有 reserve-only 边界内补齐合法 gap 并冻结 `R_u`、`D_u^{C2}`、scene activation、fallback 和 routing contract。

### 3. C2 reason 与诊断 gap 分开

C2 assignment reason 仍只允许 CI precision insufficiency 与核心 worker--scene support insufficiency。common/core discrepancy 和 Geometry evaluability gap 只能作为诊断、closeout gap 或 audit evidence；除非能严格映射到上述既有 worker-side reason，否则不得写成新的 C2 assignment reason。

### 4. active-time 与 duplicate/revision

RQ1 primary identity 为 `project_id + ls_runtime_task_id + worker_id + annotation_id`，必要时同时保存 selected annotation version/time。一个 worker-task 出现多个 annotation ID 时，未完成 adjudication 前 `primary_active_time_eligible=false`、`active_time_status=not_evaluable`；不得自动累加、不得自动选择最新版本。只有人工确认同一合法连续 revision 且日志区间不重叠时，才允许特殊合并，并保存 duplicate/revision disposition 与 adjudication provenance。geometry/quality 与 active-time 必须绑定同一 selected annotation identity。

### 5. 三状态、Geometry LOO 与事件 replay 的实现状态

三状态 task-tag、seam-aware Geometry LOO 和 event-driven replay 的代码或 candidate-only scaffold 已实现；由于正式 C1 closeout 尚未完成，formal sidecar、frozen worker state 和 thesis-facing result 尚未生成。`q_boundary`、`q_wallwall` 是 diagnostic components/alternative-estimator comparison，不替换当前 `R_u` primary；convex-hull medoid 仅为 legacy agreement proxy。候选 stop contract 按 task purpose 分支：scope-only/OOS 不强制 geometry；Difficulty 只要求三状态 evidence gate；Model Issue recognition 与 correction 分开；Geometry production 和 scene profile 才要求 geometry stable、required evidence sufficient 且无 critical provenance/missing blocker。

### 6. machine-readable 正式证据索引

附录 machine-readable index 至少覆盖 annotation registry、annotation version disposition、duplicate review/adjudication/forensic audit、selected-annotation active-time registry、task outcome adjudication、worker-task-tag observation、task-tag three-state evidence、Calibration `R_u` evidence manifest、worker-specific LOO reference manifest、geometry stability、worker-scene profile、formal worker state、online routing evidence、process-only duplicate evidence 与 final closeout adjudication。本索引是字段覆盖合同，不代表这些 artifact 已经生成；缺失 artifact 必须写 `pending implementation` 或 `not_evaluable`，不得用文档完整性伪装实验完成。

### 7. 收口一致性补充

`N_{R,\min}` 目前不是一个可从正式运行结果中反推的冻结常数：代码通过 `min_r_u_tasks` 命令参数传入，当前合同只冻结 LOO peer support=2。正文因此将 `N_{R,\min}` 标记为 `prospective pending`，必须在查看 thesis-facing C1 worker result 前冻结并写入 manifest；不得依据排名稳定性、显著性或 C1 结果事后选择。

当前 CI 代码默认使用 task-level percentile bootstrap、1000 次重采样、95\% interval、seed=0；若正式命令覆盖这些参数，必须以 artifact manifest 的实际值为准。LOO reference 的当前实现是：在同一 task 中先排除被评价 worker，使用剩余 peers 的 pairwise IoU 选取 median-agreement medoid；peer set 不足、scope 混合/未知、geometry 不可计算或 metric compatibility gate 失败时，reference/status 为 `not_evaluable`，不得生成 `q^R_{t,u}`。

`task_final_scope` 的权威来源仅限 frozen final-gold adjudication、expert adjudication 或 review/unresolved 状态。Crowd scope response 只进入 scope reliability、disagreement audit、review trigger 和 case analysis；majority/weighted consensus 不能覆盖 expert/final-gold、改变 primary activation 或改变 scene-aware continuation。

同一 task 的 tied trusted timestamp 采用 simultaneous atomic batch；终止后的后到证据写 `post_terminal_audit_only=true`，不改变已选 worker、`k_used`、stop reason、formal aggregate 或 policy outcome。RQ1 的 duplicate/revision 字段至少包括 `selected_annotation_id`、`selected_annotation_version`、`multiple_annotation_review_required`、`duplicate_disposition`、`revision_disposition`、`adjudication_source`、`adjudication_reason` 与 `active_time_annotation_identity`。
