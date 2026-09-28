# 局部点位数值研究：仓库接收版

先读[本地客观审查](LOCAL_REVIEW.md)，再读[原报告](reports/REPORT_ZH.md)和[16项原文答复](reports/COMMENT_REPLIES_ZH.md)。原报告、用户文字及数值结果保持原样；本地解释不冒充新的人工裁决。

这轮研究有用，接收为**已冻结历史数据上的数值研究**。图上最大端点距离＋真实代表半径可作为下一轮重点审核候选；完整链接保留对照。25.6像素未校准，未替换当前审核页或冻结正式方法。

## 在仓库运行

从仓库根目录运行，依赖见本目录`requirements.txt`：

```powershell
python -X utf8 -B tools/thesis_main/analysis/clustering_numeric_research/run_all.py --out results_recomputed --jobs 4
```

默认在本目录创建`results_recomputed/`及`work/source/`，拒绝覆盖非空输出。只核对距离与分区可加`--audit-only`。源输入直接在`inputs/source_snapshot.zip`中，无需联网、下载目录或原始日志。入口固定本次历史版本；真实新批次仍须先走既有身份、修订和冻结时间接入流程。

```powershell
python -X utf8 -B tools/thesis_main/analysis/clustering_numeric_research/compare_runs.py analysis_results/clustering_numeric_received_20260920/results analysis_results/clustering_numeric_received_20260920/results_recomputed --output analysis_results/clustering_numeric_received_20260920/reproduction_check
python -X utf8 -B -m pytest tests/test_clustering_numeric_research.py -q -p no:cacheprovider
python -X utf8 -B tools/thesis_main/analysis/clustering_numeric_research/make_figures.py
```

原交付比较器会将跨平台JSON浮点舍入判为失败。本地修正只允许浮点值的微小差异，身份、JSON整数成员标签和结构仍严格相同；两边清单分别核验自身文件，再核对所有被引用载荷。逐文件差异见[复算记录](../clustering_numeric_local_20260920/README.md)。

## 接收与复算分开

- `results/`、`reports/`、`figures/`、`evidence/`是原交付证据；`ISOLATED_*`是对方环境的复算记录。
- [本地运行目录](../clustering_numeric_local_20260920/README.md)另存本机复算、差异及验收，不用对方的测试日志代替本地测试。
- 原14个脚本和原测试完整保存在`received_code.zip`。本地运行代码位于`tools/thesis_main/analysis/clustering_numeric_research/`；调整仓库路径、测试入口、程序版本记录及上述跨平台比较器，数值算法不变。绘图默认读取本次复算并写入`figures_recomputed/`，拒绝覆盖原图目录。原报告中的`code/...`命令属于原交付目录结构，仓库内使用上面的命令。
- 原静态报告生成器及交付校验器保留在代码归档中。没有把写死研究叙述的报告生成器接成“新数据自动报告”。
- `DELIVERY_MANIFEST.json`保留原160份有效载荷清单，代码/测试改从归档读取；新增的仓库测试核对这160份原件。`RECEIPT.json`记录接收位置与边界。

最后验收仍覆盖全部214张历史图片、239个图片×条件单元；当前15项数值队列、8项暂缓以及既有39图开发案例均不等于全量视觉通过。当前没有新增采集、排除人员或最终人工裁决。
