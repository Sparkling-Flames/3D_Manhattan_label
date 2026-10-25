# 最终条件表的口径

`FINAL_CONDITIONS_COMPACT.csv`按stage、phase、method、role、n、m保存主推荐及有比较价值的邻近条件。`FINAL_CONDITIONS_ALL_COMPONENTS.csv.gz`保留这些条件的全部已汇总分项。完整搜索空间仍在各stage的方法、角色及反推分支表中，未进入紧凑表不是被删除。

同类幅度=|B-A|；跨类幅度=(|C-A|+|C-B|)/2；gap=跨类-同类。主要均值先均衡同XYZ内背景层、再XYZ、方向、图片；建筑另汇总。B8L2、D10、IoU3D100分数越高越好；几何距离只说明变化幅度。定位角误差、omission、extension的负向CB通常表示改善；结构点数增加本身不代表更正确。

每项 *_image_equal 是图片均衡统计；*_raw_count / *_raw_valid_events 是原始事件计数，分母不同，不能互换。*_affected_images 是出现过该风险的图片数。C_failed原始分母包括所有尝试；C_loss10使用对应两队可评分的真实分母。失败未补零，失败/明显损失复合指标独立保留。时间是库存标注记录总秒数的相对变化，不是新测生产耗时；各时间量保留实际图片与事件支持。

source_seats_replaced_fraction=m/A队真实源类席位；fraction_team_replaced=m/n；这两者均不同于m/source_capacity。D目标类人数、目标类全换及Z变化均来自实际成员，不凭类别规模假设。小类定义来自各楼外折历史人数最小类；最大类→最高困难转折角色也只用楼外历史定义。

筛选与确认分开。selection_heldout_building为本轮该次选型未用建筑的内部v2检查，数据不是全新外部盲测。部分补充条件是在此次确认表中发现更有意思的方向，需按补充探索解读，不抹去原stage身份。
