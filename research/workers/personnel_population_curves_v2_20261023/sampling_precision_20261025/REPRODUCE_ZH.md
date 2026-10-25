# 复现入口：随机顺序抽样精度补充

## 版本与解压位置

真人 v2；使用的 main 为 `40d0fe62dc62f6f6c12723af10195b7abb7bc9fe`。

本轮所有包采用同一仓库内前缀：

`research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/`

先取得该提交的仓库，按原人口包的 `README.md`、`LARGE_TABLE_STORAGE.json` 恢复其正式大表。需要的原文件、SHA256和大小列在 `inventory/NECESSARY_SOURCE_FILES.csv`。原来的 `source_original` 截断追溯文件不作为本轮计算输入。把本轮 P01、P02 和 P04 解压到同一仓库根；查看全身份票账时再加 P03 几何分包。无需复制原图全集、环境文件或其它同房大表。

- **P01**：已冻结的精确种子、顺序、前缀、团队请求、有限边际目录，以及可执行的冻结方法闭包。第2版修正策略顺序元数据，原件与更正回执仍保留。
- **P02**：本轮实际新增标量、轻量几何、全部新增前缀值及精确边际结果。分片是完整 gzip 流，并非压缩文件的字节截断。
- **P03**：新增原生端点的完整状态、身份票账及连接，按体积拆包；一般统计和几何波动复算不需要它们。
- **P04**：最终报告、所有精度/策略/几何分析程序、完整分析结果、图表和三组有限边际案例。后处理程序的最终版本以此包为准。
- **P00**：正式追加前对原24条的诊断及预算冻结记录，可用于追溯，不替代最终新旧比较。

各包实际文件、大小和校验记录见 `CURRENT_FILES.csv` 与最终下载清单。P03 只含主原生执行的端点；正式设计命中的2个本轮计时端点，其完整状态在 P01 的 `engine/benchmark/`。其它计时队不进入主分析。

## 1. 恢复本轮统一表

以下从本轮目录执行。路径仅为位置参数，不应改动团队键、种子、参考、资格或评分。

```bash
python engine/restore_table_shards.py \
  --manifest new_endpoints/TABLE_SHARD_MANIFEST.json \
  --output new_endpoints
```

恢复器读取每个分片到 gzip 结尾，检查行数、字段及语义哈希。CSV合并只保留一次表头；恢复后的压缩字节可以因压缩头不同而变化，字段字符串、JSON对象值和行顺序必须相同。

## 2. 重算自然路径统计

设 `HOHONET_POPULATION_ROOT` 为固定提交内的原人口研究目录；`HOHONET_STUDY_ROOT` 为本轮目录。依赖见 `engine/requirements.txt`，分析另用 SciPy 与 Matplotlib，实际版本在最终环境记录中。

```bash
python analysis_precision/analyze_new_natural_precision.py \
  --old "$HOHONET_POPULATION_ROOT/stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz" \
  --old-scalars "$HOHONET_POPULATION_ROOT/results/ENDPOINT_SCALARS.csv.gz" \
  --new new_endpoints/NEW_PREFIX_VALUES_COMPACT.csv.gz \
  --focus analysis_precision/FOCUS_PRESELECTION_OLD24_RMS.csv \
  --exact new_endpoints/EXACT_MARGINAL_VALUES.csv.gz \
  --out analysis_precision/new_results --bootstrap 2000
```

该步骤没有新融合。原24、独立新24、合并48与重点96由实际成员及批次连接；固定全图主比较只用48。完整路径重抽与建筑重抽分开；重点独立新72另存条件描述。P10、有限总体标准差及少量门洞不可评分重抽的处理见 `analysis_precision/METHODS_AND_REPRODUCE_ZH.md`。

## 3. 重算四种优先进入策略

```bash
python analysis_policy/analyze_policy_precision.py \
  --old "$HOHONET_POPULATION_ROOT/stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz" \
  --new new_endpoints/NEW_PREFIX_VALUES_COMPACT.csv.gz \
  --old-endpoints "$HOHONET_POPULATION_ROOT/results/ENDPOINT_SCALARS.csv.gz" \
  --new-endpoints new_endpoints/NEW_ENDPOINT_SCALARS.csv.gz \
  --out analysis_policy/results --replicates 1000 --seed 2026102511
```

