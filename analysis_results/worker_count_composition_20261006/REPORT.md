# 高人数面板：人员构成、参考误差与成员波动

2026-10-06。本轮实际计算；BEV声明底面、Lee等权投票。沿用当前预处理、环序、人员资格与GT版本，不新增人员分类或总分。

## 范围

| 面板 | 固定图数 | 比较至人数 |
|---|---:|---:|
|common10|10|24|
|manual_n16|39|16|
|manual_n20|33|20|
|manual_n24|10|24|
|semi_n16|18|16|
|semi_n20|17|20|
|semi_n24|13|24|
|manual_external_n16|17|16|

整池不可用／参考不可用：[{'image': 'rPc6DW4iMge-22', 'building': 'rPc6DW4iMge', 'condition': 'manual', 'gate': 'main_candidate', 'n': 24, 'workers': 'P001|P002|P003|P004|P005|P006|P007|P008|P009|P010|P011|P012|P014|P017|P018|P019|P020|P021|P022|P023|P024|P025|P026|P027', 'status': 'whole_pool_unavailable', 'reason': 'R01424', 'difficulty': '未记录', 'd_model_feat_static': None, 'bilayout_legacy_band': None, 'scope_explicit_tag': False, 'detail_explicit_tag': False}]。其人员未被删除以换取成功。

## 随机抽人：固定图片上的人数变化

误差为期望对称差面积／参考面积，**不是1−IoU**；换组量为两次独立抽组的区域差异／全员并集。两者量纲分母不同，不直接互比。

| 面板 | 规则 | k | 图数 | 参考误差 | 换组差异 |
|---|---|---:|---:|---:|---:|
|common10|mv50|1|10|0.274035|0.127822|
|common10|mv50|4|10|0.251772|0.070988|
|common10|mv50|8|10|0.245943|0.042147|
|common10|mv50|12|10|0.243450|0.029880|
|common10|mv50|16|10|0.242453|0.021780|
|common10|mv50|20|10|0.242938|0.014016|
|common10|mv50|24|10|0.246163|0.000000|
|common10|mv_strict|1|10|0.274035|0.127822|
|common10|mv_strict|4|10|0.261653|0.056943|
|common10|mv_strict|8|10|0.250261|0.035746|
|common10|mv_strict|12|10|0.247499|0.026002|
|common10|mv_strict|16|10|0.246516|0.018574|
|common10|mv_strict|20|10|0.246198|0.010959|
|common10|mv_strict|24|10|0.245318|0.000000|
|manual_n20|mv50|1|33|0.279738|0.144685|
|manual_n20|mv50|4|33|0.234053|0.076656|
|manual_n20|mv50|8|33|0.219906|0.043773|
|manual_n20|mv50|12|33|0.215194|0.030112|
|manual_n20|mv50|16|33|0.213027|0.020548|
|manual_n20|mv50|20|33|0.212110|0.011028|
|manual_n20|mv_strict|1|33|0.279738|0.144685|
|manual_n20|mv_strict|4|33|0.244115|0.066638|
|manual_n20|mv_strict|8|33|0.225375|0.040734|
|manual_n20|mv_strict|12|33|0.219366|0.027806|
|manual_n20|mv_strict|16|33|0.216892|0.018580|
|manual_n20|mv_strict|20|33|0.216184|0.009405|
|semi_n20|mv50|1|17|0.229102|0.090886|
|semi_n20|mv50|4|17|0.197497|0.036047|
|semi_n20|mv50|8|17|0.177496|0.014092|
|semi_n20|mv50|12|17|0.172133|0.007200|
|semi_n20|mv50|16|17|0.170490|0.003857|
|semi_n20|mv50|20|17|0.170275|0.001843|
|semi_n20|mv_strict|1|17|0.229102|0.090886|
|semi_n20|mv_strict|4|17|0.171459|0.029303|
|semi_n20|mv_strict|8|17|0.168996|0.012269|
|semi_n20|mv_strict|12|17|0.169358|0.006341|
|semi_n20|mv_strict|16|17|0.170071|0.003592|
|semi_n20|mv_strict|20|17|0.170657|0.001853|

![人数曲线](count_curves.png)

## 构成比较：同图、同人数、同校准政策

