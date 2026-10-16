# 标注不确定性、模型介入与标注者差异：跨计算机视觉、NLP、医学影像与众包学习的文献证据综述

## 执行摘要

“标注不确定性”在学术文献中并不是一个单一概念。至少有四条相互关联但不能混同的研究传统：一是 **crowd-label / noisy-label learning**，把观测标签看作由潜在真实标签、任务难度和标注者误差共同生成；二是 **disagreement / perspectivism**，认为部分分歧不是噪声，而是任务本身允许多个合理解释；三是 **ambiguous structured prediction / segmentation**，直接对多个合理几何或分割解的分布建模；四是近年的 **human–AI / model-assisted annotation**，研究模型 proposal、自动标签或 AI 建议进入标注流程后，人类输出分布如何改变。Dawid–Skene、Whitehill、Raykar、Welinder 等经典工作主要属于第一条传统；Pavlick、Davani、Jiang、Sap 等工作推动了第二条；Probabilistic U-Net、Stochastic Segmentation Networks 和医疗多标注者分割工作体现第三条；中文依存句法标注研究、临床 AI 辅助研究以及 2025 年的 LLM-assisted subjective annotation 实验则直接提供第四条证据。citeturn8search1turn20search1turn19search3turn20search2 citeturn20search25turn18view6turn22search6turn18view7 citeturn19search0turn19search1turn23view0

从这些文献综合起来，标注不确定性至少可以拆成：**拓扑/结构不确定性、模式多样性或多模态、连续几何偏差、语义/协议不确定性、分区可识别性、时间/行为不确定性、元标签不确定性、参考/GT 不确定性、标注者异质性以及模型介入诱导的不确定性**。这些维度并非彼此替代。例如，两组标注可以具有完全相同的角点数和拓扑，却有很大的连续边界位移；也可以拥有很高的 pairwise 几何一致性，却由于共享模型 proposal 而被共同锚定到同一解。医学影像和 NLP 文献同样表明，“高一致性”不能在没有独立 reference 或任务语义证据时自动解释为“更正确”。citeturn23view0turn18view6turn22search6

一个重要的历史变化是：早期工作通常把标注差异当作需要估计和消除的 **observer noise**。Dawid–Skene 通过潜变量和个体 confusion/error rates 推断未观测真值；Whitehill 将标注者能力与任务难度同时纳入；Welinder 则进一步把标注者能力从单一标量扩展成多维潜在属性。较新的工作越来越多地表明，尤其在 NLI、毒性、冒犯性语言、情感判断等主观任务中，分歧可能稳定存在，而且能反映语义歧义、背景知识、身份、价值观和协议解释差异。citeturn8search1turn20search1turn20search2 citeturn20search25turn18view6turn22search6turn22search10

模型介入文献则增加了第二层问题：观测到的“人类共识”可能不再仅来自图像/文本本身，而是来自**共享初始化或共同建议**。在中文依存句法树标注实验中，作者特意设置“人机独立标注”，即不让人工看到机器答案，以规避人工校对中的“认同倾向”；实验中“机器标注＋人工校对”的一致性明显高于人机独立流程，论文据此直接讨论了校对者认同机器结果的倾向。citeturn12view0turn12view1 2025 年一项预注册 LLM-assisted annotation 实验更加直接：350 名独立标注者产生 7,000 个标注，覆盖四种条件、两个模型和两个数据集；向 crowdworkers 展示 LLM 建议并没有使其更快，但提高了自报信心，标注者大量接受模型建议，从而显著改变最终标签分布，并进一步抬高了使用这些“human-approved”标签评价 LLM 时得到的模型成绩。citeturn18view5

相邻的临床 human–AI 文献给出了更强的“模型正确性 × 人类反应”证据。Kiani 等在 11 名病理学家和肝癌全切片任务上发现：模型建议正确时，AI assistance 提高人类正确率；模型错误时则显著降低正确率，且该效应横跨不同专业经验。citeturn13view2 Gaube 等在 138 名放射科医生和 127 名内科/急诊医生中随机操控正确或错误建议，发现错误建议会降低判断准确率，而且有相当一部分医生持续跟随错误建议；论文将这种行为与 anchoring、confirmatory search 等认知机制联系起来。citeturn14view0turn14view1turn14view2turn14view3 Tschandl 等的皮肤癌诊断研究同样发现，高质量 AI 可改善协作结果且低经验临床人员收益更明显，但故意错误的 AI 会误导不同经验层级的人类。citeturn13view1

因此，在现有学术证据中，“模型介入后多人更加一致”至少有两种不可仅凭一致性本身区分的来源：

\[
\text{更高共识}
=
\text{共享有效信息导致的结构发现}
\quad\text{或}\quad
\text{共享 proposal 导致的响应相关/锚定}
\]

而且两者可以同时存在。Polygon-RNN++、Extreme Clicking、SAM data engine 等工作证明机器交互可以有效降低像素级或掩膜标注成本，但这些效率论文通常并不以“多个独立标注者在有/无 proposal 条件下的完整输出分布变化”为主要研究对象，因此不能单独回答 proposal 是否压缩了原本真实存在的多模态。citeturn21search3turn3search0turn4search0

对于不同类型标注者，文献同样不支持“专家总是趋同、非专家只是随机噪声”这一简单模型。Snow 等在五类 NLP 任务中显示，多名非专家标签经过聚合可接近专家标注；但生物医学分割比较中，专家相对专家共识通常优于众包非专家，而众包又可能优于当时的自动算法。citeturn20search0turn10search3 在主观 NLP 中，身份、政治倾向、种族相关信念和语言背景又会系统性改变标签分布，而非仅仅增加随机误差。citeturn18view7turn6search6

最重要的文献层面结论因而不是“分歧越少越好”，而是：**标注数据应被理解为 item、annotator、protocol、reference 和 interface/model intervention 共同生成的观测分布。**现代文献正在从“怎样消除 disagreement”逐渐转向“哪些 disagreement 是噪声、哪些是可重复观点、哪些是任务本身的多个合理解、哪些是模型或界面诱导出来的相关性”。citeturn18view6turn22search6turn22search10turn18view5


## 概念与分类

下表把不同领域中使用的概念统一到一个可计算框架中。需要特别说明：**“分区可识别性”并不是目前文献中像 Shannon entropy 或 inter-rater agreement 那样高度标准化的统一术语**；它更接近 clustering stability、partition identifiability、consensus stability 和“能否把有限个标注稳定分成若干模式”的组合概念。Probabilistic U-Net、SSN、人工分歧建模以及 crowdsourcing identifiability 文献提供了相关理论背景，但具体操作化需要声明聚类算法和相似度规则。citeturn19search0turn19search1turn20search24

