# HoHoNet 纯净仓库地图

## 文档目标

这份文档只回答一件事：

当前仓库里，哪些目录和文件属于现役主链，它们各自承担什么职责。

这份地图刻意不做这些事：

- 不写时间线
- 不写“几号补充”
- 不写阶段性争论和交接背景
- 不把 legacy / 原型 /临时讨论稿混进正式入口

---

## 一、主链总览

当前仓库的现役主链可以压缩成 8 层：

1. `import_json/`
   - planned import / planned split 真源
2. `tools/prepare_labelstudio_docker.py` 及相关导入脚本
   - 生成可导入 Label Studio 的任务 JSON
3. `tools/official/ls_userscript_annotator.js`
   - 正式标注端浏览器脚本
4. `tools/cors_server.py` + `tools/official/start_log_server.sh`
   - active-time 日志采集链
5. `export_label/`
   - Label Studio 运行时导出真源
6. `tools/analyze_quality.py` + `tools/official/analyze_quality_formal.py`
   - 正式分析链
7. `tools/build_registry_suite.py` 等 registry / audit 脚本
   - planned / runtime / log 的 join 与审计
8. `analysis_results/`
   - 所有分析结果、freeze、manifest、图表与审计产物落盘位置

---

## 二、根目录地图

### 当前需要保留认知的根目录文件

- `README.md`
  - 仓库门面说明
- `QUICK_START.md`
  - 快速进入当前标注与分析链
- `hohonet_env.example`
  - 部署环境变量模板
- `nginx_fixed.conf`
  - 当前最接近正式使用的 Nginx 代理配置参考

### 当前真正重要的根目录目录

- `tools/`
  - 主代码目录
- `tools/official/`
  - 正式运行入口
- `docs/`
  - 正式说明文档
- `import_json/`
  - 导入 JSON 与 planned split
- `export_label/`
  - 导出 JSON 与运行时真源
- `active_logs/`
  - active-time 日志
- `analysis_results/`
  - 分析结果与审计产物
- `tests/`
  - 自动化测试
- `trap集/`
  - trap / manual 候选与人工素材层
- `data/`
  - 数据资产层
- `output/`
  - HoHoNet 推理与中间产物层

### 默认不属于纯净地图主入口的根目录内容

- 原始 HoHoNet 训练/推理旧链
- 各类缓存目录
- 临时输出
- 历史备份配置

---

## 三、`tools/` 地图

### 正式分析与审计主链

- `tools/analyze_quality.py`
  - 上游质量分析主入口
- `tools/official/analyze_quality_formal.py`
  - 正式分析入口
- `tools/build_experiment_visual_audit.py`
  - 每轮实验结果的图表与审计包生成器
- `tools/audit_active_log_quality.py`
  - active-log 质量审计
- `tools/aggregate_analysis.py`
  - 多份分析结果汇总
- `tools/compute_mgeo_diagnostic.py`
  - Paper A / A-line 的 offline audit-only Manhattan geometry diagnostic MVP。读取 JSONL layout geometry，输出可选 `M_geo` sidecar 与 worker-level `J_u` summary；不接入 routing、Label Studio UI、import/export 或正式轮次 artifact contract。
- `tools/manhattan_preview_compat.py`
  - 实验外 realtime Manhattan assistant 的 deterministic 3D preview compatibility 纯函数原型。复刻 current preview 的 percent-to-pixel、`W * 0.05` greedy pairing 与 compatibility failure 判定；不接 Label Studio UI、userscript、routing、formal `g_t` 或 worker-facing experiment。

### 导入与分池主链

- `tools/prepare_labelstudio_docker.py`
  - 生成可导入 Label Studio 的任务 JSON
- `tools/create_labelstudio_split.py`
  - 生成可重复 split
- `tools/create_labelstudio_split_by_outline.py`
  - 按 outline / 协议生成导入分池
- `tools/build_stage1_prescreen_imports.py`
  - Stage 1 / prescreen 导入包构造

### truth / final-gold / freeze 主链

