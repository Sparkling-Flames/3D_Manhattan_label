# 自然256条与历史策略32条：新来源归档和读取入口

2026-10-27。本目录按原包路径保存 S01、S10、S11 与14个 DATA 包的完整有用材料。研究采用与独立重算范围见[256条独立审查](../../../statistics/pro_return_review_20261023/population256_20261027/README.md)；这里负责来源、读取和复现，不另做融合、评分或分类。

## 当前采用与历史边界

- 普通Manual和门洞自然人数采用旧48＋独立新208＝**256条**，新增分A104、B104；不是新增256名人员。194池中普通177、门洞17，保留各自质量、几何、状态与实际支持。
- 已知完整有限团队目录的单人、缺一人、满员和小池点，采用**精确有限边际**；`natural_display`给出精确/随机混合来源，`natural_curves`保留纯路径结果。不能用混合曲线恢复真实路径配对。
- 历史四种优先进入策略采用旧16＋新16＝**32条配对基础顺序**，保持V3_BEHAVIOR/V3_JOINT_QT角色；不是DSTRUCT/RFUSE策略验证，也不是256条策略。
- 53个旧重点池的96/304仅是敏感性；Semi没有追加。旧24/48来源、参考、资格、OOS及原实验身份不变。

## 可直接读取的接口

[DATA_ACCESS.json](DATA_ACCESS.json)登记21个表别名、仓库相对路径、必需字段及默认版本；[read_saved.py](read_saved.py)只读取保存值。CSV/gzip按UTF-8 BOM相容方式读入，所有单元保持字符串，空值不补零，64位seed不先经浮点数。

|用途／别名|文件|默认读取范围|
|---|---|---|
|`natural_display`|[精确＋256主展示](analysis_precision26/results_stage2/HYBRID_POOLED256_DISPLAY_CURVES.csv.gz)|6,290行；每点保留`exact_kind/estimator`及纯路径对照|
|`natural_curves`|[纯自然逐池人数](analysis_precision26/results_stage2/NATURAL_CURVES.csv.gz)|`cohort=pooled256`，6,290行；原表41,252行保留各历史批次|
|`natural_fixed_bands`|[固定图片曲线与两类范围](analysis_precision26/results_stage2/FIXED_IMAGE_AGGREGATE_CURVE_BANDS.csv.gz)|合256；`panel/layer/difficulty/weighting/uncertainty`共同筛选，容量与实际有效数分列|
|`natural_summary`、`natural_interval_summary`|`COMMON_SUPPORT_*_SUMMARY.csv.gz`|合256；保持指标各自图片/建筑支持及正负图数|
|`natural_intervals`、`natural_components`|`NATURAL_INTERVALS/COMPONENTS.csv.gz`|合256；边际变化与双端可评路径差分开|
|`natural_status`|[逐点状态](analysis_precision26/results_stage2/NATURAL_STATUS.csv.gz)|合256；7,487条状态行，不与6,290个点混算|
|`geometry_curves`、`geometry_intervals`|`analysis_geometry26/results_stage2/GEOMETRY_FIXED_SUPPORT_*.csv.gz`|合256，独立几何支持|
|`policy_image_k`、`policy_phase`、`policy_summary`、`policy_support`|`analysis_policy26/results/`下同名表|`version=pooled32`，保留策略角色和合法Q/T支持|
|`policy_events`|[全部精确配对事件](analysis_policy26/results/EXACT_PAIRED_EVENTS.csv.gz)|672,512行：old16与new16各336,256行；合32是并集，无第三份重复事件|
|`orders`、`pool_plan`、`endpoint_shards`|[设计](design26/)、[新增片索引](new_endpoints26/COMPLETE_NEW_ENDPOINT_SHARD_INDEX.csv.gz)|50,400条新自然/策略顺序、194池、5,914个标量片|
|`exact_marginals`、`exact_p10`、`exact_values`|旧`sampling_precision_20261025`精确目录|直接复用原位置，未复制；分别613、613、14,904行|

