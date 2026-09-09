# 全历史building统计与固定人员留出划分

2026-09-08。本目录仅整理身份、版本和人员划分，不计算几何指标、预测或收敛结论。核心测量与模拟由协作主任务在上级目录另行完成。没有改写旧数据、旧资格或人工裁决，没有派发新标注。

## 全部历史数据入口

来源是`uncertainty_cloud_inputs_20260906_v1/annotations.csv.gz`及`facts/annotation_version_lineage.csv.gz`。全部2501份canonical、2513个原始版本、26人、214图、270个context、22个building均保留；额外12条修订不增加独立响应或人数。Manual 1693份，Semi 574份，oos 234份分开。候选图没有进入真人响应统计。

旧资格和旧排除原因仅作属性统计，见两个census表中的JSON计数；它们未被用作划分过滤。当前20人只保留属性，不限制总入口。

| building | 图 | context | 历史人员 | 当前20中的人员 | canonical | 原始版本 | 非独立修订 | Manual | Semi | oos |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2t7WUuJeko7 | 3 | 5 | 4 | 4 | 7 | 7 | 0 | 7 | 0 | 0 |
| 7y3sRwLe3Va | 12 | 14 | 26 | 20 | 154 | 155 | 1 | 68 | 34 | 52 |
| B6ByNegPMKs | 11 | 14 | 26 | 20 | 174 | 176 | 2 | 110 | 64 | 0 |
| S9hNv5qa7GM | 10 | 12 | 20 | 20 | 56 | 56 | 0 | 56 | 0 | 0 |
| UwV83HsGsw3 | 11 | 13 | 26 | 20 | 188 | 188 | 0 | 102 | 8 | 78 |
| VFuaQ6m2Qom | 5 | 8 | 20 | 20 | 36 | 36 | 0 | 36 | 0 | 0 |
| VLzqgDo317F | 1 | 1 | 2 | 2 | 2 | 2 | 0 | 2 | 0 | 0 |
| X7HyMhZNoso | 4 | 5 | 26 | 20 | 66 | 66 | 0 | 36 | 30 | 0 |
| Z6MFQCViBuw | 4 | 6 | 26 | 20 | 50 | 50 | 0 | 15 | 35 | 0 |
| b8cTxDM8gDG | 5 | 5 | 26 | 20 | 89 | 89 | 0 | 37 | 26 | 26 |
| e9zR4mvMWw7 | 9 | 9 | 26 | 20 | 174 | 174 | 0 | 44 | 130 | 0 |
| jh4fc5c5qoQ | 7 | 9 | 10 | 10 | 15 | 15 | 0 | 15 | 0 | 0 |
| jtcxE69GiFV | 16 | 25 | 15 | 15 | 37 | 37 | 0 | 37 | 0 | 0 |
| pRbA3pwrgk9 | 11 | 17 | 20 | 20 | 48 | 48 | 0 | 48 | 0 | 0 |
| pa4otMbVnkk | 11 | 15 | 17 | 17 | 22 | 22 | 0 | 22 | 0 | 0 |
| q9vSo1VnCiC | 16 | 19 | 26 | 20 | 221 | 221 | 0 | 156 | 39 | 26 |
| rPc6DW4iMge | 10 | 10 | 26 | 20 | 192 | 194 | 2 | 166 | 26 | 0 |
| uNb9QFRL6hY | 28 | 34 | 26 | 20 | 426 | 431 | 5 | 348 | 52 | 26 |
| wc2JMjhGNzB | 15 | 19 | 26 | 20 | 258 | 260 | 2 | 137 | 121 | 0 |
| x8F5xyUWy9e | 4 | 4 | 26 | 20 | 41 | 41 | 0 | 41 | 0 | 0 |
| yqstnuAEVhm | 15 | 17 | 26 | 20 | 228 | 228 | 0 | 193 | 9 | 26 |
| zsNo4HB9uLZ | 6 | 9 | 13 | 13 | 17 | 17 | 0 | 17 | 0 | 0 |

表中人员是整栋不同人员的并集，不能当作每图人数。各阶段、条件分层见`building_stage_condition_census.csv`，同图跨阶段/block/条件保持完整context，不合并成更多独立人员。

## 划分规则

固定`seed=20260908`。建立一个`numpy.random.default_rng(seed)`，按数值排序全历史worker ID列表，顺次调用200次`permutation`。每次得到一个26人全局顺序；每个building只保留该楼出现过的人员，保留相对次序，再划分：

