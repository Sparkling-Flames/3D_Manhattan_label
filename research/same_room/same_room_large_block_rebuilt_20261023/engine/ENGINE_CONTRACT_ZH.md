# 新大块实验的冻结原生端点接口

## 来源与身份

本接口服务于 **2026-10-23 重新开展的严格 ABC 实验**。它不是遗失的 111,054 个端点原件，也不以复现旧报告的数量或效应为目标。

## 本次实际完成

正式设计含 62,676 个严格 ABC 事件；两个视角、三支队伍的引用去重后为 **311,333 个精确端点、76 个池**。本批请求均为 Manual，普通与门洞依冻结池 `layer` 分开。所有请求均由原生接口实际执行，未用历史标量替代新队的几何或票账。

| 层 | 全部唯一端点尝试 | 完整可评 | 不完整 |
| --- | ---: | ---: | ---: |
| 普通 Manual | 302,346 | 297,824 | 4,522 |
| 门洞 Manual | 8,987 | 7,337 | 1,650 |
| 合计 | 311,333 | 305,161 | 6,172 |

失败按原生状态保留：`below_four` 2,600、`no_connection` 3,478、`invalid_floor` 94。`geometry_status=ok` 只说明保存的候选几何通过相应几何诊断，仍可能低于正式所需的四节点；完整性请用 `complete_evaluable` 与 `score_status`。时间在队内满足全部已知、正总时长且同来源语义的端点有 147,363 个；三臂劳动比较仍需进一步要求 A/B/C 语义相同。

正式标量共 142 字段；658 份完整状态分片逐份读至 EOF，并核对精确成员、原答对象及标量/几何关联。几何对照共 376,056 行（每事件六行），对应 365,622 个去重的有序团队对，沿用冻结角点对应。

正式端点调用 311,333 次。兼容检查另有 9 次调用，提前交付案例另有 6 次重复调用，记录调用总数为 311,348；这 15 次不增加正式设计的唯一端点数。提前案例的六队与正式输出 Q/D10 差异均为 0，几何与完整状态均一致。正式执行未重启，计算及全量合并、文件核验墙钟共 4,148.18 秒。

实际回执为 `../EXECUTION_COMPLETION.json`。端点状态分母小表位于 `../native_endpoints/ENDPOINT_STATUS_COUNTS.csv`、`ENDPOINT_STATUS_MARGINALS.csv` 与 `POOL_STATUS_COUNTS.csv`。这些是全部唯一尝试的状态统计；事件分析的共同支持与引用次数另行记录。ZIP 内部完整性由最终打包流程另行验证。

实际读取 main：`e92abe8631d7f01dc192ee796b46f295ece37a6d`。
运行依赖按路径保存在 `frozen_repo/`；`RUNTIME_SOURCE_MANIFEST.json` 列出每个文件的提交、字节数与 SHA-256。132 个既有冻结清单文件与其历史清单逐字节相同。另包括从当前 main 读取的两份原生端点包装代码。旧包装中的历史提交元数据仍原样保留于源文件；新运行输出明确登记当前读取提交及历史冻结规则来源。

`native_team_runner.py` 只负责请求校验、调用、保留原始输出、分片和重启。没有调整预处理、人员正式资格、参考绑定、环序、投票门槛、匹配、位置估计、连接、B8L2 或 D10。正式池快照含 229 池、7,302 条记录；未把被筛除作答恢复为投票成员。

## 运行

建议 Python 3.12；本次实际为 3.12.14。依赖版本见 `requirements.txt`。运行目录中的 `deps/` 只用于当前环境安装，不是交付内容。

```bash
python -m pip install -r requirements.txt
python restore_frozen_sources.py
python native_team_runner.py --requests ../design/ENDPOINT_REQUESTS.csv.gz --output ../native_endpoints --jobs 6 --chunk-size 500
```

若交付含 `frozen_repo/`，可先执行 `python restore_frozen_sources.py --verify-only`；无需下载。恢复脚本仅下载索引列出的固定提交文件，不克隆全库。已有完整 checkpoint 时，用同一条命令继续；不要改请求文件后复用相同输出目录。

## 最小请求及精确身份

每行一个唯一端点，CSV、CSV.gz、JSON 或 JSON.gz。字段：

| 字段 | 含义 |
| --- | --- |
| `pool_id` | 冻结同图、条件和参考的正式人员池 |
| `team_key` | 沿用全研究精确团队键 |
| `n` 或 `k` | 真实成员数量 |
| `member_workers` | 按编号排序，以 `\|` 分隔的实际人员 |
| `member_object_ids` | 可选；若有，将按冻结池核对原答对象绑定 |
| `reference_id/reference_version/image/image_id/condition/building` | 可选；若有，必须与池一致 |

团队键为 `pool_id + '__' + sha256(json.dumps(sorted(workers), sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:20]`。

请求预检拒绝重复成员、不合资格成员、非规范团队键和不一致对象绑定。目标 Q 不参与这个校验或团队构造。

## 原生计算输出

`FrozenNativeEngine` 可作为单进程 Python 上下文直接使用；调用 `evaluate(pool, workers)` 返回完整原生结果。

