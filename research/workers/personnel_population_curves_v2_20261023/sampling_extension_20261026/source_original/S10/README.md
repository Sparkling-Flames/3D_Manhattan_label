# HOHONET：人数曲线的完整随机顺序追加与抽样精度

本专题基于已有真人v2，保留原48条自然进入顺序，为194个Manual图片人员池各新增208条完整均匀随机顺序，研究人数曲线的均值、低尾、换组质量与几何波动、失败及历史进入策略的抽样精度。

**本轮新增端点、精确路径、自然精度、历史策略和几何汇总全部完成。14个DATA分片包已保存，并从实际取回的ZIP读取内部CSV、gzip及JSONL至结尾。** 最新科学结论统一采用综合报告；旧阶段包保留追溯身份，不能覆盖本轮最终表。

下载与采用状态见[当前统一交付入口](https://chatgpt.com/library?file_id=libfile_381dc032fac08191b4b8d1b28c16ac84&account_id=personal)。该入口保留固定真实身份，并只列实际保存和取回核验成功的文件。

仓库相对目录：

```text
research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/
```

## 先从这些入口阅读

|需要了解什么|入口|
|---|---|
|本轮综合发现、采用判断及新旧结论|[中文综合报告](REPORT_ZH.md)；[可独立阅读的HTML](report26/REPORT.html)|
|逐图、逐人数、难度分层及精度主表|[关键表说明](report26/KEY_TABLES_REPRODUCE_ZH.md)；[最终关键表目录](report26/key_tables/README_ZH.md)|
|研究问题、精确证据与采用关系|[中文主张索引](report26/CLAIMS_INDEX_ZH.csv)；[新旧结论对照](report26/OLD_NEW_CONCLUSIONS.csv)|
|如何恢复输入、重新分析或重跑端点|[复现说明](report26/REPRODUCE.md)；[依赖与交付补记](report26/DELIVERY_REPRO_NOTES_ZH.md)|
|研究台的键、状态、指标及图表源数据|[接入字段合同](report26/RESEARCH_DESK_FIELDS_ZH.md)；[冻结端点字段](engine26/FIELD_CONTRACT.json)|
|实际抽样设计、范围及输入版本|[冻结设计](FROZEN_EXTENSION_DESIGN.json)；[逐池计划](design26/POOL_SAMPLING_PLAN.csv)；[输入版本](INPUT_VERSION.json)|
|历史四策略旧16／新16／合32的完整子域|[策略32报告](report26/POLICY32_COMPLETED_FINDINGS_ZH.md)；[15张证据小表](report26/policy32_evidence/README_ZH.md)|

综合报告、主张索引和17张关键表均来自完成的全量结果。阅读阶段材料时仍按其实际支持解释，不将阶段完成标记追溯改写为全量结果。

## 1. 实际使用的版本与研究范围

源仓库为[3D_Manhattan_label](https://github.com/Sparkling-Flames/3D_Manhattan_label)，固定输入提交为：

```text
b9bcec809fbaec8ab055931a1abb7baa5db44dac
```

2026-10-26 15:11:51 UTC再次读取远端main，仍为上述提交，与登记输入一致；见[最终来源检查](FINAL_SOURCE_CHECK.json)。沿用真人v2的正式资格、参考、预处理、融合、B8L2和D10，不重新分类、不修改融合规则或GT。

|主研究层|人员池／图片|建筑|本轮自然追加|
|---|---:|---:|---|
|普通Manual|177|22|每池208条完整独立均匀随机顺序|
|门洞交界Manual|17|9|每池208条，单列分析|
|合计|194|建筑可能重叠，不把22与9相加|40,352条自然独立抽样|

普通固定N≥30的容量范围为157图；固定N≥35为92图，实际均为35人池。容量候选数与某项指标的实际可评图片数分开保留。本轮没有新增Semi顺序，Semi沿用此前实际版本。

自然主比较为旧48、独立新208、合256；新增分为两个预先固定的104条批次。53个旧重点池的额外48只作为`prior96`／`all_history304`敏感性，不能写成所有人员池都有304条。

历史四种优先进入策略沿用V3_BEHAVIOR／V3_JOINT_QT相应楼外角色，在157个原策略支持池中各追加16对基础顺序，比较旧16、新16、合32。它们不是新DSTRUCT或RFUSE策略验证，也不能把四种派生顺序算作四批独立自然抽样。

## 2. 已完成的真实执行规模

|登记与实际完成量|数量|含义|
|---|---:|---|
|新增独立自然顺序|40,352|194池×208；整条顺序内部无放回|
|新增派生策略顺序|10,048|157池×16个共同基础顺序×4个历史策略|
|新增自然／派生策略顺序记录|50,400|前两项合计，不等于50,400次独立自然抽样|
|前缀出现|1,644,576|同一团队重复出现仍保留抽样权重|
|登记去重团队|1,396,509|按精确成员集合复用冻结端点|
|复用已有端点|39,852|母人数研究23,252；前轮精度研究16,600|
|本轮新增端点结果记录|1,356,657|第一阶段784,140；第二阶段572,517，全部闭合|

执行依据为[完整运行账本](new_endpoints26/FINAL_EXECUTION_LEDGER.json)及[逐池账本](new_endpoints26/FINAL_POOL_EXECUTION_LEDGER.csv.gz)。[最终路径关联检查](delivery26/FINAL_PATH_LINK_VALIDATION.json)已经覆盖194池和全部1,644,576次前缀，核对登记顺序、前缀成员、team_key、实际进入者以及策略稳定优先分块；满员每图只指向一个唯一团队。

新增去重端点的保存状态如下：

|`endpoint_state`|新增结果记录数|
|---|---:|
|`scored`|1,293,037|
|`consensus_incomplete_below_four`|19,787|
|`consensus_not_connected`|14,345|
|`generated_geometry_unscorable`|734|
|`design_deferred_k2`|28,754|
|总计|1,356,657|

非延期新增记录为1,327,903。**这张表是去重运算账本，不是普通自然团队或策略团队的研究失败率。** 研究失败率按对应自然／策略路径、人数、图片和全部实际尝试计算；可评分Q、不完整、输出不可评和两人暂缓分别保留，缺Q不填零。新增端点均保存最终候选几何，完整内部身份状态仅按预定案例及hash子样本保留。

## 3. 怎样组合交付包

统一入口只列实际可取得文件及其真实下载身份、版本、SHA和读回状态。最终文件的解压及覆盖顺序为：

**S01完整设计 + 全部DATA_S1／DATA_S2 → S11完整分析结果 → 最后S10最新报告代码。**

|包|用途与采用关系|
|---|---|
|S10|当前综合报告、关键表、完整新代码和复现入口；最后解压，覆盖阶段代码|
|S11|最终逐图逐人数统计、策略、几何、精度、图表源数据与完整分片索引|
|S01|完整精确顺序、前缀、请求、缓存关联和登记回执；其中代码保留阶段身份|
|全部14个DATA包|完整新增端点标量、逐队最终候选几何及预定完整状态；不可仅取一片声称全量|
|S00／S04|计算前快照／计算中代码检查点，用于追溯，不覆盖S10|
|S05|四种历史策略16→32的完整独立阶段；原件保留，结果接入最终S10/S11|
|S02|六小池完整有限目录、真实顺序和独立复算；可单独阅读|
|FINITE_CASES|三个近满员有限目录的频数、两种P10、几何与精度校准|
|ORIGINAL_IMAGE_CASES|两张Release原图、原答／融合／参考叠加与局部票账|

只阅读报告、接入汇总或重画正式图，最少使用S10+S11；从精确路径重新统计则另加S01、全部DATA和固定main历史输入。小池及案例包按需要另取，不代替全量设计或端点。文件名、字节数、SHA和取回核验状态见统一下载入口。

ZIP内已包含本专题完整仓库相对路径，应解压到共同接收根目录，不要再在`sampling_extension_20261026/`下嵌套一层`research/`。旧main大表、原图全集、环境和可重建工作缓存不重复打包。

## 4. 精确数据怎样连接

|对象|位置与键|
|---|---|
|精确进入顺序|`design26/orders_by_pool/*.csv.gz`，键`path_id`；种子按十进制字符串或uint64读取|
|真实前缀出现|`design26/links_by_pool/stage{1,2}/*.csv.gz`，键`path_id,k`；重复team_key保留频数|
|来源与精确成员|`design26/dependencies_by_pool/*.csv.gz`，键`team_key`；保留原答object_id、人员、图片、参考及输入hash|
|新增标量|`new_endpoints26/stage{1,2}/parts/<pool_id>/part_*.scalars.csv.gz`|
|新增候选几何|同片`part_*.geometry_compact.jsonl.gz`；与标量的行数和team_key顺序一致|
|最终分片索引|[COMPLETE_NEW_ENDPOINT_SHARD_INDEX.csv.gz](new_endpoints26/COMPLETE_NEW_ENDPOINT_SHARD_INDEX.csv.gz)，记录物理路径、行数及SHA|
|正式自然统计|`analysis_precision26/results_stage2/`，主键`pool_id,cohort,k`；区间比较另保留成对人数与路径支持|
|正式策略统计|`analysis_policy26/results/`，键`pool_id,policy,version,phase/k`；精确配对保留`base_path_id`|
|正式几何统计|`analysis_geometry26/results_stage2/`，键`pool_id,cohort,k,metric`及成对人数区间|

`NEW_ENDPOINT_SCALARS.csv.gz`是可选单文件导出；权威数据是全部分片及其索引，没有这个重复大文件不表示标量缺失。旧端点从指定main来源读取，本轮不另存副本。`geometry_state_pointer`的`#L`指解压JSONL的1起始行号；是否可评以正式状态为准，不能仅凭存在候选对象判断。

## 5. 代码与复现入口

|工作|入口|
|---|---|
|映射指定main与恢复必要历史分片|[setup_from_main.py](engine26/setup_from_main.py)|
|登记设计和端点复用、冻结执行|[引擎说明](engine26/README_ENGINE_ZH.md)；[generate_registered_design.py](engine26/generate_registered_design.py)；[execute_extension.py](engine26/execute_extension.py)|
|恢复精确路径数值工作表|[prefix_outputs.py](engine26/prefix_outputs.py)|
|自然完整路径精度与汇总|[自然分析说明](analysis_precision26/README.md)；[analyze_natural.py](analysis_precision26/analyze_natural.py)；[summarize_natural.py](analysis_precision26/summarize_natural.py)|
|历史策略配对分析|[analyze_policy32.py](analysis_policy26/analyze_policy32.py)|
|几何波动、MCSE与建筑汇总|[几何合同](analysis_geometry26/METHOD_AND_FIELD_CONTRACT_ZH.md)；[geometry_extension.py](analysis_geometry26/geometry_extension.py)|
|Q80／Q90全部尝试达标率|[fixed_threshold_attainment.py](analysis_reporting26/fixed_threshold_attainment.py)，输出`analysis_reporting26/thresholds/`|
|只从正式结果整理报告主表|[assemble_key_tables.py](report26/assemble_key_tables.py)|
|最终分包与内部读回|[prepare_final_packages.py](delivery26/prepare_final_packages.py)；[package_and_verify.py](delivery26/package_and_verify.py)|

完整命令、输入分片、环境及字段解释见[REPRODUCE.md](report26/REPRODUCE.md)。读取保存结果、重做bootstrap和实际追加进入顺序是不同操作；bootstrap次数不计为新增路径。正式评分分项按既有raw量和冻结公式补齐，不改变Q、参考或端点。

## 6. 完成状态分层读取

端点与精确路径是否完成，读取运行账本及`FINAL_PATH_LINK_VALIDATION.json`；自然统计是否全194池完成，读取`analysis_precision26/results_stage2/NATURAL_FINALIZATION_COMPLETE.json`及对应分析、汇总回执；几何统计读取其`RUN_RECEIPT.json`和`SUMMARY_RECEIPT.json`。科学结论进入主报告前使用各自的实际固定支持。

最终交付采用S10时，统一入口会显式标明最新综合报告，并合并独立报告／小表的真实身份。入口脚本的`--final`要求S10/S11实际保存及下载读回、全部DATA记录合计1,356,657，以及独立附件核验完成；不以本地生成文件冒充已经可下载的附件。
