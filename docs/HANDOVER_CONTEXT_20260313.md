# HoHoNet 最新交接说明（2026-03-13）

## 1. 这份文档的用途

这份文档用于 2026-03-13 的最新交接，目标是让下一位接手者一次性看清三件事：

1. 这个项目现在到底在做什么。
2. 当前已经推进到了什么程度。
3. 下一阶段具体应该做哪些事情。

建议阅读顺序：

1. 先看 [PROJECT_MAP_CLEAN_20260308.md](PROJECT_MAP_CLEAN_20260308.md) 了解当前仓库主链。
2. 再看本文件理解“研究目标、进度状态、后续执行计划”。

---

## 2. 项目是做什么的

### 2.1 当前研究目标

这个项目当前不是在做传统 HoHoNet 训练复现，而是在做“可审计的半自动全景布局标注流程”。

核心问题是：

1. 半自动初始化是否真正降低标注负担与有效时间。
2. 半自动流程在质量与一致性上是否稳定，是否引入新的失败模式。
3. 能否基于 worker 可靠度、场景信息与 OOD 风险代理做更稳健的任务路由。

### 2.2 当前方法主线

当前主线已经固定为：

1. `Pilot -> PreScreen -> Calibration -> Main(Test + Validation)`
2. 区分 planned truth、runtime truth、compat truth、active-time truth。
3. 把 pooled QA、stage-aware formal analysis、compat/provenance audit 分层，而不是混成单一结果表。

对应口径审查见 [PHASE1_PROGRESS_AUDIT_20260311.md](PHASE1_PROGRESS_AUDIT_20260311.md)。

---

## 3. 我目前的进度（截至 2026-03-13）

本节只写“已经落盘、可复核”的事实。

### 3.1 A 线：真源与 registry 层已成型

现状：

1. planned/runtime/compat/active-time registry 已形成可追踪链。
2. export inventory 审计与排除清单已建立。
3. 来源字段与 fallback 语义已明确，避免 condition/source 混讲。

关键产物与入口：

1. [analysis_results/registry_20260308](../analysis_results/registry_20260308)
2. [analysis_results/export_inventory_20260309](../analysis_results/export_inventory_20260309)
3. [tools/build_task_registry.py](../tools/build_task_registry.py)
4. [tools/build_registry_suite.py](../tools/build_registry_suite.py)

### 3.2 B 线：pooled QA 已稳定，主分析尚未闭环

现状：

1. pooled QA 已完成 schema/source/scope/meta-missing 分层审计。
2. 但 stage-aware 主分析（Worker×Scene、工人画像、T/I/M 分层）还未闭环。
3. 当前不应再把旧 split 文件直接当 formal 主分析真源。

关键产物与入口：

1. [docs/B_NEXT_STEPS_20260311.md](B_NEXT_STEPS_20260311.md)
2. [analysis_results/pooled_qa](../analysis_results/pooled_qa)
3. [tools/pooled_qa_plots.py](../tools/pooled_qa_plots.py)

### 3.3 C 线：已从 manifest 层推进到可执行生成层

现状：

1. 已新增扰动算子与 materialization 脚本，不再只停留在 frozen_rule 描述。
2. 已从 `PreScreen_semi` import predictions 实际生成新 bundle。
3. 当前 materialization 结果为：15 行中 13 行 realized，11 行 synthetic 已生成，2 行 reject。
4. 这代表执行层有实质推进，但不代表 revised thesis 的 Stage 1 目标配额已全部对齐。

关键产物与入口：

1. [tools/perturbation_operators.py](../tools/perturbation_operators.py)
2. [tools/materialize_c_traps.py](../tools/materialize_c_traps.py)
3. [analysis_results/c_manifests_20260311/materialization_summary_v1.json](../analysis_results/c_manifests_20260311/materialization_summary_v1.json)
4. [analysis_results/c_manifests_20260311/trap_manifest_materialized_v2.csv](../analysis_results/c_manifests_20260311/trap_manifest_materialized_v2.csv)
5. [docs/C_TRAP_EXECUTION_STATUS_20260311.md](C_TRAP_EXECUTION_STATUS_20260311.md)

### 3.4 文档治理：旧计划文档已归档

现状：

1. 部分过时 markdown 已移入 legacy，不再作为现役入口。
2. txt 记录文件保持未改动。

归档目录：

1. [docs/legacy/plans](legacy/plans)

---

## 4. 当前风险与边界（必须明确）

1. 当前 split 相关文件仍有“旧计划快照”成分，不能直接等同于 revised thesis 的最终样本配额。
2. trap 集当前仍是部分收集状态，不应过度宣称“自然难例已完整覆盖”。
3. C 线虽然已具备生成能力，但仍存在 reject 行，说明执行策略仍需收敛与补强。

---

## 5. 将来要做的事情（可直接执行）

### 5.1 第一优先级（先做）

1. 收敛 C 线 reject 行策略
   - 目标：把当前 2 行 reject 转为可解释的 realized 或可回退策略。
   - 产出：更新 materialized manifest 与 summary，并记录 reject->resolved 机制。

2. 启动 B 线 stage-aware 主分析脚手架
   - 目标：不再只做 pooled QA，开始 Worker×Scene 与工人画像主分析入口。
   - 产出：独立脚本或 notebook 入口，明确输入来自 registry + selection manifest，而非旧 split 直读。

3. 对齐 target-vs-realized 追踪
   - 目标：持续把“论文目标”“当前计划”“当前实现”三层分开汇报。
   - 产出：更新 [analysis_results/phase1_progress_20260311/phase1_target_vs_realized_manifest_v1.json](../analysis_results/phase1_progress_20260311/phase1_target_vs_realized_manifest_v1.json) 的后续版本。

### 5.2 第二优先级（随后）

1. 完善 C 线自然 exemplars 与 synthetic family 覆盖平衡。
2. 在 B 线补齐 Type-4 过程证据图层，避免仅凭汇总指标解释。
3. 最后再做 A 线统一回写，确保 split/registry/formal 字段口径完全一致。

---

## 6. 交接接手建议（操作顺序）

1. 先跑 C：
   - 执行 [tools/materialize_c_traps.py](../tools/materialize_c_traps.py)
   - 检查 [analysis_results/c_manifests_20260311/materialization_summary_v1.json](../analysis_results/c_manifests_20260311/materialization_summary_v1.json)

2. 再开 B：
   - 以 [docs/B_NEXT_STEPS_20260311.md](B_NEXT_STEPS_20260311.md) 为清单搭 stage-aware 入口

3. 最后做全局同步：
   - 更新交接文档
   - 更新仓库地图 [docs/PROJECT_MAP_CLEAN_20260308.md](PROJECT_MAP_CLEAN_20260308.md)

---

## 7. 一句话总结

当前项目已经完成“可审计底座 + C 线可执行生成”的关键跨越，但还未到“样本配额与主分析完全闭环”的状态；下一阶段应优先完成 C 的 reject 收敛与 B 的 stage-aware 主分析落地。
