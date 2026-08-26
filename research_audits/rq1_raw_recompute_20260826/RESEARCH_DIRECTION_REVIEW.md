# 360°布局标注不确定性研究方向：独立审查与推荐方案

**日期**：2026-08-26  
**状态**：`INDEPENDENT REVIEW / NON-NORMATIVE / NOT A METHOD CONTRACT`  
**数据基线**：原始 P1/C1 Label Studio 导出、C1 parser amendment、冻结 canonical authority、冻结 formal active-time 表；修正审计见 `analysis_results/rq1_corrections_20260826/`。

## 1. 核心裁决

当前方向**可以继续，但不能按“已经高把握成立”的版本启动**。最合理的论文结构是：

1. **Study 1 / RQ1：回顾性测量研究**  
   回答在固定协议下，独立 Manual 360°布局标注的 operational reproducibility、cardinality disagreement、computability 与支持量需求。它负责建立测量合同和背景事实，不负责证明“真实多峰 prevalence”。
2. **Study 2 / RQ2：前瞻随机实验，作为论文主贡献**  
   回答一个可发表且可因果识别的问题：**plausible model proposal 的 truth status，究竟使人类输出向正确解收敛、向共同错误收敛，还是增加分散？**
3. **原 RQ3 降级为 exploratory mechanism analysis**  
   当前系统没有 technical phase lock 或 phase-event persistence。Model Issue 只能称为 `protocol-requested appraisal`，不能称为已技术证明的“编辑前识别”，也不能承担正式因果中介。

这不是保守性降级，而是把论文的创新集中到真正可识别的机制：

> **Correct 与 plausible-Wrong proposal 如何改变结构化360°几何标注的输出分布，并区分 productive convergence 与 error homogenization。**

“标注者存在分歧”“多标注比单标注更丰富”“辅助标注更快”均已有大量先例，单独不能支撑强创新。你的差异化必须来自 proposal truth 的随机操纵、distribution-level outcome、结构化几何表示，以及质量—一致性的联合解释。

## 2. 对外部观点的逐项裁决

| 外部观点 | 独立裁决 |
|---|---|
| 42图不是全部RQ1数据 | 成立。42图是高密度测量校准集，不是广覆盖总体。 |
| C1 core有71个严格 `k≥5` 任务 | 不成立。raw-strict 是70；正式 C1 amendment-compliant 派生几何口径是 **72**。 |
| 每臂5人可估计平均几何离散 | 基本成立，但只对跨图片平均效应成立；不能把单图结果当成稳定真值。 |
| `k=8–10` 更适合筛查高分歧图 | 方向成立。对候选 mask distance，Spearman 中位数由 `k=5:0.882` 提升到 `k=8:0.927`。 |
| 历史“supported_multimodal”可直接给 prevalence | 不成立。当前算法在阈值0.90–0.98下，supported count从21降到14，not-evaluable从4升到19；分类高度依赖合同。 |
| active time 尚未建立 | 不成立。冻结 rebinding 表的 SHA 已验证；在84个 Manual `k≥5` 任务中有594个可用 worker-task time。 |
| 72图应默认采用 | 不成立。它不是数据推导的必然结果，而且违反当前约20人、每人最多50份、总量约1,000份的容量约束。 |
| RQ3在无锁情况下仍可做正式机制/中介 | 不成立。最多做协议请求下的描述性 pathway evidence。 |

## 3. RQ1：应当研究“可复现性”，而不是宣称固有真相

### 3.1 推荐表述

> 在冻结的 operational annotation protocol 下，独立 Manual 标注的输出分布有多大、在哪些任务上不稳定、多少标注者可以恢复任务级平均分歧与cardinality多样性？

不建议写成：

- “场景的真实不确定性是多少”；
- “某张图有/没有真实多峰”；
- “工人分歧自动说明存在多个正确布局”。

历史标注同时包含场景歧义、协议解释、工人能力、界面行为、scope失配和偶发错误。RQ1测得的是 **operational annotation reproducibility**，不是纯粹 aleatoric uncertainty。

### 3.2 数据层

推荐固定三层：

