# 人数随机顺序精度：执行与复现接口

## 冻结输入与本轮变化

本轮读取的 GitHub main 提交为 `40d0fe62dc62f6f6c12723af10195b7abb7bc9fe`，使用真人 v2。`FROZEN_SOURCE_COMPATIBILITY.json` 记录原生融合、对应、评分、端点包装及人口执行入口的关键源文件与该提交逐字节相同，人口输入快照和恢复的冻结快照包含相同的 229 个人员池。此次没有改动资格、参考、环序、融合、门槛、评分、难度或类别。

`frozen_repo/` 是实际执行的最小冻结代码与必要输入闭包，可从本包直接执行；其来源是此前 R01 的真实恢复件，执行包装同时继承 R04A 修订。文件清单及来源保留于 `RUNTIME_SOURCE_MANIFEST.json` 等文件。本轮新增的是随机顺序设计、缓存请求联接、分片保存与抽样精度分析。

`executed_native_population_runner_20261025.py` 保存实际启动本轮计算时的源码，其 SHA256 与 `../new_endpoints/REQUEST_MANIFEST.json` 一致。`native_population_runner.py` 只补充了可搬移的默认代码路径：优先使用同目录 `frozen_repo/`；两者调用的原生方法相同。可以通过环境变量 `HOHONET_NATIVE_REPOSITORY` 指定已还原全部依赖的同版本仓库。

## 已登记的有限设计

- 177 个普通 Manual 池、17 个门洞 Manual 池，每池新增 24 条独立均匀随机排列。
- 在旧 24 条的噪声上预选普通 Manual 简单／中等／困难各 12 池，并纳入全部 17 个门洞池；这 53 池另新增 48 条，原 24 加新增 72，共 96 条。预选依据为旧样本低至中人数区间的均值 Monte Carlo 标准误 RMS，未读取新结果。
- 原四策略共同支持的 157 个普通 Manual 池，每种策略使用新增自然顺序的前 8 个 base 作严格配对。该支持定义是原四策略齐备且 N≥20，不能用同为 157 图的 N≥30 集合替代。
- 194 池的全部单人队、全部 N−1 队和满员单队，以及 6 个 N≤10 池的全部非空成员子集，另立精确边际设计。它们不被追加为随机路径；n=2 保留原设计延期状态。
- 固定预算执行完即停止，不按升降方向、显著性或曲线平滑程度延长。

`../design/DESIGN_RECEIPT.json` 是登记回执：12,224 条新顺序（7,200 条自然、5,024 条策略），403,376 个新前缀链接，14,904 个精确边际链接，共请求 340,055 个独特队。原人口端点复用 16,246 队，计时批次中本轮新队复用 2 队，其余 323,807 个端点请求执行冻结原生流程，其中包括单人和两人延期记录，不能全部称为一次完整多人融合。满员请求只引用已有的 194 个独特队，没有新算满员端点。

## 随机数、估计对象与权重

主种子数值为 `2026102501`。每个池、每个新增序号的种子由 `JSON(["population_precision_20261025", master_seed, pool_id, new_index])` 的 SHA256 前 8 字节按 little-endian 转成完整 uint64，交给 NumPy `default_rng(seed).permutation(sorted_workers)`；哈希输入中的 master_seed 和 new_index 是 JSON 整数，CSV 中种子按完整字符串保存。实际种子和完整顺序均保存在设计表；不搜索或删除不利种子。`new_index=0..23` 对应 `balanced_new24`；`24..71` 对应 `focus_new48`；已有 replicate 为 0..23，本轮为 `24+new_index`。

自然路径抽取的是固定人员池的均匀随机排列。每个 n 的前缀成员集合因此均匀分布于 C(N,n) 个可行团队；同一路径各 n 有依赖，人数变化及路径重抽应保留整条路径。偶然相同的排列／前缀保留各自抽样权重，但确定性端点只计算一次。已有与新增样本合并时在每个池内按路径等权，跨图汇总保持所声明的图片或建筑权重，不因焦点池多算路径而增加其跨图权重。

策略保持原楼外角色定义，对同一自然 base 作“目标类先进入”的稳定二分排序，类内原顺序不变。它是原策略的抽样总体，不是自然人群的均匀团队总体。精确边际表按独特队 `1/C(N,n)` 计权；它能给出该人数的有限总体均值、分位数、波动及失败率，不能替代完整进入过程的人数配对。

## 执行与端点身份

每个团队从所列原答集合独立执行冻结融合，不把上一人数的融合输出继续和新人融合。规范键为：

