# v2.1 来源、版本与 Q-only 人工处理覆盖的独立复核

## 判定

**固定 208 个登记事件的五臂比较中，没有发现需要新增人工排序的遗漏端点。** 从原冻结设计的全部 1,040 条“事件×臂”记录出发，原来有 32 条无 Q：其中 29 条为 `no_connection`，对应 21 个去重团队、14 个事件、8 张图；29/29 条引用及 21/21 个团队均已有这次返回的确认顺序。另 3 条是固定节点数为 3 的 A/B 端点，排序不能使节点数量达到 4。这一结果由原设计、原状态、原 670 端点和人工回收身份独立连接得到，未以“更新过的端点已同步到五臂”代替完整失败分母审查。

**GitHub 无版本漂移。** 当前默认分支 `main` 仍为 `ac395e703d1fef573d1ef3e105df0286d62a0468`，与前批分析冻结版本相同。提交时间为 `2026-11-03T16:39:32Z`，提交说明为 `Archive current ring audit and sharded cache`。实际读取的源文件和恢复的 8 个人工回收输入均与该提交的 Git blob SHA 逐字节一致，保留了 BOM、CRLF 和压缩文件字节。

这些判断只覆盖原先固定的 208 个事件，不证明全库无环结果都可恢复，也不将人工辅助结果改称原自动方法。辅助评分值、分项、原共同支持和扩展支持的数值验收由主验收脚本另行完成；本复核不修改评分或重新选队。

## 原设计边界与身份核对

原设计来源是 `q_only_exchange_20261031/DESIGN.json`、`DESIGN_LINKS.csv`、`TEAM_REQUESTS.csv`，并与原生产代码核对。原代码的 `design()` 读取当前合法半队事件，明确断言 14/7 为 147 事件、20/7 为 61 事件；五个端点臂为 A、B、STRUCTURE、Q_RAW、Q_PEER。所有事件均有 5 条链接，合计 1,040 行，精确去重后是 670 支团队。

本次重新核对了每条链接的原团队、池、成员、参考版本和 n/m。A=D∪X，B=D∪Y，STRUCTURE=D∪Z；D、X、Y、Z 保持互斥，三个替换块均为 7 人；Q_RAW 与 Q_PEER 保持同一个 D，排除 D/X/Y 后换入 7 人。原评分端点中的成员、团队人数、池和参考与请求逐项相同。未更改原选员或参考。

原合同将 Q_RAW 固定为主比较，Q_PEER 为敏感性；候选来自同一 Manual 合法池，要求已有 TARGET 标签、目标楼外至少 12 张可评分图和 3 栋楼，两个历史 Q 均可得。原 `DESIGN.json` 的 `selection_uses_target_Q=false`、`scoreable_filter_before_selection=false` 与代码吻合。这里确认的是冻结设计的来源与实现，没有重新开展分类选型，也没有根据辅助结果筛换候选。

## 五臂逐一覆盖

以下“原无连接”“已有确认顺序”均以臂内登记事件为分母。团队跨臂共用，因此这些行的端点数不能再相加当作独立团队数。

| 条件 | 臂 | 登记事件 | 原可评 | 原无连接 | 已有确认顺序 | 原节点不足 | 未覆盖无连接 |
|---|---|---:|---:|---:|---:|---:|---:|
| 14/7 | A | 147 | 143 | 3 | 3 | 1 | 0 |
| 14/7 | B | 147 | 142 | 4 | 4 | 1 | 0 |
| 14/7 | STRUCTURE | 147 | 141 | 6 | 6 | 0 | 0 |
| 14/7 | Q_RAW | 147 | 141 | 6 | 6 | 0 | 0 |
| 14/7 | Q_PEER | 147 | 142 | 5 | 5 | 0 | 0 |
| 20/7 | A | 61 | 60 | 0 | 0 | 1 | 0 |
| 20/7 | B | 61 | 60 | 1 | 1 | 0 | 0 |
| 20/7 | STRUCTURE | 61 | 59 | 2 | 2 | 0 | 0 |
| 20/7 | Q_RAW | 61 | 60 | 1 | 1 | 0 | 0 |
| 20/7 | Q_PEER | 61 | 60 | 1 | 1 | 0 | 0 |

各臂接受人工处理的原始数量不同，是因为原来的无连接数量不同。本次核查的必要条件是每臂所有需要连接审查的端点均有对应顺序，不要求给原来已经可评的团队额外改变顺序。21 个原无连接团队的固定节点数均至少为 4；没有用“原来不可评”一概跳过某个政策臂。

3 个仍不属于排序修复范围的臂事件为：

| 条件 | 图 | 事件 | 臂 | 固定节点数 |
|---|---|---|---|---:|
| 14/7 | S9hNv5qa7GM-12 | 3541b27a4eff744938462e2b | A | 3 |
| 14/7 | S9hNv5qa7GM-12 | 3541b27a4eff744938462e2b | B | 3 |
| 20/7 | x8F5xyUWy9e-08 | 7c216787f0079fdc10fcee6f | A | 3 |

这 3 个端点没有确认顺序，不构成对 Q_RAW/Q_PEER 的选择性遗漏。它们的 Q 继续缺失，不计为 0；也不在本轮擅自增删节点。

## 20/7 不同选员的完整范围