- **高密度校准层**：P1 Manual 30图 + C1 anchor 12图，支持量23–26。用于人数下采样、metric比较、cardinality检出率和探索性cluster。
- **广覆盖描述层**：C1 core 75个 Manual task context；正式 amendment-compliant `k≥5=72`。逐图scope尚未重新审定，称为 `assigned operational task sample`。
- **其他阶段敏感性**：C2-B、C2-A-RP、P1 OOS分别报告，不解释成阶段因果变化；本次修正审计没有把它们合并到核心支持量结论。

不得直接回归 `D ~ annotator_count`。C1 anchor/core 和 C2 的支持量由不同设计机制决定；人数效应只能在同一高密度任务内下采样识别。

## 4. 测量合同：冻结一个整体通道，同时保留结构分解

### 4.1 推荐连续 Primary 候选

将当前模糊的 `1-IoU` 明确写成：

\[
d_{\text{mask}}(Y_a,Y_b)=1-\operatorname{IoU}\{M(Y_a),M(Y_b)\},
\]

其中 `M(Y)` 是在周期全景图坐标中，由 ceiling/floor boundaries 围成的 **wall-region mask**。它不是俯视平面 IoU，也不是3D IoU。

采用它的理由：

- 能处理不同 vertical-boundary count 的有效结果；
- 直接对应工人在全景标注界面提交的边界表示；
- 在42图回放中，`k=5` 对全支持任务排序的 Spearman 中位数为 **0.882**，高于 boundary 的0.858和 wall-event的0.809；
- 但 `k=5` 的 mask MAE 中位数仍为 **0.031**，所以它适合跨图片平均比较，不适合把单图值当作精确真值。

### 4.2 必须分开的结构轴

将原 `D_top` 改名为：

\[
D_{\text{count},ic}=P\{n(Y_a)\neq n(Y_b)\},
\]

并单独报告：

- structural validity / computability；
- vertical-boundary count distribution；
- closure / pairing validity；
- geometry hash 仅用于身份、重复和provenance，不得作为 topology signature。

在单房间 Manhattan 周期多边形中，“角点坐标hash不同”不是拓扑不同；即使 boundary count不同，也更准确地称为 cardinality/representation-structure disagreement。完整坐标hash若进入signature，会把几乎所有微小坐标差异错误升级成“拓扑变化”。

### 4.3 无效结果不能被静默删除

若只在 valid pair 上计算 `D_mask`，某一处理臂只要制造更多 invalid outcome，剩余有效样本反而可能看起来更一致。推荐冻结一个透明的 operational pairwise loss：

\[
d^*(Y_a,Y_b)=
\begin{cases}
1-\mathrm{IoU}\{M(Y_a),M(Y_b)\}, & \text{两者均有效},\\
1, & \text{至少一者无效}.
\end{cases}
\]

以每个 image-arm 的10个pair平均值 `D*` 作为 confirmatory operational non-reproducibility outcome，同时强制分解报告：

- invalid-pair probability；
- valid-pair conditional `D_mask`；
- `D_count`；
- penalty sensitivity（例如 invalid penalty 0.5、0.75、1.0）。

若不接受该复合定义，则必须把 valid rate 设为共同解释门，并做 worst-case missingness sensitivity；不能单纯删掉 invalid pair。

## 5. RQ2：唯一值得作为Confirmatory Primary的对比

### 5.1 Primary contrast

冻结：

\[
\Delta_{WC}=E_i[D^*_{i,Wrong}-D^*_{i,Correct}].
\]

理由：它在“都有proposal”的前提下直接识别 proposal truth 的作用，是最贴近理论贡献的对比。

以下作为预注册 secondary contrasts：

- `Correct − Manual`；
- `Wrong − Manual`。

不建议：

- 把三个对比全部设为同等级 Primary；
- 使用 `(Correct+Wrong)/2 − Manual`，因为它会把帮助和伤害人为抵消；
- 根据结果再选择“最有显著性”的对比。

### 5.2 质量轴是解释条件，不是装饰

对每个最终结果计算冻结 reference 下的质量，例如：

