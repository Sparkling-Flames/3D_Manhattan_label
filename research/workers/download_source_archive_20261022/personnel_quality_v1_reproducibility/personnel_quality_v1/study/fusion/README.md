# 数据 v1：人员构成与共识过程的可复现分析

主要阅读入口是 [REPORT.md](REPORT.md)。两张科学图为 [真实前缀](figure_1_true_prefixes.png) 和 [固定构成／具体成员替换](figure_2_composition_and_replacement.png)，同时提供同名 SVG 矢量版本。所有质量仍使用冻结 B8L2 主线和 D10 敏感性；代码不修改仓库数据、参考或几何评分。

## 运行范围与状态

- 数据释放：v1。历史目录名中的旧脚本／文件版本号不是本任务的数据 v2。
- 固定仓库提交：`c4dd8266c42a478c68b0dce8097c98e33e4b32b2`。
- 主面板：7 图、6 建筑、每图 24 名已准入实际人员；楼外 Q/T 标签由目标整栋建筑排除后的折提供。
- 已有资产复现：7,320 原轨迹行中主比较 4,032 尝试，3,578 成功、168 个 k=2 暂缓、286 其他不完整；独立重融 14 个既有前缀核对结构。
- 新增 stage 2：4 策略 × 7 图 × 12 显式排列 × 8 前缀＝2,688 尝试；2,167 个新子集重融；2,264 成功、336 个 k=2 暂缓、88 其他不完整。
- 两阶段分别记录 [RUN_RECEIPT.json](RUN_RECEIPT.json) 和 [stage2/RUN_RECEIPT.json](stage2/RUN_RECEIPT.json)。保存值来自真实运行，不是预计运行计划。
- 根目录不变、只有默认输出目录和环境变量配置属于运行路径约定；运行代码后不会提交、推送或修改源仓库。

## 环境与依赖

实际 Python 为 3.12.14。依赖锁定见 [requirements.txt](requirements.txt)：numpy 2.3.5、pandas 2.2.3、scipy 1.17.0、Shapely 2.1.2、matplotlib 3.10.8、Pillow 12.3.0。原运行的 Shapely 安装在工作区 `runtime_deps`，脚本会优先加入这个可选目录；在别的机器按 requirements 正常安装即可，不依赖该目录存在。

```bash
python -m venv /path/to/venv
/path/to/venv/bin/python -m pip install -r /path/to/fusion/requirements.txt
```

脚本默认寻找 `fusion` 文件夹上两级目录下的 `repo`，默认输出为代码所在 `fusion` 目录。推荐显式设置下述两个环境变量，以便复制到任意位置运行。路径可包含空格，使用 shell 引号。

```bash
WORKER_PROFILE_REPO="/path/to/3D_Manhattan_label" WORKER_PROFILE_OUTPUT="/path/to/new-results" /path/to/venv/bin/python "/path/to/fusion/analyze_fusion_profiles.py"
WORKER_PROFILE_REPO="/path/to/3D_Manhattan_label" WORKER_PROFILE_OUTPUT="/path/to/new-results" /path/to/venv/bin/python "/path/to/fusion/replay_registered_compositions.py"
WORKER_PROFILE_OUTPUT="/path/to/new-results" /path/to/venv/bin/python "/path/to/fusion/prepare_readable_outputs.py"
```

三步依次执行。第一步建立所有复现及基底表，第二步生成新实验，第三步仅读取结果生成覆盖表、事件汇总及图。使用一个新的结果目录保留本次交付证据；同目录重跑会覆盖该目录下相应输出。实际本轮第一步约 33 秒、第二步约 106 秒，环境不同不保证同耗时。绘图使用 Agg 后端，缓存目录默认 `/tmp/worker-profile-matplotlib`，不需要显示器或浏览器。

`REGISTRATION.json`、`STAGE2_REGISTRATION.json` 始终从代码所在目录读取，故复制三个 Python 文件时应一起复制两份登记文件。第三步还使用第一份登记的主图顺序。README／报告可以直接阅读，重跑不需要联网或重新获取本轮新采集。

## 仓库输入与 LFS

需要对应提交中的实际文件内容，不是 Git LFS 指针。特别是评分引擎档案必须能作为 ZIP 打开：

- `research/quality/quality_joint_closeout_review_20261015/pro_closeout_delta.zip`（本轮实际 43,333,390 字节）。
- `research/quality/quality_ab_feedback_handoff_20261015/prior_AB/src/working_models.py`。

本模块调用 `scope_quality_scoring_20261016.scoring_engine()` 默认冻结档案，不使用缺失的 `research/statistics/b8l2_shared_v6_20261016/inputs/measurement_engine.zip`。这是同一冻结测量来源；已有 7 图旧状态的 B8L2 与 D10 数值重测已验证对齐。没有要求完整重跑仓库所有数据预处理模块。

其他直接输入：

