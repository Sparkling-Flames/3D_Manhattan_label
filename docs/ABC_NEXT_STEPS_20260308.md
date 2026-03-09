# A / B / C 后续事项（2026-03-08 更新版）

## 总原则

这次更新后的分工，不再把“冻结契约”理解为一次性拍死最终主表，而是分成：

1. 冻结实验真源
2. 冻结 annotation schema 真源
3. 冻结兼容映射真源
4. 冻结 trap / embedding 生成规则

在你当前仓库状态下，这比“先写一张最终 merged_all.csv 规范”更稳，也更符合 pilot 到正式实验的演进方式。

## Dev A

### A 当前最该做的事

A 现在最该做的是接管“真源冻结与接线”，而不是继续讨论 taxonomy 本身。

### A 的具体动作

1. 建 `Task Registry`
   - 以 `import_json/outline_v2_seed20260228/` 下的分池文件为主真源。
   - 这里先冻结的是 `planned task registry`，不是运行时导出表。
   - split 真源阶段统一汇总：`planned_task_key/base_task_id/image/title/planned_stage/dataset_group/condition/is_anchor/has_expert_ref/init_type/source_pool`。
   - `task_id` 属于 Label Studio 运行时字段，需在 export 侧通过 bridge 补上，而不是在 split 侧强行假定。
   - 目的：让 `dataset_group` 和 `condition` 不再依赖命令行注入或 prediction 自动推断，同时把 planned key 与 runtime key 分开管理。

2. 建 `Annotation Schema Registry`
   - 从累计导出 JSON 中逐条抽 annotation。
   - 为每条记录标注：
     - `schema_version`: `v2_structured / legacy_quality_only / mixed / malformed`
     - `annotation_created_at`
     - `raw_field_profile`
   - 目的：把 pilot 的“故意缺失”和历史旧字段区别开。

3. 建 `Compatibility Registry`
   - 专门登记 legacy 行如何被兼容映射。
   - 至少保留：
     - `scope_source`
     - `difficulty_source`
     - `model_issue_source`
     - `compat_rule_version`
     - `compat_review_needed`
   - 目的：主分析保持 v2 严格口径，兼容分析单独留痕。

4. 建 `Active Time Provenance Registry`
   - 当前脚本会把 `active_logs` 与 `lead_time fallback` 混成一个 `active_time`。
   - A 需要把来源拆开，至少记录：
     - `active_time_value`
     - `active_time_source` (`log` / `lead_time_fallback` / `missing`)
     - `active_time_source_file`
     - `active_time_match_status`
   - 目的：后续 active_time 图表和论文口径可审计。

5. 让 `merged_all.csv` 成为 join 产物，不是唯一真源
   - `merged_all` 由上面几层 registry/manifest join 得到。
   - join 不能静默强配；凡是 split 侧与 export 侧无法唯一对应的任务，必须显式保留 `ambiguous / unmatched` 状态。
   - A 的职责不是“手写一张万能总表”，而是设计 join 关系和产出规则。

### A 本周交付建议

1. 一份 `task_registry.csv`
2. 一份 `annotation_registry.csv`
3. 一份 `compat_registry.csv`
4. 一份 `active_time_registry.csv`
5. 一份最小 `merged_all_v0.csv`，哪怕字段还不全，也必须能追溯来源

## Dev B

### B 当前最该做的事

B 现在最该做的是把图表口径拆成“pooled QA”与“stage-aware analysis”两层，不再默认所有结果都能直接进论文主图。

### B 的具体动作

1. 先基于当前累计导出做 pooled QA 图骨架
   - active time 分布
   - reject reason 分布
   - mixed scope task 列表
   - annotator profile 粗图

2. 图表必须按 `schema_version` 分层
   - 至少区分：
     - `v2_structured`
     - `legacy_quality_only`
   - 目的：避免把旧字段兼容问题画成“标注员违规”。

3. 不把当前累计导出的 `condition` 和 `dataset_group` 直接当论文真源
   - 在 A 的 `task_registry` 接上前，只能当 QA 标签，不是最终实验分组标签。

4. 准备两套 notebook / script 入口
   - 一套给 pooled QA
   - 一套给 stage-aware 主分析

### B 本周交付建议

1. `pooled_qa` 图表骨架
2. `schema_version` 分层统计表
3. mixed scope 审计表
4. active_time 来源拆分后的展示预案

## Dev C

### C 当前最该做的事

C 现在最该做的是把“后置依赖”工程化成可 join 的 manifest，而不是继续停留在素材层或说明文档层。

### C 的具体动作

1. 冻结 `Trap Manifest Schema`
   - 每条 semi trap 至少包含：
     - `base_task_id`
     - `source_type` (`synthetic` / `natural_failure`)
     - `operator_id`
     - `seed`
     - `lambda_level`
     - `planned_quota`
     - `realized_quota`
   - 目的：trap bank 可直接回写到主表。

2. 把 natural-failure 与 synthetic 统一到同一 schema
   - 不再分别放在“素材目录”和“算子计划”里各自维护。

3. 冻结 embedding OOD procedure，而不是立刻冻结 IID/OOD 名单
   - 先锁：
     - `ckpt`
     - feature layer
     - reference pool
     - K
     - threshold rule
     - seed
   - 等 `d_t` 真算出来，再导出 realized split。

4. 所有交付物都要能与 A 的 registry 直接 join
   - 交付的是结构化 csv/json manifest，不是纯说明文档。

### C 本周交付建议

1. `trap_manifest_schema_v1`
2. `natural_failure_bank_index_v1`
3. `embedding_ood_protocol_v1`
4. 一份可被 A 直接 join 的 `trap_manifest_draft.csv` 或 `json`

## 三人协作顺序（建议）

1. A 先把 task / annotation / compat / active-time 四层 registry 起出来。
2. C 按 A 的 key 规范输出 trap 与 embedding manifest 草案。
3. B 基于 registry 先做 pooled QA 图，再切换到 stage-aware 图。
4. 三人最后再一起定义 `merged_all` 的正式 join 输出，而不是一开始就围绕最终大表争论字段。

## 一句话总结

- A：冻结真源与接线
- B：分层展示与审计图
- C：把 trap 与 embedding 变成可 join manifest

当前阶段最忌讳的，是继续把“导出 JSON 的现状字段”误当成“实验设计真源字段”。
