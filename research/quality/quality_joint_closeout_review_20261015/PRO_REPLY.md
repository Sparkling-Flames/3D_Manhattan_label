**本轮已把有固定／条件参考的完整评分从718份扩展到1145份，并完成962份普通作答、人员组合及220个冻结融合终点的指标敏感性分析。**

最终建议是：**“接近指定参考”保留3D IoU为主指标；“几何质量”保留WQ-LS08及分项，并强制报告两者对研究结论的影响。WQ参数不再追加调整，也不把任何一个总分宣布为已经验证的人类质量真值。**

这是本轮实算后的采用建议。上一条的解析推断没有直接作为依据，其中部分已做成实验，支持和不支持当前模型的结果均保留。

quality_model_closeout_verified_20261014.zip[下载完整研究包：代码、输入、分项、图表、报告及后续核验清单，约99 MB](sandbox:/mnt/data/quality_model_closeout_verified_20261014.zip)

REPORT_ZH.md[中文报告](sandbox:/mnt/data/quality_closeout_verified_20261014/REPORT_ZH.md) · REPORT_ZH.html[HTML报告](sandbox:/mnt/data/quality_closeout_verified_20261014/REPORT_ZH.html) · METHODS_AND_RESULTS_ZH.md[论文方法与结果草稿](sandbox:/mnt/data/quality_closeout_verified_20261014/METHODS_AND_RESULTS_ZH.md) · quality_model_closeout_verified_20261014.verification.json[最终解压与复现回执](sandbox:/mnt/data/quality_model_closeout_verified_20261014.verification.json)

## 一、本轮实际完成了什么

开始和结束时读取的main均为 `134e7c775b9ea25a076851c0605571ba0ea0ac31`，没有更新到不同研究基线，也没有向仓库写入修改。

恢复的3152份用途账本包括2344份manual、574份semi和234份oos采集条件。完整数值覆盖如下：

| 数值用途层 | 完整评分数 | 保留的限制 |
|---|---:|---|
| 普通manual当前参考绑定 | **962** | 条件参考不自动升级为逐图认证正确 |
| 非trap且改过坐标的semi第二层 | 39 | 与manual分开 |
| 已审严重例外 | 9 | 不恢复人员资格 |
| 门洞条件记录 | 125 | 其中10份明确保留范围混杂诊断 |
| 历史旁证 | 10 | 不混入普通主分析 |
| **合计** | **1145** | 不是1145份同等资格训练样本 |

另外完成了**217份仅底面评分**。普通1304份候选闭合为：

\[
962\text{完整}+217\text{底面}+121\text{GT版本目标未定}+4\text{几何／路由不可用}.
\]

121份目标未定记录仍保留各参考版本的数值，但没有挑最高分进入普通主对照。全部结果共有1610个“作答—参考—评分口径”组合，其中1393个完整、217个仅底面；**多参考组合没有计作新增独立作答。**

计算方式也分开记录了：974个配对复用可靠分项重评分，636个缺失配对从点测量，另外21个存储配对做了几何重建抽查。既有151份控制重新测量，先前718条WQ数值的回归最大差小于 \(3.13\times10^{-13}\)。

ALL_3152_LEDGER.csv[3152份来源、用途与数值账本](sandbox:/mnt/data/quality_closeout_verified_20261014/results/ALL_3152_LEDGER.csv) · ALL_REFERENCE_PAIRS.csv[全部同参考配对结果](sandbox:/mnt/data/quality_closeout_verified_20261014/results/ALL_REFERENCE_PAIRS.csv)

有一个执行边界不能省略：**本轮没有运行仓库原生 `load_current_bundle()`，也没有重新验证全部评论交叉表。** 完整坐标来自已挂载的有效快照，结合最新规则和回执恢复用途；907个共享对象与较新READY一致，810条共享用途记录的14项字段差异为0。全量坐标与数值链已独立检查，但不能冒充原生loader全链验收。SOURCE_PROVENANCE.md[来源与恢复说明](sandbox:/mnt/data/quality_closeout_verified_20261014/SOURCE_PROVENANCE.md)

## 二、质量模型的收尾定义

保留的工作式为：

\[
B=\frac{S_b^2}{32},\qquad
L_D=\frac{1.5D^2}{D^2+37.5},\qquad
H=\left(\frac{H_m}{0.8}\right)^2+
  \left(\frac{H_c}{0.25}\right)^2,
\]

\[
\boxed{Q_{\mathrm{WQ}}=\frac{100I}{1+I(B+L_D+H)}}.
\]

