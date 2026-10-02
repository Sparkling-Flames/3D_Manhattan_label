# 固定池曲线精度补强：研究与复算入口

2026-10-03。用户确认的两条线为A“粗难度与人数曲线”、B“人员类型、构成与具体成员的不确定性”。人员/图片效应模型按需使用，不是前置。详见[推进台账](../../docs/thesis_main/研究推进台账_20261003.md)。

本包不复制旧固定输入和整套外部审查附件，只保留必要的数值对照。所有新计算从[10/2固定输入](../lee_tile_stage1_20261002/input.json)开始，代码复用原tile核心，不直接把外部结果表当成本轮结果。

## 本轮工件

- [新结果与边界](../../analysis_results/lee_tile_precision_20261003/REPORT.md)、[参考均值曲线](../../analysis_results/lee_tile_precision_20261003/reference_means.png)。
- [代码](../../tools/thesis_main/analysis/lee_tile_precision_20261003.py)、[针对性测试](../../tests/test_lee_tile_precision_20261003.py)。
- 输出目录的 `design.json` 在计算前记录固定设计、完成后标记completed；`curves.csv`区分exact/MC，`field_contract.json`定义字段；`orders.npz`和`rosters.json`保留完整抽样成员顺序。
- `raw_disagreement.csv`保留原始作答分歧，`coverage.json`保留195=177+18分母，`warnings.json`与`validation.json`保存数值情况。

## 外部证据来源与用途

用户于2026-10-03提供Pro包 `lee_stage1_independent_20261002` 和dot包 `lee_tile_independent_review_20261002`。完整附件保留在用户原Downloads目录；本仓库不复制重复输入、源码和所有复算目录。

- Pro主要独立复算一组8人、255子集；其意见不直接升级为本项目结论。
- dot扩展12图，精算4554子集，另提供全人数解析面积。其 `lee-audit-exploration/results/exact_iou_vs_16.csv` 原数表保存为 [review_exact_iou.csv](review_exact_iou.csv)，166个精确参考切片。
- 同目录的 `all_k_expectations.csv` 原数表保存为 [review_area_expectations.csv](review_area_expectations.csv)，492个解析参考切片。
- 本地已独立核对上述数值，当前实现再次从固定输入计算后对照；这两个CSV仅作历史证据和验证目标，不参与新MC采样、投票、均值或阈值选择。二者原字段名称保留，含NOT_expected_iou的列不得当平均IoU。

## 复算

依赖沿[原执行环境](../lee_tile_stage1_20261002/environment.json)，无需增加依赖。从仓库根目录执行：

```powershell
python -B -m pytest tests/test_lee_tile_precision_20261003.py tests/test_lee_tile_stage1_20261002.py tests/test_supervisor_gt_sensitivity_20260922.py tests/test_consensus_contract_20260923.py -q -p no:cacheprovider
python -B -m tools.thesis_main.analysis.lee_tile_precision_20261003 --out analysis_results/lee_tile_precision_recomputed
python -B -m tools.thesis_main.analysis.render_paper_a_method_contract --check
```

研究解释报告和外部证据对照记录为交付时审核材料；运行命令重新产生数值、设计、字段合同、成员顺序与图，不自动改写人工研究结论。

## 精度含义

本轮预定16384次独立均匀排列及0.02参考均值计算分辨率；全部326个MC参考均值采用Hoeffding界和union bound控制95%同时计算误差，界为约±0.01701。该选择是计算预算和分辨率，**不是**有研究意义的差值、真实人员抽样区间、人员分类阈值或最佳人数。

大组中间人数保留重复抽中成员集的出现频次，以维持独立排列平均的误差界；原16排列的去重均值保留历史结果，两者目标均为均匀固定池子集均值。小组及大组端点全枚举。均值精度不自动覆盖分位数、相邻Jaccard或成员Jaccard；原始分歧也不等于融合稳定性。

新算法只做离线积分：全员边界划分得更细，不改变子集投票集合；用当前成员重新切tile核验等价。禁止把这项优化声称为已观察未来人员的在线预测。GT只评价，未改坐标、环序、资格、参考或原融合方法。
