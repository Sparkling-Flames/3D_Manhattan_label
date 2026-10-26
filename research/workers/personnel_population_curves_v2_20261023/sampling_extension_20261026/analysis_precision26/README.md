# 完整随机进入顺序的精度统计

本目录只分析已保存的冻结端点，不重新融合、评分或分类。研究方法见 [PRECISION_METHODS_ZH.md](PRECISION_METHODS_ZH.md)。旧 48 路径主域与本轮各独立新批次分开；旧重点池的额外 48 条单列。

## 文件职责

|文件|用途|
|---|---|
|`check_prior48.py`|核对用户提供的旧 48 路径精度计数；给出明确标作预算预测的精度缩放表|
|`precision_core.py`|均值、线性与逆 CDF 分位数、完整路径频数 bootstrap、二项区间、完整曲线经验带|
|`analyze_natural.py`|逐池实际版本比较、逐 k 与配对人数区间、状态、分项及原子检查点|
|`summarize_natural.py`|固定图片/指标支持、图片与建筑等权、路径误差与建筑重抽、旧新独立批次对照|
|`exact_anchor_and_display.py`|完整有限团队目录诊断；保留纯路径结果并生成显式标来源的展示曲线|
|`refresh_components.py`|按冻结公式补齐命名损失项，仅刷新分项统计，不重算Q/P10或bootstrap|
|`repair_seed_exports.py`|从逐池精确记录修复跨池导出的64位种子文本，不重新生成路径或bootstrap|
|`validate_exact_small_pools.py`|完整六个小池的48/新208/合256逐k精确对照、频数反例及总图|
|`watch_natural.py`|在融合执行期间仅增量保存已完成池的统计；全集完成前不做总体解释|

`results_stage2/` 是完成两个 104 条新批次后的当前结果，已包含 A104、B104、152、256 等各批次及合并结果；它是正式总体交付的唯一入口。`results_stage1/` 是第一批检查点，工作区中曾有一份明确标为 `complete=false` 的 36 池技术汇总，该汇总不进入正式总体交付。`results_stage0/` 是本轮代码对旧数据的运行检查，不能冒称新增路径。全过程是否完整，读取 `ANALYSIS_RECEIPT.json` 与 `SUMMARY_RECEIPT.json` 各自支持，不将较晚完成的输入数量追溯赋给较早技术汇总。

## 输入依赖

源提交：`b9bcec809fbaec8ab055931a1abb7baa5db44dac`。以下路径相对本轮解压根目录；大历史输入由主入口的依赖恢复说明取得，不重复打包。

- `repo/research/workers/personnel_population_curves_v2_20261023/stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz`：原 24 条前缀。
- `inputs_cache26/ENDPOINT_SCALARS_20261023.csv.gz`：补齐旧路径保存的分项和状态，不重算 Q。
- `inputs_cache26/precision25/NEW_PREFIX_VALUES_COMPACT.csv.gz`：前轮自然新 24 条及重点池额外 48 条；自然与政策按 `policy` 分开。
- `prior_recovered/research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/analysis_precision/new_results/EXACT_FINITE_MARGINAL_STATISTICS.csv` 与同分析目录 `p10_definition_sensitivity/EXACT_P10_REFERENCES.csv.gz`：已有完整有限边际。
- `new_endpoints26/stage1/prefix_values/<pool_id>.csv.gz` 与 `stage2/` 对应文件：本轮真正追加的独立顺序前缀。分片保存优先于长时间打开的全局大文件；必须完整读至 EOF。
- `engine26/derive_frozen_blocks.py`：沿 main 的 `enrich_cached_geometry.py::score_blocks` 冻结公式，由五个保存 raw 量补齐 B8/D10 命名损失项；不改变保存的 Q、D10、资格或状态。缺任一必要 raw 量时保留 NA，已存在命名项须相容。

## 实际运行

在本轮解压根目录运行，`--root .` 指向含 `analysis_precision26/`、`repo/`、`new_endpoints26/` 等目录的根。依赖为 Python、NumPy、pandas、SciPy；实际版本保存在 `ANALYSIS_RECEIPT.json`。

```bash
python analysis_precision26/precision_core.py
python analysis_precision26/analyze_natural.py --root . --stage 2 --bootstrap 2000 --resume
python analysis_precision26/refresh_components.py --root . --stage 2
python analysis_precision26/analyze_natural.py --root . --stage 2 --bootstrap 2000 --compile-only
python analysis_precision26/summarize_natural.py --root . --stage 2 --bootstrap 2000
python analysis_precision26/exact_anchor_and_display.py --root . --stage 2
python analysis_precision26/plot_natural_precision.py --root . --stage 2
```