\(I\) 测底面范围重合，\(S_b\) 测底边位置，\(D\) 测自身方向规整，\(H_m\) 测整体均高偏差，\(H_c\) 测去除整体高低差后的局部高度差异。角度量使用度，输入仍是既定平均x后的点对和环序。

参数维持：底边尺度 \(\sqrt{32}=5.656854^\circ\)，方向尺度 \(\sqrt{37.5}=6.123724^\circ\)，方向饱和系数1.5，整体高度尺度0.8、局部高度尺度0.25。缺顶界时完整Q为空，不借另一参考的顶部；原始上下x差仍不入分。

**WQ应被定义为“带规整性先验的连续几何质量指数”，不是纯参考距离。** 它增加了IoU没有充分表达的方向和局部高度信息，但这些信息的权重仍是研究设计取舍，不能因计算可复现就称为人类效度已验证。

对上一轮“去掉重复处罚”的解释，也作了收窄。旧式与新式在倒数尺度上的交互分解成立，但换到负对数尺度，旧式同样可以写成相加。因此，**代数分解不能证明旧式计算错误或必然重复处罚**。本轮保留WQ，是保留一个可解释、已有工作基础的连续刻度，不是证明它在数学上唯一正确。

WQ_LS08_UNCHANGED.json[冻结参数](sandbox:/mnt/data/quality_closeout_verified_20261014/configs/WQ_LS08_UNCHANGED.json) · ADOPTION_RECOMMENDATION.json[采用与适用条件配置](sandbox:/mnt/data/quality_closeout_verified_20261014/configs/ADOPTION_RECOMMENDATION.json)

## 三、两种指标确实会改变人员和组合判断

### 同一作答参考下，并非只有绝对分数不同

962份普通完整作答覆盖115图、21建筑、24人和116个图片—参考单元。

| 对照结果 | WQ与3D IoU | WQ与当前hill08 |
|---|---:|---:|
| 同图同参考、不同人员的非重复比较 | 6829对 | 6829对 |
| 次序相反 | **1388对，20.33%** | **75对，1.10%** |
| 人员单元中心化后的排名相关 | 0.801 | 0.998 |
| 探索性三分位分组变化 | 7/24人 | 0/24人 |

WQ与IoU的总体Spearman相关为0.825，但较高相关性并没有消除同图排序分歧。按建筑等权的次序差异率为22.54%，建筑重采样的描述区间为14.98%—30.68%。这些比较共享图片和人员，**不是6829次独立试验，也不是1388次人类质量判断错误。**

人员结果先在同图片、同参考、同采集条件内中心化，再等单元汇总，避免直接拿不同任务上的均分排序。不过，24人共同覆盖只有4个参考单元，仍不足以认证总体能力排行榜。

这里的“三分位”只是展示敏感性的等人数诊断，**没有把人员正式分成三类，更没有修改既有人员资格**。不依赖这种人为分组的结果也显示差异：WQ与IoU的人员相对名次最大相差12位，8人的单元中心化均值符号不同。

这意味着，主要需要公开的是 **WQ与IoU的测量对象差异**；单纯从当前hill08换成WQ，对本批人员相对排序的影响反而很小。

:chatgpt-content-reference{index="19"}[人员逐项敏感性结果](sandbox:/mnt/data/quality_closeout_verified_20261014/results/WORKER_METRIC_SENSITIVITY.csv)

### 人员组合变化更明显，但没有证据证明WQ组合更好

组合诊断仅用目标建筑以外的历史记录估计人员表现，再从**实际标过目标图的人员**中选择固定人数。没有读目标图分数来选人，也没有重新融合。

48个目标单元、12建筑满足条件。按WQ或IoU历史表现选人时：

- 选1人：12/48个选择不同；
- 选3人：**42/48个集合不同**；
- 选5人：36/48个集合不同。

但“选择不同”不等于“选择更好”。三人方案中，WQ选择相对IoU选择的目标个人平均表现没有稳定优势。五人方案中，WQ选择的建筑等权IoU反而低约**1.03个百分点**，描述重采样区间为−1.80至−0.52。

这个负结果保留在交付中。它只适用于当前有限历史池，不是未来随机路由的因果结论；评价的是所选**个人的平均表现，不是他们的融合结果**。

:chatgpt-content-reference{index="20"}[组合选择规则、逐例集合与结果](sandbox:/mnt/data/quality_closeout_verified_20261014/results/TEAM_SELECTION_DIAGNOSTIC.json)

## 四、已有融合结论也存在指标依赖

220个冻结融合终点已完成对照：**144个完整数值、1个仅底面、75个继续暂缓**。没有改成员、几何、参考、自动／辅助来源或融合算法。

