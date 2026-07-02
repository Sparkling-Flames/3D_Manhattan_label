# Calibration rebuild v2 review packet

## git diff --stat
```text
.../assignment_manifest_C1_manual_draft_v2.csv     | 604 ++++++++---------
 .../assignment_manifest_C1_semi_draft_v2.csv       | 112 +--
 .../c1_launch_readiness_draft_v2.json              |   2 +-
 .../calibration_rebuild_input_manifest_v2.csv      |  26 +
 .../calibration_rebuild_review_packet_v2.md        | 749 +++++++++++++++++++++
 tests/test_calibration_rebuild_v2_drafts.py        |  83 +++
 .../build_calibration_rebuild_v2_drafts.py         | 124 +++-
 7 files changed, 1307 insertions(+), 393 deletions(-)
```

## git diff -- tools/thesis_main/registry/build_calibration_rebuild_v2_drafts.py
```diff
diff --git a/tools/thesis_main/registry/build_calibration_rebuild_v2_drafts.py b/tools/thesis_main/registry/build_calibration_rebuild_v2_drafts.py
index 4a36266..71ccf04 100644
--- a/tools/thesis_main/registry/build_calibration_rebuild_v2_drafts.py
+++ b/tools/thesis_main/registry/build_calibration_rebuild_v2_drafts.py
@@ -164,6 +164,23 @@ def _manual_review_rows(path: Path) -> dict[str, dict[str, str]]:
     return rows
 
 
+def _hard_exclude_ids(path: Path) -> set[str]:
+    if not path.exists():
+        return set()
+    in_section = False
+    ids: set[str] = set()
+    for line in path.read_text(encoding="utf-8").splitlines():
+        if line.startswith("## "):
+            in_section = "直接排除" in line
+            continue
+        if not in_section or not line.startswith("|") or "---" in line or "task" in line:
+            continue
+        cells = [c.strip() for c in line.strip("|").split("|")]
+        if cells and cells[0].isdigit():
+            ids.add(cells[0])
+    return ids
+
+
 def _final_gold(root: Path) -> dict[str, dict]:
     path = root / "analysis_results/prescreen_closeout_final_gold_v2_20260701/final_gold_records_v2_p1_closeout_corrected.jsonl"
     out: dict[str, dict] = {}
@@ -233,7 +250,7 @@ def build_inventory(root: Path) -> tuple[list[dict], dict]:
     legacy_unreviewed = _markdown_task_ids(root / "trap集/旧标注补充清单_20260702.md")
     pure_model = _markdown_task_ids(root / "trap集/纯模型问题任务记录_20260702.md")
     semi_model = {row["task_id"]: row for row in _read_csv(root / "trap集/校准semi模型问题整理_20260702.csv")}
-    hard_exclude = {"566", "615", "649", "498"}
+    hard_exclude = _hard_exclude_ids(root / "trap集/亲自复核整理与分层_20260702.md")
 
     rows: list[dict] = []
     for task in tasks:
@@ -426,6 +443,21 @@ def select_semi_from_core(core: list[dict], seed: int = SEED) -> tuple[list[dict
     return selected, {"quotas": quotas, "shortfalls": shortfalls, "semi_count": len(selected)}
 
 
+def audit_semi_source(semi: list[dict], core: list[dict], anchor: list[dict], reserve: list[dict]) -> dict:
+    semi_ids = {row["task_id"] for row in semi}
+    core_ids = {row["task_id"] for row in core}
+    anchor_ids = {row["task_id"] for row in anchor}
+    reserve_ids = {row["task_id"] for row in reserve}
+    return {
+        "source_pool_all_core": semi_ids <= core_ids,
+        "anchor_in_semi_count": len(semi_ids & anchor_ids),
+        "reserve_in_semi_count": len(semi_ids & reserve_ids),
+        "legacy_proxy_unconfirmed_count": sum(row.get("semi_family_confidence") == "legacy_proxy" for row in semi),
+        "used_for_r_u": False,
+        "used_for_rq2": True,
+    }
+
+
 def load_workers(root: Path) -> list[dict[str, str]]:
     rows = _read_csv(root / "analysis_results/prescreen_closeout_final_gold_v2_20260701/prescreen_worker_admission.csv")
     workers = [r for r in rows if _bool(r.get("eligible_for_C1"))]
@@ -437,6 +469,7 @@ def load_workers(root: Path) -> list[dict[str, str]]:
 def build_manual_assignment(anchor: list[dict], core: list[dict], workers: list[dict[str, str]]) -> tuple[list[dict], dict]:
     rows: list[dict] = []
     order_by_worker = defaultdict(int)
+    shuffled_rank = {worker["worker_id"]: idx for idx, worker in enumerate(workers)}
     for task in anchor:
         for worker in workers:
             order_by_worker[worker["worker_id"]] += 1
@@ -455,7 +488,7 @@ def build_manual_assignment(anchor: list[dict], core: list[dict], workers: list[
             })
     load = Counter()
     for idx, task in enumerate(core):
-        ranked = sorted(workers, key=lambda w: (load[w["worker_id"]], (idx + int(w["worker_id"])) % len(workers)))
+        ranked = sorted(workers, key=lambda w: (load[w["worker_id"]], (idx + shuffled_rank[w["worker_id"]]) % len(workers)))
         for worker in ranked[:5]:
             load[worker["worker_id"]] += 1
             order_by_worker[worker["worker_id"]] += 1
@@ -551,20 +584,60 @@ def build_semi_assignment(semi: list[dict], manual_rows: list[dict], workers: li
     counts = Counter(r["task_id"] for r in rows)
     semi_load = Counter(r["worker_id"] for r in rows)
     load_values = [semi_load[w["worker_id"]] for w in workers]
+    overlap_audit = audit_manual_semi_overlap(manual_rows, rows)
     audit = {
-        "passed": len(semi) == 25 and set(counts.values()) == {4} and overlap == 0 and min(load_values) >= 4 and max(load_values) <= 5,
+        "passed": len(semi) == 25 and set(counts.values()) == {4} and overlap_audit["manual_semi_same_image_overlap_count"] == 0 and min(load_values) >= 4 and max(load_values) <= 5,
         "semi_task_count": len(semi),
         "semi_k_min": min(counts.values()) if counts else 0,
         "semi_k_max": max(counts.values()) if counts else 0,
         "worker_semi_load_min": min(load_values) if load_values else 0,
         "worker_semi_load_max": max(load_values) if load_values else 0,
-        "manual_semi_same_image_overlap_count": overlap,
+        "manual_semi_same_image_overlap_count": overlap_audit["manual_semi_same_image_overlap_count"],
         "anchor_in_semi_count": 0,
         "reserve_in_semi_count": 0,
         "used_for_r_u_false_count": sum(r["used_for_r_u"] == "false" for r in rows),
         "used_for_rq2_true_count": sum(r["used_for_rq2"] == "true" for r in rows),
     }
-    return rows, {"manual_semi_same_image_overlap_count": overlap, "passed": overlap == 0}, audit
+    return rows, overlap_audit, audit
+
+
+def audit_manual_semi_overlap(manual_rows: list[dict], semi_rows: list[dict]) -> dict:
+    manual_pairs = {(row["worker_id"], row["base_task_id"]) for row in manual_rows}
+    overlap = sum((row["worker_id"], row["base_task_id"]) in manual_pairs for row in semi_rows)
+    return {"manual_semi_same_image_overlap_count": overlap, "passed": overlap == 0}
+
+
+def build_readiness_draft(
+    *,
+    deprecation: dict,
+    balance: dict,
+    manual_audit: dict,
+    semi_audit: dict,
+    overlap_audit: dict,
+    semi_quota: dict,
+    test_results: str,
+) -> dict:
+    return {
+        "passed": False,
+        "status": "draft_pending_human_review",
+        "blockers": [
+            "manual pool draft pending human approval",
+            "semi family draft pending human approval",
+            "LS import not yet materialized",
+            "active log smoke test not yet run on v2 projects",
+            "worker-facing distribution not generated",
+        ],
+        "protocol_checks": {
+            "random_c1_deprecated": deprecation["passed"],
+            "reserve_excluded_from_c1": manual_audit["reserve_assignment_count"] == 0,
+            "semi_only_from_core": semi_quota["source_pool_all_core"],
+            "readiness_for_launch": False,
+        },
+        "overlap_checks": {"prescreen_overlap_count": balance["prescreen_overlap_count"]},
+        "assignment_checks": {"manual": manual_audit, "semi": semi_audit, "manual_semi_overlap": overlap_audit},
+        "proxy_balance_warnings": balance["warnings"] + [f"semi_shortfall:{k}={v}" for k, v in semi_quota.get("shortfalls", {}).items()],
+        "test_results": test_results,
+    }
 
 
 def _import_task(row: dict, group: str, include_model_issue: bool) -> dict:
@@ -624,14 +697,9 @@ def build_all(root: Path, test_results: str = "not_run_by_script") -> dict:
     _write_json(out / "calibration_pool_proxy_balance_summary_v2.json", balance)
     semi, semi_quota = select_semi_from_core(core)
     _write_csv(out / "calibration_semi_selection_draft_v2.csv", semi, POOL_FIELDS + ["semi_family", "semi_family_confidence", "semi_selection_rank"])
-    _write_json(out / "calibration_semi_family_quota_draft_v2.json", semi_quota | {
-        "source_pool_all_core": all(r["calibration_split"] == "core" for r in semi),
-        "anchor_in_semi_count": 0,
-        "reserve_in_semi_count": 0,
-        "legacy_proxy_unconfirmed_count": sum(r["semi_family_confidence"] == "legacy_proxy" for r in semi),
-        "used_for_r_u": False,
-        "used_for_rq2": True,
-    })
+    semi_source_audit = audit_semi_source(semi, core, anchor, reserve)
+    semi_quota = semi_quota | semi_source_audit
+    _write_json(out / "calibration_semi_family_quota_draft_v2.json", semi_quota)
     _write_csv(out / "calibration_semi_source_audit_v2.csv", semi, POOL_FIELDS + ["semi_family", "semi_family_confidence", "semi_selection_rank"])
     workers = load_workers(root)
     manual_assign, manual_audit = build_manual_assignment(anchor, core, workers)
@@ -651,27 +719,15 @@ def build_all(root: Path, test_results: str = "not_run_by_script") -> dict:
         "counts": {"anchor": len(anchor), "core": len(core), "semi": len(semi), "reserve": len(reserve)},
         "reserve_import_scope": "C2_draft_only",
     })
-    readiness = {
-        "passed": False,
-        "status": "draft_pending_human_review",
-        "blockers": [
-            "manual pool draft pending human approval",
-            "semi family draft pending human approval",
-            "LS import not yet materialized",
-            "active log smoke test not yet run on v2 projects",
-            "worker-facing distribution not generated",
-        ],
-        "protocol_checks": {
-            "random_c1_deprecated": deprecation["passed"],
-            "reserve_excluded_from_c1": manual_audit["reserve_assignment_count"] == 0,
-            "semi_only_from_core": all(r["calibration_split"] == "core" for r in semi),
-            "readiness_for_launch": False,
-        },
-        "overlap_checks": {"prescreen_overlap_count": balance["prescreen_overlap_count"]},
-        "assignment_checks": {"manual": manual_audit, "semi": semi_audit, "manual_semi_overlap": overlap_audit},
-        "proxy_balance_warnings": balance["warnings"] + [f"semi_shortfall:{k}={v}" for k, v in semi_quota.get("shortfalls", {}).items()],
-        "test_results": test_results,
-    }
+    readiness = build_readiness_draft(
+        deprecation=deprecation,
+        balance=balance,
+        manual_audit=manual_audit,
+        semi_audit=semi_audit,
+        overlap_audit=overlap_audit,
+        semi_quota=semi_quota,
+        test_results=test_results,
+    )
     _write_json(out / "c1_launch_readiness_draft_v2.json", readiness)
     report = "\n".join([
         "# C1/C2 v2 rebuild draft report",
```

