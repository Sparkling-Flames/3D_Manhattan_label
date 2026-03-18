# HOHONET 预屏到校准到派单的权威审稿人分析与当前落地一致性审查

## 执行摘要

**最关键可执行建议（按优先级）**

- **P0：把“专家锚点（expert anchors）”从概念升级为“统计上可防循环论证的评估协议”**：至少拆成 *calibration anchors* 与 *evaluation anchors* 两套互斥集合；任何用于估计 worker/scene 参数、设定阈值、调参（含聚类数/距离度量/过滤规则）的锚点，都不得再用于最终论文主结果评估（否则会形成隐性信息泄漏）。这类“专家验证/主动获取真值”的做法在学习自众包与任务依赖偏差研究里属于标准审稿关注点。citeturn2search0turn14search44turn0search2  
- **P0：不要在 PreScreen 阶段宣称“场景特异可靠性已被估计”**：PreScreen 的专家锚点更适合“全局可靠性 + 粗粒度偏差嗅探 + 任务/场景分层抽样框架”，而“场景特异可靠性（scene-conditional reliability）”应推迟到 Calibration，在有足够每场景观测后用“分层/部分池化（hierarchical partial pooling）”估计。否则容易出现高方差、后验过拟合与不可复现的审稿风险。citeturn0search2turn0search7turn1search5turn14search44  
- **P0：场景定义（scene）建议采用“契约优先的混合方案”**：先冻结一个可审计的 `core_scene`（来自任务设计、错误类型学或专家 taxonomy），再允许用 embedding 聚类做“候选细分/覆盖诊断/主动抽样辅助”，但**不建议让 embedding 聚类直接成为论文主口径的唯一 scene 定义**（可解释性与稳定性不足，且容易与 difficulty 自报标签混淆）。这种“用任务特征/潜变量刻画 task-type 或 bias”的路线在任务依赖偏差、以及 worker×task 联合建模中更容易经得起审稿。citeturn14search44turn1search5  
- **P1：派单（routing）若要基于聚类/场景，请把它当成“有约束的在线决策问题”**：用可审计策略（如 LCB/置信下界、dominance suppression、显式探索率）来平衡探索-利用，避免“只喂给少数高分工人”的支配效应与估计偏差；这在主动众包标注与 proactive learning 文献中有明确对应。citeturn6search0turn15search44turn15search42  
- **P1：就你当前进度而言，下一步最像“审稿人会要求你先补齐”的闭环是 C 线 reject lifecycle + B 线 core_scene 契约化**：你现状（来自你贴的 codex 核查摘要与进度截图）显示 A 线门禁很可能是 blocked，且 B 线仍是原型拼装；因此应先把 C 线与 B 线做到“可重复、可解释、可对齐”，再回头做 A 线 hardening 与 routing replay 才不会返工。

下文分两部分：先以该领域权威审稿视角逐一回答你关于 anchors / scene / clustering / difficulty / worker profiling 的问题；再把你贴出的 codex 一致性核查要点映射到“论文条款—实现产物—修复路径”的审稿表格（**但我在本对话环境里没有拿到你提到的“论文提纲 PDF 与实验集设定文件”，因此这一部分无法做到逐页逐条引用原文，只能先基于你贴出的审计摘要与工程产物名做“预对照表”；你把 PDF 上传到当前对话后，我可以把“章节号/页码/条款原句”补齐并校准冲突判定**）。

## 权威视角下的设计决策分析

### 权威观点对照表

