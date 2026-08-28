# 360°布局标注不确定性研究：候选实验方案（导师讨论稿 v2）

> **状态：DRAFT / NON-NORMATIVE / NOT APPROVED**
> **用途：仅供与导师讨论、质疑和修订；不是正式协议，不得据此启动实验、生成正式 assignment/import、部署 Label Studio 配置或解释正式结果。**
> **日期：2026-08-29**
> **候选计划锚点：24 张正式图片 × 3 个条件 × 每图每条件 4 个独立结果 = 288 条正式标注；该数字不是已冻结样本量。**

本 v2 只取代 v1 作为当前的**讨论建议**，不具有规范上的替代效力，也不删除或回写 v1。全文中的研究问题、假设、刺激物、问卷、几何日志、残差、成功标准和样本量都必须在导师批准、独立 pilot、功效仿真和统计计划冻结后才能进入正式执行。

## 0. 核心裁决

### 0.1 候选创新不是“比别人多收一份问卷”

如果只把元标签描述为“标注后附带问卷”，创新性很弱。更准确的候选贡献是：在可编辑的 360°结构化几何任务中，把下列三层在同一条 task-worker 记录上对齐，并检验它们何时一致、何时分离：

1. **外部结果层**：最终布局相对于独立证据、冻结参考和已知 proposal 目标错误是否正确；
2. **行为与几何层**：标注者从 initial/proposal 到 final 做了什么，以及最终布局的内部结构约束是否成立；
3. **主观元认知层**：标注者是否认为 proposal 有实质性问题、对此判断有多大把握，以及完成后对自己最终布局有多大把握。

Correct/Wrong proposal 的随机化提供可识别的干预；initial→final 的几何比较提供行为结果；最终信心、问题判断与多解判断提供元认知报告；复核需求和残余错误提供外部效标。研究对象因此是**主观判断—实际行为—外部结果的对齐与失配**，而不是问卷本身。

这是一项候选的组合式贡献，不声称“首次”研究标注分歧、预标注偏差、元认知或人工复核。最终新颖性表述必须以正式系统文献检索为准，不能仅凭本草稿下结论。

### 0.2 三类“不确定性”必须分开

| 层次 | 本研究中的含义 | 可观测代理 | 不能被替代为什么 |
|---|---|---|---|
| 对象/证据不确定性 | 图像证据不足、遮挡、开口边界不清或存在多个合理完整布局 | 独立复核、multiple plausible、scope、跨标注者受支持模式 | 不能被“工人信心低”直接定义 |
| 行为/输出不确定性 | 不同标注者给出的几何、范围或拓扑不同，或同一 proposal 被不同程度保留 | pairwise/LOO 几何距离、拓扑差异、target-error retention | 不能被内部 Manhattan 残差直接定义 |
| 元认知不确定性 | 标注者对 proposal 判断或最终答案的主观把握不足 | issue confidence、final layout confidence | 不能被当作客观错误概率，除非经过外部效标验证 |

此外，**内部约束符合度不等于外部正确性**。一个方正、闭合、低残差的布局仍可能标错墙、遗漏当前空间或纳入相邻空间；一个外部边界大体正确的布局也可能有内部自交、短墙或高度不一致。论文必须分别报告二者，不能都称为“墙残差”。

### 0.3 最小推荐路径

若目标是短、平、快，同时保留可辩护的创新性，建议：

- 不新增盲重复作为默认设计，不以招募低质量工人制造效应；
- 用一个最清晰的主要因果比较：Semi 内 Wrong vs Correct；
- 把 Semi vs Manual 明确降为“整套 proposal + 强制自审工作流”的次要比较；
- 三臂共同只增加两个核心 post-edit 元标签：最终布局信心、多个合理布局判断；scope 保留为运营/可评估性字段；
- Semi 只增加 proposal 问题判断及其信心，并尽可能在编辑前锁定；
- 环向角点顺序和残差只在研究者侧离线记录/计算，不实时反馈给工人；
- 24×3×4 只作为仿真起点。若功效不够，应增加图片或每图重复数，或降低结论层级，而不是降低工人质量。

---

## 1. 不可改变的正式边界

本草稿与 Paper A 当前正式方法合同及统计分析计划并行讨论。撰写时核对的机器规范真源为 contract_version paper_a_method_20260811_v23、JSON SHA-256 f3c1ea58d0857a40aa2240b4680b674c76fe2cec8f048f61a643d9e4b74b0588；本稿不是该合同的修订或消费者替代，不自动修改以下任何语义：

- 正式阶段仍为 Pilot → PreScreen(P1) → Calibration(C1 + C2-B + C2-A-RP) → Main(T1 + V1)；
- formal_launch_default 仍为 false；本讨论稿不授权 Stage 3 或任何正式 launch；
- C2-B 和 C2-A-RP 已关闭的范围、原始记录、closeout 和解释不回写；
- C1 原始 export、assignment 与当前 annotation 不因新的派生链或研究解释而追溯改变；
- P1、C1 predictive validation、C2-B confirmation、C2-A-RP precision 的角色继续分开；P1 component 只有满足现行 C1/C2 验证条件后才能进入 Full，本稿不能绕过；
- export_label、import_json、active_logs 是事实真源，analysis_results 只是派生输出；
- formal assignment eligibility、不可评估记录不按零分处理、机器异常不自动排除等正式规则保持不变；
- 正式设计中 worker-caused structural failure 留在原 condition 并按既定 delivery-adjusted 规则处理；外部行政/技术删失单列，不伪装成工人零分；
- 正式 T1 仍是既定的 Manual/Semi × mode/risk-assist 设计及 image-paired 解释，本候选实验不得冒充 T1 的静默改版；
- 正式 V1 仍是前瞻性 ITT 设计，离线 replay 或本候选实验不能替代 V1；
- T1/V1 结果不得反向调节 admission、worker state、风险阈值、权重、冗余或 freeze 参数；
- active time 仍只能使用 owner-valid 的 task-worker context 累计日志，不使用 lead time，不进入能力、roster 或 routing；
- scope/meta 响应保持描述、分层或 triage 角色，不因本稿自动成为 worker axis、roster、Full 或 Stage 3 gate；
- Label Studio CE 页面、角色、筛选器和任务可见性不是正式分发或安全隔离机制；外部 assignment manifest 才是分发真源；
- GT 与 worker 的活动路径必须继续运营隔离，但这种隔离不宣称为 CE 权限安全；
- 本稿不改变任何现行 XML、userscript、项目、导入包、外部分配表或运行映射。

如果导师决定把本研究纳入正式论文主线，必须新建并冻结独立的研究合同、统计计划、stimulus truth manifest、assignment manifest、instrument manifest 和启动审批；不得仅把本稿标题改成“正式版”后直接运行。

---

## 2. 旧实验为何没有回答预期问题

旧工作并非“数据质量差所以失败”，主要是设计、构念和证据链不匹配。

### 2.1 根因审计

1. **描述、因果和预测混在同一问题里。** 历史数据可以描述输出分歧，却不能仅凭观察到的 Manual/Semi 差异识别 proposal 的因果效应；元标签与最终错误相关也不自动证明它能在新图上诊断风险。
2. **历史 Manual 与 Semi 不是为当前 RQ 随机产生的。** 阶段、图片、worker、proposal 质量和任务目的同时变化，直接合并会把阶段差异误写成预标注效应。
3. **旧 Model Issue 没有可靠的编辑前技术锁。** 工人可能在编辑中或编辑后形成判断，因此不能正式声称“先识别、再修复”。
4. **元标签语义跨阶段漂移。** 旧 acceptable 强调“不需要任何调整”，新 material issue=no 允许自愿轻微调整；旧 scope 把唯一可复现布局与多解混在一起，新 scope 问“是否至少存在一个完整布局”；两者不能机械同值。
5. **没有共同的最终信心字段。** 历史数据能提供行为分歧，不能回答标注者是否知道自己的最终答案可能错误。
6. **把低内部残差误当作外部正确的风险很高。** 3D preview 的方正度主要提示内部一致性，不能证明当前空间范围、真实边界或拓扑选对。
7. **行为轨迹的可复现性不足。** 仅有最终点集或浏览器 localStorage，无法保证恢复当时 preview 使用的环向顺序、尺寸、版本和对应 submit。
8. **“高质量工人发现并修复 Wrong”曾被误认为会让实验泡汤。** 这其实是重要机制结果：干预增加了纠错需求，但工人通过自审吸收了干预。若事先只把最终均值显著变差定义为成功，就会错判有价值的鲁棒修复。
9. **候选样本量没有完全对应最终 estimand 与依赖结构。** 同图、多工人、同 worker 多图产生交叉聚类；不能把 288 条记录当 288 个独立样本做普通检验。
10. **界面隐藏不等于数据清除。** 分支从 UI 消失后，旧值仍可能留在提交 payload；如果 material issue 改为 no 而缺陷/修复字段仍保存，会制造逻辑矛盾。

