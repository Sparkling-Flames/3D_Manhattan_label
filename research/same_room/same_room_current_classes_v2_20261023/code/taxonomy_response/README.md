# 类别配比与具体成员响应：可携带分支

先读 `FINDINGS_ZH.md`。详细统计定义见 `METHOD_ZH.md`。两张图位于交付根目录：

- `figures/GROUP_COMPOSITION_MEMBER_REPEATABILITY.png`
- `figures/G015_COMPOSITION_MEMBERS.png`

## 关键结果定位

| 问题 | 文件 |
|---|---|
| 17组的配比、成员、结构与时间重复性 | `summary/GROUP_PATTERN_PRIMARY.csv`；其它预算/条件见 `GROUP_PATTERN_SUMMARY.csv.gz` |
| 主面板完整矩与精确团队 | `results/PANEL_DECOMPOSITION_PRIMARY.csv.gz`、`PAIRED_TEAM_RESPONSES_PRIMARY.csv.gz` |
| 不同人数下的当前结构构成作用 | `results/DECOMPOSITION_PAIR_N.csv.gz`：仅当前结构全部已知支持，各人数/replicate/条件原样保留；联合共同支持在主面板矩和分组表中 |
| 双端活跃与仅源活跃的不同分母 | `results/COMPOSITION_DIRECTION_COUNTS.csv`、`COMPOSITION_DIRECTION_SUMMARY.csv`、`COMPOSITION_DIRECTION_PANEL_PRIMARY.csv.gz` |
| 同配比真实成员质量低尾/波动 | `summary/COMPOSITION_CELLS_PRIMARY.csv.gz`、`SAME_COMPOSITION_MEMBER_SPREAD_*` |
| 换一批实际成员仍保持完整配比 | `results/REPLICATE_MATCHED_COMPOSITION_CELLS.csv.gz`、`REPLICATE_COMPOSITION_CURVES.csv.gz`、`summary/REPLICATE_CORRELATION_SUPPORT.csv` |
| 能真正区分类别与多名成员的支持 | `summary/DECOMPOSITION_MEMBER_SUPPORTED_*`；单成员强反例见 `SINGLE_MEMBER_CLASS_STRONG_REVERSALS.csv` |
| Q的强连续校准与类别增量 | `calibration/CALIBRATED_*`、`FOLD_COEFFICIENTS.csv.gz`、`summary/MODEL_COMMON_SUPPORT_COMPARISON.csv` |
| 主劳动时间模型 | `summary/TIME_PREDICTION_PRIMARY.csv`；指标是 `log_recorded_time`，为合语义、全员已知的总活动耗时取自然对数；33对/10楼/11组，全部模型同支持 |
| Q和时间同一批实际队的重复性 | `summary/TIME_QUALITY_COMMON_SUPPORT_*`，39对/10楼/12组 |
| G015的精确人员和替换 | `cases/CASE_G015_COMPOSITION_MEMBERS.csv.gz`、`CASE_G015_SAME_CLASS_W104_W120.csv` |

时间模型中 `mae` 是绝对log耗时误差；`contrast_mae`、`contrast_mse` 是扣除两端各自均值后的队间响应形状误差，目标均值仅用于评价。绝对MAE没有明显改善；形状MSE改善约22%—25%。二者不可混称为绝对交付时间精度提升。时间分支不要求源图GT，但使用既有楼外Q/T等连续画像；Q预测要求源图正式Q。

`DECOMPOSITION_GROUP.csv.gz` 和 SUMMARY 中有 `budget` 列，主结果必须筛 `mid_n_rep0`。完整表把其它人数及第二批实际成员单列。主普通Q支持是308个可分解面板；几何/失败为309个登记面板。失败不补零。

## 不依赖整个仓库的复现

以下命令从本交付根目录运行。代码科学计算未改变；增加的 `--labels` 和 `--native-scalars` 仅定位随包必要输入。`inputs/LABELS_AND_HISTORIES_REQUIRED.csv.gz` 是原main标签文件中实际17个Manual楼外折和所需字段的逐字符串副本，2,108行；没有重训、重新编号、四舍五入或补缺失。来源与SHA见 `inputs/REQUIRED_LABELS_RECEIPT.json`。

```bash
python -m pip install -r code/taxonomy_response/requirements.txt

python code/taxonomy_response/analyze_response.py \
  --labels results/taxonomy_response/inputs/LABELS_AND_HISTORIES_REQUIRED.csv.gz \
  --design design --native results/native \
  --out rebuild/taxonomy_response/results

python code/taxonomy_response/calibrate_response.py \
  --labels results/taxonomy_response/inputs/LABELS_AND_HISTORIES_REQUIRED.csv.gz \
  --design design \
  --responses rebuild/taxonomy_response/results/PAIRED_TEAM_RESPONSES.csv.gz \
  --budget mid_n_rep0 --out rebuild/taxonomy_response/calibration

python code/taxonomy_response/summarize_response.py \
  --results rebuild/taxonomy_response/results \
  --calibration rebuild/taxonomy_response/calibration \
  --out rebuild/taxonomy_response/summary

python code/taxonomy_response/build_composition_cells.py \
  --responses rebuild/taxonomy_response/results/PAIRED_TEAM_RESPONSES_PRIMARY.csv.gz \
  --design design --out rebuild/taxonomy_response/summary
```

`summarize_response.py` 加 `--font /path/to/a/CJK-font.otf` 会同时出中文主图。G015图可以这样重建：

```bash
python code/taxonomy_response/case_g015.py \
  --responses rebuild/taxonomy_response/results/PAIRED_TEAM_RESPONSES.csv.gz \
  --design design --native-scalars results/native/ENDPOINT_SCALARS.csv.gz \
  --out rebuild/taxonomy_response/cases --font /path/to/a/CJK-font.otf
```

原始研究运行从106个完成池快照读取数据，实际命令用了 `--partial` 作为读取路径；读取时全部 **141,260端点、1,954面板** 已完成。`ANALYSIS_RECEIPT.json` 保留这个实际参数，并明确 `all_requested_panels_complete=true`；不是把未完成研究当终稿。以上复现直接使用已保存的完整精简标量，数值定义一致。

## 交付取舍与研究台连接

本分支不附全量逐队中间表、全n全部分类交叉汇总、临时校准输入、原图或字体副本。完整端点及设计已在主包保存，可以重建被省略的重复表。交付中的大CSV使用gzip；CSV字段名与未压缩工作输出一致。

`panel_id` 连接 `design/PANELS.csv`，包含直接关系、原声明组、视角图片、参考、类别折、人数与核心候选；`team_key_a/b` 连接 `results/native/ENDPOINT_SCALARS.csv.gz` 与主包保存几何；`member_set_key` 是完整实际成员，`selected` 是可变成员块。`structure_vector`、`joint_vector` 均为包含核心的整队类别计数。类别版本/历史隔离、量义与不可计算状态分别保留，不以研究组数代替独立物理房间数。

文件与大小见 `DELIVERY_MANIFEST.json`。本分支报告和表全部为本轮新增分析；历史分类标签为冻结输入引用，不把它计作本轮重新训练。
