# 正文 Figure 7：支持人数与局部结构

本目录是现行 `figure_package/latex/fig07.tex` 实际引用的正式图源。
整图固定为 145 mm；每行依次为 40 mm 的支持人数图、47 mm 的完整底面和
47 mm 的局部结构图。所有普通文字按这一实际宽度绘制为 8–9.5 pt，
总图注和子图注保持由原有 LaTeX 排版。

## 图示的科学关系

- 两支团队各 10 人，均以 5 人为角点保留门槛。
- Team 1 对转折 A/B 的独立支持为 4/2 人，输出四角布局。
- Team 2 对同两处转折的支持为 8/8 人，输出六角布局。
- 两行完整底面使用相同坐标范围和等比例坐标；局部放大也使用相同范围。
- 虚线为参考，灰线为个人墙线，紫线为共识，叉号为未保留聚类。
- 展示的是不同成员组成，不代表增加人数，也不把两队的人员逐行配对。

## 复现

在 `figure_package/` 中运行：

```bash
python dot_fig07/build.py
```

生成 `panels/team{1,2}_{support,footprint,detail}` 与 `panels/legend` 的
PDF、SVG 和 600 dpi PNG。正式正文引用独立 PDF；带图注的校样不作为图源。

依赖为 Python、NumPy、Matplotlib、Pillow。
`data/consensus_case.json` 保留逐人观察和保存的输出，
`source/original_geometry.py` 用于核对中位数、底面及全景回投。
本轮不重新运行团队实验、聚类或参数选择。

`verification.json` 记录人数、门槛、成员对应、保存中心、真实底面和回投检查。
原逐人支持矩阵仍保存在 `panels/original_person_support.pdf`，供进一步核查。
