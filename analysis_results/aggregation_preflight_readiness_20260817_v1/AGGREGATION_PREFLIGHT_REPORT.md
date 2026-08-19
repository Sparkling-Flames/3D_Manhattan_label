# Aggregation-first 前置确认审计

## 最终分类

`A4_DEVELOPMENT_NOT_READY`

A0/A2/A3/A5 的回顾性开发证据可以保留；但真正 GT-blind、deployable、topology-aware A4 当前不能进入开发确认，因为没有覆盖目标 aggregation tasks 的 SHA-bound pre-outcome image-evidence matrix。该结论不是 A4 科学性能结论，也不是 prospective confirmation。

## 输入版本选择

- 选择：`post_block2_analysis_pack_20260817_v3`。v3 manifest mismatches：`0`。
- v2：`NO-GO`，profile P0 inventory=`1`，QA/manifest SHA 分别为 `cbb2213883c9661373a57ffd1407a2283cd3d87e6f9b3dc7067275f820abcb7d` / `f63bb6fd4df7e9d57db1bb28d980fb30b2c6c1262417bd734dc532f19cd59e4b`。
- v3：`GO`，profile P0 inventory=`0`，formal profile 已绑定 `final_calibration_profile_20260817_v1`；QA/manifest SHA 分别为 `182257251d0662d9d254dfba548c19432ab34fcebf611b0cc230633fe0abc5eb` / `abffc3dc4f28582d8a8d8818e5166aa5040af7a50a2a53995cf109da5efe7d04`。
- v2 只用于版本选择审计；本次数据表全部来自 v3 和独立 development audit outputs，不跨版拼接字段。

## 数据层级与分母

- v3 task/context index：`327` 行；aggregation development universe：`101` 个 task-context，`13` 个 building scene。
- v3 `building_support_summary.csv` 的 327/327 raw `building_id` 是带 hash 的 base_task_id，不是真实 MP3D scene；原文件未改。本次 aggregation index 使用 C1 frozen crowd sidecar 的 `building_id`，其余 task identity 仅在本地审计中标为 derived，不把 raw support summary 当作正确 building registry。
- A0 evaluable：`97/101`；clean A2 evaluable：`62/101`；A3：`98/101`；A4：`0/101`；A5：`90/101`。
- A0 与 clean A2 的共同可评价分母：`61` 个 task；所有 A0/A2/A3/A4/A5 的共同可评价分母：`0`，因为 A4 `source_absent`。未评价的 101 行均保留在 `DATA_HIERARCHY_AND_DENOMINATOR.csv`，没有从分母删除。
- clean A2-A0 task-paired delta：n=`61`，mean=`0.002918481`，variance=`0.001143058`。这只是 development evidence。
- LOBO 方向：`6` positive、`6` negative、`0` zero，共 `12` 个有两方法结果的 fold，不支持稳定方向结论。
- building-stratified bootstrap：`12` 个 paired buildings，95% CI=`[-0.007120850784512194, 0.00780014819477056]`；few-cluster uncertainty 明显不能按 task 独立处理。

## Reference readiness

- public MP3D/HoHoNet reference 可用于 development 评价，但 test 只有少量局部研究者修正，validation 没有研究者自己的修正；均不称为全量 user-verified。
- C1 13 条 conflict 是 candidate-only，`reference_modified=false`，必须 strict exclusion；不能依据聚合结果改 reference。
- C2-B scope audit 仍有 pending conflict count=`1`；该条保持 source_absent/pending，不能进入 closed reference claim。
- 详细 coverage、source path、SHA 和 exclusion 状态见 `REFERENCE_READINESS.csv`。

## Deployability

- panorama 原图输入存在，但只证明 image file 可读；A4 所需的 pre-outcome topology/evidence feature matrix 仍缺。
- C1 preannotation feature：87 rows; ready=0; d_model_feat_candidate_overlap=0；没有 ready frozen matrix。
- boundary/line、portal/opening、独立 occlusion proxy 的 SHA-bound A4 source absent；现有 post-task worker flags、reference cache 或 candidate-only feature audit 不可替代。
- A4 的完整 matrix 不能读取当前 task worker outcome，也不能读取任何候选聚合结果来反推 feature。

## Development/holdout

- 已物化 deterministic building-disjoint split：development `9` buildings，internal holdout `4` buildings；按 `sha256(seed:building)` 排序，seed=`20260817`，未读取任何 A0/A2/A3/A4/A5 outcome。
- 13 个 building 足以形成一次内部留出，但不足以支持 15-building 的当前数据宣称；更重要的是 A4 image feature source absent，所以 split 只能作为后续开发占位，不能宣布 A4 development-ready。

## Baseline 与功效

- clean A2 只改变 worker weight，保留 frozen `min(boundary, wall)` medoid eligibility；没有把 topology mismatch 变成可评价结果。
- `aggregation_required_N.csv` 的 central normal approximation 与公式最大 MDE 差异=`0.0028053410758776647`，required-N 最大差异=`126`；它没有 building cluster design effect。
- 保守 clustered simulation 使用 task delta variance x2、经验 building ICC=`0.000000`、two-sided alpha=`0.05`、seed=`20260817`、replicates=`5000`。`CONSERVATIVE_CLUSTERED_POWER.csv` 中的 true_delta 只是模拟假设，不是 observed effect。

## 边界

- 未实现/调优最终 A4；未启动 prospective 标注；未生成 Block 3；未做 Full-vs-Global 或 continuation-routing 设计；未把 oracle evaluator 当算法性能。
- 未修改 raw export、active logs、历史冻结工件、method contract、SAP、routing 或现有正式分析目录；v2/v3 pack 均未修改。


## 定向统计修正（v2）

- residual 为 task-level 独立误差：聚合和的方差为 `sigma_e2 * N`，不再使用 `sigma_e2 * sum(n_j^2)`。
- 不等 cluster size 方差分量：`MSB=SSB/(J-1)`，`MSW=SSW/(N-J)`，`C=(N-sum(n_j^2)/N)/(J-1)`，`sigma_u2=max(0,(MSB-MSW)/C)`，`sigma_e2=max(0,MSW)`；经验 ICC=0.000000，仅作为 `small_cluster_noisy_estimate_J_12`。
- ICC sensitivity：`0, 0.05, 0.10, 0.20, empirical`；variance scenarios：`central` 与 `pessimistic_2x`；临界值为 `t(df=J-1)`。每个 scenario/ICC/N/building/delta 均单独输出。
- nominal alpha=`0.05`；已知 cluster_se 配合 t 临界值时 implied conservative alpha：J=10 `0.023688`，J=12 `0.027737`，J=15 `0.031970`；delta=0 测试与该 implied alpha 比较，容差仅为 3 个 Monte Carlo 标准误。
- 新增 power regression tests：`PASS`。
- split 表只报告 context、paired-evaluable support 和 reference conflict support，不读取或输出 holdout quality delta；支持不足时标记 placeholder。
