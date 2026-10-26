# HOHONET 人数曲线全路径抽样追加：复现与接入

本轮仓库相对目录为：

`research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/`

ZIP 内已包含上述仓库相对路径。先将各包解压到同一个接收根目录 `DEST`，然后令 `STUDY=DEST/research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026`。不要把 ZIP 再解压到 `STUDY` 本身，否则会多出一层重复的 `research/`。`REPO` 指另一个已经检出指定提交的 HOHONET 仓库。交付不重复包含历史大表、完整仓库、原图全集或 Python 环境。

以下命令在本轮目录运行。先将前两行换成实际绝对路径；之后的`"$STUDY"`和`"$REPO"`是Shell变量，不是名为STUDY或REPO的目录：

```bash
DEST=/absolute/path/to/unpacked_delivery
REPO=/absolute/path/to/pinned_HOHONET_repository
STUDY="$DEST/research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026"
cd "$STUDY"
```

采用顺序为：S01 精确设计 → 全部 DATA_S1 / DATA_S2 新端点片 → 所需 S02／有限目录／原图案例包 → S11 完整分析表 → **最后解压 S10 最新报告代码包**。早期 S01、S02 中保留了其阶段代码身份，最后一步确保当前分析代码优先。S00 是计算前的历史快照，不是本轮复算必需包。所有文件以最终有效清单、包内相对路径和 SHA256 为准。

|需要做的事|最小交付依赖|
|---|---|
|独立阅读报告、查看已绘图|S10；其HTML已嵌入主要图像|
|重新整理最终关键小表或重画正式汇总图|S10 + S11；不用重跑融合或恢复逐路径bootstrap缓存|
|从实际进入顺序和端点重新统计|S01 + 全部DATA_S1/S2 + S10 + 指定main输入；S11用于对照已交付结果与提供正式支持索引|
|研究台打开具体团队的原答、参考及几何|S01精确关联 + 相关DATA分片 + 对应旧main依赖；S11提供完整分片索引|
|独立阅读六小池、近满员目录或原图机制案例|相应S02／FINITE_CASES／ORIGINAL_IMAGE_CASES；这些小包不替代全量设计和端点|

已取回的S05是完整策略子域的独立快照，无须重写。S10/S11已经分别纳入最终策略代码、报告和完整结果；同时保留S05时，仍最后解压S10，避免早期代码覆盖当前入口。

## 1. 固定输入

- 仓库：`https://github.com/Sparkling-Flames/3D_Manhattan_label`
- 实际 source main：`b9bcec809fbaec8ab055931a1abb7baa5db44dac`。
- 数据：已有真人 v2；沿用正式参考、资格、预处理、融合和 B8L2 / D10 评分。
- 母研究：`personnel_population_curves_v2_20261023`。
- 上轮精度研究：同目录 `sampling_precision_20261025`，以本次源提交中的 `LOCAL_ACCEPTANCE.md` 和 `local_audit/` 为准。
- 四种进入策略：原 V3_BEHAVIOR / V3_JOINT_QT 历史角色；本轮没有重新训练类别，也不是 DSTRUCT / RFUSE 策略验证。

`engine26/setup_from_main.py` 检查实际 commit，并按仓库原有大表清单恢复所需表。它复用完整文件，或从完整字节分片／逻辑行分片恢复；不会运行融合、修改 Git 或根据报告数字制造输入。

```bash
python engine26/setup_from_main.py --repo "$REPO" --study "$STUDY"
```

稀疏检出可能只留下 manifest 而没有实际分片。该脚本会列出精确缺件；应取出记录提交中的这些路径，不把本地未检出误称为远端缺失。原输入的 318,816 个标量、前轮 323,809 个标量及几何、403,376 个前缀值均可从指定 main 恢复。正式人数过程 04C 使用已恢复的完整版本；追溯用截断原文件不是本轮输入。

重做几何统计还会直接读取母研究中的`design/EXACT_ORDER_DESIGN.csv.gz`、`results/PREFIX_TEAM_LINKS.csv.gz`和`results/ENDPOINT_GEOMETRY.json.gz`。重做自然统计直接读取`stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz`。这些文件在指定main中已是完整文件，不由`setup_from_main.py`重新合成；稀疏检出时须一并取出。`setup_from_main.py`负责的字节／逻辑分片恢复范围以其回执列出的表为准。

## 2. 从已交付结果重新分析

只想从正式结果重新导出报告小表或策略对照图时，可直接使用S10/S11：

```bash
python report26/assemble_key_tables.py --base "$STUDY"
python report26/plot_policy32_Q_labor.py --base "$STUDY"
```

前一命令写`report26/key_tables/`，后一命令写`report26/figures/P02_policy32_Q_labor_support.*`及36行SOURCE表；两者都不重抽、不拟合、不融合。下面才是从精确路径重新做统计的较长流程。

按上述接收根目录与顺序解压设计包、完整新端点分片和分析代码包，先完成历史输入映射。全局逻辑表由逐池分片组成；任取一片不能代表全量。逐路径全字段值是可从精确设计和端点重建的工作缓存，不重复装入最终包；所有新增端点的完整标量和最终候选几何都已在 DATA 分片中保存。

