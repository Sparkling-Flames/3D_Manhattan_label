# 实际选择用途：字段和复现

## 输入身份

- `../composition/DESIGN_TEAMS.csv.gz`：本轮实际成员集合；`PANELS.csv`、`PANEL_MEMBERSHIP.csv.gz` 定义同一固定背景与总人数下的完整 6/12 子集。
- `../composition/batches/batch_*/ENDPOINT_SCALARS.csv.gz`：不重复融合的完整新端点分批，失败行也必需。
- `../taxonomy/LABEL_FREEZE.json`、`LABELS_LOBO.csv.gz`、`JOINT_LABELS_LOBO.csv.gz`：最终楼外标签。代码在选队前后检查同一 SHA，禁止一边修改标签一边报告结果。
- `../taxonomy/CONTINUOUS_FEATURES_LOBO.csv.gz`：楼外连续结构、尺度、冗余特征。
- 旧 `personnel_global_composition_20261021/multivariate/continuous_features_lobo.csv.gz`、`composition/FROZEN_LABELS.csv`：连续 QT 与旧分类。旧 `continuation_20261021/next_stage/batches/batch_*/ENDPOINT_SCALARS.csv.gz` 和第一阶段完整 `composition/TEAMS_SCALARS.csv.gz` 提供历史训练终点。

这些路径保持原交付包的阶段身份。先按各包的相对目录恢复，再运行。大历史表只需引用原包，不重复放进用途包。

## 执行

从本文件所在目录执行，或提供脚本绝对路径：

```bash
python3 prepare_training.py --from-consolidated
python3 run_policy_batch.py select --regime historical_only
python3 run_policy_batch.py select --regime cross_panel_LOBO
python3 run_policy_batch.py evaluate --regime historical_only
python3 run_policy_batch.py evaluate --regime cross_panel_LOBO
python3 summarize_policy.py
```

训练缓存可由第一阶段完整合并表恢复；不必取得未打包的逐图 runtime 缓存。`prepare_training.py` 按规范团队键哈希排序，每个 pool×n 取最多 256 个历史集合。先对分块取前 256、再合并取前 256，与对全表排序后取前 256 的键集相同。它不读取评分来选择训练团队。`TRAINING_SOURCE_INDEX.csv` 记录所用输入；缓存本身可重建，不纳入最终精简包。

`historical_only` 先前已算团队训练，新的 n 可能位于训练支持之外；`cross_panel_LOBO` 使用本轮其它建筑成员面板训练，目标建筑的旧和新结果均排除。两者身份分别保存，不合并为一个验证结果。

## 主要字段

| 表 | 主键和含义 |
|---|---|
| `*/SUPPORT.csv` | `panel_id`；登记成员数、共同支持成员集合数、未知导致的机会不足、总人数、来源域、建筑等。 |
| `*/COMMON_CANDIDATES.csv.gz` | `panel_id,team_key`；全体共同候选成员集合，普通策略在其上均匀选取。 |
| `*/SELECTIONS.csv.gz` | `panel_id,policy,team_key`；所选实际集合及概率，类别并列最优一律保留。 |
| `*/FITS.csv.gz` | `heldout_building,model,outcome`；楼外训练支持、人数范围、特征、系数和 ridge。 |
| `*/PANEL_POLICY_RESULTS.csv.gz` | `panel_id,policy`；实际分项均值、失败率、时长、随机成员对照及损失尾部。 |
| `*/POLICY_CLASS_COMPOSITIONS.csv.gz` | `panel_id,policy,tier,class_counts_json`；所选完整粗/细人数向量及其选择概率，不能用平均人数代替完整构成分布。 |
| `*/PANEL_OBSERVED_OPPORTUNITIES.csv` | `panel_id`；实际质量范围、失败数量及事后可达上界。带 `oracle` 的字段用目标结果诊断剩余空间，不是可执行或经验证的选择策略。 |
| `POLICY_EFFECTS_SUMMARY.csv.gz`、`KEY_POLICY_EFFECTS.csv` | 策略相对普通随机选择的实际结果；按面板→图→建筑等权，另列人数、来源域、难度；后者为可直接打开的小表。 |
| `PAIRED_POLICY_EVENTS.csv.gz` | 相同面板上的粗/细、类别/连续策略逐项对照。 |
| `PAIRED_POLICY_SUMMARY.csv.gz`、`KEY_PAIRED_POLICY_EFFECTS.csv` | 上述逐面板对照的建筑等权汇总及建筑重采样区间。 |
| `PAIRED_METHOD_EVENTS.csv.gz`、`PAIRED_METHOD_SUMMARY.csv.gz`、`KEY_PAIRED_METHOD_EFFECTS.csv` | 新旧分类策略的实际直接比较；仅保留共同候选团队集合完全相同的面板。 |
| `PAIRED_METHOD_COVERAGE.csv` | 各方法共有面板、实际候选集合完全相同面板及候选不同而排除的数量。 |

`delta_B8L2` 等是策略真实结果减同一共同面板普通随机集合的成功条件均值；`failure_delta_pp` 单独保留失败变化。质量缺失未置零。`time_percent_vs_uniform` 是实际总记录秒数比值的变化，要求面板全部共同候选有完整且兼容的时间；它不是预测误差改善百分比，也不是并行墙钟时间。

效率结论使用 `slice_kind=joint_time_support` 或 `n_joint_time_support`：所有质量分项、风险和时间同时限制到完整兼容时间面板。不能把 `all` 行在较大质量样本上的收益与较小时间样本上的节时拼成同一质量—时间结论。

分项表另保存角点不足四个、连接不可用、定位未决、顺序并列和完整底面失败的概率及相对普通策略百分点差。原始几何字段（ERP 顶/底平均 y、BEV 质心与边界、面积、高度等）用于说明向哪里变化；其正负方向本身不等于质量变好或变差。参考结构召回包含 5°/9° 两种逐点评价口径，这些数字不是改变融合墙角对应参数。

