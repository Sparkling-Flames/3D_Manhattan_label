# 三人开发分工 v4 — Phase 1（数据清洗 + 可视化 + 扰动算子）

> 生成日期：2026-03-01（基于导师语音 + 最新提纲修订）  
> 依据：`01_研究问题.tex` / `02_方法.tex` / `04_报告与可审计输出.tex`，英文正文 `03_problem_formulation.tex` / `04_system_design.tex`，导师两段语音，以及 `tools/` 下脚本实际盘点。

---

## 0. 现有活跃脚本盘点（先纠错）

> **前提澄清**：`tools/legacy/` 下全部脚本均已废弃，不计入基础。

| 脚本 / Notebook | 状态 | 实际功能 |
|---|---|---|
| `analyze_quality.py` | ✅ 活跃主力（1828 行） | v2 结构化字段解析、OOS/NA/scope/difficulty/model_issue、IoU 计算、gate 检测 |
| `visualize_output_v2.ipynb` | ✅ 主可视化 notebook（最近有执行记录） | 门控失败分布图、指标直方图、按标注员通过率表 |
| `visualize_output.ipynb` | ✅ **v1 内部全量诊断版**（与 v2 配套，输出目录独立）| 与 v2 配套分工：**v1 = Internal 全量（调参/排障/质控）**，输出 `internal_figures_v1/`；**v2 = Paper Slim（论文精简输出）**，输出 `paper_figures_v2/`；v1 含 Figure Registry 表（`paper_core`/`paper_appendix`/`internal_only` 三档分级）|
| `aggregate_analysis.py` | ✅ 多数据集合并 API（无 CLI） | 跨 CSV 合并 + 分组统计，有配置 schema |
| `create_labelstudio_split_by_outline.py` | ✅ 最新数据分组（N=458） | Pilot→PreScreen→Main 全分组，含 anchor/core/reserve |
| `split_active_logs.py` | ✅ 活跃日志切分 | `active_time` 按 session 切分 |
| `diagnose_gating_bias.py` | ✅ gate selection-bias 诊断 | OOS/scope_missing 过滤分析 |
| `save_quality_figures.py` | ❌ **实际不可运行** | `from viz_quality_utils import ...` → `viz_quality_utils.py` **文件不存在** |
| `viz_quality_report.py` | ⚠️ 转发 wrapper | `from tools.legacy.viz_quality_report import main` → 指向 legacy，功能受限 |

**结论**：v1 + v2 是配套设计（v1 顶部 markdown 明文说明分工：v1=Internal，v2=Paper Slim），两者均不废弃；v2 有 2 个 cell 有执行记录，v1 零执行但功能更完整（63 cells）；`save_quality_figures.py` 是死代码，留 Phase 2 修复。

---

## 1. 可行性严谨评估

### 1.1 阶段一范围定义（你的规划）

> "第一阶段：数据清洗 + 可视化，以及其扰动算子这个算法实现出来。"

| 子任务 | 现有基础 | 缺口 | 可行性判断 |
|---|---|---|---|
| **数据清洗** | `analyze_quality.py` 90% 就绪 | 跨数据集合并无 CLI 入口；`active_time` 字段输出格式待规范 | ✅ **高可行** |
| **可视化** | `visualize_output_v2.ipynb` 已有门控/指标分布/按标注员通过率 | 缺：Worker×Scene 矩阵（表 C）、工人画像二维散点图（图 D，3 类功能组）、`active_time` 审计展示 | ⚠️ **中等**，2 个核心新模块需从头写 |
| **扰动算子** | tools/ 中无相关代码；`model_issue` 归档结构已知 | 定义明确（详见 §1.2） | ✅ **可行**，角点级扰动生成器，实现量适中 |
| **$d_t$ OOD 风险代理** | `infer_layout.py` 已有 HOHONet 加载 + 推理管线 | 需注册 `horizon_refinement` 输出 hook 提取 $e_t$；构建 kNN 索引 | ✅ **可行**，依赖现有推理基础设施（详见 §1.3） |

### 1.2 「扰动算子」的真实含义——来自论文 §3.1/PreScreen（已修正，非导师语音）

> ⚠️ **之前对扰动算子的理解有误。下面是论文 `03_实验设置.tex` 的正式定义，已修正。**

**扰动算子（Perturbation Operator）= 可复现地生成「误导性初始化」**，用于 `PreScreen_semi`：

