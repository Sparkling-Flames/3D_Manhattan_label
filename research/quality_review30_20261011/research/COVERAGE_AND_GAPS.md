# 30份唯一作答：冻结候选清单与覆盖/缺口（主审私有）

状态：**候选版v1先交主审；最终用户页、叠线和回执尚未生成。旧8例及回执未改。**

已合入实际main `9c1d91173bf8ec50de4983daaff325b339965e04`；正式输入 `24360ad8544d76d8aba18a8e641f784a76ca0d42`。只新增独立研究工件，不改原数据、GT、资格、旧分数，不推main。

30个不同record_id及object_id：24质量+6空间。24张原照片；质量12个既有room_group。质量池1059减冻结留出交集152=907记录/83图；完整282留出保持排除。空间资格池272记录/21图。

## 工件

- `selection_private.csv/json`：30行可审核清单、资格/参考/来源、五原公式与所有边界距离、曝光及照片哈希；禁止放入用户包。
- `boundary_coverage_private.json`：声明控制池、全池最近邻与所选距离分开。
- `selected_original_photos_private.zip`：24张原字节照片；`pixel_sheet_1..4.jpg`仅供主审查看原像素，尚不是最终叠线。
- `selected_geometry_private.json`：30作答、原参考及6份B底面；所有新B缺top，不造完整B Q。
- `pixel_audit_private.json`：真实照片观察及复杂顶面/门洞/遮挡的适用性疑点；需主审终审，未预填质量判断。

## 唯一记录清单

以下分层只是数值选样依据，不能称为人工质量等级、成因或空间意图。空间行Q只是原参考下既有诊断，不用于空间归属。

|题号|record_id|object_id|图像|v1.1 Q|D°|F°|采样依据|
|---|---|---|---|---:|---:|---:|---|
|T01|R02428|f8bbcc65deb718e2|wc2JMjhGNzB-40|94.91175|0.64685|0.31701|Q_v11_95_below_exact_pool_nearest|
|T02|R01042|6c28d1705fb5c4b4|e9zR4mvMWw7-10|95.07354|0.32356|0.19328|Q_v11_95_above_exact_pool_nearest|
|T03|R01055|6d3c8739804e5920|7y3sRwLe3Va-13|84.96471|1.73383|0.39888|Q_v11_85_below_exact_pool_nearest|
|T04|R01407|8f04217c549dac0c|rPc6DW4iMge-20|85.01909|0.73530|0.15102|Q_v11_85_above_exact_pool_nearest|
|T05|R03106|new_94_3628_6947_W035|uNb9QFRL6hY-40|49.95599|9.40369|0.56983|Q_v11_50_below_exact_pool_nearest|
|T06|R01289|8426a252a40fabd5|B6ByNegPMKs-10|50.10534|3.28871|1.91522|Q_v11_50_above_exact_pool_nearest|
|T07|R00678|432c6ebaa6bb7a54b3a9|uNb9QFRL6hY-45|71.30856|4.99510|0.89544|D5_below_controlled_nearest|
|T08|R02189|e00297d47bfd5498|q9vSo1VnCiC-15|47.82354|5.01326|2.57934|D5_above_controlled_nearest|
|T09|R00637|3f1d4cacc3faf7d7|B6ByNegPMKs-11|34.04977|9.94588|0.98928|D10_below_controlled_nearest|
|T10|R03347|new_95_3657_7093_W037|Z6MFQCViBuw-08|46.76499|10.12275|1.58144|D10_above_controlled_nearest|
|T11|R00825|54158b496be934232a98|yqstnuAEVhm-27|19.33022|14.52861|1.01051|D15_below_controlled_nearest|
|T12|R01501|974f94a2b16103ea9324|B6ByNegPMKs-47|56.04159|15.55566|1.96859|D15_above_controlled_nearest|
|T13|R03274|new_94_3647_7412_W032|yqstnuAEVhm-05|52.25916|19.42382|1.80588|D20_below_controlled_nearest|
|T14|R01727|adef48d62993c490|q9vSo1VnCiC-02|74.48550|0.76015|1.98342|F2_below_controlled_nearest|
|T15|R02102|d6f4c71d3816fc9fef4a|uNb9QFRL6hY-45|45.99604|4.57750|2.01072|F2_above_controlled_nearest|
|T16|R01839|b8e9932406666fdb|wc2JMjhGNzB-20|30.30726|2.75106|3.49445|F4_below_controlled_nearest|
|T17|R00464|2e72e743616d19e3|wc2JMjhGNzB-40|39.26453|2.45679|4.09889|F4_above_controlled_nearest|
|T18|R00687|44c73224857604910e05|jtcxE69GiFV-09|33.98222|2.34760|5.68894|F6_below_controlled_nearest|
|T19|R00421|2926abff9dbf4e375b92|jh4fc5c5qoQ-02|33.72570|18.53347|7.64084|F6_above_uncontrolled_nearest_mixed_D_F_diagnostic|
|T20|R00397|272f8ef889915150|B6ByNegPMKs-10|16.72163|2.17211|0.54050|high_Hstar_with_high_floor_I_low_D_F; S_also_large_not_single_error|
|T21|R01357|8a6c9350ded9f505|7y3sRwLe3Va-13|32.44963|1.26529|0.48139|lowest_floor_I_under_low_D_F_scope_position_proxy|
|T22|R02015|cd59ff6392d0007b|B6ByNegPMKs-11|38.64822|1.01875|1.60067|largest_Hlocal_minus_Hmean_under_control; structural_proxy_not_confirmed_cause|
|T23|R01973|c7a9fd0c71a7a2c7|wc2JMjhGNzB-18|73.41667|0.52797|0.12860|same_image_same_reference_existing_alpha30_rank_conflict; general_absolute_rating_first|
|T24|R02447|faa0be6922f7cc2d|wc2JMjhGNzB-18|74.91272|0.50270|1.20360|same_image_same_reference_existing_alpha30_rank_conflict; general_absolute_rating_first|
|T25|R00169|1120d74f964c5f97|rPc6DW4iMge-22|98.29978|0.54086|0.26144|A_only_sensitivity_nonidentical_floor|
|T26|R02061|d229ebc66bef1a22b980|pRbA3pwrgk9-02|1.08308|1.12503|1.03730|B_only_sensitivity|
|T27|R03438|new_95_3668_7351_W036|wc2JMjhGNzB-61|83.20745|0.68460|0.74909|both_compatible_sensitivity|
|T28|R03091|new_94_3626_6945_W035|uNb9QFRL6hY-26|53.38383|3.98079|2.72132|boundary_corner_preference_conflict_detail|
|T29|R03192|new_94_3637_6963_W035|uNb9QFRL6hY-67|7.45486|2.38588|1.18997|both_exclusive_regions_intersected_and_absolute_far; not_proven_diagonal_intention|
|T30|R02962|new_93_3608_7113_W006|uNb9QFRL6hY-88|12.99295|11.79538|1.93053|both_far_sensitivity_separate_image|

