# Codex 任务交接：第二轮造数 —— 按 label_studio_gallery.html 补齐 144 张（project 98 到 35 人/图）

> **交付对象**：Codex（自主编码 Agent）。本文件自包含，按顺序读即可开工。
> **仓库根目录**：`/Users/ethan/Documents/ChatGPT/manha/3D_Manhattan_label`（相对路径基于它）。
> **workspace 根**：`/Users/ethan/Documents/ChatGPT/manha`（画廊 html 与 `output/` 在这里）。
> **当前分支**：`research/simulated-annotators-local-20261014`（本地私有，永不推送）。
> **日期**：2026-10-17。这是**第二轮**；第一轮交接见 `docs/agent/CODEX_HANDOFF_difficulty_wild_35_20261017.md`（其红线全部沿用）。

---

## 0. TL;DR

`label_studio_gallery.html`（project 98 画廊）有 **378 张图**、5496 份真人标注、48 个真人。第一轮只做了其中 259 张（v6 难度表）。本轮**只补 gallery 独有的 144 张**（全部未分类、每张已有 15–16 份真人标注）：每张 `need = 35 − annCount` ≈ 合计 **2740 份**合成 Manual；难度 = **真人分歧经验值**（成对平均角点距离三分位 → 简单/中等/困难，`difficulty_basis='real_annotator_disagreement_empirical'`）；基座 = 模型三族 + 真人标注模式校准；**无 GT → 不评 B8L2**。

---

## 1. 关键输入（全部只读）

| 数据 | 路径 | 说明 |
|---|---|---|
| 画廊 html | `/Users/ethan/Documents/ChatGPT/manha/label_studio_gallery.html` | 内嵌 `const DATA = {...}`；见 §2 结构 |
| 第一轮输入冻结包 | `/Users/ethan/Documents/ChatGPT/manha/output/difficulty_wild_35_20261017/inputs/` | v6 难度 259 张 `image_inventory.csv`（用于求差） |
| 第一轮全量输出 | `/Users/ethan/Documents/ChatGPT/manha/output/difficulty_wild_35_20261017/full/` | 只读；`simulations.jsonl` 有 6678 个 `S_MANUAL` 编号（撞号断言用） |
| 模型 bank | `analysis_results/uncertainty_cloud_inputs_20260906_v1/models/layouts.jsonl` | 三族 `HoHoNet`/`Bi-enclosed`/`Bi-extended`；144/144 已核实 |
| 全景图 | `data/mp3d_layout/{valid,test}/img/<image_id>.png` | 144/144 已核实 |
| 上一轮实现 | `tools/thesis_main/analysis/difficulty_wild_{inputs,run,sampler,quality,review}.py` | 复用，不改其行为 |

## 2. 画廊 DATA 结构（解析要点）

```js
const DATA = {
  tasks: [{
    title: "<image_id>.jpg",        // hash 即 image_id
    code: "<building>-NN",          // building = code.split('-')[0]
    image: "<cos 图片 url>",         // 仅作展示；本地用 data/mp3d_layout 全景
    condition: "mixed",             // 本轮只做 Manual
    corners, annCount, scopeVotes: {in_scope, out_of_scope},
    workers: [{w: "114", kps: [[x%, y%], ...], scope: "in_scope"|"out_of_scope", gt: false, t, lt}],
    diff, diffClass                  // 144 张都是 None/未分类
  }],
  stats, workerColor, workerList, difficultyCounts, palette
}
```
- **kps 是百分比坐标对** `[[x%,y%],...]` → 像素 `[x*1024/100, y*512/100]`；每份作答 = 一个真人的完整点对集（相邻上下成对，保留顺序）。
- 目标清单 = `tasks` 的 hash **不在** v6 `image_inventory.csv` 的 259 个 `image_id` 中 → **必须恰好 144 张**（断言，否则报错排查）。
- 真人人数 `annCount` ∈ {16,15}：need = 19 或 20；总合成 = 140×19 + 4×20 = **2740**（断言）。

## 3. 难度派生（真人分歧经验值，本轮核心新逻辑）

- 每图取 15–16 份真人点对集，算**成对平均角点距离**（x 周期性 1024，y 直接差；对角点逐对配对后取均值，含点数不同的作答按可配对部分）。
- 144 张的三分位切分 → **简单 / 中等 / 困难**（参考值：t1≈188.3px、t2≈225.0px，实测分布 94.9–270.7px；**阈值必须从数据重算并写入审计**，不得硬编码）。
- 逐图记录：`difficulty`（简单/中等/困难）、`difficulty_basis='real_annotator_disagreement_empirical'`、`disagreement_px`（原始值）、`difficulty_thresholds`。**不得声称学长裁定**；tier 名称就是简单/中等/困难，不带"代理"字样（来源在字段里）。

## 4. 生成规格（沿用第一轮 wild 模型，校准源换成该图真人）

