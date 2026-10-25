# 同图严格大块换人／换类：汇总口径

本目录的脚本只读取已经登记的事件及已计算端点/事件指标，不更改人员、标签、参考、融合或评分。已完成screen 22830事件、confirm 38808事件、reverse_screen 8082事件、reverse_confirm 20278事件的汇总；另完成target_omissions 2002事件的固定A留一比较。每阶段实际回执位于相应子目录。

当前采用入口是 `ADOPTED_CONDITIONS_MEMO.md`、`FINAL_CONDITIONS_COMPACT.csv`（71行，phase/role分开）及 `figures/CONFIRM_Q_SEPARATION.png`。完整方向/失败仍在各阶段表中。`partial_schema_check/`只是一度用于接口调试的部分结果，不应进入最终研究结论或正式交付包。

## 输入与执行

```bash
python exchange_research_20261025/analysis/summarize_exchange.py \
  --events exchange_research_20261025/design/screen/EVENTS_EXACT.csv.gz \
  --metrics exchange_research_20261025/results/screen/EVENT_METRICS.csv.gz \
  --output exchange_research_20261025/analysis/screen
```

各输入可给多个文件，确认阶段按 `phase` 单列。事件表是成员、阶段和背景的依据；事件指标已经包含精确端点的可评分/连接失败和记录时间，由主计算脚本提供。`--endpoints`仅在提供与本次登记相符的端点文件时作为补充；native的总体标量文件可能由后续批次重建，不能自动当成所有阶段的完整端点库存。没有取得端点不作失败，不能评分不作Q=0。

## 主比较量

- 同类幅度：`within = distance(A,B)`。
- 跨类幅度：`cross = [distance(A,C)+distance(B,C)]/2`。
- 区分度：`gap = cross-within`，及聚合均值的 `cross/within`。类内幅度为零时，不加入任意小数制造比值。
- 有符号变化 `BA`、`CA`、`CB` 单列。区分度高不等于升质，Q接近也不等于形状接近。

三个队伍的共同背景、n 与 m 一致；严格设计中 XYZ 及 D 两两不重叠。因此上述三个距离都有相同实际换人数。失败率和质量损失尾部是独立用途判断，不要求零失败才采用分类。

## 权重与分母

先对固定 XYZ、同一个目标类背景人数下的不同 D 做平均，再对同一 XYZ 的背景人数层等权，再对 XYZ 块等权；同图、同方法、同 n/m 的不同可行方向等权。主结果同时给图等权和楼等权：每楼先平均其图片，再对楼平均。

每个指标保留实际可用的事件、图和楼分母。Q/几何幅度要求实际可比的端点，失败仍进入失败率；可用分数不因失败变成零。两次使用同一端点不构成两个独立建筑证据。

每个楼外折内的源类/目标类编号仅在该折内比较。跨楼角色按楼外历史 Q 方向、相对记录时间方向和困难结构转折方向对齐。原始编号、成员及中心仍在事件/标签来源表中保留。

## 输出用途

