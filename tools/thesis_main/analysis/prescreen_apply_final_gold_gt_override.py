from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.registry.perturbation_operators import (
    canonical_corners_to_runtime_pairs,
    ls_keypoints_to_canonical_corners,
)


DEFAULT_FINAL_GOLD = Path("analysis_results/final_gold_layer_20260325/final_gold_records_v1.jsonl")
DEFAULT_EXPORT_GT = Path("export_label/groudTruth.json")
DEFAULT_OUTPUT_DIR = Path("analysis_results/prescreen_closeout_gtfix_20260701")
DEFAULT_V2_OUTPUT_DIR = Path("analysis_results/prescreen_closeout_final_gold_v2_20260701")


def _safe(value: Any) -> str:
    return str(value or "").strip()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _task_value(task: dict[str, Any], key: str) -> str:
    data = task.get("data") if isinstance(task.get("data"), dict) else {}
    return _safe(task.get(key)) or _safe(data.get(key))


def _task_base_key(task: dict[str, Any]) -> str:
    data = task.get("data") if isinstance(task.get("data"), dict) else {}
    explicit = _safe(data.get("base_task_id")) or _safe(data.get("task_id"))
    if explicit:
        return explicit
    title = _safe(data.get("title"))
    return Path(title).stem if title else ""


def _find_gt_task(tasks: list[dict[str, Any]], task_id: str, inner_id: str) -> dict[str, Any]:
    matches = [task for task in tasks if _task_value(task, "id") == task_id]
    if len(matches) != 1:
        raise ValueError(f"expected one GT task id {task_id}, found {len(matches)}")
    task = matches[0]
    if inner_id and _task_value(task, "inner_id") != inner_id:
        raise ValueError(f"GT task {task_id} inner_id mismatch: expected {inner_id}, got {_task_value(task, 'inner_id')}")
    return task


def apply_gt_override(
    *,
    final_gold_jsonl: Path,
    export_gt_json: Path,
    output_dir: Path,
    final_gold_task_id: str,
    gt_task_id: str,
    gt_inner_id: str,
    expected_pair_count: int,
    expected_keypoint_count: int,
    final_gold_n_corners: int,
) -> dict[str, Path]:
    rows = _read_jsonl(final_gold_jsonl)
    gt_tasks = json.loads(export_gt_json.read_text(encoding="utf-8"))
    if not isinstance(gt_tasks, list):
        raise ValueError(f"{export_gt_json} is not a Label Studio task-list export")

    row_indexes = [index for index, row in enumerate(rows) if _safe(row.get("task_id")) == final_gold_task_id]
    if len(row_indexes) != 1:
        raise ValueError(f"expected one final gold task {final_gold_task_id}, found {len(row_indexes)}")
    row_index = row_indexes[0]
    old_row = rows[row_index]

    gt_task = _find_gt_task(gt_tasks, gt_task_id, gt_inner_id)
    gt_base_key = _task_base_key(gt_task)
    if _safe(old_row.get("base_task_id")) != gt_base_key:
        raise ValueError(f"base task mismatch for final gold {final_gold_task_id}: {_safe(old_row.get('base_task_id'))} != {gt_base_key}")

    annotations = gt_task.get("annotations") or []
    if len(annotations) != 1:
        raise ValueError(f"GT task {gt_task_id} expected one annotation, found {len(annotations)}")
    annotation = annotations[0]
    corners_norm, meta = ls_keypoints_to_canonical_corners(annotation.get("result") or [])
    if int(meta.get("n_keypoints", 0)) != int(expected_keypoint_count):
        raise ValueError(f"GT task {gt_task_id} keypoint count mismatch: {meta.get('n_keypoints')} != {expected_keypoint_count}")
    if len(corners_norm) != int(expected_pair_count):
        raise ValueError(f"GT task {gt_task_id} pair count mismatch: {len(corners_norm)} != {expected_pair_count}")
    if int(final_gold_n_corners) != len(corners_norm):
        raise ValueError(f"final_gold_n_corners mismatch: {final_gold_n_corners} != {len(corners_norm)}")

    new_row = dict(old_row)
    new_row["canonical_corners_norm"] = corners_norm
    new_row["runtime_pairs_1024x512"] = canonical_corners_to_runtime_pairs(corners_norm, 1024, 512)
    new_row["n_corners"] = int(final_gold_n_corners)
    new_row["pair_coverage"] = float(meta.get("pair_coverage", 0.0))
    notes = list(new_row.get("final_gold_notes") or [])
    if "gt106_geometry_override_20260701" not in notes:
        notes.append("gt106_geometry_override_20260701")
    new_row["final_gold_notes"] = notes
    rows[row_index] = new_row

    corrected_path = output_dir / "final_gold_records_v1_corrected.jsonl"
    audit_path = output_dir / "prescreen_final_gold_gt_override_audit.json"
    _write_jsonl(corrected_path, rows)

    old_pair_count = len(old_row.get("runtime_pairs_1024x512") or old_row.get("canonical_corners_norm") or [])
    new_pair_count = len(new_row["runtime_pairs_1024x512"])
    audit = {
        "status": "applied",
        "final_gold_task_id": final_gold_task_id,
        "gt_task_id": gt_task_id,
        "gt_inner_id": gt_inner_id,
        "gt_annotation_id": _safe(annotation.get("id")),
        "base_task_id": gt_base_key,
        "expected_pair_count": int(expected_pair_count),
        "expected_keypoint_count": int(expected_keypoint_count),
        "final_gold_n_corners": int(final_gold_n_corners),
        "old_564_pair_count": old_pair_count,
        "new_564_pair_count": new_pair_count,
        "old_564_keypoint_count": old_pair_count * 2,
        "new_564_keypoint_count": new_pair_count * 2,
        "source_final_gold_sha256": _sha256(final_gold_jsonl),
        "corrected_final_gold_sha256": _sha256(corrected_path),
        "export_gt_sha256": _sha256(export_gt_json),
    }
    _write_json(audit_path, audit)
    return {"corrected_final_gold_jsonl": corrected_path, "audit_json": audit_path}