其中60个终点从冻结点重建；其余84个完整及1个底面终点复用最新机器分项的明确字段投影后重评分。144个完整数值仍不等于144个正式合资格融合终点：51个有成员或上下文限制，18个包含原留出成员。

26组同图同参考自动／辅助比较中，21组数值相同，只有5组改变；其中一组的改善方向随指标改变：

\[
\text{jtcxE69GiFV-28：辅助−自动}
\]

\[
\Delta Q_{\mathrm{WQ}}=+9.49,\qquad
\Delta \mathrm{IoU}_{3D}=-1.04\text{个百分点}.
\]

因此，**“辅助后的几何质量指数更高”不能直接写成“辅助后更接近参考”。**

另外，92个终点能够对全部成员建立同参考完整比较，其中15个“融合分数减成员平均分”的正负方向依赖所用指标。它们不是新增融合实验，但足以否定“指标选择不会影响现有融合解释”的笼统说法。

当前仍没有该gap7.5方法的真实逐人数进入顺序及对应几何轨迹。本轮没有用终点插值制造人数曲线，也没有宣布“人数增加后是否收敛”的结论已经稳健。

FUSION_220_SCORES.csv[220个融合终点对照及限制](sandbox:/mnt/data/quality_closeout_verified_20261014/results/FUSION_220_SCORES.csv) · FUSION_220_RESULTS.json[完整融合敏感性分析](sandbox:/mnt/data/quality_closeout_verified_20261014/results/FUSION_220_RESULTS.json)

## 五、上一条的机制推断，这次哪些得到实测支持

### 1. 顶点均高3D IoU存在表示敏感性，已经实际测出

官方HoHoNet评价器采用顶点平均墙高构造棱柱，并同时报告其他深度指标。因此，这里的3D IoU不是任意局部非平顶布局的精确实体体积IoU。本轮使用同几何的冻结兼容实现，并显式处理像素中心约定，没有把缺值照官方异常分支补零。

实测合成例中，参考高度2.5，作答四角高度为 \([2,2,2,4]\)，顶点均高也为2.5，原棱柱IoU为1。只在一条边加入线性共线点，声明的底面、墙带与顶边几何不变，IoU却随点数改变。

真实诊断进一步覆盖962份作答：在固定第一条边加入3个共线点，**149份IoU变化至少1个百分点，2份至少5个百分点**，变化范围约−6.05至＋4.02个百分点。

完整WQ只对确定性抽样的49份重新测量，变化小于 \(2\times10^{-13}\)；其余913份没有被填成“已重算且零变化”。

这是一个明确的**实现层测量差异**，说明WQ的周长／边界表达具有额外价值；它不证明WQ的分数已符合人类判断，也不允许给真实作答加点“提高质量”。

:chatgpt-content-reference{index="23"}[共线细分与高度估计器逐例结果](sandbox:/mnt/data/quality_closeout_verified_20261014/results/HEIGHT_ESTIMATOR_AND_SUBDIVISION_962.csv)

### 2. D的语义盲区仍在，但不能把消融反转冒充完整Q反转

151份既有控制全部重新测量。

狭长矩形控制中，bottom-y RMS从8增至16像素，IoU从0.8031降至0.6232，D反而从18.82°降至11.44°。不过，当前完整Q为32.13→21.64，WQ为36.44→28.70，**两者完整分都下降**。

等边菱形45°→30°也保留D下降的盲区，但当前完整Q和WQ均下降。不能继续把旧“仅IoU＋D”消融中的反转当成当前完整Q已经反转，也不能把前轮已完成的尾项修复再次记成本轮收益。

相反的负例也保留了：正交窄分支遗漏时，D为0，IoU约95.24%，WQ仍约94.45。**高Q不能证明必要局部结构完整。**

### 3. J04支持局部投影放大，不支持指定一个正确分数

实际查看了原图叠加和同尺度三维。第一对bottom-y偏差约21.13像素，占四个bottom-y平方差的97.33%。仅在诊断副本恢复这一处，D从19.42°降至2.21°，IoU从0.6802升至0.9284，WQ从33.53升至78.13。

这支持局部底点经投影影响整体形状的机制。没有写回作答，也没有把修后副本纳入拟合。

J01绝对三十多分是否合适，仍没有独立量表依据；T20/P04实际高度扣分约5.06／4.45，与最新“B应略多扣”的倾向仍有小幅不一致。**这些不一致公开保留，没有为了逐题满意再次修改全域参数。**最新人工意见本来就是定性开发反馈，不要求逐例目标分或精确平局。

## 六、外部研究给出的支持与反证

