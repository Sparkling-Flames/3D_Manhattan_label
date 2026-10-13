# 独立结构、投影与数值实验

本目录提供可重跑的独立几何描述、反例、参数候选检验及静态研究图。科学结论见 `REPORT_ZH.md`；最终参数读包根目录 `calibration/recommended_parameters.json`。

## 一条命令重跑

在解压后的研究包根目录运行，输出目录应是新目录：

```bash
python experiments/reproduce_experiments.py \
  --source baseline \
  --config calibration/recommended_parameters.json \
  --local-results sources/main/research/quality_parallel_local_20261012/record_results.json \
  --out /tmp/quality_experiments_replay
```

依赖 Python、NumPy、SciPy、Shapely、Matplotlib、Pillow。13 个最小基线输入的逐文件 SHA256 在 `SOURCE_DEPENDENCIES.json`；不需要访问旧独立研究目录，也不需要网络。

流水线依次产生 922 作答结构描述、共同轴切换反例及修复性联合 hinge、335 定向几何、39 真实作答与 335 控制的采样核验、144 极端投影扩展、原始输入字段交叉核验、最终三候选独立复算、解析诊断和四幅静态图。144 极端扩展中 6 个无法在预设正向底面射线域内构造，账本保留为不可用。

## 主要输出

| 文件 | 内容 |
|---|---|
| `results/real_direction_descriptors.json` | 922 作答的逐边角度残差、长度权重、超限二/四次矩；89 个旧参考的描述 |
| `results/joint_hinge_descriptors.json` | 922×9 个精确联合选轴的连续最小损失值 |
| `results/axis_switch_counterexample.json` | 轴切换导致外挂尾量跳变的可复现几何与修复检验 |
| `results/targeted_constructed_cases.json` | 335 控制的完整 3D 几何、输入预算和原参考版本 |
| `results/targeted_metrics.json` | 上述控制的完整基线指标和计算状态 |
| `results/extreme_projection_cases.json` | ±16/±32 像素扩展的完整几何及域外账本 |
| `results/extreme_projection_results.json` | 138 可算扩展的三级球面采样与高度归因 |
| `results/sampling_verification.json` | 39 真实作答及 335 控制的多精度几何指标 |
| `results/input_alignment_cross_version_verification.json` | 实际本地 X 字段、独立端点位移 E、版本及哈希对齐 |
| `results/candidate_validation_real.json` | 922 作答按同一旧参考的独立候选评分和分解 |
| `results/candidate_validation_controls.json` | 479 控制尝试、473 完整控制的四配置结果、优先级与耦合 |
| `results/candidate_precision.json` | 最终三候选的采样误差复算 |
| `results/real_topology_diagnostics.json` | 低 D 但相对旧参考凹角更少的 16 个描述案例；不自动认定范围错误 |
| `results/response_transition_ranges.json` | 模型响应转折与单项响应；没有人类等级切点 |
| `figures/FIGURE_VERIFICATION.json` | 四幅 PNG 的完整解码、大小和 SHA256 |

`candidate_validation_real.json` 使用同一旧参考隔离公式效应；实际新路由与四格归因以包根目录的主交付为准。这里的 479 次控制尝试来自 6 个原参考及少量解析形状，没有新增 479 个人工标签或独立房间。