| 面板 | 规则 | k | 构成 | 实际上半比例均值 | 参考误差 | 换组差异 |
|---|---|---:|---|---:|---:|---:|
|common10|mv50|4|lower_rich|0.000|0.271797|0.059261|
|common10|mv_strict|4|lower_rich|0.000|0.278221|0.050664|
|common10|mv50|4|balanced|0.500|0.252287|0.070260|
|common10|mv_strict|4|balanced|0.500|0.261651|0.056814|
|common10|mv50|4|higher_rich|1.000|0.228044|0.067355|
|common10|mv_strict|4|higher_rich|1.000|0.245099|0.048249|
|common10|mv50|8|lower_rich|0.000|0.267345|0.027207|
|common10|mv_strict|8|lower_rich|0.000|0.267194|0.023556|
|common10|mv50|8|balanced|0.500|0.245844|0.041976|
|common10|mv_strict|8|balanced|0.500|0.250188|0.035634|
|common10|mv50|8|higher_rich|1.000|0.226886|0.026471|
|common10|mv_strict|8|higher_rich|1.000|0.233691|0.026223|
|common10|mv50|12|lower_rich|0.000|0.265509|0.000000|
|common10|mv_strict|12|lower_rich|0.000|0.263117|0.000000|
|common10|mv50|12|balanced|0.500|0.243359|0.029747|
|common10|mv_strict|12|balanced|0.500|0.247457|0.025847|
|common10|mv50|12|higher_rich|1.000|0.220714|0.000000|
|common10|mv_strict|12|higher_rich|1.000|0.226661|0.000000|
|common10|mv50|16|lower_rich|0.250|0.254762|0.013656|
|common10|mv_strict|16|lower_rich|0.250|0.255219|0.011224|
|common10|mv50|16|balanced|0.500|0.242404|0.021727|
|common10|mv_strict|16|balanced|0.500|0.246470|0.018420|
|common10|mv50|16|higher_rich|0.750|0.231208|0.014912|
|common10|mv_strict|16|higher_rich|0.750|0.238031|0.014991|
|common10|mv50|20|lower_rich|0.400|0.247717|0.010865|
|common10|mv_strict|20|lower_rich|0.400|0.249049|0.009567|
|common10|mv50|20|balanced|0.500|0.242922|0.014046|
|common10|mv_strict|20|balanced|0.500|0.246200|0.010859|
|common10|mv50|20|higher_rich|0.600|0.238165|0.013165|
|common10|mv_strict|20|higher_rich|0.600|0.243383|0.010458|
|common10|mv50|24|lower_rich|0.500|0.246163|0.000000|
|common10|mv_strict|24|lower_rich|0.500|0.245318|0.000000|
|common10|mv50|24|balanced|0.500|0.246163|0.000000|
|common10|mv_strict|24|balanced|0.500|0.245318|0.000000|
|common10|mv50|24|higher_rich|0.500|0.246163|0.000000|
|common10|mv_strict|24|higher_rich|0.500|0.245318|0.000000|
|manual_external_n16|mv50|4|lower_rich|0.000|0.241179|0.060707|
|manual_external_n16|mv_strict|4|lower_rich|0.000|0.235353|0.062941|
|manual_external_n16|mv50|4|balanced|0.500|0.226047|0.064080|
|manual_external_n16|mv_strict|4|balanced|0.500|0.223586|0.068233|
|manual_external_n16|mv50|4|higher_rich|1.000|0.213741|0.051859|
|manual_external_n16|mv_strict|4|higher_rich|1.000|0.211113|0.047056|
|manual_external_n16|mv50|8|lower_rich|0.000|0.218956|0.023889|
|manual_external_n16|mv_strict|8|lower_rich|0.000|0.218343|0.020709|
|manual_external_n16|mv50|8|balanced|0.500|0.206532|0.037324|
|manual_external_n16|mv_strict|8|balanced|0.500|0.205472|0.037396|
|manual_external_n16|mv50|8|higher_rich|0.985|0.194853|0.014966|
|manual_external_n16|mv_strict|8|higher_rich|0.985|0.192482|0.012965|
|manual_external_n16|mv50|12|lower_rich|0.108|0.209968|0.010962|
|manual_external_n16|mv_strict|12|lower_rich|0.108|0.212085|0.008441|
|manual_external_n16|mv50|12|balanced|0.500|0.199721|0.024460|
|manual_external_n16|mv_strict|12|balanced|0.500|0.200262|0.024043|
|manual_external_n16|mv50|12|higher_rich|0.809|0.191007|0.010332|
|manual_external_n16|mv_strict|12|higher_rich|0.809|0.190671|0.010826|
|manual_external_n16|mv50|16|lower_rich|0.331|0.201471|0.012355|
|manual_external_n16|mv_strict|16|lower_rich|0.331|0.203508|0.010122|
|manual_external_n16|mv50|16|balanced|0.493|0.196127|0.014296|
|manual_external_n16|mv_strict|16|balanced|0.493|0.197670|0.013813|
|manual_external_n16|mv50|16|higher_rich|0.607|0.192566|0.010508|
|manual_external_n16|mv_strict|16|higher_rich|0.607|0.192952|0.010565|

![构成曲线](composition_curves.png)

## 解读范围

- Common10沿用外建筑校准。新增建筑用共同10图校准；同属校准建筑的新增图仍剔除整栋。Semi只做人数研究，不借Manual分组解释Semi人员类型。
- 12人以上不能维持全上半／全下半；24人换组波动为零是有限池穷尽，不能宣布真实人数停止点。奇偶门槛引起的锯齿由两规则并列展示。
- 同k换组、增加一人后的融合变化、当前融合与下一位人员的差异分别计算。变动小不等于参考正确，也不等于预测新人员准确。
- 原GT／手工修订在相同双参考图片并列；分组原GT／修订优先两政策也分别保留。图片／建筑等权汇总同时输出；没有新增总体显著性或置信区间。
- 新增精确的是面积期望与概率，不是平均IoU。已有136图IoU曲线未重跑；本轮不会用期望交并比冒充平均IoU。
- 只测试新增概率接线、面积计算、目标建筑隔离和大人数可行构成；不重跑108点基线或全库输入审核。

## 文件

`design.json`是计算前的设计；`input.json`含当前名单与坐标摘录；`coverage.csv`保留高人数资格／失败；`per_image.csv`、`summary.csv`为逐图与固定面板结果；`assignments.csv`为楼外校准名单；`integration_bases.npz`保存可复用积分基底；`field_contract.json`定义分母与缺失；`warnings.json`保留几何库警告。

复算：`python -B -m tools.thesis_main.analysis.worker_count_composition_20261006 --out analysis_results/NEW_worker_count`。新输出目录必须不存在。
