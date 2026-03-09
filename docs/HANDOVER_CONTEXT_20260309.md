# HoHoNet 项目详细交接说明（2026-03-09）

## 文档定位

这份文档的目的不是替代 [PROJECT_MAP_CLEAN_20260308.md](PROJECT_MAP_CLEAN_20260308.md)，而是给“新对话里的新助手”一份更完整的上下文底稿。

建议这样使用：

1. 先读 [PROJECT_MAP_CLEAN_20260308.md](PROJECT_MAP_CLEAN_20260308.md)，快速理解当前仓库主链、正式入口、哪些目录算当前系统的一部分。
2. 再读本文件，理解这个项目到底在研究什么、我们这段时间具体做了哪些工作、dry run 和字段分析已经确认了哪些关键事实、当前 A 线推进到了哪里。

换句话说：

- `PROJECT_MAP_CLEAN` 解决“仓库里什么东西是当前主链”。
- 本文件解决“这条主链现在在做什么、已经知道什么、下一步该怎么接”。

---

## 一、项目是干什么的

### 1.1 项目的研究目标

这个项目的主题，不再是传统意义上的 HoHoNet 训练/推理复现，而是围绕“可审计的半自动全景布局标注流程”展开。

核心问题是：

1. 半自动初始化是否真的能减少标注者的有效工作时间。
2. 半自动流程在质量、一致性、可靠性上是否稳定，是否会暴露新的失败模式。
3. 是否可以基于预筛选、工人画像、场景信息和 OOD 风险代理做更稳健的任务路由。

因此，这个项目现在的重点已经从“模型性能本身”转向：

1. 标注协议设计。
2. 标注数据的字段规范与 provenance。
3. 质量分析链路。
4. A/B/C 三条工程线的可交接产物。

### 1.2 当前方法论主线

当前论文与工程主线已经明确成：

1. 采用 Pilot → PreScreen → Main 的三段式可审计流程。
2. 在进入 Main 前冻结关键规则，而不是边跑边改口径。
3. 区分 planned truth、runtime truth、compat truth、active-time truth。
4. 用 `d_t` 和 `g_t` 做标注前风险代理，用 meta-label 共识做标注后审计和解释。
5. 把 pooled QA、compatibility audit、formal analysis 分开，而不是混成一张“大结果表”。

### 1.3 当前仓库真正服务的业务闭环

当前闭环是：

1. 生成导入任务。
2. 在 Label Studio 中进行 manual / semi 标注。
3. 通过 userscript 和日志服务记录 active time。
4. 从 export 中解析 annotation 与 structured meta-label。
5. 生成质量报告、可靠性报告、registry、manifest、compat 表和审计附件。

当前主链细节请配合 [PROJECT_MAP_CLEAN_20260308.md](PROJECT_MAP_CLEAN_20260308.md) 阅读。

---

## 二、这段时间我们实际做了什么

这部分按“已经做过并落到仓库里的工作”来写，不按聊天顺序写。

### 2.1 重新定义了 A/B/C 的职责边界

一个关键变化是：A 线不再被理解为“立刻写出一张最终主表”，而是负责冻结真源关系与接线规则。

当前分工可概括为：

1. A：冻结真源、建 registry、把 provenance 落到表里。
2. B：做 pooled QA 和 stage-aware 分层图，而不是直接画论文主图。
3. C：把 trap 与 embedding/OOD 过程变成可 join 的 manifest，而不是只停留在说明文档层。

这套分工的依据记录在 [ABC_NEXT_STEPS_20260308.md](ABC_NEXT_STEPS_20260308.md)。

### 2.2 重构了对“真源”的理解

前期最大的认知修正，是把以前容易混在一起的几类“真源”重新拆开：

1. `import_json/` 里的 split/import 文件是 planned truth。
2. `export_label/` 里的 Label Studio 导出是 runtime truth。
3. legacy `quality` 到 v2 字段的映射是 compat truth。
4. `active_logs` 与 `lead_time fallback` 是 active-time provenance truth。

这个修正很关键，因为它直接决定：

1. `condition` 不能再随便拿 export 里推断值当实验真源。
2. `dataset_group` 不能再默认相信 CLI 注入值或下游补值。
3. `merged_all.csv` 只能是 join 产物，不能被当成唯一真源。

### 2.3 建立了 A 线 registry 体系

我们已经在仓库里补齐并跑通过一套 A 线 registry 体系，核心脚本是：

