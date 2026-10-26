# 2026-10-26 人数曲线追加：精确设计与冻结端点执行

## 本轮实际登记

- 读取 main：`b9bcec809fbaec8ab055931a1abb7baa5db44dac`，真人 v2。
- 194 个 Manual 池：177 普通、17 门洞；每池新增 208 条独立均匀完整顺序。
- 两个预定批次：`new_index=0..103` 与 `104..207`。主比较旧 48 加新 208 为 256；历史焦点额外 48 单列。
- 157 个既有策略支持池，4 个旧历史 V3 角色策略，各新增 16 条配对顺序。取自然新序号 `0..15` 作为共同 base；这不是新 DSTRUCT/RFUSE 策略验证。
- namespace：`population_wholecurve_precision_20261026`；master seed：`2026102601`。
- 全部 50,400 个新路径，1,644,576 个前缀；1,396,509 个去重团队。其中复用 39,852（旧人数表 23,252、前轮精度表 16,600），新计算 1,356,657（第一阶段 784,140，第二阶段 572,517）。
- 每条路径内部无放回；每个前缀重新对其全部原始作答运行冻结融合。相同集合复用端点，路径表保留重复访问次数。

## 文件权威关系

`design26/REGISTRATION_RECEIPT.json` 列出全部逐池文件及 SHA256。以下是完整逻辑表的分片，不能只取一片：

| 表 | 位置 | 键 |
|---|---|---|
| 真实精确顺序 | `design26/orders_by_pool/*.csv.gz`；完整 50,400 行全局 order 也可用 | `path_id` |
| 新前缀与团队 | `design26/links_by_pool/stage{1,2}/*.csv.gz` | `path_id,k` |
| 缓存/新增依赖 | `design26/dependencies_by_pool/*.csv.gz` | `team_key` |
| 必须新增的精确团队 | `design26/requests_by_pool/stage{1,2}/*.csv.gz` | `team_key` |
| 新端点全部标量 | `new_endpoints26/stage{1,2}/parts/<pool_id>/part_*.scalars.csv.gz` | `team_key` |
| 新端点全部最终候选几何 | 同目录 `part_*.geometry_compact.jsonl.gz` | `team_key` |
| 预定保留的完整身份状态 | 同目录 `part_*.full_state.jsonl.gz` | `team_key` |
| 新路径指标 | `new_endpoints26/stage{1,2}/prefix_values/*.csv.gz` | `path_id,k` |

前两次长开文件描述符的全局导出未通过读回；已隔离并登记于 `FAILED_EXPORTS_EXCLUDED.json`，不作为输入或交付数据。短事务逐池文件已实际解压、解析至末尾。重建的是相同设计的索引与存储，不是重新抽样。独立步骤发现前轮 scalar 尾部另附两条修正行，缓存准备按重复出现的池分段保存，完整保留这些行。

## 运行入口

假定 `BASE` 是本轮目录，已按依赖索引恢复 `repo/`、`prior_recovered/` 及 `inputs_cache26/`。固定评分闭包来自前轮 P01，复用相同 Shapely 2.1.2、NumPy 2.3.5、pandas 2.2.3、SciPy 1.17.0；当前执行 Python 3.12。

```bash
# 从登记的 seed 重新生成相同设计；只写设计，不执行融合。
python engine26/generate_registered_design.py --base BASE

# 已有真实 order 与精确 request 时，重建/校验逐池关联与历史缓存。
# 本轮实际执行了这一衔接步骤；不是从报告数值反推设计。
python engine26/finalize_registration_shards.py --base BASE

# 或验证、复用已有完整缓存准备回执。
python engine26/prefix_outputs.py --base BASE --prepare

# 两阶段均须完成；不按结果符号或显著性停止。
python engine26/execute_extension.py --base BASE --stage 1 --jobs 8
python engine26/execute_extension.py --base BASE --stage 2 --jobs 8
```

`generate_registered_design.py` 使用原登记函数确定种子与成员，但将全局长写器替换为逐池短事务；随后调用正式关联恢复。`register_extension.py` 是本轮实际选择逻辑的来源，不应单独运行其旧全局导出路径。

native 内核、预处理、投票门槛、对应、定位、连接、参考与 B8L2/D10 均从前轮冻结闭包导入。新增代码只组织请求、缓存、状态标签及存储。当前环境对 36 个前轮预设计时团队的 B8L2/D10/节点数/原生状态逐项一致。另对原 4 个计时池各 160 个旧团队测量缓存热身后的速度，选择基于团队键与人数而非 Q；这些不计入新增随机样本。

## 状态解释

`score_status`、`complete_evaluable`、`complete_floor_evaluable`、`connection_available` 等原生字段全部保留。追加 `endpoint_state`：

| 状态 | 含义 |
|---|---|
| `scored` | 正式 B8L2 可得 |
| `design_deferred_k2` | 冻结规则下两人评分暂缓 |
| `fusion_exception` | 冻结融合出现异常 |
| `consensus_incomplete_below_four` | 正式结构所需节点不足 |
| `consensus_not_connected` | 未形成连通候选 |
| `generated_geometry_unscorable` | 已有输出，但底面或完整几何不可评分 |
| `measurement_exception` | 测量发生异常 |
| `reference_unavailable` | 参考不满足评分要求 |
| `not_executed` | 未执行；不会被补成零分或失败 |

`actual_consensus_failure` 仅为前三类形成共识问题的显式组合；几何不可评分与参考问题另列。分析仍可按原生字段给出更细分母。任一缺 Q 均保持缺失，不能填零。完整池只有一支团队，重复满员前缀不是新增独立团队。

## 保存与续跑

通常每 250 个新端点关闭一个完整片；三个预定机制池每片 50 队以限制内存。所有新端点保留 compact 最终候选（points、footprint 及状态）；完整 identity state 留给 `VFuaQ6m2Qom-04`、`wc2JMjhGNzB-46`、`rPc6DW4iMge-06` 全部新队及 SHA256(team_key) mod 200=0 子样本。保留规则不读取结果。

每片先写标量/几何，解压解析到 EOF，再写 SHA 和行数回执。每池完成后才写 `POOL_RECEIPT.json` 与其路径指标；0 新队池也有回执。续跑校验请求 hash、冻结输入 hash 和已保存团队，跳过已完成端点。

8 个执行 worker 是资源安排，不改变抽样设计。重启可降低并行度；不得因某个 Q 结果不利而删队或删路径。最终交付应实际读取包内 CSV/gzip，并用全部请求键与片内端点键核对，不只检查外层 ZIP。
