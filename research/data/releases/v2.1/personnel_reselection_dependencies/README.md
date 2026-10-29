# v2.1 新人员分类：已存结果接续与依赖审查

**当前依赖已接续新增十包。** 阶段03A、03B核心及01—05、03C、05A、05B已独立归档，完整配比数值、广筛原始登记和固定XYZ人数路径已可读取。原五包阶段06、07A/B/C/D继续保留；新增代码不覆盖07A执行代码及已修复的对象ID导出。完整证据入口为[已有模拟人群证据](../simulated_population_evidence/README.md)，归档范围见[十包回执](../../../../workers/personnel_v21_reselection_20261029/additional_delivery/IMPORT_RECEIPT.json)及[实际路径映射](../../../../workers/personnel_v21_reselection_20261029/additional_delivery/PATH_MAP.csv)。

原五包导入回执为 `research/workers/personnel_v21_reselection_20261029/IMPORT_RECEIPT.json`，源提交 `a476461d7ede8db95da43de4139e612c05e618bc`。本目录只消费保存结果；原始作答、正式难度、排除资格和旧结果均未改变，没有新增融合、评分、分类拟合或SHA校验。

采用口径来自本轮协调任务：OPPJOINT K3/K4 为联合主家族，K4 的12/6与20/5为主换类条件；TARGET_DSTRUCT K3 14/7为结构补充；RFUSE_GEOM K2 12/4为反推对照。同容量 Q-only 的额外增益仍未隔离，但不作为此次采用阻断条件。报告中旧的用途建议保持来源身份，不自动覆盖该采用口径。

## 可以直接接入的结果

`ADOPTED_CONDITION_RESULTS.csv` 从已交付方向汇总中精确选择四个条件，保留全部原指标及各自有效分母，新增采用用途和来源路径；不进行二次选优。

|用途|方法与 n/m|登记事件/图/楼|CB有效图|图均 C−B|正向图|楼均 C−B|
|---|---|---|---|---|---|---|
|联合主条件|OPPJOINT K4 12/6|172/56/13|56|8.051041|52/56|7.145410|
|联合主条件|OPPJOINT K4 20/5|378/88/15|88|3.284346|83/88|2.627392|
|结构补充|TARGET_DSTRUCT K3 14/7|192/85/21|83|6.559866|76/83|6.659257|
|反推对照|RFUSE_GEOM K2 12/4|210/83/21|83|4.730133|67/83|4.191970|

这些是已有汇总值的接续；此次没有重复上一轮对主事件的全面实核。不同条件支持不同，不能按这四行均值直接排列方法优劣。CA、CB、幅度差、时间和失败各有分母。K3/K4的家族采用不等于所有K3条件都被选为主换类条件。

人员表64,170行=45法×23折×62人，方法/折/人员键唯一。ALL仅用于描述，22个楼外折用于相应建筑评价。60,547条有标签记录全部连接到对应折的类别角色；3,623条未知记录保留。`METHOD_FOLD_SUPPORT.csv` 保存每法每折已知及总人数。跨折必须按角色含义对齐，不能把C1/C2编号当成固定人员类型。

`SAVED_DESIGN_COVERAGE.csv` 保留原五包按方法、条件、n/m登记的范围。新增全局路径和全部分类证据由[换人证据链](../simulated_population_evidence/exchange/README.md)汇总，不能把这张原五包覆盖表当成新增十包的全集：

|实验|实际交付|边界|
|---|---|---|
|重点严格ABC|10,980事件，9法|不是69,485事件广筛全集|
|固定A改变m|10,184增量关联，1,947路径，3法|同一A；D随m变化；容量策略混合实际起止m|
|同XYZ背景|3,252背景对照，9法|n/m和XYZ固定，D真实成员改变|
|大块直接AC|1,966事件，3法|没有严格ABC的B基线要求|
|固定父类细分|13,544事件，25法|使用父类映射与实际可行支持；不等于全库普遍改善|
|固定XYZ改变n|166条选定条件汇总，及新增05B完整路径源表|摘要保留原登记范围，完整路径已交付；逐路径核验见换人证据链|

## 完整配比与广筛：新包已补齐原缺件

Manual报告明确记载45法重新汇总完成：231面板/40图/22楼，213,444关联，213,442端点；45法共同已知域182面板/38图/22楼。每面板924队是固定12选6空间，不是所有30余人团队的穷举。Semi报告也单独存在。

原五包审查时，Manual/Semi完整配比目录只有README，因此当时记为“已报告计算、数值文件缺交付”。这项缺件已由新增十包补齐，当前不再沿用 `report_only` 或 `computed_reported_delivery_missing` 状态。新归档按 `additional_delivery/packages/<stage>/` 分别保留原相对目录：

- `03B_core/composition/primary_mixture_results/ALL45_ALL_METRICS_BOTH_SUPPORTS.csv`：Manual完整主汇总；核心包同时保存面板、团队、端点和紧凑关联。
- `03B_01`至`03B_05/composition/primary_manual45/by_method/`：合计45法的格计数、逐格分布、面板方差和汇总，未混合覆盖成一个虚构源目录。
- `03C/composition/semi_mixture_results/COMMON_SUPPORT_ALL_METRICS.csv`：Semi自身分类的全指标数值，和Manual分开使用。
- `03A/composition/stage03A_other_targets/ALL45_COMMON_SUPPORT_KEY_METRICS.csv`：其它合法目标的共同支持结果。

