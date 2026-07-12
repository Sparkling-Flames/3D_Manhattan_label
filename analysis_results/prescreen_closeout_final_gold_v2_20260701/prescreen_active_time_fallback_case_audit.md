# P1 active_time fallback 情况审计

## 审计范围与解释口径

本审计覆盖所有 canonical P1 annotation 中 `active_time_source=lead_time_fallback` 的记录。数据来源为 consolidated final-gold v2 closeout 的 canonical 表和原始 Label Studio export。本文件不改变 admission、duplicate 或 active-time 规则。

`lead_time` 是 Label Studio export 中按 annotation 保存的秒数。它不能用 `updated_at - created_at` 重建，因为这两个时间通常只反映 annotation 的持久化事件。fallback 值只作为 sensitivity/audit 证据，不能作为 primary active-time evidence。

| 标注者 | canonical 行数 | log 行数 | fallback 行数 | fallback 总时长 | match status 汇总 | 当前解释 |
|---:|---:|---:|---:|---:|---|---|
| 8 | 57 | 56 | 1 | 00:06:06.0 | annotation-level ambiguous: 1 | 一个 duplicate-same-geometry task；其余 56 个 task 仍有 primary 时间。 |
| 12 | 57 | 0 | 57 | 01:05:55.5 | no direct log: 57 | 全部 fallback；只能作为 sensitivity/watch 证据。 |
| 14 | 57 | 0 | 57 | 00:11:00.9 | no direct log: 57 | 全部 fallback，且来自 parent annotation 派生记录；不能解释为独立工作时长。 |
| 26 | 56 | 0 | 56 | 01:02:51.5 | no direct log: 56 | 全部 fallback；另外因任务未完成而排除，与时间来源无关。 |
| 30 | 57 | 47 | 10 | 00:28:16.7 | no direct log: 9；project mismatch/no direct log: 1 | 部分 fallback；47 个 task 仍有 primary 时间。 |
| 31 | 57 | 0 | 57 | 04:38:38.5 | no direct log: 57 | 全部 fallback；只能作为 sensitivity/watch 证据。 |
| 34 | 57 | 0 | 57 | 26:11:00.1 | no direct log: 55；annotation-level ambiguous: 2 | 全部 fallback；总时长主要由一个长期打开的 draft 造成，不能视为实际工作时长。 |
| 35 | 57 | 0 | 57 | 02:18:21.8 | no direct log: 57 | 全部 fallback；只能作为 sensitivity/watch 证据。 |
| 36 | 57 | 56 | 1 | 00:09:03.3 | annotation-level ambiguous: 1 | 一个最终 revision 无法获得精确 annotation-level log；其余 56 个 task 仍有 primary 时间。 |

## 分标注者证据

### 标注者 8

- fallback task：`29:3095`，canonical annotation `3496`，`lead_time=366.048 s`。
- 该 task 属于 `duplicate_same_geometry`；canonicalization 按冻结的 duplicate policy 保留了较长的 `lead_time` annotation。
- active log 不包含 annotation identity，因此 duplicate pair 无法进行精确的 annotation-level 匹配。这是归属限制，不代表该 worker 没有日志。

### 标注者 12

- 57 个 canonical task 全部是 `fallback_no_direct_log`；原始 annotation 没有 parent annotation。
- fallback `lead_time`：总计 `3955.464 s`，中位数 `49.482 s`，范围 `22.194–380.814 s`。
- 最大值为：`30:3101` / `3428`（`380.814 s`）、`29:3083` / `3435`（`238.339 s`）、`28:3081` / `3481`（`197.906 s`）。
- 结论：没有 primary 时间估计，只保留已批准的 fallback watch。

### 标注者 14

- 57 个 canonical task 全部是 `fallback_no_direct_log`。
- fallback `lead_time`：总计 `660.869 s`，中位数 `7.549 s`，范围 `0.731–112.543 s`。
- 57 条原始 annotation 全部引用同一 task 的 `parent_annotation`。parent owner 分布为：13 号（30 个 task）、10 号（12 个）、11 号（8 个）、2 号（6 个）、15 号（1 个）。
- 因此，表面上的 11 分钟不能解释为从空白任务开始的独立标注时长，只能保留为 sensitivity/watch 证据。