| 不确定性维度 | 精确定义 | 可量化对象 | 一组典型计算方式 | 主要文献基础 |
|---|---|---|---|---|
| **拓扑/结构不确定性** | 不同标注对“对象由哪些离散结构组成”存在差异，而不只是坐标误差 | 角点数、墙面数、连通分量、孔洞、图边、句法依存弧、拓扑类别 | 若 \(g_i\) 为第 \(i\) 个标注的拓扑签名，则 \(D_{top}=\frac{2}{k(k-1)}\sum_{i<j}I(g_i\neq g_j)\)；也可计算 \(H_{top}=-\sum_g p_g\log p_g\) | 结构化分割和多标注者医学分割表明，标注者误差可以具有明显空间/结构形式，而非独立像素噪声。citeturn23view0turn19search1 |
| **模式多样性 / 多模态** | 同一 item 存在两个或更多内部相对一致、彼此明显不同的受支持解 | 离散类别、几何簇、完整 mask hypotheses | \(H=-\sum_m p_m\log p_m\)；\(H_{norm}=H/\log M\)；Gini–Simpson \(=1-\sum_mp_m^2\)；最大模式占比 \(p_{\max}\) | Probabilistic U-Net 和 SSN 直接建模单张图的多个空间一致解；NLI 文献发现人类分歧可稳定存在。citeturn19search0turn19search1turn20search25 |
| **连续几何偏差** | 标注者采用同一结构解释，但边界、角点、中心线等连续位置不同 | 坐标、曲线、mask、3D 点或面 | \(\bar d=\frac{2}{k(k-1)}\sum_{i<j}d(x_i,x_j)\)；可用 RMSE、平均表面距离、Hausdorff、IoU、Dice 等 | 医学影像和交互分割文献长期以边界重叠与表面距离区分连续误差和结构错误。citeturn23view0turn19search0 |
| **语义/协议不确定性** | 标注者对任务定义、句义、scope、类别边界、上下文或说明的理解不同 | 类别选择、scope、理由编码、协议规则 | Krippendorff \(\alpha=1-D_o/D_e\)；类别熵；pairwise agreement；多标签分布；混合效应模型 | Jiang 将 NLI 分歧细分为 10 类、3 大类；Sandri 将主观任务分歧区分为 subjectivity、sloppiness、context 等来源。citeturn22search6turn22search10 |
| **分区可识别性** | 给定有限标注及相似度规则，是否存在稳定、近唯一的模式分区 | cluster assignment、bootstrap partitions | 重采样 \(B\) 次：`cluster(subset_b)`；计算 partition success rate、bootstrap ARI/NMI、consensus matrix；例如 \(I=1-\frac{1}{B}\sum_b I(\text{partition nonunique})\) | crowdsourcing 中存在真值/参数 identifiability 文献；多假设分割则展示不同完整输出分布。citeturn20search24turn19search0turn19search1 |
| **时间/行为不确定性** | 同一任务或同一标注者的操作时间、暂停、修订、点击轨迹等存在可重复或长尾差异 | active time、lead time、clicks、revisions、sessions | median/IQR、MAD、log-time SD、CV、尾部分位数；事件序列可计算 revision rate、return rate、burst interval | 中文依存标注研究分别报告标注与审核耗时；交互式视觉标注研究也把时间和交互次数作为核心结果。citeturn12view1turn21search3turn3search0 |
| **元标签不确定性** | 对“困难”“遮挡”“模型良好”“不确定原因”等描述标注本身也可能存在分歧 | difficulty、confidence、reason tags、multi-select tags | 单标签熵；ordinal ICC；多选集合 Jaccard：\(J(A,B)=|A\cap B|/|A\cup B|\)；每 tag 的 Bernoulli entropy | NLP 的 disagreement taxonomy 和 annotator-attitude 文献表明，对任务性质的判断也与观察者视角有关。citeturn22search6turn18view7 |
| **参考 / GT 不确定性** | “ground truth” 本身不是直接可观测或并非唯一，而是从专家、众包或模型中估计出来 | latent \(z_i\)、expert consensus、reference version | Dawid–Skene：估计 \(P(z_i\mid Y,\Pi)\)；posterior entropy；专家间 disagreement；reference-version sensitivity | Dawid–Skene、Raykar、Tanno、Zhang 等均把真实标签和观察者错误区分为不同潜在对象。citeturn8search1turn19search3turn19search2turn23view0 |
| **标注者异质性** | 不同标注者具有系统性不同的 sensitivity、specificity、类别偏好、技能或观点 | worker confusion matrix、bias、random effect | 每工人 \(\Pi^{(r)}_{ab}=P(Y=b\mid Z=a,r)\)；worker random-effect variance；test–retest 或 split-half 稳定性 | Whitehill 引入 expertise 与 item difficulty；Welinder 把 annotator latent state 扩展为多维；Sap 展示身份和信念相关的系统标签变化。citeturn20search1turn20search2turn18view7 |
| **模型介入不确定性** | model proposal 改变了人类输出的条件分布，因此最终标签同时反映 item 和 proposal | adoption、edit distance、proposal-conditioned label distribution | adoption \(A=P(y_{final}=y_{proposal})\)；编辑距离；\(\Delta H=H_{assist}-H_{manual}\)；proposal-attraction 可比较最终结果距不同 proposal 的距离 | 中文依存标注、LLM-assisted annotation 及临床 AI 决策研究都发现 AI 建议能够系统性改变人类判断。citeturn12view0turn12view1turn18view5turn13view2turn14view0 |

其中三个区分尤其重要。

第一，**结构不确定性与连续偏差不同**。例如，两个室内布局标注都包含六个相同语义角点，但天花板边界偏离 20 像素，是连续几何问题；若一人认为有额外墙面而增加两个角点，则首先是拓扑模式问题。医学多标注者分割研究也发现，观察者差异能够表现为 thinning、thickening、断裂或系统边界位移等具有空间结构的错误。citeturn23view0

第二，**多模态与普通方差不同**。如果一半人标在位置 \(x=0\)，另一半标在 \(x=10\)，均值 \(x=5\) 可能根本不是任何人的合理解；Probabilistic U-Net 和 SSN 的核心动机正是避免把多个空间一致解释压缩成单一像素平均不确定性。SSN 明确对完整 label map 的联合分布建模，而非独立地给每个像素一个置信度。citeturn19search0turn19search1

第三，**GT 不确定性与 worker uncertainty 不是同一层次**。Dawid–Skene 的基本思想就是：观察到的标注和 latent truth 分开建模；Raykar 将这种思想与监督模型联合；Tanno 和 Zhang 则把 annotator confusion / spatial error 扩展到现代视觉任务。于是，“离 GT 远”只能说明相对给定 reference 的偏离，除非 reference 的来源和稳定性已经独立确立，否则它并不与“标注本身不合理”逻辑等价。citeturn8search1turn19search3turn19search2turn23view0


## 文献谱系与代表性工作

下面汇总三十篇具有代表性的原始论文。时间范围刻意保留了 1979 年以来的经典基础，同时重点覆盖 2018–2025 年的人类分歧、概率分割和人机协作研究。表中的“样本规模”按照论文可直接比较的层级记录；对于纯方法论文或包含多个不同数据集的工作，不人为合并成一个无意义的总 \(N\)。

