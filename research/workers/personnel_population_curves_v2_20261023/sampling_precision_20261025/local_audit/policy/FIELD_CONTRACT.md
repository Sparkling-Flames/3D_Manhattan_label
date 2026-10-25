# 策略共同支持修正字段说明

本地独立审查日期：2026-10-25。原作者 `analysis_policy/` 代码和表保持不变。

- `pool_id / policy / batch / phase / metric`：人员池、旧冻结策略、原8/新8/合并16基础路径、人数阶段和指标。
- `candidate_k`：该图声明阶段内的全部人数点数。
- `original_valid_k`：该批次在上述人数点内可估指标的数量。
- `fixed_k / fixed_k_list`：原8、新8、合并16都可估的共同人数点；按每图、策略、阶段、指标固定。这是回顾性共同支持，不能声称某批次包含原计划全部人数点。
- `point`：先在每个固定k的合法路径支持上算指标，再对固定k等权平均。质量按自然/策略共同可评路径；失败用全部尝试，不受Q可用性筛选。
- `attempted_prefixes`：该图该阶段全部路径×候选k的尝试数；`both_Q_prefixes` 是其中双方Q可评数；`legal_QT_prefixes` 还要求完整正值时间、队内单一且两队相同的时间语义。三者不能互换。
- `valid_bootstraps / invalid_bootstraps`：整条基础路径重抽后，所有固定k都可估/至少一个不可估的次数。后者不减k、不补Q=0。
- 总表 `images / candidate_images`：固定共同可估图片数/声明候选图片数。图等权或楼等权身份通过 `weighting` 分开；同一比较的图片及其权重在所有路径重抽中固定。
- `path_valid_replicates / path_invalid_replicates`：对整个固定图片范围可估/不可估的重抽次数。若任何应纳入图片不可估，该次总体结果缺失，不临时删除图片。
- `path_lo / path_hi`：可估重抽的2.5%/97.5%经验分位数。存在不可估重抽时，这是条件于可估重抽的经验范围，不能称完整无缺失的置信带；`path_interval_status` 明示完整、条件或不可用。
- `building_lo / building_hi`：固定已观察路径及点估计后，建筑整块重抽的经验范围，与路径误差分开；不是新建筑验证。
- `positive_images / negative_images / nearzero_images`：固定图片中指标值大于1e-9、小于−1e-9或介于其间的数量。SD、失败等指标的正负不自动代表好坏。

`POLICY_IMAGE_K_RECOMPUTED.csv.gz` 逐项独立重算作者的20个k级指标；`POLICY_IMAGE_PHASE_FIXED.csv` 为修正阶段结果；`AUTHOR_VS_FIXED_IMAGE_PHASE.csv` 保留原值和修正差；`FIXED_K_SUPPORT.csv.gz` 保存每个指标的完整人数支持及不可估次数；`POLICY_PRECISION_FIXED_SUMMARY.csv` 保留全难度、图/楼等权和各阶段汇总。`KEY_EARLY_Q_RESULTS.csv` 仅是前段Q的阅读入口。

时间是已有来源记录的劳动量，不是并行交付时长；这次不重新回放原始时间日志。策略沿用原四套冻结角色，不是DSTRUCT/RFUSE的新策略验证。
