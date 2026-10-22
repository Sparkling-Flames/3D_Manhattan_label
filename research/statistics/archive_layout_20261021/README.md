# 当前分析文件直接可用：第一批整理

盘点基准 main：`51b519f943b2dd3a4fb2f0198133ac5dd17209ab`；提交基于随后合并研究台和 PR19 内容的 `515e38447bbc12fe44034ec2491c9e23ccfdc242`。本次仅整理文件组织、读取和导出入口，不开展新 Pro 审查，不调整原始数据、GT、资格或评分。PR #19 本身保持不动，新 PR 单独提供这些变更。

## 已实际处理

### 1. 当前评分引擎不再需要解 ZIP

普通目录：[measurement_engine](../b8l2_shared_v6_20261016/inputs/measurement_engine/)。原有 13 个 Python/配置文件逐字节展开，无算法改写；[文件清单](../b8l2_shared_v6_20261016/inputs/measurement_engine_manifest.json)提供原 ZIP 和各文件哈希。

`scope_quality_scoring_20261016.scoring_engine()` 默认读取普通目录。现有调用者传入旧 `measurement_engine.zip` 路径时，优先读取同名普通目录，因此拉取仓库即可运行，不需要先解压，也不需要 ZIP 文件存在。仅当普通目录不存在时，保留历史 ZIP 兼容路径。旧接口不被无关改写。

13 文件亦与历史 `pro_closeout_delta.zip` 的冻结测量实现一致。原 ZIP 保留为历史证据，不作为当前运行必须入口。旧 3152 份历史重放仍有专门历史归档来源，未冒称全部历史脚本已迁移。

### 2. PR #19 的关键逐目标表提供普通 CSV

不改 PR #19 的分支、提交或原压缩表；当前 main 已包含该成果。本独立 PR 同步把两条生成脚本的默认关键明细输出改为普通 CSV，并增加可直接读取的等价 CSV：

- [B8L2 逐人员目标表](../../same_room/same_room_independent_followup_20261021/calibration/worker_targets/B8L2.csv)
- [D10 逐人员目标表](../../same_room/same_room_independent_followup_20261021/calibration/worker_targets/D10.csv)
- [B8L2 停止目标汇总](../../same_room/same_room_independent_followup_20261021/stopping/target_summary.csv)
- [D10 停止目标汇总](../../same_room/same_room_independent_followup_20261021/stopping/d10_sensitivity/target_summary.csv)

人员表按原有 metric 自然分为两张完整 CSV，不是 ZIP 字节片。每张自带字段名，可由 `pandas.read_csv()` 或普通文本工具直接读取；无须拼包或恢复脚本。单元格字符串与源表相同；[PLAIN_TABLES.json](PLAIN_TABLES.json)记录原固定提交、行数、列名和新旧哈希。

原分析代码、完整说明及原件以 PR #19 固定头为源，当前 main 经 PR #20 已包含它。本 PR 保留新研究台接入，不重复带入那 41 个文件，也不操作原 PR。

## 已验证

- 按先测试再实现：原读取代码在“禁止打开 ZIP”的两个测试中失败，改为直接目录后全部 4 项通过。
- 包内 13 个实现/配置文件哈希相同，测量引擎与历史关闭包对应文件相同。
- G117、G015、G205 的 11 个精确团队在直接目录引擎下重新融合评分，与归档结果相同，最大检查差为 0；不是重新搜索全部团队。
- 四个普通 CSV 的字段、逐单元格内容和行数与固定源表相同。
- 没有删除旧文件，没有新增 ZIP 或 ZIP 切片，没有改变评分/GT。针对性验证不代表全仓库 CI。

## 全库盘点与边界

[ZIP_INVENTORY.json](ZIP_INVENTORY.json)记录固定 main `51b519f` 的 64 个已跟踪 ZIP（21 个位于 research/）。原清单因中文路径漏记 5 包，已补齐；大量位于明确 legacy 目录，另一些已同时有普通代码和关键表，不应全部重复解压。它区分当前引擎、本次处理、已有展开、明确历史和仍需核对来源，**不是宣称 64 个包全部属于历史或全部完成迁移**。

### 2026-10-22 复查：保留与清理边界

当前仓库仍有 64 个已跟踪 ZIP，另有 31 个未跟踪或被忽略的本地 ZIP；后者含原始数据、私有映射和本地历史快照，本次只点数，不移动或删除。PR #22 的五个返回包原件不在本地，这 64 包不能据此认定为已被 PR #22 替代。

清单字段合同：`main_commit` 固定盘点基线；`count` 等于 `items` 长度；每条 `path` 是该提交中的仓库相对 ZIP 路径，`sha` 是 Git blob ID，`bytes` 是 ZIP 文件字节数，`status` 仅表示清理审查状态。后续 main 新增 ZIP 应重新盘点，不把本快照误作实时库存。

按文件名、长度及 CRC32 寻找仓库中的普通文件，有 9 个已跟踪 ZIP 的全部成员可匹配；其中当前测量引擎 13/13、质量 READY 交付包 119/119、四空间用户包 135/135、review30 私有映射 13/13 与原图包 24/24 又逐字节核对。前三个历史镜像包的逐字节核验见[2026-10-10 重复盘点](../../../analysis_results/repo_cleanup/GitHub压缩包重复盘点_20261010.md)。匹配内容不等于包的交付身份可删除：质量 READY 包仍是人工修订后的正式交付，四空间用户包及测量引擎 ZIP 仍被脚本或清单按路径引用。

两组完整 ZIP 复用同一 Git blob：`clustering_numeric_received` 与 `local_point_clustering` 的源快照，以及 `panorama_research_received` 与 `pro_research_handoff` 的源快照。删掉其中一个当前路径不会消除历史 Git 对象，且后者路径仍被代码引用。若仅为节省当前检出体积，可优先单独评估已完全展开的 `analysis_results/research_dashboard_20260922.zip`；处理前须保留原交付回执并更新引用。

其余包不能按名称批量删除。例如质量关闭包仍保存旧阶段 ledger 和独有复现脚本；2026-10-09 质量数值核心包有普通目录中未找到的 Python 文件；部分 cluster 原始返回也有独有代码。这里的“未找到”只表示当前已跟踪普通文件中未匹配到相同名称、大小与 CRC32，不证明内容全局唯一。现阶段保持原主题路径和历史 ZIP，不进行统一搬迁。

原则：当前采用的报告、代码、关键表以普通文件作为入口；旧版、错误版、原始提交凭证可以留档。尚未提交的五个新 Pro 包及其上传切片不纳入本 PR；新 Pro 审查已按用户要求暂停，后续整理时也不能以 ZIP 作为关键文件入口。