- **来源**：Pilot 阶段 `model_issue` 归档——如 `corner_drift`、`corner_duplicate`、`overextend_adjacent` 等
- **对齐约束（必须补齐）**：扰动类型集合必须与 Label Studio 标注界面中的 `model_issue` 别名集合一致（见 `tools/label_studio_view_config.xml`），并与论文附录 [A1_扰动算子库.tex](docs/overleaf_project/sections/A1_扰动算子库.tex) 的 
   `model_issue`→算子映射表一致。否则会出现“工程实现可生成的误导类型”与“论文披露/标注体系中的类型”不一致，属于审稿中会被直接指出的可复现性缺陷。
- **操作**：给定真实角点标注（模型预测结果），施加扰动类型，输出扰动后角点坐标作为"误导性初始化"
- **冻结机制**：Pilot 后锁定扰动清单 + 随机种子，生成 `perturbation_plan_frozen.json`，之后只读
- **目的**：测量候选标注员的**纠错能力**（能否识别并修正误导初始化）与**盲信风险**（直接提交半自动输出）
- **论文原文**（`03_实验设置.tex`）： `"PreScreen_semi 用于测量纠错能力与盲信风险，误导性初始化由扰动算子生成并冻结清单与随机种子"`，以及 `"基于 Pilot 的 model_issue 归档锁定扰动算子集合与强度范围，作为后续 PreScreen_semi 误导性初始化生成的主实现"`

**IID/non-IID 应激切分（`difficulty_split.py`）是完全独立的机制：**

| 维度 | 扰动算子 | IID/non-IID 应激切分 |
|---|---|---|
| 论文位置 | §3.1 PreScreen；MDE §3.4 | §3.1 第一段 IID Stress Test |
| 作用阶段 | Stage 1 PreScreen（筛工人） | Stage 3 Validation（评策略鲁棒性）|
| 操作对象 | **角点坐标**（施加几何扰动） | **数据子集切分**（按 difficulty 分层）|
| 目的 | 生成可复现误导样本 | 模拟分布偏移（non-closed-world）|
| 与导师语音的关系 | 导师语音 §5 提到的半自动误导 | 导师语音提到的难度分层 OOD 场景 |



### 1.3 Phase 1 工作量客观估计（三人 × 约 4 周）

| 模块 | 工时估计 | 负责 | 依赖 |
|---|---|---|---|
| 数据清洗 pipeline CLI 封装 + 跨数据集合并 | 3–4 人天 | Dev A | `analyze_quality.py` + `aggregate_analysis.py` 已有 API |
| `active_time` 字段规范化输出（`split_active_logs.py` 已有，补 spec 对齐） | 1–2 人天 | Dev A | 现有脚本扩展，不重写解析逻辑 |
| LOO 可靠度 `r_u` + BCa bootstrap CI + Type 1–4 flag | 3–4 人天 | Dev A | 新增函数扩展 `analyze_quality.py` |
| `visualize_output_v2.ipynb` 补全 Cell 组（T/I/M、IAA、IoU_edit、反例频次） | 2–3 人天 | Dev B | notebook 已有骨架 |
| `active_time` 审计展示 Cell + `active_time` 异常摘要表 | 1–2 人天 | Dev B | 依赖 Dev A 规范化输出的字段 |
| Worker×Scene 矩阵（表 C，含 LCB 排序 + 局部失效标注） | 3–4 人天 | Dev B | 依赖 Dev A 的 `r_u_s`（Week 3 后才可用，前期用 mock）|
| 工人画像二维散点图（图 D，3 类功能组） | 2–3 人天 | Dev B | 依赖 Dev C 的 `S_u` 回写 |
| **扰动算子（PreScreen_semi 硬前置）**：`perturbation_operators.py`（角点级误导生成 + 冻结引擎） | 4–5 人天 | Dev C | 依赖 Pilot `model_issue` 归档；类型集合需与 XML + 附录 A1 对齐 |
| **$d_t$ OOD 代理**：提取 HoHoNet 共享 pre-head latent，经宽度池化与 L2 归一化后计算 kNN 距离 | 2–3 人天 | Dev C | `infer_layout.py` 加载模式可复用；参考集建议用 `Calibration_manual` 固定池（N=100）以获得稳定尺度（anchor=12 仅作 sanity check）|
| IID/non-IID 应激切分（`difficulty_split.py` + KL 验证） | 1–2 人天 | Dev C | 基于 `d_t` 分位数 + difficulty 标签 |
| 离线 Replay 框架（三策略：子集选取 + IAA 调用） | 2–3 人天 | Dev C | 实质为子集选取 + `compute_iaa` 调用，已有 mock 接口 |
| **合计** | **~23–32 人天** | — | — |

