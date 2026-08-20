# Paper A 原始实验数据盘点与客观关联扫描

## 边界

仅使用 Paper A。原始记录为主，派生表只用于 canonical 对账和既有固定关系扫描；不构造 T1/V1 outcome，不给结果分级或按价值排序，阴性、反转及不可评价结果全部保留。

## 原始覆盖

- Label Studio annotation：2,513（P1 1,485；C1 788；C2-B 160；C2-A-RP B1/B2 各 40）。其中 2,501 条连接 canonical spine，12 条为原始重复/版本记录并保留。
- active-log event：34,417；session group：3,735，固定键为 `project_id + task_id + annotator_id + session_id`（空 session_id 仍作为原始值保留）。
- 原始字段账本：3,668 个 `source_path × record_type × field_path` 条目，扫描每条记录而非首行。
- 阶段外日志事件：6,546，明确标记且不按目录静默归入正式阶段。
- C1 active log 没有随当前 main 跟踪逐文件 SHA manifest；本次记录当前文件 SHA，不据此重算正式 active time。

## 派生对账

- canonical submission：2,501（P1 1,481；C1 780；C2-B 160；C2-A-RP 80）；worker 26；semi-review 574；C1 Manual/Semi overlap 25 个 base task。
- C1 原始连接键使用 `project + ls_runtime_task_id + worker_id + annotation_id`，不使用派生表中含义不同的 planned task id。
- active time 的正式分析值只取冻结 spine；Label Studio `lead_time` 与事件片段均独立保存，绝不混入 primary active time。

## 推断

随机种子 20260820；最多五折，分组键不跨训练/验证。p 值来自独立组聚合后的 1,999 次 permutation，区间来自整组 cluster bootstrap；缺失不补零，族内 BH-FDR。关系矩阵只按关系族、predictor、outcome、population、unit 字典序输出。
