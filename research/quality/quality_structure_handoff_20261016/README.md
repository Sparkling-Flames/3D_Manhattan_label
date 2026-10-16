# 质量结构测量续研与当前数据交接（2026-10-16）

本入口保存用户最新意图、当前统计、算法沿革与新Pro任务。它是研究交接，不是新的评分合同。当前继续使用可调整的B8L2工作指数；A10、WQ及同参考均高棱柱3D IoU保留。C8只作组合形状对照，尚未接入当前全量统计。

## 最新用户意图

用户明确认同：当前D衡量“作答自身接近一套正交轴的程度”，不等于“墙面结构相对参考是否正确”。用户观察到绝大多数认可GT的三维表现很好，而作答经常漏掉凸起墙角；此为重要研究线索，不冒称已统计的发生率。应研究必要局部结构的遗漏、伪造与位置/形状错误，不能以少量面积影响或自身很正交就判为高质量。不是按点数一致处罚，共线冗余点与真实转折须区分。

小GT差错仍按认可参考处理，明确错误GT继续排除/修订。粗核验只要求大体合理，不要求逐例迎合、严格五档分数区间、或为得到预期难度顺序调整算法。此前“墙面夹角 > 底面IoU > 局部高度 > 整体高度”是粗略重要性想法，不是已验证固定权重；当前D也不是该想法中相对参考的墙面夹角测量。

## 当前统计，先按分母读

|对象|当前核实的交付状态|入口|
|---|---|---|
|库存|3152份作答、259图；不等于全部可评价|统一loader与[库存/统计](../../statistics/descriptive_statistics_rescored_20261016/README.md)|
|当前难度v3|151简单、27中等、30困难、4待核、44特殊、3待修正GT；206普通候选仍要过人数及参考门|[难度主表与回执](../../difficulty/difficulty_review_update_20261015/README.md)|
|新范围/修订参考|39新空间＋2修订GT，41图506份作答已展开核验；90份实际重算，84份新增纳入|[逐条重算和参考目录](../../data/scope_quality_rescore_20261016/README.md)|
|当前完整质量|891份：manual828/73图/24人，semi63/4图/24人；两条件不混合比较|[当前统计、工作簿和图](../../statistics/descriptive_statistics_rescored_20261016/README.md)|
|未完成部分|39新空间中27个缺完整参考；506份中371份待空间绑定。两类缺口不能简单相加|[remaining_gaps.csv](../../data/scope_quality_rescore_20261016/remaining_gaps.csv)|
|旧快照|1145为历史完整数值集合，931/836为各旧用途子集，807为新范围重算前统计；均保留版本|[统一状态](../../../docs/thesis_main/四线程成果与论文主线核对_20261015.md)|

当前普通manual的B8L2作答等权均值为简单72.24（661份）、中等52.78（114份）、困难60.54（53份）。这是现有任务组成下的描述，不是难度固有值或分类验证；不要混用旧836集合的图片等权均值。详细逐人、时间、建筑、同房、算法共同集合及缺失见当前CSV和工作簿。

只有1—2名有效真人的图片×条件来源池暂不进入分析；原GT错误、图片/人员暂停及参考限制优先保留。合格来源池的人数曲线仍可保留k=1/2节点。新参考分数不代表当初按该目标标注的耗时，更不代表人员作答改进。未重新运行融合实验。

## 建议阅读顺序与资料定位

