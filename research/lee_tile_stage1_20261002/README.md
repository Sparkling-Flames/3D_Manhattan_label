# Lee tile 第一阶段：分步研究入口

2026-10-02。本轮只回答：固定已审核的几何解释和等权区域投票后，增加不同真人，融合区域、成员差异及固定参考距离怎样变化？先不将人员类别、图片难度、质心权重和三维参数一起放入分析。

## 当前材料

- [结果报告](../../analysis_results/lee_tile_stage1_20261002/REPORT.md)、[参考曲线](../../analysis_results/lee_tile_stage1_20261002/reference_curves.png)、[稳定性曲线](../../analysis_results/lee_tile_stage1_20261002/stability_curves.png)。
- [固定输入](input.json)：已有12图开发面板的195份作答及15份参考版本，保留所有资格、来源索引、预处理点与BEV足迹。177份独立共识候选参与；其余18份仍在输入与覆盖记录中，不悄悄恢复资格。
- [来源绑定核验](source_binding.json)：本地通过当前manifest完整加载后，对210个对象的点位、来源索引和顺序，以及人员键、独立票和质量/共识资格逐项对照固定交接。公开数值复算从本输入开始，不冒称重新完成所有原始来源核验。
- [实现](../../tools/thesis_main/analysis/lee_tile_stage1_20261002.py)、[针对性测试](../../tests/test_lee_tile_stage1_20261002.py)。复用仓库既有 `region_mesh` 几何切分函数；没有改写历史结果。
- [逐前缀结果](../../analysis_results/lee_tile_stage1_20261002/replay.csv)、[逐图摘要](../../analysis_results/lee_tile_stage1_20261002/summary.csv)、[全员tile及支持者](../../analysis_results/lee_tile_stage1_20261002/full_tiles.geojson)。GeoJSON仅借用容器格式，坐标为相机高度单位h，不是经纬度。
- [资格覆盖](../../analysis_results/lee_tile_stage1_20261002/coverage.json)、[字段说明](../../analysis_results/lee_tile_stage1_20261002/field_contract.json)、[数值警告](../../analysis_results/lee_tile_stage1_20261002/warnings.json)、[执行环境](environment.json)、[验证记录](VALIDATION.md)。

## 固定设置

每图按原condition与共识资格分层，16个固定无放回排列。每一当前k只用这k人的BEV多边形叠加边界切tile，每人对每块至多一票。≥50%为Lee MV基线，>50%检查平票影响。相同成员集缓存不含GT；全员tile仅为结果展示，不用于提前定义小k分区。

输入已经预处理：确认环保留，其余人员环按共享x默认排序，GT沿用既有参考版本。没有重配、改点、拟合正交、几何修复或删细小碎片。参考两版分别评价；无参考时不妨碍几何融合及稳定性。缺几何时整个前缀标不可计算，不能悄悄从k中减去失败者。

这是固定小面板的方法开发，不是全量人员研究。16个排列未穷举全部组合；同k的参考均值和分位数按采到的不同成员集等权。p10/p90不是置信区间。全员时只剩一个成员集合，成员差异为0是机制属性，不证明达到质量上限。

门洞交界除难度高外还可能有局部无法按规则合理标注；OOS的GT未必正确或适用。沿用原审核状态，不把这类图的参考距离当人员错误，不重新全面裁定GT。当前包没有原图，因此不支持视觉真假判断。

## 复算

从仓库根目录执行；`requirements.txt`列出本机执行版本，`environment.json`记录平台与GEOS。不同环境的结果及警告需要如实比较，不保证逐字节一致。

```powershell
python -m pip install -r research/lee_tile_stage1_20261002/requirements.txt
python -B -m pytest tests/test_lee_tile_stage1_20261002.py tests/test_supervisor_gt_sensitivity_20260922.py tests/test_consensus_contract_20260923.py -q -p no:cacheprovider
python -B -m tools.thesis_main.analysis.lee_tile_stage1_20261002 --out analysis_results/lee_tile_stage1_recomputed
```

源码只做数值重放，不消费原图，不更改标注。`full_tiles.geojson`保留最终每块的几何与匿名成员；`replay.csv`保存每次排列的前缀成员，可以逐条追溯和复算。

## 此后如何逐步推进

本轮已出现两种值得区分的现象：`7y3sRwLe3Va-12`的MV50原始参考IoU从采样单人均值约0.494降至24人时0.388，同时成员差异缩小；它属于OOS探索层，不能直接解释为人员变差。`e9zR4mvMWw7-19`的同一24人融合区域，对原始参考IoU约0.469，对既有修订参考约0.810，说明参考版本会明显影响解释。偶数人数的两种多数规则还会产生不同起伏。本轮保留这些现象，不平滑成单调收敛，也不据此判定哪一版参考视觉正确。

1. 先审查本轮tile结果、人数曲线、平票效应、资格分母及数值警告；只修具体问题。
2. 再扩大可用图片，或单独补一种质量分项。BEV、质心、边界、上/下轮廓、墙高和模型体积仍有研究价值，但不在本轮合成总分。
3. 利用参考适用的图片研究人员跨图表现，再决定分类；随后比较不同类型的真实人员组合。
4. 用已有图片分类、人工难度预期、冻结d_model_feat及BiLayout enclosed/extended差异，分别检查与曲线的大致对应。不建精细难度模型，不把它们一次塞进联合分析。

分簇、局部路径、合理空间候选独立；同房预测后置。主线与合同见[研究方向](../../docs/thesis_main/研究方向_空间差异与共识_20260930.md)、[当前方法合同](../../docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json)、[统计计划](../../docs/thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md)。

ChatGPT Pro可以在没有图片的条件下独立审查实现、复算数值、识别曲线解释的边界，并提出最值得做的下一小步。用户将通过对话提供目标提示词；本包不要求Pro采用指定的分析方法，也不请其替代视觉裁决。
