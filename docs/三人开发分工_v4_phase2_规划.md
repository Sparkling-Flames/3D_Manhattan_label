# 三人开发分工 v4 — Phase 2 修订规划（按当前提纲对齐版）

> 修订日期：2026-03-09  
> 依据：当前中文提纲 `01_研究问题.tex`、`02_方法.tex`、`03_实验设置.tex`、`04_报告与可审计输出.tex`、附录 A1/A4，以及 2026-03-09 A 线 registry/provenance 冻结现状。

---

## 0. Phase 2 的真实目标

Phase 2 不是把 Phase 1 的离线脚本简单“服务化”，也不是追求一个自发进化的黑箱系统。

当前提纲下，Phase 2 的目标应当是：

1. 把 Phase 1 的可审计离线分析链升级为“可部署、可退化、可审计”的在线路由与证据系统。
2. 为 RQ3 提供在线部署或准在线 shadow deployment 证据，而不是只停留在离线 replay。
3. 在任何场景分层、风险分层、序贯增冗余失效时，都能显式退化并留下审计证据，而不是静默失效。

一句话：

Phase 2 的主任务是“把当前已经冻结的规则真正跑起来，并把失败、退化、边界条件都留痕”。

---

## 1. Phase 2 的前置条件

进入 Phase 2 前，至少应满足以下条件：

1. A 线的 planned/runtime/compat/active-time registry 已稳定。
2. export inventory exclusion 规则已能接入 registry suite 或 formal wrapper，而不只是停留在 CSV/JSON 审计层。
3. `condition` 与 `dataset_group` 的 frozen truth 已尽量回写进分析分组逻辑，避免继续依赖 export-side 派生值。
4. C 线的 `d_t`、trap manifest、risk-proxy split 与 replay 契约已与当前提纲对齐。
5. B 线已有 pooled QA、mixed scope、schema_version、active_time_source 的基础审计产物，证明数据链是可用的。

若以上条件不满足，Phase 2 应视为“预备阶段”，先补齐 contract，而不是直接开服务。

---

## 2. 当前提纲对 Phase 2 的关键约束

### 2.1 路由主线

当前 RQ3 主线不是连续 `S_u` 二维散点式路由，而是：

- 全局可靠度主轴：`LCB(r_u)`
- 离散风险层级：`R0/R1/R2/R3`
- 风险签名：`T_u`、`C_u`、`G_u`
- 标注前风险代理：`d_t`、`I_t_OOD`、`g_t`
- 场景特异可靠度：`r_u^(s)` 与显式 activation / degeneration

### 2.2 在线系统的关键要求

在线系统必须满足：

1. 所有路由决策都可追溯到固定版本的规则、阈值、manifest 与输入状态。
2. 当 scene-specific 路由不可用时，必须显式退化到 global `LCB(r_u)`，并记录退化比例。
3. 当任务高风险时，必须记录其来自 `I_t_OOD`、`g_t` 还是两者共同触发。
4. 门控失败、字段缺失、拒收、被拦截提交、`k_max` 达到但未停止等事件全部视为安全性审计证据，而不是噪声。

### 2.3 不能再沿用的旧思路

以下思路不应继续作为 Phase 2 主线：

- 用连续 `S_u` 做主画像横轴
- 用 difficulty 主导 IID/non-IID split
- 用旧版 `GlobalReliability / Stratified` 口径直接代替当前 `Random / Global / Full`
- 让路由服务依赖未冻结的 notebook 私有中间表

---

## 3. Phase 2 推荐工作流

建议把 Phase 2 拆成 6 个工作流，而不是按“一个人一个脚本”拆。

### 工作流 A：Contract 与 State 冻结

目标：先冻结在线系统要读什么、写什么、如何退化。

最小交付：

- `docs/phase2_data_contract.md`
- `docs/phase2_api_contract.yaml`
- `docs/phase2_rule_registry.md`
- `data/contracts/route_rule_manifest.json`

