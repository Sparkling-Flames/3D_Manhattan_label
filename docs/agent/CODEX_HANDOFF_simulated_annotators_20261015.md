# Codex 任务交接：完善「模拟标注器（造数据）」工具

> **交付对象**：Codex（自主编码 Agent）。本文件自包含，按顺序读即可开工。
> **仓库根目录**：`/Users/ethan/Documents/ChatGPT/manha/3D_Manhattan_label`（下文所有相对路径都基于它；先在仓库根运行，不要 `cd` 到别处）。
> **当前分支**：`research/simulated-annotators-local-20261014`（**本地私有分支，永不推送**）。
> **期限**：本周（学长要求）。

---

## 0. TL;DR（一句话任务）

完善并跑通已有的「模拟标注器（造数据）」工具：按**四类真人模板（快好/快差/慢好/慢差）× 不同难度图片（简单/中等/困难/门洞，必要时 OOS）× 两种采集条件（Manual / Semi）**造出「逼真」的合成布局标注，并带**标注时间（active_time）**与 **scope 标签（in_scope/oos）**；先小批量试点给学长看，再全量造数；输出要能被后续 Label Studio 流程直接消费。**核心原则：数据不能太假，且每条合成数据都必须能追溯到来源。**

---

## 1. 先读这些（自导航，避免重复造轮子）

在动手前，按顺序读下面文件，理解项目语境和已有实现：

1. `docs/thesis_main/CONTEXT.md` —— 术语表（Manual/Semi/OOS/门洞/点对/环序/共享 x/融合/四象限等）。
2. `docs/thesis_main/研究数据说明_来源预处理与用途_20261006.md` —— 数据链与输入真源。
3. `analysis_results/simulated_annotators_local_20261014/STATUS.md` —— **本任务的核心状态文档**：已完成项 + 待办清单。
4. `docs/PROJECT_MAP_CLEAN_20260308.md` —— 目录地图与写入边界。
5. 工具本体（docstring 已说明各自用途）：
   - `tools/thesis_main/analysis/simulate_annotators.py`（v1 基线）
   - `tools/thesis_main/analysis/simulate_annotators_opt.py`（优化变体，含 count 模式）
   - `tools/thesis_main/analysis/simulate_annotators_pilot.py`（试点编排）
   - `tools/thesis_main/analysis/simulated_response_metadata.py`（时间/Semi/scope 元数据）
   - `tools/thesis_main/analysis/worker_archetype_quadrants.py`（人员四象限）
   - `tools/thesis_main/analysis/personalized_simulator_v2.py` / `_run.py` / `_temporal.py`（v2 个性化 + 时间溯源审计）
   - `tools/thesis_main/analysis/render_simulated_annotators.py`（review.html 渲染）

---

## 2. 背景与术语速查

这是一个**室内全景布局标注的不确定性研究**项目。人在 360° 全景图（ERP，1024×512）上标出房间「曼哈顿布局」的墙角上下点对。本项目要把「合成标注（synthetic annotators）」造得足够逼真，用于扩充人数面板做仿真。

| 术语 | 含义 |
|---|---|
| **点对 (point pair)** | 每个墙角 = 上端点(天花板侧) + 下端点(地面侧)，成对保存 |
| **环序 (ring order)** | 点对按墙面走向连成闭合环的顺序 |
| **共享 x** | 预处理：每对上下点 x 取周期最短弧中点（y 不变） |
| **Manual / Semi** | 无模型预标注（人从零标）/ 有模型初始化（人在模型结果上改） |
| **GT / 参考** | 参考真值布局；GT 不参与人员计票，只作外部评价 |
| **IoU / 3D IoU / BEV IoU** | 作答与参考的交并比（BEV=俯视面积 IoU，3D=体积 IoU） |
| **四象限 (archetype)** | 按「质量(IoU) × 速度(active_time)」把人分四类：`fast_good` / `fast_bad` / `slow_good` / `slow_bad` |
| **active_time_seconds / lead_time_seconds** | 标注耗时 / 前导时间 |
| **scope 标签** | `in_scope` / `oos`（out of scope，任务适用性）；本工具记为「采样的作答回应，不是几何裁决」 |
| **synthetic 标记** | 每条合成作答必须 `synthetic=True`，并带来源（模板 worker / donor / building / seed / 参数） |
| **模型三族 (FAMILIES)** | `HoHoNet` / `Bi-enclosed` / `Bi-extended`，来自冻结模型 bank |

