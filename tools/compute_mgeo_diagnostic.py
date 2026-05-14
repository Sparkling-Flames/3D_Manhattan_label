"""Offline audit-only Manhattan geometry diagnostic.

This CLI computes a post-hoc M_geo sidecar and worker-level summary from a
minimal JSONL geometry export. It intentionally does not integrate with the
formal P1/C1/C2/T1/V1 contracts, routing, Label Studio UI, or production
assignment/import artifacts.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Iterable


GEOMETRY_DIAG_VERSION = "mgeo_mvp_v1"
EPS = 1e-9


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def _scope_is_in_scope(value: Any) -> bool:
    if value is None:
        return False
    norm = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return norm in {"in_scope", "inscope"}


def _base_output(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": row.get("task_id"),
        "worker_id": row.get("worker_id"),
        "submission_id": row.get("submission_id"),
        "geometry_diag_valid": False,
        "geometry_diag_exclusion_reason": None,
        "mgeo_vertical_residual": None,
        "mgeo_manhattan_angle_residual": None,
        "mgeo_height_residual": None,
        "mgeo_renderability_flag": None,
        "mgeo_snap_residual": None,
        "mgeo_composite_residual": None,
        "geometry_diag_version": GEOMETRY_DIAG_VERSION,
    }


def _exclude(row: dict[str, Any], reason: str) -> dict[str, Any]:
    out = _base_output(row)
    out["geometry_diag_exclusion_reason"] = reason
    return out


def _points_close(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return abs(a[0] - b[0]) <= EPS and abs(a[1] - b[1]) <= EPS


def _parse_corners(raw: Any) -> tuple[list[tuple[float, float]], float | None, str | None]:
    if raw is None:
        return [], None, "missing_geometry"
    if not isinstance(raw, list) or not raw:
        return [], None, "unparseable_geometry"

    points: list[tuple[float, float]] = []
    vertical_offsets: list[float] = []

    for item in raw:
        if isinstance(item, dict):
            x = _as_float(item.get("x"))
            y = _as_float(item.get("y"))
            if x is not None and y is not None:
                points.append((x, y))
                continue

            x_floor = _as_float(item.get("x_floor", item.get("floor_x", item.get("x"))))
            y_floor = _as_float(item.get("y_floor", item.get("floor_y")))
            x_ceil = _as_float(item.get("x_ceiling", item.get("ceiling_x", item.get("x"))))
            y_ceil = _as_float(item.get("y_ceiling", item.get("ceiling_y")))
            if x_floor is not None and y_floor is not None:
                points.append((x_floor, y_floor))
                if x_ceil is not None and y_ceil is not None:
                    vertical_offsets.append(abs(x_floor - x_ceil))
                continue
            return [], None, "unparseable_geometry"

        if isinstance(item, (list, tuple)) and len(item) >= 2:
            x = _as_float(item[0])
            y = _as_float(item[1])
            if x is not None and y is not None:
                points.append((x, y))
                continue
            return [], None, "unparseable_geometry"

        return [], None, "unparseable_geometry"

    if len(points) >= 2 and _points_close(points[0], points[-1]):
        points = points[:-1]

    if len(points) < 4:
        return [], None, "unparseable_geometry"

    vertical_residual = None
    if vertical_offsets:
        xs = [p[0] for p in points]
        scale = max(max(xs) - min(xs), 1.0)
        vertical_residual = sum(vertical_offsets) / len(vertical_offsets) / scale

    return points, vertical_residual, None


def _polygon_area(points: list[tuple[float, float]]) -> float:
    area = 0.0
    for idx, (x1, y1) in enumerate(points):
        x2, y2 = points[(idx + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _orientation(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> bool:
    return (
        min(a[0], c[0]) - EPS <= b[0] <= max(a[0], c[0]) + EPS
        and min(a[1], c[1]) - EPS <= b[1] <= max(a[1], c[1]) + EPS
        and abs(_orientation(a, b, c)) <= EPS
    )


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

    if o1 * o2 < -EPS and o3 * o4 < -EPS:
        return True
    if abs(o1) <= EPS and _on_segment(a, c, b):
        return True
    if abs(o2) <= EPS and _on_segment(a, d, b):
        return True
    if abs(o3) <= EPS and _on_segment(c, a, d):
        return True
    if abs(o4) <= EPS and _on_segment(c, b, d):
        return True
    return False


def _polygon_is_simple(points: list[tuple[float, float]]) -> bool:
    n_points = len(points)
    for i in range(n_points):
        a = points[i]
        b = points[(i + 1) % n_points]
        for j in range(i + 1, n_points):
            if abs(i - j) <= 1:
                continue
            if i == 0 and j == n_points - 1:
                continue
            c = points[j]
            d = points[(j + 1) % n_points]
            if _segments_intersect(a, b, c, d):
                return False
    return True


def _edge_lengths_and_angles(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    edges: list[tuple[float, float]] = []
    for idx, (x1, y1) in enumerate(points):
        x2, y2 = points[(idx + 1) % len(points)]
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length > EPS:
            edges.append((length, math.atan2(dy, dx) % math.pi))
    return edges


def _angle_distance_mod_pi(a: float, b: float) -> float:
    return abs((a - b + math.pi / 2.0) % math.pi - math.pi / 2.0)


def _manhattan_angle_residual(points: list[tuple[float, float]]) -> float | None:
    edges = _edge_lengths_and_angles(points)
    if len(edges) < 4:
        return None

    base_angle = max(edges, key=lambda item: item[0])[1]
    weighted_error = 0.0
    total_length = 0.0
    for length, angle in edges:
        parallel_error = _angle_distance_mod_pi(angle, base_angle)
        orthogonal_error = _angle_distance_mod_pi(angle, base_angle + math.pi / 2.0)
        weighted_error += min(parallel_error, orthogonal_error) * length
        total_length += length

    if total_length <= EPS:
        return None
    return math.degrees(weighted_error / total_length)


def _height_residual(row: dict[str, Any]) -> float | None:
    raw = row.get("room_height", row.get("room_heights", row.get("height_values")))
    if raw is None:
        return None
    if isinstance(raw, list):
        values = [value for value in (_as_float(item) for item in raw) if value is not None and value > 0]
        if len(values) < 2:
            return 0.0 if len(values) == 1 else None
        mean_value = sum(values) / len(values)
        if mean_value <= EPS:
            return None
        variance = sum((value - mean_value) ** 2 for value in values) / len(values)
        return math.sqrt(variance) / mean_value
    value = _as_float(raw)
    if value is None or value <= 0:
        return None
    return 0.0


def _composite_residual(
    angle_residual: float | None,
    vertical_residual: float | None,
    height_residual: float | None,
) -> float | None:
    components: list[float] = []
    if angle_residual is not None:
        components.append(min(max(angle_residual / 45.0, 0.0), 1.0))
    if vertical_residual is not None:
        components.append(min(max(vertical_residual, 0.0), 1.0))
    if height_residual is not None:
        components.append(min(max(height_residual, 0.0), 1.0))
    if not components:
        return None
    return sum(components) / len(components)


def diagnose_submission(row: dict[str, Any]) -> dict[str, Any]:
    """Compute one audit-only M_geo sidecar row."""
    if not _scope_is_in_scope(row.get("scope")):
        return _exclude(row, "scope_not_in_scope")
    if not _as_bool(row.get("manhattan_assumable")):
        return _exclude(row, "not_manhattan_assumable")

    raw_geometry = row.get("layout_corners", row.get("corners"))
    points, vertical_residual, parse_error = _parse_corners(raw_geometry)
    if parse_error is not None:
        return _exclude(row, parse_error)

    out = _base_output(row)
    out["mgeo_vertical_residual"] = vertical_residual

    if _polygon_area(points) <= EPS or not _polygon_is_simple(points):
        out["geometry_diag_exclusion_reason"] = "invalid_polygon"
        out["mgeo_renderability_flag"] = False
        return out

    angle_residual = _manhattan_angle_residual(points)
    height_residual = _height_residual(row)

    out["geometry_diag_valid"] = True
    out["mgeo_renderability_flag"] = True
    out["mgeo_manhattan_angle_residual"] = angle_residual
    out["mgeo_height_residual"] = height_residual
    out["mgeo_snap_residual"] = None
    out["mgeo_composite_residual"] = _composite_residual(
        angle_residual=angle_residual,
        vertical_residual=vertical_residual,
        height_residual=height_residual,
    )
    return out


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[int(position)]
    fraction = position - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def summarize_workers(sidecar_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in sidecar_rows:
        grouped[row.get("worker_id")].append(row)

    summaries: list[dict[str, Any]] = []
    for worker_id in sorted(grouped, key=lambda value: "" if value is None else str(value)):
        rows = grouped[worker_id]
        valid_rows = [row for row in rows if row.get("geometry_diag_valid") is True]
        composite_values = [
            row["mgeo_composite_residual"]
            for row in valid_rows
            if isinstance(row.get("mgeo_composite_residual"), (int, float))
        ]
        summaries.append(
            {
                "worker_id": worker_id,
                "n_total_submissions": len(rows),
                "n_geometry_diag_valid": len(valid_rows),
                "n_geometry_diag_excluded": len(rows) - len(valid_rows),
                "mgeo_median": median(composite_values) if composite_values else None,
                "mgeo_p90": _percentile(composite_values, 0.9),
                "mgeo_invalid_render_count": sum(row.get("mgeo_renderability_flag") is False for row in rows),
                "geometry_diag_version": GEOMETRY_DIAG_VERSION,
            }
        )
    return summaries


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL row") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"{path}:{line_number}: row must be a JSON object")
            rows.append(payload)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def write_summary(path: Path, worker_summaries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "geometry_diag_version": GEOMETRY_DIAG_VERSION,
        "score_contract": "audit/sensitivity only; not annotation correctness, routing, or formal g_t",
        "workers": worker_summaries,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Input JSONL, one row per task/worker/submission.")
    parser.add_argument("--output", required=True, type=Path, help="Output sidecar JSONL path.")
    parser.add_argument("--summary", required=True, type=Path, help="Output worker summary JSON path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    input_rows = read_jsonl(args.input)
    sidecar_rows = [diagnose_submission(row) for row in input_rows]
    write_jsonl(args.output, sidecar_rows)
    write_summary(args.summary, summarize_workers(sidecar_rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

