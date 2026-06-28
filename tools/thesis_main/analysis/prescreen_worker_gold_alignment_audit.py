from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

DEFAULT_CANONICAL = Path("analysis_results/prescreen_closeout/prescreen_canonical_annotations.csv")
DEFAULT_GOLD_STATUS = Path("analysis_results/prescreen_closeout/prescreen_gold_status_audit.csv")
DEFAULT_FINAL_GOLD = Path("analysis_results/final_gold_layer_20260325/final_gold_records_v1.jsonl")
DEFAULT_SYNTHETIC_GT = Path("analysis_results/prescreen_closeout/prescreen_synthetic_geometry_gt_binding_audit.csv")
DEFAULT_SCOPE_SUMMARY = Path("analysis_results/prescreen_closeout/prescreen_scope_summary.json")
DEFAULT_OUTPUT_DIR = Path("analysis_results/prescreen_closeout")

UNDER_RATIO = 0.75
OVER_RATIO = 1.25

AUDIT_FIELDS = [
    "annotator_id",
    "task_id",
    "project_id",
    "dataset_group",
    "condition",
    "reference_type",
    "reference_validation_status",
    "worker_geometry_valid",
    "worker_n_corners",
    "reference_n_corners",
    "corner_count_delta",
    "worker_bbox_area",
    "reference_bbox_area",
    "bbox_area_ratio_to_reference",
    "worker_polygon_area_proxy",
    "reference_polygon_area_proxy",
    "polygon_area_ratio_to_reference",
    "alignment_available",
    "alignment_block_reason",
    "gold_alignment_bucket",
    "undercoverage_candidate_flag",
    "overcoverage_candidate_flag",
    "manual_review_required",
    "dry_run",
    "notes",
]


def _safe(value: Any) -> str:
    return str(value or "").strip()


def _truthy(value: Any) -> bool:
    return _safe(value).lower() in {"1", "true", "yes", "y"}


