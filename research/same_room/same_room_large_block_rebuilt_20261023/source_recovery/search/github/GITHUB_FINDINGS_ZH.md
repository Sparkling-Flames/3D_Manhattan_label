# GitHub真实原件检索结果

本轮核对的远程 main 仍为 `e92abe8631d7f01dc192ee796b46f295ece37a6d`，共38,686个tracked文件。没有切换本地HEAD，也没有执行融合、重新分类或重建事件。

## 取得的真实原件

本轮从GitHub取得的**所求新大块原始研究文件为0份**。检索记录本身不是研究原件，不能作为缺失设计或数据的替代。

已列出14个当前分支、25个PR和2个Release。读取main及8个直接相关分支的完整树；11类明确目标名称（大块目录、STRICT_ABC_EVENTS、111054、final_conditions、path_sampling_closeout、HOHONET_10—14、endpoint_part_06）均未命中。其它较早、明显无关的分支仅列元数据，没有逐一读取其所有内容。

## 历史与归档检查

GitHub按路径查询main历史，`research/same_room/same_room_large_block_matched_20261023/`与`research/workers/personnel_population_curves_v2_20261023/path_sampling_closeout_20261023/`均返回0条历史提交。因此没有发现可以按该路径从main旧提交恢复的原件；此结论不覆盖更名未知的外部备份。

两个Release分别是2026-10-15原图与2026-09-27旧布局研究，共9个资产，无所求大块端点或条件包。PR最新为25（论文讨论存档）与24（质量收尾），没有新的同房大块PR；25个PR正文亦未命中所求文件/目录名。

main中含“同房/大块”字样的现存候选只有旧BLOCK_TIME、独立容量和已存AC诊断表等。这些文件在旧任务中已知，**不等于后来严格ABC设计或111,054端点集合**，本轮没有将它们复制成“恢复件”。

## 本目录里的实际文件

- `BRANCH_TARGET_SEARCH.csv`：9个实际读取树的commit、文件数和目标匹配计数。
- `BROAD_SAME_ROOM_BLOCK_CANDIDATES.csv`：较宽命名候选路径，明确只是候选，不认定为所求原件。
- `RELEASE_ASSET_INDEX.csv`：真实Release资产及公开下载URL。
- `PULL_REQUEST_INDEX.csv`：25个PR的身份、头提交和状态。
- `GITHUB_RECOVERY_RECEIPT.json`：范围和结论。
- `refs_heads_tags.tsv`、`refs_pull_heads.tsv`、`releases.json`、`pulls.json`、两份path history JSON与最近30提交JSON：原始只读响应。

这些记录只支持“在本次可访问GitHub范围未找回所求原件”。是否能原样重算还须检查精确设计、生成器版本/种子、资格/标签/融合输入；不能因为存在冻结融合引擎就认定原成员设计可以恢复。
