from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DRY_RUN_FLAGS = {
    "dry_run_only": "true",
    "no_C2_freeze_yet": "true",
    "tau_d_not_final": "true",
    "not_thesis_facing_artifact": "true",
    "do_not_use_for_split": "true",
}
FORBIDDEN_PREANNOTATION_FIELDS = {
    "difficulty",
    "model_issue",
    "lead_time",
    "active_time",
    "manual_review_label",
    "manual_review_notes",
    "annotator_id",
    "completed_by",
    "worker_id",
}
HARD_REASON_CODES = (
    "polygon_missing",
    "polygon_construction_failure",
    "self_intersection_or_invalid_polygon",
    "topology_pairing_failure",
    "invalid_corner_count",
)
SOFT_REASON_CODES = (
    "high_keypoint_count",
    "high_polygon_point_count",
    "duplicated_corner_cluster",
    "abnormal_polygon_area",
    "oversegmentation_candidate",
)
REVIEW_LABELS = (
    "likely_structural_risk",
    "likely_prediction_artifact",
    "likely_visual_domain_shift",
    "likely_oos_or_boundary_ambiguous",
    "likely_easy_false_positive",
    "unclear",
)
G_BUCKETS = (
    "hard_prediction_failure",
    "soft_prediction_complexity",
    "nominal_prediction_structure",
    "render_or_prediction_missing",
    "manual_review_needed",
)
OUTPUT_COLUMNS = (
    "dry_run_only",
    "no_C2_freeze_yet",
    "tau_d_not_final",
    "not_thesis_facing_artifact",
    "do_not_use_for_split",
    "task_id",
    "base_task_id",
    "image_path",
    "image_url",
    "render_status",
    "prediction_status",
    "prediction_model_version",
    "keypoint_count",
    "polygon_point_count",
    "polygon_area_pct2",
    "duplicate_corner_pair_count",
    "g_score_raw",
    "g_bucket",
    "g_hard_failure_flag",
    "g_complexity_flag",
    "g_reason_codes",
    "legacy_risk_score",
    "legacy_primary_bucket",
    "manual_review_label",
    "manual_review_notes",
)


@dataclass
class ParsedTask:
    task_id: str
    base_task_id: str
    image_url: str
    image_path: Path | None
    prediction_model_version: str
    prediction_status: str
    keypoints: list[tuple[float, float]]
    polygon: list[tuple[float, float]]
    forbidden_field_hits: Counter[str]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def current_date_slug() -> str:
    return datetime.now().strftime("%Y%m%d")


def _stringify(value: Any) -> str:
    return "" if value is None else str(value)


def _contains_forbidden_fields(payload: Any) -> Counter[str]:
    hits: Counter[str] = Counter()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in FORBIDDEN_PREANNOTATION_FIELDS:
                hits[key] += 1
            hits.update(_contains_forbidden_fields(value))
    elif isinstance(payload, list):
        for item in payload:
            hits.update(_contains_forbidden_fields(item))
    return hits


