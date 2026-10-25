# 人员主报告整合：已完成的报告与历史材料

**当前状态：本轮研究、结果整合和现有主报告更新稿均已完成。** 请从下表的成稿进入；不再使用带占位的早期插入模板作为结果入口。本目录没有改动 Git checkout 或公开推送仓库。

## 1. 最终入口

| 用途 | 实际文件 |
|---|---|
| 保留原章节与历史成果、补入本轮完成结果的仓库主报告 | [repo_integration/docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md](../repo_integration/docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md) |
| 可单独取得的主报告成稿 | [final/人员分类与构成不确定性_主报告_更新至20261025.md](../final/人员分类与构成不确定性_主报告_更新至20261025.md) |
| 已填入实际确认、反推、规模结果的新增章节 | [MAIN_REPORT_INSERTIONS_COMPLETED_ZH.md](MAIN_REPORT_INSERTIONS_COMPLETED_ZH.md) |
| 可审阅的原主报告更新补丁 | [repo_integration/personnel_main_update.patch](../repo_integration/personnel_main_update.patch) |
| 主报告整合完成回执 | [INTEGRATION_COMPLETE.json](INTEGRATION_COMPLETE.json) |
| 全轮事件、端点、标签与阶段完成账 | [final/FINAL_LEDGER_RECEIPT.json](../final/FINAL_LEDGER_RECEIPT.json)、[final/STAGE_PHASE_COVERAGE.csv](../final/STAGE_PHASE_COVERAGE.csv) |
| 报告新增研究链接的实际文件及打包检查 | [NEW_LINK_FILE_CHECK.csv](NEW_LINK_FILE_CHECK.csv) |

完成回执记录 `all_insertions_completed=true`、未填占位数量为 0。原主报告的阶段成果保留；本轮结果分别进入新增的 1.5、4.12、5.1、7.1、8.1 节。新的确认／反推／规模结果已经写入成稿，早期模板中的“等待填入”不再表示当前研究状态。

本轮完成账为 **97,552 个事件，其中 95,264 个严格 ABC、2,288 个直接 AC；170 图、22 栋楼、31 个方法／层级实例；必要端点去重后 283,211 个**。这些数值来自统一完成回执；旧阶段的事件和端点保持各自身份，不再次相加。

## 2. 报告新增链接与打包范围

`NEW_LINK_FILE_CHECK.csv` 只检查成稿直接链接到 `research/workers/personnel_exchange_discrimination_20261025/` 的本轮文件，不重新审计历史研究，也不递归扩展全部原库链接。表内保存报告行号、链接文字、目标仓库路径、本研究包内对应路径、实际存在状态、字节数和打包要求。

这里的路径映射是：仓库目标 `research/workers/personnel_exchange_discrimination_20261025/<相对路径>` 对应当前研究包根目录的 `<相对路径>`。报告、表、图和小文件说明均应随本轮包保存；补丁本身不代替这些证据文件。未存在的目标如实标为待生成，不能凭已有索引或摘要记作取得。最终下载清单由全包统一维护。

直接链接的主要内容包括：分类及成员说明、反推说明、screen 完整比较表、规模和大团队结果、全部方法采用判断、有效条件／逐图／分项表、确认图、四组完整比较图、六例机制入口以及统一下载索引。小表中的实际人员和端点关联仍按原文件负责，避免在主报告中重复大段几何。

## 3. 保留的来源与成员说明

