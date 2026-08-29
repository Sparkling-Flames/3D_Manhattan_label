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
- 默认把**连续 delivery-adjusted quality** 作为唯一 primary；二元 remaining error/review-needed 降为安全结果，避免让全部 288 条结果依赖额外双人盲审；
- 把识别失败/修复失败作为机制性 key secondary，把 owner-valid active time 与编辑负担作为效率性 key secondary；
- 把 Semi vs Manual 明确降为“整套 proposal + 强制自审工作流”的次要比较；
- RQ1 主要由历史高密度 Manual 支撑，新 Manual 的 confidence validity 只作估计性补充；RQ3 held-out 增量诊断降为 exploratory，不作为本轮论文成败门；
- 三臂共同只增加两个核心 post-edit 元标签：最终布局信心、多个合理布局判断；scope 保留为运营/可评估性字段；
- Semi 只增加 proposal 问题判断及其信心，并尽可能在编辑前锁定；
- initial/final geometry、proposal SHA 和**提交时最终可见角点顺序**必须绑定；不要求恢复每次拖动轨迹，残差只在研究者侧离线计算且不实时反馈；
- 24×3×4 只作为仿真起点。若功效不够，应增加图片或每图重复数，或降低结论层级，而不是降低工人质量。

### 0.4 当前建议执行层：V2-lite

V2 全文继续保留为方法边界和失败模式清单，但当前执行建议只冻结下表。后文与本表冲突时，V2-lite 代表本轮推荐的优先级；它仍须导师批准和独立 pilot，不能直接启动。

| 层级 | 当前保留 | 当前不承担 |
|---|---|---|
| Confirmatory primary | Wrong-Semi vs Correct-Semi 的连续 delivery-adjusted quality ITT | defect-family 交互、稳定 worker 类型、多峰 prevalence |
| Key mechanism | Wrong 内识别失败、识别后修复失败、target retention；Correct 的无必要退化 | 完整因果中介 |
| Key efficiency | owner-valid `log1p(active_time)`、是否编辑、编辑幅度/角点数变化 | 把时间当质量分数或筛人规则 |
| Supporting | 历史 Manual 分歧基线；新 Manual 的质量/信心与 workflow 对照 | 用每臂 k=4 恢复单图真实分布 |
| Exploratory | 元标签增量诊断、内部残差、连续 worker profile | held-out AUPRC 作为成功门、离散 worker taxonomy |

当前实际启动瓶颈有两个，而不是一个：其一是 24 个经双 reviewer/adjudication 的 matched Correct/Wrong stimulus pairs 尚未齐备；其二是最小 instrument 尚须证明 pre-edit 首次回答不可覆盖、proposal/initial/final geometry 与提交时最终可见 corner order 能唯一绑定。完整 preview event stream、每次拖点轨迹和高级 residual 不属于 primary launch blocker。

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

主要因果比较只在 Semi 内进行：同一批图片、同一界面和同一强制自审流程中，随机呈现 Correct 或 Wrong proposal，跨臂比较 initial→final 修改和两臂同义定义的最终外部错误/复核需求；target-error retention 仅在 Wrong 内作为机制结果。

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

**H2-primary：** 在 Semi 强制自审工作流内，Wrong 与 Correct proposal 对连续 **delivery-adjusted quality** 产生不同的 assignment-level ITT 总效应。V2-lite 默认使用与现行合同同构、但须为本研究另行冻结版本的候选定义：

```text
Q_DA(final) = IoU(final, frozen eligible reference)   if structurally valid
              0                                       if worker-caused structural failure
              not_evaluable                           if external/technical/reference failure
```

这不是把所有 `structurally_valid=false` 机械乘成 0：只有可归因于 worker submission 的结构失败进入原 condition 并计 0；外部加载、绑定、reference 或行政失败保持 not_evaluable。若一张图存在多个经 reviewer 确认的合理完整布局，必须在 outcome 不可见前冻结 allowed-reference set 及 scoring；为保持 V2-lite 简单，优先排除无法形成稳定单 reference/有限允许集的图片。二元 remaining material error/review-needed、target-error retention 和新引入错误降为安全/机制结果。

- 零假设：Wrong−Correct 的主要结果差异为 0；
- 方向性预期可登记为 Wrong 更差，但必须同时报告双侧 95% CI；
- condition 按随机分配分析，不因工人识别、是否编辑或最后修好而改组；
- 最终残差、active time、编辑幅度和 material issue 都可能受 treatment 影响，不作为估计总效应的普通调整协变量。

### 4.2 Key secondary：机制与效率成本

**H2-mechanism：** Wrong 的失败分解为未识别、识别后未修复和修复时引入新错误；Correct 单列无必要编辑或质量退化。即使 primary 最终质量差接近 0，也可检验错误是否被主动识别和修复。

**H2-efficiency：** Wrong 相对于 Correct 是否增加 owner-valid active time、发生编辑的概率和编辑幅度。时间是 treatment 后的效率/纠错成本 outcome，不是 worker 能力分数，也不进入 primary 总效应的普通调整项。

### 4.3 Supporting 与 exploratory

Supporting / estimative：

- 历史 Manual 的连续几何分歧、结构数量差异与方差分量；
- 新 Manual 中 final confidence 与外部质量的有序关系；
- Correct-Semi、Wrong-Semi 各自相对于 Manual 的工作流差异；
- multiple plausible 与 LOO 分歧、独立复核多解状态的关联；

Exploratory：

- held-out building/image 中元标签相对常规信号的增量 AUPRC/固定预算 recall；样本或正类不足时只报告可估计性；
- 缺陷类型、proposal severity、图片证据类型与 condition 的交互；
- perceived difficulty/difficulty reason 与行为/结果的关系；
- per-layout self-fit 残差、canonical order 方向和局部修改模式；
- worker 随机斜率或潜在策略差异，仅在数据支持时报告，不据此建立稳定 worker 类型学。

只有 primary 家族可以承载最终质量的确认性因果结论。机制和效率 key secondary 解释该结果如何产生、付出何种成本；RQ1 新测量关系与 RQ3 预测只提供支持或生成下一步假设，不再决定本轮研究是否成功。

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
- worker 资格必须在看到本实验 outcome 前按既有批准规则或独立 prescreen 冻结；历史表现最多作为预先定义的描述/precision covariate，不据本实验结果删除“修得太好/太差”的 worker，也不把 meta/active-time 变成新的 roster gate；
- worker 间不得共享 proposal truth 或讨论具体图片；历史暴露按 same-worker × same-image 在正式分发前核查；
- 独立 stimulus reviewers 不参与对应图片的工人标注，结果评估尽可能对 condition 和工人元标签盲。

候选分配算法采用最小的受约束随机化：先生成 `image × arm × replicate_slot` 空位，再用冻结 seed 在 eligible workers 中随机填充，同时硬约束 same-worker×same-image 不重复、每臂每图达到目标重复数、worker workload cap；软约束每位 worker 的臂数量和任务顺序尽量平衡。若某 seed 不满足硬约束，可在不查看任何 outcome 的前提下重抽，并在 manifest 记录所有失败 seed/理由；满足后一次性冻结 assignment manifest，运行中不手工换臂。

