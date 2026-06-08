# 旧版目录回退说明

本次 tools/docs 迁移不保留旧 root wrapper。旧版目录和文件通过 Git 引用保留，便于按需回退或局部取回。

## 远端保留点

- `rollback/pre-tools-docs-reorg-d1df512`
  - 指向迁移前的旧版 commit：`d1df512`。
  - 旧版 `tools/` 根脚本、`docs/` 根文档、`foreign_recruitment/` 根目录都在该引用里。
- `archive/pre-tools-docs-reorg-d1df512`
  - 同样指向迁移前旧版 commit。
  - 用作更直观的旧目录归档分支。

## 查看旧版目录

```bash
git fetch origin --tags
git ls-tree --name-only rollback/pre-tools-docs-reorg-d1df512 tools
git ls-tree --name-only rollback/pre-tools-docs-reorg-d1df512 docs
git ls-tree --name-only rollback/pre-tools-docs-reorg-d1df512 foreign_recruitment
```

## 取回某个旧文件

示例：只取回旧版 `tools/analyze_quality.py` 到当前工作区：

```bash
git restore --source rollback/pre-tools-docs-reorg-d1df512 -- tools/analyze_quality.py
```

示例：只查看旧文件内容，不写工作区：

```bash
git show rollback/pre-tools-docs-reorg-d1df512:tools/analyze_quality.py
```

## 回退整个旧目录布局

如果需要把旧版 `tools/`、`docs/` 和 `foreign_recruitment/` 整体恢复到工作区：

```bash
git restore --source rollback/pre-tools-docs-reorg-d1df512 -- tools docs foreign_recruitment
```

如果需要从旧版重新开一个分支：

```bash
git switch -c restore/pre-tools-docs-reorg rollback/pre-tools-docs-reorg-d1df512
```

## 注意边界

- 回退旧目录布局是文件组织回退，不代表要修改 protocol、schema、routing 或 SOP 语义。
- 本次迁移没有写入 `export_label/`；回退旧目录时也不要把 `export_label/` 当作迁移对象。
- 云服务器运行时 URL `/tools/vis_3d.html` 是部署兼容路径；旧版源码路径可从上述 Git 引用恢复。