| 工作 | 年份 / 来源 | 任务与样本规模 | 方法 | 主要发现 | 数据/代码公开情况 | 模型介入关联与主要局限 |
|---|---|---|---|---|---|---|
| Dawid & Skene, *Maximum Likelihood Estimation of Observer Error-Rates Using the EM Algorithm* citeturn8search1 | 1979, JRSS C | 多分类 observer judgments；方法型论文 | 潜在真值 + 每观察者 error matrix，EM | 在无直接真值情况下可联合估计真实类别与观察者误差率 | 历史论文；无现代代码仓库 | 无 AI proposal；假设可由固定混淆矩阵描述 observer |
| Snow et al., *Cheap and Fast—But is it Good?* citeturn20search0 | 2008, EMNLP | 5 类 NLP 标注任务，专家与 Mechanical Turk 非专家 | 多人非专家聚合与专家标签比较 | 多名非专家聚合在多个 NLP 任务中可接近专家质量 | 论文与相关 NLP 资源公开；统一代码不是研究重点 | 说明“非专家≠纯噪声”；不研究模型建议 |
| Whitehill et al., *Whose Vote Should Count More* citeturn20search1 | 2009, NeurIPS | 模拟 + 真实众包图像标签 | GLAD：同时估计 labeler expertise 与 item difficulty | 比简单多数投票更能处理不同能力和不同任务难度 | 方法公开；现代复现实现较多 | 无模型介入；把 ability 主要作为标量 |
| Raykar et al., *Learning From Crowds* citeturn19search3 | 2010, JMLR | 多个分类/回归 crowdsourcing 场景 | 联合学习 classifier、latent truth 与 annotator quality | 多标注者标签可在没有显式 gold 的情况下进入监督模型 | JMLR 全文公开 | 主要将分歧视为 noisy observation；主观多真值不是中心 |
| Welinder et al., *The Multidimensional Wisdom of Crowds* citeturn20search2 | 2010, NeurIPS | 图像众包任务 | item 与 annotator 的多维 latent factor 模型 | 标注者差异不必压缩为单一“能力”参数 | 论文公开 | 无 AI proposal；为“稳定个人偏好/维度”提供早期模型 |
| Gurari et al., *How to Collect Segmentations for Biomedical Images?* citeturn10search3 | 2015, WACV | 305 个 biomedical objects，6 个生物医学数据集；专家、crowd、算法 | 与 expert-consensus segmentation 比较 | 以该 expert consensus 为 reference 时，专家整体最好，众包非专家次之，自动算法再次之 | 论文公开 | 不涉及共享 proposal；GT 由专家共识定义，因此仍具有 reference-definition 依赖 |
| Rodrigues & Pereira, *Deep Learning from Crowds* citeturn5search0 | 2018, AAAI | 多个 crowdsourced classification 数据集 | end-to-end crowd layer 学习 annotator confusion | 可在神经网络训练中直接建模不同 annotator reliability，而不先硬聚合标签 | 作者实现曾公开 | 主要是噪声建模，不研究主观多模态 |
| Kohl et al., *A Probabilistic U-Net for Segmentation of Ambiguous Images* citeturn19search0 | 2018, NeurIPS | ambiguous image segmentation，包括医学图像和 Cityscapes 类型任务 | conditional VAE + U-Net；采样多个 segmentation hypotheses | 单张图可有多个合理且空间一致的分割；模型可学习这些模式及频率 | 论文和实现公开 | 不研究人类被 proposal 影响；核心对象是标签分布本身 |
| Acuna et al., *Polygon-RNN++* citeturn3search0 | 2018, CVPR | polygon instance segmentation annotation | 模型预测多边形、人类交互修正 | 人机交互可明显减少逐像素标注成本 | 论文/代码公开 | 关注效率和最终精度，非多标注者分布或锚定 |
| Peterson et al., *Human Uncertainty Makes Classification More Robust* citeturn22search0 | 2019, ICCV | CIFAR 类视觉分类上的高密度人类判断分布 | 用人类软标签分布而非 one-hot targets 训练 | 人类类别分布携带可用于提高分类鲁棒性的结构信息 | 相关人类标签数据公开 | 人类 disagreement 被当作信息而非必须清除的噪声；无 model-assisted annotator |
| Geva et al., *Are We Modeling the Task or the Annotator?* citeturn22search1 | 2019, EMNLP-IJCNLP | 3 个 NLU 数据集 | annotator ID、训练/未见 annotator 分割 | 使用 annotator ID 可以提高性能，模型还能识别高产标注者；对未见过的标注者往往泛化较差 | NLP 数据公开 | 证明 dataset creator / worker signature 能进入模型 |
| Tanno et al., *Learning From Noisy Labels by Regularized Estimation of Annotator Confusion* citeturn19search2 | 2019, CVPR | 多个视觉分类数据集、模拟和真实 annotators | jointly estimated annotator confusion + regularization | 能联合估计标签和 annotator confusion，包括每图标注很少的条件 | 论文公开 | 仍以 latent ground truth 为主要假设 |
| Pavlick & Kwiatkowski, *Inherent Disagreements in Human Textual Inferences* citeturn20search3turn20search25 | 2019, TACL | NLI 多人判断 | 增加 ratings、改变 context，比较人类和模型 uncertainty | 相当一部分 disagreement 随增加 ratings/context 仍持续；现有 NLI 模型 uncertainty 与人类 disagreement 不一致 | 数据/论文公开 | 直接反驳“更多人以后分歧必消失”的一般假设 |
| Sap et al., *The Risk of Racial Bias in Hate Speech Detection* citeturn6search6 | 2019, ACL | Twitter hate/offensive language，AAE 等语言变体 | dialect/race context 与 annotation bias 分析 | AAE 与黑人身份相关文本更易被判 offensive；给标注者语言/身份语境可改变该偏差 | 数据研究公开 | 展示 annotator perception 与语言身份之间的系统联系 |
| Zhang et al., *Disentangling Human Error from the Ground Truth in Segmentation of Medical Images* citeturn23view0 | 2020, NeurIPS | MNIST toy + MSLSC、BraTS、LIDC-IDRI 三个医学分割数据集 | 两个 coupled CNN 同时学习 latent segmentation 与 annotator reliability | 在标注少、分歧大时优于基线，并能捕获 annotator error 的空间结构 | 论文第一页明确给出公开代码 | 仍需要模型对“error vs truth”的结构性假设 |
| Monteiro et al., *Stochastic Segmentation Networks* citeturn19search1 | 2020, NeurIPS | ambiguous segmentation | label-map logits 的低秩 multivariate Gaussian | 相比 pixel-independent uncertainty，可产生空间一致的多个完整假设 | 论文/实现公开 | 不直接建模不同人是谁，而主要建模 aleatoric label-map distribution |
| Kiani et al., *Impact of a Deep Learning Assistant on Histopathologic Classification of Liver Cancer* citeturn13view2 | 2020, npj Digital Medicine | 11 名病理学家；80 张测试 WSI，另有验证集 | 有/无 DL assistant 的病理诊断比较，并按 AI 是否正确分层 | AI 正确时显著帮助人类，AI 错误时显著降低人类准确率；平均效应掩盖这种条件异质性 | 研究材料按论文政策提供 | 是 clinical judgment，不是 dataset annotation；但直接测量错误 AI 对专家判断的牵引 |
| Tschandl et al., *Human–computer collaboration for skin cancer recognition* citeturn13view1 | 2020, Nature Medicine | 大规模国际皮肤病变 reader study，不同经验层级 | 人类、AI、不同形式人机协作以及 faulty AI | 优质 AI 可提高协作表现，经验较少者获益较大；错误 AI 会误导不同经验层级 | 测试图像和 reader-level 数据公开，模型材料按论文说明提供 | 邻近 human-AI judgment 证据，非纯数据标注 |
| Zhang & de Marneffe, *Identifying inherent disagreement in NLI* citeturn22search16 | 2021, NAACL | CommitmentBank | Artificial Annotators 模拟 annotation modes | 可区分系统性一致项目和 inherent disagreement items，且捕获语言/上下文模式 | 论文与数据资源公开 | 把 disagreement modes 本身作为建模对象 |
| Leonardelli et al., *Agreeing to Disagree* citeturn7search3 | 2021, EMNLP | offensive-language annotation | 保留 annotator disagreement 的数据构造与分析 | 主观任务中强制 majority aggregation 会丢弃有效的观察者差异 | ACL 论文/相关数据公开 | 不涉及 AI proposal |
| Gaube et al., *Do as AI say: susceptibility in deployment of clinical decision-aids* citeturn14view0turn14view1 | 2021, npj Digital Medicine | 138 radiologists + 127 内科/急诊医生；8 个胸片病例 | 建议来源 AI/人类与建议正确性随机操控 | 错误建议降低判断准确度，不同医生存在显著 susceptibility；错误建议的影响并不限于低经验人群 | 研究材料按论文说明 | 对 anchoring / confirmatory search 的邻近实证非常直接 |
| Mostafazadeh Davani et al., *Dealing with Disagreements* citeturn18view6 | 2022, TACL | 7 个二分类主观 NLP 任务 | multi-annotator multitask model，每人判断作为独立 subtask | 个体标注建模可达到或超过预聚合标签训练，模型 uncertainty 与人类 disagreement 更一致 | ACL 论文与相关资源公开 | 明确将系统分歧理解为观点/价值差异的一部分 |
| Jiang & de Marneffe, *Investigating Reasons for Disagreement in NLI* citeturn22search6 | 2022, TACL | NLI | 10 类、3 大类 disagreement taxonomy；4-way 与 multilabel modeling | 分歧既可能来自句义不确定，也可能来自 annotator bias 和 task artifact；multilabel 更能保留可能解释 | 论文/资源公开 | 提供“语义歧义”和“标注流程 artifact”分离框架 |
| Sap et al., *Annotators with Attitudes* citeturn18view7 | 2022, NAACL | 两项在线实验；人口统计和政治/种族信念多样的参与者 | annotator identity、belief 与 toxicity rating 联合分析 | 保守倾向及较高 racist-belief score 的标注者对 anti-Black 与 AAE 文本表现出方向不同的系统 rating 差异 | 论文公开 | 说明 annotator group differences 不是单纯 variance inflation |
| 周明月等，《数据标注方法比较研究：以依存句法树标注为例》 citeturn12view0turn12view1 | 2022，《清华大学学报（自然科学版）》 | 随机/困难句法数据；双人独立、人机独立、机器标注人工校对等流程 | 比较准确率、一致性、标注/审核时间与成本 | 作者专门用“人机独立标注”避免人工看到机器结果；机标人校较高的一致性被解释为存在“认同倾向” | 中文论文公开 | 与“共享模型 proposal 是否制造共识”高度直接相关 |
| Amgad et al., *NuCLS* citeturn10search4 | 2022, GigaScience | 乳腺癌病理；超过 22 万个 nucleus annotations；医学生、病理专家等 | 可扩展众包核分类/分割，结合算法辅助 | 证明在医学病理中可把不同专业层级和算法辅助结合到大规模标注流程 | 数据和代码公开 | 模型提示可以改变非专家标注能力；任务和审核结构复杂 |
| Kirillov et al., *Segment Anything* citeturn4search0 | 2023, ICCV | SA-1B：约 1,100 万图像、超过 10 亿 masks | 三阶段 data engine，从 model-assisted 到更自动化数据生成 | 展示模型介入可以扩展到十亿级 mask 数据生产 | 模型、代码、SA-1B 数据公开 | 重点是规模和模型能力，并未随机估计 model proposal 对人类 disagreement distribution 的因果影响 |
| Sandri et al., *Why Don’t You Do It Right?* citeturn22search10 | 2023, EACL | 英文 Twitter offensive-language 数据子集 | disagreement reason taxonomy + classification | disagreement 可来自 subjectivity、sloppiness、上下文不足等不同机制，不宜作为同质噪声处理 | ACL 论文公开 | 不涉及模型建议，但给出分歧原因层级 |
| Wu et al., *Calibrate the Inter-Observer Segmentation Uncertainty via Diagnosis-First Principle* citeturn10search2 | 2024, IEEE TMI | 眼底 optic disc/cup、甲状腺超声、皮肤病变等多类医学影像 | 用下游诊断相关性校准 inter-observer segmentation uncertainty | 不是把每一种 segmentation variation 等价处理，而是按临床诊断信息对不确定性进行校准 | 论文公开 | 说明“标注差异大小”与“下游意义”并非同一量 |
| Schroeder, Roy & Kabbara, *Just Put a Human in the Loop?* citeturn18view5 | 2025, Findings ACL | 350 unique annotators；7,000 annotations；4 conditions；2 models；2 datasets | 预注册 LLM-assisted subjective annotation 实验 | LLM 建议没有加快标注，却提高自报信心；标注者大量接受建议，标签分布改变，进而显著提高用这些标签评估 LLM 得到的成绩 | ACL 论文公开；论文报告完整预注册设计 | 当前最直接的“human-approved ≠ independent human ground truth”证据之一 |

