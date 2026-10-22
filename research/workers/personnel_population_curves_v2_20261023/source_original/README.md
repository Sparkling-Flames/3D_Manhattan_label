# v2 自然混合人群人数曲线与类别进入顺序

**本轮已完成并保存全部登记结果。** 研究结论、难度差异、角色选择与机制解释统一维护在[人员主报告第6节](../../../docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md)；本文件只负责输入身份、完成范围和文件入口，不另建一份重复的最终报告。

实际读取main：`72a44e80c344975962e1071bd54d894dd86bb4b4`。GitHub比较API已确认该提交包含用户指定的 `ef148c82d`，见[SOURCE_COMMIT_ANCESTRY.json](SOURCE_COMMIT_ANCESTRY.json)。底层始终是真人 **v2**；历史包名中的v3表示研究轮次。

## 已完成范围

| 对象 | 实际完成 | 口径 |
|---|---:|---|
| 正式人员池 | 229池／196图／22楼，7,302份正式原答 | 同图片、同采集条件、固定参考与资格；实际容量3—46人 |
| 自然进入顺序 | 5,424条，175,032个前缀 | 225池各24条；4个N=3池完整枚举6条。N=4的24条同样是全排列，小池不额外重复加权旧4条 |
| 全部登记顺序 | 12,398条，404,082个前缀 | 包含自然及四种既有角色优先顺序；每条覆盖k=1至全池 |
| 不同成员端点 | 318,816个 | 288,628个本轮新增结果、30,188个历史复用；相同成员集合的确定性终点只保存一次 |
| 完整事件 | 557,138行 | 自然相邻169,608、自然区间45,960、政策对自然229,050、角色直接对照112,520；不是557,138个独立团队 |
| 机制案例 | 5张Manual原图及精确状态 | 原答、票数、门槛、对应、融合与分项；另接每案完整24条自然及各政策配对顺序背景 |

以上为**已登记有限研究范围的完整结果**，不等于全池所有排列与成员集合已穷尽。完整性记录见[COMPLETION](results/COMPLETION.json)和[DELIVERY_VERIFICATION](results/DELIVERY_VERIFICATION.json)；可行空间与实际覆盖见`coverage/`。本轮新增端点数不等于执行器历史总调用次数，针对缺失落盘尾部的恢复及既有几何补充有独立回执。

Manual与Semi始终分别评价。普通Manual177池、普通Semi32池、门洞Manual17池，另有特殊Manual2池、特殊Semi1池；门洞与特殊层不并入普通难度主均值。正式池不等于全部非OOS行为库存，未进入者及原因保存在逐池资格覆盖表。

四种优先角色为**较多非冗余转折、历史人数最多结构类、联合较高历史Q、联合较快**，均由目标建筑之外的既有标签与历史中心确定；本轮没有重新训练分类。政策通常使用8条与自然顺序精确配对的路径，一个N=3快类条件使用全部6条。低尾与成员波动也按相同配对路径比较，不把策略8条直接与自然24条混为同一支持。所有顺序的最终人员池相同，比较的是前中段过程；全员终点相同与零方差是确定性事实。

`k=2`按冻结连接合同延期，保留登记行并单列，不补Q=0或当普通融合失败。质量、几何、失败、时间各保留真实分母；质量—时间联合结论使用两者共同完整支持。时间是既有来源记录的成员秒数之和，不是新测生产工时或并行交付历时。

## 文件入口与固定目录

| 目录／入口 | 内容与用途 |
|---|---|
| [SOURCE_AND_DESIGN.json](SOURCE_AND_DESIGN.json) | 源提交、数据身份、已完成设计、来源拆分及阶段00历史登记 |
| [DATA_DICTIONARY.md](DATA_DICTIONARY.md)／[REPRODUCE.md](REPRODUCE.md) | 字段、缺失与分母、表间关联，以及直接重聚合和必要时原生重放 |
| `inputs/` | 冻结v2池与原答、既有楼外标签与逐折定义、难度/机会和原池特征；无原图全集或虚拟环境 |
| [design/EXACT_ORDER_DESIGN.csv.gz](design/EXACT_ORDER_DESIGN.csv.gz) | 精确无放回顺序、基础路径、角色、随机种子、采样权重、成员与支持 |
| [design/ENDPOINT_CLASS_VECTORS.csv.gz](design/ENDPOINT_CLASS_VECTORS.csv.gz) | 按team_key保存结构/联合粗细类别人数向量与UNKNOWN；轴定义见[CLASS_VECTOR_AXES_BY_POOL](design/CLASS_VECTOR_AXES_BY_POOL.csv) |
| [coverage/FORMAL_POOL_INVENTORY_COVERAGE.csv](coverage/FORMAL_POOL_INVENTORY_COVERAGE.csv) | 正式池与完整库存的资格对应；另存排列、成员集合和类别人数向量的可行及已覆盖空间 |
| [results/ENDPOINT_SCALARS.csv.gz](results/ENDPOINT_SCALARS.csv.gz)／[PREFIX_TEAM_LINKS](results/PREFIX_TEAM_LINKS.csv.gz) | 去重端点的完整标量、成员与来源，以及所有前缀到端点的关联；展开表为[PREFIX_RESULTS](results/PREFIX_RESULTS.csv.gz) |
| [results/ENDPOINT_GEOMETRY.json.gz](results/ENDPOINT_GEOMETRY.json.gz) | 按端点保存必要候选几何；[PREFIX_GEOMETRY_VARIATION](results/PREFIX_GEOMETRY_VARIATION.csv.gz)保存同人数换组的几何波动 |
| [natural/NATURAL_TABLE_GUIDE.md](natural/NATURAL_TABLE_GUIDE.md) | 自然过程逐图/楼/难度分布、固定共同人员容量面板、低尾、失败、分项、时间与波动；逐图主表为[NATURAL_IMAGE_CURVES](natural/NATURAL_IMAGE_CURVES.csv.gz) |
| [policies/POLICY_FIELDS.md](policies/POLICY_FIELDS.md) | 四角色对自然及角色之间的配对过程；逐图人数表、共同域、分项与固定n20摘要均在本目录 |
| [events/README.md](events/README.md) | 全557,138行完整关系式事件；保留所有已算差值、比率、风险与具体成员变化，避免反复复制两端标量 |
| [cases/README.md](cases/README.md) | 五个原答—投票—融合机制与原图；完整顺序背景见[case context](cases/final_context/CASE_CURVE_BACKGROUND.md) |
| `code/` | 本轮实际登记、运行、恢复、汇总、覆盖、关系表和可视化代码；冻结原生引擎仍从指定仓库提交读取 |

