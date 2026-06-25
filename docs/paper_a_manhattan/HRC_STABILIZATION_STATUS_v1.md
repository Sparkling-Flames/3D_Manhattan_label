# HRC Stabilization Status v1

> 冻结日期：2026-06-21。范围仅限 Manhattan Constrained Hypothesis Ranking Core（HRC）状态盘点；不新增算法、portfolio bucket、搜索器、UI/plugin 或 annotation writeback。

## 1. 当前主模块

- 主 evaluator：`tools/paper_a_manhattan/manhattan_constrained_hypothesis_evaluator.py`。
- portfolio/ranking：`tools/paper_a_manhattan/manhattan_hypothesis_portfolio.py`；独立 runner 为 `tools/paper_a_manhattan/run_manhattan_hypothesis_ranking_core.py`。
- candidate source：runner 通过 C3.1 interface 与 legacy wrapper 调用 M15.28 action library；`legacy_m1528` 仍是唯一 active source，不是新的 constrained candidate generator。
- legacy score：core 输出已把 `legacy_score_breakdown` / `local_score_total` 移出 `constrained_evaluations`，集中到 `legacy_diagnostics` 并标记 `diagnostic_only`；`build_hypothesis_ranking_key()` 已移除 `local_score_total`，legacy score 不再进入 active ranking key，禁止继续调其权重。

## 2. C0–C10 状态

| 阶段 | 冻结状态 | 仓库实际状态 |
|---|---|---|
| C0 | completed | legacy score removed from active ranking key; retained only as diagnostics。`legacy_score_breakdown` / `local_score_total` 仅保留在 legacy diagnostics / evaluator diagnostic fields，不进入 active ranking。 |
| C1 | completed | `manhattan_case_contract.py` 已有 case contract 与 projection-rule-based inferred contract；C1.2/C1.2.1 已禁用 missing/partial/malformed metrics 的 legacy default contract。projection metrics / expert assertions 不足时输出 `contract_status=unavailable`、`contract_source=contract_unavailable`、`fail_closed=true`、`expert_review_only=true`，不再生成 legacy/default/invalid active contract。 |
| C2 | v1 diagnostic implemented | evaluator 已输出 hard feasibility、wall/turn/local residual、height consistency、layout plausibility、evidence interface、movement/edit cost 与 decision class；`direction_family_fit` / `parallel_family_residual` v1 已实现并由真实 projection artifacts 与 core runner 回归锁定，但仍只是可审计 diagnostic，不是 C4 Column Evidence Layer。 |
| C3 | C3.1–C3.4b.3 complete；C3.5 two-family consolidation audit implemented | column-x real audit 与 height real audit 均 fail closed；height positive fixture 仅验证 explicit after-y shadow contract。两个 family 均不接入 active selection；其余三个 family 冻结为 missing，`legacy_m1528` 仍是唯一 active source。 |
| C4 | C4-lite implemented | runner 对已有 HoHoNet proposal 执行 source inventory/parser probe，并物化 corner column、floor/ceiling boundary 与 seam delta；缺失、歧义或合同异常时 fail-closed 为 unavailable，不训练模型、不写回。 |
| C5 | C5-lite plane proxy v0 implemented | evaluator 已物化独立 `plane_proxy_metrics`：复用 direction-family、同族平行 residual、dominant height cluster 与 floorprint residual 形成 geometry proxy。它不是 depth model、不是 GeoLayout reproduction、不是 C4 evidence layer；C6.2 仅把其中 geometry diagnostics 用于分层排序。 |
| C6 | C6.5a.4a spec + 4b fixture contract + 4c minimal implementation completed；still audit-blocked | Active key now follows L0→L5, L1 structural metrics precede direction residuals, L2 has availability/conflict/delta gates, C5 moved out of best_manhattan_feasible, and L4 supports a manual-evidence gate. Default critical bucket selections did not drift. Compliance remains partial because candidate-specific C4 and manual sidecars are incomplete. |
| C7 | blocked | legacy `manhattan_m1527_semantic_direct_search.py` 存在 Hooke–Jeeves 搜索，但新 geometry-normalized MADS/Hooke–Jeeves 在 evaluator 稳定前不得启动。 |
| C8 | 仅记录系统 | feedback ledger schema 与 `materialize_manhattan_feedback_ledger_entry.py` 可保留；不得进入训练、参数更新或自动应用系统。 |
| C9 | blocked | 未发现 Adaptive Parameter Update 实现；不得启动。 |
| C10 | blocked | 未发现 Lightweight Candidate Ranker 实现；不得启动。 |