1. [tools/build_task_registry.py](../tools/build_task_registry.py)
2. [tools/build_registry_suite.py](../tools/build_registry_suite.py)

已经明确产出的表包括：

1. planned task registry
2. annotation registry
3. compatibility registry
4. active-time registry
5. merged join 表
6. source manifest / summary JSON

这些工作解决的不是论文最终统计问题，而是“后续所有分析都要站在哪张地板上”的问题。

### 2.4 给分析链补了 provenance 字段

上游分析器 [tools/analyze_quality.py](../tools/analyze_quality.py) 目前已经不再是只吐分数的黑箱。

已经补进去的关键 provenance 字段包括：

1. `dataset_group_source`
2. `export_dataset_group`
3. `export_source_file`
4. `export_source_path`
5. `runtime_condition_source`
6. `active_time_source`
7. `active_time_match_status`
8. `lead_time_seconds`

这一步的意义是：

1. 以后看到某行数据，不用再猜它是旧 export 还是新 export。
2. 不会再把 log-derived active time 和 `lead_time` fallback 混讲。
3. 不会再把 derived runtime condition 误讲成实验设计真源。

### 2.5 正式分析入口已经和上游分层接通

[tools/official/analyze_quality_formal.py](../tools/official/analyze_quality_formal.py) 目前已经补了更清晰的 formal 逻辑：

1. 会调用上游分析器。
2. 会输出 formal CSV 和 formal manifest。
3. 当 export 里只有一个唯一 `dataset_group` 时，可以自动推断，而不是必须手填 CLI 参数。

它的定位已经明确：

1. 它不是实验设计真源的来源。
2. 它是 runtime export 被整理成正式分析口径的 formal wrapper。

### 2.6 建了新的 export inventory 审计层

最新新增的脚本是 [tools/audit_export_inventory.py](../tools/audit_export_inventory.py)。

它的作用是：

1. 扫描 `export_label/` 整个目录。
2. 对每份导出统计 schema 概况、annotation 规模、raw field profile。
3. 标注它是 pilot、legacy compatibility 还是 ad-hoc test。
4. 明确它是否应排除出未来 formal estimand。
5. 产出 legacy exclusion 审计清单。

这一步非常关键，因为它把“这些导出和以后正式分析到底有没有关系”这个问题，从口头判断变成了 manifest 级结论。

---

## 三、前面 dry run 和字段分析到底做了什么

这部分是新对话最需要继承的部分，因为很多关键结论都不是代码里一眼能看出来的，而是通过 dry run 和字段体检确认出来的。

对应复盘文档是 [DRY_RUN_REVIEW_20260308.md](DRY_RUN_REVIEW_20260308.md)。

### 3.1 dry run 的目的不是出论文结果

这次 dry run 的目的不是算论文主结果，而是做底层链路排雷，主要回答 4 类问题：

1. 当前分析脚本能不能稳定处理“跨月累计导出 + pilot 混合口径”。
2. mixed in-scope / OOS 会不会被识别出来。
3. 新服务器导出与旧累计导出的字段层面差异到底在哪里。
4. 接下来 A 线到底应该冻结哪些东西，哪些字段绝不能继续靠 export 原文现状猜。

### 3.2 实际拿来检查的输入

dry run 主要检查了三类输入：

1. 旧累计导出
   - `export_label/project-2-at-2026-02-22-11-22-ee6c4607.json`
2. 新补充单图导出
   - `project-11-at-2026-03-07-17-05-1b4f93f3.json`
   - `project-12-at-2026-03-07-17-05-72d96094.json`
3. active log 原始日志
   - `active_logs/active_logs/active_times_*.jsonl`

### 3.3 mixed scope 检测已经有效存在

通过 dry run 已确认：

1. 当前脚本能够识别“同一任务有的标成 in-scope，有的标成 OOS”的 mixed scope 情形。
2. 这种任务不会只是被打印提醒，而是会被排除出共识与可靠度计算。
3. 旧累计导出的 dry run 中，确实检测到了 4 个 mixed scope multi-annotator tasks。

这个结论很重要，因为它说明：

1. mixed scope 不是未来要发明的新机制。
2. 它已经是现有分析链的一部分。
3. 以后 B 线做图时，应当把这类任务作为审计对象，而不是再怀疑脚本有没有识别到。

### 3.4 旧累计导出不是“整体旧版”，而是“v2 主体 + 少量 legacy 混入”

