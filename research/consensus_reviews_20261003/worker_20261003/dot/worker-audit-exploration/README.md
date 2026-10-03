# 固定四人替换背景与优势集中度

完整中文结论：[REPORT_zh.md](REPORT_zh.md)。本包是对固定提交 `405f3041fdd76977f625d50c558c63dbf342699d` 的本地独立探索，不修改源仓库、GT、人员资格或投票。

## 当前正式结果

- `results_v2/`：最终主分析，含严格保留数值并列的排名。`results/` 若出现在工作目录，是最初探索记录，不应当作最终排名结果；交付压缩包不包含它。
- `restricted_results/`：假设性缩小人员池的敏感性分析，保留原 LOBO 标签，不重训、不重新平分。
- `inputs/`：经核验的固定分数、人员顺序、外建筑分组、两政策单人矩阵、原警告及字段说明。
- `validation/`：另一项完整几何重放的依赖证据；本分析自身没有重新生成几何。
- `comparator_validation.json`：与收到的原 `paired_replacement.py` 在全部 28 个实际评分数组、7,728 个人员对行上完全一致。
- `tests/` 与 `test.log`：14 项独立单元测试。

## 复现

在 Python 3.12 环境安装 `requirements.txt`。输出目录必须尚不存在：

```sh
python -B reproduce.py --out ../replacement_exploration_replay
```

入口会先核验输入 SHA-256，再运行 14 项测试、全 10 图主分析、全部留一人员限制与两人联合限制、建筑影响分析以及原程序全量对照。它不会覆盖冻结输入或已发布结果，也不需要 GitHub、图像或新几何计算。

`src/reference_paired_replacement.py` 是收到的原程序的原样副本，只用作独立实现对照。其来源为 `worker_consensus_independent_20261003/src/paired_replacement.py`；其单图默认模式不在此包运行，复现入口只使用完整来源分数模式。

## 结果读取

- `pair_effects_by_image.csv`：每图、规则、评价政策的 276 对×1,540 个共同背景的分布摘要；含均值、SD、分位数、正/负/平局比例与两侧阈值敏感性。
- `additive_projection_by_image.csv`：目标参考下的事后可加投影与残差；它不是外建筑训练画像。
- `group_contrasts_by_image.csv`：两个校准政策×两个评价政策完整交叉，避免将分组变化与GT评价变化混在一起。
- `candidate_influence_*`：仅从被比较的两名候选中去掉指定人，仍允许他出现在三人背景。
- `restricted_pool_*`：同时从候选和背景中排除指定人，仅是假设性固定子池，原资格仍保留。
- `pair_effects_panel_average.csv`：先将同一个 a、b、T 在图片/建筑上等权平均，再看 T 分布。不要与逐图统计直接混用。
- `leave_one_building_contrast_sensitivity.csv`：只删去一个被评价建筑的贡献，不重新训练 LOBO 标签。

## 解释边界

所有分数、组合及子池仅描述这批固定记录；组合数不是独立人员样本量。原参考与“4图修订、6图原参考”分别保留，修订政策不等于完整修订真值。数值平局容差 1e−12；0.001 和 0.005 只作预先规定的幅度敏感性，不是验证过的任务重要性阈值。非可加残差可能来自投票阈值、几何覆盖和非线性 IoU，不能解释成真人协调或因果能力。没有任何自动删票、GT裁决或未来人群置信区间。
