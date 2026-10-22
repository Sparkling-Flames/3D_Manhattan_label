# 人员混合构成与成员变化：本轮证据与文件入口

**状态：本轮目标已完成，2026-10-23本地独立核验并修复旧n20失败统计后，按当前真实支持范围采用。** 先读[本地验收与文件保存说明](LOCAL_ACCEPTANCE.md)，原作者内容与原表另存，当前旧n20表已修正。 实际读取 main 为 `ef148c82df18582228b2d23837faa2659e79eba7`，包含用户指定的 `ef148c82d`。底层真人 **v2**；历史包名 v3 是研究轮次。本轮新增0次原生融合、0次质量评分、0套标签，复用已保存的完整团队进行新的构成、同背景成员、方向和难度条件分析。

中文主报告继续更新既有文件：

[人员分类与构成不确定性：研究组织与比较清单](../../../docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md)

本目录负责证据、代码、来源与精确成员，不另起同义“最终报告”。全部比较保留，主文选择不代表删掉负向、失败或近零结果。

## 先读这几张表

| 用途 | 实际文件 | 内容 |
|---|---|---|
| 最终保留哪些方法 | [11家族选择与覆盖](integration/METHOD_SELECTION_AND_COVERAGE.csv) | 原身份、本轮采用、粗细增量、输入条件及其它方法未进主文理由 |
| 具体选什么方向/规模 | [中文有效换类条件](integration/有效换类条件表.csv) | 18个重点收益、代价、反向、条件及容量边界；n/m/r、图楼背景、分项、时间、风险 |
| 完整推荐指标与分母 | [推荐条件全字段](integration/RECOMMENDED_STRICT_CONDITIONS.csv) | 保留全部指标；共同QT与各自时间分母分开；难度行不复制总体端点分母 |
| 推荐条件具体是谁 | [逐楼外折、逐图成员](integration/RECOMMENDED_CONDITION_MEMBERS_BY_FOLD.csv) | 523条源/目标角色支持，实际X/Y/Z及D人员并集、变体数、训练中心差和精确事件入口 |
| 四套完整配比 | [Manual全部10,094格](configurations/CONFIGURATION_OVERVIEW_manual.csv.gz)、[Semi全部3,312格](configurations/CONFIGURATION_OVERVIEW_semi.csv.gz) | 每完整类别向量的团队数、失败、均值/分位数/离散度；46指标完整长表另存 |
| 全部定向对照 | [85严格ABC条件](exchanges/ALL_CONDITIONS.csv)、[共同QT](exchanges/COMMON_QT_CONDITIONS.csv)、[461直接AC条件](direct_ac/CONDITION_COMPARISON.csv) | 同类、跨类、净效应及失败；设计互不冒充 |
| 同配比与改配比 | [有限配对精选](exchanges/finite_pair_comparison/FINITE_PAIR_SELECTED_ZH.csv)、[完整说明](exchanges/finite_pair_comparison/README.md) | 全部m1–6/实际n/粗细层，以相同实际D/m对比变化幅度 |
| 难度为何改变结论 | [201条件×难度](difficulty/exchange_difficulty_core.csv)、[原答/难度说明](difficulty/README.md) | 原答结构机会、同类近Q快慢、简单/困难方向反转及全部分项 |
| 旧分类和大块 | [旧n20父内76条件](exchanges/legacy_n20/PARENT_FIXED_M_RESPONSE.csv)、[历史来源索引](exchanges/HISTORICAL_METHOD_COMPARISON_INDEX.csv) | 完整271,331旧事件已恢复；A2/M/QTD/SP/F01/Rnew2/跨条件保留 |

## 真实完成范围

| 单元 | 实际完成 | 身份 |
|---|---|---|
| 分类 | 四套主类的ALL及5,456行楼外标签；11家族及跨条件小输入 | 标签原样复用；不跨折直接拼类号 |
| 有限混合构成 | 336面板，每面板固定D、12选6的924队；310,464面板关联、310,458唯一团队；13,406方法/层级/配比格、616,676指标分布行 | 本轮新完整重汇总；所选有限空间全部枚举 |
| 严格ABC | 146,031登记行，138,244跨阶段去重物理ABC；85条件、130图22楼；100,530实际用到的端点 | 原101,092端点库存与请求复用；本轮全方向统一比较 |
| 有限成员配对 | 143,279,136个面板内无向配对机会，实际m1–6；同精确D/m，细类另固定完整粗向量 | 本轮新实验分析；按确定性规则完整枚举，结果以背景统计保存 |
| 旧n20 | 269,814 Manual＋1,517 Semi完整行；76父内/实际m条件 | 从实际保存文件恢复并重新汇总；Y/Z可重叠原设计单列 |
| 直接AC | 2,056行、461条件、58图22楼、实际m4–20 | 复用较大纯类块端点；无同类B对照不补造 |
| 难度/原答 | 9,217行为库存；当前目标主域8,131原答/215图；3,790角色对照；201换类难度格、37,788指标行 | 本轮新分析，非新采集；资格、记录时间来源与缺机会保留 |
| 机制 | 7y13全924背景路径、pa4-18中位附近事件；必要结构/门槛/失败旧机制小包 | 新几何呈现与原案例复用分别标记；0融合重放 |

