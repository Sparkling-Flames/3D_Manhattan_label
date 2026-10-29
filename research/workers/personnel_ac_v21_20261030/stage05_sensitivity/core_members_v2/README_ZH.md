# 实际成员核心与使用频次

此目录是最终成员覆盖表，只读取冻结登记身份，未读取目标 Q，未新增团队。

- `AC_CELL_MEMBER_CORES_AND_FREQUENCIES.csv.gz`：26,887 条条件（25,641 Manual、1,246 Semi），每条保留 pool、楼、目标层、方法、n/m、方向、独立 X/Z 块数、A/C/D 变体数、两侧固定核心名单、每人出现在该条件多少条 AC 事件中。
- `AC_CELL_CORE_COVERAGE_SUMMARY.csv.gz`：逐方法、scope、Manual/Semi、n/m 的覆盖计数。类标签依楼外折变化，不将跨楼 C1/C2 编号当成同一个永久人群。
- `CORE_MEMBER_COVERAGE_RECEIPT.json`：输入 hash、CSV 宽度、完整 gzip EOF 和输出 hash。

`source_fixed_core_workers`/`target_fixed_core_workers` 是该条件所有已抽取块的交集；不自动意味着该类别在自然人群中只有这些人。`*_all_available_in_every_block` 才表示该图该类全部可用成员每次都被使用。`*_every_block_identical` 指注册样本内这一侧无成员扰动。频次以条件内不同 AC 事件为分母，不能当成人员独立重复，也不能与其他分类的同一物理团队重复加权。

Semi 登记没有 Manual 的 cell_id 时，以 pool/method/n/m/source_class/target_class 派生仅用于分析的条件 ID，并标记 `cell_id_origin`。团队 key、事件 ID、标签和成员均不变。

例：原主目标 n20/m10，TARGET K3 有3图/2楼的3方向条件，其中2条件来源块固定；RAW3有19图/7楼、21方向条件，来源块固定4、目标块固定4；JOINT3有82图/11楼、82方向条件，来源块固定16、目标块固定13；JOINT4有107图/16楼、107方向条件，来源块固定13、目标块固定21。固定一侧并不使比较失效，但限制对该类别内部成员泛化的程度。各具体核心及逐人频次均能从完整条件表直接取出。