- `METHOD_N_M_COMPARISON.csv`：所有候选×n/m 的幅度、gap、比值、图/楼同向比例以及有符号变化，不只保留正结果。
- `ALL_OUTCOMES_BY_METHOD_N_M.csv.gz`：每个质量分项和风险/时间指标的实际分母、图/楼等权均值与图片间分布。
- `DIFFICULTY_COMPARISON.csv`、`ALL_OUTCOMES_BY_DIFFICULTY.csv.gz`：简单/中等/困难分别呈现。
- `SEMANTIC_ROLE_COMPARISON.csv`：按楼外历史角色方向对齐，避免跨折拼编号。
- `FOLD_CLASS_ROLE_MAP.csv`：从实际楼外中心计算困难转折排名、最高/最低转折类及最大人数类。`FAIR_ROLE_COMPARISON.csv` 专列“最大类→最高转折类”“任何非最高类→最高转折类”及逆方向，避免旧分类额外的中间方向稀释其主要用途；同时保留全方向总体。`FAIR_ROLE_COMMON_POOL_DIFFERENCES.csv.gz` 再限制到相同角色与共同图片/n/m。
- 各 `POOL_*`、`BUILDING_*`、`CONCRETE_BLOCK_*` 和 `BLOCK_BACKGROUND_*` 表：可追溯到具体图片、楼、XYZ块及背景层。
- `FIXED_XYZ_BACKGROUND_GRADIENTS.csv.gz`：同 XYZ 不同目标类背景人数的高减低变化，同时看 A、B、C 和净效应。真实 D 成员随背景人数变化，不能解释成唯一参数的纯干预。
- `COMMON_POOL_BASELINE_DIFFERENCES.csv.gz`：新旧方法在共同图片/n/m 下的差异，用于初步方法比较。它不宣称两法用了相同 D/XYZ，也不代替共同人员域或完全相同端点比较。
- `RISK_TIME_SUMMARY.csv`：可评分失败、连接失败、Q下降超过5/10分、记录时间变化及质量/时间同时改善。

筛选阶段允许积极选择 gap 达数分、跨类/同类比值较高、在多数图/楼上重复且容量足够的条件。幅度、改善方向、结构/几何、风险分别评价；不要求一个分类包办所有用途。确认阶段使用未参与本轮选择的楼或新组合，但整个 v2 已经多轮研究，应称内部检查，不称新的外部盲测。

`geometry_same_pair_count` 是一致性指标，值越大表示角点数量更常相同；它的负 gap 可以表示跨类更容易改变角点数。汇总的 `metric_polarity` 明确区分它与其它距离指标，不能机械要求每个指标都正 gap。

## 指标与补充解释

B8L2/D10 的变化用分数点；`geometry_bev_distance` 是两支融合输出之间的1−IoU，独立于参考，0.02表示几何距离差0.02，不是质量提高2分。上下点/成对角距离以度计，与未匹配节点数量分别保存。记录时间是已有可追溯记录的总和，不是本轮新测得的生产耗时。

`compact_interpretation.py` 接上历史Q方向、同角色难度分层和已有结构机会/参考转折数分层，并生成198格等完整候选的简表。机会表只在实际参考ID匹配时接入，参考省略的可见细节不能因这张分层表自动判错。

`analyze_target_omissions.py` 用于固定A的目标七人面板完整7选6：同时保存C7−C6、B7−B6和净差、每人被替换时的失败/降质、七个六人块的收益保留情况。n始终10；这是以固定源类人员替换某目标人员，不是团队人数从6增到7。每锚点内部7种目标子块完整，锚点和整个目标类人员集合并未全枚举。

## 最终整理代码与小表

- `summarize_reverse_branches.py`：四种反推分类同时保留全方向、小类进入、大分支之间替换；角色来自历史类容量，不读目标效果决定。
- `focus_condition_support.py`：从实际成员验证m、D源/目标类人数、m/A原有源类席位和XYZ/D重复性；输出在 `condition_support/`。
- `describe_response_condition.py`：反推GEOMQ_K3 20/6源响应角色、真实目标六人块与同图K2对照，输出在 `reverse_confirm/GEOMQ_K3*`。
- `build_final_conditions.py`：从完整阶段汇总及原始事件生成最终条件表。失败/损失的原始次数和分母与图等权率分别保留。
- `final_condition_strata.py`：最终条件逐图、难度和绑定参考的结构机会分层；使用现有计算结果，不补算融合。
- `plot_separation_scatter.py`：screen图与confirm四格主图共用可复现脚本；PNG/SVG/PDF及实际绘图点独立保存。

最终图采用DSTRUCT18/7、RFUSE_GEOM_K2 12/4、RFUSE_GEOMQ_K3 20/6、MSDGEOM_SCOPE_K4 20/6的已解释方向。具体条件是完整比较后的采用判断；phase保留其原始登记身份，不把条件后选变成新的外部盲测。该判断不要求各方法在所有n/m、所有方向均成立。
