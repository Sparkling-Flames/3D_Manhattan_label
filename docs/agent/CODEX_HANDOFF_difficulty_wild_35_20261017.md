# Codex 任务交接：难度驱动的「每图补到 35 人」模拟标注器（Manual 臂）

> **交付对象**：Codex（自主编码 Agent）。本文件自包含，按顺序读即可开工。
> **仓库根目录**：`/Users/ethan/Documents/ChatGPT/manha/3D_Manhattan_label`（下文相对路径都基于它）。
> **当前分支**：`research/simulated-annotators-local-20261014`（**本地私有分支，永不推送**）。
> **日期/版本**：2026-10-17。难度口径 = 学长「难度 v6 稳定交接」；数据口径 = 学长「数据 v1」；质量指标 = **B8L2（主）/ D10**。

---

## 0. TL;DR（一句话任务）

在现有「模拟标注器」上新增一个**难度驱动的 Manual 臂**：按学长 v6 难度标签，把每张研究图补到**总数 35 人**的合成人工标注；其中每图"离谱（wild）"人数由图片难度决定（简单 0–2 / 中等 5–7 / 困难 ≤20 / 特殊单列·待修正GT·待复核按"困难"），其余为高质量标注；全量造数 + 审计，守全部红线。

---

## 1. 先读这些（自导航）

1. `docs/thesis_main/CONTEXT.md` —— 术语（Manual/Semi/OOS/门洞/点对/环序/共享 x/融合等）。
2. 上一份交接（背景与既有实现）：`docs/agent/CODEX_HANDOFF_simulated_annotators_20261015.md`。
3. 工具本体（docstring 已说明用途）：
   - `tools/thesis_main/analysis/simulate_annotators.py`（v1 基线：`fit`/`geometry_status`/`rays`/`distance`/`seed_for`/`parsed`/`load_inputs`/`FAMILIES`/`comparison`）
   - `tools/thesis_main/analysis/simulate_annotators_opt.py`（`apply_residual` 抖动 / `trim_pairs` 删点 / count 模式）
   - `tools/thesis_main/analysis/simulator_personality_inputs.py`（当前输入适配器 `load_current`/`fit_profiles`，`QUALITY_VERSION`）
   - `tools/thesis_main/analysis/personality_annotator_sampler.py`（分层采样 `fit_personality`/`generate`/`transfer`/`choose_donor`/`sample_time`）
   - `tools/thesis_main/analysis/personality_response_channels.py`（Semi/scope/lead_time 通道）
   - `tools/thesis_main/analysis/semi_edit_distribution.py`（Semi 生成式改动）
   - `tools/thesis_main/analysis/personality_incremental_run.py`（全量编排 `target_panel`/`run_incremental`，当前 `fill-to-eight` 模式）
   - `tools/thesis_main/analysis/export_synthetic_label_studio.py`（`export_samples`/`synthetic_worker`）

---

## 2. 本轮需求 → 验收口径（用户/学长原话逐条）

| # | 需求 | 落地为（可检验） |
|---|---|---|
| 1 | 图分简单/中等/困难 | 用学长 v6 稳定交接 `difficulty_class`（见 §5.1），不含主观新分类 |
| 2 | 每张图补到 35 人 | 每图 `need = 35 − 真实Manual人数`（n≥35 跳过）；Manual 臂 |
| 3 | 简单图尽量高质量，最多 0–2 人离谱 | 简单图 wild 数 ∈ {0,1,2}（偏 0–1） |
| 4 | 中等图 5–7 人离谱 | 中等图 wild 数 ∈ {5,6,7} |
| 5 | 困难图最多 20 人离谱 | 困难图 wild 数 ∈ [8,20]（≤need） |
| 6 | 特殊单列/待修正GT/待复核 | **按「困难」**处理（≤20），并把 `gt_error_excluded`/`pending` 标记带进输出 |
| 7 | "离谱"= 角点能标到墙角但没完全标出 / 漏角点 / 只标一个空间范围 | 三类几何退化（§6.2），几何始终过 `geometry_status` |
| 8 | 有些图 GT 范围有问题，参考真人标注 + 学长范围修正 | 参照学长 `floor_scope_update`（§5.4），不直接信坏 GT；10 张待核范围图单独标记 |
| 9 | 只做 Manual | 本轮不做 Semi |
| 10 | 直接全量 | 全量 259 图（内部先 smoke 冒烟校验，见 §9） |
| 11 | 数据不能太假 | 抖动/删点/范围退化从真实低质量 worker 实测 delta 校准；可人工核验 |

---

## 3. 关键背景变化（相对上一份交接，务必注意）