共同范围为四策略都存在且 N≥20 的157个普通Manual池，和自然 N≥30 的157图不是同一清单。每图原8、新8和合并16个base；同base、同人数、同最终人员池比较。质量差条件于两队共同可评分，失败分母包括全部非延期尝试。劳动时间要求成员时间齐全、正值且双方来源语义相同，详见字段合同。

## 4. 几何与图表

几何程序使用旧保存几何与本轮轻量几何，命令见 `analysis_geometry/GEOMETRY_METHOD_ZH.md`。统计量是同一人数下两支独立自然团队间的几何差异；其路径jackknife与固定图片/建筑的汇总保持单位一致。完整精确边际按有限团队全集计权，几何V分母为M²。

在自然、策略和几何分析完成后：

```bash
python make_key_tables.py --root .
python make_precision_figures.py --root .
python build_report.py --root .
```

图表导出相应CSV和可分享的PNG/PDF。中文字体可通过 `HOHONET_CJK_FONT` 指定。VFua-04的代表案例程序只重绘已保存的几何与票账，不增加融合。

## 5. 从原答重新执行新增端点（非日常复核必需）

精确实际设计已完整保存，不需要重新选择重点池或种子。执行：

```bash
python engine/native_population_runner.py \
  --requests design/NEW_NATIVE_ENDPOINT_REQUESTS.csv.gz \
  --output new_endpoints --jobs 6 --chunk-size 200

python engine/compile_precision_results.py \
  --base . --repo "$HOHONET_REPOSITORY_ROOT"
```

`engine/frozen_repo/` 是真实恢复的冻结方法和输入闭包；关键原生方法与本轮固定main逐字节一致。`executed_native_population_runner_20261025.py` 另存实际启动源码，当前可移植入口只调整默认路径。主实验新增端点和计时批次分开，全部尝试的状态保留。已有端点不重复融合，同一团队跨顺序的访问次数仍在路径表中。

## 6. 验证实际附件

`package_and_verify.py` 对ZIP实际成员读取CRC到结尾，并继续解压其中每个CSV/gzip、JSONL/gzip到结尾，检查字段数与行数。`verify_downloaded_associations.py` 读取指定的已下载P01/P02（可加P03），逐项核对：精确成员前缀、全部路径、端点来源、新标量与轻量几何键、前缀Q及精确边际权重。

```bash
python package_and_verify.py --zip /path/to/downloaded-package.zip \
  --receipt /path/to/readback.json

python verify_downloaded_associations.py \
  --zip /path/to/P01.zip /path/to/P02.zip \
  --out /path/to/association_readback.json
```

若P02分为多包，应把全部P02路径传入同一 `--zip`；若检查全部P03，加 `--check-full-geometry`。本轮交付验证使用实际保存后取回的文件，记录见 `verification/`，不是只核查打包前目录。

## 研究台连接

`pool_id` 固定图片/条件/参考/人员池；`path_id, k` 固定一次进入过程；`team_key` 固定实际成员集合；`object_id` 接回真人原答。`version/batch` 是抽样批次，不能当成人员类别或难度。`HYBRID48_IMAGE_CURVES.csv.gz` 可用作边界精确、中段48条的采用结果，但原24及配对人数变化表仍保留。缺Q、延期、失败、参考状态各自保留。字段、权重和状态含义详见 `FIELD_CONTRACT_ZH.md`。

## 7. 有限P10定义诊断及本次元数据更正

`python analysis_precision/p10_definition_sensitivity/derive_p10_definition_sensitivity.py --base .` 从已完成的精确目录和抽样结果计算两种分位参考，不新增融合。报告生成还需要Markdown（本轮3.7；或可用Mistune），实际依赖记录见ENVIRONMENT.json和requirements_analysis.txt。

P01正式顺序采用第2版。`engine/correct_policy_order_metadata.py` 可从保留原件与冻结前缀重建更正；正式清单和当前注册代码均已更正，不需要日常复现前再次运行。下载关联核验会对实际策略顺序、entrant及团队前缀逐项断言，不能跳过或以原自然顺序替代。