三人并行 4 周（每人约 5 人天/周 × 4 = 20 人天）基本可行；其中 **扰动算子 + 冻结清单**是 `PreScreen_semi` 的硬前置，应在 Week 1 优先闭环。$d_t$ 模块需 Week 1 先确认推理环境（`ckpt/` 权重 + GPU/CPU 可用），若环境不可用则降级为仅用 $g_t$ 触发进行分层（附录披露）。

---

## 2. 分工原则——v3 → v4 提纲变化摘要

| 变化点 | 对分工的影响 |
|---|---|
| **「扰动算子」有了明确含义（论文 §3.1/PreScreen）** | = 可复现角点级误导生成（非数据切分），Dev C 实现 `perturbation_operators.py`；IID 切分是独立的 `difficulty_split.py` |
| **新增 $d_t$ OOD 代理（论文 §2.8，HoHoNet shared latent kNN）** | Dev C 新增 `compute_dt_score.py`；字段 `d_t` 与 `I_t^{OOD}` 写入 `merged_all.csv`，供 IID 应激切分与路由触发使用 |
| **Worker 功能分组采用 3 类（Stable/Vulnerable/Noise）** | Dev B 的「图 D」按二维坐标（$\mathrm{LCB}(r_u),S_u$）展示 3 类功能组；分组规则由预注册阈值与风险桶失效条件决定 |
| **新增 Type 4 反例（字段缺失/NA + 元标签不合规）** | Type 4 拆成两类：①可由采集协议前移控制的“空选/互斥冲突”（提交时硬校验，记录被拦截次数作为过程证据）；②系统侧 NA/导出缺损（仍需在清洗输出中审计并披露）。|
| **`viz_quality_utils.py` 不存在，`save_quality_figures.py` 不可运行** | Dev B **主战场改为 notebook（`visualize_output_v2.ipynb`）而非补写 utils 模块** |
| **导师语音强调「process evidence + 中间结果」** | 每位 Dev 交付物必须能直接产出图（存 PNG，可引用进论文） |
| **`active_time` 日志审计表是口径 T 必报项** | Dev A 规范化字段输出（复用 `split_active_logs.py`）；Dev B 负责审计展示 Cell |

---

## 3. 三人分工（Phase 1）

### 人员角色假设
- **Dev A**（你）：熟悉 `analyze_quality.py`，负责数据清洗与核心指标计算
- **Dev B**：负责可视化，**主战场为 `visualize_output_v2.ipynb`**（向该 notebook 追加新 cell 组）
- **Dev C**：负责**扰动算子**（`perturbation_operators.py`，角点级可复现误导生成，PreScreen_semi 用）+ **IID 应激切分**（`difficulty_split.py`）+ 离线 replay 框架

> 若三人角色不同请按下面接口说明调整，不影响架构。

---

### Dev A（数据清洗 + 核心指标）

**交付物：**

1. **`tools/clean_pipeline.py`**（新建）
   - CLI 入口：`python tools/clean_pipeline.py --config clean_config.json`
   - 功能：
     - 拉取所有 Label Studio 导出 CSV/JSON → 归一化字段（已有 `parse_quality_flags_v2`）
     - 输出 `data/cleaned/merged_all.csv`（含 `dataset_group`、`condition`、`subset`、所有 flag；字段见接口约定）
     - 附：`data/cleaned/type4_process_failures.csv`（字段缺失/NA 明细，Type 4 反例候选）
     - `active_time` 字段直接从 `split_active_logs.py` 现有输出对接，格式规范化后写入 `merged_all.csv`（异常展示由 Dev B 的 Cell 组 5 负责）

2. **`analyze_quality.py` 新增函数**（在现有文件上扩展）：
   - `compute_iaa(task_submissions) → float`：中位数两两 IoU，对应 `IAA_t`
   - `compute_loo_reliability(submissions_df) → worker_reliability_df`：输出含 `r_u`、`LCB`、`UCB`、`h_u`，BCa bootstrap 置信区间
   - `detect_type4_failures(df) → series[bool]`：字段缺失/NA/导出缺损等系统侧 Type 4 检测（注意：空选/互斥冲突优先由提交时硬校验前移控制，但仍需在离线清洗中做兜底审计）
   - `classify_worker_group(df) → series[str]`：按预注册规则分入 3 类（Stable/Vulnerable/Noise，见下方说明）

