# 本轮实际计算的复算入口

固定仓库提交 `a476461d7ede8db95da43de4139e612c05e618bc`，底层数据 v2.1。此处只使用已冻结的人员标签和目标池，不重新判资格、空间或 GT。运行目录是交付包根目录；`TASK_REPO` 替换成该提交的完整本地仓库路径。环境需 NumPy、pandas、SciPy、Shapely；本轮 Python 3.12，Shapely 2.2.0。

## 已冻结输入与事件直接复算

正式请求已经保存时，优先使用它们。这样不依赖重新运行任何探索选型步骤。

```bash
TASK_REPO=/path/to/3D_Manhattan_label

python experiment/run_registered.py \
  --repo "$TASK_REPO" \
  --pools "$TASK_REPO/research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json" \
          "$TASK_REPO/research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json" \
  --requests experiment/global_screen_design/REQUESTS.csv.gz \
  --output experiment/global_screen_endpoints \
  --cache-roots "$TASK_REPO/research/data/releases/v2.1/current_exchange_endpoints" \
                "$TASK_REPO/research/data/releases/v2.1/admitted_space_extension/new_space_natural256" \
                composition/other_targets_endpoints/pools \
  --cache-files experiment/benchmark/BENCHMARK_ENDPOINTS.jsonl.gz \
  --jobs 6
```

已完成的其它目标有限配比面板使用同一命令，将 `--requests` 改为 `composition/other_targets_design/TEAM_REQUESTS.csv.gz`、`--output` 改为 `composition/other_targets_endpoints`，并去掉把该输出自己列作输入缓存的参数。共有 8,940 唯一请求，其中 2,459 从旧自然曲线复用、6,481 本轮新算；本轮完整标量文件已经交付，无需为了取得它再算一次。

`--cache-roots` 只扫描本地已取得的 JSONL shards，不自动下载。缺少缓存会增加实际新算量，不改变队伍或算法。各池 `POOL_INPUT.json` 冻结输入 hash；输出路径保持相同且请求包含已有团队时可继续未算部分。每完成 100 个端点写一个原子分片；每池完成后先提供 `scalar_shards/<pool>.csv.gz`，全批完成后汇成 `ENDPOINT_SCALARS.csv.gz`。

## 从冻结标签再生成同一设计

```bash
python experiment/select_screen_grid.py \
  --primary-pools "$TASK_REPO/research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json" \
  --other-pools "$TASK_REPO/research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json" \
  --labels classification/MAIN45_LABELS_ALL_LOBO.csv.gz \
  --phases experiment/source/IMAGE_PHASE_ASSIGNMENT.csv \
  --dependencies "$TASK_REPO/research/data/releases/v2.1/pools/DEPENDENCIES.json" \
  --output experiment/global_screen_capacity

python experiment/register_adaptive.py \
  --pools "$TASK_REPO/research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json" \
          "$TASK_REPO/research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json" \
  --labels classification/MAIN45_LABELS_ALL_LOBO.csv.gz \
  --cells experiment/global_screen_capacity/SCREEN_CELLS.csv.gz \
  --output experiment/global_screen_design \
  --blocks 1 --backgrounds 1 --background-levels balanced \
  --reuse-events "$TASK_REPO/research/data/releases/v2.1/current_exchange_design/design/confirm/EVENTS_EXACT.csv.gz" \
                 "$TASK_REPO/research/data/releases/v2.1/current_exchange_design/design/reverse_confirm/EVENTS_EXACT.csv.gz"
```

随机种子 `2026102907`。抽取仅依赖池、当前折人员类别、候选容量、n/m 和固定种子；不读取目标 Q。类别编号重排不会改变同一实际分区的背景层哈希；实际端点仍按完整成员集合去重。不同候选保留独立事件身份，不能把共用端点当成独立融合样本。

最终复算脚本额外提供实际源类席位被替换比例与缓存写入同步信息；这些是报告字段的补充，不改变已冻结的 D/X/Y/Z。已交付事件中相同字段可由 `m/(m+background_source_n)` 和 `m/(m+background_target_n)` 恢复，另有 `EVENT_SEAT_FRACTIONS.csv.gz` 关联表。

## 精确关联和重要字段

- `EVENTS_EXACT.csv.gz`：逐事件方法、楼外折、源／目标类、n/m、D/X/Y/Z、精确 ABC 成员及类别人数向量、各臂 team_key。
- `REQUESTS.csv.gz`：按 team_key 去重的必要端点。`n` 是实际人数，`member_workers` 是按字典序排列的人。
- `ENDPOINT_SCALARS.csv.gz`：所有请求的 Q/D10、现有分项、结构表达、记录时间、失败状态和几何摘要。缺失评分保留空值；失败不伪填零分。
- `pools/<pool>/part_*.jsonl.gz`：上述端点的完整几何和来源；无须在每个事件重复一份几何。
- `POOL_METHOD_CAPACITY.csv.gz`、`ALL_FEASIBLE_M_N_INTERVALS.csv.gz`：完整目标空间容量，包括未在广筛实际计算的池或规模。
- `REGISTERED_COVERAGE.csv.gz`：每个登记格的真实 XYZ／D 覆盖，另列精确可行成员空间；每格抽样一组不称成员穷举。
- `FROZEN_REGISTRATION_INPUTS.json`、`RUN_PLAN.json`、`CACHE_COVERAGE.json`、`RUN_RECEIPT.json`：输入标签／请求 SHA、当前版本、实际缓存命中和新算数。

## 少量机制案例

`export_event_mechanism.py` 接收最终选定的 event_id，重放这些必要队伍以导出完整 identity_groups、支持票、是否入选、阈值和连接状态；同时核对已保存的标量。例：

```bash
python experiment/export_event_mechanism.py \
  --repo "$TASK_REPO" \
  --pools "$TASK_REPO/research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json" \
          "$TASK_REPO/research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json" \
  --events experiment/global_screen_design/EVENTS_EXACT.csv.gz \
  --scalars experiment/global_screen_endpoints/ENDPOINT_SCALARS.csv.gz \
  --event-ids REAL_EVENT_ID \
  --output cases/mechanism_traces
```

案例文件内包括完整原答和当前参考，可以据此画 ERP、BEV 和 3D；参考之外的转折仍需要原图和结构机会解释，票数或角点数不自动等于语义正确性。