同一 worker 连续看到多种 proposal 后，可能学会“这些 proposal 有时会错”，从而提高后续任务的审查强度；这属于跨任务学习/干扰，而不是 same-image 重复。短平快方案不为此改成纯 between-worker 三臂，因为那会把 worker 差异与 arm 强绑定并显著增加招募需求。正式 estimand 应明确为**混合任务序列下的 pragmatic assignment effect**，用平衡随机顺序限制偏差，并预先报告首个 Semi 任务的低功效敏感性、condition × 任务序号以及累计既往 Wrong 暴露的探索性异质性；若顺序效应很强，结论不得外推到单次首次使用场景。

### 5.2 24×3×4 只是计划锚点

候选锚点为：

- 24 张正式图片；
- 每图 Manual、Correct-Semi、Wrong-Semi 各 4 个独立 worker 结果；
- 总计 288 条正式 assignment。

这不是 288 个独立统计单元。图像和 worker 是交叉聚类来源，Correct/Wrong 又共享 image。正式启动前必须使用历史 Manual 方差、image ICC、worker ICC、连续结果分布、二分类残余错误基率、预期缺失率和实际分块算法做仿真。

V2-lite 的一个可行运营排程是 16 名 active worker + 4 名预注册 reserve：把 16 人在每个四图循环分配到 Manual / Correct / Wrong / Unexposed 四个 4 人组，循环内轮换，6 个循环后每名 active worker 各完成 6 个 Manual、6 个 Correct、6 个 Wrong，共 18 题。它只是待程序校验的候选 Latin-square 式排程；reserve 只能按 outcome 不可见时冻结的替补规则进入，不能在看到表现后手工换人。最终仍以 assignment manifest 的约束验证为准，而不是以这段文字为准。

每个 image-arm 的 `k=4` 只支持平均质量、平均 dispersion 和粗粒度 topology disagreement。它不支持单图低频模式 prevalence、稳定多峰数量、“恢复真实 annotation distribution”或客观 multiple-plausible 判定；`2/4` 或 `3/4` 工人回答 multiple plausible=yes 仍只是主观响应比例。历史高密度重抽样也只表明 k=5 对有限 roster 平均连续分歧的 ±0.03 恢复率约 0.648、对既有多种 cardinality 的检出率约 0.634，并未验证完整几何模式恢复。

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

用假定 `SD=0.10` 和任意 design effect 推出的 0.057/0.068 一类 MDE 只能作数量级 sanity check，不能冻结为本设计的功效结论；它忽略 bounded `Q_DA`、same-image pairing、交叉 worker、实际缺失和随机化约束。正式决定仍须用实际 assignment 算法仿真。

### 5.3 Pilot 不进入主分析

instrument pilot 与正式实验必须使用不同 assignment。V2-lite 默认使用 6 张不进入正式 Main 的图片 × 3 臂 × 每臂 2 人 = 36 次 pilot action，覆盖 yes/no/uncertain、scope 分支、不同角点数和至少一种 binding mismatch。Pilot 只验证操纵、可修复性与数据链，不估计 Wrong−Correct 效应，也不根据 p 值或方向选择 Main 图片。

若 pilot 后修改任何科学字段、truth 定义、主要结果、随机化、残差算法或问法，pilot 永久标为 development，不并入正式分析。

### 5.4 当前刺激池 readiness（截至 2026-08-29，仅作运营快照）

现有审核口径为 36 张：原始决定 18 PASS、6 REVISE、12 REJECT；但按当前字段合同机械检查，暂只有 14 张可直接进入候选池。以下 4 张虽标 PASS，仍需复核后才能决定是否恢复资格：

- `B1-004`、`B1-022`：同时标记结构无效；
- `B1W-040`：`wrong_material=no`，却保留缺陷和修复字段；
- `B1W-110`：结构有效性仍为 uncertain。

所以当前距离 24 张的机械缺口是 10 张，而不是 6 张；上述 4 张经独立复核可能缩小缺口，但不得为凑数自动改为 eligible。14 张干净候选的主错误家族暂为 boundary shift 7、current-space undercoverage 5、spurious non-layout structure 2；尚无确认可用的 adjacent-space inclusion 或 duplicate/redundant corner。

这意味着当前池能够支持“proposal correctness 的总体效应”候选设计，但还不能自动支持对所有错误家族的平衡比较或交互结论。正式刺激冻结前应：

1. 先完成上述 4 张的一致性复核；
2. 从剩余 broad pool 定向补充，但不降低 truth/结构/可修复性门槛；
3. 若某错误家族仍缺失，就把该家族从正式泛化范围排除，而不是人工制造弱 truth；
4. 24 张全部通过双 reviewer + adjudication 后，才进入功效仿真和 assignment freeze。

### 5.5 Correct/Wrong proposal pair 的候选合同

每张正式图片必须同时冻结一个 Correct 与一个 Wrong proposal；二者都能被同一 viewer/编辑工具正常加载，不能把“技术损坏”当作 Wrong。

- **Correct**：两名独立 reviewer 按同一 materiality rubric 判断，即使 worker 不修改也可接受；允许亚像素/非实质视觉差异，但不得含已知必须修正的问题。
- **Wrong**：包含至少一个预先命名、可定位、可修复且达到 material threshold 的目标错误；同时保持整体外观足够合理，避免一眼可见的崩坏/自交成为纯注意力测试。
- 优先使用同一模型/流程的自然 proposal 与其最小必要专家修正版形成 pair；若人工注入错误，注入规则、操作者、坐标 delta、版本和理由必须冻结，且另报 natural/injected 来源。
- severity 在 worker 结果不可见前，由独立外部 metric + 盲 reviewer 共同分级。不能以 pilot 中“骗倒多少 worker”反向定义 severity。
- 若 Correct 与 Wrong 除目标错误外还存在多处差异，本研究估计的是整个 proposal package 的效果；只有满足预先冻结的单一差异合同，才能把效应归因到某个 defect family。
- Wrong 的 target-error retention 使用 proposal-specific target mask/segment/corner set 与容许修复区间定义；Correct 没有同义 target，因此该指标不得用于跨臂 primary。

### 5.6 Worker 进入设计的方式

历史证据支持“控制交叉 worker 差异”，不支持建立离散工人类型：geometry 的 task/worker/residual 方差份额约为 65.25%/2.75%/31.99%，quality IoU 约为 55.99%/2.91%/41.10%；另一个探索性聚类的最高 silhouette 仅 0.201，task split-half median ARI 仅 0.120（IQR 0.011–0.266）。因此：

