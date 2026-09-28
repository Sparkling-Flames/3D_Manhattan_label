# Paper A vFinal 代码迁移审计 v1

## 迁移原则

本轮采用 additive sidecar migration。旧 artifact 的路径、字段和 legacy 语义保留；新计算通过独立模块和 frozen manifest 进入候选层。正式 C1 缺失时，链路只能完成 dry-run 结构检查，不得形成正式 closeout 或 C2 分发。

## 阶段与状态

| 阶段 | 代码范围 | 完成条件 |
|---|---|---|
| P0 | contracts / manifests / index | manifest 可读、gitignore 精确放行、地图同步 |
| P1 | canonical evidence | 原始 response、registry SHA、annotation identity、合法性与 schema 绑定 |
| P2 | three-state / harmonization | concrete-tag `+/-/0/NA` 与 explicit/semi/provenance/order gate |
| P3 | Geometry LOO / scene | 双通道 LOO、base-task context、scene mapping fail-closed、候选不升级 |
| P4 | routing / replay | 静态 scaffold 降名；事件驱动 replay 强制到达时间与 base-task fold |
| P5 | closeout | input bundle/SHA stale 防护；无正式 C1 时 formal gate 保持 blocked |

## 当前边界

本审计记录不声明已获得正式 C1 标注，不声明任何 dry-run 数值为正式效应、worker profile 或 routing threshold。未提供的模型 provenance 统一保持缺失，不补写哈希。

## 验证

代码迁移完成后运行定向 pytest、既有 C1 相关 pytest、`git diff --check` 和 forbidden semantic grep；未通过项必须在交付中列明。
