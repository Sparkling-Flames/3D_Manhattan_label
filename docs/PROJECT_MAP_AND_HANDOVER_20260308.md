# HoHoNet 项目地图与交接底稿（2026-03-08）

## 文档目的

这份文档不是论文草稿，也不是阶段性 brainstorm，而是当前仓库的“持久上下文”。

作用只有 4 个：

1. 记录仓库里主要目录/脚本各自负责什么。
2. 固定当前 A 线已经澄清的真源关系，避免后续再次把导出字段误当成实验真源。
3. 说明正式入口和历史入口的边界。
4. 给 B / C 提供可交接的输入、约束和未完成事项。

## 更新规则

后续凡是出现以下变化，都应同步更新本文件和 [README_INDEX.md](README_INDEX.md)：

1. 新增正式入口脚本。
2. A 线新增 registry / manifest / frozen truth。
3. B 线主图表口径变化。
4. C 线 trap / embedding manifest schema 变化。
5. export / analysis / active_time 的 provenance 规则变化。

## 一、仓库地图

### 1. 根目录中的主要角色

- `export_label/`
  - Label Studio 导出 JSON 真源目录。
  - 旧累计导出、单次试运行导出、新服务器测试导出都在这里。
- `import_json/`
  - 分池导入 JSON。
  - A 线的 planned split truth 主要来自这里，而不是 export。
- `active_logs/active_logs/`
  - 浏览器脚本记录的 active time JSONL。
  - 比 annotation `lead_time` 更可信。
- `analysis_results/`
  - 各类分析结果、registry 输出、formal 输出落盘目录。
- `tools/`
  - 当前实验在用脚本。
- `tools/official/`
  - 正式运行入口。
- `tools/legacy/`
  - 历史脚本、旧原型、旧入口。
- `docs/`
  - 当前执行文档与审计说明。

### 2. 当前与 A 线最相关的脚本

- [tools/build_task_registry.py](../tools/build_task_registry.py)
  - 从 split/import 侧构建 planned task registry。
  - 这是 planned truth，不包含运行时 `task_id`。
- [tools/build_registry_suite.py](../tools/build_registry_suite.py)
  - A 线 registry 总装脚本。
  - 负责联合 split truth、export truth、active log truth。
- [tools/analyze_quality.py](../tools/analyze_quality.py)
  - 上游分析器。
  - 负责从 export JSON 解析 annotation、计算质量指标、输出质量 CSV。
  - 当前已经补充 provenance 字段，不应再被理解成“纯黑箱分数器”。
- [tools/official/analyze_quality_formal.py](../tools/official/analyze_quality_formal.py)
  - 正式分析入口。
  - 当前优先从 export 内的 `data.dataset_group` 自动推断组别；只有混合导出或缺失字段时才需要 CLI 指定。
- [tools/pooled_qa_plots.py](../tools/pooled_qa_plots.py)
  - B 线 pooled QA 图包入口。
  - 强制把图表定位在 QA / provenance audit，而不是论文主图。
  - 当前默认按 `schema_version` 分层，并对 active time 图继续按 `active_time_source` 分层；组汇总时先按 `dataset_group_source` 可信来源过滤。
- [tools/official/README.md](../tools/official/README.md)
  - 正式入口说明。
- [tools/audit_export_inventory.py](../tools/audit_export_inventory.py)
  - export 真源盘点脚本。
  - 用来冻结“哪些导出只是 pilot / 兼容输入，哪些才可能进入未来正式分析候选”。

## 二、A 线已经冻结的真源关系

### 1. Planned truth 与 runtime truth 不能混

- split/import JSON 是 planned truth。
- export JSON 是 runtime truth。
- 两者必须通过 bridge/join 关联，不能假装是同一张表。

### 2. 当前 A 线 registry 分层

- `task_registry_v2.csv`
  - planned split registry。
  - 关注 `planned_stage / planned_condition / dataset_group / init_type / source_pool`。
- `annotation_registry_v1.csv`
  - annotation 级别运行时真源表。
  - 关注 schema、join 状态、export 来源、condition 来源、dataset_group 来源。
- `compat_registry_v1.csv`
  - legacy 兼容映射层。
- `active_time_registry_v1.csv`
  - active time 来源层。
- `merged_all_v0.csv`
  - join 产物，不是唯一真源。
- `registry_source_manifest_v1.json`
  - 当前 export 输入源清单与新鲜度审计。

### 3. 已明确的 provenance 规则

- `condition`
  - 在 analyze/export 侧属于派生字段。
  - 当前规则：根据 prediction presence 推断 `manual / semi`。
  - 这不是 split 侧 planned truth。
- `dataset_group`
  - 对旧累计导出，常常不是 export 原始字段，而是 CLI 注入或 registry 补充。
  - 对新服务器导出，`task.data.dataset_group` 已经可以直接携带。
- `active_time`
  - 优先取 active log。
  - 无 direct log match 时退回 `lead_time`。
  - 这两者不能混成无来源区分的一列。

## 三、当前已经确认的关键事实

### 1. 3 月 7 日新服务器导出不在旧 filtered cumulative export 中

已确认以下两个文件是新服务器测试导出：

- `export_label/project-11-at-2026-03-07-17-05-1b4f93f3.json`
- `export_label/project-12-at-2026-03-07-17-05-72d96094.json`

它们不包含在此前使用的：

- `analysis_results/rerun_20260308/export_filtered_from_20260101.json`

因此，后续凡是继续使用旧 filtered export 的分析，都必须额外说明“未包含 3 月 7 日新服务器样本”。

### 2. 那 7 条旧 schema 行确实存在