1. **难度源升级**：从 `difficulty_coarse_closeout_20261014`（v2）→ **v6 稳定交接 `difficulty_b8l2_handoff_20261016`**（§5.1）。
2. **质量指标升级**：从 `WQ-LS08-20261014` → **B8L2（主）/ D10**（§5.3）。
3. **数据口径**：当前标注锁定为**数据 v1**（3222 份规范作答 / **261 张研究图** / 27 个源人员身份，含 Project 98 的 70 份），冻结入口 `research/data/releases/v1/RELEASE.json`（§5.2）。
4. **"范围判断"已被学长框定**：不是"每张图都判断"，而是 `PENDING_SCOPE_AUDIT.md` 里的 **29 张待核**（19 张仅数值误差可忽略 + 9 张"实际范围扩展" + 1 张证据不足）→ 真有问题的是 **9+1=10 张**（§5.4）。其余 41 张 43 个空间已确认，不要重画。
5. 现有模拟器读的是旧包 `research_input_20260929`；数据 v1 是新冻结。**需要核对真实人数/记录来源**（§7 Phase 0 的核对项）。

---

## 4. 当前代码状态（done vs 待办）

**已可复用（不要重写）：**
- 分层采样 `personality_annotator_sampler.py`（`transfer`=抖动+删点、`choose_donor`、`sample_time`）。
- 抖动算子 `simulate_annotators_opt.apply_residual`、删点 `trim_pairs`、`count_mode`。
- 全量编排骨架 `personality_incremental_run.run_incremental`（building-holdout 拟合 + 导出 + 覆盖审计 + 源完整性校验）。
- Label Studio 导出 `export_synthetic_label_studio.export_samples`。

**待办（本次要做）：**
- [x] 新模块 `difficulty_wild_sampler.py`：难度装载 + wild 数量抽样 + wild 几何退化（含**新增 scope_restricted 连续子集算子**）。
- [x] 编排新增 `mode='fill-to-35-wild'`（**不动既有 `fill-to-eight` 行为**，保历史可复现）。
- [x] 输入源对齐到 v6 难度 + 数据 v1（§5、§7 Phase 0）。
- [x] 输出字段 + 审计 + 测试（§6.3、§9）。

---

## 5. 关键输入真源（都来自学长最新代码，先用 §7 Phase 0 的命令拿到）

> 这些文件在 `origin/main`（最新 commit `1bbcf8ad`），**不在本地工作树**。用 §7 的 `git fetch` + `git show origin/main:<path>` 读取；运行时要加载的文件复制到工作树内只读参考位置。

### 5.1 难度 v6 稳定交接（本任务的核心输入）
`research/difficulty/difficulty_b8l2_handoff_20261016/`
- `image_inventory.csv`：259 图逐图。关键列：`image`(短码)/`image_id`(hash)/`difficulty_class`(简单/中等/困难/单列/待修正GT/待复核)/`difficulty_analysis_eligible`/`difficulty_analysis_exclusion`/`gt_error_excluded`/`original_candidate_vertex_count`/`selected_vertex_count`/`effective_turn_count`/`H`/`reference_full_available`/`answer_exposure_status`/`label_basis`。
- `difficulty_snapshot.json`：259 图 v6 完整记录（含 `doorway_status`/`oos_subtype` 等，供需要场景字段时用）。
- `version_changes.csv`、`CHECKS.json`、`INPUT_MANIFEST.json`、`CONFIRMATION_AND_GATE.md`。
- **口径**：205 普通候选 = 简单133 / 中等35 / 困难37；但本任务范围是「全部 259 张」（§6.1）。

### 5.2 数据 v1 冻结（真实作答 / 真实人数来源）
`research/data/releases/v1/`
- `RELEASE.json`（冻结入口：原始导出坐标、环序、评论、当前参考目录与绑定、难度、同房、时间口径、共同评分、六线输出）、`FIELD_CONTRACT.json`、`README.md`、`VERSION_POLICY.md`。
- 口径：3222 份规范作答、261 张研究图、27 个源人员身份（含排除/缺失/OOS，≠ 1911 可用质量或 1048 人员训练）。
- 另有新输入包 `analysis_results/research_input_20261017/`（`manifest.json`/`data.json`/`batch_admission.json`/`field_contract.json`…），可能与数据 v1 对应，核对时二选一并用同一套。

### 5.3 人员画像与质量分（B8L2/D10）
- `research/workers/worker_b8l2_d10_20261017/profiles.csv`：逐人 Q（相对较高/较低）× T（较快/较慢）名单（B8L2 10/14、D10 12/12 等）。
- `research/workers/worker_b8l2_d10_20261017/README.md`、`research/workers/worker_quality_profile_pro_handoff_20261017/`。
- 共同评分包：`quality_b8l2_d10_20261017_v2`（在数据 v1 的 metric_version 里登记）。**本任务质量校准用 B8L2/D10，不用旧的 WQ-LS08。**