## git diff -- tests/test_calibration_rebuild_v2_drafts.py
```diff
diff --git a/tests/test_calibration_rebuild_v2_drafts.py b/tests/test_calibration_rebuild_v2_drafts.py
index 860346b..85de1ae 100644
--- a/tests/test_calibration_rebuild_v2_drafts.py
+++ b/tests/test_calibration_rebuild_v2_drafts.py
@@ -6,6 +6,9 @@ from pathlib import Path
 
 from tools.thesis_main.registry.build_calibration_rebuild_v2_drafts import (
     INVENTORY_FIELDS,
+    audit_manual_semi_overlap,
+    audit_semi_source,
+    build_readiness_draft,
     build_inventory,
     build_manual_assignment,
     build_semi_assignment,
@@ -142,3 +145,83 @@ def test_assignments_enforce_core_k5_semi_k4_and_no_same_image_overlap() -> None
     assert semi_audit["worker_semi_load_max"] <= 5
     assert overlap_audit["manual_semi_same_image_overlap_count"] == 0
     assert all(row["used_for_r_u"] == "false" and row["used_for_rq2"] == "true" for row in semi_rows)
+
+
+def test_core_extra_assignments_use_seeded_worker_order_not_lexical_order() -> None:
+    rows = [_candidate(i, reviewed=i <= 30) for i in range(1, 125)]
+    anchor, core, _, _ = select_manual_pools(rows)
+    workers = [{"worker_id": str(i), "watch_flag": "False"} for i in range(1, 24)]
+
+    manual_rows, manual_audit = build_manual_assignment(anchor, core, workers)
+    core_load = {}
+    for row in manual_rows:
+        if row["dataset_group"] == "Calibration_core":
+            core_load[row["worker_id"]] = core_load.get(row["worker_id"], 0) + 1
+    extra_workers = {worker_id for worker_id, count in core_load.items() if count == 17}
+    lexical_first_seven = set(sorted({worker["worker_id"] for worker in workers})[:7])
+
+    assert manual_audit["worker_core_load_min"] == 16
+    assert manual_audit["worker_core_load_max"] == 17
+    assert len(extra_workers) == 7
+    assert extra_workers != lexical_first_seven
+
+
+def test_negative_semi_source_audit_counts_anchor_and_reserve_in_semi() -> None:
+    anchor = [_candidate(1)]
+    core = [_candidate(2)]
+    reserve = [_candidate(3)]
+    semi = [anchor[0], core[0], reserve[0]]
+
+    audit = audit_semi_source(semi, core, anchor, reserve)
+
+    assert audit["source_pool_all_core"] is False
+    assert audit["anchor_in_semi_count"] == 1
+    assert audit["reserve_in_semi_count"] == 1
+
+
+def test_negative_manual_semi_same_worker_same_image_overlap_detected() -> None:
+    manual_rows = [{"worker_id": "w1", "base_task_id": "base_1"}]
+    semi_rows = [{"worker_id": "w1", "base_task_id": "base_1"}]
+
+    audit = audit_manual_semi_overlap(manual_rows, semi_rows)
+
+    assert audit["passed"] is False
+    assert audit["manual_semi_same_image_overlap_count"] == 1
+
+
+def test_negative_legacy_label_is_not_upgraded_to_confirmed_family(tmp_path: Path) -> None:
+    _write_old_json(tmp_path / "export_label/project-2-at-2026-03-25-10-52-c04c6496.json")
+    raw = tmp_path / "analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs"
+    raw.mkdir(parents=True)
+    (raw / "project-1-at-x.json").write_text("[]", encoding="utf-8")
+    gold = tmp_path / "analysis_results/prescreen_closeout_final_gold_v2_20260701/final_gold_records_v2_p1_closeout_corrected.jsonl"
+    gold.parent.mkdir(parents=True, exist_ok=True)
+    gold.write_text("", encoding="utf-8")
+    (tmp_path / "trap集").mkdir()
+    (tmp_path / "trap集/旧标注补充清单_20260702.md").write_text(
+        "| task_id | x |\n| --- | --- |\n| 460 | x |\n", encoding="utf-8"
+    )
+
+    rows, _ = build_inventory(tmp_path)
+    row = next(row for row in rows if row["task_id"] == "460")
+
+    assert row["legacy_label_status"] == "legacy_proxy"
+    assert row["expert_review_status"] == "unreviewed"
+    assert row["proxy_confidence"] == "legacy_proxy"
+    assert row["proxy_confidence"] != "confirmed"
+
+
+def test_negative_readiness_draft_never_passes_before_human_review() -> None:
+    readiness = build_readiness_draft(
+        deprecation={"passed": True},
+        balance={"prescreen_overlap_count": 0, "warnings": []},
+        manual_audit={"passed": True, "reserve_assignment_count": 0},
+        semi_audit={"passed": True},
+        overlap_audit={"passed": True, "manual_semi_same_image_overlap_count": 0},
+        semi_quota={"source_pool_all_core": True, "shortfalls": {}},
+        test_results="all local checks passed",
+    )
+
+    assert readiness["passed"] is False
+    assert readiness["status"] == "draft_pending_human_review"
+    assert "manual pool draft pending human approval" in readiness["blockers"]
```

## Input manifest

CSV: `analysis_results/calibration_rebuild_20260702/calibration_rebuild_input_manifest_v2.csv`

| path | bytes | sha256 | role |
| --- | ---: | --- | --- |
| docs/thesis_main/ROUND_BASED_EXECUTION_PROTOCOL_v1.md | 9269 | `31aba4e153ba1bab6ddc4f0a57f60f5e57a00ff2775ad379e0b0fbcdba66700c` | protocol |
| docs/thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.md | 8548 | `8170e76d02a550c1e432454fee6bc88dd0b723b724e911c38cd784a30a0f9b75` | assignment_sop |
| docs/thesis_main/C1_C2_ARTIFACT_FIELD_CONTRACT_v1.md | 8042 | `fcf56f74a98402c99a7d9c18e2a7cc7b7303a106f92228bcae885f54f8eaaa9c` | artifact_field_contract |
| docs/agent/playbooks/protocol_guard.md | 1254 | `ff2e917669610869ec73b8819edde1241661753975331073817382ee308189ac` | protocol_guard |
| docs/agent/playbooks/statistical_plan_guard.md | 1397 | `19ecc9d4cb1de3b1b4cef9d6a0bc16921888ad37b48bfbd836830e6828597cdc` | statistical_plan_guard |
| docs/agent/playbooks/label_studio_ce_guard.md | 1059 | `6407c8ab21d8e8c7bc3c121a9c917d5b6a7c14d1c9facd85960cbc8d89ffde3c` | label_studio_ce_guard |
| docs/agent/AGENT_CONTEXT_INDEX.md | 5504 | `5b0130d55684e12aa7b269d3df29992eba0eb5a9fc5e20488e755e47ca304ada` | agent_context |
| analysis_results/prescreen_closeout_final_gold_v2_20260701/prescreen_worker_admission.csv | 10638 | `8a8575d1229aab6e2cea4e49af7fab39de7aa308923c73875019bbba99b3b554` | p1_eligible_worker_pool |
| analysis_results/prescreen_closeout_final_gold_v2_20260701/final_gold_records_v2_p1_closeout_corrected.jsonl | 121490 | `82dbcb1d08754476e4f2a447b70550bd297689c2c50df9f96aeb270b37f163d6` | p1_final_gold_v2 |
| analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/project-28-at-2026-07-01-07-14-56a198ba.json | 1547456 | `a40ea344c04cc6259c5841f40a427cc82fa44258916dee672b4a7599d2cf8c69` | p1_raw_input_prescreen_overlap_source |
| analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/project-29-at-2026-06-30-09-00-e7ea6931.json | 1478893 | `63b34e8adce3790c76f41f1e77302ea926dfdcbb0bc2950f6258a8d90d8ccdd1` | p1_raw_input_prescreen_overlap_source |
| analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/project-30-at-2026-06-30-09-00-69d8051b.json | 474932 | `2f274f31c2ac9dd48128593357f1d0f4cae98dfc8fc62cf77a40e7df2641c4d7` | p1_raw_input_prescreen_overlap_source |
| analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/project-39-at-2026-06-28-05-14-65ca3316.json | 1266031 | `f79fb49ae72195c4fbea4934f17ac6235d75da513fa8fbfc11c993ad726a84ae` | p1_raw_input_prescreen_overlap_source |
| analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/project-40-at-2026-06-28-05-14-bb74a057.json | 1276775 | `1ce8a32e5708aa87c11f4e9957efebccd183b60e6d12066ceee69ce87d763305` | p1_raw_input_prescreen_overlap_source |
| analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/project-41-at-2026-06-28-05-13-8641854f.json | 453267 | `307f6e6974a836a21193af64e93e72a0a907d7193be3bff6729f386aeac12fe2` | p1_raw_input_prescreen_overlap_source |
| analysis_results/calibration_c1_prep/calibration_round_input_manifest_v1.json | 54428 | `722b394f138d473416c53ee1c3582490d02697e9558ee917287dcef98ffffd2d` | deprecated_random_c1_provenance_only |
| analysis_results/calibration_c1_prep/c1_launch_readiness_summary.json | 903 | `9bbc1397b4c7c32ddace0dbf86d2b6895888eec91f47a98b6c138721c169aef8` | deprecated_random_c1_readiness_check |
| analysis_results/calibration_c1_prep/C1作废说明_20260702.md | 1052 | `1421a940c2f533ec1d5d2232a61b148255e5c9eb5c7e0cc891b4b6fc6fb17be6` | deprecated_random_c1_note |
| export_label/project-2-at-2026-03-25-10-52-c04c6496.json | 4480511 | `3d03cec43488e2ab8b01a9016a30251805f29d0e2773f0107f8de3b2f872ca9f` | legacy_label_scope_difficulty_model_issue_proxy |
| trap集/范围难度人工分层候选_20260702.md | 13751 | `d715764a72197d9e35b8566d5b3be4489d6e9c804d1ef651844cf48966e9e211` | human_scope_difficulty_review_source |
| trap集/旧标注补充清单_20260702.md | 18635 | `9f72068d1ddf2562c6af3a30ef44ff9531b112956d7d62942e5e34c8a8393814` | legacy_unreviewed_scope_difficulty_proxy_source |
| trap集/纯模型问题任务记录_20260702.md | 4518 | `78cbef132eaec8991739b52bf7efed9677e7fe5789bbeef829c8fb66776503f5` | human_model_issue_only_source |
| trap集/亲自复核整理与分层_20260702.md | 4311 | `c8f500966dc1c9f9a028cd7f126ec3ec2ebe4a78140c8834fdc30ec2f8c2cbdd` | latest_human_review_source |
| trap集/校准semi模型问题整理_20260702.csv | 45920 | `34dda330297cf265dab6d5b041efb7bcf0217241e43306af2cdf510c81b20c72` | semi_model_issue_proxy_source |
| trap集/校准semi模型问题整理_20260702.md | 1249 | `fb2aa6ef79d9f125886bc5dae67dacc88954b75091dc5839f082bfb64e98bc9a` | semi_model_issue_summary_source |

## calibration_candidate_inventory_v2.csv

### summary
```text
rows=258 columns=35
expert_review_status={'none': 33, 'reviewed': 55, 'unreviewed': 170}
proxy_confidence={'confirmed': 26, 'legacy_proxy': 172, 'weak_proxy': 60}
```

