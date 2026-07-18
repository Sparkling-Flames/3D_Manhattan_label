# Round-Based Execution Protocol v1

> Last updated: 2026-07-17

## 0. 定位

本项目后续 thesis-facing 执行采用阶段化、轮次化协议，而不是连续流式采集。

正式主线统一为：

`Pilot -> PreScreen -> Calibration -> Main(Test + Validation)`

阶段分工固定为：

- `PreScreen`：独立准入、`r_u^(0)`、`w_max`、blind-trust 前证据；不负责正式 `r_u / r_u^(s)`。
- `Calibration`：正式 `r_u`、`LCB(r_u)`、候选 `r_u^(s)`、`tau_d`、scene-routing 参数的形成与冻结。
- `Main-Test`：主要服务 `RQ1`。
- `Main-Validation`：主要服务 `RQ3`。

当前注册执行面的最小完整配置固定为：

- `P1`：PreScreen 正式准入轮
- `C1`：Calibration 主校准轮
- `C2`：Calibration 补齐/冻结轮
- `T1`：Main-Test 轮
- `V1`：Main-Validation 轮

若未来新增轮次，只能在 protocol core 不变的前提下作为 `extension cohort` 或 `replication cohort` 单独报告，不得回流修改主分析合同。

## 1. 全局硬约束

### 1.1 不允许改变的主协议边界

以下边界一旦在对应阶段冻结，后续不得更改：

- 四阶段主线定义
- `PreScreen / Calibration / Main` 的职责分工
- `PreScreen_manual / PreScreen_semi / OOS gate` 三池角色分离
- `Main-Test` 与 `Main-Validation` 的研究问题分工
- `d_t` 只作为 OOD risk proxy，不用于 scene taxonomy
- non-IID split 只允许由标注前可得代理驱动；`difficulty / model_issue` 只作后验审计解释

### 1.2 所有正式轮次都必须回答四件事

每一轮都必须明确：

- 本轮输入是什么
- 本轮允许更新什么
- 本轮禁止更改什么
- 本轮必须落盘什么

若缺其中任一项，该轮只能视为 exploratory operation，不得计入 thesis-facing 主协议。

### 1.3 Failure disposition 与外部事故边界

`C1` 起必须记录未完成、结构无效和运行事故的原始证据及 provisional disposition；`C2` 在 `T1/V1` 结果可见前冻结 `failure_disposition_rule_manifest_v1.json`，并据此固定 `C1` 的派生 disposition。`T1/V1` 必须按该 manifest 分类，不得在查看条件或政策臂结果后改写归因。类别固定为：

- `worker_caused_structural_failure`：工人造成的结构性失败；进入其原条件或原政策臂的审计。
- `policy_caused_failure`：候选耗尽、替补规则失败、容量耗尽等由冻结政策或其执行资源导致的失败；不得改归为 worker failure。
- `external_system_failure`：服务器整体宕机、平台不可用、导出损坏等不归责工人或政策的事故；必须有冻结清单要求的时间窗、影响范围和不可变证据支持。

只有在事故证据于结果不可见时已记录、且满足 manifest 的证据字段时，才可分类为 `external_system_failure`。证据不足的历史异常只可标为 `not_evaluable` 并单列审计，不能事后称为系统事故。原始事故日志是运行输入真源；分析输出只保存其派生 disposition 与审计摘要。

## 2. Round P1 — PreScreen

### 2.1 目标

完成独立准入与初始锚定。

### 2.2 输入

- `PreScreen_manual = 30`
- `PreScreen_semi ~= 18`
- OOS gate 小池
- 当前正式 Stage 1 binding / import / final-gold 契约文件

### 2.3 允许更新

- 通过工人名单
- `r_u^(0)` 估计
- `w_max`
- blind-trust 前证据 `T_u`
- prescreen 质量审计结果

### 2.4 禁止更改

- 不得修改 PreScreen 三池定义
- 不得修改 `manual / semi / OOS` 角色边界
- 不得提前生成正式 `r_u / r_u^(s)`
- 不得提前定义 `tau_d`
- 不得把 PreScreen 结果直接写成正式 routing profile

### 2.5 必须落盘

- `prescreen_worker_admission.csv`
- `prescreen_r0_snapshot.csv`
- `w_max_locked.json`
- `prescreen_blind_trust_audit.csv`
- `prescreen_scope_gate_audit.csv`
- `prescreen_round_report.md`

### 2.6 本轮后冻结

冻结：

- admission 名单
- `w_max`
- PreScreen 阈值
- Stage 1 准入边界