\[
U=\mathbf 1(\text{valid})\times\mathrm{IoU}(Y,R).
\]

必须联合解释 `D*` 与 `U`：

| Wrong相对Correct | 质量U | 解释 |
|---|---|---|
| `D*`下降 | 下降 | **error homogenization**：人更一致，但共同错向错误proposal |
| `D*`上升 | 下降 | destabilization / harm |
| `D*`下降 | 不降或上升 | productive convergence |
| `D*`近零变化 | 下降 | 质量伤害存在，但未改变总体离散 |
| 两者均近零 | 对当前强度/样本下无可识别效应 |

这张联合解释表应在看Main结果前冻结。

### 5.3 Correct/Wrong proposal合同

每张Main图必须在分发前冻结：

- researcher-adjudicated in-scope；
- expert-reviewed acceptable Correct proposal；
- plausible、materially wrong、但不是明显破坏性伪造的 Wrong proposal；
- wrong error family、与reference的距离、结构有效性和严重度；
- proposal truth 对工人不可见；
- reference review 与工人结果盲离。

Wrong proposal必须足够强才能构成有效操纵，但不能通过事后选图放大显著性。建议在历史已标图上完成技术/操纵可识别性测试，Main新图一旦启动不得自适应更换severity阈值。

## 6. 样本量：淘汰72，推荐60

当前容量约束为20人、每人最多50份、总量约1,000份。每张图15个提交（3臂×5人）：

| 图数 | 总提交 | 每人任务 | 4图cycle数 | 裁决 |
|---:|---:|---:|---:|---|
| 60 | 900 | 45 | 15 | **推荐**；留每人5份容量处理缺失/替补 |
| 64 | 960 | 48 | 16 | 数学上可行，但每人仅余2份，运行脆弱 |
| 72 | 1,080 | 54 | 18 | **违反现有容量约束，淘汰** |

推荐正式Main：

- **60张新图**；
- 三个大批次，每批20图；
- 每批5个四图cycle；
- 每个cycle内，每名工人分别完成1张 Manual、1张 Correct、1张 Wrong，另1张不暴露；
- 每人每批15份、全程45份，三臂各15份。

72相对60只降低约8.7%的理论标准误；候选 mask distance 的理想化80% MDE下限仅从约0.027降至约0.0246，而实际阈值因处理异质性、building相关、无效结果和新图分布只会更高。它不值得违反硬容量约束。

64图只比60图降低约3.2%的理论标准误，却几乎耗尽替补容量。除非另有冻结的替补工人池，否则不建议。

## 7. 推断单位与统计分析

### 7.1 10个pair不是10个独立样本

每个5人臂产生10个pair，但pair共享annotation。`D_ic` 是二阶 U-statistic；分析单位必须是 image-arm / image-level contrast，不能把10个pair当作独立观测扩大样本量。

### 7.2 Primary推断应尊重真实随机化

推荐：

1. 对每张图计算 `D*_{M}, D*_{C}, D*_{W}`；
2. 形成 image-level `W−C` contrast；
3. 采用尊重四图cycle、5/5/5配额和实际 worker assignment 的 randomization/permutation inference；
4. 给出 image-level effect、置信区间和随机化p值；
5. `C−M`、`W−M` 用同一冻结框架作为secondary，做预先规定的多重性控制。

工人跨图重复、图片来自building，不能只做普通独立样本t检验。可把 cross-classified worker/image mixed model 作为secondary model-based analysis，但不能让模型选择取代设计本身。

### 7.3 Building处理

Building不是研究重点，但它是刺激抽样依赖来源。启动前应：

- 冻结每个building的图数上限；
- 尽可能增加building覆盖，而不是从少数building大量抽图；
- 报告 leave-one-building-out；
- 使用building bootstrap或随机效应敏感性；
- 不把同building图片默认视为完全独立。

### 7.4 Worker画像

历史 worker profile 可以在Main前冻结，用于检查三臂平衡和预注册 moderator；不能在Main中根据正在出现的处理结果动态路由，否则会破坏随机化。Main结束前不得依据结果排除工人、重算画像或重新分配难图。

## 8. RQ3的正确位置

保留以下描述性问题：

