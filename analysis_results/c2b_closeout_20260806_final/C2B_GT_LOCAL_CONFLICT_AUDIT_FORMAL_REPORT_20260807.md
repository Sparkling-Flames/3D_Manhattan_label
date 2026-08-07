# C2-B GT 局部冲突自动审查正式报告

## 1. 报告身份

- 报告日期：2026-08-07
- 审查对象：C2-B 唯一图片层的公开 GT 冲突发现机制
- 重点案例：`VFuaQ6m2Qom_ad4c387f8175498491966703c8441e0d`
- Label Studio inner ID：Project 76 = `3416`；Project 77 = `3462`
- 方法合同：`paper_a_method_20260803_v18`
- 方法合同 SHA-256：`694a3126342d7c8de4a5ed788d7ac50b2fec4f104d0b77ace0e604d078c39a87`
- 当前 GT 冲突规则：`gt_conflict_candidate_v1`，状态为 `candidate`，`interpretation_allowed=false`
- 报告性质：正式审计结论与机制整改建议；不是 GT 修订决定，不修改任何 reference、worker score 或正式 eligibility。

## 2. 核心结论

**应当把 GT 冲突自动审查变得更严格。**

但正确的加严方向不是单纯提高整图 IoU 阈值，而是保留现有整图规则，同时新增“局部结构冲突候选筛查层”。3416 证明当前机制存在系统性漏检：局部 GT 错位或冗余角点可以只占很小图像区域，整图 IoU 仍然较高，因此不会触发现有整图级候选规则。

加严后的自动机制只能产生 `pending_manual_review` 候选，不得自动判定 GT 错误、自动改写 GT，或根据工人提交直接修订 reference。

## 3. 3416 的证据链

### 3.1 正式 reference

- 正式公开 GT 来源：`data/mp3d_layout/valid_no_occ/label_cor/VFuaQ6m2Qom_ad4c387f8175498491966703c8441e0d.txt`
- GT SHA-256：`c5d8b41e32472e4d4dbb7150e060cf3f703978d4b58ce407568f7d1f2099ae11`
- GT 包含 16 对 ceiling/floor 角点。
- GT 在 `x=444` 处包含两对不同的 ceiling/floor 角点；`x=432–466`、`x=529–543` 和 `x=972–1001` 区域角点高度密集。
- 现有 reference normalizer 返回 `passed`，只说明其可解析、可配对、可投影，不代表局部房间拓扑正确。

### 3.2 M4.1.3 局部结构诊断

正式 16-pair GT 的本地纹理 3D 诊断得到：

- 16 面墙，无自交；
- 总 wall Manhattan residual：`56.7067°`；
- 总 corner residual：`87.5447°`；
- 最短墙：`0.14984`；
- short wall：2 条；
- wall 7 的方向残差：`23.906°`；
- corner 8 的直角残差：`25.640°`。

这些信号集中在局部密集角点区域。它们不足以自动证明 GT 错误，但足以在不依赖研究者事先声明的情况下，把该图送入人工 GT 审查队列。

### 3.3 工人证据

同一唯一图片在 Project 76 和 Project 77 共形成 20 条 C2-B canonical submission。项目副本不能作为两张不同图片重复计数，但不同工人提交可以作为同一图片的多观察证据。

- 工人提交的角点数分布明显分散：8、10、12、20、24、26；
- Project 77 中 7/10 名工人提交了 24 个角点，即 12 对角点；
- 用户指定复核的 worker 002 与 worker 036 均为 24 个角点，即 12 对角点；
- 工人相对正式 GT 的整图质量仍约为 `0.8639–0.9640`。

因此，3416 的问题不是“工人整体与 GT 完全不重合”，而是“局部拓扑/角点数量存在一致性差异，但整图指标把差异稀释了”。工人证据只能触发审查，不能直接决定 GT 修订内容。

## 4. 为什么现有自动机制漏检

### 4.1 规则粒度不匹配

当前候选规则主要使用：

- dominant cluster 对 GT 的整图 IoU `< 0.50`；
- minority cluster 比 dominant cluster 对 GT 的 IoU 高出 `> 0.05`；
- public GT structurally invalid；
- known reference issue。

3416 的局部异常面积小，整图 IoU 仍高，因而第一项不会触发。它也不是典型的“少数簇比多数簇更接近 GT”，所以第二项不适合捕获该问题。GT 可解析且无自交，因此第三项也不会触发。最终只能依赖研究者提前声明的第四项。

### 4.2 覆盖范围不足

