# n20 匹配对照：最终小包与分批结果索引

本包保存已完成研究的总结、小表、代码、输入引用和覆盖收据。Manual 的 **269,814 个完整事件、697 个字段** 已分九批交付；本包不再重复复制。Semi 的 **1,517 个完整事件** 已在独立完整结果包交付，条件保持分开。

## 优先阅读

1. `MANUAL_N20_FINDINGS_ZH.md`：采用判断、质量／形状／时间／失败与反例。
2. `checkpointed_manual/summary/N20_MANUAL_KEY_FINDINGS.csv`：方法与父类内关键结果；同目录另有 m、难度、来源匹配响应表。
3. `checkpointed_manual/time_analysis/N20_QTD_LOWQ_SLOW_CLASS_DIRECTIONAL_EVENTS.csv`：875 个方向事件；A/B 和 A/C 的匹配 m 与 B/C 的实际净换人数分开。
4. `results_semi/RESULTS_ZH.md`：Semi 独立结果和机会限制。
5. `N20_MATCHED_EVENT_FIELD_DICTIONARY.csv`：完整 697 字段定义。

时间是原来源记录时长之和，单位秒；新批标记为 `user_processed_reported_not_raw_log_replayed`，本分支没有重放原始日志验证主动时长。统计以建筑为单位描述，质量无效不补零，原生失败留在失败及联合稳定分母。

## 九批 Manual 结果

| 批次 | 事件数 | 池数 | 建筑数 | 至少一队原生失败事件 |
|---|---:|---:|---:|---:|
| BATCH_001 | 161 | 3 | 1 | 0 |
| BATCH_002 | 17,305 | 32 | 4 | 604 |
| BATCH_003 | 30,442 | 5 | 1 | 1,866 |
| BATCH_004 | 5,179 | 32 | 7 | 0 |
| BATCH_005 | 35,455 | 10 | 1 | 12 |
| BATCH_006 | 55,667 | 10 | 1 | 1,047 |
| BATCH_007 | 30,612 | 36 | 3 | 302 |
| BATCH_008 | 40,330 | 14 | 1 | 1,108 |
| BATCH_009 | 54,663 | 22 | 3 | 8 |
| 合计 | 269,814 | 164 | 22 | 4,947 |

`N20_MANUAL_RESULT_BATCH_INDEX.csv` 保存每个 ZIP 的精确名称、字节数、SHA256、建筑和失败分母；`N20_MANUAL_RESULT_SHARD_INDEX.csv` 保存全部 164 分片的位置、池、行数和哈希。九批之间没有重复建筑或分片，分片并集与冻结计划一致。流式汇总已逐事件验证完整 ID 并集等于 269,814 个设计事件；此处通过不可变分片哈希及九个 ZIP 哈希衔接该校验，不重新复制宽表。

全部事件仅穷举于各方法自己的预登记有限成员面板；没有穷举全人口所有具体成员集合或所有加入顺序。三团队 A/B/C 是对照臂，不限制人员类别数。所有选择先只用人员和楼外标签，结果阶段再读取质量、几何和时间。

## 恢复与解包顺序

将设计包、九批 Manual 结果包、Semi 设计／结果包分别解压到研究的 `continuation_20261021/n20_abc/` 目录，最后解压本小包，使最终加固的写入及恢复代码生效。早期批内保存的是当时的代码快照，不应改写它们的 manifest 或哈希；最终脚本在本包根目录。

原终点标量、精简几何、冻结类别及输入引用仍由研究主包和 n20 全配置阶段提供，具体 SHA256 见 `REPRODUCE_MATCHED_N20_ZH.md`、`INDEX_RECEIPT.json` 及设计收据。SQLite 查询索引、分片设计输入、原图、虚拟环境、`.pending` 文件均不随本包复制。完成分片的恢复以成功 receipt 为准。

`checkpointed_manual/time_analysis/N20_MATCHED_TIME_EVENT_VALUES.csv.gz` 是可由既有宽表重建的 269,814×32 派生时间表，未重复打入本小包；`TIME_RECEIPT.json` 保留其当时生成哈希。执行 `analyze_n20_time.py` 可以重建它及已交付的小型时间表。主要结果宽表已经包含相应原始终点值。

`N20_M_FINE_ILLUSTRATION_CASES.csv` 的三个案例按明确结果条件后选，仅解释 M 细类正例、D10 门槛敏感性和反例，不估计频率。`PREVIOUS_EVENT_PHYSICAL_OVERLAP.json` 另验证本轮 Manual／Semi 三团队物理集合与旧事件均无重叠，不能据此将本次探索称为全新盲测。

全部实验已经完成；此包的封存不新增融合、评分或分型搜索。
