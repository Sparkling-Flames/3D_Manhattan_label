# 图片难度v1分析交接

2026-10-17。已完成261图人工粗类与当前共同评分的人员内、场景、时间、低尾及不可计算分析。主入口[README](README.md)，可复算工具`tools/thesis_main/analysis/difficulty_v1_analysis_20261017.py`，重要边界测试`tests/test_difficulty_v1_analysis_20261017.py`。当前文件仅为数据v1下新增分析修订，数据v1冻结包不改。

输入：`research/data/releases/v1/RELEASE.json`、`research/quality/quality_b8l2_d10_20261017/CROSS_MODULE_INPUTS.json`、同包`shared_records.csv`和`difficulty_records.json`。身份键`object_id`，1911份质量可用记录的`rescore_target_id`与该图人工难度`target_version`均相同。B8L2是工作主指标；D10只改方向尺度8°→10°，同一资格面板。Manual和Semi分开，门洞×OOS保留交集，OOS仅数值诊断。图级至少3名来源池、GT与人工暂停等门沿共同包，不在本模块放宽。

原261标签、新空间、原GT、清洗、绑定、评分公式及共享资格未改。部分难度标签看过作答，质量梯度不能作独立验证。逐人配对是不同图的同人员观察，不是固定图片的随机化难度实验。来源任务时间与同目标审计时间并列，缺失不补0。失败、缺参考、仅底面、未绑定保留分母。

验证：`python -m pytest tests/test_difficulty_v1_analysis_20261017.py -q`，3 passed；`python -m tools.thesis_main.analysis.difficulty_v1_analysis_20261017`，库存3222／261图／27身份、质量1911及四计算状态闭合；生成的三张图已目视检查。未跑全库测试：仅新增本模块消费者，未修改共享评分、协议或采集代码。没有临时截图残留。

融合过程消费已更新至当前完整发布：237池尝试、233池/208图完成、4池输入问题；消费修订`v1_complete_measurement_cache_main_panel_r2_20261017`。原104普通Manual图、k=3/4/6的312行未重写，公共字段逐值与当前融合一致。阶段发布/等待状态存于`history/pre_doorway_r1/`，不再作为当前状态。门洞17图随机过程及15图主资格面板已经展开，见[门洞报告](doorway/README.md)与[CROSS_MODULE_INPUTS](CROSS_MODULE_INPUTS.json)。

目录登记待统筹统一整合：`research/difficulty/difficulty_v1_analysis_20261017/README.md`、`tools/thesis_main/analysis/difficulty_v1_analysis_20261017.py`、`tests/test_difficulty_v1_analysis_20261017.py`；检查`research/catalog/CATALOG.json`及生成目录、`docs/README_INDEX.md`与`docs/PROJECT_MAP_CLEAN_20260308.md`。本轮只检查地图定位，未并发改全局文件。不提交、不推送。


## 门洞本轮新增交付

门洞库存246份/20图（含23份门洞×OOS），质量188份/15图/24人；17图808随机前缀、703完整几何、655主质量、59完整来源时间。固定k=1/3/4/6的17图机会与15图主资格分开，N≥8为14机会/13主资格，N≥12为4机会/4主资格，各面板带自身早期k基线。三张科学图已生成，人员内对照、低尾、时间及反例、四个已有证据案例均有底表。本轮用户人工裁决清单为空。

复算入口新增`tools/thesis_main/analysis/difficulty_doorway_v1_20261017.py`；定向测试新增`tests/test_difficulty_doorway_v1_20261017.py`，验证机会分母保留失败和诊断节点，主质量不混诊断。辅助WQ/损失字段r2载荷已接入并逐项核验；本轮仍只解释既定核心主分与几何字段，未新增辅助分项分析。不改共享融合、参考、资格、release或人工类别。

展示台直接读取本包`CROSS_MODULE_INPUTS.json`，所有门洞表位于`doorway/`。目录与地图登记仍由统筹处理，新增工具/测试路径同上。未提交或推送。

本轮实际验证：`python -m pytest tests/test_difficulty_v1_analysis_20261017.py tests/test_difficulty_doorway_v1_20261017.py -q`，4 passed。门洞构建完成并校验246/20、188/15/24、17/808、703完整/655主质量/59时间；固定17/15的每k机会与可用计数对账一致。104图312行未重写并与现行公共字段一致；四个案例原图路径均存在，三张新增科学图已目视核验。未跑全仓测试，因仅新增本模块消费者及状态同步；当前r2辅助载荷与源一致，新增4条失败原因已同步；不因数值一致宣称来源未变。统计可直接读`CROSS_MODULE_INPUTS.json`；确需用户人工裁决：无。

## r2最小消费同步

实际消费修订为`v1_complete_measurement_cache_main_panel_r2_20261017`。已按pool_id/path_id/k核对808节点的75个源字段；辅助数值此前即与r2一致，只有4条失败原因由空值恢复。仅补这4条原因并同步SOURCES、接口和文档；原104图312行公共字段再次核对一致，既有摘要、曲线和数值结果未重算。差异及核验见`doorway/VERSION_SYNC.json`、`doorway/r2_reason_changes.csv`，同步前文件存于`history/pre_fusion_r2_source_sync/`。辅助载荷已接入与开展辅助分项研究是两件事，本次未新增后者。无用户人工裁决需求。

R图显示修正：仅增加R轴上方12%留白并重生成`doorway/doorway_process.png`；全部门洞CSV字节未变，已目视确认k3/k4点完整显示，门洞定向测试1项通过。正式交付图保留，未重跑分析。