**RoomFormer与当前问题最接近。** 它的SceneCAD非学习流程获得86.0的room IoU，但corner F1为72.7、angle F1为49.6；作者明确指出粗轮廓重合尚可，精确房间几何仍不足。反方向上，tight-room版本的angle F1从81.2升至84.2，而room F1从97.3降至96.7，说明角度改善也可能与其他几何目标冲突。其官方代码比较匹配GT角点的角度，而不是统一要求所有角为90°。[arXiv](https://arxiv.org/pdf/2211.15658) 

完整引用：Yuanwen Yue, Theodora Kontogianni, Konrad Schindler, Francis Engelmann（2023），*Connecting the Dots: Floorplan Reconstruction Using Two-Level Queries*，CVPR，845–854。[作者PDF](https://arxiv.org/pdf/2211.15658)。

**Bi-Layout说明目标范围歧义可能先于几何误差。** enclosed与extended的区别直接对应本项目Q01／Q02需要保留的范围限制；但其双预测匹配评价不能移植成“选择最高分GT”。[arXiv](https://arxiv.org/pdf/2404.09993)

完整引用：Yu-Ju Tsai, Jin-Cheng Jhang, Jingjing Zheng, Wei Wang, Albert Y. C. Chen, Min Sun, Cheng-Hao Kuo, Ming-Hsuan Yang（2024），*No More Ambiguity in 360° Room Layout via Bi-Layout Estimation*，CVPR，28056–28065。[作者PDF](https://arxiv.org/pdf/2404.09993)。

**Boundary IoU提供面积与边界敏感度不同的具体例子，但不是三维布局效度证据。** 它可支持边界量单独报告的动机，不能为本项目墙高、方向或结构遗漏权重背书。[arXiv](https://arxiv.org/pdf/2103.16562)

完整引用：Bowen Cheng, Ross Girshick, Piotr Dollár, Alexander C. Berg, Alexander Kirillov（2021），*Boundary IoU: Improving Object-Centric Image Segmentation Evaluation*，CVPR，15334–15342。[作者PDF](https://arxiv.org/pdf/2103.16562)。

HoHoNet的原始出处为Cheng Sun, Min Sun, Hwann-Tzong Chen（2021），*HoHoNet: 360 Indoor Holistic Understanding With Latent Horizontal Features*，CVPR，2573–2582。[作者PDF](https://arxiv.org/pdf/2011.11498)。

四篇正文和相关官方实现已核查；RoomFormer作者项目页的结果图实际查看过。其他PDF截图服务失败，相关图例论断限于原文、表格解析和图注，没有声称看过未返回的图像像素。完整核验边界见RELATED_WORK_ZH.md[文献与案例说明](sandbox:/mnt/data/quality_closeout_verified_20261014/references/RELATED_WORK_ZH.md)。

## 七、最终采用与复现状态

**现在可以冻结的，是模型定义、固定参数、双指标分工和逐例可复现结果，不是通用等级切点。**

对论文的实际用法：讨论“融合是否接近指定参考”，以同参考3D IoU为主，同时报告WQ敏感性；讨论方向、局部高度和几何规整，则使用WQ及分项，但不能据此忽略参考重合或目标范围。人员与组合结论若随指标改变，应保留这种依赖，不能只挑支持叙事的一项。

本轮没有重新调参，继承普通阶段冻结参数和门洞无追加调整结论。门洞125份条件数值、92份暂缓均保留；Q01图8份和Q02两份明确不作为同目标质量验证。台阶整图剔除后的959份保守对照也已提供。OOS没有参与调参。

**最终ZIP已实际解压，322个载荷文件哈希全部通过；从解压副本完整重跑后，44项测试通过。3152份账本、1610个参考配对和220个融合终点的CSV逐字节一致，数值最大差为0。**这证明执行可复现，不等于独立人类效度已验证。

```bash
python verify_delivery.py
python -m pip install -r requirements.txt
python reproduce.py --output ../quality_closeout_new_replay --figures
python score_one.py --record R03274 --rebuild
```

后续核验队列已经固定为**25卡、29份作答、21图**，覆盖普通分数区间、指标分歧、严重例外、门洞、仅底面及参考限制，不只选有利案例。CANDIDATE_QUEUE.json[候选与选择理由](sandbox:/mnt/data/quality_closeout_verified_20261014/review/CANDIDATE_QUEUE.json) · CANDIDATE_BINDINGS.csv[对象与参考绑定](sandbox:/mnt/data/quality_closeout_verified_20261014/review/CANDIDATE_BINDINGS.csv)。其中5卡已有原图，20卡保留缺图状态；包内脚本可按image_id从原图目录或ZIP补齐，不改变候选和参考，也不需要重做已有八卡反馈。