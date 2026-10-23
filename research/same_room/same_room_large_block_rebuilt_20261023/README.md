# 同房较大块严格匹配：来源归档与当前入口

本目录保存本轮 R00—R06 新重建设计的完整已收材料。**这是 62,676 个严格 ABC、311,333 个唯一端点的新实验，旧 111,054 端点实验未恢复。** 作者报告与本地独立核验分开保留。

## 阅读顺序

1. [独立核验](../../statistics/same_room_rebuilt_audit_20261023/README.md)：采用结论与实际核验范围。
2. [作者综合报告](REPORT_ZH.md)与[可离线打开的报告](REPORT_ZH.html)：方向、支持、反例与机制。
3. [中文主张索引](CLAIM_INDEX_ZH.csv)、[方向及人员](direction_tables/DIRECTION_READABLE_ZH.csv)、[字段合同](FIELD_CONTRACT.md)。
4. [复现入口](REPRODUCE.md)：恢复大表、精确团队读取和重新分析。

普通 Manual、门洞和其它范围保持原层次；Semi 没有 m>4 严格 ABC 容量，本轮不将 Manual 结论转用为 Semi 结论。人数路径重抽与同语义时间另存[人数稳定性专题](../../workers/personnel_population_curves_v2_20261023/stability_rebuilt_20261023/README.md)。

## 数据与来源

- `design/`：精确 ABC、实际人员、楼外标签、角色、容量与路径。
- `results/`、`geometry/`、`anchor_paths/`：逐事件、同视角几何对照与实际规模/背景变化。
- `native_endpoints/ENDPOINT_SCALARS.csv.gz`：311,333 个唯一端点，失败仍保留。
- `native_endpoints/parts/`：658 份 gzip 几何票账，精确定位见 `ENDPOINT_ARCHIVE_LOCATOR.csv.gz`。
- `cases/first_event/`、`cases/structure_mechanism/`：G130、G172 的实际原图、原答、三队两视角与票账。
- `source_recovery/`：R00 找回材料及未恢复旧原件说明；它不覆盖新实验身份。
- `source_report/repository_snapshot/`：原包附带的旧同房报告副本，不覆盖当前主文档。

[LOCAL_SOURCE_FILES.csv](LOCAL_SOURCE_FILES.csv)逐项记录包名、包内路径、仓库路径与字节数。2026-10-24 将 R00–R06 的 1,909 项、R03 单独清单的 60 项及 10A 的 52 项与仓库副本逐字节核对，均无差异；对应 15 个源 ZIP 已清理，归档内容已推送至 GitHub main（`5d4cc3fdd`）。ZIP 容器不重复存入仓库。三个超过 100 MiB 的 gzip 按原字节分片保存，完整本地表被 Git 忽略，恢复方式见复现说明。

## 本地修补

Windows 包装器修复、两张空 PDF 重建、原件保存及核验详见[本地修补记录](LOCAL_REPAIRS.md)。冻结融合/评分依赖和研究数值未因归档改写。作者清单与回执描述收到时的原件，不能替代独立核验，也不用于认证修补后的文件。
