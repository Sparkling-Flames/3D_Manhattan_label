# 人员分类与有效换类续研：复现与恢复

本说明对应 `personnel_exchange_closure_20261022`。**底层输入为真实数据 v2；目录或方法名中的 v3 仅表示此前研究轮次。** 默认复用已交付的精确团队端点，不重新融合和评分。分类标签、目标楼外历史、A/B/C 成员和实验阶段均保留原身份。

## 1. 三种复现层级

| 目的 | 输入 | 操作 | 是否调用融合／评分 |
|---|---|---|---|
| 重聚合主表、分项、风险与图楼支持 | 已交付完整 `EVENTS_COMPLETE`、策略结果和小输入 | 第 3 节的汇总命令 | 否 |
| 从端点重新构成完整逐事件结果 | 去重端点全集、冻结 REQUEST／事件、楼外标签和历史 | 第 2 节恢复批次，再按第 4 节评价 | 否；会重算两队之间的几何差异 |
| 可选复演实际融合与质量计算 | 冻结 v2 `INPUT_SNAPSHOT`、评分 ZIP、原 REQUEST、原代码和小缓存 | 第 5 节原 native runner | 是，仅在独立工作副本中主动运行 |

第一层足以复核报告的汇总，第二层可追溯每个事件的来源与三队差值。完整端点已经交付，不需要把每个事件用到的同一团队再计算一次。人员加入顺序没有在这一交付步骤中展开。

以下命令均从 **仓库根目录** 执行。路径示例使用本轮实际目录；下载后可将仓库放到任意位置，只需保持仓库内的相对层次。

```bash
cd /workspace/scratch/fe955c3c772c/HOHONET
HOHONET_STUDY=research/workers/personnel_exchange_closure_20261022
```

## 2. 从去重全集恢复原批次

父目录统一交付：

- `delivery/endpoints/ALL_REQUIRED_ENDPOINT_SCALARS.csv.gz`：101,092 个唯一团队，完整质量、结构、时间、资格和失败状态。
- `delivery/endpoints/ALL_REQUIRED_ENDPOINT_GEOMETRY.csv.gz`：相同 101,092 个键的几何，包括失败时缺失的几何状态。
- `delivery/endpoints/ENDPOINT_SOURCE_INDEX.csv.gz`：端点原来源与本轮新算／旧复用身份。
- `delivery/endpoints/DELIVERY_RECEIPT.json`：原始字节数、SHA256、行数与状态数量；该回执是交付总量的权威来源。

该全集包含中央 101,093 条批次引用所对应的 101,090 个唯一团队，以及两条中央 REQUEST 之外的既有 Semi 连续 QT 控制端点。重复引用不会增加唯一端点数；两条旧控制不会被冒记为新融合。

先核对所有请求键、成员串、人数和标量／几何身份：

```bash
python "$HOHONET_STUDY/integration/reproduce/restore_endpoint_batches.py" --check-only
```

检查成功写入 `integration/reproduce/RESTORE_CHECK_RECEIPT.json`，必须满足 `missing_scalar_keys=0`、`missing_geometry_keys=0`。这一步读取全部端点，保留失败，**不调用融合或质量评分**。

在解压工作副本中恢复可供既有评价器读取的批次：

```bash
python "$HOHONET_STUDY/integration/reproduce/restore_endpoint_batches.py"
```

工具逐个读取 `native/batches/*/REQUESTS.csv.gz`，按**完整 `team_key` 与精确成员**投影到该批次所需的 `ENDPOINT_SCALARS.csv.gz` 和 `ENDPOINT_GEOMETRY.csv.gz`。所有写入先生成临时文件，通过全集键与成员校验后再原子发布。失败端点不被删除，缺失评分不填零，CSV 数值文本不重新浮点格式化。

已有完整批次默认保留并核对键集合；若明确需要重建，可增加 `--overwrite`。重建时若原 `COMPLETION.json` 已存在，工具将它保存在 `ORIGINAL_NATIVE_COMPLETION.json`，新回执明确标注从交付全集恢复。重新压缩后的字节 SHA 可能与旧批次不同，不能拿压缩字节差异冒称评分或几何差异。

两条旧 Semi QT 控制单独恢复到 `native/batches/restored_delivery_extras/`。该目录有 compact 端点与恢复回执，**没有新建 native REQUEST**；它是历史补充视图。Semi 评价器会自动读取。恢复工具也支持把结果写到独立目录：

```bash
python "$HOHONET_STUDY/integration/reproduce/restore_endpoint_batches.py" \
  --output-dir /tmp/hohonet_restored_batches \
  --receipt /tmp/hohonet_restored_batches_receipt.json
```

独立目录模式会复制每批冻结 REQUEST，方便检查；正式评价器仍读取研究目录的 `native/batches/`，请保持该标准布局。无需交付原 `native/runtime` JSON 大缓存。Manual 的 `evaluate_registered.py` 已加入 compact 批次读取后备路径，沿用原 `typed` 解析器与事件公式；原运行缓存存在时仍优先复用。

