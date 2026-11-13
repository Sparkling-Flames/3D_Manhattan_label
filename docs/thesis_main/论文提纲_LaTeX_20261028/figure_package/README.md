# 正式论文图片包

本目录为 2026-11-13 的 15 组正文正式图及代码。使用方法、替换步骤和完整交付范围见上一级 `README_使用说明.md`。

本包不包含 `.tex`。请将本目录合并进入现有论文的 `figure_package` 目录，保留原 LaTeX 文件。当前图号和分面路径见 `figure_catalog.json`；逐图决定见 `qa/正式图审查与替换_20261113.md`。

复现入口：`python source/rebuild_formal_figures.py`。已有三维模型和照片保留原始素材；统计图保留冻结科学路径。十个构建步骤的顺序见 `source/reproduce.txt`。历史源码仅作来源记录，正式入口已选择当前版本。

本目录 `FILE_MANIFEST.json` 仅列出本次 ZIP 所含文件；没有列入的原论文文件应予保留。
