你是 Codex。任务：在现有「模拟标注器（造数据）」上新增一个**难度驱动的「每图补到 35 人」Manual 臂**，并全量造数。

## 一句话任务
按图片难度（简单/中等/困难，学长 v6 稳定交接）把每张研究图补到**总数 35 人**的合成人工标注（Manual），其中"离谱"（wild）人数由难度决定，其余为高质量；全量产出，守全部红线。

## 开工顺序（必须）
1. 先读交接文档（自包含，按顺序读即可）：
   `docs/agent/CODEX_HANDOFF_difficulty_wild_35_20261017.md`
2. 按它 Phase 0 先 `git fetch origin/main`（**用 HTTP/1.1**，见文档），拿到 v6 难度 + 数据 v1 冻结输入。
3. 按 Phase 1–5 实现、测试、全量造数、审计。

## 硬约束（违反即返工，细节在交接文档 §8）
- `synthetic=True` + `S*` 命名空间，与真人严格隔离；绝不把合成标注冒充真人、绝不混入真实资格/GT/评分。
- 不写 `export_label/`、`import_json/`、`active_logs/`、模型 bank、真人记录等真源。
- building-holdout：donor 不得来自目标建筑。
- 不推送；输出新目录，不覆盖历史；同 seed 逐字节可复现。
- 难度标签 = 学长 v6 稳定交接（已复核）；"离谱"是合成几何退化标记，诚实写入，不宣称等于真人质量。

## 验收清单（对应交接文档 §9）
1. 新模块 + 测试全绿，且现有 99 个测试不回归。
2. 259 张图补到总数 35 人（Manual）；每图"离谱"人数落在难度区间：简单 0–2 / 中等 5–7 / 困难 ≤20 / 特殊单列·待修正GT·待复核按"困难"。
3. 输出齐全：`simulations.jsonl` + `label_studio_synthetic.json` + `difficulty_wild_audit.csv` + `summary.json` + `VALIDATION.json`。
4. 几何问题率 ≈0、同 seed 复现一致、`source_integrity` 全 True。

先读完交接文档再动手；不清楚的字段/路径先读文档 §5 关键输入，不要自己猜。