| 权威工作/代表性作者 | 他们会如何“定义问题” | 与你问题最相关的结论（审稿口径） | 对你体系的直接启示 |
|---|---|---|---|
| **DS（EM 聚合/工人错误率）**：entity["people","A. P. Dawid","statistician ds em 1979"]、entity["people","A. M. Skene","statistician ds em 1979"] | 在没有真值时，用潜变量 + EM 估计“工人错误率/混淆矩阵”和“潜在真值”。citeturn0search2 | 若你只有少量 anchors，最稳妥的是先做“全局层面的 worker reliability”估计；场景特异要靠更多数据与层级模型，否则方差极大。citeturn0search2 | PreScreen anchors 更像是“启动与校准”而非“完成 scene-specific reliability 估计”。 |
| **GLAD（能力×难度）**：entity["people","Jacob Whitehill","glad model author"] | 同时估计 worker 专长/能力与 item difficulty，用概率模型解释“同一批工人为何在某些样本上更易错”。citeturn0search7turn0search48 | *difficulty* 是可建模的一等变量；但 difficulty 的估计需要与 worker 能力共同推断，不能直接把“自报 difficulty”当作真难度。citeturn0search7 | 你的 difficulty 标签可以进模型，但应当当做噪声观测或协变量，而不是 scene 定义本身。 |
| **多维 worker×task 潜空间**：entity["people","Peter Welinder","vision researcher crowdsourcing 2010"]、entity["people","Pietro Perona","computer vision researcher"] | 把 task 放进抽象欧式空间、把 worker 表示成多维实体（能力/偏差/专长），允许发现“不同 task-type 与不同 worker 子群”。citeturn1search5turn1search47 | “task space/scene space”可以是连续潜空间或可聚类结构，但**审稿会要求你证明它稳定、可解释且不泄漏**。citeturn1search5 | embedding 聚类用来辅助“场景/任务类型”是合理的，但需要契约与验证，而不是随手聚类即当作论文 scene。 |
| **选择性多标注/不确定性驱动加标**：entity["people","Victor Sheng","kdd 2008 crowdsourcing"]、entity["people","Foster Provost","data mining researcher"]、entity["people","Panagiotis Ipeirotis","crowdsourcing researcher"] | “多要几个标签”并非总是最佳；应对不确定样本选择性加标，兼顾成本与质量。citeturn0search0turn0search6 | 你在 Calibration 阶段做场景特异可靠性，本质上就是“对不确定/高风险场景加标”，审稿会要求 baseline 与成本曲线。citeturn0search0 | 你的 pipeline 需要显式预算与停止准则（何时停止加标、何时进入派单）。 |
| **Proactive learning（样本×标注者联合选择）**：entity["people","Pinar Donmez","proactive learning author"]、entity["people","Jaime G. Carbonell","cmu professor"] | 不是只选样本，也要选“问谁”；同时考虑成本、回答概率、信息增益。citeturn15search44turn15search42 | 他们在 discovery phase 里就做了 clustering 来提升多样性与估计（即便是 k-means）。这为“用 embedding/聚类辅助 PreScreen/Calibration 抽样”提供了强背书。但审稿会问：聚类如何稳定？如何不造成反馈环？citeturn15search42 | 你的路由若基于聚类，必须带探索项与审计日志（reason chain），否则不可复核。 |
| **Learning from Crowds（有特征的联合学习）**：entity["people","Vikas C. Raykar","learning from crowds author"] | 同时学习任务模型与标注者噪声，可用样本特征辅助真值与 worker 质量估计。citeturn1search0turn1search46 | embedding/特征可以进入“真值估计与 worker 模型”，但要当心把模型预测当作真值（循环论证）。审稿会追问你的 anchors 如何切断环路。citeturn1search0 | 你的专家锚点如果被用于训练任何“能影响后续选择/过滤/派单”的模块，必须有独立 held-out 评估集。 |
| **主动估计连续共识 + 在线派单**：entity["people","Yunus Emre Kara","crowd labeling bayesian 2018"] | 用贝叶斯推断估计共识，并用“共识后验方差”挑选最需要新标注的样本，再挑选最可靠的标注者；同时考虑 dominance suppression 与探索-利用。citeturn6search0turn3search12 | 这是你“Calibration → Routing”的直接理论原型：scene-specific reliability 其实就是把 sample score（不确定/风险）与 annotator score（能力/一致性）放到同一套在线决策里。citeturn6search0 | 你若采用 embedding scene，等价于在 sample score 里引入“场景分层的后验不确定性”。但需要严格冻结与审计。 |
| **任务依赖偏差（task-dependent bias）**：entity["people","Ece Kamar","microsoft researcher"]、entity["people","Eric Horvitz","microsoft researcher ai"] | 群体多数意见也会系统性错：偏差可能由 task 特征诱发；需把 task features 纳入模型并可主动获取少量专家真值来去偏。citeturn14search44turn14search43 | “场景特异可靠性”从审稿角度更像“task-dependent bias/skill”的实例：你需要证明不同 scene 下工人错误模式确实不同，而不是抽样噪声。citeturn14search44 | embedding + core_scene 的混合方案与“task features 进模型”天然对齐。 |
| **专家交互式验证与传播**：entity["people","Shixia Liu","visual analytics researcher"] | 将 learning-from-crowds 模型输出的“不确定 instance + 不可靠 worker”交给专家验证，并把验证结果传播到相关实例与工人，迭代提升质量。citeturn2search0turn4search45 | PreScreen 的专家锚点并不只用于算准确率，更用于“挑最能改变全局推断的验证点”。这支持你用专家锚点避免循环论证，但也强化了“锚点必须独立评估”的要求。citeturn2search0 | 若你后续要做“专家精标锚点集覆盖多种情况”，应把覆盖策略写成可审计抽样协议。 |
| **Datasheet/口径冻结**：entity["people","Timnit Gebru","datasheets for datasets author"] | 强调数据集动机、采集、用途、限制与偏差的结构化文档化。citeturn2search2 | 你 A 线的 TruthBundle/合同化（contract）路线是正确方向：审稿会要求你清晰写出“哪些 export 可进入 thesis estimand”。citeturn2search2 | A 线 blocked 本质上是“口径未冻结”，不是小瑕疵。 |
| **可解释与可审计决策**：entity["people","Cynthia Rudin","interpretable ml researcher"] | 高风险决策应偏向可解释模型而非黑盒+事后解释。citeturn3search1turn3search0 | 你把 routing 限定为规则型可审计路由（并记录 reason chain）在审稿上更安全。citeturn3search1 | embedding/聚类可用，但要避免把它当“不可解释的核心裁决器”。 |
| **OOD/错误检测基线**：entity["people","Dan Hendrycks","ood detection researcher"]、entity["people","Kevin Gimpel","nlp researcher"] | 最大 softmax 概率等简单分数可作为 misclassification/OOD 检测基线。citeturn2search1turn2search7 | 你的 difficulty/risk proxy 可以先用简单可复现分数（例如模型置信度/一致性）作为 baseline，再逐步引入更复杂结构。citeturn2search1 | 有助于把“difficulty 标签”从主观变成可对照的信号（但不能替代真值）。 |

