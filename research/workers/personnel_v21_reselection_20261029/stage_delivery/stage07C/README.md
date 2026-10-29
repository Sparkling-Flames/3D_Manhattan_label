# 阶段 07C：固定原队替换规模、同图背景解释及大团队直接 AC

真实数据 v2.1；仓库提交 `a476461d7ede8db95da43de4139e612c05e618bc`。所有路径以研究 WORK 根目录为基准，和其他阶段包叠加解压。

本包只整理已完成结果；不训练新标签、不新增融合，不复制几何缓存。精确成员见 `experiment/*_design/EVENTS_EXACT.csv.gz`，请求通过 `team_key` 关联去重端点标量。

## 实际覆盖

| 数据集 | 精确事件 | 去重请求/标量 | 图片 | 建筑 |
|---|---:|---:|---:|---:|
| fixed_A_m | 5191 | 11693 | 195 | 22 |
| refinement_m | 2040 | 4647 | 144 | 17 |
| direct_AC | 1622 | 2852 | 190 | 22 |
| refinement_AC | 344 | 635 | 77 | 17 |

合计 9197 条阶段事件，9197 个不同方法事件 ID，19656 个不同实际团队端点。全部事件臂都能关联到本包标量。事件数不是独立统计分母。

## 文件与来源

- `SOURCE_FILE_INDEX.csv`：本包实际载荷的相对路径、字节数与 SHA-256；清单自身不自引用。
- `COVERAGE.json`：逐数据集、逐事件臂的请求—标量完整性和可评分分母。
- `EXTERNAL_REFERENCES.json`：核心标签、代码及前阶段依赖的哈希；避免重复输入和全代码。
- `endpoint_delivery/*/TEAM_GEOMETRY_SOURCES.csv.gz`：按实际 team_key 定位已交付 delta 几何或旧缓存确定性复算来源。几何包另交。
- `experiment/refinement_*_endpoints/SUBSET_PROVENANCE.json`：从共享 refinement 标量逐行提取的精确子表，无新增融合。

固定 A 的 7,397＋2,787 条增量在 `analysis/scale_background_summary/FIXED_A_ALL_M_INCREMENT_METRICS.csv.gz` 合并为 10,184 条，保留 1,947 条真实路径；不再重复收两张原增量宽表。实际 mmax 逐路径保存。ΔC、ΔB、净差使用匹配四个 B/C 端点支持，另留较宽分母；净差增加不全部等于 C 队升质。

直接 AC 两批共 1,966 条事件没有同类 B，不能混进同/跨幅度判断；合并结果见 `analysis/direct_AC_combined_summary/`。同图目标背景对照依赖阶段 07B，固定 XYZ 变 n 路径依赖前阶段全局结果；本包摘要严格区分三个设计。

