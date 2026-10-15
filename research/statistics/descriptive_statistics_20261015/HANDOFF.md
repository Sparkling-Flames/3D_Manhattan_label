# 本次统计交付与验证

2026-10-15。本次在原有未提交工作区上新增统计交付，未清理、覆盖或归入本次成果的其它线程改动。用户后续的新授权已实际执行；上一轮仅整理文档、未执行统计的历史仍保留。

## 交付与复用

- [中文统计报告](README.md)、[同房说明](SAME_ROOM_NOTES.md)、[工作簿](现有研究数据描述统计.xlsx)。
- 33张CSV明细/汇总，全部字段见[字段合同](FIELD_CONTRACT.json)，计算结果统一保存在`tables.json`（本地可重建聚合副本，Git保留逐表CSV）。工作簿为查阅快照，修改工作簿不反写源表或自动重算Python统计。
- 生成入口：`python -m tools.thesis_main.analysis.descriptive_statistics_20261015`。此入口明确绑定本次源版本与分母；新批次应另立快照并复核来源，不覆盖本交付，也不绕过当前断言。
- 工作簿入口：`tools/thesis_main/analysis/descriptive_statistics_workbook_20261015.mjs`，使用已配置可解析artifact-tool的捆绑Node工作目录运行。实际导出校验见[工作簿验证](WORKBOOK_VERIFICATION.json)。

本次工作簿复用命令（依赖联接已经建立在以下工作目录）：

```powershell
Set-Location 'C:/Users/ASUS/.codex/visualizations/2026/10/15/01a13eaa-5b3e-7191-8ed5-ce722daf436e'
& 'C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' --max-old-space-size=12000 'D:/Work/HOHONET/tools/thesis_main/analysis/descriptive_statistics_workbook_20261015.mjs'
```

最终工作簿33页、32张筛选表、1张原生柱图，4,152,039字节。长表保留五项核心指标；人员×建筑/房间粗类保留931及836面板，其余仍在CSV。表头及每表首尾源值自检通过，错误值检索无命中，导出ZIP结构复核通过；各页局部已查看，最终34张预览和导出调试旁文件已删除。

## 改动范围

新增主统计、库存/时间、同房、报告四个Python模块与工作簿生成器，以及三个关键测试文件。同步四线程核对页第5/7节、术语、数据说明、统一模型、模块接入交接、Agent入口、文档总索引和项目地图的统计状态与入口。第8节明确保留上一轮文档整理边界的历史身份。

项目地图只登记生成入口、研究交付目录及测试族；33张派生表由报告和字段合同列出，不逐个升格为正式输入真源。

## 验证结果

运行：

```powershell
python -m tools.thesis_main.analysis.descriptive_statistics_20261015
python -m pytest tests/test_descriptive_statistics_20261015.py tests/test_descriptive_inventory_20261015.py tests/test_descriptive_same_room_20261015.py tests/test_same_room_quality_curves_20261015.py -q
```

生成成功；相关测试13项通过。覆盖源/参考错配、重复连接键、缺失与图片等权分母、lead_time及人工加秒不得当有效时间、直接关系不传递补造、同房未作答视角的元数据追溯。

另检查持久化结果：3152唯一库存对象，1145评分/931人员/836同目标层的包含关系；259图难度对全部库存覆盖，无未评分行的难度漏接；1949有效时间且其它状态均留空；33张CSV；217条仅底面记录的I/Sb/D/floor_WQ全部保留，完整WQ/IoU不补值；独立复算836作答等权均值及图片等权均值与汇总相符；756直接关系全部可追溯到建筑及原图片编号。

文档新增入口链接检查通过。按仓库CRLF约定使用 `git -c core.whitespace=cr-at-eol,-blank-at-eol diff --check` 做定向差异检查。

## 边界与下一步

未改正式合同、资格、源坐标、人工审核、时间冻结规则、评分参数或融合规则；没有重评分、新融合实验、导入新增人员/图片、提交或推送。未运行无关训练、Label Studio运营、全仓库历史测试，因未改这些消费者。

651条新采集时间尚未冻结，353条lead_time回填、116条历史不合格、83条已知人工加秒均未当有效时间。若后续需要扩大时间比较，先处理新批次冻结；不要求用户重复已有图片或底面审核。

931中95条与新难度目标不完全兼容，继续留在旧绑定参考描述层；范围/顶界未决及表示不适用保持独立。人员任务组成、共同图覆盖和同房小样本仍限制外推。当前可先用工作簿筛选并核查具体现象，再决定最少的补证据范围，不预先选择有利结果或固定论文大纲。

## 后续追加：独立核验、扩展接入与关键图

用户后续要求再次核验、预留新人／新数据／新算法位置并可视化。实际结果见[独立审计](INDEPENDENT_AUDIT.md)、[接入指南](EXTENSION_GUIDE.md)、[图册及数据](figures/FIGURES.md)。

- 独立检查源身份、3152时间绑定、1145评分，复算2100行汇总、10359行人员对照、3780行同房配对，未发现数值错误。另有可复用核验命令 `python -m tools.thesis_main.analysis.verify_descriptive_statistics_20261015`，直接复算200行总体／难度分布及同房差值。
- 新增 `descriptive_snapshot_inputs_20261015.py`，由`SNAPSHOT_INPUTS.json`登记批次、输入版本、参考版本、算法独立版本、数值方向及范围；旧入口硬断言保留。实际基线演示输出在`research/descriptive_statistics_extension_20261015/`：3152输入、12608算法长表、36覆盖层、42同集合比较。每算法1145有效、2007缺失；普通同目标配对均836。A10/B8L2沿配置实际版本登记，IoU仅声明结果工件快照标签。
- 新接入口拒绝覆盖已有目录，来源同时保存原配置与`SOURCE_LOCATIONS.json`绝对来源位置。新参考或同对象几何修订须先审核、形成独立快照，不在算法接入时推断。
- 8幅正式科研图均含PNG、SVG及数据CSV，已逐图检查中文、边界、分母与缺失显示；这些图是正式交付，保留。未生成额外临时截图。`FIGURE_MANIFEST.json`明确每指标版本及来源，原`score_version`列只指WQ。当前8图消费原描述统计schema和4个指标，不冒称自动消费全部未来long-score结果。
- 本次相关测试共31项通过：原13项、新独立核验1项、绘图3项、接入口14项。后续新增输入无需复制整套历史测试，只需核对新批次身份、参考、资格、覆盖和时间来源。

项目地图及总索引已补登记三个新入口和图册／指南；四线程状态页同步追加状态。没有重评分、逐事件重算时间、启动新融合、修改正式合同／人工审核／准入、提交或推送。