### first 50 lines
```text
task_id,base_task_id,image_id,image_stem,source_path,image_path,source_pool,source_files,used_in_prescreen,used_in_random_c1_deprecated,has_final_gold,geometry_gold_ready,scope_gold_ready,gt_keypoint_count,gt_pair_count,corner_count_bin,old_manual_scope_raw,old_manual_difficulty_raw,old_semi_model_issue_raw,legacy_label_status,expert_review_status,expert_scope_confirmed,expert_proxy_family_primary,expert_proxy_family_secondary,model_issue_only,semi_only,hard_exclude,exclude_reason,eligible_for_manual_calibration,eligible_for_core_proxy_sampling,eligible_for_anchor_candidate,eligible_for_reserve_candidate,eligible_for_semi_candidate,proxy_confidence,notes
459,b8cTxDM8gDG_f63819c407e64c2897b703080766cb60,b8cTxDM8gDG_f63819c407e64c2897b703080766cb60,b8cTxDM8gDG_f63819c407e64c2897b703080766cb60,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/b8cTxDM8gDG_f63819c407e64c2897b703080766cb60.png,legacy_project2_full_annotation,old_label_json;校准semi模型问题整理,true,false,true,false,true,8,4,pairs_le_4,normal,reflection,acceptable,legacy_proxy,none,,模型标注质量好,模型标注质量好,false,false,false,,false,false,false,false,false,weak_proxy,
460,X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9,X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9,X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,24,12,pairs_ge_9,oos_geometry,residual,overextend_adjacent,legacy_proxy,reviewed,,跨门扩张,跨门扩张,false,false,false,,true,true,true,true,true,confirmed,过度解析-跨门扩张；更适合semi
461,rPc6DW4iMge_7316bf706e0d46368334c0c989210e09,rPc6DW4iMge_7316bf706e0d46368334c0c989210e09,rPc6DW4iMge_7316bf706e0d46368334c0c989210e09,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/rPc6DW4iMge_7316bf706e0d46368334c0c989210e09.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,trivial,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
462,UwV83HsGsw3_8e9c912f525744eeaea21083a20a1596,UwV83HsGsw3_8e9c912f525744eeaea21083a20a1596,UwV83HsGsw3_8e9c912f525744eeaea21083a20a1596,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/UwV83HsGsw3_8e9c912f525744eeaea21083a20a1596.png,legacy_project2_full_annotation,old_label_json;校准semi模型问题整理,true,false,true,true,true,8,4,pairs_le_4,normal,occlusion;seam;residual,acceptable,legacy_proxy,none,,模型标注质量好,模型标注质量好,false,false,false,,false,false,false,false,false,weak_proxy,
463,uNb9QFRL6hY_01ea3de3141a4adaa917cebb3db3c086,uNb9QFRL6hY_01ea3de3141a4adaa917cebb3db3c086,uNb9QFRL6hY_01ea3de3141a4adaa917cebb3db3c086,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_01ea3de3141a4adaa917cebb3db3c086.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,12,6,pairs_5_6,normal,trivial,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
464,Z6MFQCViBuw_451088e169fd4fe3b14d1f26b18d9a27,Z6MFQCViBuw_451088e169fd4fe3b14d1f26b18d9a27,Z6MFQCViBuw_451088e169fd4fe3b14d1f26b18d9a27,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/Z6MFQCViBuw_451088e169fd4fe3b14d1f26b18d9a27.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,8,4,pairs_le_4,normal,trivial,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
465,B6ByNegPMKs_e52609aae11f42a79f6cf50360180fd5,B6ByNegPMKs_e52609aae11f42a79f6cf50360180fd5,B6ByNegPMKs_e52609aae11f42a79f6cf50360180fd5,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/B6ByNegPMKs_e52609aae11f42a79f6cf50360180fd5.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,trivial,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
466,B6ByNegPMKs_bdc0695537064383b5cc5dbcff2a0b99,B6ByNegPMKs_bdc0695537064383b5cc5dbcff2a0b99,B6ByNegPMKs_bdc0695537064383b5cc5dbcff2a0b99,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/B6ByNegPMKs_bdc0695537064383b5cc5dbcff2a0b99.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,trivial;occlusion,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
467,X7HyMhZNoso_445ae0203f294b5c9889505576e37998,X7HyMhZNoso_445ae0203f294b5c9889505576e37998,X7HyMhZNoso_445ae0203f294b5c9889505576e37998,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/X7HyMhZNoso_445ae0203f294b5c9889505576e37998.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,occlusion,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
468,uNb9QFRL6hY_1434b965c3c147419c4ff40310633b58,uNb9QFRL6hY_1434b965c3c147419c4ff40310633b58,uNb9QFRL6hY_1434b965c3c147419c4ff40310633b58,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_1434b965c3c147419c4ff40310633b58.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,12,6,pairs_5_6,normal,occlusion,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
469,q9vSo1VnCiC_a412536ff52747d3b078f66e764cf103,q9vSo1VnCiC_a412536ff52747d3b078f66e764cf103,q9vSo1VnCiC_a412536ff52747d3b078f66e764cf103,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/q9vSo1VnCiC_a412536ff52747d3b078f66e764cf103.png,legacy_project2_full_annotation,old_label_json;校准semi模型问题整理,true,false,false,true,true,8,4,pairs_le_4,normal,occlusion;low_texture,acceptable,legacy_proxy,none,,模型标注质量好,模型标注质量好,false,false,false,,false,false,false,false,false,weak_proxy,
470,UwV83HsGsw3_7482b1a2655e4655ae4ab58749f43f65,UwV83HsGsw3_7482b1a2655e4655ae4ab58749f43f65,UwV83HsGsw3_7482b1a2655e4655ae4ab58749f43f65,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/UwV83HsGsw3_7482b1a2655e4655ae4ab58749f43f65.png,legacy_project2_full_annotation,old_label_json;范围难度人工分层候选;校准semi模型问题整理,true,false,true,true,true,20,10,pairs_ge_9,normal,seam;reflection,overextend_adjacent,legacy_proxy,reviewed,,跨门扩张,跨门扩张,false,false,false,,false,false,false,false,false,weak_proxy,
471,B6ByNegPMKs_b5dcbc0109a344a281d8ae467ccf3fc2,B6ByNegPMKs_b5dcbc0109a344a281d8ae467ccf3fc2,B6ByNegPMKs_b5dcbc0109a344a281d8ae467ccf3fc2,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/B6ByNegPMKs_b5dcbc0109a344a281d8ae467ccf3fc2.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,8,4,pairs_le_4,normal,trivial;reflection,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
472,wc2JMjhGNzB_074ac1d681e3415081b89cf582e1e995,wc2JMjhGNzB_074ac1d681e3415081b89cf582e1e995,wc2JMjhGNzB_074ac1d681e3415081b89cf582e1e995,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_074ac1d681e3415081b89cf582e1e995.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,8,4,pairs_le_4,normal,low_texture,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
473,q9vSo1VnCiC_3e5aacbc10904d4b88660a3cb91efcb9,q9vSo1VnCiC_3e5aacbc10904d4b88660a3cb91efcb9,q9vSo1VnCiC_3e5aacbc10904d4b88660a3cb91efcb9,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/q9vSo1VnCiC_3e5aacbc10904d4b88660a3cb91efcb9.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,20,10,pairs_ge_9,oos_geometry,occlusion;residual,corner_drift;topology_failure;over_parsing;fail,legacy_proxy,reviewed,,模型预标注失败/拓扑失败,模型预标注失败/拓扑失败,false,false,false,,true,true,true,true,true,confirmed,跨门扩张；适合semi但GT待修正
474,uNb9QFRL6hY_8b6f1b0b025848b482e747ab6a027b97,uNb9QFRL6hY_8b6f1b0b025848b482e747ab6a027b97,uNb9QFRL6hY_8b6f1b0b025848b482e747ab6a027b97,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_8b6f1b0b025848b482e747ab6a027b97.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;范围难度人工分层候选;旧标注补充清单;校准semi模型问题整理,false,true,true,true,true,12,6,pairs_5_6,normal;oos_insufficient,occlusion;residual;low_texture,corner_drift;corner_duplicate,legacy_proxy,reviewed,inscope,遮挡明显/玻璃干扰,角点错位/飘移,false,false,false,,true,true,true,true,true,confirmed,可作中等玻璃/遮挡样本
475,wc2JMjhGNzB_1d8917d25abb4a77a0da9583dc82c17c,wc2JMjhGNzB_1d8917d25abb4a77a0da9583dc82c17c,wc2JMjhGNzB_1d8917d25abb4a77a0da9583dc82c17c,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_1d8917d25abb4a77a0da9583dc82c17c.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;范围难度人工分层候选;校准semi模型问题整理,false,false,true,true,true,8,4,pairs_le_4,normal,occlusion;low_quality;residual;low_texture,fail;corner_drift,legacy_proxy,reviewed,inscope,遮挡明显,模型预标注失败/拓扑失败,false,false,false,,true,true,true,true,true,confirmed,可保留为高难候选，但需先确认 GT 稳定性
476,uNb9QFRL6hY_a38a8c6dced34d8bb18fb67165c099f2,uNb9QFRL6hY_a38a8c6dced34d8bb18fb67165c099f2,uNb9QFRL6hY_a38a8c6dced34d8bb18fb67165c099f2,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_a38a8c6dced34d8bb18fb67165c099f2.png,legacy_project2_full_annotation,old_label_json;校准semi模型问题整理,true,false,true,false,true,16,8,pairs_7_8,oos_split_level,residual;low_quality,corner_drift;corner_duplicate;fail,legacy_proxy,none,,模型预标注失败/拓扑失败,模型预标注失败/拓扑失败,false,false,false,,false,false,false,false,false,weak_proxy,
477,uNb9QFRL6hY_aed830f085ee4ad88ef6bed7f66f1359,uNb9QFRL6hY_aed830f085ee4ad88ef6bed7f66f1359,uNb9QFRL6hY_aed830f085ee4ad88ef6bed7f66f1359,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_aed830f085ee4ad88ef6bed7f66f1359.png,legacy_project2_full_annotation,old_label_json;校准semi模型问题整理,true,false,true,true,true,8,4,pairs_le_4,normal,occlusion;low_quality;residual;low_texture,corner_duplicate;corner_drift;fail,legacy_proxy,none,,模型预标注失败/拓扑失败,模型预标注失败/拓扑失败,false,false,false,,false,false,false,false,false,weak_proxy,
478,q9vSo1VnCiC_5deeec8cee844e6e9899bfff35b06f5d,q9vSo1VnCiC_5deeec8cee844e6e9899bfff35b06f5d,q9vSo1VnCiC_5deeec8cee844e6e9899bfff35b06f5d,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/q9vSo1VnCiC_5deeec8cee844e6e9899bfff35b06f5d.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,12,6,pairs_5_6,normal,trivial;occlusion,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
479,e9zR4mvMWw7_0ee61863ec0c4c06bac95fb886e98945,e9zR4mvMWw7_0ee61863ec0c4c06bac95fb886e98945,e9zR4mvMWw7_0ee61863ec0c4c06bac95fb886e98945,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/e9zR4mvMWw7_0ee61863ec0c4c06bac95fb886e98945.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,low_texture;seam,corner_drift;corner_duplicate;topology_failure;over_parsing;fail,legacy_proxy,unreviewed,,模型预标注失败/拓扑失败,模型预标注失败/拓扑失败,false,false,false,,true,true,false,true,true,legacy_proxy,
480,e9zR4mvMWw7_0977162f6d4e47f7b3764379ba68d8db,e9zR4mvMWw7_0977162f6d4e47f7b3764379ba68d8db,e9zR4mvMWw7_0977162f6d4e47f7b3764379ba68d8db,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/e9zR4mvMWw7_0977162f6d4e47f7b3764379ba68d8db.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,seam;reflection,corner_drift,legacy_proxy,unreviewed,,角点错位/飘移,角点错位/飘移,false,false,false,,true,true,false,true,true,legacy_proxy,
481,wc2JMjhGNzB_ec04ef10a0664e94878aa2d0f1720c2f,wc2JMjhGNzB_ec04ef10a0664e94878aa2d0f1720c2f,wc2JMjhGNzB_ec04ef10a0664e94878aa2d0f1720c2f,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_ec04ef10a0664e94878aa2d0f1720c2f.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,12,6,pairs_5_6,normal,reflection,corner_drift;over_parsing,legacy_proxy,unreviewed,,过度解析,过度解析,false,false,false,,true,true,false,true,true,legacy_proxy,
482,uNb9QFRL6hY_ba24e5a57ef34c6dbc0458ed4c1e701d,uNb9QFRL6hY_ba24e5a57ef34c6dbc0458ed4c1e701d,uNb9QFRL6hY_ba24e5a57ef34c6dbc0458ed4c1e701d,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_ba24e5a57ef34c6dbc0458ed4c1e701d.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,28,14,pairs_ge_9,oos_open_boundary,seam;residual,overextend_adjacent;corner_drift;corner_duplicate;topology_failure;over_parsing;fail,legacy_proxy,reviewed,inscope,玻璃干扰-遮挡明显/纯色墙,模型预标注失败/拓扑失败,false,false,false,,true,true,true,true,true,confirmed,可作高难玻璃+纯色墙样本
483,rPc6DW4iMge_0a84204ae666476f97095e784a772323,rPc6DW4iMge_0a84204ae666476f97095e784a772323,rPc6DW4iMge_0a84204ae666476f97095e784a772323,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/rPc6DW4iMge_0a84204ae666476f97095e784a772323.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,8,4,pairs_le_4,normal,trivial;occlusion,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
484,X7HyMhZNoso_a59d092e0c50479089a85c2b36dd6d20,X7HyMhZNoso_a59d092e0c50479089a85c2b36dd6d20,X7HyMhZNoso_a59d092e0c50479089a85c2b36dd6d20,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/X7HyMhZNoso_a59d092e0c50479089a85c2b36dd6d20.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,trivial;occlusion,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
485,wc2JMjhGNzB_6e491bc8576345bda3cdde9ab216b7be,wc2JMjhGNzB_6e491bc8576345bda3cdde9ab216b7be,wc2JMjhGNzB_6e491bc8576345bda3cdde9ab216b7be,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_6e491bc8576345bda3cdde9ab216b7be.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,trivial,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
486,wc2JMjhGNzB_ea42bf32a1984ae399c9f96d9b62b635,wc2JMjhGNzB_ea42bf32a1984ae399c9f96d9b62b635,wc2JMjhGNzB_ea42bf32a1984ae399c9f96d9b62b635,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_ea42bf32a1984ae399c9f96d9b62b635.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,8,4,pairs_le_4,normal,trivial;occlusion,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
487,uNb9QFRL6hY_85e7a14905bd44648061e3eb7f79cf13,uNb9QFRL6hY_85e7a14905bd44648061e3eb7f79cf13,uNb9QFRL6hY_85e7a14905bd44648061e3eb7f79cf13,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_85e7a14905bd44648061e3eb7f79cf13.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,trivial;occlusion,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
488,UwV83HsGsw3_a497aa9041fd41b3b5e6f3cab0849f98,UwV83HsGsw3_a497aa9041fd41b3b5e6f3cab0849f98,UwV83HsGsw3_a497aa9041fd41b3b5e6f3cab0849f98,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/UwV83HsGsw3_a497aa9041fd41b3b5e6f3cab0849f98.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,8,4,pairs_le_4,normal,trivial;occlusion,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
489,wc2JMjhGNzB_2880c0784aa0462a8070b30416752de6,wc2JMjhGNzB_2880c0784aa0462a8070b30416752de6,wc2JMjhGNzB_2880c0784aa0462a8070b30416752de6,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_2880c0784aa0462a8070b30416752de6.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,occlusion,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
490,e9zR4mvMWw7_1f8ee74dbb254dff85771776279eae94,e9zR4mvMWw7_1f8ee74dbb254dff85771776279eae94,e9zR4mvMWw7_1f8ee74dbb254dff85771776279eae94,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/e9zR4mvMWw7_1f8ee74dbb254dff85771776279eae94.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,occlusion,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
491,uNb9QFRL6hY_26b3b14f6ce047489259ab14d131122d,uNb9QFRL6hY_26b3b14f6ce047489259ab14d131122d,uNb9QFRL6hY_26b3b14f6ce047489259ab14d131122d,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_26b3b14f6ce047489259ab14d131122d.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,occlusion;trivial,corner_drift;acceptable,legacy_proxy,unreviewed,,角点错位/飘移,角点错位/飘移,false,false,false,,true,true,false,true,true,legacy_proxy,
492,e9zR4mvMWw7_1daae4b7becc43949516096170ce2a76,e9zR4mvMWw7_1daae4b7becc43949516096170ce2a76,e9zR4mvMWw7_1daae4b7becc43949516096170ce2a76,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/e9zR4mvMWw7_1daae4b7becc43949516096170ce2a76.png,legacy_project2_full_annotation,old_label_json;校准semi模型问题整理,true,false,true,true,true,8,4,pairs_le_4,normal,trivial;occlusion,corner_drift;acceptable,legacy_proxy,none,,角点错位/飘移,角点错位/飘移,false,false,false,,false,false,false,false,false,weak_proxy,
493,e9zR4mvMWw7_f7ab5b3ece274b48be57eb65bb6d4814,e9zR4mvMWw7_f7ab5b3ece274b48be57eb65bb6d4814,e9zR4mvMWw7_f7ab5b3ece274b48be57eb65bb6d4814,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/e9zR4mvMWw7_f7ab5b3ece274b48be57eb65bb6d4814.png,legacy_project2_full_annotation,old_label_json;校准semi模型问题整理,true,false,true,true,true,14,7,pairs_7_8,normal,occlusion;low_quality,overextend_adjacent;corner_duplicate,legacy_proxy,none,,跨门扩张,跨门扩张,false,false,false,,false,false,false,false,false,weak_proxy,
494,B6ByNegPMKs_c36b46ddcadf4896a2aa0abca657f33d,B6ByNegPMKs_c36b46ddcadf4896a2aa0abca657f33d,B6ByNegPMKs_c36b46ddcadf4896a2aa0abca657f33d,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/B6ByNegPMKs_c36b46ddcadf4896a2aa0abca657f33d.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,trivial,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
495,yqstnuAEVhm_66ecc07f3cda4d8ebaf84288325669f5,yqstnuAEVhm_66ecc07f3cda4d8ebaf84288325669f5,yqstnuAEVhm_66ecc07f3cda4d8ebaf84288325669f5,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/yqstnuAEVhm_66ecc07f3cda4d8ebaf84288325669f5.png,legacy_project2_full_annotation,old_label_json;校准semi模型问题整理,true,false,true,false,true,12,6,pairs_5_6,oos_split_level,occlusion;reflection,overextend_adjacent;corner_drift;over_parsing,legacy_proxy,none,,跨门扩张,跨门扩张,false,false,false,,false,false,false,false,false,weak_proxy,
496,7y3sRwLe3Va_6376b741b50a4418b3dc3fde791c3c09,7y3sRwLe3Va_6376b741b50a4418b3dc3fde791c3c09,7y3sRwLe3Va_6376b741b50a4418b3dc3fde791c3c09,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/7y3sRwLe3Va_6376b741b50a4418b3dc3fde791c3c09.png,legacy_project2_full_annotation,old_label_json;校准semi模型问题整理,true,false,true,false,true,12,6,pairs_5_6,oos_split_level,occlusion;low_texture,corner_drift,legacy_proxy,none,,角点错位/飘移,角点错位/飘移,false,false,false,,false,false,false,false,false,weak_proxy,
497,uNb9QFRL6hY_d02f87bbb0414146a7a15070110a0384,uNb9QFRL6hY_d02f87bbb0414146a7a15070110a0384,uNb9QFRL6hY_d02f87bbb0414146a7a15070110a0384,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_d02f87bbb0414146a7a15070110a0384.png,legacy_project2_full_annotation,old_label_json;校准semi模型问题整理,true,false,true,true,true,8,4,pairs_le_4,normal,occlusion,corner_drift,legacy_proxy,none,,角点错位/飘移,角点错位/飘移,false,false,false,,false,false,false,false,false,weak_proxy,
498,b8cTxDM8gDG_d38c4ae95f5b4640a2696b923b80d1f4,b8cTxDM8gDG_d38c4ae95f5b4640a2696b923b80d1f4,b8cTxDM8gDG_d38c4ae95f5b4640a2696b923b80d1f4,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/b8cTxDM8gDG_d38c4ae95f5b4640a2696b923b80d1f4.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,14,7,pairs_7_8,oos_split_level;normal,occlusion;low_texture,overextend_adjacent;corner_drift;corner_duplicate;over_parsing,legacy_proxy,reviewed,,跨门扩张,跨门扩张,false,false,true,hard_exclude_from_human_review,false,false,false,false,false,confirmed,
499,q9vSo1VnCiC_1cd414875b9b4311bc6a179d91e6270d,q9vSo1VnCiC_1cd414875b9b4311bc6a179d91e6270d,q9vSo1VnCiC_1cd414875b9b4311bc6a179d91e6270d,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/q9vSo1VnCiC_1cd414875b9b4311bc6a179d91e6270d.png,legacy_project2_full_annotation,old_label_json;范围难度人工分层候选;旧标注补充清单;校准semi模型问题整理,false,true,true,true,true,10,5,pairs_5_6,normal,occlusion;low_texture,overextend_adjacent;corner_duplicate;corner_drift,legacy_proxy,reviewed,,跨门扩张,跨门扩张,false,false,false,,true,true,true,true,true,legacy_proxy,
500,Z6MFQCViBuw_22fff6c74efb476592569c18718feb41,Z6MFQCViBuw_22fff6c74efb476592569c18718feb41,Z6MFQCViBuw_22fff6c74efb476592569c18718feb41,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/Z6MFQCViBuw_22fff6c74efb476592569c18718feb41.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,10,5,pairs_5_6,normal;oos_geometry,low_quality;occlusion;seam;residual,overextend_adjacent;corner_duplicate;corner_drift,legacy_proxy,unreviewed,,跨门扩张,跨门扩张,false,false,false,,true,true,false,true,true,legacy_proxy,
501,X7HyMhZNoso_28ada927582d4d6ea7cf44cabf31527a,X7HyMhZNoso_28ada927582d4d6ea7cf44cabf31527a,X7HyMhZNoso_28ada927582d4d6ea7cf44cabf31527a,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/X7HyMhZNoso_28ada927582d4d6ea7cf44cabf31527a.png,legacy_project2_full_annotation,old_label_json;校准semi模型问题整理,true,false,true,true,true,12,6,pairs_5_6,normal;oos_geometry,low_texture,overextend_adjacent,legacy_proxy,none,,跨门扩张,跨门扩张,false,false,false,,false,false,false,false,false,weak_proxy,
502,uNb9QFRL6hY_dcb326d4bb9b4a5f8d7e565ec32bce8e,uNb9QFRL6hY_dcb326d4bb9b4a5f8d7e565ec32bce8e,uNb9QFRL6hY_dcb326d4bb9b4a5f8d7e565ec32bce8e,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_dcb326d4bb9b4a5f8d7e565ec32bce8e.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,occlusion;reflection,corner_drift,legacy_proxy,unreviewed,,角点错位/飘移,角点错位/飘移,false,false,false,,true,true,false,true,true,legacy_proxy,
503,7y3sRwLe3Va_112edb40f34e470da3a5b04599e71211,7y3sRwLe3Va_112edb40f34e470da3a5b04599e71211,7y3sRwLe3Va_112edb40f34e470da3a5b04599e71211,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/7y3sRwLe3Va_112edb40f34e470da3a5b04599e71211.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,occlusion;residual;low_texture,corner_drift,legacy_proxy,unreviewed,,角点错位/飘移,角点错位/飘移,false,false,false,,true,true,false,true,true,legacy_proxy,
504,q9vSo1VnCiC_9ba6cd412cb04c5c9beb15ef9e6d22c5,q9vSo1VnCiC_9ba6cd412cb04c5c9beb15ef9e6d22c5,q9vSo1VnCiC_9ba6cd412cb04c5c9beb15ef9e6d22c5,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/q9vSo1VnCiC_9ba6cd412cb04c5c9beb15ef9e6d22c5.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,8,4,pairs_le_4,normal,occlusion,corner_drift,legacy_proxy,unreviewed,,角点错位/飘移,角点错位/飘移,false,false,false,,true,true,false,true,true,legacy_proxy,
505,B6ByNegPMKs_48ee619d38b142f88914e7e2582bc1d8,B6ByNegPMKs_48ee619d38b142f88914e7e2582bc1d8,B6ByNegPMKs_48ee619d38b142f88914e7e2582bc1d8,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/B6ByNegPMKs_48ee619d38b142f88914e7e2582bc1d8.png,legacy_project2_full_annotation,old_label_json;校准semi模型问题整理,true,false,true,true,true,12,6,pairs_5_6,normal,occlusion;low_texture,corner_duplicate;corner_mismatch;corner_drift,legacy_proxy,none,,过度解析,过度解析,false,false,false,,false,false,false,false,false,weak_proxy,
506,B6ByNegPMKs_3ed1f9b2f3c341d68c6d42895f56f7f9,B6ByNegPMKs_3ed1f9b2f3c341d68c6d42895f56f7f9,B6ByNegPMKs_3ed1f9b2f3c341d68c6d42895f56f7f9,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/B6ByNegPMKs_3ed1f9b2f3c341d68c6d42895f56f7f9.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,occlusion,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
507,wc2JMjhGNzB_c7e4c175f9b347cf9256fa7e291f26d9,wc2JMjhGNzB_c7e4c175f9b347cf9256fa7e291f26d9,wc2JMjhGNzB_c7e4c175f9b347cf9256fa7e291f26d9,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_c7e4c175f9b347cf9256fa7e291f26d9.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,8,4,pairs_le_4,normal,occlusion,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,
```

