# 本模块交付与接入说明

完成 v2 普通场景同房 Q/T 描述、留建筑预测和固定目标面板人数实验。新增一份分析脚本、一份测试文件及本研究包；未修改原始数据、共享评分、人员类别、融合、protocol 或历史结果，未提交或推送。

验证：`python -m pytest tests/test_same_room_v2_prediction_20261019.py -q`，5 项通过。分析执行中的评分一致性和分折检查通过；交付后检查 OOS/门洞排除、训练准入、固定 k 面板和 B8L2/D10 评价成员；两图目视检查通过。详见 VALIDATION.json。未运行全库测试，因改动为独立研究消费者；未重算旧几何或全库融合。

已检查项目地图与 README 索引。本包是现有 same_room 主题下的探索性支撑资料，不改变正式协议入口。依此前多线程分工，全局目录、地图和统一入口由统筹线程同步，本任务未覆盖这些已有并发修改的公共文件。**待统筹登记**：`research/same_room/same_room_v2_prediction_20261019/CONSUMER_INTERFACE.json` 及 README.md 到 `research/catalog/CATALOG.json`，随后运行 `python -m tools.thesis_main.analysis.build_research_catalog --write` 与 `--check`。本次不声称全局目录同步已经完成。

关键限制：同房条件预测有增益不等于同房特异性已被证实；新增人员个体迁移增益较弱，存在负增益建筑；人数实验只有 10 栋建筑、3 次抽样，尚无独立外部验证或置信区间。新增源耗时与严格目标匹配耗时必须分开。人员分类待验收后再接入。
