# 固定来源与全嵌入数值审核

## 结论

返回包实际输出的6份作答与1份原始GT，其ID及坐标均与固定来源逐值相同；35项可用摘要数值复核通过。但返回输入存在两项来源绑定问题：R03288的匿名人员标签与源点索引错误，以及未使用的额外R03280记录无法绑定到该195作答快照。二者不能因数值复算通过而忽略；不据此推测任何真实人员身份。

完整当前交接包10项测试通过。官方verify.py原样运行失败，不能标为全量通过。继续执行相同计算、只将比较器从遇错即停改为记录差异的独立诊断完成了195对象、390参考行、17改序及参考对照；超出原容差的差异全部局限于极小方向角浮点差，最大1.8695165593385354e-7度。BEV、墙带、模型体积、墙高、状态、输入身份与环序未发现超容差差异。

## 固定版本与下载边界

- 仓库：Sparkling-Flames/3D_Manhattan_label
- 固定提交：bba3dc7c9a79b8342ecb4ce2487affe41886eb56
- 入口：research/pro_quality_handoff_20261002
- 全部42个有界交接文件共9,430,097字节，逐一匹配Git blob SHA；MANIFEST列41文件，另有MANIFEST自身。完整Git blob、SHA-256及大小清单见handoff_download_hashes.json
- results.json：3809553a325c49baebb1a15a04da30017d98177d
- 当前3D源码：9922ebfc2d08b072575c4dd0f82ff86824d3d359
- 当前metrics.csv：a473dcc8f7291cb1d824d116df47fb36a5cd847e
- 当前REPORT.md：bc9c4151e9ce9b65c97fef6e7b02d5047dec9a1b
- 当前机器合同JSON：dced0454329eea9295dc16ed46059cc388e2ac6f
- verify.py：42b31faead13ca74e02e1c0c0ad5104f78fc475a

额外只读检查了同提交的tools/thesis_main/data_prep/project_public_research_20260929.py（blob 13eddb6bc79a0dd854de8370ee75df1a1729944c）。其P/R标签按整个投影输入的排序枚举生成，是快照内标签。正确连接键至少包含固定提交/结果blob、图像、record ID，以及参考版本；不能把P标签当作跨版本永久身份。没有读取或下载其private map、完整原始身份或评论语料，也未调用完整bundle生成器。

## 官方执行与独立诊断分开报告

环境：Python 3.12.14、NumPy 2.3.5、SciPy 1.17.0、Shapely 2.1.2。手包requirements只有下限，未锁定原生成环境。

1. 官方测试命令：python -B -m pytest tests -q -p no:cacheprovider -W error::RuntimeWarning。10 passed，原日志pytest_official.log。历史文件所写40项是本地完整仓库历史范围，本次没有重新运行那40项
2. 官方验证命令：python -B verify.py。先完成前轮74合成、15有效真实比较、9缺参考及1加密边界检查，随后本轮对象诊断在R03293.direction_self.axis_deg失败，完整错误保留verify_official.log
3. 失败值：保存2.263540068818403度，复算2.263540035225588度，差3.359281475212583e-8度；原容差relative=1e-9、absolute=1e-10
4. 继续诊断不修改源文件或阈值，完成官方全部计算，并收集而非吞掉超容差项：70,211浮点叶、33,110其他叶，1,720项超容差，全部direction字段。该数包含对象、比较行及改序对照对相同诊断值的重复引用，不是1,720个独立案例
5. 最大方向差1.8695165593385354e-7度；非方向最大绝对差约1.44e-14。墙带列比较数值完全一致；BEV、边界、墙高和模型体积均在原容差内。原官方验证仍然是失败，诊断不将其改称通过
6. 首个失败对象的新旧floor数组逐值相同；两个轴角代入当前目标函数均得到0.011441384044813577，RMS仅差约4e-15度。与极小优化器浮点差相符，但未取得原生成环境锁文件，不能归因到某一个版本升级

full_recompute_differences.json保留所有差异及各类最大差；full_recompute.log保存覆盖和汇总。没有覆盖或修改交接包结果，也没有换用仓库根目录旧实现。

## 390行与资格分母

