# 当前共同输入的 B8L2 / D10 统计

本包从[共同评分入口](../../quality/quality_b8l2_d10_20261017/CROSS_MODULE_INPUTS.json)重新生成，版本 `quality_b8l2_d10_20261017_v2`；当前 3222 份库存、261 图、27 名源身份，质量可用 1911 份。两指标相同作答、参考和资格，B8L2 为工作主指标，D10 是仅方向尺度 8°→10° 的敏感性，**不是 A10**。数量和字段以 [CHECKS.json](CHECKS.json)、[FIELD_CONTRACT.json](FIELD_CONTRACT.json) 为准。

逐人/逐图总库存见 `worker_inventory.csv`、`image_inventory.csv`，分条件分布见 `worker_condition_stats.csv`、`image_condition_stats.csv`。人员×难度见 `worker_difficulty.csv`，人员×门洞/OOS/场景见 `worker_special_axes.csv`；`difficulty_overview.csv` 与 `time_quality_focus.csv` 保留难度分层和质量时间共有集合。

每张表的 B8L2、D10 均值、中位数、样本标准差、四分位和有效 n 并列；作答等权与视角等权均值分别列示。普通、门洞和其它用途单列，manual/semi/oos 不混成均值。OOS 已计算的数值仅在 `diagnostic_quality_stats.csv` 诊断表和逐条诊断字段显示，不恢复质量资格。无数据为 n=0、估计空值。

按用户已有完整分类：`user_original_group_summary.csv` / `user_original_worker_groups.csv` 为人工原组与人员×原组，`room_group_summary.csv` / `room_worker_groups.csv` 为采用工作分组，`room_group_views.csv` 为逐视角贡献，`room_direct_pair_summary.csv` / `room_worker_direct_pairs.csv` 为直接关系对。登记表保留原始分类、成员与分组证据；采用版本 `same_room_user_working_classification_20261016_v2`，不新增逐组确认门，不跨组做传递推断。组可重叠，原组/子组/图对不能相加；未记录同房不等于确认异房。

全部作答含排除和未评分见 `record_lookup.csv`。清洗移出与来源分析不合格分开看 `cleaning_summary.csv`、`exclusion_time_summary.csv`；清洗 retained 尚含重复独立票限制，不能当独立保留人数。逐条多重理由 `exclusion_reason_hits.csv` 不可相加为人数。计算状态见 `calculation_summary.csv`。时间缺失定位 `time_missing_records.csv`，来源时间与同目标时间分别保留，不用 lead_time 或零补缺失。新增70份合计 5205 秒只是任务人员总耗时，新增同目标耗时全部空；既有核实的同目标时间保留，两种时间均只用各自真实非空交集。

运行 `python -m tools.thesis_main.analysis.b8l2_d10_statistics_20261017`。复用既有细致统计和关系描述 helper；在新目录生成，旧冻结评分/统计包未覆盖。4项新边界测试和10项既有细致/关系统计测试通过，覆盖指标同掩码、库存漂移、OOS隔离、分母漂移与新增目标时间空值。地图与目录由统筹线程统一登记。

本包描述当前观察，不训练人员模型、不根据均值修改难度，也不固定论文大纲。未跑全仓测试；任务组成、参考/资格差异和时间口径仍限制跨组因果解释。

[两张关键图](figures/FIGURES.md)：普通难度双指标分布、全部库存质量与计算覆盖；附n、分母、绘图CSV和SVG。
