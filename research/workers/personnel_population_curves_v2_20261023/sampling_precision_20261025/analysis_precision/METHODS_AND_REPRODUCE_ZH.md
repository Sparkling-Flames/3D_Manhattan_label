# 自然人数路径精度：统计对象、误差层次与复算

本轮分析基于 main `40d0fe62dc62f6f6c12723af10195b7abb7bc9fe` 的真人 v2 保存结果。精度诊断、抽样冻结、追加融合和分析分别留有代码与回执。这里说明自然路径分析；策略的共同基路径比较由同一交付中的策略专题保存。

## 估计什么

对每张图片，固定正式合格的实际人员池。自然路径是该人员集合的均匀随机排列；k 人前缀在所有 k 人子集上均匀。不同 k 共用同一顺序，增加人数的同一过程按路径配对。相同成员集合复用保存的融合端点，并保留在随机抽样中出现的次数；复用端点不改变抽样权重。

均值、P10 和 SD 针对可评分团队。失败使用全部非合同延期的尝试；k=2 保留为合同延期，不算实际融合失败；缺 Q 不补成 0。P10 沿用逐图逐 k 的 NumPy `linear` 经验分位数。样本 SD 沿用 `ddof=1`。图层结果先逐图计算再作图等权或建筑等权，绝不把大量前缀当成大量独立图片。

完整有限成员子集可给精确边际：满员只有一个团队；k=N−1 只有 N 队；k=1 是全部原始个体。N≤10 的六个普通 Manual 池另外穷尽全部合法非空子集。成员目录还完整保留了这六池的 180 个 k=2 组合，但其状态仍为合同延期，没有正式融合尝试，失败率和质量都留空；目录完整不等于“融合全成功”。**真有限总体 SD 使用 ddof=0**，另保留全表 ddof=1 以说明与旧表的关系。全量有限边际的 P10 保留 `linear` 约定；二项秩区间针对分布分位数，二者在离散小总体下不是完全相同的量。

## 什么误差被检验

1. 原 24 与独立新增 24：相同预算的真实抽样重复。
2. 原 24 与合并 48：样本扩大后的估计变化；两者共享旧路径，不能当成独立样本检验。
3. 旧噪声预选的 53 池最终 96：在固定重点子域提高精度；不能替代平衡的全图 48 主结果。
4. 精确有限边际：直接比较抽样点估计与全部子集结果，能看到 bootstrap 未观察到的稀少低尾。
5. 固定当前图片、完整路径重抽：Monte Carlo 抽样误差。
6. 路径结果固定、建筑整块重抽：观察到的建筑差异。它和路径误差分别报告，不混成一个来源不清楚的区间。

重点 53 池的重抽均条件于**已冻结的旧噪声选池名单**，没有在每次重抽中重新排序、重新选池，不能解释成包含选池过程的不确定性。

另以现成的 24+48 条新增路径汇总重点池的**独立新72**点估计与均值 MCSE，和包含旧24的 focus96 区分；不再增加融合或另一套重抽。它用于检查旧高噪声选图后的条件表现。旧样本 SD/MCSE 较高、新样本较低，可能同时含旧噪声极值的回归均值，不能全部解释为路径数增加的功劳。

每一张图的旧批次、新 24 批次、重点追加 48 批次独立重抽。旧批次在 old24、pooled48、focus96 三种估计中使用相同重抽索引；新增批次也按此共享。一次索引覆盖整条曲线，故前后人数保持配对。主程序默认 2,000 次重抽。这些重抽是误差计算，真实新增顺序由另存设计生成，不将 bootstrap 次数冒称新样本。

图中的 95% 百分位范围是逐统计量的点态重抽范围，不是整条曲线同时覆盖 95% 的带。

固定 N≥30 的 `30_to_full` 比较保留实际 N=30 的 10 张零变化图片，不因起终人数相同删掉它们。主方向计数采用 1e−9 数值零容差，与 main 后段口径相同；同时保存 strict >0/<0 列，避免把浮点残差写成实质正向或反向。