### 5.4 范围修正（"GT 范围有问题"的参照）
- `analysis_results/research_input_20260929/floor_scope_update_20261015.json`：41 图底面范围修正（`floor_xz_h` 多边形、`floor_region_confirmed`、`scope_semantics`）。
- `research/difficulty/difficulty_b8l2_handoff_20261016/PENDING_SCOPE_AUDIT.md` + `pending_scope_audit.json`：29 张待核；**9 张"实际范围扩展"**（e9z-09、uNb-18、uNb-26、uNb-41、uNb-54、uNb-59、uNb-66、uNb-67、uNb-88）+ **1 张证据不足**（wc2-22）= 10 张真有问题。
- 待修正 GT 4 张（`gt_error_excluded=True`）继续排除 GT 参照；uNb-36 待定。

### 5.5 模型 bank（不变）
`analysis_results/uncertainty_cloud_inputs_20260906_v1/models/layouts.jsonl`（三族 `HoHoNet`/`Bi-enclosed`/`Bi-extended`）+ `images.csv`。

---

## 6. 技术规格

### 6.1 范围与难度 → 离谱预算（可调常量，默认如下）
```
WILD_BUDGET = {
    '简单': (0, 2),      # 偏 0–1 抽样：P(0)=0.5, P(1)=0.35, P(2)=0.15
    '中等': (5, 7),      # 区间均匀
    '困难': (8, 20),     # 区间均匀，≤need
    '单列': (8, 20),     # 特殊单列按困难
    '待修正GT': (8, 20), # 按困难，且输出带 gt_error_excluded 标记
    '待复核': (8, 20),   # 按困难，且输出带 pending 标记
}
```
- 每图先算 `need = 35 − 真实Manual人数`（来自数据 v1 真实记录，§5.2）；`k = min(wild_count(难度), need)`；其余 `need − k` 份为"正常"高质量。
- 范围 = 全部 259 张（`image_inventory.csv`）；**核对数据 v1 的 261 图与 259 图的 2 张差**（§7 Phase 0），差出的 2 张若没有难度标签则本轮单独列 `difficulty_unassigned`，不硬编难度。

### 6.2 "离谱"（wild）错误模型 —— 三类几何退化，随机组合，仍保几何合法
1. **没完全标出（partial_corner）**：对部分点对施加**较大**残余抖动（复用 `apply_residual`/`transfer`，cap/scale 取低质量（`lower`）worker 实测 delta 的较大分位）。
2. **漏角点（missing_corner）**：删 1–2 对（复用 `trim_pairs` / `transfer` 的 `kept_pairs` 子集，即 `count_offset<0` donor）。
3. **只标一个空间范围（scope_restricted）**：只保留**连续角度区段**内的点对（一个空间），删掉其余 —— **新增算子**：在环序上取一段连续子集（区别于随机 `trim_pairs`）。
- 单个 wild worker 随机施加 1–3 项组合；生成后必须过 `geometry_status`；失败则退化为更轻退化（**不回退成模型复制**，沿用现有"不 inflate validity"约定）。
- 抖动幅度/删点频率从真实低质量 worker 的实测 delta 校准（"数据不能太假"）。

### 6.3 输出字段（在现有 `personality_annotator_sampler.generate` 的 row 基础上加）
```
difficulty, difficulty_version(v6), difficulty_source(文件路径),
wild(bool), wild_error_types(list), wild_budget_k, need, real_manual_n,
gt_error_excluded, pending_review, scope_reference_status
```
- 保留既有 `synthetic=True` / `S*` 命名空间 / `source_worker_profile_id` / `model_family` / donor 溯源 / `seed`。
- 新增 `difficulty_wild_audit.csv`：每图 `difficulty_class / need / real_manual_n / synthetic_n / wild_n / wild_error_types 计数`。
- 导出：`simulations.jsonl` + `label_studio_synthetic.json`（`export_samples` 不变）+ `summary.json` + `VALIDATION.json` + `source_integrity.json`。

---

## 7. 分阶段执行

### Phase 0 — 拿新输入 + 基线复验
```bash
cd /Users/ethan/Documents/ChatGPT/manha/3D_Manhattan_label
# 网络走 HTTP/1.1（HTTP/2 会报 framing 错误）
git -c http.version=HTTP/1.1 fetch --no-tags --filter=blob:none origin main
# 读新输入（示例；按需 git show origin/main:<path>）
git -c http.version=HTTP/1.1 show origin/main:research/difficulty/difficulty_b8l2_handoff_20261016/image_inventory.csv
```
- 复跑现有测试确认不回归：
```bash
/Users/ethan/Documents/ChatGPT/manha/.conda-envs/manha-sim/bin/python -m pytest \
  tests/test_personality_simulation.py tests/test_semi_edit_distribution.py \
  tests/test_worker_archetype_quadrants.py tests/test_simulated_review_3d.py -q
```
- **核对项（必须先做，写在审计里）**：
  1. 259（难度分类）vs 261（数据 v1）差在哪 2 张。
  2. 真实 Manual 人数来源：用数据 v1 `RELEASE.json`（或 `research_input_20261017`）还是现有 `load_current()`（旧包）；二者真实人数是否一致；不一致则按数据 v1 为准并记录差异。
  3. `reference_full_available=False` 的图（29 张待核）在模拟时的参照策略（§6.2 用学长范围修正，不硬造顶界）。

