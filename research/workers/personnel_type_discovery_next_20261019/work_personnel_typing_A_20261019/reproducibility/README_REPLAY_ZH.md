# Part A 复现与交换入口

本入口负责把已冻结的输入、两条人员分型路线和共同事件评价接起来。**默认只核验关键输入、检查表头、列出可运行层级，不拟合模型、不重新融合、不下载原图、不写 GitHub。** 实际计算必须显式选择层级、给出隔离工作区，并加 `--execute`；这是运行参数，不是再次向用户申请研究授权。

本轮已经从 main 核心归档恢复并核验 824 个冻结源文件及 519 个保留逻辑文件，随后完成新的 Part A 计算。能重放已审计数据，不等于从原始日志独立复现全部采集与人工审核；Dot 缺少的完整设计、逐曲线及团队状态也没有被声称完整复现。

## 1. 所有 ZIP 应解压到同一父目录

各伴随 ZIP 都保留同一个 `work_personnel_typing_A_20261019/` 前缀。依次解压到同一父目录，合并这个目录；不要再多套一层同名目录，也不要把 `recovered` 里的两个兄弟目录拆开。

| 路径（相对该父目录） | 内容 |
|---|---|
| `work_personnel_typing_A_20261019/reproducibility/` | 本说明、`reproduce.py`、交换字段合同与入口检查。|
| `work_personnel_typing_A_20261019/recovered/work_v2_20261019/` | 按原布局恢复的 Pro 核心：旧人员画像、几何/分簇测量、冻结融合输入、原函数。|
| `work_personnel_typing_A_20261019/recovered/repo_main_20261019/` | 与上一个目录同级的冻结科学源快照。|
| `work_personnel_typing_A_20261019/events/` | 精确事件设计、请求、逐事件结果及可重建原生状态。|
| `work_personnel_typing_A_20261019/forward/`、`reverse/` | 两条类型发现路线的代码、注册、逐折标签、人员关系及解释。|
| `work_personnel_typing_A_20261019/assessment/` | 同事件独立重校准、覆盖、替换差异、最后一席策略、60 人联合画像、共同四节点与消融汇总。|

精简包若省略了派生大缓存，入口会列出具体缺项；不会把缺缓存当作缺失的真人标注。`events/REQUESTS.json.gz`、`events/event_design.csv.gz`、冻结分折和各类候选代码可精确重建本轮研究请求，不需要用户重新打包 Dot 或整套原图。

**三个 ZIP 合并后的最小数值复现目录**由 `MINIMUM_LAYOUT.json` 逐项列出。所有层级都需要五个代码目录、各自注册/配置和完整的 `recovered/` 兄弟布局。`aggregate` / `refit` 还需要 `events/common_events.csv.gz` 与 `events/native_runs/team_results.csv`；后者是 58,882 行端点请求表，供完整性和来源/同目标时间覆盖汇总使用，不等同于大几何状态缓存。`aggregate` 另需逐折类别、D10 标签、历史画像与冻结解释/类友稳定表；`refit` 会重建这些人员派生表。`fresh` 不复制已有本轮事件结果或团队表。

已经具备上述恢复区时，**不需要**本轮根目录的一次性 `download_main_inputs.py`、`recover_bootstrap_inputs.py`、`audit_inputs_A.py`，也不需要外部 `main_personnel_A_20261019/`、重复的 `frozen_source_82c6164b/` 或 `.git` 目录。这些文件记录最初下载/恢复/审计过程，未被当前数值入口调用。原图与展示页素材仅影响视觉查看，不构成冻结几何与人员分类的数值复现前置。

## 2. 固定提交与恢复范围

本轮读取的 GitHub main 固定为：

`dafa73ac7d8ada9a7f5c0e483d695adcbd916550`

Pro 核心归档要求的科学源提交为：

`82c6164b0d4630de5316199c92aa405930973168`

