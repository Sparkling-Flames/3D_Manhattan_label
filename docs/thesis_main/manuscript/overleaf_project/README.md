# Paper A vFinal Overleaf 工程

当前文档定位为“新版完整论文提纲与方法合同草案”，不是冻结后的最终 SAP。

## 内容结构

- `main.tex`：唯一中文主入口，采用 Elsevier `elsarticle` 预印本版式。
- `sections/00_研究总览.tex`：保留此前 6 页短稿的总览层。
- `sections/01_*.tex` 至 `sections/18_*.tex`：以
  `Paper_A_新版完整论文提纲_vFinal_Draft.md` 为唯一内容真源迁移的完整正文。
- `appendix/A_*.tex` 至 `appendix/I_*.tex`：完整方法与分析合同附录。
- `figures/`：图片目录。
- `refs/references.bib`：参考文献数据库。

旧短稿章节仍由 `00_研究总览.tex` 引用，因此没有删除；旧 A1--A4
文件保留为历史材料，但不再由 `main.tex` 编译。正式方法与分析合同只来自
vFinal 对应章节，不使用旧短稿替代。

## Overleaf 编译

1. Main document：`main.tex`
2. Compiler：**XeLaTeX**
3. TeX Live version：选择 Overleaf 提供的较新稳定版本
4. 首次上传或替换大量文件后：**Recompile from scratch**

本工程不能改用 pdfLaTeX：正文含中文并使用 `fontspec` 与 `xeCJK`。
`elsarticle` 只负责 Elsevier 风格的文档结构，不改变 XeLaTeX 编译要求。

## 结果占位纪律

C1 尚未 closeout。正文中的结果章只冻结报告结构，不得把 dry-run、fixture、
模拟输出或尚未生成的数据写成正式结果。
