# 当前口径统计交付与复现

2026-10-15。按后续明确授权执行CURRENT v3、同条件至少3名有效真人来源池、GT／既有排除及当前参考匹配。旧`research/descriptive_statistics_20261015/`及其836／931／1145报告、工作簿和八图未覆盖；本目录是独立新快照。

## 实际结果

- 库存3152条／259图，259×3条件共777个来源池；不把GT、修订GT或融合计成人员。
- manual：232个已有作答池→190池至少3有效真人→184池通过图级门→153个普通难度池。semi为43→43→43→40；OOS为9→9→9→0。普通合计193个图×条件池，对应170个不同图片；206只是原普通难度候选。
- 42个有作答的待补人池：40个1—2有效人，2个零有效人。人数、GT及其它暂停原因交叉保留，不能靠补人解除GT或范围限制。
- 39个新空间的来源全部核对，33旧registry＋4本日增量＋2既有delta，完整顶界均待完备；两修订GT另保留新坐标。旧1145条中985条几何兼容并不等于获准分析；160条列为待参考处理／重评。
- 当前完整Q807条：manual768条／67图／24人，semi39条／3图／18人。旧836仅保留768、移除68、无新增；旧931保留768、移除163、无新增。历史原分单列，未给新范围换标签复用。
- 2834条来源池合格作答中，有效采集时间1750条；当前参考资格相容且有时间的440条另列。新空间的采集时间没有解释为完成新目标的耗时。`inventory_all`保留的是未套图片门的库存时间，不能拿它替代分析时间。
- 特殊／待定层保留来源和时间，本次当前完整Q为0覆盖。普通manual同房图先过来源池门，逐图对共同人数另报，保留1／2人的共同子集，没有修改合格图片的k=1／2人数轨迹。

## 入口与改动范围

主生成器 `tools/thesis_main/analysis/descriptive_statistics_current_20261015.py` 调用来源池门、参考审计、当前报告模块，另有当前绘图和工作簿生成器。字段、所有清单和原来源指针见[字段合同](FIELD_CONTRACT.json)、[当前目标](current_images.csv)、[逐条审计](record_audit.csv)、[独立审计](INDEPENDENT_AUDIT.md)。

```powershell
python -m tools.thesis_main.analysis.descriptive_statistics_current_20261015
python -m tools.thesis_main.analysis.descriptive_statistics_current_figures_20261015
```

主入口支持`--out`。难度版本或人数规则版本改变时，禁止覆盖既有快照，必须另取输出目录。新增批次仍须先经正式loader及必要审核，来源池门与参考匹配重新判断；原版本化算法接入口不自动赋予当前分析资格。

工作簿使用捆绑Node及已配置依赖的本次可视化目录，运行 `tools/thesis_main/analysis/descriptive_statistics_current_workbook_20261015.mjs`；实际24页、一个原生图、2,373,987字节。CSV保留被工作簿精简的完整字段，工作簿不反写源数据。六组科研图保留PNG、SVG和数据CSV，见[图册](figures/FIGURES.md)。

## 验证

```powershell
python -m pytest tests/test_descriptive_pool_gate_20261015.py tests/test_descriptive_reference_audit_20261015.py tests/test_descriptive_statistics_current_20261015.py tests/test_descriptive_statistics_current_figures_20261015.py tests/test_descriptive_same_room_20261015.py tests/test_descriptive_inventory_20261015.py -q
```

18项通过。重点覆盖真人去重／条件隔离／排除作答不凑人数、GT及旧暂停优先、仅底面不放行完整参考、参考或输入变化不复用原分、当前指标和历史原分分离、版本规则变化不覆盖旧目录、时间来源及同房配对。

独立复算777池人员集合、807条质量输入／参考／当前目标及原四分数、121行汇总、2421行人员对照、3780行同房逐指标配对，全一致。工作簿24页及原生图25张QA预览逐一查看后清理，公式错误搜索0命中；六幅正式科研图逐张目检并保留。[工作簿验证记录](WORKBOOK_VERIFICATION.json)。

同步文档总索引、项目地图、统一状态第3.1／7节、术语、数据说明、模型及Agent入口；只登记当前正式入口，逐CSV由字段合同索引。旧历史文字和旧数值不追改。未运行全仓库历史测试、模型训练或新融合实验，因为没有修改这些消费者；正式合同、人员资格、源标注和人工审核未改，未提交或推送。

剩余问题仅保留实际未决：GT错误待修复、新空间顶界与逐作答目标相容性、两修订参考的重评分、低人数池待补人。既有22处局部难度分歧没有按分数或预期自动改类，不要求重复已完成的空间审核。