- `tools/extract_truth_layer.py`
  - 从精标导出中抽取 truth layer
- `tools/materialize_final_gold_records.py`
  - 物化 final-gold 记录层
- `tools/build_final_gold_preflight.py`
  - final-gold 接入前检查
- `tools/rebind_stage1_to_final_gold.py`
  - Stage 1 与 final-gold 重绑
- `tools/freeze_prescreen_manual.py`
  - manual freeze
- `tools/freeze_stage1_final_prep.py`
  - Stage 1 final prep freeze
- `tools/revise_semi_selection_v10.py`
  - semi selection 收口

### registry / manifest / round-based 主链

- `tools/build_task_registry.py`
  - planned registry
- `tools/build_registry_suite.py`
  - planned / runtime / log 多层 registry 总装
- `tools/build_c1_assignment_manifest.py`
  - `C1` assignment manifest 生成
- `tools/build_calibration_round_input_manifest.py`
  - 将 planned Stage 2 import JSON 收口为 Calibration round input manifest
- `tools/audit_c1_assignment_manifest.py`
  - 审计 `C1` assignment manifest 的 target/min k、worker 负载与 reserve 排除
- `tools/init_task_risk_rule_manifest.py`
  - 初始化 `task_risk_rule_manifest`
- `tools/materialize_meta_label_consensus_summary.py`
  - 物化 meta-label 共识摘要
- `tools/compute_dt_score.py`
  - `d_t` 最小正式实现
- `tools/compute_g_t_diagnostics.py`
  - `g_t` 标注前结构诊断 dry-run 工具；只用于 exploratory contact sheet 与人工 sanity check 准备，不是正式 routing 入口

### 日志与运行时链路

- `tools/cors_server.py`
  - active-time 接收服务
- `tools/official/start_log_server.sh`
  - 正式日志服务启动脚本
- `tools/split_active_logs.py`
  - active-log 拆分
- `tools/lead_time_stats.py`
  - `lead_time` / `active_time` 对照
- `tools/meta_label_guard.py`
  - 导出字段合规兜底

### Label Studio 前端链路

- `tools/official/ls_userscript_annotator.js`
  - 正式标注员脚本
- `tools/official/ls_userscript_debug.js`
  - 调试脚本
- `tools/label_studio_view_config.xml`
  - 主用 LS 界面配置
- `tools/label_studio_view_config_manual.xml`
  - 手工条件变体
- `tools/vis_3d.html`
  - 3D 预览页面
- `tools/ls_3d_logic.js`
  - 3D 逻辑辅助文件
- `tools/three.min.js`
  - 3D 依赖
- `tools/OrbitControls.js`
  - 3D 交互依赖

### 辅助但仍在用

- `tools/pooled_qa_plots.py`
  - pooled QA 图包
- `tools/analyze_stage_aware.py`
  - stage-aware 原型分析入口
- `tools/save_quality_figures.py`
  - 质量图表生成
- `tools/viz_quality_report.py`
  - 可视化报告
- `tools/benchmark_cost.py`
  - 成本/效率辅助分析
- `tools/diagnose_gating_bias.py`
  - 门控偏差排查

### 默认不属于正式入口

- `tools/legacy/`
- `tools/legacy_server/`
- 旧 notebook
- 研究原型脚本

---

## 四、`tools/official/` 地图

这是“正式运行入口”目录，优先级高于 `tools/` 里的同类文件。

- `tools/official/analyze_quality_formal.py`
  - 正式分析入口
- `tools/official/ls_userscript_annotator.js`
  - 正式标注员脚本
- `tools/official/ls_userscript_debug.js`
  - 调试/巡检脚本
- `tools/official/start_log_server.sh`
  - 正式日志服务入口
- `tools/official/README.md`
  - 正式入口说明

---

## 五、`import_json/` 地图

这个目录只放 planned import 侧文件，不放运行时导出。

### 当前关键目录

- `import_json/stage1_prescreen_final_20260325/`
  - 当前 Stage 1 / prescreen 正式导入包
