# S01：完整追加设计与可运行代码

本包与 S00 使用同一固定设计，补齐真实的逐池前缀、缓存依赖及新增端点请求。它是设计包；新增端点输出另按阶段交付。

正式源 main：`b9bcec809fbaec8ab055931a1abb7baa5db44dac`。真人 v2，194个Manual人员池（177普通、17门洞），新自然顺序40,352条，新历史策略顺序10,048条。1,644,576个前缀对应1,396,509个独特团队；其中39,852个团队引用既有端点，1,356,657个团队实际请求新增计算。

## 正式文件

- `design26/NEW_EXACT_ORDER_DESIGN.csv.gz`：50,400条完整顺序，含成员、base、种子和策略定义。
- `design26/POOL_SAMPLING_PLAN.csv`：每池人数、分层、请求及阶段规模。
- `design26/links_by_pool/stage1|stage2/*.csv.gz`：全部1,644,576个前缀链接，保留重复团队的抽样次数。
- `design26/requests_by_pool/stage1|stage2/*.csv.gz`：新增1,356,657个精确队的成员及object_id。六个小池每阶段没有新队，保留完整零行表，不虚构融合。
- `design26/dependencies_by_pool/*.csv.gz`：全部1,396,509个去重团队的新算／复用来源。
- `design26/orders_by_pool/*.csv.gz`、`pool_registration_receipts/`、`REGISTRATION_RECEIPT.json`：可逐池独立核对的顺序与计数。
- `engine26/README_ENGINE_ZH.md`及Python代码：正式从种子生成、执行、缓存联接和分片恢复接口。`generate_registered_design.py`调用原选择函数，但用完整小分片保存；本轮实际由`finalize_registration_shards.py`将已核真实顺序和请求联成逐池表。

本次先前两次长文件导出未完整，不是正式输入；`FAILED_EXPORTS_EXCLUDED.json`仅登记其身份，损坏／不完整大文件不打包。正式逐池片均独立读至gzip结尾，列数和计数均核实；这不改变种子、成员或评分。

## 复用输入

原318,816标量和前轮323,809标量/紧凑几何仍引用所列main中的正式目录及README恢复流程，不重复打包。新旧关联键为`pool_id + team_key`，成员绑定沿`member_workers`和`member_object_ids`，参考沿`reference_id/reference_version`。冻结执行闭包在同提交`sampling_precision_20261025/engine/frozen_repo/`；本轮不修改投票、对应、定位、连接、资格或参考。

原生执行将逐池及每250个团队短片保存标量、紧凑几何和回执，三个固定案例池进一步限制小片大小；全内部票账仅固定三个案例池及按team_key固定哈希1/200子样保留。最终几何对所有新队保存，不能把没保留全票账误当没有最终几何。