3. **`tests/test_data_cleaning.py`**（新建，最小可跑）
   - 用 `tests/` 下小样本 fixture 验证 `parse_quality_flags_v2` 边界（NA、混合判定）

**3 类 Worker 功能分组（与论文提纲一致）：**

| 分组 | 条件（预注册阈值） | 可视化符号 |
|---|---|---|
| Noise | `LCB(r_u) ≤ τ_{r,low}` 或 `S_u ≥ τ_{S,high}` | 灰色方块 |
| Vulnerable | `LCB(r_u) > τ_{r,low}` 且 `S_u < τ_{S,high}`，并满足 `Δ_u ≥ τ_{gap}` 或存在高风险桶使 `LCB(r_u^{(b)}) ≤ τ_{r,low}` | 橙色三角 |
| Stable | 不属于 Noise 与 Vulnerable 的其余 worker | 蓝色实心圆 |

**接口约定（供 Dev B / C 使用）：**

```python
# merged_all.csv：核心字段（最小集合，允许扩展）
# 说明：difficulty/model_issue 均为多选。工程侧以 Label Studio XML 的 alias 为稳定ID，
# 并用分号 ';' 连接（与 tools/analyze_quality.py 一致）。
# 任何需要 one-hot / per-tag κ 的统计在分析阶段按 ';' 拆分展开。
#
# 必需（跨模块硬依赖）：
# task_id, annotator_id, condition, subset, dataset_group,
# active_time,
# iou, iou_manual, iou_corner, iou_edit,
# scope, scope_missing, is_oos,
# difficulty,             # 多选 alias 串：如 'occlusion;low_texture'
# model_issue,            # 多选 alias 串（可含 acceptable，用于审计原始选择）
# scope_filled,           # bool：scope 是否非空（UI 侧应强制必填；分析侧仍审计）
# difficulty_filled,      # bool：difficulty 是否非空（UI 侧应强制至少选1项；分析侧仍审计）
# difficulty_conflict,    # bool：trivial 与其他困难标签共存（不合规，需审计/复核）
# model_issue_required,   # bool：是否应填写 model_issue（仅 semi 条件）
# model_issue_missing_required,  # bool：semi 条件下 model_issue 空选/缺失（不合规）
# model_issue_conflict,   # bool：acceptable 与其他 issue 共存（不合规，需审计/复核）
# has_model_issue,        # bool：是否存在任意非 acceptable 的问题（用于二值切分/审计）
# model_issue_types,      # 仅问题类型（排除 acceptable），';' 连接
# model_issue_primary,    # 多选时的确定性“主问题”（用于需要单标签的图/表）
# IAA_t, iou_to_consensus_loo,
# r_u, r_u_lcb, r_u_ucb, h_u,
# type1_flag, type2_flag, type3_flag, type4_flag,
# d_t,                    # Dev C 写入（HOHONet penultimate embedding kNN OOD 代理）
# S_u,                    # Dev C 回写
# worker_group,
# core_scene,
# r_u_s
#
# 可选扩展（用于诊断/对齐基准，不作为其他模块硬依赖）：
# layout_2d_iou, layout_3d_iou, layout_depth_rmse, layout_delta1,
# gate reasons / pairing meta 等。
```

**时间估计**：7–9 人天

---

### Dev B（可视化模块）

**前置依赖**：Dev A 交付 `merged_all.csv` 及字段约定（可先用 mock CSV 开发）

**主战场：`visualize_output_v2.ipynb`**（向该 notebook 末尾追加新 Cell 组；不新建 utils 模块）

> `viz_quality_utils.py` 不存在，`save_quality_figures.py` 已破损，Phase 1 **不修复**，留 Phase 2。

**交付物：**

1. **`visualize_output_v2.ipynb` 新增 5 个 Cell 组**
   - **Cell 组 1**：T/I/M 三口径分布对比（条形图，按 `condition` 分组）
   - **Cell 组 2**：IAA 直方图（`IAA_t` 分布，按 `difficulty` 叠加密度曲线）
   - **Cell 组 3**：IoU_edit vs. IoU_2d 散点图（检测"退改"模式，标注 Type 3 flag 点）
   - **Cell 组 4**：Type 1–4 反例频次汇总水平条形图（每类按 `dataset_group` 堆叠），并补充 Type 4 的拆解披露：NA/导出缺损 vs. 元标签不合规（空选/互斥冲突）；若启用提交时硬校验，还需同时报告“被拦截提交次数/原因分布”以作为过程证据
   - **Cell 组 5**：`active_time` 审计展示（每 annotator 时长分布 + P99 异常标注，输入字段直接来自 `merged_all.csv` 的 `active_time` 列，Dev A 规范化输出后即可用）
   - 所有 cell 末尾：`fig.savefig("paper_figures_v2/XXX.png", dpi=150, bbox_inches="tight")`

