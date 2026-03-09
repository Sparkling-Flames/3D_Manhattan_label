# HoHoNet 标注分析工具包

本工具包提供用于分析 3D 房间布局标注质量（来自 Label Studio）以及为双流 HoHoNet 模型准备数据集的脚本。

## 当前目录说明（2026-03-07）

- `tools/official/`：正式实验推荐入口。只放正式标注与正式分析要用的脚本。
- `tools/`：当前实验在用脚本与共享依赖（split、导入准备、分析、汇总、可视化、运维辅助）。
- `tools/legacy/`：已归档的旧版、分叉版、历史原型。
- `tools/legacy/research_prototypes/`：阶段性原型或历史脚本（不作为当前主流程入口）。

若需复现实验，优先以 `tools/official/` 和 `docs/README_INDEX.md` 的“当前必读”为准。

**相关文档**：

- [测试计划与代码审查](../docs/TEST_PLAN_AND_REVIEW.md)：完整测试用例、CFG/COC、代码缺陷分析
- [数据流与门控说明](../docs/ANALYSIS_DATA_FLOW.md)：从 Label Studio JSON → CSV 的完整管线
- [交接文档索引](../docs/README_INDEX.md)：所有文档的快速导航

---

## 测试

本工具包包含单元测试和集成测试，详见 [tests/README.md](../tests/README.md)。

```bash
# 运行所有测试
pytest tests/ -v

# 运行带覆盖率报告
pytest tests/ --cov=tools --cov-report=html
```

---

## 脚本边界与职责划分（审稿人视角 / 可审计设计）

遵循 **Krippendorff (可靠性理论)** 和 **Artstein-Poesio (IAA 设计)** 的"单一事实源 + 可审计"原则，本工具链的核心脚本职责如下：

| 脚本                     | 层级          | 职责                                                                         | 输出                                               |
| ------------------------ | ------------- | ---------------------------------------------------------------------------- | -------------------------------------------------- |
| `analyze_quality.py`     | **上游/计算** | 从 Label Studio JSON 解析数据、计算所有指标（L1–L4）、应用门控规则、生成 CSV | `quality_report_*.csv`、`reliability_report_*.csv` |
| `visualize_output.ipynb` | **下游/展示** | 读取 CSV、做 sanity check（一致性校验）、生成论文图表                        | 图表、Markdown 摘要                                |

### 字段权威性（Single Source of Truth）

- **上游权威字段**（由 `analyze_quality.py` 计算，下游只读取不重算）：
  - `scope_missing`：scope 字段是否缺失（bool）
  - `is_oos` / `is_normal`：scope 派生的 OOS/In-scope 判定（tri-state: True/False/None）
  - `layout_used` / `layout_gate_reason`：L1 标准 layout 指标门控
  - `iou_to_consensus_loo` / `consensus_uid_loo`：L3 可靠性指标（LOO 共识）
  - 所有指标列（`iou`、`boundary_rmse_px`、`layout_2d_iou` 等）

- **下游派生字段**（`visualize_output.ipynb` 仅用于展示/sanity check）：
  - `scope_clean` / `is_oos_clean` / `is_normal_clean`：对 scope 列做标准化后重新判定（用于一致性校验）
  - `data_valid_for_main` / `data_valid_for_reliability`：论文图表的样本掩码
  - `flag_*`：异常标记（如 `flag_active_time_zero`）

### 门控层次（Gating Layers）

本工具链区分两套独立的门控系统，**不可混淆**：

| 层级                    | 门控字段                             | 用途                                                               | 适用范围                            |
| ----------------------- | ------------------------------------ | ------------------------------------------------------------------ | ----------------------------------- |
| **L1 标准 layout 指标** | `layout_used` / `layout_gate_reason` | 控制 `layout_2d_iou` / `layout_3d_iou` 等 HoHoNet 风格指标的有效性 | 角点配对、覆盖率、深度渲染          |
| **L3 可靠性/LOO 共识**  | `iou_to_consensus_loo.notna()`       | 控制该行是否参与 IAA/r_u 计算                                      | In-scope + layout_used + 多标注任务 |

> **审稿人关注点**：LOO 共识只应包含"通过 L1 门控且 In-scope"的标注，否则会被质量不合格的几何污染。

### 本版本修复（2026-01-18）

1. **LOO 门控修复**：`task_user_poly`（用于共识/LOO 计算）现在仅在 `layout_used==True` 时才加入，防止被门控排除的行进入共识计算。
2. **scope_missing 口径**：v2 模式下无结构化 scope 字段时，不再回退到 legacy `quality` 文本推断 `is_normal`；改为 `scope_missing=True, is_normal=None`。
3. **scope_missing 列输出**：CSV 现在始终包含 `scope_missing` 列，下游无需重复推导。