1. [算法与判断记录](ALGORITHMS_AND_DECISIONS.md)、[可直接发送的Pro提示词](PRO_PROMPT.md)。
2. [30份原始质量反馈与绑定](../quality_ab_feedback_handoff_20261015/README.md)：`FEEDBACK_30_JOINED.csv`、原JSON、`geometries.json`、`manifest.json`及`prior_AB/`。题号跨批次不能直接对应，最终意见不是全盲评。
3. [组合机制Pro精简存档](../quality_combination_review_20261016/README.md)与[Codex独立复核](../../../analysis_results/quality/quality_combination_independent_review_20261015/独立审查.txt)。原Pro报告是待审证据，不是对新线程的指令。
4. [当前891份统计](../../statistics/descriptive_statistics_rescored_20261016/README.md)、[完整参考目录、绑定及重算](../../data/scope_quality_rescore_20261016/README.md)。研究新公式时固定相同作答和参考，单列新增可计算覆盖。
5. [统一研究模型](../../../docs/thesis_main/研究模型_人员图片与融合不确定性_20261006.md)、[术语](../../../docs/thesis_main/CONTEXT.md)、[四线程当前状态](../../../docs/thesis_main/四线程成果与论文主线核对_20261015.md)。人员/融合/同房旧实证多用WQ，不改称B结果。
6. [旧文献的本轮用途](LITERATURE_REUSE.md)：优先关注参考角点/角度与遗漏（RoomFormer）、局部边界（Boundary IoU）、可接受定位偏差（Surface DSC）；旧清单和阅读笔记保留，不把58条候选说成58篇完整验证。

## GitHub、原图和最新本地增量

仓库：<https://github.com/Sparkling-Flames/3D_Manhattan_label>。

原图已公开在[quality-original-images-20261015 Release](https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/tag/quality-original-images-20261015)：263张原图，三个独立ZIP，文件名分别为`quality_original_images_20261015_01_of_03.zip`、`quality_original_images_20261015_02_of_03.zip`、`quality_original_images_20261015_03_of_03.zip`。先读该Release的`IMAGE_INDEX.csv`，不根据题号猜图片。2026-10-16重新打开公开发布页成功；本轮未重新下载全部图片字节。

作答/参考入口：`analysis_results/research_input_20260929/manifest.json`及`tools/thesis_main/data_prep/consolidate_research_input.py`的`load_current_bundle()`。必须应用审核、环序、范围增量，不能只读冻结基线。LFS真实内容入口、原始来源及图片包说明见[现有资料定位](../quality_scope_model_handoff_20261015/EXISTING_DATA_SOURCES.md)。

本次用户要求提交**本地main**，没有要求推送。因此不能假定GitHub已包含本次新增资料。新Pro应同时收到本次精简增量ZIP，按仓库相对路径覆盖到取得的仓库副本；原图与已有LFS实体不重复放入增量包。若随后同步远端，仍须核对实际文件存在，不把“本地已提交”写成“GitHub可读”。

## 本次整理的取舍

本目录中的`quality_structure_handoff_20261016.zip`是已发出的冻结交接快照，内部路径按打包时的仓库布局记录；本次主题归档没有重写这个ZIP。当前工作树里的新路径、迁移前路径和对应关系见[研究资料总目录](../../catalog/INDEX.md)及[可读迁移映射](../../catalog/MIGRATION.md)。本次资料目录整理尚未提交或推送；交接提示词里有关此前本地main的句子只记录该ZIP生成时的状态，不表示本次整理已同步。

保留当前及历史统计CSV、报告/字段合同、人工回执、必要几何、图和交付工作簿，以及已有生成代码与相关测试。保留多人/同房/融合已有研究证据，不重跑或重新命名其算法版本。

不提交三个统计目录内可由逐表CSV/生成器重建的巨型`tables.json`（合计约234MB）、独立复算的重复replay目录、服务器日志、重复上传ZIP。工作簿已保留；若要重建工作簿，应先用对应统计生成器生成本地`tables.json`。不删除这些本地材料，不重新上传原图，不改原始作答。

验证与归档清单见`ARCHIVE_MANIFEST.json`；本次检查不等于全库视觉审查或新模型效度验证。

复现限制：原参考来源核验/构造工具默认读取仓库根目录`data/external/label_data.zip`，允许`HOHONET_SOURCE_ZIP`显式配置；本机原ZIP尚未迁移；当前`reference_catalog.json`保留已确定的完整参考及来源证据，研究新分数可直接用它的固定几何。不能声称任意新环境只克隆Git就能重跑全部原GT来源审查。
