# 保存结果的读取与复现

在仓库根执行，Python标准库即可读取，无需本地服务器或计算融合。

```powershell
python research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/read_saved.py natural_display --limit 1
python research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/read_saved.py policy_summary --limit 1
python -m unittest discover -s research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026 -p test_read_saved.py -v
python research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/check_saved.py
```

Windows如需终端直接打印中文，可在PowerShell设置`$env:PYTHONIOENCODING='utf-8'`。所有正式本地入口文件明确采用UTF-8；源CSV存在BOM时按utf-8-sig读取。

## 研究台读取示例

```python
from pathlib import Path
from itertools import islice
import sys

base = Path('research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026').resolve()
sys.path.insert(0, str(base))
import read_saved

# 默认合256，保留每点exact_kind；所有单元仍是字符串。
display = list(read_saved.rows('natural_display', image='uNb9QFRL6hY-40'))
# 纯路径表用于真实路径统计和精度，不能拿混合精确展示恢复配对路径。
pure = list(read_saved.rows('natural_curves', image='uNb9QFRL6hY-40'))
# 主32策略汇总；一项结果仍需筛policy/phase/metric/weighting/difficulty。
policies = list(read_saved.rows('policy_summary'))
# 需要历史48或敏感性时显式改选，默认不会混入。
history = list(read_saved.rows('natural_curves', cohort='old48', image='uNb9QFRL6hY-40'))

shard = next(read_saved.rows('endpoint_shards'))
scalar = next(read_saved.endpoints(shard['pool_id'], stage=shard['stage']))
geometry = read_saved.geometry(scalar)
assert geometry['team_key'] == scalar['team_key']
```

`rows(alias, defaults=False, ...)`保留全部批次；`table_path(alias)`只返回原文件位置，不应用默认筛选。若用pandas，先保留seed字符串，按需把质量/计数列转数值；不要把所有列整体强转浮点，也不要将空值、失败或延期写为0。直接`pd.DataFrame(read_saved.rows(alias))`得到字符串表后再对指定测量列转换即可。

`policy_events`默认输出old16和new16两批原事件。它们相加代表合32，原事件中没有单独的`version=pooled32`；不可重复再拼一次聚合版。策略汇总中的`pooled32`与原始事件版本字段不是同一物理表层级。

## 原始大表与作者复现

新增端点已是每池分片，直接按索引读取，不需要拼出`NEW_ENDPOINT_SCALARS.csv.gz`。旧数据定位和作者逻辑缓存对应关系见[REUSED_INPUTS.json](REUSED_INPUTS.json)：母人数原字节分块与旧精度的`TABLE_SHARD_MANIFEST.json`不被复制或改写。

若克隆后母人数完整标量表未恢复，沿用原命令：

```powershell
python research/workers/personnel_mixture_comparison_20261022/restore_large_tables.py --root research/workers/personnel_population_curves_v2_20261023
```

旧精度端点可直接按其清单顺序读取`table_shards/`，无需第二份缓存。旧精确边际已是可直接读的小表。不存在某个作者中间缓存不能推断为本轮源包缺失。

作者最终版主表输入的无写入核查（需已有pandas/NumPy）：

```powershell
python research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/report26/assemble_key_tables.py --base research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026 --check-only
```

本地已检查完成回执及15个输入表头，未运行无`--check-only`的重新整理，也未运行带SHA重建的setup/helper。本次不调用`engine26/execute_extension.py`。需要研究作者整个执行过程时，先读[S10原README](source_original/S10/README.md)、[报告复现](report26/REPRODUCE.md)及[主表前置条件](report26/KEY_TABLES_REPRODUCE_ZH.md)，按其冻结提交与输入要求另行处理；当前保存表读取不要求新建worktree或复制旧输入。

本地`check_saved.py`只做源文件大小、表字段/行宽/EOF、片索引及6个指针样本检查，不生成新SHA、不复算评分、不重做独立科学审查。完整审查范围仍以[独立采用入口](../../../statistics/pro_return_review_20261023/population256_20261027/README.md)为准。
