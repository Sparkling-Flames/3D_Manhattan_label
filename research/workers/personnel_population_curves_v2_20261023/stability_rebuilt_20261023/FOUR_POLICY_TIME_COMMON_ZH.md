# 四策略相同pool/base/k的同语义共同域：只重新汇总

从现有精确前段事件自然取交集，没有新增团队、重抽或补齐缺失。先要求四策略都存在，再要求同一自然队与四个策略队的时间分别齐全、队内语义单一且五队语义相同。质量/时间/坏尾进一步要求五队全可评；失败另在前一层全部时间合法尝试中报告，不以QT全可评交集的零失败证明无风险。

|条件|分层|时间语义|域|图片|建筑|base×k配对单位|
|---|---|---|---|---:|---:|---:|
|manual|doorway_manual|all_semantics_design_denominator|four_policy_design|17|9|1,968|
|manual|ordinary_manual|all_semantics_design_denominator|four_policy_design|157|22|18,056|
|manual|special_manual|all_semantics_design_denominator|four_policy_design|1|1|104|
|semi|ordinary_semi|all_semantics_design_denominator|four_policy_design|21|11|3,008|
|semi|special_semi|all_semantics_design_denominator|four_policy_design|1|1|160|
|manual|doorway_manual|user_processed_reported_not_raw_log_replayed|four_policy_time_common|3|2|202|
|manual|ordinary_manual|user_processed_reported_not_raw_log_replayed|four_policy_time_common|67|18|4,613|
|manual|special_manual|user_processed_reported_not_raw_log_replayed|four_policy_time_common|1|1|104|
|semi|ordinary_semi|user_processed_reported_not_raw_log_replayed|four_policy_time_common|4|4|218|
|manual|doorway_manual|user_processed_reported_not_raw_log_replayed|four_policy_QT_common|2|2|61|
|manual|ordinary_manual|user_processed_reported_not_raw_log_replayed|four_policy_QT_common|67|18|4,304|
|manual|special_manual|user_processed_reported_not_raw_log_replayed|four_policy_QT_common|1|1|96|
|semi|ordinary_semi|user_processed_reported_not_raw_log_replayed|four_policy_QT_common|4|4|218|

|条件|分层|时间语义|策略|共同QT支持|Q差值|时间比|Q损失>5|
|---|---|---|---|---|---:|---:|---:|
|manual|doorway_manual|user_processed_reported_not_raw_log_replayed|joint_fast_first|2图/2楼|-2.171|0.939|14.8%|
|manual|doorway_manual|user_processed_reported_not_raw_log_replayed|joint_highq_first|2图/2楼|+19.411|1.038|5.5%|
|manual|doorway_manual|user_processed_reported_not_raw_log_replayed|structure_dominant_first|2图/2楼|-1.844|0.957|25.9%|
|manual|doorway_manual|user_processed_reported_not_raw_log_replayed|structure_moreturn_first|2图/2楼|+13.492|1.214|3.7%|
|manual|ordinary_manual|user_processed_reported_not_raw_log_replayed|joint_fast_first|67图/18楼|-0.873|0.776|14.0%|
|manual|ordinary_manual|user_processed_reported_not_raw_log_replayed|joint_highq_first|67图/18楼|+7.419|1.026|4.4%|
|manual|ordinary_manual|user_processed_reported_not_raw_log_replayed|structure_dominant_first|67图/18楼|-3.255|1.021|22.7%|
|manual|ordinary_manual|user_processed_reported_not_raw_log_replayed|structure_moreturn_first|67图/18楼|+6.810|1.097|5.4%|
|manual|special_manual|user_processed_reported_not_raw_log_replayed|joint_fast_first|1图/1楼|+0.935|0.754|20.8%|
|manual|special_manual|user_processed_reported_not_raw_log_replayed|joint_highq_first|1图/1楼|+29.338|0.991|5.8%|
|manual|special_manual|user_processed_reported_not_raw_log_replayed|structure_dominant_first|1图/1楼|+0.573|1.210|25.5%|
|manual|special_manual|user_processed_reported_not_raw_log_replayed|structure_moreturn_first|1图/1楼|+22.923|0.997|8.7%|
|semi|ordinary_semi|user_processed_reported_not_raw_log_replayed|joint_fast_first|4图/4楼|-2.364|0.764|12.5%|
|semi|ordinary_semi|user_processed_reported_not_raw_log_replayed|joint_highq_first|4图/4楼|-1.898|0.976|12.5%|
|semi|ordinary_semi|user_processed_reported_not_raw_log_replayed|structure_dominant_first|4图/4楼|-2.131|1.060|12.5%|
|semi|ordinary_semi|user_processed_reported_not_raw_log_replayed|structure_moreturn_first|4图/4楼|-2.497|0.850|12.5%|