---

## 功能特性

1.  **质量分析 (`analyze_quality.py`)**:
    - **双重指标**: 同时计算语义 IoU（2D 多边形）和布局 IoU（基于 1D 角点），以评估标注质量的不同方面。
    - **标注者间一致性**: 自动检测具有多个标注者的任务，并计算成对一致性（IoU）以识别专家共识。
    - **边缘案例检测**: 突出显示“修改最多”的任务（潜在的模型失败）和“几何误差高”的任务（潜在的 3D 畸形），以便进行人工复核。
    - **效率追踪**: 将实际标注时间与修改幅度相关联。

2.  **数据集准备 (`prepare_dual_dataset.py`)**:
    - 将 Label Studio JSON 导出文件转换为 HoHoNet 兼容格式：
      - **布局 (Layout)**: 包含角点坐标的 `.txt` 文件。
      - **语义 (Semantics)**: 用于语义分割训练的 `.png` 掩码。

## 安装

确保已安装以下 Python 依赖项：

```bash
pip install numpy scipy shapely matplotlib
```

## 使用方法

### 1. 分析标注质量

#### 1.1 生成质量报告 CSV

对 Label Studio 导出的 JSON 文件运行分析脚本：

```bash
# 方式 1：直接运行（推荐，需要在项目根目录执行）
python tools/analyze_quality.py path/to/project-export.json --metric corner --quality_mode v2

# 方式 2：使用 python -m（从任何目录都可以）
python -m tools.analyze_quality path/to/project-export.json --metric corner --quality_mode v2
```

**推荐用法（正式标注，从项目根目录执行）**：

```bash
# 主对照集分析 (Manual Test)
python tools/analyze_quality.py export_label/manual_test_export.json --dataset_group Manual_Test --project_version v1.0 --metric corner --quality_mode v2 --output_dir analysis_results

# 校准集分析 (Calibration Manual)
python tools/analyze_quality.py export_label/calibration_manual_export.json --dataset_group Calibration_manual --project_version v1.0 --metric corner --quality_mode v2 --ru_min_tasks 5 --output_dir analysis_results
```

**参数说明:**

- `--metric`: 选择摘要的主要指标。
  - `corner`（**推荐默认**）: 强制使用布局角点 IoU（Corner-only 工作流，降低标注成本）。
  - `auto`: 如果存在手动多边形则使用手动 IoU，否则使用角点 IoU。
  - `manual`: 强制使用语义多边形 IoU（需要标注者绘制 polygon）。
- `--dataset_group`: **（关键）** 标注数据所属的实验组。例如：`Manual_Test`、`SemiAuto_Test`、`Calibration_manual`、`Validation_semi` 等。用于下游 Notebook 的纵向对比。
- `--project_version`: 版本标识，如 `v1.0`。
- `--output_dir`: 保存 CSV 报告的目录（默认：`analysis_results`）。
- `--no_smooth`: 禁用 `boundary_rmse_px` 的边界曲线平滑。
- `--pair_warn_min_coverage`: 配对覆盖率阈值 (0-1)。如果关键点无法很好地配对，脚本将设置 `pairing_warning=true` 并发出有限的控制台警告。

#### 1.2 可视化质量分析（推荐）

生成质量报告后，使用以下工具进行交互式或批量可视化：

**方式 A：Jupyter Notebook（推荐用于探索式分析）**

```bash
# 启动 Jupyter Lab
jupyter lab

# 打开 tools/viz_quality_analysis.ipynb
# 修改 CSV 路径并逐个运行 cell 查看分析结果
```

**方式 B：批量生成图表（用于报告/演示）**

```bash
python tools/save_quality_figures.py analysis_results/quality_report_20260116.csv --out-dir analysis_results/figures --tag pilot_20260116 --metric iou
```

生成的图表包括：

- `scope_distribution.png`: Scope 分布（in-scope vs OOS）
- `layout_gate_reasons.png`: Layout gating 拒绝原因统计
- `iou_distribution_by_scope.png`: IoU 分布直方图（按 scope 分层）
- `iou_vs_time.png`: 指标 vs 标注时间散点图
- `iou_by_annotator.png`: 标注者间指标箱线图
- `time_by_annotator.png`: 标注者耗时箱线图
- `task_annotator_heatmap.png`: 任务×标注者热力图（发现分歧）
- `mixed_scope_tasks.png`: Mixed-scope 任务可视化（如存在）

同时生成 `SUMMARY.md` 和 3 个 CSV 表格（低 IoU 样本、高边界误差、高分歧任务）。

**Python 函数库（用于自定义分析）**

