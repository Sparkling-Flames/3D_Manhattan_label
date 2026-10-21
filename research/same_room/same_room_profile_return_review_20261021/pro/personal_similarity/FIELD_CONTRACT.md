# 本轮个人同房质量：字段与接入合同

本目录全部实算来自 commit `561584c8f64d5349d497ec1c6e91f1aeb4bbd7c9`。旧 47.1 MiB 包原件未在重置工作区找到；这里是**本轮新增计算**，其中旧预测目标面板与划分直接复用仓库表，不标为原包恢复。原始 Q、参考、资格、点位和点序均未重算或修改。

## 对象、关系与资格

- 原答主键：`object_id`；逐人任务：`image_id + condition + worker_id`。本次正式面板该键唯一。
- 比较任务键：`image_id + condition + reference_id + reference_version`。`chosen_target_id` 必须等于现用 `current_target_id`。
- 直接关系主键：`pair_id` 是采用关系 `relations.json` 的零起始行序号；同时保留两端完整 `image_id`，因此不依赖单独序号定位。
- `user_groups` 保留重叠原声明，不作传递闭包。`scope_comparable` 与物理同房、质量资格分开。
- 正式 Q 要求 `pool_analysis_eligible && quality_usable && !is_oos`，`quality_use` 为 `ordinary_primary/doorway_quality`，参考现行且 B8L2、D10 可算。门洞独立列为 `layer=doorway`。
- 训练许可复制已发布 `training_admission.csv`。旧人员 holdout、人员/背景障碍不恢复；该许可只约束拟合及楼外画像，不把有效评价作答删除。

## 描述表

`direct_pair_workers.csv.gz` / `direct_pair_workers_with_class.csv.gz` 每行一名共同人员的一条无向直接图对。

- `Q_a/Q_b`：原 B8L2；`D10_a/D10_b`：原 D10。
- `relative_a/b`：本人 Q 减同图、同条件、同参考其他正式人员的均 Q。
- `common_relative_a/b`：只用该图对固定共同人员构造的留本人残差。
- `external_theta`：目标建筑外、训练许可普通 Manual 作答的留本人同行残差均值；同行也限训练许可。缺值保持 NA。
- `surprise_a/b = relative_a/b - external_theta`。这不是新评分，只是分析剩余项。
- `rank_a/b`：该图正式人员 Q 的百分位排名，平分平均名次。
- `primary_*_class`：目标建筑对应 `labels/lobo_labels.csv` 的已校正采用标签；`label_version`、`heldout_building` 一并保存。
- `object_a/b`、`source_a/b`、`reference_a/b`、`code_a/b` 可连接到原答、导出来源、参考和原图 Release。
- `low_a/b` 固定为 Q<50，只作描述和结果变量。

`worker_repeatability.csv` 先在每人每建筑内平均直接图对，再对建筑等权。它描述谁经常相对好/差；不能把稳定的整体人员水平称为该人的房间专长。`symmetric_pair_Q_rho` 将每个无向图对同时按两种方向计入，消除图名排序方向的任意性。

`declaration_common_matrix.csv.gz` 为每个原声明有质量支持的视角与**全组共同人员**完整矩阵。`declaration_variation_partition.csv` 将总平方和分成行均值、列均值和双中心剩余项；这是描述性平方和分解，不能当作已识别的因果/随机效应方差。两视角分解尤其不能用“人员份额”直接充当重复性系数。没有共同人员的 G172 等仍保留在 `declaration_support.csv`，并继续进入图对与留出研究。

## 留出预测

`prediction_design.csv.gz` 每行一个 `row_id`，保留 `group_id/split_id/target_image/worker_id/m/N/source_images/target_object_id`。

- `budget=majority`：完全复用原 `m>N/2` 的所有历史组合及固定跨 m 目标人员支持。
- `single_matched`：相同多视角目标人员，每次只给一个本人实际答过的源视角。
- `single_direct`：所有范围可比普通 Manual 直接同房图对，双向单源；覆盖两视角房间。
- `source_images` 是本人确有作答的源图。公共均值、本人均值和类别/近邻源信息都只使用这组相同源图；没有借缺本人作答的额外历史图。
- 所有同行均值、低尾比例、标准差均排除本人。计算同类/近邻其他人的源残差时，也把被预测的本人从那些人的同行基准中排除。

信息分解：公共源均值 `peer=P`；楼外个人相对水平 `theta`；本人同房剩余项 `own_surprise=mean(Q_source-peer_source)-theta`。`public_external=clip(P+theta)`；加入完整剩余项等于本人源 Q 均值，半项为固定收缩对照。

类别与近邻信息先对其他人的源残差扣除他们的楼外 theta，再平均。`class_fine/coarse` 使用原采用层级；`neighbor` 使用六个楼外连续标法特征空间的固定五近邻。三者都用固定 2 个零残差先验量收缩，真实同伴数另列；零先验不是伪造作答。缺类/无同伴没有被解释成实际零误差。

外层按整栋建筑留出。训练行的楼外个人历史同时排除外层目标建筑和该训练行的建筑。整折类别/连续标法字段取外层建筑排除的已发布版本；不重新分型。任何拟合、标准化、缺值中位数均仅使用训练建筑。训练响应及本人的源作答沿用旧训练许可。

`prediction_rows.csv.gz` 保留每次历史的宽格式预测，是可选大结果。主交付的小表 `prediction_worker_targets.csv.gz` 先平均同一人员/目标/组/m 的历史误差；`prediction_targets.csv` 再平均人员。主汇总依次平均重复组、图片、建筑，避免 G172 的大量组合支配结果。主 MAE 是**各历史实际误差的平均**，不是把所有历史预测先平均再算误差。

排序亦先在每个真实历史划分的共同支持人员中计算，再平均；不把单源预算偷偷换成所有源均值的排序。`actual_low_quality_diagnostic.csv` 的目标 Q<50 是事后诊断，不是选人/训练输入。`lowtail_*` 的概率使用同样留楼流程；Brier 和 logloss 与绝对 Q 误差分开。

## 缺失与支持

未知/不合资格未填 Q=0。主描述有 2581 个人图对，其中 1 条 W022（S9h-06/-10）缺合法楼外历史；剩余项与需要它的预测只在实际有值的支持上计算。每模型实际 train/test 行、建筑及唯一目标原答数见 `model_folds.csv`。大量历史、方向、重叠组不是独立房间或图片。

`selected_person_cases.csv` 和 `selected_person_geometry.json` 为 G130/G202 的人工可读原答切片；几何仅从同一冻结证据逐字段摘取。主报告的照片/叠加由综合包提供。