当前累计导出里存在少量 legacy `quality`-only 行。

它们不应直接混入主分析 v2 口径，而应该走 compat 层。

### 3. 当前 export_label 目录内导出都不应直接当正式主分析样本

当前仓库里已有的导出文件虽然对 A 线非常重要，但它们的作用主要是：

1. 验证 runtime/export/schema/provenance 链路是否可审计。
2. 验证 formal wrapper 与上游分析器是否能正确处理新旧 schema。
3. 产出 pilot QA、兼容映射与 exclusion audit。

它们不应直接充当未来正式效应估计的主样本池。

### 4. export inventory 已经成为 A 线正式产物

当前新增的 export 审计输出位于：

- `analysis_results/export_inventory_20260309/export_inventory_v1.csv`
- `analysis_results/export_inventory_20260309/export_inventory_summary_v1.json`
- `analysis_results/export_inventory_20260309/legacy_annotation_audit_v1.csv`

其中：

1. `export_inventory_v1.csv` 记录每份 export 的 schema 概况、run class、formal relevance 与推荐用途。
2. `legacy_annotation_audit_v1.csv` 专门列出 legacy/mixed/malformed annotation，作为 formal exclusion / compat review 候选。

### 3. official 目录是正式入口，不是草稿区

- 正式浏览器脚本在 `tools/official/ls_userscript_annotator.js`
- 正式分析入口在 `tools/official/analyze_quality_formal.py`

旧分叉脚本不应再被当作正式入口使用。

## 四、当前 A 线已完成到哪里

### 已完成

1. 纠正了 A 第一步的语义：`task_registry` 是 planned registry，不是 runtime task table。
2. 建好了 registry suite，并产出 task/annotation/compat/active_time 四层表。
3. 给 registry suite 增加了 export 来源与新鲜度审计。
4. 给 formal 入口增加了 dataset_group 自动推断与 manifest 记录。
5. 给 `analyze_quality.py` 增加了 provenance 字段：
   - `dataset_group_source`
   - `export_dataset_group`
   - `export_source_file`
   - `runtime_condition_source`
   - `active_time_source`
   - `active_time_match_status`
   - `lead_time_seconds`
6. 新增 export inventory 审计脚本与输出，把 pilot / 兼容 / 正式候选边界落成 manifest。

### 当前未完成

1. 还没有把 registry frozen truth 直接回写进 `analyze_quality.py` 的所有分组字段。
2. 还没有把 export inventory 与 registry source manifest 做统一 join。
3. 还没有把 inventory 规则提升成可配置 override，而不是仓库内冻结规则。

## 五、A 向 B 的交接内容

B 当前需要拿到的，不是口头解释，而是下面这些“明确输入”。

### 必交付给 B 的文件

1. `analysis_results/registry_20260308/annotation_registry_v1.csv`
2. `analysis_results/registry_20260308/compat_registry_v1.csv`
3. `analysis_results/registry_20260308/active_time_registry_v1.csv`
4. `analysis_results/registry_20260308/merged_all_v0.csv`
5. `analysis_results/registry_20260308/registry_suite_summary_v1.json`

### 必须口头或文档明确告诉 B 的规则

1. `condition` 不是实验设计真源，而是 export-side derived field。
2. `dataset_group` 在旧数据里可能不是 export 原生字段，要看 `dataset_group_source`。
3. `active_time` 只能在区分 `log / lead_time_fallback` 后再画图。
4. `legacy_quality_only` 行不能和 `v2_structured` 行混着解释成“标注员同口径表现”。
5. `ambiguous / unmatched` task join 不能静默强配进 stage-aware 主分析。

### B 现阶段最适合做的事

1. 先做 pooled QA 图，而不是直接画论文主图。
2. 所有图先按 `schema_version` 分层。
3. active time 相关图必须按 `active_time_source` 分层。
4. 如果要按组汇总，优先用 `dataset_group_source` 过滤出可信行。

## 六、A 向 C 的交接内容

C 需要的核心不是“结果表”，而是 join key 规范和 manifest 约束。

### 必交付给 C 的内容

1. planned key 规范
   - `planned_task_key`
   - `base_task_id`
   - `planned_stage`
   - `planned_condition`
2. runtime join 规范
   - `normalized_title`
   - `matched_registry_uid`
   - `task_join_status`
3. source/provenance 约束
   - `condition` 不能当 frozen truth
   - `dataset_group` 需要保留来源

### 必须告诉 C 的规则

1. trap manifest 和 embedding manifest 都必须能用 `base_task_id` 或 planned key 直接 join。
2. 不要只交说明文档，必须交结构化 csv/json。
3. natural-failure 与 synthetic trap 不能分裂成两套不可 join 的 schema。
4. realized quota 和 planned quota 必须分开。

### C 现阶段最适合做的事

1. 冻结 `trap_manifest_schema_v1`。
2. 输出 `natural_failure_bank_index_v1`。
3. 把 embedding OOD procedure 固定成 manifest-able protocol，而不是口头规则。

## 七、当前建议的协作顺序

1. A 继续把 export_label 全量输入重建成正式 registry source manifest。
2. B 基于 annotation/compat/active_time 三张表做分层 QA 图。
3. C 按 A 的 key 规范输出 trap/embedding manifest 草案。
4. 三方最后再决定正式 `merged_all` 字段，而不是提前围绕大表争论。

## 八、一句话提醒

当前阶段最容易犯的错误，不是代码算错，而是把：

- 导出 JSON 的现状字段

误当成：

- 实验设计的冻结真源字段。

这份文档就是为了持续防止这个错误反复出现。