完整路径重抽若某张图某 k 抽到的全为不可评，则该图该次对应质量量保持缺失，不补分；**固定图层该单元的这一整次重抽也保持缺失，不把其余图片重新加权**。汇总保存 `valid_bootstrap_draws`、`bootstrap_min_available_normalized_weight` 和 `bootstrap_missing_image_weight_draws`。原样本非精确边际若某图仅有 1 条可评，经验 bootstrap 的零宽并不是可估方差：该量的正式不确定性留空，另保留经验范围、原点和单条支持标记，不能算入达标比例。这个问题实际仅发生在少量门洞后段单元；满员和完整穷尽的有限边际按精确已知状态处理。失败仍保留原尝试分母。主比较逐单元使用各版本均可计算的共同图片，逐图支持键另表保存；报告面板的容量筛选固定，不能把不同 N 门槛的均值直接相减解释人数效应。

## 冻结的预算和精度量尺

查看旧表后、查看新增结果前冻结：194 普通/门洞 Manual 池各新增 24 条；普通 Manual 中 N>10，每难度按旧 24 在 k=3..min(20,N−1) 的均值 MCSE 之 RMS 取前 12 池，全部 17 门洞也入选，合计 53 池再追加 48 条。名单及完整排序见 `FOCUS_PRESELECTION_OLD24_RMS.csv`。

报告量尺为单图均值 MCSE≤1 分、固定图片层均值 MCSE≤0.5 分、单图 P10 经验 95% 区间半宽≤2 分。它们用来说明现有精度能回答多细的问题，**不是不断加样直到全部达标的停止条件**。完成注册预算后停止广泛追加；未达部分保留。均值 MCSE 1 分不等于均值 95% 区间半宽 1 分。

24 条中，真实 P10 以下期望仅 2.4 个观测。对连续分布，24 次全部落在真实 P10 以上的概率为 0.9^24≈7.98%，故分布无关双侧 95% 秩区间往往需要理论 Q 下界 0。经验 bootstrap 在旧样本内部看起来较窄，不能排除未见尾部。零失败同样保留二项置信上界；满员或完整穷尽边际已知真实状态时无需这种抽样上界。

## 代码和运行

以下命令中 `BASE` 是取得的 main 目录下 `research/workers/personnel_population_curves_v2_20261023`，`STUDY` 是本轮交付目录。真实路径可按解压位置替换，不能改输入键或冻结方法。

```bash
python analysis_precision/diagnose_existing_paths.py \
  --input "$BASE/stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz" \
  --out "$STUDY/analysis_precision/old_diagnostics" --bootstrap 1000

python analysis_precision/freeze_focus_design.py \
  --precision "$STUDY/analysis_precision/old_diagnostics/OLD_PATH_POOL_K_PRECISION.csv.gz" \
  --out "$STUDY/analysis_precision"

python analysis_precision/analyze_new_natural_precision.py \
  --old "$BASE/stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz" \
  --old-scalars "$BASE/results/ENDPOINT_SCALARS.csv.gz" \
  --new "$STUDY/new_endpoints/NEW_PREFIX_VALUES_COMPACT.csv.gz" \
  --focus "$STUDY/analysis_precision/FOCUS_PRESELECTION_OLD24_RMS.csv" \
  --exact "$STUDY/new_endpoints/EXACT_MARGINAL_VALUES.csv.gz" \
  --out "$STUDY/analysis_precision/new_results" --bootstrap 2000
```

依赖为 Python、NumPy、pandas、SciPy；无需重新分类或训练模型。`diagnose_existing_paths.py` 的 1,000 次是预算冻结前的旧表诊断，正式新旧对照的 2,000 次由第二程序生成。前者与已发表 R03 的 2,000 次不是新增自然顺序。

## 关键表