当前 main 相比这个源 pin 仅两份入口 Markdown 有差异；科学输入与代码沿冻结源校验。未来 main 再次变化时，应按这两个固定提交理解本轮输入，不把移动分支的新内容混入。

如果交付中的 `recovered/` 已齐，可以直接使用。若仅从 GitHub 开始，在一个独立克隆中取得本轮 main，调用仓库的 bootstrap；它会校验源哈希，并在需要时从原科学提交读取历史 Git 对象：

```bash
git clone https://github.com/Sparkling-Flames/3D_Manhattan_label.git /tmp/personnel-main-source
git -C /tmp/personnel-main-source checkout dafa73ac7d8ada9a7f5c0e483d695adcbd916550
python /tmp/personnel-main-source/research/workers/pro_personnel_v2_archive_20261019/bootstrap.py --repository /tmp/personnel-main-source --workspace /tmp/personnel-partA/work_personnel_typing_A_20261019/recovered --smoke
```

最后一个目标目录须不存在。若浅克隆没有原科学提交，先显式取得该对象：

```bash
git -C /tmp/personnel-main-source fetch origin 82c6164b0d4630de5316199c92aa405930973168
```

上面是恢复 Pro 核心，**不会单独生成本轮新增的 Part A 类型发现代码和事件设计**；还需把本轮代码/设计包解压进同一个 `work_personnel_typing_A_20261019/`。bootstrap 的 `--stage all --execute` 是旧 Pro 全管线，不是本 Part A 编排入口，不能混称同一次计算。

`recovered/BOOTSTRAP_RECEIPT.json` 记录本轮 824＋519 核验。新的 `reproduce.py` 默认再次检查 14 个关键输入 SHA、已有表头和依赖版本；它不把这次较小的入口检查冒充重新做了全部 1,343 项恢复或完整采集审计。

## 3. 运行环境

数值重放使用 **Linux/WSL 或支持 Python `fcntl` 的 POSIX 环境**。原生事件执行器使用 `fcntl` 文件锁，不能把 Windows 原生 Python 当作已支持的等价环境。本轮使用 Python 3.12，依赖的完整固定版本来自恢复区的 `requirements.txt`：numpy 2.3.5、pandas 2.2.3、scipy 1.17.0、scikit-learn 1.8.0、shapely 2.1.2 等。

可以在自己的虚拟环境安装，不会由本入口自动联网或安装包：

```bash
python -m venv /tmp/personnel-replay-env
/tmp/personnel-replay-env/bin/python -m pip install -r work_personnel_typing_A_20261019/recovered/work_v2_20261019/requirements.txt
```

之后把下面命令中的 `python` 换成 `/tmp/personnel-replay-env/bin/python` 即可。本轮环境中 Shapely 2.1.2 位于工作目录 `deps/`，其它固定包在活动 Python 中；如果来源目录存在 `deps/`，隔离工作区会复制它并加入模块路径。这样的本地二进制依赖仅适合同平台/ABI；跨平台应使用上面的固定版本安装方式。

默认 `--jobs 1`，同时把 BLAS/OMP 线程限制为 1，避免多个解析或拟合进程竞争内存。实际任务按图和折组织，8 GiB 环境下不应并行启动多套全量宽 CSV 解析。可明确指定 `--jobs 2` 或 `3`；它只控制原生事件和反向折并行，不改变类别数、权重、阈值或随机种子。

## 4. 默认核验与三种实算层级

从所有 ZIP 的共同父目录运行：

```bash
python work_personnel_typing_A_20261019/reproducibility/reproduce.py
```

默认输出关键源 SHA、表头、bootstrap 来源记录、运行环境，以及三个层级所需文件是否齐备。要完整流式检查合同中列出的 CSV 的 gzip CRC、行数和唯一键，可以执行：

```bash
python work_personnel_typing_A_20261019/reproducibility/reproduce.py --deep --report /tmp/partA-verify.json
```

这仍不执行科学计算。默认不写文件，只有显式 `--report` 才保存核验/计划 JSON。若仅想查看重算计划，选择层级但省略 `--execute`：

