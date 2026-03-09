# Dry Run 复盘与字段检查（2026-03-08）

## 1. 本次复盘的目标

本次复盘不是为了给出论文最终主结果，而是为了回答 4 个更基础的问题：

1. 当前分析脚本能否稳定处理“跨月累计导出 + pilot 混合口径”数据。
2. 当前脚本能否识别同一任务被不同标注者同时标成 in-scope 和 OOS。
3. 新补充导出的单图 semi/manual JSON 与旧累计导出在字段层面有何不同。
4. 下一步 A 应冻结什么，哪些字段不能再依赖导出原文推断。

## 2. 本次实际使用的输入

### 2.1 旧累计导出

- `export_label/project-2-at-2026-02-22-11-22-ee6c4607.json`
- 这是一个跨月累计导出，包含 220 条有效 annotation。
- 标注时间分布：
  - 2025-12：31 条
  - 2026-01：56 条
  - 2026-02：133 条

### 2.2 新补充单图导出

- `export_label/project-11-at-2026-03-07-17-05-1b4f93f3.json`
  - `PreScreen_semi`，带 prediction
- `export_label/project-12-at-2026-03-07-17-05-72d96094.json`
  - `PreScreen_manual`，不带 prediction

### 2.3 active logs

- `active_logs/active_logs/active_times_*.jsonl`
- 本地可见 16 份日志文件

## 3. 当前脚本能否检测 mixed in-scope / OOS

可以，且不只是“打印提醒”，还会把这类任务排除出共识与可靠度计算。

### 3.1 检测逻辑

在解析每条 annotation 时，脚本会按 task 记录：

- `n_in_scope`
- `n_oos`
- `n_unknown`

代码位置：

