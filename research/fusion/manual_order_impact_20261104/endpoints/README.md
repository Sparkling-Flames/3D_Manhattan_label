# 第一批：57 组人工顺序接入、几何核查与端点评分

## 已完成结果

在用户已确认的 **57 组、22 张图** 上，保留原自动融合的节点、节点坐标、票数、节点来源、团队成员、原始标注与参考版本，只应用已返回的完整节点顺序。**56 组形成合法、可完整评价的辅助几何；1 组按原确认顺序形成自交，保持未评分。** 原自动结果全部为 `no_connection`，其 B8L2 与 D10 保持缺失。

本批 56 个新增可评端点的 B8L2 最小值为 30.8298804527329、中位数为 53.78306921371091、最大值为 93.58525089820289。这是定向案例新增支持上的描述，不是相对原自动结果的配对增益；没有将原缺失 Q 当作 0。全部 57 个团队均有明确的参考身份，当前恰为每个团队一个参考上下文。

数值来源为本目录 `ENDPOINT_SCORES.csv`、`CHECKS.json`；逐项固定性来源为 `FIXED_INPUT_CHECKS.csv`。后续模块的事件、统计、结论评估另批交付，本批没有用端点恢复率代替下游结论。

## 与原实验的方法关系

输出版本为 `v21_targeted_manual_order_assisted_20261104_v1`，基线代码与输入固定在仓库提交 `ac395e703d1fef573d1ef3e105df0286d62a0468`。

原自动路径利用完整源环覆盖已保留节点；当不存在覆盖全部节点的源环时，保留节点但不给出自动连接。`consensus_delivery_20261008.fuse` 已区分 `automatic` 与可选 `assisted` 分支；历史实验中的自动结果使用 `automatic`。本次在原保存节点上接入用户确认顺序，是单独的、定向的人工辅助敏感性版本。它不是对历史自动成功率的追溯改写，也不是未发生过的全自动结果。

本次没有调用原始融合、身份聚类、坐标中位数重算或节点筛选；原自动输出文件没有修改。人工顺序可能含有人类视觉判断，因而不能把这批结果称为原自动算法的 GT-blind 输出。57 组的选择有明确针对性，不能据此推断所有无环结果都可恢复，亦不能将新的合法几何自动认定为正确几何。

## 固定合同与测量路径

每组输入来自 `research/fusion/missing_ring_review_20261104/prepared/<review_id>.json.gz`；顺序直接读取 `user_order_return/VALIDATED_ENDPOINT_ORDERS.csv.gz`。已验证每条顺序恰好覆盖每个保留节点一次，不允许重复、缺失或额外节点。没有重新排序用户结果。

逐组检查以下约束：节点 ID 与数量不变；每个顶底坐标完全相等；支持票数与成员配对不变；团队的人员及原始对象 ID 不变；原始标注坐标不变；目标参考 ID、参考版本及参考顶底/地面坐标不变。57 组保存原始记录和参考还与当前 v2.1 主池或扩展池 `INPUT_SNAPSHOT.json` 逐项精确核对，全部一致。

实际调用链为：

1. `ring_correspondence_20261007.assemble_fusion`：直接组装保存的已选择节点及已确认顺序；原始源环投影也从固定记录复原，检查原自动 `no_source_ring_covering_all_selected_nodes` 状态。
2. `research_round_20260929.reconstruct(..., coordinate_convention='continuous')`：重建辅助几何，检查有限坐标、有效多边形、非相邻边相交等。图像坐标仍使用原 `1024×512` 连续坐标约定，原图像素不参与坐标调整。
3. `wall_consensus_quality_20261015.measured` 与 `quality_b8l2_d10_20261017.dual_scores`：复用当前冻结测量函数、参考及模型参数，输出 B8L2、D10 和完整原评分分项；参数全文保存于 `SCORING_PARAMETERS.json`。
4. 复用既有参考结构、几何形状和墙边覆盖诊断函数，提供下游需要的节点、转折、短边、冗余、墙覆盖、节点/边召回、面积、高度等字段。各实验特有的额外诊断，由相应下游批次按其原定义补充，不改变 B8L2/D10 定义。

原标注劳动量不变。人工排序耗时没有记录，`human_labor_seconds` 保持缺失，不能当作 0。后续叠加端点时须保留旧缓存的实际劳动、成员标签、历史与其他未改变的元数据。

