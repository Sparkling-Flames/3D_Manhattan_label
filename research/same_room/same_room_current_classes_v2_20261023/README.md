# 当前类别的同房跨视角研究：本地归档入口

2026-10-23。本目录归档同房01—04包和四份标量端点分片，保留原包内部结构。原作者研究报告为[REPORT_ZH.md](REPORT_ZH.md)；**采用时同时阅读[独立核验与口径修正](../../statistics/pro_return_review_20261023/same_room/SRCC_INDEPENDENT_REVIEW.md)**。

## 可直接接续的材料

- `design/PANELS.csv`、`PANEL_TEAM_LINKS.csv.gz`与`REQUESTS.json.gz`：面板、具体人员及双视角端点关联。
- `results/native/parts/ENDPOINT_SCALARS_PART_01...04.csv.gz`：四张独立CSV，共141,260唯一端点，直接合并读取即可。
- `results/taxonomy_response/inputs/LABELS_AND_HISTORIES_REQUIRED.csv.gz`：本轮实际使用的楼外标签和历史。
- `results/key_tables/`、`results/budget/`及各专题结果目录：已有构成、换人、同背景、几何摘要、时间和增人结果。
- `code/`：原设计、端点适配器与分析代码，按原README要求设置仓库来源。
- `figures/`：已有汇总图；研究台采用前按修订口径核对图注。

[LOCAL_SOURCE_FILES.csv](LOCAL_SOURCE_FILES.csv)记录全部209来源文件。原目录名`HOHONET_SRCC_20261023`在仓库中对应本目录；通过相对路径读取的包内关系不变。四份标量表不是压缩分卷，无需下载额外拼接工具。

## 当前采用与三处修正

多数有响应条件下的类别配比重复性、时间方向相对稳定及类内成员Q不确定性均采用。源极差是双端共同可评分支持上的回顾性筛选；劳动比2.006是分层算术平均；一格严格零阈值符号计数采用本地端点的49/120。具体修正表均在独立核验包，不悄悄改写作者原报告和原回执。

原同房m≤4含人为设计上限。主预算中100面板有m5—10真实容量；现有端点已补出134个纯类m5—6与193,704个同配比m5—12比较，见[大块支持及结果](../../statistics/pro_return_review_20261023/same_room/SRCC_INDEPENDENT_REVIEW.md#四m4-是什么限制还有什么可做)。两批支持不同，不直接比较平均变化谁更大。

**较大块严格ABC补充现已完成。** 新冻结设计的62,676个ABC及规模/背景路径见[大块来源](../same_room_large_block_rebuilt_20261023/README.md)，采用结论见[独立核验](../../statistics/same_room_rebuilt_audit_20261023/README.md)。它与本目录141,260端点的阶段研究分别保留身份；原Pro任务已经执行，无需重发。

## 交付范围

本地已收到01—04包、四个端点分片；未收到05案例完整包及06历史副本包。现有`CASE_INDEX`仍可用于定位来源，`figures/`含部分案例图，但不把它当作全部原答/票账几何已归档。当前主要标量与大块补充不依赖这两包；后续选用某个独缺同房案例时再取所需文件。

原作者README与复现说明保存在`source_original/`；原报告中对全交付的描述按其阶段阅读。此归档未修改GT、房间关系、正式资格、评分或融合规则。