- `import_json/outline_v2_seed20260228/`
  - outline / seed 固定后的导入集合
- `import_json/mp3d_txt_smoke_test_20260328/`
  - smoke test 导入包

### 当前关键文件类型

- `*_import*.json`
  - 直接导入 Label Studio 的任务 JSON
- `*_summary*.json`
  - 导入包摘要
- `*_report*.json`
  - split / import 报告

### 职责边界

- 这里只描述 planned split / planned task
- 它不是运行时标注真源
- 与 `export_label/` 必须分开理解

---

## 六、`export_label/` 地图

这个目录只放 Label Studio 导出 JSON。

### 当前关键区域

- `export_label/人工精标/`
  - 精标导出与 truth / final-gold 上游
- 根目录下少量 `project-*.json`
  - 仍在被兼容审计、测试或对照链使用
- `export_label/legacy/`
  - 历史导出归档

### 职责边界

- 这里是运行时标注真源
- 它记录“实际发生了什么”
- 它不是 planned split 真源

---

## 七、`active_logs/` 地图

这个目录保存 active-time 日志和相关说明。

- `active_logs/readme.md`
  - 写入路径与归档说明
- `active_logs/*.jsonl`
  - 每日日志
- 各类子目录
  - 可按服务器、脚本版本或轮次拆分

### 职责边界

- 这里只存日志与日志归档
- 它不是质量分析结果目录

---

## 八、`analysis_results/` 地图

这个目录只存分析产物、freeze、registry、图表和审计结果，不存代码。

### 当前主链目录

- `analysis_results/phase1_progress_20260324/`
  - Stage 1 / prescreen 主 freeze 与 binding 审计目录
- `analysis_results/final_gold_layer_20260325/`
  - final-gold 主层
- `analysis_results/truth_layer_extraction_20260324/`
  - truth-layer extraction 输出

### 当前仍需保留认知的支撑目录

- `analysis_results/trap_collection_freeze_20260320/`
  - trap freeze 输出
- `analysis_results/mp3d_txt_smoke_test_20260328/`
  - smoke test 输出
- `analysis_results/pooled_qa/`
  - pooled QA 图包与审计表
- `analysis_results/c_manifests_20260310/`
  - C 线 manifest 支撑输出
- `analysis_results/c_manifests_20260311/`
  - C 线后续支撑输出

### 历史但保留可追溯性的目录

- `analysis_results/selection_freeze_20260317/`
- `analysis_results/stage_aware_analysis_freeze_*`
- `analysis_results/phase1_progress_20260311/`
- `analysis_results/export_inventory_20260309/`
- `analysis_results/registry_20260308/`
- `analysis_results/registry_20260308_march7_check/`
- `analysis_results/rerun_20260308/`

### 已归档区域

- `analysis_results/legacy/`
  - 不再承担当前主链入口职责的历史结果

### 使用约定

- 新结果优先建独立子目录，不要散在根目录
- 主链判断优先看：
  1. `phase1_progress_20260324/`
  2. `final_gold_layer_20260325/`
  3. `truth_layer_extraction_20260324/`
  4. `analysis_results/README.md`

---

## 九、`tests/` 地图

这个目录放当前仍有效的自动化测试。

### 主链关键测试

- `tests/test_audit_active_log_quality.py`
- `tests/test_build_experiment_visual_audit.py`
- `tests/test_build_c1_assignment_manifest.py`
- `tests/test_init_task_risk_rule_manifest.py`
- `tests/test_materialize_meta_label_consensus_summary.py`
- `tests/test_compute_dt_score.py`
- `tests/test_compute_g_t_diagnostics.py`
- `tests/test_compute_mgeo_diagnostic.py`
- `tests/test_manhattan_preview_compat.py`
- `tests/test_extract_truth_layer.py`
- `tests/test_materialize_final_gold_records.py`
- `tests/test_build_final_gold_preflight.py`
- `tests/test_freeze_stage1_final_prep.py`
- `tests/test_rebind_stage1_to_final_gold.py`

