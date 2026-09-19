# 局部点、配对与时间研究：本地接收及独立核验

**当前接续：**下述“按x待验证”为上一轮准备时点；按序全量研究已完成[接收与核验](../paired_split_research_received_20260920/README.md)。当前优先[轻量人工复核、收束分簇并准备分析成稿](../../docs/thesis_main/Pro下一轮_分簇定稿与分析准备_20260920.md)，不继续将复杂方法开发作为主线前置条件。

**2026-09-20 Pro续研准备：**[任务、六张补充视觉证据与云端资料](pro_followup_20260920/README.md)。复用Studio基础制作独立专项页，两个子代理独立复核4图，另2图为对照；按x顺序比较及人员异常分析仍待Pro研究，不冒充已验证。

这是探索性复算入口，不是正式分簇标准或停止规则。原始点、人工裁决、原导出、active-time日志和正式SOP未改。

**六图点对初验及审核已完成：**[结果、用户原件与研究澄清](pair_pilot/README.md)。两项相近、四项保留差异，A/B均接受候选1。先前比较是自由最优匹配，用户明确的按x顺序逐项比较仍待验证；单人簇讨论已关联探索SOP。后续复用示范基础制作专用审核页，不再向旧页追加。

先读[独立审查与研究方向](独立审查与研究方向.md)。Pro原报告为[REPORT_ZH.md](REPORT_ZH.md)，保留原文；其中概率与“新局部”的关系、跨环境精度问题，以独立审查补充解释。

## 本地执行

在仓库根目录运行：

```powershell
python -m tools.thesis_main.analysis.local_point_research
python -m pytest tests/test_local_point_research.py tests/test_extra_cluster_review.py -q
```

可传`--input-root`和`--output`。输入清单逐文件核对，默认输出`local_recheck/`，不覆盖原包`received_results/`。旧arccos计算保留用于历史对照，稳定弦长公式另列敏感性，不在原距离中偷偷加阈值容差。

源码在[tools/thesis_main/analysis/local_point_research](../../tools/thesis_main/analysis/local_point_research/)。迁入8个数值模块，保留其原算法，调整包导入、UTF-8和输入/输出路径；一个共同入口运行。新增`audit_extensions.py`独立核对匹配、有限池公式、点并集含义，复用既有冻结解析器重查配对警报，并复算上轮已通过来源审计的时间基线。没有新增审图界面、模型、尺度学习或依赖。

## 有用内容如何接续

|来源|已接入的本地能力|保留边界|
|---|---|---|
|此前全量与39图研究|原先已接收的输入、源码、模型比较仍在`full_corpus_research_received_20260918`与`cluster_visual_20260918_v2`；本轮复用冻结配对函数|不重复复制全套数据，不替代正式协议|
|上一轮配对研究|全量同侧配对警报可在新入口重算；原替代配对及消融代码、行级警报归档于`previous_pairing_time/`|本轮未重新执行所有配对消融，也未自动重配24份记录|
|上一轮时间研究|来源资格记录、4份不一致证据保留；楼外人员基线及同图目标作答留出可重算|本轮复用上轮已审计来源，不冒称重新读取全部原始日志|
|本轮局部研究|OSPA1/2、双向最近邻、半径匹配、瓶颈、完整链接、真实代表分组、逐点证据、原奇数点敏感性、固定池事件、跨视角时间比|所有配置均探索；不同问题分开输出，不选算法冠军|

接收了数值输入、25份原CSV、原脚本、原报告及本次实际查看的3幅已有叠加图。没有复制整套原图、独立图册或制作交付网页的依赖，因此此目录是**可运行数值子集**，不是完整原ZIP的替代。`source_code/`保留原代码用于对照，受支持的执行入口是上述仓库模块。

`RECEIPT.json`记录接收来源；原包126文件清单核验通过。`inputs/`是来源已记录的冻结研究快照，不是新的运行时真源；未来新数据应从`export_label/`、`active_logs/`和已确认恢复记录重新准备，不向此快照追加。

## 输出口径

- `pairwise.csv`：同图同条件的真实作答对；角距离单位为度。`matched_r`是半径内最大一一匹配数，未匹配不自动等于漏标。`bottleneck`不同点数时缺失，不能填零。
- `memberships.csv`与`exemplar_memberships.csv`：前者为完整链接，后者为真实代表覆盖。簇号只在各方法、各单元内有意义；代表覆盖不保证两两相近。
- `next_person_diagnostics.csv`：有效点版本；`no_borrowed_next_person.csv`：两份历史补点恢复原9/11点的独立敏感性。事件是随机目标与前k人中是否存在相容的**完整作答**。
- `independent_union_point_expectation.csv`：目标点未被前k人所有点的并集覆盖的**期望比例**；不是至少出现一个新点的概率，也不是新语义比例。`independent_union_counterexamples.csv`给出两种事件不等价的真实数值例子，尚非视觉裁决。
- `reviewed_point_witnesses.csv`：原冻结有效点数组中的序号；最近邻和某个最大匹配解都不等于物理角点的唯一对应。人工原文字段不产生整图必须异簇的真值。
- `same_person_time_*`及`independent_same_image_time_predictions.csv`：合格active time的历史预测检查；不使用lead_time，不推断认真程度。
- `REPRODUCTION_CHECK.json`：逐表差异明示。`INDEPENDENT_CHECK.json`：独立核验范围。**不能把“全阶段运行完成”写成“25表逐项相同”。**

本地缓存和日志可通过入口再生。原包结果与本地结果分别保存；未推送GitHub。