### PreScreen 的专家锚点：应估计全局可靠性还是场景特异可靠性？

以严格审稿口径，你的 PreScreen “专家精标锚点”设计**最合理的定位是：先解决“全局层面的可用性与口径闭环”，并为后续场景特异估计提供分层采样框架**，而不是在这一阶段就声称已经稳定估计了场景特异可靠性。

原因分三层：

1) **统计可辨识性与样本量问题**：经典 DS 类模型首先给的是“每工人的整体错误率/混淆结构”的可辨识估计；GLAD 开始把 item difficulty 拉进来，但 difficulty 与 worker ability 是耦合推断，需要足够的多标注/交叉覆盖，否则场景切片后方差会爆炸。citeturn0search2turn0search7

2) **你真正要避免的循环论证来自“选择—评估同源”**：如果 PreScreen anchors 同时被用来（a）定义/调参场景划分或过滤规则，（b）估计 worker 参数/阈值，（c）又被拿来评估“场景特异可靠性”，那么即便你名义上是“专家精标”，也会因为信息泄漏而被审稿人认为循环论证。Kamar 体系对“用少量专家真值去纠偏 + 主动选择专家标注点”的讨论，隐含前提就是：要区分“用于学习纠偏/建模的真值”与“最终评价的真值”。citeturn14search44turn14search43

3) **PreScreen 更像是“专家验证（expert validation）”的启动轮**：Liu 的交互式体系强调把“最不确定的样本/最不可靠的工人”交给专家验证，然后把影响传播回去，本质是一种“用少量专家标注最大化整体质量提升”的策略；这支持你用专家锚点，但也强化了审稿点：专家锚点的抽样、盲标、传播机制必须可审计，且要有独立评估集。citeturn2search0turn4search45

**结论（审稿式表述）**  
- PreScreen：应以**全局可靠性（global reliability）+ 偏差类型嗅探 + 分层覆盖抽样协议**为主。  
- Calibration：才是**场景特异可靠性（scene-conditional reliability）**的主战场，并且应使用**层级模型**（见下节）以避免小样本切片造成的不稳定。

### Calibration 是否应采用 embedding 聚类来定义场景？派单是否应基于该聚类？

从权威路线看，答案是：**“可以用，但不能裸用；更推荐混合方案：契约化 core_scene + embedding 聚类做增量细分与抽样/覆盖辅助。”**

- 支持“可以用”的依据：  
  - Welinder–Perona 的模型把任务视为潜在空间结构，允许发现“任务类型/图片群落”和“工人技能群落”，这与 embedding → 聚类 → scene 的工程路径在思想上同构。citeturn1search5turn1search47  
  - Donmez–Carbonell 的 proactive learning 在早期 discovery phase 就使用 clustering（即便是简单 k-means）来做多样性采样与可靠性估计，从权威角度等于为“聚类辅助抽样/派单”做了背书。citeturn15search42turn15search44  

- 强烈反对“裸用”的审稿理由：  
  1) **稳定性**：不同 embedding、不同降维、不同随机种子会改变聚类边界；如果你把它当作论文主口径 scene，那么可复现性与可解释性会被挑战（尤其当你没冻结 seed/模型版本/预处理）。这也是你当前整体计划强调 RunSpec/可复现的原因。citeturn6search0turn15search42  
  2) **语义错配**：embedding 相似≠标注场景相同≠错误模式相同。Kamar–Horvitz 体系把 task features 纳入“任务依赖偏差”，强调的是“某些特征诱发系统性错误类型”，这通常需要“可解释特征”或至少需要证明 embedding cluster 与错误模式/难度之间存在稳健关系。citeturn14search44turn14search43  
  3) **反馈环**：若派单基于聚类，而聚类又受当前模型/标注分布影响，就会出现“你让谁标什么”反过来改变你对场景的理解，形成 policy-induced confounding。proactive / active crowd-labeling 文献通常通过显式探索与审计来缓解。citeturn6search0turn15search44  

**推荐的审稿安全方案**  
- “场景（scene）”至少两层：  
  - `core_scene`：人类可解释、契约冻结、论文主结果用它对齐（例如来源于任务协议、错误类型学、或你论文里定义的 scene taxonomy）。  
  - `embed_scene`：embedding 聚类得到的候选细分，用于：  
    - 覆盖诊断（哪些 embed cluster 没有 anchors/没有足够标注）  
    - 主动抽样（在每个 cluster 取锚点/取 calibration 点）  
    - 作为模型的协变量/随机效应索引（进入层级模型，而不是当作硬规则口径）citeturn14search44turn1search5  