### 2.2 旧数据仍然有用

当前中性底座 analysis_results/uncertainty_substrate_20260823_v1 报告 2,501 条 canonical 记录，其中 2,438 条可计算几何，2,069 条具有正式 active-time；历史 model issue 在 574 条 Semi 响应中可见（P1 468、C1 106）。这些记录的合理分工是：

- **RQ1 行为基线**：历史 Manual 输出用于估计图像层分歧、支持度、方差分量和功效仿真的先验范围；
- **刺激物与 proposal 审计**：历史 initial/final 几何、Model Issue 分布和研究者回放用于构造 Wrong 类型及严重度候选；
- **技术与运营基线**：owner-valid active-time、缺失率、结构失败率和导出 schema 用于 pilot 门槛；
- **构念效度线索**：旧 model_issue 的多选压力测试可说明单一互斥缺陷标签不够，但不能成为新标签 truth；
- **负面证据**：历史数据明确告诉我们哪些因果或时间顺序结论目前不能做。

旧 Pilot project 2 的混合 schema、重复快照和非正式分配只作探索或兼容性检查，不进入正式合并分析。

### 2.3 最小历史 crosswalk

crosswalk 必须作为 sidecar 保存，永远保留 raw field、raw value、stage、instrument version 和 source SHA；不得覆盖旧导出。

| 历史字段 | 新候选字段/构念 | 可比等级 | 允许用途 | 禁止用途 |
|---|---|---:|---|---|
| 历史 geometry/final layout | final geometry、行为分歧 | 较高，但需记录可计算状态 | RQ1 行为基线、方差/ICC、刺激筛选 | 与新 final confidence 伪配对 |
| 旧 scope | worker scope response + multiple plausible | 低/部分 | 按原值分层描述、敏感性分析 | 直接重编码为新 in/out scope 或多解 |
| 旧 difficulty reasons | 新 difficulty reason | 部分 | occlusion、low texture、seam/distortion、reflection/transparency、image quality 的近似映射 | 把 trivial 映射为新难度=1，或合成统一量表 |
| 旧 model_issue=acceptable | 新 material issue=no | 低 | 原语义描述 | 视为同一构念；旧值要求无调整，新值允许轻微自愿调整 |
| 旧 model_issue 错误类别 | observed defects | 部分 | 类别频率、候选 taxonomy 压力测试 | 证明编辑前识别、敏感度/特异度或新 truth |
| 历史 active time | 新 active time | 条件可比 | owner-valid、source-matched 的辅助描述和仿真 | 用 lead time 替代，或进入能力/routing |
| 历史角点顺序 | observed/canonical/unknown order state | 依来源而异 | observed 原序或可证明 canonical 的分析 | 对 unknown 假装精确恢复 preview 顺序 |

不需要让所有历史阶段拥有完全相同的字段。正确做法是保留 stage-specific instrument，在长表中显式记录 applicable、response state 和 provenance；新正式实验内部则必须冻结一个跨三臂一致的 common core。

---

## 3. 候选研究问题

### RQ1：无辅助条件下，主观判断、输出行为和外部误差是否对齐？

在 Manual 条件下：

- final layout confidence 是否能区分外部正确与错误结果，而不只是反映 3D preview 的方正度？
- multiple plausible layout 判断是否对应更高的跨标注者分歧或独立复核歧义？
- 内部几何残差、跨标注者分歧与外部误差之间有多大重叠，又有多少失配？

历史 Manual 只提供**行为分歧基线**；新的 Manual 数据补充同任务、同界面、同时间点的 final confidence 和 multiple plausible，才可检验主观—行为—外部三者对齐。

### RQ2：强制自审工作流下，Correct 与 Wrong proposal 的因果效应是什么？

主要因果比较只在 Semi 内进行：同一批图片、同一界面和同一强制自审流程中，随机呈现 Correct 或 Wrong proposal，比较 initial→final 的修改、target-error retention、外部错误和复核需求。

Manual 与 Semi 的比较是次要的**整套工作流对比**。即使实现了编辑前锁定，Semi 仍同时包含 proposal、proposal 检查题和不同初始状态；因此 Semi vs Manual 不能被窄化解释为“只提供几何预标注”的纯效应。

### RQ3：元标签是否在常规信号之外提供增量风险诊断？

目标不是解释相关性，而是预测一个此前未见 building/image 的最终记录是否存在残余错误或需要复核。比较嵌套诊断模型：

1. condition、训练折内 worker/image 信息、proposal severity、owner-valid active time；
2. 上述变量 + 内部残差；
3. 上述变量 + 内部残差 + material issue、issue confidence、final confidence、multiple plausible。

RQ3 问的是第 3 层是否在严格 held-out 评估中带来可复现的增量 AUPRC 或固定复核预算下 recall，而不是“元标签的回归系数是否显著”。

### 3.1 识别失败与修复失败

在 Wrong-Semi 内预先定义机制状态：

- **识别成功**：编辑前锁定的 material issue=yes；uncertain 单列，不静默并入 yes 或 no；
- **识别失败**：material issue=no，但独立 truth 确认 proposal 含目标错误；
- **修复成功**：目标错误的 retention 降到预先冻结的可接受范围，且没有引入更严重的外部/拓扑错误；
- **修复失败**：已识别或 uncertain 后，目标错误仍保留，或修复引入等价/更严重的新错误。

由此可区分“没看出问题”和“看出了但没修好”。若高质量工人几乎都识别并修复 Wrong，结果不是实验失败，而是说明该 self-review 工作流对这一级别错误具有鲁棒性；此时 Wrong 的最终总效应可能接近零，但 initial→final 纠错需求和修复机制仍可被估计。

---

## 4. 可证伪假设与证据层级

### 4.1 Primary：一个主要因果效应族

**H2-primary：** 在 Semi 强制自审工作流内，Wrong 与 Correct proposal 对预先冻结的主要外部结果产生不同的意向处理总效应。推荐 primary 为两臂都能同义定义的 task-level residual material error/review-needed；也可在 launch 前改选一个两臂共同的连续外部误差，但只能冻结一个 primary，不能看结果后切换。target-error retention 只在 Wrong 内有自然定义，因此属于机制性 secondary，不作为 Wrong vs Correct 的跨臂 primary。

- 零假设：Wrong−Correct 的主要结果差异为 0；
- 方向性预期可登记为 Wrong 更差，但必须同时报告双侧 95% CI；
- condition 按随机分配分析，不因工人识别、是否编辑或最后修好而改组；
- 最终残差、active time、编辑幅度和 material issue 都可能受 treatment 影响，不作为估计总效应的普通调整协变量。

### 4.2 Key secondary：测量效度与增量诊断

**H1-validity：** 在新 Manual 中，final confidence 等级越高，独立外部错误/复核需求越低；这种单调关系不是仅由内部残差解释。若关系方向相反、接近零且 CI 排除预定最小效应，主观信心不具备本任务的风险诊断效度。

**H3-incremental：** 在 held-out building/image 中，加入元标签后，AUPRC 和固定 review budget 下 recall 相对于“常规变量 + 内部残差”提高至少一个事前冻结的最小有意义幅度 Δ诊断。Δ诊断 必须由实际复核预算与误漏成本在 launch 前确定，不能由观察结果倒推。

### 4.3 Secondary 与 exploratory

Secondary：

