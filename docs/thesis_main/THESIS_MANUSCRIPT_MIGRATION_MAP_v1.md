# Paper A manuscript migration map v1

> 版本日期：2026-07-12
> 状态：旧稿到 Paper A 新主轴的写作施工合同；本次仅建立映射，不执行正文迁移。
> 旧稿真源：本地未纳入 Git 的 `docs/thesis_main/manuscript/overleaf_project/main.tex` 与 `sections/*.tex`。仓库内未发现整篇最新 PDF，因此本表以 TeX 源为可核验真源；PDF 差异须在正文迁移前补核。
> 不回写：本表不修改历史预注册、protocol freeze、assignment、routing、统计执行参数、原始 export/log 或任何分析工件。

最终写作交付以同目录 `THESIS_OUTLINE_AUDITABLE_DUAL_CHAIN_v3.tex` 为 LaTeX outline source；Markdown 文件只承担合同和迁移审计，不替代 LaTeX。

## 0. 迁移原则

- 新章节真源是 `THESIS_OUTLINE_AUDITABLE_DUAL_CHAIN_v3.md`，不是旧 amendment 的追加段落。
- 正文迁移后仍必须保持 `Pilot → PreScreen → Calibration → Main(Test + Validation)` 和 `P1 → C1 → C2 → T1 → V1`。
- 旧稿中与新主轴冲突的内容只能重写、合并、降级或删除，不能通过保留两个并列定义解决。
- `T_u/U_u` 等物理字段保留兼容，但论文展示层改用 `G_u/S_u/C_u/V_u/P_u` 和独立 raw risk-rate。
- 本次交付不声称 Overleaf 已经完成章节迁移。

## 1. 主入口迁移

| 当前旧位置 | 新位置 | 动作 | 说明 |
|---|---|---|---|
| `main.tex` title/abstract | 第1章引言与新摘要 | 重写 | 保留协议、双链路、冻结路由总纲；补充 RQ3a/RQ3b 与 evidence gate。 |
| `main.tex` `\input{01_研究问题}` | 第1章、RQ 合同 | 重写 | 旧 RQ 合并表达拆为 RQ1/RQ2/RQ3a/RQ3b。 |
| `main.tex` `\input{02_方法}` | 第3—5章 | 拆分重组 | 生命周期进入第3章；测量模型进第4章；路由/统计进第5章。 |
| `main.tex` `\input{03_实验设置}` | 第3、5章 | 拆分合并 | 阶段数据流进第3章，统计与比较场进第5章。 |
| `main.tex` `\input{04_报告与可审计输出}` | 第3、6章、附录 | 拆分合并 | evidence gate 进第3章，结果表图进第6章，字段与 provenance 进附录。 |
| `main.tex` `05_标注数据重训练` | 第7.5/附录/未来工作 | 降级 | 不作为 Paper A 主实验或一级贡献。 |
| `main.tex` `06_讨论与局限性` | 第7章 | 保留并重写 | 以双链路边界、support、predictive validity 和支线内容为主。 |
| `main.tex` 注释掉的 07/08 | 第1、7、8章 | 合并吸收 | 审稿问答和贡献总结不再作为独立正文章，内容分散到引言、讨论和结论。 |
| `main.tex` A1—A4 | 附录 | 保留并校正 | 保留冻结合同和统计细节，清除与新主轴冲突的核心贡献表述。 |

## 2. 正文 section 逐项映射

### 2.1 `sections/01_研究问题.tex`

| 旧小节/内容 | 新章节 | 动作 | 处理合同 |
|---|---|---|---|
| `\section{研究问题}` | 第1章 引言 | 重写 | 补研究缺口、三项一级贡献和排除项。 |
| 四阶段与轮次总述 | 第1.3、3.1 | 保留并统一 | 固定 `Pilot→PreScreen→Calibration→Main(Test+Validation)`，注明 P1/C1/C2/T1/V1 freeze。 |
| RQ1 效率 | 第1.4、5.4、6.2 | 保留并收紧 | exact annotation-level owner-valid log primary；task-level/lead_time sensitivity/audit；unknown/parent-derived 排除 primary。 |
| RQ2 质量与纠错 | 第1.4、5.4、6.3 | 重写 | 增加 issue recognition、geometry correction、blind trust、undercoverage、failure-family；weighted consensus 只作消融。 |
| RQ2 weighted consensus | 第4.7、6.6、附录 | 降级 | 删除“核心干预手段”措辞。 |
| RQ3 综合表述 | 第1.4、5.3—5.4 | 拆分 | 明确 RQ3a predictive validity 与 RQ3b routing utility。 |
| scene-specific routing | 第4.4、5.2、6.5 | 保留并收紧 | support 达标启用，否则 Global；主比较来自 Calibration_manual offline replay。 |

