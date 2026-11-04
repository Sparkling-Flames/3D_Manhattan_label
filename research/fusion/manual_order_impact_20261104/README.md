# v2.1 人工融合顺序与全链影响交付

<!-- SECOND_ACCEPTANCE_20261104_BEGIN -->
## 第二次独立验收入口

本目录保留前五批的自动/辅助科学结果。[第二次验收与重跑判断](../manual_order_acceptance_20261104/REPORT_ZH.md)补齐了固定208事件内Q-only的完整机会分母、AC全部翻向和实际消费者验收。唯一覆盖修正是有限配比两份标量表中8个成员字段单元及对应生成代码；科学数值、成员内容和顺序保持。原批次校验清单保留历史身份，当前覆盖差异以[第二次验收覆盖表](../manual_order_acceptance_20261104/PARENT_OVERLAY_CHANGES.csv)为准。

AC 的定向 57 组不覆盖全部登记对手。当前可评支持的数值验收通过，但完整登记队列的同等人工处理和精确完整均值不能声称完成；RAW3 其它目标 n=m=4 为 13/16，另 3 个缺失端点的合法 Q 界限仍保持负方向，未以极值替代实测评分。
<!-- SECOND_ACCEPTANCE_20261104_END -->

入口：[完整中文报告](REPORT_ZH.md)、[逐条结论](CONCLUSION_MATRIX.csv)、[模块影响矩阵](MODULE_IMPACT_MATRIX.csv)、[离线研究台](../../statistics/research_explorer_v1_r2_20261017/v21-manual-order.html)。

基线仓库提交：`ac395e703d1fef573d1ef3e105df0286d62a0468`。任务标识沿用用户回收目录`20261104`，不代表本轮重新冻结实验设计。方法身份为额外定向人工辅助；原自动数据和分母保持。57组固定坐标主分支56可评、1失败；F2/F9坐标候选独立记录且未并入主分支。缺失Q不按0，人工劳动未知。

## 文件组织

|目录|内容|主要入口|
|---|---|---|
|endpoints|57组固定节点辅助几何、完整评分、原自动对照和参考绑定|[README](endpoints/README.md)|
|preprocessing_audit|完整预处理、用户先前编辑、点对、源索引及融合节点核查|[报告](preprocessing_audit/REPORT_ZH.md)|
|dependencies|558源表复读、536引用、间接依赖及未命中模块|[检查](dependencies/CHECKS.json)|
|half_qonly|当前/冻结ABC、50%换人、Q-only、难度、同XYZ、原劳动及30图反例|[报告](half_qonly/REPORT_ZH.md)|
|same_room|当前/原native同房、六端支持、角点、图对、成员和历史Q消费者|[报告](same_room/REPORT_ZH.md)|
|ac|AC及真实敏感性、共同池/背景、三段、状态漏斗和strict桥|[报告](ac/REPORT_ZH.md)|
|alliances|标签快照×连接版本的纯类/全员、403可执行项与支持选择变化|[报告](alliances/REPORT_ZH.md)|
|composition|67有限面板及11冻结方法的配比/成员方差|[报告](composition/REPORT_ZH.md)|
|natural|两个其它目标、重复路径、均值/P10/波动、固定窗口及消费者|[报告](natural/REPORT_ZH.md)|
|policy|一条旧角色前缀和真实后段路径/建筑bootstrap依赖|[报告](policy/REPORT_ZH.md)|
|coordinate_candidate|F2/F9用户指定x平均的独立几何和分数|[README](coordinate_candidate/README.md)|
|ac/coordinate_candidate、alliances/coordinate_candidate|坐标候选的52条实际下游引用|[AC候选](ac/coordinate_candidate/README.md)|

CSV含自动/人工、标签版本及支持字段；不能将`frozen/updated`标签快照当作连接版本。`.gz`是标准gzip，均可由Python、R等读取。原始大表依照仓库现有大文件恢复方式保留，ZIP交付不是全仓库克隆。

## 复现顺序

在源提交对应的完整仓库中叠加交付文件。所有命令从仓库根目录运行；Python和数值依赖的实际版本见`endpoints/SCORING_ENVIRONMENT.json`，各模块CHECKS记录冻结统计实现和参数。

Windows PowerShell先设置`$env:PYTHONUTF8 = "1"`，确保中文CSV、JSON和报告统一使用UTF-8；以下采用`python -m`包入口，不直接执行含相对导入的脚本路径。

1. 端点：`python -m tools.thesis_main.analysis.apply_manual_ring_orders_20261104`。仅读用户确认的绑定，重建缺失几何、按原参考评分，不重新选择节点。
2. 预处理核查：`python -m tools.thesis_main.analysis.audit_manual_order_preprocessing_20261104`；依赖核查：`python -m tools.thesis_main.analysis.evaluate_manual_order_dependencies_20261104`。这些检查不修改输入。
3. 独立候选端点：`python -m tools.thesis_main.analysis.evaluate_manual_coordinate_candidate_20261104`。联盟脚本在主统计之后还生成单独候选比较，故从零复现先准备该文件。主端点文件始终保持固定坐标结果。
4. 各模块用包入口运行，例如`python -m tools.thesis_main.analysis.evaluate_manual_order_natural_20261104`、`python -m tools.thesis_main.analysis.evaluate_manual_order_policy_20261104`、`python -m tools.thesis_main.analysis.evaluate_manual_order_alliances_20261104`、`python -m tools.thesis_main.analysis.evaluate_manual_order_composition_20261104`。AC、半队及同房的详细参数/阶段和源表见对应模块报告与CHECKS。必须先有端点评分再聚合，不能把全模块任务改为全库融合；候选传播仍独立保存在候选子目录。
5. 统计完成后运行`python -m tools.thesis_main.analysis.summarize_manual_order_selected_statistics_20261104`生成natural/policy/alliances报告、结论及完整性清单；该命令不重跑策略bootstrap。
6. 索引：`python -m tools.thesis_main.analysis.assemble_manual_order_delivery_20261104`。该程序仅汇编已检查结果的版本合同、结论索引和模块矩阵。
7. 研究台：`python -m tools.thesis_main.analysis.build_manual_order_workbench_20261104 --images PATH_TO_22_ORIGINAL_IMAGES`。输入为本地的`v21-manual-order/original_images`，不会加工图片或运行评分；输出为同目录静态JS/原图。直接打开HTML即可离线查看。按要求，22张原始全景图保留在本机但不上传GitHub；云端仓库副本因此不含这些图，克隆后须另行放回该目录才能显示原图。

## 分批叠加与验收

按批号将ZIP内的仓库相对路径叠加到`D:/Work/HOHONET`，最后一批为文档、研究台及最终验收/更正；不删除原自动结果目录。每包包含文件哈希清单和批次说明，原已交付ZIP不回写。最终包中的回执/说明优先于较早批次的过程性回执。

最终实际检查见[FINAL_CHECKS.json](FINAL_CHECKS.json)、[独立复核](INDEPENDENT_REVIEW.md)、[浏览器回执](WORKBENCH_CHECKS.json)。如有已交付回执元数据的更正，单列`CORRECTIONS_20261104.md`，科学数值变更与回执字段修正分别说明。