### 标注者 26

- 56 个已观察到的 canonical task 全部是 `fallback_no_direct_log`；原始 annotation 没有 parent annotation。
- fallback `lead_time`：总计 `3771.537 s`，中位数 `11.608 s`，范围 `3.739–554.274 s`。
- 最大值为：`41:3177` / `3834`（`554.274 s`）、`41:3175` / `3832`（`378.316 s`）、`39:3132` / `3807`（`297.102 s`）。
- 该 worker 因任务未完成而排除，不是因为使用了 fallback。

### 标注者 30

- 10 个 fallback task 是 `40:3155–3164`；另外 47 个 canonical task 有 direct log。
- 其中 9 行是 `fallback_no_direct_log`，`40:3155` / `4154` 是 `fallback_project_mismatch_no_direct_log`。
- fallback `lead_time`：总计 `1696.723 s`，中位数 `150.426 s`，范围 `55.326–410.887 s`。
- 结论：保留现有 mixed-source tier，不把 fallback 值转换成 primary 时间证据。

### 标注者 31

- 57 个 canonical task 全部是 `fallback_no_direct_log`；原始 annotation 没有 parent annotation。
- fallback `lead_time`：总计 `16718.525 s`，中位数 `254.250 s`，范围 `71.523–752.250 s`。
- 最大值为：`41:3174` / `4087`（`752.250 s`）、`41:3175` / `4088`（`712.613 s`）、`39:3150` / `4147`（`707.359 s`）。
- 结论：没有 primary 时间估计，只保留已批准的 fallback watch。

### 标注者 34

- 57 个 canonical task 全部使用 fallback。其中 2 个 duplicate-same-geometry task 属于 annotation-level ambiguous，另外 55 个是 `fallback_no_direct_log`。
- fallback `lead_time`：总计 `94260.055 s`（`26:11:00.1`），中位数 `193.084 s`，范围 `66.530–79323.603 s`。
- 仅 `41:3173` / `4398` 一条记录就有 `lead_time=79323.603 s`（`22:02:03.6`）。其 draft-to-submit 间隔约 22 小时，说明该值包含长期打开 draft 或闲置时间，而不是实际 active annotation time。
- 只去掉这一条异常值后，剩余为 `14936.452 s`（`04:08:56.5`），但这些仍全部是 fallback，不能作为 primary 时间估计。

### 标注者 35

- 57 个 canonical task 全部是 `fallback_no_direct_log`；原始 annotation 没有 parent annotation。
- fallback `lead_time`：总计 `8301.839 s`，中位数 `125.889 s`，范围 `29.404–487.921 s`。
- 最大值为：`40:3161` / `4317`（`487.921 s`）、`40:3163` / `4319`（`468.367 s`）、`41:3173` / `4302`（`369.603 s`）。
- 结论：没有 primary 时间估计，只保留已批准的 fallback watch。

### 标注者 36

- 56 个 canonical task 有 direct active log，合计 `54372 s`（`15:06:12`）。
- 唯一 fallback task 是最终 revision `39:3129` / annotation `4595`，其 `lead_time=543.273 s`。
- 同一 worker/task 还存在早期 revision `4533`。原始 active log 只有 project/task/worker，没有 annotation id，并且在两个 revision 附近存在多个 session，因此不能安全地把日志分配给最终 annotation `4595`。
- canonical 总时长 `15:15:15.3` 中，正好包含这一条 `09:03.3` fallback；其余 `15:06:12` 属于 primary active-log evidence。

## P1 closeout 边界

本审计确认现有 closeout 口径：direct active log 是 primary；`lead_time_fallback` 只是 sensitivity/audit support；missing 或 annotation-ambiguous 的时间不能静默提升为 primary evidence。fallback-only worker 是否保留或排除，仍按已冻结的 P1 admission 决策处理，不由时间来源单独决定。