`loss_gt5_vs_random_success_probability` 是先按策略概率选择实际集合，再与面板均匀选取的一个成功集合比较，损失超过 5 分的有限总体概率。`failure_or_loss_gt5_vs_random_success_probability` 把所选集合完整失败计入风险。10 分字段同理。普通策略也报告同一定义的自身风险，以免把所有差异都归咎于分类。

`loss_gt5_delta_pp` 和 `failure_or_loss_gt5_delta_pp` 是上述风险减普通随机策略自身风险后的百分点差，10 分字段同理。

`expected_changed_members_vs_uniform` 是策略与普通随机集合独立抽取时的期望实际换人数。`expected_changed_members_between_policies` 也是两个策略独立抽取的期望，**不是两种构成间必须替换的最小人数**。类别策略可有相同的选队分布；`policy_choice_distribution_identical` 以整个实际集合分布 SHA 比对，分布完全相同时仍可能因两次独立抽取出现成员波动。

配对表的 `relative_time_percent_between_policies` 用每面板的实际期望总秒数计算 `100×(新策略/对照−1)`；`contrast_time_percent_vs_uniform` 是两种策略各自相对普通策略百分比的差，单位为百分点，两者不混用。

用途表中 `class_fine` 与 `class_coarse` 的比较，回答“允许模型使用细分类信息后，实际选队结果怎样变化”。两个模型可以选择不同的粗类人数向量，因此这不是固定父类人数后的纯细类块干预；后者由 composition 专题的匹配事件另行评价。连续模型加细类的比较也保留这一含义。

Manual 新联合类的每个外折均为未再分叉的粗细同叶：`fine_label` 名称存在，但 `coarse_k=fine_k`，两策略成员分布相同。这些别名不构成新增细层，也不能把它们的零差解释为一次有选择机会的细类无效检验。实际粗细分叉及容量以每个外折标签和 `SUPPORT.csv` 为准。

`selected_worker_inclusion_probabilities` 给出每位成员被选中的精确概率，便于解释同类成员的贡献；`selection_distribution_sha256` 标识完整均匀并列集合，不能仅凭人数向量当成同一策略。

`candidate_support_sha256` 标识整个共同候选集合，用于跨方法的同支持比较。相同面板内两种方法若需要不同历史支持，不能把其普通均值或策略效果直接相减；直接跨方法表会排除这种情况，同时在覆盖账保留其分母。

## 构成含义与有限 F01 补充

`explain_policy_compositions.py --condition manual|semi|both` 将已经冻结并评价的策略连接到同一目标建筑外人员历史，输出 `*_SELECTED_HISTORY_SHIFTS.csv.gz` 及建筑等权汇总。每种策略的期望人员特征均值由完整选队概率分布计算，再减同一共同候选的普通均值；这不是重新拟合或目标成绩选优。只有整队全部概率质量都具有该历史字段时才报告均值和差，缺少机会不作零值。

其中 `q_effect/q_downside/t_effect/t_tail` 继承旧连续 QT 定义；`joint_q_history/joint_q_downside/joint_t_history` 继承新联合类的自身 Q、低尾及来源校正 log 时间定义，不能把两套同名含义不同的变量混成一列。`turn/short/redundancy` 是各对应结构表达的楼外同图同行残差历史，`area/height` 为 log 尺度残差历史；`simple/complex` 字段只使用相应机会。人员历史平均增加不代表目标图真实新增结构同样增加，目标几何与票账须另读实际端点。

F01 的独立有限域执行：

```bash
python3 run_f01_finite_utility.py
python3 summarize_f01_configurations.py
python3 summarize_f01_policies.py
python3 plot_f01_configurations.py
```

依赖 `../composition/F01_*` 请求、标签和成员表，以及 `batches/f01_001/ENDPOINT_SCALARS.csv.gz`；主 Manual QT 模型须已完成以提供跨域迁移敏感性。`F01_COMPLETE_CONFIGURATION_CURVE.csv` 覆盖该有限域每个可行人数向量下全部成员集合，`F01_EXTREME_CONFIGURATION_CONTRASTS.csv` 是最多/最少快类的描述性构成对照，并未逐对固定共同背景。F01 只有原生粗类，内部接口的细类别名不对外交付，不产生“细分有效”结果。

报告辅助表与图可在评价完成后直接复现，不需重新拟合：

```bash
python3 make_condition_checkpoint.py --condition manual
python3 make_condition_checkpoint.py --condition semi
python3 explain_policy_compositions.py --condition both
python3 make_component_digest.py --condition manual
python3 make_component_digest.py --condition semi
python3 plot_policy_utility.py
python3 make_utility_digest.py
```

`UTILITY_ACTUAL_USE_DIGEST.csv` 只摘取已完成共同支持策略，不重新选择；历史构成解释对各字段严格保留未知，并保留旧 QT 与联合类自身 QT 的不同定义。

## 保存与恢复

每个条件×分类×训练身份分别原子保存。`SELECTION_RECEIPT.json` 标识选择完成；`EVALUATION_RECEIPT.json` 标识目标结果读取完成；只存在前者不能写成用途评价完成。`run_policy_batch.py --skip-complete` 仅跳过有对应回执的已完成步骤。`superseded_pre_freeze_selection/` 是标签正式冻结前的接口试算，不读取新目标分数、不进入报告，不纳入精简交付。

训练时发现的一片旧本地 scalar gzip 截断已从完整合并表恢复，见 `recovered_training_input/RECOVERY_RECEIPT.json`；恢复没有重新融合或改变分数。只保留这项实际输入恢复记录，不扩大为一轮重复审计。
