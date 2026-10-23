# 原件恢复与重算边界：精确设计是否仍存在

读取版本：`e92abe8631d7f01dc192ee796b46f295ece37a6d`。本目录所有列入交付的原文件均实际读取 Git blob，并保留原字节、仓库相对路径和来源；没有用报告数字生成实验数据。没有新增融合、评分、分类、ABC设计、顺序或 bootstrap。

## 1. 需要先明确的结论

**对于遗失的新大块严格 ABC 研究，目前可凭现存精确设计与原代码直接原样重算的设计数为 0。** 没有找回 `design/STRICT_ABC_EVENTS.csv.gz`、新大块逐事件表、111,054端点成员/标量/几何、原条件分析及重抽代码。旧面板、容量表、类别名单和冻结引擎不能唯一确定当时具体选择的 X/Y/Z/D、锚点、背景、顺序与抽取权重；根据它们再次构造可行 ABC 属于新实验设计，不是原件恢复。

另有**独立的人员人数过程**保留了精确设计和原代码，本目录已恢复它们。它的 318,816 端点集合与缺失的 111,054 新大块端点不是同一集合；下面的闭合数据也不能替代用户要求的新大块结果。

三个重算等级应分开：

|等级|适用内容|本轮判断|
|---|---|---|
|① 原精确设计、原程序和冻结输入仍在|人数过程精确顺序注册；已存人数数据的原汇总程序|可以保持原团队/路径重算；本轮只恢复文件，未重新运行研究计算|
|② 原设计也丢失|新大块严格ABC及依赖它的条件、成员、删楼分析|只能新登记设计后重新开展；不得以复现原报告数字或达到原事件/端点数量为目标|
|③ 设计保留，但原分析实现丢失|人数路径与建筑 bootstrap 收尾|可固定已保存路径重新实现分析，不必重新生成团队；这仍不是恢复原 bootstrap 代码或原样复算区间|

完整判定见 `RECOMPUTE_CLASSIFICATION.csv`。类别①关于独立人数过程，不改变新大块类别①为0的判断。

## 2. 实际取回的独立人数设计与原代码

`population_existing_originals/` 复原该专题当前 main 的原相对目录：

- `design/EXACT_ORDER_DESIGN.csv.gz`：12,398行、229池，其中自然路径5,424行；包含全部实际进入顺序、策略、配对 `base_path_id`、成员、历史角色与原始路径关联。
- `inputs/INPUT_SNAPSHOT.json.gz`：229个池的冻结原答与参考执行输入；保留图、人员、object_id、几何与记录时间。
- `inputs/REQUESTS_INITIAL.json.gz`：916条历史顺序及77,942条历史请求；不能把它们叫新大块请求。
- `inputs/ALL_METHOD_LABELS_LOBO.csv.gz`、`FOLD_CLASS_DEFINITIONS.csv`：冻结楼外标签与中心。
- `code/register_population_orders.py`：原顺序注册程序，11,731字节。
- `code/order_policies.py`：原登记程序直接导入的角色/顺序模块，9,743字节；本轮后补实际原字节，使上面登记命令的本地模块依赖完整。它按楼外历史角色筛选，不重新分类。
- 原 `analyze_natural_curves.py`、`analyze_policy_curves.py`、直接策略对照、向量、前缀连接、原生前缀运行和宽表恢复代码。

这些是已取得的原文件，共34份。完整原字节列表在 `MATERIALIZED_POPULATION_ORIGINALS.csv`，各CSV/gzip实际读到结尾的字段/行数在 `READ_AND_LINK_RECEIPT.json`。

完整人数主分析另外依赖原目录下的 `results/PREFIX_TEAM_LINKS.csv.gz`、`results/ENDPOINT_SCALARS.csv.gz`，几何分析还需要 `ENDPOINT_GEOMETRY.json.gz` 和相应波动表。它们未在本小包重复下载或打包；main 的 `LARGE_TABLE_STORAGE.json` 记录标量按3份顺序合并。依赖入口不等于本轮已读过这些大表，原主汇总命令见附带的 `source_original/REPRODUCE.md`。

## 3. 最小完整真实数据究竟完整到哪里

本轮取回既有 `UwV83HsGsw3-12` 人数案例原件：

|内容|实际完整性|
|---|---|
|原 `PATH_SCALARS.csv`|112行，4条旧自然路径×k=1…28；全部原行保留|
|原 `CASE_GEOMETRY.json.gz`|仅 path2 的全部28个状态；不声称其它3条路径的几何也在该文件|
|path2完整数据|精确进入顺序、28前缀标量、28几何/身份组状态、28份原答与完整参考、178条局部票记录、28条事件|
|新增内容|只提取精确子集及连接索引，不产生任何新端点或评分|

闭合路径为：

`UwV83HsGsw3-12__manual__66a7b558e6__path2`

`minimum_complete_population_path/EXACT_ORDER.csv` 和 `PATH_SCALARS.csv` 是从上述原件按精确路径过滤的副本。`PREFIX_LINKS.csv` 为每个 k 保存原团队键、按顺序进入的成员、object_id、参考键和 `/states/<k>` 几何定位。它们的状态是 `exact_extraction_from_existing_population_originals_not_large_block_ABC`。

