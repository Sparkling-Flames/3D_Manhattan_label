# v2.1 Q/QT选队共同支持补充

入口：[中文报告](REPORT_ZH.md)。这是基于Pro全链路研究已有精确团队的补充再分析，新增融合0，不覆盖原资料。

- 固定源→目标上下文与候选池后比较n=3/4/5/6/7/9/13；126上下文、46图、9楼。
- 计算楼簇重采样、删楼敏感性、相邻人数配对及成员嵌套率；保留失败与质量有效分母。
- n5的微小正质量差在固定支持下保留，但不能声称普遍升质；n13低相对坏尾不等于更高绝对质量。

复现：

```bash
python scripts/analyze_common_support.py
python scripts/validate_independently.py
```

依赖：Python、numpy、pandas、matplotlib；无网络调用、无模型训练、无新融合。脚本默认输入为包内原始三份表，也支持 `--input <selection目录> --output <输出目录>`。

`ANALYSIS_PLAN.json`在主要结果计算前保存；报告第4节的n5→n13绝对对照明确标记为事后探索诊断。输入SHA、原表复算、独立标准库重建和完整再运行记录均在`results/`。

本目录只供主任务统一发布；没有修改或推送用户仓库，没有联系Pro，没有启动新的Work/Codex任务。