- primary 模型保留 worker random intercept/blocking；
- 只有实验前冻结、与本实验 outcome 无关的连续历史指标可作可选 precision covariate；没有它们也不损害随机化识别；
- Wrong correction、Correct degradation 和 confidence validity 是本实验结果，只能事后描述或 cross-fit，不能先用它们定义类型再在同一数据上检验类型；
- 速度—质量或质量—干预安全图可以作为带支持量和区间的 descriptive profile，不切四象限、不命名 reliable/sloppy/spammer 类型。

active time 的历史 task/worker/residual 方差份额约为 11.56%/51.72%/36.73%，说明其 worker-specific pace 成分很强；这正是把它作为随机化条件下效率成本 outcome、而不是能力或不确定性分数的理由。

---

## 6. 最小元标注与时点设计

### 6.1 三臂共同的 post-edit 核心

所有条件在几何完成后使用相同措辞和顺序收集。先回答 scope，再决定布局相关题是否适用：

1. **worker_scope_response（运营/可评估性字段，必答）**
   - 保持“当前相机空间是否至少支持一个完整、闭合、单层 Manhattan 布局”的现行语义；
   - 不把“难”“多解”自动视为 out of scope。
2. **final_layout_confidence（1–5，有序等级；仅 in-scope 时必答）**
   - 1：把握很低，认为最终布局很可能仍有需要复核的实质性问题；
   - 2：把握较低，更倾向于认为仍需实质复核；
   - 3：无法可靠判断最终布局是否仍需实质复核；
   - 4：把握较高，更倾向于认为可以接受，但仍有有限疑虑；
   - 5：把握很高，未发现需要复核的实质性问题。
3. **multiple_plausible_layouts（yes / uncertain / no；仅 in-scope 时必答）**
   - yes：至少两个实质不同的完整布局同样受到图像证据支持；
   - uncertain：无法可靠判断是否存在第二个同样合理的完整布局；
   - no：未发现第二个同样合理的完整布局；
   - 轻微坐标差异不算“多个布局”。

若 worker 回答 out of scope，则 final layout confidence 与 multiple plausible 均记为 structural_not_applicable，而不是强迫回答低信心/no。若未来需要“对 OOS 判断的信心”，必须新增独立 `scope_confidence` 构念，不能借用 final layout confidence；本轮最小方案不新增。

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

该 pre-edit 提问本身是一种 cognitive forcing/self-audit，不是无害测量：它可能提高错误察觉并改变后续编辑。Correct 与 Wrong 都接受完全相同的提问，因此二者仍可识别 proposal truth/package 的随机化差异；但任何 Semi vs Manual 结果只能解释为“proposal + 强制自审 + 不同起点”的联合工作流效应。本轮短平快方案不再增加“有 proposal 但无提问”的第四臂；若导师要分离提问效应，必须另立实验而不是事后声称已经分离。

分支规则：

- material issue=yes：observed defects 至少选一项；
- material issue=uncertain：显示 observed defects，但允许空集合；空集合表示无法定位具体类型，不等于 no issue；
- material issue=no：observed defects 必须隐藏并在前端 state、提交 payload 和服务端校验三处清空；
- 工人可以在锁定后看到自己的首次判断，但不能覆盖它；若需要收集事后修正意见，应写入单独字段，不能改写首次判断。

yes 分支比 no 分支更长，存在“为了省步骤选 no”的预期成本偏差。最低缓解是先原子锁定 material issue + issue confidence，再展示任何 checklist；pilot 还必须检查 material_issue=no 是否随任务序号上升、yes 分支额外耗时和缺失是否系统性增加。若出现明显分支成本效应，正式方案应把 observed defects 降为非必答 exploratory，或在锁定后向三个状态统一展示同长度 checklist（含 none/unclear），而不是用结果后加权补救。选择哪一种必须在 launch 前冻结。

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

**V2-lite 最小边界：** primary 不要求鼠标轨迹或持续 preview stream。每个成功提交只必须绑定 blind assignment/task/worker、proposal JSON+SHA、initial geometry+order、final exported geometry、确认提交时 iframe 的 final visible order、W/H/版本以及唯一 binding disposition。若预先验证并冻结的 canonical reconstruction 能保证与工人可见连接完全等价，可用它替代 final visible order；否则 order 缺失会使依赖 polygon/topology 的 `Q_DA` not_evaluable，不能仅称为“少了一个探索性 residual”。下述完整 raw-event 合同只在需要精确时点审计、preview 复现或 order/residual 扩展时启用。

### 7.1 为什么必须记录

全景布局的同一无序点集可对应不同的环向连接、起点和方向。3D preview 依据某个具体顺序构造墙段；如果分析只拿最终点坐标后自行猜序，就可能计算出与工人当时看到的 preview 不同的拓扑和残差。

因此，当前可见的环向顺序是**解释提交几何所需的运行时状态**。它不是鼠标级完整轨迹，也不需要记录每次拖动。V2-lite 最低只记录最终成功 submit 对应的可见状态；若启用完整审计层，再记录：

- proposal/preview 首次稳定可见时的 base state；
- 每次 submit attempt 当下的 visible state；
- Label Studio 最终成功导出后可绑定的 submitted state。

### 7.2 不能只读 localStorage

localStorage 可被覆盖、跨任务残留、缺少 annotation/attempt 身份，且不保证与当前 iframe 内 preview 状态同步。可靠采集必须从正在显示该任务的 viewer/bridge 取得显式状态，并同时写入身份、版本、尺寸和签名。localStorage 最多作为调试线索，不能作为正式真源。

截至本稿日期，正式 userscript 仅在显式“保存顺序”时把 override 写入标注者浏览器；iframe 虽会返回当前 `previewOrder/previewSignature`，父脚本尚未把它们持久化到研究服务器，现有 manifest 也明确 `phase_event_persistence=not_collected`。因此下述合同是待实现、待 pilot 的候选，不描述已存在能力。

### 7.3 三层记录合同：raw event、离线富化、export binding

不得把浏览器当时可知的原始事件、冻结 manifest 才知道的实验真值和最终导出才能确定的绑定结论混成一层。

1. **runtime raw event（`preview_orders_*.jsonl`）**
   - 只发送盲化 assignment key、project/runtime task、worker registry key、session、viewer 状态和几何状态；
   - 不发送真实 `arm_code=Correct/Wrong`、proposal truth、GT 或其他可能破坏网络层盲法的字段；
   - `annotation_id` 在创建前允许缺失，不能为满足 schema 伪造占位值。
2. **server/offline enrichment（派生 sidecar）**
   - 由冻结 assignment/stimulus manifest 补充 planned task、image/building、batch/block、真实 arm、blinded proposal 与 proposal truth；
   - enrichment 必须保存 manifest 版本、SHA 和 join status，不能回写 raw event。
3. **export-binding ledger（派生 binding ledger）**
   - 由 Label Studio 最终导出补充 annotation/version、最终 geometry signature 和绑定结论；
   - `export_bound` 是研究侧派生状态，不伪装成浏览器产生的 preview event。

