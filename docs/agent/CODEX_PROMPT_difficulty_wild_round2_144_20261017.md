你是 Codex。任务：第二轮造数 —— 按 `label_studio_gallery.html`（project 98 画廊）补齐 **144 张**未覆盖图，让 project 98 每张图达到 35 人标注。

## 一句话任务
画廊有 378 张图（5496 份真人标注、48 个真人）；上一轮只做了其中 259 张。本轮**只补 gallery 独有的 144 张**（每张已有 15–16 份真人标注）：每张 `need = 35 − annCount`（≈2740 份合成 Manual），难度用**真人分歧经验值**（成对平均角点距离三分位 → 简单/中等/困难），基座用模型三族 + 真人标注模式校准；无 GT，不评 B8L2。

## 开工顺序
1. 先读交接文档（自包含）：`docs/agent/CODEX_HANDOFF_difficulty_wild_round2_144_20261017.md`
2. 按它 Phase 0–4 执行：解析画廊 → 144 目标清单 → 生成 → 审计 → 测试。
3. 复用上一轮实现（`tools/thesis_main/analysis/difficulty_wild_*.py`），**新增 `mode='fill-144-gallery'`，不改动 `fill-to-35-wild` 及其历史输出**。

## 硬约束（细节在交接文档 §红线）
- 画廊 html / 真人标注 / 模型 bank / 全景图全部只读；building-holdout（donor 不得来自目标建筑）；不推送；新输出目录不覆盖历史；同 seed 逐字节复现。

## 验收清单（对应交接文档 §验收）
1. 144 张全部 `真实 + 合成 = 35`；合成 ≈2740；wild 预算合规（简单 0–2 / 中等 5–7 / 困难 8–20）。
2. 几何问题 0、同图重复坐标 0、编号唯一、无 donor 泄漏。
3. 新增测试 + 既有测试全绿；同 seed 复现逐字节一致；源完整性 True。
4. 输出齐全：`simulations.jsonl` + `label_studio_synthetic.json` + `difficulty_audit.csv`（含 difficulty_basis + 分歧值）+ `summary.json` + `VALIDATION.json` + `REPRODUCIBILITY.json`。

先读交接文档再动手；画廊在 `/Users/ethan/Documents/ChatGPT/manha/label_studio_gallery.html`（workspace 根，不在仓库内）。
