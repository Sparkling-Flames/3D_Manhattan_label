from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.registry.build_calibration_rebuild_v2_drafts import (
    INVENTORY_FIELDS,
    build_inventory,
    build_manual_assignment,
    build_semi_assignment,
    select_manual_pools,
    select_semi_from_core,
)


def _candidate(task_id: int, *, reviewed: bool = True, eligible: bool = True, family: str = "occlusion") -> dict[str, str]:
    row = {field: "" for field in INVENTORY_FIELDS}
    row.update(
        {
            "task_id": str(task_id),
            "base_task_id": f"img_{task_id}",
            "image_id": f"img_{task_id}",
            "image_stem": f"scene{task_id % 7}_img_{task_id}",
            "image_path": f"https://example.test/img_{task_id}.png",
            "used_in_prescreen": "false",
            "used_in_random_c1_deprecated": "false",
            "geometry_gold_ready": "true",
            "scope_gold_ready": "true",
            "gt_keypoint_count": "8",
            "gt_pair_count": "4",
            "corner_count_bin": "pairs_le_4" if task_id % 3 else "pairs_5_6",
            "old_manual_scope_raw": "normal",
            "old_manual_difficulty_raw": family,
            "old_semi_model_issue_raw": "acceptable" if task_id % 5 == 0 else "overextend_adjacent",
            "legacy_label_status": "legacy_proxy",
            "expert_review_status": "reviewed" if reviewed else "unreviewed",
            "expert_scope_confirmed": "inscope",
            "expert_proxy_family_primary": family,
            "expert_proxy_family_secondary": "模型标注质量好" if task_id % 5 == 0 else "跨门扩张",
            "model_issue_only": "false",
            "semi_only": "false",
            "hard_exclude": "false",
            "eligible_for_manual_calibration": str(eligible).lower(),
            "eligible_for_core_proxy_sampling": str(eligible).lower(),
            "eligible_for_anchor_candidate": str(eligible and reviewed).lower(),
            "eligible_for_reserve_candidate": str(eligible).lower(),
            "eligible_for_semi_candidate": str(eligible).lower(),
            "proxy_confidence": "confirmed" if reviewed else "legacy_proxy",
            "notes": "高难 stable" if task_id in {1, 2} else "",
        }
    )
    return row


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_old_json(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for tid in [460, 461, 566]:
        payload.append(
            {
                "id": tid,
                "data": {"image": f"https://example.test/img_{tid}.png", "title": f"img_{tid}.png"},
                "annotations": [
                    {
                        "result": [
                            {"from_name": "kp", "type": "keypointlabels", "value": {"keypointlabels": ["Corner"]}},
                            {"from_name": "kp", "type": "keypointlabels", "value": {"keypointlabels": ["Corner"]}},
                            {"from_name": "scope", "type": "choices", "value": {"choices": ["normal"]}},
                            {"from_name": "difficulty", "type": "choices", "value": {"choices": ["trivial"]}},
                            {"from_name": "model_issue", "type": "choices", "value": {"choices": ["acceptable"]}},
                        ]
                    }
                ],
            }
        )
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_inventory_keeps_legacy_unreviewed_but_excludes_prescreen_and_hard_exclude(tmp_path: Path) -> None:
    _write_old_json(tmp_path / "export_label/project-2-at-2026-03-25-10-52-c04c6496.json")
    raw = tmp_path / "analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs"
    raw.mkdir(parents=True)
    (raw / "project-1-at-x.json").write_text(json.dumps([{"data": {"title": "img_461.png"}}]), encoding="utf-8")
    (tmp_path / "analysis_results/prescreen_closeout_final_gold_v2_20260701/final_gold_records_v2_p1_closeout_corrected.jsonl").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "analysis_results/prescreen_closeout_final_gold_v2_20260701/final_gold_records_v2_p1_closeout_corrected.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "trap集").mkdir()
    (tmp_path / "trap集/旧标注补充清单_20260702.md").write_text("| task_id | x |\n| --- | --- |\n| 460 | x |\n", encoding="utf-8")
    (tmp_path / "trap集/亲自复核整理与分层_20260702.md").write_text("| task | 建议层 | scope | 难度代理 | 人工评价 | 处理建议 |\n| --- | --- | --- | --- | --- | --- |\n| 566 | x | | | 不好 | 不适合 |\n", encoding="utf-8")

    rows, summary = build_inventory(tmp_path)
    by_id = {row["task_id"]: row for row in rows}

    assert by_id["460"]["expert_review_status"] == "unreviewed"
    assert by_id["460"]["hard_exclude"] == "false"
    assert by_id["461"]["used_in_prescreen"] == "true"
    assert by_id["461"]["eligible_for_manual_calibration"] == "false"
    assert by_id["566"]["hard_exclude"] == "true"
    assert summary["hard_exclude_count"] == 1


def test_manual_pool_counts_and_exclusions() -> None:
    rows = [_candidate(i, reviewed=i <= 30, family="高难" if i in {1, 2} else "occlusion") for i in range(1, 125)]
    rows.append(_candidate(999, eligible=False))

    anchor, core, reserve, audit = select_manual_pools(rows)
    selected = anchor + core + reserve

    assert len(anchor) == 12
    assert len(core) == 75
    assert len(reserve) == 13
    assert audit["blockers"] == []
    assert all(row["task_id"] != "999" for row in selected)
    assert len([row for row in anchor if "高难" in row["notes"] + row["expert_proxy_family_primary"]]) >= 1


def test_assignments_enforce_core_k5_semi_k4_and_no_same_image_overlap() -> None:
    rows = [_candidate(i, reviewed=i <= 30) for i in range(1, 125)]
    anchor, core, _, _ = select_manual_pools(rows)
    semi, semi_quota = select_semi_from_core(core)
    workers = [{"worker_id": str(i), "watch_flag": "True" if i % 7 == 0 else "False"} for i in range(1, 24)]

    manual_rows, manual_audit = build_manual_assignment(anchor, core, workers)
    semi_rows, overlap_audit, semi_audit = build_semi_assignment(semi, manual_rows, workers)

    assert semi_quota["semi_count"] == 25
    assert all(row["calibration_split"] == "core" for row in semi)
    assert manual_audit["core_redundancy_min"] == 5
    assert manual_audit["core_redundancy_max"] == 5
    assert manual_audit["reserve_assignment_count"] == 0
    assert semi_audit["semi_k_min"] == 4
    assert semi_audit["semi_k_max"] == 4
    assert semi_audit["worker_semi_load_min"] >= 4
    assert semi_audit["worker_semi_load_max"] <= 5
    assert overlap_audit["manual_semi_same_image_overlap_count"] == 0
    assert all(row["used_for_r_u"] == "false" and row["used_for_rq2"] == "true" for row in semi_rows)
