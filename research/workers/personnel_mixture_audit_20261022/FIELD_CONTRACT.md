# 审计派生表字段与分母

- `SOURCE_FILES.csv`：每个ZIP来源成员一行；同字节公共文件可共用`repository_path`。bytes为源文件解压长度；不包含哈希。
- `RECOMPUTED_DECOMPOSITION.csv`：condition×domain×method×outcome×stratum一行。`total_variance/within_variance/between_variance`为先面板、再图、再楼的平均方差（原量单位平方）；`between_share`为后二者聚合后相除。单格成员数为1时不能证明内部稳定。零总方差的比例留空。
- `RECOMPUTED_PREDICTION.csv`：同上但method改model；mse/baseline_mse为保存逐面板误差重聚合，`response_r2=1−mse/baseline_mse`。`positive_buildings`为该楼平均mse小于基准的楼数。未重新拟合，未重算bootstrap区间。`stratum=difficulty`沿用冻结面板粗类，已另与主线逐图核对。
- `F01_RECOMPUTED_CONFIGURATIONS.csv`：panel_id×fast_C01_n一行。Q/D10为非缺失均值，B8L2_std为总体标准差ddof=0；分位数为线性插值；失败分母为该构成全部团队。time为全体成员来源记录秒数总和，不是并行完工时间。
- `F01_RECOMPUTED_CONTRASTS.csv`：每个有至少两种构成的面板一行。delta为最多快类减最少快类，时间为相对百分比，失败差为百分点。未固定同一共同背景。
- `F01_PANEL_VARIANCE.csv`及`F01_VARIANCE_SUMMARY.csv`：先按真实成员集合等权分解，再按图/楼汇总；仅包含有构成变化的12图。Q/D10排除无值团队，failure保留全部；失败状态为1、成功0。时间使用原始秒数，不能与response的log时间占比直接排名。
- `PANEL_DIFFICULTY_LINK.csv`：336个冻结面板，各一行；保留原difficulty及主线coarse_class，附当前target_id、特殊场景和完整参考状态。图号/难度匹配不等于已核对每个源端点实际评分参考。
- `CHECKS.json`：本次逐面板/成员重聚合行数和最大偏差；`OLD_N20_CHECK.json`区分逐事件重聚合和保存楼级值复核，其sources、aggregation及证据限制为字段说明的一部分。

各表的面板/图片/建筑数不能相加为独立样本；域、指标和难度层的有效支持不同。Manual/Semi分开，v1人数曲线不并入本包v2结果。