必须明确：

- worker 状态最小字段
- task 风险状态最小字段
- assignment 事件日志 schema
- stop-check 事件日志 schema
- activation / degeneration / fallback 事件码

### 工作流 B：Weighted Consensus Calibration

目标：完成 RQ2b 与 Phase 2 共用的加权共识校准链，但不引入额外自由度。

最小交付：

- `tools/calibration_pipeline.py`
- `data/prescreen/w_max_locked.json`
- `analysis_results/weighted_consensus_calibration/`

要求：

- 严格沿用当前提纲里的 repeated balanced 2-fold 主方案
- 3-fold 只做附录敏感性
- `w_max` 一旦冻结，不得在部署阶段重调

### 工作流 C：Worker Risk Tier Builder

目标：把 `LCB(r_u)`、`T_u`、`C_u`、`G_u`、`R_u^{tier}` 做成稳定的状态构建器，而不是散落在 notebook 里。

最小交付：

- `tools/build_worker_state.py`
- `data/worker/worker_state_snapshot.csv`
- `data/worker/worker_state_manifest.json`

要求：

- 显式输出 `group_rule_version`
- 显式输出 `worker_group_reason`
- 连续 `S_u` 只作为 auxiliary 字段
- 若 bucket 内样本不足，必须输出 `insufficient_support` 而不是猜值

### 工作流 D：Routing Service 与 Shadow Deployment

目标：把离线 replay 升级成可部署的在线服务，同时保留 shadow mode。

最小交付：

- `tools/routing_service/app.py`
- `tools/routing_service/strategies.py`
- `tools/routing_service/db.py`
- `tools/routing_service/replay_bridge.py`
- `docker-compose.routing.yml`

策略只保留：

- `Random`
- `Global`
- `Full`

要求：

- `Full` 必须能记录 scene-specific activated 还是 degenerated
- 高风险任务必须记录触发来源
- `R3` 默认不进主候选池
- shadow deployment 必须能在不影响真实派单的情况下记录策略差异

### 工作流 E：Audit Pipeline 与 Process Evidence

目标：把当前论文第 4 章要求的证据链自动化。

最小交付：

- `tools/auto_audit.py`
- `tools/audit_report_template.html.j2`
- `tools/meta_label_guard.py` 的在线对齐报告
- `analysis_results/online_audit/`

至少覆盖：

- reject rate 与 reason distribution
- Type 4 残余事件
- active_time 数据质量
- activation / degeneration rate
- `k_max` 命中率
- 高风险任务的路由支持率

### 工作流 F：Counterexample 与 OOS Review

目标：把反例与 OOS 复核从“分析后查看”变成“可重复的工单流”。

最小交付：

- `tools/import_counterexample_tasks.py`
- `import_json/counterexample_review_config.xml`
- `tools/counterexample_summary.py`
- `analysis_results/counterexample_review/`

要求：

- 反例候选必须来自冻结规则
- OOS ambiguity 只进入 audit bank，不回流污染主可靠度估计

---

## 4. 4 人开发时的推荐结构

如果到时是 4 人开发，不必把职责细到“每个人写哪个函数”，但建议按下面 4 条主线拆：

1. Contract / Data / Release Gate
2. Calibration / Worker State / Weighted Consensus
3. Routing Service / Deployment / Replay Bridge
4. Audit / Review / Reporting

这样比“一个人同时做算法和审计”更稳，因为：

- contract 和 release gate 需要持续把控字段漂移
- calibration 和 worker state 需要统计一致性
- routing service 需要工程实现与在线退化逻辑
- audit/review 需要保证证据链完整

---

## 5. 建议交付顺序

### 阶段 P2-0：Contract Freeze

先做：

1. phase2 data contract
2. phase2 api contract
3. route rule manifest
4. worker state snapshot schema

完成标准：