- proposal truth 是否改变 `material_issue` appraisal；
- appraisal 是否与 proposal retention、编辑幅度和最终质量关联；
- 工人报告“无问题”时，是否更可能保留Wrong proposal。

但必须写为：

> protocol-requested appraisal collected in the annotation workflow

不能写为：

- technically verified pre-edit detection；
- causal mediator；
- 独立于编辑行为的早期识别能力。

在无technical lock的前提下，把RQ3留作独立正式RQ会削弱审稿可信度。推荐在论文中作为RQ2机制小节或exploratory analysis。

## 9. 现有数据对“显著结果概率”的真实含义

当前数据只能建立测量噪声下限，不能给出处理效应功效。对推荐的 wall-region mask distance：

- `k=5` 单图 MAE中位数约0.031；
- 60图、5/5/5、零处理效应回放的条件80% MDE下限约0.027；
- 该下限没有包含真实实验中最重要的额外方差。

因此：

- 对平均效应明显大于约0.03的操纵，60图存在检测可能；
- 对小于约0.03的效应，当前设计不能被描述为高把握；
- 实际可检测阈值预计高于0.027；
- 在没有可信的前瞻 treatment-effect distribution 前，任何“高概率显著”都是无数据依据的判断。

可发表性是**中等、非高把握**：

- 若发现 `Wrong` 导致质量下降并同时压缩分歧，形成error homogenization证据，创新最强；
- 若只发现Correct辅助更快、质量相近，结果更接近已有AI-assisted annotation效率研究；
- 若只完成RQ1描述和不稳定cluster，多数Q2 HCI/CV审稿人很可能认为贡献不足；
- 若Primary结果为null但操纵检查、quality和retention均显示Wrong被有效感知，仍可形成边界性结论，但不能事后更换Primary挽救故事。

## 10. Main启动前必须冻结的工件

1. `d_mask` 的精确定义、周期seam处理、unit tests与无效结果规则；
2. `D*`、`D_count`、validity、quality `U` 的SAP；
3. 唯一 confirmatory `Wrong−Correct` contrast；
4. 60图清单、scope审定、building配额；
5. Correct/Wrong proposal、error family、severity与独立reference review；
6. 20人具名roster、预先排除、替补规则；
7. 20×3 batch与四图cycle assignment manifest；
8. randomization-inference代码在假数据上的dry run；
9. formal active-time日志身份与freeze manifest；
10. 明确声明无technical phase lock，RQ3仅exploratory。

在这些工件冻结之前，不应启动Main，也不应根据Main结果再改变60/72、Primary metric或Primary contrast。

## 11. 相关原始文献与定位

1. Hoeffding, W. (1948). **A Class of Statistics with Asymptotically Normal Distribution**. *The Annals of Mathematical Statistics*, 19(3), 293–325. DOI: 10.1214/aoms/1177730196.  
   用途：说明平均两两距离是二阶 U-statistic；无偏不等于低方差，pair也不独立。