## 3. 只用完整事件重新聚合

### Manual 联合分类

主阶段与后续语义条件检查分开。阶段 B 路径为 `phase_b_highq_slower`；它是在阶段 A 观察后选择的条件，并用新背景进行内部检查，不称新的建筑盲测。

```bash
python "$HOHONET_STUDY/manual_joint/summarize_results.py"
python "$HOHONET_STUDY/manual_joint/summarize_results.py" \
  --study-dir "$HOHONET_STUDY/manual_joint/phase_b_highq_slower"
python "$HOHONET_STUDY/manual_joint/summarize_coverage.py"
python "$HOHONET_STUDY/manual_joint/close_common_abc.py"
python "$HOHONET_STUDY/manual_joint/analyze_target_swaps.py"
python "$HOHONET_STUDY/manual_joint/build_final_outputs.py"
python "$HOHONET_STUDY/manual_joint/plot_results.py"
```

`close_common_abc.py` 在同一三队共同可评分行上重聚合 B−A、C−A、C−B 与 C−(A+B)/2，并检查有符号差值闭合。它和原逐对可评分结果并存，避免把不同分母的均值误当可直接相减。

### Manual 结构分类

```bash
python "$HOHONET_STUDY/structure/analyze_structure.py"
python "$HOHONET_STUDY/structure/summarize_common_abc.py"
python "$HOHONET_STUDY/structure/summarize_change_loci.py"
python "$HOHONET_STUDY/structure/finalize_structure.py"
```

使用合并的冻结结构事件，保留 n20 主层、固定成员的 n 路径、m 路径和新来源时间子集身份。全类人数向量覆盖与具体成员／背景覆盖不是同一个分母。

### Semi 自身联合分类

```bash
python "$HOHONET_STUDY/semi/summarize_semi_closure.py"
python "$HOHONET_STUDY/semi/analyze_nested_n.py"
python "$HOHONET_STUDY/semi/finalize_semi_deliverables.py"
```

Semi 的 13,882 行有向事件对应 6,941 个物理 ABC；其中主层为 13,000／6,500，配置补齐层为 882／441。镜像 A/B 仍保留在精确事件中，汇总时按既有层级与物理事件身份处理，不能把镜像当额外独立图片。各分项、时间、失败有各自真实分母。

## 4. 由已算端点重新生成逐事件表

先执行第 2 节恢复，再运行：

```bash
python "$HOHONET_STUDY/manual_joint/evaluate_registered.py" --require-complete
python "$HOHONET_STUDY/manual_joint/evaluate_registered.py" --require-complete \
  --study-dir "$HOHONET_STUDY/manual_joint/phase_b_highq_slower"
python "$HOHONET_STUDY/structure/evaluate_structure.py"
python "$HOHONET_STUDY/semi/evaluate_semi_closure.py"
```

随后按第 3 节重聚合。这些评价器使用已计算的端点数值，重构三队差值、两队几何距离、失败与记录时间比较；不会把 Manual 与 Semi 原答混在一支团队中。

评价器默认续接已完成池。若要从端点完整重建而不是复用分池结果，请在另一个解压工作副本中操作：保留精确登记表、小输入与代码，**不复制** `manual_joint/results/`、`manual_joint/phase_b_highq_slower/results/`、`structure/results/` 和 `semi/completed_pools/` 的派生检查点。原交付完整事件保持独立存档。每池完成后即时保存，因此中断不会丢失所有已完成结果。

## 5. 可选：从冻结请求复演 native 端点

这是可选的原计算复演，重聚合不需要它。请使用独立工作副本，保留 `native/*_BATCH_PLAN.csv` 和每批 `REQUESTS.csv.gz`，不复制原 `native/runtime/` 与批次端点／完成回执。原 runner 看到 `COMPLETION.json` 会跳过已完成批次，这是恢复设计。

```bash
python "$HOHONET_STUDY/run_native_closure.py" cache
python "$HOHONET_STUDY/run_native_closure.py" run --batch manual_001 --jobs 3
```

`cache` 把既有 compact 历史端点恢复成运行时可读的小池缓存，不融合。其输入包括旧 `joint_exchange/ALL_USED_ENDPOINT_*`、原旧扩展批次（若已恢复）和 `ADDITIONAL_CACHE_PAIRS.json` 所指的两个约 15 KB 合计小文件。按原 REQUEST 中的 `cached` 标记精确复用，剩余请求调用冻结原引擎。需要原样完成某一已登记系列时可分别运行：

```bash
python "$HOHONET_STUDY/run_native_closure.py" run-all --prefix manual --jobs 3
python "$HOHONET_STUDY/run_native_closure.py" run-all --prefix jointb --jobs 3
python "$HOHONET_STUDY/run_native_closure.py" run-all --prefix structure --jobs 3
python "$HOHONET_STUDY/run_native_closure.py" run-all --prefix mpath --jobs 3
python "$HOHONET_STUDY/run_native_closure.py" run-all --prefix semi --jobs 3
```

