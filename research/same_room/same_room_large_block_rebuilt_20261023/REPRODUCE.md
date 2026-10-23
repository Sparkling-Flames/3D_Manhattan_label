# 本地仓库复现补充（2026-10-23）

当前路径为 `research/same_room/same_room_large_block_rebuilt_20261023/`。原件已归档；不需要再次下载冻结源码。

## ZIP 引用说明

`delivery/CROSS_PACKAGE_LINK_CONFIG.json` 和 `delivery/receipts/` 保留原交付包的构建与校读记录；其中 `/workspace/scratch/...` 及 `source_original/` 内的 ZIP 名称/链接仅作历史溯源，不是当前复现入口。R00–R06 的 14 个源 ZIP 与 10A 源 ZIP 容器未存入仓库；其文件成员已按映射逐字节核对并归档至本仓库，源 ZIP 已清理。当前复现请使用本文件中的仓库相对路径。运行所需的 `engine/frozen_repo/.../measurement_engine.zip` 已随冻结源码归档，ZIP 完整性检查通过。案例中的原图 ZIP URL 仅记录原始图片来源；所需案例图片已存于 `cases/`。

## 先恢复三张完整大表

仓库根运行：

```powershell
.venv/Scripts/python.exe research/workers/personnel_mixture_comparison_20261022/restore_large_tables.py --root research/same_room/same_room_large_block_rebuilt_20261023
```

使用已有恢复器与 `LARGE_TABLE_STORAGE.json`，逐字节拼接 9 份原分片；没有抽样、重新编码或删列。本机完整表已可读。其余 gzip 直接读取。

## 运行说明

- 下方作者命令在本专题根运行。Windows 原生包装器已修复 `resource` 导入：仅峰值内存诊断留空，融合/评分算法不改。
- 案例 README 中旧 `work/rebuild_large_block_20261023` 是作者工作目录，现统一对应本专题根；相对命令仍适用。
- `source_recovery/` 对应 R00 的 `recovery/`；该包附带旧报告在 `source_report/repository_snapshot/`，不覆盖当前正文。
- 重算到新输出目录。几何正式分片不重复保存各分片标量，交付目录不能直接当作中断计算缓存续跑。
- 两张原空 PDF 已按原绘图代码重建；作者原回执仍对应收到的原件，修补记录见 `LOCAL_REPAIRS.md`。

以下保留作者完整执行说明。全量统计、融合和分类训练是否已本地重跑，以[独立核验](../../statistics/same_room_rebuilt_audit_20261023/README.md)为准。

---

# 复算与交付使用

本目录建议放在：`research/same_room/same_room_large_block_rebuilt_20261023/`。
R01—R06 保留仓库相对目录，解压到同一个仓库根，不应再给每个 ZIP 增加一层同名文件夹。
R00 是独立恢复档案，位于包内 `recovery/`；需要回填原件时按它的来源索引操作，不将整个恢复目录冒充仓库原路径。
实际输入 main：`e92abe8631d7f01dc192ee796b46f295ece37a6d`。

## 1. 使用哪些包

- R00：实际找回的历史代码、输入、完整人数路径小单元与原件恢复边界；不是旧大块原件。
- R01：本轮冻结精确 ABC 设计、请求、标签/角色与执行代码的最小依赖闭包。
- R02：按事件 ID 选出的首个完整新 ABC 案例；包含两张实际原图、原答、六队状态、票账及图。
- R03：独立人数专题的固定路径重新分析、两类重抽与同来源时间配对；不替代本轮 ABC。
- R04 报告/代码与事件结果：本轮分析结果、方向/成员/建筑/难度/真实路径表、综合报告、接续补丁及新增机制案例。
- R05：本轮 311,333 个去重执行请求的完整标量；按实际交付清单给出的整表或分片恢复为 `native_endpoints/ENDPOINT_SCALARS.csv.gz`。
- R06 各分片：全部新原生 `full_state`、几何与票账；每个状态只出现于一个正式几何分片，失败状态同样保留。

最终有效文件、每包字节数/SHA、分片范围和实际保存状态以统一交付清单为准。旧 01—09 与本轮 R00—R06 不是同一实验身份。
不要用旧同房 m≤4 标量替换本轮缺失文件。已有 main 的大表按依赖索引读取，不重复下载全仓库或原图全集。

## 2. 只复算统计（不重新融合）

在本专题根目录：

```bash
python -m pip install numpy==2.3.5 pandas==2.2.3 matplotlib==3.10.8
python analysis/run_saved_analysis.py --root .
```