### 2.2 `sections/02_方法.tex`

| 旧小节/内容 | 新章节 | 动作 | 处理合同 |
|---|---|---|---|
| 总体框架 | 第3.1 | 重写 | 只描述协议生命周期和冻结点，不提前合并画像与 routing。 |
| 标注对象与元信息 | 第3.2—3.3 | 保留并拆分 | Scope、Difficulty、Model Issue、reference provenance 分开。 |
| Scope/OOS 规则 | 第3.3、4.5、6.3 | 保留并重写 | OOS gate 与 manual geometry reliability 分离；undercoverage 不归 OOS。 |
| Difficulty/Model Issue | 第3.2、4.6 | 保留并限权 | 作为场景/诊断元标签；model_issue 不等于 correction。 |
| `IoU_edit`/Boundary RMSE/RMSE | 第4.1、4.2、6.2—6.3 | 保留并分类 | work proxy、diagnostic geometry、reference gate 分开；不兼容 metric 不合并。 |
| 活跃标注时间 | 第3.4、5.4、6.2 | 保留并收紧 | exact primary、fallback sensitivity/audit、system issue 分离。 |
| 多选标签 consensus | 第4.7、6.6 | 保留并降级 | weighted consensus 仅辅助消融，不是主轴。 |
| `质量与可靠度评估：LOO` | 第4.1、4.3 | 重写 | `R_u` 只由 C1/C2 Calibration_manual；P1/semi/C2b/Main 排除。 |
| 标注者全局可靠度 | 第4.3 | 重写 | 统一为 `R_u`，写出 LCB、CI、support、freeze。 |
| 场景特异可靠度 | 第4.4、5.2 | 保留并收紧 | support-aware `R_{u,s}`，不足退化 Global。 |
| 预筛选与工人画像 | 第3.1、4.5、4.8 | 重写 | P1 画像是 diagnostic/predictive，不是正式 `R_u` 或 routing profile。 |
| 任务路由策略 | 第5章 | 拆分 | Random/Global/Full、offline replay、T1/V1 隔离。 |
| OOS 统计与混合判定 | 第3.3、6.1/6.3 | 保留并重写 | 作为 gate/provenance 和结果审计。 |
| 反例筛选规则 | 第4.7、6.6、附录 | 降级 | 五个一级 family 保留；auto candidate 需 expert review。 |
| P1 post-closeout correction | 第3.5—3.6、4.2、4.8 | 合并 | 独立 evidence-validity gate；不回写任何冻结边界。 |

### 2.3 `sections/03_实验设置.tex`

| 旧小节/内容 | 新章节 | 动作 | 处理合同 |
|---|---|---|---|
| IID/non-IID 应激测试 | 第5.1、5.2、6.5 | 保留并重写 | 标注前代理驱动；后验 difficulty/model_issue 只作诊断。 |
| 条件分组与数据组织 | 第3.2、表1 | 保留并矩阵化 | 阶段、pool、condition、允许用途。 |
| worker mix 控制 | 第3.2、5.4 | 保留 | 不改变 assignment 或 protocol。 |
| 元标签硬校验 | 第3.3、3.5 | 保留并纳入 gate | invalid/missing label 进入 process/audit，不静默丢弃。 |
| RQ1 主终点 | 第5.4、6.2 | 保留 | 遵守既有 paired allocation 与 active-time 统计合同。 |
| RQ2 主终点 | 第5.4、6.3 | 保留并拆分 | quality、correction、failure-family 和 weighted sensitivity。 |
| RQ3 主终点 | 第5.3、5.4、6.4—6.5 | 拆分 | RQ3a 跨阶段 predictive validity；RQ3b offline routing utility。 |
| 多重检验/MDE | 第5.4、附录 | 保留 | 不改 STATISTICAL_ANALYSIS_PLAN 冻结口径。 |

### 2.4 `sections/04_报告与可审计输出.tex`