## 3. 唯一允许的下一步

C6.5a.5.1 completed。4543gt uses independent 4-pair corrected projection；`short_wall_exists=false`；`keep_distinct_contract=not_applicable`；explicit column identity available。旧 `task238_ann2389` 仅为 deprecated old-GT diagnostic，其 manual requirements 不是 corrected-GT blocker。C6.5a.6.2 completed：人工选择 `c6_5a_6_1_candidate_0003`（pair2 y `+0.75`）供 review only；不构成自动接受或 preference 授权。candidate-specific C4 evidence 仍缺失，2369 manual sidecar 仍 pending；C6.5b、C3 shadow expansion、C7/C9/C10 继续 blocked。

`candidate_set.recommended_review_candidate` 只表示 diagnostic/bucket selection，不具有下游授权语义。下游必须同时读取 `overall_verdict.recommended_review_candidate_available`、bucket `accepted` 与 `downstream_recommendation`；当前仍保持 `accepted=false`、`downstream_recommendation=false`，0017 不是 accepted final fix。

- 不扩展 C4，不做 full image-edge evidence；除 `column_x_alignment`、`height_target_reproject` 外的 constrained_v0 family 仍不得实现，C7/C9/C10 仍 blocked；
- 不继续调 `local_score_total` 权重；
- 不新增 portfolio bucket；
- 不自动写回 annotation。

## 4. 文件与依据

