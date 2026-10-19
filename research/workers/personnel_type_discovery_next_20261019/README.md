# 人员多变量正向与反向分型：Pro Part A 完整内容归档

本目录整理 2026-10-19 的三个 **Part A 新研究 ZIP**。它们是同一次交付的报告/代码表格、冻结输入和精确事件三部分，不是上一轮 v2 四包，也不是四种研究版本。原 Pro 会话：<https://chatgpt.com/c/6ad2e1ea-e5c0-83ec-b7bc-3408ca9b84c0>。本次直接读取的是 Library 已保存的报告与三个研究包；截至审查时，对话中的最终回复尚不能直接读取。

## 先看什么

1. [Pro 中文完整报告（仓库在线阅读版）](REPORT_ZH.md)：正文及数字保持原样，只修正分片/去重后的阅读链接；不代表独立审查认可。
2. [7 个关键实例图集](FIGURE_GALLERY.md)：包内原始 PNG 的 A/B 全景、俯视、三维与完整簇视图；原图和全部 52 个 PNG 均保留。
3. [60 人联合画像](work_personnel_typing_A_20261019/assessment/WORKER_PORTRAITS_60.csv)、[Pro 运行证据](work_personnel_typing_A_20261019/RUN_EVIDENCE_ZH.md)。
4. [完整原成员清单与存放映射](ARCHIVE_FILE_MAP.json)、[三个原包大小和 SHA256](ORIGINAL_ARCHIVES.json)。
5. [独立审查、复算证据与关键统计图](../personnel_type_independent_review_20261019/README.md)：与 Pro 自述分别阅读。

原始报告的字节版本仍在 [原 Markdown](work_personnel_typing_A_20261019/REPORT_ZH.md) 和 [原 HTML](work_personnel_typing_A_20261019/REPORT_ZH.html)。原报告中的相对链接在完整恢复目录可用；直接浏览整理后的树时，优先使用本页在线阅读版。

## 保存范围与去重

- 原三个 ZIP 合计 **1,018,842,344 字节**，共 **3,844 个文件成员**，解压内容 **1,552,498,895 字节**。
- **824 个科学源文件**（160,951,556 字节）与仓库冻结源完全相同；**519 个旧核心文件**（259,866,888 字节）与已入 main 的 [上一轮整理包](../pro_personnel_v2_archive_20261019/README.md) 完全相同，复用现有内容。
- 其余 2,501 个成员全部保留，包括实际团队状态、所有已交付逐事件比较、候选与逐折输出、日志、代码、运行证据、7 张案例原图、PNG 及离线展示。14 个相同内容文件仅存一份，恢复时回填各自原路径。
- 大量逐池文件合并为 gzip tar 内容包，再按不超过 7,000,000 字节分片；其他大表按原内容 gzip/分片。不是 Git LFS 指针，不依赖外部缓存地址。
- **没有额外省略三个 ZIP 内的任何文件。** Pro 在打包前已省略的缓存不会因此出现：22 个反向大概率表等须按原 [重导出说明](work_personnel_typing_A_20261019/reproducibility/README_REEXPORT_REVERSE_PREDICTIONS_ZH.md) 重建。保存了请求与代码，不等于本次已重跑所有计算。
- 每个原成员均记录 SHA256 和恢复路径，代码保持原字节。不会修改原标注、生产评分、正式人员等级；此次提交仅新增归档并补导航，不删除既有内容。

## 一次恢复，无需下载三个 ZIP

在包含本目录及上一轮整理包的仓库克隆内，用 Python 3 运行：

```bash
python research/workers/personnel_type_discovery_next_20261019/bootstrap.py \
  --output /tmp/personnel-part-a-restored
```

产物是 `/tmp/personnel-part-a-restored/work_personnel_typing_A_20261019/`，与原三个包合并后的目录结构及每个成员 SHA256 一致。输出目录必须新建或为空；失败后请另选新目录，入口不会覆盖已有内容。默认只恢复并验哈希，不联网、不装依赖、不重算科学实验。

`--repository` 可指定克隆根目录；`--previous-archive` 可指定上一轮归档位置。科学源优先使用工作树中 SHA 相同的文件，否则从 Git 固定提交 `82c6164b0d4630de5316199c92aa405930973168` 读取。浅克隆缺少历史对象时，先取得该提交；入口不会静默下载或改用新版本。

完整恢复约需 1.56GB；还应预留仓库分片和解压临时文件空间。恢复使用 Python 标准库；数值执行需 Linux/WSL/POSIX、Python 3.12 及 [原固定依赖](requirements.txt)。

## 恢复与复算是两件事

```bash
python /tmp/personnel-part-a-restored/work_personnel_typing_A_20261019/reproducibility/reproduce.py
```

这也是默认只验证关键输入和入口。真正重算要显式选择 `--level aggregate`、`refit` 或 `fresh`，新建独立工作区并加 `--execute`；详见 [原复现说明](work_personnel_typing_A_20261019/reproducibility/README_REPLAY_ZH.md)。不要把默认入口检查或本目录的完整字节恢复称作完整数值复现。

离线查看时打开恢复后的 `presentation/personnel_types_part_a.html`。原文件约 5.4MB，其相对资源已随包保留；GitHub Markdown 图集可免运行先查看关键截图。

## 冻结版本与质量边界

- 计划/输入 main：`dafa73ac7d8ada9a7f5c0e483d695adcbd916550`。
- 科学源：`82c6164b0d4630de5316199c92aa405930973168`。
- 本轮为真实 v2，B8L2 主线，D10 敏感性；四节点人数 8/12/16/24，不包含全部整数人数或 Part B 奇偶机制验证。
- 本整理只保证归档字节、目录及入口，不把候选类别视为已通过独立验收的可互换人员类型。
- [归档恢复验证](PORTABILITY_VALIDATION.json) 记录实际完成的检查。关键图集经过文件存在性核验并抽查一张图；本次归档未重新完成所有页面的浏览器视觉验收。