这组文献形成了一条较清楚的历史轨迹。

**早期阶段：把 observer disagreement 当作 measurement error。**  
Dawid–Skene 的 latent truth + observer confusion 模型奠定了后来的 crowd aggregation 框架；Whitehill 加入 item difficulty，Welinder 加入多维 annotator characteristics，Raykar 则把 truth inference 与下游 classifier training 联合起来。citeturn8search1turn20search1turn20search2turn19search3

**中间阶段：从标量“准确率”转向结构化不确定性。**  
医学和视觉研究发现，观察者错误可以具有明显的空间结构；Probabilistic U-Net 和 SSN 更进一步，不试图强行得到唯一 mask，而是学习完整输出分布。citeturn19search0turn19search1turn23view0

**近期阶段：把 disagreement 本身视为数据。**  
Pavlick & Kwiatkowski 发现 NLI disagreement 在增加 ratings 或 context 后仍可能持续；Davani 等显示 multi-annotator model 能利用这种信息；Jiang、Sandri 则进一步区分 disagreement 的语义、偏见、artifact、context 和 careless/sloppy 等来源。citeturn20search25turn18view6turn22search6turn22search10

**最新阶段：AI 不再只是消费标签，而开始参与制造标签。**  
这改变了经典“item → human label”的生成结构，因为实际过程变为：

\[
X
\longrightarrow
\begin{cases}
P=f_{\theta}(X),\\
Y_r=h_r(X,P,\text{protocol},\text{history})
\end{cases}
\]