2. Berzak, Y., Huang, Y., Barbu, A., Korhonen, A., & Katz, B. (2016). **Anchoring and Agreement in Syntactic Annotations**. *Proceedings of EMNLP 2016*, 2215–2224. Association for Computational Linguistics. DOI: 10.18653/v1/D16-1239. [Official PDF](https://aclanthology.org/D16-1239.pdf).  
   用途：自动建议可能改变人类判断并产生anchoring；支持随机操纵proposal truth，而不是假定辅助只影响速度。

3. Mikulová, M., Straka, M., Štěpánek, J., Štěpánková, B., & Hajič, J. (2022). **Quality and Efficiency of Manual Annotation: Pre-annotation Bias**. *Proceedings of LREC 2022*, 2909–2918. European Language Resources Association. [Official PDF](https://aclanthology.org/2022.lrec-1.312.pdf).  
   用途：pre-annotation在另一任务中可提高效率与一致性而不降低质量，说明效应高度依赖任务和proposal质量。

4. Pavoni, G., Corsini, M., Ponchio, F., Muntoni, A., Edwards, C., Pedersen, N., Sandin, S., & Cignoni, P. (2022). **TagLab: AI-assisted annotation for the fast and accurate semantic segmentation of coral reef orthoimages**. *Journal of Field Robotics*, 39(3), 246–262. DOI: 10.1002/rob.22049. [Open-access article/PDF](https://onlinelibrary.wiley.com/doi/full/10.1002/rob.22049).  
   用途：视觉领域已有AI-assisted annotation效率和质量研究；你的创新不能只停留在“辅助更快”。

5. Sun, C., Hsiao, C.-W., Sun, M., & Chen, H.-T. (2019). **HorizonNet: Learning Room Layout With 1D Representation and Pano Stretch Data Augmentation**. *Proceedings of CVPR 2019*, 1047–1056. [Official PDF](https://openaccess.thecvf.com/content_CVPR_2019/papers/Sun_HorizonNet_Learning_Room_Layout_With_1D_Representation_and_Pano_Stretch_CVPR_2019_paper.pdf).  
   用途：界定360°layout的1D boundary/event表示；支撑mask、boundary和wall-event三种测量通道的表示含义。

6. Sun, C., Sun, M., & Chen, H.-T. (2021). **HoHoNet: 360 Indoor Holistic Understanding With Latent Horizontal Features**. *Proceedings of CVPR 2021*, 2573–2582. [Official PDF](https://openaccess.thecvf.com/content/CVPR2021/papers/Sun_HoHoNet_360_Indoor_Holistic_Understanding_With_Latent_Horizontal_Features_CVPR_2021_paper.pdf).  
   用途：界定模型proposal的技术背景，但不证明人类会如何响应Correct/Wrong proposal。

7. Judd, C. M., Westfall, J., & Kenny, D. A. (2012). **Treating Stimuli as a Random Factor in Social Psychology: A New and Comprehensive Solution to a Pervasive but Largely Ignored Problem**. *Journal of Personality and Social Psychology*, 103(1), 54–69. DOI: 10.1037/a0028347.  
   用途：图片是刺激样本，工人与图片交叉重复；不能把所有图片/工人响应视为单层独立样本。

8. Cameron, A. C., Gelbach, J. B., & Miller, D. L. (2011). **Robust Inference With Multiway Clustering**. *Journal of Business & Economic Statistics*, 29(2), 238–249. DOI: 10.1198/jbes.2010.07136.  
   用途：提醒worker/building等非嵌套依赖需要设计或多维稳健推断；本项目cluster数较少，仍需randomization inference和敏感性分析。

9. Wang, Y., Tao, S., Xie, N., Yang, H., Baldwin, T., & Verspoor, K. (2023). **Collective Human Opinions in Semantic Textual Similarity**. *Transactions of the Association for Computational Linguistics*, 11, 997–1013. DOI: 10.1162/tacl_a_00584. [Official PDF](https://aclanthology.org/2023.tacl-1.56.pdf).  
   用途：高争议任务需要更多标签才能恢复响应分布；不能把该文本任务的具体人数直接移植为360°几何标准。

10. Mostafazadeh Davani, A., Díaz, M., & Prabhakaran, V. (2022). **Dealing with Disagreements: Looking Beyond the Majority Vote in Subjective Annotations**. *Transactions of the Association for Computational Linguistics*, 10, 92–110. DOI: 10.1162/tacl_a_00449. [Official PDF](https://aclanthology.org/2022.tacl-1.6.pdf).  
    用途：分歧可包含系统性结构；但你的几何任务同时含错误和协议失配，不能自动把全部分歧解释为有效多解。

11. Pyatkin, V., Yung, F., Scholman, M. C. J., Tsarfaty, R., Dagan, I., & Demberg, V. (2023). **Design Choices for Crowdsourcing Implicit Discourse Relations: Revealing the Biases Introduced by Task Design**. *Transactions of the Association for Computational Linguistics*, 11, 1014–1032. DOI: 10.1162/tacl_a_00586. [Official PDF](https://aclanthology.org/2023.tacl-1.57.pdf).  
    用途：annotation protocol本身会改变分布；支持把你的结论严格限定为冻结协议下的operational response distribution。
