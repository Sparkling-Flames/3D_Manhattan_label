# Proposal correctness × Model Issue 数据桥接（2026-08-23）

## 核心裁决

1. 当前 648 张审计的主硬门只是 `valid pair encoding + exact corner-pair count`；它是拓扑数量代理，不是完整 topology 正确性，也不是可直接提交性。
2. `.90/.80/.05` strict gate 与 `.75/.65/2%` acceptable gate 都是历史 post-hoc operational thresholds。本报告保留它们作为敏感性字段，不把它们升级为确认性 correctness 标签。
3. 现有 25 张 C1 Semi 任务已全部连接到当前审计；历史 `U_initial` 与当前 proposal audit 不是同一个量，禁止静默替换或混用。
4. `model_issue` worker response 与几何审计 family 不是同一构念；本报告只提供描述性 crosswalk，不把它解释成独立验证或因果机制。
5. Validation/Test 差距在同一 checkpoint 和同一推理配置下仍存在；Validation 是开发集，Test 是最终泛化集。不能用 Validation 的高通过率规划确认性“正确 proposal”比例。

## 输入覆盖

- Model audit: 648 images; Test=458, Validation=190.
- Existing C1 paired Semi tasks: 25.
- Joined C1 response rows: 106; workers=23.
- Test sampling frame after excluding already exposed C1 Semi images: 433/458.

## Split 审计

| split | n | topology_pair_count_exact_rate | mean_topdown_2d_iou | mean_derived_3d_iou | posthoc_strict_pass_n | posthoc_acceptable_n |
|---|---|---|---|---|---|---|
| test | 458 | 0.6266 | 0.8212 | 0.7968 | 95 | 238 |
| validation | 190 | 0.8579 | 0.9258 | 0.9164 | 148 | 156 |

## 现有 C1 任务按角点数量关系

| proposal_topology_relation | task_count | building_count | mean_delta_shannon_entropy | mean_delta_iou_to_gt | mean_edit_rate | mean_issue_report_rate |
|---|---|---|---|---|---|---|
| model_fewer_pairs | 7 | 6 | 0.2268 | 0.0477 | 0.1786 | 0.7500 |
| model_more_pairs | 7 | 6 | 0.0183 | 0.0079 | 0.3429 | 0.3571 |
| pair_count_exact | 11 | 7 | -0.1787 | 0.0894 | 0.2773 | 0.3909 |

这些均是自然发生、观察性的小样本结果。它们不能估计“正确 proposal 的帮助”或“错误 proposal 的伤害”。

## Model Issue 检出桥接

| audit_outcome | row_count | task_count | worker_count | sensitivity | specificity | status |
|---|---|---|---|---|---|---|
| pair_count_mismatch | 106 | 25 | 23 | 0.5500 | 0.6087 | primary_descriptive_topology_proxy |
| posthoc_not_strict_pass | 106 | 25 | 23 | 0.4886 | 0.5556 | legacy_posthoc_threshold_sensitivity_only |
| posthoc_not_acceptable | 106 | 25 | 23 | 0.5417 | 0.6471 | legacy_posthoc_threshold_sensitivity_only |

解释边界：

- `pair_count_mismatch` 只表示模型/GT 角点对数量不等；它不等于 UI 中的 `topology_failure`（配对、闭合、自交等非法结构）。
- `posthoc_not_strict_pass` 和 `posthoc_not_acceptable` 使用分析者定义阈值，只能作为敏感性。
- Worker 在编辑过程中可随时看到并修改 Model Issue 回答；当前 UI 没有锁定 pre-edit 判断，因此不能把它当成纯粹的 issue-recognition 测量。

## 后续实验所需 correctness 状态

未来确认性实验不要从单个连续指标事后二分。每个 proposal 应在分配前保存：

```text
proposal_design_arm: manual / correct / wrong
proposal_generation_source: expert_reference / frozen_model / controlled_perturbation
proposal_error_family: none / localization / missing_structure / extra_structure / adjacent_space / invalid_topology
proposal_error_magnitude
reference_review_status
scope_terminal
proposal_manifest_sha256
```

`correct` 应表示在冻结 operational target 下，经独立 reference review 认可、无需实质结构修复；`wrong` 应由预先冻结的 error operator 与 magnitude 产生。自然模型输出可以用于选图，但不应在看到人工结果后才决定其实验身份。

## 直接复现

```bash
python -m tools.thesis_main.analysis.full_uncertainty.materialize_proposal_correctness_model_issue_bridge_20260823
```
