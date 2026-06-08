from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


PHASE1_DIRNAME = "phase1_progress_20260324"
TRUTH_LAYER_DIRNAME = "truth_layer_extraction_20260324"
PROJECT2_EXPORT_NAME = "project-2-at-2026-03-25-10-52-c04c6496.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _find_latest_verified_export(root: Path) -> Path:
    export_root = root / "export_label" / "人工精标"
    candidates = sorted(export_root.glob("project-20-at-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError("No project-20 verified export found under export_label/人工精标")
    return candidates[0]


def _extract_choices(row: dict[str, Any], field: str) -> list[str]:
    anns = row.get("annotations", [])
    if not anns:
        return []
    out: list[str] = []
    active_ann = anns[-1]
    for result in active_ann.get("result", []):
        if result.get("from_name") != field:
            continue
        out.extend(result.get("value", {}).get("choices", []))
    dedup: list[str] = []
    for item in out:
        if item not in dedup:
            dedup.append(item)
    return dedup


def build_rows(repo_root: Path) -> list[dict[str, Any]]:
    registry_rows = [
        row
        for row in _read_csv(
            repo_root / "analysis_results" / TRUTH_LAYER_DIRNAME / "trap_task_registry_v1.csv"
        )
        if row["bucket_dir"] == "semi"
    ]
    latest_export_path = _find_latest_verified_export(repo_root)
    latest_export = _read_json(latest_export_path)
    project2_export = _read_json(repo_root / "export_label" / PROJECT2_EXPORT_NAME)

    latest_by_base = {
        row.get("data", {}).get("title", "").rsplit(".", 1)[0]: row for row in latest_export
    }
    project2_by_base = {
        row.get("data", {}).get("title", "").rsplit(".", 1)[0]: row for row in project2_export
    }

    rows: list[dict[str, Any]] = []
    for row in sorted(registry_rows, key=lambda item: int(item["task_id"])):
        base_task_id = row["base_task_id"]
        latest_row = latest_by_base.get(base_task_id, {})
        project2_row = project2_by_base.get(base_task_id, {})
        latest_model_issue = _extract_choices(latest_row, "model_issue")
        project2_model_issue = _extract_choices(project2_row, "model_issue")
        rows.append(
            {
                "task_id": row["task_id"],
                "base_task_id": base_task_id,
                "trap_family_dir": row["trap_family"],
                "priority_flag": row["priority_flag"],
                "review_note_flag": row["review_note_flag"],
                "latest_verified_export": latest_export_path.name,
                "latest_verified_scope": row["current_scope_alias"],
                "latest_verified_model_issue_tags": ";".join(latest_model_issue),
                "latest_verified_issue_count": len(latest_model_issue),
                "latest_verified_has_mixed_issue": len(latest_model_issue) > 1,
                "project2_model_issue_tags": ";".join(project2_model_issue),
                "project2_issue_count": len(project2_model_issue),
                "project2_has_mixed_issue": len(project2_model_issue) > 1,
                "notes": (
                    "latest_verified_multi_issue"
                    if len(latest_model_issue) > 1
                    else "project2_multi_issue_only"
                    if len(project2_model_issue) > 1
                    else ""
                ),
            }
        )
    return rows


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latest_multi = [row["task_id"] for row in rows if row["latest_verified_has_mixed_issue"]]
    project2_multi = [row["task_id"] for row in rows if row["project2_has_mixed_issue"]]
    latest_export_snapshot = rows[0]["latest_verified_export"] if rows else ""
    return {
        "summary_name": "semi_label_overlap_summary_v1",
        "latest_verified_export": latest_export_snapshot,
        "semi_task_count": len(rows),
        "latest_verified_multi_issue_task_ids": latest_multi,
        "project2_multi_issue_task_ids": project2_multi,
        "latest_verified_multi_issue_count": len(latest_multi),
        "project2_multi_issue_count": len(project2_multi),
        "notes": [
            "latest verified export is the authoritative source for current prescreen truth-layer semantics",
            "project-2 export is comparison-only and is used to recall earlier model-issue impressions",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=f"analysis_results/{PHASE1_DIRNAME}")
    args = parser.parse_args()

    repo_root = _repo_root()
    output_dir = repo_root / args.output_dir
    rows = build_rows(repo_root)
    summary = build_summary(rows)
    _write_csv(output_dir / "semi_label_overlap_audit_v1.csv", rows)
    _write_json(output_dir / "semi_label_overlap_summary_v1.json", summary)


if __name__ == "__main__":
    main()