这是前面字段分析最关键的结论之一。

对旧累计导出做字段体检后，确认：

1. 多数 annotation 已经具有 v2 结构化字段。
2. 但混入了少量 legacy `quality`-only 行。
3. 因此不能把整份导出都当成“旧版不可用”。
4. 更准确的表述是：当前总导出以 v2 为主，但混有少量 legacy schema 行，主分析与兼容分析必须分层处理。

这也是后来 A 线建立 `schema_version` 和 compat 层的直接原因。

### 3.5 那 7 条旧 schema 行不是误判，而是严格口径的结果

前面的检查确认过：

1. 有一批 annotation 的 `result.from_name` 只有 `kp / poly / quality`。
2. 它们没有 `scope / difficulty / model_issue`。
3. 因此在当前 v2-only 的严格解析口径下，会被记成结构化字段缺失，而不是被“聪明地猜回来”。

这不是脚本坏了，而是故意的设计：

1. 不再从 legacy `quality` 反推现代结构化字段。
2. 避免旧字段把当前审计口径污染掉。

### 3.6 新旧导出的差异，核心不在 annotation，而在 task.data

前面一个非常关键的结论是：

1. 新服务器导出与旧累计导出的差异，不主要在 annotation 结构本身。
2. 更关键的差异是 `task.data` 是否已经携带 `dataset_group / init_type / is_anchor / has_expert_ref` 之类实验设计字段。

旧累计导出的问题是：

1. `task.data` 往往只有 `image / title / vis_3d`。
2. 没有实验设计字段。
3. 下游只能通过 prediction presence 派生出 `condition=semi` 之类 convenience 字段。

而新导出中：

1. `task.data.dataset_group` 已经能直接携带。
2. `init_type / is_anchor / has_expert_ref` 也开始进入 runtime task data。

这说明未来 formal pipeline 不能一直依赖“导出后猜字段”，而必须走显式的 registry/manifest。

### 3.7 active_time 当前存在双来源，必须分开讲

dry run 确认了一个很容易误讲的事实：

1. 当前脚本算 `active_time` 时，会先查 active log。
2. 如果没有 direct log match，会退回 annotation 自带的 `lead_time`。

因此：

1. 不是所有 `active_time` 都来自浏览器日志。
2. 新补充单图导出虽然没有 log match，仍然会得到时间值，因为用了 `lead_time fallback`。
3. 这两种来源不能混成一列解释，不然论文里会讲错“有效标注时间”的测量口径。

这也是后来一定要补 `active_time_source` 和 `lead_time_seconds` 的原因。

### 3.8 dry run 对 A 线的直接启发

dry run 最终给 A 线的启发不是“立刻做更多统计图”，而是“先冻结 4 类真源”：

1. Task Registry
2. Annotation Schema Registry
3. Compatibility Registry
4. Active Time Provenance Registry

这四层不稳定，后面所有 formal / stage-aware 分析都会漂。

---

## 四、字段分析后得到的关键信息

下面这些结论，都是后续新对话应该直接继承的，不应该再从头讨论一遍。

### 4.1 `condition` 当前是 derived runtime field，不是实验设计真源

当前已经明确：

1. 在 export/analyze 侧，`condition` 往往来自 prediction presence 的派生。
2. 这只说明运行时任务里有没有 prediction，不等于 planned experimental truth。
3. 因此不能再把 `condition` 当作 split 侧 frozen truth。

一个最新的直接证据来自 export inventory：

1. `project-12` 的 `dataset_group` 是 `PreScreen_manual`。
2. 但它的 `runtime_conditions` 在当前审计输出里仍显示为 `semi`。

这说明：只要下游还继续依赖 derived condition，就有错分风险。

### 4.2 `dataset_group` 在旧导出里经常不是 export 原生字段

这个结论已经稳定：

1. 旧累计导出往往不带 `task.data.dataset_group`。
2. 旧分析里常常是 CLI 注入值或 registry 补值。
3. 新服务器导出才开始更接近“runtime side 也携带实验设计字段”的理想状态。

所以以后看到 `dataset_group`，必须连同 `dataset_group_source` 一起解释。

### 4.3 legacy 行的存在是事实，不是感觉

通过前面的审计，已经确认：