- `tools/paper_a_manhattan/manhattan_constrained_hypothesis_evaluator.py`：C2 字段、hard gate、ranking key；legacy score 已从 active ranking key 移除，仅保留 diagnostic 输出。
- `tools/paper_a_manhattan/manhattan_case_contract.py`：C1 inferred contract、C1.2/C1.2.1 missing/partial/malformed metrics fail-closed contract-unavailable 行为与安全边界。
- `tools/paper_a_manhattan/run_case_contract_fallback_audit.py`：C1.1/C1.2 read-only fallback audit；记录 projection-rule-based 正常路径与 missing-metrics fail-closed 状态，不改变 runner。
- `tools/paper_a_manhattan/manhattan_hypothesis_portfolio.py`：C6 当前 portfolio 外壳。
- `tools/paper_a_manhattan/run_hrc_c6_stability_audit.py`：C6.3c read-only active multi-case bucket audit attempt；区分 active HRC bucket audit、`unavailable_for_active_hrc_bucket_audit` 与 evidence-only / fixture-only records，并记录 accepted/downstream 边界。
- `tools/paper_a_manhattan/run_hrc_multicase_audit_input_pack.py`：C6.3d read-only audit input pack materializer；仅复用已有 candidate artifacts / fixtures，输出 audit-only packs，不接入 active runner、不写回、不授权 recommendation。
- `tools/paper_a_manhattan/run_hrc_candidate_adequacy_audit.py`：C6.4 read-only candidate adequacy audit；只审计 existing-artifact/input-pack candidate coverage，不生成 candidate、不改 ranking、不授权 recommendation。
- `docs/paper_a_manhattan/HRC_C6_5_GLOBAL_HYPOTHESIS_PROBE_SPEC_v1.md`：C6.5 shadow-only global hypothesis probe safety spec；仅定义未来有限 probe 的合同，不实现生成器、不运行优化、不接 active runner。
- `tools/paper_a_manhattan/run_hrc_shadow_global_probe_planner.py`：C6.5a read-only planner skeleton；只记录各 case 的 family readiness、missing inputs 与 hard gates，不生成 candidate/geometry variant，不改 active runner/ranking/C3。
- `tools/paper_a_manhattan/run_hrc_source_artifact_readiness_audit.py`：C6.5a.1 manifest-driven source readiness audit；校验 schema/case identity/variant/row count，区分 projection height 与 candidate-row height，并引用独立 manual evidence sidecar schema；不生成 candidate/proposal/geometry，不改 active runner/ranking/C3。
- `tools/paper_a_manhattan/run_hrc_evidence_input_materialization.py`：C6.5a.2 audit-only evidence input materializer；只处理 readiness audit 标记为 materializable 的 2369/2389 输入，复用 original variant 物化 C2/C4/C5/contract baseline diagnostics，不投影或修改 candidate rows，不改 active runner/ranking/C3。
- `tools/paper_a_manhattan/run_hrc_scoring_compliance_audit.py`：C6.5a.3 read-only scoring compliance audit；映射 evaluator/ranking fields 到 L0-L5，记录层序违规和 accepted gate，完全不改 evaluator/ranking/portfolio/runner。
- `tools/paper_a_manhattan/run_hrc_gt_correction_audit.py`：C6.5a.5/5.1 corrected-GT audit；保留 task238/2389 旧 GT 为 deprecated source，物化独立 `task238_ann2389_4543gt` 4-pair projection 与 explicit-column sidecar；short-wall/keep-distinct 不适用，不生成 candidate、不授权 preference/C6.5b。
- `tools/paper_a_manhattan/run_hrc_c6_5a_6_candidate_dry_run.py`：C6.5a.6.1 四个固定 pair2 y-step（`+0.25/+0.50/+0.75/+1.00`）4-pair audit-only 候选及本地 3D preview；不执行搜索、不接 active ranking/portfolio、不授权 preference/writeback。
- `tools/paper_a_manhattan/run_hrc_c6_5a_6_2_manual_selection_ledger.py`：C6.5a.6.2 人工 review-only selection ledger；校验所选 candidate 来自 C6.5a.6.1，不改变 accepted/downstream/preference/writeback。
- `docs/paper_a_manhattan/HRC_C6_5A_4_SCORING_EVALUATOR_HARDENING_SPEC_v1.md`：C6.5a.4 spec-only hardening contract；定义未来 L0–L5 key 与 gate 改造，不构成实现授权。
- `tests/fixtures/paper_a_manhattan/hrc_scoring_layer_compliance_v1.json` 与 `tests/test_hrc_scoring_layer_hardening_contract.py`：C6.5a.4b fixture-based contract；锁定 hard gate、L1/L2/L3/L4/L5 层序及 legacy exclusion。
- `tools/paper_a_manhattan/manhattan_constrained_hypothesis_evaluator.py` 与 `manhattan_hypothesis_portfolio.py`：C6.5a.4c 最小实现；共享 L0–L5 layer key，保持 bucket 集合与 recommendation authorization 不变。
- `tools/paper_a_manhattan/manhattan_candidate_source_interface.py`：C3.1 candidate source 最小字段合同与校验。
- `tools/paper_a_manhattan/manhattan_legacy_m1528_candidate_source.py`：C3.1 legacy wrapper；仅调用既有 M15.28 action library。
- `tools/paper_a_manhattan/manhattan_constrained_v0_candidate_source.py`：C3.3 contract-only shadow skeleton；固定输出空 candidate set，无 active runner role。
- `tools/paper_a_manhattan/run_manhattan_hypothesis_ranking_core.py`：主 runner、M15.28 source 接线、core/legacy 输出隔离。
- `tools/paper_a_manhattan/manhattan_m1528_semantic_action_library.py`：实际 candidate source 与 constrained evaluator 接入。
- `tools/paper_a_manhattan/manhattan_m1527_semantic_direct_search.py`：legacy Hooke–Jeeves 依据；不是已批准的 C7。
- `docs/paper_a_manhattan/后续方针.md`：C0–C10 目标定义。
- `docs/paper_a_manhattan/M15_LEGACY_ARTIFACT_DEPENDENCY_INVENTORY_v1.md`：legacy source/compatibility chain 仍被 core 使用的依据。
- `docs/paper_a_manhattan/MANHATTAN_HYPOTHESIS_FEEDBACK_LEDGER_SCHEMA_v1.md` 与 `tools/paper_a_manhattan/materialize_manhattan_feedback_ledger_entry.py`：C8 只记录、不训练、不写回边界。
- C3.1–C3.3、C3.4a column-x 与 C3.4b height-target shadow-only 已存在；`short_wall_preserving_local`、`primary_edge_direction_family_repair`、`floor_depth_balance` implementation，以及 C9/C10：missing / not found。C4-lite 已实现，不在 missing 清单内。

本冻结不改变 Paper A 正式实验、`P1/C1/C2/T1/V1`、routing、worker-facing、协议或 Label Studio 数据。
