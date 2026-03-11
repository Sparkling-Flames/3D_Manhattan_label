# B 线下一步推进清单（2026-03-11）

这份清单只写 B 线从现在起真正该推进的内容，不再沿用旧 split 文件当作正式实验分组真源。

## 1. 当前必须固定的前提

1. 当前仓库里的旧 split 文件不能再被当成 B 的正式 stage-aware analysis 真源。
2. 原因不是简单“字段有点旧”，而是你的实验集设置本身还依赖后续人工选择：
   - Stage 1 manual anchors 仍待补齐；
   - trap 集仍未收集完成；
   - revised thesis target 与旧 split 计划并不完全一致。
3. 因此，B 线目前只能把 A 线 registry 与当前已落盘的 C 线 manifest 当作“当前仓库可审计现状”，不能把旧 split 直接上升为论文正式分组结论。

## 2. B 线接下来真正要推进什么

### 2.1 继续保留 pooled QA，但只当基础审计层

当前 pooled QA 仍然有价值，但价值只在：

1. `schema_version` 分层审计；
2. `active_time_source` 分层审计；
3. mixed-scope、scope-bucket、meta-missing 最小 QA；
4. trusted `dataset_group_source` 的最小 provenance 检查。

它不应再承担：

1. 论文主图；
2. 正式实验分组结论；
3. 直接解释 worker 行为差异。

### 2.2 尽快补 stage-aware 主分析骨架

在旧 split 不可信、人工选择未完的条件下，B 最该先搭主分析骨架，而不是继续扩 pooled QA 图包数量。

优先顺序建议如下：

1. `Worker × Scene` 矩阵骨架
2. 工人画像主图骨架
3. T / I / M 三口径图层
4. Type 4 过程证据图层

### 2.3 让 B 能吃人工补选后的现状

因为你后面还要人工选择图片，B 线需要提前把入口改成可替换分组清单，而不是写死旧 split 文件。

这意味着 B 的脚本或 Notebook 应优先支持：

1. 从 A 线 registry 读取当前 planned/runtime truth；
2. 从 C 线 manifest 读取当前 trap、anchor、OOS gate 现状；
3. 用可替换的 selection manifest 覆盖旧 split 逻辑；
4. 显式区分 thesis target、current planned snapshot、current realized snapshot。

### 2.4 B 线暂时不要做的事

在你补齐人工选择前，B 不应继续做以下事情：

1. 直接按旧 split 输出论文正式分组对比图；
2. 把当前 `PreScreen_semi=30` 当成最终定稿；
3. 把当前 12 个 prescreen anchors 当成 revised thesis target 已实现；
4. 把 pooled QA 里的 `condition` 或 `dataset_group` 解释成正式实验设计标签。

## 3. 一句话结论

B 线现在不该再围着旧 split 文件做正式实验图，而应先把 stage-aware analysis 骨架搭好，并把入口切到 A 线 registry + C 线 manifest + 可替换 selection manifest 的组合上。