### difficulty 标签是否可用于场景分类？worker profile 应如何利用这些信息？

**difficulty 标签的合理用途**（按审稿人更容易接受的顺序）：

1) **作为“与误差/分歧相关的观测信号”进入模型，而不是当作场景定义本身**：  
   GLAD 的核心就是把 difficulty 当作潜变量，与 worker ability 共同推断；如果你直接把自报 difficulty 当真难度，会被质疑“能力差的人更可能报难/乱报”。因此更稳妥的是把 difficulty 作为 noisy covariate 或辅助观测，用层级模型吸收偏差。citeturn0search7  

2) **作为 Calibration 的分层抽样维度**：  
   你可以把“自报 difficulty × embed_scene × core_scene”作为分层格子，保证锚点与校准集覆盖高难区域，避免只在 easy 区域估计到乐观可靠性。这个思路与“选择性加标”路线一致。citeturn0search0turn0search6  

3) **作为 routing 的约束变量（谨慎）**：  
   可以，但要写清楚“如何避免把难题永远派给少数专家工人而导致估计偏置”。Kara 的 dominance suppression 与探索-利用控制本质上就是在防止这种支配/偏置。citeturn6search0turn3search12  

**worker profile 应如何利用 scene/embedding/difficulty 信息？**  
建议把 worker profile 明确拆成三块，每块对应一种统计对象，并各自输出置信区间/下界（LCB）：

- **全局能力（global ability）**：用 anchors（或高置信共识样本）估计 worker 的整体质量下界 `r_u_lcb`；这是派单时最稳健的先验信号。DS/GLAD 都支持这一层。citeturn0search2turn0search7  
- **场景条件能力（scene-conditional ability）**：用层级模型估计 `r_{u,scene}`，并强制部分池化（否则小样本导致极端值）；这与 task-dependent bias 文献在审稿口径上高度一致。citeturn14search44turn14search43  
- **行为与成本侧特征（behavior/cost features）**：例如 active-time、拒答率、dominance、speed-accuracy tradeoff 等，用于 routing 的成本函数与审计解释；proactive learning 把“答复概率/成本”显式纳入目标函数。citeturn15search44turn15search42  

### PreScreen 到 Calibration 到 Routing 的数据流与决策点

```mermaid
flowchart TD
  A[原始任务池 / exports] --> B{PreScreen: 专家锚点抽样协议}
  B -->|calibration anchors| C[估计全局 worker 可靠性\n(含初始置信区间/LCB)]
  B -->|evaluation anchors| D[独立评估集\n(永不参与建模/调参)]
  A --> E[Embedding 提取\n(与 crowd label 解耦)]
  E --> F[embed_scene 聚类/分层\n(稳定性与可解释性校验)]
  C --> G{Calibration: 场景特异估计?}
  F --> G
  G --> H[层级模型: worker×scene×difficulty\n部分池化 + 不确定性输出]
  H --> I{Routing: 派单策略}
  I -->|可审计规则 + 探索| J[在线派单\n(含 dominance suppression)]
  J --> K[新标注流入]
  K --> H
  K --> L[Reject/异常生命周期审计\n(材料化/依赖/算子拒收区分)]
  L --> M[论文主证据产物\n(仅来自通过 gate 的 RunSpec)]
```

该流程图刻意把 embedding 提取放在与 crowd label 解耦的支路，并把 evaluation anchors 标成“永不参与调参”，这是为了把“循环论证/信息泄漏”风险在协议层切断。citeturn14search44turn15search42turn2search0  

## 推荐的可执行方法与算法配方

### 关键未指定项与默认建议

| 未指定项 | 建议默认值 | 选择依据（审稿能接受的理由） |
|---|---|---|
| embedding backbone | CLIP 系列（如 ViT-B/32 或 ViT-L/14 级别），并冻结版本号 | CLIP 的跨数据集迁移与零样本能力较强，适合作为“与当前标注分布相对解耦”的通用 embedding；同时工程生态成熟。citeturn16search3turn17search2 |
| embedding 距离度量 | cosine（向量 L2 归一化后等价欧氏） | 对比学习 embedding 的常见度量；实现稳定、解释简单。citeturn16search3 |
| 场景聚类算法 | HDBSCAN（默认）+ 可选 KMeans baseline | HDBSCAN 适合“不知道 cluster 数且密度不均”的情形，并能输出噪声点；同时有可引用的软件论文。citeturn16search0turn16search17 |
| 降维（用于聚类或可视化） | UMAP 到 32~64 维（用于聚类）+ 2 维（用于审计可视化） | UMAP 有软件论文与广泛使用案例；且比 t-SNE 更便于保留全局结构并用于中等维度嵌入。citeturn16search1turn16search15 |
| 随机种子 seed | 固定为 RunSpec 的一部分（建议取 git hash 的稳定哈希） | 主动众包/派单会引入策略性偏差；固定 seed 是最基本的可复现要求。citeturn6search0 |
| scene 数/粒度 | 不预设，先用 HDBSCAN；最终论文口径以 core_scene 为主 | 避免“选 K 就是在调参”；把 scene 的主口径放在可解释契约上更稳。citeturn14search44turn3search1 |