## calibration_manual_pool_draft_v2.csv

### summary
```text
rows=100 columns=39
calibration_split={'anchor': 12, 'core': 75, 'reserve': 13}
expert_review_status={'reviewed': 23, 'unreviewed': 77}
proxy_confidence={'confirmed': 21, 'legacy_proxy': 79}
```

### first 50 lines
```text
task_id,base_task_id,image_id,image_stem,source_path,image_path,source_pool,source_files,used_in_prescreen,used_in_random_c1_deprecated,has_final_gold,geometry_gold_ready,scope_gold_ready,gt_keypoint_count,gt_pair_count,corner_count_bin,old_manual_scope_raw,old_manual_difficulty_raw,old_semi_model_issue_raw,legacy_label_status,expert_review_status,expert_scope_confirmed,expert_proxy_family_primary,expert_proxy_family_secondary,model_issue_only,semi_only,hard_exclude,exclude_reason,eligible_for_manual_calibration,eligible_for_core_proxy_sampling,eligible_for_anchor_candidate,eligible_for_reserve_candidate,eligible_for_semi_candidate,proxy_confidence,notes,calibration_split,selection_rank,selection_reason,used_for_r_u
558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;范围难度人工分层候选;校准semi模型问题整理,false,true,false,true,true,8,4,pairs_le_4,normal,occlusion;reflection,acceptable,legacy_proxy,reviewed,inscope,遮挡明显-纯色墙,模型标注质量好,false,false,false,,true,true,true,true,true,confirmed,可作低难遮挡+纯色墙样本,anchor,1,draft_proxy_balanced,true
561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;范围难度人工分层候选;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,occlusion;reflection,acceptable,legacy_proxy,reviewed,inscope,遮挡明显/玻璃干扰,模型标注质量好,false,false,false,,true,true,true,true,true,confirmed,可作低难玻璃/遮挡样本,anchor,2,draft_proxy_balanced,true
672,uNb9QFRL6hY_6c4fa6dfddc1499db228854454bfc61d,uNb9QFRL6hY_6c4fa6dfddc1499db228854454bfc61d,uNb9QFRL6hY_6c4fa6dfddc1499db228854454bfc61d,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_6c4fa6dfddc1499db228854454bfc61d.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;范围难度人工分层候选;校准semi模型问题整理,false,false,false,true,true,12,6,pairs_5_6,normal,trivial,corner_duplicate,legacy_proxy,reviewed,oos 边界不可判断,拉伸明显,角点重复,false,false,false,,true,true,true,true,true,confirmed,可作 OOS 边界候选,anchor,3,draft_proxy_balanced,false_scope_gate_audit
705,X7HyMhZNoso_2b16acff0dc042a1a75816a1fbd0a302,X7HyMhZNoso_2b16acff0dc042a1a75816a1fbd0a302,X7HyMhZNoso_2b16acff0dc042a1a75816a1fbd0a302,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/X7HyMhZNoso_2b16acff0dc042a1a75816a1fbd0a302.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,12,6,pairs_5_6,oos_open_boundary,occlusion,over_parsing,legacy_proxy,reviewed,oos 边界不可判定,拉伸明显/遮挡明显,过度解析,false,false,false,,true,true,true,true,true,confirmed,可作典型 OOS 边界候选,anchor,4,draft_proxy_balanced,false_scope_gate_audit
499,q9vSo1VnCiC_1cd414875b9b4311bc6a179d91e6270d,q9vSo1VnCiC_1cd414875b9b4311bc6a179d91e6270d,q9vSo1VnCiC_1cd414875b9b4311bc6a179d91e6270d,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/q9vSo1VnCiC_1cd414875b9b4311bc6a179d91e6270d.png,legacy_project2_full_annotation,old_label_json;范围难度人工分层候选;旧标注补充清单;校准semi模型问题整理,false,true,true,true,true,10,5,pairs_5_6,normal,occlusion;low_texture,overextend_adjacent;corner_duplicate;corner_drift,legacy_proxy,reviewed,,跨门扩张,跨门扩张,false,false,false,,true,true,true,true,true,legacy_proxy,,anchor,5,draft_proxy_balanced,true
716,B6ByNegPMKs_7018ca302c584d0d85024187f3568460,B6ByNegPMKs_7018ca302c584d0d85024187f3568460,B6ByNegPMKs_7018ca302c584d0d85024187f3568460,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/B6ByNegPMKs_7018ca302c584d0d85024187f3568460.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;范围难度人工分层候选;校准semi模型问题整理,false,false,false,true,true,12,6,pairs_5_6,normal,occlusion,over_parsing,legacy_proxy,reviewed,inscope,遮挡明显,过度解析,false,false,false,,true,true,true,true,true,confirmed,可作偏简单遮挡样本,anchor,6,draft_proxy_balanced,true
474,uNb9QFRL6hY_8b6f1b0b025848b482e747ab6a027b97,uNb9QFRL6hY_8b6f1b0b025848b482e747ab6a027b97,uNb9QFRL6hY_8b6f1b0b025848b482e747ab6a027b97,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_8b6f1b0b025848b482e747ab6a027b97.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;范围难度人工分层候选;旧标注补充清单;校准semi模型问题整理,false,true,true,true,true,12,6,pairs_5_6,normal;oos_insufficient,occlusion;residual;low_texture,corner_drift;corner_duplicate,legacy_proxy,reviewed,inscope,遮挡明显/玻璃干扰,角点错位/飘移,false,false,false,,true,true,true,true,true,confirmed,可作中等玻璃/遮挡样本,anchor,7,draft_proxy_balanced,true
695,7y3sRwLe3Va_9e4c92fd7eb74504baecf55a3264716e,7y3sRwLe3Va_9e4c92fd7eb74504baecf55a3264716e,7y3sRwLe3Va_9e4c92fd7eb74504baecf55a3264716e,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/7y3sRwLe3Va_9e4c92fd7eb74504baecf55a3264716e.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,12,6,pairs_5_6,oos_split_level,low_texture,acceptable,legacy_proxy,reviewed,oos 错层多平面,错层多平面,模型标注质量好,false,false,false,,true,true,true,true,true,confirmed,可作 OOS 错层/多平面候选,anchor,8,draft_proxy_balanced,false_scope_gate_audit
547,yqstnuAEVhm_26b2e92ccd314a2da1a4fc8dfc6e6f56,yqstnuAEVhm_26b2e92ccd314a2da1a4fc8dfc6e6f56,yqstnuAEVhm_26b2e92ccd314a2da1a4fc8dfc6e6f56,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/yqstnuAEVhm_26b2e92ccd314a2da1a4fc8dfc6e6f56.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,16,8,pairs_7_8,oos_split_level,occlusion;reflection;residual,corner_duplicate;topology_failure;over_parsing;fail,legacy_proxy,reviewed,inscope,拉伸明显-玻璃干扰,模型预标注失败/拓扑失败,false,false,false,,true,true,true,true,true,confirmed,可作拉伸+scope 歧义候选,anchor,9,draft_proxy_balanced,false_scope_gate_audit
518,uNb9QFRL6hY_9f199750b00c4f5484a546d79e06a0f8,uNb9QFRL6hY_9f199750b00c4f5484a546d79e06a0f8,uNb9QFRL6hY_9f199750b00c4f5484a546d79e06a0f8,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_9f199750b00c4f5484a546d79e06a0f8.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,16,8,pairs_7_8,oos_geometry,seam;reflection;residual,overextend_adjacent;corner_drift;corner_duplicate,legacy_proxy,reviewed,inscope,遮挡明显-玻璃干扰,跨门扩张,false,false,false,,true,true,true,true,true,confirmed,可作高难遮挡+玻璃样本,anchor,10,draft_proxy_balanced,false_scope_gate_audit
698,7y3sRwLe3Va_b564162b2c7d4033bfe6ef3dfb959c9e,7y3sRwLe3Va_b564162b2c7d4033bfe6ef3dfb959c9e,7y3sRwLe3Va_b564162b2c7d4033bfe6ef3dfb959c9e,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/7y3sRwLe3Va_b564162b2c7d4033bfe6ef3dfb959c9e.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,16,8,pairs_7_8,oos_split_level,low_texture,acceptable,legacy_proxy,reviewed,oos 错层多平面,错层多平面,模型标注质量好,false,false,false,,true,true,true,true,true,confirmed,可作 OOS 错层/多平面候选,anchor,11,draft_proxy_balanced,false_scope_gate_audit
473,q9vSo1VnCiC_3e5aacbc10904d4b88660a3cb91efcb9,q9vSo1VnCiC_3e5aacbc10904d4b88660a3cb91efcb9,q9vSo1VnCiC_3e5aacbc10904d4b88660a3cb91efcb9,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/q9vSo1VnCiC_3e5aacbc10904d4b88660a3cb91efcb9.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,20,10,pairs_ge_9,oos_geometry,occlusion;residual,corner_drift;topology_failure;over_parsing;fail,legacy_proxy,reviewed,,模型预标注失败/拓扑失败,模型预标注失败/拓扑失败,false,false,false,,true,true,true,true,true,confirmed,跨门扩张；适合semi但GT待修正,anchor,12,draft_proxy_balanced,false_scope_gate_audit
582,7y3sRwLe3Va_99b1210b63c94f9184a9f06032a2ea4a,7y3sRwLe3Va_99b1210b63c94f9184a9f06032a2ea4a,7y3sRwLe3Va_99b1210b63c94f9184a9f06032a2ea4a,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/7y3sRwLe3Va_99b1210b63c94f9184a9f06032a2ea4a.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,12,6,pairs_5_6,normal,occlusion;low_texture,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,,core,1,draft_proxy_balanced,true
596,wc2JMjhGNzB_55b45b0f19c2460bbcd1fb1c86c6610d,wc2JMjhGNzB_55b45b0f19c2460bbcd1fb1c86c6610d,wc2JMjhGNzB_55b45b0f19c2460bbcd1fb1c86c6610d,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_55b45b0f19c2460bbcd1fb1c86c6610d.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,10,5,pairs_5_6,normal,trivial,corner_duplicate,legacy_proxy,unreviewed,,角点重复,角点重复,false,false,false,,true,true,false,true,true,legacy_proxy,,core,2,draft_proxy_balanced,true
702,wc2JMjhGNzB_5b147d7f689a410baca131f29c8a9515,wc2JMjhGNzB_5b147d7f689a410baca131f29c8a9515,wc2JMjhGNzB_5b147d7f689a410baca131f29c8a9515,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_5b147d7f689a410baca131f29c8a9515.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,12,6,pairs_5_6,normal,occlusion,corner_drift,legacy_proxy,unreviewed,,角点错位/飘移,角点错位/飘移,false,false,false,,true,true,false,true,true,legacy_proxy,,core,3,draft_proxy_balanced,true
525,UwV83HsGsw3_b979526475874ad68ae33f02d407a1fc,UwV83HsGsw3_b979526475874ad68ae33f02d407a1fc,UwV83HsGsw3_b979526475874ad68ae33f02d407a1fc,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/UwV83HsGsw3_b979526475874ad68ae33f02d407a1fc.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,12,6,pairs_5_6,normal,occlusion;reflection,overextend_adjacent,legacy_proxy,unreviewed,,跨门扩张,跨门扩张,false,false,false,,true,true,false,true,true,legacy_proxy,,core,4,draft_proxy_balanced,true
540,uNb9QFRL6hY_33dd9892d10e474ead8f7ad38a8da562,uNb9QFRL6hY_33dd9892d10e474ead8f7ad38a8da562,uNb9QFRL6hY_33dd9892d10e474ead8f7ad38a8da562,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_33dd9892d10e474ead8f7ad38a8da562.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,12,6,pairs_5_6,normal,occlusion,over_parsing,legacy_proxy,unreviewed,,过度解析,过度解析,false,false,false,,true,true,false,true,true,legacy_proxy,,core,5,draft_proxy_balanced,true
683,wc2JMjhGNzB_dda6efcba51c40de8552408953719515,wc2JMjhGNzB_dda6efcba51c40de8552408953719515,wc2JMjhGNzB_dda6efcba51c40de8552408953719515,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_dda6efcba51c40de8552408953719515.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;范围难度人工分层候选;校准semi模型问题整理,false,true,true,true,true,12,6,pairs_5_6,normal,occlusion,corner_duplicate;over_parsing,legacy_proxy,reviewed,inscope,遮挡明显,过度解析,false,false,false,,true,true,true,true,true,confirmed,可作中等遮挡样本,core,6,draft_proxy_balanced,true
621,yqstnuAEVhm_9de98503fd994452b627cdcc7a7d47b2,yqstnuAEVhm_9de98503fd994452b627cdcc7a7d47b2,yqstnuAEVhm_9de98503fd994452b627cdcc7a7d47b2,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/yqstnuAEVhm_9de98503fd994452b627cdcc7a7d47b2.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;范围难度人工分层候选;校准semi模型问题整理,false,false,false,true,true,10,5,pairs_5_6,normal,occlusion;seam,corner_drift;over_parsing,legacy_proxy,reviewed,inscope,遮挡明显-玻璃干扰,过度解析,false,false,false,,true,true,true,true,true,confirmed,可作中高难遮挡+玻璃样本,core,7,draft_proxy_balanced,true
650,yqstnuAEVhm_fc84c67a0ffd49cf8ffdc32df703bc86,yqstnuAEVhm_fc84c67a0ffd49cf8ffdc32df703bc86,yqstnuAEVhm_fc84c67a0ffd49cf8ffdc32df703bc86,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/yqstnuAEVhm_fc84c67a0ffd49cf8ffdc32df703bc86.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,16,8,pairs_7_8,normal,occlusion,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,,core,8,draft_proxy_balanced,true
587,7y3sRwLe3Va_a775c7668ca9419daaf506e76851821e,7y3sRwLe3Va_a775c7668ca9419daaf506e76851821e,7y3sRwLe3Va_a775c7668ca9419daaf506e76851821e,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/7y3sRwLe3Va_a775c7668ca9419daaf506e76851821e.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,16,8,pairs_7_8,normal,low_texture;seam,overextend_adjacent;corner_drift;corner_duplicate;topology_failure,legacy_proxy,unreviewed,,模型预标注失败/拓扑失败,模型预标注失败/拓扑失败,false,false,false,,true,true,false,true,true,legacy_proxy,,core,9,draft_proxy_balanced,true
595,q9vSo1VnCiC_c4b0b6a41c2a4db3927f5fa9cafb6345,q9vSo1VnCiC_c4b0b6a41c2a4db3927f5fa9cafb6345,q9vSo1VnCiC_c4b0b6a41c2a4db3927f5fa9cafb6345,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/q9vSo1VnCiC_c4b0b6a41c2a4db3927f5fa9cafb6345.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,14,7,pairs_7_8,normal,occlusion;low_texture,corner_drift;corner_duplicate,legacy_proxy,unreviewed,,角点错位/飘移,角点错位/飘移,false,false,false,,true,true,false,true,true,legacy_proxy,,core,10,draft_proxy_balanced,true
511,7y3sRwLe3Va_ad77d6eeca5b492b8fe3317177f4f03f,7y3sRwLe3Va_ad77d6eeca5b492b8fe3317177f4f03f,7y3sRwLe3Va_ad77d6eeca5b492b8fe3317177f4f03f,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/7y3sRwLe3Va_ad77d6eeca5b492b8fe3317177f4f03f.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,16,8,pairs_7_8,oos_geometry,occlusion;low_texture,overextend_adjacent;corner_drift;corner_duplicate,legacy_proxy,unreviewed,,跨门扩张,跨门扩张,false,false,false,,true,true,false,true,true,legacy_proxy,,core,11,draft_proxy_balanced,false_scope_gate_audit
627,uNb9QFRL6hY_6a500a9a43a340eb817c58bb084327fe,uNb9QFRL6hY_6a500a9a43a340eb817c58bb084327fe,uNb9QFRL6hY_6a500a9a43a340eb817c58bb084327fe,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_6a500a9a43a340eb817c58bb084327fe.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,16,8,pairs_7_8,normal,low_texture,corner_drift;over_parsing,legacy_proxy,unreviewed,,过度解析,过度解析,false,false,false,,true,true,false,true,true,legacy_proxy,,core,12,draft_proxy_balanced,true
626,uNb9QFRL6hY_5948424345f541b9a570b48f1cfcf622,uNb9QFRL6hY_5948424345f541b9a570b48f1cfcf622,uNb9QFRL6hY_5948424345f541b9a570b48f1cfcf622,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_5948424345f541b9a570b48f1cfcf622.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;范围难度人工分层候选;校准semi模型问题整理,false,false,false,true,true,14,7,pairs_7_8,normal,occlusion;low_texture,corner_drift;corner_duplicate;over_parsing,legacy_proxy,reviewed,inscope,遮挡明显/遮罩干扰-玻璃干扰,过度解析,false,false,false,,true,true,true,true,true,confirmed,可作高难遮挡/遮罩/玻璃样本,core,13,draft_proxy_balanced,true
620,rPc6DW4iMge_0dfe61800cc540db8e25c1738bc4b8ff,rPc6DW4iMge_0dfe61800cc540db8e25c1738bc4b8ff,rPc6DW4iMge_0dfe61800cc540db8e25c1738bc4b8ff,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/rPc6DW4iMge_0dfe61800cc540db8e25c1738bc4b8ff.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,20,10,pairs_ge_9,normal,occlusion;reflection,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,,core,14,draft_proxy_balanced,true
482,uNb9QFRL6hY_ba24e5a57ef34c6dbc0458ed4c1e701d,uNb9QFRL6hY_ba24e5a57ef34c6dbc0458ed4c1e701d,uNb9QFRL6hY_ba24e5a57ef34c6dbc0458ed4c1e701d,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_ba24e5a57ef34c6dbc0458ed4c1e701d.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,28,14,pairs_ge_9,oos_open_boundary,seam;residual,overextend_adjacent;corner_drift;corner_duplicate;topology_failure;over_parsing;fail,legacy_proxy,reviewed,inscope,玻璃干扰-遮挡明显/纯色墙,模型预标注失败/拓扑失败,false,false,false,,true,true,true,true,true,confirmed,可作高难玻璃+纯色墙样本,core,15,draft_proxy_balanced,false_scope_gate_audit
542,wc2JMjhGNzB_4884da3227464ab5b82f631ff22205bd,wc2JMjhGNzB_4884da3227464ab5b82f631ff22205bd,wc2JMjhGNzB_4884da3227464ab5b82f631ff22205bd,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_4884da3227464ab5b82f631ff22205bd.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,24,12,pairs_ge_9,normal,occlusion;reflection,overextend_adjacent;over_parsing,legacy_proxy,unreviewed,,跨门扩张,跨门扩张,false,false,false,,true,true,false,true,true,legacy_proxy,,core,16,draft_proxy_balanced,true
652,yqstnuAEVhm_c93bf298b1cb41a1b368a6ce8bcff53d,yqstnuAEVhm_c93bf298b1cb41a1b368a6ce8bcff53d,yqstnuAEVhm_c93bf298b1cb41a1b368a6ce8bcff53d,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/yqstnuAEVhm_c93bf298b1cb41a1b368a6ce8bcff53d.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,36,18,pairs_ge_9,normal,occlusion,corner_drift;corner_duplicate;over_parsing,legacy_proxy,unreviewed,,过度解析,过度解析,false,false,false,,true,true,false,true,true,legacy_proxy,,core,17,draft_proxy_balanced,true
516,B6ByNegPMKs_8c414a8052c844b4bcd5dc3fadde7f8c,B6ByNegPMKs_8c414a8052c844b4bcd5dc3fadde7f8c,B6ByNegPMKs_8c414a8052c844b4bcd5dc3fadde7f8c,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/B6ByNegPMKs_8c414a8052c844b4bcd5dc3fadde7f8c.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,reflection,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,,core,18,draft_proxy_balanced,true
479,e9zR4mvMWw7_0ee61863ec0c4c06bac95fb886e98945,e9zR4mvMWw7_0ee61863ec0c4c06bac95fb886e98945,e9zR4mvMWw7_0ee61863ec0c4c06bac95fb886e98945,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/e9zR4mvMWw7_0ee61863ec0c4c06bac95fb886e98945.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,low_texture;seam,corner_drift;corner_duplicate;topology_failure;over_parsing;fail,legacy_proxy,unreviewed,,模型预标注失败/拓扑失败,模型预标注失败/拓扑失败,false,false,false,,true,true,false,true,true,legacy_proxy,,core,19,draft_proxy_balanced,true
580,wc2JMjhGNzB_b41b10699d614f24851b56a9a0e743c6,wc2JMjhGNzB_b41b10699d614f24851b56a9a0e743c6,wc2JMjhGNzB_b41b10699d614f24851b56a9a0e743c6,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_b41b10699d614f24851b56a9a0e743c6.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;范围难度人工分层候选;校准semi模型问题整理,false,false,true,true,true,8,4,pairs_le_4,normal,occlusion,overextend_adjacent;corner_duplicate;over_parsing,legacy_proxy,reviewed,inscope,玻璃干扰/遮挡明显,跨门扩张,false,false,false,,true,true,true,true,true,confirmed,可作高难玻璃/遮挡样本,core,20,draft_proxy_balanced,true
563,rPc6DW4iMge_0012f6dcce9645778ac459e189cf0db3,rPc6DW4iMge_0012f6dcce9645778ac459e189cf0db3,rPc6DW4iMge_0012f6dcce9645778ac459e189cf0db3,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/rPc6DW4iMge_0012f6dcce9645778ac459e189cf0db3.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;范围难度人工分层候选;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,occlusion;reflection,acceptable,legacy_proxy,reviewed,inscope,简单,模型标注质量好,false,false,false,,true,true,true,true,true,confirmed,可作简单基线样本,core,21,draft_proxy_balanced,true
480,e9zR4mvMWw7_0977162f6d4e47f7b3764379ba68d8db,e9zR4mvMWw7_0977162f6d4e47f7b3764379ba68d8db,e9zR4mvMWw7_0977162f6d4e47f7b3764379ba68d8db,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/e9zR4mvMWw7_0977162f6d4e47f7b3764379ba68d8db.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,seam;reflection,corner_drift,legacy_proxy,unreviewed,,角点错位/飘移,角点错位/飘移,false,false,false,,true,true,false,true,true,legacy_proxy,,core,22,draft_proxy_balanced,true
594,yqstnuAEVhm_2f8c1f8ea7364f67b1c5fe2be2750257,yqstnuAEVhm_2f8c1f8ea7364f67b1c5fe2be2750257,yqstnuAEVhm_2f8c1f8ea7364f67b1c5fe2be2750257,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/yqstnuAEVhm_2f8c1f8ea7364f67b1c5fe2be2750257.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,trivial,corner_duplicate;over_parsing,legacy_proxy,unreviewed,,过度解析,过度解析,false,false,false,,true,true,false,true,true,legacy_proxy,,core,23,draft_proxy_balanced,true
475,wc2JMjhGNzB_1d8917d25abb4a77a0da9583dc82c17c,wc2JMjhGNzB_1d8917d25abb4a77a0da9583dc82c17c,wc2JMjhGNzB_1d8917d25abb4a77a0da9583dc82c17c,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_1d8917d25abb4a77a0da9583dc82c17c.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;范围难度人工分层候选;校准semi模型问题整理,false,false,true,true,true,8,4,pairs_le_4,normal,occlusion;low_quality;residual;low_texture,fail;corner_drift,legacy_proxy,reviewed,inscope,遮挡明显,模型预标注失败/拓扑失败,false,false,false,,true,true,true,true,true,confirmed,可保留为高难候选，但需先确认 GT 稳定性,core,24,draft_proxy_balanced,true
468,uNb9QFRL6hY_1434b965c3c147419c4ff40310633b58,uNb9QFRL6hY_1434b965c3c147419c4ff40310633b58,uNb9QFRL6hY_1434b965c3c147419c4ff40310633b58,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_1434b965c3c147419c4ff40310633b58.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,12,6,pairs_5_6,normal,occlusion,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,,core,25,draft_proxy_balanced,true
700,wc2JMjhGNzB_9087f0358178420a8b9ac7b17a8919c7,wc2JMjhGNzB_9087f0358178420a8b9ac7b17a8919c7,wc2JMjhGNzB_9087f0358178420a8b9ac7b17a8919c7,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_9087f0358178420a8b9ac7b17a8919c7.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,12,6,pairs_5_6,normal,low_texture,corner_duplicate,legacy_proxy,unreviewed,,角点重复,角点重复,false,false,false,,true,true,false,true,true,legacy_proxy,,core,26,draft_proxy_balanced,true
659,uNb9QFRL6hY_3450b3accb584493bf13be8e9554dbea,uNb9QFRL6hY_3450b3accb584493bf13be8e9554dbea,uNb9QFRL6hY_3450b3accb584493bf13be8e9554dbea,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_3450b3accb584493bf13be8e9554dbea.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,12,6,pairs_5_6,normal,occlusion;low_texture,corner_drift,legacy_proxy,unreviewed,,角点错位/飘移,角点错位/飘移,false,false,false,,true,true,false,true,true,legacy_proxy,,core,27,draft_proxy_balanced,true
500,Z6MFQCViBuw_22fff6c74efb476592569c18718feb41,Z6MFQCViBuw_22fff6c74efb476592569c18718feb41,Z6MFQCViBuw_22fff6c74efb476592569c18718feb41,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/Z6MFQCViBuw_22fff6c74efb476592569c18718feb41.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,10,5,pairs_5_6,normal;oos_geometry,low_quality;occlusion;seam;residual,overextend_adjacent;corner_duplicate;corner_drift,legacy_proxy,unreviewed,,跨门扩张,跨门扩张,false,false,false,,true,true,false,true,true,legacy_proxy,,core,28,draft_proxy_balanced,true
528,yqstnuAEVhm_08e2145b15fc4d2497c084af41dc7089,yqstnuAEVhm_08e2145b15fc4d2497c084af41dc7089,yqstnuAEVhm_08e2145b15fc4d2497c084af41dc7089,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/yqstnuAEVhm_08e2145b15fc4d2497c084af41dc7089.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,12,6,pairs_5_6,normal,reflection,over_parsing,legacy_proxy,unreviewed,,过度解析,过度解析,false,false,false,,true,true,false,true,true,legacy_proxy,,core,29,draft_proxy_balanced,true
648,uNb9QFRL6hY_e24473d2b8a24568b89c1c4c2a4a9bf1,uNb9QFRL6hY_e24473d2b8a24568b89c1c4c2a4a9bf1,uNb9QFRL6hY_e24473d2b8a24568b89c1c4c2a4a9bf1,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_e24473d2b8a24568b89c1c4c2a4a9bf1.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,16,8,pairs_7_8,normal,occlusion,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,,core,30,draft_proxy_balanced,true
519,q9vSo1VnCiC_3e7f67e8969f434b9a4aec0c68668b20,q9vSo1VnCiC_3e7f67e8969f434b9a4aec0c68668b20,q9vSo1VnCiC_3e7f67e8969f434b9a4aec0c68668b20,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/q9vSo1VnCiC_3e7f67e8969f434b9a4aec0c68668b20.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,16,8,pairs_7_8,oos_geometry,occlusion;reflection,overextend_adjacent;corner_drift;over_parsing;fail,legacy_proxy,unreviewed,,模型预标注失败/拓扑失败,模型预标注失败/拓扑失败,false,false,false,,true,true,false,true,true,legacy_proxy,,core,31,draft_proxy_balanced,false_scope_gate_audit
699,yqstnuAEVhm_30f3ce4575234a7ba5ff97797f059ae1,yqstnuAEVhm_30f3ce4575234a7ba5ff97797f059ae1,yqstnuAEVhm_30f3ce4575234a7ba5ff97797f059ae1,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/yqstnuAEVhm_30f3ce4575234a7ba5ff97797f059ae1.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,16,8,pairs_7_8,normal,seam,corner_drift,legacy_proxy,unreviewed,,角点错位/飘移,角点错位/飘移,false,false,false,,true,true,false,true,true,legacy_proxy,,core,32,draft_proxy_balanced,true
604,b8cTxDM8gDG_f3748786c3704532abb2358581488f3f,b8cTxDM8gDG_f3748786c3704532abb2358581488f3f,b8cTxDM8gDG_f3748786c3704532abb2358581488f3f,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/b8cTxDM8gDG_f3748786c3704532abb2358581488f3f.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,14,7,pairs_7_8,normal,occlusion;low_texture,corner_drift;over_parsing,legacy_proxy,unreviewed,,过度解析,过度解析,false,false,false,,true,true,false,true,true,legacy_proxy,,core,33,draft_proxy_balanced,true
460,X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9,X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9,X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,24,12,pairs_ge_9,oos_geometry,residual,overextend_adjacent,legacy_proxy,reviewed,,跨门扩张,跨门扩张,false,false,false,,true,true,true,true,true,confirmed,过度解析-跨门扩张；更适合semi,core,34,draft_proxy_balanced,false_scope_gate_audit
646,q9vSo1VnCiC_ca6944f5dd334193bb86058ba5ab5dc3,q9vSo1VnCiC_ca6944f5dd334193bb86058ba5ab5dc3,q9vSo1VnCiC_ca6944f5dd334193bb86058ba5ab5dc3,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/q9vSo1VnCiC_ca6944f5dd334193bb86058ba5ab5dc3.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,occlusion;reflection,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,,core,35,draft_proxy_balanced,true
710,e9zR4mvMWw7_4273c4dd97974531b5256f96204fee47,e9zR4mvMWw7_4273c4dd97974531b5256f96204fee47,e9zR4mvMWw7_4273c4dd97974531b5256f96204fee47,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/e9zR4mvMWw7_4273c4dd97974531b5256f96204fee47.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,occlusion,corner_drift,legacy_proxy,unreviewed,,角点错位/飘移,角点错位/飘移,false,false,false,,true,true,false,true,true,legacy_proxy,,core,36,draft_proxy_balanced,true
617,rPc6DW4iMge_e7f5cf7434824a0ab0b4cc060e863c9a,rPc6DW4iMge_e7f5cf7434824a0ab0b4cc060e863c9a,rPc6DW4iMge_e7f5cf7434824a0ab0b4cc060e863c9a,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/rPc6DW4iMge_e7f5cf7434824a0ab0b4cc060e863c9a.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;范围难度人工分层候选;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,occlusion;reflection,acceptable,legacy_proxy,reviewed,inscope,遮挡明显,模型标注质量好,false,false,false,,true,true,true,true,true,confirmed,可作中等遮挡样本,core,37,draft_proxy_balanced,true
```