- Correct-Semi、Wrong-Semi 各自相对于 Manual 的工作流差异；
- Wrong 内的识别失败率、修复失败率及二者分解；
- final confidence 与外部连续误差的有序趋势；
- multiple plausible 与 LOO 分歧、独立复核多解状态的关联；
- Correct proposal 上的无必要修改和新引入错误。

Exploratory：

- 缺陷类型、proposal severity、图片证据类型与 condition 的交互；
- perceived difficulty/difficulty reason、active time 与行为/结果的关系；
- per-layout self-fit 残差、canonical order 方向和局部修改模式；
- worker 随机斜率或潜在策略差异，仅在数据支持时报告，不据此建立稳定 worker 类型学。

只有 primary 家族可以承载主因果结论。Key secondary 支持测量和诊断贡献；exploratory 只生成下一步假设。

---

## 5. 候选三臂设计与功效决策

### 5.1 设计骨架

| 条件 | 初始状态 | proposal 题 | 共同 post-edit 题 |主要解释 |
|---|---|---|---|---|
| Manual | 无 proposal，从空白/正式 Manual 起点完成 | 结构性不适用 | final confidence、multiple plausible、scope | 无辅助下的主观—行为—外部对齐 |
| Correct-Semi | 独立审核为可接受的 proposal | material issue + issue confidence；锁定后才出现 checklist | 同上 | 正确初始化 + 强制自审工作流 |
| Wrong-Semi | 含预先定义目标错误的 proposal | 同上 | 同上 | 错误初始化 + 强制自审工作流 |

核心约束：

- 三臂使用同一组正式图片，形成 same-image balanced design；
- 每位 worker 对同一图片只见一个条件一次，永远不能随后在另一臂重见该图；
- worker 不知道 proposal truth，界面、文件名、任务编号和说明不得泄露 Correct/Wrong；
- Correct/Wrong 在 Semi 内按预先生成的随机 assignment 分配，分析按 assignment；
- 图片顺序、臂顺序与 worker workload 分块平衡；同一 worker 可做多图，但不能由单一 worker 承担某一臂或某类图片；
- worker 间不得共享 proposal truth 或讨论具体图片；历史暴露按 same-worker × same-image 在正式分发前核查；
- 独立 stimulus reviewers 不参与对应图片的工人标注，结果评估尽可能对 condition 和工人元标签盲。

### 5.2 24×3×4 只是计划锚点

候选锚点为：

- 24 张正式图片；
- 每图 Manual、Correct-Semi、Wrong-Semi 各 4 个独立 worker 结果；
- 总计 288 条正式 assignment。

这不是 288 个独立统计单元。图像和 worker 是交叉聚类来源，Correct/Wrong 又共享 image。正式启动前必须使用历史 Manual 方差、image ICC、worker ICC、连续结果分布、二分类残余错误基率、预期缺失率和实际分块算法做仿真。

仿真至少报告：

- primary estimand 的 bias、SE、95% CI 覆盖率和功效；
- 不同 image 数 × 每图每臂重复数的等成本比较；
- 二分类基率低、Wrong 几乎全被修复、signature 缺失和 scope 不可评估等情景；
- image/worker 随机效应较强时的稳健性；
- planned mixed model 不收敛时的预先降级分析。

若 24×3×4 对 primary 或 key secondary 明显不足，只能：

1. 增加图片；
2. 增加每图每臂重复数；
3. 缩减 primary 结果或把某 RQ 降为估计性/探索性；
4. 放弃无法被当前规模支持的强结论。

不得通过故意招募低质量 worker、选择极端容易失败的 Wrong proposal、删除“修得太好”的工人或查看 pilot 显著性来放大效应。

### 5.3 Pilot 不进入主分析

instrument pilot 与正式实验必须使用不同 assignment；建议使用不进入正式 24 图的 6–9 张图片，覆盖三臂、yes/no/uncertain、scope 分支、不同角点数和至少一种 signature mismatch。Pilot 只验证操纵与数据链，不进行 outcome-driven 显著性筛选。

若 pilot 后修改任何科学字段、truth 定义、主要结果、随机化、残差算法或问法，pilot 永久标为 development，不并入正式分析。

---

## 6. 最小元标注与时点设计

### 6.1 三臂共同的 post-edit 核心

所有条件在几何完成后使用相同措辞收集：

1. **final_layout_confidence（1–5，有序等级，必答）**
   - 1：把握很低，认为最终布局很可能仍有需要复核的实质性问题；
   - 2：把握较低；
   - 3：把握一般；
   - 4：把握较高；
   - 5：把握很高，未发现需要复核的实质性问题。
2. **multiple_plausible_layouts（yes / uncertain / no，原则上必答）**
   - yes：至少两个实质不同的完整布局同样受到图像证据支持；
   - uncertain：无法可靠判断是否存在第二个同样合理的完整布局；
   - no：未发现第二个同样合理的完整布局；
   - 轻微坐标差异不算“多个布局”。
3. **worker_scope_response（运营/可评估性字段）**
   - 保持“当前相机空间是否至少支持一个完整、闭合、单层 Manhattan 布局”的现行语义；
   - 不把“难”“多解”自动视为 out of scope；
   - 若 out of scope，则 multiple plausible 记为 structural_not_applicable，而不是强迫回答 no。

final confidence 是对**最终提交布局**的把握，不是对图像清晰度、3D preview 美观程度或初始 proposal 的评价。它是 ordinal report，不应暗示 1–5 等于 0%–100% 概率。

### 6.2 Semi 的 pre-edit 核心

Correct-Semi 与 Wrong-Semi 在首次允许编辑前共同收集：

1. **material_issue（yes / uncertain / no）**：页面打开时的 initial proposal 是否至少存在一项必须修正的实质性问题；
2. **issue_confidence（1–5）**：对上述判断的把握程度；
3. **observed_defects（多选）**：第一判断锁定后才显示。

建议复用经开发测试的五个可并存类别：boundary misalignment、current-space undercoverage、adjacent-space inclusion、spurious non-layout structure、duplicate/redundant corner。topology validity 继续由几何/研究者 QC 派生，不强迫 worker 把所有结构失败归入某个可见缺陷类别；若 pilot 证明确有未覆盖的常见实质问题，只能在正式 instrument freeze 前增加 other/unclear，并给出互斥/多选语义。

issue confidence 的 1–5 指“对自己所选 yes/uncertain/no 分类的把握”，不等于 proposal 正确概率；高把握地选择 uncertain 可以表示标注者确信当前证据不足以作 yes/no 判断。

建议流程：

1. 加载并确认 proposal 完整；
2. 工人查看图像与 3D preview，但尚不能移动/增删角点；
3. 回答 material issue 和 issue confidence；
4. 系统保存不可覆盖的首次判断及时间戳；
5. 锁定后显示 observed defects 并开放几何编辑；
6. 工人完成几何，再回答三臂共同的 post-edit 核心。

分支规则：

- material issue=yes：observed defects 至少选一项；
- material issue=uncertain：显示 observed defects，但允许空集合；空集合表示无法定位具体类型，不等于 no issue；
- material issue=no：observed defects 必须隐藏并在前端 state、提交 payload 和服务端校验三处清空；
- 工人可以在锁定后看到自己的首次判断，但不能覆盖它；若需要收集事后修正意见，应写入单独字段，不能改写首次判断。

### 6.3 不再要求工人自报 repair actions/extent

repair actions 和 repair extent 建议由 initial→final 几何差、目标错误 retention 和人工盲审派生，不再作为核心工人题。原因是：

- 工人可能将“移动一个角点”与“影响多面墙”理解不同；
- 自报动作与实际几何可以冲突；
- 增加必答题会提高疲劳和分支残留风险；
- 本研究已经计划保存足以派生编辑幅度的 initial/final 几何。

若导师希望保留工人自报，它只能作为 exploratory self-report，并用不同字段名与派生 repair action 分开，不能二者都叫 repair_actions。

### 6.4 难度字段降为可选探索

perceived difficulty 和 difficulty reason 不是三个 RQ 的必要核心。为缩短表单，建议：

