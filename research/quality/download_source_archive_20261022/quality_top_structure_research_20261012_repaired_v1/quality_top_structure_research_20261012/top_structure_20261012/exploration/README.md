# 完成指定任务后的单项自由探索

先读 `REPORT_ZH.md`。本目录在指定A/B/C计算完成之后开始，只研究可解释的高度幅度/底周长支持诊断。0.10、0.20、0.40是显示尺度，不是人类阈值；没有增加Q罚项或调整等级。

运行：

```bash
python top_structure_20261012/exploration/run_exact_height_support.py --root . --out new_run/exploration/results
python top_structure_20261012/exploration/render_support_evidence.py --results new_run/exploration/results
```

依赖numpy；科学图另需matplotlib。所需39份真实、71项控制输入沿用主包冻结文件，1项无效控制保留空值。输出为110行、109有效剖面，327项表示不变性检查及36项独立解析式核对。

`exact_height_support.py`中的 `paired_height_diagnostics(annotation, reference)` 提供无评分的最小接口。输入是原有、已核资格/配对的 `top3d` 和 `bottom3d`，函数不建立人员标签、配对或参考。

该量的明确盲区是整体低顶、规整但漏角、错误范围，以及从底角重建敏感性传播而来的顶面起伏。完整失败案例与原基线数值均保留在报告和CSV中。
