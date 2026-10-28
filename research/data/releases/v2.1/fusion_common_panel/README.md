# v2.1 参考下的固定融合方法面板

沿用 2026-10-24 固定共同面板：48 池、138 支实际团队，各队的墙线自动融合、无 GT medoid 和 Lee 底面均复用原保存几何与原选择；未新增选队、融合或 medoid 选择。仅对参考受影响的 9 池、81 条方法记录更新评分和底面诊断，其余 333 条记录原样保留。原参考逐条复算核对 81 条，通过后才计算新参考。

完整输出、底面输出及共同可评支持不变；三法共同底面仍为 131 队，完整／底面共同指标的 2,220 条比较身份完全一致。Lee 只提供底面区域，其顶部和完整三维评分保持不适用。原团队、人员、方法和分层身份均未改变。

普通 Manual 的墙线减 medoid 平均 B8L2 差，在 n=4（22 队）、n=8（22 队）、n=16（23 队）分别由 +7.108、−0.515、−5.545 变为 +7.109、−0.533、−5.567 分。这是预先固定面板的同队比较，不是全库随机胜率。

`METHOD_ENDPOINTS.csv` 保存全部方法记录；`COMMON_TEAM_METRICS.csv`、`COMMON_IMAGE_METRICS.csv`、`COMMON_BUILDING_METRICS.csv` 与 `COMMON_SCENE_SUMMARY.csv` 为原方法同队／同图／同楼汇总；`THREE_METHOD_COMMON_FLOOR.csv` 为三法共同底面域；`COMMON_SCENE_SUMMARY_OLD_V21.csv` 为对应分层的新旧参考对照。验证结果见 `CHECKS.json`，几何原件仍在 `research/fusion/fusion_common_panel_20261024/METHOD_GEOMETRY.json`。

执行：`python -m tools.thesis_main.analysis.rescore_v21_fusion_common_20261029`。本结果保留旧面板的旧场景与难度分层，不借此推广到新增池。