- 不设为正式必答；
- 若保留，只在 post-edit 收集并标为 exploratory；
- no specific reason 必须与其他原因互斥；
- 不把旧 difficulty reason 回填为新的 1–5 perceived difficulty。

### 6.5 时点降级规则

如果当前 Label Studio/脚本无法做到“首次判断持久化后才开放编辑”，则不得把工人说明文字当技术证据。此时：

- material issue 和 issue confidence 降级为 **task-time self-report**；
- 不使用“编辑前识别”“先识别再修复”的强时间顺序措辞；
- 识别失败/修复失败只作弱机制分层；
- RQ2 的 Semi vs Manual 明确解释为“proposal + 自审表单 + 编辑工作流”的组合差异；
- Wrong vs Correct 仍可作为 assignment-level ITT 因果比较，只要 proposal truth 随机分配、未泄露且最终结果完整。

### 6.6 与当前本地开发配置的关系

当前本地 manifest/XML 仍是开发工件：部分题只有 yes/no，没有 final layout confidence，repair actions/extent 仍为工人自报，technical time lock=false。本文描述的是**待导师批准后才可能实现的候选最终 instrument**，不代表这些能力已经存在或已部署。

---

## 7. 环向角点顺序：必要运行时状态，不是完整编辑轨迹

### 7.1 为什么必须记录

全景布局的同一无序点集可对应不同的环向连接、起点和方向。3D preview 依据某个具体顺序构造墙段；如果分析只拿最终点坐标后自行猜序，就可能计算出与工人当时看到的 preview 不同的拓扑和残差。

因此，当前可见的环向顺序是**解释提交几何所需的运行时状态**。它不是鼠标级完整轨迹，也不需要记录每次拖动。默认只记录：

- proposal/preview 首次稳定可见时的 base state；
- 每次 submit attempt 当下的 visible state；
- Label Studio 最终成功导出后可绑定的 submitted state。

### 7.2 不能只读 localStorage

localStorage 可被覆盖、跨任务残留、缺少 annotation/attempt 身份，且不保证与当前 iframe 内 preview 状态同步。可靠采集必须从正在显示该任务的 viewer/bridge 取得显式状态，并同时写入身份、版本、尺寸和签名。localStorage 最多作为调试线索，不能作为正式真源。

### 7.3 preview_orders JSONL 最小记录

独立日志建议命名为 preview_orders JSONL，每行至少包含：

| 类别 | 必需字段 |
|---|---|
| 身份 | project_id、runtime_task_id、planned_task_id、image_id、assignment_id、worker_pseudonym、annotation_id（若当时已知）、attempt_id |
| 实验 | arm_code、blinded_proposal_id、batch/block、instrument_version |
| 事件 | event_type（base_visible / submit_attempt / export_bound）、client_timestamp、server_received_at、sequence_no |
| 图像坐标 | image_width、image_height、coordinate_system、seam_convention、normalization_version |
| 几何 | current_visible_order_raw、preview/base corners、submit geometry、corner_count、orientation_if_known |
| 签名 | signature_algorithm_version、preview_signature、submit_signature、signature_match_status、mismatch_reason |
| 软件 | viewer_version、userscript_version、Label Studio project/config version、browser bridge version |
| 溯源 | source_file/source_endpoint、payload_sha、record_created_at |

worker identity 只使用批准的伪名/registry key，不在研究日志复制真实姓名。

### 7.4 submit attempt 不等于成功提交

点击提交、弹出确认框或触发 submit hook 只证明发生了 attempt。正式绑定流程应为：

1. 记录 submit attempt 的几何、环序和签名；
2. Label Studio 成功创建/更新 annotation 后，以导出记录为事实真源；
3. 使用 project/task/worker、时间窗口、instrument version、corner count 和 geometry signature 离线绑定；
4. 绑定成功生成 export_bound 记录；
5. 多个候选或签名不一致时保留全部候选与 mismatch 原因，不静默选最近一条。

signature mismatch 不应阻断工人提交，以免研究日志破坏正式标注任务；但 mismatch 记录不能声称精确复现了工人提交时的 preview。

### 7.5 原始顺序与规范化顺序同时保存

正式分析不得覆盖 current_visible_order_raw。另行派生：

- rotation-canonical：在保持方向的前提下，按冻结规则选择环的起点；
- reversal-canonical：仅在分析明确允许反向等价时，在正向/反向中选择冻结的规范表示；
- topology signature：基于 normalization version 计算，不与原始签名混写。

任何对旋转、反向、全景 seam 的等价处理都必须有版本。若某分析对方向有物理含义，则不得应用 reversal canonical。

历史记录按来源标记：

- observed：日志或导出直接保存了当时顺序；
- canonical：只能证明某个冻结算法的规范序，不能声称是当时可见顺序；
- unknown：无法恢复；仍可用顺序不敏感的 mask/边界指标，但不能进入精确 preview-order 分析。

### 7.6 与 active time 严格分流

preview_orders JSONL 只记录几何状态事件；active_times 日志只记录批准的 task-worker active-time 事件。两者可以通过不可变身份离线连接，但：

- 不把角点事件混入 active-time 文件；
- 不用角点事件间隔重建 lead time；
- 不因 preview_orders 缺失改写正式 active-time；
- 不因 active-time 缺失丢弃外部质量结果，除非独立的 eligibility 规则另有规定。

---

## 8. 离线内部残差与外部正确性

### 8.1 残差的定位

所有残差只在冻结原始数据后由研究者离线计算，不在标注过程中显示给 worker，不改变 3D preview，不提供“得分”“红绿灯”或自动纠正。否则残差会从测量变量变成 treatment，破坏 RQ1/RQ2 的解释。

内部残差只回答“这组几何在给定 Manhattan/单层模型下有多自洽”，不回答“墙选对了吗”。

### 8.2 候选残差族

精确公式和单位必须在 pilot 后随 geometry engine 版本冻结。最低限度包括：

1. **R_heading：墙面朝向残差**
   - 对每个墙段求水平 heading；
   - 相对于一组互相正交的全局 Manhattan 轴，计算到最近轴的周期角距离；
   - 同时报 wall-length-weighted mean、unweighted mean 和 max；
   - 使用角度的周期距离，不能把 179° 与 −179° 当作相差 358°。
2. **R_corner：相邻墙交点/重投影角点残差**
   - 在给定 camera/frame 与相邻墙平面下重建理论交点；
   - 计算理论交点重投影与 submitted corner 的周期像素距离或球面角距离；
   - 报 mean、max 和按相邻墙长度加权的 mean；
   - 明确 corner 是原始可见顺序还是 canonical 顺序。
3. **R_height：单一地面/天花高度一致性**
   - 由各墙段/角点推断的 floor/ceiling height 对统一高度的偏差；
   - 报稳健中心、MAD/绝对残差 mean 和 max；
   - 对无法稳定推断的布局记 not_evaluable，不填 0。
4. **结构事件**
   - self-intersection count/rate；
   - short-wall count/rate（阈值按图像尺度或角宽归一化并预先冻结）；
   - duplicate/redundant corner flag；
   - non-closure/topology invalid flag。

不能只报告 residual sum。角点/墙面更多的布局天然有更多求和项；每个残差族至少报告 mean、max 和 length-weighted summary，并把元素数作为描述量。

### 8.3 两种 frame 版本

**Per-layout self-fit**

- 每个提交布局自己拟合 Manhattan heading、height 和必要 camera 参数；
- 适合描述“这个布局能否被某个 Manhattan frame 很好解释”；
- 可能因自由度较多而把外部错误拟合掉，不能用于证明墙选对。

**Image-level frozen reference frame**

- 每张图在结果不可见前，由独立参考/审核流程冻结 camera、主方向、floor/ceiling 参数和版本；
- proposal、Correct、Wrong 与所有 final 都投影到同一 frame；
- 适合比较 proposal→final 的残差变化和三臂差异；
- 若 frame 来源使用了当前参与者结果，就产生循环，不能作为独立外部效标。

proposal→final 的主要残差变化必须使用固定 frame；self-fit 只作辅助/敏感性分析。若 frozen frame 不能可靠建立，该图的 fixed-frame residual 记 not_evaluable，但外部 mask/boundary 等结果仍可保留。

