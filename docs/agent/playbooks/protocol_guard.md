# 协议护栏

## 触发条件（Trigger）

- 涉及 `P1`、`C1`、`C2`、`T1`、`V1` 的变更
- 涉及 admission、`w_max`、`r_u`、`r_u^(s)`、`tau_d`、Score、worker tier、routing 或 Validation 的变更
- 任何 protocol、SOP 或 thesis-facing 解释变更

## 必须检查（Required checks）

- 阅读 `docs/thesis_main/ROUND_BASED_EXECUTION_PROTOCOL_v1.md`。
- 阅读 `docs/thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.md`。
- 检查变更是否影响 freeze boundaries 或 allowed updates。
- 检查是否把 Main/Test/Validation 结果回流到 admission、`w_max`、worker tier、`tau_d`、Score、`k0/kmax` 或 stop rules。
- 检查 OOS gate 是否仍与 manual geometry reliability 分离。

## 禁止事项（Forbidden actions）

- 不改变 `Pilot -> PreScreen -> Calibration -> Main(Test + Validation)`。
- 不改变 `P1/C1/C2/T1/V1` 边界。
- 不把 PreScreen 输出升级为正式 routing profile。
- 不把 `difficulty` 或 `model_issue` 用作标注前 non-IID split 真源。
- 不让 `V1` 结果修改 C2 冻结内容。

## 预期交付（Expected handoff）

- Protocol guard pass/fail 结果。
- 已检查文件。
- 边界影响说明。
- 是否需要 protocol amendment 记录。
