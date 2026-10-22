# 完整事件的关系式交付

这些文件是已经完成的自然人数与类别进入顺序实验的完整事件表。只将两端重复的原始测量移到一次保存的端点表，通过精确 `team_key` 关联；未删除事件、失败、负向结果或任何已计算的事件差值。原宽表不改动。

每个源按5,000行分块处理，输出后重新逐行读取，确认 `source_row_1based` 从1连续到源表末行。新增成员差集按登记顺序的实际前缀取得；两端canonical键与源事件一致。同人数政策比较的差集人数同时与已有actual_m核对。该步骤用于交付关联，不新增融合或质量评价。

## 实际文件与覆盖

| 表 | 完整行数 | 原列数 | 保留原列 | 改为端点关联的列 | 输出列数（另含6个关联字段） | 压缩大小 MB |
|---|---:|---:|---:|---:|---:|---:|
| [NATURAL_ADJACENT_TRANSITIONS_LINKED.csv.gz](NATURAL_ADJACENT_TRANSITIONS_LINKED.csv.gz) | 169,608 | 203 | 111 | 92 | 117 | 62.70 |
| [NATURAL_PAIRED_PATH_INTERVALS_LINKED.csv.gz](NATURAL_PAIRED_PATH_INTERVALS_LINKED.csv.gz) | 45,960 | 194 | 102 | 92 | 108 | 19.10 |
| [POLICY_PAIRED_PREFIX_EVENTS_LINKED.csv.gz](POLICY_PAIRED_PREFIX_EVENTS_LINKED.csv.gz) | 229,050 | 208 | 124 | 84 | 130 | 79.11 |
| [POLICY_DIRECT_PAIRED_PREFIX_EVENTS_LINKED.csv.gz](POLICY_DIRECT_PAIRED_PREFIX_EVENTS_LINKED.csv.gz) | 112,520 | 221 | 137 | 84 | 143 | 42.82 |

## 怎样继续分析

1. 直接用本表中全部 `*_change`、`*_delta`、`*_ratio`、`*_logratio`、净席位变化和风险字段重聚合；这些值按原字符串保留，没有重算或补缺。两端Q、D10、节点、记录总时间和评分/失败状态也保留，便于直接读。
2. 读取同一交付中的 `results/ENDPOINT_SCALARS.csv.gz`，按关系映射中每端的 `team_key` 左连接。底面、三维、定位、尺度、边界、短边和参考对应等其余原值每个唯一成员集合只保存一次。`COLUMN_RETENTION_AND_ENDPOINT_MAP.csv` 逐列给出保留/关联决定及目标列。
3. 两端完整成员可从端点的 `member_workers` / `member_object_ids` 取得。新增 `members_added` / `members_removed` 直接列出方向上的成员差集；空字符串表示差集确实为空。自然前缀是增加成员，不冒称为等人数替换。
4. 完整类别人数向量按同一 `team_key` 连接 `design/ENDPOINT_CLASS_VECTORS.csv.gz`，包含结构粗/细类、联合粗/细类及UNKNOWN人数；类别轴由 `CLASS_VECTOR_AXES_BY_POOL.csv` 定义。保留逐池楼外语义，不把不同折的编号当同一类型。已有目标类人数、容量、净席位变化仍在事件中。
5. 路径过程、进入者与来源用 `path_id` 和 `k` 关联 `results/PREFIX_RESULTS.csv.gz`；精确无放回顺序、抽样权重、角色和楼外来源用 `path_id` 关联 `design/EXACT_ORDER_DESIGN.csv.gz`。端点重复使用不增加独立成员集合数。

## 方向与文件身份

- 自然相邻：current − previous；当前键为 `team_key`，前端键为 `team_key_previous`。
- 自然区间：to − from；区间原名、人数与路径保持原样。
- 政策对自然：priority − natural；自然使用 `base_path_id`，政策使用 `path_id`，人数相同。
- 角色直接对照：focal − comparison；两个角色使用同一 `base_path_id` 与人数，原角色重叠、实际m、全部类别向量席位变化都保留。

`source_row_1based` 是原CSV数据行号（不含表头），可定位历史宽表，不是新的抽样权重。表中空值、失败和n2排序延期沿用原分析。未直接出现在端点表的自然派生量，例如参考转折差和一些状态旗标，仍保留两端原值，避免信息损失。

## 清单与复现

- [DELIVERY_COVERAGE.csv](DELIVERY_COVERAGE.csv)：源/目标行数、实际字节和SHA。
- [COLUMN_RETENTION_AND_ENDPOINT_MAP.csv](COLUMN_RETENTION_AND_ENDPOINT_MAP.csv)：全部原列的决定与恢复字段。
- [EVENT_RELATION_MAP.csv](EVENT_RELATION_MAP.csv)：每种事件各端的端点、前缀、顺序及类别向量关联。
- [build_linked_event_tables.py](build_linked_event_tables.py)：实际整理代码；逐源回执保留独立阶段。

原整理脚本保留历史执行路径与源表身份。当前交付不再重复存放原宽表，直接接续请使用本目录完整关系表；需要宽表时运行：

```bash
python code/restore_event_wide.py --root . --dataset policy_paired --out restored/POLICY_PAIRED_PREFIX_EVENTS.csv.gz
```

上例当前目录为研究目录根部，完整说明见[恢复入口](../code/RESTORE_EVENT_WIDE_RECIPE.md)。四种关系表都支持恢复。原始列、行顺序、数值和缺失状态保留，事件差值不重新计算；额外的六个关联字段继续保留在LINKED表。