```python
from viz_quality_utils import (
    load_quality_report,
    compute_task_summary,
    plot_metric_distribution,
    # ... 其他函数
)

# 加载数据
df = load_quality_report("quality_report.csv")

# 绘图（返回 matplotlib figure 对象）
fig = plot_metric_distribution(df, metric="iou", hue="scope")
fig.show()  # Jupyter 里自动显示
# fig.savefig("my_plot.png", dpi=200)  # 保存到文件
```

- `--boundary_method`: 边界曲线生成方法。
  - `auto`（默认）：当 pred/ann 都能规范化为成对 cor_id 时使用 `connect`，否则回退到 `heuristic`。
  - `connect`: 融合 HoHoNet 正规做法，使用 `pano_connect_points` 连接相邻角点后再周期插值得到边界曲线。
  - `heuristic`: 直接对配对后的 (x, y_ceiling, y_floor) 列做周期插值。

- `--quality_mode`: 质量标签解析模式。
  - `v2`（**推荐默认**）: 严格按当前 `label_studio_view_config.xml` 的新标签解析（必须用于正式标注）。
  - `legacy`: 兼容旧版试标/旧配置的标签文本（仅用于历史数据）。
  - `auto`: 两者取并集（探索性，不推荐）。

### 标注对象与字段约定（必须严格执行）

**标注范围**：只标"相机所在主房间（camera room）"的布局包络。

**v2 字段设计**（推荐用于正式标注）：

- `scope`（**单选，必填**）：决定任务是否进入主指标
  - `In-scope：只标相机房间`：能在不猜的情况下稳定闭合 → **进入主指标**
  - `OOS：几何假设不成立` / `OOS：边界不可判定` / `OOS：错层/多平面` / `OOS：证据不足`：主指标**默认剔除**
- `difficulty`（多选）：解释耗时/误差来源（仅参考，不影响指标）
  - `遮挡` / `低纹理` / `拼接缝` / `反光` / `低质/被遮罩影响`
  - `尽力调整但 3D 仍不佳`：不等于 OOS，用于难例分层
- `model_issue`（多选，仅半自动）：标注初始化问题（见下）

**字段填写约定**：

- `scope` 必填
- 若没有明显困难因素或半自动初始化无需修改，则 `difficulty/model_issue` 可**留空**（不要为了"填满"而勾选）
- 当 `scope=OOS` 时，`model_issue` 允许留空（OOS 不在初始化评价范围内）

### model_issue 选项详解（仅半自动初始化条件）

- `overextend_adjacent`：模型跨门包含相邻空间（范围错）
- `underextend`：模型漏标部分边界/墙角（点数/覆盖不足）
- `over_parsing`：过度解析，把柱子/家具边缘/装饰凸凹等非布局结构误判为角点/边界（点数冗余，需做“减法”）
- `corner_drift`：角点位置偏移/漂移（位置错）
- **`corner_duplicate`**：同一物理拐角附近出现多个点（一角多点，需要删到只剩一个最合理角点）
- `topology_failure`：拓扑/配对/闭合失败（ceiling-floor 对不齐、无法闭合或配对严重错乱）。注意：若主要问题是点数偏多/偏少，优先选 over_parsing/underextend
- `fail`：初始化结果严重误导/大范围错误，基本需要从零重画（但场景仍可能 In-scope）。仅当其他具体错误类型都无法概括时选此项。

**兼容说明（历史数据）**：若旧版数据中存在 `corner_mismatch`，分析代码会按“拓扑失败”口径将其映射为 `topology_failure`，避免统计断裂。

**使用建议**：

- 针对不同的初始化错误选择精确的选项（避免都选 fail）
- 当 `scope=OOS` 时，`model_issue` 允许留空

**输出结果:**

