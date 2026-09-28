# Paper A manuscript migration map v2

> 版本日期：2026-07-16  
> 状态：v4 提纲到当前本地 Overleaf active input chain 的迁移合同；不代表正文、结果或 PDF 已完成。  
> 历史边界：v1 map 保留为上一轮迁移记录；本文件不改写 protocol、assignment、统计计划或原始工件。

## 0. 入口与状态

实际正文真源是 `docs/thesis_main/manuscript/overleaf_project/main.tex` 与被其输入的 section 文件。当前 active chain 已是八章骨架；旧文件仍在目录中但不被 `main.tex` 输入。v4 迁移只改 active chain、附录 A2/A4、审计文档与索引。

## 1. 主入口映射

| 当前位置 | v4 位置 | 动作 | 处理 |
|---|---|---|---|
| `main.tex` title/abstract | 第1章与摘要 | 重写 | 去除未定义风险符号；加入三状态、Geometry LOO、时序路由与 pending 边界 |
| `main.tex` 八个 active `\input` | 第1—8章 | 保留入口、修订正文 | 不改变文件名与章节顺序 |
| `main.tex` appendix inputs | 附录 machine-readable contracts | 保留并扩展 A2/A4 | 不生成虚构 artifact |
| `main.tex` 未输入 legacy section | legacy archive | 暂不改动 | 由 audit 明确 inactive，不进入 PDF |

## 2. Active section 逐项映射

| 旧 active section/小节 | v4 位置 | 动作 | 处理合同 |
|---|---|---|---|
| `01_引言.tex` 的旧总纲、贡献、RQ | 第1章 1.1—1.3 | 重写 | RQ1/RQ2/RQ3，RQ3a/RQ3b 保持三级关系 |
| `02_相关工作.tex` | 第2章 2.1—2.5 | 保留并补齐 | 独立 related work，不承载结果主张 |
| `03_研究协议与数据生命周期.tex` 的阶段/元标签/OOS/P1 | 第3章 3.1—3.6 | 拆分重写 | 增加四类证据、三类共识、独立 validity gate、当前 C1 状态 |
| `04_测量模型与双链路工人画像.tex` 的 consensus/LOO/profile | 第4章 4.1—4.8 | 重写 | 三状态 model、Difficulty/Model Issue、Geometry LOO、`R_u/D_u`、failure-family |
| `05_路由策略与统计分析.tex` 的 routing/replay/统计 | 第5章 5.1—5.6 | 重写 | 初次/追加/冲突/停止时序、四个动态冗余候选参数、cross-fitting |
| `06_实验结果.tex` 的 audit/report 结构 | 第6章 6.1—6.6 | 重写 | 只预定义结果表位；pending/未完成不填数值 |
| `07_讨论与局限.tex` | 第7章 7.1—7.6 | 重写 | 三状态局限、Geometry pending、replay 外部效度、支线降级 |
| `08_结论.tex` | 第8章 8.1—8.3 | 重写 | 按 primary/sensitivity/audit/not_evaluable/unresolved 回答 |
| `A2_数据集汇总表.tex` | 附录数据生命周期 | 保留并校正 | 只更新 accounting 与状态说明 |
| `A4_测度与统计方法速查.tex` | 附录表2/表3/五类 artifact | 重写/扩展 | 移除固定 `k0/kmax` 和二元 consensus 主口径 |

## 3. Legacy section 映射

| 文件 | v4 位置 | 动作 | 说明 |
|---|---|---|---|
| `01_研究问题.tex` | 第1章历史来源 | 暂不改动 | 未被 active chain 输入，保留历史文本 |
| `02_方法.tex` | 第3—5章历史来源 | 暂不改动 | 旧大方法稿，仅作为迁移 provenance |
| `03_实验设置.tex` | 第3/5章历史来源 | 暂不改动 | 未被 active chain 输入 |
| `04_报告与可审计输出.tex` | 第3/6章历史来源 | 暂不改动 | 报告合同已迁入 active 章节 |
| `05_标注数据重训练.tex` | 第7.6/附录 | 暂不改动 | 明确非一级贡献 |
| `06_讨论与局限性.tex` | 第7章历史来源 | 暂不改动 | active `07_讨论与局限.tex` 为正文真源 |
| `07_与审稿员预期批评的预设回答.tex` | 第1/7章历史来源 | 暂不改动 | 不作为独立正文章 |
| `08_预期贡献总结.tex` | 第1/8章历史来源 | 暂不改动 | 不作为独立正文章 |
| `A1_扰动算子库.tex` | 附录 | 保留 | 只记录 planned/realized，不升格为贡献 |
| `A3_启用门槛保守估计表.tex` | 第4/5章附录 | 保留 | C1 provisional/C2 final 模板，不填虚构数值 |

## 4. 旧表述处理清单

