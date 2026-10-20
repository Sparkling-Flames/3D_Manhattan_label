# 用真实融合替换变化学习人员类别：历史训练与审计

本目录属于 20261020 新一轮研究。类别直接学习“相同图片、参考、总人数、共同背景下，换入不同人员后，实际融合输出变化多大”。上一轮历史共簇、原答几何角色只作背景，本轮这些反向类别没有以原答几何聚类冒充可互换性学习。**这里的数字是历史训练、内层选择和冻结后历史背景压力测试；目标楼多人类别块结果由主研究另行报告。**

## 1. 数据和边界

最新文档 main 为 `445686f8f3cf6039c4ce1f60016cad1d26829044`，科学融合源仍为 `82c6164b0d4630de5316199c92aa405930973168`。沿用 `analysis/composition/SPLIT.json` 的 10 栋 history，未读取 discovery/validation 输出拟合或选择本目录类别。所有 Q、T、结构、Semi、scope 解释变量来自冻结的 `analysis/forward/results/features_train.csv.gz`，其 train key 为 `history_d199d7b13dccfe7e`。

旧 A 的实际固定背景面板有 122,082 个 history 替换事件，79 图、10 楼、606 个图片×人数×背景，人数为 8/12/16/24。新增面板只按元数据、人员 ID 和种子选择背景，在全部 81 个普通 Manual history 池计算 31,539 个不同真实团队；1,576 个背景锚点产生 359,916 个不同实际人员对替换。新增人数为 3/4/5/6/7/9/11/13/15/17/19/21/23/25/29/31。**每个选中背景内剩余人员对是穷举，背景、团队及所有可能人数并未穷举。** 旧、新两个学习面板的已选人数互不重合。

`extract_native_history.py` 逐对核验共同核心、真实成员集合、同人数及 turnover=1，复用冻结几何比较函数，不重新融合或评分。原始失败、不可评分、连续距离缺失均保留。`NATIVE_PAIR_EXTRACTION_RECEIPT.json` 给出全部 81 池原生输出及抽取结果 SHA。新面板的完整事件流约 36 万行，不应随精简成果包重复打包；代码、精确 anchors、输入索引与 SHA 足以重建。

## 2. 实际搜索了什么

旧版四个域、四个风险表达、四个算法，在允许范围内尝试每个整数 K，共 768 个候选。合并新面板后有 ordinary、hard、small_n、large_n、ordinary_new、hard_new、hard_v1 七域，共 1,040 个候选，752 个通过全历史拟合容量和关系机会门槛。旧版、合并版分别保留，没有覆盖旧标签。

风险表达是原主阈值失败率、去 Q 几何阈值失败率、底面与均高棱柱连续变化损失、相对于同背景整体风险的居中变化。连续损失在几何不完整/不可比较时给予预先声明的单位损失；这没有把原始缺失 IoU 编造为 0，也没有给原始距离填 1。均高棱柱只是代理，不是对任意非平顶室内实体的精确完整三维 IoU。

算法包括完整连接、谱嵌入后 k-means、直接降低类内风险的容量约束分区，以及额外惩罚类内宽阈值坏尾的分区。后两者是本轮明确写出的启发式目标，不声称已找到全局最优人员分区。每类至少 4 人；K 在 2 到 `floor(合格人数/4)` 间逐整数尝试。完整连接产生过小类、类内已知关系比例不足、删楼后人数不足均保留为失败候选，未用单人类抬高成功率。

人员资格为至少 3 楼、4 图；人员对资格为至少 2 楼、3 图。关系均值先平均同图同人数的背景，再平均图内人数、楼内图片和各楼；机会分母单列。对稀疏关系向训练域均值收缩 1 个等效楼，未知边估计权重为 0，未当作相似边。合并版要求每一类内部至少 75% 人员对有支持。ordinary 有 55 名合格人员、1,485 对全部有支持；hard 的 53 人只有约 66.7% 跨人员对受支持，来源关联尤其强。hard_v1 有全历史分区，却无法形成合格的内层留出共同背景类内/类间比较，因此未进入目标块短单。

## 3. 选择规则与可用候选

固定五折、每折留出两栋 history 楼。每次仅用其余八楼重新建立资格、风险图、收缩先验和标签，再在留出楼比较同一真实背景的同类与跨类替换。背景必须同时具备两种关系才纳入该对照；按背景→图内人数→图片→建筑逐层平均，最终建筑等权。完整成分和失败均保留，不只给一个排名分数。

