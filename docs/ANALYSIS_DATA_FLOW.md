# HOHONET Analysis 数据流与反馈使用说明

## 问题 1: analyze_quality.py 收集哪些数据？

### 数据来源（三大块）

```
┌─────────────────────────────────────────────────────────────┐
│                    Label Studio 导出 JSON                     │
├─────────────────────────────────────────────────────────────┤
│ 1. Predictions 数据（模型初始化结果）                         │
│    └─ 角点坐标 (keypoints) + 多边形 (polygon)                │
│                                                              │
│ 2. Annotations 数据（标注者修改后的结果）                     │
│    ├─ 角点坐标 + 多边形                                      │
│    ├─ 标注者 ID (completed_by)                              │
│    ├─ Choice 反馈（scope/difficulty/model_issue）          │
│    └─ lead_time（标注耗时）                                 │
│                                                              │
│ 3. Task metadata                                             │
│    └─ task_id, multiple annotations (if multi-labeler)      │
└─────────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│             active_logs/*.jsonl（时间记录日志）              │
├─────────────────────────────────────────────────────────────┤
│ 由 Tampermonkey 脚本实时记录：                               │
│  {task_id, user_id, active_time, timestamp}                 │
│ 更精确的"有效标注时间"（排除暂停/离开）                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 问题 2: Label Studio 反馈具体怎么使用？

### 反馈字段解析流程（v2 配置）

```
Label Studio 前端选择
    │
    ├─ scope（单选）
    │   ├─ "In-scope：只标相机房间" → is_oos = False
    │   ├─ "OOS：几何假设不成立" ──┐
    │   ├─ "OOS：边界不可判定" ────┼─→ is_oos = True
    │   ├─ "OOS：错层/多平面" ─────┤
    │   └─ "OOS：证据不足" ────────┘
    │
    ├─ difficulty（多选）
    │   ├─ 遮挡、低纹理、拼接缝、反光、低质
    │   ├─ residual（尽力调整但3D不佳）
    │   └─ [用于难例分层，但不禁用计算]
    │
    └─ model_issue（仅Semi项目，多选）
        ├─ 跨门扩张、漏标、角点漂移
        └─ [记录模型失败原因，不影响质量计算]
```

### 反馈的三重作用

#### **第一层：门控（Gating）**

```python
if is_oos:
    layout_used = False              # 剔除标准 layout 指标
    layout_gate_reason = "out_of_scope"
    # 但 iou_manual/iou_corner 等仍然计算（可选记录）
else:
    # 核心修正 (2026-01-25):
    # n_pairs_mismatch 不再是硬门控 (不再阻断 IoU 计算)
    # 只要几何合法，2D/3D IoU、Depth RMSE 均会计算

    # 核心修正 (2026-01-26):
    # 进一步消除选择性偏差 (Selection Bias)。
    # 在分析层面 (Notebook)，df_main 不再要求 layout_used=True。
    # 只要标注为 In-scope，其 2D IoU 和 耗时均计入主表。
    # layout_used 仅用于筛选 3D 深度相关的几何指标。
    layout_used, layout_gate_reason = compute_layout_standard_metrics(...)
```

📌 **意义**：显著提升指标覆盖率（从 67% 提升至 98% 以上），避免因为"角点数量改变"导致的样本选择偏误。

---

#### **第二层：聚合统计（Stratification）**

```python
# CSV 输出包含
'scope': "In-scope"  或  "OOS：边界不可判定"  等
'difficulty': "遮挡;低纹理"  (多选用 `;` 连接)
'model_issue': "漏标;角点漂移"
'is_oos': True/False    (布尔值，方便筛选)

# 输出中自动分类统计
n_total = len(rows)
n_oos = len([r for r in rows if r.get('is_oos')])
n_normal = len([r for r in rows if r.get('is_normal')])
n_fail, n_occl, n_resid = ...