T30保留既有`scope_and_order_difference_not_global_error`说明，restrict_primary=false；不把它虚报为错误GT，也不隐藏限制。

## 边界覆盖

Q全池近邻；D/F优先 I≥.6、S≤6°、Hstar≤.4，另方向F≤3°、平整D≤5°。S使用冻结`boundary_rms_deg`。半损失尺度D5°/F2°不是合格线。控制最近与全池最近在JSON分开保存。

|量|界点|侧|控制池最近|距离|实际所选最近|距离|所选满足控制|
|---|---:|---|---|---:|---|---:|---|
|Q|95|below|R02428|0.088251|T01 / R02428|0.088251|True|
|Q|95|above|R01042|0.073545|T02 / R01042|0.073545|True|
|Q|85|below|R01055|0.035287|T03 / R01055|0.035287|True|
|Q|85|above|R01407|0.019094|T04 / R01407|0.019094|True|
|Q|50|below|R03106|0.044011|T05 / R03106|0.044011|True|
|Q|50|above|R01289|0.105338|T06 / R01289|0.105338|True|
|Q|90|below|R01980|0.190454|T04 / R01407|4.980906|True|
|Q|90|above|R02450|0.008396|T01 / R02428|4.911749|True|
|Q|75|below|R02447|0.087281|T24 / R02447|0.087281|True|
|Q|75|above|R00092|0.046144|T03 / R01055|9.964713|True|
|Q|60|below|R02285|0.054417|T12 / R01501|3.958414|True|
|Q|60|above|R01288|0.038036|T07 / R00678|11.308557|True|
|D|5|below|R00678|0.004902|T07 / R00678|0.004902|True|
|D|5|above|R02189|0.013259|T08 / R02189|0.013259|True|
|D|10|below|R00637|0.054122|T09 / R00637|0.054122|True|
|D|10|above|R03347|0.122751|T10 / R03347|0.122751|True|
|D|15|below|R00825|0.471389|T11 / R00825|0.471389|True|
|D|15|above|R01501|0.555662|T12 / R01501|0.555662|True|
|D|20|below|R03274|0.576184|T13 / R03274|0.576184|True|
|D|20|above|缺|未定义/缺|缺 / 缺|未定义/缺|False|
|F|2|below|R01727|0.016583|T14 / R01727|0.016583|True|
|F|2|above|R02102|0.010722|T15 / R02102|0.010722|True|
|F|4|below|R01839|0.505553|T16 / R01839|0.505553|True|
|F|4|above|R00464|0.098891|T17 / R00464|0.098891|True|
|F|6|below|R00687|0.311057|T18 / R00687|0.311057|True|
|F|6|above|缺|未定义/缺|T19 / R00421|1.640835|False|
|F|8|below|R00687|2.311057|T19 / R00421|0.359165|False|
|F|8|above|缺|未定义/缺|缺 / 缺|未定义/缺|False|