```bash
# 复用已经登记并完成的精确端点，物化路径值；不重新选择人员。
python engine26/prefix_outputs.py --base "$STUDY" --prepare
python engine26/prefix_outputs.py --base "$STUDY" --stage 1
python engine26/prefix_outputs.py --base "$STUDY" --stage 2

# 自然路径：整条路径重抽，保留独立批次和重复团队出现权重。
python analysis_precision26/analyze_natural.py --root "$STUDY" --stage 2 --bootstrap 2000 --resume
python analysis_precision26/refresh_components.py --root "$STUDY" --stage 2
python analysis_precision26/analyze_natural.py --root "$STUDY" --stage 2 --compile-only
python analysis_precision26/summarize_natural.py --root "$STUDY" --stage 2 --bootstrap 2000
python analysis_precision26/exact_anchor_and_display.py --root "$STUDY" --stage 2
python analysis_precision26/plot_natural_precision.py --root "$STUDY" --stage 2

# 进入策略：从旧16、新16到合32；共同自然基准路径配对。
python analysis_policy26/analyze_policy32.py --base "$STUDY" --prepare-old
python analysis_policy26/analyze_policy32.py --base "$STUDY" --replicates 2000 --aggregate
python analysis_policy26/restore_named_loss_components.py --base "$STUDY" --replicates 2000
python analysis_policy26/report_policy_precision.py --base "$STUDY"
```

若从没有任何分析结果的新目录起算，完成上述逐池自然统计后，可运行`watch_natural.py --root "$STUDY" --stage 2 --bootstrap 2000`核对全部194池并生成`WATCH_COMPLETE.json`，再运行`finalize_natural.py --root "$STUDY"`完成汇总与正式`NATURAL_FINALIZATION_COMPLETE.json`。这两个脚本不会启动融合；已具备S11正式结果时无需为了阅读或提取小表重建它们。

正式194池完成标记已存在后，可生成最终紧凑读数与N05单图完整曲线：

```bash
python analysis_precision26/extract_final_natural_readout.py --root "$STUDY"
python analysis_precision26/plot_individual_full_curves.py --root "$STUDY"
python analysis_reporting26/extract_point_precision_readout.py --base "$STUDY"
```

N05只读已完成的自然统计与精确有限目录，不生成新路径。三个既定近满员案例与一个按最终低人数新旧差异选出的事后展示案例，其选择规则、完整候选排序、曲线及精确锚点均另存SOURCE表；此展示选择不参与抽样预算或停止决定。

几何统计的`--root`指向`analysis_geometry26/`，与自然统计的研究根不同；准确命令为：

```bash
POPULATION="$REPO/research/workers/personnel_population_curves_v2_20261023"
PRIOR_PRECISION="$STUDY/prior_recovered/research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025"
python analysis_geometry26/geometry_extension.py --study "$STUDY" --population "$POPULATION" --prior "$PRIOR_PRECISION" --prepare
python analysis_geometry26/geometry_extension.py --study "$STUDY" --stage 2 --jobs 1
python analysis_geometry26/summarize_geometry_extension.py --root "$STUDY/analysis_geometry26" --stage 2 --replicates 2000
python analysis_geometry26/render_geometry_results.py --root "$STUDY/analysis_geometry26"

# 沿用Q80/Q90的全部尝试达标率、同路径人数变化及建筑范围。
python analysis_reporting26/fixed_threshold_attainment.py --base "$STUDY"
```

Q80/Q90输出位于`analysis_reporting26/thresholds/`，主文件为`Q80_Q90_PER_IMAGE_K.csv.gz`、`Q80_Q90_PAIRED_INTERVALS.csv.gz`及`Q80_Q90_FIXED_SUPPORT_INTERVAL_SUMMARY.csv`。可评且达到阈值才计入达标事件；缺Q保持原状态，未把其质量填成零。人数变化保留同路径关联，使用解析路径MCSE与2000次建筑重抽，不产生新融合端点。独立有限案例的命令与几何字段见`analysis_geometry26/METHOD_AND_FIELD_CONTRACT_ZH.md`。所有统计模拟及bootstrap均不计为新增进入顺序；真实排列由精确设计表确定。

命名的 B8 / D10 损失分项由 `engine26/derive_frozen_blocks.py` 按仓库既有公式，从已保存的 `iou_2d`、`S_bottom_deg`、`dir`、`Hmean`、`Hcenter` 补齐。它们是无量纲惩罚项，越小越好，不是 0–100 分或可相加的百分比贡献。该补齐不改变主 Q、D10、参考、资格或任何共识端点；其来源见 `FROZEN_SCORE_BLOCKS_ZH.md`。策略的恢复分项另存 `analysis_policy26/restored_components/`，明确记录补齐后的共同支持，不用旧缺字段导致的缩小支持冒充完整比较。

## 3. 从精确设计重新运行冻结融合

