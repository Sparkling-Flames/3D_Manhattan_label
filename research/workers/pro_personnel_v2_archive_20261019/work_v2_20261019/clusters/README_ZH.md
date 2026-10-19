# v2：逐图标法簇、团队替换和楼外迁移

本目录是人员研究中的反向路线。固定 GitHub main 提交 `82c6164b0d4630de5316199c92aa405930973168`，继承冻结最终点位、绑定上下点、声明环序、参考和质量资格。所有目标图分簇均标为当图解释/oracle，不能当作事先已知的人员类型。

主结论见 `REPORT_ZH.md`；少量需要整簇/团队联动查看的案例见 `CASE_CATALOG.json`。源图是否存在由根目录原图台账另行说明，本目录不冒称已完成新视觉裁定。

## 入口与输出

|入口|含义|
|---|---|
|`DESIGN.json`|9°/12°分簇、团队采样、实际容忍范围的冻结设计|
|`CLUSTER_API.json.gz`|229质量池的全部9°/12° affinity/complete分区和冻结几何|
|`assignments.csv`|7302记录×2阈值×2算法，共29208条成员归属|
|`pair_distances.csv.gz`|121515个实际作答对；普通Manual92438对；不同点数距离为空|
|`pool_summary.csv`、`cluster_summary.csv`|逐池/整簇支持量、单例、分项描述|
|`solver_status.csv`、`ALGORITHM_AUDIT.json`|求解gap、状态、旧函数与穷举的独立对照|
|`ORACLE_REQUESTS.json.gz`|37932个冻结团队/前缀请求、准确成员、随机种子及708全路径|
|`fusion_analysis/`|实际簇内/跨簇替换、固定构成换人、严格turnover/点数匹配、失败和分布|
|`forward_swaps/`|目标建筑以外学习的Q2、QT、difficulty_type、fine_dtype_merged逐事件标签与对比|
|`conditional_dtype/`|同QT内控制连续β/T残余差异的解释诊断；不等同额外盲测|
|`transfer/`|双排除嵌套画像的LOBO共簇/最大簇成员预测|
|`swap_transfer/`|同样双排除的实际换人影响预测；历史画像与当图oracle分列|
|`pair_history_diagnostic/`|差基线之后显式展开的同难度人员对历史诊断；不是新盲测|
|`prefix_analysis/`|每一步实际成员、入场簇比例、投票阈值/完整性变化和同k路径比较|
|`room_sensitivity/`|只使用原始声明且physical_same支持的组；不造同房关系|
|`version_cluster_*`|固定v1记录、v2旧质量资格和新人员池加入的分开复核|
|`REPLAY_RECOVERY.json`|所有发现并修复的运行/汇总问题；源证据没有改写|

## 从已审计输入顺序重放

从交付根目录运行，`PYTHON` 可指定有 numpy/pandas/scipy/sklearn/shapely 的 Python。代码需要兄弟目录 `profiles/`、`fusion/` 及固定主仓库中的工具函数。本目录代码不是原始采集导出重生成器。

```bash
python work_v2_20261019/clusters/build_clusters.py
python work_v2_20261019/clusters/audit_algorithms.py
python work_v2_20261019/clusters/summarize_clusters.py
python work_v2_20261019/clusters/reverse_ring_partition_sensitivity.py
python work_v2_20261019/clusters/version_cluster_sensitivity.py
python work_v2_20261019/clusters/register_oracle_requests.py
```

`ORACLE_REQUESTS.json.gz` 交给同一冻结融合运行入口执行，先生成并完整验证 `fusion/INITIAL_replacements.csv.gz` 和最终 `composition_comparisons.csv.gz`、`prefix_transitions.csv.gz`、`team_results.csv`。不要让下游边读边写。

```bash
python work_v2_20261019/clusters/cluster_transfer.py
python work_v2_20261019/clusters/swap_transfer.py
python work_v2_20261019/clusters/summarize_swap_transfer.py
python work_v2_20261019/clusters/analyze_fusion_clusters.py --replacements-only
python work_v2_20261019/clusters/analyze_cluster_composition.py
python work_v2_20261019/clusters/forward_swap_labels.py
python work_v2_20261019/clusters/conditional_dtype_diagnostic.py
python work_v2_20261019/clusters/prefix_cluster_analysis.py
python work_v2_20261019/clusters/pair_history_diagnostic.py
python work_v2_20261019/clusters/expand_contrast_summaries.py
python work_v2_20261019/clusters/room_sensitivities.py
python work_v2_20261019/clusters/select_cluster_cases.py
python work_v2_20261019/clusters/build_cluster_report.py
```

## 解释边界

1. B8L2/D10分数来自冻结质量和融合评分工具。本路线没有通过选参考提高分数，也未加入N1。
2. 记录和团队变体的数量是实验分母，不是独立真人样本数。主要区间按建筑重采样。
3. `fine_dtype_merged`、原始`difficulty_type`和旧`fine_candidate`/hard_adaptation不是同一种细类。本路线明确分列，不混用名称。
4. 原图缺失不影响冻结坐标计算；只有在人工看过后才可写视觉裁定。节点数少于参考不等于已确证遗漏。
5. 缺失时间/失败质量没有补零。分类和统计模型中的数值编码带缺失指示，不产生新的真实证据。
6. 旧v1历史留出在本轮已属已看过资料；楼外交叉验证是现有v2数据的诚实重采样验证，不是新采集盲测。

