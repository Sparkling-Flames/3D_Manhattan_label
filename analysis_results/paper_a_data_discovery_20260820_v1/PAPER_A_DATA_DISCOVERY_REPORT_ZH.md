# Paper A 全量数据盘点与客观关联扫描

## 结论边界

本报告只使用 Paper A；主总体为 `all_observed`，formal eligibility 按阶段合同统一后作为并列敏感性总体。没有 T1/V1 outcome，因此 E4 当前不可获得。阴性、反转及不可评价结果均保留。

## 数据覆盖

- submission：2,501（P1 1,481；C1 780；C2-B 160；C2-A-RP 80）。
- worker：26；W14 的 32 条 C1 记录及 W19、W21、W26 均保留。
- task：327 个 observed context；另有 458 个 T1 coverage-only 候选，不构造 outcome。
- semi-review：574 条；U_initial=557、U_final=558、delta_U=555。
- C1 Manual/Semi overlap：25 个 base task。

## 自动证据

等级计数：`{'E1_descriptive': 16, 'E0_not_evaluable': 12}`。结果按等级、折方向率、q、支持量及稳定键机械排序。`pre_existing` 与 `systematic_scan` 已分开标记；结果派生字段没有进入预测变量。

## 推断与可复现性

随机种子 20260820；最多五折，分组键不跨训练/验证。p 值来自独立组聚合后的 1,999 次确定性 permutation，区间来自整组重采样的 cluster bootstrap；dyad 同时进行 worker-held-out 与 task-held-out 并保留较弱结果。缺失不补零；族内 BH-FDR。active time 仅采用 spine 中正式 active-time 字段，lead time 未混入。
