# 复现与接续

本包已完成229池、12,398条顺序、404,082个前缀与318,816个去重端点；自然部分为5,424条顺序和175,032个前缀。优先使用已经交付的结果重聚合。科学结论统一见[人员主报告第6节](../../../docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md)。

## 输入身份

本轮读取 `Sparkling-Flames/3D_Manhattan_label` main 提交 `72a44e80c344975962e1071bd54d894dd86bb4b4`。真人数据保持v2；包含用户指定提交ef148c82d的GitHub API证据位于 `SOURCE_COMMIT_ANCESTRY.json`。类与冻结输入在 `inputs/`，角色与精确顺序在 `design/`，源代码哈希在 `FROZEN_INPUT_CODE_HASHES.csv`。楼外标签与最新main对应Git blob一致：`322afaee576dbe4eed8a07436345f40cf3932d6c`；类别定义为 `b8a06874bb749b7f663c3c15f9f6de4bd4163851`。

正式输入为229个池，覆盖当前所有至少3份独立、正式质量可用作答的池。库存313个图片—条件池的逐项去向在 `coverage/FORMAL_POOL_INVENTORY_COVERAGE.csv`；未进入正式过程的36个非OOS、独立人员≥3的池缺少至少3份正式质量记录，不能用行为库存冒充完整Q曲线。本轮未改变这些资格。

## 首选：直接重新汇总，无需融合

以下命令假定当前目录是本研究目录，代码、inputs、design、results、natural、policies并列。Python版本及依赖实测版本见 `RUNTIME_VERSIONS.json`。依赖 numpy、pandas、scipy、shapely、matplotlib。

```bash
python code/join_prefix_results.py \
  --links results/PREFIX_TEAM_LINKS.csv.gz \
  --scalars results/ENDPOINT_SCALARS.csv.gz \
  --out results/PREFIX_RESULTS_REJOINED.csv.gz

python code/analyze_natural_curves.py \
  --prefix results/PREFIX_RESULTS_REJOINED.csv.gz \
  --annotations inputs/IMAGE_DIFFICULTY_OPPORTUNITIES.csv \
  --raw-pool-features inputs/RAW_POOL_FEATURE_SUMMARY.csv \
  --geometry-variation results/PREFIX_GEOMETRY_VARIATION.csv.gz \
  --caption 'v2: 24 natural orders; N<=4 exact permutations' \
  --out reproduced/natural

python code/analyze_policy_curves.py \
  --results results/PREFIX_RESULTS_REJOINED.csv.gz \
  --orders design/EXACT_ORDER_DESIGN.csv.gz \
  --annotations inputs/IMAGE_DIFFICULTY_OPPORTUNITIES.csv \
  --out reproduced/policies
```

上述政策汇总会在 `reproduced/policies/` 重新生成分析宽表；交付包本身采用完整关系式事件避免重复存两端标量。继续生成两个角色之间的精确配对对照：

```bash
python code/analyze_direct_policy_contrasts.py \
  --paired reproduced/policies/POLICY_PAIRED_PREFIX_EVENTS.csv.gz \
  --orders design/EXACT_ORDER_DESIGN.csv.gz \
  --vectors design/ENDPOINT_CLASS_VECTORS.csv.gz \
  --out reproduced/policies
```

所有命令顺序执行；全部长表同时展开会增加内存占用。缓存按成员集合去重，汇总时恢复每条抽样顺序的频率，不先对重复端点去权重。

自然表说明见 `natural/NATURAL_TABLE_GUIDE.md`；策略表与直接角色比较见 `policies/POLICY_FIELDS.md`。字段含义与缺失状态在 `DATA_DICTIONARY.md`。

## 重建精确顺序与完整构成向量

