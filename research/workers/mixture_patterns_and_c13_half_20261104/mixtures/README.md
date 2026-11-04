# 现有混合人群规律分析

主入口：[REPORT_ZH.md](REPORT_ZH.md)。逐条数值及精确筛选条件：[KEY_FINDINGS.csv](KEY_FINDINGS.csv)。

本目录接续 v2.1 的当前 DSTRUCT K3、RFUSE K2、JOINT K3/K4，研究既有完整联盟、固定人数配比、同配比成员及固定替换块背景。只重聚合保存结果；未新增团队、拟合、融合或评分。新增 C1↔C3 半队严格 ABC 和前缀收敛在本批其它模块中单列。

## 科研图

|图|内容|
|---|---|
|[FIG01](FIG01_COALITION_BASELINES_AND_STRUCTURE.png)|同一混合终点的不同基线；官方难度×参考结构|
|[FIG02](FIG02_FIXED_N_COMPOSITION_AND_MONOTONICITY.png)|固定 n 的配比方向；至少三层完整配置链的单调性|
|[FIG03](FIG03_BACKGROUND_SIGNED_AND_ABSOLUTE.png)|固定换人块、嵌套背景增加的有符号效应和绝对幅度|
|[FIG04](FIG04_GEOMETRY_ILLUSTRATIONS.png)|三张事后机制例的当前参考、完整纯类及混合几何，图内同尺度|

四图均有同名 SVG。研究台可直接使用 [GEOMETRY_ILLUSTRATIONS.json](GEOMETRY_ILLUSTRATIONS.json)，其中含 3 个参考与 6 个既有几何端点。

## 数据入口

|主题|逐条或逐图表|汇总与支持|
|---|---|---|
|当前 DSTRUCT 联盟|`DSTRUCT_CURRENT_ALLIANCE_ENDPOINTS.csv.gz`、`DSTRUCT_ALLIANCE_IMAGE_CONTRASTS.csv.gz`|`DSTRUCT_ALLIANCE_STRATA.csv`、`DSTRUCT_ALLIANCE_SUPPORT.csv`|
|难度、用途、结构|`POOL_SCENE_DIFFICULTY_INDEX.csv`|`DSTRUCT_DIFFICULTY_STRUCTURE_CROSS.csv`、`DSTRUCT_DIFFICULTY_STRUCTURE_SUPPORT.csv`|
|两类混合与两支纯类|`DSTRUCT_MIXTURE_VS_BOTH_PURE_IMAGE_EFFECTS.csv`|`DSTRUCT_MIXTURE_VS_BOTH_PURE_STRATA.csv`|
|固定 n 配比|`FIXED_N_ADJACENT_CONFIGURATION_PAIRS.csv.gz`、`FIXED_N_FOCUSED_IMAGE_EFFECTS.csv.gz`|`FIXED_N_FOCUSED_STRATA.csv`、完整的 `FIXED_N_CONFIGURATION_STEP_STRATA.csv`|
|主分析的配比链|`FIXED_N_THREE_OR_MORE_LEVEL_CHAINS.csv.gz`、`FIXED_N_THREE_OR_MORE_LEVEL_CHAINS_BY_IMAGE.csv`|`FIXED_N_THREE_OR_MORE_LEVEL_CHAIN_STRATA.csv`|
|同配比成员|`SAME_CONFIGURATION_MEMBER_DISTRIBUTIONS.csv.gz`、`MEMBER_SPREAD_BY_IMAGE.csv`|`MEMBER_SPREAD_STRATA.csv`|
|相同完整队伍上的 Q/T|`Q_T_IDENTICAL_COMPLETE_CONFIGURATION_PAIRS.csv.gz`、`Q_T_IDENTICAL_COMPLETE_IMAGE_EFFECTS.csv`|`Q_T_IDENTICAL_COMPLETE_STRATA.csv`、`Q_T_IDENTICAL_COMPLETE_QUADRANTS.csv`|
|RFUSE/JOINT 联盟|`RFUSE_JOINT_CLASS_ADDITION_PAIRS.csv.gz`、`RFUSE_JOINT_CLASS_ADDITION_IMAGE_EFFECTS.csv.gz`|`RFUSE_JOINT_CLASS_ADDITION_STRATA.csv`、`RFUSE_JOINT_CLASS_ADDITION_SUPPORT.csv`|
|固定换人块及背景|`FIXED_BLOCK_BACKGROUND_EXISTING_ROWS.csv.gz`、`FIXED_BLOCK_BACKGROUND_IMAGE_EFFECTS.csv.gz`|`FIXED_BLOCK_BACKGROUND_STRATA.csv`、`FIXED_BLOCK_BACKGROUND_COMMON_Q_SUPPORT.csv.gz`|

`FIXED_N_MONOTONICITY_*` 是保留全部二层及以上链、在图内按链等权的辅助表。论文主结论使用名称含 `THREE_OR_MORE_LEVEL` 的完整三层及以上链表，按链→面板→图等权，避免两点连线自动算成多层单调证据。

`Q_T_EXCLUDED_UNEQUAL_TEAM_SUPPORT.csv` 保留 14 条不同 Q/T 团队分母的排除记录；它们来自一张 n=25 图片的 1 支缺少合法时间支持的队伍，不影响报告的 n12/n20 主条件。所有无 Q 端点和失败支持均保持缺失身份，没有以 0 计改善。

## 复现

在仓库根目录依次运行：

```bash
python research/workers/mixture_patterns_and_c13_half_20261104/mixtures/analyze_mixtures.py
python research/workers/mixture_patterns_and_c13_half_20261104/mixtures/deepen_mixtures.py
python research/workers/mixture_patterns_and_c13_half_20261104/mixtures/export_geometry_examples.py
python research/workers/mixture_patterns_and_c13_half_20261104/mixtures/render_mixture_figures.py
python research/workers/mixture_patterns_and_c13_half_20261104/mixtures/finalize_mixtures.py
```

依赖为项目现有 Python、NumPy、pandas、Matplotlib、Pillow。绘图支持 `--font` 或 `HOHONET_CJK_FONT`，并自动查找常见 Windows、Linux、macOS 中文字体。首次复现运行完整分析；`--reuse-pairs` 仅供已经保留本轮相邻配置原始结果的相同输入重汇总使用。

原始资料路径、SHA-256 和固定提交 URL 在 [FINAL_SOURCE_MANIFEST.csv](FINAL_SOURCE_MANIFEST.csv)。三份本地辅助输入与固定 Git 源逐字节、逐表相同的证明由父目录 `audit/ASSISTED_SOURCE_LOGICAL_COMPARISON.json` 给出。压缩文件、PNG/SVG、引用和数值检查见 [FINAL_VERIFICATION.json](FINAL_VERIFICATION.json)，本目录文件清单见 [DELIVERY_MANIFEST.csv](DELIVERY_MANIFEST.csv)。
