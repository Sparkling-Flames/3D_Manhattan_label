# B8L2/D10 命名解释块的读取补充

本轮沿用的 native 标量完整保存 `iou_2d`、`S_bottom_deg`、`dir`、`Hmean`、`Hcenter` 与正式 B8L2/D10。旧 20261025 编译器列出了六个命名解释块，却没有对新端点调用派生函数；本轮直接继承 native 输出时也存在这些命名列缺失。由此，直接聚合旧前缀表的块字段会只剩部分缓存命中记录，不能代表完整的新样本。

`derive_frozen_blocks.py` 在读取端按已冻结公式补齐这些**解释字段**。原分数、资格、几何、失败状态及已交付端点 ZIP 均不修改；它不重新融合，也不从图像重新测量。已有非空命名块先与公式核对，缺值才补入。

公式直接来自固定提交 `b9bcec809fbaec8ab055931a1abb7baa5db44dac` 的：

`research/workers/personnel_population_curves_v2_20261023/code/enrich_cached_geometry.py::score_blocks`

正式评分及方向尺度 8/10 的参数来源同时保留在冻结闭包：

`tools/thesis_main/analysis/quality_b8l2_d10_20261017.py::model_parameters`。

## 含义和尺度

设 `I=iou_2d`、`S=S_bottom_deg`、`d=dir`、`h=Hmean`、`c=Hcenter`。

| 字段 | 冻结公式 | 含义与范围 |
|---|---|---|
| `B8_floor_block` | `(1/I − 1) + S²/32` | 地面区域与底点位置损失；无量纲，通常非负，无固定上界 |
| `B8_direction_block` | `1.5 d²/(d²+64)` | B8 方向损失；无量纲，范围 `[0,1.5)` |
| `D10_direction_block` | `1.5 d²/(d²+100)` | D10 方向损失；无量纲，范围 `[0,1.5)` |
| `B8_global_height_block` | `(h/0.8)²` | 全局高度损失；无量纲，非负、无固定上界 |
| `B8_local_height_block` | `(c/0.25)²` | 局部高度损失；无量纲，非负、无固定上界 |
| `B8_height_block` | 全局高度块 + 局部高度块 | 高度损失的合计，与前两项并非独立信息 |

**这些块是已含冻结参数的损失项，越低越好。它们不是 0–100 的子分数，也不是可以相加成百分比的质量贡献。** 例如，地面块减少 0.05 不能写成“质量提高 5 分”。它们共同进入非线性组合：

`B8L2 = 100 / (1 + hypot(B8_floor_block, B8_direction_block) + B8_height_block)`。

D10 采用相同地面和高度块，只将方向项换成 `D10_direction_block`。

`B8_formula_residual` 仅记录保存分数与此解释公式的差，单位为分，用于核对；不会覆盖原 B8L2。

## 用法与支持

```python
from derive_frozen_blocks import add_blocks_frame
values = add_blocks_frame(values)
```

读取**旧批、新批与合并批**时使用同一函数，避免组件比较因缺列而换了图片或团队支持。五个原始测量必须全部有限且 `iou_2d>0` 才能派生；缺测量仍缺失。块可派生不等于恢复原本不可评分的 Q 资格。

本轮实际小检查为 24 条旧有命名块记录及 24 条新原生记录，逐行函数与 DataFrame 函数一致，保存 B8L2 的改变量为零；具体残差见 `FROZEN_BLOCK_PROJECTION_CHECK.json`。这是输出字段的补充，不是新评分模型。旧原件留存，最终分项结果应采用本轮统一读取投影。
