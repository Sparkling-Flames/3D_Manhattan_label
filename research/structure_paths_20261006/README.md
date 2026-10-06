# 连续路径Pro／dot原件与本地核验

2026-10-06。`pro_original/`、`dot_original/`分别保留用户提供的两份交付目录内容，未修改原代码或原结论。它们是研究原件，尚未接入正式融合算法。

- [本地深入审查与接续判断](../../analysis_results/structure_paths_review_20261006/REPORT.md)
- [Pro报告](pro_original/REPORT_ZH.md)
- [dot复审](dot_original/REVIEW_ZH.md)
- [dot事件窗口实验](dot_original/event_exploration/REPORT_ZH.md)
- [最新9图main交接入口](../structure_constraints_20261006/README.md)

Pro全流程本地重放入口（输出目录须不存在）：

```bash
python research/structure_paths_20261006/pro_original/reproduce.py --out analysis_results/structure_paths_review_NEW/pro_replay
```

dot事件代码使用`STRUCTURE_SOURCE`环境变量定位`pro_original`。Windows本地原14项测试有1项因原件要求浮点值完全相等而失败，差异为两个角距末位约7.1e-15°；原测试和原件未改。独立执行同政策全部432细分对照已通过，详见审查报告。不能把云端14通过直接写成本地14通过。

当前仓库核验入口：`python -m tools.thesis_main.analysis.structure_paths_local_review_20261006 --stage current`；dot有界重放用`--stage events`。原件的历史ZIP请求被当前main交接方式替代，无需再次打包。
