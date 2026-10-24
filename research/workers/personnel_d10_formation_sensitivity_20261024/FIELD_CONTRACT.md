# D10 人员分型敏感性字段合同

所有 CSV 为 UTF-8；`.csv.gz` 为 gzip。`condition` 固定 `manual`/`semi`；`formation_arm` 为 `B8L2_original`、`D10_fixed_old_model`、`D10_reselected`；`tier` 为 `coarse`/`fine`。`ALL` 只用于全样本描述，建筑外对照使用真实 `heldout_building`。`unknown`/空值不可当零。`worker_id`、`image`/`image_id`、`building`/`building_id`、`panel_id`、`team_key` 维持来源原键，不能仅凭显示名合并。

| 文件 | 行键 / 分母 | 关键字段和单位 |
| --- | --- | --- |
| `QUALIFIED_RECORD_SCORE_INPUTS.csv.gz` | 可评分 `object_id`，7,302 行 | `B8L2`、`D10`、`lift_D10_minus_B8L2` 为质量分；`B8L2_peer_delta`、`D10_peer_delta` 为同图中心化分；`dir` 等分项只有来源存在时可用。 |
| `INPUT_SCORE_STRATA.csv` | `condition × origin × difficulty` | `records`、`workers`、`images` 分开计；`direction_records` 是非空分项数。 |
| `D10_RESELECTED_CHOICES.json`、`D10_CANDIDATE_SELECTION.csv`、`D10_INNER_BUILDING_LOSSES.csv.gz` | 条件×外层建筑；候选/内层另展开 | 原候选规则的 D10 重选及内层损失；内层不能含目标建筑。 |
| `TRAINING_EXCLUSION_LEDGER.csv` | `condition × outer × inner` | `training_records`、`excluded_records` 为原适格训练记录数；两个 `target_*_in_training` 必须为 0。 |
| `D10_LABELS_FIXED_AND_RESELECTED.csv.gz`、`WORKER_RANK_AND_LABELS.csv.gz`、`PARTITION_COMPARISON.csv`、`LABEL_TRANSITIONS.csv` | 条件×外层建筑×臂×人员/类层 | `ARI` 不受类名置换影响；`matched_same` 用最大匹配；`rank_shift_D10_minus_B8` 为名次差，正值是名次下降。 |
| `D10_CLASS_CAPACITIES_AND_CENTERS.csv` | 条件×外层建筑×臂×层×类 | `workers` 容量、`members` 原键及 Q/T/结构代理中心；类标签跨折无固定语义。 |
| `PANEL_LABEL_COVERAGE.csv` | `panel_id × formation_arm` | `complete_panel` 为全 12 候选及固定背景已知，可用于实际选队；`known_teams` 可在部分面板大于零。 |
| `COMPOSITION_TEAM_LINKS.csv.gz`、`COMPOSITION_CELLS.csv.gz` | 面板×臂×层×物理队/类别计数向量 | 每面板 924 队；未知向量留空；每格 `teams`、`failed`、有效分数数、均值和样本 SD 均独立保留。 |
| `COMPOSITION_COMMON_PANEL_SUMMARY.csv`、`COMPOSITION_COMMON_CELLS.csv.gz`、`COMPOSITION_COMMON_COMPARISON.csv` | 旧/被比较臂都已知的同一批队；面板和格层级 | `matched_teams` 为共同物理团队数；`eta2` 是分数在类别计数格之间的描述性平方和占比；`cell_mean_span` 为格均值极差。比较均值只用两侧 η² 均非空的 `comparable_panels`。 |
| `SELECTED_TEAMS.csv.gz`、`SELECTED_TEAM_CROSS_EVALUATION.csv.gz` | 完整面板×臂×层×策略；配对表仅旧与 D10 | `replacements = 6 − shared_members`；各 `*_delta` 为 D10 所选端点−旧所选端点，**B8L2 与 B8L2、D10 与 D10**比较；8 个主评分/几何字段两边齐全才有 `all_score_metrics_common`。 |
| `SELECTED_TEAM_IMAGE_EFFECTS.csv`、`SELECTED_TEAM_BUILDING_EFFECTS.csv`、`SELECTED_TEAM_SUMMARY.csv` | 图片、建筑、难度分层 | `mean_delta` 为同一计分单位的配对差；`scored_panels` 不等同于 `panels`；图片、建筑等权均值与正向支持分开。 |
| `ABC_COVERAGE.csv`、`ABC_LEGALITY_SUMMARY.csv` | 采样资格状态组合；面板/难度×n×m×层×对照臂 | `attempts` 是固定抽样分组的次数，非唯一三队数；`old_only`/`new_only` 在同一尝试对照；`unknown` 单列。 |
| `ABC_EVENTS.csv.gz`、`ABC_COMMON_PHYSICAL_TRIPLES.csv.gz` | 去重的合法物理三队；后者同一尝试两臂均合法 | `within_abs=|B−A|`，`cross_abs=(|C−A|+|C−B|)/2`，`extra_abs=cross_abs−within_abs`，`net_C_minus_B=C−B`；`same_orientation` 记录 A/B/C 角色是否一致。 |
| `ABC_PANEL_EFFECTS.csv`、`ABC_IMAGE_EFFECTS.csv`、`ABC_BUILDING_EFFECTS.csv`、`ABC_SUMMARY.csv`、`ABC_COMMON_PHYSICAL_SUMMARY.csv` | 面板→图片→建筑层 | `attempts` 为去重合法事件，`scored` 为相应指标非空事件；报告人数/图片/建筑，不把事件当独立样本。 |
| `STRUCTURE_HIGHQ_ROLE_*.csv` | 固定 `V3_BEHAVIOR` 结构类的面板和配对 | 只重新选 Q 最高的结构类角色；未改结构分类。`available=false` 的面板不进入角色/质量比较。 |

`B8L2`、`D10`、`IoU3D100` 越大越好；`S_bottom_deg`、`dir`、`Hmean`、`Hcenter`、turn/短边为几何或结构诊断量，按各自定义解释，不能混加。`recorded_time_logratio` 仅在两侧记录时间资格与来源相同且来源单一时计算；没有时间的端点保持缺失。所有失败端点保留 `failure`，失败质量值不填零。Q 的中心化参照群体及分型折须与所选 `heldout_building` 一致。多次用到相同物理团队/图片的面板和 ABC 尝试有依赖性，推断单位不应降为事件行。

η²数值零方差处理（2026-10-24验收修正）：总平方和≤有效团队数×1e-20时留空，不计入可比较面板数；保留原格、团队和失败。该阈值仅排除舍入精度下的常数，不是效果大小阈值。
