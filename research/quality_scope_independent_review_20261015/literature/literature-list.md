# 质量评分文献：阶段性检索与独立双审清单（2026-10-15）

本轮登记 **58条初步去重候选记录**：24条形成完整摘要审稿输入并由两个相互隔离的同模型子任务按相同3T独立筛选；17条双Yes纳入、1条双No排除、6条摘要证据不足。另有30条元数据/摘要待核验、4条背景/综述候选。因此总计36条待核验；这些不是排除结果。

58条记录不等于58篇相互独立的研究，背景文献版本关系仍待核。

这是一份可续检的阶段清单，**没有满足两轮互补扩展无新增、引用队列清空的停止条件**。公开搜索结果有限，部分原始来源发生403、429、验证码或超时；不能称系统综述或全库穷尽。没有WoS/Scopus付费数据库检索，没有向量RAG，没有人类真值筛选标签。

## 冻结范围与执行

- T1：全景/房间/平面布局几何质量评价，或可明确迁移的空间几何误差测量，或连续客观质量与人类顺序判断的校准。
- T2：实际提供指标定义、归一尺度、容忍距离、结构匹配或顺序校准方法之一；非仅背景提及。
- T3：原始理论、建模、仿真或实证研究；综述单列。三项AND。
- 不限年份、没有篇数上限，中文与英文查询均执行；中文检索未形成完整核验论文，不能声称覆盖中文数据库。
- 使用3T-only降级，knowledge/retrieved明确为空；未装模型。按用户指示不执行SHA，使用冻结输入批次、唯一审稿调用ID及逻辑一致性检查。没有原样运行强制SHA字段的compare_reviews脚本，未声称完整复现原论文流程。

## 最值得迁移的结果

1. **Surface DSC：先定义可接受误差，再报告有多少边界在容忍范围内。** 正式版以专家之间的差异决定各器官容忍距离，按双向表面面积归一。可迁移的是容忍带与长度/面积比例的解释，不能照搬医学毫米阈值、95%验收标准，或假定总体人工误差都是正确。
2. **RoomFormer：区域、角点、角度分别评估，角度建立在参考结构匹配上。** 可借鉴匹配覆盖/漏检的报告；其训练匹配和评价匹配也必须分开。不能将其像素阈值或角度阈值直接接到全景球面。
3. **Boundary IoU：边界敏感性和组合方式值得做对照。** 原文用于Boundary AP/PQ的min(Mask IoU, Boundary IoU)提供非相加组合范例，但不是证明D+IoU必须去重，也不一定提高现有好图分数。
4. **McCullagh及主观尺度研究：将几何连续指标和五档人类顺序标签分开建模。** 有序回归不要求把五档当等距数值；校准只能建立读数含义，不能自动修复几何反例。
5. **GIoU/DIoU：低优先级。** 主要解决框回归在非相交时的优化与收敛，不能直接回答现有中高质量房间布局分数过严的问题。

上述是本项目的迁移判断，不是这些论文已验证WQ或提供了可直接采用的权重。完整正文迁移证据见[阅读笔记](reading-notes.md)。

## 全部双Yes纳入（17条）