此时多个标注者的相关性可能部分来自共同 \(P\)，而不是共同观察到同一个客观结构。中文依存标注研究和 2025 年 LLM-assisted annotation 实验都直接观察到这一现象。citeturn12view0turn12view1turn18view5


## 模型介入与人类不确定性

模型介入文献中可以客观区分至少五类现象；它们在统计上并不是同一个效应。

| 文献中的现象 | 可观察结果 | 已有直接证据 | 不能由该结果单独证明的事情 |
|---|---|---|---|
| **信息引导 / structure discovery** | 好模型介入后准确率提高、时间减少或有效结构更容易被发现 | 交互分割、Tschandl、Kiani 等都显示高质量模型能够帮助人类。citeturn3search0turn13view1turn13view2 | 不能仅凭最终一致性判断帮助是否来自真正结构发现 |
| **锚定 / proposal attraction** | 最终答案向初始化 proposal 移动；proposal 错时人类也系统性偏移 | 中文依存标注的“认同倾向”、Kiani 的 wrong-AI effect、Gaube 的 incorrect-advice susceptibility、Schroeder 的 LLM-label adoption。citeturn12view1turn13view2turn14view0turn18view5 | 不能推出所有接受 proposal 都是不合理 |
| **共享初始化诱导的相关性** | 有 proposal 时不同人的标签分布更集中 | Schroeder 直接观察到建议改变总体标签分布；中文研究发现机标人校一致性高于独立人机流程。citeturn18view5turn12view1 | 共识提高不能独立区分“真实纠错”与“共同锚定” |
| **错误继承 / automation bias** | AI 错误时人类正确率下降 | Kiani、Gaube、Tschandl 都观察到错误 AI 或建议可误导人类。citeturn13view2turn14view0turn13view1 | 不是所有修改 AI 的行为都更正确，也不是所有保留 AI 都有问题 |
| **评估反馈污染** | AI 辅助产生的“human-approved”标签再次用于评估同类模型，模型分数发生系统变化 | Schroeder 等发现 LLM suggestion 改变标签分布，并显著抬高基于这些标签得到的 LLM 评价。citeturn18view5 | 不能把“有人类审核”简单等同于独立 gold |

中文依存句法标注研究对“是否展示机器结果”进行了尤其有价值的流程区分。论文把“机器标注＋人工校对”和“人机独立标注”区分开来；在人机独立流程中，人工在独立完成自己的标注前并不知道机器答案，目的正是减少看到 machine output 后的认同倾向。citeturn12view0

论文在 MT 数据上报告的部分结果具有直接可比性。困难样本中，双人独立标注准确率约 89.2%，人机独立约 85.0%；随机样本对应约 94.1% 与 93.6%。与此同时，人机独立流程所需总时间明显少于双人独立流程：困难样本约 81 对 152 秒/句，随机样本约 55 对 119 秒/句。更关键的是，作者观察到“机标人校”的一致性显著高于人机独立，并明确将其联系到校对者对机器结果的认同倾向。citeturn12view1

这与视觉几何标注中的 shared proposal 问题具有直接结构对应：

\[
\text{Manual: }X\rightarrow Y_r
\]

\[
\text{Semi: }X\rightarrow P,\quad (X,P)\rightarrow Y_r
\]

Semi 条件下，\(P\) 是所有工人的共同输入，因此

\[
\operatorname{Cov}(Y_r,Y_s\mid X)
\]

可能因为共享 proposal 增大。换言之，观察到的 inter-rater agreement 同时包含 item information 和 common-treatment correlation。这一点并非某一篇论文统一采用的公式，而是上述人机标注文献所对应的统计生成结构。citeturn12view0turn18view5

Schroeder 等的 2025 年研究尤其说明，**“人工审核过”并不会自动恢复 independence**。在 350 人、7,000 个 annotation 的预注册实验中，LLM suggestion 没有让标注者更快，却提高了其自报 confidence；更重要的是，annotators 显著采纳 suggestion，使标签分布相对 baseline 发生改变。用这些 assisted labels 重新评价 LLM 时，模型性能也显著提高。citeturn18view5

临床文献则提供了“proposal correctness”变化时的反事实方向信息。Kiani 等报告，在模型正确的病例上，辅助提高人类正确判断的 odds；当模型错误时，辅助方向相反。论文报告的条件效应大约为正确 AI 时 OR 4.289、错误 AI 时 OR 0.253。citeturn13view2 这意味着只报告所有病例合并后的“AI assistance 平均效应”，会把两个方向相反的机制平均掉。

Gaube 等还发现，这种 susceptibility 并不是简单的“专家不会受影响”。研究中的 138 名放射科医生和 127 名内科/急诊医生都可能受错误建议影响；个体层面，不同专业群体中都有持续跟随错误 advice 的参与者，也都有持续拒绝错误 advice 的参与者。论文讨论了 anchoring 和 subsequent confirmatory information search 作为可能机制。citeturn14view1turn14view2turn14view3

对“模型是否为了某种硬结构约束强行拟合”这一更具体问题，目前检索到的 annotation 文献中**没有形成与“Manhattan forced fitting”完全对应的标准研究类别**。最接近的三个文献概念是：

1. **initialization/proposal bias**：人类结果向已有 proposal 偏移；citeturn12view1turn18view5
2. **automation bias / incorrect-advice susceptibility**：模型错误时仍能牵引人类；citeturn13view2turn14view0
3. **model-induced label-distribution shift**：共享模型建议使最终人类标签总体分布改变。citeturn18view5

因此，现有文献并不支持把“工人修改了一个高 GT-score proposal”自动称为 over-correction 或 harmful edit。现有实证研究实际上要求至少把 **proposal correctness、最终 correctness、是否修改、修改大小和 suggestion exposure** 分开。Kiani 的结果就是一个典型例子：关键不是工人有没有遵从 AI，而是 AI 在该病例中是否正确。citeturn13view2


## 不同标注者类型的差异

标注者类型差异可以分为“能力差异”和“观点差异”两类。前者更接近 Dawid–Skene/Whitehill 的 confusion 或 expertise；后者更接近 Welinder、Davani、Sap 的 multidimensional perspective。二者在观测上可能都表现为“与多数人不一致”，但统计含义完全不同。citeturn8search1turn20search1turn20search2turn18view6turn18view7

