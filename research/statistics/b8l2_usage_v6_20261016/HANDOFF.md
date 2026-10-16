# 新用途统计交接

2026-10-16。父级[CROSS_MODULE_INPUTS.json](CROSS_MODULE_INPUTS.json)为精确输入，旧共享1622用途保留。本版固定输入与原B8L2参数，实际全库存检查几何，对唯一目标完整参考的2594份原作答完成冻结计量；46份只有底面结果且完整参考待定。

**后续人工房间分类采用已更新：** 当前详细统计为[details_room_adopted_v3](details_room_adopted_v3/README.md)，直接消费同房线程`same_room_user_working_classification_20261016_v2`。260原组已完整人工查看，缺少唯一全库物理ID或未点status不再构成统计缺项；原组、259个拆分/合并工作单元及777直接关系分别保存。旧details/21页保留为严格层历史。下文关于首次21页的描述保持当时交付身份。

## 实际改变与边界

新增用途政策及台账、覆盖和细致描述，明确门洞可用188、OOS只诊断。新质量1787=1599保留+188门洞，移出旧OOS23。主数据、原作答、GT、CURRENT、预处理点及评分参数均未改。目标不是按分数反选；10条明确scope hold与6条未确认门洞继续待目标。质量用途更新与原正式合同/采集准入分开，旧事实不追改。

新工具为`b8l2_usage_snapshot_20261016.py`、`b8l2_calculation_status_20261016.py`、`b8l2_usage_coverage_20261016.py`、`b8l2_detailed_views_20261016.py`、`b8l2_detail_summary_20261016.py`、`b8l2_room_descriptions_20261016.py`、`b8l2_usage_figures_20261016.py`及`b8l2_detailed_workbook_20261016.mjs`，全部位于`tools/thesis_main/analysis/`。复用既有冻结评分、来源池、同房和统计重建实现，未另造能力模型。

逐条台账覆盖3152，人员库存27/分析25，图片259；人员×难度/场景、关系组、直接图对、缺口导航以及边际与共有时间统计实际落盘。所有GT参照OOS指标只存诊断；其合法时间、行为与来源记录不因质量不可用而被删除。新用途中正常质量字段只对`quality_usable`填值。

五组科研图已生成PNG/SVG/CSV并逐图视觉核验，空质量面板明确标注无可用数据；图序按身份和类别，不作人员能力排名。21页工作簿与原生覆盖图均已视觉核验，26张临时QA图片及预览目录已删除；主线程再次确认预览目录不存在，验证JSON记录`current_usage_ready`及全部页面通过。

## 验证

主线程执行如下定向测试，33项通过：

```powershell
python -m pytest tests/test_descriptive_snapshot_inputs_20261015.py tests/test_b8l2_detailed_views_20261016.py tests/test_b8l2_room_descriptions_20261016.py tests/test_b8l2_usage_coverage_20261016.py tests/test_b8l2_calculation_status_20261016.py tests/test_b8l2_usage_figures_20261016.py tests/test_b8l2_usage_snapshot_20261016.py -q
```

覆盖新批次/人员/图片/算法接入、版本和参考冲突、实际几何边界、门洞纯场景门解除、明确hold保留、OOS遮罩、计数去重、共有时间、条件分层和权重。独立数据核验见[audit/USAGE_SCORING_AUDIT.md](audit/USAGE_SCORING_AUDIT.md)：逐条重建3152状态/用途，全量几何和1599保留值核对，6条冻结引擎直接复算，以及3940格细致汇总复算均通过；没有另行重算全部2594数值。共有时间1107=旧1042+新门洞82−移出OOS17。图表清单见`figures/`，工作簿验证见`details/`。全部本包Markdown本地链接检查通过。此前共享版的31项检查及旧数值审计保留在旧目录，不冒称本轮重新全库测试。

## 地图、资料目录与剩余工作

已检查`docs/PROJECT_MAP_CLEAN_20260308.md`和`docs/README_INDEX.md`，它们目前登记旧共同版。按本次统筹写入边界暂不修改全局入口或catalog，工具、测试和产物已由统筹登记；[REGISTRATION_PENDING.json](REGISTRATION_PENDING.json)作为历史接入回执保留，当前目录校验见`research/catalog/INDEX.md`。

未重新人工认定所有物理房间、未补29份完整参考、未解决全部待目标作答、未训练人员能力或执行新的融合/同房预测实验。下一步安全接续是按台账补充有证据的目标/参考，另起输入/用途版本后更新下游；新采集、新算法与新参考不能覆盖本快照。工作区其它线程已有修改保持原状，未提交或推送。

上述首次交付的“未重新人工认定”不是缺完整人工分类：现已按用户明确要求直接使用已有完整分类，未索要重复认证。新版每工作单元397格/人员×工作组2651格/逐视角429格；原组总体400格/人员×原组2668格/逐视角430格，含无当前库存的显式n0行。状态纠偏测试先失败再实现，房间描述/详细统计/统一关系采用15项定向测试通过。评分与时间逐条保持，原分类不回写；新关系统计及24页工作簿与旧严格层分开，临时截图核验及清理由新版验证文件记录。

最终关系输入为冻结v2，替代v1开发阶段。只更新关系标签和证据，分组成员及所有统计数值逐项保持，未重算无关统计；75条直接边由其它范围转入已有分类可比层，最终逐对381可比/291其它范围/67不支持/36待定/2具体争议。统一manifest与三份关系资料按原字节归档在新版`relation_inputs/`，和交付时的冻结源逐文件相同；完整记录见`RELATION_FREEZE_ADOPTION_AUDIT.json`。此关系层采用不改变OOS诊断用途或评分准入。