2. **`tools/plot_worker_profile.py`**（新建，独立脚本，用于图 D）
   - 横轴：`S_u`（spammer score）；纵轴：`r_u_lcb`（可靠度下界）
   - 颜色/形状区分 3 类功能组：Stable（蓝色实心圆）/ Vulnerable（橙色三角）/ Noise（灰色方块）
   - 输出 `paper_figures_v2/fig_D_worker_profile.png`

3. **`tools/plot_worker_scene_matrix.py`**（新建）
   - 输入：`merged_all.csv`（`r_u_s`、`core_scene` 字段由 Dev A 提供）
   - 输出：热力图（行=worker，列≤4 个核心场景+other）
   - 单元格显示 `r_u^(s) ± CI`，不达 $N_{u,s,\min}$ 显示 `--`
   - 局部失效三条判别准则自动标红（绝对阈值 / 相对下降 / 保守显著性）
   - 输出 `paper_figures_v2/fig_C_worker_scene_matrix.png`

**时间估计**：8–10 人天

---

### Dev C（扰动算子 + IID 应激切分 + 离线 Replay）

> **「扰动算子」论文正式定义**（`03_实验设置.tex`，§3.1 PreScreen）：  
> 可复现地将真实角点标注派生为**误导性初始化**，类型来自 Pilot `model_issue` 归档（`corner_drift` / `corner_duplicate` / `overextend_adjacent` 等）；清单与随机种子 Pilot 后冻结，用于 `PreScreen_semi` 测量标注员**纠错能力**与**盲信风险**。

> **IID/non-IID 应激切分**（论文 §3.1 前半段，与扰动算子相互独立）：  
> 按 difficulty meta-label 分层切分，模拟训练/验证集分布偏移（non-closed-world / 非 IID）。

**交付物：**

0. **采集协议的硬校验与兜底审计（P0，避免 Type 4 可控项落入后验自由度）**
   - Label Studio 视图配置：`tools/label_studio_view_config.xml`（required + 统一 alias）
   - 提交时互斥硬阻断与审计计数：正式入口为 `tools/official/ls_userscript_annotator.js`；调试/巡检入口为 `tools/official/ls_userscript_debug.js`（Submit/Update 阶段阻断互斥冲突；记录被拦截次数与原因）
   - 导出兜底校验：`tools/meta_label_guard.py`（对导出 JSON 生成 accepted/rejected 清单与原因统计；主分析输入默认只用 accepted，同时披露 reject rate）

1. **`tools/perturbation_operators.py`**（新建，扰动算子实现；PreScreen_semi 硬前置）

   - **算子集合必须覆盖附录 A1 与 XML 的 `model_issue`：**
    `acceptable`（No-op/轻微扰动）、`overextend_adjacent`、`corner_drift`、`corner_duplicate`、`underextend`、`over_parsing`、`topology_failure`、`fail`。
   - **冻结清单字段对齐附录 A1：**至少包含 `operator_id`、`lambda_level`、`seed`，并写入脚本版本哈希（可用 git commit hash 或文件 hash）。

   ```python
   class AcceptableOperator:
      """acceptable：不施加强扰动；可选轻微扰动用于检验细调能力"""
      def apply(self, corners: list[dict], seed: int, lambda_level: str = "weak") -> list[dict]: ...

   class OverextendOperator:
      """overextend_adjacent：沿门洞方向外推并跨越门框停止点"""
      def apply(self, corners: list[dict], seed: int, lambda_level: str) -> list[dict]: ...

   class CornerShiftOperator:
      """corner_drift：对局部角点受限平移"""
      def apply(self, corners: list[dict], seed: int, lambda_level: str) -> list[dict]: ...

   class CornerDuplicateOperator:
      """corner_duplicate：在同一物理拐角附近插入冗余角点"""
      def apply(self, corners: list[dict], seed: int, lambda_level: str) -> list[dict]: ...

   class UnderextendOperator:
      """underextend：裁剪部分边界段或删除局部角点"""
      def apply(self, corners: list[dict], seed: int, lambda_level: str) -> list[dict]: ...

   class OverParsingOperator:
      """over_parsing：插入伪角点或伪折线段（小配额，弱强度即可）"""
      def apply(self, corners: list[dict], seed: int, lambda_level: str = "weak") -> list[dict]: ...

   class TopologyFailureOperator:
      """topology_failure：制造配对/闭合不稳定（固定小配额）"""
      def apply(self, corners: list[dict], seed: int) -> list[dict]: ...

   class FailOperator:
      """fail：生成明显不可用但仍可从零重画的初始化（固定小配额）"""
      def apply(self, corners: list[dict], seed: int) -> list[dict]: ...

   class PerturbationEngine:
      """按冻结清单批量生成误导性初始化，保证可复现"""
      def __init__(self, frozen_plan: dict): ...
      def generate_batch(self, tasks: pd.DataFrame) -> pd.DataFrame: ...

   def freeze_plan(operator_configs: list[dict], seed: int,
               output_path: str = "data/perturbation_plan_frozen.json") -> dict:
      """冻结扰动清单 + 种子（Pilot 后生成一次，之后只读）"""
   ```

