# 两处固定局部观察的人数与构成响应

2026-10-06。综合判断见[返回分析](../../../research/pro_parallel_return_20261006/README.md)。本目录是新增连接实验，不是Pro原件的复算副本，也不把局部片区当GT。

## 测量

令P为Pro已选定的固定片区，F为一组人员产生的单一Lee区域，计算`E[|F∩P|]/|P|`。将两图各24人原作答划成tile，按tile与P的真实相交面积乘以既有有限池覆盖概率求和，不用网格近似或蒙特卡洛。分母包括P中无人覆盖的部分。

- rPc：R01557／P023，第2、3、4个处理后点对围成的片区，在来源作答内部，覆盖比例称该观察凸出的保留率。
- yq：R02256／P023，第10、11、12个处理后点对围成的片区，在来源作答外部，覆盖比例称该观察内收的填入率。Pro路径距离另用9至13点；路径和片区定义不同，均沿原件保留。
- 索引从0开始，原始点对索引映射留在[Pro片区GeoJSON](../../../research/pro_parallel_return_20261006/pro_original/results/diagnostic_patches.geojson)。两处均为观察诊断，不是已认证真实角点或人数身份支持。

## 文件

- [per_image.csv](per_image.csv)：180行；随机k=1…24，及k=8下／混合／上构成；MV50／严格多数；现有两种楼外校准政策和实际可用参考版本。D／O／E／V复用全局表；只有片区覆盖期望是本轮新增。
- [field_contract.json](field_contract.json)：公式、输入、来源、语义与端点检查。
- [local_patch_response.png](local_patch_response.png)：原GT评价；构成标记使用原GT校准；其它参考／政策结果保留表中。实线含所有整数k，奇偶门槛引起起伏；方点为真实全员终点。

`source_higher`仅记录来源人员在当前校准政策中的上下半标签，不表示该次抽组必包含来源人员。两处来源都是P023；不能视为两名独立人员的局部质量验证。

## 最小检查

`python -m pytest tests/test_consensus_response_20261006.py -q`：3项通过。

`python -m tools.thesis_main.analysis.local_patch_response_20261006`：两池871／1257个tile；k=1对逐人覆盖均值、k=24对实际全员区域和Pro端点，最大绝对差1.11×10⁻¹⁶；无几何警告。除此未重新计算57池全局实验。
