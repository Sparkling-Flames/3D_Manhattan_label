# Paper A 全量数据盘点与客观关联扫描

## 结论边界

本报告只使用 Paper A；主总体为 `all_observed`，formal eligibility 仅保留为事实字段。没有 T1/V1 outcome，因此 E4 当前不可获得。阴性、反转及不可评价结果均保留。

## 数据覆盖

- submission：2,501（P1 1,481；C1 780；C2-B 160；C2-A-RP 80）。
- worker：26；W14 的 32 条 C1 记录及 W19、W21、W26 均保留。
- semi-review：574 条冻结行级复核记录。
- T1 候选池只作覆盖输入登记，不构造 outcome。

## 自动证据

等级计数：`{'E1_descriptive': 4, 'E0_not_evaluable': 15}`。结果按等级、折方向率、q、支持量及稳定键机械排序。`pre_existing` 与 `systematic_scan` 已分开标记；结果派生字段没有进入预测变量。

## 可复现性

随机种子 20260820；最多五折，分组键不跨训练/验证；缺失不补零；族内 BH-FDR。active time 仅采用 spine 中正式 active-time 字段，lead time 未混入。
