<!-- PAPER_A_MACHINE_STATUS: normative -->
<!-- PAPER_A_METHOD_CONTRACT_CURRENT.json paper_a_method_20260807_v19 SHA-256 60e60f01d762ee89d788979ad9ef243db1887f6ef81f4d5bb8ae2e6f29b5af38 -->
# Paper A Round-Based Assignment SOP v1

本 SOP 只消费当前方法合同，不定义独立的机器字段、eligibility 或统计语义。正式机器真源为 `docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`。

## 1. 正式阶段与输入

正式链路为：

```text
Pilot -> P1 -> C1-A Batch A -> C2-B Batch A -> C1-B/C2-B Batch B -> C2-A-RP -> T1 -> V1
```

`export_label/`、`active_logs/` 和 `import_json/` 分别是运行时标注、active-time 和 planned assignment 真源。分析输出只能进入 `analysis_results/`，不得反向覆盖原始证据。

所有 primary estimand 先验证 `formal_assignment_eligible`。outside、duplicate/revision、非独立或未登记证据不得进入 GT、peer、LOO、structural 或 timing；不能证明时保留 `not_evaluable`，不补零、不估算。

## 2. C1-A 与 rolling enrollment

C1-A Batch A 的正式范围是 original cohort 加冻结的授权 repair set。Batch A 不等待 late-entry worker，也不关闭整个 rolling enrollment。

未来新人必须先通过 P1，再完成 C1-B；他们只进入 Batch B。Batch B 复用 Batch A 的 `selected_design_sha`、task pool、common anchor 和 bridge generator，只追加新的 worker-task 行，不重新选择 D8/D10/D12、阈值或 task identity。

所有 worker ID 在跨文件连接前规范化为无前导零、无 `W` 前缀的形式，例如 `W034`、`034` 和 `34` 均为 `34`。

## 3. C2-B

C2-B 正式任务设计固定消费 D8、D10、D12。C2-B roster 只来自 `worker_profile_v2.c2_risk_model_eligible`，正式三轴为 `Q_GT`、`R_peer`、`F_struct`；LOO 和 timing 只作为独立 sensitivity/tie-break 状态。

设计、审批、assignment manifest 和 runtime mapping 必须绑定方法合同版本与 SHA。任务包只在本地产生，不自动调用 Label Studio API；人工导入后必须完成一对一 runtime mapping 和 private assignment list audit。该本地审计不声称已验证 Label Studio UI 的 worker visibility。

## 4. C2-A-RP

每个 C2-A-RP block 固定包含 1 张 ordinary task 和 1 张 stress task。每名 worker 最多 5 个 block，即最多 10 张图；只有上一 block 完成并按正式证据重估后，才可决定是否派发下一 block，不得预分配 Block 2--5。

## 5. active-time 与删失

C1 active time 的正式测量层级为 `project_id`–`runtime_task_id`–`worker_id`。它只接受 formal assignment 上的累计型日志：同一 session 取正的累计秒数最大值，再对合格 session 求和；`active_seconds_fragment` 不得相加。annotation-exact identity 仅保留为 forensic audit，不再是 task-worker timing 的前提。

task-worker context 无日志、仅有明确的他人工人选中事件、页面/提交桥接不合格或其他合同排除原因时，统一写入：

```text
task_worker_time_analysis_eligible=false
timing_status=not_evaluable
```

W034 的 17 张 authorized replacement 须通过原 sentinel，或通过 SHA 绑定的事前人工确认回溯声明并逐项通过统一 task-worker 日志审计。回溯路径只能标为 `eligible_with_protocol_deviation`，不得伪装成 fully verified sentinel；无日期证据时记录 `time_basis=operator_recollection`、`timestamp_precision=unavailable`。Timing 是 worker profile 的辅助 operational 字段，不影响 `Q_GT`、`R_peer`、`F_struct`、正式 worker eligibility/rank、C2-B roster、T1 分配或 V1 路由；不得补零、估算或以 `lead_time` 作逐行 fallback。每次 rehearsal 的具体 worker、行数和原因以当次 audit 输出为准，不在 SOP 中硬编码。

Independence 按异常例外审计：正式 assignment、canonical 有效、非 outside、非 W014 且 duplicate 已解决的行默认 `independent` / `protocol_assumption`。机器只能生成 `pending_manual_review`，不得自动判定复制或排除；几何完全相同单独只是诊断标记。普通 completion 直接由冻结 assignment/export 计算，仅例外需人工处置。Public GT 默认按现有 SHA 版本使用，只在研究者明确声明 GT 问题时启动 amendment。

## 6. closeout 与 Stage 3

`C1_EVIDENCE_FROZEN` 只证明 C1 证据已按依赖闭包冻结；它不等于最终 pooled Calibration profile。`FINAL_POOLED_PROFILE_FROZEN` 必须由 C1+C2 最终 profile materializer 单独产生。

Stage 3 之前才要求 `CALIBRATION_ENROLLMENT_CLOSED`、`ALL_CALIBRATION_WORKERS_TERMINAL` 和 `FINAL_POOLED_PROFILE_FROZEN` 同时成立。T1、V1 和 Stage 3 在这些全局条件满足前保持关闭。
