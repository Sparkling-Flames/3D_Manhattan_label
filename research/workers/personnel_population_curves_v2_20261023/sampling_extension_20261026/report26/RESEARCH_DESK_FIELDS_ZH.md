# 研究台接入：人数曲线抽样精度追加

主键沿用已有 `pool_id`、`image` / `image_id`、`reference_id` / `reference_version`、`team_key`、`member_workers`、`member_object_ids`。本轮版本为 `population_wholecurve_precision_20261026`，来源提交为 `b9bcec809fbaec8ab055931a1abb7baa5db44dac`。

## 展示层级和数量

| 层级 | 键／字段 | 页面含义 |
|---|---|---|
| 人员池 | `pool_id, pool_n` | 一张图已有合格标注者集合及其实际容量，不是新增人员 |
| 人数点 | `k` | 当次团队成员数 |
| 独立进入顺序 | `path_id, stratum, new_index, seed` | 一次完整排列；不同 k 共用同一条路径 |
| 前缀出现 | `path_id,k,team_key` | 真实抽样次数；重复 team_key 不能删除其出现权重 |
| 精确端点 | `team_key` | 同一团队的冻结结果，缓存命中不重复融合 |
| 比较版本 | `cohort` | `old48`、`stage1_104`（A104）、`stage2_104`（B104）、`new208`、`pooled152`、`pooled256`；旧重点池`prior96` / `all_history304`单列 |
| 进入策略配对 | `base_path_id` | 原自然顺序与四种历史优先策略的共同基础，不与自然256条混成一个样本数 |

自然结果里的 R 是路径抽样量，k 是团队人数，N 是池内人数。显示“256条”时不要写成“256名标注者”。相同满员团队出现256次也仍只有一个唯一成员集合。

所有`seed`与`*_seed`字段按十进制字符串或无符号64位整数读取，不能先转浮点数。`stratum`是底层批次，如`old24`、`prior_new24`、`new104A`、`new104B`；`cohort`是分析中的批次组合，二者不能混成一个连接键。

## 自然主结果

`analysis_precision26/results_stage2/NATURAL_CURVES.csv.gz` 的键是 `pool_id,cohort,k`。

| 字段 | 解释 |
|---|---|
| `paths_attempted, quality_valid_paths, unique_teams` | 三个分母分别保留：路径次数、正式Q有效次数、不同团队数 |
| `Q_mean, D10_mean` | 可评分团队条件下的平均质量；缺Q没有填零 |
| `Q_sd_ddof1` | 同人数随机换成员产生的质量波动估计，单位Q分 |
| `Q_mean_MCSE_analytic` | 对该均值估计的Monte Carlo标准误；不是人员质量波动本身 |
| `Q_p10` | 沿用原样本linear P10；不等同于平均质量或置信界 |
| `Q_p10_inverse_cdf` | 同一抽样频率下的经验逆CDF P10，保留离散跳变 |
| `Q_p10_boot_low/high` | 对样本linear P10的整路径重抽逐点经验区间 |
| `P10_order_low/high` | 总体逆CDF P10的二项秩区间；与上项目标、依据不同 |
| `P10_curve_Bonferroni_low/high` | 对声明合法k范围的保守同时秩区间 |
| `fullN_single_known_team` | 满员只有一支固定团队；若指标有效，真实换队波动为零 |
| `empirical_constant_Q_nonfull` | 当前样本观察到同一分数；未穷尽时不能据此宣布不存在未见模式 |

`NATURAL_INTERVALS` 同时保存边际质量差与路径配对差：

- `marginal_Q_delta` 是同图两个 k 的各自条件均值之差。
- `paired_Q_delta` 只用同一路径两个端点都可评分的支持。
- `Q_p10_delta` 是两个条件分布P10之差，不是“逐路径改善量的P10”。
- 各差值分别给路径有效量、图片／建筑支持，不能互相替换。

主展示采用固定 N≥30 的157个普通Manual候选池；N≥35为92候选池，实际均N35。门洞17池单列；小池和所有可用图片另有逐图表。全程固定可评图片可能少于容量候选数，尤其是满员失败图。`FIXED_IMAGE_AGGREGATE_CURVE_BANDS` 保存 `capacity_images`、实际 `images/buildings`、排除池和可估人数范围。失败面板仍按全部对应实际尝试显示。

## 执行状态与失败

优先显示原 `score_status` 和新增显式状态。下列量不得合成一个“缺失率”：

1. `actual_consensus_failure_rate`：共识形成异常、节点不足或未连接。
2. `output_unscoreable_rate`：已有候选，但正式几何或测量不可评分。
3. `reference_unavailable_rate`：参考不具备相应评分资格。
4. `not_executed_rate`：尚未执行。
5. `policy_deferred`：冻结规则下的两人暂缓，与“优先策略”不是同一概念。

为衔接旧表保留的 `failure_rate` 是更宽的非延期不可评分总率，不能直接改名为“共识失败率”。缺Q保持NA；失败、未知和暂缓都不变成0分。共识形成失败与输出不可评率使用实际执行、非延期支持，参考及执行缺口有自己的计数。

## 精确有限边际与随机整路径

`HYBRID_POOLED256_DISPLAY_CURVES.csv.gz` 供当前主展示引用：有完整团队目录的单人、缺一人、满员和小池点，可直接显示已知均匀团队结果，其余点使用随机256。

必须同时显示每个点的 `exact_kind`／估计来源，并保留原纯路径表。精确目录的团队等权与抽样路径的出现频率加权是不同输入。目录linear P10和总体逆CDF P10亦分别保留。混合来源的展示曲线不能用于恢复一次真实进入过程；路径配对问题继续读取精确 `path_id,k`。

