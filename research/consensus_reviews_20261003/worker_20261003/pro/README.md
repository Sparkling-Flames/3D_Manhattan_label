# 人员区分与共识不确定性的独立研究（2026-10-03）

核心报告：[REPORT_zh.md](REPORT_zh.md)。固定仓库提交：`405f3041fdd76977f625d50c558c63dbf342699d`。

## 实际输入与范围

四个10图×24人矩阵由当前GitHub阅读接口读取并恢复原文件字节，含UTF-8 BOM。Git blob SHA1与接口返回值完全相同；见`inputs/transfer_checks.json`。它们是当前原始参考／有修订时使用修订参考的IoU及标准化面积质心距离，不是本轮重新审核的GT。

`inputs/one_image_geometry.json`只含`7y3sRwLe3Va-04`的24份独立候选足迹和原始参考。坐标从当前`input.json`摘录，保留已给顺序，不重新投影、配对、共享x或修复。这个数值摘录不是完整`input.json`：源图另有2份历史未纳入记录，本包没有把它们恢复为候选。该图难度为“未记录”，不因IoU高而改称简单。完整预处理点与全部源审核字段未复制，原始来源仍以固定仓库为准。

容器DNS无法解析GitHub域名，完整仓库/NPZ没有下载到容器。GitHub阅读工具取得了报告、当前源码及上述材料。**没有全量复跑A线136图、B线全部10图的几何融合或原仓库23项测试**。本包的10图人员分析是完整矩阵计算；几何和组合复算限于上述单图。

## 已执行数值工作

- 原/修订政策的完整人员矩阵、LOBO、35种无序4+4建筑分割、全部留一人员影响分析；建筑校准bootstrap及建筑内一致的身份置换诊断。
- 单图全部10,626个四人集合×两种规则；30项源摘要复现；6项当前子集重切tile对照。
- 单图所有可行上/下半人数配比的336个解析面积状态，采用有限池超几何概率，不把面积期望比称为平均IoU。
- 单图两种规则各276对人员的“共同三人、替换第四人”示范。完整B线NPZ模式代码已提供但未在本轮执行。
- 12项独立针对性测试；运行环境见`environment.json`，日志见`results/tests.log`。

## 复算

```sh
python -m pip install -r requirements.txt
python reproduce.py --out ../worker_consensus_independent_replay
# 可选同时生成图：
python reproduce.py --out ../worker_consensus_independent_replay_with_figures --figures
```

输出目录必须不存在；不会覆盖发布结果。安装范围适配原接口，实际执行版本固定记录在environment.json，不宣称所有满足范围的版本逐字节一致。

现有完整B线工件在本地可用时：

```sh
python src/paired_replacement.py \
  --source-dir /your/repo/analysis_results/worker_profiles_20261003 \
  --out /your/new-output/paired_replacements
```

该额外模式读取`subsets.npz`与`rosters.json`，不改GT、不学习新分组、不改权重。它只比较同一三人背景下替换第四人的**标量参考差异**；原始区域波动仍须单独计算。

## 主要结果文件

`profile_analysis_summary.json`和`lobo_recomputed.csv`：来源分组复现与预测性诊断。

`disjoint_building_splits.csv`、`four_building_membership.csv`：互不重叠校准块的可重复性，不是35个独立统计样本；并列切点保留全部允许分法。

`leave_one_worker_influence.csv`：影响诊断，不是删除人员的决定。

`metric_image_diagnostics.csv`：质心与IoU的图内关系、参考政策影响。

`one_image_k4_exact.csv`及`composition_30_field_checks.csv`：组合数、IoU、SD、面积分解。

`one_image_all_composition_area_expectations.csv`：精确面积期望及波动；其中`ratio_of_expected_intersection_union`**不等于平均IoU**。

`paired_replacements/*.csv`：固定其余三人后的替换作用，枚举背景不是独立样本。

## 必须保留的解释限制

“相对上/下半”不是已验证的自然人员类型。原始参考和修订政策不是两个等价真值。bootstrap频率不是人员真实高质量的后验概率。来源中的`independent=true`是记录状态，不证明所有人员错误统计独立；相同坐标也不证明抄袭。本包没有改任何资格，原样保留24票。没有原图，局部结构真假、范围选择、GT适用和成像问题需本地确认。
