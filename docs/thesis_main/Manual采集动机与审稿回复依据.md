# Manual 采集动机与审稿回复依据

更新日期：2026-11-15。用途：持续维护的作者工作记录与审稿回复资料；不属于正文或投稿补充材料，不默认随论文打包。

## 1. 作者最终写作取舍

作者确认：采用 Manual 的原因不是主要内容或贡献，正文最多用 1–2 句说明即可，不在引言、相关工作、方法、结果和结论反复展开。完整动机保存于本文件，供遇到具体审稿问题时使用。

正文保留从头绘制、3D 预览及 Manual/Semi 各自用途。现有 Semi 发现继续作为研究结果，不另建“手工与半自动工具优劣”论证。完整说明也不转移进论文附录。后续如需增加论文中的篇幅，先与作者讨论。

## 2. 作者提出的完整想法

以下记录动机及关切，不把尚未验证的推测改写为结果。

1. **先了解人工表达，再改进辅助与数据生产。** 重新标注和参考复核需要了解人们如何选择空间范围、保留局部结构并放置边界。主要分析从没有模型预置布局的绘制出发，让人员自行构造布局，并通过 3D 预览检查和调整。
2. **已有参考仍有问题。** 目标定义不清和实际几何错误均是研究动机；工具能生成规整、闭合的布局，并不替代对真实结构的检查。作者关心壁炉、墙角等遗漏，以及这些问题如何影响后续模型训练和评价。
3. **初始化可能保留共同起点。** 若所有人都修改已有结构，最终相同的部分可能沿用了初始化。作者希望通过从头绘制获得可相互比较的独立结构观察，再研究多人支持与汇总。
4. **从单份编辑走向多人共识。** 作者提出既有流程可能主要依赖个人编辑，缺少多份独立观察的汇总。本研究明确研究同一转角的人员支持及上下点对，并考察人数、分类换类、具体成员与保留背景。外部数据是否每图只有 1 人标注，必须依据实际来源，不能以此关切代替事实。
5. **保留几何表达差异。** 人员上下端点的位置及局部推算高度可以不同；这些观察连接到 Q 的几何测量与配对角点共识。自动初始化与自动几何约束是两个设计维度，不能把所有半自动工具视为同一种流程。
6. **Semi 提供相关的实际观察。** 作者认为，部分人员保留错误初始化、或编辑后仍未纠正目标缺陷，侧面支持采用 Manual 观察自行构造布局的价值。回复中可以使用这一发现，但不将它写成已证明的“工具使人停止检查”的心理因果。
7. **真实图像的条件也值得考虑。** ToF-360 报告的拼接问题表明可见线索未必处处符合理想几何。此项作为任务背景，不把本研究改成拼接误差研究，也不宣称手工绘制能够消除拼接误差。

## 3. 已有证据及准确用途

| 证据 | 可用于回答的问题 |
|---|---|
| [原 Manual 动机核查，第 4–7 节](论文写作工作资料/共识支持统计与Manual动机_深入核查及前后对照_20261108.md)；[第一章中文核对稿，第 22–30 行](论文写作工作资料/第一章_中文核对稿.md) | 当时已经明确从头绘制、三维检查、保留结构与位置差异，并连接两项方法及人员研究。旧文其他主题的取舍不随引用恢复。 |
| [Manual 界面配置](../../tools/label_studio/label_studio_view_config_manual.xml)与 [3D 预览](../../tools/label_studio/vis_3d.html) | 点对输入与三维检查的交互条件。预览包含共享水平位置等几何处理，局部顶高由各点对计算；“独立绘制”不是“未经任何处理”或“无工具”。 |
| [当前 Semi 结果](论文提纲_LaTeX_20261028/sections/05_individual_expression.tex) | 自然错误初始化被 3 人原样提交。受控缺陷任务中 138 份标准主目标提交有 20 份未改、32 份精确移除目标重复点对、1 份改了其他位置但保留该对、85 份修改但未干净解决目标缺陷。自然与受控案例分别说明。 |
| [MatterportLayout，§3.3.1](https://arxiv.org/html/1910.04099#S3.SS3.SSS1) | 该参考使用 PanoAnnotator 制作，流程包含增删墙、调整墙位和顶底高度；数据制作从已有布局继续细化。说明工具与本研究直接相关，不能据此推断错误均由软件造成或每图只有 1 位标注者。 |
| [PanoAnnotator 原文摘要](https://scholar.nycu.edu.tw/en/publications/panoannotator-a-semi-automatic-tool-for-indoor-panorama-layout-an/) | 自动初始化、交互编辑、几何细化及效率收益。它是现有辅助生产流程的背景；本研究另外关注独立结构观察的测量、汇总及人员重组。 |
| [ToF-360，§4.4、§5.1、§5.4](https://www.dfki.de/fileadmin/user_upload/import/15783_ToF_360_CVPR_2025.pdf) | 报告 MatterportLayout 漏墙实例及拼接畸变；自身也使用 PanoAnnotator。支持参考复核和图像条件的重要性，不支持“发现 GT 错误就证明工具有因果缺陷”。 |

## 4. 面向具体审稿问题的回复要点

### 为什么已有半自动工具仍采用从头绘制？

本研究需要观察人员自行选择的结构与边界位置，以及这些观察怎样随人数和成员重组形成不同群体布局。Manual 不预置完整布局，并提供 3D 预览供检查；Semi 则记录已有初始化的保留、编辑与纠正。两种条件对应不同的研究问题。

可按审稿问题选用的英文表述：

> Our primary analyses concern the structural details and boundary positions that annotators choose when constructing a layout. We therefore collect from-scratch annotations with a 3D preview for inspection and revision. These submissions allow us to examine how individual observations contribute to collective layouts as team size and membership change. The Semi condition separately records how participants retain, edit or correct initialized geometry.

### Semi 结果怎样支持这一设计？

可引用自然错误保留案例，以及受控任务中的实际提交状态，说明已有结构和缺陷可能延续到终稿。这进一步体现从头绘制观察的价值；不倒写成“实验结束后才决定采用 Manual”，也不据此声称完成了 Manual 相对所有半自动工具的因果优劣比较。

> The Semi results show that initialization errors can persist into submitted layouts, including unchanged submissions and edits that do not resolve the target defect. This finding reinforces the value of separately examining layouts constructed from scratch, where the initial proposal does not predefine the structure.

### 自由输入是否只是人为制造误差？

任务规则规定应表达的空间与几何，输入记录人员实际提交的结构与位置，3D 预览供其检查。目标是否选对、转折是否遗漏，与几何是否规整是不同问题。Q 测量提交布局的几何表现，结构共识汇总多人对转角与上下边界的观察。无需把这些差异解释成纯粹认知能力，也无需为回答此问题恢复已撤销的历史处理叙事。

## 5. 后续使用与更新

- 回复实际问题时选择相关段落，不整篇复制成防御性答辩。
- 保持 Q、配对角点结构共识、门洞交界现象以及人数与成员构成研究的贡献层次；Manual 是采集设计理由。
- 按[写作取舍清单](论文写作取舍与禁止回流清单.md)处理当前写作范围；本文件不授权恢复旧问卷、内部版本、修复审计或排序分支叙事。
- 新确认事实、正式统计更新或作者改变取舍时，更新对应条目；不把假设列为已验证事实。
