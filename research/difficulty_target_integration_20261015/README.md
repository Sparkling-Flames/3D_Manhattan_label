# 图片难度与评价目标接入：1145条质量、12图融合

> 当前图片难度已由[v3及GT排除](../difficulty_review_update_20261015/README.md)接续，本页保留旧目标/旧分类绑定。新增空间按整个空间体竖向边界解释；下游还须应用至少3名有效标注者规则，旧计数不可直接作为最新分析分母。


> 2026-10-15接续说明：本报告保留当时的图片目标绑定审计。其后融合线程完成12图WQ接入及另6图特殊层比较，见[融合接续](../wall_consensus_quality_20261015/README.md)；不把本报告原来的底面绑定覆盖改写成完整质量资格。 当前统一状态见[资料核对](../../docs/thesis_main/四线程成果与论文主线核对_20261015.md)。该句原属文档整理阶段；后续已获授权并完成描述统计，当前版本见统一状态入口。


2026-10-15。已执行接入，原 `scope_preferred_difficulty_20261011_v2` 的259图粗分类不覆盖：144简单、30中等、38困难、5待核、42特殊单列。本轮无需重做全图判读，也不按WQ或融合结果改标签。

## 原意与本轮边界

用户要粗分类；多种已接受范围时优先无自遮挡范围，并让各类型可供复核。无/少遮挡六转折可简单，角线被挡不自动等于难推断。OOS和门洞保留独立轴。旧[粗审页面](../../analysis_results/difficulty_scope_preferred_20261011/review.html)继续使用，不要求重复审核。

已核对本线程历史、当前统一模型/CONTEXT、10月15日接入交接与本模块README。统筹上轮“只整理不接入”已被本轮授权替代。质量使用WQ-LS08-20261014研究工作版及同参考IoU/分项，不新调参、不采用Q-Profile映射；未启动同房预测或新批数据。前一轮800条READY审计保持历史。

## 可直接使用的数据

|输出|分母|用途|
|---|---:|---|
|[quality_bindings_1145.csv](quality_bindings_1145.csv)|1145条/135图/24人|原联合表全部字段与分数原样保留，加范围关系、当前门控、版本及消费层|
|[ordinary_same_target_panel.csv](ordinary_same_target_panel.csv)|836条/95图|普通manual同目标条件面板，671简单、80中等、85困难（记录数）；不授予正式资格|
|[limited_or_unmatched.csv](limited_or_unmatched.csv)|309条|全部不进入上述面板的记录及原因，互斥划分而非丢弃|
|[different_id_audit_95.csv](different_id_audit_95.csv)|95条/17图|逐条核对ID不同的情况，保留作答所用参考，禁止只按图片批量映射|
|[fusion_reference_bindings.csv](fusion_reference_bindings.csv)|12图/28参考条目|每个original/manual_revision/difficulty_selected_floor与难度目标的关系|
|[fusion_pool_bindings.csv](fusion_pool_bindings.csv)|269份池内作答|公开人员号、稳定人员/作答/对象ID、采集条件、当前门控及坐标核验|
|[fusion_observation_bindings.csv](fusion_observation_bindings.csv)|6456个路径状态|人员子集对应的稳定作答集合、难度目标、条件、已有指标和完整性，不把重复子集当独立样本|
|[fusion_same_target_floor_curves.csv](fusion_same_target_floor_curves.csv)|逐图逐k|接出已发布的同目标底面IoU及实际分母，不重跑融合|
|[fusion_floor_difficulty_description.csv](fusion_floor_difficulty_description.csv)|分层逐k|同时提供固定共同10图和当k可用12图视图，按图片等权汇总|
|[new_target_addendum.json](new_target_addendum.json)|2个新目标|N05/N28已确认底面下的条件粗类；不覆盖旧目标档或嫁接旧完整分数|

## 几何与身份核验结果

从 `load_current_bundle()` 读取当前manifest、顺序/质量授权增量及完整data。当前data与质量评分来源ZIP内 `source/historical_current_formal_loader_data.json` 完全相等。因此本轮1145条的作答、参考坐标及版本与当前输入未漂移；额外逐行核对record_id→object_id、image_id、worker_id和condition。不是只因ID相同就认可同几何。

