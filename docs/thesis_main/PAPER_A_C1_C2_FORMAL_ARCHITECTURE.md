# Paper A C1→C2-B 正式分析架构

## 1. 范围与真源

本文件只梳理 `PreScreen → C1 → C2-B` 的生产链。设计语义以
`Paper_A_新版完整论文提纲_vFinal_Draft.md`、Protocol、Assignment SOP 和 SAP
为上位真源；本文件描述代码怎样落实这些合同，不改变实验设计。

本轮没有修改 T1、V1、C2-A-RP、旧 temporal replay、Label Studio 原始 export、
C1 assignment、GT 或云端 `cors_server`。

## 2. 单一生产 DAG

```text
PreScreen immutable closeout (active_logs/prescreen)
                    │
C1 exports + assignments + active_logs/new_server
                    │
                    ├─ freeze-c1 ─────────────> active_logs/c1 + freeze/closure manifests
                    └─ pre-annotation model evidence
                       checkpoint/config/reference PCA/layout/building registry
                                      │
                                  audit-c1
                                      │
                 canonical rows + row eligibility + Q_GT/LOO/F_struct
                                      │
                                 finalize-c1
                                      │
                           C1 evidence freeze manifest
                                      │
                                 design-c2b
                                      │
      risk inventory + task eligibility + hierarchical simulation candidates
                                      │
                numeric threshold approval + selected design approval
                  + selected task/reference approval + capacity manifest
                                      │
                                  build-c2b
                                      │
             assignment_manifest_C2B.csv + worker files + LS import
```

没有旁路入口可以生成正式 C2-B assignment。Rehearsal、候选边和历史 reverse
清单都不能被重命名后充当正式 assignment。

## 3. 状态 owner

| 状态 | 唯一 owner | 下游行为 |
|---|---|---|
| C1 active-log frozen | `c1_active_log_freeze_manifest.json` | 只校验路径、cutoff 和 SHA |
| `collection_window_closed` | collection closure manifest | 不从完成率推断 |
| `C1_CANONICAL_CLOSED` | formal C1 audit | 只反映 identity/version/disposition closure |
| `Q_GT_FREEZE_STATUS` / `R_LOO_FREEZE_STATUS` / `F_STRUCT_FREEZE_STATUS` | C1 measurement owner | 每轴独立为 `frozen`、`support_limited` 或 `pending_collection_close`，不互相替代 |
| `C1_EVIDENCE_BUNDLE_FROZEN` | C1 evidence freeze envelope | collection close 后三轴均已到达终态；不表示三轴都可估计 |
| `C2B_BASELINE_INPUT_FROZEN` | C1 evidence freeze envelope | 只要求 Q_GT frozen 及合格 process/independence/Q_GT worker support |
| `C1_MEASUREMENT_FROZEN` | C1 evidence freeze envelope | 兼容别名，等于 evidence bundle 终态，不再表示三轴全局 AND |
| `C2_TASK_FEATURES_FROZEN` | feature freeze manifest | checkpoint/config/cache/PCA/whitening/circular/seam 均通过独立 SHA 审批 |
| `C2B_ELIGIBLE_RISK_POOL_FROZEN` | C2-B eligibility owner | 最终 source/holdout/history/Scope/reference join 后重新验证任务、building 与 strata 门 |
| `C2B_RISK_DESIGN_FROZEN` | `c2_task_risk.summary.json` | builder 只能继承 |
| C2-B candidate feasibility | design simulation | 不等于设计获批 |
| `C2B_DESIGN_FROZEN` | SHA 绑定的人工 design approval | 必须指定一个非支配可行 `design_id` |
| `C2B_ASSIGNMENT_MATERIALIZED` | `build-c2b` | 还要通过 task/reference、source/holdout、capacity gate |

任何模块都不得因为 `input_status=formal` 自行把上游状态改成 true。

## 4. Active-time 边界

- PreScreen 永远读取 `active_logs/prescreen` 或 P1 immutable snapshot。
- C1 日常 rehearsal 可读取 `active_logs/new_server`，但只按 C1
  `project + task + worker` context 绑定。
- 正式 C1 必须先把 cutoff 以内事件写入 `active_logs/c1`，并验证
  cutoff-eligible source aggregate 与 frozen aggregate 相同。
- cutoff 后事件只进入 source exclusion count，不进入冻结日志。
- 路径身份也属于合同；相同字节位于另一个目录不能冒充冻结根目录。
- 只有 page gate、annotation identity 和 session 规则均合法的区间进入 primary
  active time。unknown/mixed session 只报告 `duration_not_allocatable`，不伪造秒数。
- 客户端自报的 late-binding alias 不是冻结证据；没有 SHA 绑定 alias registry 时，
  对应 session 保持 `not_evaluable_unfrozen_alias`。JSONL 解析错误单独进入 parse audit。

## 5. C1 证据与 partial worker

`c1_row_analysis_eligibility.csv` 是唯一逐行资格 sidecar，分别拥有：

