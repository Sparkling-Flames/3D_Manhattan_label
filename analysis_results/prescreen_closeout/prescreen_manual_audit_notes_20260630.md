# PreScreen Manual Audit Notes 2026-06-30

本文件记录当前 P1 closeout 人工审计决定与待修正规则；不表示进入 C1/C2 分析。

## 停止边界

- 当前停止在 P1 closeout / C1 handoff 准备节点。
- 不继续推进 C1 数据分析。
- 不冻结正式 `r_u`、`r_u^(s)`、`tau_d`、Score 或 routing profile。

## Active-Time 记录问题

以下 worker 的 57/57 条 P1 response 都未匹配到 userscript active log，全部使用 Label Studio `lead_time` fallback：

- worker 12: manual 30, semi 18, oos 9; `fallback_no_direct_log`
- worker 14: manual 30, semi 18, oos 9; `fallback_no_direct_log`
- worker 35: manual 30, semi 18, oos 9; `fallback_no_direct_log`

worker 31 允许进入下一阶段，但 active-time 证据记录为人工例外：

- `manual_allow_lead_time_fallback_for_31`
- active log 主口径仍不可用；`lead_time` 只作为 fallback / audit / sensitivity 证据。

## Duplicate Annotation 记录

当前重复标注 group 共 4 个：

| worker | project_id | task_id | image | condition | duplicate type | annotation ids | current kept | note |
|---|---:|---:|---|---|---|---|---|---|
| 8 | 29 | 3095 | `7y3sRwLe3Va_92fb09a83f8949619b9dc5bda2855456.jpg` | semi | `duplicate_same_geometry` | `3495;3496` | `3496` | lead_time 365.971 vs 366.048, 差异不显著 |
| 36 | 39 | 3129 | `B6ByNegPMKs_b8e1ecf1bd044e7292581a66683e7993.jpg` | manual | `revision` | `4533;4595` | `4595` | 不同 geometry，保持 revision 人工审查 |
| 34 | 39 | 3137 | `uNb9QFRL6hY_07a43087f1e54e3f828851d8e457a283.jpg` | manual | `duplicate_same_geometry` | `4433;4434` | `4434` | lead_time 相同，191.288 vs 191.288 |
| 34 | 39 | 3148 | `B6ByNegPMKs_4b983544c13946e3a3a518c565ad1086.jpg` | manual | `duplicate_same_geometry` | `4444;4483` | `4483` | latest 也是更长 lead_time，119.944 vs 254.157 |

Manual adjudication:

- worker 36 / project 39 / task 3129 是 revision duplicate。
- 人工确认最终采用 annotation `4595`。
- annotation `4533` 仅保留为 revision audit evidence，不进入 canonical response。
- 该决定不改变 worker 36 的 `process_risk` watch 记录；C1 可继续观察。

Policy update:

- `duplicate_same_geometry`: 保留 lead_time 更长的提交；若相同则保留 latest。
- `revision`: 仍保留 latest，并进入人工审查；不因旧提交 lead_time 更长而自动替换。
- 重复提交时间不相加。

## Undercoverage Screening 修正规则

当前 `high_undercoverage_review` 偏严格，因为 worker-level 计数没有先排除 task-level ambiguity。

当前阶段，undercoverage 更适合作为 hard-case / 反例库 / 任务难度审计 / worker watch 证据，弱作用于 worker 筛选；不作为 P1 强剔除依据。

修正语义：

- P1: `undercoverage = task_or_worker_undercoverage_watch`，默认非阻塞。
- C1/C2: 观察是否形成稳定 worker 偏差。
- 未来插件: 充分校准后可用于 routing / retraining / worker reliability，但不能直接用 P1 单阈值筛人。

后续采用三层规则：

1. Task-level ambiguity
   - 若同一 task 上 `high/medium undercoverage` 人数 >= 4，或 high/medium 比例 > 50%，标记为 `task_majority_undercoverage_risk`。
   - 这些 row 暂不计入 worker-level high undercoverage 风险。

2. Worker-level persistent undercoverage
   - 只统计非 majority-risk task 上的 high undercoverage。
   - 若 worker 在这些非歧义 task 上仍 high >= 2，或 high 比例 >= 20%，才进入 `high_undercoverage_review`。

3. Manual review focus
   - 人工先审 task，而不是先审 worker。
   - 若确认 GT 正确且多数 worker 误解规则，再回写为 instruction / worker-risk evidence。
   - 若确认 GT 或任务定义有歧义，该 task 从 worker screening evidence 中剔除或降权。

## New Server Active-Time 审计

对当前 duplicate task 在当前入口 `active_logs/prescreen` 与 snapshot `analysis_results/prescreen_closeout/raw_inputs/new_server` 进行了比对，输出：

- `prescreen_duplicate_active_time_new_server_audit.csv`

结论：

| worker | project_id | task_id | duplicate type | current active log | new_server snapshot | conclusion |
|---|---:|---:|---|---:|---:|---|
| 8 | 29 | 3095 | `duplicate_same_geometry` | 171.0s, 1 session, 14 events | 171.0s, 1 session, 14 events | 两边一致 |
| 34 | 39 | 3137 | `duplicate_same_geometry` | missing | missing | 两边都无 active log，走 lead_time fallback |
| 34 | 39 | 3148 | `duplicate_same_geometry` | missing | missing | 两边都无 active log，走 lead_time fallback |

Active-time 链路说明：

- userscript 上报粒度是 `(project_id, task_id, annotator_id, session_id)`。
- payload 不包含 Label Studio `annotation_id`。
- 分析端按 session 取 max active seconds，再按 `(project_id, task_id, annotator_id)` 对 session 求和。
- 因此，同一 worker 在同一 task 下创建两个 annotation 时，active_time 只能可靠归到这个 worker-task，不能可靠分配到具体 annotation。
- 当前 duplicate canonicalize 策略因此是：同 geometry 重复按 lead_time 选择 canonical；revision 按 latest 保留并人工审查。
