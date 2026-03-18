# 给新 Codex 对话的起始说明（2026-03-16）

## 0) 先验约束（必须遵守）

1. 本仓库当前数据均为测试数据，且包含旧版本数据；不得把现有结果表述为正式论文结论闭环。
2. 任何仓库文件发生增删改后，需检查并更新纯净仓库地图（`docs/PROJECT_MAP_CLEAN_20260308.md`）是否需要同步变更。
3. 来自上一轮 `thinking` 或转交文本的信息必须逐条回到仓库文件核验，不能直接当作事实。

---

## 1) 项目定位与固定主线

本项目不是 HoHoNet 训练复现，主线是“可审计的半自动全景布局标注流程”。

正式流程固定为：

`Pilot -> PreScreen -> Calibration -> Main(Test + Validation)`

方法主轴固定为：

1. `PreScreen_manual` expert anchors -> `r_u^(0)`, admission, `w_max`
2. `PreScreen_semi` -> blind-trust / correction-risk evidence (`T_u`)
3. `Calibration_manual` -> `r_u`, `r_u^(s)`, `C_u`, `LCB(r_u)`, core_scene activation rules
4. Calibration 12 张 = common-item anchor，不是 expert-reference anchor
5. scene proxy = difficulty + model_issue consensus
6. embedding = calibration-only `d_t / I_t^{OOD}` reference，不是 scene definition
7. routing = Calibration/Validation 之后的可审计路由

对应依据：`docs/实验集设定与用途.md` 与论文提纲相关文档。

---

## 2) 三条线当前正式状态（切换时口径）

### A 线

- 状态：`partial / blocked`
- `split_alignment_gate`：blocked
- `formal_input_gate`：blocked
- thesis path 不能从 export_label + runtime join 直接启动
- 依据：`docs/提纲一致性审计_20260313.md`

### B 线

- 状态：`partial / formal-prep-freeze-v1`
- 已有：默认 thesis-facing gate + replaceable selection manifest
- freeze v1 产物：
  - `core_scene_contract_v1.csv`
  - `worker_portrait_minimal_v1.csv`
  - `worker_portrait_schema_v1.json`
  - `tim_row_audit.csv`
  - `type4_evidence_v1.csv`
  - `formal_prep_freeze_v1_manifest.json`
- 真实数据 freeze manifest（来自当前仓库产物）：
  - `n_rows=114`
  - `n_tasks=91`
  - `n_workers=4`
- 仍非正式闭环：
  - core_scene 仍是 freeze v1，不可表述为最终冻结契约
  - formal `r_u^(s)` / scene activation / degeneration / route attribution 未完整闭环
  - Type 4 目前是最小 evidence，不是完整过程证据链
- 测试状态：`pytest tests/test_analyze_stage_aware.py -q` = 6 passed

### C 线

- 状态：`partial / closest-to-closure`
- materialization 引擎可执行
- reject lifecycle 尚未正式收口
- 依据：既有审计与 C 线状态文档

---

## 3) 禁止表述（写作与口径红线）

以下表述禁止出现：

1. “A 线已闭环”
2. “B 线 formal analysis 已完成”
3. “scene 由 embedding 聚类定义”
4. “RQ1 active_time 主终点已闭环”
5. “第 4 章正文证据链已全部完成”

原因：提纲一致性审计已明确 Stage 1 配额未对齐、formal thesis input blocked、RQ1 active_time 仍有 fallback 混入风险、第 4 章正文证据链尚未形成。

---

## 4) 必带实情（不能丢）

active_time 仍是混合量：

- `lead_time_fallback = 75`
- `log = 39`

因此 RQ1 主终点不能写成拿到干净主 estimand。

当前 mixed active_time 只能作为 fallback / sensitivity / instrumentation audit，不得写成已闭环主终点。

---

## 5) 推荐任务优先顺序

### 优先路线 A：继续 B 线 formal freeze v2

在 freeze v1 基础上补齐：

1. 更正式的 core_scene 规则冻结
2. `r_u^(s)` / `r_u_s_lcb` / `activation_status` / `degeneration_status`
3. `worker_group` / `worker_group_reason` 规则稳定化
4. Route Attribution 最小正式层：
   - `task_id`
   - `risk_path`
   - `scene_path`
   - `used_scene_specific_reliability`
   - `selected_worker`
   - `decision_reason_chain`
5. Type 4 evidence 从最小链接推进到完整过程证据链

### 备选路线 B：先收 C 线 reject lifecycle

继续推进：

1. `reject_lifecycle.csv`
2. `reject_lifecycle.jsonl`
3. `materialization_summary_v2`
4. `open / resolved / fallback / grandfathered`
5. 明确 thesis family impact

### 备选路线 C：B/C 输入稳定后再做 A 线 hardening

包括：

1. `source_of_truth_matrix`
2. `formal_input_gate`
3. `split_alignment_gate`
4. `scope_integrity_gate`
5. `active_time_estimand_gate`

---

## 6) 新对话优先读取文件

1. `docs/codex转交给thinking.txt`
2. `docs/提纲一致性审计_20260313.md`
3. `docs/实验集设定与用途.md`
4. `docs/B_NEXT_STEPS_20260311.md`
5. `analysis_results/stage_aware_analysis_freeze_v1_20260316/` 下 freeze v1 产物
6. `analysis_results/stage_aware_analysis_freeze_v1_20260316/formal_prep_freeze_v1_manifest.json`

若继续 C 线，再读：

1. `docs/C_MANIFEST_STATUS_20260310.md`
2. `docs/C_TRAP_EXECUTION_STATUS_20260311.md`

注：提纲原文当前以 LaTeX 工程形式维护：中文主稿在 `docs/overleaf_project/`，英文（未完工）在 `docs/overleaf_project_en_elsarticle/`。新对话需要核对提纲时，应优先读取这两个目录而不是查找同名 PDF。