| 标注者类型 | 文献中典型行为特征 | 常用度量 | 实证结果 |
|---|---|---|---|
| **领域专家** | 平均 reference alignment 通常较高，但专家间仍可有系统 inter-observer variation | expert–expert Dice/IoU、ICC、confusion matrix、边界距离 | 医学影像文献反复记录 inter-reader variability；Zhang 等因此专门把 expert error 与 latent truth 分开建模。citeturn23view0 |
| **非专家 / 众包工人** | 单人方差通常更大，但多人聚合可有较高质量 | majority accuracy、worker confusion、agreement vs expert、cost/time | Snow 在五类 NLP 任务中发现多人非专家聚合可接近专家；生物医学分割研究中相对专家共识，专家整体仍优于 crowds。citeturn20search0turn10search3 |
| **经过任务训练的非专家** | familiarity、protocol learning 和 worker-specific bias 同时存在 | learning curve、within-worker consistency、worker random effects | 经典 crowd models 和 annotator-ID 研究显示，worker identity 能形成稳定数据结构；Geva 等甚至发现 NLP 模型会学到 annotator-specific signatures。citeturn20search1turn22search1 |
| **具有不同身份/价值观的标注者** | 分歧可能有明确方向性，而不是均值周围对称噪声 | group conditional probability、mixed-effects coefficients、individual label distributions | Sap 等发现政治倾向和种族相关信念与 toxicity ratings 有强关联；AAE 和 anti-Black language 的方向还不相同。citeturn18view7 |
| **Manual 工人** | 输出主要条件于 item、protocol 和个人 latent state | entropy、pairwise distance、worker bias、time | 可作为人类自然分歧分布的观测，但仍会受协议、界面和工人构成影响；主观 NLP 文献表明这种分歧未必收敛到唯一标签。citeturn20search25turn18view6 |
| **模型辅助工人** | 输出同时条件于 item 和 proposal；可能提速、纠错，也可能锚定 | edit rate、proposal retention、final–proposal distance、conditioned accuracy、label-distribution shift | 中文句法研究、临床辅助研究和 LLM-assisted annotation 均记录了 suggestion-dependent shifts。citeturn12view1turn13view2turn18view5 |
| **人工校对模型输出的 reviewer** | “不修改”不等于独立同意；review task 的默认状态本身影响行为 | acceptance rate、false acceptance、false correction、time | 中文研究明确用“人机独立”来避免 machine-first correction 中的认同倾向。citeturn12view0turn12view1 |
| **自动模型 / 自动后处理** | 无人类时间波动，但错误具有 architecture/constraint-specific structure | output calibration、failure mode、topology violation、IoU | 概率分割工作证明模型自身也可有 multimodal predictive distributions；因此“自动结果”并不是零不确定性。citeturn19search0turn19search1 |

专家和非专家之间的关系并不是单调的。对于规则明确、专家 gold 相对稳定的任务，专家往往具有更高的单人准确性；而 Snow 等证明，在部分 NLP 任务上增加非专家数量可以有效弥补单个非专家质量差距。citeturn20search0turn10search3

但在主观任务中，“专家”本身也不一定定义唯一真值。Davani 等在七个二分类任务上发现，对每位 annotator 分别建模而不是先 majority-vote，可以达到相同或更好的预测性能，而且由 multi-annotator model 给出的不确定性与真实人类分歧更相关。citeturn18view6 Jiang & de Marneffe 又表明，NLI 中有的 disagreement 是句义本身不确定，有的是 annotator bias，有的是 task artifact；将所有分歧压成一个 error rate 会失去这些差异。citeturn22search6

标注者人口统计也不能简单用“组均值”替代个体。Sap 等发现身份和信念确实与 toxicity ratings 强相关；但更广泛的 perspectivism 文献表明，同一人口组内部依旧存在大量个人差异，所以人口属性只是 annotator heterogeneity 的一部分。citeturn18view7turn18view6

对 model-assisted worker 而言，最重要的新变量不是单纯“skill”，而是**reliance profile**：

\[
R_r
=
P(\text{follow proposal}\mid
\text{proposal correct/incorrect},r).
\]

临床文献显示这种 profile 在个体间差异很大。Gaube 等观察到一些医生频繁遵从错误 advice，另一些医生能够持续拒绝；Kiani 等则表明 model correctness 与 assistance 的效应方向高度相关。citeturn14view3turn13view2 因而，“模型辅助工人”的不确定性至少包含：

\[
\text{个人几何/语义偏好}
+
\text{普通任务难度反应}
+
\text{对模型 proposal 的依赖程度}.
\]

这比传统单一 worker accuracy 参数更接近现代 human–AI annotation 的实际数据生成过程。citeturn20search2turn18view5


## 文献中的测量、统计与可复现实现

现有研究中最常见的一个错误是只计算最终 majority label；上述文献实际上提供了从“原始多人响应”到“潜在真值、模式和人机条件效应”的多层测量体系。Dawid–Skene、Raykar、Whitehill、Tanno 等属于 latent-truth 模型；Davani、Pavlick、Jiang 等属于 disagreement-preserving 分析；Kohl 和 Monteiro 属于 structured multimodal distribution；human–AI 文献则增加 treatment/proposal 变量。citeturn8search1turn19search3turn20search1turn19search2 citeturn18view6turn20search25turn22search6

**标签分布层。** 对一个 item 的 \(K\) 个标注，若分为 \(M\) 个模式：

\[
p_m=\frac{n_m}{K},
\qquad
H=-\sum_{m=1}^{M}p_m\log p_m.
\]

归一化 entropy：

\[
H_{\mathrm{norm}}
=
\begin{cases}
H/\log M,&M>1,\\
0,&M=1.
\end{cases}
\]

同时可保留：

\[
G=1-\sum_m p_m^2
\]

和

\[
L=\max_m p_m.
\]

\(H\) 对稀有模式敏感，\(G\) 是两个随机 annotators 取不同模式概率的直接函数，\(L\) 描述最大模式占比。将这些量同时保留比只保留 majority share 更接近 disagreement-preserving 文献的思路。citeturn18view6turn19search0turn19search1

一个最小 Python 实现为：

```python
from collections import Counter
from math import log

def mode_uncertainty(labels):
    counts = Counter(labels)
    n = sum(counts.values())
    p = [v / n for v in counts.values()]

    entropy = -sum(x * log(x) for x in p if x > 0)
    norm_entropy = entropy / log(len(p)) if len(p) > 1 else 0.0
    gini_simpson = 1.0 - sum(x * x for x in p)
    largest_mode = max(p)

    return {
        "n": n,
        "n_modes": len(p),
        "shannon_entropy": entropy,
        "normalized_entropy": norm_entropy,
        "gini_simpson": gini_simpson,
        "largest_mode_share": largest_mode,
    }
```

**连续几何层。** 对同拓扑的几何 \(x_1,\ldots,x_K\)，pairwise dispersion 可以写成：

\[
D_{\mathrm{geo}}
=
\frac{2}{K(K-1)}
\sum_{i<j} d(x_i,x_j).
\]

如果是闭合多边形，\(d\) 不能直接在未对齐的 vertex arrays 上计算，而需要先解决起点、方向和循环对应问题；如果 topology 不同，则连续 RMSE 和 topology disagreement 应分别报告。多标注者医学分割工作正是因为不同观察者错误具有空间结构，不能简单把所有差异视为 pixel-independent noise。citeturn23view0turn19search1

```python
import numpy as np

def pairwise_dispersion(geometries, distance_fn):
    vals = []
    for i in range(len(geometries)):
        for j in range(i + 1, len(geometries)):
            vals.append(distance_fn(geometries[i], geometries[j]))
    return {
        "pair_count": len(vals),
        "mean": float(np.mean(vals)) if vals else np.nan,
        "median": float(np.median(vals)) if vals else np.nan,
        "q90": float(np.quantile(vals, 0.90)) if vals else np.nan,
    }
```

**参考/GT 层。** Dawid–Skene 类型模型并不把 majority vote 当成真值，而是估计：

\[
P(Z_i=z\mid Y_{i1},\ldots,Y_{iR},\Pi_1,\ldots,\Pi_R),
\]

