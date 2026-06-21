# HRC C6.2 Post-change Selection Audit v1

## 自动审计结果

| Bucket | Candidate | Decision | Hard gate | Action family | Authorization |
|---|---|---|---|---|---|
| best_manhattan_feasible | 0017 | legacy_trial_blocked | pass | edge_6_7_floor_depth_balance | audit blocked |
| best_balanced | 0017 | legacy_trial_blocked | pass | edge_6_7_floor_depth_balance | audit blocked |
| best_height_consistent | 0017 | legacy_trial_blocked | pass | edge_6_7_floor_depth_balance | audit blocked |
| best_short_wall_preserving | 0001 | hard_feasible_neutral | pass | vertical_column_align_x | audit blocked |
| best_low_movement | 0070 | hard_feasible_neutral | pass | azimuth_translate_keep_top_bottom_delta | audit blocked |
| best_hohonet_consistent | 0007 | hard_feasible_neutral | pass | azimuth_translate_keep_top_bottom_delta | audit blocked |

C4-lite 对 0017 给出无 conflict 的 available evidence；0019 出现 corner-column 与 ceiling-boundary 正向回归 flag。C6.2 的 L1 多指标 frontier 与 L2 evidence 因而不再由 direction max residual 单项把 0019 推到 0017 前面。

现有 `task218_ann3741`、`task218_ann2369`、`task238_ann2389` original artifacts 均成功解析对应 HoHoNet source，evaluation complete、hard gate passed；单候选 audit 下六个 selection bucket 均选择 original。该检查只验证合同可运行，不构成候选优劣结论。

## 边界与结论

- bucket 名称、hard-gate suppression 与 candidate diagnostics 未改变。
- 所有 bucket 均为 `accepted=false`、`downstream_recommendation=false`。
- 本文只确认计算合同和选择可解释性，不声称 0017 已成为最终修正。
- 自动 audit 通过；人工视觉 sanity check 尚未完成，overall verdict 保持 `audit_blocked`。
- C3 继续 blocked，直到人工 post-change selection audit 明确通过。
