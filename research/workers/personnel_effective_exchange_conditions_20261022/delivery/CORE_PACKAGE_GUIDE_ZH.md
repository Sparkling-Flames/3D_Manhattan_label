# 核心代码、标签与必要小输入包

本说明只组织已经完成的研究与可复现输入，不新增分类、融合、评分或事件搜索。底层仍为真实 **v2**；`personnel_useful_taxonomy_v3_20261021` 中的 v3 是此前研究轮次号。

## 1. 两个新包各装什么

| 包 | 内容 | 正常用途 |
|---|---|---|
| `CORE_RESEARCH_CODE_AND_SMALL_EVIDENCE.zip` | 本轮关键 Python 代码；三家族冻结 ALL/LOBO 标签、中心、成员与未知原因；旧方法身份和映射；旧事件筛查的精简正式表；联合专题与扩大专题的正式汇总；代表案例的原答、冻结参考、原生状态、票账及图 | 核心选入文件已在本目录归档；原包中 171 个被标为中间/重复输入的文件未另行复制，原 ZIP 保留作来源包 |
| `SMALL_ANALYSIS_INPUTS.zip` | 253 份精确冻结事件请求；253 格 `PANEL_SUMMARY.csv.gz` 和 253 格 `COMPLETION.json`；联合专题冻结请求；原生批次请求与完成回执；25 大事件分片的计划和小回执 | 已按原路径解压到本目录，供重聚合脚本读取 |

两个包中的有效路径都以 `research/workers/...` 开头。`SMALL_ANALYSIS_INPUTS.zip` 的 850 个文件已完整解压到仓库根目录，合计 50,646,993 字节；校验回执见 [SMALL_ANALYSIS_INPUTS_RECEIPT.json](SMALL_ANALYSIS_INPUTS_RECEIPT.json)。`CORE` 包按 `SOURCE_SELECTION.json` 的选择归档；171 个 `source_package_only` 文件保留在来源 ZIP，没有静默丢弃或重复展开。完整事件与端点仍需独立交付，不在这两个包中重复。包内也没有 runtime、PARTIAL、临时恢复副本、虚拟环境、原图全集或嵌套 ZIP。

`CORE_PACKAGE_INPUTS.csv` 逐文件列出路径、所属包、角色、字节数与 SHA256；`delivery_mode=external` 表示独立交付或仓库依赖。来源包 SHA、文件数及已核验的清单项见 [CORE_PACKAGE_RECEIPT.json](CORE_PACKAGE_RECEIPT.json)。清单自身不记录循环自哈希，其 SHA 由回执保存。

扩大专题的 253 份请求只保留分格原件，没有重复收入四张合并请求表。完整请求是复现“哪些人、哪些背景、哪些实际换人数”的输入，253 份小摘要是便携重聚合的必要输入；两者已随 `SMALL_ANALYSIS_INPUTS.zip` 归档，且不是新的实验结果。

## 2. 旧代码包与仓库依赖

本轮新脚本继续调用冻结的旧模块。已有旧包的准确名称为：

`research/workers/personnel_useful_taxonomy_v3_20261021/integration/HOHONET_v3_复现代码与必要小输入_20261021.zip`

- 193 个文件，其中 143 个 Python 文件；1,294,016 字节。
- SHA256：`f4c1912f5163dfd3342adbaaeae658d4c90bf93b506038a31dd8b6e8d2b5c34d`。
- 它保持 `personnel_global_composition_20261021`、其 `continuation_20261021`、V3 等阶段的独立身份；也解压到同一仓库根目录。
- 它不包含 `tools/` 原生算法模块，也不包含原生 `INPUT_SNAPSHOT.json.gz`，因此不能用这个旧 ZIP 替代基础仓库和冻结原生输入。

输入 main 快照是 `324dba44d0a82d9d64a62965f2e549ee05165417`。原生输入继续保持 `82c6164b0d4630de5316199c92aa405930973168` 与模式 `v2_real_fusion_inputs_v1`：

`research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz`

其字节数为 1,464,097，SHA256 为 `83179b9842d06916b105d80ff181918c223e4fee2073f425f9825db124ec11d7`。main 与原生输入的合同衔接见前轮 `integration/NATIVE_CONTRACT_MAIN_IDENTITY.json`。本轮没有将新 main 身份冒充原生输入的原始提交，也没有替换 GT、资格、环序、参考或融合门槛。

具体代码和输入依赖列于本轮 `joint_exchange/INPUT_AND_CODE_DEPENDENCIES.csv`、`integration/INPUT_REFERENCES.csv` 及标签来源回执。主要旧模块包括 `global_study.py`、原 `event_kernel.py`、`evaluate_n20_abc.py`、`fusion_engine.py`、`pool_io.py`、`geometry_diagnostics.py` 和仓库 `tools/thesis_main/analysis/` 下的冻结评分/对应模块。旧标签、V3 面板、训练拟合与连续历史特征也保持原路径；普通重聚合不要求重新拟合这些文件。

## 3. 最轻量的可运行重聚合

核心选入文件与 SMALL 输入当前已在仓库中，无需再次解压来源 ZIP。完整复现还需取得独立的 25 份扩大事件表与相应完成回执，放回：

`research/workers/personnel_effective_exchange_conditions_20261022/delivery/expanded_events/`