```bash
python work_personnel_typing_A_20261019/reproducibility/reproduce.py --level refit
```

| 层级 | 复用什么 | 重新计算什么 | 是否产生新真实团队融合 |
|---|---|---|---|
| `aggregate` | 本轮逐事件几何结果及端点团队表、冻结逐折类别、旧基线与 FULL 人员画像、已冻结解释规则及类友稳定表 | 从训练楼重新校准概率，重算共同事件摘要、类与时间/质量收益、房间/重复请求/四节点敏感性、B8–D10与规则评价、来源控制、60 人联合画像、固定 K 消融与代表案例目录 | 否 |
| `refit` | 审计逐份记录、原函数、已冻结的逐图历史 9°/12°分簇测量、本轮逐事件结果及端点团队表 | 69 个训练子集的 B8/D10画像、全部前向候选、反向历史关系和全部候选、训练内选择、解释与稳定性，再做 `aggregate` | 否 |
| `fresh` | 已处理逐份几何、参考、原函数、冻结局部分簇测量、精确请求和事件设计 | 从空的本轮原生团队缓存重新融合/评分/比较全部请求，然后做 `refit` 和 `aggregate` | 是，初始空缓存目标为 58,679 个唯一真实团队 |

`refit` 重拟合人员类型，不宣称重新生成了所有历史局部分簇、原始时间日志、GT 审核或原始预处理。`fresh` 的 fresh 指本轮原生团队状态从空目录新算，仍继承冻结点、删点、平均 x、声明环序、参考与资格。

当前顺序为 `aggregate` 8 步、`refit` 24 步、`fresh` 26 步。三个层级均执行 `final_diagnostics.py` 与 `report_tables.py`；前者在类别冻结后校准来源控制并做成对策略/实际覆盖诊断，后者只从已有预测、四节点链、画像和团队表产生可读汇总。它们不会重新选择类别、难度或稳定阈值。入口还重建事件机会/重复请求表；`refit` / `fresh` 在反向解释之后生成该路线的可读交换汇总。

### A. 只重聚合已有类与事件

```bash
python work_personnel_typing_A_20261019/reproducibility/reproduce.py --level aggregate --workspace /tmp/partA-aggregate/work_personnel_typing_A_20261019 --execute
```

它创建新的目标目录，复制必要的冻结输入与标签；不复制本轮已有 `assessment/` 结果。随后运行 `evaluate_common.py --stage all`，所以“只重聚合”也会独立重算训练侧校准概率，而不是直接信任任一分型代理输出的大概率表。

### B. 重新画像和类型发现

```bash
python work_personnel_typing_A_20261019/reproducibility/reproduce.py --level refit --workspace /tmp/partA-refit/work_personnel_typing_A_20261019 --execute --jobs 1
```

它不复制本轮 `feature_fits/`、内层评分缓存或已学类别，在新目录按原选择器重新计算。默认使用未修改的 `selection_common.py` 原聚合实现；运行时间可能较长。各代理的等价加速侧车仍随代码保留，但不是本统一入口的默认前提；规则/计量敏感性脚本内部的等价编码器保留其自身原函数 parity 检查。

### C. 精确事件从空缓存重放

```bash
python work_personnel_typing_A_20261019/reproducibility/reproduce.py --level fresh --workspace /tmp/partA-fresh/work_personnel_typing_A_20261019 --execute --jobs 1
```

此层不会复制本轮 `events/native_runs/` 或 `comparisons/`；先调用 `events/run_events.py --stage full`。全部 58,882 个注册端点请求保留，其成员集合去重后为 58,679 个真实团队。事件仍是旧面板 270,370＋新增面板 16,296，共 286,666；没有重抽样、按新类别删请求或更改融合函数。

目标目录必须不存在，且必须与来源树分离。入口从不自动删除已有缓存；如果指定已存在的目录，会在执行科学步骤前拒绝并保留内容。新建目录中任何中断或导出失败都保留现场和日志。对本入口自己创建、相同层级/输入/代码的工作区，可显式续跑：

