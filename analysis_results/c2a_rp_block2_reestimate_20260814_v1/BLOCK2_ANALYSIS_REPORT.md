# C2-A-RP Block 2 本地审计报告

## 结论

Block 2 数据采集与身份闭合已经完成：20 名工人、40 个 worker-task submission 与冻结分配逐条一致。Block 2 本身可以视为收轮，但本次仅完成数据审计与重估，不生成或授权 Block 3。

累计正式 risk evidence 为 240 行，其中 225 行可进入冻结模型。冻结模型返回 `multiple_variance_components_unidentifiable`，因此本轮不能机械地产生新的逐工人 CI、`target_met` 或停止决定。这不是缺交或 active-time 异常造成的；收敛的 Powell 解同时把 building variance 与 worker-slope variance 推到数值边界，按既有 boundary rule 必须停止，而不能事后改模型。

## 数据完整性

- 冻结分配：40 行，20 人，每人 1 ordinary + 1 stress。
- 实际提交：40 行；无缺交、无额外正式提交、无取消、无重复。
- Runtime：Project 84/85，task 3533–3564，40 行全部绑定。
- Canonical geometry：40/40 可解析。
- Risk-slope evidence：38/40 eligible。

两条 geometry evidence 自动退出：

- W029 / `pRbA3pwrgk9_16beb21e65a84850a509972190038d0e`：13 个角点，无法形成成对布局。
- W037 / `S9hNv5qa7GM_53d54b73e58940019b731673e65c1902`：角点顺序无法通过冻结 geometry normalizer。

两条记录均保留原始提交，不做人工补点或重排。

## Active Time

原始日志已冻结到 `active_logs/c2a_rp_block2_20260814/`，覆盖 2026-08-11 至 2026-08-14，四个文件 SHA-256 已写入 freeze manifest。

- 40/40 正式提交均有 project + runtime task + worker 精确匹配。
- 中位 active time：167.5 秒；范围：26–3474 秒。
- 6 条使用旧脚本，标为 `legacy_script_auxiliary_only`。
- W036 的 runtime task 3561（1896 秒）和 3563（3474 秒）进入 `long_duration_review`。
- 4 个非分配浏览上下文及 Project 84 早期 5 条旧项目名事件只保留为 forensic provenance，不进入正式匹配。
- Active time 仍为 auxiliary-only，不影响 geometry eligibility 或 risk routing。

## 冻结模型结果

- 累计 evidence：240 行；eligible 225 行。
- 支持：20 workers、67 tasks、9 buildings。
- CI 目标：0.012607928483052961。
- Powell optimizer 收敛，但 building 与 worker-slope 两个方差分量同时处于边界。
- 冻结 boundary rule 的正式终态：`multiple_variance_components_unidentifiable`。
- 因此没有输出 post-Block2 worker profile，也没有生成下一 Block 的 precision plan 或 assignment。

## 当前边界

本报告只关闭 Block 2 的本地数据与 provenance 审计。若之后决定继续，必须先单独处理“多方差分量同时到边界”对应的既有模型终态；不得用查看 Block 2 结果后的临时模型替代正式规则。
