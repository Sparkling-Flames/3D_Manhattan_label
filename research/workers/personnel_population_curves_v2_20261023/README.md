# v2自然人数过程：本地归档与采用入口

2026-10-23。研究发现统一读[人员主报告第6节](../../../docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md)，实际独立核验读[两轮返回核验](../../statistics/pro_return_review_20261023/README.md)。本目录保存最新03A、03C、04C、04D来源，覆盖去重标量、必要几何、精确顺序、类别向量、输入标签、代码及五个机制案例。

**2026-10-25完整人数过程：** [低人数至30人、35人与实际满员](late_population_20261024/README.md)从既有自然前缀重聚合。普通Manual157图画到30人、92图画到35人，同一范围保留3→6、6→10、10→20及后段比较；另显示单人原答基线和2人政策暂停空档。质量、波动与失败使用明确固定范围；旧168图范围仍保留，Semi为次要分析。没有新增融合、评分或分类训练。

## 直接读取

- `results/ENDPOINT_SCALARS.csv.gz`：318,816唯一端点，原gzip约155 MiB。Git中以3个原字节分块保存，本机完整表已恢复；克隆后按下方命令恢复。
- `results/PREFIX_TEAM_LINKS.csv.gz`：404,082个前缀到精确端点的连接。
- `design/EXACT_ORDER_DESIGN.csv.gz`：12,398条完整顺序；自然部分5,424条。
- `design/ENDPOINT_CLASS_VECTORS.csv.gz`：逐团队类别人数，含未知成员。
- `results/ENDPOINT_GEOMETRY.json.gz`：318,616条保存几何；与318,816标量分母不同。
- `events/POLICY_PAIRED_PREFIX_EVENTS_LINKED.csv.gz`：**本地恢复后229,050行**，默认使用本文件。
- `events/POLICY_DIRECT_PAIRED_PREFIX_EVENTS_LINKED.csv.gz`：112,520行完整原表。
- `cases/`：五张普通原图、精确路径、投票/连接明细与已有图版；另接[7y-06门洞满员失败](cases/doorway_full_pool_20261024/README.md)，32份完整原答、4个既有端点与24条自然路径，纯提取不重算。
- [主文图表来源清单](../../statistics/pro_return_review_20261023/MAIN_FIGURE_PLAN.csv)：分类、配比、替换、难度、人数和机制六组来源。

## 从Git恢复大表

在仓库根执行：

```powershell
.venv/Scripts/python.exe research/workers/personnel_mixture_comparison_20261022/restore_large_tables.py --root research/workers/personnel_population_curves_v2_20261023
```

`LARGE_TABLE_STORAGE.json`登记原文件和分块字节数。归档时逐字节验证拼接与来源完全一致；没有重编码CSV、抽样、删列或新增哈希。本机完整文件被Git忽略，分块正常提交。

## 原件、修复与未包含材料

[LOCAL_SOURCE_FILES.csv](LOCAL_SOURCE_FILES.csv)逐项记录来源包、包内路径、仓库路径、字节数与储存方式。04D携带的仓库文档保存在`source_report/repository_snapshot/`，没有覆盖当前已核主文档。作者README/复现说明在`source_original/`保留原样。

原04C政策对自然gzip截断，只有224,972完整行。损坏原件保存在`source_original/04C/*.truncated`，仅供交付问题追溯，不作为分析输入。缺失4,078行已由完整顺序、连接及端点重建，全部已有行逐字段核对，见[恢复回执](../../statistics/pro_return_review_20261023/population/EVENT_RECONSTRUCTION_RECEIPT.json)。原作者完整性回执对应收到的原件，不用它认证修复后数据。

本次收到的四包不含自然相邻169,608行、自然区间45,960行两个派生事件原件，也不含`natural/`和`policies/`的完整派生汇总包。它们能从已归档的顺序/端点重聚合，当前正式采用的主要曲线和策略汇总已由独立核验包保存。**不将来源README所述557,138行全部事件视为本地已收到。** 展开前缀`PREFIX_RESULTS`同样可以按连接生成，无需再复制一份大表。

## 本地接续

[REPRODUCE.md](REPRODUCE.md)给最短读取路径；作者完整Linux执行记录见`source_original/REPRODUCE.md`。原代码归档不等于所有脚本都已在Windows逐一运行。本轮没有新增融合、评分或分类训练；核心科学采用范围以独立核验为准。
