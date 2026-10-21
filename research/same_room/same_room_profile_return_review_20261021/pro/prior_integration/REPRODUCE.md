# 停止与旧成果整合分支：复现说明

## 版本及范围

- 主仓库：https://github.com/Sparkling-Flames/3D_Manhattan_label
- 本轮实际main：`561584c8f64d5349d497ec1c6e91f1aeb4bbd7c9`。
- 独立Dot PR #19：固定头`e83286b7814afc614253aa392050e9a3851ae058`，本轮取得时未合并。其包及停止脚本只读。
- 主分析沿用已有普通Manual、B8L2选择和D10敏感性、既定多数投票/中位数/连接，不改变资格、参考、原答或评分。
- 本轮文件是重建/新增交付，不是原47.1 MiB Pro压缩包的原件。

## Python依赖

实际运行：Python 3；numpy 2.3.5、pandas 2.2.3、matplotlib 3.10.8、scipy 1.17.0、shapely 2.2.0、Pillow 12.3.0。仅重新分析保存前缀的`rebuild_stopping.py`只需numpy/pandas；原生几何分支需仓库完整可导入及其几何依赖，特别是Shapely。绘图另需支持中文的字体。

```sh
python rebuild_stopping.py \
  --repo /path/to/3D_Manhattan_label \
  --output /path/to/output \
  --pr-dir /path/to/pr19_fixed/research/same_room/same_room_independent_followup_20261021

python online_geometry_branch.py \
  --repo /path/to/3D_Manhattan_label \
  --output /path/to/output --jobs 2

python plot_stopping.py \
  --repo /path/to/3D_Manhattan_label \
  --output /path/to/output \
  --font /path/to/NotoSansCJKsc-Regular.otf \
  --photo /path/to/S9hNv5qa7GM_ed36c0b595de42f0a4e13ba5d332814a.png
```

`--pr-dir`仅用于把本轮独立实现与PR保存表连接；不提供时仍可完整运行停止主计算。`--photo`可省略，其他三张统计/几何图仍可生成。`online_geometry_branch.py --reuse-geometry`只在同目录已有本轮保存坐标和回执时复用它们，精确核对请求键后重算决策；不重新运行融合。

运行环境可用`MPLCONFIGDIR=/tmp/hohonet_mpl`指定可写字体缓存。脚本中的`/tmp/hohonet_deps`是本轮可选依赖查找位置；常规环境已安装相同依赖时无需该目录，也不打包环境目录。

## 必要输入

相对主仓库根目录：

|输入|用途|
|---|---|
|`research/same_room/same_room_multiview_20261020/replay_nodes.csv.gz`|124,924个冻结真实前缀、Q/D10、人员键、几何完整状态、时间|
|同目录`REPLAY_GROUPS.json`|既有声明/支持池、全组与覆盖子集、共同人员|
|同目录`REPLAY_ORDERS.json.gz`|保存的人员顺序及稳定哈希抽取|
|同目录`REPLAY_POOLS.json.gz`|原生几何重建所需冻结原答、参考键及案例参考坐标|
|`tools/thesis_main/analysis/consensus_delivery_20261008.py`及原有依赖|原生`fuse`，保持7.5°对应间隙、未启用N1|
|`tools/thesis_main/analysis/wall_consensus_population_20261014.py`|几何完整合同，原本在参考比较前定义|
|`tools/thesis_main/analysis/paired_split_research/study.py`|绑定环角距中的角距与循环对应方法|
|固定PR包`stopping/summary.csv`|Dot规则数值桥，只读|

Release原图：`quality-original-images-20261015`，案例ID `S9hNv5qa7GM_ed36c0b595de42f0a4e13ba5d332814a`。字节校验、团队键与局部坐标框见`online_G046_21_visual_manifest.json`。不需要下载原图全集。

## 三种决策的明确区别

1. **源曲线决策**：其他历史视角的完整B8L2曲线已知；每一人数必须所有选中源视角都可评分，候选缺失不插值。选择距源最大值指定分差以内的最早前缀，或最大化源Q减人数。源图GT/质量与全部共同人员原答是输入要求。
2. **目标几何补收**：达到源或固定预算后，若当前几何无效、少于4点或没有连接，则继续收下一份，直到几何完整。只观察到达的目标几何，不读目标参考Q。它保证的是这次实验中的完整输出，未定义质量达标阈值。
3. **在线几何停止**：不使用源Q或目标GT；最近四次已到达输出完整且同角点数，三次相邻绑定环角距均≤2°时停止，否则收至共同池上限。固定哈希小样本分支，无阈值搜索。

源曲线的`m=1`与所有`m>N/2`单独保存；主报告使用最大历史，并列最少多数和单源。没有把全部m按组合数混成一个历史预算。`full_common_pool`是各支持池实际共同人员上限，不是固定16人。

## 结果文件及精确复算

- `stopping_summary.csv`、`stopping_group_actual_m.csv`、`stopping_target_actual_m.csv.gz`：主表、逐组与每个实际m/目标的支持和输出；全部尝试与Dot共同完整诊断分开。
- `decisions_whole_maxhistory.csv.gz`：六个全组、最大历史、8条主要规则的49,152个精确决策行。每行含源图组合、目标、实际前缀、人员/原答/参考/团队键；其他决策由相同脚本和冻结节点确定生成，不另打包所有重复前缀。
- `source_acquisition_project_cost.csv.gz`、`source_acquisition_group_actual_m.csv`、`source_acquisition_summary.csv`：实际历史划分的源+目标劳动；完整源图原答只计一次，不按重放排列重复计劳动。
- `dot_rule_bridge.csv`：重建与固定PR四种主要口径的k/Q桥。
- `online_geometry_prefixes.json.gz`：新增固定哈希分支的所有2,094个前缀坐标引用；重复实际团队可共享原生输出。没有塞入原图全集或运行环境。
- `online_geometry_orders.json`、`online_geometry_transitions.csv`、`online_geometry_decisions.csv`、`online_geometry_target.csv`、`online_geometry_summary.csv`：固定样本、每步距离、决策及同支持比较。
- `online_G046_21_case_evidence.csv`、`online_G046_21_visual_manifest.json`：案例精确来源、组件变化及局部定位。

主要结果按“路径/划分在同一目标内平均 → 目标等权 → 组等权 → 建筑等权”汇总。各图对/声明组可能重叠，不做独立房间推断。P10列是逐目标分位数的层级平均。时间主表只使用全新人员且源/目标全共同池活动时间均已知的固定支持；缺失不补值，不混合旧/新不同语义时间。

## 必要检查与计算身份

`REBUILD_RECEIPT.json`记录输入SHA256、冻结版本和Dot规则的数值重合。`ONLINE_GEOMETRY_RECEIPT.json`记录新执行1,678次原生几何融合、0次重评分、60条固定路径和全前缀结构一致性。它们不把引用已有124,924个前缀当作新增实验次数。

报告中的“相对全共同池损失>5分”和“相对固定7人损失>5分”使用不同字段。可评分均值不包含未完成结果；失败率和分母另列，不将未完成赋0分。请不要仅比较不同可评分子集的均值。
