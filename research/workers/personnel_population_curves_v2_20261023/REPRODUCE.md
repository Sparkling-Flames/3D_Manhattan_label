# 本地接续与最少依赖

先按[归档入口](README.md)恢复唯一超过100 MiB的标量表。人员、参考、正式资格和标签均沿用冻结v2；不需要新增下载即可读取主要结果。

在仓库根运行独立核验：

```powershell
.venv/Scripts/python.exe -X utf8 research/statistics/pro_return_review_20261023/audit_scripts/audit_population.py .
.venv/Scripts/python.exe -X utf8 research/statistics/pro_return_review_20261023/audit_scripts/audit_geometry.py .
```

输出到`analysis_results/pro_return_review_20261023/`，不会覆盖已采用表。修复后的政策事件已经在`events/`；如需重建修复回执，运行同目录`rebuild_policy_events.py .`，读取隔离的损坏原件作逐行对照。

所有前缀原值均可用`PREFIX_TEAM_LINKS.team_key`连接`ENDPOINT_SCALARS.team_key`；顺序用`path_id`连接`EXACT_ORDER_DESIGN`，类别向量用`team_key`连接。先恢复路径频率再汇总，不能对重复团队去重后冒充随机顺序平均。

原生融合、完整派生宽表与全部汇总的原作者命令保留在[source_original/REPRODUCE.md](source_original/REPRODUCE.md)。该记录按Linux编写，部分写盘工具使用目录fsync；本次只验证必要读取和归档恢复，不承诺全部原作者脚本的Windows兼容性。若后续制作图表需要缺少的派生汇总，优先从当前保存表重新聚合，零次融合，不补造未收到的事件原件。
