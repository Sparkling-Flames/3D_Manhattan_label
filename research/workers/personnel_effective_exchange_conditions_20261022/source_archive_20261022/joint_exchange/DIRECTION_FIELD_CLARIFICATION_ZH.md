# 方向解释字段补充

冻结成员、背景和预测选类全部不变。缓存登记中的 training_QT_direction 来自实际 Y/Z 成员楼外历史均值，早期 summary 的 center_ 前缀不够准确。最终另存 TRAINING_DIRECTIONS 表：training_class_center_QT_direction 由本折完整类别中心与 Y/Z 类别人数向量求得；training_member_QT_direction 保留实际成员历史方向。最终中心条件表统一使用前者；原登记字段及SHA不改。原生纯类块原字段本来就是完整类别中心方向，因此其主结果不变。

这是一项解释字段身份修正，不新增或删除端点、事件，不重选候选，不改变楼外类别或冻结预测模型。预测双优子集按原 pred_QT_both_improve_BC 字段保留。
