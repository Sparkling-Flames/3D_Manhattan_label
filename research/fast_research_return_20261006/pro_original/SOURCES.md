# 文件来源与本轮使用方式

仓库：`Sparkling-Flames/3D_Manhattan_label`，通过连接器读取当时的默认 main；没有写入仓库。以下均为仓库内路径。路径用于回查，不表示运行了整个目录。

## 最新判断入口（先读）

`research/fast_research_handoff_20261006/README.md`

`research/fast_research_handoff_20261006/LATEST_FINDINGS.md`

`research/fast_research_handoff_20261006/REVIEW.md`

用于约束任务分工和最新研究边界，不将这些文件的作者观点当作已验证结果。

## 四个真实质量案例

`research/pro_quality_handoff_20261002/analysis_results/layout_metric_response_20261001/REPORT.md`

同目录 `real_metrics.csv`、`experiment_plan.json`、`results.json`。`results.json` 包含选中原作答、参考坐标和审核字段。本轮选取 jtcxE69GiFV-12/R03398、e9zR4mvMWw7-19/R01301、B6ByNegPMKs-42/R03325、e9zR4mvMWw7-16/R00087。

`research/pro_quality_handoff_20261002/analysis_results/layout_3d_quality_probe_20261002/REPORT.md`

同目录 `metrics.csv`，用于条件体积、平均墙高偏差、内部墙高 RMS。已有指标摘入 `inputs/quality_selected.json`，不混同本轮重算。

## 2t7-06 完整三路线

根目录 `research/layout_reliability_20261005/pro_original/`：

`inputs/2t7WUuJeko7-06.json`：同一三人的真实上下点。

`results/construction/2t7WUuJeko7-06_domain.json`：共同可计算域。

`results/construction/2t7WUuJeko7-06_lee.json`

`results/construction/2t7WUuJeko7-06_point_numeric.json`

`results/construction/2t7WUuJeko7-06_exact.json`

以上三份为既有最终几何；本轮只评估与重绘，不重跑构造。

`evaluation/references.json`：固定原参考 R02502。

`research/structure_constraints_20261006/human_review.json`：对局部对应已有审核，不升级为全环对应确认。

## 范围案例与完整原作答

`analysis_results/worker_profiles_20261003/input.json`：只提取 e9zR4mvMWw7-19 这一图；24 人原有有效足迹、排除记录和两版参考。没有运行该目录的人员画像、固定四人或人数增长实验。

原作答代表 R02122/P006：本轮只按与其他 23 份作答的平均 BEV IoU 最大选出。候选 R01301/P021：由既有明确 scope 标记选择，而非 GT 分数。两份原作答都未编辑。

`research/lee_tile_stage1_20261002/README.md`

`research/consensus_reviews_20261003/lee_20261002/dot/lee-audit-exploration/REPORT_zh.md`

上述历史结果已报告同一范围终点对两版 GT 的不同一致性；本轮没有将历史结果改称新发现。本轮新增的是完整原作答代表对照和 scope 候选共识外区域的支持分解。

## 复用数值模块

`tools/thesis_main/analysis/layout_reliability_20261005/arc_consensus.py`：摘录 Ring、连续坐标投影和相应小函数至 `src/arc_excerpt.py`。

`tools/thesis_main/analysis/lee_tile_stage1_20261002.py`：摘录 `tile_consensus`。

`tools/thesis_main/analysis/audit_supervisor_gt_sensitivity_20260922.py`：仅摘录 `region_mesh`，**没有使用该旧文件的半像素投影函数**。以上两函数放在 `src/lee_excerpt.py`。

## 原图状态

`research/fast_research_handoff_20261006/quality_images.json` 已提供原图文件名、原始 data 路径及 `quality_images/*.png` 映射，但本轮未取得可查看的 PNG 字节。没有以历史图像描述冒充本轮看图。交付图件全由本包真实坐标和实际计算生成。
