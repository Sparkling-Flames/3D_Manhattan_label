# Round-Based Assignment SOP v1

> Last updated: 2026-03-28

本 SOP 面向实际执行，逐轮说明：

- 输入
- 分发规则
- 允许更新什么
- 禁止更改什么
- 必须落盘什么
- 轮结束判据

若某轮未满足这些要求，则只能视为 exploratory operation，不进入 thesis-facing 主协议。

## 0. CE-only 执行总原则

当前 Label Studio 采用 Community Edition 单实例运行，固定边界如下：

- LS 只承担展示与采集，不承担权限分发
- 外部 `assignment manifest` 是唯一分发真源
- LS 项目、tab、filter 只是执行视图，不是权威分发记录
- 若 LS 页面状态与 manifest 冲突，以 manifest 为准

当前单实例 CE-only 方案下，优先采用**项目切分**而不是复杂 tabs/filter 承载 round / batch：

- `P1_manual`
- `P1_semi`
- `P1_oos`
- `C1_anchor_all`
- `C1_core_batch_*`
- `C2_reserve_batch_*`
- `T1_manual`
- `T1_semi`
- `V1_full_batch_*`

GT 项目可与 worker-facing 项目共实例存在，但只允许作为管理员维护项目，不进入 worker 日常路径。

每轮结束后，除本 SOP 原有工件外，还必须核对：

- 实际导入项目名
- 实际导入任务数
- 实际参与 worker
- manifest 预期 worker/task 映射

## 1. P1 — PreScreen

### 输入

- `import_json/stage1_prescreen_final_20260325/stage1_prescreen_manual_import_v2.json`
- `import_json/stage1_prescreen_final_20260325/stage1_prescreen_semi_import_v5.json`
- `import_json/stage1_prescreen_final_20260325/stage1_prescreen_oos_import_v2.json`
- `analysis_results/phase1_progress_20260324/stage1_final_binding_audit_v6.json`
- `analysis_results/final_gold_layer_20260325/final_gold_records_v1.jsonl`

### 分发规则

- `PreScreen_manual`：全员完成同一批任务
- `PreScreen_semi`：全员完成同一批任务
- OOS gate：单独成池，不并入主几何可靠度链
- CE-only 执行视图默认对应三个独立项目：`P1_manual`、`P1_semi`、`P1_oos`

### 允许更新

- admission 名单
- `r_u^(0)`
- `w_max`
- blind-trust 前证据
- scope-gate / meta-label / active-log 审计结果

### 禁止更改

- 不得改三池定义
- 不得把 `PreScreen` 输出升级为正式 routing profile
- 不得提前计算正式 `r_u / r_u^(s)` 或 `tau_d`

### 必须落盘

- `prescreen_worker_admission.csv`
- `prescreen_r0_snapshot.csv`
- `w_max_locked.json`
- `prescreen_blind_trust_audit.csv`
- `prescreen_scope_gate_audit.csv`
- `prescreen_round_report.md`

### 结束判据

- admission 名单冻结
- `w_max` 冻结
- Stage 1 准入边界冻结

## 2. C1 — Calibration 主校准轮

### 输入

- 通过 `P1` 的 worker pool
- `Calibration_anchor`
- `Calibration_core`

### 分发规则

- `Calibration_anchor`：全员完成
- `Calibration_core`：平衡分配，不要求全员覆盖
- 本轮禁止调用 `Calibration_reserve`
- CE-only 执行视图默认对应：
  - `C1_anchor_all`
  - `C1_core_batch_01`、`C1_core_batch_02`、...
- `C1_core_batch_*` 只导入 manifest 指定的该批任务，不在同一大项目内依赖复杂 tab 分派

### 允许更新

- 第一版 `r_u`
- 第一版 `LCB(r_u)`
- 候选 `r_u^(s)`
- scene 候选频率 / 一致性
- `d_t` calibration reference basis
- CI precision gaps
- scene coverage gaps

### 禁止更改

- 不得改 `Calibration_pool`
- 不得新增 task-side pool
- 不得因为中间结果好看而改 family taxonomy
- 不得提前改写 Validation routing contract

### 必须落盘

- `worker_state_snapshot_C1.csv`
- `scene_candidate_summary_C1.csv`
- `dt_reference_summary_C1.json`
- `ci_precision_audit_C1.csv`
- `scene_coverage_gap_C1.csv`
- `assignment_manifest_C1.csv`
- `calibration_round1_report.md`

### 结束判据