---

## 3. 需求清单（学长原话逐条 → 验收口径）

学长（项目合作者）的完整要求，逐条对应一个可检验点。实现时确保每条都能被验证：

| # | 学长原话 | 落地为 |
|---|---|---|
| 1 | 把之前的工具翻出来，再测试一下 | 跑通现有测试 + v5 基线复现 |
| 2 | 先造一点看看，造完再微调 | 先小批量试点，参数可调（`cap`/`scale`/`count_mode`） |
| 3 | 照人模板造、造有特征的 | 四类模板（快好/快差/慢好/慢差）都能造 |
| 4 | 等质量分析后按「缺哪类人」定向补造 | 本次先临时标准，模板来源可一键重配 |
| 5 | 好标准等我分析；你先自己判断谁标得好 | 用现有 IoU 四象限做临时标准，先跑起来 |
| 6 | 试不同类型图片 | 覆盖 简单/中等/困难/门洞（必要时 OOS） |
| 7 | 半自动(Semi)能不能也搞 | Semi 臂：模型初始化 + 人的真实改动分布 |
| 8 | w001/w002/w017 应该都比较好 | ⚠️ 见第 10 节，与 IoU 数据有出入，需单列标注 |
| 9 | 标注时间怎么造 | 时间臂：按（模板×条件×点数）拟合/抽样，带来源 |
| 10 | in scope 标签也要造，争议图随机选 | scope 臂：争议范围图随机选，其余按图级真实分布 |
| 11 | 这周搞完 | 本周交付 |
| 12 | 数据不能太假 | 几何/时间/scope 都贴近真人，可人工核验 |
| 13 | 把脚本完善，接通整条线 | 输出 Label Studio 兼容格式，可被后续流程消费 |

---

## 4. 当前代码状态（done vs 待办）

对照 `STATUS.md`，已完成：

- ✅ 工具落地（v1 基线 + v2 个性化 + 测试 + 工作流）已合并。
- ✅ 环境：`.conda-envs/manha-sim`（Python 3.13.9 + numpy/pandas/scipy/shapely/Pillow/pytest）。
- ✅ v5 基线复现：覆盖 ~5.8°、合成多样性 ~2.1°、角点 TV ~0.5。
- ✅ 工人四象限 `worker_archetype_quadrants.py`：`fast_good` 4 / `fast_bad` 8 / `slow_good` 8 / `slow_bad` 3（锚点见下）。
- ✅ Semi 改动统计：574 份（25.4% 完全照抄、52% 点数不变、删除 -2/-4 对为主）。
- ✅ 优化实验 `scaled` 变体：合成多样性 2.1°→**5.2°**、覆盖误差 5.79°→**5.01°**、角点 TV 0.56→0.50、解析失败 0。
- ✅ 试点批次：7 图（简单×2/中等×1/困难×2/门洞未定×2）× 4 类 × 4 人，已渲染 `review.html`。

**待办（就是本次要做的）：**

- [ ] 复测修好的 **count 模式**（目标：角点 TV ≤ 0.3）。
- [ ] **时间臂**：按（原型×条件×点数）拟合 `active_time_seconds`，不是只抄单个 donor。
- [ ] **scope 臂**：24 张争议范围图按变体随机选（small/large R 例 + 3 张已确认 polygon），其余按图级真实 `scope_status` 分布。
- [ ] **Semi 臂**：模型初始化 + 按 `semi_initial_final_changes.csv` 的模板改动分布（复制率/RMSE/删点）。
- [ ] **合并级转换器**：输出 Label Studio 导出格式（annotations + completed_by 新工人号 + lead_time + worker_scope_response + keypointlabels 百分比坐标），字段与真实导出一致。
- [ ] **全量造数**：166 候选图 + 补 N<8 已标图 → 并入人数面板验证覆盖提升。
- [ ] **私有台账**：合成 worker/图 ↔ 模板来源（本地专用，可随时删）。
- [ ] 学长质量分析出来后按新好坏标准重配模板（本次不阻塞）。

