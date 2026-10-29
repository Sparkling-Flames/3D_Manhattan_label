# 阶段 07B：重点扩展、共同支持基线及目标成员敏感性

真实数据 v2.1；仓库提交 `a476461d7ede8db95da43de4139e612c05e618bc`。所有路径以研究 WORK 根目录为基准，和其他阶段包叠加解压。

本包只整理已完成结果；不训练新标签、不新增融合，不复制几何缓存。精确成员见 `experiment/*_design/EVENTS_EXACT.csv.gz`，请求通过 `team_key` 关联去重端点标量。

## 实际覆盖

| 数据集 | 精确事件 | 去重请求/标量 | 图片 | 建筑 |
|---|---:|---:|---:|---:|
| focused | 10980 | 30166 | 187 | 22 |
| refinement_baseline | 438 | 1314 | 56 | 13 |
| member_sensitivity | 336 | 448 | 56 | 13 |

合计 11754 条阶段事件，11754 个不同方法事件 ID，31446 个不同实际团队端点。全部事件臂都能关联到本包标量。事件数不是独立统计分母。

## 文件与来源

- `SOURCE_FILE_INDEX.csv`：本包实际载荷的相对路径、字节数与 SHA-256；清单自身不自引用。
- `COVERAGE.json`：逐数据集、逐事件臂的请求—标量完整性和可评分分母。
- `EXTERNAL_REFERENCES.json`：核心标签、代码及前阶段依赖的哈希；避免重复输入和全代码。
- `endpoint_delivery/*/TEAM_GEOMETRY_SOURCES.csv.gz`：按实际 team_key 定位已交付 delta 几何或旧缓存确定性复算来源。几何包另交。
- `experiment/refinement_*_endpoints/SUBSET_PROVENANCE.json`：从共享 refinement 标量逐行提取的精确子表，无新增融合。

`analysis/focused_compact/` 四张全量主表保留全部 10,980 事件效果、端点参考诊断及去重团队对几何；不重复收入 41 MB 的展开宽表和分片。成员敏感性是 n12/m5 六种目标块留一，不冒称原 m6 实验。