worker identity 只使用批准的伪名/registry key，不在研究日志复制真实姓名。三个层次的字段适用性如下：

| 记录/事件 | 当时必须存在 | 允许缺失或结构性不适用 |
|---|---|---|
| `base_visible` raw event | event/session identity、blind assignment key、project/runtime task、worker key、有效 viewer state、preview base corners、当前可见 order、preview W/H 与来源、runtime signature、版本 | annotation_id、真实 arm、proposal truth、submit geometry、binding disposition |
| `submit_attempt` raw event | event_id、attempt_id、attempt_stage、上述 runtime identity、最后有效 preview snapshot、当下 submit geometry、两套签名、W/H、版本 | annotation_id 若尚未创建；真实 arm/truth 始终不在 raw payload |
| offline enrichment | raw event key、冻结 manifest key/version/SHA、planned/image/building/batch/block/arm/proposal truth、join status | manifest 无匹配时保留 unresolved，不猜值 |
| export-binding ledger | event/attempt key、export annotation/version、全精度 binding signature、binding disposition、candidate count、理由、source SHA | 无唯一匹配时为 unbound/ambiguous，不选最近一条代替 |

runtime raw event 的最小字段族为：

| 类别 | 必需字段 |
|---|---|
| 盲化身份 | blind_assignment_key、project_id、runtime_task_id、worker_registry_key、session_id |
| 事件 | event_id、event_type、attempt_id（submit lifecycle 才适用）、attempt_stage、client_timestamp、server_received_at、sequence_no |
| 图像坐标 | preview_image_width/height、submit_image_width/height、各自 source、dimension_status、coordinate_system、seam_convention |
| 几何 | preview_base_corners、current_visible_order_raw、order_source、submit_base_corners、corner_count、pairing_algorithm_version |
| 签名 | runtime_preview_signature/version、export_binding_geometry_signature/version（客户端可计算候选，但正式值由离线层复算）、match components/status、mismatch_reason |
| 软件 | viewer_runtime_version、userscript_version、Label Studio project/config version、browser bridge version |
| 溯源 | source_endpoint、record_type、record_created_at；server 对实际收到的原始 body 计算 payload hash |

`base_visible` 只在当前 iframe 已 ready、收到本任务的 `update_layout`，随后又从可信 `event.source === iframe.contentWindow` 返回通过校验的 state 后成立。仅父 DOM ready、仅点击“刷新”或 iframe 尚未回传有效 state，都不能记为 `base_visible`。父脚本必须保留 iframe 当前可见的 `previewOrder/previewSignature`；标注者换序但未点“保存”时，也必须记录实际可见顺序。

### 7.4 raw order 的精确定义与校验

当前实现中的 order 不是 Label Studio 原始 `results` 数组下标，而是 viewer bridge 生成的 `pairedDefault/base_corners` 的排列。候选 v1 合同冻结为：

- 先从当前 LS keypoints 生成点集，按 x 排序，并按 `5% × image_width` 阈值配成 vertical pairs；完整过程写入 `pairing_algorithm_version`；
- `base_corners` 保存配对后的默认数组及其每个元素的来源点身份/坐标；
- `order_index_base=0`；`order_applies_to=base_corners`；
- `current_visible_order_raw` 必须是长度等于 `corner_count`、元素不重复、全部位于 `[0, corner_count-1]` 的完整排列；
- 墙边按相邻 order 元素连接，最后一个元素显式闭环连接到第一个；
- 任一排列、corner count、来源点或算法版本不合法时，顺序状态为 invalid，不得自动修补后进入正式分析。

默认 x 排序、5% 配对阈值只是当前候选实现，不因写入本文而升格为最终规范；pilot 后必须随 engine/bridge 版本冻结并测试 seam、重复 x、增删 corner 和无法配对情形。

### 7.5 submit attempt、确认框与最终导出的生命周期

点击提交、弹出确认框或触发 submit hook 只证明发生了 attempt。每条 raw event 使用全局唯一 `event_id`；同一次提交意图共享 `attempt_id`，并使用：

- `attempt_stage=intent`：用户触发 submit/update/Ctrl+Enter；
- `attempt_stage=confirm_accepted`：确认框明确接受；
- `attempt_stage=confirm_cancelled`：确认框取消；
- `attempt_stage=client_unknown`：浏览器无法观察最终确认结果。

网络重试必须复用同一 `event_id`，服务器按 `event_id + payload hash` 幂等去重；相同 event_id 出现不同 body 时拒绝并进入 quarantine。最终研究侧 binding ledger 再写：

- `attempt_disposition=export_bound`；
- `attempt_disposition=unbound`；
- `attempt_disposition=ambiguous`；
- `attempt_disposition=cancelled_or_validation_blocked`（有充分证据时）；
- `attempt_disposition=unresolved`。

正式绑定流程为：

1. 在 intent 时重新读取当前 LS keypoints，保存 submit geometry；同时保存最后一个由 iframe 确认的 preview state；
2. Label Studio 成功创建/更新 annotation 后，以最终导出记录为事实真源；
3. 使用 blind assignment/project/task/worker、时间窗口、instrument/bridge version、corner count 和全精度 geometry signature 离线生成候选绑定；
4. 唯一且所有必要组件一致时，在独立 binding ledger 写 `export_bound`；
5. 多个候选或任一关键组件不一致时保留全部候选与 mismatch 原因，不静默选最近一条。

签名必须拆分：

- `runtime_preview_signature`：保持现有 viewer/cache guard 的舍入与排序语义，用于判定缓存/可见状态是否陈旧；
- `export_binding_geometry_signature`：由冻结算法对全精度坐标、固定 base 排序、W/H、坐标系、corner count 和 pairing/version 计算，用于正式 export binding；
- 完整 `preview_base_corners` 与 `submit_base_corners`：签名冲突时的最终仲裁证据。

“精确复现”要求几何签名、pairing/signature 算法版本、W/H、坐标系、corner count 和当前 raw order 均一致。现有 0.1 px 舍入的 cache signature 单独不足以证明精确绑定。

W/H 必须分别保存 preview 与 submit 值、`image_width_source/image_height_source`，并标记 `dimension_status=observed/default_fallback/mismatch`。使用 1024×512 等默认回退、来源未知或 preview/submit 尺寸不一致时，不得标为精确复现。

signature mismatch 不应阻断工人提交，以免研究日志破坏正式标注任务；但 mismatch 记录不能声称精确复现了工人提交时的 preview。

### 7.6 原始顺序与规范化顺序同时保存

正式分析不得覆盖 current_visible_order_raw。另行派生：

- rotation-canonical：在保持方向的前提下，按冻结规则选择环的起点；
- reversal-canonical：仅在分析明确允许反向等价时，在正向/反向中选择冻结的规范表示；
- topology signature：基于 normalization version 计算，不与原始签名混写。

任何对旋转、反向、全景 seam 的等价处理都必须有版本。若某分析对方向有物理含义，则不得应用 reversal canonical。

历史记录按来源标记：

