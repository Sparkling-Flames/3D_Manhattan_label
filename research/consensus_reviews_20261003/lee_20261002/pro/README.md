# Lee tile stage 1：独立核查与小组穷举（2026-10-02）

## 范围和来源

固定仓库：Sparkling-Flames/3D_Manhattan_label，提交 `b1ebab888fe8ac736548897f126a8bce7292c114`。
当前入口：`research/lee_tile_stage1_20261002/README.md`。
输入来源：同目录 `input.json`，Git blob `9fdb7ba918cdffad23a24bf8ca017cf7c2e9f74b`。

容器直连GitHub发生DNS失败；GitHub阅读接口可读。本包不是完整仓库镜像。
`inputs/subset.json`从阅读接口实际显示的数值摘录，保留 `2t7WUuJeko7-07` 全部8份独立候选足迹、匿名ID/人员和必要资格、原始GT足迹。不包含该记录全部字段，也不重新处理坐标。
该图是难标门洞探索层，quality_candidate均为false。原始GT环未人工确认；所有参考差距仅供几何诊断，不推断人员错误。其余11图结果来自源报告/摘要阅读，未在本包复跑。

`src/core.py`是当前tile、IoU和人数汇总的独立可运行摘录，不是原仓库完整模块。函数来源：
- `tools/thesis_main/analysis/lee_tile_stage1_20261002.py`，blob `8933a98a528f82285b403b79e937ca51fd8d9a1c`；
- `region_mesh`来自 `tools/thesis_main/analysis/audit_supervisor_gt_sensitivity_20260922.py`，blob `2fa3a3525b08581163d6212b95b80622576988ff`。
仅抽取本次消费的核；未导入其旧坐标或旧清洗加载器。原始根模块的可视化/CLI/全员导出包装未复制。

`inputs/published_summary_extract.csv`摘录源 `summary.csv` 第2–17行的共同字段，用于核对当前8人组。输入为人工转录，因此不是源字节SHA复核；当前同种子摘要126个非缺失数值字段吻合，不构成独立上游身份绑定证明。

## 实际执行

```
python inputs/build_excerpt.py
python src/run_audit.py
python -m pytest src/tests.py -q -p no:cacheprovider
python src/make_figures.py
```

本包已有执行结果。Python/GEOS版本见 `results/checks.json`。9项针对性检查通过，不是原仓库10项测试的重跑。
`run_audit.py`分别以当前成员重新切分全部255个非空子集，计算2种多数规则，共510个区域输出；另外重放当前种子的16个排列并核对原摘要。

全员细分用于一个独立的数学一致性诊断：只读取当前成员的票，比较与每前缀重新切分的输出是否一致。不是用未来成员选择阈值、候选或调整测量。最大对称差面积3.92e-16 h²。

2000批×16个无放回排列仅衡量蒙特卡洛汇总的计算波动，不是新人员、新图片或统计验证集。参考均值按各批实际抽到的不同子集等权；没有将重复真人计成额外票。

## 关键结果

- 8人组原16次排列的两人严格多数均值0.547015716；穷举28种两人组合均值0.457619173（完整精度见CSV）。
- 原单人均值0.565177837；穷举全部8人的均值0.530929748。差别来自抽样覆盖，不是修正投票公式。
- 全员mv50=0.625896067，strict=0.632079019，与原摘要一致。
- 126个非缺失摘要数值最大差7.77e-16。
- 全员融合的成员集差异为0，但原始支持场分歧（以GT面积归一）为0.216666183。
- 支持场参考偏差0.370730719，与分歧相加等于平均个人对称差0.587396902，恒等式误差2.22e-16。
- 本组本环境没有数值警告；这不解决原全量97条警告。未在全部警告案例上复算，未声称版本是原因。

## 输出

- `exact_vs_16.csv`：所有k的穷举与原设计比较，含成员差异、相邻变化。
- `all_subsets.csv`：510个结果，含成员ID、IoU、遗漏/外扩和区域分量/孔洞。
- `sampling_error_batches.csv`：2000批重放的汇总均值波动，分位区间不是人群置信区间。
- `support_field_finite_population.csv`：有限人群期望公式的逐k实算。
- `support_field.json`：原始票率的参考偏差/分歧分解及tile面积、参考交集面积、支持人数。
- `hole_counterexample.json`：3个包含相机的简单区域，其多数结果有孔洞。它不代表真实图，只说明有效区域不必是当前合法房间格式。

## 不作的宣称

没有全量195份来源绑定重跑，没有全量177人/12图复算，没有原图/GT新裁决，没有确认人员类型、因果顺序效应或难度显著性。没有对已排除资料恢复资格，没有制造真实屋顶，没有将支持场当GT后验或人员/图片方差分量。
