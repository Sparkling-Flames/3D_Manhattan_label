# 同图严格大块换人／换类：汇总口径

本目录的脚本只读取已经登记的事件及已计算端点/事件指标，不更改人员、标签、参考、融合或评分。结果文件在实际运行后生成；本说明不代表融合已经完成。

## 输入与执行

```bash
python exchange_research_20261025/analysis/summarize_exchange.py \
  --events exchange_research_20261025/design/screen/EVENTS_EXACT.csv.gz \
  --metrics exchange_research_20261025/results/screen/EVENT_METRICS.csv.gz \
  --endpoints exchange_research_20261025/native/ENDPOINT_SCALARS.csv.gz \
  --output exchange_research_20261025/analysis/screen
```

各输入可给多个文件，确认阶段按 `phase` 单列。事件表是成员、阶段和背景的依据；端点表是可评分/连接失败和记录时间的依据；事件指标由主计算脚本提供。没有取得端点不作失败，不能评分不作 Q=0。

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
