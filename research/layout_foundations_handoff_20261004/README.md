# 全景布局共识下一轮深研交接

2026-10-04。本包补充到本地main，供用户上传后交给Chat Pro继续研究。研究目标、阶段边界和验收条件见[推进方案](../../docs/thesis_main/研究推进方案_共识可靠性与Pro深研_20261004.md)。提示词仅在对话中给出，不另存文件。未启动Chat Pro，未自行push。

## 先读的材料

1. [后续推进方案](../../docs/thesis_main/研究推进方案_共识可靠性与Pro深研_20261004.md)，随后读[原线程交接](../../docs/thesis_main/线程交接_连线质量与完整共识_20261004.md)和[当前研究方向](../../docs/thesis_main/研究方向_空间差异与共识_20260930.md)。
2. [新Pro报告](external/dot/source/layout_foundations_20261004_v2/REPORT_ZH.md)、[dot独立复审](external/dot/REVIEW_ZH.md)、[高度与均值反例证明](external/dot/crosscheck/CROSSCHECK_ZH.md)。外部报告是待评价证据，不是方法合同。
3. [四图数据说明](DATA.md)、[名单](inputs/rosters.json)、[来源绑定](source_binding.json)。构造输入与参考坐标分离。
4. [当前合同](../../docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json)、[统计计划](../../docs/thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md)。算法开放，既有输入、GT隔离与资格边界保留。

当前重点是连线与空间表示、分项测量和完整共识。允许推翻现有解释，允许明确失败或无新增收益；不以新法GT最高、压缩必须成功、困难必然更慢为目标。

## 外部原件只保存一次

external/dot完整保留94个外部文件，约15.65 MB；其中source/layout_foundations_20261004_v2是Pro完整73文件交付，经直接逐文件字节比较，与用户单独提供的Pro目录一致，因此不再存第二份。原始报告、源码、输入、结果、失败记录、测试、viewer、图表及dot三个独立复算ZIP均保留；见[归档清单](archive_inventory.json)。原包里的历史散列文件与日志原样保留，本轮不建立新的散列验收门槛。

关键可读入口：

- [精确构造](external/dot/source/layout_foundations_20261004_v2/src/arc_consensus.py)、[压缩](external/dot/source/layout_foundations_20261004_v2/src/simplify.py)、[指标](external/dot/source/layout_foundations_20261004_v2/src/quality.py)。
- [原运行入口](external/dot/source/layout_foundations_20261004_v2/run_research.py)、[自定义完整名单入口](external/dot/source/layout_foundations_20261004_v2/run_local.py)、[原测试](external/dot/source/layout_foundations_20261004_v2/tests/test_foundations.py)。
- [原交互展示](external/dot/source/layout_foundations_20261004_v2/EVIDENCE_VIEWER_ZH.html)、[原结果目录](external/dot/source/layout_foundations_20261004_v2/results/final/)、[dot输入核对](external/dot/source_binding/README.md)。
- [dot数值审查ZIP](external/dot/reproductions/layout_foundations_v2_independent_audit_20261004.zip)、[dot高度与支持实验ZIP](external/dot/reproductions/oct4-evening-foundation-explore.zip)、[dot指标审查ZIP](external/dot/reproductions/oct4-evening-quality-audit-portable.zip)。

这些文件只作为外部研究原件归档，没有接入tools运行消费者。dot的crosscheck脚本会向自身目录写结果；如复跑，应复制到新实验目录。ZIP也解到新目录，不能覆盖此归档。原Pro复算入口及环境见其[README](external/dot/source/layout_foundations_20261004_v2/README_ZH.md)和[requirements](external/dot/source/layout_foundations_20261004_v2/requirements.txt)；本轮没有重跑其32测试或29个结果。

## 四图完整当前名单

| 图片 | 源记录数 | 当前Manual独立主共识名单 | 输入 |
|---|---:|---:|---|
| 2t7WUuJeko7-06 | 3 | 3 | [3人](inputs/2t7WUuJeko7-06.json) |
| 7y3sRwLe3Va-04 | 26 | 24 | [24人](inputs/7y3sRwLe3Va-04.json) |
| rPc6DW4iMge-06 | 26 | 24 | [完整24人](inputs/rPc6DW4iMge-06.json) |
| uNb9QFRL6hY-67 | 16 | 15 | [15人](inputs/uNb9QFRL6hY-67.json) |

四图共66份作答，源总记录71份；5份未进入当前名单的记录及具体资格原因保留在rosters.json。它们不是因本轮算法失败被删除。此面板用于开发机制检查，不估计全库发生率，不称全新盲测。

四个单图输入可直接传入原run_local.py，默认只构造，不打开GT。示例从仓库根执行，必须选择不存在的新输出路径：

```sh
python -B research/layout_foundations_handoff_20261004/external/dot/source/layout_foundations_20261004_v2/run_local.py --input research/layout_foundations_handoff_20261004/inputs/7y3sRwLe3Va-04.json --out analysis_results/layout_foundations_next_research_20261004/7y3s_exact.json
```

该命令是下一轮入口，本轮未执行。rPc整池不适用也必须保留为完整24人结果；不能只跑其中成功成员。候选和压缩政策固定后，评价端另读[evaluation/references.json](evaluation/references.json)。没有原图，不用几何或GT距离替代视觉裁决。

## 与当前仓库和未提交内容的关系

四图快照经当前load_current_bundle校验后，从project_bundle与prepare_record导出。完整权威入口仍是[统一manifest](../../analysis_results/research_input_20260929/manifest.json)，本快照不是新真源或资格合同。导出使用本地工作区中已有的两个未提交消费者，实际名单／字段又独立核对；其路径在source_binding.json披露，没有将它们纳入此次提交。

仓库根geometry、studio、地基／3D探针等仍有其他线程未提交内容，详见[原交接的边界](../../docs/thesis_main/线程交接_连线质量与完整共识_20261004.md)。不能声称用户上传本次main后，云端就具备所有本地改动。必要旧质量快照见[独立质量交接包](../pro_quality_handoff_20261002/README.md)，不在这里再复制。

核对当前源码时优先查看[源环准备与首交墙带](../../tools/thesis_main/analysis/research_round_20260929.py)、[Lee](../../tools/thesis_main/analysis/lee_tile_stage1_20261002.py)、[点方法](../../tools/thesis_main/analysis/global_pair_consensus_20261004.py)、[ERP原型](../../tools/thesis_main/analysis/erp_region_demo_20261003.py)。当前主工作台未静默使用旧wall_mask；点候选仍按中心x建立新环，其诊断不能当物理确认。ERP和Lee同名mv50在偶数人数时不是同一底面。

## 保留的下游证据

- [136图人数结果](../../analysis_results/lee_expanded_20261003/REPORT.md)、[8到20人配对精度与人员返回审查](../../analysis_results/worker_review_20261003/REPORT.md)。
- [24人乘10图画像及构成](../../analysis_results/worker_profiles_20261003/REPORT.md)、[最新人员子类复核](../../analysis_results/worker_subtype_review_20261004/REPORT.md)。
- [当前难度和来源审计](../../analysis_results/review_source_audit_20261004/REPORT.md)。旧标签组摘要不作当前结果；复用逐图值即可重汇总。

本包只做资料归档、源侧输入投影和研究计划，没有新融合、指标、压缩或人数结果。[本地交付检查](verification.json)单列已检查与未运行内容。