### 8.4 外部结果必须独立保留

外部结果族至少包括：

- periodic boundary distance / D_mask；
- wall-region IoU 或等价区域重叠；
- q_wallwall（只能引用冻结实现与版本，不在本稿另行改写正式定义）；
- target-error retention：Wrong proposal 中预定义目标错误保留多少；
- topology correctness/结构有效性；
- scope correctness 与相邻空间纳入/当前空间漏标；
- independent review-needed / residual material error。

外部 reference/truth 必须在工人结果不可见时冻结或由对 condition 盲的独立复核产生，并记录多解允许集。存在多个合理布局时，不能强迫所有 worker 向单一 reference 收缩；应采用允许集最小距离、盲审可接受性或预先定义的 set-valued scoring。

---

## 9. 数据合同

### 9.1 分层真源

| 数据层 | 一行/一事件 | 主要真源 | 是否可覆盖 |
|---|---|---|---|
| planned assignment | assignment | 冻结 external manifest | 否 |
| stimulus truth | proposal/image | 独立审核 manifest + proposal SHA | 否 |
| LS annotation | 成功 annotation/version | export_label 原始导出 | 否 |
| pre/post 元标签 | annotation response | 同一成功导出及锁定事件 | 否；更正另记版本 |
| preview order | viewer state event | preview_orders JSONL | 否，append-only |
| active time | task-worker event | active_logs | 否，按现行聚合规则派生 |
| derived geometry | annotation × algorithm version | analysis_results | 可重算，不是输入真源 |
| analysis table | analysis unit | 上述真源的显式 join | 可重算，保留 manifest/SHA |

### 9.2 主键与必要字段

assignment 层至少包含：

- experiment_id、protocol_candidate_version、assignment_id；
- project_id、runtime_task_id、planned_task_id、image_id、building_id；
- worker_pseudonym、arm_code、block_id、within-worker order；
- blinded_proposal_id、proposal_truth（研究者侧）、proposal_type、severity；
- image/proposal SHA、assignment_manifest SHA；
- planned eligibility 与 same-worker × same-image exposure check。

annotation/response 层至少包含：

- annotation_id、annotation_version、created_at、updated_at、submitted_at；
- raw geometry、result schema version、instrument_version；
- material_issue、issue_confidence、observed_defects；
- final_layout_confidence、multiple_plausible_layouts、worker_scope_response；
- 每字段 applicability、response_state、first_locked_at（若实现）；
- source export path、source SHA、parse version、join status。

派生层必须保留：

- residual algorithm/frame/reference version；
- external truth/reference version；
- raw order state（observed/canonical/unknown）；
- LOO target 的成员集合、明确排除当前 annotation；
- not-evaluable 原因、QA flag、任何 adjudication 的 reviewer/version。

### 9.3 missing、结构性不适用和逻辑状态

所有分析表至少区分：

- observed：按合同收集到有效值；
- structural_not_applicable：例如 Manual 的 proposal 字段；
- branch_not_applicable：例如 material issue=no 后的 observed defects；
- not_collected_by_instrument：历史版本没有该字段；
- technical_missing：本应收集但技术失败；
- invalid_response：存在值但违反合同；
- not_evaluable：有响应但对应几何/外部结果不能计算；
- unknown_historical：历史来源无法判明。

禁止：

- 把 structural NA、not collected、technical missing 或 not evaluable 填成 no/0；
- 用隐藏字段的旧值补全分支；
- 因 meta 字段缺失而静默删除有效的主要外部结果；
- 把 proposal truth 放入 worker 可见导入字段、URL、文件名或 HTML。

### 9.4 inactive branch 清理

前端隐藏只是第一层。正式合同要求：

1. material issue 从 yes/uncertain 改成 no 时，立即清空 observed defects 的 UI state；
2. 提交前重新根据当前父字段构造 payload，不提交不可用分支；
3. 导出后 fail-closed 校验；发现 inactive branch residual 则标 invalid_response/QA，不替工人猜正确父值；
4. Manual 的所有 proposal 字段无论 DOM 是否存在均必须 structural_not_applicable；
5. scope 导致后续题不适用时使用同样规则；
6. exhaustive test 覆盖 yes→no、yes→uncertain、uncertain→no、取消重选、保存草稿、确认框后二次提交和刷新恢复。

### 9.5 版本与 provenance

每条正式记录必须能追溯：

- protocol/SAP/instrument/assignment/stimulus truth 版本与 SHA；
- XML、userscript、viewer、bridge 和 Label Studio project/config 版本；
- image/proposal/reference/frame/algorithm 版本与 SHA；
- export、preview_orders、active log 的源文件与提取时间；
- worker registry 映射版本，但研究表只保存伪名；
- 所有 join 的一对一/一对多状态、冲突和解决记录。

schema drift、身份冲突、source mismatch 或 active-time owner mismatch 不得静默忽略。

---

## 10. 候选统计分析计划

本节是待仿真和导师确认的候选，不覆盖当前 STATISTICAL_ANALYSIS_PLAN_v1.md。正式实验必须把最终版本单独冻结。

### 10.1 分析单位与 estimand

| RQ | 分析单位 | 目标 estimand | 首要结果/比较 |
|---|---|---|---|
| RQ1 | 新 Manual annotation，嵌套于 image 与 worker | final confidence 与独立外部错误的条件关联/有序趋势 | confidence 每升一级对应的外部错误变化；同时报告非线性等级差异 |
| RQ2 | 所有随机分配的 Semi assignment | Wrong vs Correct 的 assignment-level ITT 总效应 | 两臂共同定义的 residual material error/review-needed 或预冻结连续外部误差；同图配对结构由模型保留 |
| RQ3 | annotation，预测目标按独立外部复核定义 | 在未见 building/image 上加入 meta 后的增量诊断效用 | ΔAUPRC、固定 review budget 下 Δrecall |

Manual vs Semi 只作为 secondary workflow estimand。识别成功者、编辑者或最终修好者的条件分析是 post-treatment 机制描述，不取代 ITT。

### 10.2 外部效标与 LOO 防循环

优先级：

1. 结果不可见前冻结的独立 reference/允许集；
2. 对 condition、worker meta 和 proposal truth 盲的独立审稿；
3. LOO peer/consensus 只作敏感性或分歧结果。

任何 LOO 分数都必须从 target pool 排除当前被评分 annotation。若计算 worker/image 历史风险特征，也必须在每个训练折内重算，不能使用 held-out 记录或同一记录的结果。不得把某人的结果加入 consensus 后再声称该结果与 consensus 的高一致性证明正确。

RQ2 primary 不应依赖由三臂参与者共同构造的 contemporaneous consensus；否则 Wrong 可能改变“真值”本身。主要外部效标必须独立，LOO 只报告其作为有限 roster 的相对结果。

### 10.3 RQ2：Wrong vs Correct 主要因果模型

根据 primary outcome 类型，在 launch 前择一：

- 连续结果：cross-classified linear mixed model；
- 二分类 review-needed/target retained：logistic mixed model，并额外报告可解释的 marginal risk difference；
- 有明显边界/零膨胀的距离：预先指定变换、两部分模型或 randomization inference，不在看结果后挑最显著模型。

最小固定项：

- treatment：Wrong vs Correct；
- 预先冻结的 randomization block/order；
- 仅可加入 treatment 前、与 assignment 无关的 precision covariates。

随机结构至少包括 image 与 worker 截距；若数据和收敛允许，评估 condition 的 worker 随机斜率。敏感性分析包括 image fixed effects 或同图差分、按实际随机化的 permutation/randomization inference、以及双向聚类/cluster bootstrap 的可行实现。

下列变量不得作为总效应模型的普通协变量：

- final internal residual；
- active time；
- initial→final edit amount；
- material issue、issue confidence、final confidence；
- repair success。

它们均可能在 treatment 后产生。把它们加入总效应模型会阻断或扭曲因果路径。若做中介/机制分析，必须单列假设、时间顺序和识别限制，不把中介系数写成随机化效应。