| 仓库目录 | 文件／作用 |
|---|---|
| `research/workers/worker_b8l2_d10_20261017` | `fold_profiles.csv`、`team_scores.csv`、`personnel_ledger.csv`、`fixed_base_entrants.csv`、`replacement_pairs.csv` |
| `research/fusion/wall_consensus_d10_20261017` | `trajectory_scores.csv`、`subset_scores.csv`、`member_bridge.csv` |
| `research/fusion/wall_consensus_population_20261014` | `input_snapshot.json`、主图 `states/*.json.gz`，包含真实原答和显式完整排列 |
| `research/fusion/wall_consensus_b8l2_20261016` | `input_snapshot.json`，提供冻结指定参考 |
| `research/workers/worker_wq_integration_20261015` | `cached_team_scores.csv`、`new_states/*.json.gz`，复用先前准入子集 |
| `research/same_room/same_room_update_20261017` | `actual_18_curve_relation_coverage.csv`，审查可用同房间曲线 |
| `tools/thesis_main/analysis` | 原有融合、状态汇总、身份变化、冻结测量及模型代码；本模块直接调用 |

主表来源 SHA256 与文件大小见第一个运行回执；[ENVIRONMENT.json](ENVIRONMENT.json)补充依赖、几何参数和代码／引擎哈希。`inputs` 是仓库下载尚未完成时的准确读取缓存，25 份文件已逐文件哈希核对当前 repo，见 [CACHE_REPO_PARITY_RECEIPT.json](CACHE_REPO_PARITY_RECEIPT.json)；正式三个脚本均直接从指定 repo 读取，不依赖缓存目录。它不是新增标注，打包时可省去这份 43 MB 重复缓存。

## 冻结方法参数

融合复用仓库 `wall_consensus_population_20261014` 中原有规则：`WORKING_GAP=7.5`、MV50、全当前成员坐标中位数和原环连接政策；k=2 暂缓，少于四个节点或几何无效保留不可评分。人员加入的真实子集仅包含当前前缀，未来成员或 GT 不进入选择。

B8L2 参数版本 `WQ-B8L2-20261015`，方向尺度 8°、pooling order 2；D10 只替换方向尺度为 10°、版本 `B8L2-D10-20261016`。完整模型字段保存在环境回执。两个版本始终同几何、同指定参考、同完整性掩码；不自选参考、不重拟评分。

主分类是目标建筑外 B8L2 Q 的零点：正数为 high；现有值中没有精确零点，代码将有限且非正数归 low；不支持者 unknown。T 为相对 log active time 效应，负数 fast、非负数 slow，不支持者 unknown。±2 分三分法仅为登记的边界诊断，保留 boundary，不能称置信分类。D10 分类仅在已有对照表中作为敏感性，不用来重挑 stage 2 成员。

stage 2 seed=20261017，H=8，每图策略 12 条固定顺序。每次先生成一次全 24 人的均匀排列，8 高／8 低取其对应类别前八，随机取其前八；混合取两类各前四再独立打乱八人顺序。输入顺序固定为登记的 7 图，人员别名先排序。`PERMUTATIONS.csv` 在第一份新几何前写盘，运行后断言字节未改变。

无需追求复现相同的 CSV 浮点最后一位以外的机器误差；原几何重融离散结构严格核对，浮点容差 10⁻¹⁰；原评分重测允许 10⁻⁸；原 R 一致性容差 10⁻¹²。过程下降计数用 ΔQ < −10⁻⁹ 的纯数值容差，几何非零为 >10⁻¹²，未设置按结果调节的“实质变化”分界。

## 输出索引

### 已有结果复现与固定共同成员设计

| 文件 | 内容 |
|---|---|
| `out_of_building_member_profiles.csv` | 168 个图×人员的准入作答、楼外 Q/T、类别、支持、工时桥接 |
| `primary_true_path_states.csv` | 全部 4,032 旧主图实际前缀，含质量、失败、构成、R、工时缺失 |
| `primary_panel_coverage.csv` | 每图分母、失败、时间覆盖和全员终点 |
| `frozen_teams_enriched.csv` | 399 个冻结主团队及画像 |
| `feasible_compositions.csv` | 129,593 个组合容量内的可行类别向量；是枚举，不是 129,593 次实验 |
| `composition_coverage.csv` | 已有路径覆盖哪些可行构成、哪些未观察到 |
| `path_selection_manifest.csv` | 以楼外 Q 前八人均值固定选出的原有路径及其原始次序 |
| `path_policy_*.csv`、`path_matched_changes.csv` | 原有真路径短名单诊断及配对覆盖 |
| `true_prefix_transitions.csv` | 原有全 k 真路径的相邻变化 |
| `fixed_base_entrants_enriched.csv` | 14 七人基底 × 17 实际候选，完整保留 238 次机会 |
| `fixed_base_class_contrasts.csv` | 基底内质量、完整性、R、工时及时间联合可见子集对比 |
| `fixed_base_contrast_summary_with_coverage.csv` | 每终点的基底／图／建筑、人员机会、质量和工时已知分母 |
| `fixed_base_entrant_class_coverage.csv` | QT 各类具体人员数和加入机会、成功、工时覆盖 |
| `replacement_pairs_enriched.csv` | 2,597 主比较替换对，同类／跨类／未知与结果 |
| `replacement_7plus1_coverage.csv` | 固定 7+1 的 1,904 替换对类别及完整几何覆盖 |
| `replacement_7plus1_by_building.csv`、`replacement_7plus1_summary.csv` | 同构成换具体人、跨构成换人的六建筑等权结果 |
| `same_k_geometry_pairs.csv` | 46,368 对旧路径同 k 输出，保留共享成员及失败 |
| `independent_prefix_replay_checks.csv` | 14 个已有前缀独立重融核查 |
| `RUN_RECEIPT.json`、`run_stdout.log` | 已有资产复现的实际回执／stdout |