当前可按[完整配比源索引](../simulated_population_evidence/composition/SOURCE_INDEX.csv)定位实际文件；[配比复核报告](../simulated_population_evidence/composition/README.md)给出成员、完整格计数、分布与方差复核。OPPJOINT少数案例继续用于解释，完整45法数值现在有独立入口。

广筛原件也已补齐：`05B/experiment/global_screen_capacity/SCREEN_POOL_FRAME.csv`、`05A/experiment/global_screen_design/EVENTS_EXACT.csv.gz`以及`05B/analysis/global_size_paths/SIZE_PATH_RESULTS.csv.gz`。`DEPENDENCIES.csv`已指向这些实际repo相对路径；固定XYZ的166行摘要不再标为“等待原始路径”。广筛边界和规模路径的复核详见[换人证据链](../simulated_population_evidence/exchange/README.md)，内部比较选型的研究身份仍保留。

## 策略、同房与无需重跑的部分

OPPJOINT K4小池策略有实际逐n分布、概率端点关联和汇总。20个Manual小池复用1,081个端点；15池有未到齐过程，覆盖14图8楼。高Q优先平均Q约+1.500，但仅5/14图提高；较快优先约−1.900，仅4/14图提高。保留低尾、失败和时间取舍的用途，不说成多数图片平均Q改善。全部人员到齐后各策略输出相同。

原 `current_policy_results/` 的policy32使用V3_BEHAVIOR/V3_JOINT_QT楼外角色，原共同域153图和新增26图分别报告。它不是OPPJOINT。未发现大池OPPJOINT策略结果，交付说明也只宣称小池新角色策略；这项应登记为新设计待执行，而非缺少一个旧结果文件。最小接续为：冻结OPP楼外角色优先序和未知组顺序，复用 `current_policy_design/` 的自然基础路径，重新导出前缀团队键；查询 `current_policy_endpoints/` 及自然端点缓存，只补真正缺失团队，再在固定共同支持上配对。不能直接改旧V3轨迹名称。

`same_room_current_results/` 有真实的当前结构/联合标签计算，包含2,659有限面板及62,964大块双视角事件；它们形成于此次OPP采用之前。新包说明不改写同房，未交付OPP新标签同房实验。本轮协调后，已另外完成[OPPJOINT固定面板接续](../same_room_oppjoint_fixed_panels/README.md)：复用2,659原面板，给92,342条原团队记录接新配比；共同全员已知63,892条。普通同范围主预算的双视角Q有效307面板、127图对、13楼、9,766条团队记录，全部源端点保持。该结果已有独立回执，不属于五包原交付。如声称“OPP同类/跨类严格换人”，须用 `same_room_current_capacity/`、既有共同人员和空间关系重新检查容量与设计，不能给旧事件换标题。新增团队先查缓存，只有缓存缺口才需要融合；仍保持既有关系、视角与排除边界。

自然256的到达顺序、固定实际团队Q、同团队几何都不因类别名或标签变化而改变。分类改变只触发分组统计或依赖类别的选队设计；不触发这些原生量全面重算。正式三档难度仍保持；目标结构条件与难度标签分别表达。

## 验证与机器合同

运行 `python tools/thesis_main/analysis/audit_v21_reselection_dependencies_20261029.py`，只读取归档，写入本目录。实际重新聚合固定m对、容量策略、背景对照及小池策略，按目标→图片→建筑等权，分别保留缺失。3,906个均值/有效数/正向数单元全部匹配，最大误差7.11e−15；2,940条全池策略比较的可用均值差为零。`CHECKS.json` 记录范围和数值。定向测试 `python -m pytest tests/test_v21_reselection_dependencies.py -q`：8通过，覆盖同图多目标等权、缺失分母、错误分母拒绝，以及新增包路径解析、拒绝回退旧报告和保留07A来源路径。当前25行非空来源路径全部存在，6项数值／登记来源直接解析新增包文件；完整配比及全局事件的科学复核另见模拟人群证据各模块CHECKS。

`DEPENDENCIES.csv` 每行一个模块/工件，字段为topic、source_path、delivered、status、method_identity、next_action。delivered表示当前路径实际存在；ready_numeric_tables、ready_registered_paths等状态说明已交付的材料层级，统计复核需同时查看对应CHECKS。当前旧缺件状态已撤销，source_path指向独立归档或已生成的实际源索引；空路径只用于尚无结果的新设计。`SAVED_DESIGN_COVERAGE.csv` 的rows是所指源表行数，path_id_count/event_id_count才是对应唯一对象数；图/楼计数不能跨行直接相加。`ADOPTED_CONDITION_RESULTS.csv` 保留源表schema，仅附adopted_use/source_path；来源汇总并非此次新增独立推断。

已检查项目地图与文档索引，目录仍属于既有v2.1研究归档；本任务按分工不改地图、catalog、RELEASE、正式文档或工作台，交由协调线程登记本入口。没有临时服务和临时文件待清理。

本脚本保留原聚合复核，并更新交付位置；新增完整配比、广筛和人数路径的逐项科学核验由模拟人群证据模块记录。本轮未启动OPP大池策略、新选队的同房严格ABC或原生融合重放，也未做浏览器交互验收。它们与已补齐的旧文件缺件分别登记；现有结果继续保留少数反向图及各自支持范围。
