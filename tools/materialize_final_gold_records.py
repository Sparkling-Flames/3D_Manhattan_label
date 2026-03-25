from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


TRUTH_LAYER_DIRNAME = "truth_layer_extraction_20260324"
FINAL_GOLD_DIRNAME = "final_gold_layer_20260325"
FINAL_GOLD_STATUS = "final_adjudicated_gold"
FINAL_GOLD_SOURCE = "user_verified_project20_export"
FINAL_GEOMETRY_SOURCE = "ls_canonical_geometry"
LEGACY_TXT_ROLE = "legacy_mp3d_reference"

CSV_FIELDS = [
    "task_id",
    "base_task_id",
    "bucket_dir",
    "family_dir",
    "priority_flag",
    "review_note_flag",
    "default_eligible",
    "final_scope_alias",
    "final_scope_binary",
    "geometry_gold_ready",
    "scope_gold_ready",
    "adjudication_status",
    "final_gold_source",
    "final_geometry_source",
    "legacy_txt_role",
    "poly_residue_flag",
    "export_snapshot",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})


def load_truth_layer(root: Path | None = None) -> dict[str, Any]:
    repo_root = root or _repo_root()
    truth_dir = repo_root / "analysis_results" / TRUTH_LAYER_DIRNAME
    return {
        "repo_root": repo_root,
        "truth_summary": _read_json(truth_dir / "truth_layer_extraction_summary_v1.json"),
        "annotation_records": _read_jsonl(truth_dir / "manual_annotation_records_v1.jsonl"),
    }


def build_final_gold_records(
    truth_summary: dict[str, Any],
    annotation_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in annotation_records:
        final_scope_binary = str(row["scope_binary"]).strip()
        geometry_gold_ready = final_scope_binary == "in_scope" and bool(row.get("canonical_corners_norm"))
        scope_gold_ready = bool(str(row.get("scope", "")).strip())

        rows.append(
            {
                "task_id": row["task_id"],
                "base_task_id": row["base_task_id"],
                "bucket_dir": row["bucket_dir"],
                "family_dir": row["family_dir"],
                "priority_flag": row["priority_flag"],
                "recommended_role": row["recommended_role"],
                "review_note_flag": row["review_note_flag"],
                "default_eligible": row["default_eligible"],
                "final_scope_alias": row["scope"],
                "final_scope_binary": final_scope_binary,
                "geometry_gold_ready": geometry_gold_ready,
                "scope_gold_ready": scope_gold_ready,
                "canonical_corners_norm": row["canonical_corners_norm"],
                "runtime_pairs_1024x512": row["runtime_pairs_1024x512"],
                "n_corners": row["n_corners"],
                "pair_coverage": row["pair_coverage"],
                "poly_residue_flag": row["poly_residue_flag"],
                "legacy_txt_present": row["legacy_txt_present"],
                "legacy_txt_role": LEGACY_TXT_ROLE,
                "final_gold_source": FINAL_GOLD_SOURCE,
                "final_geometry_source": FINAL_GEOMETRY_SOURCE,
                "scope_source": "project20_scope",
                "geometry_source_export": row["source_export"],
                "export_snapshot": truth_summary["export_snapshot"],
                "adjudication_status": FINAL_GOLD_STATUS,
                "final_gold_notes": [
                    "promoted_from_latest_project20_verified_trap_export",
                    "poly_is_residue_only_not_authoritative",
                    "legacy_txt_is_reference_only_not_authoritative",
                    "difficulty_and_model_issue_are_not_promoted_to_final_gold_contract",
                ],
            }
        )
    return rows


def build_final_gold_summary(
    truth_summary: dict[str, Any],
    final_gold_records: list[dict[str, Any]],
) -> dict[str, Any]:
    n_total = len(final_gold_records)
    n_in_scope = sum(1 for row in final_gold_records if row["final_scope_binary"] == "in_scope")
    n_oos = sum(1 for row in final_gold_records if row["final_scope_binary"] == "oos")
    n_geometry_gold_ready = sum(1 for row in final_gold_records if row["geometry_gold_ready"])
    n_scope_gold_ready = sum(1 for row in final_gold_records if row["scope_gold_ready"])
    n_poly_residue = sum(1 for row in final_gold_records if row["poly_residue_flag"])
    n_low_priority = sum(1 for row in final_gold_records if row["priority_flag"] == "low_priority")
    n_special_review = sum(1 for row in final_gold_records if row["priority_flag"] == "special_review")
    n_missing_scope = sum(1 for row in final_gold_records if not row["final_scope_alias"])
    n_missing_corners_for_in_scope = sum(
        1
        for row in final_gold_records
        if row["final_scope_binary"] == "in_scope" and not row["canonical_corners_norm"]
    )

    return {
        "summary_name": "final_gold_summary_v1",
        "source_truth_layer_dir": TRUTH_LAYER_DIRNAME,
        "source_truth_layer_status": truth_summary["summary_status"],
        "export_snapshot": truth_summary["export_snapshot"],
        "final_gold_source": FINAL_GOLD_SOURCE,
        "adjudication_status": FINAL_GOLD_STATUS,
        "n_records_total": n_total,
        "n_in_scope": n_in_scope,
        "n_oos": n_oos,
        "n_geometry_gold_ready": n_geometry_gold_ready,
        "n_scope_gold_ready": n_scope_gold_ready,
        "n_low_priority": n_low_priority,
        "n_special_review": n_special_review,
        "n_poly_residue": n_poly_residue,
        "n_missing_scope": n_missing_scope,
        "n_missing_corners_for_in_scope": n_missing_corners_for_in_scope,
        "difficulty_model_issue_promoted_to_final_gold": False,
        "legacy_txt_authoritative": False,
        "poly_authoritative": False,
        "ls_canonical_geometry_authoritative": True,
        "summary_status": "final_gold_materialized_from_verified_project20_export"
        if n_missing_scope == 0 and n_missing_corners_for_in_scope == 0
        else "final_gold_materialization_incomplete",
        "notes": [
            "This layer upgrades the verified latest project-20 trap export into final adjudicated gold for Stage 1 rebinding.",
            "Only scope and LS canonical corner geometry are promoted into the final-gold contract.",
            "Difficulty and model_issue remain available in the underlying export/truth layer, but are not treated as final-gold adjudication fields here.",
        ],
    }


def run(output_dir: Path | None = None, root: Path | None = None) -> dict[str, Path]:
    inputs = load_truth_layer(root=root)
    repo_root = inputs["repo_root"]
    final_output_dir = output_dir or (repo_root / "analysis_results" / FINAL_GOLD_DIRNAME)

    final_gold_records = build_final_gold_records(
        truth_summary=inputs["truth_summary"],
        annotation_records=inputs["annotation_records"],
    )
    final_gold_summary = build_final_gold_summary(
        truth_summary=inputs["truth_summary"],
        final_gold_records=final_gold_records,
    )

    outputs = {
        "final_gold_jsonl": final_output_dir / "final_gold_records_v1.jsonl",
        "final_gold_csv": final_output_dir / "final_gold_records_v1.csv",
        "final_gold_summary": final_output_dir / "final_gold_summary_v1.json",
    }
    _write_jsonl(outputs["final_gold_jsonl"], final_gold_records)
    _write_csv(outputs["final_gold_csv"], final_gold_records)
    _write_json(outputs["final_gold_summary"], final_gold_summary)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Materialize verified project-20 trap truth layer into final gold records."
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    outputs = run(output_dir=args.output_dir)
    print(json.dumps({key: str(value) for key, value in outputs.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
