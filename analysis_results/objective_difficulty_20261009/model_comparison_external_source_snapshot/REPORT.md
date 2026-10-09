# 图片难度：本地模型信号与点数对照

2026-10-09。先提取不使用GT／人员作答／难度标签的模型输出，再离线连接主观标签。所有结果仍为回顾性研究候选。

## 覆盖与面板

全研究图259；旧共同普通面板136图/42标签，扩展raw普通面板216图/112标签。边界修正另有162图/84标签可计算。

原三个代理和新三个候选在old_common上各自重做同建筑留出；expanded_raw单独计算，不能跨面板比较高低。普通仍含clear和unflagged，未标特殊不认证正常。特殊图原始信号保留、不进主观选权。

|面板|候选组|评分/单轴|标签图|建筑|Spearman|建筑等权MSE|
|---|---|---|---:|---:|---:|---:|
|old_common|new_raw_candidates|baseline_score|42|14|0.6226|0.1245|
|old_common|new_raw_candidates|calibrated_score|42|14|0.8177|0.0646|
|old_common|new_raw_candidates|hohonet_replay_pair_count|42|14|0.8177|0.0646|
|old_common|new_raw_candidates|hohonet_rotation_mae_deg|42|14|0.4135|0.2070|
|old_common|new_raw_candidates|bilayout_raw_relative_gap|42|14|0.2799|0.2168|
|old_common|original_three_proxy_candidates|baseline_score|42|14|0.6567|0.1122|
|old_common|original_three_proxy_candidates|calibrated_score|42|14|0.8197|0.0646|
|old_common|original_three_proxy_candidates|hohonet_offline_pair_count|42|14|0.8197|0.0646|
|old_common|original_three_proxy_candidates|d_model_feat_static|42|14|0.5299|0.1703|
|old_common|original_three_proxy_candidates|bilayout_floor_gap|42|14|0.1923|0.1978|
|expanded_raw|new_raw_candidates|baseline_score|112|18|0.5160|0.1449|
|expanded_raw|new_raw_candidates|calibrated_score|112|18|0.5941|0.1266|
|expanded_raw|new_raw_candidates|hohonet_replay_pair_count|112|18|0.6881|0.1167|
|expanded_raw|new_raw_candidates|hohonet_rotation_mae_deg|112|18|0.3416|0.2101|
|expanded_raw|new_raw_candidates|bilayout_raw_relative_gap|112|18|0.2896|0.1939|
|correction_available|supplementary_single_axis|hohonet_boundary_correction_deg|84|18|0.3027|0.2576|

## 是否超过点数单轴

- old_common：没有更低损失；不据此替换点数基线；全部预测建筑折权重频次{'[1.0, 0.0, 0.0]': 22}，其中有标签的评价建筑折{'[1.0, 0.0, 0.0]': 14}。
- expanded_raw：没有更低损失；不据此替换点数基线；全部预测建筑折权重频次{'[1.0, 0.0, 0.0]': 16, '[0.75, 0.0, 0.25]': 6}，其中有标签的评价建筑折{'[1.0, 0.0, 0.0]': 12, '[0.75, 0.0, 0.25]': 6}。

## 输入图像核查

两套模型的259图输入源独立保存路径和尺寸。HoHo源用BOX缩小至Bi源尺寸后的RGB像素MAE中位数1.644537/255、逐图MAE最大50.932875/255；四个90°滚动中非零滚动误差最低2图。
这只核查源图内容与四分之一周方向，没有修改预测输入；HoHo实际使用torch bilinear，Bi实际使用其原resize流程，不能据此声称预处理或输出完全一致。逐图记录见image_source_audit.csv。

## 解释边界

- yaw只有四个90°相位，是模型等变性诊断；低变化不证明难度低或预测正确，相位数不是独立图片数。
- Bi raw是两头radial depth差，最终底面相等不保证raw相同。不是置信度、遮挡或真实范围误差。
- boundary correction包含峰检测、墙拟合、上下高度统一及可能回退；多值边界不强行平均，作为不可计算。
- 原型特征在看过案例后选择，本次内外留出只隔离百分位／权重；不能声称全流程新建筑独立泛化。
- 主观三档口径不统一、部分判断已看过作答；任何相关改善均不等于识别固有难度。
- 首轮/分层分数和参考冻结不改。新信号保留原量纲供解释，未经独立验证不建立简单／中等／困难新阈值。

来源：[HoHoNet重放](../hohonet_probe/REPORT.md)、[BiLayout探查](../bilayout_probe/REPORT.md)、[场景分层](../stratified/REPORT.md)。

复算：`.venv/Scripts/python.exe -m tools.thesis_main.analysis.difficulty_model_comparison_20261009`。
