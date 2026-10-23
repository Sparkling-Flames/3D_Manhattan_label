# 全端点标量与完整几何定位

这是本轮新冻结严格 ABC 设计的正式输出，不是遗失的 111,054 端点原件。输入 main：e92abe8631d7f01dc192ee796b46f295ece37a6d。

- ENDPOINT_SCALARS.csv.gz：311,333 行、142 字段；包含全部尝试、正式评分、分项、成员、对象、时间、失败和完整几何定位。
- 305,161 个端点完整可评，6,172 个保留真实失败：低于四节点 2,600、未形成连接 3,478、无效底面 94。
- ENDPOINT_ARCHIVE_LOCATOR.csv.gz：每团队到实际 R06 包名、几何分片与行号。七份 R06 包合计 658 个 JSONL.gz 分片、311,333 份 full_state；失败也保留。
- GEOMETRY_SHARD_INDEX.csv.gz：658 行原生分片索引。
- ENDPOINT_STATUS_COUNTS、ENDPOINT_STATUS_MARGINALS、POOL_STATUS_COUNTS：全部唯一尝试的状态与逐池分母。

`geometry_status=ok` 包含低于四节点的候选，不等于完整可评；使用 complete_evaluable、score_status 和真实 Q 缺失。人员匿名号与 object_id 原样保存。

## 精确查找

按 R01 事件表的六个 team_key 连接标量，再在定位表找到需下载的 R06 分片。解压时保留包内仓库相对路径。只读 helper：`python engine/read_exact_team.py --help`。它不重新融合。

仅需统计时使用 R04 的已保存事件及分析程序；复算融合时使用 R01 的冻结代码与精确请求，在新输出目录运行。最终包不重复保存每个原生分片的标量，完整合并标量已经包含全部行。

原件恢复 R00、精确新设计 R01、新完整案例 R02、固定人数路径重抽 R03 与本包各有自己的阶段身份。全量正式调用为 311,333，另有 9 次兼容检查和 6 次提前案例重复，不增加正式唯一端点数。