该目录的最终 `EVENT_FILES_INDEX.csv` 与各分片 `*_COMPLETION.json` 是独立大表的定位、行数和 SHA 依据。253 份小格摘要/回执已经在 SMALL 包中。以下命令均从本轮研究目录执行：

```bash
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
python3 expanded_blocks/analysis/restore_event_inputs_from_delivery.py
python3 expanded_blocks/analysis/analyze_expanded_results.py --require-complete
python3 expanded_blocks/analysis/prepare_readable_results.py
```

恢复器只做流式读写，将原事件字符串、缺失和失败行恢复到 `analysis/rebuilt_event_inputs/`；重新压缩后的文件记录自己的 SHA，不伪造旧 gzip 字节哈希。统计程序在原逐格大表缺席时自动读取恢复路径。它利用 253 格、494 背景、390,208 个已登记事件，不运行新融合、评分或选类。

最终正式分析已经放在 CORE 包的 `expanded_blocks/analysis/FINAL_*`、`CANONICAL_*` 与 `*_FINAL_COMPLETE` 文件中。仅阅读结果不需要执行上述命令。扩大专题使用背景、图、楼的既定权重；不能改为全事件简单均值。

联合专题分别下载六张独立完整事件表，放回 `joint_exchange/`：`NATIVE_MANUAL`、`NATIVE_SEMI`、`CACHED_MANUAL`、`CACHED_SEMI`、`CROSS_MANUAL`、`CROSS_SEMI` 各自的 `_EVENTS_COMPLETE.csv.gz`。例如：

```bash
python3 joint_exchange/summarize_joint.py native manual
python3 joint_exchange/summarize_joint.py native semi
python3 joint_exchange/focused_native.py
python3 joint_exchange/focused_semi_native.py
```

这些步骤保持 Manual/Semi 分开，也保留全部失败记录和每项自己的可评分/时间支持。更全的命令、分项字段与 time 单位见独立交付的 `delivery/REPRODUCE_ZH.md` 和 `RESULT_SCHEMA_ZH.md`。

## 4. 从紧凑端点重建事件时，额外需要什么

联合专题的两个独立文件 `ALL_USED_ENDPOINT_SCALARS.csv.gz` 和 `ALL_USED_ENDPOINT_GEOMETRY.csv.gz` 覆盖 44,328 个唯一团队。扩大专题端点分别放回 `expanded_blocks/batches/joint_001`—`joint_003`、`expand_001`—`expand_025` 的 `ENDPOINT_SCALARS.csv.gz` 和 `ENDPOINT_GEOMETRY.csv.gz`；请求和小完成回执在 SMALL 包中。

```bash
python3 joint_exchange/evaluate_joint.py native manual
python3 joint_exchange/evaluate_joint.py native semi
python3 joint_exchange/evaluate_joint.py cached manual
python3 joint_exchange/evaluate_joint.py cached semi
python3 joint_exchange/evaluate_joint.py cross manual
python3 joint_exchange/evaluate_joint.py cross semi
python3 expanded_blocks/evaluate_expanded.py --jobs 2
```

这些命令使用已有端点计算原事件比较和几何差异，端点已齐时不需要 runtime，也不需要重新融合或重新评分。事件比较会加载前述旧几何/历史模块，因此要保留仓库结构和旧代码依赖。已有完成单元被跳过。普通复现不应运行 `run_native.py` 去重算已交付端点。

## 5. 标签、机制与时间口径

`CROSS_LABELS_ALL.csv` 是描述用全数据标签，`CROSS_LABELS_LOBO.csv.gz` 是评价用目标楼外标签；形成目标楼分类时同时排除该楼两条件。三个新家族和 M/SP/A2、QTD/Rnew2/F01、原单条件结构×QT各自保留方法与适用域；没有拼成一棵统一树。标签未知原因和机会支持原样保留，人员标签不自动授予正式组队资格。

CORE 包包含本轮小机制的精确原答、冻结参考、原生状态、对应/票账和 ERP/BEV/3D 对照。图像源取自既有 Release；包中保存取图回执和完成图，不复制原图全集。重新渲染需按回执另取对应原图、保留原路径。机制案例是事后选取的解释证据，不据少量案例估计总体频率。

时间有两种已声明的汇总口径：联合专题聚合对数时间比再转百分比；扩大专题保留既定的事件百分比算术分层均值，并在 `FINAL_TIME_AGGREGATION_COMPARISON.csv` 并列同支持几何口径。二者不是可随意互换的“同一百分比”；复现必须保留文件中的来源、单位、共同支持和分层权重。

## 6. 独立交付与明确排除

主整合报告、最终推荐条件表以及大事件/端点独立交付，CORE 不收入正在写作的 root 主报告，也不将其当作运行输入。已冻结的专题报告保留本阶段身份。`integration/RECOMMENDED_EXCHANGE_CONDITIONS.csv` 和配套 schema 在此打包时由另一作者独立保存，因此不在两个 ZIP 内。

这两个包没有把“有限子空间完整枚举”改称“全正式人员池穷尽”。精确全空间与实际覆盖仍由 `EXACT_FULL_SPACE_LEDGER.csv.gz`、canonical 覆盖表和实际成员请求说明。包的验证只检查所收文件的冻结身份、CRC、SHA 与完整性，不重新开展研究。
