# HOHONET topology sequential preflight v3

开发诊断工件；不构成科学结论、正式政策冻结或 Main 启动依据。v1/v2 均为 `superseded_development_descriptive_only`。

- development_only: true
- diagnostic_pre_stage3: true
- scientific_conclusion_prohibited: true
- block3: false
- formal_policy_frozen: false
- formal_profile_frozen: false

## 冻结历史 replay 准入

主分析使用78个 frozen C1 manual geometry-pool task、594条正式候选和13个building。`frozen_geometry_pool_member=true` 是本次 development replay 的准入条件，不等同正式 C1 analysis eligibility。W18/W27 后续退出不追溯删除其已完成的 C1 记录；W14、7条 outside-assignment 以及未进入冻结pool的记录继续排除。15条正式 replacement 已包含在冻结pool中。

两条 owner-confirmed 偶发多点提交使用既有冻结 repaired geometry，标记 `preflight_development_repair_binding=true`、`formal_c1_derivation=false`；原始 structural failure、repair requirement 和 attribution 均保留。该处置不扩展 parser amendment 对正式 Q_GT/peer/LOO 或未来 live delivery 的授权。冻结有效但当前 normalizer 失败的 `370095f69c5b170678fa` 保留在主 replay，并单独标记版本漂移。

## 主 estimand、顺序与敏感性

seed=20260818，replicates=1000。F0、M0_corner_count_gate_geometry_medoid、M1在每个task/replicate使用完全相同的无放回order，共234000个政策行；先在task内汇总，再做78个task等权平均。cluster和medoid读取冻结 pairwise similarity，不重跑旧 parser。

主口径为 frozen pool 78任务。current normalizer、raw structural pass、二者交集以及current20 roster仅报告确定性support敏感性：`{"current20_current_normalizer": 49, "current20_frozen_geometry_pool": 50, "current20_raw_structural_and_current_normalizer": 47, "current20_raw_structural_pass": 48, "current_normalizer": 77, "frozen_geometry_pool": 78, "raw_structural_and_current_normalizer": 75, "raw_structural_pass": 76}`。这些口径不是独立政策比较，不估计未来 candidate exhaustion 或 transportability。

M0停止门只读取corner count，最终输出使用geometry medoid，因此其准确名称是 `corner-count stopping gate with geometry-medoid selection`。M1开发门仍为k=3仅3:0，k=4仅4:0或3:1，k=5仅5:0或4:1；其他k=5状态为`unresolved_expert_escalation_required`，不是`policy_failure`。

## 质量、成本与边界

public-GT complete-case质量仅作诊断。自主未交付记0的结果只称 `reference-evaluable autonomous-delivery mITT sensitivity`；成功输出若缺少合格reference仍保持missing。包含expert fallback的最终质量和总成本均为`not_identifiable`。E[K]及其差值只表示冻结历史几何候选的submission-count replay，不代表paid production cost或生产节省。

raw structural failure、repair、formal replacement、current-normalizer drift、prefix instability、multimodality、GT conflict和actual expert harm分 lane 报告；actual expert/reference delivery harm仍为`source_absent`。M2状态为`not_evaluated_leakage_safe_estimator_absent`；M3状态为`pending_pre_peer_timing_binding`。post-task meta不进入首次路由，不声称causal routing effect。