| ID | 原题及来源 | 作者 | 年份/载体 | 纳入证据 | 决策 |
|---|---|---|---|---|---|
| arxiv-2404.09993 | [No More Ambiguity in 360° Room Layout via Bi-Layout Estimation](https://arxiv.org/abs/2404.09993) | Yu-Ju Tsai, Jin-Cheng Jhang, Jingjing Zheng et al. | 2024 / CVPR 2024 | 摘要明确提出用于测试时消解GT歧义的新评价指标，并报告3D IoU实验。 | Yes/Yes/Yes；双Yes，无仲裁 |
| arxiv-2211.15658 | [Connecting the Dots: Floorplan Reconstruction Using Two-Level Queries](https://arxiv.org/abs/2211.15658) | Yuanwen Yue, Theodora Kontogianni, Konrad Schindler et al. | 2023 / CVPR 2023 | 摘要明确说明模型使用多边形和角点两级查询，并包含多边形匹配。 | Yes/Yes/Yes；双Yes，无仲裁 |
| arxiv-2104.09403 | [OmniLayout: Room Layout Reconstruction from Indoor Spherical Panoramas](https://arxiv.org/abs/2104.09403) | Shivansh Rao, Vikas Kumar, Daniel Kifer et al. | 2021 / CVPR OmniCV Workshop 2021 | 摘要明确采用新评价指标来量化极区高度畸变区域的误差，并比较球面卷积与常规卷积。 | Yes/Yes/Yes；双Yes，无仲裁 |
| arxiv-2107.09858 | [Weighted Intersection over Union (wIoU) for Evaluating Image Segmentation](https://arxiv.org/abs/2107.09858) | Yeong-Jun Cho | 2024 / Pattern Recognition Letters | 提出由边界距离图构造像素权重的wIoU，并用边界重要性因子调整区域与轮廓的评价。 | Yes/Yes/Yes；双Yes，无仲裁 |
| arxiv-2403.09746 | [Pairwise Comparisons Are All You Need](https://arxiv.org/abs/2403.09746) | Nicolas Chahine, Sira Ferradans, Jean Ponce | 2024 / arXiv预印本（未核实正式发表） | 摘要明确以心理测量缩放把成对比较转为JOD质量分，并设计针对稀疏成对比较的训练。 | Yes/Yes/Yes；双Yes，无仲裁 |
| arxiv-2103.16562 | [Boundary IoU: Improving Object-Centric Image Segmentation Evaluation](https://arxiv.org/abs/2103.16562) | Bowen Cheng, Ross Girshick, Piotr Dollár et al. | 2021 / CVPR 2021 | 摘要提出Boundary IoU，讨论预测与GT对称性、跨尺度响应以及与Mask IoU和其他边界指标的区别。 | Yes/Yes/Yes；双Yes，无仲裁 |
| arxiv-1809.04430 | [Deep learning to achieve clinically applicable segmentation of head and neck anatomy for radiotherapy](https://arxiv.org/abs/1809.04430) | Stanislav Nikolov, Sam Blackwell, Alexei Zverovitch et al. | 2018 / arXiv预印；2021正式版另见版本关系 | 摘要明确提出surface Dice similarity coefficient，以表面轮廓而非体积量化分割偏差。 | Yes/Yes/Yes；双Yes，无仲裁 |
| arxiv-1902.09630 | [Generalized Intersection over Union: A Metric and A Loss for Bounding Box Regression](https://arxiv.org/abs/1902.09630) | Hamid Rezatofighi, Nathan Tsoi, JunYoung Gwak et al. | 2019 / CVPR 2019 | 提出GIoU作为新度量和回归损失，并以标准IoU和GIoU评价实验。 | Yes/Yes/Yes；双Yes，无仲裁 |
| arxiv-1812.07032 | [Boundary loss for highly unbalanced segmentation](https://arxiv.org/abs/1812.07032) | Hoel Kervadec, Jihene Bouchtiba, Christian Desrosiers et al. | 2021 / Medical Image Analysis 67:101851; MIDL 2019 earlier | 明确将轮廓空间的非对称L2距离表达为区域积分，并与区域损失结合。 | Yes/Yes/Yes；双Yes，无仲裁 |
| arxiv-1911.08287 | [Distance-IoU Loss: Faster and Better Learning for Bounding Box Regression](https://arxiv.org/abs/1911.08287) | Zhaohui Zheng, Ping Wang, Wei Liu et al. | 2020 / AAAI 2020 | DIoU加入预测和目标盒的归一距离，CIoU联合重合、中心距离和纵横比。 | Yes/Yes/Yes；双Yes，无仲裁 |
| mccullagh-1980 | [Regression Models for Ordinal Data](https://rss.onlinelibrary.wiley.com/doi/10.1111/j.2517-6161.1980.tb01109.x) | Peter McCullagh | 1980 / JRSS Series B 42(2),109–127 | 摘要给出比例优势、比例风险模型以及极大似然估计方法。 | Yes/Yes/Yes；双Yes，无仲裁 |
| perezortiz-2020 | [From Pairwise Comparisons and Rating to a Unified Quality Scale](https://discovery.ucl.ac.uk/id/eprint/10081517/) | M. Pérez-Ortiz, A. Mikhailiuk, E. Zerman et al. | 2020 / IEEE Transactions on Image Processing 29:1139–1151 | 提出概率框架，把评分与成对比较实验的结果融合到统一心理测量尺度。 | Yes/Yes/Yes；双Yes，无仲裁 |
| arxiv-2108.00201 | [Subjective Image Quality Assessment with Boosted Triplet Comparisons](https://arxiv.org/abs/2108.00201) | Hui Men, Hanhe Lin, Mohsen Jenadeleh et al. | 2021 / arXiv；正式版待核验 | 提出增强三元比较并说明从比较结果进行Thurstone尺度重建，以JND单位表达质量差异。 | Yes/Yes/Yes；双Yes，无仲裁 |
| arxiv-2410.09501 | [Fine-grained subjective visual quality assessment for high-fidelity compressed images](https://arxiv.org/abs/2410.09501) | Michela Testolina, Mohsen Jenadeleh, Shima Mohammadi et al. | 2024 / arXiv；正式版待核验 | 提出质量评估、增强刺激、重建JND尺度和把增强尺度重新映射到原始感知尺度的方法。 | Yes/Yes/Yes；双Yes，无仲裁 |
| yeghiazaryan-2018 | [A family of boundary overlap metrics for the evaluation of medical image segmentation](https://ora.ox.ac.uk/objects/uuid%3A7e78a014-24cd-4195-8383-aa305870c397) | V. Yeghiazaryan, I. Voiculescu | 2018 / Journal of Medical Imaging 5(1):015006 | 提出在区域边界点固定大小邻域内计算平均重合的新指标族，并分析自由参数对误差敏感性和计算时间的影响。 | Yes/Yes/Yes；双Yes，无仲裁 |
| hanhart-2016 | [How to Benchmark Objective Quality Metrics from Paired Comparison Data?](https://infoscience.epfl.ch/bitstreams/3b22051b-b37b-4a5e-b001-928d8ba3d66a/download) | Philippe Hanhart, Lukáš Krasula, Patrick Le Callet et al. | 2016 / QoMEX 2016 | 将分类错误分析用于主观偏好分，并提出基于ROC的客观质量指标评价工具。 | Yes/Yes/Yes；双Yes，无仲裁 |

| cui-2000 | [Comparison of Two Psychophysical Methods for Image Color Quality Measurement: Paired Comparison and Rank Order](https://library.imaging.org/cic/articles/8/1/art00041) | Chengwu Cui | 2000 / IS&T Color and Imaging Conference | 比较排序与成对比较，并研究从排序数据得到尺度值。 | Yes/Yes/Yes；双Yes，无仲裁 |

Surface DSC采用2018预印本冻结摘要进行筛选；2021正式发表题名为Clinically Applicable Segmentation of Head and Neck Anatomy for Radiotherapy: Deep Learning Algorithm Development and Validation Study，doi:10.2196/26151。[正式版](https://pmc.ncbi.nlm.nih.gov/articles/PMC8314151/)正文另经核查，不计成第二篇独立验证。wIoU同样合并2021预印与2024期刊版；Boundary loss保留2019会议及2021期刊版本关系。

## 已双审但仍待正文证据（6条）

下表是冻结摘要未能支持T2，**不是断言全文没有相关指标或结构测量内容**。

| ID | 原题及来源 | 缺口 |
|---|---|---|
| arxiv-2011.11498 | [HoHoNet: 360 Indoor Holistic Understanding with Latent Horizontal Features](https://arxiv.org/abs/2011.11498) | 仅从冻结摘要不能确认本文提供T2要求的方法内容；应检查评价章节或官方评价器，不能以既有印象补足。 |
| arxiv-2407.10439 | [PolyRoom: Room-aware Transformer for Floorplan Reconstruction](https://arxiv.org/abs/2407.10439) | 表示和角度监督具有潜在相关性，但不能仅据摘要认定已提供冻结T2要求的方法；需核验损失或评价部分。 |
| arxiv-2407.10687 | [FRI-Net: Floorplan Reconstruction via Room-wise Implicit Representation](https://arxiv.org/abs/2407.10687) | 正则化研究本身不自动满足T2；需要核验其具体损失或评价定义是否可迁移。 |
| arxiv-1908.06702 | [Floor-SP: Inverse CAD for Floorplans by Sequential Room-wise Shortest Path](https://arxiv.org/abs/1908.06702) | 图结构优化和一致性约束不自动等于T2中的结构匹配；需核实正文中的指标或匹配方法是否满足范围。 |
| arxiv-2211.13287 | [HouseDiffusion: Vector Floorplan Generation via a Diffusion Model with Discrete and Continuous Denoising](https://arxiv.org/abs/2211.13287) | 生成满足约束的布局不自动等于提供本次需要的测量或匹配方法；需查看损失或评价章节。 |

| good-1994 | [Subjective and objective assessment of image quality--a comparison.](https://pubmed.ncbi.nlm.nih.gov/8075187/) | 初审Unknown/Yes；主线程状态复核仍待核。摘要只有强制成对选择与83%偏好，没有可用尺度校准或阈值定义；不能从JND措辞推断完成校准。 |

## 元数据/摘要待核验（30条，未完成独立双审）

这些记录全部保留；网页片段、作者仓储被阻或标题相似不等于资格已通过。后续先补完整摘要与来源，再独立双审。

| ID | 原题/发现名及来源 | 当前缺口 |
|---|---|---|
| use-evaluator | [USE-Evaluator: Performance metrics for medical image segmentation models supervised by uncertain, small or empty reference annotations in neuroimaging](https://pmc.ncbi.nlm.nih.gov/articles/PMC11997713/) | PMC验证码，搜索片段不完整 |
| kinetic-consensus | [Understanding the Impact of Evaluation Metrics in Kinetic Models for Consensus-Based Segmentation](https://pmc.ncbi.nlm.nih.gov/articles/PMC11854527/) | 需核对完整摘要与方法适用性 |
| mrenet | [MreNet: A Vision Transformer Network for Estimating Room Layouts from a Single RGB Panorama](https://www.mdpi.com/2076-3417/12/19/9696) | 摘要未完整获取 |
| lgtnet | [LGT-Net: Indoor Panoramic Room Layout Estimation With Geometry-Aware Transformer Network](https://openaccess.thecvf.com/content/CVPR2022/papers/Jiang_LGT-Net_Indoor_Panoramic_Room_Layout_Estimation_With_Geometry-Aware_Transformer_Network_CVPR_2022_paper.pdf) | 摘要未完整获取 |
| s2fb-iou | [S2FB IoU: Improving Boundary-based Object-Centric Image Segmentation Quality Evaluation](https://doi.org/10.1145/3696409.3700238) | 官方仓储摘要片段；全文方法待核 |
| arxiv-1905.07852 | [Boundary Loss for Remote Sensing Imagery Semantic Segmentation](https://arxiv.org/abs/1905.07852) | 仅搜索摘要片段 |
| headneck-2023 | [Deep learning for automatic head and neck lymph node level delineation provides expert-level accuracy](https://pmc.ncbi.nlm.nih.gov/articles/PMC9978473/) | 需确认是否提供可迁移评价方法，还是只应用已知指标 |
| partial-label-hn | [Deep Learning-Based Segmentation of Head and Neck Organs-at-Risk with Clinical Partially Labeled Data](https://pmc.ncbi.nlm.nih.gov/articles/PMC9689629/) | 需确认是否只应用已知指标 |
| clinical-acceptability | [Validation of clinical acceptability of deep-learning-based automated segmentation of organs-at-risk for head-and-neck radiotherapy treatment planning](https://pmc.ncbi.nlm.nih.gov/articles/PMC10115982/) | 完整摘要及原始人类评价设计待核 |
| benefits-hn | [Benefits of deep learning for delineation of organs at risk in head and neck cancer](https://www.sciencedirect.com/science/article/abs/pii/S0167814019304098) | 完整摘要待核 |
| ssd-giou | [Optimization of the Bounding Box Regression Process of SSD Model](https://doi.org/10.2991/iccia-19.2019.50) | 候选；可能只是GIoU应用，不因题名自动纳入 |
| arxiv-2303.15067 | [Intersection over Union with smoothing for bounding box regression](https://arxiv.org/abs/2303.15067) | 完整摘要待核 |
| bradley-terry-1952 | [Rank Analysis of Incomplete Block Designs: The Method of Paired Comparisons](https://academic.oup.com/biomet/article-abstract/39/3-4/324/326091) | 出版元数据已核；PDF付费，无完整摘要 |
| handley-2004 | [Comparative Analysis of Bradley-Terry and Thurstone-Mosteller Paired Comparison Models for Image Quality Assessment](https://www.researchgate.net/publication/2930678_Comparative_Analysis_of_Bradley-Terry_and_Thurstone-Mosteller_Paired_Comparison_Models_for_Image_Quality_Assessment) | 作者上传页线索；需原始仓储与完整摘要 |
| medical-calibration | [Calibration of medical diagnostic classifier scores to the probability of disease](https://pmc.ncbi.nlm.nih.gov/articles/PMC5548655/) | 方法迁移边界及完整摘要待核；概率不是几何质量 |
| spatial-conjoint-1991 | [Spatial and Conjoint Models Based on Pairwise Comparisons of Dissimilarities and Combined Effects: Complete and Incomplete Designs](https://www.cambridge.org/core/journals/psychometrika/article/abs/spatial-and-conjoint-models-based-on-pairwise-comparisons-of-dissimilarities-and-combined-effects-complete-and-incomplete-designs/09974029F20CD45669E7A88E29510402) | 完整摘要与作者待核 |
| pairwise-rank-2016 | [Pairwise comparison and rank learning for image quality assessment](https://www.sciencedirect.com/science/article/abs/pii/S0141938216300051) | 正文节选与摘要不同，不当完整摘要 |
| jnd-2016 | [A new full-reference image quality metric based on just noticeable difference](https://www.sciencedirect.com/science/article/abs/pii/S0920548916300587) | 完整摘要与迁移边界待核 |
| arxiv-2504.06301 | [Subjective Visual Quality Assessment for High-Fidelity Learning-Based Image Compression](https://arxiv.org/abs/2504.06301) | 完整摘要待核 |
| watershed-cn | [边缘走向自适应的多尺度分水岭分割算法](https://ira.lib.polyu.edu.hk/bitstream/10397/55440/1/边缘走向自适应的多尺度分水岭分割算法.pdf) | 中文检索命中边界容差评价；作者年份及全文摘要待核 |
| trend-odds | [The Trend Odds Model for Ordinal Data](https://pmc.ncbi.nlm.nih.gov/articles/PMC3650098/) | 主线程发现，完整摘要待核 |
| ordinal-dispersion | [Separating location and dispersion in ordinal regression models](https://www.sciencedirect.com/science/article/pii/S245230621630003X) | 主线程发现，完整摘要待核 |
| correlated-ordinal | [Regression Analysis of Correlated Ordinal Data Using Orthogonalized Residuals](https://pmc.ncbi.nlm.nih.gov/articles/PMC4472482/) | 主线程发现，完整摘要待核 |
| raster2seq | [Raster2Seq](https://cornell-vailab.github.io/Raster2Seq/) | 待核正式题名/摘要 |
| floorplan-gan | [Reconstructing Floorplans from Point Clouds Using Generative Adversarial Networks](https://pmc.ncbi.nlm.nih.gov/articles/PMC9967194/) | 待核正式题名/摘要 |
| arxiv-2408.06075 | [Five Pitfalls When Assessing Synthetic Medical Images with Reference Metrics](https://arxiv.org/abs/2408.06075) | 可能为背景评论；类型与完整摘要待核 |
| bt-response-surface | [Response Surface Fitting Using a Generalization of the Bradley-Terry Paired Comparison Model](https://academic.oup.com/jrsssc/article/22/1/59/6882706) | 序比较到属性响应模型；完整摘要待核 |
| bt-spatial | [Bayesian Spatial Bradley–Terry Model: Urban Deprivation Modelling in Tanzania](https://academic.oup.com/jrsssc/article/71/2/288/7033984) | 可能领域不合格，完整摘要待核 |
| bt-statespace | [A state-space perspective on modelling and inference for online skill rating](https://academic.oup.com/jrsssc/article/73/5/1262/7734616) | 可能超出质量校准范围，完整摘要待核 |
| consumer-paired | [Theory of Consumer Behaviour Derived from Repeat Paired Preference Testing](https://academic.oup.com/jrsssa/article/132/2/164/7104542) | 范围边界与完整摘要待核 |

## 背景/综述候选（4条）

| ID | 原题及来源 | 当前定位 |
|---|---|---|
| metrics-reloaded | [Metrics reloaded: recommendations for image analysis validation](https://doi.org/10.1038/s41592-023-02151-z) | 多阶段Delphi形成问题驱动的指标选择框架；作为背景/方法论，不与具体评分原始方法混计。 |
| metrics-pitfalls | [Understanding metric-related pitfalls in image analysis validation](https://pmc.ncbi.nlm.nih.gov/articles/11181963/) | Delphi及社区反馈整理指标陷阱；作为背景单列。 |
| arxiv-2104.05642 | [Common Limitations of Image Processing Metrics: A Picture Story](https://arxiv.org/abs/2104.05642) | 与后续pitfalls关系待核，避免算独立验证证据。 |
| arxiv-2601.14727 | [Recent advances in the Bradley–Terry Model: theory, algorithms, and applications](https://arxiv.org/abs/2601.14727) | 只发现二级概述；完整摘要/类型/版本待核。 |

## 排除及争议

唯一双No（ID：zadrozny-elkan-2002）：Zadrozny与Elkan（2002），[Transforming Classifier Scores into Accurate Multiclass Probability Estimates](https://www.cs.columbia.edu/~djhsu/ML/handouts/zadrozny2002kdd.pdf)。摘要研究一般分类概率，冻结T1要求的人类顺序质量或空间几何对象未得到支持。两位最终均No，但对T2有分歧（No/Yes），保留为标准项争议待人工复核。未触发最终判断分歧式仲裁；排除不等于方法无价值，可另作为一般校准背景，但不能写成本轮合格的质量模型原始研究。

24条中没有二元Yes/No最终分歧，但good-1994存在Unknown与Yes状态分歧，主线程按原始摘要和固定3T复核后保留待核验。此为状态分歧处理扩展，不称原文二元RRA完全复现；保留两位初审，未投票。其余一致也不能证明正确。建议人工抽查Boundary IoU、surface DSC、RoomFormer、McCullagh、Hanhart五条一致纳入，以及唯一一致排除；本轮未冒称人工质控已完成。

## 搜索和续检

共记录本子任务7轮查询与主线程2轮查询；R2—R7工具返回148个结果块（含重复/噪声），R1和主线程原始块数未完整保存，所以不报全轮精确原始召回数。全部执行式、访问失败和轮次新增量见[search-log.json](search-log.json)。已确认RoomFormer回引Floor-SP、后续关系及其他待扩展线索见[citation-edges.json](citation-edges.json)。

尚待：30条摘要/元数据补齐、6条全文补证、4条背景版本核对；MonteFloor/HEAT/FloorNet/Cabral2014、早期顺序尺度与Platt原文等引用未扩展。未访问的引文不算已检索论文，也不冒称没有相关研究。[checkpoint.json](checkpoint.json)保存续检队列。

本轮没有在HOHONET数据上实现或验证新指标，没有确定新参数，也没有把任何论文的阈值直接移植为工作算法。