### 职责边界

- 这里只放当前还应运行的测试
- 不把已经失效的历史验证脚本当成正式回归依据

---

## 十、`docs/` 地图

`docs/` 只保留当前正式入口、正式参考和必要的操作文档。

### 当前优先入口

- `docs/README_INDEX.md`
  - 文档总索引
- `docs/ROUND_BASED_EXECUTION_PROTOCOL_v1.md`
  - round-based 主协议
- `docs/ROUND_BASED_ASSIGNMENT_SOP_v1.md`
  - round-based 分发 SOP
- `docs/PRESCREEN_STAGE1_OPERATIONAL_GUIDE_20260327.md`
  - prescreen 运行手册
- `docs/P1_PRESCREEN_LAUNCH_CHECKLIST_v1.md`
  - `P1` 启动清单
- `docs/C1_C2_ARTIFACT_FIELD_CONTRACT_v1.md`
  - `C1/C2` 工件字段合同
- `docs/RQ3_MINIMAL_EVIDENCE_CHAIN_CONTRACT_v1.md`
  - `RQ3` 最小证据链合同
- `docs/STAGE3_OOD_PREPARATION_PLAN_v1.md`
  - Stage 3 / Main-Validation / OOD-aware routing 准备计划
- `docs/MANHATTAN_GEOMETRY_TOOL_ROADMAP_v2.md`
  - 当前 Manhattan 工具入口。统一区分 A-line post-hoc audit-only `M_geo` worker-profile diagnostic 与实验外 realtime Manhattan / 3D preview assistant prototype；不写成 protocol core。
- `docs/VIS_3D_GEOMETRY_COMPATIBILITY_SPEC_v1.md`
  - 实验外 realtime Manhattan assistant 的 3D preview 几何兼容性说明。记录 current `vis_3d.html` / `ls_3d_logic.js` / official userscript 的 keypoint、pairing、坐标转换、closure 与 compatibility failure 边界；不修改 worker-facing UI。
- `docs/VIS_3D_GEOMETRY_FIXTURE_PLAN_v1.md`
  - 实验外 realtime Manhattan assistant 的 synthetic fixture 设计。覆盖 clean rectangle、wraparound seam、duplicate / near-duplicate、odd keypoint 与 wrong-order / self-intersection；只服务后续 deterministic compatibility tests，不写 UI，不接正式 routing，不进入 worker-facing experiment。
- `docs/AMBIGUITY_AWARE_HOHONET_EXTENSION_PLAN_v1.md`
  - B-line / Paper B 的 Ambiguity-aware enclosed HoHoNet 研究计划；属于 non-thesis-facing model research planning，不是 A-line protocol amendment，不回流 A-line routing、formal `g_t`、OOS gate、V1 artifact 或生产 Label Studio 导入/界面
- `docs/PAPER_B_MODEL_ARCHITECTURE_SPEC_v1.md`
  - Paper B / non-thesis-facing 的 HoHoNet-AE 架构规划；定义 `P_enc`、`A_amb(x)`、`r_over`、训练目标与禁止输出，不进入 A-line `P1 / C1 / C2 / T1 / V1`
- `docs/ZIND_MAPPING_AUDIT_PROTOCOL_v1.md`
  - Paper B / non-thesis-facing 的 ZInD raw / visible mapping audit 规划；用于判断 `Y_enc`、`Y_ext_ref`、`usable_for_B1Z` 与 `usable_for_B2_aux`，不替代 MP3D / MatterportLayout B0 审计
- `docs/SOP_labelstudio_experiment.md`
  - Label Studio 运行 SOP
- `docs/README_ANNOTATOR.md`
  - 标注员说明
- `docs/手动分析流程.md`
  - 自己拿到数据后手动跑分析的流程
- `docs/ANALYSIS_DATA_FLOW.md`
  - 数据流说明
- `docs/label studio注意事项.md`
  - LS Community Edition 运营边界

### 论文与提纲相关

