# 已确认空间与修订GT的质量重算（2026-10-16）

本次核验41图的全部506份现有作答：39图采用确认的新空间，另2图使用修订GT。旧160条只是1145份历史完整评分中的受影响子集：54条同底面但完整参考未核、96条底面改变、10条修订GT；不能将160当成全部受影响作答。

实际送入冻结引擎90份，完整计算90份。通过当前目标绑定、原图片/人员限制和来源池人数门后，新增84份当前质量，当前总数由807变为891。诊断可评分不授予统计资格；旧评分和参考身份保留在逐作答对照中。旧待处理160条中，仍有99条尚无绑定空间完整评分；已完成的61条包含59条新增当前质量与2条人工指定的其它合法空间。其余25条新增当前质量来自旧160条之外。所有506份的其它缺口另见remaining_gaps，两个分母不混用。

|condition|records|images|workers|
|---|---|---|---|
|manual|828|73|24|
|semi|63|4|24|

## 参考及空间绑定

39图中12个新空间完整参考可确定：6个严格等价底面保留已有完整点对，6个在可信原空间内，使用原布局JSON已明确声明的顶平面完成整个空间的竖向裁切。源JSON既定转换与现有原GT逐值一致后才使用其顶平面，没有从IoU均高公式倒造顶界。另27个确认多边形部分超出可信源域，原域交集仅为诊断，不替代确认范围；需核对范围或补对应完整几何。两份修订GT保留原点对对应，均按唯一修订参考评价原完整作答。

原GT、手工GT的历史版本并不自动成为两个合法空间。仅继承既有审核准入的空间；人工指定优先，family A/B约束不擅自细化成A或B，多个合法目标仍未定者保持待绑定。没有按最高Q或最高全局IoU选空间，没有裁剪或修改作答。

|binding_status|作答数|
|---|---|
|explicit_manual_target|5|
|fixed_current_gt_revision|10|
|pending_manual_family_not_unique|2|
|pending_multiple_admitted_spaces|369|
|sole_admitted_space|120|

image_spaces按图片×空间×条件列出来源池人数与已绑定空间人数；同一人展开多个候选不会增加实际人数。主分析仍按图片×条件的有效人员池至少3人，GT错误、旧暂停和个别作答限制继续优先；每指标可用人数另报。

|image_code|role|full_reference_available|method|minimal_gap|
|---|---|---|---|---|
|7y3sRwLe3Va-26|user_revised_gt|True|user_supplied_surviving_full_pairs||
|B6ByNegPMKs-37|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|S9hNv5qa7GM-04|confirmed_scope|True|identical_footprint_existing_full_geometry||
|UwV83HsGsw3-10|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|b8cTxDM8gDG-18|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|e9zR4mvMWw7-09|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|e9zR4mvMWw7-17|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|pRbA3pwrgk9-02|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|pa4otMbVnkk-11|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|pa4otMbVnkk-14|confirmed_scope|True|identical_footprint_existing_full_geometry||
|q9vSo1VnCiC-11|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|q9vSo1VnCiC-12|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|q9vSo1VnCiC-15|confirmed_scope|True|identical_footprint_existing_full_geometry||
|q9vSo1VnCiC-16|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|q9vSo1VnCiC-29|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|q9vSo1VnCiC-34|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|rPc6DW4iMge-05|confirmed_scope|True|contained_vertical_cut_explicit_source_ceiling_plane||
|rPc6DW4iMge-06|confirmed_scope|True|contained_vertical_cut_explicit_source_ceiling_plane||
|rPc6DW4iMge-22|confirmed_scope|True|contained_vertical_cut_explicit_source_ceiling_plane||
|uNb9QFRL6hY-18|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|uNb9QFRL6hY-26|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|uNb9QFRL6hY-41|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|uNb9QFRL6hY-44|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|uNb9QFRL6hY-50|confirmed_scope|True|identical_footprint_existing_full_geometry||
|uNb9QFRL6hY-54|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|uNb9QFRL6hY-55|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|uNb9QFRL6hY-59|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|uNb9QFRL6hY-60|confirmed_scope|True|identical_footprint_existing_full_geometry||
|uNb9QFRL6hY-66|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|uNb9QFRL6hY-67|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|uNb9QFRL6hY-68|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|uNb9QFRL6hY-81|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|uNb9QFRL6hY-86|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|uNb9QFRL6hY-88|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|wc2JMjhGNzB-03|confirmed_scope|True|contained_vertical_cut_explicit_source_ceiling_plane||
|wc2JMjhGNzB-22|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|wc2JMjhGNzB-26|confirmed_scope|True|identical_footprint_existing_full_geometry||
|wc2JMjhGNzB-29|confirmed_scope|False|pending|confirmed_polygon_extends_beyond_complete_source_domain|
|wc2JMjhGNzB-54|confirmed_scope|True|contained_vertical_cut_explicit_source_ceiling_plane||
|wc2JMjhGNzB-61|confirmed_scope|True|contained_vertical_cut_explicit_source_ceiling_plane||
|x8F5xyUWy9e-03|user_revised_gt|True|user_supplied_surviving_full_pairs||

## 固定评分与解释

WQ-LS08、A10、B8L2和现用均高棱柱IoU3D均复用已有冻结实现；各分项、公式版本、输入/参考身份保存在rescore_comparisons。三个历史控制复现至1e-8，未重新调参。参考自比的原方向惩罚也原样保留。IoU3D不是任意实体精确体积IoU；新增竖切边界不因此被断言为实体墙。

新旧参考不同的分数差只描述参考修订后的数值变化，不是作答改进，也不是算法优劣。新目标下的完整质量重算不证明采集时以该目标完成任务；原始有效操作时间单列，未据此补造新目标耗时。

## 交付与复现

- [更新后的完整统计、工作簿与关键图](../descriptive_statistics_rescored_20261016/README.md)
- [独立审计与逐层数量复算](INDEPENDENT_AUDIT.md)
- reference_catalog：每稳定目标一行，完整参考、参考版本、构造及原回执来源。
- affected_records：506原作答逐条状态；record_targets：候选展开，不作为作答分母。
- image_spaces：空间支持人数和来源人数分别列出；rescore_comparisons：实际冻结重算及历史对照。
- remaining_gaps：确切对象、未解决原因和最小人工问题；historical_pending_160保留旧子集身份。
- [后续批次及质量算法接入](EXTENSION_GUIDE.md)。

```powershell
python -m tools.thesis_main.analysis.scope_quality_rescore_20261016
```

输入为现有CURRENT及完整loader；输出为独立目录，原始标注、旧GT、难度v3、历史统计和已存在融合曲线均未覆盖。下游统计按新参考重建，不重跑融合实验。