这些计数不能相加作独立样本数。方法、层级、阶段会共用端点；源/目标只有一个可行块时，人员波动不可估。有限面板完整不等于所有图片全人员池、背景、团队或进入顺序全部穷尽。全池各配比可行容量和未覆盖保留在 `configurations/DOMAIN_CONFIGURATION_CENSUS.csv.gz`；严格请求容量见 `exchanges/ALL_FEASIBLE_CAPACITY_AND_REGISTRATION.csv.gz`。

## 文件怎样关联

1. `inputs/` 保存必要ALL、楼外、旧方法和跨条件标签/中心，`SOURCE_MANIFEST.csv`逐文件列原路径、身份、源和副本哈希。
2. `configurations/TEAM_MEMBERS.csv.gz` 的 `team_key` 连接逐团队分项；`PANEL_TEAMS` 连接面板与成员，`TEAM_CONFIGURATION_LINKS` 连接完整粗/细人数向量。`PANELS_USED`保存固定背景和候选12人。
3. `exchanges/<批次>/EXACT_EVENT_LINKS.csv.gz`逐行列 A/B/C、D/X/Y/Z、楼外角色、实际m和r；以 `event_id`及`condition_id`连同目录 `EVENT_OUTCOMES.csv.gz`。物理三队与有向三队键均保留。完整原标量/几何在基线main的closure交付中，不重复打包。
4. `finite_pair_comparison/*BACKGROUND_STRATA*`按候选位图与原面板D恢复精确共同背景；细类父内比较还固定父向量键。完整端点对由成员清单和代码确定性重建，无需上亿行重复端点几何。
5. `direct_ac/EXACT_AC_EVENTS_AND_OUTCOMES.csv.gz`同时保存实际集合、方向及分项；必要使用端点也已包含。
6. `difficulty/`及`integration/reused_cases/`包含足够复看主要病例的原答、端点、票账与真实图像；没有复制原图全集。

质量B8L2/D10、底面/三维代理、角点/底点/方向、高度、遗漏/外扩、结构表达、时间与失败均独立保留分母。`dir`是冻结算法的自身方向误差，不能把它当外部绝对朝向测量。时间是同源库存记录总秒数，不是新测生产用时。各目录README与字段合同解释量纲。

## 分阶段实际交付

| 文件包 | 内容 | 状态 |
|---|---|---|
| `HOHONET_人员混合构成_阶段01_20261022.zip` | 早期可用分类/Manual联合/难度检查点 | 已保存；是历史检查点，完整结果以下列包为准 |
| `HOHONET_四分类完整混合配比与大块AC_阶段02_20261022.zip` | 四分类全配比、310,458团队分项与关联、七个完整格范例、直接AC | 已保存 |
| `HOHONET_personnel_stage03A_exchanges_v2data_20261022.zip` | 全严格ABC、旧n20完整事件、同分母QT、成员/容量/失败及代码 | 已保存 |
| `HOHONET_personnel_stage03B_finite_pairs_v2data_20261022.zip` | 全部有限配对汇总、逐背景分片、实际m/r及代码 | 已保存 |
| `HOHONET_人员分类构成_主报告标签机制与代码_20261022.zip` | 更新后的既有人研究主报告、建议表、方法/标签小输入、完整难度与机制、统一索引/复现 | 本轮最终核心包；实际完成状态以最终清单为准 |

同时交付可单独下载的主报告、18条件表、11家族表、完整构成宽表、85条件、201难度格、精选图和文件清单。**阶段02以`personnel_mixture_comparison_20261022/`为包根，解压到仓库的`research/workers/`；阶段03A/03B和最终核心包以`research/`、`docs/`为包根，解压到仓库根。** 这样文件关联到同一研究目录。不包含虚拟环境、完整原图全集或重复历史大源包。

复现入口：[REPRODUCE.md](REPRODUCE.md)。最终实际文件与哈希见 `COMPLETE_FILE_INDEX.csv`，旧源包恢复依据见 `SOURCE_RECOVERY_INDEX.json`。**包内数据实体已经存在，不把ZIP索引当逐事件交付。**

本轮没有新做所有全池随机前缀、同房预测、Semi困难图采集或研究台；这些是范围以外项目。人员分类、有限混合构成、实际成员变化与条件性换类判断已具备可用成果。