不要为复现本轮重新搜索全部类别、改变标签或重新展开未登记的理论组合。`register_design.py`、`register_phase_b.py`、`register_structure.py`、`register_m_paths.py`、`register_semi_closure.py` 与 `register_configuration_completion.py` 已交付以解释和重建原登记逻辑；原冻结表本身才是本次端点身份清单。

## 6. 冻结代码、数据和版本

`INPUT_CODE_MANIFEST.csv` 按实际文件提供角色、仓库相对路径、当前绝对路径、字节数、SHA256、版本与定位来源。`collect_reproduce_manifest.py` 只调用 `gs.setup_engine()` 取得实际模块位置，并读取已加载的 `sys.modules`；它没有扫描整个仓库，也没有调用融合或评分。

| 项目 | 实际来源／合同 |
|---|---|
| main 与 PR #23 | 已合并，提交 `8bfd3e476bd5ae6edc1424e2c8ea07dd2f69a235` |
| 上轮 v3 来源 main | `324dba44d0a82d9d64a62965f2e549ee05165417`；仅指研究阶段 |
| 本轮适配器 | `run_native_closure.py` → 旧 `expanded_blocks/run_native.py` → `global_study.py`、`run_endpoints.py` |
| 冻结融合 | `pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/fusion_engine.py` 与 `pool_io.py` |
| 实际单队执行 | `personnel_interchangeability_20261020/analysis/composition/fusion_runner.py` |
| 质量与几何辅助 | 同目录 `summarize_grid.py`、`geometry_diagnostics.py`；后续 `audit_corner/corner_distance.py` |
| 评分包 | `research/statistics/b8l2_shared_v6_20261016/inputs/measurement_engine.zip`，13 个归档成员，另有 `working_models.py` |
| 冻结输入 | fusion 目录 `INPUT_SNAPSHOT.json.gz`；`schema=v2_real_fusion_inputs_v1`、`data_release=v2`、输入提交 `82c6164b0d4630de5316199c92aa405930973168` |
| 快照转换 | 只改字段名；原终稿几何、上下点绑定与声明环序按原值继承；`N1_applied=False` |
| 融合内部参数 | `WORKING_GAP=7.5`；不可与整份原答的 9°／12°分簇或参考诊断阈值混同 |
| 记录时间 | `personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz`；单位秒，保留来源字段 |
| 实验楼外标签 | `personnel_useful_taxonomy_v3_20261021/taxonomy/ALL_METHOD_LABELS_LOBO.csv.gz`，各线另存实际筛选与训练中心 |
| 结构语义对齐 | 旧 `screening/CLASS_TRAINING_ROLE_MAP.csv.gz`；不能按 K 号跨折拼接 |
| 连续基线与历史 | `personnel_global_composition_20261021/multivariate/continuous_features_lobo.csv.gz` |

质量主算法仍为 B8L2，D10 为敏感性。人员资格、图像资格、参考版本、缺失和融合失败均沿用原合同。时间是库存同来源记录总秒数之和，不是新测生产耗时；缺时间、缺历史机会或缺质量不填零。全数据描述标签与楼外实验标签分开。

快照 SHA256 为 `83179b9842d06916b105d80ff181918c223e4fee2073f425f9825db124ec11d7`。其余代码和输入使用清单中的完整 SHA，而不是只凭文件名识别。原图只在少量机制案例使用，重新聚合无需下载原图全集。

## 7. 环境与交付边界

本轮实际环境：Python 3.12.14、NumPy 2.3.5、pandas 2.2.3、SciPy 1.17.0、Shapely 2.1.2、scikit-learn 1.8.0、Matplotlib 3.10.8、Pillow 12.3.0。平台为 Linux x86_64／glibc 2.39。完整版本、线程变量和冻结合同见 `ENVIRONMENT_AND_CONTRACT.json`。

native 适配器将 `OPENBLAS_NUM_THREADS`、`OMP_NUM_THREADS`、`MKL_NUM_THREADS` 设置为 1；`--jobs` 决定进程数。交付不包含虚拟环境。已有事件重聚合主要依赖 pandas／NumPy；重算几何及可选 native 复演还需要清单中的仓库模块和评分依赖。

历史文件下载入口是相邻的 `integration/historical/HISTORICAL_DOWNLOAD_INDEX_ZH.md` 与 CSV：31 份旧完整事件、56 个已恢复旧端点分片、历史代码／小输入包保留各自阶段身份。旧均匀选队收益与本轮匹配替换结果分开解释，26×2 变量域覆盖引用原台账，不在本复现步骤重做候选筛查。

清单生成命令：

```bash
python "$HOHONET_STUDY/integration/reproduce/collect_reproduce_manifest.py"
```

本目录仅提供小代码、说明、版本与核对回执；完整事件和去重端点由统一交付目录提供一次。无需另打重复大缓存 ZIP，也不复制原图全集。
