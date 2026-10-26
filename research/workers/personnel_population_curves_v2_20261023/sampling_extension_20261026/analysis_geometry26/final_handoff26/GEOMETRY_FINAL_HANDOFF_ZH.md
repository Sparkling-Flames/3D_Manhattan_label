# 人数抽样扩充：几何分支最终交接

当前 main：`b9bcec809fbaec8ab055931a1abb7baa5db44dac`。本文件只整理已保存代码的运行关系、读数位置和有限案例锚点；不把尚未完成的全库新几何结果写成既成结论。

## 1. 当前作业归属与后续顺序

root 已接管 `geometry_stage2`，会话 `74107`，启动时 PID `17886`，`--jobs 1`。本子任务没有再次启动几何 worker。运行中可按 root 的资源安排重启同一可恢复作业；每池 receipt 已完成者自动跳过。进度以 `checkpoints/stage2/*.receipt.json` 为准；`PROGRESS_STAGE2.json` 在整批已排入队列的池完成后更新，可能暂时落后于实际闭合 receipt。

全库几何完成的必要入口是 `analysis_geometry26/results_stage2/RUN_RECEIPT.json`：必须 `pools=194`、`all_pool_receipts_present=true`、`uncomputed_links=0`。之后依次运行：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 analysis_geometry26/summarize_geometry_extension.py \
  --root analysis_geometry26 --stage 2 --replicates 2000

OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 analysis_geometry26/render_geometry_results.py \
  --root analysis_geometry26
