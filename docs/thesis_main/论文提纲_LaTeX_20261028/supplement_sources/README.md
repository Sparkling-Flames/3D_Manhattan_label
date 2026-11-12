# 补充材料源文件

本目录保存现有补充材料的编译依赖及支撑输入，是否随投稿提交由目标期刊及数据共享要求决定。不要将目录整体当作必须上传的附件。

## 编译与研究材料

| 目录 | 用途 |
|---|---|
| geometry | 补充 A 的 LaTeX、66 个构造配置及矢量面板；input/geometry_controls.zip 是 render_geometry.py 的实际输入，不是多余压缩包 |
| evidence | 补充 B 的 LaTeX 和面板；source_reference 中的 PDF 是 extract_panels.py 重提取面板的输入，需保留 |
| questionnaire | 当前问卷输入与重算脚本 |
| personnel | 人员、同房、选人与劳动的已保存结果及代码依赖 |
| score_sensitivity | Q 参数敏感性证据 |
| automatic_sensitivity | 补充材料采用的已保存分支比较和汇总输入 |
| implementation_reference | 几何、评分、对应及共识实现参考；运行要求见该目录说明 |

正式编译入口在论文根目录：supplement_geometry.tex、supplement_evidence.tex、supplement_personnel.tex、doorway_supplement.tex。当前正文图片使用 figure_package/latex 和 figure_package/panels；figures 中仅保留现有 TeX 引用的补充图件。

## 投稿准备原则

- 上传当前编译的补充 PDF 及期刊要求的可编辑源文件；复现代码、数据和参考实现按实际共享安排另行提供。
- 不在这里保存旧正文图、历次审稿回执、过期页数校验、重复编译 PDF 或已撤回的选参展示。
- 不以“正文没有引用”为由删除脚本依赖、完整研究输入或有价值的源文件。
- 2026-11-13 已移出旧图、开发选参记录、导航/保存校验及 A/B 重复编译件。它们归档在论文写作工作资料/非投稿历史材料_20261113，不属于投稿源目录；逐项路径见该目录移出清单.csv。