2. **`tools/compute_dt_score.py`**（新建，$d_t$ OOD 代理计算）

   ```python
   # 依赖：torch（no_grad），sklearn.neighbors.NearestNeighbors
   # 1. 复用 infer_layout.py 的 HOHONet 加载模式，冻结权重
   # 2. 注册 forward hook 捕获 model.horizon_refinement 输出 → e_t（1D feature）
   # 3. torch.no_grad() 批量推理，抽取 e_t 并 flatten
   # 4. 参考集建议用 Calibration_manual 的固定图像池（N=100）以获得稳定的 kNN 距离尺度
   #    （anchor=12 仅用于可靠度锚点，不适合作为 kNN 参考分布；可用于 sanity check）
   #    NearestNeighbors(n_neighbors=10, metric="euclidean").fit(ref_embeddings)
   # 5. d_t = mean of K=10 nearest L2 distances（公式见 §2.8）
   # 6. 将 d_t 列写入 merged_all.csv（或单独 embeddings/dt_scores.csv）
   # CPU fallback：无 GPU 时自动降级并打印警告（>100 张图约 3–5 min）
   def compute_dt(model_ckpt: str, image_dir: str, anchor_csv: str,
                  output_csv: str, K: int = 10) -> pd.DataFrame:
       """主入口；返回含 d_t 列的 DataFrame"""
   ```

3. **`tools/difficulty_split.py`**（新建，IID/non-IID 应激切分——独立于扰动算子）

   ```python
   def derive_difficulty_level(difficulty_tags: str) -> str:
         """将 Label Studio 多选 difficulty tags（如 'occlusion;seam'）映射到 {easy, medium, hard}。
       规则在 Week 1 锁定并预注册；脚本内只读该规则（可由 JSON 配置注入）。
       """

   class DifficultyBasedSplit:
       """训练=easy/medium，验证=hard（非闭世界外推，§3.1 模式 A）"""
       def split(self, df, difficulty_col="difficulty",
                 train_levels=["easy", "medium"], test_levels=["hard"]
       ) -> tuple[pd.DataFrame, pd.DataFrame]: ...

   class IIDBreaker:
       """有偏采样打破 IID（§3.1 模式 B）"""
       def split(self, df, train_ratio: dict, test_ratio: dict, seed=42
       ) -> tuple[pd.DataFrame, pd.DataFrame]: ...

   def validate_kl_divergence(train, test, col="difficulty") -> float:
       """KL 散度验证，附录 q∈{85,90,95} 敏感性分析配套"""
   ```

4. **`tools/offline_replay.py`**（新建）
   - 输入：`merged_all.csv` + difficulty split 产出的子集
   - 三种策略（Random / GlobalReliability / Stratified）在候选池内选 k' 个 worker 的真实标注
   - 输出：`data/replay/replay_results.csv`（含 `IAA_t_replay`、`strategy`、`k_used`、`split_mode`）
   - 接口：`run_replay(df, split, strategies, k_range=[1,2,3]) → replay_df`

5. **`tools/compute_spammer_score.py`**（新建，轻量）
   - 计算 `S_u`：各 worker 标注与 LOO 共识偏离度分位数，写回 `merged_all.csv`

6. **`tests/test_perturbation_operators.py`**（新建）
   - 用 mock 角点坐标验证三种算子输出格式与可复现性（相同 seed → 相同输出）
   - 验证 `freeze_plan` JSON 读回后精确复现

**时间估计**：9–11 人天（`d_t` 计算 2–3 天，扰动算子 4–5 天，difficulty split + replay 2–3 天，tests 1 天）