- observed：只有冻结的 viewer/bridge 事件明确保存了当时可见的 base corners、raw order、版本和身份，且可与导出绑定；
- canonical：只能证明某个冻结算法的规范序，不能声称是当时可见顺序；
- unknown：无法恢复；仍可用顺序不敏感的 mask/边界指标，但不能进入精确 preview-order 分析。

Label Studio export 中 `results` 的数组顺序不等于 observed preview order；历史浏览器 localStorage 若没有在当时冻结导出并完成身份/签名绑定，也不能事后升级为 observed。缺少 viewer/bridge 原始事件的历史数据原则上只能标 canonical 或 unknown。

### 7.7 与 active time 严格分流

preview_orders JSONL 只记录几何状态事件；active_times 日志只记录批准的 task-worker active-time 事件。两者可以通过不可变身份离线连接，但：

- 不把角点事件混入 active-time 文件；
- 不用角点事件间隔重建 lead time；
- 不因 preview_orders 缺失改写正式 active-time；
- 不因 active-time 缺失丢弃外部质量结果，除非独立的 eligibility 规则另有规定。

即使复用现有 `/log_time` 的 nginx 路由和 token，服务器也必须先按严格白名单 `record_type` 分流：active-time 记录只能进入 `active_times_*.jsonl`，preview/order 记录只能进入 `preview_orders_*.jsonl`；未知类型拒绝或进入 quarantine。pilot 必须做负向断言：

- 所有 `active_times_*.jsonl` 中 preview record 数为 0；
- 所有 `preview_orders_*.jsonl` 中 active-time record 数为 0；
- 未知/非法 record type 不进入任一正式真源；
- 重试不会生成重复科学事件；同 event_id 的冲突 body 被隔离。

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
2. **R_turn：相邻墙转角残差**
   - 使用现有 engine 已实现的相邻墙夹角，计算其到最近允许 Manhattan 转角（90°，必要时按冻结合同处理 180°）的角距离；
   - 报 unweighted mean、max 和按相邻墙长度加权的 mean；
   - 明确使用原始可见顺序还是 canonical 顺序；
   - 不把它称为“角点重投影误差”，因为现有 engine 尚未实现理论交点到 submitted corner 的独立重投影残差。
3. **R_height：单一地面/天花高度一致性**
   - 由各墙段/角点推断的 floor/ceiling height 对统一高度的偏差；
   - 报稳健中心、MAD/绝对残差 mean 和 max；
   - 对无法稳定推断的布局记 not_evaluable，不填 0。
4. **结构事件**
   - self-intersection count/rate；
   - short-wall count/rate（短平快主方案沿用并冻结现有 engine 的绝对 3D 长度与相对中位墙长双阈值及版本）；
   - duplicate/redundant corner flag；
   - non-closure/topology invalid flag。

真正的 **R_corner_reprojection**（理论墙交点重投影到 submitted corner 的像素/球面角残差）只列为未来可选扩展。只有完成实现、独立数值验证、单位/周期/seam 测试并冻结版本后，才能进入正式候选指标；本轮主方案不为它新增算法。

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
- independent review-needed / remaining material error（不要与内部几何 residual 混称）。

外部 reference/truth 必须在工人结果不可见时冻结或由对 condition 盲的独立复核产生，并记录多解允许集。存在多个合理布局时，不能强迫所有 worker 向单一 reference 收缩；应采用允许集最小距离、盲审可接受性或预先定义的 set-valued scoring。

若把 binary remaining material error/review-needed 选为 primary，最终 annotation 必须以随机顺序呈现给不知道 condition、proposal、worker meta 和其他 worker 结果的两名独立 reviewer；分歧按冻结 rubric adjudicate，并保留两名原始判断、adjudication 与版本。IAA 只描述 reviewer 一致性，不能替代 outcome 定义。若资源无法支持对全部正式结果的双盲复核，就应在 launch 前改选经过验证的共同连续外部 metric 为 primary，而不是正式运行后用未经验证的单 reviewer 判断补救。

---

## 9. 数据合同

### 9.1 分层真源

| 数据层 | 一行/一事件 | 主要真源 | 是否可覆盖 |
|---|---|---|---|
| planned assignment | assignment | 冻结 external manifest | 否 |
| stimulus truth | proposal/image | 独立审核 manifest + proposal SHA | 否 |
| LS annotation | 成功 annotation/version | export_label 原始导出 | 否 |
| pre/post 元标签 | annotation response | 同一成功导出及锁定事件 | 否；更正另记版本 |
| preview runtime state | viewer raw event | preview_orders JSONL（只含盲化 runtime 字段） | 否，append-only |
| preview offline enrichment | raw event × frozen manifest | 可重算 enrichment sidecar | 可重算，不回写 raw event |
| preview export binding | attempt × export annotation/version | 可重算 binding ledger | 可重算，保留全部候选与 disposition |
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
- pairing algorithm、order index base/order target、runtime signature 与全精度 export-binding signature 的版本和值；
- preview/submit W/H、来源、dimension status、event/attempt/binding disposition；
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
| RQ1 supporting | 历史与新 Manual，嵌套于 image 与 worker | 输出分歧基线；新数据的 final confidence 与独立外部质量关系 | image-level dispersion/方差分量；confidence 有序趋势及 CI |
| RQ2 primary | 所有随机分配的 Semi assignment | Wrong vs Correct 的 assignment-level ITT 总效应 | 连续 `Q_DA`；同图配对与交叉 worker 结构由模型保留 |
| RQ2 mechanism/cost | Wrong/Correct assignment，按字段适用性 | 识别、修复、过度干预与效率成本 | failure proportions/target retention；`log1p(active_time)`、编辑概率/幅度 |
| RQ3 exploratory | annotation，预测 target 若可稳定定义 | 在未见 building/image 上加入 meta 后的探索性增量诊断效用 | ΔAUPRC、固定 review budget 下 Δrecall；不作成功门 |

Manual vs Semi 只作为 secondary workflow estimand。识别成功者、编辑者或最终修好者的条件分析是 post-treatment 机制描述，不取代 ITT。

### 10.2 外部效标与 LOO 防循环

优先级：

1. 结果不可见前冻结的独立 reference/允许集；
2. 对 condition、worker meta 和 proposal truth 盲的独立审稿；
3. LOO peer/consensus 只作敏感性或分歧结果。

任何 LOO 分数都必须从 target pool 排除当前被评分 annotation。若计算 worker/image 历史风险特征，也必须在每个训练折内重算，不能使用 held-out 记录或同一记录的结果。不得把某人的结果加入 consensus 后再声称该结果与 consensus 的高一致性证明正确。

RQ2 primary 不应依赖由三臂参与者共同构造的 contemporaneous consensus；否则 Wrong 可能改变“真值”本身。主要外部效标必须独立，LOO 只报告其作为有限 roster 的相对结果。

### 10.3 RQ2：Wrong vs Correct 主要因果模型