2000 指 bootstrap 次数，不是新增人员顺序。分析主种子为 `2026102607`，按池和实际生成批次用 SHA256 派生整路径重抽种子；自然顺序种子来自另存的实际设计表，二者不能混称。

所有 `seed` 与 `*_seed` CSV 字段都须按十进制字符串读取、合并与保存。不要经过 float64：不同池的 int64/uint64 混合合并可能损失低位。正式合并函数 `read_csv_exact_seeds` 已执行该规则；`SEED_EXPORT_CORRECTION.json` 记录此前一份阶段合并表的定点修复，实际随机数生成与所有统计结果均未受影响。

`prior_pool_cache/`、`bootstrap_cache/`、`pool_checkpoints/` 为可重建工作缓存，通常不装入交付包。每个池完成后原子保存各表和 DONE 回执；全库合并表也重新读取 CSV/gzip 至 EOF，核字段数和行数。跨阶段输入支持相同，不以中途看到的质量方向决定执行顺序或停止。

中文图使用 `assets/NotoSansCJKsc-Regular.otf`；官方来源及哈希见主包 `assets/FONT_SOURCE.json`，字体文件可按该来源恢复，避免重复装入大字体。图片与PDF已导出，无需安装字体即可阅读。

## 主要表和连接键

`NATURAL_CURVES.csv.gz` 的键为 `pool_id × cohort × k`，含图片/建筑/条件/难度/参考键、实际路径数、有效 Q 路径数、去重团队数、失败数、指标、点精度与秩区间。`NATURAL_INTERVALS.csv.gz` 的键为 `pool_id × cohort × interval`，同时保留边际均值变化和同一路径两端均可评的变化；实际 `k_from/k_to` 不只靠区间名称推断。

`NATURAL_STATUS.csv.gz` 按全部计划/尝试路径登记不同状态；延期与缺 Q 不等同实际融合失败。`NATURAL_COMPONENTS.csv.gz` 保留各质量分项的有效样本数与均值 MCSE。`NATURAL_CURVE_BANDS.csv.gz` 和汇总表额外使用 `metric × band_scope` 键；`all_random_prefix_k` 是纯路径整曲线，`nonexact_display_k` 只覆盖尚未由已有精确边际解决的展示点，两者都固定观察到的合法 k 支持。

`failure_rate` 为沿用的非延期不可评分总率；`actual_consensus_failure_rate` 仅含 `fusion_exception/below_four/no_connection`，`output_unscoreable_rate` 单列 `invalid_floor/invalid_full_geometry/measurement_exception`，参照缺失与未执行另列。分项 `B8_*_block` 是无量纲冻结损失，低好，不是0–100分或可相加百分比贡献；`B8_height_block` 为两项高度损失之和。

`COMMON_SUPPORT_KEYS.csv.gz` 保存每个指标实际比较的图片/人数或区间，`COMMON_SUPPORT_*_SUMMARY.csv.gz` 在该支持上同时列图片等权与建筑等权。`path95_*` 是固定图片中的路径 Monte Carlo 经验范围；`building95_*` 是保留当前路径估计后的整栋建筑重抽范围。某个固定图片的 bootstrap 分数不可估时，该次总体也不可估，`path_valid_draws` 如实保留，不重分配其余权重。

`PER_IMAGE_OLD_NEW_COMPARISONS.csv.gz`、`PER_IMAGE_FULL_CURVE_BATCH_DIFFERENCES.csv.gz` 保留逐图变化。`PRECISION_REACH_BY_LAYER_K.csv.gz` 记录工作精度尺；其中本轮统一 bootstrap 种子所得旧 48 的 P10 临界计数可与历史保存区间略异，历史原数由 `design_diagnostics/OLD48_SUPPLIED_PRECISION_COUNTS.csv` 固定保留。

`EXACT_ANCHOR_MC_ACCURACY.csv.gz` 的 P10 两套参考不可互换。展示表的 `Q_sd_display` 明确区分随机样本 ddof=1 估计与完整有限总体 ddof=0；历史目录 ddof=1 数值另列，纯路径统计完全保留。展示表不是新的实际进入路径，路径增减研究仍使用原始路径关联。

随机团队条件质量分布的 P10 目标是总体逆 CDF 分位数；沿用的 `linear` 是样本估计器。有限完整目录的 `linear` 插值是历史目录口径，并非该样本估计器的大样本必然极限。`EXACT_P10_EXPECTATION_BUDGET_COMPARISONS.csv.gz` 利用已知有限目录、条件于实际有效 q 的二项次序统计量解析期望，区分预算改变的有限样本偏差与随机偏离；解析计算不计入新路径或新融合。
