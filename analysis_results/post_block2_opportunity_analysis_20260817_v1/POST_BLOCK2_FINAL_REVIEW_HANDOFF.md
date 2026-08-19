# POST-BLOCK2 FINAL REVIEW HANDOFF

## 数据版本

- pack：`analysis_results/post_block2_analysis_pack_20260817_v3`
- pack manifest SHA-256：`abffc3dc4f28582d8a8d8818e5166aa5040af7a50a2a53995cf109da5efe7d04`
- analysis role：`development_cross_fitted_retrospective_audit_opportunity_estimate`

## 四组分析

- Aggregation：冻结 A0 重建检查为 `True`；A4 因 pre-outcome image evidence source absent 不可评估。
- Routing：完成 caliper/probability graph、maximum matching 与 1000 次 profile perturbation；历史 routing effect/cost counterfactual 不可识别。
- Clustered power：aggregation 与 routing fixed/generalized 设计网格已生成；不是 observed confirmation。
- Estimand：只输出 GO_CANDIDATE/CONDITIONAL 矩阵，未决定最终主线。

## 可用于设计但不能用于确认性主张

所有 cross-fitted selector、minority、matching 与 power 结果均为 retrospective development/opportunity evidence。A_oracle 仅为 evaluator-only bound。没有读取 T1/V1 outcome。

## Strongest evidence / counter-evidence

- Aggregation strongest evidence：task/building-disjoint paired selector表与 frozen A0 audit。
- Aggregation strongest counter-evidence：A4 与 corrected operational reference 不可识别，历史源码 commit object 本地不存在。
- Routing strongest evidence：全 sensitivity grid 的可匹配基数与 uncertainty perturbation。
- Routing strongest counter-evidence：没有随机化 next-worker counterfactual；LOBO/task-family profile covariance source absent。

## 新数据量

见 `POST_BLOCK2_CLUSTERED_POWER/aggregation_required_N.csv` 与 `routing_required_N.csv`。这些数值依赖明确的 optimistic/central/pessimistic 假设，不是招募决定。

## 当前不能下结论

不能确认 aggregation effect、routing effect、routing cost saving、operational-reference robustness，也不能由本线程冻结最终实验路线。

## 工件

- `POST_BLOCK2_AGGREGATION_OPPORTUNITY_AUDIT/`
- `POST_BLOCK2_MATCHED_ROUTING_FEASIBILITY/`
- `POST_BLOCK2_CLUSTERED_POWER/`
- `POST_BLOCK2_ESTIMAND_DECISION/`