- 主方案`scheme=two_thirds`，`history_fraction=2/3`，历史组人数为`floor(N×2/3)`。
- 敏感性`scheme=sixty_percent`，`history_fraction=0.6`，历史组人数为`floor(N×0.6)`。
- 历史组是该楼有序名单的前缀，验证组是剩余人员。两种比例共用同一replicate的全局顺序；不同building的筛选名单可能不同。
- 同一replicate、同一building、同一scheme中，同一人员在所有图像、阶段、block和条件中固定同组。划分只读取身份，不读取几何、质量或验证结果。

例如有26人的楼，主方案为17历史＋9验证，敏感性为15历史＋11验证；有20人的楼则为13＋7及12＋8。这是楼级名单人数，某个context可能只有其中少量人员有标注，甚至一组为空。没有为补齐或获得更理想支持而重抽。

“验证组”是另一组**历史人员的既有响应**，不是真正未来新人。排列前缀不是实际提交时间或招募顺序；200次回放共享大量原始资料，不是200个独立实验。两种比例不能当独立重复样本。所有人员分组只供上级分析使用，不构成工人类型或后续招募方案。

## 文件、关键字段与直接读取

| 文件 | 粒度／字段 |
|---|---|
| `canonical_index.csv.gz` | 2501canonical，保留原索引全部字段，新增`raw_version_count`、`nonindependent_revision_count`；旧排除只是属性 |
| `annotation_version_lineage.csv.gz` | 2513个版本完整原字段；以canonical ID连接，不把版本当独立响应 |
| `building_census.csv` | 22楼；图、context、人员并集、当前20覆盖、canonical/版本/修订及Manual/Semi/oos数量；旧状态JSON计数 |
| `building_stage_condition_census.csv` | building×stage×raw_condition，同样的统计字段；context内部保留block身份 |
| `global_worker_orders.jsonl` | 200行；`replicate`从0至199，`worker_ids`为全26人的有序字符串ID列表 |
| `worker_splits.csv.gz` | 8800行＝200×22×2；`split_id=replicate\|building\|scheme`，比例、人数、`history_worker_ids_json`、`validation_worker_ids_json`均有序 |
| `context_splits.csv.gz` | 108000行＝200×270×2；split_id＋完整context_key唯一，含building/image/stage/block/condition、三种原始人数、两组人员/对应canonical ID有序列表、支持状态 |
| `CENSUS_QA.json` | 覆盖、种子、比例、规则与来源清单 |
| `VALIDATION.json` | 从输出逐条核对身份、比例、组别与支持状态的结果 |
| `FILE_LIST.json` | census目录实际交付清单，不包含自身；不管理上级核心分析文件 |

同一context中`history_worker_ids_json`与`history_canonical_ids_json`逐位置对应，验证组亦然；历史canonical列表按指定前缀顺序过滤，便于核心分析读取。是否可以在某种几何表示中使用，需要核心测量另外判断，本目录一律标为`geometry_support_status=not_evaluated_in_census`，不把原始人数当几何可用人数。

`raw_support_status`只描述原始支持：

- `history_empty`：该context没有历史组响应。
- `validation_empty`：没有验证组响应。
- `history_single_with_validation`：仅1份历史响应、有验证响应。
- `history_pair_with_validation`：至少2份历史响应、有验证响应。

这些不是“收敛／不收敛”或“通过／失败”的实验判据，也不保证验证组能计算两两差异。实际总计为history_empty 9165、validation_empty 20472、history_single_with_validation 14004、history_pair_with_validation 64359，全部留在表中。

## 复现与验证

在仓库根目录运行，只有现有numpy/pandas依赖，无需模型、图片、GPU或本机外部路径：

```powershell
.venv/Scripts/python.exe -m tools.thesis_main.data_prep.prepare_building_holdout_20260908 --root .
.venv/Scripts/python.exe -m tools.thesis_main.data_prep.prepare_building_holdout_20260908 --root . --verify-only
.venv/Scripts/python.exe -m pytest -q tests/test_prepare_building_holdout_20260908.py
```

`--out`可指定另一个census输出目录。验证器逐一核对全canonical未受旧资格过滤、原索引字段保留、版本计数、不重叠且并集完整、固定全局顺序、人数向下取整、每楼同人跨context不换组、完整context元数据、每份canonical只出现于一组。2项最小测试覆盖跨block与revision不增样本、旧排除不删人、共用随机排列与固定分组。

数据整理任务到此停止；没有计算任何k的收敛，没有利用全体旧簇进行训练选择，也没有修改旧包、共同索引或提交Git。核心分析另行报告可用几何、组间预测与不确定性，不能由本目录的原始支持状态代替。
