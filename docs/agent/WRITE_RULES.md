# tools/docs 写入规则


## tools 写入规则

- `tools/` 根目录只放 `README.md`、包初始化文件和稳定目录；不要新增根目录脚本 wrapper。
- 论文主线工具写入：
  - `tools/thesis_main/analysis/`
  - `tools/thesis_main/registry/`
  - `tools/thesis_main/data_prep/`
  - `tools/thesis_main/foreign_recruitment/`
- 论文 B 线 B0/B1/B2、训练、cue、bilayout 和模型审计工具写入 `tools/paper_b/`。
- Label Studio XML、3D viewer、active-time server、CORS server、COS/upload、official userscripts 和 import/build helper 写入 `tools/label_studio/`。
- `tools/legacy/`、`tools/legacy_server/`、`tools/backups/` 默认不迁移、不修订。

## docs 写入规则

- `docs/` 根目录只保留 `README_INDEX.md` 和 `PROJECT_MAP_CLEAN_20260308.md`。
- 论文主线协议、SOP、统计计划、字段合同、PreScreen/Calibration/Main 文档写入 `docs/thesis_main/`。
- Paper B 模型、ZInD mapping、B-line freeze/audit 和训练计划写入 `docs/paper_b/`。
- Label Studio CE-only、active-time、云端部署、COS、标注员/开发者说明写入 `docs/label_studio/`。
- Agent 上下文、playbook、写入规则和给 Codex 的补充说明写入 `docs/agent/`。
- 论文模板、共享参考资料、Overleaf/LaTeX 项目和通用写作资产可放在 `docs/shared/` 或 `docs/thesis_main/manuscript/`，但按仓库现有 `.gitignore` 默认作为本地资料资产，不强制加入 Git。
- `docs/legacy/` 默认不迁移、不修订。

## 同步规则

- 新增、删除或移动 `tools/`、`docs/` 文件后，检查并必要时更新 `docs/README_INDEX.md` 和 `docs/PROJECT_MAP_CLEAN_20260308.md`。
- 修改 Label Studio 运营、分发、可见性、assignment、权限或 GT 隔离时，先检查 `docs/label_studio/LS_CE_ONLY_OPERATION_SOP_v1.md`。
- 修改协议、routing、admission、worker tier、Validation 或统计口径时，先检查主线 protocol 与对应 playbook。
- 云服务器运行时 URL `/tools/vis_3d.html` 允许作为部署兼容路径保留；不要把它误判为仓库源码根目录路径。
- 不写 `export_label/`，不改变 protocol、schema、routing、SOP 语义。
