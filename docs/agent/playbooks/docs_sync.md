# 文档同步

## 触发条件（Trigger）

- 新增、删除或移动文件
- 修改正式入口文档
- 修改 protocol、SOP、字段合同或上下文索引

## 必须检查（Required checks）

- 运行 `git status --short`。
- 检查 `docs/PROJECT_MAP_CLEAN_20260308.md`。
- 检查 `docs/README_INDEX.md`。
- 确认变更文件是正式入口、支撑文档，还是 legacy / 临时工件。
- 同步改动保持短小，采用索引式登记。

## 禁止事项（Forbidden actions）

- 不在缺少明确理由时把 legacy、临时或探索性文件升格为正式入口。
- 不在窄同步任务中重写项目地图。
- 不移动或删除历史文件，除非用户明确要求。

## 预期交付（Expected handoff）

- 项目地图同步决策。
- README 同步决策。
- 新增正式入口。
- 有意不登记的文件及原因。
