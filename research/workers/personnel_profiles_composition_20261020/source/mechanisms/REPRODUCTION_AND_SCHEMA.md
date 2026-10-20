# 精选案例复现与字段

## 目录与最小输入

本子包包含已选案例的当前个人处理点、明确参考绑定、最终融合、局部投票账本、精确成员和历史分组依据；不包含全量团队临时状态。`path_scores.csv` 与 `path_node_support.csv` 保留四条解释路径的成员、分数和节点支持小表，足以用仓库输入复算；其 44 队已包含在本轮质量团队实验中，不加到样本量。

基础仓库版本为 `6503e2f54966a74352a6ec526f211fc3871c1427`。最小直接输入：

- `research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz`
- 仓库原有 `fusion_engine.py`、冻结测量引擎与 `tools/thesis_main/analysis/fusion_change_mechanisms_20261020.py`
- 画图复用 `research/workers/personnel_composition_study_20261019/analysis/composition/case_visuals.py` 的球面边与底面显示函数。

输入快照 SHA256：`83179b9842d06916b105d80ff181918c223e4fee2073f425f9825db124ec11d7`。

原图来自 GitHub Release `quality-original-images-20261015`。仅保留实际主板使用的 6 张图；图片 ID、原库路径、分包名在原图来源表中。绘制时将 2048×1024 原图按连续坐标缩放到 1024×512；未修改原图内容。参考、原标注、融合都使用相同坐标系与既定点序。

## 运行

以下从本子包目录运行。`REPO` 是用户已有完整 HOHONET 仓库，`PYTHONPATH` 应能发现其已安装依赖。所有输出均由参数指定，不写回正式仓库。

```bash
python code/replay_selected_cases.py --repo /path/to/HOHONET --case cases/manual_jtc26_speed_complement.json --out replay_check.json
python code/replay_selected_cases.py --repo /path/to/HOHONET --case cases/manual_Uw22_local_dilution.json cases/manual_e9z19_lowQ_complement.json cases/semi_Z610_extra_node_pruning.json --paths path_scores.csv --out path_replay_check.json
python code/render_cases.py --repo /path/to/HOHONET --case cases/manual_jtc26_speed_complement.json --photo images/jtcxE69GiFV_c90412ad99334d3aa7a1ec74d8e543a1.png --font fonts/NotoSansSC-Regular.ttf --out figures/manual_jtc26_speed_complement.png
python code/render_profile_examples.py --repo /path/to/HOHONET --records profile_examples.json --image-dir images --font fonts/NotoSansSC-Regular.ttf --out figures/profile_W109_W112.png
python code/plot_case_paths.py --work . --font fonts/NotoSansSC-Regular.ttf
```

已实际运行最终复现入口重算 jtc-26 两队：与保留点完全一致，B8L2/D10 复算通过 1e-7 绝对容差。其余机制状态的 50 个唯一团队均在案例制作时完成重放并与保存点精确比较。没有以复算结果重新选择成员或修改方法。

环境记录：Python 3.12.14；NumPy 2.3.5、Pandas 2.2.3、SciPy 1.17.0、Matplotlib 3.10.8、Pillow 12.3.0、Shapely 2.2.0、fontTools 4.61.1。字体是 Noto Sans SC 的 regular 400 实例，按本子包使用字符裁剪，附 SIL OFL。读取与融合还依赖仓库冻结引擎本身已有的依赖。

## `personnel_case_v1` 字段

| 字段 | 含义及连接规则 |
|---|---|
| `case_id` | 本轮精选展示的稳定键，不是一个新图片或新实验样本。 |
| `pool_id`、`meta` | 对接研究台现有精确图片条件池；Manual/Semi 不合池，门洞与普通层用 `meta.layer/scene` 区分。 |
| `reference` | 原快照中的已绑定参考；`target_id` 对接目标，`reference_version` 指定版本，`points_1024x512` 与 `floor_xz_h` 用于显示和原评分。 |
| `records[].object_id` | 正式个人作答 ID，和逐人证据表一对一连接。保留原输入的 `id/worker_id/origin/order_status/order_used/source_pair_indices`。 |
| `records[].points`、`points_1024x512` | 两者相同，都是当前研究处理后的点，不宣称未经处理的原始导出。以顶/底成对，顺序保持正式输入。 |
| `history_groups` | 当前目标建筑排除后的 H/L 或历史配对 F/S 标记，不能把它当永久全局人员类型。 |
| `historical_selection` | H/L 分组所用楼外相对 Q、绝对 Q、低尾与历史支持量。 |
| `historical_matching` | F/S 的实际配对、历史相对 Q 与 log 时间、来源与时间语义；fast/slow 相对于匹配对。 |
| `panels[].team_key` | 本轮团队研究的精确队伍键。`score.member_workers/member_object_ids` 保留成员，`object_ids` 用于图层。 |
| `panels[].score` | 读取本轮团队保存的 B8L2、D10、几何诊断、范围、时间等结果。这里只为机制解释做子集保留，不另设评分。 |
| `panels[].state.identity_groups` | 候选局部实体组；`members` 保留每人的 `source_pair_index` 和观察点，`support/selected/center` 给出支持、入选与中位数。组号只在本团队内有效。 |
| `state.minimum_support` | 当前 `ceil(n/2)`，偶数半票可入选。 |
| `state.candidate` | 最终点、底面、所用节点和环序。不可按横坐标排序。 |
| `state.ring_diagnostics.edges` | `direct_workers` 是实际直接相邻观察的支持；`projected_workers` 是完整来源环在保留节点上投影后的支持。两者不等价，不能把节点支持数当边支持数。 |
| `transition/transitions` | 以共同 `(worker, source_pair_index)` 追踪的一对一、拆分、合并或多对多关系；`retained_partition_changed` 标记原有观察是否重分组。 |
| `input_provenance`、`fusion_parameters` | 仓库提交、输入快照摘要、原图来源及不变算法参数。 |

## 诊断解释

B8L2 为主，D10 为敏感性。`ref_node_recall_5/9` 与 `ref_edge_recall_5/9` 复用冻结角距离匹配诊断，属于“相对于现用参考”，不是自动语义必要墙角标注。几何 `diag_corner_recall_05` 先筛选转向严格大于 10° 的底面顶点，再在欧氏距离不超过 `0.05 × sqrt(reference area)` 的条件下最大化一一匹配数，最后最小化匹配总距离。这里的 5% 是参考面积平方根尺度，不是相机高度的 5%。底面图的坐标仍以相机高度归一化，显示坐标单位与诊断容差基准不能混为一谈。它可能与 ERP 角点对数不同；例如共线点仍是标注节点，却不一定计为几何角点。保留这种差别，不改指标以符合案例叙事。

时间只在 jtc-26 同为新批次、同时间语义的团队中比较：总活动耗时完整覆盖 5 人；最大活动耗时仅用于明确理想并行假设。其余混来源 Q 机制板不显示加总劳动，避免无条件混合时间字段。
