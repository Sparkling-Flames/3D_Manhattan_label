# 人工辅助顺序对人数曲线的影响

## 范围与原方法

只补2个其它目标 Manual 池的现有端点：`rPc6DW4iMge-06__manual__other_space_10` 的 k=4 与 `uNb9QFRL6hY-88__manual__other_space_22` 的 k=3。两池分别 N=7、N=5，各保留256条冻结随机前缀路径。实际命中8+25=33条路径引用，但只有2个独立物理团队。成员、路径顺序、参考、票数、坐标和劳动记录保持。没有新增融合或重评分调用；使用端点交付中的既有人工顺序分数。

原自动 Q 为空，不能按0分计算改善。结果使用原 `analyze_response.py` 的路径频数、线性 P10 与 ddof=1 标准差。另保留逆CDF分位数列供定义核查；不会把线性P10与有限穷举团队P10混成同一估计。

## 实际 k 上的数值与支持

|image|N|k|metric|valid_unique_teams_automatic|valid_unique_teams_assisted|valid_paths_automatic|valid_paths_assisted|mean_automatic|mean_assisted|p10_automatic|p10_assisted|sd_automatic|sd_assisted|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|rPc6DW4iMge-06|7|4|B8L2|34|35|248|256|73.467623|72.556038|53.601518|44.857986|14.013133|14.699284|
|rPc6DW4iMge-06|7|4|D10|34|35|248|256|77.362383|76.408560|58.344488|47.569315|13.376245|14.199451|
|rPc6DW4iMge-06|7|4|IoU3D100|34|35|248|256|87.966930|87.445830|80.064680|72.273623|6.313061|6.859686|
|uNb9QFRL6hY-88|5|3|B8L2|9|10|231|256|45.420856|44.478358|30.940435|32.416707|11.388243|11.190052|
|uNb9QFRL6hY-88|5|3|D10|9|10|231|256|48.031063|46.923045|31.612850|33.192708|13.296139|13.070719|
|uNb9QFRL6hY-88|5|3|IoU3D100|9|10|231|256|68.204016|67.565182|58.432364|58.432364|11.452941|11.049696|

来源：[AFFECTED_K_COMPARISON.csv](AFFECTED_K_COMPARISON.csv)。Q均值分别由73.467623降至72.556038、45.420856降至44.478358，来自新纳入的低Q团队，不表示原有可评团队几何恶化。uNb9 的线性P10反而升高，说明均值、尾部与波动不能用单一方向概括。原可评支持上的质量和几何逐行值差为0，见[ORIGINAL_SCORED_SUPPORT_CHECKS.csv](ORIGINAL_SCORED_SUPPORT_CHECKS.csv)。

## 全链实际消费者

两池的 per-k 状态、相邻/固定/到全员路径变化、尾部包络、平台敏感性、短暂平坦后再变化和既有带宽核查全部沿用原函数。stage03 的7张合表按原池行替换，然后直接调用原 `combine_pool_outputs`，保留目标池、图片、建筑不同分母。`FIXED_WINDOW_DOMAIN_SUMMARY.csv`、主起点表及域摘要均已补齐。

stage07 原固定面板曲线、每图边际变化、固定面板变化摘要使用原 `per_k_panels`、`marginal_changes`、`contrast_summaries`；其它域原行保持。`RESULT_FACTS.json` 也经过原 `facts` 函数复现与辅助分支更新。真实变化统计如下：

|table|变化数值格|
|---|---|
|stage03/FIXED_WINDOW_DOMAIN_SUMMARY.csv|103|
|stage03/PRIMARY_SMALL_CHANGE_ONSETS.csv|2|
|stage07/FIXED_PANEL_CHANGE_SUMMARY.csv.gz|385|
|stage07/FIXED_PANEL_CURVES.csv.gz|420|
|stage07/PER_IMAGE_MARGINAL_CHANGES.csv.gz|159|

逐格旧值、新值和差见[AGGREGATE_NUMERIC_CHANGES.csv.gz](AGGREGATE_NUMERIC_CHANGES.csv.gz)。原 stage07 面板成员不变；后段跳变只从 k>=10 开始，两个小池零命中；主平台起点与难度分层起点摘要保持。原 main-only 几何、结构分项、P10定义、有限尾部、连续结构和诊断脚本均无真实命中，未重算。证据见[DOWNSTREAM_CONSUMERS.csv](DOWNSTREAM_CONSUMERS.csv)。

`PRIMARY_SMALL_CHANGE_ONSETS.csv`中的两个辅助诊断格确有变化：uNb9的complete_evaluable_rate和quality_available_rate在不施加后续观察门槛时，首个小范围k由4变3；正式`onset_k`仍为空。这个区别已记录，不能将未通过门槛的诊断起点写成人数平台提前。

|pool_id|table|automatic_rows|assisted_rows|
|---|---|---|---|
|rPc6DW4iMge-06__manual__other_space_10|TRANSIENT_FLAT_THEN_CHANGE.csv.gz|0|0|
|uNb9QFRL6hY-88__manual__other_space_22|TRANSIENT_FLAT_THEN_CHANGE.csv.gz|0|0|
|rPc6DW4iMge-06__manual__other_space_10|REUSED_BAND_ESTIMATE_CHECKS.csv.gz|0|0|
|uNb9QFRL6hY-88__manual__other_space_22|REUSED_BAND_ESTIMATE_CHECKS.csv.gz|0|0|

两池原本没有可复用置信带；没有将不存在的原带宽补为零。保存的空表、实际行数与合表引用保持可核验。

## 结论边界与复现

N=5/7仍只允许描述，不能满足原“至少还观察 max(5,ceil(.15N)) 人”的平台规则；人工顺序补入并不产生平台人数或最优停止人数的新证据。自然主目标、raw k1和原k2处理边界保持。劳动均为原标注劳动；缺少人工排序计时，不能声称包含介入成本的效率改善。

完整运行：`python -m tools.thesis_main.analysis.evaluate_manual_order_natural_20261104`。已有端点及池层输出时，`--finalize-only`仅闭合统计消费者。原汇总复现最大绝对误差 1.42e-14，见[BASELINE_REPRODUCTION.csv](BASELINE_REPRODUCTION.csv)和[CHECKS.json](CHECKS.json)。57组是定向案例，本模块仅2队，不外推所有无环结果可修复。