### 用于你问题的一组“最小但审稿安全”的模型组合

**组合一：全局可靠性（PreScreen）**  
- **Beta-Binomial（基于 anchors 的工人准确率后验 + LCB）**：  
  - 输出：`r_u_mean`、`r_u_lcb(p=0.05)`、`n_anchor_u`。  
  - 优点：无需复杂假设，清晰可解释；对派单的“安全下界”非常实用。  
  - 风险：只覆盖 anchors 分布；若 anchors 抽样偏离真实任务分布，会产生偏差，因此必须分层抽样。  
  - 对应权威立场：DS 传统错误率估计的可解释版本。citeturn0search2  

**组合二：场景特异可靠性（Calibration）**  
- **Hierarchical GLAD / Hierarchical DS（部分池化）**：  
  - 将 `core_scene`（或 `embed_scene`）作为随机效应索引：  
    - `ability_u`（全局）  
    - `delta_{u,s}`（场景偏移，收缩到 0）  
    - `difficulty_i`（样本难度，可选）  
  - 对应权威：GLAD 与 task-dependent bias 的融合式审稿口径。citeturn0search7turn14search44  

**组合三：派单（Routing）**  
- **两段式策略：先选“最需要”的样本，再选“最可靠且不过度支配”的工人**：  
  - 样本分数：`need(i)` = 共识后验方差 / 风险分数 / 置信度下界  
  - 工人分数：`score(u,i)` = `LCB(r_{u,scene(i)})` × `cost(u)` 约束 × dominance suppression  
  - 对应权威：Kara 的 sample posterior variance + annotator competence + dominance suppression；以及 proactive learning 的样本×标注者联合选择。citeturn6search0turn15search44turn15search42  

### 可复用的 Python 风格伪代码示例

```python
# -------------------------
# 0) 关键对象：anchors 协议
# -------------------------
# anchors_calib: 用于估计 worker/scene 参数、设阈值、调参
# anchors_eval : 仅用于最终评估（论文主结果），严禁进入训练/调参/过滤/聚类选择

def split_anchors(all_anchors, seed=0, ratio_eval=0.4):
    rng = Random(seed)
    rng.shuffle(all_anchors)
    k = int(len(all_anchors) * ratio_eval)
    anchors_eval = all_anchors[:k]
    anchors_calib = all_anchors[k:]
    return anchors_calib, anchors_eval


# --------------------------------------
# 1) 全局 worker 可靠性：Beta-Binomial
# --------------------------------------
from scipy.stats import beta

def worker_lcb_from_anchors(correct, wrong, alpha0=1.0, beta0=1.0, p=0.05):
    # posterior = Beta(alpha0 + correct, beta0 + wrong)
    a = alpha0 + correct
    b = beta0 + wrong
    return float(beta.ppf(p, a, b))


# --------------------------------------
# 2) embedding -> 聚类：UMAP + HDBSCAN
# --------------------------------------
import numpy as np
import umap
import hdbscan

def embed_cluster(embeddings, umap_dim=48, min_cluster_size=30, seed=0):
    # embeddings: [N, D], assumed L2-normalized
    reducer = umap.UMAP(
        n_components=umap_dim,
        metric="cosine",
        random_state=seed
    )
    Z = reducer.fit_transform(embeddings)

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        metric="euclidean",   # ok after UMAP; or use cosine directly on embeddings
        prediction_data=True
    )
    labels = clusterer.fit_predict(Z)   # -1 means noise
    return labels, Z


# ---------------------------------------------------------
# 3) 派单（简化版）：need(i) 先选样本，再选 worker
# ---------------------------------------------------------
def choose_next_task(posterior_var_by_item, unlabeled_items):
    # Kara 风格：优先选择共识质量最低 (= posterior variance 最大) 的样本
    i = max(unlabeled_items, key=lambda x: posterior_var_by_item[x])
    return i

def choose_worker(item, candidate_workers, r_lcb_worker_scene, dominance_penalty):
    # r_lcb_worker_scene[(u, scene)] gives LCB of reliability
    # dominance_penalty[u] in (0,1], smaller => suppress domination
    scene = item.scene
    best = None
    best_score = -1
    for u in candidate_workers:
        score = r_lcb_worker_scene[(u, scene)] * dominance_penalty[u]
        if score > best_score:
            best_score = score
            best = u
    return best
```

上面三段伪代码对应三条审稿关键线：**（a）anchors 的防泄漏拆分**、**（b）embedding 聚类作为“辅助视图”**、**（c）两段式派单 + dominance 抑制**。其中（c）的思想与 Kara 的两段式 active crowd-labeling 与 dominance suppression 一致；（b）与 proactive learning 的“先聚类保证多样性/探索，再做联合选择”也高度一致。citeturn6search0turn15search42turn15search44turn16search1turn16search0  

### 推荐开源库与版本建议

