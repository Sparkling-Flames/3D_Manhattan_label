# C2-A-RP 显著性优先 capacity / power amendment（本地审计）

## 决策结论

- 当前 v4 保持冻结，未授权发放。
- Block 1 当前精确容量为 **14/20**；新增 **3 张**对全部 20 人未见、每图最多 2 人的 stress task 后，精确匹配达到 **20/20**。
- 按冻结 CI 投影，Block 1 后仍有 **16 人**可能需要 Block 2；若现在为这一路径一次性备足，累计至少新增 **11 张** stress task。
- 不建议现在新增工人：新工人不能直接提供已校准的 Full 画像，反而新增 P1/C1/C2 校准负担。

## V1 诊断结果

当前正式点估计的 worker slope 方差位于 0 边界，因此 Full 的风险个体化分量应禁用：Block 1/2 下 policy divergence 均为 0，质量优势效应为 0，质量代理功效仅为名义 alpha（约 0.05）。

以下非零异质性结果仅使用 C2-B 旧模型作敏感性诊断，不是正式预注册 power，也不用于反向选择 reserve 数量：

| 阶段 | 启用风险个体化人数 | stress 内政策分歧概率 | 全 V1 policy divergence | 期望质量差 | 质量代理功效 |
|---|---:|---:|---:|---:|---:|
| Block 1 | 4/20 | 0.999 | 0.201 | 0.00077 | 0.059 |
| Block 2 | 20/20 | 0.991 | 0.199 | 0.00204 | 0.076 |


功效假定 458 个 V1 candidate task、1:1 分配、单侧 0.05 正态近似；只覆盖 delivery-adjusted quality 代理，不覆盖 V1 层级中的 severe failure、unresolved+severe failure、动态容量或聚合效应。

## 建议

先新增 3 张 stress reserve 并完成 20/20 Block 1；随后用真实 Block 1 结果重估 slope 方差与 CI。只有非零异质性仍存在且 16 人确需 Block 2 时，再补至累计 11 张。现在一次性补足两轮 reserve 或招新工人都没有新增决策价值。

容量结论以新增图均为 validation-only、对 20 人全部未见、通过 scope/reference 审核且每图支持上限为 2 为条件；本审计不负责选择或导入这些图片。


## 实际 capacity amendment

- 已冻结 3 张 primary 与 1 张未暴露 backup；前三张从 future-holdout 永久退出 T1。
- amended pool 的精确容量为 20/20。
- Block 1 preview 为 40 行、20 名工人，每人恰好 1 ordinary + 1 stress；单 task support 不超过 2。
- 当前产物仅供本地审核，不是导入或发放授权。