def _iter_tasks(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("tasks", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError("input JSON must be a Label Studio task list or contain a task list")


def _resolve_image_path(image_url: str, image_root: Path) -> Path | None:
    text = image_url.strip()
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme in {"http", "https"}:
        path_text = unquote(parsed.path).lstrip("/")
        if path_text.startswith("data/"):
            return PROJECT_ROOT / path_text
        return image_root / Path(path_text).name
    path = Path(text)
    if path.is_absolute():
        return path
    return image_root / path


def _prediction_from_task(task: dict[str, Any]) -> dict[str, Any] | None:
    annotations = task.get("annotations")
    if isinstance(annotations, list):
        for annotation in annotations:
            if isinstance(annotation, dict) and isinstance(annotation.get("prediction"), dict):
                return annotation["prediction"]
    predictions = task.get("predictions")
    if isinstance(predictions, list):
        for prediction in predictions:
            if isinstance(prediction, dict):
                return prediction
    prediction = task.get("prediction")
    if isinstance(prediction, dict):
        return prediction
    return None


def _extract_prediction_geometry(prediction: dict[str, Any] | None) -> tuple[str, str, list[tuple[float, float]], list[tuple[float, float]]]:
    if not isinstance(prediction, dict):
        return "missing", "", [], []
    results = prediction.get("result")
    if not isinstance(results, list):
        return "missing_result", _stringify(prediction.get("model_version")), [], []

    keypoints: list[tuple[float, float]] = []
    polygon: list[tuple[float, float]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        value = item.get("value")
        if not isinstance(value, dict):
            continue
        item_type = item.get("type")
        if item_type == "keypointlabels" and "x" in value and "y" in value:
            try:
                keypoints.append((float(value["x"]), float(value["y"])))
            except (TypeError, ValueError):
                continue
        elif item_type == "polygonlabels" and isinstance(value.get("points"), list):
            points: list[tuple[float, float]] = []
            for point in value["points"]:
                if not isinstance(point, (list, tuple)) or len(point) < 2:
                    continue
                try:
                    points.append((float(point[0]), float(point[1])))
                except (TypeError, ValueError):
                    continue
            if points and not polygon:
                polygon = points
    return "ok", _stringify(prediction.get("model_version")), keypoints, polygon


def parse_task(task: dict[str, Any], image_root: Path) -> ParsedTask:
    data = task.get("data") if isinstance(task.get("data"), dict) else {}
    image_url = _stringify(data.get("image") or task.get("image") or "")
    title = _stringify(data.get("title") or Path(urlparse(image_url).path).name)
    prediction = _prediction_from_task(task)
    prediction_status, model_version, keypoints, polygon = _extract_prediction_geometry(prediction)

    return ParsedTask(
        task_id=_stringify(task.get("id") or task.get("task_id") or title),
        base_task_id=Path(title).stem if title else _stringify(task.get("id") or task.get("task_id")),
        image_url=image_url,
        image_path=_resolve_image_path(image_url, image_root),
        prediction_model_version=model_version,
        prediction_status=prediction_status,
        keypoints=keypoints,
        polygon=polygon,
        forbidden_field_hits=_contains_forbidden_fields(task),
    )


def polygon_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    total = 0.0
    for idx, (x1, y1) in enumerate(points):
        x2, y2 = points[(idx + 1) % len(points)]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def _orientation(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)
    return (o1 * o2 < 0) and (o3 * o4 < 0)


def has_self_intersection(points: list[tuple[float, float]]) -> bool:
    if len(points) < 4:
        return False
    n = len(points)
    for i in range(n):
        a = points[i]
        b = points[(i + 1) % n]
        for j in range(i + 1, n):
            if abs(i - j) <= 1 or {i, j} == {0, n - 1}:
                continue
            c = points[j]
            d = points[(j + 1) % n]
            if _segments_intersect(a, b, c, d):
                return True
    return False


def count_duplicate_corner_pairs(points: list[tuple[float, float]], *, tolerance: float = 1.0) -> int:
    count = 0
    for i, left in enumerate(points):
        for right in points[i + 1 :]:
            if math.dist(left, right) <= tolerance:
                count += 1
    return count


def topology_pairing_failure(keypoints: list[tuple[float, float]], *, x_tolerance: float = 0.75) -> bool:
    if not keypoints:
        return False
    if len(keypoints) % 2 != 0:
        return True
    groups: list[list[tuple[float, float]]] = []
    for point in sorted(keypoints, key=lambda item: item[0]):
        if not groups or abs(groups[-1][0][0] - point[0]) > x_tolerance:
            groups.append([point])
        else:
            groups[-1].append(point)
    return any(len(group) != 2 for group in groups)


def check_render_status(image_path: Path | None) -> tuple[str, int, int]:
    if image_path is None:
        return "missing_image_path", 0, 0
    if not image_path.exists():
        return "image_not_found", 0, 0
    try:
        from PIL import Image

        with Image.open(image_path) as image:
            return "ok", int(image.width), int(image.height)
    except Exception:  # noqa: BLE001
        return "render_failure", 0, 0


def compute_diagnostics(parsed: ParsedTask) -> dict[str, Any]:
    render_status, _, _ = check_render_status(parsed.image_path)
    keypoint_count = len(parsed.keypoints)
    polygon_point_count = len(parsed.polygon)
    area = polygon_area(parsed.polygon)
    duplicate_count = count_duplicate_corner_pairs(parsed.keypoints)

    hard_flags = {
        "polygon_missing": parsed.prediction_status == "ok" and not parsed.polygon,
        "polygon_construction_failure": bool(parsed.polygon) and polygon_point_count < 3,
        "self_intersection_or_invalid_polygon": bool(parsed.polygon) and (area <= 1e-6 or has_self_intersection(parsed.polygon)),
        "topology_pairing_failure": topology_pairing_failure(parsed.keypoints),
        "invalid_corner_count": keypoint_count > 0 and (keypoint_count < 4 or keypoint_count % 2 != 0),
    }
    soft_flags = {
        "high_keypoint_count": keypoint_count > 12,
        "high_polygon_point_count": polygon_point_count > 120,
        "duplicated_corner_cluster": duplicate_count > 0,
        "abnormal_polygon_area": bool(parsed.polygon) and (area < 250.0 or area > 7500.0),
        "oversegmentation_candidate": keypoint_count > 12 and polygon_point_count > 120,
    }

    hard_reasons = [key for key in HARD_REASON_CODES if hard_flags[key]]
    soft_reasons = [key for key in SOFT_REASON_CODES if soft_flags[key]]
    missing_flag = render_status != "ok" or parsed.prediction_status != "ok"
    if missing_flag:
        g_bucket = "render_or_prediction_missing"
    elif hard_reasons:
        g_bucket = "hard_prediction_failure"
    elif soft_reasons:
        g_bucket = "soft_prediction_complexity"
    else:
        g_bucket = "nominal_prediction_structure"

    legacy_risk_score = 0
    if hard_flags["self_intersection_or_invalid_polygon"]:
        legacy_risk_score += 3
    if hard_flags["topology_pairing_failure"]:
        legacy_risk_score += 2
    if soft_flags["duplicated_corner_cluster"]:
        legacy_risk_score += 1
    if soft_flags["high_keypoint_count"]:
        legacy_risk_score += 1

    if missing_flag:
        legacy_primary_bucket = "render_or_prediction_missing"
    elif hard_flags["self_intersection_or_invalid_polygon"]:
        legacy_primary_bucket = "self_intersection_or_invalid_polygon"
    elif hard_flags["topology_pairing_failure"]:
        legacy_primary_bucket = "topology_pairing_failure"
    elif soft_flags["duplicated_corner_cluster"]:
        legacy_primary_bucket = "duplicated_corner_cluster"
    elif soft_flags["high_keypoint_count"]:
        legacy_primary_bucket = "high_complexity_prediction"
    else:
        legacy_primary_bucket = "nominal_prediction_structure"

    reason_codes = hard_reasons + soft_reasons
    g_score_raw = len(soft_reasons) + 10 * len(hard_reasons)
    return {
        **DRY_RUN_FLAGS,
        "task_id": parsed.task_id,
        "base_task_id": parsed.base_task_id,
        "image_path": str(parsed.image_path or ""),
        "image_url": parsed.image_url,
        "render_status": render_status,
        "prediction_status": parsed.prediction_status,
        "prediction_model_version": parsed.prediction_model_version,
        "keypoint_count": keypoint_count,
        "polygon_point_count": polygon_point_count,
        "polygon_area_pct2": round(area, 6),
        "duplicate_corner_pair_count": duplicate_count,
        "g_score_raw": g_score_raw,
        "g_bucket": g_bucket,
        "g_hard_failure_flag": str(bool(hard_reasons)).lower(),
        "g_complexity_flag": str(bool(soft_reasons)).lower(),
        "g_reason_codes": ";".join(reason_codes),
        "legacy_risk_score": legacy_risk_score,
        "legacy_primary_bucket": legacy_primary_bucket,
        "manual_review_label": "",
        "manual_review_notes": "",
        "_keypoints": parsed.keypoints,
        "_polygon": parsed.polygon,
        "_forbidden_field_hits": dict(parsed.forbidden_field_hits),
    }


def write_csv(path: Path, rows: list[dict[str, Any]], columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _draw_overlay(draw: Any, tile_size: tuple[int, int], keypoints: list[tuple[float, float]], polygon: list[tuple[float, float]]) -> None:
    width, height = tile_size
    if polygon:
        scaled = [(x / 100.0 * width, y / 100.0 * height) for x, y in polygon]
        draw.line(scaled + [scaled[0]], fill=(255, 165, 0), width=2)
    for x, y in keypoints:
        px = x / 100.0 * width
        py = y / 100.0 * height
        draw.ellipse((px - 3, py - 3, px + 3, py + 3), fill=(220, 20, 60), outline=(255, 255, 255))


def write_contact_sheet(path: Path, rows: list[dict[str, Any]], *, title: str, max_items: int = 30) -> None:
    if not rows:
        return
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Pillow is required to write contact sheets") from exc

    shown = rows[:max_items]
    tile_w, image_h, label_h = 320, 160, 62
    tile_h = image_h + label_h
    cols = 5
    rows_n = math.ceil(len(shown) / cols)
    sheet = Image.new("RGB", (cols * tile_w, rows_n * tile_h + 32), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()
    draw.text((8, 8), title, fill=(0, 0, 0), font=font)

    for idx, row in enumerate(shown):
        col = idx % cols
        row_i = idx // cols
        x0 = col * tile_w
        y0 = 32 + row_i * tile_h
        image_path = Path(str(row.get("image_path") or ""))
        try:
            with Image.open(image_path) as image:
                image = image.convert("RGB")
                image.thumbnail((tile_w, image_h))
                canvas = Image.new("RGB", (tile_w, image_h), (245, 245, 245))
                offset = ((tile_w - image.width) // 2, (image_h - image.height) // 2)
                canvas.paste(image, offset)
        except Exception:  # noqa: BLE001
            canvas = Image.new("RGB", (tile_w, image_h), (230, 230, 230))
        overlay = ImageDraw.Draw(canvas)
        _draw_overlay(overlay, (tile_w, image_h), row.get("_keypoints", []), row.get("_polygon", []))
        sheet.paste(canvas, (x0, y0))
        label = (
            f"{row['task_id']} {row['g_bucket']}\n"
            f"g={row['g_score_raw']} legacy={row['legacy_risk_score']} "
            f"kp={row['keypoint_count']} poly={row['polygon_point_count']}\n"
            f"{row['g_reason_codes'][:58]}"
        )
        draw.text((x0 + 4, y0 + image_h + 4), label, fill=(0, 0, 0), font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


def build_report(
    *,
    input_path: Path,
    output_dir: Path,
    rows: list[dict[str, Any]],
    ignored_fields: Counter[str],
    contact_sheets: list[Path],
) -> str:
    bucket_counts = Counter(str(row["g_bucket"]) for row in rows)
    reason_counts: Counter[str] = Counter()
    for row in rows:
        for reason in str(row["g_reason_codes"]).split(";"):
            if reason:
                reason_counts[reason] += 1

    lines = [
        "# g_t Diagnostic Dry-Run Report",
        "",
        f"Generated at: {utc_now_iso()}",
        "",
        "## Status flags",
        "",
    ]
    lines.extend(f"- `{key}={value}`" for key, value in DRY_RUN_FLAGS.items())
    lines.extend(
        [
            "",
            "## Scope",
            "",
            "- This is an exploratory dry-run for prediction-side structural diagnostics.",
            "- It is not a formal `g_t` rule, not a V1 artifact, not a routing artifact, and not a split source.",
            "- `d_t` and `g_t` remain separate proxies: `d_t` is feature-space shift, while this `g_t` dry-run is prediction-side structural diagnostics.",
            "- `legacy_risk_score` is retained only as an old baseline field and is not the main explanation.",
            "- Manual review labels are only for visual sanity check and must not be used for split, `tau_d`, K, q, embedding layer, H admission, `g_t` freeze, or routing.",
            "- `difficulty`, `model_issue`, `lead_time`, `active_time`, worker labels, and manual review fields are not used as pre-annotation risk inputs.",
            "",
            "## Input",
            "",
            f"- Source JSON: `{input_path}`",
            f"- Parsed tasks: {len(rows)}",
            "",
            "## Bucket counts",
            "",
        ]
    )
    lines.extend(f"- `{bucket}`: {bucket_counts.get(bucket, 0)}" for bucket in G_BUCKETS)
    lines.extend(["", "## Reason counts", ""])
    for reason in HARD_REASON_CODES + SOFT_REASON_CODES:
        lines.append(f"- `{reason}`: {reason_counts.get(reason, 0)}")
    lines.extend(["", "## Ignored forbidden-field audit", ""])
    if ignored_fields:
        lines.extend(f"- `{key}`: {value}" for key, value in sorted(ignored_fields.items()))
    else:
        lines.append("- none detected")
    lines.extend(["", "## Outputs", ""])
    lines.append(f"- Sample manifest: `{output_dir / 'g_t_diagnostic_sample_manifest.csv'}`")
    lines.append(f"- Manual review template: `{output_dir / 'manual_g_t_review_template.csv'}`")
    for sheet in contact_sheets:
        lines.append(f"- Contact sheet: `{sheet}`")
    lines.extend(
        [
            "",
            "## Formal-use prohibition",
            "",
            "Do not use this dry-run to define formal Validation_OOD, define Hard subset H, initialize V1 assignment, freeze `tau_d`, freeze `g_t`, create task-risk manifest, or update routing contract.",
            "",
            "## Manual review labels",
            "",
        ]
    )
    lines.extend(f"- `{label}`" for label in REVIEW_LABELS)
    return "\n".join(lines) + "\n"


def run_dryrun(input_json: Path, output_dir: Path, *, image_root: Path, max_per_sheet: int = 30) -> dict[str, Any]:
    payload = json.loads(input_json.read_text(encoding="utf-8"))
    tasks = _iter_tasks(payload)
    rows: list[dict[str, Any]] = []
    ignored_fields: Counter[str] = Counter()
    for task in tasks:
        parsed = parse_task(task, image_root)
        row = compute_diagnostics(parsed)
        ignored_fields.update(row.pop("_forbidden_field_hits"))
        rows.append(row)

    rows.sort(key=lambda item: (-int(item["g_score_raw"]), str(item["g_bucket"]), str(item["task_id"])))
    manifest_path = output_dir / "g_t_diagnostic_sample_manifest.csv"
    review_path = output_dir / "manual_g_t_review_template.csv"
    write_csv(manifest_path, rows, OUTPUT_COLUMNS)
    write_csv(review_path, rows, OUTPUT_COLUMNS)

    contact_dir = output_dir / "contact_sheets"
    sheets = [
        (
            "contact_sheet_hard_prediction_failure.png",
            "g_t hard prediction failure",
            [row for row in rows if row["g_bucket"] == "hard_prediction_failure"],
        ),
        (
            "contact_sheet_soft_prediction_complexity.png",
            "g_t soft prediction complexity",
            [row for row in rows if row["g_bucket"] == "soft_prediction_complexity"],
        ),
        (
            "contact_sheet_nominal_prediction.png",
            "g_t nominal prediction",
            [row for row in rows if row["g_bucket"] == "nominal_prediction_structure"],
        ),
        (
            "contact_sheet_highest_g_score.png",
            "g_t highest raw diagnostic score",
            rows,
        ),
    ]
    written_sheets: list[Path] = []
    for filename, title, sheet_rows in sheets:
        if sheet_rows:
            path = contact_dir / filename
            write_contact_sheet(path, sheet_rows, title=title, max_items=max_per_sheet)
            written_sheets.append(path)

    report = build_report(
        input_path=input_json,
        output_dir=output_dir,
        rows=rows,
        ignored_fields=ignored_fields,
        contact_sheets=written_sheets,
    )
    report_path = output_dir / "g_t_diagnostic_dryrun_report.md"
    report_path.write_text(report, encoding="utf-8")
    summary_path = output_dir / "g_t_diagnostic_dryrun_summary.json"
    summary = {
        "flags": DRY_RUN_FLAGS,
        "generated_at": utc_now_iso(),
        "source_json": str(input_json),
        "n_tasks": len(rows),
        "bucket_counts": dict(Counter(str(row["g_bucket"]) for row in rows)),
        "ignored_forbidden_fields": dict(ignored_fields),
        "outputs": {
            "sample_manifest": str(manifest_path),
            "manual_review_template": str(review_path),
            "report": str(report_path),
            "contact_sheets": [str(path) for path in written_sheets],
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Exploratory dry-run for prediction-side g_t diagnostics.")
    parser.add_argument("--input-json", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--image-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--max-per-sheet", type=int, default=30)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_dir = args.output_dir or PROJECT_ROOT / "analysis_results" / f"g_t_diagnostic_dryrun_{current_date_slug()}"
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dryrun(args.input_json, output_dir, image_root=args.image_root, max_per_sheet=args.max_per_sheet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
