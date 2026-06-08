# Label Studio CE 护栏

## 触发条件（Trigger）

- 修改 Label Studio 导入、项目切分、worker 可见性、任务分发、权限、GT 隔离或 LS 运营文档

## 必须检查（Required checks）

- 阅读 `docs/label_studio/LS_CE_ONLY_OPERATION_SOP_v1.md`。
- 阅读 `docs/label_studio/label studio注意事项.md`。
- 阅读 `docs/thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.md`。
- 涉及分发时检查当前正式 `import_json/` 文件和 assignment manifest。
- 确认外部 manifest / import JSON 仍是分发真源。

## 禁止事项（Forbidden actions）

- 不依赖 Label Studio CE 角色、项目成员权限或单任务分配作为正式分发机制。
- 不把 LS 项目可见性当作安全隔离。
- 不把 GT 维护路径与 worker-facing active project 路径混用。
- 不用 CE 不支持的权限假设替代项目/批次切分。

## 预期交付（Expected handoff）

- CE-only guard 结果。
- 已检查文件。
- 分发真源说明。
- 运营风险或需要人工审计的事项。