- 形成 provisional `Score`
- 形成 provisional `N_{u,s,min}`
- 形成 provisional `tau_d`
- 明确哪些 worker / scene 需要进入 `C2`

## 3. C2 — Calibration 补齐 / 冻结轮

### 输入

- `C1` 的 worker / scene / CI audit
- 预注册固定的 `Calibration_reserve`

### 分发规则

只允许两类补派：

- CI precision 补派
- 核心场景覆盖补齐

两类都只能是 worker-side insufficiency correction。

CE-only 执行视图默认采用短时项目：

- `C2_reserve_batch_01`
- `C2_reserve_batch_02`
- `...`

每个 reserve batch 完成即关闭，不保留常驻 reserve 池。

### 允许更新

- `r_u` / `LCB(r_u)` 的最终版本
- `r_u^(s)` 的最终启用 / 退化状态
- `tau_d`
- worker risk tier rule version
- Validation routing contract

### 禁止更改

- 不得改 `Calibration_pool`
- 不得做 task-side 扩池
- 不得把新任务塞入 reserve
- 不得为“提升路由收益”而追加任务
- 不得把 `C2` 变成新的选样轮

### 必须落盘

- `worker_state_snapshot_C2_final.csv`
- `scene_contract_locked_v1.json`
- `task_risk_rule_manifest_v1.json`
- `assignment_manifest_C2.csv`
- `reserve_usage_audit_C2.csv`
- `calibration_freeze_report_v1.md`

### 结束判据

- `Score` 冻结
- `N_{u,s,min}` 冻结
- `tau_d` 冻结
- activation / degeneration 规则冻结
- high-risk bucket 规则冻结
- Validation routing contract 冻结

若本轮后仍未满足覆盖或精度要求，必须按降级口径报告，不再无限补。

## 4. T1 — Main-Test

### 输入

- 冻结后的 worker admission
- 冻结后的 `Main-Test` task set
- 冻结后的 timing contract

### 分发规则

- `Manual_Test` 与 `SemiAuto_Test` 按预注册条件分配
- 保持 worker mix 审计与条件平衡
- CE-only 执行视图默认对应 `T1_manual` 与 `T1_semi`

### 允许更新

- `active_time`
- `IoUedit`
- `Manual vs Semi` 条件比较
- worker mix 平衡审计

### 禁止更改

- 不得更改 `w_max`
- 不得更改 worker tier
- 不得把 `T1` 结果回流修改 routing
- 不得把 `T1` 写成 `RQ3` 主证据

### 必须落盘

- `test_condition_assignment_manifest.csv`
- `rq1_active_time_analysis.csv`
- `rq1_time_quality_audit.csv`
- `rq1_test_round_report.md`

### 结束判据

- `RQ1` primary estimand 分析完成
- active-log coverage 与 fallback 比例完成审计

## 5. V1 — Main-Validation

### 输入

- 冻结后的 `LCB(r_u)`
- 冻结后的 `R0 / R1 / R2 / R3`
- 冻结后的 `Score`
- 冻结后的 `r_u^(s)` 启用规则
- 冻结后的 `tau_d`
- 冻结后的 `I_t^{OOD}` / `g_t`
- 冻结后的 `k0 / kmax / stop rule`

### 分发规则

- 只运行已冻结的主策略
- 若部署时仅执行 `Full`，则 `Random / Global` 的主可比证据必须来自 `Calibration_manual` 上的 offline replay 或 shadow support set
- CE-only 执行视图默认只开 `V1_full_batch_*`；`Random / Global` 不在 LS 内并跑补主证据

### 允许更新

- routing event logs
- assignment outcomes
- stop-check results
- activation / degeneration / fallback ratios
- `Validation_OOD / Hard subset H` 审计结果

### 禁止更改

- 不得更改 worker tier rule
- 不得更改 `tau_d`
- 不得更改 `Score`
- 不得更改 `k0 / kmax / stop rule`
- 不得因 `V1` 结果不理想而反推修改 `C2` 冻结内容

### 必须落盘

- `task_risk_snapshot_V1.csv`
- `assignment_manifest_V1.csv`
- `stopcheck_log_V1.csv`
- `routing_event_log_V1.jsonl`
- `validation_round_report.md`
- `online_audit_summary_V1.json`

### 结束判据

- 完成 `RQ3` 部署面审计
- 完成 OOD / Hard subset / stress mode 报告
- 明确区分“offline replay 主可比证据”与“V1 在线执行证据”