---

## 5. 分阶段执行清单

### Phase 0 — 基线复验（先确认工具能用）

```bash
cd /Users/ethan/Documents/ChatGPT/manha/3D_Manhattan_label
/Users/ethan/Documents/ChatGPT/manha/.conda-envs/manha-sim/bin/python -m pytest \
  tests/test_simulate_annotators.py \
  tests/test_simulate_annotators_opt.py \
  tests/test_simulated_response_metadata.py -q
```

再复跑 v5 基线，核对指标与 `STATUS.md` 一致：

```bash
/Users/ethan/Documents/ChatGPT/manha/.conda-envs/manha-sim/bin/python -m tools.thesis_main.analysis.simulate_annotators \
  --output /tmp/sim_repro_check --seed 20260915 --conservative --synthetic-workers 50
```

### Phase 1 — count 模式复测/修复

- 位置：`tools/thesis_main/analysis/simulate_annotators_opt.py` 的 `count_mode` 分支（`simulate_v2`、`worker_counts_bankless`、`trim_pairs`）。
- 历史 bug：首版「点数/对数」混淆（`len(points)` 与 `len(points)//2` 混用），STATUS 称已修、**待复测**。当前代码已统一用 `//2` 取对数，请复核确认无遗漏。
- 复测目标：count 模式角点 TV ≤ 0.3、解析失败 0。用 `--variant count` 与 `--variant count_paired` 对比。

### Phase 2 — 三条元数据臂

**时间臂**（`simulated_response_metadata.py` 的 `augment` 内 time 部分）：
- 现状：从 `record_evidence.csv` 抽一个 donor 直接抄 `active_time_seconds`。
- 目标：按 `(archetype × condition × point_count)` 拟合/分层抽样生成时间，保留 `timing_status`、`time_pool`、donor 溯源；不能只是单个 donor 复制。

**scope 臂**（`augment` 的 scope 部分）：
- 现状：按 `worker × condition` 抽真实 scope 回应（`scope_responses.csv`）。
- 目标：实现学长要求——在**有范围争议的图**上按变体随机选 small/large；其余图按图级真实 `scope_status` 分布。争议图清单可在 `analysis_results/quality_scope_human_review_20261010/candidate_reconciliation_24.csv`、`analysis_results/difficulty_scope_preferred_20261011/`、`analysis_results/worker_four_block_exploration_20260910_v1/scope_responses.csv` 中定位（STATUS 提到「24 张争议范围图 + 3 张已确认 polygon」）。

**Semi 臂**（`transfer_semi` 与 `augment` 的 semi 部分）：
- 现状：已有 `transfer_semi`（复制/位移/删点）+ 574 份 `semi_initial_final_changes.csv`。
- 目标：核验改动分布（复制率/RMSE/删点）是否合理，必要时按模板调；Semi 作答的 `semi_status`、`initialization_trace` 来源必须可追溯。

### Phase 3 — 临时「好」标准与模板标注

- 保留 `worker_archetype_quadrants.py` 四象限作为模板来源。
- 但把学长点名的锚点结果**单列标注**（见第 10 节）：`W002`/`W027` 数据为好、`W001`/`W017` 数据偏快差、待学长质量分析重定。
- 每条合成作答写清：`source_worker_profile_id`（模板人）、`archetype`、`residual_donor_*`（donor 溯源）、`model_family`、`seed`、`cap/scale/count_mode`。这样等学长最终标准出来后，可一键重配模板而不重写生成逻辑。

### Phase 4 — 多类型图片试点