- process；
- independence；
- Scope/reference；
- Q_GT；
- held-out Geometry LOO；
- structural opportunity。

`closed_partial_usable` 只能由 SHA 绑定的 completion disposition 在支持审查后给出；
collection closure 本身只会把未完成者标为 `closed_partial_insufficient`。
Nonstarter、行政排除和局部 not-evaluable 不记作质量失败。

Project-level independence disposition 绑定整份 project evidence CSV 的真实 SHA，
并逐项核对 project、condition、annotation count、raw export、parent coverage 和
adverse counts。行级 adverse evidence 永远覆盖项目级 clearance。

## 6. C2-B 风险和任务证据

唯一 exposure 为：

```text
risk_design_vector_A
  = [d_model_feat, d_model_feat_local_max, g_model_struct, d_cal_A]
risk_design_score_A
  = frozen scalar derived from that vector
```

stratum、worker slope、bridge maximin 和 simulation 都使用同一个 score/vector。
正式特征必须绑定 checkpoint、config、reference feature、candidate descriptor cache、PCA、whitening、
circular-shift audit、seam audit 和 base-task layout SHA。
Circular/seam audit 对原始参考图执行循环平移后重新运行 `extract_feat()`，不能只滚动
已经提取的 feature；退化 PCA/whitening 不得冻结。C1 risk reference 由当前冻结的
C1 pre-annotation feature table 只读取同一 SHA-bound descriptor cache，不重新推理或接受旁路 CSV 覆盖。circular 使用四相位 orbit aggregation；seam 使用独立的小位移 audit，二者禁止共用一个 audit SHA。
重复执行静态准备时，只有 reference listing、candidate inventory、checkpoint、config、cache 与 audit SHA 全部一致才允许复用；复用路径只刷新 threshold approval 和环境 manifest，不再次运行模型。

`building_id` 只来自经 reviewer/time 审批的 registry，不从文件名或 task 前缀猜测。
`prepare-c2b-static` 预先生成的六份 `*.review_queue.csv` 只暴露待补证据；其 gate 字段必须为空或 `pending_review`，不得作为正式 registry 或 approval 使用。
`c2b_task_eligibility_evidence.csv` 按 `image_id + base_task_id` 直接连接 source split、
future holdout、history、Scope、reference、feature 和 risk。任一证据缺失即排除。

旧 C2 reverse 只保留 `legacy_human_curated_candidate` provenance；它可影响人工审查
优先级，但不能绕过 P1/C1 overlap、holdout 或任何正式 gate。

## 7. 模拟与审批

层级模拟分别消费：

- `between_worker_slope_sd`；
- `outcome_residual_sd`；
- `worker_intercept_sd`；
- `task_sd`；
- `building_sd`；
- `Q_GT_baseline_se`。

缺任一方差时 simulation status 为 `insufficient_variance_parameters`。Building/task
有放回抽样保留 building instance 和 task-slot identity；每个 building 保留本设计原有
task 槽数，只从 selected tasks 抽样。每轮只使用该 task 原有 assignment edges，并按
delivered edges 重建支持、覆盖和图连通性；零交付 task 的 support 明确为 0。

仓库内 `C2B_DESIGN_SELECTION_THRESHOLDS.json` 默认仍为空，这是有意的 fail-closed。
正式选择需要另行审批的数值阈值 manifest，以及一个绑定 candidate manifest SHA、
明确指定非支配 `design_id` 的审批文件。代码不会自动选择最小 connected design。

## 8. 正式运行顺序

1. collection cutoff 时冻结日志到 `active_logs/c1`。
2. 生成 closure manifest，绑定 export aggregate、assignment aggregate 和 active-log
   freeze SHA。
3. 从 immutable raw snapshot 运行 `audit-c1`。
4. 完成人工 disposition 后运行 `finalize-c1`。
5. 准备并冻结 HoHoNet reference cache、C1/C2 building registry、source/holdout/history/
   Scope/reference evidence。
6. 运行 `design-c2b`，只得到 risk freeze 和候选模拟。
7. 审批阈值、design、selected task/reference 和 capacity。
8. 运行 `build-c2b`，只消费冻结候选边，生成正式 assignment、worker distribution 和 Label Studio import。

当前数据仍未 collection close，且正式 feature/building/approval 工件尚未齐全；正确输出
应保持 assignment 为 0。代码已经为正式数据到位后的全量重跑保留唯一入口，不需要修改
raw export 或 C1 标注。

正式派生目录统一使用 `analysis_results/c1_formal_audit_*`、`c2b_design_*` 和
`c2b_build_*`；这些前缀被 Git 忽略，避免阶段输出把下一阶段的 clean-commit gate 弄脏。

Raw snapshot 的 `input_role`、`snapshot_path` 等审计元数据不进入 source aggregate；
closure 绑定的 assignment identity 始终只由规范化 `{path,size,sha256}` 计算。
