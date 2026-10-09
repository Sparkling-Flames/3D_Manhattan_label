# HoHoNet：约束前输出与重放诊断

2026-10-09。本地ep300模型重放，不修改原模型或旧分数。

259图，四相位完整259图；相位0四角回退0图，任一相位回退0图；旋转后点对数变化23图。

与旧模型点数比较236图，差异1图；差异保留，不覆盖旧结果。

## 指标意义

- 原峰数、一般解码墙数、强制改向／插入墙、四角回退：来自实际后处理调用，不能推断真实角数或遮挡。
- boundary correction：raw上下边界到最终球面边界的平均角度变化，反映模型约束调整，不等于图像到真实空间的误差。
- rotation MAE：yaw逆对齐后的raw边界／角点响应差，测模型不稳定；不能作为人的不确定性或正确率。
- raw_predictions.npz与layouts.json保存各图四相位原输出与最终点；失败相位单列，不删图凑完整。

本轮不据这些信号自动改难度档、不更换模型checkpoint、不按GT选结果。训练清单核查与实际checkpoint训练历史是不同证据。

复算：`.venv/Scripts/python.exe -m tools.thesis_main.analysis.difficulty_model_probe_20261009`。