```bash
python work_personnel_typing_A_20261019/reproducibility/reproduce.py --level fresh --workspace /tmp/partA-fresh/work_personnel_typing_A_20261019 --execute --resume --jobs 1
```

续跑复用已经成功生成的本轮缓存，**不能再把续跑中复用的状态称为新鲜计算**。入口和原生函数的收据分别记录阶段、耗时、退出码、新计算/复用；改变科学输入或脚本后应另建目录。`reproduce.py` 不自动调用任何“删除缓存再跑”的动作。

## 5. 现有原生 CLI 与计算顺序

统一入口只是依赖顺序编排。下面这些原有脚本均已按源码核对参数；不需要通过本入口才能运行。

| 阶段 | 已有入口及参数 | 说明 |
|---|---|---|
| 事件注册 | `events/register_events.py --native <recovered/work_v2_20261019/fusion> --out <events>` | 重建精确设计；已有注册必须逐值相同。本统一入口直接复制冻结注册，避免误以为 fresh 要重抽样。|
| 事件重放 | `events/run_events.py --stage pilot/full/compare/merge --jobs 1`，可多次 `--pool <pool_id>` | `pilot` 为 100 个请求；`full` 执行/复用原生团队后比较；`compare` 仅比较已有状态；`merge` 仅合并逐池事件。部分 pool 不能称全量。|
| 事件校验 | `events/verify_replay.py` | 核对事件身份、背景、嵌套身份、阈值及保留旧结果数值 parity。|
| 事件机会覆盖 | `events/summarize_design.py` | 只读冻结事件设计，生成各 k 覆盖、逐人入场机会和实际端点对重复次数，不读取融合优劣或类别。|
| 正向画像 | `forward/build_features.py --metric B8L2` 或 `D10` | 每个训练子集独立拟合；已有缓存会核对输入和代码身份。|
| 正向分区与选择 | `forward/discover_forward.py --stage partition --metric B8L2/D10`；`--stage select --implementation original` | 保存全部候选；训练选择只用旧主面板。|
| 正向解释/敏感性 | `forward/explain_and_audit.py --stage stability/explain`；`metric_sensitivity.py`；`final_profile_sensitivities.py`；`summarize_forward.py` | 解释不反改类别；D10 保持 B8 选择的 family/K。|
| 反向几何测量 | `reverse/discover_reverse_types.py --stage geometry` | 默认读恢复的 `clusters/assignments.csv`、`records_geometry.csv`，建立历史人员对和几何候选。|
| 反向发现 | `reverse/run_discovery_batch.py --events <common_events.csv.gz> --jobs 1 --implementation original` | 分配互不重叠的外折；缓存完成折不会被默默重新拟合。|
| 单折反向发现 | `reverse/discover_reverse_types.py --stage discover --events <...> --folds FULL,2t7WUuJeko7` | 可指定折；训练面板默认 `Pro_exact_fixed_background_v1`。统一入口不改此默认，不使用 `--force` 清场。|
| 反向汇总/解释 | `reverse/discover_reverse_types.py --stage consolidate`；`analyze_partition_stability.py`；`explain_reverse_types.py` | 由每折正式表合并，预测仍可按折存。|
| 反向可读交换表 | `reverse/make_exchange_summaries.py` | 在反向稳定性与解释之后生成 FULL 人员表、类成员稳定表、选择频数和规则特征使用表；只汇总已有输出。|
| 共同评价 | `assessment/evaluate_common.py --stage predict/summarize/all` | `predict` 重校准，`summarize` 读取已有 wide 概率，`all` 顺序完成；不再选择人员类别。|
| 组队与敏感性 | `assessment/selection_and_classes.py`；`additional_sensitivity.py`；`metric_and_rule_sensitivity.py` | 最后一席质量/时间收益与互换性分开；直接房间关系、重复端点对、四节点和 D10/解释规则分别计算。|
| 冻结后诊断 | `assessment/final_diagnostics.py` | 在上述共同评价与最后一席结果之后执行，重算成对策略差、实际图覆盖和来源条件校准；校准仍留出目标建筑，并保留原函数概率 parity。|
| 联合画像与报告表 | `assessment/report_tables.py` | 在四节点链、前向 FULL 画像及反向类友稳定表之后执行；输出 60 人联合画像、共同 164 图/3,936 链/15,744 事件的四节点表、固定 K 消融以及端点完整性/时间覆盖。支持量来自当前冻结事件。|
| 代表案例 | `assessment/select_cases.py` | 只形成事后展示目录，不修改模型。|
| 单个事件几何导出 | `events/export_event_cases.py --event-id <event_id> --out <目录> --selection-description <说明>` | 使用完整原生状态；省略状态的精简包须先重放相关 pool。|

