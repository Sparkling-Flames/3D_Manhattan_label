# 协议护栏

## 触发条件

- 修改 P1、C1、C2-B、C2-A-RP、T1、V1；
- 修改 admission、worker state、risk、routing、capacity、failure disposition 或 Validation；
- 修改 protocol、SOP 或 thesis-facing 解释。

## 必须检查

- 阅读 `ROUND_BASED_EXECUTION_PROTOCOL_v1.md` 与 `ROUND_BASED_ASSIGNMENT_SOP_v1.md`。
- 保持 `Pilot -> PreScreen -> Calibration -> Main(Test + Validation)` 和
  `P1/C1/C2/T1/V1` 边界；C2 内部分为 C2-B 与 C2-A-RP。
- C1 原始 export、assignment 和正在进行的标注不得因派生链变化而返工。
- P1 component 只有通过 C1 predictive validation 与 C2-B confirmation 才可进入 Full。
- T1/V1 outcome 不得回流修改 admission、C1/C2、worker state、risk 或 freeze 参数。
- OOS、外部事故、工人结构失败和政策失败保持分离。
- external incident 必须验证证据 SHA、时间窗、范围和结果可见前登记。

## 禁止事项

- 不恢复 reserve-only C2 正式合同。
- 不把 P1 原始表现直接升级为正式 routing profile。
- 不用旧 Random/Global/Full 离线 replay 替代 Strong Global 与 Full-Integrated 的前瞻 V1。
- 不让两臂跨臂借容量或使用不同 offer/replacement/aggregation 规则。
- 不用 T1/V1 结果重设阈值、权重、动态冗余或失败归因。

## 交付

- 报告 protocol guard pass/fail。
- 列出检查的正式合同与 freeze 边界。
- 说明 C1 原始数据是否保持不变。
