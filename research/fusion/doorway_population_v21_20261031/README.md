# 门洞 v2.1 人数曲线与物理几何归档

来源为同一冻结提交 `d4c73943ae58476880bf3ceb7b774e4ec59a95b5` 的三个有清单交付包；包内文件保留原目录和原始清单。归档接收与排除方式见 [SOURCE_ARCHIVE_INTAKE.json](HOHONET_doorway_v21_20261031/SOURCE_ARCHIVE_INTAKE.json)。

## 阅读顺序

1. [人员池与统计设计](HOHONET_doorway_v21_20261031/stage01_pools/README_ZH.md)
2. [参考与GT门禁报告](HOHONET_doorway_v21_20261031/stage02_reference_gate/REFERENCE_AND_GT_REPORT_ZH.md)
3. [最终质量与人数曲线结果](HOHONET_doorway_v21_20261031/stage05_results/RESULTS_REPORT_ZH.md)
4. [逐图共识与机制案例](HOHONET_doorway_v21_20261031/stage06_cases/FULL_POOL_AND_MECHANISMS_REPORT_ZH.md)
5. [综合报告 PDF](HOHONET_doorway_v21_20261031/stage07_synthesis/DOORWAY_FINAL_REPORT_ZH.pdf)
6. [物理几何端点总表](HOHONET_doorway_v21_20261031/stage04_computation/ENDPOINT_TARGET_SCORES.csv.gz)

原始标注以逐条 JSON 保存于 `HOHONET_doorway_v21_20261031/source/data/external/label_data/`；内层压缩容器未上传。两个包含原始全景图的HTML查看器保存在 `HOHONET_doorway_v21_20261031/local_only/`，由 `.gitignore` 排除。

## 版本边界

此包的主分析保留584份基础候选／553份筛后候选，并报告17图的人员容量、共识形成及几何端点。它在后续145份追加筛除并形成439保留版本之前完成；因此是独立的较早筛选快照，不能替代或与[当前584/439对照](../../data/doorway_review_20261030/screen439_results_20261031/RESULTS_ZH.md)混成同一分母。`DOORWAY_04`中的几何端点按包内`physical_team_key`和`score_key`连接；合并结果不改变当前筛选资格。

此包提供结果和来源证据，不含生成分析的脚本。具体分母、缺失状态和置信区间应以阶段报告及表内口径为准；不能将容量上限曲线解释为固定图片集合上的纯人数因果效应。