- 不再争论字段命名
- 不再争论 fallback 规则
- 不再争论 shadow mode 记录什么

### 阶段 P2-1：Offline-to-Online Bridge

先把离线结果桥接成可服务化输入：

1. worker state builder
2. replay bridge
3. risk-proxy split manifest reader
4. route event logger

完成标准：

- routing service 不再直接读 notebook 中间表
- 所有输入都来自 manifest 或 snapshot

### 阶段 P2-2：Service Skeleton

实现：

1. `/assign`
2. `/stop_check`
3. `/worker_state`
4. 本地 SQLite 状态持久化

完成标准：

- 本地 docker 联调跑通
- 可记录 assignment / stop / degeneration 事件

### 阶段 P2-3：Shadow Deployment

实现：

1. Random / Global / Full 三策略并行 shadow
2. 不影响真实生产派单
3. 可导出 shadow evaluation 结果

完成标准：

- 能形成 RQ3 的部署级证据草稿
- 能比较支持率、退化率、预算效率与失败率

### 阶段 P2-4：Audit & Review Closure

实现：

1. 在线审计报告
2. counterexample review 工单流
3. OOS / ambiguity audit bank

完成标准：

- 第 4 章要求的过程证据可自动产出
- 失败与退化不再靠手工补记

---

## 6. 推荐里程碑

### Milestone 1：规则冻结

时间建议：1 周

完成物：

- API contract
- data contract
- rule manifest
- worker state schema

### Milestone 2：状态构建与离线桥接

时间建议：1 到 2 周

完成物：

- worker state builder
- replay bridge
- risk split reader
- calibration outputs 可直接接入服务

### Milestone 3：本地服务闭环

时间建议：2 周

完成物：

- FastAPI skeleton
- SQLite state
- Random / Global / Full 可调用
- 本地联调通过

### Milestone 4：Shadow Deployment

时间建议：1 到 2 周

完成物：

- shadow mode 运行日志
- deployment audit report
- replay vs online 行为对比

### Milestone 5：论文证据固化

时间建议：1 周

完成物：

- RQ3 deployment evidence pack
- activation / degeneration tables
- budget efficiency summary
- safety audit appendix pack

---

## 7. 关键风险与应对

### 7.1 场景分层静默失效

风险：`r_u^(s)` 支持不足，系统表面上在做场景路由，实际上退化成全局。

应对：

- 强制记录 activation / degeneration
- 若总体 activation rate 低于阈值，主结论降级为 global + stress redundancy

### 7.2 连续 `S_u` 重新污染主线

风险：工程上图省事，又把 `S_u` 当主轴。

应对：

- worker state contract 中明确 `S_u_role=auxiliary_only`
- routing service 不允许 `S_u` 成为唯一主排序字段

### 7.3 风险 split 真源回漂到 difficulty

风险：为了“更好看”，又回到 difficulty 主导 split。

应对：

- split manifest 强制记录 proxy mode
- 若不是 `dt_plus_gt`，必须标记 provisional

### 7.4 在线服务与审计脱节

风险：服务跑了，但没有 reject / degeneration / fallback 证据。

应对：

- 所有关键端点必须写 event log
- audit pipeline 以 event log 为第一输入，而不是事后猜

---

## 8. Phase 2 的完成判据

Phase 2 不应以“服务上线”作为唯一完成标准，而应同时满足：

1. 规则与 contract 已冻结。
2. Random / Global / Full 三策略都能在 shadow mode 下复现。
3. activation / degeneration / fallback / reject / stop 事件都有日志与汇总。
4. 能形成可直接支持 RQ3 的部署级证据包。
5. 当场景分层或高风险路由失效时，系统能显式降级而不是静默失败。

---

## 9. 一句话总结

Phase 2 的正确方向不是“更复杂”，而是“把当前提纲里已经冻结的规则真正工程化，并让每一次退化、失败和边界条件都有证据链”。