### Phase 1 — 难度装载 + wild 数量抽样
- 新模块 `tools/thesis_main/analysis/difficulty_wild_sampler.py`：
  - `load_difficulty(path)`：读 `image_inventory.csv`（`utf-8-sig`），返回 `image_id → {difficulty_class, gt_error_excluded, ...}`。
  - `wild_count(difficulty, seed)`：按 §6.1 抽样。
  - 单测：各难度区间内、`k ≤ need`、`need = 35 − n`。

### Phase 2 — wild 几何退化
- `wild_edit(points, model, rng, severity)`：实现 partial_corner / missing_corner / **scope_restricted（新增连续子集）**；复用 `apply_residual`/`trim_pairs`。
- 单测：三类退化几何合法（`geometry_status`）、不返回模型复制、scope_restricted 产出连续子集。

### Phase 3 — 编排 `mode='fill-to-35-wild'`
- 在 `personality_incremental_run.py` 新增模式（不动 `fill-to-eight`）：
  - target panel = 259 张难度图，`need = 35 − n`。
  - 每图按 `k = wild_count(难度)` 分配 wild/normal；wild 身份偏向低质量模板、normal 偏向高质量模板（可调）。
  - building-holdout 不变（donor 不泄漏目标建筑）。
  - 输出字段见 §6.3。
- 内部 smoke：每难度 1–2 张先跑，验证 wild 预算与几何，再全量。

### Phase 4 — 审计 + 导出
- `difficulty_wild_audit.csv`（每图难度/wild 数）、`summary.json`、`VALIDATION.json`、`source_integrity.json`。
- 质量参照（非验收）：对比合成 wild 标注的 B8L2 分布 vs 真实低质量 worker 的 B8L2 分布，验证"离谱"尺度贴近真人。

### Phase 5 — 测试 + 人工核验
- 新增 pytest（参考 `tests/test_personality_simulation.py` 写法）：wild 预算、wild_edit 几何、scope_restricted、命名空间隔离、同 seed 复现。
- 现有测试全绿。

---

## 8. 红线/约束（违反即返工）

1. **不推送**；本分支本地私有。
2. **不改写真源**：`export_label/`、`import_json/`、`active_logs/`、模型 bank、真人记录、数据 v1 `RELEASE.json`、难度交接包一律只读。

---

## 9. 验收标准

1. 现有测试 + 新增测试全绿；现有 99 测试不回归。
2. 259 张图补到总数 35 人（Manual）；每图 wild 数落在 §6.1 区间内。
3. `difficulty_wild_audit.csv` 中每难度 wild 数均值/范围符合预算；几何问题率 ≈0。
4. 输出字段齐全（§6.3），`synthetic=True` + `S*` + 来源完整，可复现（同 seed 逐字节一致）。
5. `source_integrity.json` 全 True；`VALIDATION.json` 记录质量参照结果（B8L2 wild 分布 vs 真人）。
6. 不推送；`STATUS.md`/交接文档待办状态更新（本地）。

---

## 10. 遗留问题（需用户/学长回音，不阻塞本次交付）

1. **259 vs 261**：数据 v1 说 261 张研究图，难度 v6 是 259 张；差 2 张待核对（Phase 0）。
2. **待修正GT 4 张 + 待复核 1 张**：本轮按"困难"造并带标记；若学长后续改判，重跑难度源即可。
3. **10 张待核范围图**（9 扩展 + 1 证据不足）：本轮用学长范围修正 + 标记 `scope_reference_status`，不硬造顶界；若学长/用户要逐图复核，再单独接。
4. **Semi 臂** 的 35 人填法：本轮不做。
5. 最终"好/坏"标准：学长质量分析仍在进行（B8L2/D10 为当前主指标）；wild 预算/模板待其定稿后重校。


## 2026-10-17 本地执行回执

Phase 0 至 5 的本地实现、冒烟、全量、独立复现及核验资料已完成。详见 [交付说明](DIFFICULTY_WILD_35_DELIVERY_20261017.md)，其中列明实际120项测试（原有91项、新增29项）、原99项清单差异、经用户授权的模型补充索引及质量分布边界。未推送，真源哈希保持一致。