V2-lite 默认以连续 `Q_DA` 为唯一 primary，使用 cross-classified linear mixed model，并以实际随机化的 image-level paired permutation/randomization inference 作为稳健性分析。若 pilot 表明 `Q_DA` 的 reference、边界质量或分布无法通过冻结 gate，必须在 Main outcome 不可见前替换 primary 并重做功效仿真；不能保留多个备选 primary 等结果后挑选。二分类 review-needed/remaining material error 仅为安全 secondary，Wrong 内 target retention 为机制 secondary。

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

机制结果先报告 Wrong 的识别失败、识别后修复失败、target retention 和修复引入新错误的分母、比例与 image-clustered CI；Correct 报告无必要编辑和 quality degradation。样本支持时再用 mixed logistic/连续模型，不能为每个 defect family 拆一套确认性检验。

效率结果使用：

```text
log1p(owner_valid_active_time) ~ condition + task_order + block + (1|image) + (1|worker)
```

同时报告 Wrong−Correct 的几何均值比/中位数差、编辑概率、edit magnitude 和 corner-count change。worker 内中心化时间可作描述性敏感性。active time 缺失不删除对应 `Q_DA`；时间、编辑和识别变量均不进入 primary 总效应模型作普通协变量。

### 10.4 RQ1：主观—行为—外部对齐

先回答最基础的“到底有多不一致”。对历史和新 Manual 分别计算 image 内所有有效 worker pair 的 periodic boundary distance、mask/region overlap 与拓扑/scope 是否一致，并报告 image-level 中位数、IQR、上分位数、达到预定实质差异阈值的比例，以及 image/worker/剩余方差分量。连续几何、类别状态和外部正确性不能硬压成一个通用 IAA；同一 image 产生的多个 pair 也不是独立样本，区间估计应按 image（必要时再按 worker）重采样。历史结果按 stage/instrument 分层，不用新问卷值回填旧记录。LOO/peer disagreement 描述 roster 内分歧，不充当真值。

final confidence 为 1–5 有序等级：

- 主分析只包含按冻结合同可回答 final confidence 的 in-scope records；out-of-scope 的结构性 NA 不填低分，也不进入该模型，scope correctness 另行报告；
- 首要效度模型令独立外部错误/review-needed 为 outcome，使用 mixed logistic（或外部连续误差对应的 mixed model），把 confidence 作为预先指定的有序趋势项并用等级 factor 作非线性敏感性；
- 反向的 cumulative-link mixed model（confidence 为 ordinal outcome，外部正确性/误差为 predictor）只作互补的响应模型，不能与首要效度模型混写；
- 同时报告每个等级的样本数、外部错误率/误差分布和 bootstrap CI；
- Spearman/有序趋势可作直观补充；
- 使用内部 residual 和 image/worker 随机效应检验信心是否不仅反映内部方正度；
- multiple plausible 使用三分类/有序或 multinomial 模型，并与独立多解审稿、LOO 分歧分别比较。

1–5 等级不是概率预测，因此默认不计算 ECE、Brier score 或“校准到 20%/40%/…”的曲线。只有另行收集明确的概率判断并在 launch 前冻结解释，才可使用概率校准指标。

历史 Manual 与新 Manual 不合并估计 confidence 关系，因为历史没有同构 final confidence；历史只提供 geometry baseline、支持度和方差先验。新旧行为分歧可以分 stage/instrument 并列，不能假装完全同一总体。

### 10.5 RQ3：探索性增量风险诊断

#### 目标

RQ3 不再是 V2-lite 的成功门，也不为它扩大问卷或标注预算。只有在独立复核能稳定定义二分类 target、正类数与 held-out building/image 数达到事前可估计门槛时才运行；否则只报告基率、缺失和“当前不可估计”，不临时换 target。

#### 特征阶梯

- M0 常规层：condition、训练折内可得的 worker/image 特征、proposal severity、owner-valid active time；
- M1 几何层：M0 + R_heading/R_turn/R_height、结构事件、initial→final edit summaries；
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
- 识别/修复与效率成本组成两个预先冻结的 key-secondary family；若对同一 family 内多个指标作确认性声明，使用 Holm 或事前层级检验；
- RQ1 新 confidence validity 与 RQ3 incremental diagnosis 均按 supporting/exploratory 报告，不以其 p 值挽救 primary；
- exploratory 结果报告 effect、CI 和未校正状态，不用星号堆叠形成结论；
- 所有主要结果同时报告绝对效应、标准化效应（若有意义）、95% CI、样本/图片/worker 数和缺失；
- 在仿真前冻结 `Q_DA` 的最小有意义 Wrong−Correct 效应、机制差异与可接受效率成本；只有实际运行 RQ3 时才另冻 Δ诊断、review budget 和 precision/recall trade-off；
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
| Wrong 的 `Q_DA` 低于 Correct，CI 排除预冻最小有害效应；安全结果方向一致 | 错误 proposal 在强制自审下仍产生因果伤害 | proposal correctness 会改变最终质量；机制结果解释伤害来自哪里 | 所有预标注都会伤害 |
| Wrong 引发明显更多修改/时间，但多数被修复，`Q_DA` 差异接近 0 且 CI 足够窄 | 自审工作流以额外成本吸收测试严重度的错误 | 识别—修复链、鲁棒纠错边界与纠错成本；“最终无害”仅限测试 worker/错误/流程 | 实验失败；或一般性证明错误 proposal 无害 |
| Wrong 常被识别但仍保留错误 | 主要瓶颈是修复，不是识别 | 识别失败 vs 修复失败分解有价值 | 提高问题识别题就一定能解决质量 |
| Wrong 很少被识别且错误保留 | 主要瓶颈是错误察觉 | issue 判断的敏感度不足、需要更好提示/复核 | 工人整体低质量，除非有独立证据 |
| Correct 产生大量无必要修改或新错误 | 强制自审/编辑可能诱发 commission error | 正确 proposal 也有工作流代价 | Wrong 与 Correct 等价 |
| Wrong 与 Correct 的 `Q_DA` 接近，但 Wrong active time 明显更长 | 最终质量相近不是“零成本无害”，而是人工吸收了 proposal 错误 | 同质量下的效率代价 | active time 证明了更高或更低能力 |
| final confidence 对外部错误有清楚的有序区分，并超越内部 residual | 主观元认知在本任务有测量效度 | RQ1 的主观—外部对齐 | 信心就是客观概率 |
| M2 在 held-out group 的 ΔAUPRC/Δrecall 达到预定幅度且 CI 支持 | 元标签提供常规信号之外的可迁移诊断信息 | RQ3 增量风险诊断 | 元标签有因果改善作用 |
| 元标签相关但 held-out 增量接近 0 | 元标签可能重复现有 residual/time 信息 | 有限的构念描述；RQ3 强诊断主张不支持 | “多收问卷提高复核效率” |
| 三臂差异接近 0，CI 排除预定重要效应 | 在测试边界内的 informative null | 界定高质量 worker/自审对 proposal 错误的鲁棒范围 | 任意错误、任意 worker、任意场景都无效应 |
| 所有效应 CI 很宽、模型不稳或正类过少 | 研究规模不能区分关键情景 | 仅报告可估计性与下一步功效 | 无效应或机制成立 |
| truth、分配、preview、分支或身份绑定系统性失败 | 技术/合同失败 | 只能形成开发审计 | 正式科学结果 |