- **Embedding/深度特征**：PyTorch 2.x（实现与部署生态成熟）citeturn17search3turn17search10；OpenCLIP（CLIP 开源实现，便于冻结模型版本与权重）citeturn17search2  
- **聚类与降维**：UMAP（`umap-learn`）citeturn16search1turn16search20；HDBSCAN（`hdbscan`）citeturn16search0turn16search17  
- **贝叶斯/层级模型**：PyMC 5.x（分层模型与不确定性输出友好）citeturn17search1turn17search5  
- **传统 ML/统计**：scikit-learn（KMeans/指标/基线）citeturn17search8  

## 实验验证与统计方案

### 你需要回答的“审稿人会追问”的核心因果问题

1) **你的专家锚点是否真的切断了循环论证？**  
最低要求：所有用于建模/调参/派单策略设定的锚点必须与最终评估锚点严格互斥；评估锚点不能参与任何形式的聚类选择、过滤规则选择、阈值 tuning。否则审稿会把结果视为“在 test 上调参”。citeturn14search44turn1search0  

2) **你所谓“场景特异可靠性”是否只是切片方差？**  
最低要求：给出（a）场景分层后的样本量，（b）每场景的可靠性置信区间/后验区间，（c）部分池化 vs 不池化 的对照（后者通常会出现极端值）。GLAD/任务依赖偏差路线都隐含这个审稿点。citeturn0search7turn14search44  

3) **embedding scene 是否与错误模式/难度相关，且稳定？**  
最低要求：  
- 稳定性：不同 seed、不同 embedding backbone 下，聚类一致性（如 ARI/NMI）与下游结论的敏感性分析；  
- 有效性：cluster 与（a）分歧度、（b）专家纠错率、（c）reject/异常类型的关联检验；  
- 解释性：从每 cluster 抽样可视化/示例，解释它对应什么 core_scene 或错误类型。citeturn1search5turn16search1turn16search0  

### 建议的实验分割、baseline 与指标

**数据分割（强推荐）**  
- 以 *task/item* 为单位做 split（避免同一 item 的相关样本跨集合）；  
- anchors 分成 calibration/evaluation；evaluation anchors 只在最后计算主指标；  
- 如果你要比较 routing 策略，建议按 RunSpec 固定 seed 多次重复运行（≥20 次）并报告均值与置信区间。citeturn6search0turn15search42  

**Baseline（至少四类）**  
- 多数表决/简单平均（作为 naive 聚合基线）  
- DS（EM 聚合）/其连续值版本（worker 噪声高斯化）citeturn0search2  
- GLAD（能力×难度）citeturn0search7  
- Kara 风格的两段式 active crowd-labeling（sample posterior variance → annotator competence）citeturn6search0turn3search12  
- （可选）task-feature/bias 模型（Kamar 风格）作为“场景特异偏差”强基线citeturn14search44  

**指标（建议与你论文三条主线对齐）**  
- 共识质量：accuracy / MAE（若连续目标） vs 标注成本曲线；共识后验方差/置信区间覆盖率（calibration）；citeturn6search0  
- worker 建模：`r_u_lcb` 的分布、与 held-out anchors 的一致性、场景条件下的 rank correlation；  
- routing：单位成本提升（quality gain per label）、对“长尾工人/新工人引入”的敏感性（探索率扫参），dominance 指标（最高 workload 占比）。citeturn15search44turn6search0  

**显著性与稳健性**  
- 对比策略：优先使用 **bootstrap（按 item 重采样）** 或 **permutation test**，比单纯 t-test 更稳；  
- 场景/工人重复测量：可用混合效应模型（worker 与 item 随机效应）或贝叶斯层级后验对比；  
- 进行敏感性分析：embedding backbone、聚类超参（min_cluster_size）、difficulty 使用/不使用、anchors 抽样策略。citeturn14search44turn16search0turn16search3  

### 把 expert anchors 设计成“可防循环论证”的具体规则

可直接写进论文方法节的“硬规则”建议：

- **独立性**：evaluation anchors 在任何阶段都不能参与（a）聚类训练/选择，（b）阈值与 gate 调参，（c）worker/scene 参数估计，（d）派单策略的在线更新。  
- **盲标**：专家标注时不显示工人答案、不显示模型预测（防止 confirmation bias），必要时“双人专家 + 仲裁”。  
- **分层抽样**：anchors 必须覆盖 `core_scene × embed_scene × predicted_risk/difficulty` 的格子；每格至少保证最小样本（哪怕很小），否则你只能声称“覆盖诊断未完成”。  
- **交叉验证式锚点校准**：如果你必须用锚点调参（例如确定聚类数/阈值），就应当在 calibration anchors 内再做 K-fold，把调参与评估再隔离一层。  
- **审计产物**：输出 `anchor_protocol.json`（抽样规则/随机种子/分层统计/盲标流程），否则审稿时很难说服对方“没有人为挑选有利样本”。这些要求与 datasheet 思路一致。citeturn2search2turn14search44  

## 提纲一致性审查与修复路径