其中 \(\Pi_r\) 是标注者 \(r\) 的 confusion matrix。citeturn8search1 Raykar 将 \(Z_i\) 进一步与 classifier 参数共同估计；Tanno 和 Zhang 把该框架扩展到神经网络和空间标签。citeturn19search3turn19search2turn23view0 因而 reference uncertainty 可以直接用 posterior entropy 表示：

\[
H(Z_i\mid Y)
=
-\sum_z P(Z_i=z\mid Y)\log P(Z_i=z\mid Y).
\]

**多标注者身份层。** 一个最直接的分析结构是交叉随机效应：

\[
y_{ir}
=
\beta_0
+
u_i^{(\text{item})}
+
v_r^{(\text{annotator})}
+
\epsilon_{ir}.
\]

由此可分解：

\[
\operatorname{Var}(y)
=
\sigma^2_{\text{item}}
+
\sigma^2_{\text{annotator}}
+
\sigma^2_{\epsilon}.
\]

Whitehill 与 Welinder 的潜变量方法虽然形式不同，但共同思想都是 item 和 annotator 不应混为一个噪声项。citeturn20search1turn20search2

Python 中可用 mixed-effects 框架表达：

```python
import statsmodels.formula.api as smf

# 交叉随机效应示意：
# worker_id 作为 grouping factor，
# task_id 通过 variance component 加入。
model = smf.mixedlm(
    "outcome ~ condition",
    data=df,
    groups=df["worker_id"],
    vc_formula={"task": "0 + C(task_id)"}
)
fit = model.fit()
print(fit.summary())
```

**等支持量比较。** 当 Manual 与 Semi 的 \(K\) 不同，entropy 和 minority-mode detection 的有限样本偏差也不同。因此一个客观的 support-matched 操作是从较大组抽取与较小组相同的 \(k\)，并在每个 subset 上**重新建立相似关系和重新聚类**，而不是先在全样本上聚类再截断 cluster counts。该过程对应的是有限样本 clustering distribution，而不是固定分区上的 hypergeometric rarefaction。

```python
import numpy as np

def equal_support_recluster(
    annotations,
    target_k,
    cluster_fn,
    statistic_fn,
    repeats=1000,
    seed=1,
):
    rng = np.random.default_rng(seed)
    results = []

    if len(annotations) < target_k:
        return results

    for _ in range(repeats):
        idx = rng.choice(len(annotations), target_k, replace=False)
        subset = [annotations[i] for i in idx]

        # 关键：对 subset 重新计算关系并聚类
        partition = cluster_fn(subset)

        if partition is None:
            results.append({
                "partition_identifiable": False,
                "statistic": np.nan,
            })
        else:
            results.append({
                "partition_identifiable": True,
                "statistic": statistic_fn(partition),
            })
    return results
```

这里自然产生两个不同的结果变量：

\[
H\mid\text{partition identifiable}
\]

和

\[
P(\text{partition identifiable}).
\]

这也是为什么“分区可识别性”不能被 entropy 替代：一个算法在某条件下更频繁无法产生唯一 partition 时，仅比较成功 partition 的 entropy 会条件化掉一部分不确定性。

**模型 proposal 层。** 现有人机文献中最直接的量不是“修改就是好/坏”，而是 suggestion 的条件影响。可以定义：

\[
A_r=P(Y_{final}=P\mid r),
\]

\[
E_r=d(Y_{final},P),
\]

以及如果存在 independent reference \(G\)：

\[
\Delta Q
=
Q(Y_{final},G)-Q(P,G).
\]

但 \(\Delta Q<0\) 的语义只是“相对指定 reference 的指标下降”，并不等于“人为修改不合理”；latent-GT 文献本身就说明 reference 与 latent truth 需要区分。citeturn8search1turn23view0

对于随机提供不同建议的文献型设计，proposal attraction 可以写成：

\[
Y_{ir}
=
\beta_0+\beta_1 P_{ir}
+u_i+v_r+\epsilon_{ir},
\]

其中 \(\beta_1\) 描述人类最终输出随随机 proposal 移动的程度。临床 advice studies 和 LLM suggestion experiment 的核心识别逻辑都与此相近：改变建议本身或建议正确性，再观察人类响应。citeturn14view0turn18view5

**元标签层。** 对 multi-select difficulty/reason tags，pairwise Jaccard 可写成：

\[
J_{rs}
=
\frac{|T_r\cap T_s|}
{|T_r\cup T_s|},
\qquad
D_J=1-J.
\]

每一个 tag 又可以独立作为 Bernoulli variable：

\[
H_j
=
-p_j\log p_j-(1-p_j)\log(1-p_j).
\]

这使“所有人都觉得 geometry 相似，但对 difficulty 原因意见不同”成为一个单独可观察现象，而不需要把元标签混进几何熵。Jiang、Sandri 和 Sap 的研究都显示，对 disagreement 原因、toxicity 或主观属性的判断本身具有观察者依赖。citeturn22search6turn22search10turn18view7

**时间层。** 时间变量至少应区分 active annotation time 与平台 elapsed/lead time，因为后者可能包含离开页面、等待或会话中断。中文依存标注研究将人工标注和审核时间分别报告，而交互视觉标注文献则通常将点击次数/交互数与耗时作为不同 efficiency measures。citeturn12view1turn21search3turn3search0

对于长尾时间，文献式描述更适合：

\[
\{\mathrm{median},\ IQR,\ q_{90},q_{95}\}
\]

或先使用：

\[
T'=\log(1+T)
\]

再进入线性模型，而不是仅使用原始均值。

**文献检索策略。** 本轮检索覆盖了早期 foundational work 到 2025 年的人机标注文献，并以原始出版页面为主。检索概念簇包括：

```text
"annotator disagreement"
"annotation uncertainty"
"human label variation"
"learning from crowds"
"annotator confusion"
"annotator bias"
"inherent disagreement"
"ambiguous segmentation"
"inter-observer segmentation uncertainty"
"multiple annotators segmentation"
"model-assisted annotation"
"AI-assisted annotation"
"LLM-assisted annotation"
"human AI anchoring"
"automation bias AI advice"
"interactive annotation segmentation"
"human machine annotation"
"机器标注 人工校对 认同倾向"
"数据标注 方法 人机独立"
```

来源优先级为正式论文出版页和原始会议/期刊页面，包括 ACL Anthology、NeurIPS Proceedings、CVF Open Access、JMLR、Nature/npj、IEEE 和中文期刊论文；综述和二手资料主要用于发现关键词，不作为主要实证结论的证据。

一个 PRISMA 风格筛选表可以客观记录为：

```csv
record_id,title,authors,year,venue,doi_or_id,
database,search_query,search_date,
task_domain,annotation_type,
human_annotators,model_assistance,
multi_annotator_data,ground_truth_type,
include_title_abstract,include_fulltext,
exclusion_reason,
sample_size_text,
public_data,public_code,
primary_outcome,
disagreement_measure,
annotator_type,
model_intervention_type,
main_finding,
limitations,
notes
```

本轮没有人为填报一个“PRISMA 总检索条数”，因为并未运行一个预注册、去重后固定数据库快照的系统综述流程；虚构检索总量会造成错误的系统综述外观。

