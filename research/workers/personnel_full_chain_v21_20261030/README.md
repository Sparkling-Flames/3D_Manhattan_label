# v2.1全链路补件与Q/QT共同支持归档

2026-10-30。本目录保留作者交付内部结构，原文件未覆盖既有v2或v2.1源数据。

- [主线采用与本地核查](../../data/releases/v2.1/full_chain_downstream_20261030/README.md)。
- [Pro完整报告](HOHONET_v21_full_chain_20261030/REPORT_ZH.md)、[原始复现说明](HOHONET_v21_full_chain_20261030/REPRODUCE.md)。
- [独立Q/QT共同支持补充](common_support/v21_q_qt_common_support_20261030/REPORT_ZH.md)。
- [Pro归档回执](IMPORT_RECEIPT.json)、[逐成员来源](SOURCE_PATH_MAP.csv)；[补充包回执](common_support/IMPORT_RECEIPT.json)。六个Pro包1,406项，补充包31项；全部ZIP成员实际读取通过CRC，路径检查通过，没有同名异版合并，也没有额外批量SHA。
- [本地关键统计](local_review/HEADLINE_CHECKS.json)、[隔离运行检查](local_review/RERUN_CHECKS.json)。

00包以“修复重建版”名称接收；本目录不将其称为损坏原包的字节副本。原始ZIP未删除。包内repository_update仅作为作者拟议补丁保存，没有自动覆盖当前仓库文件；主线接入使用本地审查后的结果。

当前仓库无需依赖下载目录即可读取和复算本轮材料。本地核查命令：`python -B tools/thesis_main/analysis/check_v21_full_chain_20261030.py`（仓库根运行）。所有执行日志属于本地检查，作者回执仍保存在原阶段目录，二者不互相替代。

发布边界：交付包中51张2048×1024原始全景图和3个内嵌原图的HTML查看器只保留在本机，并由`.gitignore`排除；其余报告、源表、复现代码与小型查看器随仓库提交。压缩包CRC回执仍记录完整本地归档，不表示上述原图已上传。

去重说明：Pro交付包的`source/`镜像有177个文件，其中169个与仓库根目录已跟踪文件逐字节一致；7个不同版本单独保存在`source_variants/`；1个Python缓存不归档。云端不重复提交整个镜像，运行代码使用仓库根目录中的对应源文件。
