# 按x顺序点对研究：接收与本地复核

2026-09-20。结论见[独立审查](独立审查与研究方向.md)。有用的贡献是可追溯的逐端点测量和分区诊断；尚未选定新正式分簇方法。

## 内容与来源

- `inputs/`：Pro使用的冻结输入、用户六图原始裁决、前轮六图AI证据。2501份记录及上述审核输入与本地上一包核对一致。
- `source_code/`、`REPORT_ZH.md`、`report/`：返回的原代码、原报告与任务说明，保持原件；文中相对路径属于原包，不保证在精简接收目录内可点击。
- `received_results/`、`received_min_horizontal/`：返回的数值结果；主关联与最小横向成本关联对照分开保存。未接收可再生成缓存、完整HTML图册或临时截图。
- `visual_checked/`：本轮实际查看的3张作答叠加证据，供追溯，不是临时界面截图。
- `local_recheck/`：本地重新计算的独立输出，`REPRODUCTION_CHECK.json`记录25张表的逐列比较，均一致（数值容差1e-9，含相对容差）。缓存可再生成。
- `RECEIPT.json`为接收范围；`SOURCE_PACKAGE_MANIFEST.json`是原包清单，不是本精简目录的完整清单。

## 本地执行

在仓库根目录运行，使用已有numpy/pandas/scipy，无需安装返回包所列版本：

```powershell
D:/anaconda/python.exe -B -m tools.thesis_main.analysis.paired_split_research
D:/anaconda/python.exe -B -m pytest tests/test_paired_split_research.py -q
```

迁入[本地模块](../../tools/thesis_main/analysis/paired_split_research/)的代码只调整导入、路径、UTF-8读取和输出位置；数值算法保留。入口支持`--input-root`、`--output`，默认写入本目录`local_recheck/`，不覆盖接收原件。不调用原包发布、打包或浏览器脚本。

本地版本为Python 3.11.7、numpy 1.26.4、pandas 2.3.1、scipy 1.11.4。原包测试及35轮随机小例通过；另用三维单位向量的叉积/点积角公式独立校验237416条端点记录及其最大值汇总，并检查分开路线的顺序，均通过。独立测试还固定了“点对中点并列时依赖存储顺序”的合成反例，并确认当前数据无精确点对中点并列。

## 结果解释合同（探索输出）

`response_eligibility.csv`记录点集、角色、关联各自的可用性；不可计算不等于单人簇。`point_ordinals.csv`的`point_index`指有效点数组的1起始索引，`ordinal`是本视图排序后的序号；原始与复原点的区别继续查输入来源。`all_fixed_endpoint_comparisons.csv.gz`保留每个实际比较端点。`pairwise_rules.csv`保留固定、循环编号、自由匹配各距离与状态。

`memberships.csv`中的簇号仅在图片×条件×视图×阈值内有意义。181是不可比签名的阻断占位，**不是实测角距**；不同总点数或角色数量不兼容不能据此报告“偏差181度”。`top_fixed`与`bottom_fixed`仍受联合总点数和两侧角色数量门约束，不是无限制单侧点集研究。

最大值、完整链接、3/6/9/12度、水平线上下角色划分及历史51.2像素关联约束均是本轮明确标记的研究设定，不升级为人工正确性规范。原始导出、既有正式合同和历史距离快照不变；未增加采集或人员排除。新六图的最终答案仍待用户。