需要 R01 的设计、R05 的全标量，以及 R04 中已保存的事件几何结果。
这一步不会拟合类别、选择新团队、改参考或重新评分。详细脚本可单独执行；失败和不可计算保持原状态。
`ANALYSIS_SPECIFICATION.md` 与 `ANALYSIS_AMENDMENTS.md` 位于 `analysis/`，后者说明同语义时间及四端点补充的精确支持。
机器内存紧张时按脚本顺序运行，不同时加载全标量与所有 full_state。

## 3. 按精确设计重新执行冻结融合

此步骤用于复核算法输出，通常无需为阅读结果重复运行。

```bash
cd engine
python -m pip install -r requirements.txt
python restore_frozen_sources.py --verify-only
python native_team_runner.py --requests ../design/ENDPOINT_REQUESTS.csv.gz --output ../native_endpoints_recomputed --jobs 6 --chunk-size 500
python compare_event_geometry.py --events ../design/STRICT_ABC_EVENTS.csv.gz --endpoints ../native_endpoints_recomputed --output ../geometry_recomputed --jobs 2
```

6 个融合进程和 2 个几何进程是本轮运行配置，不是算法参数；可按机器容量减少并发。
冻结依赖逐字节索引为 `engine/RUNTIME_SOURCE_MANIFEST.json`，保留本轮读取提交与历史规则身份。
R01 已附最小 `frozen_repo/`。若缺少依赖，`restore_frozen_sources.py` 只取得索引列出的固定提交文件。
所有最终端点均来自上述冻结原生实现；没有把失败底面修复后评分，没有变更投票、对应、位置或连接规则。
执行器每 500 个端点原子保存标量/状态/回执，重启时验证请求与分片哈希；不得把不同请求复用到同一输出目录。
最终交付保留合并标量，不重复各原生分片标量。原执行过程的断点续跑需要分片标量与几何同时齐全；因此从交付包重新执行时，使用上面的新输出目录，不把已经完成的交付目录当作待续跑缓存。

## 4. 找到一个实际团队、事件或机制例

从 `event_id` 到两视角六个 `team_key`，再从标量定位 `geometry_shard/geometry_line_1based`。
`engine/read_exact_team.py --help` 给出只读团队接口。它不会重算，只读对应分片并核验团队键。
设计中的人员由 `FROZEN_COMMON_CLASS_MEMBERS` 连接两图 `object_id`；冻结输入快照包含对应预处理后原答和参考。

首个完整案例的独立运行命令在 `cases/first_event/README_ZH.md`。
另一个探索性案例的精确选择、提取与呈现记录在 `cases/` 的相应目录；不把所选病例当作独立验证。
原图使用 Release `quality-original-images-20261015` 的 `IMAGE_INDEX.csv` 和分片索引，先核图片键再按需读取。仅交付实际用到的少数原图。

## 5. 人数路径专题单独复算

路径稳定性位于：

`research/workers/personnel_population_curves_v2_20261023/stability_rebuilt_20261023/`

按其 README 执行。已有 318,816 端点、404,082 前缀和 12,398 顺序来自 main 原件；本轮交付完整前缀必要列和精确顺序，可直接复算 2,000 次完整路径/建筑重抽。
正式 04C 229,050 行已与端点键连接核对；截断 `source_original` 不用于计算。
原重抽代码未找回，所以该程序标为本轮新实现分析；没有声称恢复旧区间。

## 6. 接回既有报告

`integration/old_same_room_report_corrections.patch` 仅修正三项已核口径并增加新专题入口。
`integration/HISTORICAL_REPORT_CHANGES.csv` 保留修改前后文字与证据；旧数值及旧阶段提交身份不覆盖。
人员主报告的准确完成插入稿为 `integration/PERSONNEL_REPORT_INSERTIONS_ZH.md`，45项数值和4项采用判断已绑定正式结果；同目录的模板只保留生成来源，不是当前阅读稿。
应用补丁前可执行 `git apply --check`；本轮没有向 GitHub 推送修改。

## 7. 交付完整性

`delivery/pack_and_verify.py` 先关闭 ZIP，再从 ZIP 内逐个读取 CSV/gzip/JSONL 至 EOF，核字段数、行数和每个文件 SHA，最后原子替换交付包。
几何分片索引保存端点数、pool、原生分片 SHA 与对应标量分片 SHA；全标量合并器另外核验所有请求、成员、object_id、几何行与去重键。
已对恢复原件包和冻结设计包作实际取回后的字节一致性检查。其余每包也保留包内通读回执。
回执中的行数是实体文件实际读得，不是从报告抄来的目标数量。

`delivery/CROSS_PACKAGE_LINK_VALIDATION.json` 是实际闭合R01/R04B/R05/七个R06之间的完整关联回执：严格块、成员、object_id、池、六臂Q/完整性、几何队对与行号全部对应。
自包含阅读版 `REPORT_ZH.html` 由 Pandoc 从同一Markdown生成并内嵌五张正式图；复算统计不需要Pandoc。
