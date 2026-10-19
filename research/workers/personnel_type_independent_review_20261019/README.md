# 人员多变量与反向分型：独立审查（2026-10-19）

本目录是 dot 对 Pro Part A 的独立审查。Pro 原始研究另见 [整理入口](../personnel_type_discovery_next_20261019/README.md)。本目录的数值复核、批评及建议不等于 Pro 自述，也不改变生产评分、资格或正式人员标签。

**结论：真实的正向/反向人员分区已经交付，已检查的核心数值可以复算；目前仍不能接受为“同细类可可靠互换”的类别体系。** 不能把这个有限负结果扩展成“所有人员分类都无效”。

## 先看这些

- [完整中文独立报告](REVIEW_ZH.md)：进展、缺陷、证据界限及下一步。
- [主要概率预测增益及控制对照图](figures/independent_brier_controls.png)
- [类内/类外校准方向图](figures/independent_calibration_direction.png)
- [独立数值与代码检查明细](independent/NUMERICAL_CODE_AUDIT.md)
- [独立科学解释与政策风险检查](independent/SCIENTIFIC_ASSESSMENT.md)
- [ZIP、冻结文件、交付清单检查](independent/COMPLETENESS_AUDIT.json)
- [30 个空缓存新融合检查](independent_fresh/RESULT.json)；[逐值状态比较](independent_fresh/STATE_COMPARISON.json)

## 可复算与不能混淆的层次

1. 三个 ZIP 的 CRC/SHA、既有冻结源和交付清单均已检查。这里保留的是当时检查收据，仓库恢复副本不能重做原 ZIP 的 CRC。
2. 全部 286,666 事件的稳定标志，以及四方法、22 留楼折的校准概率做了独立重算。
3. 69 个正向已选分区用已冻结训练特征重新分区；仅一个外折和一个内层子集重新拟合所有特征，并做排除行污染检查。
4. 主反向 FULL 和一个外折重新分区；30 个团队空缓存重新融合并比较几何状态。
5. 没有重跑全部候选、全部融合或全部遗漏的反向长表；没有完成真实浏览器布局验收。

## 本地复算

先按 [Pro 整理包入口](../personnel_type_discovery_next_20261019/README.md) 用其 bootstrap 恢复原始层级。例如在仓库根目录：

```bash
python research/workers/personnel_type_discovery_next_20261019/bootstrap.py --output /tmp/part_a_restored
python research/workers/personnel_type_independent_review_20261019/reproduce_audit.py \
  --source /tmp/part_a_restored/work_personnel_typing_A_20261019 \
  --output /tmp/part_a_independent_new --stage diagnostics --execute
```

需使用原包声明的 Python 3.12 与依赖版本（见原包 reproducibility 目录）。原审计入口曾发现系统 Python 未安装 Shapely；实际新融合使用另外已安装的 Shapely 2.1.2。移植脚本不保留那个机器专属依赖路径，请在自己的环境安装正确版本后运行。原始检查收据如实保留该差异。

`reproduce_audit.py` 默认只打印计划。`--execute` 才执行，输出目录必须不存在，拒绝覆盖历史结果。各阶段：

- `diagnostics`：校准方向、QT/Q 来源时间与坏尾分析。
- `metrics`：全部事件标记、校准器及汇总，以及来源控制、匹配背景对比。
- `partitions`：69 个已选正向分区、两组特征拟合与排除行污染检查、两组主反向分区。
- `fresh`：30 个确定性抽样/已披露反例团队的新融合及状态比较。不是随机总体精度估计。
- `all`：顺序运行以上有限审计；仍不等于原研究全部重做。

原始审计脚本原样保存；包装器只在新目录产生路径替换副本，记录替换前后 SHA。不自动安装依赖，不联网，不改原研究输入。`metrics` 在没有原 ZIP 的恢复布局上会输出空 ZIP 列表，这是“未重验 ZIP”，不能解读成 ZIP 已通过。新收据与历史收据分目录保存。

生成本目录独立图：`python build_figures.py`（读取本目录已保存的独立重算 JSON，无新拟合）。图表使用英文短标签以减少字体环境差异；中文解释见报告。PNG 与 SVG 都保留。

## 插图来源

`figures/case_02_both_bev.png`、`case_06_both_bev.png` 是 Pro 原始案例图，未改动，SHA 与用途见 [来源表](figures/PRO_FIGURE_PROVENANCE.json)。它们是事后选例，不能代替总体统计或新增 GT。独立生成图的输入哈希见 [图表来源表](figures/INDEPENDENT_FIGURE_PROVENANCE.json)。

本目录全部文件的大小/SHA 见 `PUBLICATION_MANIFEST.json`（清单自身除外）。历史记录中的本机路径仅用于来源追踪；运行请用上述移植入口。
