# 图片难度v1分析交接

2026-10-17。已完成261图人工粗类与当前共同评分的人员内、场景、时间、低尾及不可计算分析。主入口[README](README.md)，可复算工具`tools/thesis_main/analysis/difficulty_v1_analysis_20261017.py`，重要边界测试`tests/test_difficulty_v1_analysis_20261017.py`。当前文件仅为数据v1下新增分析修订，数据v1冻结包不改。

输入：`research/data/releases/v1/RELEASE.json`、`research/quality/quality_b8l2_d10_20261017/CROSS_MODULE_INPUTS.json`、同包`shared_records.csv`和`difficulty_records.json`。身份键`object_id`，1911份质量可用记录的`rescore_target_id`与该图人工难度`target_version`均相同。B8L2是工作主指标；D10只改方向尺度8°→10°，同一资格面板。Manual和Semi分开，门洞×OOS保留交集，OOS仅数值诊断。图级至少3名来源池、GT与人工暂停等门沿共同包，不在本模块放宽。

原261标签、新空间、原GT、清洗、绑定、评分公式及共享资格未改。部分难度标签看过作答，质量梯度不能作独立验证。逐人配对是不同图的同人员观察，不是固定图片的随机化难度实验。来源任务时间与同目标审计时间并列，缺失不补0。失败、缺参考、仅底面、未绑定保留分母。

验证：`python -m pytest tests/test_difficulty_v1_analysis_20261017.py -q`，3 passed；`python -m tools.thesis_main.analysis.difficulty_v1_analysis_20261017`，库存3222／261图／27身份、质量1911及四计算状态闭合；生成的三张图已目视检查。未跑全库测试：仅新增本模块消费者，未修改共享评分、协议或采集代码。没有临时截图残留。

融合过程已接入`research/fusion/wall_consensus_v1_process_20261017/`的已完成池。首次读取时233/234池完成、1池失败；锁定104普通Manual图的k=3、4、6真实路径，`fusion_panel.json`保存身份，`fusion_fixed_pool_k.csv`、`fusion_fixed_panel_summary.csv`和`fusion_k3_to_k6.csv`保留逐池证据及失败/缺分分母。融合源标记为部分发布，不把历史18图终点或随机路径次数当独立图片。未来若失败池修复或更新人员Q/T组合，另记面板/分析修订；本轮不静默更换104图。门洞、Semi、OOS及范围不兼容单列，尚未在本包展开人数关系。

目录登记待统筹统一整合：`research/difficulty/difficulty_v1_analysis_20261017/README.md`、`tools/thesis_main/analysis/difficulty_v1_analysis_20261017.py`、`tests/test_difficulty_v1_analysis_20261017.py`；检查`research/catalog/CATALOG.json`及生成目录、`docs/README_INDEX.md`与`docs/PROJECT_MAP_CLEAN_20260308.md`。本轮只检查地图定位，未并发改全局文件。不提交、不推送。
