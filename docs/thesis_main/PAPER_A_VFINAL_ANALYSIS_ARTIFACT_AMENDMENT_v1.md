# Paper A vFinal 分析工件修订合同 v1

## 目的

本修订把 Paper A vFinal 所需的证据拆成可追溯 sidecar。它不改变既有主线 protocol、C1/C2 字段合同、routing 语义或 Label Studio CE-only 运行边界。

## C1 数据边界

当前没有正式 C1 runtime annotation export。因此本轮代码只允许：

- 对测试 fixture 或明确标记的输入执行 `dry_run`；
- 生成结构性 sidecar、schema 检查、候选规则和审计记录；
- 把无法由真实独立标注支持的字段写为 `not_evaluable`。

禁止：把 Calibration import JSON 当成标注结果、伪造 checkpoint/config/preprocess provenance、将 dry-run 数值写入正式分析结果、生成正式 C1 closeout、生成 C2 assignment、改变 `thesis_facing_closeout_ready=false` 和 `c2_decision_chain_ready=false`。

## 兼容性

以下既有 artifact 保留且继续输出：`c1_canonical_annotations.csv`、`c1_quality_annotations.csv`、`meta_label_consensus_summary_C1.csv`、`worker_state_snapshot_C1.csv`、`worker_profile_sidecar_C1.csv`、`worker_task_evidence_table_C1.csv`、`worker_failure_family_response_C1.csv`。legacy consensus 增加显式 `artifact_role=legacy_descriptive_proxy`、`routing_eligible=false`、`scene_profile_primary=false`，不重命名、不删除、不作为新 scene profile 真源。

所有新增表格必须携带 `schema_version`、`rule_version`、`source_artifact`、`source_sha256`、`dependency_bundle_id`、`stage`、`pool`、`condition`、`validity_status`、`interpretation_allowed`。多源表可额外携带 `source_artifacts_json`。

## 新增 sidecar

- canonical evidence：`c1_canonical_meta_observations.csv`、`c1_canonical_geometry.jsonl`、`c1_model_artifact_provenance.csv`；
- meta-label / worker：`worker_task_tag_observations_C1.csv`、`task_tag_three_state_summary_C1.csv`、`model_issue_harmonization_C1.csv`；三状态逐 concrete tag 输出 `+/-/0/NA` 和 NA 分类，不再输出可被误用的 worker response style；
- geometry：`geometry_pairwise_similarity_C1.csv`、`geometry_worker_task_loo_C1.csv`、`geometry_stability_C1.csv`、`geometry_metric_coverage_C1.csv`；
- scene / routing：`worker_scene_profile_candidates_C1.csv`、routing evidence snapshot、`routing_replay_scaffold_C1.csv` 与 temporal replay trace。profile 只能消费三状态 task-tag 与合法 Geometry LOO；旧 offline replay v2 仅保留兼容入口，不能称为 replay。

## 解释层级

`dry_run` 是运行模式，不是正式数据状态；所有 dry-run 行必须 `validity_status=dry_run` 或更具体的 `not_evaluable`，且 `interpretation_allowed=false`。closeout 另行报告 `structural_contract_valid`、`formal_inputs_present`、`artifacts_fresh` 与 `formal_closeout_ready`；缺任一正式证据或 SHA 失配均 fail-closed。