## calibration_semi_selection_draft_v2.csv

### summary
```text
rows=25 columns=42
calibration_split={'core': 25}
semi_family={'模型标注质量好': 5, '角点重复': 2, '角点错位/飘移': 7, '跨门扩张': 5, '过度解析': 6}
semi_family_confidence={'confirmed': 4, 'legacy_proxy': 21}
expert_review_status={'reviewed': 4, 'unreviewed': 21}
proxy_confidence={'confirmed': 4, 'legacy_proxy': 21}
```

### first 50 lines
```text
task_id,base_task_id,image_id,image_stem,source_path,image_path,source_pool,source_files,used_in_prescreen,used_in_random_c1_deprecated,has_final_gold,geometry_gold_ready,scope_gold_ready,gt_keypoint_count,gt_pair_count,corner_count_bin,old_manual_scope_raw,old_manual_difficulty_raw,old_semi_model_issue_raw,legacy_label_status,expert_review_status,expert_scope_confirmed,expert_proxy_family_primary,expert_proxy_family_secondary,model_issue_only,semi_only,hard_exclude,exclude_reason,eligible_for_manual_calibration,eligible_for_core_proxy_sampling,eligible_for_anchor_candidate,eligible_for_reserve_candidate,eligible_for_semi_candidate,proxy_confidence,notes,calibration_split,selection_rank,selection_reason,used_for_r_u,semi_family,semi_family_confidence,semi_selection_rank
689,UwV83HsGsw3_cfe01e0f074a4a2cb892c6052bce550f,UwV83HsGsw3_cfe01e0f074a4a2cb892c6052bce550f,UwV83HsGsw3_cfe01e0f074a4a2cb892c6052bce550f,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/UwV83HsGsw3_cfe01e0f074a4a2cb892c6052bce550f.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,12,6,pairs_5_6,normal,occlusion,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,,core,75,draft_proxy_balanced,true,模型标注质量好,legacy_proxy,1
653,wc2JMjhGNzB_9d8a625f48194382a0bfb748b1126069,wc2JMjhGNzB_9d8a625f48194382a0bfb748b1126069,wc2JMjhGNzB_9d8a625f48194382a0bfb748b1126069,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_9d8a625f48194382a0bfb748b1126069.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,occlusion;reflection,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,,core,53,draft_proxy_balanced,true,模型标注质量好,legacy_proxy,2
648,uNb9QFRL6hY_e24473d2b8a24568b89c1c4c2a4a9bf1,uNb9QFRL6hY_e24473d2b8a24568b89c1c4c2a4a9bf1,uNb9QFRL6hY_e24473d2b8a24568b89c1c4c2a4a9bf1,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_e24473d2b8a24568b89c1c4c2a4a9bf1.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,16,8,pairs_7_8,normal,occlusion,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,,core,30,draft_proxy_balanced,true,模型标注质量好,legacy_proxy,3
563,rPc6DW4iMge_0012f6dcce9645778ac459e189cf0db3,rPc6DW4iMge_0012f6dcce9645778ac459e189cf0db3,rPc6DW4iMge_0012f6dcce9645778ac459e189cf0db3,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/rPc6DW4iMge_0012f6dcce9645778ac459e189cf0db3.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;范围难度人工分层候选;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,occlusion;reflection,acceptable,legacy_proxy,reviewed,inscope,简单,模型标注质量好,false,false,false,,true,true,true,true,true,confirmed,可作简单基线样本,core,21,draft_proxy_balanced,true,模型标注质量好,confirmed,4
525,UwV83HsGsw3_b979526475874ad68ae33f02d407a1fc,UwV83HsGsw3_b979526475874ad68ae33f02d407a1fc,UwV83HsGsw3_b979526475874ad68ae33f02d407a1fc,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/UwV83HsGsw3_b979526475874ad68ae33f02d407a1fc.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,12,6,pairs_5_6,normal,occlusion;reflection,overextend_adjacent,legacy_proxy,unreviewed,,跨门扩张,跨门扩张,false,false,false,,true,true,false,true,true,legacy_proxy,,core,4,draft_proxy_balanced,true,跨门扩张,legacy_proxy,5
460,X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9,X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9,X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,24,12,pairs_ge_9,oos_geometry,residual,overextend_adjacent,legacy_proxy,reviewed,,跨门扩张,跨门扩张,false,false,false,,true,true,true,true,true,confirmed,过度解析-跨门扩张；更适合semi,core,34,draft_proxy_balanced,false_scope_gate_audit,跨门扩张,confirmed,6
511,7y3sRwLe3Va_ad77d6eeca5b492b8fe3317177f4f03f,7y3sRwLe3Va_ad77d6eeca5b492b8fe3317177f4f03f,7y3sRwLe3Va_ad77d6eeca5b492b8fe3317177f4f03f,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/7y3sRwLe3Va_ad77d6eeca5b492b8fe3317177f4f03f.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,16,8,pairs_7_8,oos_geometry,occlusion;low_texture,overextend_adjacent;corner_drift;corner_duplicate,legacy_proxy,unreviewed,,跨门扩张,跨门扩张,false,false,false,,true,true,false,true,true,legacy_proxy,,core,11,draft_proxy_balanced,false_scope_gate_audit,跨门扩张,legacy_proxy,7
580,wc2JMjhGNzB_b41b10699d614f24851b56a9a0e743c6,wc2JMjhGNzB_b41b10699d614f24851b56a9a0e743c6,wc2JMjhGNzB_b41b10699d614f24851b56a9a0e743c6,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_b41b10699d614f24851b56a9a0e743c6.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;范围难度人工分层候选;校准semi模型问题整理,false,false,true,true,true,8,4,pairs_le_4,normal,occlusion,overextend_adjacent;corner_duplicate;over_parsing,legacy_proxy,reviewed,inscope,玻璃干扰/遮挡明显,跨门扩张,false,false,false,,true,true,true,true,true,confirmed,可作高难玻璃/遮挡样本,core,20,draft_proxy_balanced,true,跨门扩张,confirmed,8
542,wc2JMjhGNzB_4884da3227464ab5b82f631ff22205bd,wc2JMjhGNzB_4884da3227464ab5b82f631ff22205bd,wc2JMjhGNzB_4884da3227464ab5b82f631ff22205bd,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_4884da3227464ab5b82f631ff22205bd.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,24,12,pairs_ge_9,normal,occlusion;reflection,overextend_adjacent;over_parsing,legacy_proxy,unreviewed,,跨门扩张,跨门扩张,false,false,false,,true,true,false,true,true,legacy_proxy,,core,16,draft_proxy_balanced,true,跨门扩张,legacy_proxy,9
600,uNb9QFRL6hY_c6410f47ad754d6cbd890ba7dff8b449,uNb9QFRL6hY_c6410f47ad754d6cbd890ba7dff8b449,uNb9QFRL6hY_c6410f47ad754d6cbd890ba7dff8b449,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_c6410f47ad754d6cbd890ba7dff8b449.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,12,6,pairs_5_6,normal,low_texture,corner_drift,legacy_proxy,unreviewed,,角点错位/飘移,角点错位/飘移,false,false,false,,true,true,false,true,true,legacy_proxy,,core,49,draft_proxy_balanced,true,角点错位/飘移,legacy_proxy,10
595,q9vSo1VnCiC_c4b0b6a41c2a4db3927f5fa9cafb6345,q9vSo1VnCiC_c4b0b6a41c2a4db3927f5fa9cafb6345,q9vSo1VnCiC_c4b0b6a41c2a4db3927f5fa9cafb6345,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/q9vSo1VnCiC_c4b0b6a41c2a4db3927f5fa9cafb6345.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,14,7,pairs_7_8,normal,occlusion;low_texture,corner_drift;corner_duplicate,legacy_proxy,unreviewed,,角点错位/飘移,角点错位/飘移,false,false,false,,true,true,false,true,true,legacy_proxy,,core,10,draft_proxy_balanced,true,角点错位/飘移,legacy_proxy,11
706,wc2JMjhGNzB_0a54ae7daf36423fb6a5607caf3fb942,wc2JMjhGNzB_0a54ae7daf36423fb6a5607caf3fb942,wc2JMjhGNzB_0a54ae7daf36423fb6a5607caf3fb942,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_0a54ae7daf36423fb6a5607caf3fb942.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,8,4,pairs_le_4,normal,occlusion,corner_drift,legacy_proxy,unreviewed,,角点错位/飘移,角点错位/飘移,false,false,false,,true,true,false,true,true,legacy_proxy,,core,59,draft_proxy_balanced,true,角点错位/飘移,legacy_proxy,12
686,wc2JMjhGNzB_48a93a3b61354385b30974c248c11ef2,wc2JMjhGNzB_48a93a3b61354385b30974c248c11ef2,wc2JMjhGNzB_48a93a3b61354385b30974c248c11ef2,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_48a93a3b61354385b30974c248c11ef2.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,12,6,pairs_5_6,normal,low_texture,corner_drift;corner_duplicate,legacy_proxy,unreviewed,,角点错位/飘移,角点错位/飘移,false,false,false,,true,true,false,true,true,legacy_proxy,,core,66,draft_proxy_balanced,true,角点错位/飘移,legacy_proxy,13
480,e9zR4mvMWw7_0977162f6d4e47f7b3764379ba68d8db,e9zR4mvMWw7_0977162f6d4e47f7b3764379ba68d8db,e9zR4mvMWw7_0977162f6d4e47f7b3764379ba68d8db,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/e9zR4mvMWw7_0977162f6d4e47f7b3764379ba68d8db.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,seam;reflection,corner_drift,legacy_proxy,unreviewed,,角点错位/飘移,角点错位/飘移,false,false,false,,true,true,false,true,true,legacy_proxy,,core,22,draft_proxy_balanced,true,角点错位/飘移,legacy_proxy,14
700,wc2JMjhGNzB_9087f0358178420a8b9ac7b17a8919c7,wc2JMjhGNzB_9087f0358178420a8b9ac7b17a8919c7,wc2JMjhGNzB_9087f0358178420a8b9ac7b17a8919c7,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_9087f0358178420a8b9ac7b17a8919c7.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,12,6,pairs_5_6,normal,low_texture,corner_duplicate,legacy_proxy,unreviewed,,角点重复,角点重复,false,false,false,,true,true,false,true,true,legacy_proxy,,core,26,draft_proxy_balanced,true,角点重复,legacy_proxy,15
596,wc2JMjhGNzB_55b45b0f19c2460bbcd1fb1c86c6610d,wc2JMjhGNzB_55b45b0f19c2460bbcd1fb1c86c6610d,wc2JMjhGNzB_55b45b0f19c2460bbcd1fb1c86c6610d,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_55b45b0f19c2460bbcd1fb1c86c6610d.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,10,5,pairs_5_6,normal,trivial,corner_duplicate,legacy_proxy,unreviewed,,角点重复,角点重复,false,false,false,,true,true,false,true,true,legacy_proxy,,core,2,draft_proxy_balanced,true,角点重复,legacy_proxy,16
540,uNb9QFRL6hY_33dd9892d10e474ead8f7ad38a8da562,uNb9QFRL6hY_33dd9892d10e474ead8f7ad38a8da562,uNb9QFRL6hY_33dd9892d10e474ead8f7ad38a8da562,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_33dd9892d10e474ead8f7ad38a8da562.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,true,false,true,true,12,6,pairs_5_6,normal,occlusion,over_parsing,legacy_proxy,unreviewed,,过度解析,过度解析,false,false,false,,true,true,false,true,true,legacy_proxy,,core,5,draft_proxy_balanced,true,过度解析,legacy_proxy,17
652,yqstnuAEVhm_c93bf298b1cb41a1b368a6ce8bcff53d,yqstnuAEVhm_c93bf298b1cb41a1b368a6ce8bcff53d,yqstnuAEVhm_c93bf298b1cb41a1b368a6ce8bcff53d,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/yqstnuAEVhm_c93bf298b1cb41a1b368a6ce8bcff53d.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,36,18,pairs_ge_9,normal,occlusion,corner_drift;corner_duplicate;over_parsing,legacy_proxy,unreviewed,,过度解析,过度解析,false,false,false,,true,true,false,true,true,legacy_proxy,,core,17,draft_proxy_balanced,true,过度解析,legacy_proxy,18
535,b8cTxDM8gDG_f339391e9479496e8652c972953f0ce4,b8cTxDM8gDG_f339391e9479496e8652c972953f0ce4,b8cTxDM8gDG_f339391e9479496e8652c972953f0ce4,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/b8cTxDM8gDG_f339391e9479496e8652c972953f0ce4.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,12,6,pairs_5_6,normal,occlusion;reflection,over_parsing,legacy_proxy,unreviewed,,过度解析,过度解析,false,false,false,,true,true,false,true,true,legacy_proxy,,core,72,draft_proxy_balanced,true,过度解析,legacy_proxy,19
683,wc2JMjhGNzB_dda6efcba51c40de8552408953719515,wc2JMjhGNzB_dda6efcba51c40de8552408953719515,wc2JMjhGNzB_dda6efcba51c40de8552408953719515,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/wc2JMjhGNzB_dda6efcba51c40de8552408953719515.png,legacy_project2_full_annotation,old_label_json;亲自复核整理;范围难度人工分层候选;校准semi模型问题整理,false,true,true,true,true,12,6,pairs_5_6,normal,occlusion,corner_duplicate;over_parsing,legacy_proxy,reviewed,inscope,遮挡明显,过度解析,false,false,false,,true,true,true,true,true,confirmed,可作中等遮挡样本,core,6,draft_proxy_balanced,true,过度解析,confirmed,20
597,yqstnuAEVhm_b26ae45c6c12443cbcfc3997f2e63347,yqstnuAEVhm_b26ae45c6c12443cbcfc3997f2e63347,yqstnuAEVhm_b26ae45c6c12443cbcfc3997f2e63347,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/yqstnuAEVhm_b26ae45c6c12443cbcfc3997f2e63347.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,16,8,pairs_7_8,normal,trivial,acceptable,legacy_proxy,unreviewed,,模型标注质量好,模型标注质量好,false,false,false,,true,true,false,true,true,legacy_proxy,,core,41,draft_proxy_balanced,true,模型标注质量好,legacy_proxy,21
491,uNb9QFRL6hY_26b3b14f6ce047489259ab14d131122d,uNb9QFRL6hY_26b3b14f6ce047489259ab14d131122d,uNb9QFRL6hY_26b3b14f6ce047489259ab14d131122d,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_26b3b14f6ce047489259ab14d131122d.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,occlusion;trivial,corner_drift;acceptable,legacy_proxy,unreviewed,,角点错位/飘移,角点错位/飘移,false,false,false,,true,true,false,true,true,legacy_proxy,,core,69,draft_proxy_balanced,true,角点错位/飘移,legacy_proxy,22
594,yqstnuAEVhm_2f8c1f8ea7364f67b1c5fe2be2750257,yqstnuAEVhm_2f8c1f8ea7364f67b1c5fe2be2750257,yqstnuAEVhm_2f8c1f8ea7364f67b1c5fe2be2750257,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/yqstnuAEVhm_2f8c1f8ea7364f67b1c5fe2be2750257.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,8,4,pairs_le_4,normal,trivial,corner_duplicate;over_parsing,legacy_proxy,unreviewed,,过度解析,过度解析,false,false,false,,true,true,false,true,true,legacy_proxy,,core,23,draft_proxy_balanced,true,过度解析,legacy_proxy,23
604,b8cTxDM8gDG_f3748786c3704532abb2358581488f3f,b8cTxDM8gDG_f3748786c3704532abb2358581488f3f,b8cTxDM8gDG_f3748786c3704532abb2358581488f3f,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/b8cTxDM8gDG_f3748786c3704532abb2358581488f3f.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,14,7,pairs_7_8,normal,occlusion;low_texture,corner_drift;over_parsing,legacy_proxy,unreviewed,,过度解析,过度解析,false,false,false,,true,true,false,true,true,legacy_proxy,,core,33,draft_proxy_balanced,true,过度解析,legacy_proxy,24
659,uNb9QFRL6hY_3450b3accb584493bf13be8e9554dbea,uNb9QFRL6hY_3450b3accb584493bf13be8e9554dbea,uNb9QFRL6hY_3450b3accb584493bf13be8e9554dbea,export_label/project-2-at-2026-03-25-10-52-c04c6496.json,http://106.53.106.49:8000/data/mp3d_layout/test/img/uNb9QFRL6hY_3450b3accb584493bf13be8e9554dbea.png,legacy_project2_full_annotation,old_label_json;旧标注补充清单;校准semi模型问题整理,false,false,false,true,true,12,6,pairs_5_6,normal,occlusion;low_texture,corner_drift,legacy_proxy,unreviewed,,角点错位/飘移,角点错位/飘移,false,false,false,,true,true,false,true,true,legacy_proxy,,core,27,draft_proxy_balanced,true,角点错位/飘移,legacy_proxy,25
```