| 旧小节/内容 | 新章节 | 动作 | 处理合同 |
|---|---|---|---|
| T/I/M 三级口径 | 第3.5、5.4、6.1 | 保留并统一 | 每个 evidence 和结果明确 primary/sensitivity/audit。 |
| Type 4 流程失败 | 第3.5、4.7 | 重写 | process/system issue 分离，不自动转 geometry failure。 |
| 分层报告表 | 第4.5、表2/4/5 | 重构 | 用五维 `D_u` 和 raw rates 分开呈现。 |
| worker-profile sidecar | 第4章、附录 | 保留并引用字段合同 | 物理字段兼容，论文符号统一。 |
| 反例案例库 | 第4.7、6.6 | 降级 | 仅 expert-reviewed final counterexamples 进入结果。 |
| 过程证据与归因链 | 第3.5、6.1 | 提升为 gate | 独立 evidence-validity 小节。 |
| 轮次快照与分发清单 | 第3.1、表1 | 保留 | 不修改 protocol/assignment。 |
| P1 evidence provenance | 第3.5—3.6、4.8 | 合并 | predictive validity 的前置 gate。 |
| 主文图表结构 | 第4节、表/图合同 | 重写 | 采用图1—3、表1—5 固定清单。 |

### 2.5 `sections/05_标注数据重训练.tex`

迁入第7.5、附录或未来工作，动作是**降级**。不得作为 Paper A 一级贡献、主实验、RQ 主证据或 routing 方法。

### 2.6 `sections/06_讨论与局限性.tex`

| 旧小节/内容 | 新章节 | 动作 |
|---|---|---|
| Meta-label 主观性 | 第7.4 | 保留并联系 validity/support。 |
| Type 4 可控性边界 | 第7.4 | 保留，区分 system issue 与 worker process。 |
| 样本量限制 | 第7.4 | 保留，加入 insufficient cell 与 `interpretation_allowed=false`。 |
| 离线路由模拟局限 | 第7.3 | 保留，区分 offline 主比较与 V1 deployment。 |
| Convex Hull 局限 | 第7.5/附录 | 降级，若仍需要则标 audit/sensitivity。 |
| Manhattan 几何诊断 | 第7.5 | 降级，不占主讨论中心。 |
| 基本假设与让步 | 第7.1—7.4 | 重组到证据边界。 |
| 未来工作 | 第7.6 | 保留，加入模型重训练等明确排除项。 |
| P1 amendment 局限 | 第7.2、7.4 | 合并为 post-closeout integrity 与 predictive gate。 |

### 2.7 未激活 section 与附录

| 当前文件 | 新位置 | 动作 |
|---|---|---|
| `07_与审稿员预期批评的预设回答.tex` | 第1.2、7.1—7.4 | 合并；不作为独立正文章。 |
| `08_预期贡献总结.tex` | 第1.3、第8章 | 合并；只保留三项一级贡献。 |
| `A1_扰动算子库.tex` | 附录 | 保留冻结清单；不写成主贡献。 |
| `A2_数据集汇总表.tex` | 附录表1/数据生命周期 | 保留并与阶段—用途矩阵对齐。 |
| `A3_启用门槛保守估计表.tex` | 附录与第4.4 | 保留为 C1 provisional/C2 final 模板；不得暗示已完成证据。 |
| `A4_测度与统计方法速查.tex` | 附录表2/3 | 保留为速查；修正 `T_u/U_u` 方向和 RQ3 拆分。 |

## 3. 必须清除的旧稿冲突

- 加权共识不得再写成“核心干预手段”；
- Manhattan 内容不得占据 Paper A 主讨论；
- P1 amendment 不得以零散段落形式继续叠加；
- 必须有独立 related work、results、conclusion；
- RQ3 必须拆成 predictive validity 与 routing utility；
- `T_u/U_u` 不得与越高越好的 reliability 混用；
- `model_issue` recognition 不得写成 geometry correction；
- `V1` 不得作为 Random/Global/Full 主因果比较场；
- `unknown_annotation`、parent-derived timing、system collection issue 不得进入错误的 primary denominator。

## 4. 正文迁移完成判据

正文真正迁移完成前，必须满足：

1. `main.tex` 章节顺序与新提纲一致；
2. 每章至少有二级标题，每节有问题、证据、primary、sensitivity/audit、禁止主张；
3. 图1—3、表1—5 有对应正文引用和数据来源；
4. `R_u`、`D_u`、raw rates、RQ1/RQ2/RQ3a/RQ3b 方向和阶段边界全局一致；
5. migration map 中所有旧 section 都有动作，不留未解释内容；
6. 另行完成 TeX 编译和最新 PDF 对照；本次文档合同交付不宣称已满足以上正文迁移完成条件。
