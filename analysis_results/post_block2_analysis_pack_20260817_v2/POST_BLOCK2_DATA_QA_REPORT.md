# post-Block2 analysis pack v2 QA

- 状态：**NO-GO**
- Prompt 2：**禁止**
- Block 3：未生成

## Stage counts

| stage | observed | expected |
|---|---:|---:|
| P1 | 1481 | 1481 |
| C1 | 780 | 780 |
| C2-B | 160 | 160 |
| C2A-RP-B1 | 40 | 40 |
| C2A-RP-B2 | 40 | 40 |

## Inventory counts

- submission exclusions: 16
- profile P0 inventory: 1
- combined inventory rows: 17 (16 submission exclusions + 1 profile P0 inventory)

## C1 historical binding

- freeze method contract: paper_a_method_20260802_v16 / ebedb421a1f73743380a0f58746e002c0f366031f7120473616a3efb4a010265
- historical commit binding: 6b2564c66295f4cd1a3b2516dee2feffb661896e
- historical rule: docs/thesis_main/geometry_loo_candidate_rule_manifest_v1.json / 2ec80d15019ff76956fdeee214d6647ed9228708ea2b365439649c52ff10823f
- reconstruction status: version-bound reconstruction_not_evaluable/source_absent
- unavailable components: method_contract,geometry_cluster,materializer,representation

## Block 2 observed reconciliation

- raw exports: 2
- runtime tasks: 32
- annotations: 40
- assignment rows: 40
- exact assignment matches: 40
- observed mapping source: raw export task.data base_task_id/deployment_id plus annotation completed_by
- stale distribution runtime mapping used: false

## GT provenance boundary

- test：仅少量局部研究者修正，不是全量 user-verified。
- validation：沿用 MP3D/HoHoNet 自带来源，没有研究者自己的修正，不称为用户验证。
- binding note: export_label/RAW_DATA_AND_GROUND_TRUTH_SCOPE_NOTE_20260817.md; SHA-256 c8b422755e75619798c053d5185b77606bce56c525b4d039642aa1feac30393c

## P0 findings

- post_block2_final_pooled_profile_source_absent [post-Block2]: producer searched: tools/thesis_main/analysis/materialize_final_pooled_profile_freeze.py; no formal post-Block2 snapshot exists

## P1 findings

- c1_version_bound_reconstruction_not_evaluable_source_absent [C1]: frozen sidecar reused; historical producer/rule source is unavailable for exact replay
- estimand_exclusions_present [all]: submission_exclusions=16;profile_p0_inventory=1;combined_inventory=17