```

两个命令在 study 根目录执行。汇总不调用融合、不再算几何距离，只读取逐池合并结果；它计算 2,000 次既有建筑重抽，并验证所有共同旧48点估计/MCSE与前轮保存结果一致。绘图只读取最终汇总表。

绘图入口已准备：

- `F01_GEOMETRY_FULL_CURVE_AND_PRECISION`：普通固定157范围按简单/中等/困难分层；门洞固定17候选、到27人；同时画单图 MCSE 中位数/P90。
- `F02_GEOMETRY_COMPONENT_CURVES`：普通固定157、1至30人的五种几何分量，每个子图写出该分量的严格全曲线共同支持。
- `F03_GEOMETRY_FIXED35_FULL_CURVE`：普通固定92个实际N=35池，1至35人的地面/高度/节点波动；满员合法时V=0的有限空间原因写入图注。

上述图全部在 `figures/` 生成 PNG 与 PDF。这里新增/修改了 F02 的支持标注和 F03 绘图代码，并已语法检查；尚未用未完成的全库结果运行绘图，不伪装成最终新曲线。

## 2. 固定范围与实际可算支持

`FIXED_PANEL_CANDIDATES.csv` 从本轮实际 `POOL_META.csv` 整理，25行。候选数不等于每个指标/人数都可算。

| 范围 | 候选图片 / 建筑 | 难度分层 |
| --- | --- | --- |
| 普通 Manual 全部人员池 | 177 / 22 | 简单114、中等32、困难31 |
| 普通 N≥30 | 157 / 22 | 简单105/22楼；中等25/14楼；困难27/14楼 |
| 普通 N≥35，实际全部N=35 | 92 / 22 | 简单71/22楼；中等13/9楼；困难8/7楼 |
| 门洞全部，最小N=27 | 17 / 9 | 门洞独立层，不混入三种普通难度 |
| 门洞 N≥30，实际最小N=32 | 16 / 9 | 单列 |
| 门洞 N=35 | 7 / 7 | 单列 |

两种共同支持均保存，不能混用：

1. **同一人数点的共同支持**：要求 old48、104A、104B、new208、pooled256 在该 k、该 metric 都有点估计。用于精度变化和同 k 版本比较。
2. **整条曲线的共同支持**：额外要求该固定图片在所有展示 k（除沿用暂缓的 k=2）都可算。用于直接连线画完整曲线，避免线上的图片集合改变。

所有候选仍留在支持状态表。完整地面条件分布不能代替失败率；失去完整资格的端点不填0、不恢复资格。几何指标的计量单位与支持分别见 `METHOD_AND_FIELD_CONTRACT_ZH.md`。

## 3. 报告取数索引

所有路径以下均相对于 `analysis_geometry26/results_stage2/`。`cohort` 主报告保留 old48、stage1_104、stage2_104、new208、pooled256；pooled152是阶段，prior96/all_history304是焦点子域，不合并成全库统一预算。

| 报告问题 | 精确表与筛选 |
| --- | --- |
| 完整低人数至30曲线 | `GEOMETRY_STRICT_COMMON_CURVE_SUMMARY.csv.gz`；ordinary_manual / fixed_N_ge_30；difficulty分层；metric各自；weighting=image_equal或building_equal |
| 同人数单图精度改善 | `GEOMETRY_SINGLE_IMAGE_PRECISION_CHANGES.csv.gz`；同上述范围；comparison=old48_vs_pooled256或old48_vs_new208；各k的MCSE中位/P90、点估计改变量、旧0新正MCSE数量 |
| 独立两批是否重复 | `GEOMETRY_BATCH_POINT_COMPARISONS.csv.gz`逐图；comparison=stage1_104_vs_stage2_104；配套总体 `GEOMETRY_COMMON_SUPPORT_BATCH_CHANGES.csv.gz` |
| 几何整条曲线差在哪里最大 | `GEOMETRY_WHOLE_CURVE_REPLICATION.csv`；最大绝对差人数、RMS差、共同k数；这是描述量，不能称同时95%置信带 |
| 困难图20→30几何改善 | `GEOMETRY_FIXED_SUPPORT_INTERVALS.csv.gz`；ordinary_manual / fixed_N_ge_30 / 困难 / k_from=20,k_to=30 / V_floor；同时查V_centroid_h、V_height_h、V_turn5、V_nodes |
| 同一区间多少图/楼波动下降 | 同一行的image_negative/common_images、building_negative/common_buildings；几何delta<0表示波动减少。各版本分别报告，不把合并版楼数推给104A/B |
| 固定157逐图/楼区间证据 | `GEOMETRY_FIXED157_INTERVAL_IMAGE.csv.gz`与`GEOMETRY_FIXED157_INTERVAL_BUILDING.csv`；文件亦含门洞fixed_N_ge_30子域，必须筛layer，不能从文件名认定所有行都是157 |
| 30→35 | `GEOMETRY_FIXED_SUPPORT_INTERVALS.csv.gz`；ordinary_manual / fixed_N_ge_35 / k_from=30,k_to=35；同一92候选，按困难等分层 |
| 30→各图实际满员 | `GEOMETRY_TO_ACTUAL_FULL_SUMMARY.csv`；fixed_N_ge_30 / k_from=30。`GEOMETRY_TO_ACTUAL_FULL_IMAGE.csv.gz`保留各图原k_to；N=30的合法0跨度图仍纳入，不能只留下N>30 |
| 满员几何 | `GEOMETRY_ACTUAL_FULL_SUMMARY.csv`；完整合法输出只有一队、V=0；无效满员保持缺失。报告candidate_images和common_images |
| 同时说明路径精度与建筑差异 | 同一汇总行的path_mcse/path_normal95_*与building_boot95_*分别列出；前者条件于这些图和人员池，后者重抽既有建筑，二者都不是新建筑验证 |
| 几何有限空间真值检查 | `GEOMETRY_SAMPLE_VS_EXACT.csv.gz`逐池；`GEOMETRY_EXACT_COMMON_SUPPORT_ACCURACY.csv`共同支持MAE/RMSE。精确目录复用前轮，不算新融合 |
| 精确人数过程与指标状态 | `GEOMETRY_PATH_PRECISION.csv.gz`，键pool_id+cohort+k+metric；attempted_paths、valid_paths、valid_pairs、metric_status |
| 人数改变的路径关联 | `GEOMETRY_PAIRED_INTERVAL_PRECISION.csv.gz`；同一完整路径删除jackknife，键含k_from/k_to；paired_paths是总路径，非两端可评分样本数 |
| 节省了多少几何计算 | `GEOMETRY_DISTANCE_COMPUTE_ACCOUNTING.csv.gz`；实际完全相同footprint去重数与成对距离计算次数；没有减少统计频数 |
| 哪些图被排除于某个均值 | `GEOMETRY_COMMON_IMAGE_SUPPORT.csv.gz`、`GEOMETRY_STRICT_COMMON_CURVE_SUPPORT.csv.gz`；候选状态保留 |

不要给 old48 与 pooled256 的差当独立样本差计算标准误：后者包含前者。程序为该比较保留点差，但 `independent_difference_mcse` 是缺失；old48/new208、104A/104B 才是独立批次比较。

## 4. 尚需 root 注意的依赖

- 主几何作业已准备好 `cache/baseline/*.pkl`；这些是可再生缓存，不必交付。实际内容来自旧人口端点几何、前轮新增标量/compact几何，hash保存在 `cache/baseline/INPUT_RECEIPT.json`。200条旧非完整输出原本没有几何条目，均无完整资格；没有合法几何缺件。
- `BASELINE_NATURAL_LINKS.csv.gz`与`POOL_META.csv`是小依赖，建议随几何代码保存；精确原始orders/prefix大表由上层版本依赖连接。
- 本轮新增前缀只读 `design26/links_by_pool/stage1/*.csv.gz`、`stage2/*.csv.gz`；**不要使用此前未通过读回的全局NEW_PREFIX_TEAM_LINKS文件**。
- 新端点从每池 `new_endpoints26/stage{1,2}/parts/<pool_id>/part_*.scalars.csv.gz`及`*.geometry_compact.jsonl.gz`读取；仅接受该池全部完成后写的`POOL_RECEIPT.json`。
- 最终汇总还读取 `prior_recovered/research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/analysis_geometry/results/EXACT_GEOMETRY_MARGINALS.csv` 和同目录 `GEOMETRY_PATH_PRECISION.csv.gz`。这两份是实际旧目录真值、旧combined48复核依赖，不可用报告数字替代。最终包须提供准确历史来源或小规模所需行；无需重复整个旧包。
- `safe_io.py`必须与脚本一起交付。几何距离使用Shapely2.1.2，其他依赖NumPy/pandas；汇总无需Shapely新调用；绘图另需matplotlib/Pillow及Noto中文字体。`/tmp/hohonet_deps`仅为本环境已有安装位置，复现环境正常安装相同版本即可。
- root新增 `delivery26/validate_final_path_links.py`负责最终精确顺序到真实prefix的全关联。几何的pool/k/path状态不替代该上层关联检查。
- 交付中排除cache、实现烟测目录、写入中的文件和未执行最终图；交付真实合并表、METHOD、代码、支持表、最终图与必要已存在案例数据。

## 5. 有限案例锚点与已锁定交付

`FINITE_REPORT_ANCHORS.csv`是三个已完成案例、六个版本的18行原表连接，不重新计算分布，源hash在`EXTRACTION_RECEIPT.json`。建议结合`FINITE_MAIN_REPORT_PARAGRAPHS_ZH.md`直接整合最终报告。

已交付的S02、FINITE_CASES、ORIGINAL_IMAGE_CASES均锁定；本文件和新锚点存于`final_handoff26/`，不改动这些ZIP。所有有限目录校准模拟仍只是估计器抽样模拟，不计为新的真实进入顺序或融合团队。