### 新增 stage 2

| 文件（位于 `stage2/`） | 内容 |
|---|---|
| `PERMUTATIONS.csv` | 336 个先于新融合保存的真人顺序，含当前 W 身份、旧 P 别名、object id 与源池大小 |
| `path_states.csv` | 2,688 个逐前缀状态，完整保留成功／k2／其他失败、Q、R、成员及工时缺失 |
| `states/*.json.gz` | 7 图全部已用唯一子集的真实融合几何、参考和顺序 |
| `score_parity_checks.csv` | 7 图旧状态 B8L2/D10 冻结重测 |
| `same_k_pairs.csv` | 14,784 对，包含共享人数、完全相同子集、双方是否完整 |
| `prefix_transitions.csv` | 2,352 个全部真实相邻前缀，包含政策过渡 |
| `strategy_by_image_k.csv` | 每图／策略／k 的尝试数、有效数、质量／完整率／R／V／工时 |
| `paired_strategy_differences_by_image.csv`、`paired_strategy_differences_by_building.csv`、`paired_strategy_summary.csv` | 同图固定 k 配对，再按建筑等权；每终点独立覆盖与留一楼范围 |
| `endpoint_strategy_summary.csv` | k8 终点的成功数、可比全员工时数与建筑等权结果 |
| `exact_expected_raw_R.csv` | 全部原答对的精确 R 抽样期望，k2…8 理论常数 |
| `V_by_overlap.csv` | V 与共享成员数量、有效对数，保留有限池效应 |
| `matched_true_path_intervals.csv` | 同一真人路径 k3→4、4→8、3→8 的可比端点变化 |
| `transition_event_counts.csv` | 排除 k2 政策过渡后的事件和适当机会分母 |
| `negative_step_examples.csv` | 事后最大的三个下降见证，明确标为诊断，未用于调类 |
| `RUN_RECEIPT.json` | 新重融数、缓存命中、评分调用、成功／失败、顺序 SHA256 |

所有 CSV 使用 UTF-8 BOM；缺失数值为空，bool 为显式真／假。字段解释以 [FIELD_CONTRACT.json](FIELD_CONTRACT.json) 为准。任何全局计算平均数都不能忽略报告所用的“先图／基底、再建筑”层级。

## 可读审计与有限修订记录

已完成的边界检查包含：目标整楼排除；当前人员且不泄漏未来成员；已准入 object_id 精确绑定；所有旧真实前缀；固定7+1所有可用候选；B8L2/D10共同缺失；k2不赋假分；全员有限池共同终点；相同子集 V=0 的数值恒等；不完整代价保留；实际时间全员覆盖才能给总成本；新排列 SHA256 在计算后不变。独立 Q 模块又核对 stage 2 336 排列、2,688 前缀、2,283 保存几何成员及 200 项分层聚合，其回执在完整交付的 `../q/STAGE2_SCOPE_AUDIT_RECEIPT.json`。

首次 14 前缀审计曾用严格浮点字符串相等而因约 10⁻¹⁶ 数值差失败；随后明确改为 10⁻¹⁰ 浮点容差并严格保留离散结构一致要求。原失败日志 `run_attempt_before_numeric_tolerance.log` 保留。它不代表标注成员、几何拓扑或评分变化。

主要结果跑完后，仅为可移植性加入环境变量配置、补充从原答对直接求精确 R 期望、把 receipt 中容易误读的 `new_unique_measurements` 改为 `new_unique_score_evaluations`，并增补覆盖／事件字段及科学图。旧 stdout 保留初始字段名，现 receipt 明确该计数包括不可评分返回，未宣称 1,864 次均是完整测量。没有更换登记中的类别、抽样、几何或参考。`PORTABILITY_SMOKE_RECEIPT.json` 是路径配置、代码编译和依赖验证，不冒充一次新的完整几何重跑。

研究的独立组数仍然只有六建筑；数据来自共同人员有限池，算法与图选择也并非本次完全未知的新测试。新阶段是开发性补充，用于填补纯构成覆盖并说明过程，不证明永久人群、无条件部署最优策略、同类人员等价、总体严重错误率或全策略成本曲线。
