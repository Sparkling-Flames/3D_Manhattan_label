# 融合部分复现入口

本目录是新分类的下游检验，输入依赖仓库既有快照和冻结楼外标签。建议把本目录放回仓库原相对路径运行。报告为 `REPORT_ZH.md`；最终研究包不需要复制原图全集、既有输入或运行缓存。

## 环境与不可变合同

实际环境为 Python 3.12.14、NumPy 2.3.5、Pandas 2.2.3、SciPy 1.17.0、Shapely 2.2.0（实际版本以 `INPUT_REFERENCES.json` 为准）。Shapely 安装在本次环境的 `/tmp/hohonet_deps`；脚本保留可选路径追加，复现者可以直接在自己的环境安装兼容包。代码没有修改仓库评分与融合文件。

主要原始输入：

- `research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz`：229 个已资格化池，精确成员、参考、预处理坐标和来源。
- 同目录 `fusion_engine.py`、`pool_io.py`：既有原生融合合同。
- `research/statistics/b8l2_shared_v6_20261016/inputs/measurement_engine.zip` 与 `working_models.py`：既有 B8L2/D10 评分。
- `research/workers/personnel_interchangeability_20261020/analysis/composition/fusion_runner.py`、`summarize_grid.py`：原有团队几何与相近指标。
- `research/workers/personnel_interchangeability_followup_20261020/audit_corner/corner_distance.py`：同点数、唯一循环对应的 BEV/顶部距离。
- 同目录 `common_library/COMMON_ENDPOINT_PAIRS.csv.gz`：63,476 个旧端点对；旧 K3/Rnew2 的选择条件保留，不视为新独立抽样。
- `tools/thesis_main/analysis/fusion_change_mechanisms_20261020.py`：票据分组、门槛及新票机制。
- `../route_b/lobo_labels.csv`：主结构粗细类；`../route_a/worker_labels_lobo.csv`：A2 几何分区；`../route_b/semi_new_candidate/lobo_labels.csv`：独立 Semi SP 位置尺度分类。

主标签与参数哈希保存在各设计的 `REGISTRATION.json`，关键依赖哈希另见 `INPUT_REFERENCES.json`。全数据最终标签仅作描述，不参与本目录目标验证。

融合沿用角度 gap 7.5°、MV50、偶数队保留半票节点、坐标中位数、原答连接建议及原条件评分资格。未应用 N1。B8L2 是主分，D10 仅改变评分方向尺度，同一队不产生第二份融合几何。原答 9°/12°整份标注簇不参与改变该 gap。

## 运行顺序

从仓库根目录运行。`prepare` 只按冻结标签、元数据和容量选择请求，必须先完成才进入 `run`。若仅复算报告数字，运行最后一段汇总即可。

```bash
python research/workers/personnel_taxonomy_20261021/fusion/study.py prepare
python research/workers/personnel_taxonomy_20261021/fusion/study.py run --jobs 4
python research/workers/personnel_taxonomy_20261021/fusion/study.py summarize
python research/workers/personnel_taxonomy_20261021/fusion/study.py common
python research/workers/personnel_taxonomy_20261021/fusion/relabel_a2.py
python research/workers/personnel_taxonomy_20261021/fusion/nested_paths.py prepare
python research/workers/personnel_taxonomy_20261021/fusion/nested_paths.py run --jobs 4
python research/workers/personnel_taxonomy_20261021/fusion/a2_specific.py prepare
python research/workers/personnel_taxonomy_20261021/fusion/a2_specific.py run --jobs 4
python research/workers/personnel_taxonomy_20261021/fusion/semi_position.py prepare
python research/workers/personnel_taxonomy_20261021/fusion/semi_position.py run --jobs 4
python research/workers/personnel_taxonomy_20261021/fusion/export_cases.py
python research/workers/personnel_taxonomy_20261021/fusion/summarize_extra.py
```

`export_cases.py` 直接从既有快照重构用户指定的 jtc-26 两队，不依赖未记录的手动中间结果。固定背景 W103/W104/W116/W128，替换 W113→W106；原生复算 B8L2 为 15.1437597552→65.7534284445，D10 为 15.1983726006→67.2586109111。它是评分和票据合同的针对性复核，不新增类别。

## 输出选择与解释

主实验保留 `REQUESTS.json.gz`、`TEAMS.json.gz`、`EVENTS.csv.gz`、`SUMMARY.csv`、`PER_IMAGE.csv`、`PER_BUILDING.csv` 及注册/容量/范围文件。REQUESTS 是机器可读数组；CSV 内的成员字符串仅供审阅，程序解析精确成员应读取 JSON。

配比与路径的关键输出为 `EXACT_RATIO_EFFECTS.csv`、`CLASS_COMPOSITION_EVENTS.csv.gz`、`NESTED_REQUESTS.json.gz`、`NESTED_TEAMS.json.gz`、`NESTED_COMPOSITION_PATHS.csv`、`NESTED_STEPS.csv`、`NESTED_PATH_SUMMARY.csv`。连续人数路径是预先指定或按元数据选出的固定成员顺序，不是随机总体人数曲线。

A2 专属及 SP 专属输出在相应子目录；两个子目录中的 `coarse/fine` 别名只是为了复用同一实验函数，分别都指 A2 或 SP 的单层类别，不表示新增两层分类。SP 有方向高度与面积结果在 `semi_position/SIGNED_GEOMETRY_*.csv*`；主报告采用 `SIGNED_GEOMETRY_SUMMARY.csv`。

`MECHANISM_CASES.json.gz` 仅保留 Uw-22、Semi wc-56、jtc-26 的必要原答、参考、精确成员、终点几何和完整票据，`MECHANISM_PANELS.csv` 为绘图索引。Uw/wc 的具体展示人数是结果后的机制说明选择；它们不参与重新估计总体收益或重分标签。

可以不打包 `runtime/`、`nested_runtime/`、各扩展 `runtime/`、`__pycache__/`，它们都是缓存。旧端点重新贴标的全量 `REUSED_COMMON_ENDPOINT_LABELS.csv.gz` 与 `A2_REUSED_COMMON_LABELS.csv.gz` 可由旧仓库输入与脚本恢复；精简包保留其汇总和共同背景聚合值即可。不要把缓存统计重复加入不同团队计数。

## 已完成与支持边界

主实验 3,828 队、路径 1,008 队、A2 858 队、Semi SP 114 队，四项去重仍为 5,808；用户指定 jtc-26 另 2 队，合计 5,810 个不同团队。已停止进一步实验。普通 Semi 的结构融合没有困难图容量；SP 反向 n9/m2 仅 5 楼，小于正向 11 楼。细类部分方向的块容量不足，具体不可行原因已落盘，不用全数据标签补容量。