1. 当前 `export_label` 目录中的 pilot / legacy 导出里存在大量 legacy-like annotation。
2. 其中在 `project-2-at-2026-02-22-11-22-ee6c4607.json` 里，目前明确还能识别出 7 条 legacy-like 行。
3. 这些行已经被导出到 exclusion/compat 审计附件里，而不应直接混入 formal 主分析。

### 4.4 active time 要区分 `log` 和 `lead_time_fallback`

这个点已经不是建议，而是当前约束：

1. active log 命中的值更可信。
2. `lead_time` 只是 fallback。
3. B 线画图、论文解释、以及之后 formal 口径都必须区分两者来源。

### 4.5 `merged_all` 不是真源，只是 join 产物

这个是 A 线已经明确冻结下来的工程原则：

1. `merged_all` 不能被理解为唯一 source of truth。
2. 它是 planned/runtime/compat/active-time 多层表 join 出来的结果。
3. 一旦 join 不唯一，就必须显式保留 `ambiguous / unmatched`，而不是静默强配。

---

## 五、pilot 数据和正式分析之间的边界

这是本轮对话里最重要、也最容易被误解的问题之一。

### 5.1 当前 export_label 里的数据对 formal 主结论意味着什么

根据最新的 export inventory 审计结果，当前 `export_label/` 目录里的 9 份导出，全部被归类为：

1. `exclude_from_formal_estimand`

也就是说：

1. 它们不应直接作为未来正式效应估计的主样本池。
2. 不应直接拿它们去支撑论文主结论中的 formal effect claims。

### 5.2 但这些 pilot 数据对 A 线不是“无关”

虽然它们不该进入正式效应估计，但它们对 A 线仍然非常重要，因为它们承担了以下功能：

1. 验证 export schema 是什么样。
2. 验证新旧 schema 混用时脚本是否稳健。
3. 验证 formal wrapper 是否会误读字段。
4. 验证 provenance 字段有没有正确落盘。
5. 给 compat / exclusion 审计提供真实样本。
6. 给 pooled QA 图和 dry run 复盘提供实际输入。

所以更准确的说法是：

1. 它们与 future formal estimand 无关。
2. 但它们与 A 线的“真源冻结、compat 审计、链路验证”高度相关。

### 5.3 当前 export inventory 已经把这个边界固定下来了

新的审计产物已经把这个边界写成文件，而不是继续留在对话里：

1. [analysis_results/export_inventory_20260309/export_inventory_v1.csv](../analysis_results/export_inventory_20260309/export_inventory_v1.csv)
2. [analysis_results/export_inventory_20260309/export_inventory_summary_v1.json](../analysis_results/export_inventory_20260309/export_inventory_summary_v1.json)
3. [analysis_results/export_inventory_20260309/legacy_annotation_audit_v1.csv](../analysis_results/export_inventory_20260309/legacy_annotation_audit_v1.csv)

从现在开始，如果新对话有人再问“这些导出能不能直接拿去做正式分析”，应该直接基于这三份产物回答，而不是重新凭记忆判断。

---

## 六、论文与文档侧最近发生的变化

除了数据链和 A 线工作，这段时间论文提纲和仓库文档也发生了重要变化。

### 6.1 你重新做了纯净仓库地图

你新增或重做的 [PROJECT_MAP_CLEAN_20260308.md](PROJECT_MAP_CLEAN_20260308.md) 很重要，它把当前仓库里真正与服务器标注/分析链相关的入口整理出来了。

这个文档的价值在于：

1. 它刻意不混入老 HoHoNet 训练/推理脚本。
2. 它把 `tools/official/`、`export_label/`、`import_json/`、`active_logs/`、`analysis_results/` 等当前主链梳理清楚了。
3. 它让新对话里的人先明白“当前系统是什么”，再去谈论文和分析。

### 6.2 中文论文提纲对 `d_t` 和 embedding 做了中幅修改

你新的 Overleaf 提纲现在已经更清楚地把 `d_t` 主实现写成：

1. 冻结 HoHoNet shared pre-head latent。
2. 沿宽度做全局池化形成图像级 embedding。
3. 做 L2 归一化。
4. 使用 calibration-only 的 reference pool。
5. 用 kNN-OOD 主实现进行打分。
6. 其他替代实现只放敏感性分析，不进入主实现。

这次修改总体是正向的，因为它：

1. 更接近 canonical kNN-OOD 叙述。
2. 比之前更能 defend。
3. 更符合你现在强调的“预注册、少自由度、可审计”的路线。

### 6.3 当前本地没有 XeLaTeX，不能做编译级验证

