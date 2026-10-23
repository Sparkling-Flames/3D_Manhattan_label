# 来源归档与复现入口修补

日期：2026-10-23。只修复交付入口、平台兼容与空图文件；未改冻结算法、类别、资格、GT 或数值结果。

|问题|本地处理|验证与原件|
|---|---|---|
|R01 与 R04A 的 `ENGINE_CONTRACT_ZH.md` 不同|采用 R04A 扩展版本；增加实际完成、状态分母和只读团队接口|R01 版在 `source_original/R01/engine/`；双方内容均保留|
|Windows 没有 `resource` 模块，包装器导入即失败|缺模块时只把峰值内存诊断记为 null；字体缓存改用系统临时目录，几何指针固定正斜线|正式包装器 `--help` 实测通过；原包装器在 `source_original/R01/engine/native_team_runner.py`；`frozen_repo` 未修改|
|G130 `ALL_MEMBERS_RAW_BEV.pdf` 为 0 字节|使用原 `build_case.py` 的同名绘图片段与保存的原答/六队状态重建|26,040 字节，一页；已渲染目视；空原件为 `source_original/R02/cases/first_event/figures/ALL_MEMBERS_RAW_BEV.pdf.empty`|
|R03 `PATH_VS_BUILDING_STABILITY.pdf` 为 0 字节|使用原 `make_report.py` 的同名绘图片段与保存汇总重建|21,227 字节，一页；已渲染目视；空原件在 R03 专题的 `source_original/R03/figures/`|
|作者案例说明仍用 `work/rebuild_large_block_20261023`|在当前 `REPRODUCE.md` 明确映射到本专题根|原说明留存；相对命令未变|
|三张 gzip 超过普通 Git 文件上限|沿用仓库 64 MiB 原字节分片，完整本地副本忽略|9 份分片与来源按字节拼接相同；无新增哈希；恢复器复用既有实现|

## 归档范围

- 收到 14 个 ZIP，1,969 条包内文件记录；重复内容只落一个路径，唯一版本冲突单独保留。外层导航三件另保存于 `delivery/source_original/`。
- 新大块包落本专题；R03 落人员人数专题；R00 落 `source_recovery/`；附带旧同房报告落 `source_report/repository_snapshot/`。
- `LOCAL_SOURCE_FILES.csv` 指向原始字节，修补后的入口另外注明；没有把来源原回执改成新的“通过”回执。
- 下载原件未删除。统筹已对两个专题来源索引的1,972项映射逐字节核对一致，随后删除本轮临时审查副本及新生成的缓存；原始来源和正式成果保留。材料仅在本地整合，远端推送由用户执行。

## 实际检查

所有归档路径与来源字节数逐项核对；三大表分片逐字节拼接检查。只读团队接口实际读取一个完整 gzip 票账分片，团队键/保存定位相符；非法行号及越界定位均拒绝。两张修复 PDF 读取页数与渲染查看通过。研究结论另见[独立核验](../../statistics/same_room_rebuilt_audit_20261023/README.md)，此记录不替代统计或融合核验。

补充有限格式检查：对归档内不超过10 MiB的202个CSV/CSV.gz及764个JSON逐项读取，未见解析或CSV列宽异常。已由主核验读取的大表、658份完整几何JSONL以及保留原件不重复读取；见 `SOURCE_FORMAT_CHECK.json`。
