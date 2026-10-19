# 类别块精简证据

本目录保留固定13个发现说明层在发现及冻结复查中的**全部事件**，并完整保留未入选的具体类别方向概要。没有按效果、p值或失败状态筛去记录。

## 文件

- `01_highlight_events.csv.gz`：全部说明层事件。A/B/C团队、参考、分数、完整／缺失状态、换人规模、来源／历史Q限制、类内／类间距离与C−B结构方向。可从这些事件重新算全部13层的均值、事件p10和失败率。
- `02_all_exact_strata.csv.xz`：所有方法×域×出入人数×n×m，以及难度细分和四种来源/Q子集；37个关键字段。以6位小数保存聚合指标；每项关键几何指标的有限支持另列。XZ是无损压缩，可由pandas直接读取或Python标准库lzma解压，无新增依赖。
- `03_loow_stratum_summary.csv.gz`：全部通过支持门槛的删人层概要和覆盖收缩。
- `04_highlight_loow_person.csv.gz`：固定13层所有已执行的具体人员删除结果，包括符号反转与删后不足3楼。
- `05_loow_support_ledger.csv.gz`：全部考虑过的删人方向层、支持与是否执行，不按效果删层。
- `FIELD_DICTIONARY.json`：字段含义、压缩支持计数顺序和指标原名。
- `COMPACT_RECEIPT.json`：来源hash、导出行数、精确请求成员一致检查、输出hash和实际大小。

## 由代码重建

分类标签、INPUT_SNAPSHOT、SPLIT与两阶段BLOCK_SPEC均使用主包中冻结版本，不从原始导出重新加工。按主包复现说明先恢复冻结融合运行时及原始仓库索引输入。

1. 用 `design_blocks.py --snapshot ... --split ... --labels ... --labels ... --spec BLOCK_DISCOVERY_SPEC.json --out DISCOVERY_BLOCK_REQUESTS.json.gz` 重建发现请求，验证同理使用 `BLOCK_VALIDATION_SPEC.json`。请求内每event含精确A/B/C人员、公共成员、出入块和team_key。生成规则／种子和原完整请求hash保留；缺机会不是补人或补零。
2. 用冻结 `fusion_runner.py` 对请求实算，再用 `summarize_blocks.py` 指定requests、runs、两份labels、历史features、snapshot、split、phase，生成原完整逐事件表。程序逐项核对人员、类别构成、参考、人数和团队键。
3. 用 `block_specific_findings.py` 生成全部精确层与删人敏感性；用 `report_block_highlights.py` 原封不动应用固定13定义；运行 `compact_block_evidence.py` 得到本目录。所有CLI完整参数可见主包脚本/对应receipt，运行时依赖由主包requirements固定。
4. 本次精简程序再次把所有保留事件的公共／出／入成员与原请求逐项核对，且按团队键保存了联合人员摘要hash到receipt；主表数值CSV再次读回后校验缺失、类型与精度。代表可视化案例另外独立保存精确人员和最终几何。

不同团队／事件不等于独立图片或人员；均值按图片、建筑层次计算。p10是配对事件差值的低尾；评分失败不补零。来源匹配与Q接近没有机会的情况仍保留在相关汇总，不把缺机会当低能力。困难域来自已有难度复核，不能据此声称新图自动采集前的选人成功。
