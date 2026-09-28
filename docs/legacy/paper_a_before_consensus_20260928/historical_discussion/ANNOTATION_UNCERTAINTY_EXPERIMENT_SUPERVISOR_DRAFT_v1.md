# 360°布局标注不确定性研究：完整实验方案（导师讨论稿 v1）

> **状态：DRAFT / NON-NORMATIVE / NOT APPROVED**  
> **用途：仅供与导师讨论、修改和确认，不是正式协议，不得据此直接生成任务或启动实验。**  
> **日期：2026-08-28（讨论稿修订）**
> **建议方案：20名标注者、72张拟纳入实验图片、每图5 Manual + 5 Correct-Semi + 5 Wrong-Semi、24图×3批次。**

本轮修订发生在导师尚未正式沟通或批准之前。全文中的 RQ、样本量、字段和分析方法都只是候选；`Manual` 默认按协议假定为独立标注，但不声称平台事件能够逐条证明独立性。20人是候选实验 cohort 的规模，不绑定历史工人，可以全部招募新工人。

## 0. 文档边界

本草稿提出一项新的、以标注不确定性为中心的候选研究。它与当前 Paper A 正式方法合同分开讨论。

本草稿不会也不得自动改变：

- `PAPER_A_METHOD_CONTRACT_CURRENT.json`；
- 当前 `STATISTICAL_ANALYSIS_PLAN_v1.md`；
- 已关闭的 C2-B、C2-A-RP 结果与 closeout；
- 正式 T1 的 `Manual/Semi × ordinary/stress_assist`、每图 `2+2` 设计；
- 已有 Label Studio 项目、线上配置、导入包或 assignment manifest；
- `export_label/`、`active_logs/`、`import_json/` 中的事实真源。

如果导师认可本研究方向，仍需另行完成：研究问题确认、刺激物审核、字段与界面确认、统计分析计划冻结、assignment manifest、导入包、运行映射和启动审批。本草稿本身不产生任何冻结或部署效力。

---

## 1. 研究动机与核心机制链

已有数据和文献共同提示：标注者之间的差异不能全部视为随机错误；共享模型预标注也可能同时带来有益信息和共同锚定。因此，本研究不把“标注越一致越好”作为前提，而是研究以下机制链：

```text
无预标注时的自然布局输出分歧
            ↓
正确或错误的共享预标注改变最终标注分布
            ↓
标注者能否在编辑前识别 Model Issue
            ↓
识别是否落实为有效修正，以及最终质量和分歧如何变化
```

本研究的创新候选不在单独计算 IAA，也不在重复证明“正确 AI 可能帮助、错误 AI 可能误导”，而在于将以下三层放进同一个 360°结构化几何标注框架：

1. 自然的结构化标注分歧；
2. 正确性受控的共享初始化对多人输出分布的干预；
3. 编辑前 Model Issue 判断、后续行动和最终结果之间的联系。

---

## 2. 研究问题

### RQ1：标注者之间到底有多不一致？

在没有共享模型预标注的条件下，独立标注者对同一张 360°布局图片的最终结果有多不一致？这种不一致由以下哪些部分组成：

- 连续几何/空间范围不同；
- 当前数据可可靠恢复的离散结构代理（如垂直边界数量）不同；
- 在有限工人池中是否出现受支持的候选模式；
- 图片/任务、标注者主效应以及图片×标注者/残差成分。

### RQ2：预标注如何改变这种不一致？

相对于 Manual：

- Correct-Semi 是否压缩、保持或扩大最终标注分歧？
- Wrong-Semi 是否造成错误同质化、生产性分化或噪声放大？
- Correct-Semi 与 Wrong-Semi 的分布干预方向和大小是否不同？

### RQ3：Model Issue 与结果有什么联系？

在 Semi 条件下：

- Wrong proposal 是否比 Correct proposal 更容易被判断为存在 material issue？
- 多名标注者对 Model Issue 的投票本身有多不一致？
- 编辑前的 Model Issue 判断和信心，与是否编辑、编辑幅度、纠错成功、错误保留、正确 proposal 的无必要修改及最终结果有什么联系？

---

## 3. 总体研究结构

研究由两个相互补充的部分组成。

### Study 1：历史数据中的自然标注不确定性

主要回答 RQ1。使用现有 P1–C2-A-RP 数据中按协议默认独立的 Manual 输出，不增加新的高密度重复标注。这里的“独立”是 protocol assumption，不是由阶段锁或事件日志逐条证明的事实。

### Study 2：Correct/Wrong proposal 三臂随机实验

主要回答 RQ2 和 RQ3。使用对相应被分配标注者而言此前未见过的图片；不要求该图从未被其他历史工人标注，比较：

```text
Manual
Correct-Semi
Wrong-Semi
```

Study 1 提供单图“深度”，Study 2 的 Manual 臂提供跨图片“广度”。两者的任务来源和协议版本需分别报告，不静默混成同一种数据。

---

## 4. 当前数据依据与可回答边界

### 4.1 中性数据底座

当前 retrospective 底座包含：

- 2,501条 canonical worker–task 记录；
- 2,513个原始版本，其中12条 raw-only revision 不作为独立分析单位；
- 26名历史标注者；
- 214张图片；
- 22个 building；
- 43个 proposal；
- 574条 Semi response；
- 2,438条可计算 raw geometry；
- 2,069条正式 active time。

旧 workflow eligibility 字段在新不确定性研究中只保留为历史 provenance，不作为全局过滤器。但“全部数据可使用”不等于“全部数据进入同一个 estimand”：重复版本、几何不可计算、OOS、Manual、Semi、缺失时间各自进入能够回答的分析层。

### 4.2 当前高密度 Manual 数据

当前 Manual 数据不能只分成“42张可用、其余不可用”。最新去重与可计算性审计得到：

| 支持层 | 批次×图片单元数 | 当前可回答内容 |
|---|---:|---|
| `k≥5` | 118 | 图片级连续分歧分布、困难/时间辅助关联 |
| `k=2–4` | 60 | 成对或小样本描述、分层敏感性 |
| `k=1` | 39 | 有效性、元标签和时长；不能估计同图人际分歧 |
| `k=0` | 1 | 显式记为不可评估 |

218个 Manual 单元对应187张唯一图片；同图跨批次重复不算新的独立图片。42张 P1/C1 高密度图（每图23–26个可计算结果）仍是有限工人池人数校准的主层，另有4张 C2-B `k=19–20` 任务作为不同批次复核，不能无条件混成同一总体。

42张高密度图足以描述当前任务样本和当前历史有效工人池中的平均连续分歧，并评估人数下采样后统计量的恢复；它尚不足以证明完整几何模式、多个正确答案或总体多峰发生率。图片级独立样本量不是标注条数或标注对数。

### 4.3 少数模式检出能力

最新下采样直接以42张 P1/C1 高密度图的有限历史有效工人池为目标。在每图23–26个 strict-valid 结果中无放回抽取 `k={3,5,8,10,12,15,20}`，每个节点重复1000次：

- `k=5` 时，`P(|D_mask(k)-D_mask(full)|≤0.03)=0.648`；`k=8` 为0.751；`k=15` 为0.909。
- 在 full roster 确有多个垂直边界数量的任务中，`k=5` 检出多个 count 的平均概率为0.634；`k=8` 为0.731；`k=15` 为0.882；`k=20` 为0.954。