原 `CASE_GEOMETRY.json.gz` 中 `/pool/records` 含28份原答点、作答身份和时间，`/pool/reference` 含参考点；`/states/1`…`/states/28` 含候选几何、身份组、票支持、对应和环序状态。每个状态的实际人员与精确前缀匹配，每个标量的对象集合与原答匹配，canonical团队键亦匹配。k=2 的冻结延期/不可评分状态原样保留，不补零。完整性回执不把这28个状态当成28个独立图片。

## 4. 直接读取与核对命令

本目录根执行：

```bash
python verify_and_extract_minimum.py
python summarize_saved_case.py --out inspected_case_by_k.csv
```

第一条是**本轮新写的读取辅助程序**，使用Python标准库，读取原件、核对成员/参考/几何连接并重新提取相同28行；不是原条件分析或原bootstrap代码。第二条也是本轮读取辅助，仅将已存4条历史自然路径在每个k的Q、P10、SD和状态重新汇总，明确只描述这4条旧路径，不冒充24路径研究或新的验证。两条均不调用融合或评分。

如只要读关键原文件：

```bash
python -c "import pandas as pd; d=pd.read_csv('population_existing_originals/design/EXACT_ORDER_DESIGN.csv.gz'); print(d.groupby('policy').size())"
```

原顺序注册代码的显式输入命令如下；该命令是在**同一冻结设计基础上重新生成登记文件**，本轮没有执行它：

```bash
python population_existing_originals/code/register_population_orders.py \
  --snapshot population_existing_originals/inputs/INPUT_SNAPSHOT.json.gz \
  --initial-requests population_existing_originals/inputs/REQUESTS_INITIAL.json.gz \
  --labels population_existing_originals/inputs/ALL_METHOD_LABELS_LOBO.csv.gz \
  --definitions population_existing_originals/inputs/FOLD_CLASS_DEFINITIONS.csv \
  --out reproduced_order_registration
```

默认主seed来自原脚本与已保存的登记清单。不要调整seed、重复数或选择规则去凑任何历史报告数字。

## 5. 新大块重建可以复用什么基础

`reusable_frozen_inputs/` 只存必要原输入和执行入口，没有重复打包旧同房结果：

- 用户采用的直接同房分类：`relation_adoption_20261016/CROSS_MODULE_RELATIONS.json`、`original_groups.json`、`candidate_adoption.json`、`relations.json`及字段合同；原分类允许重叠，状态原样保留。
- 当前Manual楼外标签与历史中心：`CURRENT_MANUAL_LABELS_LOBO.csv`（2,728行）及 `CURRENT_MANUAL_FOLD_CENTERS.csv`（371行，含粗细层），不能只凭跨折M编号连接。
- 现有共同成员类别底表：`DIRECT_PAIR_CLASS_MEMBERS.csv`（1,119行）；它提供既有共同池输入，不提供遗失大块X/Y/Z/D选择。
- 冻结执行入口：`global_study.py`、`run_endpoints.py`、`fusion_engine.py`、`fusion_runner.py`，以及已有融合、环对应和B8L2/D10模块。
- 资格和参考执行快照：上述 `INPUT_SNAPSHOT.json.gz`。它是已冻结的执行输入，不等于本轮重新审定或恢复任何被排除作答的资格。

源路径/字节/身份见 `REUSABLE_FROZEN_INPUT_INDEX.csv`。执行模块保留原仓库布局依赖：`global_study` 按 `__file__` 推导仓库根，再导入人员引擎与其它模块；`run_prefix_endpoints.py --repo` 显式接收完整仓库根。代码中的 `/tmp/hohonet_deps` 是历史可选搜索路径，不作为本包必需环境。

这份选择性小包**不是完整可独立运行的native融合环境**。原生融合还需要仓库内的 `pool_io`、几何诊断、测量引擎ZIP、working_models及导入依赖。已附代码只说明真实执行接口；本轮不为“可运行”冒称这些依赖都已独立打包。只读原数据、检查最小闭合路径不需要这些native依赖。

回填到仓库时，将 `population_existing_originals/*` 放到 `research/workers/personnel_population_curves_v2_20261023/`，将 `reusable_frozen_inputs/*` 按其完整相对路径放到仓库根。检查输入索引后再覆盖同一固定版本文件；不覆盖不同版本的用户修改。原说明引用的最终目录为 inputs/design/results/natural/policies，不依赖丢失工作区目录名。

## 6. 仍需安排的重建

对新大块：先以现存直接关系、资格、LOBO标签和容量登记新的严格ABC实际成员，分别保存D/X/Y/Z、n/m、两视角团队键、选择规则和覆盖；再复用冻结引擎只算缺失端点。新结果使用新实验ID，与未能复核的旧报告分开。旧报告的事件总数、端点总数、均值和显著性不作为新设计或停止目标。

对人数bootstrap：保留已经取得的精确原路径与配对键，在能够读取全部所需前缀的前提下，另行登记建筑重抽/路径重抽实现、seed、次数、缺失处理和计权。这是固定设计重新实现分析；原bootstrap文件仍列未取得。现有24条自然路径与8条配对策略路径不需要为了重算区间而另造顺序。

本恢复阶段只交付现存原件、闭合样本和边界，没有在恢复目录内启动上述重建。后续按用户新增指令开展的实验或固定设计新分析应另存新阶段，保留本恢复判断和原件身份。
