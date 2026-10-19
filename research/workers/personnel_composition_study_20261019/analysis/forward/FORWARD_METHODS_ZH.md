# 正向分类输入、规则与边界

## 固定历史侧

本模块只使用 `analysis/composition/SPLIT.json` 的 10 栋 history 建筑拟合人员画像。普通 Manual 的历史支持为 81 张图、2,578 份正式质量记录；60 人中 55 人达到至少 8 个任务、3 栋建筑的主画像门槛。5 位未达门槛者为 W014、W018、W021、W022、W027，均是旧来源；它们的可得估计仍列在画像表中，但不能进入主类，unknown 也不是一类。

程序从冻结 main 的 `forward/build_features.py` 直接提取未修改的纯特征函数，使用冻结 `profiles/run_profiles.py` 的任务固定效应与难度部分汇聚估计。没有重新加工点、改变坐标、选择参考或重评原作答。

## 候选覆盖

B8L2 下共登记 157 个方法与适用域组合，其中 151 个有支持并形成至少两类，147 个实际支持分区不重复。另有 6 个因机会不足未拟合的定义，完整保留在台账及 unknown 标签中。类别数请求覆盖 2、3、4、5、6、8；条件交叉类的实际数量据支持决定。

- Q、绝对 Q、质量相对低尾、历史点数效应的训练分位组；分位组是有定义的层级，不能据其等人数宣称天然人群。
- 相对 Q 的 0 或 −3／+3 阈值组，以及 Q 与点数、波动、T、困难适应的交叉组。
- Q、Q+结构、结构单域、Q/T/难度/结构、多域加行为的平均链接与多起点 K-medoids；完整支持的域另试 K-means 和最多四维 PCA 上的对角协方差 Gaussian mixture。
- 简单／中等／困难的支持内 θ 分组与 Q×适应类。
- 新旧 Semi 的编辑倾向、错误机会下未修改倾向分开；scope 回答倾向单列。
- 门洞和新旧 Semi 另外使用本条件合格历史最终 Q；特殊条件因历史机会不足登记失败。

跨域距离先按历史人员中位数/IQR（必要时 MAD/SD）标准化并截至 ±3，再在各域内均分权重、域间等权。两人的缺失机会只遮罩其相应特征，未补零，也没有把缺失标记或来源直接放入正向聚类。不过遮罩域本身仍可能间接携带来源差异，须看来源组成和控制后的效用。

所有 C01/C02 等类号按本类的历史普通 Manual 相对 Q 均值排序，主要为了展示和稳定复建。同一规则中的点数高低、Semi 未修改高低，必须看具体特征列，不能只读类号。`method_manifest.json` 和 `class_profiles.csv.gz` 保存完整成员、类规模、来源及各特征均值。

## 机会与来源

|历史特征|新增支持人数|旧来源支持人数|
|---|---:|---:|
|普通 Manual 主画像|35|20|
|T|35|19|
|简单 θ|35|20|
|中等 θ|35|5|
|困难 θ|35|2|
|旧确认错误未改效应|0|0|
|新报告错误未改效应|28|0|
|编辑效应|27|24|
|scope 回答倾向|35|0|
|门洞最终 Q|27|8|
|Semi 最终 Q|27|24|

普通主画像、T、难度、行为的门槛继承既有冻结特征函数。门洞/Semi 最终 Q 采用另列的至少 4 个本条件任务、3 栋建筑门槛，其机会量更少，不能与主画像支持强度等同。Semi 行为类使用自己的机会门槛，不另要求其普通 Manual 主画像合格。

旧确认错误与新报告错误不是同层证据；编辑不代表原错误已纠正，新来源没有逐份初始几何的记录不形成净改善。scope 仅表示回答倾向，不能解释为裁定准确率。比同任务同伴点数少只是结构表达习惯，不能自动宣布必要结构遗漏。

## 数值与泄漏检查

将全部非 history 建筑的 Q、几何派生值、时间和行为数字换成极端污染值，所有训练特征逐项完全不变。独立的完整任务/人员 dummy-variable OLS 与冻结任务消元法所得 q_beta 最大绝对差为 9.08×10⁻¹³。特征 CSV 回读、标签唯一键、unknown 语义均核对通过。

D10 使用同一历史侧、同一方法规则独立重拟合；`D10_class_sensitivity.csv` 比较共同人员对的共类关系，不把编号改变当作类别变化。例：Q 的 ±3 阈值三类有 2.15% 人员对改变共类关系；Q×点数二乘二为 4.44%；Q+结构 medoids 四类为 21.08%；全域 medoids 四类为 33.00%；结构单域四类为 0。后两者并不自动表示融合效用差，说明不能把某一分区当作固定的自然人员类型。

## 小文件复现

在固定 main 的稀疏或完整工作区，可运行：

```bash
python analysis/forward/build_forward.py --repo repo --split analysis/composition/SPLIT.json --out analysis/forward/results
python analysis/forward/build_forward.py --repo repo --split analysis/composition/SPLIT.json --out analysis/forward/results_D10 --metric D10
python analysis/forward/verify_forward.py --repo repo --split analysis/composition/SPLIT.json --out analysis/forward/results
python analysis/forward/summarize_forward.py --out analysis/forward/results --d10 analysis/forward/results_D10
python analysis/forward/summarize_support.py --repo repo --split analysis/composition/SPLIT.json --out analysis/forward/results
```

依赖使用既有 Python 3.12 冻结科学环境中的 numpy、pandas、scipy、scikit-learn。容量表只根据逐池成员和已冻结类计算可行人数向量与多人实现数量，明确区分“可行”与“实际已测”。不需要导出所有人员组合或距离矩阵。
