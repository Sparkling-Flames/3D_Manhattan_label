# post-Block2 analysis pack 2026-08-17 v4

2026-08-17 v4 从原始/冻结真源重新生成，并在 C2-A-RP 终态 closeout 后绑定 final Calibration profile。

- QA：GO；Prompt 2 可进入。
- 旧版本未覆盖。
- 未生成 Block 3。
- v4 修复了 v3 将 base_task_id 写入 building_id 的问题；building 字段只来自冻结身份真源。
- GT 边界：test 仅有少量局部研究者修正；validation 没有研究者自己的修正。
- 无历史随机 routing counterfactual，因此 routing replay 只能输出不可识别状态和设计功效输入。