1050条同参考ID：难度底面与质量参考底面均一致。95条异ID进一步分成：

- **54条、4图底面顶点相同**：pa4-14、uNb-50、uNb-60、wc-26的相应记录。新目标仍仅确认底面，不能宣布完整顶部已等价或把旧完整WQ作为新完整目标的评价。可接底面IoU/Sb等同底面分项；作答自身D另保留，不等同参考相对角度误差。
- **41条、14图底面不同**：保留原评分供原目标诊断，配当前粗类时只作图片级关联描述。差异来自已保留的参考/确认范围版本，不是本轮发现同ID被悄悄改坐标；仅凭多边形不同也不能一概断言是语义上不同房间，可能包含范围、细节和几何修订。
- **wc-26同时出现两类关系**：5份底面相同，1份不同。因此必须按作答＋评价参考绑定，不能一图统一指定“已对齐”。17图不是14+4个互斥图片。

底面比较允许环起点与方向等价，坐标绝对容差1e-8；也检查共线细分导致的同足迹（面积相对差与Hausdorff距离均≤1e-8）。这不是按最高IoU/Q找参考，近似重叠不当等价。本次实数据未触发仅同足迹分支；该分支有测试。相同底面不证明相同顶部，原始/修订GT分别保留。

## 1145条的互斥消费去向

|use_panel|条数|解释|
|---|---:|---|
|ordinary_same_target_conditional|836|普通manual，固定难度目标与评价参考一致；仍是研究条件集合，不是已获新正式资格|
|floor_only_target_equivalence|54|仅可认证底面等价，新目标顶部未确认；完整Q不并入同目标主面板|
|image_only_different_target|41|目标底面不同，仅图片级描述或原参考敏感性|
|hold_scope_or_reference|41|N05/N28的28条＋既有台阶参考3条＋门洞范围诊断10条；数值保留，暂不作目标已明确的主比较|
|separate_special_or_pending|117|115条门洞一般条件比较＋2条既有待核，保留原限制；不把门洞一律禁用或一律判难|
|separate_secondary_or_exception|56|39 semi次层＋9严重例外＋8历史诊断，分层保留|

836条的筛选没有以分数好坏为条件。原personnel/context barriers、role、reference_binding、same_target_unconfirmed及旧hold字段全部保留；当前 `main_quality_gate/main_consensus_gate` 另列，不覆盖既有准入。此表不恢复严重例外资格，也不把“未标特殊”认证为适用。消费者如需进一步资格筛选，须报告新分母。

## N05/N28：新目标不能继续沿用旧难度解释

只针对这两张新变化查看了照片，并把已确认底面投影到原图核对；没有全量重判。两者新底面均4转折、H=0，范围已确认，不要求用户再画或重复确认。

- [N05 / B6ByNegPMKs-37新底面](B6ByNegPMKs-37_new_floor.jpg)：直走道主体与停止边有线索，旧GT必要墙背分支不再属于新目标，**新目标条件简单；旧目标仍困难**。
- [N28 / UwV83HsGsw3-10新底面](UwV83HsGsw3-10_new_floor.jpg)：门边/墙线可支持四角停止位置，柜体局部挡脚，**新目标条件简单；旧目标也是简单**，但相同类别不等于相同评价目标。

新增目标条目版本为difficulty_target_addendum_20261015，记录确认来源与原坐标、N/H、照片依据、top_boundary_pending及空的逐作答范围分配。两个环为循环递减方向，几何有效；不重新排序，也不把方向相反当自遮挡。完整顶界和逐作答对应仍缺，相关28条旧分数不转移为新目标Q。新条目不覆盖259表，因此不擅改全库计数。

目前无需用户再裁定粗档。后续若要对这两图做完整新范围Q，真正需要解决的是新顶界及具体作答属于哪个已认可范围；这项应由参考/质量任务集中处理，不能按哪个Q高选择范围。