- 扩展 `simulate_annotators_pilot.py` 的 `PILOT_IMAGES`（当前只有 7 张），确保 简单/中等/困难/门洞（必要时 OOS）都有覆盖。
- 运行：
  ```bash
  /Users/ethan/Documents/ChatGPT/manha/.conda-envs/manha-sim/bin/python -m tools.thesis_main.analysis.simulate_annotators_pilot \
    --output analysis_results/simulated_annotators_local_20261014/pilot_expanded \
    --per-archetype 4 --quadrants analysis_results/simulated_annotators_local_20261014/worker_archetypes/worker_quadrants.csv
  ```
- 检查生成的 `review.html` + `contact_sheet.png` 可人工核验。

### Phase 5 — Label Studio 导出转换器

- 实现合并级转换器：合成作答 → Label Studio 导出格式。
- 字段与真实导出一致：`annotations` + `completed_by`（**新合成工人号，命名空间与真人隔离，建议 `S*` 前缀**）+ `lead_time` + `worker_scope_response` + `keypointlabels`（百分比坐标）。
- 参考真实导出结构：`export_label/` 下的运行时导出文件（只读，不要改）。

### Phase 6 — 全量造数 + 私有台账

- 试点确认后，对 **166 候选图 + 补 N<8 已标图** 全量造数。
- 私有台账：合成 worker/图 ↔ 模板来源（本地专用、可随时删）。
- 记录每张合成标注的生成参数（seed/cap/scale/count_mode/condition）与来源哈希，保证可复现、可追溯。

### Phase 7 — 测试 + 人工核验 + 更新状态

- 为时间臂/scope 臂/转换器补对应 pytest（参考 `test_simulated_response_metadata.py`、`test_simulate_annotators_opt.py` 的写法）。
- 人工核验一个试点批次：打开 `review.html`，确认合成标注在几何、时间、scope 上与真人不可明显区分（「不能太假」）。
- 更新 `analysis_results/simulated_annotators_local_20261014/STATUS.md` 的待办勾选状态；**不写公开文档、不推送**。

---

## 6. 环境与运行

- **Python**：`/Users/ethan/Documents/ChatGPT/manha/.conda-envs/manha-sim/bin/python`（3.13.9）。不要用系统 python。
- **运行方式**：在仓库根 `python -m tools.thesis_main.analysis.<模块>`。
- **分支**：`research/simulated-annotators-local-20261014`，**本地私有、永不推送**。
- **三条 CLI 入口**（详见 STATUS.md 与各文件 `main()`）：
  - 基线：`python -m tools.thesis_main.analysis.simulate_annotators --output <dir> --seed 20260915 --conservative --synthetic-workers 50`
  - 优化：`python -m tools.thesis_main.analysis.simulate_annotators_opt --output <dir> --variant all --cap 24 --scale 1.5`
  - 试点：`python -m tools.thesis_main.analysis.simulate_annotators_pilot --output <dir> --per-archetype 4 --quadrants <path>`
- **⚠️ 工作区已有未提交改动**，不要动无关文件：
  - 已修改：`simulate_annotators_opt.py`、`simulate_annotators_pilot.py`、`worker_archetype_quadrants.py`、`render_simulated_annotators.py`、以及若干 `tools/label_studio/` 与 `tests/` 文件。
  - 大量未跟踪的 `* 2.md`（`README 2.md`、`summary 2.json` 等）是同步冲突产生的重复文件，**不要清理、不要误删**。

---

## 7. 关键文件地图（输入真源与证据，别自己找）

| 用途 | 路径 |
|---|---|
| 冻结模型 bank（三族） | `analysis_results/uncertainty_cloud_inputs_20260906_v1/models/layouts.jsonl` |
| 图片清单 | `analysis_results/uncertainty_cloud_inputs_20260906_v1/images.csv` |
| 真人记录（训练/评价） | `analysis_results/confirmed_point_calculation_view_20260909_v1/reviewed/calculation_view.jsonl.gz` |
| 时间证据 | `analysis_results/annotation_research_prework_20260905_v2/evidence/record_evidence.csv` |
| Semi 改动证据 | `analysis_results/annotation_research_prework_20260905_v2/evidence/semi_initial_final_changes.csv` |
| scope 证据 | `analysis_results/worker_four_block_exploration_20260910_v1/scope_responses.csv` |
| 质量/画像 | `analysis_results/worker_profiles_20261003/{answer_metrics.csv,worker_profiles.csv,rosters.json}` |
| 对象映射（P↔W） | `analysis_results/research_input_20260929/preprocessed_source.json` |
| 四象限表 | `analysis_results/simulated_annotators_local_20261014/worker_archetypes/{worker_quadrants.csv,summary.json}` |
| 争议范围图候选 | `analysis_results/quality_scope_human_review_20261010/candidate_reconciliation_24.csv`、`analysis_results/difficulty_scope_preferred_20261011/` |

