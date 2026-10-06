# Downloads 研究证据补充（2026-10-06）

这是对7个既有研究ZIP的有限接收补充，不是新研究任务或正式算法入口。当前问题与安排仍以[统一研究模型](../../docs/thesis_main/研究模型_人员图片与融合不确定性_20261006.md)为准。原代码、失败日志和作者结论逐字节保存；本轮只检查归档完整性与来源，没有运行外部程序或确认其科学结论。

## 本批补入什么

- **local_cloud_original/**：171文件、13,148,613字节，完整保留该ZIP全部成员。先读[独立审查](ARCHIVE_INDEX_20261006.md)及[同坐标块敏感性报告](local_cloud_original/independent_experiment/REPORT_ZH.md)。附独立求解代码、30域紧凑输入、全量结果、初次失败与重放记录。它研究同坐标组保持对对应政策的影响；并未证明坐标相同就是同一语义身份，不能改变独立人员票数。
- **point_correspondence_selected/**：99文件、5,623,744字节。补入[报告](point_correspondence_selected/REPORT_ZH.md)、字段与配置、独立复算入口、源码／测试、四图输入、控制、成员变动及域摘要。保留少量已有相同内容的源码／输入以使该目录可以独立重新生成结果。未复制41域的大JSONL候选账本、HTML及截图；原报告关于“本包已有全部账本”的句子描述完整原ZIP，不能套用于本精选目录。直接使用extract_candidate.py需先恢复对应账本，或用原reproduce.py在新目录重新生成。
- **nine_image_supplement/**：125文件、11,426,024字节。补齐既有[九图精选](../fast_research_handoff_20261006/dot_return/)未含的复算环境／来源、逐图事件／路径／成员结果、108基线复核脚本及五图证据脚本与JSON。新增主实验代码并非主要缺口：run_study、check_study、reproduce及vendor本来就已在精选目录。本补充不重复复制它们。

合计395个原件、30,198,381字节；另附本说明、[SOURCE_MANIFEST.json](SOURCE_MANIFEST.json)和[校验记录](VERIFICATION.json)。清单逐成员记录ZIP名、SHA-256、大小、仓库既有匹配位置及新增位置；既有匹配按文件名／大小筛选后做字节比较，不声称搜遍所有改名或压缩形式。

## 七包逐一处置

| Downloads原包 | 本批决定及原因 |
|---|---|
| local_cloud_independent_review_20261006.zip | 完整补入独立敏感性实验及审核证据；原先仅4个成员找到同字节匹配，不能被结构路径包替代。 |
| nine_image_structure_independent_review_20261006.zip | 第1包：补来源、部分逐图结果、五图证据脚本／JSON。未复制17 MB实际基线重放及图像；不能与仓库基线近似相等便宣称原件相同。 |
| nine_image_structure_review_20261006_part2.zip | 第2包：补108基线复算入口、差异／环境／账本检查和逐图结果；主实验run/check代码已有。 |
| nine_image_structure_review_20261006_part3.zip | 第3包：补基线报告生成与邻接敏感性、来源、五图域诊断及逐图结果；已有e9z审计代码不重复。 |
| nine_image_structure_review_20261006_part4.zip | 第4包：补独立检查、代码差异及剩余逐图结果；已有主复算入口和vendor不重复。 |
| point_correspondence_20261006_delivery.zip | 补独立报告、紧凑结果与可重新生成结果的代码／输入；不是仅保存结构路径包中的5个旧源码文件。大候选账本保留原ZIP。 |
| paired_split_research_20260920.zip | 不新增研究文件。64个成员找到同字节匹配，包括全部9个Python文件、报告、输入、主要结果及反例。未匹配36个为缓存、图像／截图、HTML、运行日志和包清单，不据此判无价值；全部原ZIP仍保留。已有入口见下方。 |

[paired_split既有报告](../../analysis_results/paired_split_research_received_20260920/REPORT_ZH.md)与[source_code](../../analysis_results/paired_split_research_received_20260920/source_code/)保留原路径。

## 九图四包及复算边界

四包使用相同根目录，是互补ZIP，不是可随便删一个的重复下载。逐成员核对无冲突后才合并理解。既有dot_return保留主要报告、代码和部分结果；本目录只保存新增部分。需要复算时，在一个新的临时工作目录复制既有dot_return，再将nine_image_supplement内内容按相对路径覆盖到该副本；不要覆盖历史归档。此组合补齐nine_image_study的原包成员，依赖、输入和结果均保留。原命令见既有nine_image_study/README.md。

108基线复核还需要原交接输入，科学叠图还需要原图；本次没有把这些再复制一份。被省略的重放副本、图像及页面仍在四个原ZIP中。原manifest的完整包校验应对完整ZIP解压集合执行，不能直接对精选目录运行后将缺件当作数据丢失。

## 保留与验证

7个ZIP及解压目录全部留在Downloads；本批新增回收0项、0字节。local_cloud虽已完整复制，本轮不追加回收，以保持这一补充任务边界。其余为精选或原有历史接入，更不能因为存了报告就删完整原件。

检查了项目地图与总索引。这里只补外部历史证据，不新增正式研究入口；总索引及模型仍由原线程维护，故未改这些并发文件。清理审计入口另见[Downloads清理记录](../../analysis_results/repo_cleanup/downloads_20261006/README.md)。未改协议、输入资格、历史正文或研究执行入口，未提交或推送。

## 完整原件与回收后续

后续完整原件已迁出Git工作区，见[仓库外归档与回收审计索引](ARCHIVE_INDEX_20261006.md)。本页此前395文件为精选接收记录，不能当作完整包验收；后续各包完整性以仓库外SOURCE_INDEX及逐文件清单为准。历史原件字节保留，科学解释不自动升级。

## 已执行的原件外置

历史完整来源清单与恢复入口现见[可移植原件索引](ARCHIVE_INDEX_20261006.md)。精选中仍保留30个复现参考NPZ及40个gzip见证，六图必要冻结输入也保留。已外置的是本机审计、重复冻结交付及可由完整参考重建的输出mask原件；不以大范围ignore隐藏材料。