- **任务级报告**：`quality_report_YYYYMMDD.csv`，包含每个任务的指标（IoU、RMSE、active_time、scope/difficulty/model_issue、OOS 门控等）
- **用户级报告**：`reliability_report_YYYYMMDD.csv`，包含每个标注者的 $r_u$（leave-one-out 共识）与 bootstrap 置信区间
- **控制台输出**：
  - 平均 IoU/RMSE（分层统计：In-scope vs OOS）
  - 每个标注者的统计数据（时间、质量、$r_u$）
  - **Scope 一致性**：任务级别是否存在"混合投票"（某些标注者选 In-scope，其他选 OOS）
  - **边缘案例候选**：供论文/报告复核的具体任务 ID
  - **OOS 分布**：OOS 比例、OOS 子类分布

  ### 1.4 元标签合规拦截（Type 4 预防）

  为降低 Type 4（流程/字段失败）发生率，建议采用“双层防线”：

  1. 前端（best-effort）：
     - **空选硬阻断**：由 Label Studio XML（`tools/label_studio_view_config.xml`）的 `required="true"` 负责（至少选 1 项）。
     - **互斥冲突硬阻断**：`tools/ls_userscript.js` 在 Submit/Update 时阻断互斥冲突（`trivial`+其他困难标签 / `acceptable`+其他 issue）。
      - **责任边界**：脚本不负责“空选拦截”，只负责“互斥冲突拦截”；空选是否可提交由 XML 配置决定。
     - 默认开启；如需临时关闭：浏览器控制台执行 `localStorage.setItem('HOHONET_STRICT_META_GUARD', '0')`
     - 恢复开启：`localStorage.removeItem('HOHONET_STRICT_META_GUARD')`
      - 审计日志（本地）：被拦截提交会写入 `localStorage.HOHONET_META_GUARD_REJECTIONS`（最近 200 条）与 `localStorage.HOHONET_META_GUARD_REJECT_STATS`（计数汇总）。
      - **可见性范围**：上述日志保存在当前浏览器本地存储（按浏览器配置文件/机器隔离），默认只能看到“自己这台机器/这个账号环境”的拦截记录，不能直接看到其他标注员机器上的本地日志。
  2. 后端（审计兜底）：运行 `tools/meta_label_guard.py` 对导出 JSON 做拒收审计。

  ```bash
  python tools/meta_label_guard.py export_label/your_export.json --out-dir analysis_results --fail-on-reject
  ```

  #### 本地审计日志获取与导出（浏览器控制台）

  1) 查看原始日志（最近 200 条）与汇总统计：

  ```javascript
  JSON.parse(localStorage.getItem('HOHONET_META_GUARD_REJECTIONS') || '[]')
  JSON.parse(localStorage.getItem('HOHONET_META_GUARD_REJECT_STATS') || '{}')
  ```

  2) 导出为 JSON 文件（便于归档/汇总）：

  ```javascript
  (() => {
    const logs = JSON.parse(localStorage.getItem('HOHONET_META_GUARD_REJECTIONS') || '[]');
    const stats = JSON.parse(localStorage.getItem('HOHONET_META_GUARD_REJECT_STATS') || '{}');
    const payload = {
      exported_at: new Date().toISOString(),
      logs,
      stats,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `meta_guard_audit_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  })();
  ```

  3) 如需“全员可见”的统一审计，请在服务端集中采集（例如在提交拦截时上报到统一 API，或统一收集每位标注员导出的 JSON），本地 localStorage 方案本身不具备跨机器聚合能力。

  输出：

  - `analysis_results/meta_guard_accepted.csv`
  - `analysis_results/meta_guard_rejected.csv`

  说明：`--fail-on-reject` 在发现拒收记录时返回退出码 2，便于接入 CI 或批处理流水线。

---

### 1.3 可视化函数库参考

`viz_quality_utils.py` 提供了以下可复用函数：

#### 数据处理函数

| 函数                                     | 功能                                        | 返回      |
| ---------------------------------------- | ------------------------------------------- | --------- |
| `load_quality_report(csv_path)`          | 加载并规范化 quality_report CSV             | DataFrame |
| `compute_task_summary(df, metric_cols)`  | 将多标注者行聚合为一行一个任务              | DataFrame |
| `compute_disagreement_table(df, metric)` | 计算任务间方差，识别高分歧任务              | DataFrame |
| `filter_in_scope(df)`                    | 过滤出 scope 为 In-scope 的行               | DataFrame |
| `filter_layout_used(df)`                 | 过滤出 layout_used=True 的行                | DataFrame |
| `build_summary_stats(df)`                | 生成汇总统计（任务数、标注者、gate 原因等） | Dict      |

#### 可视化函数（均返回 matplotlib figure 对象）

| 函数                                                 | 功能                   | 推荐参数                              |
| ---------------------------------------------------- | ---------------------- | ------------------------------------- |
| `plot_scope_distribution(df, figsize)`               | Scope 分布条形图       | `figsize=(10, 4)`                     |
| `plot_layout_gate_reasons(df, figsize)`              | Layout gating 拒绝原因 | `figsize=(10, 4)`                     |
| `plot_metric_distribution(df, metric, hue, bins)`    | 指标分布直方图         | `hue="scope"`, `bins=25`              |
| `plot_metric_vs_time(df, metric, hue, style)`        | 指标 vs 时间散点图     | `hue="scope"`, `style="annotator_id"` |
| `plot_metric_by_annotator(df, metric)`               | 标注者间指标箱线图     | `metric="iou"`                        |
| `plot_time_by_annotator(df)`                         | 标注者间时间箱线图     | 无                                    |
| `plot_task_annotator_heatmap(df, metric, max_tasks)` | 任务×标注者热力图      | `metric="iou"`, `max_tasks=60`        |
| `plot_mixed_scope_tasks(df)`                         | Mixed-scope 任务可视化 | 无                                    |

**示例工作流：**

```python
# 加载数据
from viz_quality_utils import load_quality_report, plot_metric_distribution
df = load_quality_report("quality_report.csv")

