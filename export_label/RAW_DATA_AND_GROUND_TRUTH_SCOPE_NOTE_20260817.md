# P1/C1/C2 原始数据与 Ground Truth 范围说明（2026-08-17）

## 提交范围

本数据包只收录已经实际采集的数据，不收录计划导入文件：

- P1 / PreScreen：`export_label/stage1_chinese/`、`export_label/stage1_English/` 及 `active_logs/prescreen/`。
- C1：`export_label/stage2_Chinese/`、`export_label/stage2_English/` 及 `active_logs/c1/`。
- C2-B：`export_label/c2B_Chinese/`、`export_label/c2B_English/` 及 `active_logs/c2b/`。
- C2-A-RP Block 1：`export_label/c2arp_block1/` 与 `active_logs/c2a_rp_block1_20260810/`。
- C2-A-RP Block 2：`export_label/c2arp_block2/` 与 `active_logs/c2a_rp_block2_20260814/`。
- Ground Truth：根目录 `groudTruth*.json` 与 `export_label/人工精标/` 下的非 legacy JSON 快照。
- 其余 `export_label/` 根目录非 legacy JSON 是原始/兼容性快照，保留用于来源追踪，不因本次提交自动升级为正式输入。

明确排除：`import_json/` 计划文件、所有 `legacy/`、Block 3、worker 实名表格以及分析结果。

## Active Time 冻结状态

Active Time 只取以下五个阶段目录，不取 `active_logs/new_server/` 或 `active_logs/active_logs/`：

- `active_logs/prescreen/`
- `active_logs/c1/`
- `active_logs/c2b/`
- `active_logs/c2a_rp_block1_20260810/`
- `active_logs/c2a_rp_block2_20260814/`

C2-A-RP Block 1/2 的 `ACTIVE_TIME_FREEZE_MANIFEST.json` 已逐文件核验，manifest 所列 8 个 JSONL SHA-256 全部匹配。P1、C1、C2-B 以阶段目录副本为提交边界；P1/C1 的人工调整 audit 随冻结目录保留，以免丢失更正溯源。

## Ground Truth 验证边界

- 人工验证的 test/fine-annotation 真源是 `export_label/人工精标/` 系列快照；仓库现有说明将 `project-20-at-2026-03-27-14-57-e66c6481.json` 标记为当前 authoritative verified snapshot。
- Validation 集不能整体声称为“已人工验证”。当前可确认的 Validation 几何来源只有既有 MP3D validation reference/import 工件与 HoHoNet 自带参考数据。
- 本次上传不对 MP3D 或 HoHoNet Validation GT 进行新的人工裁决，也不把来源存在等同于人工验证。
- 文件名含“错误”的 `groudTruth` 快照是显式错误/历史快照，不得作为 authoritative GT。
- `groudTruth_2(61_84_194双标注).json` 含替代/双标注信息，不代表已完成统一裁决。
- `groudTruth(prescreen时使用的).json` 是 PreScreen 使用快照；其存在只说明运行时来源，不自动覆盖正式 final-gold/frozen binding。

逐文件大小与 SHA-256 见 `RAW_DATA_PACKAGE_MANIFEST_20260817.json`。

## 数据披露

目标仓库为公开仓库。Active Time 含 annotator/session/task/project/timestamp/route 等运行时字段；用户已于 2026-08-17 明确授权公开上传未脱敏原始日志。实名 Excel 文件仍未纳入。

