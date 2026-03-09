# Label Studio 实验 SOP（按你已创建的 5 个项目）

适用项目：

- `Manual_Test`（主对照：纯人工，100）
- `SemiAuto_Test`（主对照：半自动初始化，100）
- `calibration_manual`（方案 A 校准：纯人工，多标注，30）
- `validation_manual`（验证集：纯人工，60）
- `validation_semi`（验证集：半自动初始化，60）

目标：在不混淆数据集/条件的前提下，完成“导入 → 多人重叠标注 → 导出 → 质量/效率/可靠度分析 →（可选）分配策略对照”。

---

## 0. 前置核对（只做一次）

- 界面 XML：确保每个项目都使用同一份 [label_studio_view_config.xml](label_studio_view_config.xml)（新版 choices，无 `complex`）。
- 质量解析模式：后续分析统一使用 `--quality_mode v2`。
- 日志（可选但建议）：如果你需要 active time（推荐），确保浏览器助手（Tampermonkey userscript）已启用且 `/log_time` 可写入 `active_logs/`。

> 核对点：随便打开一张任务，能看到 choices：
>
> - `范围判定 (scope, 单选)`：In-scope（camera room only）+ 多个 OOS 子类
> - `困难因素 (difficulty, 多选)`：遮挡/低纹理/拼接缝/反光/低质/尽力调整但 3D 仍不佳
> - `模型初始化问题 (model_issue, 仅半自动，多选)`：跨门扩张/漏标/漂移/角点重复/配对异常/预标注失效（OOS 时可不选）

---

## 1. 导入任务（一次性完成）

你已经有 split 脚本输出到 `import_json/`（默认）。假设目录是 `import_json/seed42/`，对应文件应为：

- 主对照：
  - `label_studio_manual_import.json`
  - `label_studio_semiauto_import.json`
- 校准（方案 A）：
  - `label_studio_manual_calibration_import.json`
- 验证：
  - `label_studio_manual_validation_import.json`
  - `label_studio_semiauto_validation_import.json`
- 报告（必留）：
  - `label_studio_split_report.json`

### 1.1 各项目导入对应 JSON

- `Manual_Test`：导入 `label_studio_manual_import.json`
- `SemiAuto_Test`：导入 `label_studio_semiauto_import.json`
- `calibration_manual`：导入 `label_studio_manual_calibration_import.json`
- `validation_manual`：导入 `label_studio_manual_validation_import.json`
- `validation_semi`：导入 `label_studio_semiauto_validation_import.json`

> 核对点：
>
> - `SemiAuto_Test`/`validation_semi` 打开任务后，应该能看到预测初始标注（prediction）。
> - `Manual_Test`/`calibration_manual`/`validation_manual` 不应该有 prediction。

---

## 2. 人员与标注策略（最关键：避免“难度混淆”和“ru 污染”）

假设参与者 N≈10。

### 2.1 主对照（100/100）

- `Manual_Test`：每张图 **只需 1 人**标注（用于效率/最终质量对照）。
- `SemiAuto_Test`：每张图 **只需 1 人**标注。
- 分配原则：两组内“有经验/新手比例”尽量一致；每人任务量相近。

> 产出：用于 RQ1/RQ2（效率与质量对照）。

### 2.2 校准集（方案 A，必须多标注）

- `calibration_manual`：30 张图，每张至少 **k≥3 人**独立标注。
- 这是计算专家评分 $r_u$ 的唯一来源（方案 A 统一基准条件）。

> 重点：不要在 semi 条件下算 $r_u$，否则工具效应会污染专家识别。

**可行分配（N=10, k=3）**：共 30×3=90 份标注，人均约 9 份。

### 2.3 验证集（用于分配策略对照，建议至少部分多标注）

- `validation_manual` / `validation_semi`：60 张。

两种选择（二选一）：

- **A（更硬）**：每张至少 2 人标注 → 可以直接比较 $IAA_t$ 的变化。
- **B（省成本）**：只抽 20 张做 2–3 人复核，其余 1 人标；用“复核子集”评估一致性。

---

## 3. 标注规范（建议写给标注者的最短口径）

- **标注对象定义（最重要）**：只标 **相机所在的主房间（camera room）** 的包络布局。

  - 门洞后/走廊/相邻房间等“连通空间”默认不纳入当前房间布局。
  - 不要以“3D 看起来更方正”为依据去扩张房间范围；以“主房间边界是否可合理闭合”为准。

- 先标 `Corner`（角点）。`Wall` polygon **可选**（用于辅助对齐/复核；当前主评估不依赖墙线时可不画）。

- choices（新版为 3 组字段）：`scope` 必填；`difficulty/model_issue` 仅在适用时填写（否则留空）。

  1. **范围判定 `scope`（单选，决定是否进入主指标；必填）**

  - `In-scope：只标相机房间 (Normal / Camera room only)`：主指标纳入。能在不"猜"的情况下稳定闭合包络；判据为墙-天花与墙-地面外边界可形成唯一、可复现的包络（存在稳定的 y_ceil(x), y_floor(x)）。
  - `OOS：几何假设不成立 (Out-of-scope / Non-Manhattan)`：主指标剔除。
  - `OOS：边界不可判定 (Open Boundary / Ambiguous camera-room boundary)`：主指标剔除。
  - `OOS：错层/多平面 (Split-level / Multi-level)`：主指标剔除。
  - `OOS：证据不足 (Insufficient evidence)`：主指标剔除。

  2. **困难因素 `difficulty`（多选，用于解释耗时/误差来源；无明显困难可留空）**

  - 遮挡/低纹理/拼接缝/反光/`画质差/被遮罩影响 (Blur/Masked/Low quality)`（例如上下被 mask/黑边导致证据缺失）
  - `尽力调整但 3D 仍不佳 (Hard to align / residual)`：遵守规则并充分调整后，3D 包络仍不稳定或畸形（不等同于 OOS）。

  3. **模型初始化问题 `model_issue`（仅半自动项目可选，多选；初始化很好无需修改可留空；OOS 时允许留空）**

  - `跨门扩张 (Over-extend)`：模型包含了门后相邻空间
  - `漏标 (Under-extend)`：模型漏掉了部分墙角/边界
  - `角点漂移 (Corner drift)`：角点位置有偏移，但总体拓扑合理
  - `角点重复/一角多点 (Duplicate corners)`**（新）**：同一拐角附近出现多个点（如某处 3 个点）；人工应删掉多余点，仅保留最准确的一个
  - `配对异常 (Odd/mismatch)`：predict 与 annotation 角点总数差异大、无法配对，或配对严重错乱（区别于 corner_duplicate，强调整体数量/拓扑问题）
  - `预标注失效 (Prediction Failure)`：大范围错误需从零重画；仅当其他类型都无法概括时选此项

