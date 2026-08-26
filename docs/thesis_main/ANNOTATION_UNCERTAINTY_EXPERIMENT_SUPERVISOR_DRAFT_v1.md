# 360°布局标注不确定性研究：完整实验方案（导师讨论稿 v1）

> **状态：DRAFT / NON-NORMATIVE / NOT APPROVED**  
> **用途：仅供与导师讨论、修改和确认，不是正式协议，不得据此直接生成任务或启动实验。**  
> **日期：2026-08-24**  
> **建议方案：20名标注者、72张拟纳入实验图片、每图5 Manual + 5 Correct-Semi + 5 Wrong-Semi、24图×3批次。**

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
无预标注时的自然拓扑—几何分歧
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

- 拓扑/结构选择不同；
- 同一拓扑下的连续几何位置差异；
- 两个或更多受支持模式；
- 有限、任务调整后的标注者差异。

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

主要回答 RQ1。使用现有 P1–C2-A-RP 中性数据底座，不增加新的高密度重复标注。

### Study 2：Correct/Wrong proposal 三臂随机实验

主要回答 RQ2 和 RQ3。使用新的、正式标注者此前未见过的图片，比较：

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

可用于高密度自然分布分析的核心数据为：

| 来源 | 图片数 | 每图可计算 Manual 数 | 主要用途 |
|---|---:|---:|---|
| P1 Manual | 30 | 24–26 | 单图拓扑分布、多峰、少数模式 |
| C1 高支持 Manual | 12 | 23 | 独立高支持复核 |
| 合计 | 42 | 约1,017条几何标注 | RQ1 深度证据 |

这42张图足以估计本研究任务样本中的平均不一致程度、拓扑与连续几何组成，并识别占比较高的主要模式；但图片级独立样本量仍是42，不是1,017，也不是成千上万个标注对。

因此，当前数据不适合声称精确估计“所有360°布局图片的多峰发生率”，也不支持大量细分亚组。以图片比例估计为例，`N=42` 在最坏情况下的95%抽样误差约为±15个百分点，且任务选择偏差可能比该抽样误差更大。

### 4.3 少数模式检出能力

若某少数模式真实占比为 `p`，每图有 `k` 个独立标注，至少观察到2次该模式的概率为：

\[
P(X\ge2)=1-(1-p)^k-kp(1-p)^{k-1}.
\]

| 少数模式占比 | k=5 | k=12 | k=20 | k≈24–26 |
|---:|---:|---:|---:|---:|
| 10% | 8.15% | 34.10% | 60.83% | 约71%–75% |
| 20% | 26.27% | 72.51% | 93.08% | 约97% |

仓库对12个高支持C1任务的prefix replay也显示：其中在 `q=0.95`、全量 `k=22` 时被判为受支持多峰的6张图，降采样后在 `k=5` 时重新识别率约18%，`k=12` 约73%，`k=20` 约92%。这是富集样本中的条件检出率，不是自然图片总体的多峰率。

因此：

- RQ1 的多峰和少数模式使用历史高密度数据；
- Study 2 每臂 `k=5` 不用于估计单图完整模式 prevalence；
- Study 2 主要估计跨图片的平均两两不一致变化。

### 4.4 方差证据

当前交叉方差分解约为：

| 结果 | 图片/任务方差 | worker方差 | 残差 |
|---|---:|---:|---:|
| geometry disagreement | 65.25% | 2.75% | 31.99% |
| quality IoU | 55.99% | 2.91% | 41.10% |
| log active time | 11.56% | 51.72% | 36.73% |

因此，研究平均分布干预时应优先增加独立图片，而不是把少量图片从每臂5人提高到6–7人。时间分析则必须控制 worker 差异。

---

## 5. Study 1：历史数据中的 RQ1 分析

### 5.1 分析层

#### A. Independent Manual population

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

建议主指标为每图平均两两布局不相似度：

\[
D_{\text{layout},i}
=\frac{2}{k_i(k_i-1)}
\sum_{a<b}\left[1-\operatorname{IoU}(Y_{ia},Y_{ib})\right].
\]

若正式实现不采用 pairwise layout IoU，替代距离必须在查看 Study 2 条件结果前冻结，并明确量纲、有效范围、拓扑不兼容处理和数值稳定性。

#### 5.2.2 拓扑不一致

先冻结 topology signature。候选组成至少包括：

- point/corner count；
- vertical boundary count；
- topology validity；
- cyclic ordering/closure；
- 可审计的结构签名或hash。

图级拓扑不一致率：

\[
D_{\text{top},i}
=\frac{2}{k_i(k_i-1)}
\sum_{a<b}I(g_{ia}\ne g_{ib}).
\]

#### 5.2.3 同拓扑连续几何离散