不冻结：

- `r_u`
- `r_u^(s)`
- `Score`
- `N_{u,s,min}`
- `tau_d`
- routing 规则

## 3. Round C1 — Calibration 主校准轮

### 3.1 目标

产生正式 worker statistics 的第一版估计，但本轮后不宣称最终冻结完成。

### 3.2 输入

- 通过 `P1` 的 worker pool
- `Calibration_anchor`
- `Calibration_core`

### 3.3 分发规则

- `Calibration_anchor`：所有通过 `P1` 的 worker 全员完成
- `Calibration_core`：平衡分配，不要求全员覆盖
- 不允许使用 `Calibration_reserve`

### 3.4 允许更新

- 第一版 `r_u`
- 第一版 `LCB(r_u)`
- 候选 `r_u^(s)`
- scene 候选频率与一致性统计
- `d_t` calibration reference basis
- CI precision gap 列表
- scene coverage gap 列表

### 3.5 禁止更改

- 不得修改 `Calibration_pool`
- 不得新增 task-side 扩池
- 不得根据 `C1` 结果临时重定义 family taxonomy
- 不得因为某条路由看起来更优而提前改写 Validation 规则

### 3.6 必须落盘

- `worker_state_snapshot_C1.csv`
- `scene_candidate_summary_C1.csv`
- `dt_reference_summary_C1.json`
- `ci_precision_audit_C1.csv`
- `scene_coverage_gap_C1.csv`
- `assignment_manifest_C1.csv`
- `failure_disposition_audit_C1.csv`
- `calibration_round1_report.md`

### 3.7 本轮后状态

可以形成：

- provisional `Score`
- provisional `N_{u,s,min}`
- provisional `tau_d`

但这些都只是冻结候选，不是最终正式版本。

`C1` 冻结时必须从未改写的原始导出重新 materialize 派生审计；这不要求标注员返工，也不得修改 `export_label/`。

## 4. Round C2 — Calibration 补齐/冻结轮

### 4.1 目标

只用 `Calibration_reserve` 完成 worker-side 不足补齐，并在本轮结束后正式冻结后续 Main 所需参数。

### 4.2 唯一允许的补派类型

只允许两类：

- CI precision 补派
- 核心场景覆盖补齐

且二者都必须是 worker-side insufficiency correction。

### 4.3 明确禁止事项

`C2` 明确禁止：

- 不得修改 `Calibration_pool`
- 不得新增 task-side 扩池
- 不得临时把新任务塞入 reserve
- 不得因某个 family 表现不理想而重抽 calibration task
- 不得因某个 routing 结果看起来更优而改变 reserve 用途
- 不得以“提升路由收益”为由追加任务

一句话：

> `C2` 只允许补 worker-side，不允许动 task-side。

### 4.4 本轮必须冻结

- `Score`
- `N_{u,s,min}`
- `tau_d`
- activation / degeneration 规则
- high-risk bucket 启用规则
- worker risk tier rule version
- Validation routing contract
- `failure_disposition_rule_manifest_v1.json`

### 4.5 必须落盘

- `worker_state_snapshot_C2_final.csv`
- `scene_contract_locked_v1.json`
- `task_risk_rule_manifest_v1.json`
- `failure_disposition_rule_manifest_v1.json`
- `assignment_manifest_C2.csv`
- `reserve_usage_audit_C2.csv`
- `calibration_freeze_report_v1.md`

### 4.6 本轮后含义

`C2` 结束后，才允许正式声称：

- scene-aware routing contract 已冻结
- `tau_d` 已冻结
- `r_u^(s)` 的启用/退化规则已冻结

若 `C2` 后仍未满足覆盖或精度要求，则必须按降级口径报告，而不是继续无限补。

## 5. Round T1 — Main-Test

### 5.1 目标

回答 `RQ1`，不承担 routing 主证据。

### 5.2 输入

- 已冻结的 worker admission
- 已冻结的 `Main-Test` task set
- 已冻结的 timing / active-time contract

### 5.3 允许更新

- `active_time`
- `IoUedit`
- `Manual vs Semi` 条件比较结果
- worker mix 平衡审计

### 5.4 禁止更改

- 不得更改 `w_max`
- 不得更改 worker risk tier
- 不得把 Test 结果回流改 routing
- 不得把 Test 写成 `RQ3` 主证据场

### 5.5 必须落盘

- `test_condition_assignment_manifest.csv`
- `rq1_active_time_analysis.csv`
- `rq1_time_quality_audit.csv`
- `t1_failure_disposition_audit.csv`
- `rq1_test_round_report.md`

