# HOHONET v2.1 · 第 07 批：完整独立验收与最小修正

## 交付结果

本包完成 AC 与 Q-only 的定向独立验收，并接续同房 ABC、纯类/联盟、有限配比、人数、历史策略、坐标候选和真实间接依赖。原科学数值保持；实际修正为有限配比两份辅助标量 CSV 的 8 个成员字段单元及生成代码。没有新增团队、重做已确认的 57 组排序、重新融合评分或重新开展分类选型。

**Q-only 固定 208 个事件内的五臂处理机会完整；AC 的完整登记处理机会不能声称完整。** AC 所有已确认 57 组引用的传播和当前可评支持数值已验收；登记队列中仍有本批定向人工范围外的无连接对手。可评支持的结果、注册分母和机会边界分别保存。RAW3 其它目标 n=m=4 的当前 13/16 条件均值为负，三个剩余 C 端在合法 Q 范围内的数学界限也保持负；这些极值没有写入实测评分。

主报告：[REPORT_ZH.md](research/fusion/manual_order_acceptance_20261104/REPORT_ZH.md)

- [逐条结论及来源](research/fusion/manual_order_acceptance_20261104/CONCLUSION_MATRIX.csv)
- [执行决策](research/fusion/manual_order_acceptance_20261104/RERUN_DECISIONS.csv)
- [最终数值、支持、版本和引用检查](research/fusion/manual_order_acceptance_20261104/FINAL_CHECKS.json)
- [AC 完整翻向和登记机会](research/fusion/manual_order_acceptance_20261104/ac/REPORT_ZH.md)
- [Q-only 独立验收](research/fusion/manual_order_acceptance_20261104/q_only/REPORT_ZH.md)
- [实际 8 格修正回执](research/fusion/manual_order_acceptance_20261104/secondary/repairs/MEMBER_FIELD_FORMAT_REPAIR.json)
- [研究台](research/statistics/research_explorer_v1_r2_20261017/v21-manual-order.html)

## 应用到仓库

本包是相对仓库根目录的覆盖包，基于此前第 01→05 批按顺序覆盖后的版本。先保留本地已有改动，再将本 ZIP 的内容解压到 `D:/Work/HOHONET` 根目录。第 07 批包含第 06 批验收目录和脚本的同版副本；已应用第 06 批时仍可应用第 07 批。若只从原 GitHub 冻结仓库开始，应先依次应用第 01、02、03、04、05 批，然后应用第 07 批。

不要在第 07 批之后反向覆盖旧包；第 05 批已有回执计数更正，本批另有成员字段格式修正。前五批和第 06 批 ZIP 原文件保持不变。本包不代表已直接写入用户的 Windows 工作目录或已推送 GitHub。

本轮对前五批全部合并文件逐一核对哈希。允许覆盖的旧文件在 [PARENT_OVERLAY_CHANGES.csv](research/fusion/manual_order_acceptance_20261104/PARENT_OVERLAY_CHANGES.csv) 中逐项列明：两份成员表、一个生成脚本、文档入口、研究台静态验收区和对应字体。其余原文件保持逐字节相同。旧自动实验与人工辅助方法身份继续分别保留。

包内 [MANIFEST_BATCH07.json](MANIFEST_BATCH07.json) 保存每个载荷的相对路径、大小和 SHA256。它不包含自身，以避免自引用。源文件引用、原 Git blob 与冻结来源散列留在各模块的输入清单中。完整原表过大时，仅排除已有明确声明、精确子集可离线复现的下载缓存；不排除必要输入。

## 复现范围

所有本轮数值验收已经运行完成，结果和日志化检查表在包内。需要复查时，在仓库根目录执行相应 `tools/thesis_main/analysis/` 验收脚本；各模块报告给出命令和输入边界。审计脚本依赖 Python、NumPy、pandas；其它依赖按对应脚本说明。复现不要求重新融合、重新评分、创建新团队或补造未知人工顺序。

`build_manual_order_acceptance_workbench_20261104.py` 可重新生成静态验收区；包内字体已覆盖本次新增中文，无需下载完整字体。`finalize_manual_order_acceptance_20261104.py` 汇总版本、声明覆盖文件、结论路径和引用检查，不运行新的科学实验。研究台本轮验收为静态 DOM、字体字符和本地引用检查；既有端点数据与交互脚本逐字节保留，不将历史浏览器验收称为本轮重跑。

## 科学边界

57 组仍为定向案例。原缺失 Q 保持缺失，不能把新增可评支持说成从 0 分改善。图片、楼栋、池与事件分别按原层级计权；同一事件出现在多个视图不构成独立重复实验。人工辅助不等于原自动方法达到相同性能。F2/F9 的跨节点 x 平均继续是单独坐标候选，不进入固定坐标主分支，也不推广为全库预处理规则。

来源：Sparkling-Flames（2026），*3D_Manhattan_label / HOHONET v2.1*，研究代码和数据仓库，冻结提交 [`ac395e703d1fef573d1ef3e105df0286d62a0468`](https://github.com/Sparkling-Flames/3D_Manhattan_label/commit/ac395e703d1fef573d1ef3e105df0286d62a0468)。
