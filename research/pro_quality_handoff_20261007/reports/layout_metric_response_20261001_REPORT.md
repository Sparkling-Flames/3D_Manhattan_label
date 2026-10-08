# 坐标来源收尾与指标响应小实验（2026-10-01）

输入：最终manifest完整bundle；12张固定证据图片、24条人员/参考版本记录（15条有参考比较，9条人工参考缺失记录）；74个参数化合成对照，由5个等价、19个范围、14个细节和36个定位对照构成，**不是74个独立样本**。合成参数在首次运行前固定。选样审查纠正了评论候选混入的问题，最终证据层级与规则在接收复算前写入experiment_plan.json；未按指标结果改参数或选样。

当前合同已纠正：原始GT生产C；最终LS百分比用C画布解释；原生HoHoNet为P。C/P正确转换是等价性检查。同值套两公式是错配/未知来源敏感性，不能再把原始GT的P解释当等可能来源。输入phase与输出中心采样分开。

## 受控结果

| 对照 | BEV IoU | 面积质心差/h | 边界采样最大/h | 列式IoU 512 / 1024 |
|---|---:|---:|---:|---|
|对称扩展1h|0.444444444|0.000000000|1.414213562|0.710000000 / 0.709758057|
|隐藏范围延至20h|0.561643836|5.214933254|16.000000000|1.000000000 / 1.000000000|
|小凸起0.002h|0.999975001|0.000050024|0.002000000|1.000000000 / 0.999921882|
|近邻两对/三对 gap0.002h|0.999993750|0.000012604|0.037999600|1.000000000 / 1.000000000|

循环、反向、平顶/非平顶同边共线插点、正确C/P转换：BEV IoU最小1.000000000000；边界采样最大差至多6.66e-16h。身份匹配RMSE近零，但新增中间对仍记未匹配；不靠删点获得等价。

同一SE底点向地平线移动0.5原域像素：普通房间floor RMSE=0.013927h；近地平线房间=3.649889h。该RMSE汇总4个对应底点，只有SE被扰动，因此单个SE位移分别为其2倍（0.027853h和7.299778h）。near_horizon是半宽32h的更大合成房间，ordinary半宽2h；这是投影/深度传播对照，不是同一房间的人员能力比较。4px近地平线底点越界保留unavailable及原因，不当零或剔除。

BEV使用精确多边形面积，能看到隐藏声明范围；列式墙带只看每列最近底墙和线性墙顶，隐藏范围可投影相同。对称扩展质心可保持不动；凸/凹小细节IoU受全局面积稀释，边界尾部受采样限制。固定Manhattan轴残差独立报告，正交范围变化残差仍可为零，不替代空间差异。

near_three_pairs比较的是原墙上的两个共线端点与两端之间新增三角形尖凸中点的路径；同时改变点数、几何和局部角度。它不是对真实正交两对/三对表达的完整规律检验，也没有验证局部整体投票。保留身份与未匹配项，只说明这一固定尖凸案例的响应。

最小近邻细节边界复核：512样本max=0.037999600h，8192样本max=0.049779302h。有限采样的max不称Hausdorff；每侧步长与保守最大值误差上界保留。p95可能为0是细节所占边长不足5%，不能解释为无差异。

两个栅格分别保留IoU和差异像素；亚像素量化可产生平台及小幅非单调，分辨率对照不作为方法真实精度证明。相同最终几何无论来自范围选择还是定位偏移，所有这些指标都相同；语义原因不能单靠指标识别。

## 真实面板与缺失

| 类别 | 可用图片 | 本类别新选 | 缺额 |
|---|---:|---:|---:|
|detail|29|2|0|
|scope|55|2|0|
|oos|18|2|0|
|doorway|19|2|0|
|near_horizon|4|2|0|
|ordinary|7|2|0|

范围/细节优先明确个人标记，其次图级明确标签、既有台账；评论候选只保留背景，不作为选样证据。OOS/门洞需明确场景状态，近地平线用底点角距≤5°；ordinary只认明确not_oos+none。缺失标记不是阴性，类别可重叠，缺额可能来自重复图片已先选。同证据层按图片编号与记录别名固定选择，不按GT距离、人员质量或难度挑选。

| 图片 | 人员记录 | 原始GT BEV / 列式1024 IoU | 人工GT BEV / 列式1024 IoU |
|---|---|---|---|
|jtcxE69GiFV-12|R03398|0.828051 / 0.958261|NA:reference_version_absent / NA:reference_version_absent|
|yqstnuAEVhm-31|R00236|0.590552 / 0.894529|0.631732 / 0.914791|
|e9zR4mvMWw7-19|R01301|0.449596 / 0.699760|0.149518 / 0.565601|
|jtcxE69GiFV-30|R02429|0.790804 / 0.952208|NA:reference_version_absent / NA:reference_version_absent|
|7y3sRwLe3Va-08|R00041|0.834535 / 0.891713|NA:reference_version_absent / NA:reference_version_absent|
|7y3sRwLe3Va-12|R00705|0.534506 / 0.949227|NA:reference_version_absent / NA:reference_version_absent|
|2t7WUuJeko7-07|R03281|0.603697 / 0.793911|NA:reference_version_absent / NA:reference_version_absent|
|7y3sRwLe3Va-06|R03289|0.390825 / 0.799163|NA:reference_version_absent / NA:reference_version_absent|
|B6ByNegPMKs-40|R02166|0.664349 / 0.791880|NA:reference_version_absent / NA:reference_version_absent|
|B6ByNegPMKs-42|R03325|0.087372 / 0.242244|NA:reference_version_absent / NA:reference_version_absent|
|7y3sRwLe3Va-26|R00046|0.927185 / 0.970543|NA:reference_version_absent / NA:reference_version_absent|
|e9zR4mvMWw7-16|R00087|0.863683 / 0.939888|0.953827 / 0.965802|

这是固定小面板的参考一致性描述。原始GT环未经过人员环审核，状态仍为false；人工修订版本单列，缺版本明确NA。所有gate、来源索引和部分审核标记保留，不替换资格、裁定GT、传播同房标签或汇总人员分数。真实RMSE因未建立对应身份而不计算；真实Manhattan未计算是本轮未定义共同轴的实验边界。即使没有GT或共同轴，数学上仍可各自拟合每个layout的最佳轴并计算自洽残差，但各自拟合轴的残差不能替代跨layout结构距离；本轮没有实施该拟合。

## 工件与复算

- [完整结果](results.json)、[固定计划](experiment_plan.json)、[字段合同](field_contract.json)、[合成CSV](synthetic_metrics.csv)、[真实CSV](real_metrics.csv)。
- [范围幅度图](extent_response.png)、[细节幅度图](detail_response.png)、[定位幅度图](localization_response.png)、[近邻/隐藏范围及分辨率图](detail_hidden_resolution.png)。

本次验证命令、结果、地图同步及交付边界见[交付核验](VALIDATION.md)。

```powershell
python -B -m tools.thesis_main.analysis.layout_metric_response_20261001 --out analysis_results/layout_metric_response_20261001
```

本轮不执行全量共识、分簇、训练或LS运营。未观测屋顶不封顶计分；未使用原生模型至LS转换或重复缩小的训练入口。这两个具体适配缺陷须在使用相应链路前修复；ERP实际采样/逐图调平记录仍缺，不据图像相同升级物理标定。结果只用于检查指标响应和盲点，尚不能冻结总分、阈值或方法优劣。