- `docs/overleaf_project/`
- `docs/overleaf_project_en_elsarticle/`

### 约束目录

- `docs/约束/`
  - 协议、约束、字段边界与方法说明

### 归档目录

- `docs/legacy/`
  - 历史文档归档区
- `docs/legacy/manhattan/`
  - Manhattan v1 legacy reference 归档区，包含原始 diagnostic plan、offline CLI MVP contract 与 export adapter preflight contract。
  - 当前 Manhattan 工具入口是 `docs/MANHATTAN_GEOMETRY_TOOL_ROADMAP_v2.md`；`docs/VIS_3D_GEOMETRY_COMPATIBILITY_SPEC_v1.md` 是当前 3D preview compatibility spec。
  - Legacy v1 不再作为当前 implementation authority。Realtime assistant 仍是实验外 expert-side / lab-side prototype，不是 protocol core，也不是 worker-facing main experiment condition。

---

## 十一、`trap集/` 地图

这个目录是 trap / manual 候选的人工素材层，不是最终 freeze 输出目录。

### 当前需要知道的内容

- 各类 trap family 原始素材
- 说明文件与 inventory
- semi / manual / OOS 候选的人工整理依据

### 职责边界

- 这里是上游人工素材层
- 真正进入 freeze / manifest / import 的结构化输出应看 `analysis_results/` 和 `import_json/`

---

## 十二、哪些内容默认不是正式入口

以下内容即使还在仓库里，也不应默认为“当前该从这里开始”：

- `legacy/` 下任何内容
- 历史 notebook
- 旧服务器脚本
- 临时讨论稿
- 审稿式意见记录
- 原型分析目录
- 只服务于某次一次性试跑的临时产物

---

## 十三、一句话使用规则

如果你只想知道“现在该看哪里”，顺序固定为：

1. `docs/README_INDEX.md`
2. `tools/official/`
3. `import_json/` 与 `export_label/`
4. `analysis_results/`

## Manhattan smoke probe support

- `tools/manhattan_geometry_residual.py`
  - M1 offline residual calculator for preview-compatible Manhattan keypoints. It computes preview geometry stability fields only after current preview compatibility passes; it does not implement snap suggestions, adjustment vectors, UI hooks, routing, formal `g_t`, correctness, or formal `P1/C1/C2/T1/V1` artifact behavior.
- `tests/test_manhattan_geometry_residual.py`
  - Synthetic tests for the M1 residual calculator. The tests verify compatible-only residual computation and exclusion behavior for compatibility failures.
- `tools/manhattan_preview_suggestions.py`
  - M2 preview-only suggestion candidate prototype for experiment-outside Manhattan automation. It emits conservative review prompts from M1 residuals only; it does not emit snap coordinates, adjustment vectors, UI hooks, writeback payloads, routing inputs, formal `g_t`, correctness, or worker-facing hints.
- `tests/test_manhattan_preview_suggestions.py`
  - Synthetic tests for M2 preview-only suggestion candidates and guard fields.
- `tools/probe_manhattan_smoke_export.py`
  - Read-only smoke export probe for the experiment-outside Manhattan toolchain. It summarizes keypoint / scope structure and preview compatibility for 5.6 / 5.7 smoke Label Studio exports; it does not modify export files, connect to `analyze_quality.py`, routing, formal `g_t`, Label Studio UI, or formal `P1/C1/C2/T1/V1` artifact contracts.
- `tests/test_probe_manhattan_smoke_export.py`
  - Synthetic tests for the smoke export probe. The tests do not read real export files and do not validate correctness, routing, UI behavior, or formal round artifacts.

## Agent-ready 入口

- `AGENTS.md`
  - Codex 仓库级常驻上下文入口。
- `docs/AGENT_CONTEXT_INDEX.md`
  - Codex 上下文路由表。
- `docs/agent_playbooks/`
  - Codex 狭义工作流 playbook，覆盖验证、文档同步、协议/统计护栏、CE-only 护栏与交付摘要。
