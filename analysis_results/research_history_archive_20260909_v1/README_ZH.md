# 历史研究资料归档

2026年9月9日。当前入口是[研究交接](../../docs/thesis_main/研究交接_20260909.md)、[统一SOP](../../docs/thesis_main/相似场景标注稳定性分析SOP.md)和[当前结果](../multibuilding_threshold_stability_20260909_v1/分析结果.md)。这里保存旧探索的数值、图、旧Word及清理前索引，不能直接作为当前口径的结果引用。

## 做了什么

346份旧结果文件从分散目录打包为ZIP后移除原副本，另保存2份清理前工作区索引快照。348份文件逐项从ZIP读取，与原文件逐字节比较，均一致；ZIP的CRC检查也通过。13个独立ZIP共约272.58 MiB，打包前文件约344.98 MiB，每个ZIP都可单独打开。

归档覆盖旧楼内人员留出、无序点集初探、场景解释修订、单楼试算、人数支持复核和旧人员分层／组合回放。部分旧结果允许不同点数合簇，部分仍按context或固定历史／验证人数分析，不能与当前硬点数、全阶段无辅助、逐图全人数回放混用。归档不表示旧数值被认定造假或全部无用。

当前计算使用的11份census文件（包括全局人员排列）和原文档合并记录留在原路径。新版本的人员参考偏差、类型人数探索、Semi行为探索继续保留；其口径与当前场景分析的区别写在交接文档。旧计算代码和测试仍可查阅，完整运行旧流水线前需恢复相应归档输入。

没有发现仍被Git跟踪的`.pyc`、`.tmp`或表格渲染缓存，因此未为追求数量而取消有效文件的跟踪。现有全景预览v1/v2仍被浏览器回归和复算材料引用，保留。原始导出、模型、人工记录、冻结合同及Git历史不清除。

## 清单和字段

[MANIFEST.json](MANIFEST.json)的`files`每行对应一份归档文件：

| 字段 | 含义 |
|---|---|
| path / member | 原仓库相对路径；也是ZIP内成员名 |
| archive | ZIP在仓库内的相对路径 |
| bytes / crc32 | 原文件字节数和ZIP成员CRC，用于完整性核对 |
| package | 原结果包或清理前索引分组 |
| action | `archive`表示移除原副本，`snapshot_before_index_cleanup`表示仅备份索引后再整理 |

`bundles`每行是一个ZIP及大小、成员数；`retained_dependencies`列出仍保留在原路径的12份文件。`status`和`verification`记录归档完成状态与验证方式。清理后的测试、链接、源文件保护和Git状态见[CLEANUP_QA.json](CLEANUP_QA.json)。

## 查阅和恢复

先查MANIFEST定位ZIP和成员，在压缩包内阅读即可。需要重跑旧脚本时，成员名保留了完整仓库相对路径；将选中ZIP解压到**单独的旧版本仓库副本根目录**，可恢复原路径。

例如下面只把旧单楼试算解压到临时查看目录，不覆盖当前研究文件：

```powershell
.venv/Scripts/python.exe -m zipfile -e analysis_results/research_history_archive_20260909_v1/unb9_scene_transfer_trial_20260909_v1_01.zip analysis_results/history_restore_local
```

如需整套旧流水线，按依赖恢复对应多个ZIP，不要仅恢复报告。`building_convergence_evidence`有3个独立ZIP，需全部恢复才完整。`prior_worktree_indexes`仅用于查找整理前入口，不应覆盖当前README和地图。恢复目录被Git忽略，避免旧结果再次混入当前提交。

本次保持历史计算字节不变，没有重新生成旧指标，也没有把旧报告中的生成时“pending／未提交”状态改成新的分析结论。最新发布情况以Git历史和整理验证记录为准。
