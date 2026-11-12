# Fig. 4：用几何对照解释 Q

## 修改内容

原图把五个分量及其公式再列一遍，读者仍需在文字和图之间翻译，难以直接判断“标注变成什么样，分数为什么变化”。新图用四个可直接比较的受控几何面板呈现两类误差：单侧空间边界内移，以及保持地面和平均墙高不变的局部高度变化。图中只保留几何、必要测量和实际计算的 Q；不再放置评分公式、合成框或方法标题。

所有几何均为明确构造的说明案例，不是参与者标注。参考房间为 4 m × 4 m、墙高 3 m，相机高度 1.6 m。平面图的相机位于中心。高度图展示同一三维投影下的完整几何，不对畸变进行校正。蓝色表示较小变化，橙色表示较大变化，深灰虚线为参考；斜线区域为遗漏的地面。

| 面板 | 几何变化 | 图中测量 | Q |
|---|---|---|---:|
| a | 一侧边界内移 0.4 m | Floor IoU = 90%；S_b = 1.5401136° | 84.3714861 |
| b | 一侧边界内移 1.2 m | Floor IoU = 70%；S_b = 6.5220322° | 36.2601341 |
| c | 局部墙高相对 3 m 为 ±0.3 m | 平均高仍为 3 m；H_c = 0.08164965 | 90.3614479 |
| d | 局部墙高相对 3 m 为 ±1.2 m | 平均高仍为 3 m；H_c = 0.32659859 | 36.9458184 |

两类案例使用同一个 Q，分数没有为了配图手工设定。第一组同时改变地面覆盖和边界距离，不能把分数下降单独归因于 IoU。第二组保持地面、方向和平均高度不变，使读者直接看到局部高度误差对 Q 的影响。Fig. 5 保留连续响应与共线重采样性质；本图负责展示具体几何，二者承担不同任务。

## 版式与图注

`fig04_a.pdf` 至 `fig04_d.pdf` 是无子图编号、无子图标题的独立矢量面板；对应 SVG 可编辑，PNG 为 600 dpi。`fig04_legend.pdf` 为独立图例。主标题、(a)–(d) 编号和子标题必须由正文 LaTeX 在图片下方排版。建议满双栏 1 × 4 排列；每个面板使用相同宽度，图例置于面板上方或图下注释前。

建议原生 LaTeX 子标题：

- (a) Boundary shift: 0.4 m
- (b) Boundary shift: 1.2 m
- (c) Local height shift: ±0.3 m
- (d) Local height shift: ±1.2 m

建议英文主图注：

> Controlled examples show how geometric changes affect Q. The reference room has a 4 × 4 m footprint, a 3 m wall height and a 1.6 m camera height. (a–b) Moving one floor boundary inward reduces overlap and increases boundary distance; hatched regions mark omitted floor area. (c–d) Opposing upper-boundary shifts preserve the footprint and perimeter-mean height while increasing local height error. Blue and orange show the smaller and larger changes; dashed gray denotes the reference. Measurements and Q are computed from the displayed geometry.

图注中的 ×、±、破折号等在最终 LaTeX 源码中由相应数学或排版命令生成。

## 计算与来源

`controlled_q_engine.py` 从原交付包 `supplement_sources/geometry/input/q_iou_eight_cases/run_cases.py` 原样复制。其评分表达式、方向尺度 8、局部高度尺度 0.25、全局高度尺度 0.8，以及每方向 2,048 / 4,096 个边界/高度样本，与最新正文方法一致。它是已归档的受控几何方程实现，不调用参与者数据，不重算实证结果。

`build_fig04.py` 只定义这四个受控输入、调用该实现并绘图。`data/fig04/illustrative_geometry.json` 保存全部输入坐标；`illustrative_cases.csv` 保存完整输出；`verification.json` 保存验证结果和实现 SHA-256。

验证包括：参考对自身 Q = 100，矩形面积交并比的解析核对，局部高度误差的解析核对，四倍采样的精度检查，以及生成后 PDF 的渲染和文本检查。四倍采样与正式采样的最大 Q 差为 0.0000381，远小于图中两位小数。四个 PDF 均无栅格对象，文字字体嵌入并带 Unicode 映射；不存在内嵌子图标题。

## 重生成

依赖：Python 3、numpy、pandas、shapely、matplotlib；绘图字体为 Liberation Sans。安装字体后，在图片包根目录执行：

```bash
python source/fig04/build_fig04.py
```

也可通过 `--package-root` 指定输出图片包路径。脚本只写入该路径下 `panels/fig04` 和 `data/fig04`，不修改论文正文。
