# 共识可靠性返回：原件与本地修复入口

2026-10-05接续：已接收[dot本地复核](dot_local_review/LOCAL_REVIEW_ZH.md)，并完成[局部路径证据与下一轮并行交接](../local_shortcut_handoff_20261005/README.md)。新诊断未改本页所记原修复结果。

本目录的`pro_original/`是10月5日Pro返回的数值精选归档，原文件逐字节复制。目录包含源代码、四图输入、分离GT、数值结果、24项测试、报告和执行日志；未收录已渲染的HTML与图像。明细见[archive_receipt.json](archive_receipt.json)。原报告中的渲染页面／图像链接及原`verify_delivery.py`的完整包验收需要Downloads中的完整交付包，不能拿精选归档冒充完整包。

- [独立审查](../../analysis_results/layout_reliability_review_20261005/REPORT.md)：两个缺陷及作用范围，输入绑定和指标排序补查。
- [本地修复与复算](../../analysis_results/layout_reliability_fixed_20261005/REPORT.md)：维护模块位于[layout_reliability_20261005](../../tools/thesis_main/analysis/layout_reliability_20261005/continuous_metrics.py)。
- [真实局部删改试验](../../analysis_results/local_structure_deletion_20261005/REPORT.md)：五来源、51单点对删除，未使用GT。
- [候选构造计划](../../docs/thesis_main/空间候选构造_局部删改试验_20261005.md)：与完整共识的职责区分及后续多人结构池。

本地模块沿用原`arc_consensus.py`，仅将`continuous_metrics.py`改为包内导入，并修复高度包络的正切奇点分段和失败窗口的来源合并。原件不改，默认工作台和历史消费者也未替换。当前规范、源标注、资格、票权与GT隔离不变。

输入是已绑定当前源的固定研究摘录，不替代统一manifest真源。其他图片的后续研究仍须通过当前源加载器构建完整名单。

复算在仓库根目录执行：

```powershell
python -B -m pytest -p no:cacheprovider tests/test_layout_reliability_20261005.py tests/test_local_structure_deletion_20261005.py -q
python -B -m tools.thesis_main.analysis.repair_layout_reliability_20261005 --out analysis_results/NEW_reliability_check
python -B -m tools.thesis_main.analysis.local_structure_deletion_20261005 --out analysis_results/NEW_deletion_pilot
```

两个输出目录必须不存在，避免覆盖证据。主研究仍需局部图像语义及使用体验验收；代码测试通过不等于物理房间正确。