- `tools/analyze_quality.py` 中记录 scope 投票：[tools/analyze_quality.py](tools/analyze_quality.py#L1249)
- summary 输出 mixed-scope task 数量：[tools/analyze_quality.py](tools/analyze_quality.py#L1736)

### 3.2 后处理逻辑

在做 consensus 和 `r_u` 之前，脚本会直接跳过：

- mixed scope 任务
- 含 unknown scope 的任务

代码位置：

- 排除 mixed/unknown 任务：[tools/analyze_quality.py](tools/analyze_quality.py#L1559)

### 3.3 本次 dry run 的实际输出

针对旧累计导出，脚本输出：

- `Tasks with mixed scope votes: 4`
- `Mixed among multi-annotator tasks: 4/23`
- 示例 task：`474, 498, 500, 501`

因此，这一项当前是“已具备检测与排除能力”的，不需要再补一个新机制。

## 4. 旧累计导出的字段体检

## 4.1 总体结论

这份旧累计导出不是“整体旧版”，而是“以 v2 结构化字段为主，夹少量 legacy 记录”。

220 条 annotation 中：

- 有 `scope`：213 条
- 有 `difficulty`：181 条
- 有 `model_issue`：182 条
- 仅有旧 `quality` 字段：7 条

因此，不能把这份导出整体视为“旧版不能用”；更准确的说法是：

> 当前总导出以 v2 为主，但确实混入了少量旧 schema 行，主分析与兼容分析必须分层处理。

## 4.2 那 7 条旧行是什么

这 7 条行都来自同一位标注者（user 2），创建时间是 2026-01-09 到 2026-01-12，原始 `result.from_name` 只有：

- `kp`
- `poly`
- `quality`

没有：

- `scope`
- `difficulty`
- `model_issue`

对应 `quality` 值为：

- `normal` × 5
- `fail` × 1
- `split_level` × 1

这说明当前 dry run 里看到的：

- `ScopeMissing: 7`
- `DiffMissing: 39`

其中一部分并不是“当前 pilot 标注员乱填”，而是旧 schema 的历史遗留。

## 4.3 这不是当前脚本误判，而是刻意的严格口径

`parse_quality_flags_v2` 当前明确是 v2-only：

- 不再从旧 `quality` 反推 `scope`
- 缺结构化字段时直接记为 unknown / missing

原因是之前已经修过一次“scope_missing 被 legacy quality 污染”的问题。

可参见：

- `docs/legacy/handover_2026Q1/HANDOVER_2026-01-18.md`

所以这次 dry run 里那 7 条 old row 被记为 `scope_missing=True`，是符合当前审计原则的，不是脚本坏了。

## 5. condition 和 dataset_group 的再认识

## 5.1 旧累计导出

旧累计导出的 `task.data` 只有：

- `image`
- `title`
- `vis_3d`

不包含：

- `dataset_group`
- `condition`
- `is_anchor`
- `has_expert_ref`
- `init_type`

同时，220 条 annotation 对应的任务都带 `predictions`，因此分析脚本会把它们全部判成 `condition=semi`。

这意味着：

1. `condition` 在旧累计导出里不是实验真源字段。
2. `dataset_group` 在本次 dry run 中也是命令行注入值，不是导出原文值。

## 5.2 新补充导出

### 新 semi 单图导出

`export_label/project-11-at-2026-03-07-17-05-1b4f93f3.json` 的 `data` 已经带：

- `dataset_group`
- `init_type`

且任务顶层与 annotation 内都带 prediction，对应 `condition=semi` 是合理的。

### 新 manual 单图导出

`export_label/project-12-at-2026-03-07-17-05-72d96094.json` 的 `data` 已经带：

- `dataset_group`
- `is_anchor`
- `has_expert_ref`

且不带 prediction，对应 `condition=manual` 是合理的。

### 本次对比结论

新导出与旧累计导出的关键差异，不在 annotation 结构，而在 `task.data` 是否已经携带实验设计字段。

这也是下一步 A 必须从“导出后猜字段”转向“显式冻结 registry/manifest”的根本原因。

## 6. active_time 的重要说明

你补充的两个新单图导出虽然“没有 active log 数据”，但脚本仍然给出了 `active_time`，原因是当前逻辑是：

1. 先查 `active_logs`
2. 若没匹配到，再回退到 annotation 的 `lead_time`

代码位置：

- [tools/analyze_quality.py](tools/analyze_quality.py#L1251)

因此：

- `project-11` 的 `active_time = 576.512`
- `project-12` 的 `active_time = 142.342`

这里的值不是服务端 active log 回填，而是 Label Studio annotation 自带的 `lead_time` 回退值。

这件事必须在后续契约里显式区分，否则容易把：

- “active log instrumented active time”

和：

- “annotation lead_time fallback”

混为一谈。

## 7. 本次 dry run 的结果应该如何解释

## 7.1 已经可以确认的结论

1. 当前链路是能跑通的。
2. mixed scope 检测与排除逻辑是有效的。
3. 总导出是“v2 主体 + 少量旧 schema 混入”，不是整体不可用。
4. 旧字段行对 top-line IoU 影响不大，但会影响审计口径解释。
5. 新导出比旧累计导出更接近你真正想要的“stage-aware frozen input”。

## 7.2 不能直接下的结论

1. 不能把当前累计导出的 `condition=semi` 当成论文级实验真源。
2. 不能把 `dataset_group=命令行注入值` 当成已经冻结的实验标签。
3. 不能把 `meta_guard` 的总 reject rate 直接当作 protocol violation rate，因为里面混有 legacy 行和 pilot 阶段的故意缺失。

## 8. 本次额外单图验证结果

### 8.1 新 semi 单图

文件：`project-11-at-2026-03-07-17-05-1b4f93f3.json`

解析结果：

- `condition=semi`
- `scope=normal`
- `difficulty=occlusion`
- `model_issue=corner_drift`
- `active_time=576.512`（来自 `lead_time` fallback）

说明：字段解析正常，prediction 与 structured meta-label 都被正确读取。

### 8.2 新 manual 单图

文件：`project-12-at-2026-03-07-17-05-72d96094.json`

解析结果：

- `condition=manual`
- `scope=normal`
- `difficulty=trivial`
- `model_issue` 为空，且 `model_issue_required=False`
- `active_time=142.342`（来自 `lead_time` fallback）

说明：manual 条件下不要求 `model_issue`，当前逻辑是对的；由于没有 prediction，corner IoU 为 0 也是预期结果，不是字段错误。

## 9. 对 A 的直接启发

当前最需要冻结的，不是单张大表的最终内容，而是 4 类真源：

1. `Task Registry`
   - stage / dataset_group / condition / anchor / init_type / expert_ref
2. `Annotation Schema Registry`
   - annotation 属于 v2 还是 legacy
3. `Compatibility Registry`
   - 哪些行被 legacy 兼容映射过，映射规则版本是什么
4. `Active Time Provenance Registry`
   - 当前 active_time 是来自日志还是 lead_time fallback

只有先把这 4 层冻结清楚，后面的 `merged_all.csv` 才能真正成为可审计分析表。
