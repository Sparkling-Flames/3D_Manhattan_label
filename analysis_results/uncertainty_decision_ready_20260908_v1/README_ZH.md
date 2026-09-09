# 不确定性研究：数据连接与历史测量说明

本页保留2026年9月8日的数据整理范围和测量记录。研究已继续推进，最新状态见[研究交接](../../docs/thesis_main/研究交接_20260909.md)与[当前场景分析](../multibuilding_threshold_stability_20260909_v1/分析结果.md)，下文“本轮停止”仅指当时的数据连接工作。

2026-09-08。**本轮停止在“数据可连接、测量有来源、人工意见与待验证解释分开”的阶段。**可以据此讨论下一步研究，但不表示工人类型、图像歧义或人数上限已获验证。本轮没有新建工人分类、开展疲劳模拟或新增视觉裁决。

旧汇报稿已进入[历史归档](../research_history_archive_20260909_v1/README_ZH.md)。当时的独立审查在[独立审查与工人分层建议](../independent_direction_worker_review_20260908_v1/独立审查与工人分层建议.md)，不代替当前结果。

## 已整理到什么程度

| 层次 | 本轮结果 | 含义边界 |
|---|---|---|
| 历史身份 | 2501份canonical、214图、26人、270个完整context | 旧资格仅作属性；不同阶段／block／条件不混同 |
| 版本与旧簇 | 2513份版本；2497条旧簇成员连接canonical，1条保留原版本 | 2498是两个分簇版本的成员记录数，不是新增人员或独立响应数 |
| 实际初始化 | 574份Semi响应连接已有初始化追溯 | 区分初始坐标存在、来源、checkpoint是否核实及实际观看事件；离线Bi不代替当时初始布局 |
| 真人—Bi | 15006行＝2501响应×2读法×3模型表示 | 每份响应六种对照，不能算六份独立数据；不可计算行保留 |
| 候选模型 | 380图三种表示，含166张无历史真人响应候选 | 候选不进入真人分歧样本量 |
| 原人工评论 | 50图完整原记录，其中45条非空评语；4条后续补充 | 原文保留，完成选项不表示确定，AI解释不伪装人工裁决 |
| 评论连接 | 51条范围陈述、37条显示对象关系；54个真人显示对象身份均可连接 | 其中仅4份真人响应有直接明确的范围语义连接；其余评论仍有场景解释价值 |

四份直接连接的真人范围描述来自V04的W11/W15、V07的W8、V09的W2，均涉及enclosed；其中还保留“不完整”“不特别准确”等限定。**这不足以训练两类工人的分类器，也不说明只有四份标注值得研究。**当前缺的是系统的响应级语义核对，而非没有历史几何数据。

29条场景、集合或参考版本陈述保留在限制表中，不能自动变成29项人工任务。V15/V27仍可保留“不知道怎样完整确定”的状态；V04/V48的后续说明优先解释旧选项。V07/V31/V33另一视角的已有点序确认已保存，不重新要求用户给顺序。

## 测量方面的实质进展

模型浮点地面UV、整数像素及像素中心约定已经分开。真人连续百分比坐标不统一加0.5；native模型投影与真人投影的坐标轴经过非对称形状和755个有效模型多边形的同轴检查。

在三种模型表示均可计算的集合中，原邻接读法有1597份响应，历史pairmap读法有2335份。后者可计算更多不能解释为修好了相应数量的标注；未经用户确认的点序仍是读取假设。

整数换成浮点表示时，原邻接的178份、历史pairmap的257份响应出现非零亲近方向反向；另有大量原整数平局变成微小差异。反向项两种差值绝对量中的较大值，中位数均约0.00154。数值零容差检查没有消除这些变化，但它们仍然很小。**距离正负不能直接成为enclosed／extended工人标签。**详情与分母见 [几何说明](geometry/说明.md)。

同一固定context集合中，双头差异与旧真人均距的描述相关在更换模型精度后仍为弱正关联；它不是显著性检验、不是场景固有歧义概率，也没有证明可预测新building所需人数。