只在 topology signature 相同、度量兼容且 cyclic correspondence 唯一的标注对中计算：

- cyclic RMSE；
- median/mean/q90；
- boundary similarity；
- wall-wall similarity。

没有合格同拓扑标注对时写 `not_evaluable`，不得补零。

#### 5.2.4 多峰与模式

模式分析只在高支持数据中进行，并报告多个阈值，例如：

```text
q = 0.90 / 0.925 / 0.95 / 0.97 / 0.98
```

至少报告：

- supported multimodal rate；
- largest mode share；
- mode count；
- Shannon entropy / Gini–Simpson；
- partition not-evaluable/non-identifiable rate；
- 阈值与下采样敏感性。

模式算法识别出的分组不自动等于“多个合理布局”。对稳定模式抽样进行 outcome-blind 审查，区分：

- 合理替代拓扑；
- 协议诱导差异；
- 同拓扑连续偏差；
- 清晰标注错误；
- 表示或对应关系错误；
- 聚类伪影；
- reference 问题。

### 5.3 标注者异质性

不先对标注者聚类，也不预先命名“锚定型”“探索型”等类别。先估计任务调整后的连续倾向：

- quality residual；
- geometry disagreement residual；
- topology complexity residual；
- largest/minority mode participation；
- active-time residual；
- 历史 proposal retention/correction tendency。

只有 split-half、held-out task 或 bootstrap 显示足够稳定时，才讨论可复现的 worker tendency；否则只报告总体 worker variance 有限。

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

`15人/条件` 需要45名独立标注者。当前只有20人；让同一人重复看同一图的不同条件会产生记忆、学习和锚定污染，不能视为45份独立证据。

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
- 20名正式标注者此前未见过该图片；若不能满足，使用 worker-specific exposure blacklist；
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
- 只有一个 dominant error family；
- 除非错误本身是 topology 类，否则保持结构有效；
- 文件格式、显示方式、来源外观与 Correct 相同；
- 标注者不知道 proposal 是 Correct 还是 Wrong。

### 6.6 Wrong error family

四个主要家族：

1. `boundary_or_corner_localization`；
2. `underextension`；
3. `adjacent_space_overextension`；
4. `topology_or_overparsing`。

duplicate corner、ghost structure、ordering/closure 可作为第四类的 subtype，不单独成为确认性家族。

每批24图中四类各6图；最终72图中四类各18图。family-specific结果仅作次级/探索性估计，主检验将所有Wrong合并。

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
wrong_error_family
wrong_error_subtype
wrong_severity
mandatory_edit_expected
expected_edit_type

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

worker 不得看到 Correct/Wrong truth、错误家族真值、严重度、expected edit 或 reference score。

---

## 7. 界面测试与字段时序

### 7.1 中文群界面测试

在正式批次前，使用专用练习图片进行中文界面测试：

- 测试图永久排除正式实验；
- 测试理解、填写路径、刷新/返回、状态保存、浏览器兼容和术语歧义；
- 不把测试结果作为研究 outcome；
- 测试后若修改科学字段含义，重新冻结版本。

### 7.2 Semi 条件的编辑前步骤

RQ3要求标注者先完成 Model Issue 判断，再编辑模型初始标注。界面按以下顺序排列：

1. 填写 `material_issue` 和 `issue_confidence`；
2. 按 `material_issue` 的条件分支填写处理方式或修正程度；
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

#### `primary_issue_family`

仅当 `material_issue=yes` 时必填：

```text
boundary_or_corner_localization
underextension
adjacent_space_overextension
topology_or_overparsing
other
```

不提供 `unsure` family。

#### `required_correction`

`required_correction` 必须由 `material_issue` 决定可选范围，界面不得同时展示全部五项：

| `material_issue` | 界面问题 | 可选值 |
|---|---|---|
| `no` | 你认为该初始标注应如何处理？ | `no_edit_needed` / `optional_visual_micro_refinement` |
| `yes` | 该实质性问题需要什么程度的修正？ | `minor_mandatory_coordinate_correction` / `major_geometry_correction` / `topology_change_or_redraw` |

Label Studio 要求控制字段名称唯一，因此本地采集配置使用两个互斥的原始字段：

- `material_issue=no`：写入 `no_issue_handling`；
- `material_issue=yes`：写入 `required_correction`。

分析时依据 `material_issue` 将二者合并为统一的规范字段 `required_correction`。跨分支残留值属于无效响应，提交校验必须阻止，不得将其解释为标注不确定性。

“识别—行动不一致”只比较编辑前判断与后续实际几何行为，不通过允许两个编辑前回答互相矛盾来构造。

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
- difficulty reason status/reasons。

这些是 worker response 或post-treatment机制结果，不是 researcher-side图片资格真值，也不用于该图首次分配。

---

## 8. RQ2 结果定义