# 绘图并在 Jupyter 中显示
fig = plot_metric_distribution(df, metric="iou", hue="scope")
fig.show()

# 保存到文件
fig.savefig("iou_dist.png", dpi=200, bbox_inches="tight")
```

---

### 2. 准备训练数据

转换标注数据以用于训练：

```bash
python tools/prepare_dual_dataset.py path/to/project-export.json --output_dir data/custom_dataset
```

## 指标说明

- **IoU (交并比)**: 衡量初始模型预测与用户最终标注之间的重叠程度。
  - _低 IoU_: 表示用户进行了显著修改（模型失败或用户修正）。
  - _高 IoU_: 表示与模型预测一致。
  - 注意：你们当前的界面是“全景图（equirect）上的 corner + polygon 标注”，因此这里默认的 `iou_manual/iou_corner` 更接近**图像空间（screen-space）一致性**，并不等价于 layout literature 常说的 floorplan/3D 占据 IoU。
- **RMSE (均方根误差)**: 衡量角点的几何偏差。高 RMSE 伴随高 IoU 可能表示“像素位移小，但几何变化大”。
- **Pointwise-RMSE (辅)**: 仅在“角点 1-1 对齐可信”时启用的精细改动幅度指标。
  - 先将无序角点规范化为 HoHoNet 风格 `cor_id`（ceil/floor 成对、按 x 排序）。
  - 在全景拼接缝存在循环移位风险时，对“列”做 cyclic shift 对齐，取最小 RMSE。
  - 通过门控避免“点数相同但错配/乱序”导致的误导；门控阈值用 `--pointwise_min_coverage`。
- **Boundary-RMSE (推荐)**: 当点数不一致时，用于全景图布局的鲁棒几何偏差指标。
  - 通过 x 轴邻近度将无序关键点转换为成对的天花板/地板列。
  - 将 $y_{ceil}(x)$ 和 $y_{floor}(x)$ 周期性插值到固定的密集 x 轴网格上。
  - 计算 `boundary_mse = mean((\Delta y_{ceil})^2 + (\Delta y_{floor})^2)` 和 `boundary_rmse_px = sqrt(boundary_mse)`。
  - 默认应用可选的分段 Savitzky–Golay 平滑；使用 `--no_smooth` 禁用。

### 标准 Layout 指标（对齐 HoHoNet/HorizonNet）

为了对齐社区常用 layout 指标，`analyze_quality.py` 现在会在满足门控条件时，额外计算一组 HoHoNet 风格的“几何空间”指标（写入 CSV）：

- `layout_2d_iou`: 将 floor corners 投影到地面平面（top-down）后计算多边形 2D IoU。
- `layout_3d_iou`: 使用“柱体体积 IoU”近似：
  - 先算 floor polygon 的交面积 `A_inter` 与各自面积 `A_dt/A_gt`；
  - 再估计 ceiling 高度 `h_dt/h_gt`；

---

### 3. 汇总分析（跨数据集对比）

当你有多个 Label Studio 项目（如 Manual_Test、SemiAuto_Test、Calibration 等）的 quality_report CSV 时，使用 `aggregate_analysis.py` 进行批量汇总：

```bash
# 例子：汇总 5 个实验组的 CSV 指标
python tools/aggregate_analysis.py --csv main_manual:analysis_results/quality_report_manual_20260201.csv main_semi:analysis_results/quality_report_semi_20260201.csv calibration_manual:analysis_results/quality_report_calib_20260201.csv validation_manual:analysis_results/quality_report_valman_20260201.csv validation_semi:analysis_results/quality_report_valsemi_20260201.csv --output-dir analysis_results --output-prefix aggregate_final --formats csv json markdown
```

**参数说明：**

- `--csv`：支持两种格式
  - 位置映射（按配置文件中 dataset key 顺序）：`--csv path1.csv path2.csv ...`
  - 显式映射（推荐）：`--csv dataset_key:path.csv ...`
- `--config`：可选，指定自定义配置 JSON（默认使用内置的 5 数据集 schema）
- `--output-prefix`：输出文件名前缀（默认 `aggregate`）
- `--formats`：输出格式（csv/json/markdown，可多选）

**输出文件：**

1. `aggregate_final_YYYYMMDD.csv`：合并的全量明细，新增 `dataset`、`condition`、`subset` 列
2. `aggregate_final_YYYYMMDD_summary.json`：分组统计（按 condition/subset）+ 跨条件对比
3. `aggregate_final_YYYYMMDD_summary.md`：Markdown 对比表格（人工查阅）

**插件化设计（为未来开源准备）：**

脚本采用模块化架构，核心函数可独立调用：

```python
from tools.aggregate_analysis import load_csv_with_metadata, merge_csv_files, compute_summary_stats

