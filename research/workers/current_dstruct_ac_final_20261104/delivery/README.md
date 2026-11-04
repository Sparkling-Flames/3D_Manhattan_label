# 第13–15批下载、安装与文件目录

本轮是当前DSTRUCT直接AC最后一轮。三个ZIP均使用仓库相对路径，依次解压到 `D:/Work/HOHONET`；底座是main `48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b` 和已交付第08–12批。文件身份与采用优先关系见[版本说明](../VERSION_PRIORITY.html)。

|批次|ZIP文件名|完整内容|
|---|---|---|
|13|HOHONET_v21_batch13_current_DSTRUCT_AC_audit_and_gap_20261104.zip|当前标签与旧事件/成员/设计审计、全逐图容量、复用与排除、冻结补充请求/有效原答/参考、全部1,408原生端点及失败状态|
|14|HOHONET_v21_batch14_current_DSTRUCT_AC_statistics_20261104.zip|自动/辅助完整物理对底表、52,544旧TARGET指标提取、方法别名、逐图/分层/分项/状态/劳动、精确Q分解、统计代码与说明|
|15|HOHONET_v21_batch15_current_DSTRUCT_AC_mechanisms_and_closeout_20261104.zip|完整中文报告与离线研究台、12个AC原图案例及既有ABC附录、508旧端点诊断、固定XZ背景分析、科学图、最终独立验收和8个项目入口更新|

每包带 `delivery/BATCH_13_FILES.csv` 等相应文件清单，记录ZIP成员、字节数和SHA256。三个包的外部大小与SHA256见单独随包提供的 `HOHONET_v21_batches13_15_DOWNLOAD_INDEX.csv`。清单为校验提供身份，不依赖本次临时目录。

解压全部三包后，打开：

`research/workers/current_dstruct_ac_final_20261104/workbench/index.html`

[中文报告](../REPORT_ZH.html)与[完整原图图册](../mechanisms/CURRENT_DSTRUCT_AC_ATLAS.html)可离线阅读。阅读不要求重新运行分析；[运行说明](../INSTALL_AND_RUN_ZH.html)明确区分重聚合、原生补充和既有端点诊断重放。

## 大文件与可复现性

CSV/JSON的大表保留gzip形式，不只交付均值。自动和辅助完整物理对各自保存；旧TARGET指标合并提取保留全部52,544行。按源池拆分的重复临时提取缓存、Python缓存和运行日志不再重复装包；恢复源分片的固定版本清单与代码均在包内。已提取合并数据足以正常重聚合，不需先下载整个历史指标库。

[SOURCE_INDEX.csv](../SOURCE_INDEX.csv)汇总实际使用的固定main源文件、08–12批增量及本轮冻结快照。各模块还有逐端点、逐原图、逐池和逐指标分片清单。必要源代码仍来自已有仓库底座，不在ZIP里复制整个Git仓库。

本轮新数据均位于专题目录；第15批列出的已有文件更新仅添加采用说明和入口，旧嵌入数据未改。可核对[项目入口变更清单](INTEGRATED_PROJECT_FILES.csv)与[最终验收](../DELIVERY_CHECKS.json)。