旧版冻结 5 个候选，合并版冻结 10 个候选，见 `LEGACY_SCREEN_SHORTLIST.json`、`MIXED_SCREEN_SHORTLIST.json`。合并版选择兼顾粗类、细类、容量、无 Q 路径、来源内部、难度和人数条件；入选者均覆盖该域所有可用历史楼。没有提升那些因失去若干留出楼而表面分数更高的候选。最小类容量仍必须在目标图片中重新检查，55 人全局有类不代表任意图片都有人可换。

合并 ordinary 去 Q 七类的内层主稳定率为类内 67.35%、跨类 59.68%；ordinary_new 去 Q 两类为 65.92%/60.95%，35 人按 21/14 分类；hard_new 去 Q 七类为 45.49%/37.55%，同类仍有 41.08% 超过宽阈值。这些是待检验候选，不能把“有区分度”写成“同类通常可完全互换”。新增的小人数点使整体稳定率低于旧面板，并不等同于方法退步。

## 4. 来源、历史 Q 与类别解释

每折在同一训练人员集合中，按来源分别随机重排已拟合标签 40 次，使每个类的新/旧人数及总容量完全不变。评价时进一步把候选与基线限制在双方都可比较的同一组真实背景。ordinary 去 Q 七类相对这种随机分组，主类内−类间差额外增加 6.79 个百分点；相对仅按来源两分的共同 9 楼、1,449 个背景，额外增加 2.81 点，同类主稳定率提高 4.21 点、宽坏尾下降 2.56 点。ordinary_new 两类与七类相对来源内随机的主分离增量为 4.87/6.59 点。上述都是内层历史审计，40 个随机分组不是 40 组独立图片。

有明确反例：large_n 连续风险两类在同背景来源基线之上的主分离增量约 −0.06 点、去 Q 几何分离增量 −0.72 点。不能把它称为超越批次信息的普遍新类别。来源条件域只有一种来源时，“仅来源”基线没有类间关系，是不可定义，不是 0 分。

进一步在每个八楼训练折重新估计 q_beta，构建同 K 的 Q 分位类别，并在“来源×训练 Q 三分位”内随机重排类别、保留各类容量。前者的共同背景对照中，ordinary_new 去 Q 七类额外增加主分离 4.00 点、去 Q 几何分离 2.41 点；ordinary 七类仅额外增加 1.47/1.79 点，同类主稳定率增益约 0.59 点。hard_new 七类增量 1.23/2.32 点；来源包含 hard 七类对同 K Q 类的主分离几乎无额外信息（+0.03 点），去 Q 几何为 −0.15 点。来源×Q 三分位容量随机仍留下更大增量，但它只是粗 Q 控制，未严格匹配数值 Q、低尾、波动、困难适应等全部信号，不能写成“已排除质量因素”。详情和逐折重建 SHA 见 `inner_q_baselines/`；类别与短单均未改动。

去 Q 风险学习依然会得到与历史 Q 相关的类别，这是输出行为和质量相关的实证现象。ordinary_new 两类的历史相对 Q 均值为 +5.48/−6.19，点数效应 +0.106/−0.101；T 效应很接近，不能称为快慢型。ordinary 七类中 C02 为历史较高 Q、略多点且新批为主；C03 为较少点、略矮且旧批为主；C04 全旧批且缺合格困难画像；多个低 Q 类的现有画像接近，不人为编造独特心理或能力解释。

`review_tables/selected_class_names_and_profiles_zh.csv` 给出所有 15 方案的类成员、后验描述名、Q/低尾/点数/T、来源及机会。`selected_worker_explanations.csv.gz` 可逐人追踪。描述名不改变类号，不是训练定义，不是等级或每次作答保证。Semi 旧确认错误机会不足，scope 只可解释回答倾向，不能据此命名“纠错高手”“盲信者”或“域外判断准确型”。

## 5. 删楼稳定、非传递与冻结后压力

headline 删楼稳定只使用该域实际有数据的楼。hard 有 6 栋贡献楼，另外 4 栋删去后类别当然不变，不能拿这些平凡 ARI=1 抬高均值。ordinary_new 去 Q 两类的 10 楼删楼 ARI 均值 0.955、最小 0.778，收缩强度 0/1/3 的标签相同；ordinary 七类 ARI 均值 0.619、最小 0.395。hard_new 去 Q 七类在 6 次实际删楼中均值 0.558、最小 0.335；hard_new 三类均值仅 0.184，边界不可靠。来源包含的 hard 七类有一次删楼使 19 人丢失资格并导致拟合失败，保留失败分母。

