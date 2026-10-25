# 人员分类与换类研究：恢复、重聚合与可选重算

本文对应 `personnel_exchange_discrimination_20261025` 的实际交付。优先从已经保存的事件和端点重聚合；只有缺少必要端点，或有明确的复算目的时，才重新运行冻结融合。下列操作不会要求重新寻找分类、改参考或重做全部历史团队。

## 1. 版本、完成范围与目录约定

- **底层数据：真人 v2。** 旧包名中的 v3 是研究轮次，不是另一套数据。
- **实际计算源码快照：** `972857b2b3f548316be215400e42d6ef6e639250`。
- **研究期间另行读取的最新 main：** `e88d1d443f4000715a50475e085a773661be9c04`。本轮没有在计算过程中切换输入、参考、资格或冻结融合/评分合同。两个提交的身份分别保留。
- 最终关联表收录 **97,552 个事件**，其中严格 ABC 为 **95,264**，直接 AC 为 **2,288**；共 **283,211 个去重端点**、170 图、22 楼、31 个实际测试方法实例。端点出现次数不是独立样本数，来源及各阶段交集见 `final/FINAL_LEDGER_RECEIPT.json`、`final/UNIQUE_ENDPOINT_INVENTORY.csv.gz` 和 `final/ENDPOINT_REUSE_COUNTS.csv.gz`。
- 当前新效果主分析是 **普通 Manual**。分类历史可使用 Manual、Semi 和 scope；没有把两条件原答混成同一支评价队伍。历史 Semi、门洞、特殊范围及其它分类用途继续按原阶段保存。

本文用 `WORK` 指本研究目录，而不是要求再创建名为 WORK 的子目录。最终仓库布局为：

```text
3D_Manhattan_label/
  research/workers/personnel_exchange_discrimination_20261025/
    REPRODUCTION.md
    runtime/population/
    classifications/  features/  features_scope/  reverse/
    design/  results/  analysis/  final/
    run_native.py  restore_endpoint_cache.py
    measure_events.py  measure_ac.py
```

**解压位置有两种，不能混淆：**

1. 前面各阶段 ZIP 内是 WORK 相对路径，如 `design/...`、`results/...`；解压到 `research/workers/personnel_exchange_discrimination_20261025/`。
2. 最终 core 包含仓库相对路径；从仓库根目录解压。

建议先放置阶段包，再解压最终 core，以保留最终 core 中更新后的运行入口、说明和整合表。已有历史阶段README保持原阶段身份；例如阶段03“效果仍在进行”的文字不是最终状态，完成状态由各阶段 `COMPLETION.json` 及最终账本确认。先用 ZIP 文件清单检查顶层路径，不把一个 WORK 相对包再套进重复研究目录。

## 2. 当前实际环境与路径设置

本轮实际环境记录于 `runtime/RUNTIME.json`、`runtime/requirements-recorded.txt`，核读结果如下：

|项目|实际版本|
|---|---|
|Python|3.12.14，Clang 22.1.3 构建|
|系统|Linux 6.18.55，x86_64，glibc 2.39|
|NumPy|2.5.4|
|pandas|2.2.3|
|SciPy|1.18.1|
|Shapely|2.2.0|
|scikit-learn|1.9.1|
|Matplotlib|3.10.8|
|Pillow|12.3.0|

这些是实际执行环境记录，不是对所有其它版本组合的兼容性声明。可在自己的独立 Python 环境安装记录依赖：

```bash
python -m pip install -r runtime/requirements-recorded.txt
```

下列路径中的 `/absolute/path/3D_Manhattan_label` 替换为本地仓库绝对路径：

```bash
export HOHONET_EXCHANGE_REPO="/absolute/path/3D_Manhattan_label"
export HOHONET_RESEARCH_ROOT="$HOHONET_EXCHANGE_REPO/research/workers/personnel_exchange_discrimination_20261025"
export HOHONET_PRIOR_POPULATION="$HOHONET_RESEARCH_ROOT/runtime/population"
export HOHONET_FROZEN_ENGINE="$HOHONET_EXCHANGE_REPO/research/same_room/same_room_large_block_rebuilt_20261023/engine/frozen_repo"
cd "$HOHONET_RESEARCH_ROOT"
```