`team_key = pool_id + "__" + sha256(canonical_json(sorted(member_workers)))[:20]`。

缓存命中另外检查实际 object_id、参考 id／版本、人数与相同冻结池快照。请求和端点按精确成员集合去重；原顺序完整留在前缀连接表。

每 200 个新端点保存一组三件文件：`part_*.scalars.csv.gz`、`part_*.geometry_state.jsonl.gz`、最后写入的 `part_*.receipt.json`。只有最后回执存在且哈希相符的分片才算已提交；可以重启续算。几何 JSONL 的每行同时含最终候选、原生 compact full_state（身份、票数、位置及连接信息）、精确成员、object_id、资格池哈希与参考。实际失败或不完整保留为独立状态；无法形成 state 时不补造几何。n=2 延期、不可评分与实际失败分开。

## 运行

依赖见 `requirements.txt`。原分析用单线程 BLAS/OMP，6 个融合进程；不需要打包虚拟环境。

```bash
python engine/register_precision_design.py \
  --repo /path/to/pinned-repo \
  --focus analysis_precision/FOCUS_PRESELECTION_OLD24_RMS.csv \
  --out design \
  --benchmark engine/benchmark/ENDPOINT_SCALARS.csv.gz

python engine/native_population_runner.py \
  --requests design/NEW_NATIVE_ENDPOINT_REQUESTS.csv.gz \
  --output new_endpoints --jobs 6 --chunk-size 200

python engine/compile_precision_results.py --base . --repo /path/to/pinned-repo
```

主实验已登记的设计应直接复用；重新生成设计用于核对种子和成员，不以复现报告数字为选种目标。第一条命令需要固定版本人口包的原始设计、标量和快照。其大表仍引用仓库正式路径，不重复放进新包；`../design/ENDPOINT_DEPENDENCIES.csv.gz` 给出每个请求究竟来自旧表、本轮计时批次还是新端点。

编译结果的 `NEW_ENDPOINT_SCALARS.csv.gz` 只含旧人口标量源没有的、本轮实际新增且进入主请求的端点。`NEW_PREFIX_VALUES_COMPACT.csv.gz` 则是所有新增路径的完整值表，既含缓存命中也含新算队，含原 compact 字段、批次、精确成员、B8 分项、时间来源及几何字段。`EXACT_MARGINAL_VALUES.csv.gz` 是单独的精确边际实验。计时批次中未命中主设计的队保留于 `benchmark/`，不进入主估计。

运行结束的合并器会把标量、JSONL gzip 与关联回执读至结尾，并核对 team_key、人数、成员、object_id 和行顺序。最终交付包仍须从实际 ZIP 中逐文件读取至结尾；该步骤由交付验证脚本另行执行，不能用本地目录验证替代。

## 适合入仓库的行分片

完整新标量及轻量几何均按 60,000 行拆成独立完整的 gzip；单片若超过 90 MiB，程序自动减小行数并重建该组分片。CSV 每片有完整表头，JSONL 每行是完整对象，任何分片都可独立读到 gzip 结尾。新前缀值表只有在统一文件超过 90 MiB 时才分片。

```bash
python engine/package_table_shards.py --directory new_endpoints --rows 60000 --limit-mib 90
python engine/restore_table_shards.py \
  --manifest new_endpoints/TABLE_SHARD_MANIFEST.json --output new_endpoints
```

`TABLE_SHARD_MANIFEST.json` 保存各片的行数、完整字段、字节 SHA256、源行范围、首尾 team_key、按行顺序的 team_key 哈希及逐字段语义哈希。恢复器检查全部实际分片，CSV 表头只写一次，并把恢复文件再读至结尾核对语义哈希。压缩字节允许因 gzip 头或压缩级别不同而改变；CSV 字段字符串、JSON 对象值和行顺序保持一致。全票账仍保留于独立完整 state 分片，轻量几何只存最终候选和指向全票账的定位。

## 顺序元数据更正入口

采用 `design/POLICY_ORDER_METADATA_CORRECTION_RECEIPT.json` 所列的更新版顺序表。原登记脚本曾把策略行的两个顺序字段留为 base，自始实际执行的 prefix entrants 和团队正确。更正已从完整冻结前缀重建、核对全部 5,024 策略行；只改顺序清单并新增 `base_worker_order`，不改实验。原件保留在 `design/source_original/policy_order_metadata_20261025/`；`correct_policy_order_metadata.py` 为可运行更正代码。当前 `register_precision_design.py` 同步修正了未来输出，并在生成前缀时断言清单顺序与实际顺序一致。
