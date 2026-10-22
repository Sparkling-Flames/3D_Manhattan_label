# 冻结团队执行接口（2026-10-23）

本轮读取 main：`72a44e80c344975962e1071bd54d894dd86bb4b4`。
本适配器只执行已给定的实际成员集合，不选择人员，不拟合类别，不改预处理、投票、环序、参考或评分。

## 使用

```bash
export HOHONET_REPO=/path/to/3D_Manhattan_label
python3 -m pip install numpy pandas scipy matplotlib shapely pillow
python3 new_team_engine.py --requests REQUESTS.json.gz --output native --jobs 6
```

请求是 JSON 列表（或 `requests` 列表）或 CSV。字段：`pool_id`、`team_key`、`n`，以及 `workers` 列表或 `member_workers` 的 `|` 分隔字符串。`team_key` 为仓库既有 canonical key：`pool_id + '__' + sha256(json.dumps(sorted(workers), sort_keys=True, separators=(',', ':'))).hexdigest()[:20]`。

`pools/*.json.gz` 每 200 个新增团队保存一次，包含全部原生标量、最终几何和票数；重启命令会在相同请求与输入下续算。全部完成后输出 `ENDPOINT_SCALARS.csv.gz`、`ENDPOINT_GEOMETRY.csv.gz` 和 `RUN_RECEIPT.json`。`full_state` 默认关闭；机制选例可用 `Engine(full_state=True)` 原样重放以取得身份组成员票账。

## 底层接口与数据

- `research/workers/personnel_global_composition_20261021/composition/global_study.py`：`setup_engine()`、`pool_lookup()`。
- `research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz`：229 个既有正式质量/投票池、7302 份正式作答，沿用冻结绑定。
- `research/workers/personnel_interchangeability_20261020/analysis/composition/fusion_runner.py`：`evaluate_one()`，原生融合与 B8L2/D10/分项评分。
- `research/workers/personnel_global_composition_20261021/composition/run_endpoints.py`：`enrich()`，参考几何诊断、实际耗时与来源连接。
- `research/workers/personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz`：`object_id` 对应的记录时间和来源。
- `research/statistics/b8l2_shared_v6_20261016/inputs/measurement_engine.zip`、`working_models.py`：冻结质量分项与 B8L2/D10。

实际导入的仓库代码与必要输入的 SHA-256 见 `FROZEN_INPUT_AND_CODE_MANIFEST.json`。它是复现输入索引，不是重新审计全系统。

## 输出的含义

`B8L2` 主指标，`D10` 敏感性；底面、3D 代理、底点/方向/高度、遗漏/外扩分别保留。`dir` 为算法自身方向误差，不是外部绝对墙向真值。失败和未完成保留原状态、空评分。

结构表达沿用当前构成研究的冻结定义：冗余点为邻边转角 ≤5°；短边为周长占比 <0.04 且两端转角均 ≥15°。这只是几何表达，必要结构应结合参考与实际原图解释。

`source_time_total_seconds` 是继承字段名，表示这个当前图片上成员记录活动时间之和，**不是同房源图历史成本**。`recorded_time_total_seconds` 只在所有成员时间已知、且时间来源语义相同的情况下有值。混合来源不计算统一时间收益；`record_time_by_kind_json` 保留每种记录语义的成员数、已知数、已知和及全知总和。记录活动时间不等于实际排队/交付时间。

## 定向运行确认

`jtcxE69GiFV-28`、共同核心 `W109|W121|W132|W133`：

| 替换块 | B8L2 | D10 | 节点 |
|---|---:|---:|---:|
| W110、W113 | 69.4412719474991 | 74.55298952420378 | 6 |
| W102、W126 | 92.5705117192257 | 94.83463282968256 | 8 |

两队与既有保存结果一致。单队全执行约 0.053–0.056 秒。另按固定种子在同池抽取 n=6/10/15/20 各 8 队用于吞吐计时；平均 0.088/0.118/0.122/0.070 秒（缓存和几何复杂度使耗时不随 n 单调），见 `BENCHMARK.json`。这些 34 次运行是接口/吞吐确认，不计作本轮正式已登记面板结果。