`run_native.py` 支持上述四个环境变量，以及可选的 `HOHONET_PYTHON_DEPS`。若依赖装在独立的 `--target` 目录，可把该变量设为该目录；普通虚拟环境安装通常无需设置。运行器会把存在的依赖目录加入 Python 搜索路径，并将 BLAS/OpenMP 工作线程限制为1，外层进程数由 `--jobs` 控制。本轮原执行依赖目录为 `/tmp/hohonet_deps`，该临时路径不是交付物。

**可移植性范围：** 更新后的 `run_native.py` 及导入它的恢复、指标入口支持这些环境变量；不少分析脚本通过脚本所在位置确定研究根目录，其余早期脚本仍有原执行路径常量或对 `/tmp/hohonet_deps` 的兼容处理。不要假定所有旧脚本都接受环境变量。先看相应 `--help` 或脚本顶部，对有硬编码的脚本只适配输入/输出路径，保持数据、算法、参数及随机种子不变。可在独立工作副本操作，避免覆盖已交付的结果。

## 3. 足以直接使用的小输入与结果

`runtime/population/` 已保存运行入口需要的小输入，无需恢复先前环境的整棵目录：

- `code/run_prefix_endpoints.py`：同一确定性成员键、输入清理、端点规范化与冻结引擎连接代码。
- `inputs/INPUT_SNAPSHOT.json.gz`：229个实际人员池、7302份正式原答及绑定参考。主实验按已有资格从中选择普通Manual，不能因为库存中有记录就扩大主分析资格。
- `inputs/RAW_POOL_MEMBER_FEATURES.csv.gz`、`IMAGE_DIFFICULTY_OPPORTUNITIES.csv`：人员原答特征和已有难度/机会。
- `inputs/ALL_METHOD_LABELS_LOBO.csv.gz`、`FOLD_CLASS_DEFINITIONS.csv`：复用分类与逐折定义。
- `inputs/RECORD_ELIGIBILITY_TIME_LINK.csv.gz`、`DIFFICULTY_AND_CURVE_CONTRACT.md`：资格、时间和难度约定。

复制来源和哈希在 `runtime/INPUT_COPY_MANIFEST.json`。它是必要运行输入快照，不是自然人数曲线全部历史端点缓存。反推训练所需的精确训练子集另在 `reverse/inputs/`，无需为了重新拟合该子集先恢复全部318,816个历史人数过程端点。

常用结果入口：

|目的|实际文件|
|---|---|
|全部精确事件及阶段|`final/ALL_EVENTS_EXACT.csv.gz`|
|事件到端点的关联|`final/EVENT_ENDPOINT_LINKS.csv.gz`|
|每个去重端点在哪一批|`final/UNIQUE_ENDPOINT_INVENTORY.csv.gz`|
|原样保留的逐折与ALL标签|`final/LABELS_LOBO.csv.gz`、`final/LABELS_ALL.csv`|
|每阶段精确D/X/Y/Z、A/B/C或A/C|`design/<stage>/EVENTS_EXACT.csv.gz`|
|可直接重聚合的逐事件指标|`results/<stage>/EVENT_METRICS.csv.gz`|
|分类采用与具体条件|`analysis/METHOD_ADOPTION_DECISIONS.csv`、`analysis/FINAL_CONDITIONS_COMPACT.csv`|

数值恢复和重聚合不依赖原图全集。需要重新绘制ERP背景或检查语义时，再按仓库原图索引取得对应 GitHub Release 图像；不要把重新下载原图设为读取已存统计的前置条件。

## 4. 最短复现路径：已有事件指标直接重聚合

