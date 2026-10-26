# 最终交付复算与接入补记

本次仅核对现有代码入口、实际字段和最终选包依赖；没有运行融合、重抽或统计模型。S05已保存的ZIP及其读回记录保持原件身份，当前文档和代码由最终S10覆盖接续。S10/S11是否已经形成可下载成品，以统一有效文件清单及其实际ZIP读回回执为准，本说明不替代交付回执。

## 已修正的实际接入问题

|问题|修正|
|---|---|
|命令中`STUDY`、`REPO`曾作为字面参数，且未交代运行目录|`REPRODUCE.md`给出绝对路径变量、`cd "$STUDY"`及带引号的Shell变量；几何分析的`--root`单独指向`analysis_geometry26/`|
|只给了自然、策略主分析，没有接上当前分项与策略展示入口|补全`refresh_components.py`、重新合并、`restore_named_loss_components.py`及`report_policy_precision.py`；重新导出小表／画图与较长路径重算分开|
|字段说明以A104/B104描述批次，容易被当作实际`cohort`值|改为`stage1_104`／`stage2_104`，保留A104/B104中文说明；同时区分底层`stratum`与分析`cohort`|
|策略证据提取原来只读stage0元数据，而S11只交付最终stage2|`extract_policy32_evidence.py`优先读取stage2的池元数据，仅早期快照回退stage0；不读取Q来选池，不改变157集合和148交集定义。既有S05结果文件未重新导出|
|Q80/Q90阈值结果目录未在S11选择中|将`analysis_reporting26/thresholds/`加入S11；该分支保留全部尝试事件率、同路径配对解析MCSE及建筑范围，不新增融合|
|报告图目录递归选择可能带入绘图缓存|最终选择排除绘图字体缓存；保留PNG/PDF/SVG、实际SOURCE表、图注及绘图代码|
|当前根分析编排代码未随S10选择|加入`delivery26/finalize_root_analyses.py`；各分析目录根部`.py`仍自动纳入，新增全量读出脚本无需另外枚举|

## 交付组合与端点完整性

**只读报告或重画已存汇总图，使用S10/S11；从精确团队重新统计，使用S01、全部DATA_S1/S2、S10及固定main输入。** S02／有限目录／原图案例包按所研究案例另取。最后解压S10；S00、S04和S05仍保留其阶段身份，不用早期代码覆盖当前版本。

S01已选入194池的完整精确顺序、388个阶段前缀表、376个非空新增请求表、194个缓存／新增依赖表及194个登记回执；没有新增请求的池阶段不能据“请求文件少于388”解释为缺设计，实际容量与请求数查`POOL_SAMPLING_PLAN.csv`。本次仅核对现有选择名单与相关表头，没有重算登记设计。

新端点权威数据是`new_endpoints26/stage{1,2}/parts/<pool_id>/part_*.scalars.csv.gz`及其同序几何。S11的`COMPLETE_NEW_ENDPOINT_SHARD_INDEX.csv.gz`提供每片路径、行数与SHA，S01的`dependencies_by_pool/`提供team_key、来源、成员与参考关联。旧端点按固定main读取，不因本轮DATA里没有副本判为缺失。

单个物理`new_endpoints26/NEW_ENDPOINT_SCALARS.csv.gz`是可选导出，使用`assemble_scalar_table.py --base "$STUDY"`生成。未生成此文件不等于逻辑标量表不完整；全部分片与最终实际完成回执才决定完整性。`geometry_state_pointer`的`#L`是解压后JSONL的1起始行号，需同时核team_key；失败、缺参考与暂缓保留原状态。

## 图表源数据够不够接入

已完成策略图有原六联图`P01_SOURCE_ROWS.csv`、报告三联图的36行`P02_policy32_Q_labor_support_SOURCE.csv`，以及完整逐图／阶段／版本表。最终自然图按绘图代码保存F01—F04的SOURCE表；最终几何图直接读取`GEOMETRY_STRICT_COMMON_CURVE_SUMMARY.csv.gz`，筛选条件在`render_geometry_results.py`。上述目录均在S10/S11选择范围内。报告目录F04—F07案例图及其来源表保持根任务已保存版本，本次未覆盖。

研究台既可从`report26/key_tables/`读取精简展示，也可按原英文字段下钻：自然`pool_id,cohort,k`，策略`pool_id,policy,version,phase/k`，精确端点`team_key`，真实前缀`path_id,k`。图表不是唯一数据入口，无需由折线反推结果。

本次验证限于文档所列脚本存在、命令选项与代码一致、关键选包目录／字段以及小范围文件结构；没有再次进行旧库全量审计，也没有以这份补记声称最终大ZIP已完成读回。
