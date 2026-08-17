# post-Block2 analysis pack 2026-08-17 v2

本目录是独立新版本，未覆盖 analysis_results/post_block2_analysis_pack_20260817_v1/。

## 结论

- QA 状态：**NO-GO**
- Prompt 2：**禁止进入**
- Block 3：未生成。
- stage counts：P1=1481、C1=780、C2-B=160、C2A-RP-Block1=40、C2A-RP-Block2=40。

## Block 2

两份原始 export 共 32 个 runtime tasks、40 条 annotations；按 assignment manifest 的 40 条 worker×task 逐行对账。observed mapping 只使用 export task.data 的 base_task_id/deployment_id 与 annotation completed_by，distribution 中 stale pending runtime mapping 明确未使用。active time 绑定冻结 manifest 与其 JSONL SHA。

## Geometry consensus

C1 优先复用 formal audit 冻结的 canonical geometry、pairwise similarity、crowd structure、GT evidence/analysis。C1 freeze 绑定的是 paper_a_method_20260802_v16、commit 6b2564c66295f4cd1a3b2516dee2feffb661896e 和历史 producer/rule SHA；历史 producer source 未保存在仓库，因此 C1 重建状态为 version-bound reconstruction_not_evaluable/source_absent，不把 frozen sidecar 判为错误。C2-B、Block1、Block2 没有伪造公式，统一记录 producer、contract 参数、input SHA 与 output SHA。

## Inventory counts

- submission exclusions：16
- profile P0 inventory：1
- combined inventory：17，即 16 条 submission exclusions + 1 条 profile P0，不是 17 条 submission exclusions。

## Worker profile

没有找到正式 post-Block2 final pooled profile snapshot。post_block2_worker_profile_master.csv 只提供 observed support 和 source-absent 状态；post-C2B profile 仅作为历史来源记录，禁止冒充 final pooled profile。因此当前 QA 保持 P0/NO-GO。

## GT provenance

本包保持 export_label/RAW_DATA_AND_GROUND_TRUTH_SCOPE_NOTE_20260817.md 的用户说明：test 仅少量局部修正，不是全量用户验证；validation 没有研究者自己的修正，只沿用 MP3D/HoHoNet 自带来源，不称为用户验证。该说明 SHA-256 为 c8b422755e75619798c053d5185b77606bce56c525b4d039642aa1feac30393c，并写入 provenance 与逐行字段。

## 文件

- POST_BLOCK2_DATA_PROVENANCE.json：输入、producer、SHA、stage counts、P0/P1。
- POST_BLOCK2_DATA_QA_REPORT.md：QA 报告。
- post_block2_block2_assignment_reconciliation.csv：Block 2 40 行逐行对账。
- post_block2_geometry_reconstruction_consistency.csv：formal producer 重建一致性测试。
- post_block2_exclusion_provenance.csv：每条 exclusion 的 reason/source artifact/SHA/stage/time/version。
- post_block2_worker_profile_master.csv：source-absent profile 状态，非 final pooled profile。