---

## 8. 红线/约束（违反即返工）

1. **不推送、不写公开文档**；本分支本地私有。
2. **不改写真源**：`export_label/`、`import_json/`、`active_logs/`、`preprocessed_source.json`、`research_input_20260929/manifest.json`、模型 bank、真人记录一律只读。
3. 合成作答必须 `synthetic=True` 且带来源（模板 worker / donor / building / seed / 参数），否则视为「假数据」。
4. 合成工人号与真人命名空间隔离（如 `S*`），防止与真人混淆。
5. **不恢复被排除人员 W019/W026** 的资格；不把合成数据混入真实资格/GT/融合参数。
6. 不宣称「可算=已验证」「测试通过=结论成立」。
7. 不按「哪版分数更符合预期」来选参数或模板；参数选择要有记录。
8. 输出目录使用新目录（各 CLI 会拒绝已存在的 `--output`），不覆盖历史结果。
9. `synthetic` 数据的 scope 标签记为「采样的作答回应，不是几何裁决」。
10. 改动范围只限 `tools/thesis_main/analysis/` 下模拟标注器相关文件、`analysis_results/simulated_annotators_local_20261014/` 与对应 `tests/`；不要顺手改无关模块。

---

## 9. 验收标准

1. 现有测试（`test_simulate_annotators.py` / `test_simulate_annotators_opt.py` / `test_simulated_response_metadata.py`）+ 新增测试全过。
2. count 模式复测：角点 TV ≤ 0.3、解析失败 0。
3. 四类模板都能产出合成作答，且 `synthetic=True` + 来源齐全。
4. 时间臂/scope 臂/Semi 臂产出的字段齐全（`active_time_seconds`/`lead_time_seconds`、`worker_scope_response`、`semi_status` 等）且有 `*_status` 与 donor 溯源。
5. 试点 `review.html` + `contact_sheet.png` 可人工核验，合成数据「看不出假」。
6. Label Studio 导出格式字段与真实导出一致，能被后续流程直接消费。
7. 私有台账 + 每张合成的参数/来源哈希可复现。
8. `STATUS.md` 待办状态更新，未推送。

---

## 10. 遗留问题（需学长回音，不阻塞本次交付）

1. **W001/W017 好坏冲突**：学长说「w001/w002/w017 应该都比较好」，但现有 IoU 数据：
   - `W002` = fast_good（IoU 0.894，排名 2）✅ 与学长一致
   - `W027` = slow_good（IoU 0.978，排名 1）—— 真正「慢又好」
   - `W001` = fast_bad（IoU 0.802，排名 9）、`W017` = fast_bad（IoU 0.805，排名 12）—— 与学长记忆冲突
   - 另有编号陷阱：`P017` = `W027`（慢又好），**不是** `W017`。
   - **处理**：模板分组以 IoU 数据为准，但把 W001/W017 单列标注「学长记忆中偏好，数据偏快差，待质量分析重定」；等学长质量分析定稿后重配模板。
2. **最终「好」标准口径**：待学长质量分析。
3. **全量规模与范围**：待试点看效果后定。

---

## 附：当前四象限锚点（`summary.json` 摘录）

```
pool_median_iou: 0.8182
pool_median_active_s: 125.0
usable_workers: 23
counts: fast_good 4 / fast_bad 8 / slow_good 8 / slow_bad 3 / excluded_or_no_data 3
anchors: W001=fast_bad, W002=fast_good, W017=fast_bad, W027=slow_good
```
