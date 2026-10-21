# n=20 两条件共同端点结论与最后补充

这是已完成 Manual/Semi 分析的精简整合与口径补充，不新增融合、拟合、选型或资格裁定。Manual 主包、Semi 主包和 Semi 机会补包保留各自冻结身份；本补充不覆盖这些包。

## 采用判断

- **Manual M 粗类继续作为结构标法与团队构成的主要解释入口。** 在更广原人员域有小幅外建筑质量响应；同一共同端点上与连续 QT 均值的质量信号同阶。加到 QT 后没有稳定额外收益，不能称为充分团队配方。
- **M 细类保留局部表达和几何机制用途，不默认作为更优质量配比。** 全 M 域细替粗的 B8 预测误差仅降 0.553%/0.129%；在新批共同域反而略差，且 102 个质量池确有同粗内细分机会，不全是机会不足。
- **Manual 新来源 MV 细分有独立于粗分的效率用途。** 新批共同域粗→细的时间响应 R² 为 0.0295→0.2736 和 0.0088→0.0854，误差下降 25.15%/7.73%，两权重均 20/22 楼改善；在 M 锚也同向。但连续 QT/个人二阶矩更好，细类不应替代连续预测。此处“独立于粗分”不表示超出充分连续 QT 的增量。
- **Semi SP 仍保留尺度标法解释身份；本轮不推荐把其细类直接升格为一般 n20 配方。** 宽 SP 域 21 图/12 楼的 B8 粗细外楼 R² 均为负，细分误差增加 1.84%/1.65%。新批共同域只 11 个质量池，其中只有 3 个池有同粗内细分机会，不能把其细微共同域变化泛化。
- **Semi 时间继续优先用连续 QT。** 共同新批域 QT 均值 R²=0.5820/0.5838，加个人二阶矩=0.6223/0.6124；MV 细类仅为 0.0886/−0.0012。其粗细效率增量小、权重敏感，不复制 Manual 的强度。
- **A2 与 Rnew2 保持独立对照方法；F01 本 n20 阶段机会不足。** 不把 M、SP、MV、A2、Rnew2、F01 拼成一套经过统一验证的层级。

上面所有成对数字依次是“配置等权 / 成员宇宙抽样估计”，不是质量百分点。类别 K、团队人数 n=20、每格成员抽样数 r≤3、替换人数 m 分别记录；本批候选的 K 不限制最终研究的类数。

## 共同新批端点上的精确主结果

两条件分别建模。三种分类在各条件内使用同一目标楼外映射、同一端点与同一连续 QT 基线。目标池均值仅用于同图同人数的相对变化中心化；这是响应 R²，不是预测新图绝对质量的 R²。

| 条件 | 结局 | 方法 / 模型 | 图/楼/实际队 | 配置等权 R² | 成员宇宙估计 R² |
| --- | --- | --- | --- | --- | --- |
| manual | B8L2 | M_structure / coarse_source | 125/22/46259 | 0.025968 | 0.011217 |
| manual | B8L2 | M_structure / fine_source | 125/22/46259 | 0.024932 | 0.010160 |
| manual | B8L2 | A2_relation / coarse_source | 125/22/46259 | 0.017658 | 0.001942 |
| manual | B8L2 | MV_QTD_manual_new / coarse_source | 125/22/46259 | 0.020099 | 0.001967 |
| manual | B8L2 | MV_QTD_manual_new / fine_source | 125/22/46259 | 0.018561 | 0.001546 |
| manual | B8L2 | M_structure / QT_source | 125/22/46259 | 0.023945 | 0.008613 |
| manual | B8L2 | M_structure / QT_moments_source | 125/22/46259 | 0.024206 | 0.007144 |
| manual | log_source_time_total | M_structure / coarse_source | 125/22/46436 | 0.026485 | 0.002128 |
| manual | log_source_time_total | M_structure / fine_source | 125/22/46436 | 0.028284 | 0.006242 |
| manual | log_source_time_total | A2_relation / coarse_source | 125/22/46436 | 0.020214 | 0.006286 |
| manual | log_source_time_total | MV_QTD_manual_new / coarse_source | 125/22/46436 | 0.029514 | 0.008784 |
| manual | log_source_time_total | MV_QTD_manual_new / fine_source | 125/22/46436 | 0.273586 | 0.085371 |
| manual | log_source_time_total | M_structure / QT_source | 125/22/46436 | 0.621509 | 0.543245 |
| manual | log_source_time_total | M_structure / QT_moments_source | 125/22/46436 | 0.668419 | 0.602120 |
| semi | B8L2 | SP_scale / coarse_source | 11/8/215 | -0.009495 | -0.015793 |
| semi | B8L2 | SP_scale / fine_source | 11/8/215 | -0.006119 | -0.010344 |
| semi | B8L2 | A2_relation / coarse_source | 11/8/215 | -0.006316 | -0.019681 |
| semi | B8L2 | MV_QTScopeSemi_semi_new / coarse_source | 11/8/215 | -0.005261 | -0.008722 |
| semi | B8L2 | MV_QTScopeSemi_semi_new / fine_source | 11/8/215 | -0.035238 | -0.024576 |
| semi | B8L2 | SP_scale / QT_source | 11/8/215 | -0.020973 | -0.040090 |
| semi | B8L2 | SP_scale / QT_moments_source | 11/8/215 | -0.028045 | -0.048192 |
| semi | log_source_time_total | SP_scale / coarse_source | 12/9/233 | -0.009701 | -0.007797 |
| semi | log_source_time_total | SP_scale / fine_source | 12/9/233 | -0.003476 | -0.001376 |
| semi | log_source_time_total | A2_relation / coarse_source | 12/9/233 | 0.002007 | 0.030491 |
| semi | log_source_time_total | MV_QTScopeSemi_semi_new / coarse_source | 12/9/233 | 0.041480 | -0.008616 |
| semi | log_source_time_total | MV_QTScopeSemi_semi_new / fine_source | 12/9/233 | 0.088579 | -0.001201 |
| semi | log_source_time_total | SP_scale / QT_source | 12/9/233 | 0.581985 | 0.583846 |
| semi | log_source_time_total | SP_scale / QT_moments_source | 12/9/233 | 0.622279 | 0.612410 |