现有 cluster-alignment 自动候选筛查主要落在 C1 candidate screen，并未对 C2-B 选中的 46 张唯一图片形成完整的正式 preflight 队列。3416 的记录明确为 `known_researcher_declared_issue`，不是自动发现结果。

### 4.3 `passed` 状态容易被过度解释

`reference_normalizer_status=passed` 与 `geometry_reference_ready=true` 被下游理解为“GT 没问题”的风险较高。实际上它们只表示机器可消费，不表示局部语义正确。

## 5. 正式整改建议

### 5.1 保留现有整图规则

现有 `0.50` 和 `0.05` 阈值继续作为严重整体冲突候选规则。没有证据支持仅通过提高这两个阈值解决局部漏检；直接提高可能把一般标注噪声大量送入人工队列。

### 5.2 新增局部结构候选层

对每张唯一图片自动计算以下 audit-only 信号：

1. **密集或重复角点信号**：相邻 GT corner 的水平距离异常小、同 x 多对角点、或由此产生极短墙；
2. **局部 Manhattan 异常**：单墙方向残差或单角直角残差明显高，而整图无自交；
3. **局部拓扑覆盖差异**：在固定水平窗口内，GT 角点数与有足够支持的工人主导局部结构明显不同；
4. **多尺度局部一致性**：除整图 IoU 外，报告最差局部窗口的 boundary/occupancy 一致性，防止小区域错误被整图面积平均；
5. **跨来源几何不一致**：正式 `label_cor` 与任务 `vis_3d` 的 pair count 或 geometry hash 不一致时，明确记录 provenance mismatch，禁止把 preview 当作 GT。

3416 至少会被第 1、2、3、5 项送入人工队列。

### 5.3 候选队列的最低支持约束

局部工人共识触发器应满足：

- 按 `base_task_id` 合并跨 Project 副本，只审一次图片；
- 仅使用 canonical-valid、formal-assignment-eligible、非 outside、duplicate-resolved 的工人提交；
- 至少 3 个合格工人对同一局部方向提供证据；
- 工人方向只用于 `pending_manual_review`，不得自动覆写 public GT；
- 自动队列同时展示 GT、局部工人 medoid/consensus、worker 002/036 等指定参考和原图纹理 3D，不只显示整图分数。

具体数值阈值必须在 46 张唯一 C2-B 图片上先运行 dry-run，报告候选数量与假阳性负担，再冻结为新的规则版本；本报告不把未经校准的局部阈值写成正式方法阈值。

## 6. 对 C2-A-RP 的影响

### 6.1 当前状态

3416 已进入 `pending_review`，但当前 C2-B risk-slope evidence 仍包含该图的可评分工人行。只要 3416 的 terminal disposition 未完成，这部分 reference-based evidence 就存在污染风险。

### 6.2 最短安全推进路径

1. 立即对 46 张唯一 C2-B 图片运行一次局部 GT conflict dry-run；
2. 人工只审唯一图片候选，不按 Project 重复审图；
3. 优先完成 3416 的 blinded terminal disposition；
4. 若 3416 GT 保留，则记录 `reviewed_keep_original` 后继续；
5. 若 GT 修订或置为 `reference_unavailable`，则重算受影响的 Q_GT、canonical risk-slope evidence、worker profile 与 C2-A-RP precision/capacity；
6. 在重算或保留决定冻结前，不正式冻结 C2-A-RP Block 1；Block 1 的任务池准备和非正式 capacity rehearsal 可并行进行。

## 7. Protocol guard

- **PASS**：新增规则仅生成审查候选；人工 terminal review 后才决定 reference disposition；按唯一图片去重；不让提交自动改写其自身评分 reference。
- **FAIL**：依据工人多数票自动修改 GT；把局部候选直接当作 GT 错误；追溯性调阈值以得到预期结论；不重算受 reference 变化影响的正式证据。

## 8. 正式结论

当前 GT 冲突自动审查不够严格，具体缺口是缺少局部结构冲突发现，而不是全局 IoU 阈值单纯过低。3416 是已确认的机制漏检案例：局部 GT 与多名工人的局部拓扑存在明显不一致，整图质量指标仍较高，且自动流程未在研究者声明前发现。

因此，正式建议为：**保留现有全局规则，新增唯一图片级、局部窗口级、结构与工人证据联合的 audit-only 候选筛查；在 C2-A-RP Block 1 正式冻结前完成 46 张唯一图片 dry-run 和 3416 terminal review。**