已有 `EVENT_METRICS` 时，不需要运行融合，也不必先恢复 `native/`。下面把重聚合输出放到 `replay/`，保留交付表原样：

```bash
python analysis/summarize_exchange.py \
  --events design/screen/EVENTS_EXACT.csv.gz \
  --metrics results/screen/EVENT_METRICS.csv.gz \
  --centers design/screen/FOLD_ROLE_CENTERS.csv.gz \
  --output replay/analysis/screen

python analysis/summarize_exchange.py \
  --events design/confirm/EVENTS_EXACT.csv.gz \
  --metrics results/confirm/EVENT_METRICS.csv.gz \
  --centers design/confirm/FOLD_ROLE_CENTERS.csv.gz \
  --output replay/analysis/confirm

python analysis/summarize_exchange.py \
  --events design/reverse_screen/EVENTS_EXACT.csv.gz \
  --metrics results/reverse_screen/EVENT_METRICS.csv.gz \
  --centers design/reverse_screen/FOLD_ROLE_CENTERS.csv.gz \
  --output replay/analysis/reverse_screen

python analysis/summarize_reverse_branches.py \
  --summary replay/analysis/reverse_screen \
  --metrics results/reverse_screen/EVENT_METRICS.csv.gz

python analysis/summarize_exchange.py \
  --events design/reverse_confirm/EVENTS_EXACT.csv.gz \
  --metrics results/reverse_confirm/EVENT_METRICS.csv.gz \
  --centers design/reverse_confirm/FOLD_ROLE_CENTERS.csv.gz \
  --output replay/analysis/reverse_confirm

python analysis/summarize_reverse_branches.py \
  --summary replay/analysis/reverse_confirm \
  --metrics results/reverse_confirm/EVENT_METRICS.csv.gz
```

`summarize_exchange.py` 支持多个 `--events`、`--metrics` 文件，但会拒绝重复event_id。主结果仍按stage、phase、方法、n/m和角色区分；不要把多个方向或同一端点多次出现误作新的独立图/楼证据。`--centers`使最大类、最高转折类等角色按实际楼外中心恢复，避免拼接跨折类别编号。

规模路径独立重聚合：

```bash
python analysis/size_paths/code/analyze_fixed_block_paths.py \
  --design design/size_paths \
  --metrics results/size_paths/EVENT_METRICS.csv.gz \
  --output replay/analysis/size_paths

python analysis/large_team_ac_tail/code/analyze_ac_tail.py \
  --design design/large_team_ac_tail \
  --metrics results/large_team_ac_tail/EVENT_METRICS.csv.gz \
  --output replay/analysis/large_team_ac_tail
```

前者保存同一X/Y/Z路径的逐n、相对n10和相邻一步变化，并按设计容量固定n20/n21队列；后者只有直接AC，按k0—7及固定N35队列呈现。不要把后者输入ABC同/跨幅度汇总。

目标七人面板的完整7选6：

```bash
python analysis/analyze_target_omissions.py \
  --m6-metrics results/target_omissions/EVENT_METRICS.csv.gz \
  --m7-metrics results/screen/EVENT_METRICS.csv.gz results/confirm/EVENT_METRICS.csv.gz \
  --native-dir native \
  --output replay/analysis/target_omissions
```

这里 `--native-dir` 用于读取精确端点几何，应先完成下一节的缓存恢复；它不运行融合。n始终10，m6/m7是替换规模，不是团队人数6/7。报告分别使用C7−C6、B7−B6和净优势变化。

最终条件选择、分层和图的实际脚本包括 `analysis/build_final_conditions.py`、`analysis/final_condition_strata.py`、`analysis/plot_separation_scatter.py`、`analysis/method_adoption/code/build_method_adoption_decisions.py`，相应脚本有的使用固定 `analysis/<stage>/` 路径。需要完整重建这些最终表时，在独立工作副本把上面汇总写回该相对布局，再按脚本入口执行；不要以为指定 `replay/` 后所有下游脚本都会自动追踪过去。数字表和原始阶段身份仍由交付文件定位。

