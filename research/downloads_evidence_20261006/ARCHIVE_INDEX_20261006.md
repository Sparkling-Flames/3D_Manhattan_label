# 历史原件与公开复现输入（2026-10-06）

完整原件已保存在仓库外，逐文件身份、恢复相对位置和公开摘录见[来源清单](ARCHIVE_INDEX_20261006.json)。仓库不公开原场景评论、内部对象映射或本机来源路径。公开摘录保留原记录、坐标、GT版本、资格、环序、预处理及既有语义裁决；原件与摘录分别标明SHA-256，不称逐字相同。

公开复现不依赖本机D盘：

- [六图复算入口](../pro_parallel_return_20261006/pro_original/reproduce.py)仍使用自身inputs中的冻结表、GeoJSON、公开cases及六张原图。运行`python -X utf8 reproduce.py --out NEW_results`；不改人员、参考或投票规则。
- [独立敏感性实验](local_cloud_original/independent_experiment/README.md)保留30个portable_source完整参考NPZ、输入和全部域定义。运行`python -X utf8 run_sensitivity.py --source portable_source --out NEW_results`可重新生成30个完整条件mask输出。历史mask原字节另存清单，不能把候选数当后验概率。
- 九图复现沿[精选说明](README.md)组合既有dot_return与本补充；40个完整固定/事件gzip见证保留在原位置，完整域/成员/控制与vendor代码沿原组合读取。历史作者SHA清单应对其原完整交付校验，不套用于精选或公开摘录。

旧handoff复制的文档、表及重复图已外置保存；八图照片通过相对路径复用六图inputs和两张保留照片，当前任务说明与公开输入仍有入口。主线当前模型由docs/thesis_main及已完成研究报告维护，不把旧交付快照覆盖到现行文档。需要恢复精确历史原件时，由持有者提供私有归档`cleanup_20261006`，按清单的`restore_path`在独立目录恢复；另有原ZIP的源成员身份，见[SOURCE_MANIFEST](SOURCE_MANIFEST.json)。旧原件不自动成为科学真值。

回收/本机运行原记录也已外置。Windows回收站的既有访问限制见私有审计；移动到回收站不等于释放磁盘空间。本次Git整理没有再次回收文件或清空回收站。
