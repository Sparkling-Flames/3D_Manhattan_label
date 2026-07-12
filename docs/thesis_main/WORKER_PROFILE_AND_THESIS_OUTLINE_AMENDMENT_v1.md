# Worker profile 与论文提纲 amendment v1：历史兼容桥接

> 版本日期：2026-07-12
> 状态：历史 amendment 的兼容说明；不再作为 Paper A 章节结构真源。
> 正式真源：`THESIS_OUTLINE_AUDITABLE_DUAL_CHAIN_v3.md`。
> 边界：本文件不回写历史预注册、protocol freeze、P1 admission、C1/C2 assignment、routing、统计执行参数或任何原始工件。

## 1. 文件角色变更

本文件曾以 amendment 形式累积 worker profile、P1 post-closeout 和写作建议。为避免在旧提纲后继续追加条款，现将其收敛为兼容桥接：

- 章节顺序、RQ 主轴、贡献层级和主张禁区以 `THESIS_OUTLINE_AUDITABLE_DUAL_CHAIN_v3.md` 为准；
- artifact 字段、物理字段名和 inclusion flags 以 `WORKER_PROFILE_ARTIFACT_FIELD_CONTRACT_v1.md` 为准；
- protocol、assignment、冻结点和运行职责以 protocol/SOP 为准；
- 本文件只保留历史 amendment 的语义映射、不可回写边界和迁移注意事项。

## 2. 双链路兼容映射

### 2.1 链路 A：`R_u`

正式 `R_u` 是 Calibration-only protocol reliability：

- 仅由 C1/C2 `Calibration_manual` 形成；
- P1、`Calibration_semi`、C2b、T1、V1 不进入 primary `R_u`；
- C2 结束时冻结 estimator、LCB、CI、support、scene activation/degeneration 和 fallback；
- Main/Test/Validation 不回流修改 `R_u`。

历史文档中的 `r_u^calib`、`r_u` 和兼容字段 `r_u_calib` 指向同一链路；不得把 P1 operational admission proxy 写成正式 `R_u`。

### 2.2 链路 B：`D_u`

正式画像为越高越好的五维向量：

```text
D_u = (G_u, S_u, C_u, V_u, P_u)
C_u = 1 - semi correction failure rate
V_u = 1 - undercoverage failure rate
P_u = 1 - process failure rate
```

其中 `G_u`、`S_u`、`C_u`、`V_u`、`P_u` 的 evidence 必须逐行保留 stage、pool、condition、reference、support 和 inclusion flags。

现有 `T_u/U_u` 或其他 failure-rate 字段保持物理兼容，不删除、不静默改名；它们在论文展示层被视为 raw risk-rate/legacy aliases，方向为越低越好，不能与 `C_u/V_u/P_u` 共用 reliability 符号。

### 2.3 P1 predictive validity

P1-informed rows 只能在 evidence validity gate 后进入 diagnostic capability。`confirmed non-independent` 不进入 P1 capability；`suspected` 保留 pending；`not_evaluable` 不是 success。P1 画像用于跨阶段 predictive validity，不自动成为正式 routing profile，也不写入 `R_u`。

## 3. Evidence validity bridge

所有历史 amendment 产生的 P1 或 post-closeout evidence 先经过以下 gate，再决定是否进入 `D_u` 或仅进入 audit：

1. `independent`、`confirmed non-independent`、`suspected`、`not evaluable` 四态 independence；
2. owner-valid exact annotation-level active-time identity；
3. scope/final-gold path 与 SHA provenance；
4. hard-single、hard-multi、soft ambiguous reference compatibility；
5. `process_evaluable` 与 system collection issue 分离；
6. dry-run risk proxy 不自动升级为 worker failure；
7. undercoverage 需 expert adjudication；
8. missing evidence = `not_evaluable`；
9. artifact path、SHA、rule version、inclusion flags 必须落盘。

确认的 non-independent row 可作为 process-integrity evidence，但不能改写成 geometry failure；system collection issue 不进入 worker process reliability 分母。完整字段合同见 `WORKER_PROFILE_ARTIFACT_FIELD_CONTRACT_v1.md`。

## 4. Failure-family 兼容语义

五个一级 family 固定为：

- `geometry_quality_failure`
- `scope_oos_failure`
- `semi_correction_failure`
- `undercoverage_failure`
- `process_failure`

failure-family 是诊断链，不等于 `R_u`。同一 worker-task 可以产生多个 evidence signals；undercoverage 不属于 OOS；process issue 不自动成为 geometry failure；insufficient cell 保留但 `interpretation_allowed=false`；auto counterexample 需 expert review 才能进入 final bank。

## 5. active-time 兼容语义

- exact owner-valid annotation-level browser log：primary；
- known-only 但完整性可疑 session：sensitivity；
- task-level fallback：sensitivity/audit；
- `lead_time`：fallback/audit；
- `unknown_annotation`：audit-only，不分配给任务；
- parent-derived timing：forensic audit-only；
- system collection bug：系统问题，不是 worker process failure。

RQ1 必须报告 exact coverage、missing/fallback count、script version、condition-specific time、质量调整解释及 fast-low-quality/fast-blind-trust 检查。

## 6. P1 post-closeout 的不可回写边界

P1 closeout 后的 correction/profile artifacts 只能作为只读诊断和 provenance layer：

- 不改变 admission、`w_max`、P1 pool 或 Stage 1 binding；
- 不改变 C1/C2 assignment、reserve 使用、`Score`、`tau_d`、worker tier 或 routing；
- 不改变 T1/V1 分工、统计核心口径或原始 export/log；
- 不把 P1 rows 写入 primary `R_u`；
- 不把 V1 结果回流 C2。

## 7. 与新提纲的迁移关系

| 历史 amendment 内容 | 新位置 | 当前动作 |
|---|---|---|
| P1-informed geometry profile | 第4章 4.2、4.5 | 保留并改为诊断性、reference-gated |
| `r_u^calib` | 第4章 4.3 | 保留，收紧为 Calibration-only |
| `T_u/U_u` 风险字段 | 第4章 4.5 与字段合同 | 保留物理兼容，改为 raw risk-rate aliases |
| C2b extension | 第3章 3.6、字段合同 | 仅 diagnostic/audit，不进 primary `R_u` |
| failure-family 与 counterexample | 第4章 4.7、第6章 6.6 | 降为二级创新与解释性结果 |
| 旧五章写作建议 | 新提纲第1—8章 | 不再沿用，逐节见迁移地图 |

## 8. 本文件不代表的事项

本文件不表示代码、测试、sidecar、CSV schema、Overleaf 正文或任何分析结果已经完成迁移；不表示 P1 已成为 routing profile；不表示 manuscript 已完成章节重排。实际正文迁移另行执行，并以 `THESIS_MANUSCRIPT_MIGRATION_MAP_v1.md` 为施工清单。
