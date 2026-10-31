# 最终质量、人数曲线与统计表

阅读结论用 `RESULTS_REPORT_ZH.md`，个人层面用 `INDIVIDUAL_REPORT_ZH.md`。`TABLE_*.csv` 是可直接阅读的主表；未经显示舍入的正文数值与源表筛选键保存在 `RESULTS_KEY_NUMBERS.json`。最终统计只读取 `stage04_computation/ENDPOINT_TARGET_SCORES.csv.gz`，已包含正式来源平面恢复后的重评结果。

## 图表入口

- `figures/SCREENING_FIXED17_MAIN.pdf`：同一17图筛前/后，B8L2、完整率、图内P10和SD。
- `figures/WHOLE_TARGET_FIXED17_TO13.pdf`：筛后混合范围与全部目标兼容人群，固定17图容量至13人。
- `figures/SIDES_FULL_QUALITY_COMMON3_TO5.pdf`：两侧共同3图、各自目标下的完整Q及输出率。
- `figures/SIDE_FULL_QUALITY_FIXED_TO5.pdf`：各侧3→5的固定支持；两列图片不同。
- `figures/SIDE_FULL_QUALITY_TWO_IMAGES_TO10.pdf`：每侧仅2图的大人数条件，不能当作同图两侧比较。
- `figures/CONDITIONAL_SIDE_FULL_QUALITY.pdf`：q9-04空间2五人池的精确有限边际与自然256对照。
- `figures/ALL_17_IMAGE_CURVES.pdf`：17页逐图曲线；同名逐图PNG在 `figures/image_curves/`。
- `figures/CAPACITY_SUPPORT.pdf`：只按冻结成员容量确定的图/楼支持。

全部16个PDF及PNG对应关系见 `FIGURE_MANIFEST.json`。联系图仅为视觉检查缩略页，不代替可阅读的逐图页。

## 必须一起读取的统计口径

1. 自然256沿用存档的48+104+104路径，原48内保留old24/prior_new24。对恢复身份均匀插入；各目标/筛后池过滤同一基础顺序。重复团队保留路径频数，计算端点按身份缓存去重。
2. k=1是原答，不是单人融合；曲线为自然256抽样边际，个人报告为所有实际人员的精确有限均值。k=2已实际计算，单列 `TWO_PERSON_SUPPLEMENT.csv`，主折线1→3留断点，不纳入主同时带。
3. N≤10的有限团队边际已完整枚举；大池的个人、N−1与满员也有精确边际。`EXACT_FINITE_MARGINALS.csv.gz` 与自然MC分开，`HYBRID_DISPLAY_MARGINALS.csv.gz`保留每个单元的估计身份。精确总体SD用ddof=0，自然样本SD用ddof=1。
4. `MAXIMUM_SUPPORT_CURVES.csv`在每个k使用所有容量允许图片；固定面板保存在 `stage01_pools/PANEL_DEFINITIONS.json`。同时带中心线与带使用相同的全曲线可评图支持；例如全部兼容对照到13人，Q为16图共同支持，完整率仍为17图。容量不足与结果不可评不混用。
5. 使用现行2,000次整路径重抽，按保存来源层分别重抽，共享每图全部k及对照的权重。路径MC带固定图片；建筑重抽带固定路径估计。有效整条重抽数、逐点区间和同时带分别保存，不把它们混称。
6. Q只汇总可评分结果，完整输出率汇总所有实际融合尝试；缺Q不填0。k1的历史环序资格标志不算融合失败。主底面/几何使用`*_complete`门禁，原生不完整三角候选只在诊断表中保留。
7. 对照同时保留各臂自身有效图条件均值、同图双方条件均值差、同路径双方都可评差及状态转移。分母差异见 `SUMMARY_DENOMINATOR_CLARIFICATION.json`。满员仅一个确定团队；SD/MC误差为0不证明参考正确。

## 源表与回连

`QUALITY_BY_IMAGE_K.csv.gz`和`POOL_K_METRICS.csv.gz`为逐图逐人数；`PAIRED_PATH_EVENTS.csv.gz`保留逐路径团队键和实际替换人数；`PAIRED_IMAGE_K_RESULTS.csv.gz`、`PAIRED_NUMBERS_IMAGE_INTERVALS.csv.gz`为同k/同路径人数区间；`ADJACENT_FOCAL_*`和`PARITY_*`为原生状态及奇偶补充。几何与精确成员回连最终端点索引，GT/范围证据在stage02及stage06。

恢复正式高度来源前的个人阶段只保存在 `archive_before_official_height_source_recovery/`，不再作为主分母。`.tmp`、运行log和联系缩略图不进入正式产物清单。最终读取校验与图表视觉检查记录见 `ARTIFACT_READABILITY_CHECKS.json`、`FIGURE_FILE_CHECKS.json`。

## 有限池波动的解释

兼容池更小：n=10约占其人员池的29%–77%，筛后池约为29%–34%。因此SD下降描述的是当前有限人员池、当前抽样占比下的组合波动减小，也包含抽样更接近满员的作用，不能单独解释为空间或人员同质性的纯因果证据。