## assignment_manifest_C1_manual_draft_v2.csv

### summary
```text
rows=651 columns=11
dataset_group={'Calibration_anchor': 276, 'Calibration_core': 375}
```

### first 50 lines
```text
round_id,worker_id,task_id,base_task_id,dataset_group,assignment_batch,assignment_reason,is_common_anchor,expected_completion_order,manifest_version,watch_flag
C1,27,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,False
C1,29,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,True
C1,13,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,True
C1,2,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,False
C1,32,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,True
C1,30,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,False
C1,1,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,False
C1,28,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,True
C1,17,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,False
C1,18,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,False
C1,14,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,True
C1,6,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,True
C1,36,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,True
C1,31,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,True
C1,11,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,False
C1,33,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,True
C1,34,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,True
C1,12,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,True
C1,15,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,False
C1,35,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,True
C1,8,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,True
C1,10,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,False
C1,37,558,uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e,Calibration_anchor,anchor_all,common_anchor,true,1,C1_manual_v2_draft,True
C1,27,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,False
C1,29,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,True
C1,13,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,True
C1,2,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,False
C1,32,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,True
C1,30,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,False
C1,1,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,False
C1,28,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,True
C1,17,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,False
C1,18,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,False
C1,14,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,True
C1,6,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,True
C1,36,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,True
C1,31,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,True
C1,11,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,False
C1,33,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,True
C1,34,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,True
C1,12,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,True
C1,15,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,False
C1,35,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,True
C1,8,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,True
C1,10,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,False
C1,37,561,UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972,Calibration_anchor,anchor_all,common_anchor,true,2,C1_manual_v2_draft,True
C1,27,672,uNb9QFRL6hY_6c4fa6dfddc1499db228854454bfc61d,Calibration_anchor,anchor_all,common_anchor,true,3,C1_manual_v2_draft,False
C1,29,672,uNb9QFRL6hY_6c4fa6dfddc1499db228854454bfc61d,Calibration_anchor,anchor_all,common_anchor,true,3,C1_manual_v2_draft,True
C1,13,672,uNb9QFRL6hY_6c4fa6dfddc1499db228854454bfc61d,Calibration_anchor,anchor_all,common_anchor,true,3,C1_manual_v2_draft,True
```