> 注：如果按附录 A1 完整补齐算子集合（含低频类型）并做强度档位回归测试，扰动算子部分通常需要 4–5 天；上面的总工时按“核心算子优先闭环 + 低频类型小配额/弱强度”的实现策略估算。

---

## 4. 接口与协作约定

```
┌─────────────────────────────────────────────────────────────────┐
│  Dev A: clean_pipeline.py → merged_all.csv                      │
│         (task_id, r_u, r_u_lcb, S_u placeholder, worker_group) │
└───────────────────────────┬──┬──────────────────────────────────┘
                            │  │
       ┌────────────────────▼  │
       │  Dev B: visualize_output_v2.ipynb（new cells）           │
      │          plot_worker_profile.py（图 D，二维画像）         │
       │          plot_worker_scene_matrix.py（表 C）              │
       └───────────────────────┘
                            │
       ┌────────────────────▼────────────────────────────────────┐
      │  Dev C: perturbation_operators.py（角点误导生成，PreScreen_semi 前置）│
      │          compute_dt_score.py（d_t OOD 代理，HOHONet kNN）               │
       │          difficulty_split.py（IID应激切分）        │
       │          offline_replay.py（3策略×2切分模式）            │
       │          compute_spammer_score.py                        │
       │         → d_t → merged_all.csv；replay_results.csv, S_u → Dev A 合并回写      │
       └─────────────────────────────────────────────────────────┘
```

**接口约定优先级（必须在 Week 1 对齐）：**

| 字段 | 说明 | 由谁产出 |
|---|---|---|
| `r_u`, `r_u_lcb`, `r_u_ucb` | 全局可靠度 + BCa CI | Dev A |
| `h_u` | 95% CI 半宽（`(r_u_ucb-r_u_lcb)/2`） | Dev A |
| `S_u` | spammer score | Dev C → 回写给 Dev A 合并 |
| `d_t` | OOD 风险代理（HOHONet kNN 均値距离） | Dev C → 写入 `merged_all.csv` |
| `worker_group` | 3 类功能组标签（Stable/Vulnerable/Noise） | Dev A（阈值三人商定后预注册） |
| `core_scene` | 最多4个核心场景标签 | Dev A（由 meta-label 共识频率确定） |
| `r_u_s` | 场景特异可靠度 | Dev A（供 Dev B 画矩阵） |

---

## 5. Phase 1 里程碑

| 周次 | Dev A | Dev B | Dev C |
|---|---|---|---|
| Week 1 | `clean_pipeline.py` 跫通，`merged_all.csv` 格式锁定（29 列） | 用 mock CSV 搞好 notebook 新 Cell 组 1–2 骨架 | **扰动算子 Week 1 闭环**：`perturbation_operators.py` 核心算子（`overextend_adjacent`/`corner_drift`/`corner_duplicate`）+ `freeze_plan` 输出字段对齐附录 A1；`PerturbationEngine.generate_batch` 在小样本上可复现；配合 WS‑P（Owner: Dev B）完成采集协议自动化 gate 的集成测试（XML/userscript/meta_label_guard） |
| Week 2 | `compute_iaa`、LOO `r_u`（BCa bootstrap）函数通过单元测试 | Cell 组 3–4（IoU_edit 散点图、Type1–4 反例条形图）完成 | 低频算子（`underextend`/`over_parsing`/`topology_failure`/`fail`）小配额补齐；`compute_dt_score.py` 批量计算完成，`merged_all.csv` 中 `d_t` 字段可用；`difficulty_split.py` 跫通 |
| Week 3 | Type1–4 flag 写入 CSV；`classify_worker_group`（3类）完成 | `plot_worker_scene_matrix.py`（表 C，局部失效标红）完成 | `PerturbationEngine.generate_batch` 批量生成验证；`offline_replay.py` 三策略跑通 |
| Week 4 | `active_time` 审计表完成；测试覆盖率 >80% | Cell 组 5（审计表）+ `plot_worker_profile.py`（图 D）完成 | `compute_spammer_score.py` 输出 `S_u`；replay 对齐真实标注；集成测试通过 |

---

## 6. Phase 1 不做的事（留 Phase 2）