proposal severity 是刺激层的预先属性，但 Correct 与 Wrong 的定义方式不同。只有在 severity 对两臂有共同且事前可解释的量纲时才能作为 precision covariate；否则将 condition 定义为整个 proposal package，并在 Wrong 内按 severity 作 secondary 分层。

### 10.4 RQ1：主观—行为—外部对齐

final confidence 为 1–5 有序等级：

- 首选 cumulative-link mixed model，外部错误/review-needed 为 outcome 或反向建模时必须清楚说明方向；
- 同时报告每个等级的样本数、外部错误率/误差分布和 bootstrap CI；
- Spearman/有序趋势可作直观补充；
- 使用内部 residual 和 image/worker 随机效应检验信心是否不仅反映内部方正度；
- multiple plausible 使用三分类/有序或 multinomial 模型，并与独立多解审稿、LOO 分歧分别比较。

1–5 等级不是概率预测，因此默认不计算 ECE、Brier score 或“校准到 20%/40%/…”的曲线。只有另行收集明确的概率判断并在 launch 前冻结解释，才可使用概率校准指标。

历史 Manual 与新 Manual 不合并估计 confidence 关系，因为历史没有同构 final confidence；历史只提供 geometry baseline、支持度和方差先验。新旧行为分歧可以分 stage/instrument 并列，不能假装完全同一总体。

### 10.5 RQ3：增量风险诊断

#### 目标

优先使用“独立复核判定存在 residual material error / 需要人工复核”的二分类 target；定义必须在模型训练前冻结。若正类太少，先报告基率与可估计性，不临时换成更容易显著的 target。

#### 特征阶梯

- M0 常规层：condition、训练折内可得的 worker/image 特征、proposal severity、owner-valid active time；
- M1 几何层：M0 + R_heading/R_corner/R_height、结构事件、initial→final edit summaries；
- M2 元认知层：M1 + material issue、issue confidence、final confidence、multiple plausible。

Manual 的 proposal 字段保持 structural NA。实现模型时使用显式 applicability/arm interaction，不能把 Manual 的 NA 填成 no。

M0/M1/M2 中 active time、edit summaries 和 final residual 可以用于**预测**，但这不把它们变成 RQ2 的因果调整变量。论文必须将 prediction 与 causal analysis 分节。

#### 验证

- 以 building 为优先 group；building 不足时至少按 image 整组 held out，绝不随机拆 annotation；
- image_id 只作为分组/随机效应身份，不作为预测未见图片的 one-hot 特征；“image 特征”只能是推理时确实可得且不含 target 的冻结图像属性；
- 若主要部署对象是现有 worker pool，可在训练折内使用 worker history；若声称泛化到新 worker，必须另做 leave-worker-out 或 worker-history-unavailable 敏感性，不能把已见 worker 身份带入；
- 相同 folds、target 和 preprocessing 比较 M0/M1/M2；
- worker 历史统计、缺失填补、标准化、阈值选择都只在 training fold 完成；
- 模型保持简单且与样本量相称，优先正则化 logistic/ordinal 或预先指定层级模型，不做大规模算法竞赛；
- 正式选择 nested grouped cross-validation、固定 test split 或两者之一；24 图下若无法稳定 held-out building 评估，RQ3 降为 pilot/探索，不夸大。

主要诊断指标：

- AUPRC 及其相对于正类基率的解释；
- 在预先冻结 review budget（例如最多复核全部任务的 b%，具体 b 由导师决定）下的 recall、precision 和漏检数；
- ΔAUPRC(M2−M1) 与 Δrecall@budget；
- cluster/bootstrap CI，以 building/image 为重采样单元；必要时 worker 也进入交叉重采样敏感性分析。

AUROC 只作补充。残余错误可能是少数类，AUPRC 与 review-budget 指标更直接对应复核操作。不能在 test fold 上调阈值或选择 budget。

### 10.6 多重检验、CI 与最小有意义效应

- 一个 primary contrast + 一个 primary outcome；所有备选结果在冻结时明确 secondary；
- H1-validity 与 H3-incremental 作为 key-secondary family，建议用 Holm 控制 family-wise error，或由导师选择并冻结另一种方法；
- exploratory 结果报告 effect、CI 和未校正状态，不用星号堆叠形成结论；
- 所有主要结果同时报告绝对效应、标准化效应（若有意义）、95% CI、样本/图片/worker 数和缺失；
- 在仿真前冻结最小有意义效应：Δ因果、Δ诊断、review budget 和允许的 precision/recall trade-off；
- p<0.05 但效应低于最小有意义幅度不算强科学成功；
- p≥0.05 且 CI 很宽是“不确定”，不是“无效应”；
- p≥0.05 且 CI 排除最小有害/有益效应，可形成有界的 informative null。

### 10.7 缺失、失败与敏感性

- 所有随机 assignment 按臂报告：planned、opened、submitted、externally evaluable、meta complete、order matched、owner-valid time；
- 工人造成的错误提交或结构失败留在原 assignment/condition，并按预冻结 outcome 定义计入；不得删除来美化结果；
- 外部技术事件或 truth corruption 记 administrative/not-evaluable，按臂报告，不填 0；
- primary outcome 缺失做完整原因表，并按可行性做 worst-case/best-case、inverse-probability 或 bounds 敏感性；方法在看结果前冻结；
- active time 缺失只影响含时间的辅助/诊断模型，不自动删除 RQ2 外部结果；
- signature mismatch 只影响需要精确 order/frame 的分析，不自动删除顺序不敏感的外部结果。

---

## 11. 什么结果算“成功”

技术成功是科学解释的前提，但技术成功本身不证明假设；科学结果也不应只由显著性定义。

### 11.1 结果—解释矩阵

| 观察模式 | 科学解释 | 可支持的贡献 | 不可声称 |
|---|---|---|---|
| Wrong 比 Correct 有更多 residual error/target retention，CI 排除最小有害效应 | 错误 proposal 在强制自审下仍产生因果伤害 | proposal correctness 会改变最终质量；机制与风险诊断可继续解释 | 所有预标注都会伤害 |
| Wrong 引发明显更多修改，但高质量 worker 几乎全部修复，最终差异接近 0 且 CI 足够窄 | 自审工作流成功吸收测试严重度的错误 | 识别—修复链、鲁棒纠错边界；“最终无害”仅限测试 worker/错误/流程 | 实验失败；或一般性证明错误 proposal 无害 |
| Wrong 常被识别但仍保留错误 | 主要瓶颈是修复，不是识别 | 识别失败 vs 修复失败分解有价值 | 提高问题识别题就一定能解决质量 |
| Wrong 很少被识别且错误保留 | 主要瓶颈是错误察觉 | issue 判断的敏感度不足、需要更好提示/复核 | 工人整体低质量，除非有独立证据 |
| Correct 产生大量无必要修改或新错误 | 强制自审/编辑可能诱发 commission error | 正确 proposal 也有工作流代价 | Wrong 与 Correct 等价 |
| final confidence 对外部错误有清楚的有序区分，并超越内部 residual | 主观元认知在本任务有测量效度 | RQ1 的主观—外部对齐 | 信心就是客观概率 |
| M2 在 held-out group 的 ΔAUPRC/Δrecall 达到预定幅度且 CI 支持 | 元标签提供常规信号之外的可迁移诊断信息 | RQ3 增量风险诊断 | 元标签有因果改善作用 |
| 元标签相关但 held-out 增量接近 0 | 元标签可能重复现有 residual/time 信息 | 有限的构念描述；RQ3 强诊断主张不支持 | “多收问卷提高复核效率” |
| 三臂差异接近 0，CI 排除预定重要效应 | 在测试边界内的 informative null | 界定高质量 worker/自审对 proposal 错误的鲁棒范围 | 任意错误、任意 worker、任意场景都无效应 |
| 所有效应 CI 很宽、模型不稳或正类过少 | 研究规模不能区分关键情景 | 仅报告可估计性与下一步功效 | 无效应或机制成立 |
| truth、分配、preview、分支或身份绑定系统性失败 | 技术/合同失败 | 只能形成开发审计 | 正式科学结果 |

因此，“高质量 worker 发现 Wrong 并成功修正”明确**不算失败**。它否定的只是“Wrong 必然污染最终答案”这一强说法，同时支持“强制自审可以触发有效纠错”这一机制边界。真正的失败是设计无法区分这些解释，或技术链不能证明条件、时点和结果对应。

