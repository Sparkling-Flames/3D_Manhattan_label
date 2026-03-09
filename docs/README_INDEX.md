# HoHoNet 文档索引（当前版）

> 最后更新：2026-03-09

本索引仅保留“当前实验必须文档”；历史草稿与阶段性方案已归档到 `docs/legacy/`。

---

## 当前必读（按执行顺序）

1. [论文提纲*v2*初版风格.txt](论文提纲_v2_初版风格.txt)
   - 当前论文唯一主线（RQ、协议、样本口径、评测口径）。
2. [开发路线与三人分工\_20260213.md](开发路线与三人分工_20260213.md)
   - 与提纲对齐的项目执行路线与 A/B/C 分工。
3. [实验设置执行细则\_20260213.md](实验设置执行细则_20260213.md)
   - 3.1 抽离出的执行规则（抽样、隔离、补抽样、口径日志）。
4. [SOP_labelstudio_experiment.md](SOP_labelstudio_experiment.md)
   - 实验实操总流程（导入→标注→导出→分析）。
5. [README_ANNOTATOR.md](README_ANNOTATOR.md)
   - 标注员操作规范与字段填写规则。
6. [README_DEVELOPER.md](README_DEVELOPER.md)
   - 部署、日志、安全、运行维护。
7. [PROJECT_MAP_AND_HANDOVER_20260308.md](PROJECT_MAP_AND_HANDOVER_20260308.md)
   - 当前仓库地图、正式/历史入口、A 线真源层、对 B/C 的交接口径。
8. [PROJECT_MAP_CLEAN_20260308.md](PROJECT_MAP_CLEAN_20260308.md)
   - 纯净仓库地图，只保留当前服务器标注/分析主链相关目录与入口。

---

## 分析与质量控制文档

- [ANALYSIS_DATA_FLOW.md](ANALYSIS_DATA_FLOW.md)
  - 上游解析→门控→CSV 输出的字段与数据流。
- [PROJECT_MAP_CLEAN_20260308.md](PROJECT_MAP_CLEAN_20260308.md)
   - 当前主链的纯净入口地图。
- [GATING_LOGIC_FINAL_SOLUTION.md](GATING_LOGIC_FINAL_SOLUTION.md)
  - 门控逻辑与选择偏差修正依据。
- [TEST_PLAN_AND_REVIEW.md](TEST_PLAN_AND_REVIEW.md)
  - 测试边界、用例、回归与变更控制。
- [../tools/README.md](../tools/README.md)
  - 工具脚本入口与参数说明。

---

## 根目录参考文档

- [../README.md](../README.md)
- [../README_reproduction.md](../README_reproduction.md)
- [../QUICK_START.md](../QUICK_START.md)

---

## Legacy 归档说明

以下内容已迁移到 `docs/legacy/`，不再作为当前执行入口：

- `legacy/handover_2026Q1/`：历史交接文档与 AI 交接。
- `legacy/plans/`：阶段性执行计划与旧索引。
- `legacy/outline_drafts/`：旧提纲、草稿、暂存文本。
- `legacy/reviews/`：历史审稿反馈稿。

需要追溯历史决策时再查阅 legacy；当前执行以“当前必读”列表为准。
