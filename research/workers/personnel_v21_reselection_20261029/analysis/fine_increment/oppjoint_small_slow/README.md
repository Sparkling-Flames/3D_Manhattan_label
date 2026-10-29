# OPPJOINT K4小慢类：有限面板内m1严格ABC

来源角色在目标楼外冻结：每折相对log时间最高、人数≤6、log时间中心≥0.7的类，与它唯一的同父快细类比较。阈值识别已存在的小慢角色，没有按目标质量调类。

`COMMON_BACKGROUND_TARGETS.csv.gz`给出完整D、目标Z及全部可选源成员和端点。`EXACT_UNORDERED_ABC_SOURCE_PAIR_INDICES.csv.gz`每行的source_i/source_j是0起点，指向对应背景行按|分隔的source_workers/source_team_keys；两人分别为X/Y，Z和D已经固定。无序源对只列一次，两种A/B方向各半权。因此有符号BA的总体均值为0，CA/CB相同是设计对称性；同类/跨类绝对变化仍逐真实端点计算。

全部8,316无序三队组合都满足实际换人数1、完整父类人数向量不变。5,157个背景独立作为覆盖单元，先平均其所有源对，再按面板→目标→图片→楼汇总。这里的独立指不同的成员集合背景，不是统计独立抽样假设。

`BACKGROUND_TARGET_METRICS.csv.gz`保留全部质量、结构、几何、时间和失败。时间只有三队完整记录、同一来源时可用；`B8L2_on_time_support`给同时间分母的Q。`SMALL_SLOW_ROLE_SUMMARY.csv`的CA/CB为建筑等权，逐图表可算图均。实际覆盖及无机会面板在 `PANEL_OPPORTUNITY_AND_COVERAGE.csv`。

`REVERSE_DIRECT_AC_TIME_SAME_SUPPORT.csv.gz`保留反向AC的实际时间比，`REVERSE_DIRECT_AC_SUMMARY.json`同时给图均和楼均。反向缺少同小类B，不作严格ABC结论。

原始合法目标、GT、质量及融合均未改变；0新增融合。端点标量和精确成员在 `USED_ENDPOINT_SCALARS_AND_MEMBERS.csv.gz`，全几何仍引用阶段03B主目标库存。未枚举有限面板之外的全人员池组合。