| 表 | 内容 |
|---|---|
| `NATURAL_BATCH_SUPPORT.csv` | 每池的原路径、新路径、重点路径和前缀数 |
| `NATURAL_POOL_K_BATCH_PRECISION.csv.gz` | 全部原始 k、逐图各版本的均值/P10/SD、结构、失败、精度和分母 |
| `NATURAL_POOL_INTERVAL_BATCH_PRECISION.csv.gz` | 同路径前后变化、共同可评数、恢复/新增不可评、坏尾 |
| `NATURAL_POOL_K_REPLICATION_COMPARISON.csv.gz` | 每图原24与新24、48、重点96的实际变化 |
| `NATURAL_FIXED_SUPPORT_STABILITY.csv.gz` | 固定容量面板、图/楼等权、路径/建筑两种不确定性分别报告 |
| `NATURAL_FIXED_SUPPORT_BATCH_COMPARISONS.csv.gz` | 共同图片上的批次差、实际幅度和单图反向比例 |
| `NATURAL_BUILDING_BATCH_RESULTS.csv.gz` | 逐建筑结果 |
| `NATURAL_FIXED_PANEL_EXACT_SUPPORT.csv.gz` | 面板→图片→建筑的实际共同支持键 |
| `NATURAL_COMPONENT_POOL_K_BATCH_POINTS.csv.gz` | 冻结 B8 损失分项和其它质量量逐图证据 |
| `NATURAL_COMPONENT_COMMON_SUPPORT_COMPARISONS.csv.gz` | 分项共同图片比较；B8 块是损失，越低越好 |
| `PRECISION_TARGET_REACH.csv.gz` | 不按结果删图的精度达标/未达情况 |
| `EXACT_FINITE_MARGINAL_STATISTICS.csv` | 全部有限子集的精确边际统计 |
| `EXACT_ANCHOR_BATCH_ACCURACY.csv.gz` | 原24、新24、48、96对精确锚点的真实估计误差 |
| `HYBRID48_IMAGE_CURVES.csv.gz` | 可采用的逐图全 k 曲线：k1/N−1/full 和六小池合法 k 用精确有限边际，其他 k 用平衡48；原表不覆盖 |
| `HYBRID48_FIXED_SUPPORT_CURVES.csv` | 同容量图片集合上的采用曲线；边际 MCSE 不当作跨 k 变化或建筑差异区间 |
| `FOCUS_INDEPENDENT_NEW72_IMAGE_CURVES.csv.gz` | 固定重点53池只用真实新增72条的点估计/均值MCSE，不含被用来选池的原24 |
| `FOCUS_NEW72_COMMON_SUPPORT_COMPARISONS.csv.gz` | 新72与旧24、新24、48、96的同支持条件描述，不另做模型或重抽 |

`HYBRID48` 的 `Q_sd_population_estimate` 在随机点使用样本 ddof=1，在精确点使用真有限总体 ddof=0；分别写入 `SD_convention`。精确行 `path_count=0`，因为统计单位是全部不同团队，同时保留 `available_balanced_natural_paths=48`、`known_finite_teams` 和真实可评/失败分母。`known_finite_teams` 是参与该行估计的已知不同团队数，随机行通常小于 48；它不包含其它策略或缓存中未用于该估计的团队。只有 `finite_marginal_complete=true` 才代表该 k 的全部有限团队已穷尽。focus96 不进入该采用表，避免把不同精度追加域混成主总体。合同延期 k2 以及确实全失败的质量缺失都保留。

几何与原答通过 `pool_id / k / path_id / team_key` 连接设计与端点；研究台不应把 `version` 当人员分类，也不应把 `focus_selected` 当困难标签。它是旧抽样噪声驱动的追加计算域。

## 只整理已完成表的轻量入口

```bash
python analysis_precision/extract_natural_findings.py \
  --root "$STUDY/analysis_precision/new_results" \
  --focus "$STUDY/analysis_precision/FOCUS_PRESELECTION_OLD24_RMS.csv"

python analysis_precision/write_final_report_numbers.py \
  --base "$STUDY/analysis_precision"
```

前者生成 `KEY_*.csv`，后者生成 `FINAL_NUMBERS_FOR_REPORT.md` 与三份 `FINAL_*.csv`。两者只筛选、重聚合已经完成的逐图及重抽结果，不产生新增端点、随机顺序或 bootstrap。

本轮首次直接流式导出的五份 gzip 派生表发生缺尾。已以相同固定输入和相同 2,000 个注册重抽种子重新导出这五张表，不重新融合；故障原件的全部可读解压字节与完整重导表的对应前缀逐字节相同。最终写入改为内存生成完整 CSV/gzip、临时文件完整写入及 fsync、回读核对、原子替换；压缩尾、字段和行数另读至 EOF。修复记录见 `new_results/ATOMIC_EXPORT_RECEIPTS.json`、`ANALYSIS_RELATION_VERIFICATION.json`；完成回执只在修复并完整验证后恢复。历史故障诊断不作为当前有效结果文件。
