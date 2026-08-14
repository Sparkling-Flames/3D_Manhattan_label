# Calibration 双线 v3 计算验证报告

- 角色：`exploratory_diagnostic_pre_stage3`。
- 关联推断模型保留 building/stage fixed effects；预测模型不含测试不可识别的 stage/building 类别。
- 所有中心化、标准化和 channel residualization 均在训练折拟合。
- P2 对已见 worker 显式使用 BLUP intercept 与 risk slope；新 worker 才回退 fixed-only。
- Bootstrap 均为固定 seed 的 1,000 次诊断。
- 不生成正式 profile/policy freeze 或 Block 3。
