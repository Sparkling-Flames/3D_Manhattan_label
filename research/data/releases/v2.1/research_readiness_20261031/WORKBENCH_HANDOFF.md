# v2.1研究台接入交接（2026-10-31）

接收聊天：`01a159f1-9a37-7b41-a914-8944f04d3801`。主线程负责研究文档、RELEASE.json与目录；接收线程只修改已有研究台、展示构建器及对应测试，避免同时改研究数据和目录。

## 接入范围

1. 在已有v2.1入口提供当前研究状态及21模块导航。来源为本目录`MODULE_MATRIX.csv`与`README.md`；文档核验回执为`CHECKS.json`。门洞当前修正结果已交付，模块表连接其computed_delta/index.html及CORRECTED_HEADLINES.json；GT精选从专题交接进入。旧PDF不作为当前数值源。
2. 半队和同房优先接图片难度更新后的数据：`admitted_space_extension/image_difficulty_20261030/HALF_SUMMARY.csv`、`HALF_DIFFICULTY_COMPONENTS.csv`、`SAME_ROOM_HALF_SUMMARY.csv`、`SAME_ROOM_HALF_PAIRS.csv`；标签为其`classification/LABELS_ALL_LOBO.csv.gz`。历史197事件/83图和当前147事件/67共同Q图分开；同房10/5最新322登记、295六端共同Q、19图对，不替换成新选队声明。
3. 联盟入口为`closeout_20261030/alliance_completion_20261031/README.md`及同目录当前汇总。403可执行变化联盟已有端点，11条不足3人容量记录；旧279待补清单只保留历史入口。
4. Q-only：`q_only_exchange_20261031/SUMMARY.csv`、`OUTPUT_STATUS.csv`、`SELECTION_OVERLAP.csv`、`DESIGN_LINKS.csv`、`PAIRED_EVENTS.csv`与英文图。优先解释全样本：14/7与20/7结构−Q_RAW平均Q+0.0619/−0.1135，均未显示额外平均优势；119/147、54/61换入块相同。20/7是35%替换，不是半队。
5. Q-only后续诊断：`q_only_exchange_20261031/diagnostic_20261031/`。类别/Q均值65.215/66.389/80.648；输入无Q但包含参考节点匹配缺失。35个不同Q_RAW事件全部仅差1人，其中21个类别配比相同。`DIFFERENT_SELECTION_EVENTS.csv`及SUMMARY为事后子集，不能覆盖原全样本统计；缺Q和未连接保留。
6. 逐人难度查询：同诊断目录`MANUAL_WORKER_DIFFICULTY_WIDE.csv`、`WORKER_DIFFICULTY_CURRENT.csv`、`DIFFICULTY_PREFERENCES_CURRENT.csv`。60人普通Manual；primary 6512记录、all_admitted 6739；Semi单独。每人简单/中等/困难Q、图片数和同图相对排名并列。难图相对优势不是困难Q一定高于简单Q，也不是任务分配策略已验证。
7. 其它研究模块用现有专题入口和源表接通；不为了统一页面重算科学结果。已有Q/QT同房选队与本次结构Q-only分开。

## 实现及验收

保持现有file://离线分片方案；提供版本、工作标签、范围与有效支持。研究台中文讲解保留，论文英文图直接链接。默认CURRENT不自动推进，v2继续冻结。禁止将缺失当0、将工作分类写为最终确定、将其它31池写为每项主目标实验全部重选完成。

`RELEASE.json`已修正人员状态、Q-only完成及31池难度状态；同步重建研究台的release快照，修正`test_v21_release_scope_display_20261029.py`中强制旧“难度未知”文字的过时断言。保留原冻结labels/conditions对应关系，新工作标签使用单独current字段，避免把旧统计贴到新标签。

验收：实际离线数据与渲染统计一致；v2/v2.1导航；筛选与分母；失败状态；CSV下载；真实浏览器至少走当前总览→半队→Q-only→不同选员→逐人难度及返回路径。浏览器受限时如实记录所用替代与未覆盖项，静态/Node检查不称视觉验收。新增本轮研究不要求打包原图或上传任何数据。

本交接不包含新实验、全库重建、门洞资料改动、提交或推送。交付时保存本机验收回执，并说明研究台仍未覆盖的具体模块，而非笼统宣称全部v2.1已经接入。