这一点也要明确留下：

1. 本轮检查只能验证结构和交叉引用大体自洽。
2. 当前环境没有 XeLaTeX，所以无法在本机完成编译级验证。
3. 如果新对话里有人要继续检查论文提纲，最好补一轮实际编译验证。

---

## 七、当前已经沉淀到仓库里的关键产物

这一节专门列出“已经存在、值得新对话直接复用”的关键文件。

### 7.1 项目理解入口

1. [PROJECT_MAP_CLEAN_20260308.md](PROJECT_MAP_CLEAN_20260308.md)
2. [PROJECT_MAP_AND_HANDOVER_20260308.md](PROJECT_MAP_AND_HANDOVER_20260308.md)
3. [ANALYSIS_DATA_FLOW.md](ANALYSIS_DATA_FLOW.md)
4. 本文件 [HANDOVER_CONTEXT_20260309.md](HANDOVER_CONTEXT_20260309.md)

### 7.2 A 线 registry / provenance 产物

1. `analysis_results/registry_20260308/` 下的多层 registry 产物
2. `analysis_results/registry_20260308_march7_check/` 下的 March 7 新服务器专项检查
3. `analysis_results/formal_march7_check/` 下的 formal wrapper 检查
4. `analysis_results/provenance_check/` 下的 provenance CSV 检查

### 7.3 export inventory 审计产物

1. [analysis_results/export_inventory_20260309/export_inventory_v1.csv](../analysis_results/export_inventory_20260309/export_inventory_v1.csv)
2. [analysis_results/export_inventory_20260309/export_inventory_summary_v1.json](../analysis_results/export_inventory_20260309/export_inventory_summary_v1.json)
3. [analysis_results/export_inventory_20260309/legacy_annotation_audit_v1.csv](../analysis_results/export_inventory_20260309/legacy_annotation_audit_v1.csv)

### 7.4 正式入口文档

1. [tools/official/README.md](../tools/official/README.md)
2. [README_ANNOTATOR.md](README_ANNOTATOR.md)
3. [README_DEVELOPER.md](README_DEVELOPER.md)
4. [SOP_labelstudio_experiment.md](SOP_labelstudio_experiment.md)

---

## 八、如果在新对话里继续推进，最应该先继承什么

给新对话里的助手，最重要的不是“把所有文件都重新读一遍”，而是先继承下面这些硬事实：

1. 这个项目当前的主链是可审计半自动标注系统，不是老 HoHoNet 模型复现工程。
2. `PROJECT_MAP_CLEAN` 是当前主链的目录地图。
3. planned truth 和 runtime truth 已经明确分开，不能再混。
4. `condition` 当前是 derived runtime field，不能直接当实验真源。
5. `dataset_group` 必须看来源，旧数据里经常不是 export 原生字段。
6. `active_time` 必须区分 log 和 `lead_time_fallback`。
7. 当前 `export_label/` 里的 9 份导出全部不应直接进入 future formal estimand。
8. pilot 数据虽然不该做正式效应估计，但对 A 线的链路验证和 compat 审计仍然非常重要。
9. 当前 A 线重点不是继续争论 taxonomy，而是把 provenance、inventory、registry 彻底冻结好。

---

## 九、当前最自然的后续动作

如果新对话继续接这个项目，最自然的后续动作应该是：

1. 把 export inventory 的 `formal_relevance` 规则正式接进 registry suite 或 formal wrapper，让 exclusion 自动化，而不是只停留在 CSV/JSON 审计层。
2. 把 current hard-coded inventory 规则外置成 override manifest，便于未来正式导出加入时不必改 Python 代码。
3. 继续把 registry frozen truth 回写进分析分组逻辑，减少 `condition` 和 `dataset_group` 的派生歧义。
4. 让 B 线基于 `schema_version`、`active_time_source`、`dataset_group_source` 做 pooled QA，而不要直接跑主图。
5. 让 C 线优先交付可 join 的 trap manifest 和 embedding OOD protocol manifest。

---

## 十、一句话总结

这个项目当前最重要的事，不是立刻算出正式论文结果，而是先把：

1. 标注协议
2. 字段语义
3. provenance 规则
4. pilot 与 formal 的边界
5. 多层 registry / manifest

这些基础设施彻底冻结清楚。

只有这些东西站稳了，后面的 formal analysis 才不会建立在一堆“导出里碰巧长这样”的临时现状上。