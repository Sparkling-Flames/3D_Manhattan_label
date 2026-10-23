# 本地新大块原件查找结果

本任务只检查实际文件与压缩包目录，没有运行融合、分类、重抽或研究重算。

## 结果

`ACTUAL_ORIGINALS.csv` 为有完整字段的 **0 行表**：本次在当前工作区与 `/tmp` 未找到新大块原件。

未找到的重点包括：`STRICT_ABC_EVENTS.csv.gz`、`FROZEN_COMMON_CLASS_MEMBERS.csv`、新大块 `EVENT_Q_STRUCTURE_EFFECTS`／`EVENT_EXPLANATORY_COVARIATES`／`EVENT_ENDPOINT_STATUS`、111054 端点的六份标量/几何，以及 `final_conditions`／`path_sampling_closeout` 的原代码或结果目录。

本地共检查 5 个 ZIP 的成员目录：旧同房 01、03、04 包，以及同一 10A 包的两份副本。旧三包均为此前 `HOHONET_SRCC_20261023`；没有新大块目录或嵌套压缩包。10A 唯一命中项为 `MISSING_LARGE_BLOCK_DIRECTION_FIELDS.csv`，它是缺件索引，不是原设计或结果。

对扩展名与文件名检索之外，另读了 236 份现存 CSV 的表头，查找 A/B/C 团队或 X/Y/Z 替换块结构；未发现可作为遗失新大块精确设计的候选文件。相关 Python 引用主要是本轮 10A 整理代码；main 的 `audit_reuse_capacity.py` 属于旧端点直接 AC/同配比补算，不能充当后来大块严格 ABC 的设计生成器。

## 可复核记录

- `SCAN_COMMAND.json`：实际检索范围、命令与返回状态。
- `candidate_paths.txt`：匹配扩展名/名字的实际路径，不等于恢复原件。
- `ARCHIVES_INSPECTED.csv`：5 包的字节数、SHA256、成员数与阶段。
- `ARCHIVE_MEMBER_HITS.csv`：两份 10A 中的缺件索引命中，明确标记非原件。
- `CSV_HEADER_CANDIDATES.json`：236 份表头检查的范围与零候选结果。
- `CODE_REFERENCES_NOT_ORIGINALS.json`：名称引用；不把代码提到路径当作文件存在。
- `SEARCHED_LOCATIONS.csv`：两个位置及本地查找边界。

本结果只说明当前本地范围未找到，不代替根任务的 GitHub/Library 查找结论。未从报告数字生成任何设计、结果或端点，也未复制旧包作为新原件。