## 5. 从交付标量＋几何恢复端点缓存，不重新融合

完整几何按去重端点分批保存，没有把每个事件的三份几何重复复制。恢复程序接受以下四批：

|`--batch`|标量文件|几何文件|
|---|---|---|
|`screen`|`results/screen/NATIVE_ENDPOINT_SCALARS.csv.gz`|`results/screen/NATIVE_ENDPOINT_GEOMETRY.json.gz`|
|`batch02`|`results/batch02/ENDPOINT_SCALARS.csv.gz`|`results/batch02/ENDPOINT_GEOMETRY.json.gz`|
|`size_paths`|`results/size_paths/NATIVE_ENDPOINT_SCALARS.csv.gz`|`results/size_paths/NATIVE_ENDPOINT_GEOMETRY.json.gz`|
|`large_team_ac_tail`|`results/large_team_ac_tail/NATIVE_ENDPOINT_SCALARS.csv.gz`|`results/large_team_ac_tail/NATIVE_ENDPOINT_GEOMETRY.json.gz`|

`batch02`覆盖confirm、reverse_screen、reverse_confirm、target_omissions四组请求的并集，不是只对应一个事件阶段。各阶段包按下载索引取齐所需标量和几何后执行：

```bash
python restore_endpoint_cache.py --batch screen
python restore_endpoint_cache.py --batch batch02
python restore_endpoint_cache.py --batch size_paths
python restore_endpoint_cache.py --batch large_team_ac_tail
```

默认恢复到 `native/endpoints/<pool_id>.json.gz`。脚本按team_key合并同一确定性成员集合，核对池输入哈希，恢复列表字段、几何和节点票数，不初始化评分引擎、不计算新团队。每批写出 `native/RESTORE_<batch>.json`。可用 `--output`指定另一缓存目录；后续默认指标入口读取的是研究根目录的 `native/`，自定义目录时需保持下游路径一致。

可先恢复一个已知真实池；`--pool`可重复传入，不能自行编造pool_id：

```bash
python restore_endpoint_cache.py \
  --batch screen \
  --pool jtcxE69GiFV-03__manual__cff6e9a2b3 \
  --output replay/native_one_pool
```

本轮已经实际完成该池 **1934个团队**的恢复回环检查：池输入哈希、全部成员集合、全部几何一致，标量最大差约 `1.42e-14`，新融合数0。实测记录为 `runtime/RESTORE_ROUNDTRIP_CHECK.json`；它证明的是该单池恢复范围，不冒称已再次全池重算。

恢复缓存后，可以从端点重新生成事件指标：

```bash
python measure_events.py --stage screen
python measure_events.py --stage confirm
python measure_events.py --stage reverse_screen
python measure_events.py --stage reverse_confirm
python measure_events.py --stage target_omissions
python measure_events.py --stage size_paths
python measure_ac.py --stage large_team_ac_tail
```

这些入口复用已存在的 `metric_shards/`。ABC入口支持 `--refresh`，在需要从缓存重新生成该阶段指标时使用。AC入口没有 `--refresh`；需要逐池重新生成时，应在独立工作副本中从未放置旧metric_shards的结果目录开始。默认完整模式遇到缺端点会登记pending并报错；`--partial`仅用于明确标记的阶段结果，不能据部分输出宣称全部完成。没有取得端点与融合失败是不同状态。

## 6. 只有需要时重跑冻结融合

需要重算时，须保留仓库中的完整冻结引擎目录，至少包括其 `global_study.py`、`fusion_runner.py`、评分 `measurement_engine.zip`、`working_models.py` 及它们引用的文件。不能把主仓库最新的同名算法文件任意替换进来。默认位置为前面设置的 `HOHONET_FROZEN_ENGINE`。

按已登记请求补缺，不重新抽成员：

```bash
python run_native.py \
  --requests design/screen/REQUESTS.json.gz \
  --out native \
  --jobs 6
```

