# 2026-09-28研究结果历史归档

[逐文件处理清单](../../repo_cleanup/research_cleanup_20260928/actions.json)记录原路径、理由、替代依据、字节数、原Git状态、ZIP成员与验证结果；[保留原因](../../repo_cleanup/research_cleanup_20260928/retained.json)。

每个新ZIP成员已与原文件逐字节核对，并实际解压逐字节核对后移除原副本。`existing_archives/`内原ZIP直接搬移，未再次套ZIP。已结束的独立核查仍是有效历史证据；只有明确superseded或纠正前版本标为被替代。

## 恢复

在独立临时目录或历史工作区运行 `python -m zipfile -e <archive.zip> <restore_dir>`。新ZIP的成员包含完整仓库相对原路径；现有ZIP保持其原成员规则，结合它们原有MANIFEST/README恢复。先核对清单，再把所需输入恢复到历史工作区；不要直接解压覆盖当前仓库。

`*.tracked.zip`保持原已跟踪文件可加入Git；`*.local.zip`和本来被忽略的压缩包仍只留本机。未执行commit或push；发布/迁移时按清单同时备份本地归档。