def _load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"missing required input: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=AUDIT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _load_final_gold(path: Path) -> dict[str, list[dict[str, Any]]]:
    if not path.exists():
        raise FileNotFoundError(f"missing required input: {path}")
    out: dict[str, list[dict[str, Any]]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            for key in ("task_id", "base_task_id"):
                value = _safe(rec.get(key))
                if value:
                    out.setdefault(f"{key}:{value}", []).append(rec)
    return out


def _load_source_gt_from_scope_summary(path: Path | None) -> dict[str, list[tuple[float, float]]]:
    if not path or not path.exists():
        return {}
    summary = json.loads(path.read_text(encoding="utf-8"))
    snapshot = Path(_safe(summary.get("export_gt_snapshot_path")))
    if not snapshot.exists():
        return {}
    data = json.loads(snapshot.read_text(encoding="utf-8"))
    out: dict[str, list[tuple[float, float]]] = {}
    for task in data if isinstance(data, list) else []:
        anns = task.get("annotations") or []
        if len(anns) != 1:
            continue
        pts: list[tuple[float, float]] = []
        for item in anns[0].get("result") or []:
            value = item.get("value") or {}
            if "x" in value and "y" in value:
                pts.append((float(value["x"]) * 1024.0 / 100.0, float(value["y"]) * 512.0 / 100.0))
        if pts:
            out[_safe(task.get("id"))] = pts
    return out


def _reference_keys(ref: str) -> list[str]:
    ref = _safe(ref)
    if not ref:
        return []
    if ":" in ref:
        return [ref]
    return [f"task_id:{ref}", f"base_task_id:{ref}"]


def _points_from_worker(row: dict[str, str]) -> tuple[list[tuple[float, float]], str]:
    if _safe(row.get("parse_error")):
        return [], "worker_geometry_parse_error"
    raw = _safe(row.get("canonical_geometry"))
    if not raw:
        return [], "worker_geometry_missing"
    try:
        pts = [(float(p[0]), float(p[1])) for p in json.loads(raw)]
    except (TypeError, ValueError, json.JSONDecodeError, IndexError):
        return [], "worker_geometry_parse_error"
    return (pts, "") if pts else ([], "worker_geometry_missing")


def _points_from_final_gold(rec: dict[str, Any]) -> tuple[list[tuple[float, float]], str]:
    pairs = rec.get("runtime_pairs_1024x512")
    if isinstance(pairs, list) and pairs:
        try:
            pts = []
            for pair in pairs:
                x = float(pair["x"])
                pts.append((x, float(pair["y_ceiling"])))
                pts.append((x, float(pair["y_floor"])))
            return pts, ""
        except (KeyError, TypeError, ValueError):
            return [], "reference_geometry_parse_error"
    corners = rec.get("canonical_corners_norm")
    if isinstance(corners, list) and corners:
        try:
            pts = []
            for corner in corners:
                x = float(corner["x_pct"]) * 1024.0 / 100.0
                pts.append((x, float(corner["y_top_pct"]) * 512.0 / 100.0))
                pts.append((x, float(corner["y_bottom_pct"]) * 512.0 / 100.0))
            return pts, ""
        except (KeyError, TypeError, ValueError):
            return [], "reference_geometry_parse_error"
    return [], "reference_geometry_parse_error"


def _points_from_jsonish(value: str) -> tuple[list[tuple[float, float]], str]:
    if not _safe(value):
        return [], "reference_missing"
    try:
        data = json.loads(value)
        if isinstance(data, dict):
            data = data.get("points") or data.get("corners") or []
        return [(float(p[0]), float(p[1])) for p in data], ""
    except (TypeError, ValueError, json.JSONDecodeError, IndexError):
        return [], "reference_geometry_parse_error"


def _reference_points(
    gold: dict[str, str],
    final_gold: dict[str, list[dict[str, Any]]],
    synthetic_by_task: dict[str, dict[str, str]],
    source_gt: dict[str, list[tuple[float, float]]],
) -> tuple[list[tuple[float, float]], str, str]:
    validation = _safe(gold.get("validation_status"))
    if validation == "external_source_gt_checked":
        synth = synthetic_by_task.get(_safe(gold.get("task_id")), {})
        for field in ("reference_geometry", "reference_corners_json", "canonical_geometry", "geometry_corners_json"):
            pts, reason = _points_from_jsonish(_safe(synth.get(field)))
            if pts or reason != "reference_missing":
                return pts, reason, "synthetic_source_gt"
        source_pts = source_gt.get(_safe(gold.get("geometry_gold_task_id")))
        if source_pts:
            return source_pts, "", "synthetic_source_gt"
        return [], "reference_missing", "synthetic_source_gt"
    matches: list[dict[str, Any]] = []
    for key in _reference_keys(_safe(gold.get("geometry_gold_task_id"))):
        matches.extend(final_gold.get(key, []))
    if len(matches) != 1:
        return [], "reference_missing", "final_gold"
    pts, reason = _points_from_final_gold(matches[0])
    return pts, reason, "final_gold"


def _bbox_area(points: list[tuple[float, float]]) -> float:
    if not points:
        return 0.0
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return max(0.0, max(xs) - min(xs)) * max(0.0, max(ys) - min(ys))


def _area_proxy(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    cx = sum(x for x, _ in points) / len(points)
    cy = sum(y for _, y in points) / len(points)
    ordered = sorted(points, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ordered, ordered[1:] + ordered[:1]))) / 2.0


def _ratio(num: float, den: float) -> str:
    return "" if den <= 0 else f"{num / den:.6g}"


def _bucket(worker_reason: str, ref_reason: str, ratio: str, corner_delta: int) -> tuple[str, bool, bool, bool]:
    if ref_reason:
        return ref_reason, False, False, True
    if worker_reason:
        return worker_reason, False, False, True
    value = float(ratio) if ratio else 0.0
    if value < UNDER_RATIO:
        return "possible_undercoverage", True, False, True
    if value > OVER_RATIO:
        return "possible_overcoverage", False, True, True
    if corner_delta:
        return "corner_count_mismatch", False, False, True
    return "reference_ready_geometry_present", False, False, False