> 约束：若选了 `scope=OOS`，`model_issue` 通常不必填（因为该样本不在评价范围）。

**门洞/相邻空间的处理（规则化）**

- 如果门框/墙垛清晰：边界 **止于门框/墙垛处**，不跨门洞；仍为 `scope=In-scope`。
- 如果没有任何清晰停止点、必须靠语义“猜”才能闭合：选 `scope=OOS：边界不可判定`，不要硬凑 cuboid。

**错层/下沉楼梯的处理（规则化）**

- 若存在下沉区域/楼梯井/多层地面或分层天花：选 `scope=OOS：错层/多平面`（按 OOS 处理）。
- 允许模型/人给出“单层近似”仍然看起来方正，但不要把它当作主指标样本；应在 OOS 子类中单列案例。

---

## 4. 导出（每个项目单独导出一次）

当某个项目完成标注后：

- 在该项目里导出 JSON（包含 annotations + predictions）。
- 文件命名建议包含项目名与日期，例如：
  - `export_label/manual_test_YYYYMMDD.json`
  - `export_label/semiauto_test_YYYYMMDD.json`
  - `export_label/calibration_manual_YYYYMMDD.json`
  - `export_label/validation_manual_YYYYMMDD.json`
  - `export_label/validation_semi_YYYYMMDD.json`

> 核对点：导出里能看到 `annotations` 数量与项目任务数一致。

---

## 5. 跑分析（命令模板）

**重要更新 (2026-01-25)**：为了支持下游 Notebook 的自动化纵向对比，运行分析时**必须**传入 `--dataset_group` 参数。

### 5.1 主对照：效率/质量对照 (RQ1/RQ2)

分别对 Manual 与 Semi 导出跑一次：

```bash
# Manual Test 分析
python tools/analyze_quality.py manual_test_export.json --dataset_group Manual_Test --project_version v1.0 --active-logs active_logs --output_dir analysis_results --metric corner --quality_mode v2

# SemiAuto Test 分析
python tools/analyze_quality.py semi_test_export.json --dataset_group SemiAuto_Test --project_version v1.0 --active-logs active_logs --output_dir analysis_results --metric corner --quality_mode v2
```

### 5.2 方案 A：专家评分 $r_u$ (仅用 calibration_manual)

```bash
python tools/analyze_quality.py calib_man_export.json --dataset_group Calibration_manual --project_version v1.0 --active-logs active_logs --output_dir analysis_results --metric corner --quality_mode v2 --ru_min_tasks 5
```

### 5.3 验证集分析

```bash
# Validation Manual
python tools/analyze_quality.py val_man_export.json --dataset_group Validation_manual --project_version v1.0 --active-logs active_logs --output_dir analysis_results
```

---

## 6. 在 Notebook 中进行统一分析

不要手动合并 Excel。直接打开 `tools/visualize_output.ipynb`：

1.  **更新清单 (MANIFEST)**：在 Section 0 中确认文件名与 `dataset_group` 的对应关系。
2.  **一键加载**：运行加载单元格，它会自动扫描所有 CSV，注入语义标签（`analysis_group`, `analysis_role`），并进行一致性校验。
3.  **多口径过滤**：使用内置的 `df_main` (正式性能) 和 `df_rel` (可靠性分析) 掩码，确保统计口径符合科研严谨性。

---

## 6. 论文/报告必须保留的复现材料

- `import_json/<seed>/label_studio_split_report.json`（记录 seed 与每个 split 的 title 列表）
- 每个项目的导出 JSON（原始数据）
- `analysis_results/quality_report_*.csv` 与 `reliability_report_*.csv`
- 若使用了旧版导出（含废弃 choice），必须在写作中声明其仅用于探索性分析，并与主实验（v2）分开。

---

## 7. 常见踩坑与快速自检

- **导错项目**：Semi 项目导入了 manual JSON → 打开任务看不到 prediction（立刻能发现）。
- **ru 没算出来**：校准集每张只有 1 人标 → 必须保证每张至少 2（建议 3）人。
- **OOS 混进主指标**：分析时确保 `--quality_mode v2` 且标注者确实勾选了 OOS；脚本会对 OOS 关掉标准 layout 指标并记录 gate reason。
- **active time 全是 0**：没跑用户脚本/日志服务没写入；可以先用 `lead_time` 兜底，但论文里要说明来源差异。

---

## 8. Pilot（强烈建议先做）

正式招募 10+ 标注员前，建议先按 [docs/pilot_plan.md](docs/pilot_plan.md) 跑一轮 2–3 人的小规模试运行，优先验证：字段填写率、门洞规则一致性、active time 覆盖率、以及 OOS 门控是否符合预期。