对于项目级 annotation table，文献中的多个分析框架可以统一映射到以下长表结构：

```csv
annotation_id,
item_id,
cluster_id,
annotator_id,
annotator_type,
expertise_level,
condition,
protocol_version,
interface_version,
model_assisted,
proposal_id,
proposal_model_version,
proposal_geometry_or_label,
final_geometry_or_label,
topology_signature,
meta_labels,
confidence,
active_time,
lead_time,
revision_count,
reference_id,
reference_version,
reference_type,
reference_label,
quality_metric,
timestamp
```

这里每一列对应的是已存在于文献中的潜在混杂层：item difficulty 来自 Whitehill，annotator identity/expertise 来自 Dawid–Skene、Welinder 与 Geva，protocol/semantic disagreement 来自 Jiang/Sandri，proposal exposure 来自中文人机标注与 LLM-assisted annotation，reference version/type 则对应 latent-ground-truth 文献。citeturn20search1turn20search2turn22search1turn22search6turn12view0turn18view5turn8search1


## 综合证据与开放问题

从跨领域文献看，目前已有较强证据支持的关系与仍未解决的问题可以明确分开。

**已经被多领域重复观察到的现象**包括：标注者能力并不相同；item difficulty 会改变错误概率；主观任务中的分歧并非全部随更多标注者消失；标注者身份、信念和背景可以系统性改变标签；结构化标注中的不确定性可以形成多个完整而空间一致的模式；AI 建议可以提高人类表现，也可以在错误时降低表现；共享 AI suggestion 可以改变最终标签分布，即使这些标签最后经过人工确认。citeturn20search1turn20search25turn18view7turn19search0turn19search1turn13view2turn18view5

**尚未形成统一答案的问题**至少包括以下十二类。

| 开放问题 | 当前文献状态 |
|---|---|
| **何时 disagreement 是误差，何时是多个有效解？** | Dawid–Skene 类模型偏向 latent single truth；Pavlick、Davani、Jiang 等证明某些主观任务不符合该假设。目前没有跨任务通用判据。citeturn8search1turn20search25turn18view6turn22search6 |
| **几何多模态和普通边界噪声的界线在哪里？** | Probabilistic U-Net/SSN 能建模多个假设，但“一个 mode 应至少有多少独立人支持”没有领域统一阈值。citeturn19search0turn19search1 |
| **共享 proposal 后的高一致性中有多少是信息、有多少是锚定？** | 中文句法、临床 AI 和 LLM annotation 均发现 suggestion effects，但视觉几何标注领域还缺少大量直接的 multi-annotator distribution studies。citeturn12view1turn13view2turn18view5 |
| **模型 suggestion 的影响是否随 proposal 错误类型变化？** | 临床文献明确显示正确/错误建议方向相反；结构化几何中 topology error、boundary error、scope error 是否产生同样 reliance pattern 仍未统一。citeturn13view2turn14view0 |
| **专家是否比非专家更能抵抗模型锚定？** | Tschandl 发现经验较少者从好 AI 中收益更多，但 faulty AI 可影响各经验层；Gaube 同样发现专业人士并非免疫。总体证据不是简单的单调 expertise effect。citeturn13view1turn14view1turn14view3 |
| **“模型标注良好”这样的元标签与真实编辑行为是否一致？** | 现有文献大量研究 confidence、acceptance 和 label judgment，但“主观评价 proposal 良好，却仍进行结构/坐标修改”作为单独不确定性类别的系统文献仍有限。Schroeder 的 confidence/adoption 分离是最接近的证据之一。citeturn18view5 |
| **标注者稳定观点能否与低质量错误严格区分？** | Welinder 提供多维 worker model，Davani 保留 individual judgments，Sap 发现价值观相关偏差；但对每位标注者需要多少跨任务重复才能称为稳定 perspective，没有统一标准。citeturn20search2turn18view6turn18view7 |
| **GT 是否应该是单个 reference、专家 consensus 还是一个分布？** | crowd truth inference 和医学多观察者分割给出不同答案；一些模型假定 latent truth，另一些直接建模多个合理 segmentation。citeturn19search3turn23view0turn19search0 |
| **标注者 disagreement 与模型 predictive uncertainty 是否是同一对象？** | Pavlick & Kwiatkowski 明确发现当前 NLI 模型 uncertainty 并不反映人类 disagreement；两者不能默认等价。citeturn20search25 |
| **时间长是否意味着任务困难？** | 标注流程研究使用时间衡量成本，但时间同时受 worker speed、界面、审核步骤和暂停影响；现有文献并不支持把 raw elapsed time 当作纯 item difficulty。citeturn12view1turn3search0 |
| **人工审核是否足以让 AI 生成标签成为独立 gold？** | 2025 年 LLM-assisted annotation 的结果明确表明答案并非必然如此：human-approved labels 仍可保留 suggestion-induced distribution shift。citeturn18view5 |
| **大规模 model-assisted 数据集是否会系统性压缩人类观点空间？** | SAM 等 data engine 已证明 model-assisted labeling 能扩展到巨大规模，但这些工作主要优化数据规模和掩膜质量；它们并未回答独立 Manual 分布与 assisted 分布之间的完整多模态差异。citeturn4search0 |

综合这些文献，可以把现代“标注不确定性”的研究对象概括成一个层次化生成模型：

\[
\boxed{
Y_{irt}
\sim
P\Big(
Y
\mid
X_i,\;
Z_i,\;
A_r,\;
D_i,\;
C_t,\;
P_{it},\;
R_i
\Big)
}
\]

其中：

- \(X_i\)：输入图像、文本或病例本身；
- \(Z_i\)：潜在结构/语义状态，可能是单一真值，也可能本身多模态；
- \(A_r\)：标注者能力、偏好、身份、信念和稳定行为特征；
- \(D_i\)：item difficulty / ambiguity；
- \(C_t\)：协议、界面、上下文和标注阶段；
- \(P_{it}\)：该条件下展示的模型 proposal / AI advice；
- \(R_i\)：reference/GT 及其版本和不确定性。

Dawid–Skene 主要建模 \(Z_i\) 与 \(A_r\)；Whitehill 增加 \(D_i\)；Welinder丰富 \(A_r\)；NLI perspectivism 文献质疑 \(Z_i\) 必须唯一；Probabilistic U-Net 和 SSN 直接将 \(Z_i\) 视为结构化分布；最新 human–AI 文献则说明 \(P_{it}\) 已经成为不能忽略的独立生成因素。citeturn8search1turn20search1turn20search2turn20search25turn19search0turn19search1turn18view5

这也是当前学术文献中与室内几何、Manhattan layout 或其他 Semi-Auto structured annotation 最直接对应的理论位置：**不确定性既可能存在于图像本身，也可能存在于结构表示、标注协议、标注者群体和 reference 中；当模型 proposal 被插入流程后，还会增加一个共同外部信息源，使“最终多人一致程度”不再是纯粹的人类独立观察一致性。**中文人机独立标注研究、临床错误-AI实验和 LLM-assisted annotation 已分别从结构化语言、专家判断和主观众包三个不同领域给出了这一机制的实证证据。citeturn12view0turn12view1turn13view2turn14view0turn18view5