## assignment_manifest_C1_semi_draft_v2.csv

### summary
```text
rows=100 columns=14
dataset_group={'Calibration_semi': 100}
semi_family={'模型标注质量好': 20, '角点重复': 8, '角点错位/飘移': 28, '跨门扩张': 20, '过度解析': 24}
```

### first 50 lines
```text
round_id,worker_id,task_id,base_task_id,dataset_group,assignment_batch,assignment_reason,is_common_anchor,expected_completion_order,manifest_version,watch_flag,used_for_r_u,used_for_rq2,semi_family
C1,1,689,UwV83HsGsw3_cfe01e0f074a4a2cb892c6052bce550f,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,False,false,true,模型标注质量好
C1,2,689,UwV83HsGsw3_cfe01e0f074a4a2cb892c6052bce550f,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,False,false,true,模型标注质量好
C1,6,689,UwV83HsGsw3_cfe01e0f074a4a2cb892c6052bce550f,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,True,false,true,模型标注质量好
C1,8,689,UwV83HsGsw3_cfe01e0f074a4a2cb892c6052bce550f,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,True,false,true,模型标注质量好
C1,10,653,wc2JMjhGNzB_9d8a625f48194382a0bfb748b1126069,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,False,false,true,模型标注质量好
C1,11,653,wc2JMjhGNzB_9d8a625f48194382a0bfb748b1126069,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,False,false,true,模型标注质量好
C1,14,653,wc2JMjhGNzB_9d8a625f48194382a0bfb748b1126069,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,True,false,true,模型标注质量好
C1,15,653,wc2JMjhGNzB_9d8a625f48194382a0bfb748b1126069,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,False,false,true,模型标注质量好
C1,17,648,uNb9QFRL6hY_e24473d2b8a24568b89c1c4c2a4a9bf1,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,False,false,true,模型标注质量好
C1,18,648,uNb9QFRL6hY_e24473d2b8a24568b89c1c4c2a4a9bf1,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,False,false,true,模型标注质量好
C1,27,648,uNb9QFRL6hY_e24473d2b8a24568b89c1c4c2a4a9bf1,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,False,false,true,模型标注质量好
C1,28,648,uNb9QFRL6hY_e24473d2b8a24568b89c1c4c2a4a9bf1,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,True,false,true,模型标注质量好
C1,12,563,rPc6DW4iMge_0012f6dcce9645778ac459e189cf0db3,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,True,false,true,模型标注质量好
C1,13,563,rPc6DW4iMge_0012f6dcce9645778ac459e189cf0db3,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,True,false,true,模型标注质量好
C1,29,563,rPc6DW4iMge_0012f6dcce9645778ac459e189cf0db3,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,True,false,true,模型标注质量好
C1,30,563,rPc6DW4iMge_0012f6dcce9645778ac459e189cf0db3,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,False,false,true,模型标注质量好
C1,32,525,UwV83HsGsw3_b979526475874ad68ae33f02d407a1fc,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,True,false,true,跨门扩张
C1,35,525,UwV83HsGsw3_b979526475874ad68ae33f02d407a1fc,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,True,false,true,跨门扩张
C1,36,525,UwV83HsGsw3_b979526475874ad68ae33f02d407a1fc,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,True,false,true,跨门扩张
C1,37,525,UwV83HsGsw3_b979526475874ad68ae33f02d407a1fc,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,True,false,true,跨门扩张
C1,33,460,X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,True,false,true,跨门扩张
C1,34,460,X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,True,false,true,跨门扩张
C1,1,460,X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,False,false,true,跨门扩张
C1,2,460,X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,False,false,true,跨门扩张
C1,6,511,7y3sRwLe3Va_ad77d6eeca5b492b8fe3317177f4f03f,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,True,false,true,跨门扩张
C1,12,511,7y3sRwLe3Va_ad77d6eeca5b492b8fe3317177f4f03f,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,True,false,true,跨门扩张
C1,13,511,7y3sRwLe3Va_ad77d6eeca5b492b8fe3317177f4f03f,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,True,false,true,跨门扩张
C1,14,511,7y3sRwLe3Va_ad77d6eeca5b492b8fe3317177f4f03f,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,True,false,true,跨门扩张
C1,31,580,wc2JMjhGNzB_b41b10699d614f24851b56a9a0e743c6,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,1,C1_semi_v2_draft,True,false,true,跨门扩张
C1,8,580,wc2JMjhGNzB_b41b10699d614f24851b56a9a0e743c6,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,True,false,true,跨门扩张
C1,10,580,wc2JMjhGNzB_b41b10699d614f24851b56a9a0e743c6,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,False,false,true,跨门扩张
C1,11,580,wc2JMjhGNzB_b41b10699d614f24851b56a9a0e743c6,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,False,false,true,跨门扩张
C1,18,542,wc2JMjhGNzB_4884da3227464ab5b82f631ff22205bd,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,False,false,true,跨门扩张
C1,27,542,wc2JMjhGNzB_4884da3227464ab5b82f631ff22205bd,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,False,false,true,跨门扩张
C1,28,542,wc2JMjhGNzB_4884da3227464ab5b82f631ff22205bd,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,True,false,true,跨门扩张
C1,29,542,wc2JMjhGNzB_4884da3227464ab5b82f631ff22205bd,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,True,false,true,跨门扩张
C1,15,600,uNb9QFRL6hY_c6410f47ad754d6cbd890ba7dff8b449,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,False,false,true,角点错位/飘移
C1,17,600,uNb9QFRL6hY_c6410f47ad754d6cbd890ba7dff8b449,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,False,false,true,角点错位/飘移
C1,30,600,uNb9QFRL6hY_c6410f47ad754d6cbd890ba7dff8b449,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,False,false,true,角点错位/飘移
C1,31,600,uNb9QFRL6hY_c6410f47ad754d6cbd890ba7dff8b449,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,True,false,true,角点错位/飘移
C1,32,595,q9vSo1VnCiC_c4b0b6a41c2a4db3927f5fa9cafb6345,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,True,false,true,角点错位/飘移
C1,35,595,q9vSo1VnCiC_c4b0b6a41c2a4db3927f5fa9cafb6345,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,True,false,true,角点错位/飘移
C1,36,595,q9vSo1VnCiC_c4b0b6a41c2a4db3927f5fa9cafb6345,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,True,false,true,角点错位/飘移
C1,37,595,q9vSo1VnCiC_c4b0b6a41c2a4db3927f5fa9cafb6345,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,True,false,true,角点错位/飘移
C1,33,706,wc2JMjhGNzB_0a54ae7daf36423fb6a5607caf3fb942,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,True,false,true,角点错位/飘移
C1,34,706,wc2JMjhGNzB_0a54ae7daf36423fb6a5607caf3fb942,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,2,C1_semi_v2_draft,True,false,true,角点错位/飘移
C1,8,706,wc2JMjhGNzB_0a54ae7daf36423fb6a5607caf3fb942,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,3,C1_semi_v2_draft,True,false,true,角点错位/飘移
C1,10,706,wc2JMjhGNzB_0a54ae7daf36423fb6a5607caf3fb942,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,3,C1_semi_v2_draft,False,false,true,角点错位/飘移
C1,1,686,wc2JMjhGNzB_48a93a3b61354385b30974c248c11ef2,Calibration_semi,semi_rr_k4,rq2_paired_audit,false,3,C1_semi_v2_draft,False,false,true,角点错位/飘移
```