```bash
python code/register_population_orders.py \
  --snapshot inputs/INPUT_SNAPSHOT.json.gz \
  --initial-requests inputs/REQUESTS_INITIAL.json.gz \
  --labels inputs/ALL_METHOD_LABELS_LOBO.csv.gz \
  --definitions inputs/FOLD_CLASS_DEFINITIONS.csv \
  --out reproduced/design

python code/build_endpoint_class_vectors.py \
  --orders reproduced/design/EXACT_ORDER_DESIGN.csv.gz \
  --links results/PREFIX_TEAM_LINKS.csv.gz \
  --labels inputs/ALL_METHOD_LABELS_LOBO.csv.gz \
  --out reproduced/design
```

默认主种子20261023。N>4保留原4条顺序，补20条均匀无放回顺序；N=3和N=4逐一枚举全部6/24种排列，不额外把旧4条重复加权。N≤4的完整排列目录先固定种子打乱，再取策略配对子集，避免按字典序取前8条。

策略将基础随机顺序稳定分为目标类在前、其它人在后，两组内部先后保持随机。通常每个可行池×角色取8条配对顺序；一个N=3的快类条件取全部6条，两端使用相同支持。规则只看目标楼外历史中心：非冗余转折最多、历史人数最多、联合Q中心最高、联合相对时间中心最低。未知人员仍在余池。角色输入、容量、实际人员及缺机会原因均已保存。

## 只补缺失端点或选池原生重放

使用包含冻结引擎的对应GitHub提交。`--repo` 指向完整仓库根目录。以下示例只重新形成指定池的登记前缀集合：

```bash
python code/run_prefix_endpoints.py \
  --repo /absolute/path/3D_Manhattan_label \
  --orders design/EXACT_ORDER_DESIGN.csv.gz \
  --pool UwV83HsGsw3-12__manual__66a7b558e6 \
  --out reproduced/native_Uw12 \
  --jobs 1
```

如要复用现有标量可加 `--cache results/ENDPOINT_SCALARS.csv.gz`；它用于避免重复评分，不携带完整几何。提供的完整几何按 `team_key` 另表关联。大范围复现优先直接汇总；没有必要重新融合全部历史团队。冻结引擎代码位置可由 `global_study.setup_engine` 与源哈希表定位，融合7.5°对应、MV50门槛、位置、环序与评分均沿用，不在本研究目录另写替代算法。

运行器每200个新端点保存一个池内检查点，完成池另存回执。最终必须检查实际请求集合是否全部存在，不能只看回执。`repair_saved_tail.py` 只对已完成池实际缺失的集合补算，原有行保留；本轮曾补齐两个池最后3条未落盘结果，精确键与额外调用在 `results/SAVED_TAIL_REPAIR.json`。

`enrich_cached_geometry.py` 只把历史几何接回、计算几何诊断及命名清楚的B8损失块，不重评分；`geometry_variation.py` 计算同k不同成员输出的几何距离，不重融合。无效底面、缺少完整分数、两人政策延期及时间缺失均保留，不能为了重聚合方便改成0。

若需要重新计算几何波动，可由单份标量与单份几何重建分池容器，避免下载重复大缓存：

```bash
python code/restore_pool_checkpoints.py \
  --scalars results/ENDPOINT_SCALARS.csv.gz \
  --geometry results/ENDPOINT_GEOMETRY.json.gz \
  --snapshot inputs/INPUT_SNAPSHOT.json.gz \
  --out reproduced/geometry

cp results/PREFIX_TEAM_LINKS.csv.gz reproduced/geometry/PREFIX_TEAM_LINKS.csv.gz
python code/geometry_variation.py --results reproduced/geometry --jobs 4
```

两步均零次融合、零次评分；只重建容器与成对几何距离。精确身份组与全部票账仅为五个机制案例保留；其它端点保留候选几何、选中支持与必要标量，进一步深入某一票组时可按精确成员调用原引擎的 `full_state=True`。

## 源与阶段

旧v2每池4条完整自然顺序、同房子池端点、后期组成端点分别保留来源。旧v3的195,888条嵌套记录是相邻背景边，不冒称完整随机顺序；同房124,924前缀也不冒充每图全部人员池。分阶段的旧4顺序基线、真实机制与计算检查点保留独立阶段身份，最终结果以完整的 `results/COMPLETION.json` 和下载索引为准。

