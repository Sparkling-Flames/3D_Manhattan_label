# 探索评价口径 v1

本合同只约束本图片画像探索，不替代正式 Paper A 合同。seed=20260914。

- 身份：以 image_id 关联，canonical_annotation_id 标记真实作答。同人同图多条件分开；重复版本不增加独立人数。
- 几何：raw_points 保留原点序；effective_points 是已确认派生视图。主计算报告 reviewed 与不使用 imputed_point 两种覆盖。奇数点不能自动修复；无效和空响应单列。
- 参考质量：复用 tools/thesis_main/analysis/audit_annotation_research_data_20260905.py 的 normalize_geometry、_dense_boundaries、_d_mask；d_mask=1-布局区域交并比，越低越接近参考。解析失败记不可计算。公共数据参考不是人工最终真值，单列来源；reference_not_geometry_ready、missing 和已知坏 GT 不计算质量。
- 结构分歧：同图同条件不同人员之间点数不一致的配对比例；分母仅结构可计算人员对，另报失败比例。点数不同不得进入同一几何簇。
- 簇内波动：先按有效点数分层，计算不同人员对 d_mask 的中位数及各层人数；不把跨点数配对混入。当前名称是 within_topology_geometry_dispersion，不据此宣称最终收敛。
- 范围选择：以 choices 中实际 Scope 字段的类别频数/比例描述，未知或缺失单列；不把少数类别编码成错误。规则正确性必须有独立适用参考。
- 时间：仅 time_source_checks.speed_usable=true 且 main_worker_included=true；目标按图同条件取人员有效秒数中位数，同时报告样本数。lead_time 永不替代 active_time；原始事件仅追溯、不求和回填。
- 预测：每目标独立训练并报告图级 MAE、房/楼宏平均 MAE；Spearman 为次要描述。总体历史常数预测用训练图目标中位数；场景基线用同类训练图目标中位数，未见类型用总体训练中位数并标记。
- 模型选择：采用 config.json 候选；每次外层训练内部再按楼划分选择。PCA/标准化只能在内层训练侧拟合。PCA=None 表示不降维；同分优先更少变换（None）、较小有限维数、较大 ridge alpha、较小 k。训练不足或目标常数明确报告，不补造分数。
- 同房 leave-view 仅用该支持组其他图作为历史依据；人员分型使用组外资料，不能用目标图。没有足够内部组时固定 ridge alpha=10、k=1、PCA=None，不能偷看目标选参。
- 统计单位：648图是输入覆盖，214图有历史响应；条件分别算。统一比较先在候选共同可评价图上配对，再各报全部覆盖。重排和抽人均不增加独立样本。
- 房间：room_components 是支持关系连通分量，绝非完整物理房间普查。待定/不支持重叠整组件不进入同房评价；保守跨房训练排除目标楼所有其他图，因此不能把该结果说成纯同楼跨房泛化。
- 收敛：最终判据未冻结；本包不新增终点人数标签。q=.95 等历史值只作带版本敏感性，不据结果筛阈值。