- wild 预算：简单 (0,2) 偏 0–1 抽样（P=.5/.35/.15）；中等 (5,7)；困难 (8,20)；`k = min(k, need)`。
- **正常组**：模型提议（该图三族选一，沿用既有族选择逻辑）+ 残差抖动，幅度取**该图真人相对模型 delta 的中低分位**。
- **wild 三类退化**（几何始终过 `geometry_status`；失败减档重试，**不回退模型复制**）：
  1. `partial_corner`（没完全标出）：较大抖动，取真人分歧高分位幅度；
  2. `missing_corner`（漏角点）：删 1–2 对，频率按真人中"点数较少"作答的占比校准；
  3. `scope_restricted`（只标一个空间范围）：环序连续子集；"正确范围"参照该图**真人多数派范围**（`scopeVotes` in_scope/oos 记入审计；oos 投票多的图单独标记，不伪造范围）。
- 时间/范围作答：沿用既有通道；scope 回应可从该图真人 scope 投票分布采样，`scope_status='sampled_response'`。
- building-holdout：donor（真人标注）**不得来自目标建筑**（24 个建筑中取其他建筑；同图真人只能用于该图分歧/范围统计，不能作为自身 donor 泄漏——用同图真人做"校准幅度"属图内统计，允许并记录，但**抖动残差样本不得整份复制同图真人作答**）。
- 合成编号：**`S_MANUAL_200000` 起新号段**；与第一轮 6678 个 `export_worker_id`（最大 109062）做集合不相交断言。

## 5. 输出与审计

新输出目录（已存在则报错）：
`/Users/ethan/Documents/ChatGPT/manha/output/difficulty_wild_35_20261017/round2_gallery_144_20261017/`

| 文件 | 要求 |
|---|---|
| `simulations.jsonl` | 每行：`synthetic=True`、`condition=manual`、`S_MANUAL_2xxxxx`、`image_id`、`difficulty`、`difficulty_basis`、`disagreement_px`、`wild`、`wild_error_types`、`points`、`model_family`、`need`、`real_manual_n`、时间/范围/溯源字段；**evaluation 字段 = null + 原因 `no_gt_reference`**（不评 B8L2） |
| `label_studio_synthetic.json` | 沿用 `export_samples`，2740 份全部可导出、0 拒绝 |
| `difficulty_audit.csv` | 逐图：`difficulty_basis`、`disagreement_px`、`real_n`、`need`、`wild_n`、三类错误计数、`scope_votes`、`gt_none=true` |
| `summary.json` / `VALIDATION.json` | VALIDATION：几何 0 / 同图重复 0 / 编号唯一 / 预算合规 / donor 无泄漏 / **分歧一致性**（合成成对分歧 vs 真人成对分歧同量级，比值记录，不宣称通过或匹配）/ 同 seed 复现 / 源完整性 |
| `REPRODUCIBILITY.json` / `source_integrity.json` | 同第一轮做法；画廊 html、bank、全景图纳入哈希 |

## 6. 分阶段执行

- **Phase 0**：解析画廊 → 断言 144 目标、2740 总量；重算三分位阈值并冻结；核对模型/全景 144/144。
- **Phase 1**：新 `mode='fill-144-gallery'`（复用 `difficulty_wild_run.py` 骨架，不改 `fill-to-35-wild`）；实现 §3 分歧难度 + §4 生成。
- **Phase 2**：内部 smoke（简单/中等/困难各 2 张，核对预算与几何）→ 全量 144。
- **Phase 3**：审计文件 + 测试（`tests/test_difficulty_wild_round2.py`：目标 144、预算、几何、编号不相交、三分位单调、同 seed 复现、源完整性）；既有测试全绿。
- **Phase 4**：更新交接文档待办；不推送。

## 7. 红线（第一轮全部沿用 + 新增）

1. 不推送；本地私有分支。
2. 不改写真源（画廊 html、真人标注、模型 bank、全景图、v6 难度表、第一轮 `full/` 全部只读）。


## 8. 验收标准

1. 144 张全部 `真实(15/16) + 合成(19/20) = 35`；合成总量 = 2740；wild 预算合规。
2. 几何问题 0、同图重复 0、编号与第一轮不相交、donor 无建筑泄漏。
3. 新增 + 既有测试全绿；同 seed 36 类文件逐字节一致；源完整性 True。
4. `difficulty_basis`/`disagreement_px` 逐图齐全；分歧一致性审计输出；无任何 B8L2 分数冒充。

## 9. 遗留问题（不阻塞）

1. 25 张"第一轮有、gallery 无"的图：本轮不动，待定。
2. 234 张重叠图：保持第一轮结果。
3. 若学长后续给出 144 张正式难度标签：换源重跑（难度源做成可替换输入）。
4. 合并后看板可扩展到 378 张（可选，另行安排）。


## 2026-10-17 本地交付回执

Phase 0 至 4 已完成。144图补入2740份，其中正常组1791份、wild949份；每图35人，预算合规。工程几何问题0、重复坐标0、导出拒绝0、donor建筑泄漏0。149项相关测试通过，44个文件独立进程逐字节复现一致，215个受保护输入与预检哈希相同。全部evaluation为空，原因no_gt_reference。

详见[第二轮交付说明](DIFFICULTY_WILD_ROUND2_DELIVERY_20261017.md)。第一轮full、画廊与模型/全景真源保持只读；未推送。画廊整体看板扩展仍保留为后续独立事项。