# 结果：
# Total: 100 | Normal: 70 | OOS: 15 | PredFail: 5 | Occlusion: 8 | Residual: 2
```

📌 **意义**：清晰展示"剔除了多少样本及原因"，避免审稿人质疑"挑反例"。

---

#### **第三层：一致性与可靠性计算（Reliability）**

**关键设计（2026-01-18 修复）**：`task_user_poly`（用于共识/LOO 计算）仅包含同时满足以下条件的标注：

- `is_oos == False`（In-scope）
- `scope_missing == False`（scope 字段存在）
- `layout_used == True`（通过 L1 门控）

**IAA（Inter-Annotator Agreement）计算时筛选**

```python
# 只计算 In-scope 且通过 L1 门控的多标注任务
for task_id, user_polys in task_user_poly.items():
    uids = list(user_polys.keys())
    if len(uids) < 2:
        continue  # 跳过单标注任务

    # 计算该任务的 pairwise IoU
    for uid_i, uid_j in combinations(uids, 2):
        iou_ij = compute_iou(user_polys[uid_i], user_polys[uid_j])
        # task_user_poly 已过滤，此处无需再检查 is_oos
```

**r_u（专家可靠性评分）计算方式**

```python
# 对每个标注者 u：
ru_values[u] = [
    IoU(u, consensus_from_others_excluding_u)
    for each multi-annotator task where u participated
]
# 仅来自 Manual 校准集（不混 Semi）、仅 In-scope