只有需要重算实际共识端点时才执行本节。大约百万级新团队需要相应计算时间。已存在且通过键、输入 hash 和 EOF 检查的端点会复用；失败结果同样保留。

```bash
python engine26/execute_extension.py --base "$STUDY" --stage 1 --jobs 8
python engine26/execute_extension.py --base "$STUDY" --stage 2 --jobs 8
```

如果需要从种子重新生成同一设计，使用：

```bash
python engine26/generate_registered_design.py --base "$STUDY"
```

这不是重新抽一组“更好”的随机种子。登记文件中的 namespace、master seed、逐池种子和实际完整顺序均已保存。种子为十进制表示的 64 位无符号整数，读取时不得先转浮点数。`register_extension.py` 保存选择逻辑的来源；实际交付使用短事务的 `generate_registered_design.py` / `finalize_registration_shards.py` 导出，不使用早期未通过读回的长开文件导出。

## 4. 关联键和状态

| 研究对象 | 精确键 | 说明 |
|---|---|---|
| 图片人员池 | `pool_id` | 同时保留 image、image_id、building、condition、layer、difficulty、reference_id / version |
| 进入顺序 | `path_id` | 完整成员顺序、随机种子、批次、stage、new_index 均在设计表 |
| 路径人数点 | `path_id,k` | 原始抽样出现次数，不按 team_key 去重后算分布 |
| 精确团队端点 | `team_key` | 正式人员集合；标量、几何和缓存依赖均以此相连 |
| 原始人工答卷 | `member_object_ids` | 与 `member_workers` 逐一对应；保留冻结资格 |
| 策略自然配对 | `base_path_id` / `natural_base_path_id` | 同一自然顺序经历史目标成员优先的稳定分块得到策略顺序 |

详见 `engine26/FIELD_CONTRACT.json`。标量保存原始 score_status，并额外区分共识形成失败、已输出但不可评分、缺参考、未执行和两人设计暂缓。缺 Q 不填零。`geometry_available` 只说明有候选对象，不自动代表几何可用。满员重复路径指向一支确定团队；该团队失败时不能靠重复排列产生成功。

## 5. 数据包与逻辑完整表

`S01_exact_design` 保存全部真实设计与缓存／新增关联。`DATA_S1_*` 和 `DATA_S2_*` 保存新端点标量、对应最终几何、必要完整身份状态、逐片与逐池回执。分包按已完成池和体积组织，不按 Q 或失败筛选。

新端点标量的权威形式为：

`new_endpoints26/stage{1,2}/parts/<pool_id>/part_*.scalars.csv.gz`

相同片名的 `geometry_compact.jsonl.gz` 与标量的行数及 team_key 顺序一致。可选的 `full_state.jsonl.gz` 只对预先固定三个案例及 team_key hash 子样本保存，缺少 full_state 不代表融合失败。全部新端点都保存最终候选几何和状态。

`new_endpoints26/COMPLETE_NEW_ENDPOINT_SHARD_INDEX.csv.gz`在S11中列出每片`scalar_file`、`geometry_file`、行数及SHA；`design26/dependencies_by_pool/`区分旧main缓存、前轮缓存及本轮新增来源。对旧端点应按该来源读取指定main，不在本轮DATA中寻找重复副本。

若需要一个物理标量文件，可运行：

```bash
python engine26/assemble_scalar_table.py --base "$STUDY"
```

它输出`new_endpoints26/NEW_ENDPOINT_SCALARS.csv.gz`和`UNIFIED_SCALAR_RECEIPT.json`。该CSV.gz是逐池压缩成员串接、仅一处CSV表头，完整解析到EOF后与权威分片为同一逻辑表；最终包不重复存两份。分析和研究台可直接用分片索引解析`team_key`，不要求先生成这个可选物理文件。

## 6. 运行环境与验证

实际运行 Python 3.12.14、NumPy 2.3.5、pandas 2.2.3、SciPy 1.17.0、Shapely 2.1.2、Matplotlib 3.10.8、Pillow 12.3.0。版本以执行回执为准。

中文图表使用 `assets/NotoSansCJKsc-Regular.otf`；S11提供字体、官方SIL开放字体许可及来源SHA，数值分析不依赖字体。已渲染HTML可以直接独立阅读；如需从最新Markdown重建，安装Node依赖 `marked@17.0.5` 后运行 `node report26/render_integrated_report.mjs "$STUDY"`。HTML渲染不执行融合或任何新的统计抽样。

最终交付验证包括：从实际取回的 ZIP 解压读取每个 CSV、gzip 和 JSONL 到结尾；核对行宽、行数、SHA256、标量—几何团队键顺序；再用全部登记请求核对实际结果。打包前目录的检查不能代替这个步骤。失败端点属于实际结果，未完成请求单列，不用零分补齐。

精度分析中，单图 MCSE、跨图路径抽样区间和建筑重抽区间是三个不同量。复算时应保留固定图片、人数、完整路径及批次的关联，不从图上的平滑线反推原始实验。