反向 `--stage geometry/discover` 还可显式传 `--assignments`、`--records`、`--splits`、`--output`；解释脚本可传 `--classes`、`--features`、`--feature-domains`、`--output`。这些参数是路径覆盖能力，不授权混入不同冻结输入。正式复现应使用统一布局及合同中的 SHA。

已有 `repair_aggregate_exports.py`、`repair_prediction_exports.py`、`repair_analysis_input.py` 是本轮特定导出故障的可读修复证据，部分脚本会断言确实存在特定坏前缀。**它们不属于正常重放顺序**，不能对健康新输出机械执行。遇到新的坏导出，应保留现场，先根据具体错误决定修复或在新目录重跑。

## 6. 大缓存如何重建，什么可以不信任

- 正向 `event_predictions.csv.gz` 为 4,013,324 行长表。`forward/discover_forward.py --stage select` 可由冻结候选、训练内选择和精确事件重建；共同验收并不依赖该表，而是从逐折类重新校准生成 `assessment/EVENT_PREDICTIONS_WIDE.csv.gz`。
- 反向 `results/folds/<fold>/predictions.csv.gz` 的 22 折大型重复缓存从精简包省略，全部候选类、保存校准器和选择结果继续保留。正常恢复使用通用 `reexport_reverse_predictions.py`，从冻结逐折类/校准/COMPLETE 与共同事件重导指定折或全部折，不重拟合类型、不重选 K、不依赖原预测或坏前缀；精确命令、原子完整校验和已运行的小折验收见 [反向预测重导说明](README_REEXPORT_REVERSE_PREDICTIONS_ZH.md)。`results/PREDICTION_MANIFEST.json` 保留原逐折位置和历史 SHA；重导输出的身份与概率应一致，gzip 字节不作相同承诺。共同验收直接使用每折 `classes.csv.gz`，不需要拼接这个大长表。
- `events/native_runs/pools/<pool_id>/states.json.gz` 及 `request_results.json.gz` 是原生状态和质量/时间分项。精确端点请求在 `REQUESTS.json.gz`，原始点和参考在恢复区 `fusion/INPUT_SNAPSHOT.json.gz`；`run_events.py --stage full` 在空缓存目录重新生成。保留相同团队的多个请求 ID，不把它们当新真人。
- `events/native_runs/team_results.csv` 是端点请求汇总，当前未压缩约 150 MB，须与被省略的逐池大状态区别对待。`aggregate` / `refit` 明确复制此表；`fresh` 通过原生 `consolidate()` 重建。`report_tables.py` 只读取身份、完整性、缺失时间和失败原因九列，但本入口保持原完整表，不删列或改变其值。
- 逐池 `events/comparisons/<pool_id>/events.csv.gz` 可以从原生状态通过 `--stage compare` 重建，再用 `--stage merge` 合并。`common_events.csv.gz` 则足以开展人员分类与多数共同评价，无需先取回原图。
- `forward/feature_fits/`、训练集标签和人员对距离、反向人员对关系等都是由固定训练建筑清单及代码生成的缓存。新的 `refit` 工作区不复制这些本轮拟合缓存；续跑才会使用已验证的成功缓存。