所有策略都使用同一个最终人员池；本轮过程结果不声称改变了全员端点。不同最终构成的既有实验继续位于人员分类主报告第4节。本轮没有重新训练人员类型、修改GT、恢复被排除作答或新增同房预测。


## 由完整关系式事件恢复分析宽表

已经提供可直接运行的标准库恢复工具，无需复制下面的示例。详细命令见[恢复说明](code/RESTORE_EVENT_WIDE_RECIPE.md)，四种表前48行的列序、缺失与数值核对见[小样本恢复回执](code/RESTORE_EVENT_WIDE_SMOKE_RECEIPT.json)。它只恢复原列，不重算事件差值。

```bash
python code/restore_event_wide.py --root . --dataset policy_paired --out restored/POLICY_PAIRED_PREFIX_EVENTS.csv.gz
```


`events/` 保留全部557,138行事件，以及所有已计算变化、比率、风险与具体成员差集。无需为恢复宽表重新融合、评分或计算差值。以下示例按列映射分块恢复政策对自然的原始列；其它三表只需替换dataset和文件名。输出字段数和数值语义与源分析宽表一致，CSV文本的小数格式不作为科学身份。

```bash
python - <<'PY'
from pathlib import Path
import gzip
import pandas as pd

root = Path.cwd()
dataset = 'policy_paired'
linked = root/'events/POLICY_PAIRED_PREFIX_EVENTS_LINKED.csv.gz'
column_map = pd.read_csv(root/'events/COLUMN_RETENTION_AND_ENDPOINT_MAP.csv')
m = column_map[column_map.dataset.eq(dataset)].sort_values('input_position')
removed = m[m.action.eq('link_endpoint')]
fields = sorted(set(removed.endpoint_column.dropna()))
endpoint = pd.read_csv(root/'results/ENDPOINT_SCALARS.csv.gz',
                       usecols=['team_key'] + fields)
lookups = []
for arm, a in removed.groupby('arm'):
    key = a.endpoint_key_column.iloc[0]
    rename = dict(zip(a.endpoint_column, a.event_column))
    columns = ['team_key'] + list(rename)
    lookups.append((key, endpoint[columns].rename(
        columns={'team_key': key, **rename})))
output = root/'reproduced/events/POLICY_PAIRED_PREFIX_EVENTS_RESTORED.csv.gz'
output.parent.mkdir(parents=True, exist_ok=True)
first = True
with gzip.open(output, 'wt', encoding='utf-8-sig', newline='') as sink:
    for block in pd.read_csv(linked, chunksize=10000):
        for key, lookup in lookups:
            block = block.merge(lookup, how='left', on=key,
                                validate='many_to_one', sort=False)
        block[m.event_column.tolist()].to_csv(sink, index=False, header=first)
        first = False
PY
```

实际事件方向及两端键见 `events/EVENT_RELATION_MAP.csv`；完整成员在端点表，类别人数向量在 `design/ENDPOINT_CLASS_VECTORS.csv.gz`。恢复和重聚合均保留无效结果、两人延期、负向和零变化；不要先按Q成功过滤再计算失败率。

## 最终目录与历史执行路径

当前固定布局为 `inputs/`、`design/`、`coverage/`、`results/`、`natural/`、`policies/`、`events/`、`cases/`、`code/`。原工作目录的 `composition` 设计文件移至design，`difficulty/final24`汇总移至natural，`composition/final`移至policies，`compact_events`移至events；上述命令均显式使用当前布局。

历史回执中的绝对工作路径和代码默认路径保留来源身份，不表示交付依赖某个临时目录。原生运行与重聚合优先按本文显式参数执行。`build_linked_event_tables.py`记录的是原工作目录中的交付精简过程，其原始宽表没有重复打包；直接接续用已交付关系表，需要完整宽表时用上面的映射恢复，或者重新运行零融合的汇总命令。五案机制及最终顺序背景保留各自脚本与阶段回执，不与全体图的主分母混用。