def _single_final_gold_row(rows: list[dict[str, Any]], task_id: str) -> tuple[int, dict[str, Any]]:
    matches = [(index, row) for index, row in enumerate(rows) if _safe(row.get("task_id")) == task_id]
    if len(matches) != 1:
        raise ValueError(f"expected one final gold task {task_id}, found {len(matches)}")
    return matches[0]


def apply_final_gold_v2_corrections(
    *,
    final_gold_jsonl: Path,
    export_gt_json: Path,
    output_dir: Path,
) -> dict[str, Path]:
    rows = _read_jsonl(final_gold_jsonl)
    gt_tasks = json.loads(export_gt_json.read_text(encoding="utf-8"))
    if not isinstance(gt_tasks, list):
        raise ValueError(f"{export_gt_json} is not a Label Studio task-list export")

    index_564, old_564 = _single_final_gold_row(rows, "564")
    gt_task = _find_gt_task(gt_tasks, "2590", "106")
    if _safe(old_564.get("base_task_id")) != _task_base_key(gt_task):
        raise ValueError("base task mismatch for final gold 564")
    annotations = gt_task.get("annotations") or []
    if len(annotations) != 1:
        raise ValueError(f"GT task 2590 expected one annotation, found {len(annotations)}")
    corners_norm, meta = ls_keypoints_to_canonical_corners(annotations[0].get("result") or [])
    if int(meta.get("n_keypoints", 0)) != 8 or len(corners_norm) != 4:
        raise ValueError("GT106 correction must be 4 pairs / 8 keypoints")
    new_564 = dict(old_564)
    new_564["canonical_corners_norm"] = corners_norm
    new_564["runtime_pairs_1024x512"] = canonical_corners_to_runtime_pairs(corners_norm, 1024, 512)
    new_564["n_corners"] = 4
    new_564["pair_coverage"] = float(meta.get("pair_coverage", 0.0))
    notes_564 = list(new_564.get("final_gold_notes") or [])
    if "gt106_geometry_override_20260701" not in notes_564:
        notes_564.append("gt106_geometry_override_20260701")
    new_564["final_gold_notes"] = notes_564
    rows[index_564] = new_564

    index_696, old_696 = _single_final_gold_row(rows, "696")
    if _safe(old_696.get("base_task_id")) != "b8cTxDM8gDG_298a2386166a43c8a04e1c24433f7d15":
        raise ValueError("base task mismatch for final gold 696")
    new_696 = dict(old_696)
    new_696.update(
        {
            "final_scope_binary": "oos",
            "final_scope_subtype": "oos_insufficient",
            "final_scope_alias": "oos_insufficient",
            "geometry_gold_ready": False,
            "canonical_corners_norm": [],
            "runtime_pairs_1024x512": [],
            "n_corners": 0,
            "pair_coverage": 0.0,
        }
    )
    notes_696 = list(new_696.get("final_gold_notes") or [])
    if "task696_scope_override_oos_insufficient_20260701" not in notes_696:
        notes_696.append("task696_scope_override_oos_insufficient_20260701")
    new_696["final_gold_notes"] = notes_696
    rows[index_696] = new_696

    corrected_path = output_dir / "final_gold_records_v2_p1_closeout_corrected.jsonl"
    audit_path = output_dir / "prescreen_final_gold_v2_correction_audit.json"
    _write_jsonl(corrected_path, rows)
    old_564_pairs = len(old_564.get("runtime_pairs_1024x512") or old_564.get("canonical_corners_norm") or [])
    new_564_pairs = len(new_564["runtime_pairs_1024x512"])
    audit = {
        "status": "applied",
        "source_final_gold_sha256": _sha256(final_gold_jsonl),
        "corrected_final_gold_v2_sha256": _sha256(corrected_path),
        "corrections": [
            {
                "task_id": "564",
                "correction_type": "geometry_contract",
                "old_pair_count": old_564_pairs,
                "new_pair_count": new_564_pairs,
                "old_keypoint_count": old_564_pairs * 2,
                "new_keypoint_count": new_564_pairs * 2,
                "affected_runtime_tasks": ["3065", "3137"],
            },
            {
                "task_id": "696",
                "correction_type": "scope_contract",
                "old_final_scope_binary": _safe(old_696.get("final_scope_binary")),
                "old_final_scope_alias": _safe(old_696.get("final_scope_alias")),
                "new_final_scope_binary": "oos",
                "new_final_scope_subtype": "oos_insufficient",
                "new_final_scope_alias": "oos_insufficient",
                "old_geometry_gold_ready": bool(old_696.get("geometry_gold_ready")),
                "new_geometry_gold_ready": False,
                "affected_runtime_tasks": ["3077", "3149"],
            },
        ],
    }
    _write_json(audit_path, audit)
    return {"corrected_final_gold_v2_jsonl": corrected_path, "audit_json": audit_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--final-gold-jsonl", default=str(DEFAULT_FINAL_GOLD))
    parser.add_argument("--export-gt-json", default=str(DEFAULT_EXPORT_GT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--final-gold-task-id", default="564")
    parser.add_argument("--gt-task-id", default="2590")
    parser.add_argument("--gt-inner-id", default="106")
    parser.add_argument("--expected-pair-count", type=int, default=4)
    parser.add_argument("--expected-keypoint-count", type=int, default=8)
    parser.add_argument("--final-gold-n-corners", type=int, default=4)
    parser.add_argument("--consolidated-v2", action="store_true")
    args = parser.parse_args(argv)
    if args.consolidated_v2:
        outputs = apply_final_gold_v2_corrections(
            final_gold_jsonl=Path(args.final_gold_jsonl),
            export_gt_json=Path(args.export_gt_json),
            output_dir=Path(args.output_dir),
        )
        print(json.dumps({key: str(value) for key, value in outputs.items()}, ensure_ascii=False, indent=2))
        return 0
    outputs = apply_gt_override(
        final_gold_jsonl=Path(args.final_gold_jsonl),
        export_gt_json=Path(args.export_gt_json),
        output_dir=Path(args.output_dir),
        final_gold_task_id=args.final_gold_task_id,
        gt_task_id=args.gt_task_id,
        gt_inner_id=args.gt_inner_id,
        expected_pair_count=args.expected_pair_count,
        expected_keypoint_count=args.expected_keypoint_count,
        final_gold_n_corners=args.final_gold_n_corners,
    )
    print(json.dumps({key: str(value) for key, value in outputs.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