真实同背景三队中，“A 与 B 稳、B 与 C 稳，但 A 与 C 不稳”的开放楔比例，在新增面板按楼等权为主阈值 9.80%、去 Q 几何 5.21%；旧面板为 7.57%/1.19%。分母是存在两条稳定边的实际楔，不是所有人员三元组。工程接近阈值本来不保证传递，这说明硬分类边界有代价，不构成“所有分类无用”的证明。`mixed_audit/actual_nontransitivity_examples.json` 保存真实事件、共同核心、三队成员和数值。另有跨图汇总关系图的非传递表，但它的三条边可能具有不同机会集合，不能冒充同背景证据。

旧 A_nested 的 7,272 个历史事件预先不参与拟合/选择，冻结后原样用于不同背景压力测试。每个核心只有一个人员对，因此只能在同图、n、来源对层比较不同核心，不能称精确同核心试验。ordinary 去 Q 七类保留 +7.63 点主稳定差（69 图、10 楼），ordinary_new 两类 +6.82 点（67 图、10 楼）；hard_new 去 Q 七类 +21.13 点，但只覆盖 7 图、4 楼，同类宽坏尾仍 27.86%。来源包含 hard 七类主差 +2.63 点，去 Q 几何差却 −6.98 点，同类宽坏尾 46.64%，是重要反例。高类数带来的支持损失可见：旧 K12 只有 48 图可同时比较类内/类间，旧 K2/K3 为 77 图。A_nested 仍是旧历史图片和先前生成的团队，不是外部盲测。

## 6. 实现审查附注

独立审查确认 `context_joint` 的居中基线在来源域筛选之前，读取整个同一训练背景的 entrant 图。因此来源条件的 context_joint 候选会间接读取其他来源 entrant 结果；没有跨楼/折泄漏，但不能声称完全来源内部形成。冻结标签保留，方法限制见 `review_tables/METHOD_QUALIFICATIONS.json`。本次入选的来源条件候选仅用 joint/geometry，未使用该居中表达。

所有来源随机基线的快速聚合与原 pandas 逐折评价作了逐数比对，最大差低于 4e−16。原始压缩 CSV 写入采用内存完整压缩、解压 round-trip 和原子替换，避免多进程文本流未关闭导致的 gzip 页尾缺失。精确标签、输入 SHA 和重建一致性以各 receipt 为准。

## 7. 复现入口

依赖为 Python 3.12、numpy、pandas、scipy、scikit-learn、shapely；具体运行版本另见 `requirements_reverse.txt`。需先按主成果包输入索引恢复旧 A events、历史特征、split、新面板 anchors 与相同科学版本的原生团队输出。无需读取目标楼结果。

```bash
python interchangeability_20261020/reverse/extract_native_history.py
python interchangeability_20261020/reverse/learn_swap_types.py --domains ordinary hard small_n large_n --out interchangeability_20261020/reverse/legacy_rebuild
python interchangeability_20261020/reverse/learn_swap_types.py --out interchangeability_20261020/reverse/mixed_rebuild --supplemental-events interchangeability_20261020/reverse/native_history_events.csv.gz --input-tag mixed_history_v1 --minimum-class-pair-coverage .75
python interchangeability_20261020/reverse/audit_explain_types.py --fit interchangeability_20261020/reverse/mixed_fit --out interchangeability_20261020/reverse/mixed_audit --shortlist interchangeability_20261020/reverse/MIXED_SCREEN_SHORTLIST.json --supplemental-events interchangeability_20261020/reverse/native_history_events.csv.gz --lobo --nontransitivity
python interchangeability_20261020/reverse/audit_inner_baselines.py --fit interchangeability_20261020/reverse/mixed_fit --shortlist interchangeability_20261020/reverse/MIXED_SCREEN_SHORTLIST.json --supplemental-events interchangeability_20261020/reverse/native_history_events.csv.gz --out interchangeability_20261020/reverse/mixed_baselines --random-draws 40
python interchangeability_20261020/reverse/stress_nested_history.py --out interchangeability_20261020/reverse/nested_stress
python interchangeability_20261020/reverse/audit_inner_q_baselines.py
python interchangeability_20261020/reverse/summarize_training_audits.py
```

旧版原始学习脚本快照也在 `legacy_fit/learning_script_snapshot.py`。重训可能因线性代数库、k-means 版本等产生边界差异；复建主融合比较应使用已冻结的精确人员标签和请求成员。不要根据重训结果悄然替换主实验类别。