### 11.2 科学支持等级

**强支持**

- primary ITT effect 或预先定义的鲁棒修复边界具有足够精度；
- 至少一个 key secondary（测量效度或增量诊断）达到预定最小有意义幅度；
- 技术 gates 全部满足，结果对预先指定敏感性稳健；
- 结论严格限定于测试 worker、图片、proposal severity 和自审流程。

**部分支持**

- RQ2、RQ1、RQ3 中只有一部分得到精确支持；其他结果明确报告 null/inconclusive；
- 仍可形成一篇围绕“干预机制”或“元认知诊断”的窄论文，但不能把三个 RQ 都写成成功。

**有信息的否定结果**

- 技术与功效合格，CI 排除事前定义的重要效应；
- 可回答“在该边界内未观察到值得关注的 harm/diagnostic gain”，仍有研究价值。

**不确定/失败**

- 功效不足、正类过少、truth 不稳定、systematic missing、时点不可证而仍使用强机制措辞；
- 不能用“趋势正确”“某个 subgroup 显著”补救 primary 失败。

---

## 12. Pilot go/no-go gates

所有阈值必须在 pilot 前写入 instrument acceptance checklist。以下是建议门槛，不是当前已批准数值。

| Gate | 建议通过标准 | 未通过动作 |
|---|---|---|
| stimulus truth | Correct/Wrong 的 truth、目标错误、严重度和允许多解经两名独立 reviewer + adjudication 100% 解析；SHA 冻结 | 修正或替换刺激；对应 pilot 永不入正式 |
| assignment | 100% 满足一 worker 同图一次、arm/proposal 对应、历史暴露检查、truth 不在工人可见 payload | 停止分发，重建 manifest |
| proposal blind | 文件名、URL、UI、网络 payload 的工人可见层不泄露 Correct/Wrong | 阻断 launch |
| 3D preview | 支持浏览器中三臂每个 pilot task 均能显示并随几何正确更新；无整块空白/消失 | 修复后用新 pilot 重测 |
| pre-edit lock | 若主张编辑前识别，首次判断/信心 100% 持久化、不可覆盖，且开放编辑时间在锁定后 | 做不到则按 6.5 降级，不声称时间顺序 |
| form branch | exhaustive state-transition 测试 100% 清除 inactive values；Manual proposal 字段始终 structural NA | 阻断 launch |
| common post fields | 每个成功 pilot submit 都有合法 final confidence、scope 和适用的 multiple plausible | 阻断 launch 或修复表单 |
| submit semantics | submit attempt、确认框取消/确认、二次点击、刷新恢复与最终 export 均可区分 | 未解决前不依赖 attempt 解释成功 |
| order capture | base/submit state 均有 W/H、raw order、version/signature；建议 ≥95% 成功 export 可唯一绑定且 signature match | 低于门槛则放弃精确 order/residual 相关分析，不阻断外部主结果 |
| geometry export | 每个成功 annotation 均可从 export 还原顺序不敏感的 final geometry，身份一对一或冲突显式 | 阻断 launch |
| active time | owner-valid context、项目/任务/worker 映射通过；建议 ≥95% 正式可用 | 不改写主结果；active time 从 RQ3 基线移除或按 missing 报告 |
| UI 可用性 | active-time 小框不遮挡问题/preview，建议右下角紧凑且可拖动；所有必答题和提交按钮可达 | 调整 UI 后重测 |
| manipulation | reviewer truth 成立；worker 对 Wrong 的实际识别率只作 pilot 描述，不以“必须显著”作为 gate | truth 不成立则换刺激；工人识别低本身不是技术失败 |
| provenance | 每条记录具备 instrument/viewer/userscript/manifest/source 版本和 SHA | 阻断正式冻结 |

正式运行可分技术小 block，但中途只能依据预先列明的技术/安全 gate 暂停。不得查看 condition outcome p-value 后停招、换图片、改 Wrong severity、删除工人或改变 primary。

---

## 13. 风险登记与停止/降级规则

### 13.1 风险登记

| 风险 | 可能后果 | 预防/监测 | 预先动作 |
|---|---|---|---|
| 高质量 worker 全修复 Wrong | 最终 arm 差异小 | 同时保存 initial→final、识别与 target retention | 解释为鲁棒修复；用 CI 界定，不增低质 worker |
| Wrong 过强/过弱 | 天花板或地板效应 | 预先定义中等 severity 带并独立审核 | pilot 后若改 severity，旧 pilot 不入主分析 |
| Correct 实际有问题 | treatment contamination | 双 reviewer + blind adjudication + SHA | 图/assignment 记 external truth failure，按冻结规则排除并报告 |
| 图片本身多解 | 单一 reference 错罚合理答案 | multiple plausible 审核、允许集/set scoring | 无法形成稳定允许集则降为 exploratory 或替换 |
| worker 看到 truth | demand characteristic、失盲 | 工人可见 payload 审计 | 立即停 block；受影响记录不得作盲实验 |
| same worker 重见同图 | 记忆/迁移污染 | 外部 manifest 暴露检查 | 受影响 assignment 标 contamination，不静默换臂 |
| pre-edit lock 失败 | 识别时间顺序不可证 | 持久化事件与测试 | 降为 task-time self-report |
| signature/order 绑定失败 | 精确残差/拓扑复现失真 | JSONL + export-bound + mismatch ledger | 丢弃精确 order 分析，不丢外部质量 |
| 内部残差实时反馈 | 新 treatment、worker gaming | 仅离线计算 | 发现反馈立即停 block；受影响批次单列 |
| 表单疲劳/分支残留 | missing、矛盾响应 | 最小必答、exhaustive branch test | 系统性发生则暂停修复；不事后猜值 |
| active-time source mismatch | 时间模型偏差 | owner-valid join audit | 时间设 missing，不改外部 outcome |
| CE 可见性被误当权限 | GT/proposal 泄露 | 项目/批次运营隔离 + 外部分配 | 泄露即安全事件，停 block |
| RQ3 image/building 太少 | 诊断过拟合、CI 不稳 | grouped simulation/validation | 增图或降 exploratory |
| fold 内特征泄漏 | 虚假 AUPRC 增益 | 所有 worker/image 特征训练折重算 | 发现后废弃该分析，重跑独立 pipeline |
| 旧字段强行统一 | construct bias | raw + crosswalk + instrument version | 禁止回写；仅分层/敏感性 |
| 结果后筛 worker/图片 | 选择偏差 | eligibility 与 exclusions 预冻结 | 任何例外进入 deviation ledger 和 ITT 敏感性 |

### 13.2 必须停止当前 block

- proposal truth、arm 或 assignment 映射系统性错误；
- 工人可见 Correct/Wrong truth 或 GT；
- 成功提交的 geometry 无法可靠绑定到 task/worker/annotation；
- 3D preview 对某一 arm 系统性缺失或行为不同；
- inactive branch 值系统性污染；
- instrument/version 无法追溯；
- 数据安全或身份泄露。

停止只暂停后续分发，不删除已产生记录。修复后使用新 instrument version；受影响 block 是否完全 development-only 必须按冻结的 incident rule 决定并记录。

### 13.3 允许降级但不必停止主要外部结果

- order signature match 低：删除精确 order/self-fit 相关结果；
- active time owner-valid 率低：删除时间特征或按 missing 建模；
- pre-edit lock 不成立：降级时间顺序措辞；
- frozen frame 不稳定：删除 fixed-frame residual，保留外部 boundary/IoU/盲审；
- residual error 正类太少：RQ3 降为描述/探索；
- mixed model 不收敛：使用预先仿真验证的简化模型或 randomization inference；
- 24 图功效不足：在看正式 outcome 前增图/重复或缩窄结论；若正式 outcome 已可见，不得数据驱动扩样，除非事前 sequential rule 已冻结。

---

## 14. 执行 SOP