| 输出 | 解释与用途 |
| --- | --- |
| `B8L2`, `D10` | 冻结主指标及敏感性指标；不可评分保持缺失 |
| `S_bottom_deg`, `dir`, `Hmean`, `Hcenter`, `omission`, `extension`, `iou_2d`, `IoU3D100` 等 | 保留原评分器全部原始标量；历史 `WQ*` 字段仅为原生留痕，不改为本轮主评分 |
| `fusion_turn_n`, `fusion_short_turn_edges`, `fusion_redundancy_n` | 原同房研究定义：5° 近共线阈值；短边占周长不足 4% 且两端转角至少 15° |
| `floor_short_edge_03_n/05_n` | 人数研究沿用的另一种绝对边长诊断，不能与前一行混称同一短转折定义 |
| `height_*`, `top_y_mean_px`, `bottom_y_mean_px`, `centroid_*`, `geometry_area_h2` 等 | 沿用已有几何诊断；单位见原源文件，水平长度为相机高度单位 |
| `recorded_time_eligible`, `recorded_time_total_seconds` | 只有本队全部时间已知、总时长为正且同来源语义时才提供可合并的劳动时间 |
| `record_time_by_kind_json` | 各记录语义的机会数、已知数及已知和；混合语义不强行相加为正式劳动时间 |
| `source_parallel_active_seconds` | 明确同时开工假设下的最大活动耗时；不是观察到的排队或交付时间 |
| `score_status`, `score_available`, `complete_evaluable`, `score_failure_nonpolicy`, `incomplete_nonpolicy` | 全部尝试保留，失败/不完整不补为零分；2 人政策暂停另列 |
| `team_new_member_n/team_old_member_n` | 队内来源人数；旧 `new_member_n/old_member_n` 是池级元数据，另显式提供 `pool_*` 别名 |

原生 `full_state` 默认保存，包含身份组及每个成员原角点、位置分组、选中状态、支持票、门槛、节点位置、对应分配和连接诊断。它可以解释结构、位置、对应和连接变化，不依靠类别名称猜机制。

## 分片、恢复和完整性

每个池由一个进程负责，默认每 500 端点保存一对文件：

- `parts/<pool_id>/part_00001.scalars.csv.gz`
- `parts/<pool_id>/part_00001.geometry_state.jsonl.gz`
- 同名 `receipt.json` 记录确切 team_key、两文件哈希及池/请求哈希，最后写入，避免半个 checkpoint 被视为完成。

每个几何 JSONL 都有全部尝试的一行；失败行保留键和失败状态，几何可为 null。缺少完整融合时不会制造补全几何。完成后输出 `ENDPOINT_SCALARS.csv.gz`、`GEOMETRY_SHARD_INDEX.csv.gz`、`RUN_RECEIPT.json`、`OUTPUT_VALIDATION.json`。

合并程序实际读每个 CSV.gz 和 JSONL.gz 至 EOF，核对行数、字段、精确成员、object_id 和标量/几何逐行关联，再读最终合并 CSV.gz 至 EOF。交付 ZIP 仍应由总打包流程另行打开并检查其内部文件。

## 小规模端到端兼容检查

`smoke/` 使用已保存 G015 表中首四个 n=7 团队、两视角共 8 个端点，选择不依据结果。13 个既有可比量中，B8L2、D10、结构、参考召回和质量分项差异均为 0；劳动时间最大差异 `4.55e-13` 秒，来自 CSV 浮点往返。检查表为 `SMOKE_COMPATIBILITY.csv`。这是运行接口检查，不是遗失大块结果的恢复。

该次同时工作的环境中，单端点评价耗时中位数 0.167 秒、均值 0.240 秒；两进程启动和 8 队总墙钟约 29 秒。此前单队启动约 3.52 秒、评价约 0.051 秒。大规模耗时需以正式各池进度为准，复杂几何和缓存命中会改变速度。


## 严格 ABC 的同视角几何对照

```bash
python compare_event_geometry.py --events ../design/STRICT_ABC_EVENTS.csv.gz --endpoints ../native_endpoints --output ../geometry --jobs 2 --watch
```

每个正式事件的两个视角分别运行 A↔B、A↔C、B↔C；没有跨视角坐标硬对齐。`--watch` 在各原生池完成后增量处理，完整结束后保存 `EVENT_GEOMETRY_RESULTS.csv.gz`（每事件六行）与 `UNIQUE_GEOMETRY_COMPARISONS.csv.gz`。比较缓存保持有序团队对，不改变原始对应锚点和移位语义。

对应函数是冻结的 `corner_distance.corner_compare`，输出同角点数、几何完整性、唯一循环对应候选／异数／缺失等状态，以及 BEV、顶点的 mean/max/P95 距离。单位 `h` 是相机高度；不能当作米。异数、缺角、不完整与不可计算保持对应状态，不能补为零距离。逐角点行可用完整几何直接复算，只为单独选出的机制案例保存，避免反复复制。

每行保留 `event_id/view/comparison`、两个精确团队键、参考和两份几何定位。质量分析可按这三个事件键加入三臂共同可评支持；几何文件本身保留全部尝试。

## 按精确团队取回完整状态

```bash
python read_exact_team.py --native-root ../native_endpoints --team-key '<精确 team_key>' --output selected_team.json.gz
```

也可用 `--pointer 'parts/<pool>/part_00001.geometry_state.jsonl.gz#L1'` 直接读取标量表登记的定位。读取器核对保存的团队键及定位，并把所需 gzip 分片读至 EOF；不会再次运行融合或近似恢复几何。输出保留完整身份组、票账和连接状态，供独立复核或案例展示。