完整字段与界面解释见作者最终版[RESEARCH_DESK_FIELDS_ZH.md](report26/RESEARCH_DESK_FIELDS_ZH.md)和[引擎字段合同](engine26/FIELD_CONTRACT.json)。`rows(alias)`应用默认版本；`rows(alias, defaults=False)`才取全部历史/敏感性。`table_path(alias)`只定位原文件，不自动筛版本。

失败与支持：`actual_consensus_failure_*`、`output_unscoreable_*`、`reference_unavailable_*`、`not_executed_*`及两人延期分别保留。较宽的历史`failure_rate`不能直接改名为共识形成失败率。质量按可评分团队条件平均；实际失败率按已执行非延期尝试，不能把缺Q填零。固定图片容量、实际有效图数、路径数、唯一团队数及建筑数各有职责。

## 端点、原始几何及旧数据复用

- S01：`design26/orders_by_pool`、`links_by_pool/stage1/2`、`requests_by_pool/stage1/2`、`dependencies_by_pool`保存精确成员和关联；自然新顺序40,352条、策略10,048条，新前缀1,644,576次。
- DATA：`new_endpoints26/stage1/2/parts/<pool_id>/`保存新增标量、紧凑几何、按规则保留的完整状态及回执。5,914片共1,356,657个新端点；另39,852支团队复用旧端点。完整状态缺省不等于融合失败。
- `read_saved.endpoints(pool_id, stage=1或2)`按现有片索引流式读新标量；`geometry(scalar)`按`#L`一基行号读保存几何，并核对团队、池和参考身份。不会重新生成几何，也不把有几何对象等同于质量合格。
- [REUSED_INPUTS.json](REUSED_INPUTS.json)把作者逻辑缓存定位到现有母人数表、旧精度包及其原生逻辑分片。旧表、输入、参考和精确目录均不再复制；`prefix_values`及可选整表缓存没有重复物化，不表示收到的DATA缺端点。

## 包来源及版本优先级

[LOCAL_SOURCE_FILES.csv](LOCAL_SOURCE_FILES.csv)逐包逐成员登记来源包名、包内路径、仓库路径、字节数和采用状态；不在公开定位表写入下载目录路径。[归档回执](SOURCE_ARCHIVE_RECEIPT.json)记17包、24,140个来源成员记录、24,127个唯一源文件路径：13个相同重复来源合并，2个不同早期版本另存。

S10是最终代码/说明优先版本。S01被替代的`engine26/README_ENGINE_ZH.md`与`delivery26/package_and_verify.py`留在`source_original/overridden/HOHONET_20261026_S01_exact_design/`；作者原README保留于[source_original/S10/README.md](source_original/S10/README.md)，本页是新增本地入口。来源文件不等于本地新验证；作者回执与独立审查继续分开。

最大单文件47,240,992字节，低于既有64MiB分块阈值；DATA本身已经分片，按原路径保留。未另造新的大表或分块框架。旧母人数原字节分块及旧精度逻辑分片仍使用各自原清单/恢复器，详见[母人数入口](../README.md)。

## 复现、核验与未做项

最短命令和Python示例见[REPRODUCE.md](REPRODUCE.md)。本地读取检查见[READ_ACCESS_CHECK.json](READ_ACCESS_CHECK.json)：24,140条来源记录逐项文件大小核对；21接口CSV/gzip共1,945,644行完整读至EOF；5,914片路径与两阶段端点数闭合；六个标量—几何指针读回并核身份；旧19个逻辑片仍在原位。三个定向测试通过，覆盖BOM/精确seed/缺失、默认版本、未知字段、行宽及指针身份/边界。

作者`assemble_key_tables.py --check-only`在本地通过15个输入表头和完成回执检查，写文件数0。没有运行其重建主表流程（包含额外SHA）、作者引擎、百万级融合、评分、分类、几何距离或bootstrap。作者完整代码保留，不宣称Windows已重跑其全部分析。

本线程只改本来源目录、母人数README和catalog机器登记/生成；原下载和旧24/48来源未删，未推送/部署。已检查项目地图/文档索引：仍沿用现有人数与审查父专题入口，由母README和catalog引入本次追加，不修改其他线程负责的主文、模型或研究台。临时Python缓存已清理。