> 重要限制说明：你要求“对论文提纲 PDF 逐条核对（按章节号）”，但当前对话环境中我未收到该 PDF 与“实验集设定”文件，因此无法引用提纲原文逐条对照。以下表格仅能基于你贴出的 codex 核查摘要（A/B/C 三线）与工程产物文件名做“预审稿式一致性表”。你把提纲 PDF 上传到本对话后，我可以把每条映射补上“章节号/页码/原句”和更细粒度的 aligned/partial/conflict/blocked 证据链。

### 预审稿式一致性表（基于你贴出的 codex 审计摘要 + 当前产物名）

| 提纲关键条款（待你 PDF 校准章号） | 期望（审稿口径） | 当前状态 | 证据（你贴出的产物/审计要点） | 可执行修复路径（优先级/工作量/风险） |
|---|---|---|---|---|
| A 线：split 对齐与 Stage1 target | Stage1 prescreen（manual expert anchors + semi）必须与提纲 target 对齐；未对齐不得进入 thesis path | **blocked** | 你贴的审计指出：`phase1_target_vs_realized_manifest_v1.json` 中 `stage1_prescreen_manual_expert_anchor=under_target_and_not_aligned`、`stage1_prescreen_semi_total=not_aligned_and_not_materialized`，因此 split_alignment_gate 应为 blocked（不是 warning） | **P0**：把 split_alignment_gate 固化为 blocking；补齐 selection manifest 与 realized 的对齐策略（明确缺口来源：缺任务？缺 materialization？缺筛选规则？）。工作量：中；风险：若 target 定义本身不稳，会反复改口径。 |
| A 线：formal 输入（thesis-eligible exports） | 至少要有一组 export 被标记为 thesis-eligible；否则论文主证据无可用输入 | **blocked** | `export_inventory_summary_v1.json`：`export_label/` 下 9 个 export 全部 `exclude_from_formal_estimand`，没有 thesis-eligible | **P0**：建立“thesis-eligible export 的最小集合”名单与字段契约；让 Formal/TruthBundle gate 在缺失时直接 blocked。工作量：中；风险：牵动提纲口径，需要导师/你确认。 |
| A 线：registry suite 的 unmatched/ambiguous | registry join 必须可解释；unmatched/ambiguous 不能静默污染 grouping | **conflict（高风险）** | `registry_suite_summary_v1.json` task 级 33 unmatched + 32 ambiguous；`annotation_registry_v1.csv` 38 unmatched + 37 ambiguous；且 ambiguous 的 candidate_count=2（title 重复导致 title-only join 不安全） | **P0**：把 join key 从 title-only 升级为稳定主键；或建立 disambiguation 规则并输出审计表。工作量：中到大；风险：需要回溯数据血缘。 |
| C 线：materialization completeness 与 reject 解释 | materialization 不能只报 aggregate count；reject 必须可解释可回放，有生命周期 | **partial → blocked（若进入论文）** | 你贴的审计指出：`materialization_summary_v1.json` 只有 aggregate counts；2 条 reject 具有共同失败签名 `underextend + medium + 4-corner + transform_degenerate`；并且 `materialize_c_traps.py` 把所有非 success 写成 `manifest_status=blocked_by_dependency`（混淆“算子拒收 vs 依赖缺失”） | **P0**：做 `materialization_summary_v2` + `reject_lifecycle.csv/jsonl`（open/resolved/fallback/grandfathered）并区分 failure_code；修正 status 分层；补齐单测覆盖 4-corner+medium underextend。工作量：中；风险：低（主要是工程与口径清晰化）。 |
| C 线：reject 的“是否系统性边界”判定 | 要区分“算子族坏了”与“某子边界必然 reject”，并说明论文影响范围 | **aligned（诊断清晰），但需制度化输出** | 审计指出：问题是代码边界（medium 固定 remove_count=2，4-corner 第二次必触发 `len<=3` → reject），因此是特定子边界必然拒收 | **P1**：把这一判定写进 reject_lifecycle 的 reason_chain 与 thesis_family_impact；决定是 fallback 还是修算子定义。工作量：小到中；风险：中（牵涉你对 perturbation family 的理论定义）。 |
| B 线：pooled QA 的定位 | pooled QA 应为审计层，不得替代 formal 主分析输入 | **aligned** | 你贴的审计指出 `pooled_qa_plots.py` 已声明 QA/audit only；且你自己也认为 B 线要用 stage-aware framework 重起 | **P1**：把 pooled QA 中可复用的 schema/guard 逻辑抽出来供 B 线插件用，但禁止它直接作为 thesis 输入。工作量：中；风险：低。 |
| B 线：Worker×Scene、T/I/M、worker_cards、type4_audit | 四件套必须同一输入口径（A registry + selection manifest + C manifest）启动，并绑定 core_scene 契约 | **blocked（当前仍原型）** | 你贴的审计：已有 `Table_C_worker_scene.csv` 与 notebook funnel，但 scene 是派生标签（difficulty::* / model_issue::* / scene::none），不是 core_scene；worker_cards 缺关键字段；type4_audit 尚无正式脚本 | **P0/P1**：先冻结 core_scene（提纲契约），再让四件套从同一 AnalysisView 输出；新增 type4_audit 脚本并连接 userscript/meta guard 日志。工作量：大；风险：中（牵动未来派单与口径）。 |
| Routing replay 与可审计路由 | routing 必须可回放、记录 reason_chain，避免黑盒路由 | **暂无法判定（缺提纲 PDF 与当前实现细节）** | 你当前计划强调规则型路由与 replay，这与可解释审稿口径一致；但我没有看到 routing_audit 产物与提纲条款对照 | **P2**：等 B/C/A gate 都能稳定跑通后，再跑 replay_full + routing_audit，并把审计字段写死成 schema。工作量：中；风险：中（需要稳定的上游输入）。 |