数值、成员、事件身份和支持口径应重现；gzip 时间戳、浮点打印尾数、运行耗时、进程顺序和历史原始日志不承诺字节相同。默认入口对冻结源做字节 SHA 校验，对重算结果应使用对应事件/人员/折键和数值容差核对。

## 7. 交换字段与必要边界

完整机器可读合同为 `EXCHANGE_FIELD_CONTRACT.json`，事件几何分项的细合同继续使用 `../events/FIELD_CONTRACT.json`。

共同类别键为 `(heldout_building, method_id, difficulty, worker_id)`。源正向 `difficulty=all` 映射为 `global`；中文难度映射为 easy/medium/hard，仅改表示。FULL 的空 `heldout_building` 映射为字面 `FULL`。类号只在同折上下文有意义，跨折采用共类人员对或 ARI，不能直接比较“C01”。unknown 不作为一个共同能力类。

共同替换事件键是 `event_id`。a/b 按人员 ID 字典序冻结，有符号质量变化是 **B−A**；随机、Q 或类别政策选择 A/B 的方向需单独读取。两侧必须保持同图、同条件、同 k、同背景和同参考。新增四节点原字段是 `events.chain_id`，评价字段 `nested_chain_id` **直接复制这个原值**；不能按 k、图或同建筑另造链，也不能把旧面板空链伪称跨 k 嵌套。

失败团队留在全部尝试分母；任何一端失败时联合稳定为 False，而缺失 Q、几何或时间组件保持缺失，不补零。联合稳定阈值只是共同参考，还需报告质量有符号/绝对变化、范围、节点、连接、上下几何和失败。类内没有显著差异不能证明实际相近。

类别和参数选择只用目标建筑之外的旧主面板；新增面板不进入类别发现。验证建筑实际 Q、点数、簇和票数属于作答后信息，只能进入明确标注的 oracle/条件解释。参考用于历史训练质量和结果评价，不能按测试输出重新选择参考。

Q、时间与行为的分母不同：库存 10,439、正式 Q 7,302、普通 Manual Q 5,719；人员库存 62 ID、Q 画像 60 人。来源时间与同目标时间分开，不能填补；旧确认与新报告 Semi 错误分层，修改不等于修好；scope 倾向与有限 gold 正确性分开；定向审核不能外推总体错误率。同一严重事件不再通过净改善、Q 和排除重复累计处罚。

推断支持主要按图和建筑；多个背景、k、别名或重复端点请求不是独立真人。直接同房关系只用已有支持关系，不通过同建筑或传递关系扩大。

## 8. 本入口的实际检查证据

`ENTRY_POINT_CHECKS.json` 记录本入口的独立检查：帮助页退出成功；三层计划均能解析当前输入；已有目标目录拒绝执行且哨兵文件原样保留；events/reverse/assessment/forward 的 Python 源码通过语法解析。新增两份汇总的逐项读入依赖与复制/前序生成顺序也做了检查，见 `MINIMUM_LAYOUT.json` 和入口检查收据。三种昂贵层级没有为了测试这个编排器再次整体运行，避免把已有研究的完成收据误写成一次新的完整 wrapper 重放。

可重新执行这些编排检查（只更新入口检查和最小目录清单，不运行科学步骤）：

```bash
python work_personnel_typing_A_20261019/reproducibility/check_replay_entry.py
```

实际科学计算的收据来自各阶段自己的目录：事件 `FULL_RUN_RECEIPT.json`、正向 `FINAL_EXPORT_COMPLETE.json`、反向每折 `COMPLETE.json` 和相关完整性收据、共同评价的 `ASSESSMENT_RECEIPT.json` 等。工作区运行入口另写 `WORKSPACE_PREPARATION.json`、逐阶段日志和 `REPLAY_RUN_RECEIPT.json`，逐项记录新执行与续跑，不把缓存复用称为 fresh。