## 12图融合接入与已有粗分描述

12图共7简单/2中等/3困难；共同24人10图为6/1/3，其余2图为不同池大小的哨兵。269份池内作答经相同 `project_bundle + prepare_record` 入口后，坐标全部与冻结快照相同。uNb-36两份记录在prepare_record前的排列与快照不同、经既定处理后相同，明确记入表中，不报成数据漂移，也未修改源数据。

28条参考链已核验。11图存在同难度目标的完整参考；rPc-06的新难度范围只有底面，旧original完整参考与它不同。全部12图均有匹配的difficulty_selected_floor，故已有底面IoU轨迹可供粗分描述。12图完整参考身份已解析到原GT对象ID，不能再沿用上一轮177图“未声明评价参考”的笼统状态；但本轮没有把这12图结果扩写到177图全量。

6456状态中5874满足原表complete_floor_evaluable，582不满足（包含k=2政策暂停等情况，不全是算法失败）。无值保留，不补0；每条记录仍保留节点数、来源环、几何/完整性和原失败原因。5894唯一成员子集与6456路径状态不同，不能把随机路径当独立图片。

以下只读取既有底面IoU，固定共同10图、先图内按原24路径汇总再按图片等权；括号为可评价状态数/总状态数：

|粗类|k=1|k=4|k=8|k=16|
|---|---|---|---|---|
|简单6图|0.901（144/144）|0.931（143/144）|0.935（144/144）|0.937（143/144）|
|中等1图|0.711（24/24）|0.783（22/24）|0.790（24/24）|0.752（24/24）|
|困难3图|0.624（72/72）|0.701（65/72）|0.685（64/72）|0.682（59/72）|

这些图上简单组参考接近度较高；中等/困难组并非随人数单调改善。不能据此宣布“难图收敛更慢”已经验证：中等只有1图，图片/建筑/覆盖不均，困难组可评价率也变化。特别是k=24困难均值0.837只剩2/3图、48/72状态可评价，不能将它当三图整体改善。另一个available_12视图高k时哨兵退出，不能跨k误读为固定图片集合的变化。

本轮读取到的公开输入为10月14日冻结底面过程，未读取到已发布且绑定的WQ轨迹，因此没有WQ分层数值，也没有重复调用融合。融合模块后续发布WQ后，可用本次目标/成员表连接；rPc-06只走底面分支，不能嫁接旧顶面。

## 复现、字段与交付

```powershell
python -m tools.thesis_main.analysis.difficulty_target_integration_20261015
python -m pytest tests/test_difficulty_target_integration_20261015.py tests/test_difficulty_scope_preferred_20261011.py tests/test_scope_difficulty_review_20261011.py -q -p no:cacheprovider
```

本模块代码只写此新目录。当前loader与质量来源快照不等时停止而不是静默更新；换输入应新建结果版本。`CHECKS.json`保存manifest、授权质量增量、来源检查及实际分母。CSV保留原联合表数值，不重评分；`difficulty_version/difficulty_target_id/score_version`必须与数据一起消费。新增目标仅在addendum中；`full_target_match`与`bottom_target_match`分别用于融合参考，不能互换。集合标识见member_record_ids；采集条件与各源用途限制不得丢弃。

新增文件包括本目录所有CSV/JSON、说明、2张解析投影证据，以及专属工具和测试；图像是保留的分析证据，不是检查截图。本轮未改原分类、GT、原始数据、质量包、评分/融合参数、人员资格；未提交/推送。未改其它模块、公共索引、合同或统一模型。请统筹把本页登记为1145条与12图接入入口，保留10月14日800条审计的历史身份。

剩余工作：质量/融合模块发布相应版本的同目标WQ后再连接；2个新范围缺顶界及作答绑定；特殊组仍按各自限制讨论。上述缺口不阻塞已交付836条普通面板和12图已有同底面描述。

本次验证结果：9项相关pytest通过；1145条原联合表每个已有字段逐值保持、28条参考链中所有有完整点的参考均与当前来源一致、6456状态与5874可评价分母及文档链接检查通过。无新检查截图。