这些概率只衡量有限历史 roster 的统计量恢复，不外推到全新工人总体，也没有验证完整几何模式。Study 2 每臂 `k=5` 的职责仍是估计跨图片平均分歧干预；它不承担单图低频模式 prevalence 的精确恢复。

### 4.4 方差证据

当前既有全数据交叉方差分解约为（不是为本轮RQ1 Manual子集重新拟合；不同 outcome 的可用行和任务集合不同，比例不可相互当作同一量纲比较）：

| 结果 | 图片/任务方差 | worker方差 | 残差 |
|---|---:|---:|---:|
| geometry disagreement | 65.25% | 2.75% | 31.99% |
| quality IoU | 55.99% | 2.91% | 41.10% |
| log active time | 11.56% | 51.72% | 36.73% |

geometry 的 worker 主效应较小不表示“人的成分可以忽略”：31.99%的残差还混合了图片×标注者反应、测量误差与未建模因素。它只说明在现有交叉数据中，稳定的跨任务 worker 平移远小于图片差异。研究平均分布干预时应优先增加独立图片；时间分析则必须控制 worker 差异。

### 4.5 文献再核验边界

早期调研可作为研究背景，但以下结论必须按原始论文降级：

| 文献 | 可支持 | 不能推出 |
|---|---|---|
| [Zhou et al., CCL 2021](https://aclanthology.org/2021.ccl-1.48/) | 机标人校与人机独立流程的一致性和成本不同，作者讨论认同倾向 | 不是“2022《清华大学学报》”；也不是同图随机 Correct/Wrong proposal 因果实验 |
| [Sensakovic et al., Medical Physics 2010](https://pmc.ncbi.nlm.nih.gov/articles/PMC2874038/) | 共同初始轮廓使三名观察者的平均两两 Jaccard 从0.371升到0.796，74.5%仅轻微修改，直接证明初始化会压缩输出差异 | 没有独立真值和时间记录，不能说一致性提高等于质量提高，也没有检验“正确帮助、错误伤害” |
| [Mikulová et al., LREC 2022](https://aclanthology.org/2022.lrec-1.312/) | 高精度 parser 预标注约提速1.7倍，提高一致性且未观察到质量损失 | 不能外推到错误 proposal 或全景布局 |
| [Kiani et al., npj Digital Medicine 2020](https://www.nature.com/articles/s41746-020-0232-8) | 临床诊断中正确建议帮助、错误建议伤害，支持 proposal correctness 是重要调节因素 | 任务是诊断而非几何标注，只能作为邻近机制证据 |
| [Schroeder et al., Findings ACL 2025](https://aclanthology.org/2025.findings-acl.1323/) | LLM 建议提高主观信心、改变标签分布，却没有加快标注 | 网页与正式PDF的参与人数元数据不一致，引用时不应无说明地写精确N；主观NLP也不等于布局标注 |

因此，本项目可以把“共享 proposal 改变人类输出分布”作为有文献动机的问题，但 Correct/Wrong 对分歧、墙体残差和最终质量的方向都必须由本实验检验，不能预写成结论。

---

## 5. Study 1：历史无辅助标注输出差异与操作性可复现性

### 5.1 分析层

#### A. Protocol-assumed independent Manual outputs

用于估计无共享 proposal 时的自然标注分布：

- condition 为 Manual/unassisted；
- canonical 独立分析单位；
- geometry 可计算；
- OOS 与 in-scope 分开报告；
- revision 不重复计数；
- 旧 `formal_assignment_eligible` 不作为新研究的全局过滤门。

#### B. Dense Manual population

用于模式和多峰分析：

- 主报告 `k≥12`；
- 单列 P1 的 `k≈24–26` 与 C1 的 `k=23`；
- 低支持 C2 任务不得用于精确估计多峰 prevalence。

#### C. All canonical context

用于：

- 数据覆盖、版本、缺失与可计算性；
- task/worker 方差分解；
- active-time 来源审计；
- stage/condition provenance。

#### D. Historical Semi population

用于观察性描述：

- proposal retention；
- initial-to-final 修改；
- 历史 Model Issue 与行为错位；
- Manual/Semi 分布差异。

历史 Semi 的 proposal correctness 未随机化，因此不得用于 Correct/Wrong 因果结论。

### 5.2 RQ1 指标

#### 5.2.1 总体连续不一致

候选主指标为每图平均两两布局不相似度：

\[
D_{\text{mask},i}
=\frac{2}{k_i(k_i-1)}
\sum_{a<b}\left[1-\operatorname{IoU}\{M(Y_{ia}),M(Y_{ib})\}\right].
\]

其中 `M(Y)` 是当前仓库已实现的 `1024×512` equirectangular wall-region mask：对 ceiling/floor pairs 在水平轴做 panorama-periodic 插值，在每列填充 ceiling 与 floor 之间的布局区域；seam 两侧连续处理。`D_mask=0` 表示两个 mask 相同，越大表示图像平面布局区域差异越大。角点对数量可以不同，但两份 geometry 均须通过 pairing、coverage 与数值有效性检查；不可计算结果不赋为最大距离，另进入结构有效率、原因与support统计。

正式启动前必须冻结 raster 分辨率、pair normalization、periodic interpolation、round/clip、invalid处理、实现路径、测试版本与代码 SHA。若计划使用的 Wrong 刺激敏感性检查显示 `D_mask` 对某类实质错误不敏感，应在任何 worker outcome 可见前修改主指标或收缩声明，而不是事后换指标。

#### 5.2.2 可可靠恢复的离散结构代理

当前原始数据没有冻结且经验证的角点循环顺序，完整 topology signature（转向序列、闭合、简单环和 seam/cyclic invariance）不作为确认性指标。次要结果只使用可以从当前输出稳定计算并审计的代理：

- point/corner count；
- vertical boundary cardinality；
- geometry computability / structural validity。

cardinality disagreement 只能写成“离散结构代理差异”，不能改称完整房间拓扑差异。

#### 5.2.3 连续几何敏感性

`D_mask` 对范围和部分结构差异敏感，但不是完整拓扑距离，也不直接测量相对可见墙体的残差。boundary/wall pairwise 指标可作为同源几何敏感性；当前不强行实现需要唯一 cyclic correspondence 的 same-topology RMSE。若未来确实收集并验证顺序信息，再另行增加，不在本稿中预留复杂签名。

#### 5.2.4 候选模式

聚类目前只作 threshold-status 和候选抽样诊断，报告阈值、可计算性与下采样敏感性。算法分组不自动等于多个合理布局；只有在盲审和重采样都支持同一分区、成员与原型时，才可升级为稳定模式证据。本稿不把 cluster 数、entropy 或“多峰率”列为确认性结果。

### 5.3 “人的不确定性”如何进入 RQ1

人的成分不等于工人质量，也不只等于 worker 主效应。当前数据可区分三个描述层：

1. **task/item 成分**：某些图片在当前协议和工人池下普遍更易产生分歧；
2. **worker 主效应**：有人跨图系统性使用更多/更少结构或更靠近多数结果；
3. **item×worker/残差**：不同人对同一图片证据作出不同反应，加上测量误差和未建模因素。

现有 geometry 方差分解为 task 65.25%、worker 2.75%、残差31.99%。这支持“图片是主要稳定来源，人的条件反应仍占有实质部分”，但不能把残差全部命名为人的内部不确定性。当前没有同一工人的盲重复图，无法估计同一个人的 test–retest 波动。

worker tendency 的确有部分证据：任务分层置换显示 largest-mode participation 和任务中心化结构数量存在工人异质性；但 supported-minority tendency 没有证据，Manual 随机 split-half 的 worker largest-mode rate 中位 Spearman 仅0.257（IQR 0.149–0.360）。因此不建立“锚定型/探索型”等工人画像，只报告连续 worker/random-effect 与稳定性边界。

质量是另一条轴：与 reference 偏离可能是错误，也可能是可见图像支持的替代解释。人的差异只有在独立 reference、结构有效性或盲审支持后才能被解释为质量差异；不得用“与多数人不同”直接定义低质量。

---

## 6. Study 2：三臂随机实验

### 6.1 推荐规模

主建议为：

```text
20名活跃标注者
72张拟纳入实验图片
每图5 Manual + 5 Correct-Semi + 5 Wrong-Semi
每图15份结果，5名标注者对该图不暴露
24张图 × 3个批次
```

这里的20人可以全部是新工人。新 cohort 需统一 onboarding、中文说明、练习图和界面版本，并让每人跨多个图片与三个条件重复贡献，以便在模型中估计 worker 效应。历史工人画像不是 RQ2/RQ3 主效应估计的前提；只有研究“历史行为能否预测未来 reliance”时才必须继续使用原工人。若混合新旧工人，应预先记录 cohort，并分层或加入 cohort interaction，不能无条件合并。

总任务量：

| 项目 | 单批24图 | 最终72图 |
|---|---:|---:|
| Manual submissions | 120 | 360 |
| Correct-Semi submissions | 120 | 360 |
| Wrong-Semi submissions | 120 | 360 |
| Semi submissions合计 | 240 | 720 |
| worker-actions总计 | 360 | 1,080 |

每名标注者：

| 项目 | 每批 | 三批合计 |
|---|---:|---:|
| Manual | 6 | 18 |
| Correct-Semi | 6 | 18 |
| Wrong-Semi | 6 | 18 |
| Semi合计 | 12 | 36 |
| 总任务 | 18 | 54 |

这低于每人 Manual 20–30、Semi 40–50 的上限，并保留每人2个Manual和4个Semi的补漏空间。

### 6.2 为什么是每图总计15份

每图 `5/5/5` 的目标是估计跨图片的平均分布干预，不是重建每个条件下的完整少数模式分布。

`15人/条件` 需要45名独立标注者。候选设计规模为20人；让同一人重复看同一图的不同条件会产生记忆、学习和锚定污染，不能视为45份独立证据。

### 6.3 Worker–image 分配

每个4图小循环：

1. 用冻结随机种子将20名标注者分为4组，每组5人；
2. 四组在4张图中循环承担 `Manual / Correct / Wrong / Unexposed`；
3. 每个4图循环结束后重新受限随机分组，减少固定同伴共现；
4. 保持每名标注者在每4图中恰好完成1个Manual、1个Correct、1个Wrong，并有1图不暴露；
5. 同一标注者绝不能在同一图进入两个条件。

每个24图批次包含6个四图循环，因此每名标注者每批正好完成 `6 Manual + 6 Correct + 6 Wrong`。

assignment manifest 至少保存：

```text
study_id
protocol_version
batch_id
image_id
worker_id
assigned_condition
exposure_status
assignment_probability
assignment_seed
replacement_status
prior_image_exposure_check
```

Label Studio CE 不是分发真源。正式分发必须来自外部冻结 manifest，并通过分批项目、导入数、实际参与 worker 和导出映射审计。

### 6.4 图片资格

正式图片在 proposal 制作和 worker outcome 可见前满足：

- researcher-side scope 为 in-scope；
- reference ready 或经独立流程修订；
- operational target 明确；
- 图片、任务、reference identity 完整；
- 每个实际的 worker–image 配对均无历史暴露；图片可以曾被其他工人标注。复用历史工人时使用 worker-specific exposure blacklist，全部招募新工人时该黑名单为空；
- Correct/Wrong 均可从同一基础表示生成；
- 图片不因预期效应大小被挑选。

building 不作为研究问题或主要分层因素。只保留 `building_id` 作为 provenance，并避免候选池被极少数 building 完全主导；正式主分析以图片为单位，building 仅作敏感性分析。

### 6.5 三臂合同

#### Manual

- 不显示 proposal；
- 从空白 geometry 开始；
- 使用与 Semi 相同的图像、说明和最终提交要求；
- Model Issue 字段结构性不适用。

#### Correct-Semi

Correct proposal 定义为：

> 在冻结 operational protocol 下，不需要 mandatory material correction 的 proposal。

允许：

- 原样提交；
- 不影响 operational validity 的可选视觉微调。

不允许需要：

- mandatory coordinate correction；
- extent correction；
- topology correction/redraw。

Correct 不等于逐像素完全等于 GT。Correct truth 必须由独立、结果不可见的 researcher/expert review 冻结。

#### Wrong-Semi

Wrong proposal 从同一图的 acceptable base proposal 确定性施加一个受控错误生成，要求：

- 视觉上可信而非明显荒谬；
- severity 为中等且可修正；
- 正式作为单类刺激时，只有一个主要缺陷；稳定混合刺激须排除或明确只进入总体 Wrong 分析；
- 除非错误本身是 topology 类，否则保持结构有效；
- 文件格式、显示方式、来源外观与 Correct 相同；
- 标注者不知道 proposal 是 Correct 还是 Wrong。

`plausible / moderate / editable` 不能只靠文字判断。每张 Wrong 候选还须记录 `D_mask(Correct,Wrong)`、角点对数量差、boundary差异和人工严重度审核；自动数值仅用于严重度辅助，不能代替“是否属于当前空间、是否只有一个主要错误、是否视觉可信”的人工判断。当前默认不要求同时匹配 `D_mask`、operational-reference quality 与尚未验证的 `R_vis` 三个带宽，以免生成不自然刺激。

### 6.6 Wrong 缺陷分类：先经历史数据压力测试

不能继续使用“四个互斥家族 + `topology_or_overparsing`”。P1 历史回放包含18个 Semi proposal、每图26名工人、共468条响应；在至少选择一个具体问题的246条响应中，74条（30.1%）同时选择两个或以上具体问题，且6个 synthetic proposal 中有3个在专家复核后改变了最初计划类别。逐图红线初始标注、冻结绿线参考与工人选择分布的并列复核进一步发现：3/18张为稳定混合，4/18张过轻或边界不清。完整证据见6.8所列开发审计。

因此工人侧前向候选分类改为“二元问题门 + 缺陷多选”，当前五个缺陷定义为：

1. `boundary_misalignment`：目标物理墙、角和空间范围不变，主要是边界或角点位置不准确；
2. `current_space_undercoverage`：遗漏相机所在当前空间的一部分真实围护边界；角点数变化只是可能表现，不是定义；
3. `adjacent_space_inclusion`：越过门框、墙垛、墙端或拱口等分界，把相邻空间纳入当前空间；
4. `spurious_nonlayout_structure`：把家具、装饰、柱体凸起或其他非目标结构解释为独立真实墙段或转折；
5. `duplicate_redundant_corner`：同一物理角被两个或更多近邻顶点重复表示，点之间不存在独立真实墙面。

`duplicate_redundant_corner`必须独立保留：历史上它比`over_parsing`更稳定，且两者可被工人区分。`topology_failure`改为结构有效性 QC，`fail`改为重画/排除状态，`acceptable`只表示`material_issue=no`，均不作为语义缺陷。若观察到多个缺陷，工人保存全部缺陷，不再被迫指定一个主要缺陷；研究者侧仍在 stimulus truth manifest 中记录`wrong_primary_defect`，用于描述刺激设计与纯度，不作为工人响应字段。“错误是什么”“怎样修”“修多大”不得放在同一标签中。

历史 P1 中没有清楚的`current_space_undercoverage`真值样本，因此该项只是基于任务定义保留的待验证扩展类，不能写成已验证类别。每类固定6图的配额也暂不成立：先完成人工审核，再根据自然 HoHoNet 输出中可形成的单一/主要缺陷刺激数量决定是否平衡、允许不平衡，或另行生成受控刺激。family-specific结果只作次级/探索性估计，RQ2主检验仍将所有合格 Wrong 合并。

### 6.7 Stimulus truth manifest

每张图至少保存：

```text
image_id
building_id
image_sha256
researcher_scope_truth

correct_proposal_id
correct_proposal_sha256
correct_review_status

wrong_proposal_id
wrong_proposal_sha256
wrong_observed_defects
wrong_primary_defect
wrong_severity
required_repair_actions
wrong_repair_extent
structural_validity
stimulus_purity

proposal_source
model_version
generator_or_operator

reference_id
reference_version
reference_sha256

batch_id
protocol_version
assignment_seed
reviewer_id_or_role
review_timestamp
```

worker 不得看到 Correct/Wrong truth、缺陷真值、严重度、expected repair 或 reference score。

### 6.8 启动前研究者人工审核

候选图片和 proposal 在任何正式分发前执行逐图审核：

1. 图片/Manhattan资格与 operational target 是否明确；
2. Correct候选是否无需 mandatory material correction；
3. Wrong候选是否存在实质问题；逐项记录全部观察缺陷、主要缺陷、修复动作、修正范围、刺激纯度和结构有效性；
4. Correct/Wrong是否存在来源、显示、格式或附加错误不对称；
5. 最终写入 `PASS / REVISE / REJECT` 和备注。

历史构念回放与逐图复核位于：

```text
analysis_results/historical_model_issue_construct_validation_20260827_v1/review.html
analysis_results/historical_model_issue_construct_validation_20260827_v1/REPORT_ZH.md
analysis_results/historical_model_issue_construct_validation_20260827_v1/researcher_visual_reclassification.csv
```

该回放使用18张历史 P1 Semi 初始标注、与历史hash一致的冻结参考及每图26名工人的实际旧标签。它是知晓旧标签分布的开发审计，不是新的正式真值冻结，也不替代未来独立双人盲审。

按修订字段生成的当前宽口径候选审核包位于：

```text
analysis_results/annotation_uncertainty_batch1_broad_review_20260828_v1/review.html
```

它以混合GT v4的 Test 458张与 Validation 190张为共同总体，在排除研究者已经审过的28张后，仅按预先写入manifest的连续几何带宽形成139张宽候选（Test 124、Validation 15）。这里的排除只是避免研究者重复审核，不是图级历史暴露门槛；候选阶段不因图片曾被其他工人标注而删除。此前28张中已有14张PASS；为避免一次继续审核过多图片，当前先从139张中提取8张无重合补充候选（Test 5、Validation 3）：

```text
analysis_results/annotation_uncertainty_batch1_supplement_review_20260828_v1/review.html
```

这8张只是研究者补充预审，不保证全部PASS，也不是把Batch 1改成8张。绿色布局来自对应的已核验人工/official reference，只是Correct候选；红色布局来自已审计的HoHoNet ep300最终布局代理，只是Wrong候选。四个自动层仅描述mask缺失/额外方向或角点对数量变化，用于组织人工查看，不是错误家族或刺激真值。AI视觉意见最多作为“优先核实”提示，不能自动产生PASS/REJECT，也不能据此从候选总体删图。审核页要求研究者记录缺陷多选、主要缺陷、修复动作、修正范围、刺激纯度和结构QC。只有研究者审核、必要的独立复核、导师批准且truth manifest冻结后，选出的24张才可称为Batch 1。当前审核包均未分发、未冻结、不是Label Studio import，也不进入论文分析；旧24+4包仅保留作开发审计。

---

## 7. 界面测试与字段时序

### 7.1 中文群界面测试

在正式批次前，使用专用练习图片进行中文界面测试：

- 界面测试记录不进入正式分析；图片本身不作全局永久排除，正式分发仅禁止同一标注者再次处理其已测试过的同一图片；
- 测试理解、填写路径、刷新/返回、状态保存、浏览器兼容和术语歧义；
- 不把测试结果作为研究 outcome；
- 测试后若修改科学字段含义，重新冻结版本。

当前 `project-86` 小测共5图、3名标注者、15条完成记录。`material_issue`在5图上均达到三人一致，但4张问题图的单选问题家族只有2张一致，修正程度只有3张一致；这支持保留二元问题门，同时停止使用旧的“单选家族 + 单选修正程度”结构。任务003中，W10将错误语义判断为相邻空间纳入，并通过删除多对角点把结果修正到接近参考布局；这直接说明“错误为什么发生”和“需要怎样改变几何结构”是两个维度，角点数量变化不能自动定义为拓扑语义错误。其余两名测试者按研究者要求主要测试元标签、未完成geometry，因此10条无关键点记录是测试设计导致的结构性缺失，不能据此判定Label Studio导出故障，也不能用于识别—行动分析。正式启动前仍需另做受控的未编辑/移动/删除/恢复四情形导出检查，以冻结canonicalization规则，但这是独立的低成本技术核验。

### 7.2 Semi 条件的编辑前步骤

RQ3要求标注者先完成 Model Issue 判断，再编辑模型初始标注。界面按以下顺序排列：

1. 填写 `material_issue` 和 `issue_confidence`；
2. 若有实质问题，填写全部观察缺陷、所需修复动作和修正范围；
3. 完成布局编辑并提交最终 geometry；
4. 填写 post-task 字段。

本研究不实现编辑器阶段锁，不记录或额外上传阶段事件，也不声称具有技术时间戳证明。RQ3仅解释为编辑前自报判断与后续实际编辑行为、最终结果之间的关联。

### 7.3 Model Issue 字段

#### `material_issue`

强制二选一：

```text
no
yes
```

不提供 `unsure`。本研究中的核心不确定性是多人选择结果的分布不确定性，不是“多少人点击了 unsure”。

定义：

- `no`：proposal 不存在必须修正的实质问题；可选微调不属于 material issue；
- `yes`：proposal 至少存在一个必须修正的实质问题。

#### `issue_confidence`

```text
1 = very low confidence
2
3
4
5 = very high confidence
```

它保留个体判断信心，但不替代 yes/no 决策。

#### `observed_defects`

仅当`material_issue=yes`时显示6.6的五个具体缺陷，`observed_defects`可多选且至少选一项。不再先问“是否有第二类错误”：多选结果本身记录第二类及更多缺陷。工人不填写`primary_defect`，避免把真实的多问题初始标注强行压缩为单一主类；研究者侧仍保留`wrong_primary_defect`、`stimulus_purity`和全部缺陷真值。当前不提供含义不清的`other`或`unsure family`；界面测试若发现稳定的未覆盖概念，应在正式冻结前扩充定义，而不是让`other`吸收异质信息。

#### `repair_actions` 与 `repair_extent`

“需要怎样修”与“要修多大”分开采集：

- `repair_actions`可多选：移动现有边界/角点、补充遗漏边界/角点、删除相邻空间段、删除误标非布局结构、合并/删除重复角点；
- `repair_extent`单选：`local / multi_region / redraw`。

整体重标已由`repair_extent=redraw`表达，不再重复设置`redraw_layout`动作。上述三个字段仅在`material_issue=yes`时显示。`material_issue=no`时不再要求选择修正程度；是否实际进行了可选微调由proposal-to-final几何变化计算，不另加一个与结果高度冗余的意图标签。若界面分支往返导致隐藏字段保留历史值，规范化层把这些值记为“不适用并忽略”，同时记录`inactive_branch_residual` QA标记；不因此拦截或丢弃整条响应。“识别—行动不一致”只比较编辑前判断与后续实际几何行为。

### 7.4 Post-task 字段

`worker_scope_response` 与 `multiple_plausible_layouts` 分别回答两个问题，不得互相替代：

- Manhattan 约束：当前空间的主要围护墙能否近似归入两组相互垂直的水平方向，墙体近似竖直，地面和天花分别可用单一平面表示；
- 任务适用性：图像证据是否至少支持一个完整、闭合、单层的 Manhattan 布局；
- 标注不确定性：是否存在两个或以上同样合理且实质不同的完整 Manhattan 布局。

存在多个合理布局不等于任务不适用。L 形、T 形、凹形和多于四个角点的空间仍可适用。全景投影中的线条不必显示为水平或竖直，应依据真实三维结构判断。

当前空间通向相邻空间时，在门框、成对墙垛、墙端、拱口等清晰结构分界处闭合，不继续进入相邻空间。只有在不存在可重复判断的结构闭合边界时，才因此选择 `out_of_scope`。

所有三臂均可在最终 geometry 后填写：

- `worker_scope_response`；
- `multiple_plausible_layouts = no/yes`；
- `perceived_difficulty = 1–5`；
- `difficulty_reason`：必填多选，包含`no_specific_reason`及各具体原因；`no_specific_reason`只能单独选择。

这些是 worker response 或post-treatment机制结果，不是 researcher-side图片资格真值，也不用于该图首次分配。

### 7.5 元标签的最小研究映射与历史兼容

不要求“每个选项独立对应一个 RQ”。科学要求是：每个字段有预先说明的构念、分析用途和不解释边界；分支/QA 字段可以没有独立假设。当前候选映射为：

| 字段 | 研究作用 | 当前裁决 |
|---|---|---|
| `worker_scope_response` | RQ1：标注者对任务适用性/scope 的响应 | 保留；不是 researcher truth |
| `multiple_plausible_layouts` | RQ1：主观多解判断，与几何候选模式交叉检查 | 保留；单独不能证明客观多解 |
| `perceived_difficulty` | 主观负担及处理后反应 | 辅助保留；不等于不确定性或质量 |
| `difficulty_reason` | 必填多选；区分无明确原因及遮挡、低纹理、拼接、反射、开口、图像质量等探索性机制 | `no_specific_reason`只能单独选择；`other`本身不可解释 |
| `material_issue` | RQ3：Correct/Wrong proposal 的二元识别响应 | 核心保留 |
| `issue_confidence` | RQ3：对 Model Issue 判断的主观信心/校准 | 核心保留；不是最终布局信心 |
| `observed_defects` | RQ3：具体缺陷识别及多问题共现 | 候选核心；多选，五类定义见6.6；undercoverage尚未由历史truth验证 |
| `repair_actions` | RQ3：预期修复动作与实际几何变化的关联 | 候选核心；可多选，与缺陷类型分开 |
| `repair_extent` | RQ3：预期修正范围与实际geometry delta的关联 | 辅助；仅分local/multi-region/redraw，不充当错误类型 |
| `structural_validity`、`stimulus_purity` | researcher-side刺激QC | 不向worker展示，不作为worker不确定性 |

如果导师明确把“个体对最终答案的主观不确定”设为核心，才考虑为三个臂共同增加一个 `layout_confidence=1–5`；当前不因理论完整性先加字段。当前六份 XML v2 与四份 Userscript v5 只是本地待部署草稿，未部署到 Project 86；正式合同、active time、分发与三臂样本量均未改变。

旧元标签不追溯作废、不删除、不自动重编码：旧 `scope=normal` 含“唯一可复现”语义，旧 difficulty 和旧多选 `model_issue` 也与新字段构念不同。旧数据按 legacy schema 原样分析；新实验若获批，才冻结 forward schema。`historical_data_reclassified=false` 保持不变。

---

## 8. RQ2 结果定义

### 8.1 Primary：总体布局不一致

对每张图 `i`、条件 `c`，使用该条件5个有效结果的平均两两不相似度：

\[
D_{ic}
=\frac{2}{k(k-1)}
\sum_{a<b}d(Y_{iac},Y_{ibc}),\quad k=5.
\]

候选主距离：

\[
d(Y_a,Y_b)=1-\operatorname{IoU}\{M(Y_a),M(Y_b)\}=D_{\text{mask}}(Y_a,Y_b).
\]

`M` 的表示、seam、raster与invalid规则同5.2.1，并须在正式结果可见前冻结。每臂有10个标注对，但这些pair共享标注者，不能作为10个独立样本。图像是主要推断单位。

### 8.2 Planned contrasts

```text
Correct-Semi − Manual
Wrong-Semi − Manual
Wrong-Semi − Correct-Semi
```

对应 estimand：

\[
\theta_{CM}=\frac1N\sum_i(D_{iC}-D_{iM}),
\]

\[
\theta_{WM}=\frac1N\sum_i(D_{iW}-D_{iM}),
\]

\[
\theta_{WC}=\frac1N\sum_i(D_{iW}-D_{iC}).
\]

负值表示前一条件比后一条件更集中；正值表示更分散。集中本身不等于改善。

### 8.3 结构化分解

关键次要指标：

- vertical-boundary cardinality disagreement；
- point/corner count disagreement；
- geometry computability / structurally valid rate；
- proposal-to-final edit magnitude；
- 同图/同臂可评价覆盖率。

以下只作探索性：

- 单图候选 mode count；
- rare-cardinality prevalence；
- supported multimodality；
- partition identifiability。

除非未来补充并验证顺序数据，Study 2 同样不使用完整 topology signature 作为确认性指标。

### 8.4 质量与安全结局

质量不是独立RQ，而是解释分歧变化所必需的安全轴。

建议报告：

- structurally valid rate；
- final layout IoU against frozen operational reference；
- delivery-adjusted quality：

\[
U=I(\text{structurally valid})\times\operatorname{IoU}(Y_{final},G);
\]

- final-to-proposal distance；
- edit magnitude；
- corner count/topology change；
- wrong proposal correction；
- residual wrong retention；
- correct proposal retention；
- correct proposal edit、无明显收益的edit，以及经双轴证据支持的harmful edit候选。

reference quality 与可见图像合理性不是同一个对象。当前默认方案不把尚未验证的 `R_vis` 纳入72图正式结果。若论文要正式声称“人工修正降低可见墙体残差”，应先在不进入Main的图片上，由至少两名结果盲审者验证可见证据定义、重复性和响应性；通过后必须在任何正式condition outcome可见前冻结并升级为key secondary。若不通过，则只允许对预先抽取、非按 `delta_U` 选择的样本做盲法视觉贴合审查，不得从 `wall_distance_mean` 或 `delta_U` 推断真实墙残差。也不得仅凭 `delta_U<0` 宣称人工修改更差或更好。

### 8.5 联合解释

| 分歧 | 质量 | 解释 |
|---|---|---|
| 降低 | 提高或非劣 | 有益收敛 |
| 降低 | 降低 | 错误同质化 |
| 增加 | 提高 | 生产性分化/多路径纠错 |
| 增加 | 降低 | 噪声放大 |

这些类别用于解释，不额外形成四个确认性假设。

---

## 9. RQ3 结果定义

### 9.1 多人 Model Issue 分布不确定性

对每张图和每个Semi条件，令：

\[
p_{issue,ic}=\frac{\#(material\_issue=yes)}{5}.
\]

二元pairwise disagreement：

\[
D_{issue,ic}=2p_{issue,ic}(1-p_{issue,ic}).
\]

二元熵：

\[
H_{issue,ic}
=-p_{issue,ic}\log p_{issue,ic}
-(1-p_{issue,ic})\log(1-p_{issue,ic}).
\]

因此，`0/5`和`5/5`都是高共识，`2/5`和`3/5`表示最高分歧附近。研究对象是投票分布，而不是一个 `unsure` 类别。

### 9.2 Recognition

主要报告：

```text
P(issue=yes | Wrong)
P(issue=yes | Correct)
两者差值
Correct false-positive rate
Wrong miss rate
Wrong 条件下缺陷集合的 exact-set match、Jaccard 与逐缺陷召回/误报
confidence calibration
```

缺陷识别不再计算强制单一主类准确率。对 Wrong 图`i`，以研究者冻结的全部缺陷真值集合`T_i`和工人选择集合`S_ij`比较，报告exact-set match、Jaccard以及逐缺陷的召回与误报；五类频数不足时只作描述性结果。研究者侧的`wrong_primary_defect`仅用于刺激描述、纯度审核或预先声明的分层，不反推工人“应当选择的唯一主类”。

Correct/Wrong truth 是随机处理，因此 `Wrong vs Correct → material_issue` 可以解释为proposal truth对识别反应的处理效应。

### 9.3 Recognition–action evidence

报告：

- issue=yes 且进行了符合预期的mandatory edit；
- issue=yes 但未进行实质编辑；
- issue=no 但进行了mandatory edit；
- issue=no 且保留模型初始标注或只做可选微调；
- Wrong被成功、部分或未纠正；
- Correct被保留、可选微调或被实质改坏；
- confidence 与判断正确性、行为一致性和最终结果的关系。

Model Issue 是处理后的response/mediator，不得作为普通协变量加入RQ2总效应模型。Model Issue自身未随机化，因此“Model Issue导致纠正”只能作为关联表述；严格中介分析最多是探索性。

---

## 10. Active time

Active time 是次要效率/努力结局，不是标注不确定性的替代指标。它混合个人速度、熟悉度、投入、疲劳、实际编辑量、图片证据和界面行为；时间变长不能单独解释为更不确定、质量更差或更认真。

规则：

- 使用 owner-valid、task-worker cumulative active log；
- 不用 Label Studio `lead_time` 替代；
- 不固定减去估算的 Model Issue 填写时间；
- 完整任务耗时包含实际判断和编辑成本；
- 报告时间覆盖率、缺失原因和长尾；
- 主要模型使用 `log1p(active_time)` 并控制worker和image。

候选模型：

\[
\log(1+T_{iu})
\sim condition+batch+(1|worker)+(1|image).
\]

当前2069条正式时间记录的 `log1p(active_time)` 方差分解约为 task 11.56%、worker 51.72%、残差36.73%。22名有完整时间画像的工人中，task-adjusted active time 中位数为123.0秒（IQR 65.4–165.1，范围11.0–401.8）；它与 `Q_GT_EB`、`R_peer_stable`、`F_struct_EB` 的 Spearman 分别为 -0.287、-0.159、-0.012。样本小且是描述性关联，但足以否定把“快/慢”直接当作能力或质量代理。

因此 active time 可辅助回答：条件是否改变成本、同一工人在不同图片上的额外耗时是否伴随更多分歧/修改、worker 之间节奏差异有多大。它不能单独定义“人的不确定性”，也不得改变现行 worker rank、eligibility、routing 或正式画像合同。

---

## 11. 统计分析计划草案

### 11.1 RQ1

RQ1以估计为主，不强行检验“是否存在分歧”：

- 图片等权报告均值、中位数、分位数和95% CI；
- 高密度与全部Manual分层报告；
- 阈值、support和task population敏感性；
- task/worker交叉方差分解；
- 不把stage差异解释为阶段因果效应，因为各stage任务构成不同。

### 11.2 RQ2

主要估计为 image-equal contrasts，不设置三条件omnibus门。当前讨论稿把问题拆成：

1. RQ2a：`Correct−Manual` 与 `Wrong−Manual`，回答预标注相对独立Manual如何改变不一致；
2. RQ2b：`Wrong−Correct`，回答这种改变是否依赖proposal correctness；
3. 三个contrast均在结果可见前预设，并在同一确认性家族中用受限随机化maxT（若实现和模拟验证通过）或Holm控制；
4. 同时报告估计值、95% CI和标准化效应，不只报告p值。

如果导师要求只有一个primary contrast，必须在condition outcome可见前按论文主问题选择：只有当主故事明确改为proposal correctness机制时，才把`Wrong−Correct`设为唯一primary；不得事后根据显著性调整层级。

主要推断应尊重受限随机分配：

- permutation/randomization test 按实际worker–image assignment重排；
- CI可使用图片与worker交叉bootstrap；
- naive annotation-level独立检验不得作为唯一主检验；
- building只做cluster sensitivity，不进入研究主线。

### 11.3 RQ3

Recognition候选模型：

\[
\operatorname{logit}P(issue=yes)
\sim proposal\_truth+(1|worker)+(1|image).
\]

Recognition–action关联候选模型：

\[
outcome
\sim issue+proposal\_truth+issue\times proposal\_truth
+(1|worker)+(1|image).
\]

其中 outcome 可分别为 edited、mandatory edit、successful correction、correct degradation 或连续edit magnitude。后者是关联模型，不作Model Issue自身的因果解释。

### 11.4 多重比较

- RQ1描述性估计不与RQ2确认性检验混成同一个p值家族；
- RQ2主比较按预设层级/Holm控制；
- error-family、worker profile、confidence分层和多数机制结果明确标记为次级或探索性；
- 不根据第一、二批结果临时把显著的次级指标改成primary。

---

## 12. 缺失、失败与替补

### 12.1 External/technical failure

若提交前发生可验证技术故障：

- 保留原记录和incident ID；
- 在结果不可见条件下，从该图原本未暴露的5人中按冻结顺序选择替补；
- 替补进入相同condition，且不能看过该图其他条件；
- 保存original/replacement关系和assignment probability；
- 无法合规替补时记为not-evaluable，不把缺失补零。

### 12.2 Worker-caused structural invalidity

结构无效是结果，不是技术缺失：

- 在结构有效率和delivery-adjusted quality中保留；
- 对无法计算pairwise距离的无效geometry，报告该臂有效support；
- 某image-condition有效geometry不足3时，分布指标标记not-evaluable；
- 做预设的保守敏感性，不静默只分析成功提交。

### 12.3 Schema与identity

以下任一失败需fail closed并人工审计：

- proposal SHA不匹配；
- condition/assignment不一致；
- same-worker same-image multi-arm exposure；
- reference版本冲突；
- geometry字段漂移；
- active-time来源不匹配。

---

## 13. 三批执行方案

### 13.1 非正式界面测试

不计入正式批次。当前5图小测已经发现旧字段结构重叠；由于两名测试者被要求主要测试元标签，它不能用于判断geometry完整率。修订字段后只做1--2图、2--3人的受控技术冒烟测试，覆盖未编辑、移动、删除及恢复原位，确认分支、保存、刷新、导出和canonicalization规则；通过后直接进入24图Batch 1，不再反复拆成多个难以运营的小块。

### 13.2 Batch 1：24图

- 启动前先完成6.8的研究者审核；此前28张已有14张PASS，当前先审核8张补充候选，不足部分再从139张宽范围中补充；AI建议不作排除，最终由研究者选择并复核24张；
- 24张主候选必须全部达到PASS；REVISE须修订后重审，REJECT从备用池或重新筛选中替换；
- 360次worker-action；
- 每人6 Manual、6 Correct、6 Wrong；
- 当前不承诺每个语义缺陷固定6图；现有6/6/6/6只平衡机械候选筛选层，不进入truth或family效应解释；
- 重点检查技术完整性和manipulation是否明显失败。

### 13.3 Batch 2：24图

累计48图、720次worker-action；每人累计12 Manual、24 Semi。

若科学合同未改变，继续使用同一协议版本；不得根据Batch 1的效应方向选择更有利图片或缺陷构成。

### 13.4 Batch 3：24图

累计72图、1,080次worker-action；每人最终18 Manual、36 Semi。

三批均完成后进行冻结的正式分析。

### 13.5 批次间检查

批次间只允许查看预先定义的运营和操纵指标。候选运营门：

| 指标 | 草案门槛 |
|---|---:|
| assignment/condition/proposal identity错误 | 0 |
| same-worker same-image multi-arm exposure | 0 |
| geometry computability | ≥97% |
| 必填字段完整率 | ≥98% |
| Model Issue必填字段完整率 | ≥98% |
| Material Issue条件分支冲突 | 0 |

候选manipulation诊断（仍需导师确认）：

- `P(issue=yes|Wrong) − P(issue=yes|Correct)` 的点估计至少约25个百分点为Green；
- 10–25个百分点为Yellow，检查培训、刺激严重度和taxonomy；
- 小于10个百分点为Red，说明Correct/Wrong在worker感知层面可能没有形成有效对比；
- Correct的material-issue false-positive明显过高时，重新审查Correct刺激物；
- 对已冻结缺陷truth逐项报告选择率和误选率；不得把多标签truth压成一个含义不明的overall family accuracy。若定义理解测试或逐项识别明显失败，重新审查taxonomy和培训。

这些是设计诊断，不是论文主假设。不得以中途RQ2质量或分歧p值决定是否继续，也不得在结果可见后选择性追加到某个condition。

若Batch 1后发生实质性科学修改，例如改变：

- material issue定义；
- Correct/Wrong truth规则；
- Wrong severity/family；
- 三臂结构；
- RQ2 primary metric；
- 图片资格；

则Batch 1只能作为development/pilot evidence。若仅修复错字、显示、保存bug且科学合同不变，可保留并与后续批次合并，同时报告protocol version。

---

## 14. 样本量、功效与可声明边界

### 14.1 任务预算

备选规模：

| 图片数 | 总提交 | 每人Manual | 每人Semi | 每人总任务 |
|---:|---:|---:|---:|---:|
| 60 | 900 | 15 | 30 | 45 |
| **72（主建议）** | **1,080** | **18** | **36** | **54** |
| 80（硬上限参考） | 1,200 | 20 | 40 | 60 |

72图相对60图增加180次提交，但在每人较严格上限内保留补漏空间；80图用满Manual 20、Semi 40，不适合作为默认方案。

### 14.2 当前功效证据的限制

现有条件功效表针对未来连续quality interaction，并不是RQ2不一致性主指标的真实功效。以假设：

```text
true effect = 0.04
interaction SD = 0.10
design-effect sensitivity = 1.4
```

得到的条件功效约为：

| 图片数 | 条件功效 |
|---:|---:|
| 60 | 74.5% |
| 72 | 81.8% |
| 80 | 85.6% |

这些是假设条件，不是显著结果保证。

旧的25个C1 Manual/Semi配对图“拓扑差值SD/MDE”依赖未验证的结构签名，又来自非随机历史 Semi，不再作为本方案的规划证据。72图只是符合当前人均容量且优先图片覆盖的候选折中，不能保证显著性。正式启动前应使用与最终 `D_layout` 完全一致的距离、受限随机分配、worker/image交叉依赖和缺失机制进行重抽样功效模拟；若该模拟显示目标效应不可识别，应调整声明或方案，而不是事后寻找显著指标。

### 14.3 允许的结论

允许：

- 估计自然标注分歧的幅度和结构；
- 估计Correct/Wrong proposal对平均多人分歧的影响；
- 区分有益收敛、错误同质化、生产性分化和噪声放大；
- 分析编辑前Model Issue识别与后续行动/结果的联系。

不允许：

- 声称显著性已被样本量保证；
- 用每臂5人精确估计单图低频模式prevalence；
- 把一致性提高自动解释为质量提高；
- 把Model Issue与纠错的关联写成Model Issue自身的因果效应；
- 把历史自然Semi数据当作随机Correct/Wrong实验；
- 把building、语言或error family事后提升为主要研究问题。

### 14.4 从最初方案到当前最小方案

三条 RQ 的机制链没有改变；变化主要是把不可验证或不必要的实现降级：

| 最初/中间版本内容 | 当前处理 |
|---|---|
| RQ1 人际分歧、RQ2 proposal 改变分歧、RQ3 Model Issue–结果 | 保留 |
| 只看42张高密度图 | 改为全部 Manual 按支持数分层；42张只承担人数校准 |
| 完整 topology signature、same-topology cyclic RMSE | 当前数据缺少可靠顺序，删除确认性地位；只保留 cardinality/validity 代理 |
| 稳定多峰、worker 类型 | 降为候选/稳定性审计；不命名工人画像 |
| active time 作为一种不确定性 | 改为效率、努力和人—任务反应的辅助指标 |
| RQ3 独立 Study 3、完整编辑轨迹 | 保持为 Study 2 内次级关联；不做阶段锁、不声称完整轨迹 |
| 80图、24–30新工人、自适应人数、模型uncertainty对齐、概率布局、下游任务 | 不纳入当前默认方案；80图仅是容量硬上限参考 |
| 四个互斥Wrong family、角点数自动定类、每类固定6图 | 被历史18图×26人回放否决；改为工人侧缺陷多选与独立修复动作，研究者侧保留主要缺陷真值，自动几何量只作候选筛选 |

这次删减不是改变研究方向，而是让每个主结论都落在现有或计划采集的数据上。新的五类缺陷不是五个确认性假设；其主要用途是解释RQ3的识别—行动链并防止一个标签混杂多种信息。剩余明显的过度设计候选是全部困难原因、精细family-specific效应及未验证的undercoverage刺激配额；是否保留由导师决定。

---

## 15. 最低交付与审计工件（导师批准后才生成）

若研究获批，启动前至少需要：

1. 冻结的研究协议和SAP；
2. 72图图片资格清单；
3. Correct/Wrong stimulus truth manifest；
4. worker–image–condition assignment manifest；
5. proposal/reference SHA清单；
6. 三批Label Studio导入包与项目命名；
7. runtime task mapping；
8. 中文培训和界面测试记录；
9. Model Issue字段顺序、条件分支和提交校验（明确无技术阶段锁）；
10. active-time来源验证；
11. 字段合同、missing/failure disposition；
12. 与最终primary metric一致的功效模拟；
13. 每批planned/actual worker、task、submission和replacement审计；
14. 固定seed、软件版本和输出manifest。

所有分发继续遵循CE-only边界：LS只负责展示和采集，外部manifest才是分发真源；GT不进入worker-facing路径。

---

## 16. 需要导师确认的决策清单

在把本草稿升级为正式协议前，请导师逐项确认：

- [ ] 三条RQ是否保持当前表述；
- [ ] 是否同意“历史高密度深度 + 新实验广度”的两Study结构；
- [ ] 是否同意72图、20人、5/5/5、24×3；
- [ ] 是否同意每人最终Manual 18、Semi 36；
- [ ] 是否同意总体pairwise layout dissimilarity作为RQ2 primary；
- [ ] 是否同意当前只使用cardinality/validity代理，不把完整topology signature列为确认性指标；
- [ ] Correct/Wrong operational truth及盲审要求；
- [ ] 是否同意经历史数据压力测试后的五类工人侧缺陷多选、研究者侧`wrong_primary_defect`和中等severity；
- [ ] `material_issue=yes/no + confidence 1–5`，不提供unsure；
- [ ] 是否同意不再采集冗余的`no_issue_handling`，并将缺陷、修复动作和修正范围拆开；
- [ ] `current_space_undercoverage`尚无历史truth样本：是否在非正式界面测试中先验证定义和样例，再决定正式配额；
- [ ] 是否把三个臂通用的`layout_confidence`纳入核心；若不是核心则不新增；
- [ ] 是否接受只按界面顺序要求编辑前自报、不实现或声称Model Issue技术锁；
- [ ] 三批之间的运营门和manipulation诊断；
- [ ] 缺失、结构无效、technical replacement规则；
- [ ] permutation/bootstrap、multiplicity和功效方案；
- [ ] Study 2与当前正式Paper A/T1的组织关系及论文定位。

---

## 17. 本草稿所依据的仓库材料

数据与结果：

- `analysis_results/uncertainty_substrate_20260823_v1/README_ZH.md`
- `analysis_results/uncertainty_substrate_20260823_v1/geometry_pairwise.csv`
- `analysis_results/full_uncertainty_data_mining_20260821_v5/GEOMETRY_TASK_UNCERTAINTY_ALL_STAGES.CSV`
- `analysis_results/full_uncertainty_data_mining_20260821_v5/RARE_MODE_DETECTION_PROBABILITY.CSV`
- `analysis_results/full_uncertainty_data_mining_20260821_v5/CROSSED_TASK_WORKER_VARIANCE_COMPONENTS.csv`
- `analysis_results/full_uncertainty_data_mining_20260821_v5/CURRENT_MANUAL_SEMI_UNCERTAINTY_SUMMARY.CSV`
- `analysis_results/full_uncertainty_data_mining_20260821_v5/META_LABEL_STAGE_MODE_SUMMARY.CSV`
- `analysis_results/full_uncertainty_data_mining_20260821_v5/TAG_BEHAVIOR_CASE_SUMMARY.csv`
- `analysis_results/uncertainty_threshold_anchoring_worker_types_20260823/K22_PREFIX_THRESHOLD_TASK_RATES.csv`
- `analysis_results/manual_semi_correctness_oos_20260823/CURRENT_TASK_EFFECT_VARIATION_REFERENCE.csv`
- `analysis_results/manual_semi_correctness_oos_20260823/DESIGN_OPTIONS_RESOURCE_ACCOUNTING.csv`
- `analysis_results/manual_semi_correctness_oos_20260823/CONDITIONAL_INTERACTION_POWER.csv`
- `analysis_results/rq1_stratified_uncertainty_20260827_v1/RQ1_STRATIFIED_UNCERTAINTY_REPORT_ZH.md`
- `analysis_results/rq1_stratified_uncertainty_20260827_v1/human_component_summary.csv`
- `analysis_results/rq1_stratified_uncertainty_20260827_v1/meta_label_research_mapping.csv`
- `analysis_results/rq1_stratified_uncertainty_20260827_v1/literature_claim_audit.csv`
- `analysis_results/historical_model_issue_construct_validation_20260827_v1/REPORT_ZH.md`
- `analysis_results/historical_model_issue_construct_validation_20260827_v1/researcher_visual_reclassification.csv`
- `analysis_results/historical_model_issue_construct_validation_20260827_v1/review.html`
- `analysis_results/annotation_uncertainty_batch1_broad_review_20260828_v1/review.html`
- `analysis_results/annotation_uncertainty_batch1_broad_review_20260828_v1/candidate_manifest.json`
- `analysis_results/annotation_uncertainty_batch1_broad_review_20260828_v1/AI_INITIAL_SUGGESTIONS.md`
- `analysis_results/annotation_uncertainty_batch1_supplement_review_20260828_v1/review.html`
- `analysis_results/annotation_uncertainty_batch1_supplement_review_20260828_v1/candidate_manifest.json`
- `analysis_results/annotation_uncertainty_batch1_candidate_review_20260827_v2/review.html`
- `analysis_results/annotation_uncertainty_batch1_candidate_review_20260827_v2/candidate_manifest.json`

当前配置与边界：

- `tools/label_studio/label_studio_uncertainty_meta_manifest_v1.json`
- `tools/label_studio/label_studio_uncertainty_meta_manifest_v2.json`
- `docs/label_studio/LS_CE_ONLY_OPERATION_SOP_v1.md`
- `docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`
- `docs/thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md`

外部文献整理：

- `C:/Users/ASUS/Downloads/不确定性文献调研.md`（研究背景材料，不是仓库规范真源）。

---

## 18. 一页式建议结论

在导师确认前，本研究最简洁、可执行且相对严谨的候选版本为：

> 使用全部历史Manual输出按支持数分层描述历史无辅助标注输出差异与操作性可复现性，并以42张P1/C1高密度图校准有限工人池下的人数稳定性；后续候选实验使用72张对其实际被分配标注者未暴露的图片开展三臂同图随机实验（图片可以曾被其他人标注）。每张图由5名Manual、5名Correct-Semi和5名Wrong-Semi标注，20名标注者（可以全部为统一培训的新工人）通过受限轮换实现每人18个Manual和36个Semi任务，分3批、每批24图。RQ2以拟在启动前冻结的periodic equirectangular `D_mask`和图像等权的三个预设contrast为核心，不设置omnibus门，并以cardinality、结构有效性、proposal-to-final变化和独立reference质量作分解与安全解释；不强行实现完整topology signature。`R_vis`只在独立小规模验证通过后才考虑升级，否则不声明真实墙残差改善。RQ3保留为Study 2内的Model Issue识别—行动关联；其分类经P1历史18图×26人压力测试后改为工人侧缺陷多选、修复动作和修正范围分离，缺陷识别按集合比较，不强迫工人指定唯一主类；研究者侧仍记录刺激的全部缺陷真值、`wrong_primary_defect`和`stimulus_purity`。自动几何差异只作候选筛选。本研究不实施阶段锁或阶段事件上报。当前从Test与Validation共同总体生成的139张宽审核包只是候选范围；AI视觉意见只作优先核实提示，最终纳入由研究者裁决。所有内容仍待导师确认，Correct/Wrong truth、随机分配、字段、失败处理和推断方法只有在批准后才冻结。

该建议仍是导师讨论稿，不得直接作为启动授权。