def build_worker_gold_alignment_audit(
    canonical_csv: Path,
    gold_status_csv: Path,
    final_gold_jsonl: Path,
    synthetic_geometry_csv: Path,
    scope_summary_json: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    canonical = _load_csv(canonical_csv)
    gold_rows = _load_csv(gold_status_csv)
    synthetic = _load_csv(synthetic_geometry_csv)
    final_gold = _load_final_gold(final_gold_jsonl)
    source_gt = _load_source_gt_from_scope_summary(scope_summary_json)

    ready_gold = {
        _safe(row.get("task_id")): row
        for row in gold_rows
        if _safe(row.get("gold_status_for_alignment")) == "ready_for_alignment"
        and _safe(row.get("gold_status_for_undercoverage")) == "ready_for_undercoverage_audit"
        and _safe(row.get("validation_status")) in {"final_gold_geometry_checked", "external_source_gt_checked"}
    }
    synthetic_by_task = {_safe(row.get("runtime_task_id")): row for row in synthetic}
    rows: list[dict[str, Any]] = []
    for worker in canonical:
        task_id = _safe(worker.get("task_id"))
        gold = ready_gold.get(task_id)
        if not gold:
            continue
        worker_pts, worker_reason = _points_from_worker(worker)
        ref_pts, ref_reason, reference_type = _reference_points(gold, final_gold, synthetic_by_task, source_gt)
        worker_bbox = _bbox_area(worker_pts)
        ref_bbox = _bbox_area(ref_pts)
        worker_poly = _area_proxy(worker_pts)
        ref_poly = _area_proxy(ref_pts)
        bbox_ratio = _ratio(worker_bbox, ref_bbox)
        poly_ratio = _ratio(worker_poly, ref_poly)
        corner_delta = len(worker_pts) - len(ref_pts)
        bucket, under, over, review = _bucket(worker_reason, ref_reason, bbox_ratio, corner_delta)
        alignment_available = not worker_reason and not ref_reason
        rows.append(
            {
                "annotator_id": _safe(worker.get("annotator_id")),
                "task_id": task_id,
                "project_id": _safe(worker.get("project_id")),
                "dataset_group": _safe(worker.get("dataset_group")),
                "condition": _safe(worker.get("condition")),
                "reference_type": reference_type,
                "reference_validation_status": _safe(gold.get("validation_status")),
                "worker_geometry_valid": bool(worker_pts) and not worker_reason,
                "worker_n_corners": len(worker_pts),
                "reference_n_corners": len(ref_pts),
                "corner_count_delta": corner_delta,
                "worker_bbox_area": f"{worker_bbox:.6g}" if worker_pts else "",
                "reference_bbox_area": f"{ref_bbox:.6g}" if ref_pts else "",
                "bbox_area_ratio_to_reference": bbox_ratio,
                "worker_polygon_area_proxy": f"{worker_poly:.6g}" if worker_pts else "",
                "reference_polygon_area_proxy": f"{ref_poly:.6g}" if ref_pts else "",
                "polygon_area_ratio_to_reference": poly_ratio,
                "alignment_available": alignment_available,
                "alignment_block_reason": worker_reason or ref_reason,
                "gold_alignment_bucket": bucket,
                "undercoverage_candidate_flag": under,
                "overcoverage_candidate_flag": over,
                "manual_review_required": review,
                "dry_run": True,
                "notes": "dry-run proxy alignment only; no geometry score or worker decision",
            }
        )
    summary = {
        "dry_run": True,
        "rows": len(rows),
        "alignment_available_count": sum(bool(row["alignment_available"]) for row in rows),
        "gold_alignment_bucket_counts": dict(Counter(str(row["gold_alignment_bucket"]) for row in rows)),
        "reference_validation_status_counts": dict(Counter(str(row["reference_validation_status"]) for row in rows)),
        "undercoverage_candidate_count": sum(bool(row["undercoverage_candidate_flag"]) for row in rows),
        "overcoverage_candidate_count": sum(bool(row["overcoverage_candidate_flag"]) for row in rows),
        "forbidden_outputs_generated": False,
        "forbidden_metric_field_count": sum(1 for row in rows for key in row if "score" in key.lower()),
    }
    return rows, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-csv", default=str(DEFAULT_CANONICAL))
    parser.add_argument("--gold-status-csv", default=str(DEFAULT_GOLD_STATUS))
    parser.add_argument("--final-gold-jsonl", default=str(DEFAULT_FINAL_GOLD))
    parser.add_argument("--synthetic-geometry-csv", default=str(DEFAULT_SYNTHETIC_GT))
    parser.add_argument("--scope-summary-json", default=str(DEFAULT_SCOPE_SUMMARY))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)
    rows, summary = build_worker_gold_alignment_audit(
        Path(args.canonical_csv),
        Path(args.gold_status_csv),
        Path(args.final_gold_jsonl),
        Path(args.synthetic_geometry_csv),
        Path(args.scope_summary_json) if args.scope_summary_json else None,
    )
    out_dir = Path(args.output_dir)
    audit_path = out_dir / "prescreen_worker_gold_alignment_audit.csv"
    summary_path = out_dir / "prescreen_worker_gold_alignment_summary.json"
    _write_csv(audit_path, rows)
    summary.update({"worker_gold_alignment_audit_csv": str(audit_path), "worker_gold_alignment_summary_json": str(summary_path)})
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