3条Shapely运行警告已定位到2图的独立同轴一致性检查，相关结果均有限并通过容差；实际真人—模型、双头和确认派生距离未触发警告。记录见 `geometry/numeric_warnings.csv`，未将警告静默填成零。

## 数据入口与字段合同

保留既有便携输入包作为事实来源，本目录提供增量连接与敏感性结果，不复制一套原始数据或数百MB图片。

- `response_index.csv.gz`：每canonical一行。保留完整身份、人员、stage/block/condition、旧排除属性；连接旧簇／模型／参考／实际proposal的ID数组，加入时间来源和已有初始化追溯。`legacy_initialization_source_kind`是旧标签，`initialization_reconstructed_source`是后续追溯，两者不互相覆盖。
- `context_index.csv`：每完整context一行。图像、building、阶段、block、条件、响应／人员／当前20人支持数。`observed_active_time_count`只数非空时间，不能作为可靠连续工作记录数；`initialization_trace_count`不表示确认观看次数。
- `coverage_by_condition.csv`：按stage和名义条件汇总的覆盖；不能据此作Manual/Semi因果比较。
- [semantics/README_ZH.md](semantics/README_ZH.md)：原文、后续补充、AI提取、逐响应连接及未连接范围陈述的具体字段。
- [geometry/说明.md](geometry/说明.md)：地面距离、读取映射、三种模型精度、失败状态、警告和用户确认派生。
- `INDEX_QA.json`：索引字段清单与输入范围；`DELIVERY_QA.json`：最终跨表连接检查；`tests.log`：相关测试结果。

连接顺序：

`response_index.canonical_annotation_id → geometry.human_bi_comparisons（读法／表示须保留）`

`semantics.response_semantic_links.statement_id → scope_statements；canonical_annotation_id → response_index`

旧分簇、原始坐标和参考继续读取 `analysis_results/uncertainty_cloud_inputs_20260906_v1/`。旧成员的`raw_version_only`通过原版本ID读取，不能套用当前canonical几何。初始化逐行追溯源为 `analysis_results/annotation_research_prework_20260905_v2/evidence/initialization_trace.csv`。

## 如何复现和读取

在仓库根目录、现有Python依赖环境中运行：

```powershell
python -m tools.thesis_main.data_prep.prepare_uncertainty_decision_index --out analysis_results/uncertainty_decision_ready_20260908_v1
python tools/thesis_main/data_prep/prepare_scope_evidence_20260908.py --repo .
python -m tools.thesis_main.analysis.prepare_human_bi_comparisons_20260908 --out analysis_results/uncertainty_decision_ready_20260908_v1/geometry
python -m tools.thesis_main.data_prep.prepare_uncertainty_decision_index --root . --out analysis_results/uncertainty_decision_ready_20260908_v1 --check-prepared
```

读取检查只访问仓库文件，不访问仓库外Bi目录、图片服务、权重或GPU。图片访问与实际视觉判断不在这一检查的完成声明中。检查15006行的唯一主键和每响应六种对照、50份原评论的身份、4份真人语义连接及原版本成员的存在；数据可连接不等于科学解释已经成立。

最终相关测试合并运行：21项通过。另在仓库之外的工作目录启动读取检查并显式指定仓库根目录，连接检查通过；`git diff --check`通过。文档索引与项目地图已同步。未运行模型训练或全仓库无关测试，因为本轮没有修改其实现。

## 为什么现在停止

事实与测量连接已经足以让下一步分析者明确知道能算什么、缺什么。继续推进会开始涉及：如何定义响应范围类型、哪条轴用于工人分层、聚合质量还是分布恢复作为主要结果。这些已经属于研究选择，需要你和导师决定，不能靠继续整理自动解决。

本轮不要求你重做已明确的50图评论。后续若要实做人员分类，先利用现有明确场景解释开展响应级核对，只把无法从原页面、原版本及已有评论解决的具体问题交给你。没有冻结工人名单、人数阈值、论文提纲或实验条件；本轮新增资料保存在本地工作目录。