| 旧表述 | v4 动作 |
|---|---|
| per-tag binary consensus、未选中=反对、`nselected/ntotal` | active 正文删除；legacy 文件只作历史来源 |
| 单一 consensus confidence = truth probability | 删除；改为 `a/e/u` 重复性和 support |
| `trivial` = 客观无现象 | 改为 worker 报告阈值语义 |
| `model_issue` = correction success | 分为 issue recognition、correction performance、blind trust、over-correction |
| worker-specific LOO 生成不同 scene task set | 改为统一 evidence + LOO pivotality sidecar |
| convex-hull medoid 为完整布局共识 | 降级为 legacy agreement proxy |
| fixed low-risk `k0=1`、唯一 `kmax=5` | 改为四个 C2 前 candidate 参数；不回写 V1 freeze |
| 所有 cap task 自动专家裁决 | 改为 stop/escalation/unresolved 合同与专家成本报告 |
| 最终 crowd scene 回填首次 routing | 删除；首次只读 pre-annotation evidence |
| weighted consensus 主方法 | 降级为 auxiliary/ablation |
| `B_u/F_u/Q_u` 出现在摘要 | 摘要改写为具体风险名称；方法中若保留必须先定义 |
| 三状态/ seam-aware/online routing table 已实现 | 标记 `pending implementation`，结果不填数值 |

## 5. 迁移完成判据

迁移完成仅指：v4 outline、active LaTeX source、map/audit 与索引一致；不等于 C1 closeout、C2 freeze、三状态 sidecar、seam-aware metric、正式 RQ3a 或在线 routing 已完成。

## 6. 动作词汇的审计含义

- **保留**：保持入口、阶段职责或历史 artifact alias，但按 v4 语义解释。
- **重写**：主动正文用 v4 的章节和 estimand 重新组织，旧句不作为正文真源。
- **合并**：旧 `01_研究问题.tex`、`02_方法.tex`、`03_实验设置.tex` 与 `04_报告与可审计输出.tex` 的可用材料分别合并进第 1、3、4、5、6 章，不保留旧五章结构。
- **降级到附录**：A-line Manhattan、weighted consensus、counterexample bank、历史 medoid 及字段全集只保留为辅助、审计或 machine-readable contract，不作为一级贡献或主终点。
- **删除（active claim）**：主动正文删除二元 per-tag majority、固定 `k0/kmax`、后见之明首次路由、cap 后必然专家裁决及未定义风险符号；旧文件中的文字不做物理删除，以免覆盖历史审计。
- **暂不改动**：未被 `main.tex` 输入的 legacy section、冻结 protocol/SOP、assignment、C1 XML、代码、测试、数据与原始 artifact 均不改写。

## 7. 本轮定向收口映射（审查意见 v2）

| 审查项 | active 位置 | v4/合同处理 | 状态 |
|---|---|---|---|
| active-time duplicate/revision | 第3.4节、第4章 active-time 小节、A4 字段索引 | 绑定 `project_id + ls_runtime_task_id + worker_id + annotation_id`；多 annotation 进入 review；增加 selected/disposition/adjudication 字段；geometry/quality/time 同一 identity | 重写 |
| 同时间戳原子批次 | 第5.2、5.5、A4 routing evidence | simultaneous atomic batch、tie policy、pre/post snapshot、升序/降序/random sensitivity | 重写 |
| terminal 后证据 | 第5.5、第7.5、A4 | `post_terminal_audit_only=true`，不改变 worker、k、stop、aggregate、policy outcome | 新增 |
| stop gate 冲突 | 第5.3、第7.5、A4 | family-specific stop matrix；移除全局 Geometry gate | 重写 |
| 实现状态 | 摘要、第1.3、第4.6、第7.6、A4 | 统一三态：code/scaffold、candidate dry-run、formal thesis artifact | 统一 |
| trivial 语义 | 第3.4、第4.3 | explicit root negative + 报告阈值定义，不等于物理不存在 | 重写 |
| R_u support/bootstrap/LOO | 第4.7、A4、字段合同 | peer support=2 保持；`N_{R,min}` prospective pending；当前 medoid/排除规则、bootstrap 参数及 failure→not_evaluable 写清 | 补齐 |
| Geometry 层级 | 第4.6、A4 | seam-aware 为 `G_u` diagnostic/alternative components；无融合规则则不形成 integrated `G_u^{C2}` | 重写 |
| 两类 reference | 第3.4、4.7、A2/A4 | task outcome reference 与 worker-specific LOO reference 分列字段与 SHA | 拆分 |
| P1/C1/C2 命名 | 第1章、表1、A2/A4 | `D_u^{P1}`、`D_u^{C1,provisional}`、`D_u^{C2,frozen}`；C1/C2 表行拆开 | 修正 |
| RQ3a 降级 | 引言、第5.6、第6.4 | Scope/undercoverage predictor-target 记 exploratory/pending，不进入三组 primary | 新增 |
| RQ1/RQ2 统计边界 | 第5.6、A4、audit | 复用 SAP v1；缺失 MDE/quality floor/multiplicity 的项标 prospective pending，不覆写 SAP | 澄清 |
| artifact index | A2/A4 | 从“五类”改为完整 evidence-chain index，含 registry、review、R_u manifest、LOO reference、formal state、closeout | 扩展 |
| 排版/引用 | main、A1、A3、refs.bib | 默认 A4；acceptable 移出 perturbation operator；修正 support 交叉引用；替换未核验占位文献 | 修正 |

本轮仍不修改未被 `main.tex` 输入的 legacy section；其中残留旧术语只在 audit 中登记为 inactive/history，不作为 active manuscript claim。
