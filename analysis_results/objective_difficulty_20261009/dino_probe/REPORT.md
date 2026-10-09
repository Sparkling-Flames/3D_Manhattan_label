# DINOv3：视觉距离与视觉异质性候选

全研究图259的固定最后层缓存已读取；普通共同面板216图、112份历史三档标签。全景/六面不是新增独立图片。

两轴定义、内外折近邻隔离及来源限制见field_contract.json；不训练、下载或按案例选择层。保留点数和当前三轴基线；逐一加轴与五轴同时对照，禁止只挑最好结果。

|候选|评分|标签图|建筑|Spearman|异档对排序一致率|建筑等权MSE|
|---|---|---:|---:|---:|---:|---:|
|point_only|baseline_score|112|18|0.6881|0.8715|0.1167|
|point_only|calibrated_score|112|18|0.6881|0.8715|0.1167|
|current_three|baseline_score|112|18|0.5133|0.7704|0.1439|
|current_three|calibrated_score|112|18|0.6660|0.8584|0.1237|
|dino_novelty_only|baseline_score|112|18|-0.1092|0.4429|0.3112|
|dino_novelty_only|calibrated_score|112|18|-0.1092|0.4429|0.3112|
|dino_dispersion_only|baseline_score|112|18|0.0143|0.5064|0.2504|
|dino_dispersion_only|calibrated_score|112|18|0.0143|0.5064|0.2504|
|three_plus_novelty|baseline_score|112|18|0.4284|0.7289|0.1609|
|three_plus_novelty|calibrated_score|112|18|0.6660|0.8584|0.1237|
|three_plus_dispersion|baseline_score|112|18|0.5527|0.7913|0.1387|
|three_plus_dispersion|calibrated_score|112|18|0.6660|0.8584|0.1237|
|all_five|baseline_score|112|18|0.4399|0.7315|0.1549|
|all_five|calibrated_score|112|18|0.6660|0.8584|0.1237|

## 本轮采用判断

两轴按固定正向标准检查，单轴相关与误差、逐一加入的等权／选权和五轴全部并列。逐建筑误差见building_losses.csv，有标签建筑的选权频次见summary.json；不能仅凭汇总相关挑选轴或改计分方向。
五轴校准建筑等权MSE0.12372，同折点数0.11667；DINO两轴在有标签外折中全部零权重。
当前候选不自动加入评分；本轮组合或单轴表现不推论DINO或其它预先定义的视觉测量普遍无用。

数值比较仍是回顾性主观一致程度，不是新盲验证；单轴或组合较好也不认证固有难度。两轴可受家具、纹理、照明和构图影响，未直接测量边界可见性、遮挡或非正交。

源缓存记录与研究PNG路径一致，缓存为历史float16：未证明历史提取时源文件字节与当前完全一致。上游预训练/模型选择是否接触目标未知。特殊图不因DINO距离大而自动困难或不可标。

复算：`.venv/Scripts/python.exe -m tools.thesis_main.analysis.difficulty_dino_20261009`。
