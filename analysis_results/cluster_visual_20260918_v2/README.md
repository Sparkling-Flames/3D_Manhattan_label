# 39图分簇对照与图像复核｜2026-09-18

**接收后勘误：**本文为前序39图研究，数值结果未改。最新全量研究及再次看图结果见[当前复核](../full_corpus_research_received_20260918/仓库接收与视觉复核.md)。下文“过拆”仅针对结构表达分组，不表示几何差异不应研究；局部事件方案尚未胜出。X7-19的3/1/1只描述局部存在性，W015的对应问题仍在；后续环序cut8可得到该分组，不能用本轮cut12全并否定整个环序方法。B6-22是Semi条件，不能把4/5/8个数值簇称为几种空间。

结论：研究对象保持真实布局标注分布，范围、局部表达和定位是不同视图；错误、OOS、单人和不可计算记录不因不合规范而删除。8种全局方案均未解决全部旧评论，图像锚定的局部事件签名是已运行的下一步原型，但尚无独立语义准确率验证。

## 实际完成

- 原始2048×1024全景39张全部取回并核验SHA256；逐图查看原图及旧簇代表页。全部843份面板已生成/可查看，不等于全部逐点审完。另在19张图记录29项指定作答对检查。
- 冻结主口径781份、45个图片×条件单元上比较8方案；45个旧矩阵最大误差0，45个旧分区一致。全部817份可归一化作答另行重算8方案；26份不可归一化保持记录。
- 主口径8170对特征、6248行方法×成员、6248次逐人留一重分簇、1125个参数敏感性结果。它们共享人员/图片，不是新增独立样本。
- 球面插值/立体角对照共同覆盖766份主口径；其余15份明确记该指标不可计算。全843份有790份符合投影指标条件。
- 5张开发图、7个条件单元、89份作答完成局部事件签名原型。ROI扩缩8px没有改变这89份签名，但不是泛化证据。
- 完整数值代码在code/。GitHub Actions独立执行35317380911成功并提交全部行级CSV/JSON；取回工件后，17份共同CSV与本机输出以1e-10容差逐项对照全部一致。执行成功不代表语义验收。

## 8方案：同781份作答，参数均为探索设置

|方案|核心|显示组数|单人显示组|
|---|---|---:|---:|
|A0|点数门＋墙带完整链接0.10|249|143|
|A1|取消点数门，墙带0.10|203|91|
|A2|墙带＋64列局部边界差20px|279|157|
|A3|环序部分匹配，cap20，归一化后cut12px|262|121|
|A4|标注角距派生局部尺度的环序匹配|262|122|
|A5|HDBSCAN minsize2/minsamples2，未分配保留|394*|210*|
|A6|局部尺度亲和＋eigengap1—6＋KMeans|112|0|
|A7|墙带＋软角点密度Jaccard|306|174|

* A5为184个密度簇加210个未分配显示位置；未分配不是已识别的语义模式，也未删除。不能按簇少或曲线平排序方法。

全部817可归一化口径的显示组数依次268、221、299、282、282、414、118、329。Manual、Semi和OOS分别保留。

## 关键结果

**X7-19（Manual5人）：同样3簇可以分错成员。** 看图后的局部表达判读：W011/W015/W033均表达隔断前缘及后连接，W034省略，W037主要后连接。A2也是3簇，却把W015与另两份完整表达拆开，合并省略和部分表达。A1/A3/A4/A6及球面两方案会全部合并。不能只检查K。

**rPc-20：同样六对角点不等于同表达。** W034/W037均加浴室框，但左开口额外点与右走廊角取舍不同。A0/A1/A5/A6仍合并，A2/A3/A4/A7及球面两方案分开。

**rPc-15：定位过拆与细节被吞并。** 多方案拆开W002/W011的相同主要角点机会，而谱图/球面两方案把W037的增框也并掉。局部事件签名为22份无框/1份有框，仍保留组内坐标。

**q9-32与wc-60：局部距离不是万能修复。** q9-32/W014明显偏移，A0/A1仍与W027同簇；其余候选分开。wc-60/W001则连A2局部边界及立体角仍与W027合并。

**全景插值是额外的表示问题。** 旧d_mask直接在全景像素中线性插值；水平3D边界应采用相应球面投影曲线。实现与仓库pano_connect_points的独立3D线/射线算式对照最大差3.07e-12像素。在共同766份、无点数门、同cut0.10下，线性192组/82单人，球面像素155/55，立体角126/39。B6-22同24人均8点时8→5→4；不是确认4或5种语义范围，换度量后的0.10不自动具有相同语义容忍度。X7-19/uNb-45/wc-30又可能被整体面积合并。

**原始上下x恢复影响实际分区。** 8057可比对中26对跨0.10；相同成员下，旧点数门2/45单元分区变化，无门5/45。7y3-08即使0对跨阈值、K不变，成员仍改变；另有3点合成例验证层次合并顺序机制。平均距离小、K不变、阈值图不变均不足以单独保证分区一致。

**GOSPA限制再次实测。** cap20的纯整体x位移19px仍4匹配，定位平方1444；21px变0匹配，未匹配平方1600。未匹配是给定代价规则下的结果，不等于结构增删；环序约束不能解决心理/语义原因识别。本轮归一化环序扩展不宣称继承原GOSPA全部理论。

## 5图局部事件原型