# 最终 r_u(u) = median(ru_values[u]) + bootstrap CI
# 示例输出（reliability_report_*.csv）：
#
# annotator_id  n_tasks  ru_median_iou  ru_ci_low  ru_ci_high
# user_001      12       0.8245         0.7890     0.8512
# user_002      12       0.7102         0.6445     0.7823
# user_003      8        0.5634         0.4112     0.6512  (样本不足，警告)
```

📌 **意义**：量化每位标注者相对共识的一致性，用于论文结论："User_001 的改动最可靠"。

---

## 完整数据流图（从 Choice 到 CSV 输出）

```
┌───────────────────────────────────────────────────────────────┐
│          Label Studio 导出 JSON + active_logs                 │
│                         │                                      │
│                         ▼                                      │
│         extract_data(results)  ────→ corners[], poly_points[] │
│         extract_data(annotation) ──┬─→ ann_corners, ann_poly  │
│         extract_data(prediction) ──┴─→ pred_corners, pred_poly│
│                                                                │
│         【Choice 解析】                                        │
│         parse_quality_flags(quality_str, mode="v2")          │
│         ─────────────────────────────────┐                   │
│                                          ▼                   │
│              is_oos, is_occlusion, is_fail, ...             │
│                        │                                      │
│                        ▼ (decision tree)                      │
│    ┌─────────────────────────────────┐                       │
│    │ if is_oos:                      │                       │
│    │   layout_used = False           │                       │
│    │   layout_gate_reason = "oos"    │                       │
│    │ else:                           │                       │
│    │   compute_layout_2d_3d_iou()    │                       │
│    └─────────────────────────────────┘                       │
│                     │                                          │
│                     ▼                                          │
│    【指标计算】                                               │
│    ├─ iou_manual, iou_corner (图像空间)                     │
│    ├─ layout_2d_iou, layout_3d_iou (3D/floor)              │
│    ├─ pointwise_rmse_px (点到点，如果点数一致)              │
│    ├─ boundary_rmse_px (曲线插值，鲁棒)                    │
│    └─ [更多见下表]                                           │
│                     │                                          │
│                     ▼                                          │
│    【一致性计算】                                             │
│    用 task_user_poly (仅 In-scope) 计算：                   │
│    ├─ consensus_uid (medoid)                                │
│    ├─ iou_to_consensus                                      │
│    ├─ consensus_uid_loo (不含自己)                          │
│    ├─ iou_to_consensus_loo  ──┬─→ r_u = median(这个) + CI  │
│    └─ iou_to_others_median   ──┘                            │
│                     │                                          │
│                     ▼                                          │
│    【单行 Row 输出】                                          │
│    {dataset_group, project_version, task_id, annotator_id,  │
│     active_time, iou, iou_manual, iou_corner,               │
│     layout_2d_iou, layout_3d_iou, layout_used, gate_reason, │
│     scope, difficulty, model_issue,                         │
│     is_oos, is_occlusion, is_fail,                          │
│     iou_to_consensus_loo, consensus_uid_loo, ...}           │
│                     │                                          │
│                     ▼                                          │
│    【CSV 输出】                                               │
│    quality_report_YYYYMMDD.csv  (任务 × 标注者 级别)          │
│    reliability_report_YYYYMMDD.csv  (用户级别 r_u 汇总)      │
└───────────────────────────────────────────────────────────────┘
```

---

## CSV 输出字段全览

### 2026-03-08 provenance 补充

当前 `analyze_quality.py` 的 CSV 已额外输出以下 provenance 字段，供 stage-aware 审计使用：

- `dataset_group_source`
  - 当前值通常为 `cli_argument`，表示该列仍主要来自运行参数而非 export 原文。
- `export_dataset_group`
  - 若 export 的 `task.data.dataset_group` 存在，则原样保留。
- `export_source_file` / `export_source_path`
  - 标明该行来自哪份 export JSON。
- `runtime_condition_source`
  - 当前固定为 `derived_from_prediction_presence`。
- `active_time_source`
  - `log / lead_time_fallback / missing`
- `active_time_match_status`
  - 当前至少区分 direct log 与 fallback。
- `lead_time_seconds`
  - 明确保留 fallback 原值，避免与 log active time 混淆。

### 2026-03-09 export inventory 补充

当前新增 `tools/audit_export_inventory.py`，用于把 `export_label/` 全目录冻结为可审计 source manifest，而不是继续靠口头区分 pilot 与 formal relevance。

新增输出目录：

- `analysis_results/export_inventory_20260309/export_inventory_v1.csv`
  - 每份 export 的 task/annotation 规模、schema 概况、run class、formal relevance、recommended_use。
- `analysis_results/export_inventory_20260309/export_inventory_summary_v1.json`
  - 汇总 counts 与文件级说明。
- `analysis_results/export_inventory_20260309/legacy_annotation_audit_v1.csv`
  - 专门列出 `legacy_quality_only / mixed / malformed` annotation，供 exclusion / compat 审计。

这一步的含义不是“这些 export 可以直接拿去做正式主分析”，而是把当前 pilot 导出在 A 线中的用途固定下来：

1. 可用于 provenance 校验。
2. 可用于 schema compatibility 审计。
3. 可用于 pipeline/formal wrapper 验证。
4. 默认不直接进入未来正式效应估计样本池。

| 字段                     | 来源                 | 用途                  | 示例                             |
| ------------------------ | -------------------- | --------------------- | -------------------------------- |
| **dataset_group**        | `--dataset_group`    | **实验组身份**        | "Manual_Test" / "Calibration"    |
| **title**                | Task Data            | **跨组配对主键**      | "pano_xxxx.png"                  |
| **analysis_role**        | `--analysis_role`    | 分析角色分类          | "performance" / "reliability"    |
| **project_version**      | `--project_version`  | 分析版本              | "v1.0"                           |
| **task_id**              | JSON                 | 关键识别              | "img_12345"                      |
| **annotator_id**         | completed_by         | 标注者 ID             | "user_001"                       |
| **active_time**          | active_logs          | 有效时间(s)           | 42.5                             |
| **iou**                  | 角点/多边形          | **主要质量指标**      | 0.85                             |
| **iou_manual**           | 多边形 IoU           | 语义空间一致性        | 0.88                             |
| **iou_corner**           | 角点派生             | 布局空间一致性        | 0.85                             |
| **boundary_rmse_px**     | 曲线 RMSE            | 鲁棒几何偏差          | 12.3                             |
| **layout_2d_iou**        | floor polygon        | 社区对标 (gated)      | 0.79                             |
| **layout_3d_iou**        | 柱体近似             | 社区对标 (gated)      | 0.72                             |
| **layout_used**          | 门控决定             | 是否进主指标          | True/False                       |
| **layout_gate_reason**   | 门控                 | 失败原因              | "normalize_failed" / "oos"       |
| **scope**                | Choice (scope 字段)  | OOS 分类              | "In-scope" / "OOS：边界不可判定" |
| **difficulty**           | Choice (difficulty)  | 难例标记              | "遮挡;低纹理"                    |
| **model_issue**          | Choice (model_issue) | 模型失败              | "漏标;角点漂移"                  |
| **scope_missing**        | parse_quality_flags  | scope 是否缺失        | True/False                       |
| **is_oos**               | parse_quality_flags  | 过滤（tri-state）     | True/False/None                  |
| **is_normal**            | parse_quality_flags  | In-scope（tri-state） | True/False/None                  |
| **iou_to_consensus_loo** | 多标注计算           | **r_u 计算用**        | 0.82                             |
| **consensus_uid_loo**    | 多标注计算           | 谁是参考              | "user_002"                       |
| **n_corners**            | ann_corners          | 质量检查              | 8                                |
| **pairing_warning**      | boundary 计算        | 点数不一致警告        | True/False                       |

---

## 论文/实验中的三重数据使用

### **RQ1（效率）**

```python
# 对比 Manual vs Semi 的 active_time
manual_times = df[df['project']=='Manual_Test']['active_time']
semi_times = df[df['project']=='SemiAuto_Test']['active_time']

