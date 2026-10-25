# N−1 边际的失败与稀少可评支持

这是一份现成数据的有限汇总，没有追加融合、随机种子或案例图。

对 194 个普通/门洞 Manual 池的完整 N−1 团队边际逐池检查，8 个池存在正式融合失败。原 24 条都至少观察到过一次失败；本轮没有找到“旧 24 完全未见失败、精确总体存在失败、追加顺序又看见失败”的例子。`MISSED_FAILURE_CANDIDATE_SCAN.csv` 保留全部池；`MISSED_FAILURE_SELECTION.json` 记录零个符合该条件的案例。

发现的另一个现象是：以下两个门洞池，原 24 条没有任何可评分结果，但精确有限总体各有一个可评队。

| 图 / 池键 | N / k | 精确可评 / 失败队 | 唯一可评队的缺席者 | 可评队 B8L2 |
|---|---|---|---|---:|
| B6ByNegPMKs-42 / B6ByNegPMKs-42__manual__1f4ce2fd4e | 34 / 33 | 1 / 33 | W121 | 45.534421 |
| b8cTxDM8gDG-08 / b8cTxDM8gDG-08__manual__fd6a69296e | 35 / 34 | 1 / 34 | W123 | 14.679865 |

| 图 | 原 24 | 独立新 24 | 合并 48 | 独立新 72 | 合并 96 |
|---|---|---|---|---|---|
| B6ByNegPMKs-42 可评/尝试路径 | 0/24 | 1/24 | 1/48 | 2/72 | 2/96 |
| b8cTxDM8gDG-08 可评/尝试路径 | 0/24 | 1/24 | 1/48 | 1/72 | 1/96 |

独立新 72 为本轮新 24 加焦点追加 48，不含原 24。这里的缺 Q 从零条变成一条或两条，是稀少可评团队被抽中的结果，不是质量提升；所有可评路径都指向各图同一个实际团队。完整失败率仍很高，不能只展示条件质量。

`RARE_SUCCESS_EXACT_TEAMS.csv.gz` 保留 69 个精确队及成员、对象、参考、状态和分项；`RARE_SUCCESS_REGISTERED_PATHS.csv` 保留两图全部 192 条自然路径的关联；`RARE_SUCCESS_SUPPORT_SUMMARY.csv` 为上表及各预算完整分母；`RARE_SUCCESS_ONLY_EVALUABLE_TEAMS.csv` 是两个可评队的完整标量。来源都是统一注册设计的 `EXACT_MARGINAL_VALUES.csv.gz` 和新、旧前缀值表。

代码：上层 `find_missed_leave_one_out_failure.py` 与 `summarize_rare_success_support.py`。未重新评分、调整融合规则或更改失败定义。
