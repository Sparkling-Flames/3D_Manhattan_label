# 统计计划护栏

## 触发条件（Trigger）

- 修改 `RQ1`、`RQ2`、`RQ3` 统计分析
- 修改 `active_time`、IAA、replay、bootstrap、permutation、MDE 或 downgrade rules

## 必须检查（Required checks）

- 阅读 `docs/thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md`。
- 修改 thesis-facing 表述前检查相关 Overleaf 源。
- 对 `RQ1`，保持 image pairing 与 worker allocation / condition assignment 结构。
- 对 `RQ2`，保持 `Nimg=25` paired subset 与 paired permutation/bootstrap。
- 对 `RQ3`，保持 Random / Global / Full 主比较来自 `Calibration_manual` offline replay。
- 确认 active-log downgrade 与 worker pass-count contingency 规则仍存在。

## 禁止事项（Forbidden actions）

- 不把 naive annotation-level Mann-Whitney U 作为 `RQ1` 唯一主检验。
- 不把普通 chi-square 作为 `RQ2` 反例类型分布主检验。
- 不把 `V1` 当作 Random / Global / Full 主因果比较。
- 不用 Main/Test/Validation 结果设定 MDE、admission、`w_max`、`tau_d`、Score、routing freeze、`k0/kmax` 或 stop rules。
- 不把 Label Studio `lead_time` 混入 `active_time` primary estimand。

## 预期交付（Expected handoff）

- Statistical guard 结果。
- 对 primary estimand / inference 的影响。
- 对 downgrade / contingency 的影响。
- 仍属于 sensitivity-only 的主张。