独立用 `incoming_members` 集合重算，20/7 恰为 7 个不同选员事件、7 张图。每个事件结构方案与 Q-only 共享 6/7 名换入者，Q_RAW 与 Q_PEER 在这 7 个事件内选择完全相同。以下列出一名不同换入者。

| 图 | 事件 | 结构特有换入者 | Q-only 特有换入者 | 原三政策状态 |
|---|---|---|---|---|
| VFuaQ6m2Qom-04 | 6e6f9a0afa89af30a9c559c7 | W017 | W126 | 均已可评 |
| VLzqgDo317F-02 | 83d00dcac631eda8583f5242 | W015 | W102 | 均已可评 |
| pRbA3pwrgk9-07 | 53aa853b9ea6fa522d968b6b | W017 | W104 | 均已可评 |
| pa4otMbVnkk-05 | 00e06116b9f423210e8fd67e | W015 | W122 | 均已可评 |
| pa4otMbVnkk-06 | 48dc82d9693b6ee44c4c94fb | W017 | W112 | 均已可评 |
| zsNo4HB9uLZ-11 | 87e9cf0e18ea74d915edc0ba | W015 | W126 | 均已可评 |
| S9hNv5qa7GM-09 | 154d5aebcb8aaffc968f1e09 | W102 | W002 | STRUCTURE 无连接；Q_RAW/Q_PEER 已可评 |

全 7 事件×5 臂共 35 行中，原来仅最后一行所列事件的 STRUCTURE 端点无 Q，对应已有确认的 R009905：`S9hNv5qa7GM-09__manual__v21_254__4f6164f9ca2f0929fae5`。其 Q-only 对照原来已可评，不存在未获同等处理机会的另一失败对照。相同图片上的另一个 20/7 事件 `8e5bd4565d8bc469b8301fce` 三政策选员相同，共用 R010001；该无连接团队也已被覆盖。不能只查看第一个差异事件而忽略同图其它政策队，本次 61 事件全域连接已涵盖它们。

原比较定义保持“STRUCTURE − Q-only”，按背景、替换块、池、图逐层聚合，图片等权；原代码 `image_means()` 和 `cluster_interval()` 明确规定上述聚合与 2,000 次建筑整群重采样。本报告没有用 7 个差异事件的简单均值替代完整 20/7 效应。

## 可复核文件

- `audit/FROZEN_POLICY_EVENT_INVENTORY.csv.gz`：1,040 行全设计清单，连接原 Q、原节点数、原状态及确认顺序身份。
- `audit/ORIGINAL_POLICY_FAILURE_REQUIREMENTS.csv`：全部 32 条原失败臂事件，含失败原因、团队成员、参考、人工组和审查身份。
- `audit/REQUIRED_CONNECTION_ENDPOINTS_21.csv`：21 个去重无连接端点，全部已回收顺序。
- `audit/INSUFFICIENT_NODES_3_POLICY_EVENTS.csv`：3 条节点不足的独立原因。
- `audit/ORIGINAL_POLICY_SCOPE_AND_ORDER_COVERAGE.csv`：10 个条件×臂的完整覆盖分母。
- `audit/SELECTION_IDENTITY_RECALCULATION.csv`：从身份集合重新推导的 416 行政策重合表。
- `audit/20_7_DIFFERENT_SELECTION_ALL_FIVE_ARMS.csv`：重点 7 事件的全部 35 臂记录；`20_7_DIFFERENT_SELECTION_IDENTITIES.csv` 提供不同成员。
- `audit/SOURCE_VERSION_MANIFEST.csv`、`SOURCE_AND_DESIGN_CHECKS.json`：冻结版本、源文件 Git SHA/SHA-256、逐项断言回执。
- `audit_version_and_design.py`：独立审查脚本；输入为本目录 `source/` 中精确 GitHub 快照与恢复后的人工回收目录。运行 `python audit_version_and_design.py --restored-root <HOHONET目录>`。

## 一手来源

仓库维护账号：Sparkling-Flames；2026；项目：`3D_Manhattan_label`（HOHONET v2.1 研究仓库；研究代码与数据，非期刊论文）。版本均为上述冻结提交。

1. [冻结提交和提交元数据](https://github.com/Sparkling-Flames/3D_Manhattan_label/commit/ac395e703d1fef573d1ef3e105df0286d62a0468)。
2. [《人工融合顺序接入与 v2.1 全链影响评估》](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/ac395e703d1fef573d1ef3e105df0286d62a0468/research/fusion/missing_ring_review_20261104/user_order_return/PRO_PROMPT_ZH.md)。
3. [《固定背景下的 Q-only 公平换人对照》及冻结结果目录](https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/ac395e703d1fef573d1ef3e105df0286d62a0468/research/data/releases/v2.1/q_only_exchange_20261031)。
4. [`DESIGN.json`：政策、范围和聚合合同](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/ac395e703d1fef573d1ef3e105df0286d62a0468/research/data/releases/v2.1/q_only_exchange_20261031/DESIGN.json)。
5. [`q_only_exchange_v21_20261031.py`：冻结设计与评价代码](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/ac395e703d1fef573d1ef3e105df0286d62a0468/tools/thesis_main/analysis/q_only_exchange_v21_20261031.py)。

所有表中具体值由上述原始数据独立计算，完整逐行来源见文件清单；不以先前总结性文案或通过回执代替本次核对。