## 完整事件可以直接接续

| 文件 | 行数 | 差值方向 |
|---|---:|---|
| [自然相邻](events/NATURAL_ADJACENT_TRANSITIONS_LINKED.csv.gz) | 169,608 | current − previous，同一路径的相邻前缀 |
| [自然区间](events/NATURAL_PAIRED_PATH_INTERVALS_LINKED.csv.gz) | 45,960 | to − from，原登记区间 |
| [政策对自然](events/POLICY_PAIRED_PREFIX_EVENTS_LINKED.csv.gz) | 229,050 | priority − 精确配对natural |
| [角色直接对照](events/POLICY_DIRECT_PAIRED_PREFIX_EVENTS_LINKED.csv.gz) | 112,520 | focal − comparison，同基础路径、同人数 |

这些是完整事件，不是抽样摘录或只有索引。两端Q/D10、节点、时间和失败状态保留；其它重复原值按team_key从单份端点表恢复，完整类别向量同键关联。所有已计算的change/delta/ratio/logratio、风险及净席位变化原样保留；列级恢复关系见[映射表](events/COLUMN_RETENTION_AND_ENDPOINT_MAP.csv)，事件方向与两端关联见[关系表](events/EVENT_RELATION_MAP.csv)。原宽表未删除，但不在本交付重复打包；可以由关系表、端点与保留派生列重新组成等价分析宽表。

## 来源与历史阶段

原v2每池4条自然路径、同房共同/支持子池的同成员端点、后续组成研究缓存按来源分别保留。旧同房124,924前缀不是本轮每图完整人员池的自然抽样；旧195,888条是有限面板嵌套边，也不当作完整无放回顺序。复用只按实际相同成员键执行。早期4条顺序与阶段01材料继续保留阶段身份，最终完整结果以本入口及`results/COMPLETION.json`为准。

冻结输入与代码身份见[FROZEN_INPUT_CODE_HASHES.csv](FROZEN_INPUT_CODE_HASHES.csv)，实际环境见[RUNTIME_VERSIONS.json](RUNTIME_VERSIONS.json)。下方保留阶段00原文，里面的“计划”“运行中”“不宣称完成”不覆盖本页上方的完成状态。

<details>
<summary>阶段00原始README全文（历史保留）</summary>

# v2 自然混合人群人数曲线与类别进入顺序

本轮读取 main 提交 `72a44e80c344975962e1071bd54d894dd86bb4b4`。底层为真实数据 v2。

## 阶段 00：已接续的实际输入

已取得冻结融合输入229池、196张图、7,302份正式真人作答，实际池容量3—46人；普通 Manual 177池，普通 Semi 32池，门洞 Manual 17池，特殊条件3池。旧v2已有每池4条完整均匀随机排列，共916条顺序、29,208个逐人前缀，旧结果包的逐请求标量已恢复。

同房124,924前缀来自共同人员/支持子池；可以复用相同成员端点，不并作全池自然抽样。旧195,888条记录实际是有限面板嵌套背景之间的相邻人数边，不能当作195,888条完整随机顺序。

## 本轮实际设计

自然排列计划为每池24条（继承旧4条，补20条），每条覆盖k=1至全部人员。类别策略从同一自然排列稳定分区：历史转折最多类、主流表达类、联合高历史Q类、联合相对时间最快类优先；各策略8条成对顺序，最终人员池完全相同。角色只使用目标建筑外标签及历史中心，未知标签不补零且仍进入余池。

每个不同成员集合的确定性融合只计算一次。失败与缺少评分分别保留，两人池按冻结规则暂不连接，单列政策缺失。时间为既有记录的累加，并非新测生产工时。全员只有一个集合，波动为零是机械事实。

`SOURCE_AND_DESIGN.json` 为源与设计登记；本阶段不宣称新融合或曲线结果已完成。后续按批次补入真实结果，不列不存在文件。

</details>