## 仍未通过的 1 组

| 字段 | 结果 |
|---|---|
| 图像 | `pa4otMbVnkk-18` |
| 组 ID | `R024552` |
| 团队 | `pa4otMbVnkk-18__manual__bbb972aaa9__a702bf051dba0f64230b` |
| 人数 / 固定节点数 | 4 / 9 |
| 确认顺序 | `node_000 → node_001 → node_002 → node_010 → node_004 → node_005 → node_006 → node_007 → node_009` |
| 连接 / 几何状态 | 顺序可组装；`invalid_footprint` / `invalid_floor` |
| 非相邻交叉边 | 第 1、3 条边（从 0 计数），即 `node_001 → node_002` 与 `node_010 → node_004` |
| 交点 | 相机高度归一化地面坐标 `(-1.148915547616661, -2.4079876000395246)` |

没有自行修复顺序或坐标，没有为该组强行给分。`UNSCORED_REASONS.csv` 以及完整 JSON 的 `geometry_check` 和测量 `reasons` 保留机器可核对的交叉证据。后续对该组的处理仍须依据用户对这项新问题的判断；其余 56 组及不依赖该组的后续统计可继续完成。

## 文件与下游接口

| 文件 | 用途 |
|---|---|
| `ENDPOINT_SCORES.csv` | 57 行可读标量表；无前缀原兼容字段为辅助结果，`automatic_...` 保留原状态；缺失数值为空 |
| `ENDPOINTS.jsonl.gz` | 全量节点、投票、来源记录、参考快照、人工顺序、完整几何与诊断；嵌套 `automatic` 和 `assisted` 分开保存 |
| `ENDPOINT_GEOMETRY.csv.gz` | 原/辅助几何及有效性检查的序列化表 |
| `FIXED_INPUT_CHECKS.csv` | 每个端点的固定性、当前池一致性、原自动状态重现及哈希 |
| `ENDPOINT_REFERENCE_BINDINGS.csv` | 536 条原下游引用与明确参考上下文绑定；一行引用不等于一个独立事件 |
| `UNSCORED_REASONS.csv` | 保留未评分原因的 1 行端点 |
| `FIELD_CONTRACT.json` | 复合键、空值、字段含义与劳动合同 |
| `SCORING_PARAMETERS.json` | 原评分参数快照 |
| `SCORING_ENVIRONMENT_PARITY.csv` | 两个原已评分几何的 30 项环境一致性比较 |
| `SCORING_ENVIRONMENT.json` | 依赖版本、比较范围与最大误差 |
| `CHECKS.json` | 计数、状态、调用范围与固定性检查汇总 |

合并键必须使用 `(team_key, reference_id, reference_version)`。下游仅覆盖真实引用到的端点评分及几何字段；不得按图像批量替换不同团队或不同参考结果。`original_scored_support` 与 `new_scored_support` 明确区分旧支持与新增支持，`paired_Q_change` 对这 57 组均为空。`connection_changed` 只代表连边发生改变，不等价于质量提高。

## 环境与验证

Python 3.12.14；numpy 2.3.5；scipy 1.17.0；pandas 2.2.3；shapely 2.2.0；opencv-python-headless 5.0.0.93。对两个已保存的可完整评分端点，分别覆盖原始 GT 与已采用参考，以原保存几何重新测量，没有重新融合。30 项标量比较的最大绝对差为 `4.263256414560601e-14`，通过 `1e-7` 容差。

6 项合同测试通过，覆盖“绝不调用重新融合”、节点/坐标/票数固定、缺失/重复/额外顺序拒绝、自交保留无效及不同参考上下文不可混合。各批次应继续区分评分环境一致性、端点固定性和下游统计一致性，这些检查不能互相替代。

## 复现

在完整仓库根目录、安装上述依赖并备齐 57 个 prepared 输入、主/扩展池快照、当前参考目录及原已评分缓存后运行：

```bash
python -m tools.thesis_main.analysis.apply_manual_ring_orders_20261104 --parity-only
python -m tools.thesis_main.analysis.apply_manual_ring_orders_20261104
python -m pytest tests/test_manual_ring_orders_20261104.py -q
```

可指定 `--out <另一个目录>` 输出复现副本。脚本不写原实验输出。缺失输入或不一致合同会中止，不会自动替换参考、挑选节点或修改用户顺序。
