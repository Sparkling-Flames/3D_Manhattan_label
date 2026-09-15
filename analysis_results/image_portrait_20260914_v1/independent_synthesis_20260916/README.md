# 本轮返回包的接收方独立复核

[中文判断与导师讨论对照](../../../docs/thesis_main/图片难度与收敛_多轮证据及导师讨论对照_20260916.md)。原报告／517个新文件在`../cloud/image_links_after_review_20260915_v1/`，未改原作者结果。

复算：在仓库根运行`python -m tools.thesis_main.analysis.image_portrait.image_links_independent_audit "C:/Users/ASUS/Downloads/image_links_after_review_study.zip"`。读取原ZIP可避免长路径问题；相机复算还读取本地既有`models/da3/multiview/*.geometry.npz`。依赖numpy、pandas、statsmodels，不调用视觉网络。该命令只写本目录的审计产物。

字段说明：`family_paired_summary.csv`中`loss`为模型家族按保存内层损失选层后的外层损失，`baseline_loss`为相同图基线，`delta=loss-baseline_loss`，`lo/hi`为2000次楼级重采样区间；`images/buildings`是配对分母。分类为三类Brier之和，过程为MAE，不跨目标比较绝对值。选层逐图依据在`family_selected_predictions.csv.gz`。`da3_fixed_layers.csv`固定候选层全部保留，不能看外层最低值再称预先选定。

`boundary_sensitivity.csv`记录全体／n≥19与log人数／人数类别控制，其他控制为场景和楼。部分设计矩阵秩不足；运行时出现过其他控制项协方差对角的sqrt警告，本文使用的partial对比区间均有限。小样本和稀疏对照限制解释，不按区间给图片自动定类。`da3_camera_recheck.csv`从316对相机输出重新核对已知六面方向，必要一致性通过仍不等于物理正确。

本地验证：原包`tests/test_image_links_followup.py`在短路径隔离副本33项通过；本仓库`tests/test_image_links_independent_audit.py`1项通过。环境numpy1.26.4、pandas2.3.1、scipy1.11.4、statsmodels0.14.2、pytest8.3.5，与Pro固定版本并不完全相同。没有重新拟合155种预测方案；没有用户审核、原图目视判断或新独立人员样本。完整性、损失及配对复算见`audit.json`，迁入范围见`migration.json`。
