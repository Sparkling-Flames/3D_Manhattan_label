# Aggregation-first preflight readiness

- Classification: **A4_DEVELOPMENT_NOT_READY**
- Selected input: `post_block2_analysis_pack_20260817_v3`
- This directory is an independent, read-only audit output.
- A4 implementation, prospective annotation, Block3, routing continuation and scientific confirmation were not performed.

See `AGGREGATION_PREFLIGHT_REPORT.md` for denominator, reference, deployability, split and conservative power details.


## 定向统计修正（v2）

- residual 为 task-level 独立误差：聚合和的方差为 `sigma_e2 * N`，不再使用 `sigma_e2 * sum(n_j^2)`。
- 不等 cluster size 方差分量：`MSB=SSB/(J-1)`，`MSW=SSW/(N-J)`，`C=(N-sum(n_j^2)/N)/(J-1)`，`sigma_u2=max(0,(MSB-MSW)/C)`，`sigma_e2=max(0,MSW)`；经验 ICC=0.000000，仅作为 `small_cluster_noisy_estimate_J_12`。
- ICC sensitivity：`0, 0.05, 0.10, 0.20, empirical`；variance scenarios：`central` 与 `pessimistic_2x`；临界值为 `t(df=J-1)`。每个 scenario/ICC/N/building/delta 均单独输出。
- nominal alpha=`0.05`；已知 cluster_se 配合 t 临界值时 implied conservative alpha：J=10 `0.023688`，J=12 `0.027737`，J=15 `0.031970`；delta=0 测试与该 implied alpha 比较，容差仅为 3 个 Monte Carlo 标准误。
- 新增 power regression tests：`PASS`。
- split 表只报告 context、paired-evaluable support 和 reference conflict support，不读取或输出 holdout quality delta；支持不足时标记 placeholder。