## manual_semi_same_image_overlap_audit_v2.csv

### summary
```text
rows=1 columns=2
```

### first 50 lines
```text
passed,manual_semi_same_image_overlap_count
True,0
```

## c1_launch_readiness_draft_v2.json

### summary
```text
{
  "passed": false,
  "status": "draft_pending_human_review",
  "blockers": [
    "manual pool draft pending human approval",
    "semi family draft pending human approval",
    "LS import not yet materialized",
    "active log smoke test not yet run on v2 projects",
    "worker-facing distribution not generated"
  ],
  "protocol_checks": {
    "random_c1_deprecated": true,
    "reserve_excluded_from_c1": true,
    "semi_only_from_core": true,
    "readiness_for_launch": false
  },
  "overlap_checks": {
    "prescreen_overlap_count": 0
  },
  "assignment_checks": {
    "manual": {
      "passed": true,
      "anchor_task_count": 12,
      "core_task_count": 75,
      "eligible_worker_count": 23,
      "core_redundancy_min": 5,
      "core_redundancy_max": 5,
      "reserve_assignment_count": 0,
      "worker_core_load_min": 16,
      "worker_core_load_max": 17,
      "worker_total_manual_load_min": 28,
      "worker_total_manual_load_max": 29,
      "duplicate_worker_task_count": 0,
      "duplicate_task_assignment_within_worker": 0,
      "watch_workers_included": 14
    },
    "semi": {
      "passed": true,
      "semi_task_count": 25,
      "semi_k_min": 4,
      "semi_k_max": 4,
      "worker_semi_load_min": 4,
      "worker_semi_load_max": 5,
      "manual_semi_same_image_overlap_count": 0,
      "anchor_in_semi_count": 0,
      "reserve_in_semi_count": 0,
      "used_for_r_u_false_count": 100,
      "used_for_rq2_true_count": 100
    },
    "manual_semi_overlap": {
      "manual_semi_same_image_overlap_count": 0,
      "passed": true
    }
  },
  "proxy_balance_warnings": [
    "semi_shortfall:角点重复=2",
    "semi_shortfall:漏标=2",
    "semi_shortfall:模型预标注失败/拓扑失败=1"
  ],
  "test_results": "pytest tests/test_build_c1_assignment_manifest.py tests/test_calibration_rebuild_v2_drafts.py = 11 passed"
}

```

### first 50 lines
```text
{
  "passed": false,
  "status": "draft_pending_human_review",
  "blockers": [
    "manual pool draft pending human approval",
    "semi family draft pending human approval",
    "LS import not yet materialized",
    "active log smoke test not yet run on v2 projects",
    "worker-facing distribution not generated"
  ],
  "protocol_checks": {
    "random_c1_deprecated": true,
    "reserve_excluded_from_c1": true,
    "semi_only_from_core": true,
    "readiness_for_launch": false
  },
  "overlap_checks": {
    "prescreen_overlap_count": 0
  },
  "assignment_checks": {
    "manual": {
      "passed": true,
      "anchor_task_count": 12,
      "core_task_count": 75,
      "eligible_worker_count": 23,
      "core_redundancy_min": 5,
      "core_redundancy_max": 5,
      "reserve_assignment_count": 0,
      "worker_core_load_min": 16,
      "worker_core_load_max": 17,
      "worker_total_manual_load_min": 28,
      "worker_total_manual_load_max": 29,
      "duplicate_worker_task_count": 0,
      "duplicate_task_assignment_within_worker": 0,
      "watch_workers_included": 14
    },
    "semi": {
      "passed": true,
      "semi_task_count": 25,
      "semi_k_min": 4,
      "semi_k_max": 4,
      "worker_semi_load_min": 4,
      "worker_semi_load_max": 5,
      "manual_semi_same_image_overlap_count": 0,
      "anchor_in_semi_count": 0,
      "reserve_in_semi_count": 0,
      "used_for_r_u_false_count": 100,
      "used_for_rq2_true_count": 100
    },
    "manual_semi_overlap": {
```

## Determinism / hard-code audit

- fixed seed: yes
- seed: 20260702
- worker order: fixed-seed shuffle from P1 admission eligible workers
- core order: proxy-balanced interleaved order from candidate buckets
- hard-coded task_id in selection logic: no; hard excludes are parsed from human review artifact
- hard-coded worker_id in assignment logic: no