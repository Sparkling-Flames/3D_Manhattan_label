# 暂存文件与唯一推荐的设计下载

**正式分析只推荐 `HOHONET_v21_AC_stage02_frozen_design_clean.zip`。** 新包沿用旧包的精确路径清单，排除唯一的 `stage01b_semi/AC_EVENTS.csv.gz.partial`，不改变任何已冻结事件、成员、标签、替换关系或融合请求。新包52个有效载荷文件加1份manifest，共188,661,197字节，SHA256为 `18efb296e4202a8c130dd8ef021f2eac7521581f12e0ed37934bf4c7797932b2`；全部ZIP字节、内层gzip CRC/EOF、CSV列宽与JSON解析通过，上传回执SHA也相同。

旧包 `HOHONET_v21_AC_stage02_frozen_design.zip` 原样保留，仅作历史来源。其`.partial`条目是构建过程暂存，不是正式设计输入；旧回执对该条目只做ZIP成员字节及哈希核验，未宣称其内层gzip/CSV完整。不得拼接暂存条目或用于统计。本地暂存来源也保留。

新clean包包含完整 `stage01b_semi/AC_EVENTS.csv.gz`，47,914条Semi方法事件。最终跨域去重设计为 `stage01_registered/AC_EVENTS.csv.gz` 的471,758事件、`TEAM_REQUESTS.csv.gz`的478,012团队，以及`DESIGN_LINKS.csv.gz`的550,794链接，均已完整解析。

本次先取回旧包核对整体SHA，再提取原manifest逐文件比较。53个旧路径中50个当前字节相同；3个改动分别为封存校验工具增强、设计说明追加独审及桥接历史、合同状态与桥接说明更新。所有正式登记数据与参数未变；clean包保留49个未变文件和这3个当前说明/工具文件。旧文本版本、逐文件旧新SHA和diff保存在`clean_design_source_verification/`。旧持久包未删；仅按授权删除核验后新下载的重复副本。

完整回执见`clean_design_source_verification/CLEAN_DESIGN_REPACK_RECEIPT.json`。不要为了获得补件继续使用含暂存条目的旧包；另11个小补件已全部纳入通过校验并上传的代码复现包。
