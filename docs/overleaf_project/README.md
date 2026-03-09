# Overleaf Project (Professional Structure)

## Structure

- `main.tex`: 中文主入口（当前稿）
- `sections/`: 按章拆分正文
- `figures/`: 图片
- `tables/`: 表格导出
- `data/`: 数据与统计产物
- `refs/references.bib`: 参考文献
- `scripts/`: 预处理脚本（可选）

## Compile

- Compiler: **XeLaTeX**
- Main document: `main.tex`
- English (Elsevier/ScienceDirect) is isolated in: `docs/overleaf_project_en_elsarticle/`

## Notes

- 已启用 `underscore` 包，普通文本下划线（如 `low_texture`）不再触发 `Missing $ inserted`。
- 若上传 Overleaf 后出现旧缓存错误，请执行 Recompile from scratch。