|条件|分层|时间语义|策略|自然失败/全部尝试|策略失败/全部尝试|图等权自然失败率|图等权策略失败率|差值百分点|
|---|---|---|---|---:|---:|---:|---:|---:|
|manual|doorway_manual|user_processed_reported_not_raw_log_replayed|joint_fast_first|87/202|76/202|63.01%|59.66%|-3.355|
|manual|doorway_manual|user_processed_reported_not_raw_log_replayed|joint_highq_first|87/202|12/202|63.01%|4.22%|-58.793|
|manual|doorway_manual|user_processed_reported_not_raw_log_replayed|structure_dominant_first|87/202|103/202|63.01%|67.94%|+4.924|
|manual|doorway_manual|user_processed_reported_not_raw_log_replayed|structure_moreturn_first|87/202|17/202|63.01%|6.11%|-56.899|
|manual|ordinary_manual|user_processed_reported_not_raw_log_replayed|joint_fast_first|53/4613|110/4613|0.72%|1.59%|+0.868|
|manual|ordinary_manual|user_processed_reported_not_raw_log_replayed|joint_highq_first|53/4613|4/4613|0.72%|0.05%|-0.668|
|manual|ordinary_manual|user_processed_reported_not_raw_log_replayed|structure_dominant_first|53/4613|243/4613|0.72%|3.38%|+2.661|
|manual|ordinary_manual|user_processed_reported_not_raw_log_replayed|structure_moreturn_first|53/4613|5/4613|0.72%|0.07%|-0.655|
|manual|special_manual|user_processed_reported_not_raw_log_replayed|joint_fast_first|1/104|8/104|0.96%|7.69%|+6.731|
|manual|special_manual|user_processed_reported_not_raw_log_replayed|joint_highq_first|1/104|0/104|0.96%|0.00%|-0.962|
|manual|special_manual|user_processed_reported_not_raw_log_replayed|structure_dominant_first|1/104|0/104|0.96%|0.00%|-0.962|
|manual|special_manual|user_processed_reported_not_raw_log_replayed|structure_moreturn_first|1/104|0/104|0.96%|0.00%|-0.962|
|semi|ordinary_semi|user_processed_reported_not_raw_log_replayed|joint_fast_first|0/218|0/218|0.00%|0.00%|+0.000|
|semi|ordinary_semi|user_processed_reported_not_raw_log_replayed|joint_highq_first|0/218|0/218|0.00%|0.00%|+0.000|
|semi|ordinary_semi|user_processed_reported_not_raw_log_replayed|structure_dominant_first|0/218|0/218|0.00%|0.00%|+0.000|
|semi|ordinary_semi|user_processed_reported_not_raw_log_replayed|structure_moreturn_first|0/218|0/218|0.00%|0.00%|+0.000|

每个指标先逐图逐k对合法base路径平均，再在该共同域可用k等权，最后按图片/建筑汇总。四策略在同一来源层的图、k和base支持完全一致；算术时间比不是总秒数之比。逐图及楼等权值也保留在CSV。这个交集是更窄的观察域，不能代替157图全质量结果。快类在自身来源时间子域68图Q+0.228；严格四策略交集67图18楼（还缩小了同图的base/k支持）为Q−0.873、时间比0.776、坏尾14.0%，与157图全质量共同域Q−1.651并列。这是支持变化，不能把正值写成普遍无质量代价。高Q优先在该67图共同域Q+7.419、时间比1.026；较多转折优先Q+6.810、比1.097，坏尾分别4.4%、5.4%。

`FOUR_POLICY_COMMON_TIME_EFFECTS.csv`的`four_policy_time_common`保留自然和策略的Q不可用、评分失败、不完整及差值，分母为全部共同时间合法base×k尝试；不完整/失败定义沿用冻结原标量。`four_policy_QT_common`的质量/时间分母另列。表中的事件行数只是精确覆盖，不是独立样本数。

代码：`python code/describe_common_time_support.py --root .`。输出`results/time_semantics/FOUR_POLICY_COMMON_TIME_*.csv*`；没有重抽区间，采用范围以实际图/楼/配对单位为准。