本表来自各条件 `N20_PREDICTION_SUMMARY.csv`，完整 16 分项保存在 `N20_COMMON_ENDPOINT_DECISION_TABLE.csv`。重复列出的 QT 是有意保留的共同支持核验：同一支持层内各分类的 QT 数值一致，而非各自挑选对自己有利的成员。

## 支持和反例

Manual 共同新批域 125 图/22 楼，质量 46,259 队，时间/失败 46,436 队；共同人员域为 21–35 人、中位 30 人，其中 106 图不少于 25 人，已经包含非近满员情况。M 锚另有 100 图/22 楼、3,388 个质量队，不能择优只保留一个锚。原面板与新增图分别汇总，既有反复探索过的 v2 数据不改称盲测。

Semi 共同新批域质量 11 图/8 楼/215 队；时间/失败 12 图/9 楼/233 队。实际共同池为 21–22 人，主要仍是近满员。SP 采样锚只有 2 个共同支持池，训练楼数不足，没有强行产生模型结果。`yqstnuAEVhm-01` 的新批 MV 有 6 个配置、18 队全部 no_connection：质量不可评，失败仍保留，不把全失败的零响应称为稳定正确。

Manual 新批共同域成员宇宙估计下，M 粗类 Hcenter/Hmean R²=0.0304/0.0234，IoU3D100=0.0206，底面 IoU=0.0131，角点数=0.0079，omission/extension=0.0040/0.0123；M 细类没有整体增益。失败 R² 仅约 0.00007，其余现代方法接近零或负，不支持把类别向量当作一般失败预测器。Semi 个别几何项的小幅正值不改变其宽域粗细总评价。

Rnew2 本批可评 63 池/12 楼/1,640 个质量终点，全部结局 1,647 队。类别 B8 R²=0.0250/0.0002，同端点 QT=0.0519/0.0161，加入类别没有超过 QT。F01 有 76 池缺合法原外楼映射，其余 92 池只有 8–17 名原标签人员，n20 不可组成；这是精确机会不足，不是新的效果负结果。完整未形成映射和不够两队的分母见各条件 `N20_COMMON_SUPPORT.csv`。

## 时间单位、结构和损失尾部

时间结局为 20 人源记录秒数之和的自然对数。总秒数可除以 3,600 转总人员小时；这里没有使用最大等待时间，也不是并行墙钟。20 人均需有时间且来源一致。新批 `user_processed_reported_not_raw_log_replayed` 与旧 `inherited_v1_audited_source` 保留各自身份，混合来源团队不进入时间结局。二阶矩是个人历史 QT 特征平方的团队均值，可补充异质性；不是把目标时间直接泄漏入特征。

质量损失尾部、相同背景和实际替换人数 m 的同类/跨类差，以及必要结构的票数门槛机制，由独立 `n20_abc` 事件分支给出。本共同响应分析不将 MSE、一般格间方差或 r≤3 的格均值冒称同背景替换效应。两个分支回答互补问题；全局共享响应模型的负 R² 不意味着原答标法不存在，也不意味着每个局部换类都无效。

## 本追加包的身份和复现

`N20_COMMON_QT_HIERARCHY_INCREMENT.csv` 从已冻结的楼级误差汇总两个直接对照：类别粗分+QT 对 QT，以及细分+QT 对粗分+QT。`semi/N20_HIERARCHY_QT_INCREMENT.csv` 为 Semi 的新保存补充表；没有新拟合或按结局重新选方法。代码 `hierarchy_qt_increment_n20.py` 保留全部指标及固定 bootstrap。两权重定义、共同支持条件化与原细格锚口径见 `N20_WEIGHTING_CLARIFICATION_ZH.md`。

各主包还有完整质量分项、池/楼表、模型秩、抽样成员宇宙恒等式与恢复说明。独立复核在 `../next_stage/analysis_check/`，重算粗细及 QT 数值最大差 2.36e−16，未发现阻断问题。本文件不把该小复核描述为所有建模假设都已被证明。
