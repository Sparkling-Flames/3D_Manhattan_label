# Paper A vFinal 代码迁移审计 v1

## 迁移原则

本轮采用 additive sidecar migration。旧 artifact 的路径、字段和 legacy 语义保留；新计算通过独立模块和 frozen manifest 进入候选层。正式 C1 缺失时，链路只能完成 dry-run 结构检查，不得形成正式 closeout 或 C2 分发。

## 阶段与状态

| 阶段 | 代码范围 | 完成条件 |
|---|---|---|
| P0 | contracts / manifests / index | manifest 可读、gitignore 精确放行、地图同步 |
| P1 | canonical evidence | 旧 CSV 不变，新 meta/geometry/provenance 可追溯 |
| P2 | three-state / harmonization | 正向、显式负向、未断言和不可评估不混淆 |
| P3 | Geometry LOO / scene | strict geometry gate，LOO 自身排除，候选不升级 |
| P4 | routing / replay | evidence snapshot 可重放，候选 rule 不生成 C2 assignment |
| P5 | closeout | dry-run 标记贯穿，正式 gate 永远保持 blocked |

## 当前边界

本审计记录不声明已获得正式 C1 标注，不声明任何 dry-run 数值为正式效应、worker profile 或 routing threshold。未提供的模型 provenance 统一保持缺失，不补写哈希。

## 验证

代码迁移完成后运行定向 pytest、既有 C1 相关 pytest、`git diff --check` 和 forbidden semantic grep；未通过项必须在交付中列明。
