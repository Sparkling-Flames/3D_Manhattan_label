# HoHoNet 模型布局初始化代理审计（角点数量主分析版）

## 主结论

本版只把**点对编码合法且模型/GT 角点对数量完全一致**作为硬二元门。它保留用户旧报告最关心的角点数量标准，同时不把尚未独立校准的 IoU、角点距离或 mask difference 数值强行合并成另一个“成功/失败”结论。

当前对象仍是 HoHoNet ep300 保存的最终布局，即 `final_layout_as_initialization_proxy`，不是未保存的网络原始峰值。Test 采用 30 张人工校准 GT + 428 张官方 GT；Validation 190 张采用官方 GT；未使用 `test_no_occ` 或 `valid_no_occ`。

| 口径 | N | 角点对数量一致 | 数量不一致 | 一致率 (%) |
|---|---:|---:|---:|---:|
| Test 官方原始 GT（敏感性） | 458 | 290 | 168 | 63.32 |
| Test 混合 GT（当前） | 458 | 287 | 171 | 62.66 |
| Validation 官方原始 GT | 190 | 163 | 27 | 85.79 |

因此 Test 混合 GT 的角点数量主结果是 **287/458（62.66%）**；Validation 是 **163/190（85.79%）**。这是逐图拓扑代理通过率，不是官方 2D/3D IoU benchmark，也不等于“无需人工修改”。

## 连续 benchmark 指标

| 口径 | N | 2D IoU (%) | 3D IoU (%) | layout-depth RMSE | delta1 |
|---|---:|---:|---:|---:|---:|
| Test 官方原始 GT（benchmark 对照） | 458 | 81.97 | 79.52 | 0.22 | 0.94 |
| Test 混合 GT（30人工+428官方） | 458 | 82.12 | 79.68 | 0.22 | 0.94 |
| Validation 官方原始 GT | 190 | 92.58 | 91.64 | 0.09 | 0.98 |

Test 官方原始 GT 的 81.97% 2D IoU 是 458 个逐图 IoU 的均值；它与上面的角点数量一致率回答不同问题。`layout-depth` 两列由布局角点合成深度，只是 proxy，不是真实 Matterport depth 指标。

## 数量一致样本中的误差分布

以下均为“中位数 [Q1, Q3]”，不设置通过门槛。

| 指标 | Test 混合 GT（N=287） | Validation（N=163） |
|---|---:|---:|
| top-down 2D IoU (%) | 88.79 [81.18, 93.53] | 95.80 [93.93, 96.95] |
| derived 3D IoU (%) | 86.01 [78.31, 91.58] | 94.79 [92.75, 96.29] |
| 平均角点误差 / 图像对角线 (%) | 0.50 [0.35, 0.86] | 0.16 [0.13, 0.20] |
| layout mask difference (%) | 4.13 [2.46, 6.93] | 1.22 [0.90, 1.64] |

## 非拓扑误差的多阈值敏感性

各行仅单独应用一个阈值，分母均为本 split 中角点对数量一致的样本；这些行不能相加，也不代表推荐阈值。

| 单项敏感性条件 | Test 混合 GT | Validation |
|---|---:|---:|
| 2D IoU ≥ 0.75 | 249/287 (86.76%) | 159/163 (97.55%) |
| 2D IoU ≥ 0.80 | 224/287 (78.05%) | 157/163 (96.32%) |
| 2D IoU ≥ 0.85 | 183/287 (63.76%) | 154/163 (94.48%) |
| 2D IoU ≥ 0.90 | 125/287 (43.55%) | 152/163 (93.25%) |
| 2D IoU ≥ 0.95 | 41/287 (14.29%) | 100/163 (61.35%) |
| 3D IoU ≥ 0.65 | 263/287 (91.64%) | 160/163 (98.16%) |
| 3D IoU ≥ 0.70 | 254/287 (88.50%) | 160/163 (98.16%) |
| 3D IoU ≥ 0.75 | 235/287 (81.88%) | 159/163 (97.55%) |
| 3D IoU ≥ 0.80 | 206/287 (71.78%) | 156/163 (95.71%) |
| 3D IoU ≥ 0.85 | 154/287 (53.66%) | 154/163 (94.48%) |
| 平均角点误差 ≤ 1% 对角线 | 229/287 (79.79%) | 154/163 (94.48%) |
| 平均角点误差 ≤ 2% 对角线 | 265/287 (92.33%) | 157/163 (96.32%) |
| 平均角点误差 ≤ 3% 对角线 | 271/287 (94.43%) | 159/163 (97.55%) |
| mask difference ≤ 0.01 | 5/287 (1.74%) | 52/163 (31.90%) |
| mask difference ≤ 0.05 | 171/287 (59.58%) | 153/163 (93.87%) |
| mask difference ≤ 0.10 | 245/287 (85.37%) | 159/163 (97.55%) |

旧版 `.90/.80/.05` 联合门、图宽 1% 角点门和 `.75/.65/2%` 可用门仍完整保存在 `MODEL_INITIALIZATION_AUDIT_LEGACY_V1_THRESHOLDS.md` 及共享 CSV 的原字段中。若以后要把其他误差重新变成硬门，应使用独立人工“可编辑性/返工量”结局前瞻校准；不能依据当前 Test 结果反向挑阈值，也不应把已用于开发的 Validation 当独立校准集。

## 数据与复现

- 全量逐图 CSV：`analysis_results/model_initialization_audit_hybrid_gt_20260823_v4/model_initialization_metrics.csv`
- 旧版阈值报告：`analysis_results/model_initialization_audit_hybrid_gt_20260823_v4/MODEL_INITIALIZATION_AUDIT_LEGACY_V1_THRESHOLDS.md`
- 运行清单：`analysis_results/model_initialization_audit_hybrid_gt_20260823_v4/run_manifest.json`
- GPU 重跑证据：`analysis_results/model_initialization_audit_hybrid_gt_20260823_v3/GPU_REPLAY_MANIFEST.json`
- checkpoint SHA-256：`9f2522c0311064a863e838fa345e9b49dc14f95cb1608ba19e942a875344efa9`