### 5.6 Failure disposition

- `worker_caused_structural_failure` 必须计入原 `Manual` 或 `SemiAuto` 条件，写为 `structurally_valid = 0` 且 submission-level `delivery_adjusted_quality = 0`。
- 若 `external_system_failure` 影响同图双条件中的任一任务，只可按 manifest 重跑一次同一 base image 的完整 `Manual/SemiAuto` 对；不能完整配对重跑时，整对行政删失，不计入交付调整质量分母。
- `T1` 的行政删失、重跑和三类归因必须按条件披露；不得用外部事故重跑改变条件或 worker/tier 冻结内容。

## 6. Round V1 — Main-Validation

### 6.1 目标

回答 `RQ3`，执行正式 routing / stress mode / 审计链。

### 6.2 输入

已冻结的：

- `LCB(r_u)`
- `R0 / R1 / R2 / R3`
- `Score`
- `r_u^(s)` 启用规则
- `tau_d`
- `I_t^{OOD}`
- `g_t`
- `k0 / kmax / stop rule`

### 6.3 分发规则

Validation 正式执行时只运行已冻结的主策略。

若真实部署仅跑 `Full`，则 `Random / Global` 的可比性证据必须来自：

- `Calibration_manual` 上的 offline replay
- 或 shadow evaluation support set

不得在 `V1` 临时并跑未注册策略来补主证据。

### 6.4 允许更新

- routing event logs
- assignment outcomes
- stop-check results
- activation / degeneration / fallback ratios
- `Validation_OOD / Hard subset H` 结果
- 审计报告

### 6.5 禁止更改

- 不得更改 worker tier rule
- 不得更改 `tau_d`
- 不得更改 `Score`
- 不得更改 `k0 / kmax / stop rule`
- 不得因为 `V1` 结果不理想而反推修改 `C2` 冻结内容

### 6.6 必须落盘

- `task_risk_snapshot_V1.csv`
- `assignment_manifest_V1.csv`
- `stopcheck_log_V1.csv`
- `routing_event_log_V1.jsonl`
- `validation_round_report.md`
- `online_audit_summary_V1.json`
- `v1_failure_disposition_audit.csv`

### 6.7 Failure disposition

- `worker_caused_structural_failure` 作为 worker-level event 保留在原政策臂；仅当任务终态未交付时，任务级 `delivery_adjusted_quality = 0`。
- `policy_caused_failure`（包括 candidate exhaustion、replacement failure、capacity exhaustion）必须保留在原政策臂 ITT，写为 `policy_failure = 1`；`unresolved` 或 `severe_failure` 的交付调整质量为 `0`。
- `external_system_failure` 不归责 worker 或政策。仅可在同一政策臂、同一冻结版本和预留的对称重跑容量内重跑一次；否则行政删失。行政删失不进入交付调整质量分母，但必须报告原始任务数、重跑数、删失数及两臂分布。

## 7. 最小配置与未来扩展

### 7.1 当前 thesis-facing 正式口径

当前 thesis-facing 主执行面固定为：

- `T1`
- `V1`

这是注册的最小完整配置。

### 7.2 若未来新增轮次

若未来确需新增 `T2 / V2`，必须同时满足：

- protocol core 完全不变
- 使用同一冻结的 worker rule / task risk rule / stop rule
- 单独标记为 `extension cohort` 或 `replication cohort`
- 不得回流修改主注册分析口径
- 主结论仍以 `T1 + V1` 为准，新增轮只作补充或复制验证

## 8. 与当前项目状态的对齐

本协议与当前项目状态不冲突，并与现有文档边界一致：

- Stage 1 / prescreen 已 ready，可正式开始
- Calibration 才负责正式 `r_u / r_u^(s)`、`tau_d`、scene-routing 参数冻结
- `underextend` 当前是 extension family，不进 prescreen 主 12 trap
- `topology_failure` 当前无 materialized active asset，不阻碍 prescreen 启动
- `RQ3` 主可比证据不能只靠 Validation 本身，仍应依赖 `Calibration_manual` 上的 offline replay / shadow support logic

## 9. 必须同步推进的文本修订

本执行协议只有与论文文本同步修改，才真正稳固。当前必须同步推进：

- 四阶段主线统一
- 冻结时点统一
- `RQ1` estimand contract 收紧
- A3 从空表改成“`C1` 后实例化模板”

否则就会出现：执行协议已经是一个版本，论文正文还在讲另一个版本。
