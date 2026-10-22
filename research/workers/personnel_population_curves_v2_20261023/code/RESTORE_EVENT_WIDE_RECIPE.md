# 恢复原始宽事件表

`restore_event_wide.py` 只依赖 Python 标准库。在包含 `events/` 和 `results/` 的 canonical 研究目录中运行下面命令。`--root` 也可传该目录的绝对路径；输出使用新位置，不能覆盖源事件或端点文件。

## 先试读

```bash
python code/restore_event_wide.py --root . --dataset policy_paired --out /tmp/policy_paired_first48.csv.gz --limit 48
```

## 需要完整宽表时恢复

```bash
python code/restore_event_wide.py --root . --dataset natural_adjacent --out restored/NATURAL_ADJACENT_TRANSITIONS.csv.gz
python code/restore_event_wide.py --root . --dataset natural_intervals --out restored/NATURAL_PAIRED_PATH_INTERVALS.csv.gz
python code/restore_event_wide.py --root . --dataset policy_paired --out restored/POLICY_PAIRED_PREFIX_EVENTS.csv.gz
python code/restore_event_wide.py --root . --dataset policy_direct --out restored/POLICY_DIRECT_PAIRED_PREFIX_EVENTS.csv.gz
```

- 逐列读取 `events/COLUMN_RETENTION_AND_ENDPOINT_MAP.csv`，按 `input_position` 恢复**严格原列及原顺序**。LINKED 表额外的 6 个交付关联字段不追加到宽表，仍完整保留在 LINKED 源文件。
- `keep` 字段逐格复制原 CSV 字符串；`link_endpoint` 按映射的端点键与列从 `results/ENDPOINT_SCALARS.csv.gz` 回连。**不重算任何事件差值、风险或时间比。**
- 默认每次输出 5,000 行，可用 `--chunk-rows` 调整。端点索引写到临时 SQLite 文件，避免把全宽端点表读入内存；结束后自动清理。
- 保留原事件行顺序、数值和缺失；CSV 引号或浮点文本表示不作为字节级一致性承诺。遇到缺端点键、缺字段或重复端点键报错，不静默补值。
- 每次完成保存同名 `.receipt.json`，记录行列数、映射恢复数量和 `--limit`。有 `--limit` 的输出是试读样本，不是完整交付。
- 本次只将每种事件前 48 行与原宽表核对：四种列顺序、文本、缺失掩码均相同，数值最大差为 0；所有 keep 字段逐格字符串不变。回执见 `RESTORE_EVENT_WIDE_SMOKE_RECEIPT.json`。没有重新生成或保存全量大宽表。