time_save_rate = (1 - semi_times.mean() / manual_times.mean()) * 100
# 输出：半自动初始化节省 X% 的标注时间
```

### **RQ2（质量）**

```python
# 门控后的质量对比
non_oos_df = df[df['is_oos']==False]  # 仅 In-scope

manual_iou = non_oos_df[df['project']=='Manual_Test']['iou'].mean()
semi_iou = non_oos_df[df['project']=='SemiAuto_Test']['iou'].mean()

# 输出：半自动是否精度下降？ΔIoU = ?
```

### **RQ3（分配）**

```python
# 用 r_u 重新分配验证集
high_ru_users = [u for u in ru_df.annotator_id if ru_df[u]['ru_median_iou'] > 0.75]
# 将复杂任务分给 high_ru_users
# 对比："按 r_u 分配" vs "随机分配"的一致性提升

iaa_random = compute_iaa(validation_random_assigned)  # 0.68
iaa_smart = compute_iaa(validation_ru_assigned)       # 0.75
```

---

## 典型故障排查

| 问题                          | 原因                      | 解决方案                         |
| ----------------------------- | ------------------------- | -------------------------------- |
| `active_time` 全 0            | Tampermonkey 脚本未运行   | ✓ 检查 `/log_time` endpoint 可用 |
| `layout_used=False` 全部失败  | 点数不一致或标准化失败    | ✓ 检查 `layout_gate_reason` 值   |
| `is_oos=True` 比例过高 (>30%) | 标注者对 OOS 定义理解不清 | ✓ 补充示例图和 SOP 说明          |
| `iou_to_consensus_loo=None`   | 该用户只有单标注任务      | ✓ 增加多标注校准集任务           |
| `r_u` CI 超宽                 | 样本不足(<5) 或一致性太差 | ✓ 增加多标注任务或调查该用户     |

---

## 快速命令参考

````bash

---

## 问题 3: 如何操作多组数据的分析流 (CLI Guide)

为了保证实验的可复现性，建议采用统一流操作，即将不同实验组的数据保存到同一个中央 CSV 库。

### 1. 典型追加操作 (Multi-Group Command Line)
# 注意改一下output 的日期名字
```bash
# A. 初始化主报告并写入人工测试组 (Manual Test)
python tools/analyze_quality.py export_label/label_studio_manual_import.json --output analysis_results/quality_report_2026.csv --dataset_group Manual_Test --analysis_role performance

# B. 追加半自动测试组 (Semi-Auto Test)
# 注意: 必须使用 --append 参数，表头会自动校验对齐
python tools/analyze_quality.py export_label/label_studio_semi_import.json --output analysis_results/quality_report_2026.csv --append --dataset_group SemiAuto_Test --analysis_role performance

# C. 追加校准组 (Calibration) 用于专家评分 r_u 计算
python tools/analyze_quality.py export_label/label_studio_calib_import.json --output analysis_results/quality_report_2026.csv --append --dataset_group Calibration_manual --analysis_role reliability
````

---

## 问题 4: 数据库严谨性保证 (Robustness)

### A. 选择偏误修正 (Selection Bias Fix)

- **机制**：在 v2.0 之前的版本，配对失败会导致 IoU 变为 `NaN`。
- **现行逻辑**：IoU 初始默认值为 `0.0`。预测失败的样本将获得 0 分，确保性能统计覆盖所有已标注样本，防止指标虚高。

### B. 鲁棒追加 (Robust Append)

- **表头校验**：在 `--append` 模式下，脚本会自动对齐列。多余列被忽略，缺失列补空，杜绝“列移位”损坏。
- **物理属性校验**：Notebook 加载时会自动比对 `dataset_group` 与数据的实际 `condition`。例如，如果你误将包含预测的 JSON 标记为 `Manual_Test`，Notebook 会直接报错红色拦截。

---
