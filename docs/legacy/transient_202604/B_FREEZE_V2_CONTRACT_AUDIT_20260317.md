# B 线 Freeze v2 Contract Audit（2026-03-17）

## 审计范围

本审计仅评估 `formal-prep-freeze-v2` 的契约完整性，不判定论文主结果闭环。

输入文件：

1. `analysis_results/stage_aware_analysis_freeze_v2_20260317/formal_prep_freeze_v2_manifest.json`
2. `analysis_results/stage_aware_analysis_freeze_v2_20260317/tim_mapping_spec_v1.json`
3. `analysis_results/stage_aware_analysis_freeze_v2_20260317/tim_rule_summary_v1.csv`
4. `analysis_results/stage_aware_analysis_freeze_v2_20260317/worker_portrait_schema_v2.json`
5. `analysis_results/stage_aware_analysis_freeze_v2_20260317/core_scene_contract_v2.csv`
6. `analysis_results/stage_aware_analysis_freeze_v2_20260317/route_candidates_v1.csv`
7. `analysis_results/stage_aware_analysis_freeze_v2_20260317/route_attribution_v1.csv`
8. `analysis_results/stage_aware_analysis_freeze_v2_20260317/type4_evidence_v2.csv`

---

## 核心结论

结论标签：`B: partial / formal-prep-freeze-v2`

可支持表述：

1. B 线已从 freeze v1 推进到 freeze v2。
2. `T/I/M`、`core_scene`、`route attribution`、Type 4 证据链均进入 contract hardening 阶段。
3. route attribution 已具备候选池与可重算排序轨迹。

不可支持表述：

1. B 线 formal analysis 已完成。
2. RQ3 已形成正式 replay 评估闭环。
3. RQ1 主终点口径已修复。
4. 第 4 章正文证据链已闭环。

---

## 四项对照审计

### Q1. `tim_mapping_spec_v1.json` 是否形成可审计口径？

判定：`Pass (contract-level)`

证据：

1. 给出明确 tier 顺序：`M > I > T > outside_T`。
2. 给出 4 条机器可读规则：`gate_excluded`、`m_tier_layout_usable`、`i_tier_in_scope_layout_filtered`、`t_tier_scope_filtered`。
3. `tim_row_audit` 与 `tim_rule_summary_v1.csv` 可对齐重算。
4. 规则覆盖计数与 `tim_scope` 一致：
   - `gate_excluded=75`
   - `i_tier_in_scope_layout_filtered=6`
   - `m_tier_layout_usable=93`
   - `t_tier_scope_filtered=15`
   - 对应 `outside_T=75, I=6, M=93, T=15`

保留：

1. 该口径是 freeze v2 的 contract 层，不等同论文最终透明度口径定稿。

### Q2. `core_scene_contract_v2.csv` 是否已形成稳定 taxonomy 契约？

判定：`Partial`

证据：

1. 新增 `scene_bucket_v2`、`scene_path_template_v2`、strict/weak 分层。
2. strict core scenes = 2：`occlusion|acceptable`、`occlusion|corner_drift`。
3. `occlusion|over_parsing` 与 `reflection|acceptable` 被标记为 weak（当前 `n_workers` 不足）。

保留：

1. 已形成冻结规则雏形，但仍需后续审计确认是否可作为 thesis-facing 最终 taxonomy。

### Q3. `route_candidates_v1 + route_attribution_v1` 是否达到可重算决策解释？

判定：`Pass (replayable explanation-level)`

证据：

1. `route_candidates_v1.csv` 提供候选级轨迹：
   - `candidate_rank`
   - `candidate_pool_size`
   - `reliability_source`
   - `reliability_score`
   - `selection_rule_trace`
2. `route_attribution_v1.csv` 提供任务级胜者证据：
   - `selected_worker`
   - `runner_up_worker`
   - `winner_margin`
   - `decision_reason_chain`
3. 统计：
   - route rows/tasks = `91/91`
   - candidate rows/tasks = `114/91`
   - 有竞争任务数（pool>1）= `16`

保留：

1. 当前是“可重算决策解释层”，不是 RQ3 正式对照 replay 结果层。

### Q4. `type4_evidence_v2.csv` 是否已接入主链？

判定：`Pass (formal-prep evidence-level)`

证据：

1. 同表并列记录 `meta_guard`、`type4`、`tim`、`scene`、`risk_path`。
2. `type4_evidence_v2` 行数 = `114`（与分析样本齐平，不是旁路残表）。
3. 当前 `type4_flag=True` 共 `25` 行，`meta_guard_status=rejected` 共 `23` 行，可追溯。

保留：

1. 该层级仍是 formal-prep 证据链，不等同最终正文级过程证据闭环。

---

## 与提纲/一致性审计的兼容口径

本审计与现有提纲一致性审计兼容，不改变以下事实：

1. A 线仍 `partial / blocked`。
2. B 线仍不能宣称 formal analysis 完成。
3. active_time 仍为混合量，RQ1 主终点不能写已闭环。

---

## 下一步（不扩功能版）

优先建议：

1. 先做 freeze v2.1 对照审计（规则-字段-提纲条款逐条映射）。
2. 再决定进入：
   - B v2.5/v3（taxo + route replay-ready）
   - 或 C 线 reject lifecycle 收口。
