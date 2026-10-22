# 输出字段与接入合同

主键：`record_id + object_id + image_id + reference_id + condition`。同一对象多个参考不能转化为多个独立人。当前1145表每个record_id唯一，未做max参考选择。

`Q_WQ`、`Q_A10`、`Q_B8L2`：不同连续质量指数，0–100；不是概率或固定百分比正确率。`Q_IoU3D`为同参考现用角点均高棱柱IoU百分比。`WQ/current/A/RA/IoU3D100`等输入原列完整保留；注意输入的`A`是上一轮算术候选，不是本轮`Q_A10`。

`comparison_layer`只建立本轮明确比较分层；不改变原始`role/condition/stage`、资格或正式gate。`production_default_changed=false`。

`delete_*_gain`：同一对象参考、其余原始分项固定，仅将指定分项设置为理想值的实际分数增量。是算子消融，不是修复几何后的预测值，不是因果归因，不能加和解释为总扣分。

`shapley_loss_*`：对五个分项的32种理想/实际组合计算平均边际损失；可相加到100−Q，属于分摊约定，不是固定权重，不证明误差来源。

`floor_fidelity_loss=1/I−1+Sb²/32`。`effective_extra_direction_loss`是组合尺度中加入D后的增量，不等于总分扣分。`subadditive_loss_discount`是算术相加与候选几何合并的差，不是已估得的真实重复误差。

两图：`new_full_*`、`new_top_confirmed`、`adopted_reference_id`均不因数值可算而填充。`*_floor_upper_*`是非负高度损失下的保守上界，不保证物理可达，也不得混入完整分排名。`scope_pattern`是无分数输入的几何模式提示，非视觉裁决。

难度：按`image_id`及已冻结`difficulty_reference_id`接入。`same_reference_id`只声明ID一致；本轮无新的全几何校验。95个异参考结果不可混入同目标难度关系。

人员：中心化单位为图片×参考×条件，单元内先按工人聚合，再跨单元汇总。至少5单元只是输出支持门。`relative_tercile`是相对排名敏感性，不是人类五档、正式多轴分类或生产能力标签。没有改票权。

融合：`operation=fixed_endpoint_rescoring_no_reselection_or_refusion`。`second_minus_first`的版本名逐行保存，本快照first=assisted、second=automatic；报告中的“辅助减自动”须取负号。另表`leave_building_selection_diagnostic`是目标整栋排除后，在已有参与者中选择的个人集合及其均分，不是新融合。