### 8.1 Primary：总体布局不一致

对每张图 `i`、条件 `c`，使用该条件5个有效结果的平均两两不相似度：

\[
D_{ic}
=\frac{2}{k(k-1)}
\sum_{a<b}d(Y_{iac},Y_{ibc}),\quad k=5.
\]

建议主距离：

\[
d(Y_a,Y_b)=1-\operatorname{IoU}(Y_a,Y_b).
\]

每臂有10个标注对，但这些pair共享标注者，不能作为10个独立样本。图像是主要推断单位。

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

- `D_top`：拓扑不一致率；
- `D_geo`：同拓扑 pair 的连续几何离散；
- topology change rate；
- largest topology share；
- 同图/同臂可评价覆盖率。

以下只作探索性：

- 单图 mode count；
- rare-mode prevalence；
- supported multimodality；
- partition identifiability。

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
- correct proposal unnecessary/harmful edit。

reference quality 与可见图像合理性不是同一个对象。若出现“人工修改后reference指标下降”的关键候选，应进行不看条件与行为标签的视觉边界审查；不得仅凭 `delta_U<0` 宣称人工修改更差或更好。

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
primary-family recognition rate
confidence calibration
```

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

Active time 是次要效率结局，不是标注不确定性的替代指标。

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

当前数据中active time的worker方差远高于task方差，因此不得直接比较三臂原始时间均值作为唯一检验。

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

主要估计为 image-equal contrasts。推荐：

1. 先进行三条件总体随机化检验；
2. 对 `Correct−Manual` 与 `Wrong−Manual` 两个预设比较进行Holm控制；
3. `Wrong−Correct` 作为proposal correctness依赖的直接次级比较；
4. 同时报告估计值、95% CI和标准化效应，不只报告p值。

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

不计入正式批次。确认字段、条件分支、保存、刷新和说明材料可用。

### 13.2 Batch 1：24图

- 360次worker-action；
- 每人6 Manual、6 Correct、6 Wrong；
- 每个Wrong family 6图；
- 重点检查技术完整性和manipulation是否明显失败。

### 13.3 Batch 2：24图

累计48图、720次worker-action；每人累计12 Manual、24 Semi。

若科学合同未改变，继续使用同一协议版本；不得根据Batch 1的效应方向选择更有利图片或错误家族。

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
- overall primary-family recognition低于约50%时，重新审查taxonomy和培训。

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

现有25个C1 Manual/Semi配对图的拓扑不一致差值SD约0.473。以此作为粗略规划参考，80% MDE约为：

| 图片数 | 不加DE | DE=1.4敏感性 |
|---:|---:|---:|
| 60 | 0.171 | 0.202 |
| 72 | 0.156 | 0.185 |
| 80 | 0.148 | 0.175 |

因此，72图能够检验中等偏大的平均拓扑分歧变化，但不能保证检出0.05–0.10的小效应。正式启动前应使用与最终 `D_layout` 完全一致的距离、受限随机分配和缺失机制进行重抽样功效模拟。

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
9. Model Issue技术锁验证；
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
- [ ] topology和same-topology geometry分解是否充分；
- [ ] Correct/Wrong operational truth及盲审要求；
- [ ] 四类Wrong family和中等severity；
- [ ] `material_issue=yes/no + confidence 1–5`，不提供unsure；
- [ ] 是否要求Model Issue技术锁作为RQ3启动前提；
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

当前配置与边界：

- `tools/label_studio/label_studio_uncertainty_meta_manifest_v1.json`
- `docs/label_studio/LS_CE_ONLY_OPERATION_SOP_v1.md`
- `docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`
- `docs/thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md`

外部文献整理：

- `C:/Users/ASUS/Downloads/不确定性文献调研.md`（研究背景材料，不是仓库规范真源）。

---

## 18. 一页式建议结论

在导师确认前，本研究最简洁、可执行且相对严谨的候选版本为：

> 使用现有42张高密度Manual图片回答自然标注分歧的深度问题，并以新的72张未暴露图片开展三臂同图随机实验。每张图由5名Manual、5名Correct-Semi和5名Wrong-Semi标注，20名标注者通过受限轮换实现每人18个Manual和36个Semi任务。正式发放分为3批，每批24图。RQ2以图像等权的平均两两布局不相似度为主结果，拓扑和同拓扑几何离散负责分解；质量与时间用于判断收敛是否有益。Semi任务按界面顺序先填写二元Model Issue判断、1–5信心及对应处理分支，再完成布局编辑；本研究不实施阶段锁或阶段事件上报。多人yes/no投票分布定义Model Issue层面的结果不确定性。所有Correct/Wrong truth、随机分配、字段、失败处理和推断方法须在结果可见前冻结。

该建议仍是导师讨论稿，不得直接作为启动授权。
