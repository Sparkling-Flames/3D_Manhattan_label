# 机制案例交付入口

本目录包含 **9 张图、32 个已在核心研究登记的唯一物理团队**，展示 51 条 AC/联盟事件。联盟的一支队伍会在多个比较中重复出现，51 条展示事件不是 51 份独立团队证据。所有案例都沿用当前 v2.1 目标、参考、人员/标注排除、楼外冻结分类和原生融合规则；机制追踪没有添加新物理团队。

## 先打开这些文件

| 入口 | 研究问题 | 阅读文件 |
| --- | --- | --- |
| 17/10/8 七联盟，高分图 | 相同结构下的位置、尺度、Q 和劳动变化；完整类别叠加 | [pa4-06 中文报告](alliance_pa4_06/REPORT_ALLIANCE_PA4_06_ZH.md)；[离线查看器](alliance_pa4_06/PA4_06_ALLIANCE_VIEWER_ZH.html) |
| 同样容量，低分图 | 全员一致的八点表达与当前四点参考不同；共同偏差不等于失败 | [pa4-11 中文报告](alliance_pa4_11/REPORT_ALLIANCE_PA4_11_ZH.md)；[离线查看器](alliance_pa4_11/PA4_11_ALLIANCE_VIEWER_ZH.html) |
| 固定九人块、换两名背景 | 身份对应、临界票和完整来源环怎样共同改变 C 队 | [wc2-53 中文报告](background_wc2_53/REPORT_BACKGROUND_WC2_53_ZH.md)；[离线查看器](background_wc2_53/BACKGROUND_WC2_53_VIEWER_ZH.html) |
| 全量结果代表组 | TARGET 整类七人换入的正/负/微变，RAW3 十二人整类换入，JOINT 十二人替换，固定十人块 n20→22 状态变化 | [代表案例报告](representative_cases/REPORT_REPRESENTATIVE_MECHANISMS_ZH.md)；[离线查看器](representative_cases/REPRESENTATIVE_AC_VIEWER_ZH.html) |

四个 HTML 都自包含原图、中文字体、完整原答、当前参考、输出和票账，无需联网。逐人勾选原答，或只看共同背景 D / 替换块；所有未选组、原答节点顺序、直接/投影连接支持和候选环均保留。缺输出时不补画虚构连接，不把缺 Q 显示成 0。

## 如何把正文数值连回原始结果

1. `CASE_EVENT_SUMMARY.csv` 给出全部案例事件 ID、方法、精确队伍、类别容量、整类标记、双方分数/分项/状态、几何与合法劳动差值。它由完整已保存 trace 中的核心端点值生成。
2. `CASE_ENDPOINT_SUMMARY.csv` 对 32 个唯一端点去重，保存组数、来源环覆盖、逐边支持、位置政策、状态与劳动来源。
3. `CASE_ALL_UNIQUE_GROUPS.csv` 对全部 252 个唯一身份组去重，保存未选组、实际支持、全部成员与原始观测 ID。
4. `CASE_ALL_COMPLETE_ORIGINALS.csv` 保存 9 个合法目标池的 311 份完整原答记录及楼外标签；包括当前事件未使用但池内合法的人员，不能把“池内”自动等于“入队”。队内精确成员始终以各事件 X/Z/D 或端点名单为准。
5. 每个案例目录的 `traces/<event_id>.json.gz` 包含事件、参考、全部池原答、两队核心标量/几何和完整原生 full_state；`trace_endpoints/` 按唯一队伍保存原生追踪。
6. `tables/` 提供逐事件/臂的全部组、逐观测成员、来源顺序、共现、连接边、备选环和共同 D 的观测对应表。`minimal_inputs/` 是每个目标单独的完整池和参考。
7. 核心端点原值来自 `../stage03_endpoints/pools/<pool_id>/part_*.jsonl.gz`；事件测量来自 `../stage04_metrics/metric_shards/<pool_id>.csv.gz`。它们以 pool、team_key、event_id 和冻结语义 identity 连接，不依赖已删除的冗余合并几何/指标副本。

## 选型、数值一致性与限定

pa4-06/-11 来自计算前按容量指定的四图集合，不因结果好坏改选。其余代表事件在全量研究完成后按保留的全部候选和规则选择：`representative_selection/`、`background_wc2_53/BACKGROUND_WC2_53_REPRESENTATIVE_SELECTION.json`。不是只取最大 Q 收益。个案的机制证据与条件覆盖比例分开；总体结论仍以完整逐图/逐楼汇总为准。

32 个端点各补充一次成功 full_state 回放，新增物理团队为 0。31 个回放的完整几何 JSON 哈希严格一致；wc2-53 背景① A 仅一个派生 footprint 数相差 1 ULP（4.44e−16），ERP 点、节点 ID/顺序、拓扑、源观测和其余几何严格一致。保留 before/after 哈希与原文件，核心原始值未被替换；追踪 candidate 另存。两个定位这一差异的诊断回放另行记录，不增加样本。核心运行 476,359 次原生端点评价的计数不包含这些机制/诊断调用。

所有导出和后处理均保存代码。`MECHANISM_METHODS_ZH.md` 解释 MV50、组内条件中位数、跨队观测对应、连接判断、单位和劳动掩码。`CASE_FACTS_GENERATION_RECEIPT.json` 记录案例源文件哈希；`CASE_DELIVERY_VALIDATION.json` 记录全文件读取、图片、CSV、JSON、浏览器验收及成员/核心机制断言。

## 人工核查位置

| 图片 | 具体位置 | 需要判断的问题 |
| --- | --- | --- |
| pa4otMbVnkk-11 | ERP u≈525–1010，参考 r2→r3 闭合段；原答 u≈553/711/832/947 外伸路径 | 对已指定的目标空间，前厅/过渡区域应沿哪条边界表达？全员一致是否仍是共同目标语义偏差？本轮不改参考。 |
| VFuaQ6m2Qom-07 | 新保留 r3（u≈992）及 r9–r14（u≈417–466）密集转折 | 新增一个角是否对应真实结构；剩余小转折应怎样完整表达？已有票账说明哪些未过票。 |
| wc2JMjhGNzB-53 | 拼接处 r3/r4（u≈16–18），以及约u939.7短接 | 新第五节点的位置解释和残留短接是否吻合目标墙体？完整输出环只有一名来源支持。 |
| S9hNv5qa7GM-04 | u≈171/223 和 u≈359/412 两对柜体/墙体竖线 | 两套互斥原答代表哪种空间边界？n20双过票、n22保留较低Q表达的机械过程已由原答/票账证明。 |

这些人工问题不会阻断现有结果交付，也不允许按更高 Q 自动改空间归属。`validation_only/` 是旧端点开发测试，正式压缩包应排除该目录，避免误认为新研究案例。
