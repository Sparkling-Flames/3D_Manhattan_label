# BiLayout图片难度候选信号探查

本支只计算模型输出自身的几何、双头差异和旋转变化，不将这些直接命名为真人难度或置信度。

- 原序底面覆盖：259图；双头可比较257图。退化和不可计算保留空值，不重新排序。
- raw双头：259图；有效正值256维双头259图。两数组和ratio保存在raw/，没有曼哈顿拟合。
- 旋转试点：12图，按建筑排序等距选12建筑，每建筑取ID最小图；不参考人工标签或作答。128/256px滚动后按-32/-64 bins逆对齐，单列yaw.csv。

extended对应depth；enclosed对应new_depth。相对双头差是平均绝对差除以两头平均深度，有符号差保留平均方向；不设难度阈值。

既有导出是Manhattan后处理角点。两头在原序底面不可计算时，raw深度仍可能存在，这不构成修复成功或可标性认证。

供给的MP3D split清单为train1647/val190/test458，清单建筑互斥；本研究图val76/test183。它只说明清单身份，不证明下载checkpoint真实训练、预训练或选参未见目标。

未改外部repo、未训练或下载；未以人工标签调参。结果是候选测量，尚待与独立人员作答表现和主观感受对照。

## 底面不可比较图

|图片|extended点对/状态|enclosed点对/状态|
|---|---|---|
|UwV83HsGsw3-01|1 / odd_or_insufficient|2 / odd_or_insufficient|
|yqstnuAEVhm-31|12 / ok|1 / odd_or_insufficient|

raw双头是否有效另读raw.csv；不把有效raw深度称为角点修复。

raw双头相对差中位数 0.001426，P90 0.024906；仅描述模型差异。

## 旋转变化分布

|分支与像素滚动|图数|相对差中位数|P90|
|---|---:|---:|---:|
|extended_roll128_relative_gap|12|0.001226|0.005425|
|extended_roll256_relative_gap|12|0.001685|0.003789|
|enclosed_roll128_relative_gap|12|0.001237|0.005490|
|enclosed_roll256_relative_gap|12|0.001644|0.004309|
