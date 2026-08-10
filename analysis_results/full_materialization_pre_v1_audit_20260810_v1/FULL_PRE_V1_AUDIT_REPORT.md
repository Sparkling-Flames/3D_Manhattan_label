# Full materialization 与 V1 activation 审计

## 结论

当前不能把 risk-only proxy 升级为正式 V1 power，也不能解释为 Full 与 Global 科学上没有差异。正式 Full 输入尚未物化。

- active workers：20
- worker × P1 family cells：60
- `full_component_eligible=true`：0
- 其中由正式负证据否定：0
- 因 component chain 缺失而不可评价：60
- risk precision gate 暂时通过：1
- 458-task activation 可评价：0
- 458-task ranking replay 可评价：0

## 机制定位

现阶段 divergence 消失不能归因于 C2-A 精度不足。排序链在更上游即未闭合：family component chain、task activation、Full scoring freeze 和 risk scale provenance 均缺失。

`S_G=z(Q_GT_EB)` 已可作 audit-only 基线；当前 Global rank-1 为 W2。但是 raw worker slope 不得直接加到 z-score。正式 `B_u_risk_shrunk`、转换、权重与 adjustment cap 均未冻结。

## 下一安全步骤

1. 从已有 P1 工件生成三 family 的 worker-level raw/integrity 表；不能用 generic geometry capability 代替 family evidence。
2. 冻结并运行 P1→C1 predictive 与 C2-B confirmation estimator；当前仓库实现明确 fail closed at `pending_c2b_confirmation`。
3. 从 outcome-blind features 物化 458-task `risk_route/d_cal_F/family_scores`。
4. 统一 `B_u_risk_shrunk` 与 V1 engine 字段并冻结 numeric scoring manifest。
5. 随后复用正式 `rank_candidates` 与 scheduler 做 ranking/capacity replay，再运行 prospective power。