- `sources/`：文档整合时最新 `origin/main` **e88d1d443f4000715a50475e085a773661be9c04** 的人员主报告、模型／术语／整体入口、相关收尾说明和原四类 ALL 小表；15 份原文件按原字节保存。
- [SOURCE_SNAPSHOT_MANIFEST.csv](SOURCE_SNAPSHOT_MANIFEST.csv)、[SOURCE_READ_RECEIPT.json](SOURCE_READ_RECEIPT.json)：原路径、git blob、SHA256 与实际读取提交，实验输入提交和文档提交分开记录。
- [DSTRUCT_K3_AND_REVERSE_MEMBERS_ZH.md](DSTRUCT_K3_AND_REVERSE_MEMBERS_ZH.md)：新结构三类及四个反推方案的实际成员、未知原因、与旧类关系及 ALL／LOBO 用法。
- [FEATURE_AND_REVERSE_CANDIDATE_INVENTORY.csv](FEATURE_AND_REVERSE_CANDIDATE_INVENTORY.csv)、[CLASS_MEMBERS_ALL.csv](CLASS_MEMBERS_ALL.csv)：20 个前向配置加 4 个反推候选清点；DSTRUCT_K3 和四个反推方案的 62 人 × 5 法名单，未知不填作有效类别。
- [DSTRUCT_K3_OLD_ALL_MEMBERS.csv](DSTRUCT_K3_OLD_ALL_MEMBERS.csv)、[DSTRUCT_K3_OLD_ALL_CROSSTAB.csv](DSTRUCT_K3_OLD_ALL_CROSSTAB.csv)、[DSTRUCT_K3_OLD_LOBO_CORRESPONDENCE.csv](DSTRUCT_K3_OLD_LOBO_CORRESPONDENCE.csv)：新旧 ALL 逐人关系与独立楼外对应。
- [DSTRUCT_K3_CLASS_CENTERS_ALL.csv](DSTRUCT_K3_CLASS_CENTERS_ALL.csv)、[REVERSE_CLASS_CENTERS_ALL.csv](REVERSE_CLASS_CENTERS_ALL.csv)：描述用历史特征／响应中心。实际实验继续使用相应留出建筑标签。
- [SCREEN_REUSED_BASELINE_INVENTORY.csv](SCREEN_REUSED_BASELINE_INVENTORY.csv)、[SCREEN_Q_D10_SHAPE_COMPLETE_EXCERPT.csv](SCREEN_Q_D10_SHAPE_COMPLETE_EXCERPT.csv)、[SCREEN_STAGE_COVERAGE.json](SCREEN_STAGE_COVERAGE.json)：先期 screen 的来源、完整正负结果和支持，保持 screen 身份。
- [INTEGRATION_PROVENANCE.json](INTEGRATION_PROVENANCE.json)：成员关联与摘录实际读取的小表路径及哈希。

## 4. 历史工作稿：保留溯源，不作为完成交付入口

以下文件是报告更新前的准备状态，可能仍包含“待填入”、占位或旧的插入计划。这些文字**不表示最终结果仍未完成**，请以第 1 节成稿和完成回执为准。

| 历史文件 | 原用途与当前身份 |
|---|---|
| [MAIN_REPORT_INSERTIONS_ZH.md](MAIN_REPORT_INSERTIONS_ZH.md) | 早期插入模板，含 `{{RESEARCH_REL}}` 等占位；已由 `MAIN_REPORT_INSERTIONS_COMPLETED_ZH.md` 取代作交付入口 |
| [PENDING_INTEGRATION_FIELDS.csv](PENDING_INTEGRATION_FIELDS.csv) | 当时待填字段清单，保留形成过程；不作为当前未完成项清单 |
| [PREPARED_PATCH_PLAN.json](PREPARED_PATCH_PLAN.json) | 写入前的精确原文锚点计划；正式补丁已经另存 |
| [SOURCE_EXCERPTS.md](SOURCE_EXCERPTS.md) | 固定文档提交的原文摘录，保留原阶段状态，不能覆盖完成后的成稿 |
| [FILE_MANIFEST.csv](FILE_MANIFEST.csv) | 准备阶段文件清单；不声称覆盖此后新增的完成稿、回执或链接检查 |
| [prepare_integration_tables.py](prepare_integration_tables.py) | 原准备阶段制表／摘录代码，可复现当时材料；不会自动生成完成稿，不应在交付收尾时重跑来覆盖历史身份 |

## 5. 版本与责任范围

底层一直使用真人 **v2**。本轮实算输入提交为 `972857b2b3f548316be215400e42d6ef6e639250`；文档整合提交为 `e88d1d443f4000715a50475e085a773661be9c04`。更新文档来源不代表切换底层数据或重算全部历史。

本目录负责原文溯源、名单解释、主报告更新关联与链接检查。分类、实验、规模、背景、机制和端点的完整证据分别留在原主题目录；成稿只连接结论、证据与采用关系。