其它阶段把 `--requests`换成各自 `design/<stage>/REQUESTS.json.gz`。相同成员集合由team_key去重；已恢复的按池缓存会直接复用。每250个新端点及池完成时保存检查点，故中断后可用相同命令继续。`--jobs`可以按机器资源调整，人员、算法和请求不随之改变。

若另有完整历史标量和几何，也可显式指定：

```bash
python run_native.py \
  --requests design/size_paths/REQUESTS.json.gz \
  --out native \
  --jobs 6 \
  --cache-scalar results/screen/NATIVE_ENDPOINT_SCALARS.csv.gz \
  --cache-geometry results/screen/NATIVE_ENDPOINT_GEOMETRY.json.gz
```

该例只命中screen中已有的请求交集，其余从现有native复用或补算；不是宣称一个历史批已覆盖全部规模路径。正常可评分团队缺少历史几何时不当作本研究的完整缓存命中；实际失败端点仍保留失败状态。

`--consolidate-only`仅将给定请求集合的现有按池缓存汇成标量/几何，不运行融合：

```bash
python run_native.py \
  --requests design/size_paths/REQUESTS.json.gz \
  --out native \
  --consolidate-only
```

注意 `native/ENDPOINT_SCALARS.csv.gz`和`native/ENDPOINT_GEOMETRY.json.gz`是**最近一次请求集合的汇总**，后续批次可能覆盖它们，不能把它们自动当作全研究库存。正式阶段快照及最终端点来源表已经避免这个问题。重跑后先读取本次 `REQUEST_COVERAGE.json`、进度/回执和 `COMPLETION.json`，据实际新计算、缓存复用和缺失数量记录阶段身份。

## 7. 可选重建分类：不影响现有冻结标签

主要效果复现应直接使用交付的楼外标签和精确事件。只有核对建类过程或开展明确的新版本研究，才需要重建。建议输出到 `replay/`，不覆盖正式标签后悄悄沿用旧事件。

### 7.1 前向历史特征与分类

```bash
python classifications/code/build_condition_response_classes.py \
  --inputs runtime/population/inputs \
  --output replay/classifications \
  --features replay/features

python classifications/code/build_axis_controls.py \
  --features replay/features/HISTORY_FEATURES_ALL_LOBO.csv.gz \
  --output replay/classifications

python classifications/code/build_scope_increment.py \
  --features replay/features/HISTORY_FEATURES_ALL_LOBO.csv.gz \
  --scope features_scope/SCOPE_FEATURES_ALL_LOBO.csv.gz \
  --output replay/classifications \
  --feature-output replay/features
```

第一步构造Manual难度结构、位置尺度、联合QT和Manual＋Semi几何家族；轴对照另行生成；最后加入有支持的scope域。各楼外折从目标建筑之外形成，ALL只用于描述。域归一化、Ward/PCA、K及支持阈值按代码/注册表固定，没有为重现效果再调参。

历史输入是非门洞且有固定难度/参考的记录，声明包含两张特殊范围图作为辅助历史；不能把它重新描述为全部普通主分析图。主效果仍限普通Manual。早期 `BUILD_RECEIPT.json` 的初阶段scope缺件说明保留了阶段身份；完整当前状态以 `classifications/LATEST_STAGE_RECEIPT.json`、scope增量回执及README为准。

若要从原scope记录重新形成特征，脚本支持显式路径：

```bash
python features_scope/build_scope_features.py \
  --repo "$HOHONET_EXCHANGE_REPO" \
  --population-inputs runtime/population/inputs \
  --output replay/features_scope
```

它还需要仓库中的v2 `RECORD_EVIDENCE_LEDGER.csv.gz`及历史 `scope_response_evidence.csv`，路径在脚本中列明。286条旧`oos`字符串的恢复仅用于特征桥接，不改原资格和质量数据；scope回答倾向不等于有裁定的正确率。若只使用已交付scope表，则不需要重新恢复这两份原来源。

### 7.2 从真实自然团队响应重建反推分类