## 几何与质量分项

几何V是两个独立均匀团队输出之间的平均几何差异，以各几何量的可用支持为条件；同队重复出现产生零距离，但保留抽样权重。它不是与GT的距离。满员V=0由团队唯一性决定，不意味着准确。节点数、必要转折、位置、面积、方向和高度仍分别读取。

命名的 B8 / D10 分项由 `engine26/derive_frozen_blocks.py` 补齐已有raw量，保留原Q和状态。`B8_floor_block`、`B8_direction_block`、`B8_global_height_block`、`B8_local_height_block`、`B8_height_block`、`D10_direction_block` 均是无量纲损失，低好；不是百分比贡献，不能加总成“解释了多少Q”。`dir` 和 `S_bottom_deg` 为角度误差，单位度。

## 区间和权重的界面文案

- “路径抽样范围”：固定当前图片，重抽完整进入顺序，反映组队模拟精度。
- “建筑重抽范围”：固定当前单图估计，按整栋建筑重抽，反映建筑间差异。
- “图片等权”：强调当前观察图片集合。
- “建筑等权”：每栋楼总权重相同，强调不同建筑的表现。
- “条件经验区间”：某些重抽不能覆盖固定支持，只对可估重抽报告范围；同时显示有效／总重抽次数。

不能把2000次bootstrap写成2000条新增人员顺序，也不能把路径区间很窄写成已经证明跨建筑普遍成立。界面应首先显示效应大小、图片数、建筑数和反向数，然后提供区间。

## 历史策略

策略主表位于 `analysis_policy26/results/`，版本为old16、new16、pooled32。标签来自历史 V3_BEHAVIOR / V3_JOINT_QT 的相应楼外角色：联合高Q、较多转折、联合快速、人数最多结构类（旧图称结构主流表达）。它们不能改名为新 DSTRUCT / RFUSE 的验证结果。

自然和策略在同一 `base_path_id` 上配对。阶段平均使用相同固定k，缺点不自动跳过。Q/T联合结果用两端Q可评、完整正值且同一种语义的劳动来源；`labor_ratio_legal` 是逐合法配对路径比值的均值，不是总费用或实际交付时间比。分项恢复后的共同支持单列于 `restored_components/`，主Q、D10和时间结果没有因此改算评分。

## 文件定位

全部新几何可由标量中的 `geometry_state_pointer` 定位到 `new_endpoints26/stage{1,2}/parts/<pool_id>/part_*.geometry_compact.jsonl.gz#L行号`。optional `full_state_pointer` 为空只表示没有按预定保存规则保留完整内部状态，不表示端点失败。

研究台可以按 `team_key` 复用旧main端点与本轮新增分片。复用依赖、输入hash、参考和原答成员见 `design26/dependencies_by_pool/`。本轮最终分片索引与完整性回执会核对计划、实际完成和所需几何键；未完成结果不会由平滑曲线或零分填出。

### 物理文件与逻辑表

|用途|权威位置／连接方式|
|---|---|
|完整精确设计|S01的`design26/orders_by_pool/`、`links_by_pool/stage{1,2}/`、`requests_by_pool/stage{1,2}/`、`dependencies_by_pool/`；全量顺序另有`NEW_EXACT_ORDER_DESIGN.csv.gz`|
|新增标量及几何|DATA_S1/S2的逐池`part_*.scalars.csv.gz`与同名`geometry_compact.jsonl.gz`；后一文件行号从1开始，不含表头|
|完整分片索引|S11的`new_endpoints26/COMPLETE_NEW_ENDPOINT_SHARD_INDEX.csv.gz`：`scalar_file`、`geometry_file`、`rows`、SHA；路径相对本轮研究根|
|可选单文件标量|`engine26/assemble_scalar_table.py`可重建`new_endpoints26/NEW_ENDPOINT_SCALARS.csv.gz`；未生成该物理文件不代表DATA分片缺数据|
|路径数值工作表|`new_endpoints26/stage{1,2}/prefix_values/<pool_id>.csv.gz`由精确前缀与端点重建；最终不重复打包这一缓存|
|旧端点|以`dependencies_by_pool`中的`endpoint_source`及`source_table`定位指定main及恢复缓存；不要求DATA包含其重复副本|

`geometry_state_pointer`中的`#L行号`是解压后JSONL的行号。先用对应标量片及`team_key`验证，再定位几何；失败端点仍有保存行与明确状态，不能仅以“有几何对象”推定可评。无需把所有压缩片拼接后才能逐队接入。

### 图表及全部尝试达标率

自然图的`F01_SOURCE_ROWS.csv`至`F04_SOURCE_ROWS.csv`位于`analysis_precision26/figures_stage2/`，历史策略原图的`P01_SOURCE_ROWS.csv`位于`analysis_policy26/presentation/`。报告新增策略图的36行源表为`report26/figures/P02_policy32_Q_labor_support_SOURCE.csv`；图中的Q全157图与Q/T各策略支持不可互换。几何图直接读取`analysis_geometry26/results_stage2/GEOMETRY_STRICT_COMMON_CURVE_SUMMARY.csv.gz`，其字段和筛选条件由`render_geometry_results.py`保存；不需要从图像反推数据。

`analysis_reporting26/thresholds/`的`Q80_Q90_PER_IMAGE_K.csv.gz`、`Q80_Q90_PAIRED_INTERVALS.csv.gz`及固定支持汇总使用“可评且达到阈值”的全部实际尝试事件率；未评分不是Q=0。人数差按同一路径配对，解析路径MCSE与建筑重抽区间各自保留。最终报告关键小表位于`report26/key_tables/`，其源表路径、原英文字段和中文映射足以链接回这些正式表。