# 示例：在自定义管道中使用
csv_paths = {"my_dataset": "path/to/report.csv"}
rows, metadata = merge_csv_files(csv_paths, config)
summary = compute_summary_stats(rows, group_by=["condition"], metric_cols=["iou_2d"])
```

配置文件 `tools/aggregate_config.json` 定义数据集元信息和对比策略，支持扩展到更多数据集或自定义分组。

---

## 论文/报告推荐指标选择

### 研究问题与主指标对应

| 研究问题                     | 主指标                  | 辅助指标                                   | 说明                                                |
| ---------------------------- | ----------------------- | ------------------------------------------ | --------------------------------------------------- |
| RQ1：效率（省时多少）        | `active_time`           | `boundary_rmse_px`, `iou_edit`             | 标注时间与改动幅度的对标                            |
| RQ2：质量（改得对不对）      | `iaa_t` (In-scope only) | `iou_to_consensus_loo`, `layout_2d/3d_iou` | 多标注任务的一致性；标准 layout 指标（仅 In-scope） |
| RQ3：分配（高 r_u 是否有益） | `ru_median_iou`         | `iou_to_others_median`                     | 基于 Manual 校准集估计，反映标注者个体稳定性        |

### CSV 字段快速查询

**实验分组与管理 (2026-01-25 更新)**：

- **`dataset_group`**：标注数据所属的实验组（如 `Manual_Test`）。用于下游 Notebook 的纵向对比。
- **`project_version`**：分析版本追踪（如 `v1.0`）。

**工作量代理（修改幅度）**：

- `iou` / `iou_corner`：图像空间 IoU（推荐用于 Corner-only 工作流）
- `boundary_rmse_px`：几何改动幅度（最鲁棒，不依赖点数一致）
- `active_time`：实际标注时间（秒）

**质量指标（仅 In-scope）**：

- `iaa_t`：多标注任务的成对 IoU 中位数（共识一致性）
- `iou_to_consensus_loo`：单个标注与 LOO 共识的 IoU
- `layout_2d_iou` / `layout_3d_iou`：HoHoNet 风格标准指标（需通过门控）
- `layout_depth_rmse` / `layout_delta1`：深度图对标

**可靠性（专家评分 $r_u$）**：

- `ru_median_iou`：用户的 LOO 共识中位数（仅 Manual 校准集）
- `ru_ci_low` / `ru_ci_high`：bootstrap 置信区间（95% 默认）

**OOS 与门控**：

- `scope_missing`：boolean，scope 字段是否缺失（2026-01-18 新增）
- `is_oos`：tri-state（True/False/None），是否被标注为 OOS；None 表示 scope 缺失
- `is_normal`：tri-state（True/False/None），是否 In-scope；None 表示 scope 缺失
- `layout_used`：boolean，是否成功计算标准 layout 指标
- `layout_gate_reason`：失败原因（`normalize_failed` / `low_coverage` / `n_pairs_mismatch` / `depth_failed` / `out_of_scope` / `scope_missing`）
- `scope` / `difficulty` / `model_issue`：原始标注选项

---

## 插件化路线图（Future Plugin Development）

当前工具链设计时已考虑未来开源插件化需求，核心设计原则：

1. **配置驱动**：数据集元信息、对比策略通过 JSON 配置文件定义，避免硬编码
2. **模块化 API**：每个核心功能（加载、合并、统计、导出）都是独立函数，可作为 Python 库导入
3. **可扩展输出**：支持 CSV/JSON/Markdown，预留 HTML/LaTeX 接口
4. **健壮错误处理**：缺失列/文件时 graceful degradation，详细日志记录
5. **文档齐全**：所有脚本包含 docstring、参数说明、使用示例

**未来插件形态（暂未实施，仅规划）：**

- PyPI 包发布：`pip install hohonet-quality-eval`
- Label Studio 插件：内嵌质量仪表板（实时 IAA/r_u 监控）
- CLI 工具：`hohonet-eval analyze export.json` 简化调用
- Web UI：可视化对比多数据集的 IoU/RMSE 分布 - 交体积用 `A_inter * min(h_dt, h_gt)`；
  - 最终 `IoU3D = V_inter / (V_dt + V_gt - V_inter)`。
- `layout_depth_rmse` / `layout_delta1`: 将 layout 渲染为深度图后，计算 RMSE 与阈值准确率（delta_1）。

门控/诊断：

- `layout_used`: 是否成功计算（需要 ceiling/floor 能成对、覆盖率足够；**不再**要求 pred/ann 角点对数一致）。
- `layout_gate_reason`: 失败原因（如 `normalize_failed/odd_points/low_coverage/x_inconsistent/depth_failed/out_of_scope/scope_missing`）。

建议用法（论文/汇报）：

- 将 `layout_2d_iou/layout_3d_iou` 作为“最终布局质量”的主指标；
- 将 `boundary_rmse_px` 作为“几何修改幅度/工作量代理”的辅指标；
- 将 `iou_manual`（若你们有手动 polygon）作为“图像空间可见一致性”的辅指标。

### 配对诊断（对论文级质量分析很重要）

由于 HoHoNet 输出角点，且脚本通过启发式方法将它们配对成天花板/地板列，CSV 还包含诊断信息：

- `pred_n_points`, `pred_n_pairs`, `pred_pair_coverage`, `pred_odd_points`
- `ann_n_points`, `ann_n_pairs`, `ann_pair_coverage`, `ann_odd_points`
- `pairing_warning`, `pairing_failure_reason`
- `boundary_method_used`（`connect` 或 `heuristic`）

Pointwise 辅指标相关字段：

- `pointwise_rmse_px`: 点对点 RMSE（仅在门控通过时有值）
- `pointwise_rmse_used`: 是否启用 pointwise 计算
- `pointwise_best_shift`: 最佳循环移位（按“列”计数）
- `pointwise_gate_reason`: 未启用原因（如 `low_coverage` / `n_pairs_mismatch` / `normalize_failed` 等）

### 共识与可靠度（r_u，最小实现）

当一个任务存在多个标注者时，脚本会基于标注者之间的 IoU 构建一个“共识标注”（medoid：与他人中位一致性最高的那份标注），并计算每个标注者与共识的重合度。

为避免“自我参与共识导致 r*u 虚高”，脚本同时提供 **leave-one-out**（剔除自身）版本：对每个 (task, user)，用其他标注者构建 $C_t^{(-u)}$，再计算 $\mathrm{IoU}(A*{t,u}, C_t^{(-u)})$。

CSV 会额外包含：

- `consensus_uid`: 该任务的共识标注者 ID（仅对多标注任务填充）
- `iou_to_consensus`: 当前标注者与共识标注的 IoU（共识自身为 1.0）

Leave-one-out 字段：

- `consensus_uid_loo`: 对当前标注者 u，剔除 u 后的共识标注者 ID
- `iou_to_consensus_loo`: $\mathrm{IoU}(A_{t,u}, C_t^{(-u)})$
- `iou_to_others_median`: 当前标注与其他所有标注的 IoU 中位数（不选代表，直接 summarize agreement）

控制台会打印一个按用户聚合的可靠度摘要：

- $r_u = \mathrm{median}_{t \in \mathcal{T}_u} \; \mathrm{IoU}(A_{t,u}, C_t^{(-u)})$（仅在多标注任务集合上计算，leave-one-out）

并支持：

- 最小任务数阈值：`--ru_min_tasks`（默认 5）
- bootstrap 置信区间：`--ru_bootstrap_iters`、`--ru_ci`、`--ru_seed`

#### 专家评分（方案 A：统一基准条件）

如果你的论文/实验采用“方案 A”（推荐）：**用纯人工 Manual 的校准任务估计标注者可靠度 $r_u$**，以避免“半自动初始化把大家拉到同一起点”导致 $r_u$ 被工具效应污染。

工程上最稳妥的做法是：

1. 在 Label Studio 中为 **Manual 校准集**（多标注、可重复）建立单独的项目或单独导出文件（确保所有参与者在同一条件下完成）。
2. 对该导出运行本脚本，读取输出的 `reliability_report_YYYYMMDD.csv`，其中 `ru_median_iou` 即为 $r_u$（leave-one-out）。

示例：

```bash
python tools/analyze_quality.py <manual_calibration_export.json> --active-logs active_logs --output_dir analysis_results --metric auto --ru_min_tasks 5
```

说明：

- $r_u$ 默认基于 `iou_to_consensus_loo`（LOO 共识）跨任务取中位数，并给出 bootstrap CI。
- 你可以同时参考 `iou_to_others_median`，它不依赖“共识代表选择”，更适合做稳健的 agreement 汇总与异常检测。

此外会在输出目录生成按用户汇总的 `reliability_report_YYYYMMDD.csv`，包含 `ru_median_iou`、CI 上下界与样本量。

使用这些字段可以：

- 过滤掉边界指标的无效样本，
- 明确报告失败案例，
- 证明采用显式配对标注（如果采用）可以提高鲁棒性。
- **一致性**: 对于具有 >1 个标注者的任务，衡量用户之间的一致程度。高一致性表明存在“地面真值 (Ground Truth)”。

## 扩展工具包

要添加新指标，请修改 `analyze_quality.py` 中的 `extract_data` 和 `main` 函数。该脚本采用模块化设计：

1.  **提取**: `extract_data` 将原始 JSON 解析为几何对象（多边形、点）。
2.  **计算**: 添加您的指标函数（例如 `compute_my_metric(poly1, poly2)`）。
3.  **报告**: 在主循环中将新指标添加到 `rows` 字典中。

---

## 生成实验数据集（可复现 split）

脚本 `tools/create_labelstudio_split.py` 用于从 `label_studio_import_docker.json`（带预测的任务池）中按 seed 随机切分出多个**互斥**子集，并写出对应的 Label Studio 导入 JSON：

- 主对照集（同一批图）：
  - `label_studio_manual_import.json`（去掉 predictions）
  - `label_studio_semiauto_import.json`（保留 predictions）
- 方案 A 校准集（Manual-only，用于估计 $r_u$）：
  - `label_studio_manual_calibration_import.json`
- 验证集（写出 Manual + Semi 两份，便于做分配策略对照）：
  - `label_studio_manual_validation_import.json`
  - `label_studio_semiauto_validation_import.json`
- （可选）Gold 集（Manual-only，用于仲裁 reference）：
  - `label_studio_manual_gold_import.json`
- 复现报告：
  - `label_studio_split_report.json`（记录 seed、数量、以及每个 split 的 title 列表）

示例：

```bash
python tools/create_labelstudio_split.py --num-per-group 100 --calib-count 30 --val-count 60 --gold-count 0 --seed 42 --output-dir import_json/seed42
```

提示：若任务池不足以支持总量（main + calib + val + gold），脚本会直接报错并提示所需数量。

## COS 批量上传与导入 JSON 生成

当图片迁移到腾讯云 COS 后，可用以下两步替代旧的 `http://<server>:8000/...` 方式：

