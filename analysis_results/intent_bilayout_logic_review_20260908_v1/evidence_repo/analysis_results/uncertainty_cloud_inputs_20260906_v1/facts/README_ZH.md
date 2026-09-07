# P1–C2-A-RP 不确定性研究中性数据底座 v1

## 用途与边界

本目录是并行的 retrospective 数据底座，不修改 Paper A 方法合同、SAP、C2-B 历史接受决定、C2-A-RP closeout 或既有 v5 审计包。`export_label/`、`active_logs/`、`import_json/` 是事实真源；SHA 绑定历史工件只用于 canonical selection、assignment、active-time 与 reference provenance 对账。

全部 2,501 条 canonical worker-task 记录均保留。旧 eligibility 仅作为历史字段，不是全局过滤规则；12 条 raw-only revision 保留版本谱系，但 `independent_analysis_unit=false`。

## 固定覆盖

- raw annotation versions：2,513 = canonical 2,501 + raw-only 12
- worker：26；image：214；building：22；task context：270
- proposal：43；proposal response：574
- raw geometry 可计算：2,438；formal active time 可用：2,069；lead time 可追溯：2,501
- raw active event：34,417；session context：3,735

## 关键语义

- `raw_condition`、`assistance_exposure`、`task_lane`、`scope_status` 正交保存。
- C2-A-RP 统一为单一 stage，并以 `block_index=1/2` 区分。
- `geometry_variants.csv` 分开保存 raw、strict-normalized 与 repaired/frozen-canonical 版本；任何修复不覆盖 raw。
- `geometry_pairwise.csv` 只保存连续、无阈值指标，不生成 cluster、mode 或 entropy 标签。
- Manual 的 Model Issue 是结构性 `not_evaluable`，不是 `acceptable`；历史 Model Issue 统一标为 `not_time_locked`。
- `active_time_seconds` 与 `lead_time_seconds` 永不互填；event fragment 仅作审计。
- 坏 GT 任务 `zsNo4HB9uLZ_4c0aab63a4434cf4878e6f5b3ce9a70b` 仍可用于 geometry-only 同行分歧，但所有 reference quality 均为 `not_evaluable`。

## 已知完整性缺口

旧 C2-A closeout 期望 Block 2 precision plan SHA `a98ba1cce4c63f7b5688d38cffb5cc991b97bb0138322d5affc0398cb4723bdf`，当前文件 SHA 为 `90613aabb780d3f0427d8e3bd11980936cc3be3feb6fbe100e113969756e2724`。因此旧 precision/risk-slope 链不能声称完整字节可重放；本底座明确不消费该链为新研究真值。

## 尚未冻结

本底座不冻结单一相似度阈值、cluster/mode、entropy/multimodality、worker 类型、proposal correct/wrong、Manual/Semi 因果效应或跨 stage 效应。后续研究问题与推断单位应在和导师确定方向后另行冻结。