```bash
python reverse/code/learn_natural_fusion_roles.py \
  --inputs reverse/inputs \
  --output replay/reverse \
  --roster features/HISTORY_FEATURES_ALL_LOBO.csv.gz
```

它使用已保存的 `NATURAL_TRAINING_ENDPOINTS.csv.gz`和精确成员：仅普通Manual自然随机顺序、n10/12/14/16/20/24的真实融合响应；排除类别优先顺序；在图×n内居中，按建筑/图片/人数权重拟合，目标建筑从外折和内层选参中排除。当前训练子集含24,237个去重端点，实际共同有限输出拟合使用24,004个端点。失败原样保存在输入库存，不填0分参与拟合。

若要从更早完整人数包再次提取训练子集，`prepare_natural_training.py`的实际参数为 `--population`、`--links-zip`、`--output`。这里的 `--population`需要包含完整的 `design/EXACT_ORDER_DESIGN.csv.gz`及历史 `results/ENDPOINT_SCALARS.csv.gz`；`--links-zip`须包含 `results/PREFIX_TEAM_LINKS.csv.gz`。**runtime/population小输入并不含这三份大历史关联，不能宣称仅凭小输入可重新执行这个提取步骤。** 本次已交付精确训练子集和来源哈希，通常无需重新提取，更无需为此重复融合历史团队。

旧V3、XCOND及其它旧方法继续使用其原始阶段标签；不要根据本轮各折编号投票拼出一个“ALL标签”。最终账本已经从原归档补回真实旧ALL名单。

## 8. 形成最终关联与解释时保持的口径

`assemble_final_ledger.py`从七阶段事件、完成回执及四批端点快照生成统一索引，并引用仓库原始旧ALL标签。所有所需文件齐全后可在独立工作副本运行：

```bash
python assemble_final_ledger.py
```

它不融合团队；按已有team_key串接，保留 `scalar_source`、`geometry_source`、`first_delivery_batch`与精确事件来源。该脚本还需仓库 `cross_condition_taxonomy/OLD_METHOD_LABELS_ALL.csv`、`CROSS_LABELS_ALL.csv`，不能仅凭LOBO号生成旧ALL。最终文件计数以实际生成的回执为准。

复现和后续重聚合均需保持以下含义：

- 严格ABC：共同D、相同n/m，D/X/Y/Z互不重叠；同类幅度为|B−A|，跨类幅度为(|C−A|+|C−B|)/2。有符号BA/CA/CB另列；幅度更大不等于质量提高。
- 直接AC没有B，不能补造同类对照。固定XYZ人数路径每步三队加同一个人；m7保持不变；C自身变化、B自身变化与净优势变化分别保存。
- 分数不可用不作Q=0，失败保留其注册分母；缺文件、未计算、失败与连接不完整分别识别。指标各自有有效图片/建筑/事件数。
- 时间使用原记录的来源与秒数。未知时间继续未知：`source_time_total_seconds`只在队内所有人的相应时间已知时形成，`*_known_n`与`*_known_sum_seconds`另存。不得把已知部分和当完整队伍时间，也不得把库存记录时间说成本轮新测工时。
- 图/楼等权、固定块/背景层权重、phase及difficulty按实际脚本保留。保留楼内部检查与探索阶段分开；全体v2被多轮使用，不重新宣称外部盲测。
- 不更改GT、绑定参考、筛除资格、预处理、环序、B8L2/D10或融合门槛。原答9°/12°分簇、特征诊断9°对应与融合内部参数是不同对象。
- 全部已注册事件完成不等于全池排列组合穷尽；可行配置、成员集合和进入顺序三种覆盖分别解释。

本交付的正常接续方式是：**读最终条件与人员标签 → 用event_id定位精确成员 → 用team_key定位去重端点 → 从现成指标重聚合 → 只有明确缺口才补算。** 每个恢复或重算阶段都有可保存的结果入口，不需要把全部工作延迟到一个最终大包。
