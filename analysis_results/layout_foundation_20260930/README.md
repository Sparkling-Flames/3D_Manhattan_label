# 连线与表示阶段1

完整交付、坐标证据与边界：[布局表示地基与坐标核验](../../docs/thesis_main/布局表示地基与坐标核验_20260930.md)。输入统一经当前manifest验证；只是可计算性清点，不是全量研究算法或视觉正确性验证。

- 全量3441对象；人员3152记录、27人、259图。人员BEV可计算3007、列式墙带2955；失败保留原因和原资格。
- [records.csv](records.csv)：原审核、身份索引、各表示状态；[strata.csv](strata.csv)：分别列出人员/全部对象的记录、人数分母及失败；[summary.json](summary.json)、[field_contract.json](field_contract.json)。
- [合成对照](synthetic_examples.csv)、[真实坐标phase与邻接对照](real_factorial.csv)、[15份冻结源码兼容核验](selected_legacy_compatibility.json)。全量声明表示以continuous为探索候选，合同像素中心和上游生成链仍待判断。
- [合成图](synthetic_representations.png)、[真实环对照图](real_coordinate_vs_adjacency.png)。这些图是交付产物，没有浏览器截图。

复现：`python -B -m tools.thesis_main.analysis.layout_foundation_20260930 --out analysis_results/layout_foundation_20260930 --width 512`；相关44项测试及完整命令见交付文档。历史/原始数据、正式合同与研究权重未改。