以上表格里，“A 线 blocked”与“B 线 blocked”的组合意味着：**你当前论文主证据链（thesis path）在严格审稿标准下还不能宣称闭环完成**；你现在最有效的推进方式，是先把 C 线 reject lifecycle 与 B 线 core_scene 契约/四件套输出做成稳定可重复，再来做 A 线 formal 输入与 split alignment 的 hardening。这个排序与主动众包标注文献的常见工程现实一致：先把“共识/质量闭环”跑通，再谈“漂亮的平台化交付”。citeturn0search0turn6search0turn14search44  

## 给 Codex 的精确检查指令清单

> 目标：让 codex 自动化产出“门禁状态 + 阻塞证据 + 修复建议”，按 P0→P2 顺序执行。

**P0：A 线门禁（必须先跑）**
1) 读取并解析 `phase1_target_vs_realized_manifest_v1.json`：  
   - 输出 `split_alignment_gate`：若存在 `under_target_and_not_aligned` 或 `not_aligned_and_not_materialized` 直接 `blocked`；  
   - 生成 `alignment_diff_report.md`：列出缺口项、缺口类型（缺任务/缺 materialization/缺 selection）、以及建议最小修复动作（补样本/补 manifest/改 selection）。  
2) 读取并解析 `export_inventory_summary_v1.json`：  
   - 输出 `formal_input_gate`：统计所有 export 的 `thesis-eligible` 数量；若为 0 → `blocked`；  
   - 生成 `thesis_eligible_export_candidates.md`：列出哪些 export 可能被解除 exclude（需要哪些字段/审计）。  
3) 读取 `registry_suite_summary_v1.json` 与 `annotation_registry_v1.csv`：  
   - 输出 `scope_integrity_gate`：统计 unmatched/ambiguous（含 `matched_registry_candidate_count` 分布）；  
   - 抽样打印 20 条 ambiguous（candidate_count=2）并定位其在 `task_registry_v2.csv` 的重复来源，给出“替代 join key”建议。  

**P0：C 线 reject lifecycle（与你当前最直接可补齐的闭环）**
4) 读取 `trap_manifest_materialized_v2.csv` 与 `synthetic_trap_bank_v1.json`：  
   - 精确定位 2 条 reject 的 `manifest_row_id/operator_id/lambda_level/source_corner_count/failure_code`；  
   - 输出 `reject_lifecycle.csv`（含 resolution_status 初值=open）与 `reject_lifecycle.jsonl`（含 reason_chain、source_fingerprint、audit 指针）。  
5) 静态检查 `perturbation_operators.py` 与 `materialize_c_traps.py`：  
   - 证明/复现 `4-corner + medium underextend` 必然触发 `transform_degenerate` 的控制流；  
   - 要求把 `blocked_by_dependency` 拆成 **`rejected_by_operator`** 与 **`blocked_missing_dependency`** 两类（否则审计不可用）。  
6) 扩展单测 `test_perturbation_operators.py`：  
   - 新增用例覆盖：`4-corner + medium underextend -> reject`；  
   - 新增用例覆盖：`materialization_summary_v2` 的 failure_code_counts 与 resolution_status_counts 映射一致性。

**P1：B 线四件套骨架复用与契约化**
7) 检查 `Table_C_worker_scene.csv` 与 `visualize_output_v2.ipynb`：  
   - 判定当前 scene 字段是否为派生标签（difficulty::* / model_issue::* / scene::none）；若是，标记为 `appendix_only`；  
   - 输出“core_scene 迁移差异清单”：需要新增哪些字段（worker_group / worker_group_reason / r_u_lcb / core_scene / r_u_s）。  
8) 定位 type4 所需输入源：  
   - 汇总 `meta_label_guard.py`、userscript guard 日志、meta_missing 审计字段；  
   - 生成 `type4_audit_spec.md`（输入字段、判定规则、输出表 schema），以便新脚本落地。  

**P2：提纲一致性（需要你把提纲 PDF 上传到当前对话）**
9) 在你上传提纲 PDF 后：  
   - 抽取章节号→条款列表→对应门禁/产物文件名；  
   - 自动生成“aligned/partial/conflict/blocked”总表，并在每条冲突下附上具体证据片段与修复路径。

（如果你希望，我也可以把上述清单进一步改写成 codex 可直接执行的“逐文件读取/正则定位/结构化输出 JSON schema”版本，便于你们把它接到 CI 里。）