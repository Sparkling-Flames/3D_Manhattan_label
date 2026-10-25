# 固定 X/Y/Z、逐人增加共同背景的规模路径分析

本目录只读取已保存的精确设计与融合指标，不运行融合、不重选路径。底层为真人 v2，使用 `design/size_paths/` 已冻结的 286 条 m=7 路径。每条路径从 n=10 开始，保留原 X7/Y7/Z7 和 D3，让其余实际人员按已登记的无放回顺序逐人进入共同背景 D；同一步加入 A、B、C 的是同一个人。每个可行人数保留，最大 n=21。

## 统计口径

- `all_available`：各 n 所有可行路径。n 较大时可行路径集合会缩小。
- `fixed_capacity_n20`：从设计容量选定能够达到 n20 的同一组路径，展示 n10 至 n20。
- `fixed_capacity_n21`：从设计容量选定能够达到 n21 的同一组路径，展示 n10 至 n21。
- 队列只由容量确定，不要求路径每一步成功，融合失败不删出队列。每条路径在每个 n 贡献一次；先在图片内平均路径，再给图片等权和建筑等权结果。事件数是覆盖量。
- BA=B−A、CA=C−A、CB=C−B 分别保留。同类幅度为 |B−A|；跨类幅度为 (|C−A|+|C−B|)/2；幅度比较要求同一事件 ABC 三队均可评。其差值为跨类幅度减同类幅度。
- 每队相对 n10、相邻 n 的自身变化单列。`CB_change` 为净优势变化，不是 C 队自身升质；恒等式为 `CB_change = C_change − B_change`。`joint_BC_*` 字段将三项限制到相同的有效比较集合，便于直接解释这条恒等式；普通字段保留各自全部可用分母。
- 每个指标保留有效路径、图片和建筑分母。新增失败、恢复、两端均失败、原先可评后失败或下降超过 10 分分别记录；不将失败 Q 设为 0。
- 名义票门槛沿用 `ceil(n/2)`；相邻步按门槛增加/不增加、实际 n 及新进入者类别角色分别汇总。这里同时改变了共同背景和人数，不能把所有变化单独归因于票门槛。
- 记录时间是库存中的 source 秒数，不是本轮新测生产时间。固定 XYZ 并给三队加入同一个人时，CA/CB 的绝对时间差应保持不变；百分比差会随共同分母增长而变化。保存逐路径时间加法核对表。
- Q/B8L2、D10、底面与三维、上下边界、节点与短边、尺度与定位、实际团队间几何差异均使用已有标量。某个质量分项随 n 的变化不等于两份形状的直接几何距离；此处不补造未计算的跨 n 几何距离。

## 运行

```bash
python analysis/size_paths/code/analyze_fixed_block_paths.py --prepare
python analysis/size_paths/code/analyze_fixed_block_paths.py
```

从 `exchange_research_20261025/` 运行上述命令。第二条默认读取 `results/size_paths/EVENT_METRICS.csv.gz`；注册事件未全取得时会停止并保存缺件清单，不把未取得误记失败。可通过显式 `--allow-partial` 生成有标记的阶段结果。

## 输出

`SCALE_CONDITION_COMPARISON.csv` 为便于采用的逐 n 宽表。`CURVE_*` 为逐 n；`FROM_N10_*` 为固定路径相对 n10；`STEP_*` 为精确前后一步；`THRESHOLD_GROUP_*` 和 `THRESHOLD_ENTRANT_ROLE_*` 为门槛/进入角色描述。完整逐事件和逐步派生量分别在 `PATH_EVENT_MEASURES.csv.gz`、`PATH_BASELINE_CHANGES.csv.gz`、`PATH_STEP_CHANGES.csv.gz`，通过 event_id/path_id 返回精确 D/X/Y/Z 和端点。所有结果是否实际完成以 `READINESS.json` 与 `ANALYSIS_RECEIPT.json` 为准。