因此，“高质量 worker 发现 Wrong 并成功修正”明确**不算失败**。它否定的只是“Wrong 必然污染最终答案”这一强说法，同时支持“强制自审可以触发有效纠错”这一机制边界。真正的失败是设计无法区分这些解释，或技术链不能证明条件、时点和结果对应。

### 11.2 科学支持等级

**强支持**

- primary `Q_DA` ITT effect，或预先定义的鲁棒修复边界，具有足够精度；
- 识别/修复和效率成本至少能够区分“未发现”“发现但未修”“修复且付出成本”“无须修复”中的关键路径；
- 技术 gates 全部满足，结果对预先指定敏感性稳健；
- 结论严格限定于测试 worker、图片、proposal severity 和自审流程。

**部分支持**

- primary、机制或效率中只有一部分得到精确支持；其他结果明确报告 null/inconclusive；
- 仍可形成围绕 proposal correctness、纠错机制或效率成本的窄结论；RQ1/RQ3 的探索结果不能被写成确认性成功。

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
| 3D preview | 当前候选实现按“显式刷新”更新：三臂每个 pilot task 在每次刷新后均准确反映当时 geometry，无整块空白/消失；记录最后有效 preview 与 submit geometry 是否一致 | 修复后用新 pilot 重测；若未来改自动更新，另冻 debounce/version/tests |
| pre-edit lock | 若主张编辑前识别，首次判断/信心 100% 持久化、不可覆盖，且开放编辑时间在锁定后 | 做不到则按 6.5 降级，不声称时间顺序 |
| form branch | exhaustive state-transition 测试 100% 清除 inactive values；Manual proposal 字段始终 structural NA | 阻断 launch |
| branch burden | 首次 issue+confidence 在 checklist 前原子锁定；检查 no 比例随任务序号、yes/no 缺失与额外耗时，无明显“省步骤选 no”模式 | 改为统一 post-lock checklist 或把 defects 降为非必答后重测 |
| common post fields | 每个成功 pilot submit 都有合法 scope；in-scope 时有 final confidence 与 multiple plausible，out-of-scope 时二者均为 structural NA | 阻断 launch 或修复表单 |
| submit semantics | event_id/attempt_id 幂等；intent、确认框取消/确认、二次点击、表单校验拦截、刷新恢复与最终 export disposition 均可区分 | 未解决前不依赖 attempt 解释成功 |
| final submit geometry/order binding | 36 个 pilot action 中，所有成功提交都能把 proposal SHA、initial geometry/order、final export geometry 和确认提交时 final visible order 唯一绑定；换序未点“保存”、保存后再改 geometry、刷新、非法排列和 W/H fallback 均覆盖 | 若 `Q_DA` 依赖该顺序且无已验证等价 reconstruction，则阻断 launch；单条正式失败记 not_evaluable，不猜序 |
| extended preview/order audit | 若启用 base-visible/多 submit attempt/residual 扩展，建议 ≥95% 成功 export 可唯一匹配完整事件与签名 | 未达门槛则删除完整 event-stream、精确时点/residual 扩展，不影响已通过的最小 final binding |
| log segregation | 所有 active-time 文件中 preview record=0，所有 preview-order 文件中 active-time record=0；未知类型隔离；重试无重复/冲突科学事件 | 阻断 launch，修复 server dispatch/loader 后重测 |
| geometry export | 每个成功 annotation 均可从 export + final-order binding 还原实际提交 polygon/topology；身份一对一或冲突显式 | 阻断 launch |
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
| 跨任务学习/干扰 | 后期更警惕，效应依赖任务序列 | 臂顺序平衡、记录 prior-arm history、检查 condition×任务序号 | 限定为 mixed-sequence pragmatic effect；首个 Semi 任务作敏感性，不事后改 between-worker 解释 |
| pre-edit lock 失败 | 识别时间顺序不可证 | 持久化事件与测试 | 降为 task-time self-report |
| final geometry/order 绑定失败 | 提交 polygon、拓扑和 `Q_DA` 可能复现错误 | final submit snapshot + export binding + mismatch ledger | 单条记 not_evaluable；系统性发生则停 block，不猜序 |
| 扩展 preview event/signature 失败 | 精确时点或 residual 复现不足 | 独立 JSONL 与 binding ledger | 删除 event-stream/residual 扩展，保留已验证的 final binding 与 primary |
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
- remaining material error 正类太少：RQ3 降为描述/探索；
- mixed model 不收敛：使用预先仿真验证的简化模型或 randomization inference；
- 24 图功效不足：在看正式 outcome 前增图/重复或缩窄结论；若正式 outcome 已可见，不得数据驱动扩样，除非事前 sequential rule 已冻结。

---

## 14. 执行 SOP

1. **导师裁决**：确认 V2-lite 的一主两副层级、`Q_DA` primary、最小有意义效应和本研究与 Paper A/T1 的关系。
2. **历史 freeze**：冻结本次使用的 substrate、RQ1 报告、Model Issue audit 和 crosswalk sidecar；不重编码旧数据。
3. **刺激审核**：从候选池确定图片、Correct proposal、Wrong proposal、目标错误、severity、多解允许集和 scope；两名独立 reviewer + adjudication。
4. **instrument contract**：冻结字段、choice、applicability、分支清理、time-lock/降级语义、版本和数据字典。
5. **最小几何/日志 contract**：冻结 proposal/initial/final geometry、提交时 final visible order、W/H、pre-lock、post fields、owner-valid active time、reference version 和 export binding；只有启用 residual/精确时点扩展时才冻结完整 preview event stream、两套 signature 与 fixed frame。
6. **36-action 独立 pilot**：6 张非 Main 图片 × 3 臂 × 2 人，穷举表单分支、三臂提交、确认框、刷新、preview、final order、active time 和 export binding；pilot 不入主分析。
7. **功效仿真**：使用历史 variance/ICC、`Q_DA` 分布、缺失与实际 assignment 算法决定 image 数和重复数；不为 exploratory RQ3 扩大当前设计。
8. **正式冻结**：研究合同、SAP、stimulus truth manifest、assignment manifest、instrument manifest、分析代码版本、launch approval。
9. **CE-only 分发**：以外部 manifest 为唯一分发合同；项目/批次仅作运营分区；运行映射与 worker sheet 双人核查。
10. **分 block 执行**：只做盲的技术 QA、完成率与安全检查；不查看 outcome significance 调整设计。
11. **原始 closeout**：冻结 export、active logs、final-order bindings、incident/deviation ledger 和所有 source SHA；完整 preview events 若启用则另冻。
12. **盲分析**：先完成 join/QA 与 arm-blind 派生；锁定 analysis dataset 后才解盲 primary。
13. **完整报告**：按 planned、submitted、evaluable、missing、incident 分层；同时报告支持、null、inconclusive 和 deviations。