- 195份作答（不意味着统计独立）、12图、26个快照内人员标签，390为每作答两个GT版本行，不能当390独立样本
- 原始GT：182可计算、13配对/几何不可用；人工修订GT：71可计算、7配对/几何不可用、117参考缺失。因此253可计算、20几何不可用、117参考缺失
- 134人工确认环、48默认共享x未审环、13无可用点；默认环不改称人工确认或人员错误
- 所有390行中的a与对应195对象record逐值一致；同图同参考版本的b一致。没有发现完整手包内R03288别名冲突
- 97份quality_candidate与可用BEV相交，来自6图；gate仍为candidate_pending_geometry，并非已完成所有人员评价资格裁定。其余为71 out_of_primary_scene、16 excluded、9 hold_scene_or_reference、2 hold_individual_review
- 候选可算分图数：7y3sRwLe3Va-26为5；B6ByNegPMKs-40为22；e9zR4mvMWw7-16为24；e9zR4mvMWw7-19为24；jtcxE69GiFV-30为1；yqstnuAEVhm-31为21。只有5图支持候选人员同图配对
- 两GT共同可算71份只在3图。条件与图片嵌套：两图oos、单图semi、其余manual；不能从本面板单独分离条件效应和图片效应
- 17改序只来自e9zR4mvMWw7-19的11份及yqstnuAEVhm-31的6份。前后点集相同，按既有嵌入邻接重放；不重新排序或更改GT。17份相对原始GT的BEV增量均正，范围0.05751400359971287至0.4216573446142543；相对人工修订GT也均正，范围0.0982796008164244至0.3177002668317426。只支持这两张定向图的描述，不外推必然改善

逐图分母、条件与gate见panel_denominators.json。

## 返回来源绑定

source_binding_audit.json提供全部输入ID、实际选中状态、点数组SHA-256、匿名标签和点索引对比。

- 实際输出6作答：R03286、R03288、R03281、R03287、R03284、R03282。六份坐标均与当前results.json逐值相同
- GT为R02503，其ID、坐标、源点索引均相同，没有GT重命名
- R03288：返回worker=P019，当前完整objects、real两参考行及metrics.csv一致为P020；返回source_point_indices=[0,1,2,3,4,5,6,7]，当前为[4,5,2,3,6,7,0,1]。坐标仍完全相同，因此六对几何数字不因这个错误改变，但不能用返回标签或索引做人员归属、源点追溯或后续融合
- 输入JSON实际含9份作答，当前源同图只有8份。多出的R03280在195对象中无该ID、也无完全相同点数组。其来源未建立，不推测属于另一个人或版本。它被run_audit显式6-ID筛选排除，未进入实际六对；另外两份未选中R03285/R03283可绑定来源
- 返回make_input.py会重建这些输入问题；reproduce.py本身没有调用make_input，而是继续消费现有输入。修复应由固定源机器提取完整字段并加连接断言，而不是手工改一个P标签后宣布来源链完整
- 六对皆来自同一doorway_difficult图且quality_candidate=false；数值验证不等于主人员质量方法验证

35_fields_current_source_binding.json确认：手抄CSV的35个可用数字与当前CSV精确一致，返回输出对其最大绝对差8.881784197001252e-15；R03288的column_iou第36项确实不可用，未被补零或冒算。

## 当前算法确认

height_stats按每段线性墙高沿真实BEV边长解析积分：mean=sum(L*(h_i+h_j)/2)/sum(L)；RMS使用sum(L*(a²+ab+b²)/3)/sum(L)的平方根，其中a、b为端点对周长均高的偏差。它不是顶点等权拟合；现有测试覆盖线性共线细分与环反向不变性。

model_volume使用当前足迹乘该周长均高，交集为足迹交面积乘两均高较小者，再除体积并集。它是共底面的水平顶面柱体模型，不是实测顶面体积；局部顶面形状并未进入该体积。源码没有新增真实整墙对应距离。返回包的顶点LS/弧长LS是另外的候选方法，不能把它们的问题归给当前实现。

## 阅读和验证限制

已完整校验42文件字节/hash，并运行其嵌入计算；重点阅读README、当前机器合同、核心3D源码、官方验证器、对应测试及验证记录。下载不等于对每份背景历史文档逐行独立审稿，七幅手包PNG只做文件校验而未目视评价。未下载原图、原始身份映射、完整3152作答bundle或原始评论；未独立重建原始选样、源表清洗/绑定、视觉正确性或历史40测试。source_binding_audit仅将返回数据与固定公开嵌入快照核对。

## 可移植复查命令

在独立目录保留handoff/为原42文件交接包、returned/为未改动返回包、audit/为本报告及脚本。输出目录应位于handoff之外，以免触发官方inventory drift。

```
python -m pip install -r handoff/requirements.txt
cd handoff
python -B verify.py
python -B -m pytest tests -q -p no:cacheprovider -W error::RuntimeWarning
cd ..
python -B audit/collect_full_recompute_diffs.py --root handoff --out audit-output
python -B audit/check_return_source_binding.py --root handoff --returned returned --out audit-output
```

第二个脚本只依赖Python标准库。第一个使用交接包当前计算代码并保留原严格比较阈值，以差异清单完成覆盖；它不是“修复后的官方通过”。