1. **导师裁决**：确认核心贡献、三个 RQ 的层级、primary outcome、最小有意义效应和本研究与 Paper A/T1 的关系。
2. **历史 freeze**：冻结本次使用的 substrate、RQ1 报告、Model Issue audit 和 crosswalk sidecar；不重编码旧数据。
3. **刺激审核**：从候选池确定图片、Correct proposal、Wrong proposal、目标错误、severity、多解允许集和 scope；两名独立 reviewer + adjudication。
4. **instrument contract**：冻结字段、choice、applicability、分支清理、time-lock/降级语义、版本和数据字典。
5. **几何/日志 contract**：冻结 preview_orders JSONL、signature、order normalization、fixed frame、residual 算法和外部 metric 版本。
6. **测试与独立 pilot**：穷举表单组合、三臂提交、确认框、刷新、preview、order/signature、active time 和 export binding；pilot 不入主分析。
7. **功效仿真**：使用历史 variance/ICC/base rate 与实际 assignment 算法决定 image 数、重复数和可支持 RQ 层级。
8. **正式冻结**：研究合同、SAP、stimulus truth manifest、assignment manifest、instrument manifest、分析代码版本、launch approval。
9. **CE-only 分发**：以外部 manifest 为唯一分发合同；项目/批次仅作运营分区；运行映射与 worker sheet 双人核查。
10. **分 block 执行**：只做盲的技术 QA、完成率与安全检查；不查看 outcome significance 调整设计。
11. **原始 closeout**：冻结 export、active logs、preview orders、incident/deviation ledger 和所有 source SHA。
12. **盲分析**：先完成 join/QA 与 arm-blind 派生；锁定 analysis dataset 后才解盲 primary。
13. **完整报告**：按 planned、submitted、evaluable、missing、incident 分层；同时报告支持、null、inconclusive 和 deviations。

### 14.1 预期产物

- 本讨论稿及导师决策记录；
- 经批准后的独立 study contract 与 SAP；
- historical crosswalk sidecar 与 source manifest；
- image/proposal stimulus truth manifest、review/adjudication ledger；
- frozen assignment manifest、worker/runtime mapping、LS import package；
- instrument/XML/userscript/viewer/bridge manifest 与测试证据；
- 原始 export、active_logs、preview_orders JSONL；
- order/signature binding ledger、incident/deviation ledger；
- derived residual/external outcome tables及版本；
- analysis-ready long table、field contract、schema tests；
- simulation/power report、pilot gate report；
- primary/secondary/exploratory 结果、图表与可复现命令。

---

## 15. 导师必须决策的事项

在任何正式实现或分发前，至少逐项确认：

1. 是否接受“主观—行为—外部结果对齐”而非“附加问卷”作为创新核心；
2. RQ1/RQ2/RQ3 哪一个是论文主轴；是否同意只有 Wrong vs Correct 为主要因果比较；
3. primary outcome 是两臂共同定义的 residual material error/review-needed，还是一个连续外部误差；只能冻结一个主要结果；Wrong-specific target-error retention 仅作机制 secondary；
4. 最小有意义的 Wrong−Correct 效应、ΔAUPRC、Δrecall 和 review budget；
5. 24×3×4 是否仅作仿真锚点；最大可承受 image/worker 标注预算；
6. worker 是全新 cohort、历史 cohort 还是混合；任何经验门槛如何在 outcome 不可见时定义；
7. Wrong proposal 的错误家族与 severity 范围；是否需要每类最低图片数；
8. Correct truth、Wrong target error、多解允许集和最终外部结果由谁独立审核；
9. 是否批准 Semi 的 material issue=yes/uncertain/no、issue confidence 和 first-lock；
10. 如果技术 time lock 做不到，是否接受 task-time self-report 的较弱机制结论；
11. 是否批准三臂共同 final confidence 1–5 与 multiple plausible=yes/uncertain/no；
12. scope 使用现行二值运营语义还是新加 uncertain；out-of-scope 后哪些题 structural NA；
13. perceived difficulty/reasons 是否完全删除、可选收集或保留必答；
14. repair actions/extent 是否按建议改为研究者几何派生；
15. 是否批准 preview_orders 独立日志、signature match 不阻断提交和 raw/canonical 双版本；
16. image-level frozen frame 如何产生；哪些外部 metrics 为 primary/secondary；
17. RQ3 的 held-out 单元是 building 还是 image；24 图能否支持；
18. pilot gate 数值、正式 block 大小和技术停止规则；
19. 本研究是 Paper A 的独立补救研究、附加 study，还是未来另稿；不得静默并入正式 T1；
20. 论文允许的最窄成功结论是什么，以及 informative null 是否可接受。

建议导师会后最小动作是：先冻结 1–4、9–11、15–17，再做 instrument pilot 和功效仿真；在此之前不继续扩大候选审核或招募。

---

## 16. 一手文献定位

这些研究用于定位问题，不直接证明本任务会得到相同结果：

- Mikulová 等在依存句法标注实验中直接比较人工标注与高准确率预标注，观察到效率/一致性收益且未见质量下降，说明“预标注效应”取决于 proposal 正确性与任务，而不能先验假定一定有害：[Quality and Efficiency of Manual Annotation: Pre-annotation Bias（LREC 2022）](https://aclanthology.org/2022.lrec-1.312/)。
- Green 与 Chen 通过 algorithm-in-the-loop 实验强调，评价模型辅助不能只看模型本身，还要看人如何接收并修改建议；这支持把 Correct/Wrong proposal 与实际人工结果作为一个社会技术工作流研究：[The Principles and Limits of Algorithm-in-the-Loop Decision Making（CSCW 2019）](https://doi.org/10.1145/3359152)。
- Maniscalco 与 Lau 用 trial-level confidence 区分正确/错误反应来研究 metacognitive sensitivity，说明平均信心高低与“信心能否诊断自己的错误”是不同问题。本研究只借用这种效度思路；当前结构化几何和 1–5 等级不直接满足 meta-d′ 的原任务假设：[A signal detection theoretic approach for estimating metacognitive sensitivity from confidence ratings（2012）](https://pubmed.ncbi.nlm.nih.gov/22071269/)。
- Jiang 与 de Marneffe 对 NLI 分歧进行原因分类，显示分歧可来自语义不确定、annotator bias 与 task artifact。这支持把“多解/证据不确定”与“工人错误”分开，但其 NLP taxonomy 不能直接移植为本项目 truth：[Investigating Reasons for Disagreement in Natural Language Inference（TACL 2022）](https://aclanthology.org/2022.tacl-1.78/)。
- Saito 与 Rehmsmeier 的模拟和重分析说明，在正类稀少场景中 PR 表达更直接对应正例检出表现；因此 RQ3 以 AUPRC 与 review-budget recall 为主，AUROC 只作补充：[The Precision-Recall Plot Is More Informative than the ROC Plot When Evaluating Binary Classifiers on Imbalanced Datasets（PLOS ONE 2015）](https://doi.org/10.1371/journal.pone.0118432)。

正式论文仍需针对 360°布局、几何标注、人机协作、confidence/uncertainty、selective review 和 human label variation 做系统检索，并清楚区分直接证据、相邻任务证据和本研究推断。不得使用“这是第一个……”之类无系统证据的表述。

---

## 17. Launch 前必须填满的冻结空格

以下项目只要仍为空，本研究就不能启动：

- primary outcome = ______；
- Wrong−Correct 的最小有意义效应 Δ因果 = ______；
- RQ3 positive target = ______；
- review budget b = ______；
- ΔAUPRC / Δrecall 最小有意义幅度 = ______；
- image 数 / 每图每臂重复数 / worker 数 = ______ / ______ / ______；
- randomization/block algorithm 与 seed manifest = ______；
- technical time lock = yes / no；若 no，降级文本已确认 = ______；
- stimulus reviewer/adjudicator 与 blind 规则 = ______；
- fixed frame/reference version = ______；
- primary external metric implementation/SHA = ______；
- order signature algorithm/version 与 match gate = ______；
- owner-valid active-time 可用门槛 = ______；
- multiplicity rule = ______；
- missing/administrative incident rule = ______；
- grouped validation unit 与 folds = ______；
- supervisor approval 与日期 = ______。

本表不是授权入口；全部填满后仍需独立的正式合同、SAP 和 launch approval。