- v1.1 Q95/85/50两侧全部是907池真正最近邻：95下/上距0.088251/0.073545，85下/上0.035287/0.019094，50下/上0.044011/0.105338。
- D5/10/15两侧与20下侧是声明控制子集最近。D15下距0.471391、上距0.555663；20下距0.576184。全907的D最大19.423816，没有20上侧。
- F2/4两侧与6下有受控例。F4下3.494450（差0.505550），6下5.688942（差0.311058）。
- 受控池无F6上侧；T19为全907唯一F>6例：F7.640835、D18.533474，距6为1.640835。只作联合混杂诊断，不能称紧邻、纯平整证据。全907无F8上侧；8下7.640835同样混杂。
- 补充Q75下侧T24是全池最近邻；Q90两侧、75上侧、60两侧没有紧邻覆盖，具体距离见表。没有拿留出/错误例补洞；主审可明确替换辅助槽位，另存v2并保留v1。
- T20高Hstar同时高S，T21低I只作位置/范围代理，T22按Hlocal−Hmean取局部结构代理；不能解释为已分离的单误差因果。

## 独立成对题与空间证据

可选P01引用T23/T24，同图同参考；不增加唯一作答数，不强迫跨图排名。v1.1 Q(T24−T23)=+1.496052，alpha30差=-0.003226，是很小的原候选排序反转。主审最终表示/采样核验后决定是否保留成对题。单份绝对评价先填，成对答案独立。

|题号|A边界RMS/h|B边界RMS/h|B−A|A角点Fréchet/h|B角点Fréchet/h|A区别区覆盖|B区别区覆盖|
|---|---:|---:|---:|---:|---:|---:|---:|
|T25|0.008324|0.338111|0.329787|0.023392|1.156838|1.000000|未定义/缺|
|T26|0.942070|0.015607|-0.926462|2.347908|0.037204|0.001254|0.052360|
|T27|0.102563|0.045640|-0.056923|1.371545|0.110061|0.029369|未定义/缺|
|T28|0.172830|0.235072|0.062242|1.425964|0.725700|未定义/缺|0.186078|
|T29|0.853957|0.695451|-0.158506|2.264029|1.812994|0.233071|0.473765|
|T30|0.773938|0.661898|-0.112040|2.265313|2.265313|未定义/缺|1.000000|

区别区为空时覆盖未定义，不能填0伪装测量。空间采样.25h仅是敏感性分层，不是最终阈值；保留绝对不匹配、相对差距、IoU、外部面积。T28边界与角点偏好冲突；T29两区别区均相交但尺度不对称（A7.615270h²、B.031651h²），只称几何混合候选，不认定斜跨真实意图。T29/T30两参考绝对距离都大；“语义上确实斜跨”仍待用户判断/可能需替换，不宣称已充分覆盖。

## 曝光、判题、停止点

全部为历史数据，不声明历史未见。T17复用旧C07记录，T23/T24复用旧C04记录；T01、T09、T22等同图曝光单独记载。C02/C05不进入本保守池，旧样本保持一般观察用途、不得纯惩罚拟合。

未来用户页隐藏Q、方案/参数、人员和选样理由。空间选项严格使用：仅 A 可匹配 / 仅 B 可匹配 / 两者均可匹配 / 两者均不匹配 / 无法判断。所有回答默认空。新回执需独立版本/键/30ID，旧8版本应拒绝而不清当前回答；分页进度不得把查看/空白当作接受。

**本阶段先交清单，无用户ZIP，无最终渲染或用户答案。** 主审决定适用性、替换和小样后继续最后渲染、30份回执与浏览器测试。

主审已有12份Q近邻的六环表示/2048与4096采样检查，最大Q极差0.00014842684333871148，未跨六测试界点。本阶段不重复、不冒称云端复跑，不将它作为人类有效性证据或最终选例替代。

阈值导向30份不能估计总体严重比例；不能同时调66组后宣布泛化成功。最终规则与main发布归主审，282留出继续排除。

## 复现

```bash
python code/freeze_selection.py --frozen-root /path/to/unpacked/cloud_compute --photo-root /path/to/original/assets --out /path/to/new_selection_results
```

需要既有完整计算工件的results/inputs及旧8映射。24原图可从本目录照片ZIP取得（解压后以originals作photo-root）。冻结算法与Pro/官方IoU原件、MIT许可证仍按既有目录保留；本目录是新增选样适配，未改原件。

映射SHA256：`bf1c3265184fe21d313c96415c80741a65ce6f531f1141aa7ff79ea1e40d2bf8`。