### 14.1 预期产物

- 本讨论稿及导师决策记录；
- 经批准后的独立 study contract 与 SAP；
- historical crosswalk sidecar 与 source manifest；
- image/proposal stimulus truth manifest、review/adjudication ledger；
- frozen assignment manifest、worker/runtime mapping、LS import package；
- instrument/XML/userscript/viewer/bridge manifest 与测试证据；
- 原始 export、active_logs、final-order binding raw records；完整 preview_orders JSONL 仅在扩展启用时产生；
- geometry/order binding ledger、incident/deviation ledger；
- derived residual/external outcome tables及版本；
- analysis-ready long table、field contract、schema tests；
- simulation/power report、pilot gate report；
- primary/secondary/exploratory 结果、图表与可复现命令。

---

## 15. 导师必须决策的事项

在任何正式实现或分发前，至少逐项确认：

1. 是否接受“主观—行为—外部结果对齐”而非“附加问卷”作为创新核心；
2. 是否同意 RQ2 Wrong vs Correct 为唯一确认性主轴，RQ1 为 supporting、RQ3 为 exploratory；
3. 是否批准连续 `Q_DA` 为唯一 primary，并接受 worker-caused structural failure=0、external/technical/reference failure=not_evaluable 的归因边界；
4. 最小有意义的 Wrong−Correct `Q_DA` 效应、机制差异和效率成本；RQ3 指标不再是 launch 决策；
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
15. 是否批准“final visible order 必须绑定、完整 preview event stream 可选”的 V2-lite 边界；
16. `Q_DA` 的 prospective reference/允许集如何产生；哪些二元安全 outcomes 为 secondary；
17. 是否接受 RQ3 在 24 图下仅探索，若正类/building 不足则不建模；
18. pilot gate 数值、正式 block 大小和技术停止规则；
19. 本研究是 Paper A 的独立补救研究、附加 study，还是未来另稿；不得静默并入正式 T1；
20. 论文允许的最窄成功结论是什么，以及 informative null 是否可接受。

建议导师会后最小动作是：先冻结 1–5、9–12、15–16，同时继续完成刺激物复核与补足；达到 24 个 eligible pairs 后再做 36-action instrument pilot 和功效仿真，在此之前不招募正式 Main。

---

## 16. 一手文献定位

这些研究用于定位问题，不直接证明本任务会得到相同结果：

- Mikulová 等在依存句法标注实验中直接比较人工标注与高准确率预标注，观察到效率/一致性收益且未见质量下降，说明“预标注效应”取决于 proposal 正确性与任务，而不能先验假定一定有害：[Quality and Efficiency of Manual Annotation: Pre-annotation Bias（LREC 2022）](https://aclanthology.org/2022.lrec-1.312/)。
- Berzak 等在“人工编辑 parser 输出”的句法标注中观察到锚定、解析器性能高估和相对人工起点更低的标注质量；它与上述无明显伤害的结果形成关键对照，进一步说明不能把 proposal 是否正确、任务类型和人工纠错过程混为一个平均“预标注效应”：[Anchoring and Agreement in Syntactic Annotations（EMNLP 2016）](https://aclanthology.org/D16-1239/)。
- Green 与 Chen 通过 algorithm-in-the-loop 实验强调，评价模型辅助不能只看模型本身，还要研究人如何接收和使用模型信息；这支持把 Correct/Wrong proposal 与实际人工结果作为一个社会技术工作流研究：[The Principles and Limits of Algorithm-in-the-Loop Decision Making（CSCW 2019）](https://doi.org/10.1145/3359152)。
- Maniscalco 与 Lau 用 trial-level confidence 区分正确/错误反应来研究 metacognitive sensitivity，说明平均信心高低与“信心能否诊断自己的错误”是不同问题。本研究只借用这种效度思路；当前结构化几何和 1–5 等级不直接满足 meta-d′ 的原任务假设：[A signal detection theoretic approach for estimating metacognitive sensitivity from confidence ratings（2012）](https://pubmed.ncbi.nlm.nih.gov/22071269/)。
- Jiang 与 de Marneffe 对 NLI 分歧进行原因分类，显示分歧可来自语义不确定、annotator bias 与 task artifact。这支持把“多解/证据不确定”与“工人错误”分开，但其 NLP taxonomy 不能直接移植为本项目 truth：[Investigating Reasons for Disagreement in Natural Language Inference（TACL 2022）](https://aclanthology.org/2022.tacl-1.78/)。
- Saito 与 Rehmsmeier 的模拟和重分析说明，在正类稀少场景中 PR 表达更直接对应正例检出表现；因此 RQ3 以 AUPRC 与 review-budget recall 为主，AUROC 只作补充：[The Precision-Recall Plot Is More Informative than the ROC Plot When Evaluating Binary Classifiers on Imbalanced Datasets（PLOS ONE 2015）](https://doi.org/10.1371/journal.pone.0118432)。

正式论文仍需针对 360°布局、几何标注、人机协作、confidence/uncertainty、selective review 和 human label variation 做系统检索，并清楚区分直接证据、相邻任务证据和本研究推断。不得使用“这是第一个……”之类无系统证据的表述。

---

## 17. Launch 前必须填满的冻结空格

以下项目只要仍为空，本研究就不能启动：

- primary `Q_DA` 定义、方向和实现版本 = ______；
- Wrong−Correct 的最小有意义 `Q_DA` 效应 Δ因果 = ______；
- 识别/修复与效率成本的 key-secondary family/阈值 = ______；
- image 数 / 每图每臂重复数 / worker 数 = ______ / ______ / ______；
- randomization/block algorithm 与 seed manifest = ______；
- technical time lock = yes / no；若 no，降级文本已确认 = ______；
- stimulus reviewer/adjudicator 与 blind 规则 = ______；
- prospective reference/allowed-set version 与 eligibility = ______；
- primary external metric implementation/SHA = ______；
- final geometry/order binding algorithm、版本与 match gate = ______；
- preview/submit W/H 来源与 dimension fallback policy = ______；
- pre-lock/final-order/active-time dispatch 与 idempotency version = ______；
- owner-valid active-time 可用门槛 = ______；
- multiplicity rule = ______；
- missing/administrative incident rule = ______；
- supervisor approval 与日期 = ______。

以下只在决定实际运行 exploratory RQ3 或完整 residual/event-stream 扩展时填写，不阻断 V2-lite primary launch：RQ3 target、review budget、ΔAUPRC/Δrecall、grouped folds、fixed frame、runtime preview signature 与完整 event-stream gate。

本表不是授权入口；全部填满后仍需独立的正式合同、SAP 和 launch approval。
