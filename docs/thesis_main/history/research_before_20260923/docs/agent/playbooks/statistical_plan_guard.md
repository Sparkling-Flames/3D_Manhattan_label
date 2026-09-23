# 统计计划护栏

## 触发条件

- 修改 RQ1/RQ2/RQ3、active time、IAA、replay、bootstrap、permutation、MDE；
- 修改 T1/V1 estimand、failure disposition、生产标准化或 downgrade rule。

## 必须检查

- 阅读 `STATISTICAL_ANALYSIS_PLAN_v1.md` 和对应 Overleaf 源。
- T1 保持 Manual/Semi analysis pair、worker allocation 和
  `mode × risk_assist` 结构；primary active time 只使用 owner-valid 原始日志。
- T1 worker-caused structural failure 留在原条件且 delivery-adjusted quality 为零；
  external pair 行政删失不补零。
- V1 以原始随机化 task 为 ITT，前瞻比较 Strong Global 与 Full-Integrated。
- policy-caused unresolved/severe 留在原臂且 delivery-adjusted quality 为零；
  external 行政删失不进入质量分母但按臂报告。
- 同时报告 50:50 design estimand；production estimand 只能使用独立自然任务池权重。
- P1 predictive validation、C2-B confirmation、C2-A-RP precision completion 分工不混用。
- replay 只用于设计、功效、消融和审计，不替代 V1 主比较。

## 禁止事项

- 不把普通 annotation-level 独立检验当作唯一 T1 推断。
- 不把 Label Studio `lead_time` 混入 active-time primary。
- 不根据 T1/V1 outcome 选择 MDE、阈值、权重、risk 或 stop rule。
- 不把行政删失改写成零值，也不把 missing/not-evaluable 推断为 success。
- 不从 50:50 试验样本反推生产任务比例。

## 交付

- 报告 primary estimand、推断单位、missing/failure 处理和标准化口径。
- 说明仍属 sensitivity/audit 的输出。
- 报告统计 guard pass/fail。