| 功能 | 原因 | Phase 2 接口 |
|---|---|---|
| 插件化（Label Studio plugin / REST API 接口） | 导师明确列为 Phase 2 | 基于 Phase 1 `offline_replay.py` 协议扩展 |
| 自动化检测（CI 触发的实时质量报警） | 需要部署环境，Phase 1 无实时数据流 | 利用 Phase 1 图表模块 + GitHub Actions |
| 扰动算子扩展（新增/改名的 `model_issue` 类型，如 `corner_flip` / `gap_insert`） | Phase 1 已按附录 A1 + Label Studio XML 的 alias 集合对齐实现；Phase 2 仅在 Pilot 新证据支持下新增类型或调整强度档位，并同步更新附录与 XML | 扩展 `perturbation_operators.py` + 更新附录 A1 + 同步 XML |
| 加权共识 $w_u$ 裁剪优化（$w_{\max}$ K 折选择） | 需要 PreScreen 专家参考数据（尚未收集） | Phase 2 `calibration_pipeline.py` |
| 反例库人工复核流程 | 需标注员参与，Phase 1 仅自动检测候选 | Phase 2 Label Studio 工单流 |
| `save_quality_figures.py` 修复（`viz_quality_utils` 补写） | Phase 1 notebook 已满足绘图需求；修复成本高 | Phase 2 重构为独立 CLI 工具 |



*如需进一步细化某一模块的接口设计（例如 `PerturbationEngine` 的角点坐标格式约定、`difficulty_split.py` 的分位数阈值预注册方案、Worker×Scene 矩阵的图表样式），在本文档对应章节补充即可。三人须在 Week 1 结束前对齐：① `merged_all.csv` 的 29 列字段定义（之后锁定不变）；② `perturbation_plan_frozen.json` 的角点坐标格式（供扰动算子与 Label Studio 导入共用）。*

## 7. 交付导向的分工重构（补充说明）

### 核心目标
- **目标 1**：Week 1 避免 Dev C 任务过载，将“采集协议硬校验/审计链路”独立成可验收入口。
- **目标 2**：把 `ls_userscript.js` 的 meta-guard 与 `HOHONET_META_GUARD_*` schema 冻结成稳定接口，降低 1855 行文件耦合风险。
- **目标 3**：将“算子 alias 与 XML choices”对齐从口头变成自动化硬门（`; operator name` 与 `label_studio_view_config.xml` 的 alias 集合一致）。
- **目标 4**：每条工作流都需自带 gate checklist（文档 + 自动化测试 + 过程证据），防止“挡在门外就当没发生”。

### Workstream 划分与交付
| Workstream | Owner | 核心交付 | 验收 gate |
|---|---|---|---|
| WS-P（Protocol & Audit） | Dev B | P1：审计日志与规则文档（`tools/README.md`）；P2：本地审计导出/聚合脚本；P3：`meta_label_guard.py` 与 `ls_userscript.js` 对齐测试；P4：聚合后的 reject stats 报告 | Gate：JSON schema 与 README 同步；`meta_label_guard.py --fail-on-reject` 在示例出口绿灯；每周边界报告附带 reject rate + reason distribution |
| WS-E（Engine） | Dev C | E1：`perturbation_operators.py` + `perturbation_plan_frozen.json`；E2：`compute_dt_score.py` + `difficulty_split.py`；E3：`offline_replay.py` / `compute_spammer_score.py` | Gate：算子 alias 集合与 XML & 附录 A1 完全一致；`tests/test_perturbation_operators.py` 强制 seed 重现；`compute_dt_score` 在 Calibration_manual 上跑通；replay 策略输出带 hash log |
| WS-R（Release & Verification） | Dev A | R1：字段冻结文档；R2：验收清单与 gate checklist；R3：三人对齐报告（risk log + status） | Gate：每次合并前必须有 gate checklist；`merged_all.csv` 字段变更需写入 README；审计报告附 process evidence（reject counts + gate status），WS-R 签字后才能合入 |

### 协作与周节奏调整
- `merged_all.csv` 继续作为 Single Source of Truth，字段定义必须在 Week 1 freeze，任何改动需登记 gate checklist。\
- `HOHONET_META_GUARD_REJECTIONS / STATS` 结构写入 `tools/README.md` 并在 P1 中说明版本号与变更策略；聚合脚本读取该 JSON 并输出团队级审计。\
- `perturbation_plan_frozen.json` 与 `perturbation_operators.py` 的 operator name ↔ alias 对齐由 WS-R 通过 `tests/test_operator_alias_alignment.py` 自动化检查。\
- Week 1：Dev C 将任务拆成“扰动器 + freeze plan + alias gate”，并与 Dev B 共同推动 P3 自动化测试，避免 6–8 人天的重叠；Dev B 启动 P1–P4 审计链路；Dev A 完成 gate checklist 草案并组织三人对齐会议。
