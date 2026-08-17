# post-Block2 analysis pack v3 QA

- 状态：**GO**
- Prompt 2：**允许**
- Block 3：未生成

## P0 findings

- none

## P1 findings

- c1_version_bound_reconstruction_not_evaluable_source_absent [C1]: frozen sidecar reused; historical producer/rule source is unavailable for exact replay
- estimand_exclusions_present [all]: submission_exclusions=16;profile_p0_inventory=1;combined_inventory=17

## Profile and uncertainty binding

- final profile: `analysis_results/final_calibration_profile_20260817_v1/pooled_worker_profile_v2.csv`
- SHA-256: `11f7e30fd00ec388bc0b5798846002ba7d6c77033011987e0ff4f27d251c8574`
- worker_profile_uncertainty_inputs.csv：由最终 profile 的冻结区间逐字段物化。
- empirical_variance_inputs.json：仅计算现有结果可识别的经验方差；routing counterfactual 明确保留 not_identifiable。
- C1 历史 A0 使用冻结 canonical/pairwise/crowd sidecar；历史 commit 对象本地不存在，不声称源码级重放。