> 关键说明：**COS 上传的是图片文件，不是 Label Studio 导入 JSON**。  
> `label_studio_import*.json` 由脚本本地生成后，在 Label Studio 后台导入即可。

详细中文说明见：`tools/COS_上传与导入中文说明.md`。

1. 批量上传 `data/mp3d_layout/test/img` 到 COS（保留原文件名，兼容原命名格式）：

```bash
python tools/upload_mp3d_test_to_cos.py \
  --bucket label-images-1389474327 \
  --region ap-guangzhou \
  --source-dir data/mp3d_layout/test/img \
  --key-prefix data/mp3d_layout/test/img
```

说明：

- 需要提前在环境变量中设置密钥：`AWS_ACCESS_KEY_ID` 与 `AWS_SECRET_ACCESS_KEY`。
- 可先加 `--dry-run` 仅生成清单，不实际上传。

2. 生成可导入 Label Studio 的任务 JSON（图片 URL 指向 COS）：

```bash
python tools/prepare_labelstudio_docker.py \
  --image-base-url https://label-images-1389474327.cos.ap-guangzhou.myqcloud.com/data/mp3d_layout/test/img \
  --vis-base-url http://175.178.71.217:8000 \
  --output-json label_studio_import_docker.json
```

说明：

- `--image-base-url` 会覆盖旧服务器图片地址拼接逻辑。
- 若暂时不用 3D 预览，增加 `--disable-vis3d`。
- 旧服务器版本脚本已保留在 `tools/legacy_server/prepare_labelstudio_docker_old_server.py`。

## Label Studio 助手 (用户脚本)

正式浏览器助手入口位于 `tools/official/ls_userscript_annotator.js`。调试/巡检版位于 `tools/official/ls_userscript_debug.js`。历史分叉 `tools/ls_userscript_updated.js` 已归档到 `tools/legacy/ls_userscript_updated.js`，不再作为正式入口。

### 浏览器设置 (推荐)

在浏览器控制台中运行一次（保存在 `localStorage` 中，直到清除网站数据）：

```js
// 1) Nginx 基准 URL，用于提供 /tools 和代理 /log_time
localStorage.setItem("HOHONET_HELPER_BASE_URL", "http://175.178.71.217:8000");

// 2) 可选 Token，用于保护 /log_time
localStorage.setItem("HOHONET_LOG_TOKEN", "<your-secret>");
```

### 云端无需 `assets/` 目录

如果您不想在 `assets/` 目录下托管图像，请启用 Nginx 到 Label Studio (8080) 的同源代理 `/ls/`。用户脚本将自动将 Label Studio 图像 URL 重写为 `http://<server>:8000/ls/...`，以便 3D 查看器可以加载 WebGL 纹理而不会出现 CORS 问题。