|图/条件|记录的联合局部表达|结果|
|---|---|---|
|B6-11 Manual24|右端近/远＋柱体额外对|15/8/1；仅右端选择为16/8|
|X7-19 Manual5|隔断前缘＋后连接|完整3、省略1、部分1|
|X7-19 Semi4|同上|完整3、省略1|
|rPc-15 Manual23|柜框对|无22、有1|
|rPc-20 Manual24|浴室框＋左开口＋右走廊角|22/1/1|
|wc-67 Manual5|浴室框＋右主角|基础3、缺主角1、增框1|
|wc-67 Semi4|同上|同局部签名4|

ROIs与高度带是在看过图和评论后确定，代码不读取workerID、旧簇或质量分数，但规则开发不是盲法。相同签名只表示列出的局部事件相同，不能认定完整布局相同。未知、不匹配及连续变化保留。当前没有实测新人员组合对收敛的预测增益。

## 文件与复算

- `code/clustering_study.py`：8方案、成对特征、留一分区、阈值敏感性及原始x审计。
- `code/spherical_followup.py`：球面与立体角，明确不可计算原因。
- `code/validation_and_sensitivity.py`：全部人员、40个DP穷举对照、投影与接缝测试及反例。
- `code/local_event_prototype.py`：5图事件原型和29项关系检查。
- `code/legacy_reproduction.py`：此前程序所需函数的原样子集。
- `results/memberships.csv`、`pairwise_features.csv`、`all_normalizable_memberships.csv`、`spherical_memberships.csv`、`local_event_records.csv`：关键行级结果。
- `VISUAL_AUDIT_39.md`：每图本轮视觉判断；用户原话另在`results/source_review_comments.json`，没有覆盖。
- `results/source_and_code_manifest.json`、`original_image_manifest.json`、`validation_tests.json`、`CLOUD_REPRODUCED.json`：版本和执行证据。

先获取固定main提交的`analysis_results/pro_cluster_review_20260918/data.json`放到本目录`inputs/key39/`；原图按cases中的精确路径取回放`inputs/pixels/`并保存散列清单。完整自动获取和执行见仓库`.github/workflows/clustering-visual-reproduce-20260918.yml`。Python3.13；numpy2.3.5/pandas2.2.3/scipy1.17.0/scikit-learn1.8.0/numba0.65.1。原始data blob固定`5e3a08f091a4611505f9eeb90680bf5edec87c49`，源提交`d3477e700082c0a8482f1ffabd9dcc5649c9754d`。

交付附件另含完整中文报告、可离线查看全部843作答的39图交互图册和可视化脚本。数值程序不依赖渲染器；一次旧静态渲染器Git写入被工具拦截，该文件未冒称在远端。原图、生成截图、ZIP不重复提交研究目录；main、用户决定和待应用修正未更改。

## 对导师材料的使用

最新`与导师交流(6).txt`支持独立真人采集与离线组合。其书面原话：“2:是的，所谓ABCD，是人员类型（认真、不认真之类的），每个人员类型选一个人ABCD，或者不同类型人数比例不同比如AABC，这些我觉得没必要重复实现，我们以人头为单位采集数据就行”。稳定多簇、最终人员分类与阈值仍未冻结；不确定语音回忆不升级为书面要求；末行原有1:前缀与内容角色存在歧义，未擅自改写。用户只接受某种标法的规范偏好，不是删除其他行为数据的授权。原4点idea及点数补充已在source_research_clarification.json逐字保留。

## 原始文献

1. Cheng Sun, Chi-Wei Hsiao, Min Sun, Hwann-Tzong Chen (2019). HorizonNet: Learning Room Layout With 1D Representation and Pano Stretch Data Augmentation. CVPR,1047–1056. https://openaccess.thecvf.com/content_CVPR_2019/papers/Sun_HorizonNet_Learning_Room_Layout_With_1D_Representation_and_Pano_Stretch_CVPR_2019_paper.pdf
2. Lihi Zelnik-Manor, Pietro Perona (NIPS2004,论文集2005). Self-Tuning Spectral Clustering. Advances in Neural Information Processing Systems17,1601–1608. https://proceedings.neurips.cc/paper_files/paper/2004/file/40173ea48d9567f1f393b20c855bb40b-Paper.pdf （本轮只借鉴局部亲和，不是完整复刻。）
3. Ricardo J.G.B.Campello, Davoud Moulavi, Arthur Zimek, Jörg Sander (2015). Hierarchical Density Estimates for Data Clustering, Visualization, and Outlier Detection. ACM TKDD10(1),Article5:1–5:51. DOI10.1145/2733381. 作者机构条目https://researchonline.jcu.edu.au/47065/；其PDF受限，未虚构开放全文。
4. Abu Sajana Rahmathullah, Ángel F. García-Fernández, Lennart Svensson (2017). Generalized Optimal Sub-pattern Assignment Metric. FUSION,1–8. DOI10.23919/ICIF.2017.8009645. https://arxiv.org/pdf/1601.05585
5. Yu-Ju Tsai, Jin-Cheng Jhang, Jingjing Zheng, Wei Wang, Albert Y.C.Chen, Min Sun, Cheng-Hao Kuo, Ming-Hsuan Yang (2024). No More Ambiguity in 360° Room Layout via Bi-Layout Estimation. CVPR,28056–28065. https://openaccess.thecvf.com/content/CVPR2024/papers/Tsai_No_More_Ambiguity_in_360deg_Room_Layout_via_Bi-Layout_Estimation_CVPR_2024_paper.pdf
