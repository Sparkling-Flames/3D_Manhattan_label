"""Generate M15.19 local 3D projection metrics and a read-only review page."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.manhattan_3d_projection import (  # noqa: E402
    DEFAULT_CAMERA_HEIGHT,
    PROJECTION_SCHEMA_VERSION,
    compute_all_geometry_metrics,
    project_layout_to_3d,
)
from tools.paper_a_manhattan.run_single_image_manhattan_assist import (  # noqa: E402
    build_single_image_assist,
)


REVIEW_SCHEMA_VERSION = "local_3d_projection_review_m15_19_v1"
SAFETY_BOUNDARY = {
    "expert_side": True,
    "offline_local_only": True,
    "dry_run_only": True,
    "annotation_write_allowed": False,
    "annotation_patch_generated": False,
    "automatic_optimization": False,
    "automatic_reorder_merge_delete": False,
    "worker_facing": False,
    "formal_artifact": False,
}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_image(payload: Mapping[str, Any]) -> str | None:
    for key in ("source_image", "image", "image_url"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    data = payload.get("data")
    if isinstance(data, Mapping):
        value = data.get("image")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _source_basename(source: str | None) -> str | None:
    if not source:
        return None
    parsed = urlparse(source)
    candidate = parsed.path if parsed.scheme else source
    basename = Path(unquote(candidate)).name
    return basename or None


def _image_resolution(path: Path) -> dict[str, int] | None:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return {"width": int(image.width), "height": int(image.height)}
    except (ImportError, OSError, ValueError):
        return None


def resolve_local_image(
    payload: Mapping[str, Any],
    *,
    image_root: Path | None = None,
    image_path: Path | None = None,
) -> tuple[dict[str, Any], Path | None]:
    """Resolve a local panorama without making any network request."""

    source = _source_image(payload)
    basename = _source_basename(source)
    method = "unresolved"
    resolved: Path | None = None
    warnings: list[str] = []

    if image_path is not None:
        method = "explicit_image_path"
        candidate = image_path.expanduser().resolve()
        if candidate.is_file():
            resolved = candidate
        else:
            warnings.append("explicit_image_path_not_found")
    elif image_root is not None and basename:
        root = image_root.expanduser().resolve()
        direct = root / basename
        if direct.is_file():
            method = "image_root_basename"
            resolved = direct
        elif root.is_dir():
            matches = list(root.rglob(basename))
            if matches:
                method = "image_root_recursive_basename"
                resolved = matches[0].resolve()
                if len(matches) > 1:
                    warnings.append("multiple_local_images_match_basename_first_used")
            else:
                method = "image_root_basename_not_found"
                warnings.append("texture_unavailable_local_image_not_found")
        else:
            method = "image_root_not_found"
            warnings.append("image_root_not_found")
    else:
        warnings.append(
            "texture_unavailable_no_image_path_or_resolvable_image_root_basename"
        )

    exists = resolved is not None and resolved.is_file()
    public_path: str | None = None
    if exists and resolved is not None:
        if image_root is not None:
            try:
                public_path = resolved.relative_to(image_root.expanduser().resolve()).as_posix()
            except ValueError:
                public_path = resolved.name
        else:
            public_path = resolved.name
    info: dict[str, Any] = {
        "source_image": source,
        "source_image_basename": basename,
        "resolution_method": method,
        "image_path": public_path,
        "image_exists": exists,
        "image_sha256": _sha256(resolved) if exists and resolved else None,
        "image_mtime": (
            dt.datetime.fromtimestamp(resolved.stat().st_mtime, tz=dt.timezone.utc).isoformat()
            if exists and resolved
            else None
        ),
        "image_resolution": _image_resolution(resolved) if exists and resolved else None,
        "warnings": warnings,
        "network_access_used": False,
    }
    return info, resolved


def _mapping_lookup(payload: Mapping[str, Any]) -> dict[int, int]:
    rows = payload.get("pair_index_mapping")
    if not isinstance(rows, list):
        return {}
    output: dict[int, int] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        try:
            output[int(row["effective_pair_index"])] = int(
                row["source_preview_order_index"]
            )
        except (KeyError, TypeError, ValueError):
            continue
    return output


def extract_ordered_pairs(payload: Mapping[str, Any]) -> tuple[list[dict[str, Any]], str]:
    """Extract current effective order while preserving expert-verified topology."""

    if isinstance(payload.get("ordered_pairs"), list):
        pairs = copy.deepcopy(payload["ordered_pairs"])
        source = "input.ordered_pairs"
        mapping = _mapping_lookup(payload)
    else:
        assist = build_single_image_assist(payload)
        pairs = copy.deepcopy(assist.get("ordered_pairs", []))
        source = "build_single_image_assist.ordered_pairs"
        mapping = _mapping_lookup(assist)
    if not pairs:
        raise ValueError("input did not yield any effective ordered pairs")
    for index, pair in enumerate(pairs, start=1):
        if not isinstance(pair, dict):
            raise ValueError(f"ordered pair {index} must be an object")
        pair.setdefault("effective_pair_index", index)
        if mapping.get(index) is not None:
            pair.setdefault("source_preview_order_index", mapping[index])
    return pairs, source


def _candidate_lists(payload: Mapping[str, Any]) -> list[Sequence[Any]]:
    lists: list[Sequence[Any]] = []
    for key in ("recommendations", "candidate_rows", "local_dense_corner_probe_rows"):
        value = payload.get(key)
        if isinstance(value, list):
            lists.append(value)
    verified = payload.get("verified_3d_local_assist")
    if isinstance(verified, Mapping):
        for key in ("candidate_rows", "local_dense_corner_probe_rows"):
            value = verified.get(key)
            if isinstance(value, list):
                lists.append(value)
    return lists


def extract_candidate_rows(payload: Mapping[str, Any], *, limit: int = 3) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    mapping = _mapping_lookup(payload)
    for candidate_list in _candidate_lists(payload):
        for row in candidate_list:
            if not isinstance(row, Mapping):
                continue
            if row.get("recommendation_eligible") is not True:
                continue
            if row.get("probe_mode") != "align_then_translate_column":
                continue
            targets = row.get("target_pair_indices")
            target = row.get("effective_pair_index")
            if target is None and isinstance(targets, list) and len(targets) == 1:
                target = targets[0]
            try:
                target_int = int(target)
            except (TypeError, ValueError):
                continue
            key = (
                target_int,
                row.get("top_x_after"),
                row.get("bottom_x_after"),
                row.get("top_y_after"),
                row.get("bottom_y_after"),
            )
            if key in seen:
                continue
            seen.add(key)
            materialized = dict(row)
            materialized["effective_pair_index"] = target_int
            materialized.setdefault("source_preview_order_index", mapping.get(target_int))
            rows.append(materialized)
            if len(rows) >= limit:
                return rows
    return rows


def extract_candidate_rows_from_report(path: Path, *, limit: int = 3) -> list[dict[str, Any]]:
    """Best-effort fallback for the Human Action Summary when JSON is unavailable."""

    text = path.read_text(encoding="utf-8")
    sections = re.split(r"(?=^### Candidate \d+:)", text, flags=re.MULTILINE)[1:]
    rows: list[dict[str, Any]] = []
    number = r"([-+]?\d+(?:\.\d+)?)"
    for section in sections:
        if "align-then-translate column" not in section:
            continue
        effective = re.search(r"effective_pair_index:\s*(\d+)", section)
        source = re.search(r"source_preview_order_index:\s*(\d+)", section)
        top_x = re.search(rf"top_x:\s*{number}\s*->\s*{number}", section)
        bottom_x = re.search(rf"bottom_x:\s*{number}\s*->\s*{number}", section)
        top_y = re.search(rf"top_y:\s*{number}\s*->\s*{number}", section)
        bottom_y = re.search(rf"bottom_y:\s*{number}\s*->\s*{number}", section)
        if not all((effective, top_x, bottom_x, top_y, bottom_y)):
            continue
        rows.append(
            {
                "effective_pair_index": int(effective.group(1)),
                "source_preview_order_index": int(source.group(1)) if source else None,
                "probe_mode": "align_then_translate_column",
                "recommendation_eligible": True,
                "top_x_before": float(top_x.group(1)),
                "top_x_after": float(top_x.group(2)),
                "bottom_x_before": float(bottom_x.group(1)),
                "bottom_x_after": float(bottom_x.group(2)),
                "top_y_before": float(top_y.group(1)),
                "top_y_after": float(top_y.group(2)),
                "bottom_y_before": float(bottom_y.group(1)),
                "bottom_y_after": float(bottom_y.group(2)),
                "candidate_source": "candidate_report_human_action_summary",
            }
        )
        if len(rows) >= limit:
            break
    return rows


def apply_candidate_row(
    ordered_pairs: Sequence[Mapping[str, Any]], row: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Apply one review row to a copy; never mutate or reorder the original."""

    output = copy.deepcopy(list(ordered_pairs))
    target = int(row["effective_pair_index"])
    if not 1 <= target <= len(output):
        raise ValueError(f"candidate target pair {target} is outside 1..{len(output)}")
    pair = output[target - 1]
    top = pair.get("top")
    bottom = pair.get("bottom")
    if not isinstance(top, dict) or not isinstance(bottom, dict):
        raise ValueError("candidate application requires top/bottom ordered-pair shape")
    top["x"] = float(row["top_x_after"])
    bottom["x"] = float(row["bottom_x_after"])
    if row.get("top_y_after") is not None:
        top["y"] = float(row["top_y_after"])
    if row.get("bottom_y_after") is not None:
        bottom["y"] = float(row["bottom_y_after"])
    pair["effective_pair_index"] = target
    if row.get("source_preview_order_index") is not None:
        pair["source_preview_order_index"] = int(row["source_preview_order_index"])
    return output


def _summary(
    projection: Mapping[str, Any],
    metrics: Mapping[str, Any],
    candidate_row: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    pairs = projection["pairs"]
    floor = metrics["floorprint"]["summary"]
    corner = metrics["corner_turns"]["summary"]
    heights = metrics["heights"]["summary"]
    dense_rows = metrics["dense_pairs"]["pairs"]
    dense = [row for row in dense_rows if row["classification"] != "not_dense_2d"]
    target_dense: Mapping[str, Any] | None = None
    if candidate_row is not None:
        dense_indices = candidate_row.get("dense_pair_indices")
        if isinstance(dense_indices, list) and len(dense_indices) == 2:
            try:
                target_set = {int(value) for value in dense_indices}
            except (TypeError, ValueError):
                target_set = set()
            target_dense = next(
                (
                    row
                    for row in dense_rows
                    if {int(row["pair_i"]), int(row["pair_j"])} == target_set
                ),
                None,
            )
    return {
        "wall_residual_sum_deg": floor.get("wall_residual_sum_deg"),
        "corner_residual_sum_deg": corner.get("corner_residual_sum_deg"),
        "height_residual_sum": heights.get("height_residual_sum"),
        "vertical_x_residual_sum": sum(
            float(pair["top_bottom_x_residual"]) for pair in pairs
        ),
        "minimum_dense_floor_3d_separation": (
            float(target_dense["floor_3d_separation"])
            if target_dense is not None
            else (
                min(float(row["floor_3d_separation"]) for row in dense)
                if dense
                else None
            )
        ),
        "minimum_wall_length": floor.get("minimum_wall_length"),
        "short_wall_count": floor.get("short_wall_count"),
        "self_intersection": floor.get("self_intersection"),
        "warnings": list(projection.get("warnings", [])),
    }


def _delta(before: Any, after: Any) -> float | None:
    if before is None or after is None or isinstance(before, bool) or isinstance(after, bool):
        return None
    return float(after) - float(before)


def _summary_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    numeric = (
        "wall_residual_sum_deg",
        "corner_residual_sum_deg",
        "height_residual_sum",
        "vertical_x_residual_sum",
        "minimum_dense_floor_3d_separation",
        "minimum_wall_length",
        "short_wall_count",
    )
    before_warnings = set(before.get("warnings", []))
    after_warnings = set(after.get("warnings", []))
    return {
        **{key: _delta(before.get(key), after.get(key)) for key in numeric},
        "self_intersection_before": before.get("self_intersection"),
        "self_intersection_after": after.get("self_intersection"),
        "warnings_introduced": sorted(after_warnings - before_warnings),
        "warnings_resolved": sorted(before_warnings - after_warnings),
    }


def _before_after_delta(before: Any, after: Any) -> dict[str, Any]:
    return {"before": before, "after": after, "delta": _delta(before, after)}


def _metric_comparison(
    original: Mapping[str, Any],
    candidate: Mapping[str, Any],
    row: Mapping[str, Any],
) -> dict[str, Any]:
    before = original["summary"]
    after = candidate["summary"]
    dense_before = row.get(
        "dense_pair_bev_separation_before",
        before.get("minimum_dense_floor_3d_separation"),
    )
    dense_after = row.get(
        "dense_pair_bev_separation_after",
        after.get("minimum_dense_floor_3d_separation"),
    )
    return {
        "wall_residual_sum_deg": _before_after_delta(
            before.get("wall_residual_sum_deg"), after.get("wall_residual_sum_deg")
        ),
        "corner_residual_sum_deg": _before_after_delta(
            before.get("corner_residual_sum_deg"),
            after.get("corner_residual_sum_deg"),
        ),
        "height_residual_sum": _before_after_delta(
            before.get("height_residual_sum"), after.get("height_residual_sum")
        ),
        "pair_vertical_x_residual": _before_after_delta(
            row.get("vertical_x_residual_before"),
            row.get("vertical_x_residual_after"),
        ),
        "dense_floor_3d_separation": _before_after_delta(dense_before, dense_after),
        "short_wall_length": _before_after_delta(
            before.get("minimum_wall_length"), after.get("minimum_wall_length")
        ),
        "self_intersection": {
            "before": before.get("self_intersection"),
            "after": after.get("self_intersection"),
            "changed": before.get("self_intersection") != after.get("self_intersection"),
        },
        "warnings": {
            "introduced": sorted(
                set(after.get("warnings", [])) - set(before.get("warnings", []))
            ),
            "resolved": sorted(
                set(before.get("warnings", [])) - set(after.get("warnings", []))
            ),
        },
    }


def build_projection_variant(
    name: str,
    ordered_pairs: Sequence[Mapping[str, Any]],
    *,
    width: int,
    height: int,
    coordinate_mode: str,
    camera_height: float,
    candidate_row: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    projection = project_layout_to_3d(
        ordered_pairs, width, height, coordinate_mode, camera_height
    )
    metrics = compute_all_geometry_metrics(projection)
    return {
        "name": name,
        "candidate_row": dict(candidate_row) if candidate_row else None,
        "ordered_pairs": copy.deepcopy(list(ordered_pairs)),
        "projection": projection,
        "metrics": metrics,
        "summary": _summary(projection, metrics, candidate_row),
    }


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return f"{float(value):.{digits}f}"
    return str(value)


def _pair_height(variant: Mapping[str, Any], pair_index: int) -> Mapping[str, Any] | None:
    for row in variant["metrics"]["heights"]["pairs"]:
        if int(row["effective_pair_index"]) == pair_index:
            return row
    return None


def _wall_residual(variant: Mapping[str, Any], from_pair: int, to_pair: int) -> float | None:
    for row in variant["metrics"]["floorprint"]["walls"]:
        if int(row["from_pair"]) == from_pair and int(row["to_pair"]) == to_pair:
            return float(row["angle_residual_deg"])
    return None


def render_markdown_report(payload: Mapping[str, Any]) -> str:
    provenance = payload["input_provenance"]
    image_info = provenance["image"]
    variants = payload["variants"]
    original = variants[0]
    lines = [
        "# Local 3D Projection Review",
        "",
        "## Input Provenance",
        "",
        f"- Review schema: `{payload['schema_version']}`",
        f"- Projection schema: `{PROJECTION_SCHEMA_VERSION}`",
        f"- Input file: `{provenance['input_file']}`",
        f"- Input SHA-256: `{provenance['input_sha256']}`",
        f"- Ordered-pair source: `{provenance['ordered_pair_source']}`",
        f"- coordinate_mode requested/effective: `{payload['coordinate_mode_requested']}` / `{original['projection']['coordinate_mode']}`",
        f"- W / H / CAM_H: `{payload['width']}` / `{payload['height']}` / `{payload['camera_height']}`",
        f"- Image source basename: `{image_info.get('source_image_basename')}`",
        f"- Local image: `{image_info.get('image_path')}`",
        f"- Image exists: `{image_info.get('image_exists')}`",
        f"- Image SHA-256: `{image_info.get('image_sha256')}`",
        "- Network access used: `False`",
        "",
        "## Human Review Summary",
        "",
        "Local-only diagnostic. No annotation changes are produced.",
        "",
    ]
    candidates = variants[1:]
    if not candidates:
        lines.extend(
            [
                "No eligible align-then-translate candidate was supplied. Review covers original geometry only.",
                "",
            ]
        )
    for index, candidate in enumerate(candidates, start=1):
        row = candidate["candidate_row"]
        target = int(row["effective_pair_index"])
        source = row.get("source_preview_order_index")
        before_height = _pair_height(original, target)
        after_height = _pair_height(candidate, target)
        previous_pair = target - 1
        next_pair = target + 1
        next_next_pair = target + 2
        previous_wall_before = _wall_residual(original, previous_pair, target)
        previous_wall_after = _wall_residual(candidate, previous_pair, target)
        next_wall_before = _wall_residual(original, target, next_pair)
        next_wall_after = _wall_residual(candidate, target, next_pair)
        neighbor_wall_after = _wall_residual(candidate, next_pair, next_next_pair)
        local_before = sum(
            value for value in (previous_wall_before, next_wall_before) if value is not None
        )
        local_after = sum(
            value for value in (previous_wall_after, next_wall_after) if value is not None
        )
        lines.extend(
            [
                f"Candidate {index} changes effective pair {target} / source preview order {source}:",
                f"- top_x: {_fmt(row.get('top_x_before'))} -> {_fmt(row.get('top_x_after'))}",
                f"- bottom_x: {_fmt(row.get('bottom_x_before'))} -> {_fmt(row.get('bottom_x_after'))}",
                f"- top_y: {_fmt(row.get('top_y_before'))} -> {_fmt(row.get('top_y_after'))}",
                f"- bottom_y: {_fmt(row.get('bottom_y_before'))} -> {_fmt(row.get('bottom_y_after'))}",
                "",
                "Metric effect:",
                f"- vertical_x_residual: {_fmt(row.get('vertical_x_residual_before'))} -> {_fmt(row.get('vertical_x_residual_after'))}",
                f"- wall residual sum: {_fmt(original['summary']['wall_residual_sum_deg'])} -> {_fmt(candidate['summary']['wall_residual_sum_deg'])}",
                f"- corner residual sum: {_fmt(original['summary']['corner_residual_sum_deg'])} -> {_fmt(candidate['summary']['corner_residual_sum_deg'])}",
                f"- pair {target} wall_height / height residual: {_fmt(after_height.get('wall_height') if after_height else None)} / {_fmt(after_height.get('height_residual') if after_height else None)} (before {_fmt(before_height.get('wall_height') if before_height else None)} / {_fmt(before_height.get('height_residual') if before_height else None)})",
                f"- wall {previous_pair}-{target} residual: {_fmt(previous_wall_before)} -> {_fmt(previous_wall_after)}",
                f"- wall {target}-{next_pair} residual: {_fmt(next_wall_before)} -> {_fmt(next_wall_after)}",
                f"- wall {next_pair}-{next_next_pair} residual after: {_fmt(neighbor_wall_after)}",
                "",
                "Interpretation:",
                (
                    f"- {previous_pair}-{target}-{next_pair} improves in projection-space wall residual ({_fmt(local_before)} -> {_fmt(local_after)}), but this is not correctness evidence."
                    if local_after < local_before
                    else f"- {previous_pair}-{target}-{next_pair} does not show a lower combined projection-space wall residual."
                ),
                f"- If pair {target} height residual becomes worse or looks visually low, do not accept directly.",
                (
                    f"- {next_pair}-{next_next_pair}-{next_next_pair + 1} remains unresolved because wall {next_pair}-{next_next_pair} is above the {15:.0f}° review threshold; inspect that neighbor window instead of repeatedly moving pair {target}."
                    if neighbor_wall_after is not None and neighbor_wall_after > 15.0
                    else "- Inspect the next neighbor window before accepting a single-pair change."
                ),
                "",
            ]
        )

    lines.extend(["## Candidate Metric Summary", ""])
    lines.extend(
        [
            "| variant | wall residual sum | corner residual sum | height residual sum | vertical x residual sum | min wall | self-intersection |",
            "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for variant in variants:
        summary = variant["summary"]
        lines.append(
            "| {name} | {wall} | {corner} | {height} | {vertical} | {minimum} | {intersection} |".format(
                name=variant["name"],
                wall=_fmt(summary["wall_residual_sum_deg"]),
                corner=_fmt(summary["corner_residual_sum_deg"]),
                height=_fmt(summary["height_residual_sum"]),
                vertical=_fmt(summary["vertical_x_residual_sum"]),
                minimum=_fmt(summary["minimum_wall_length"]),
                intersection=summary["self_intersection"],
            )
        )

    for variant in variants:
        lines.extend(["", f"## Pair 3D Coordinates — {variant['name']}", ""])
        lines.extend(
            [
                "| pair | source order | floor (x,y,z) | ceiling (x,y,z) | wall height | height residual | clamp warnings |",
                "| ---: | ---: | --- | --- | ---: | ---: | --- |",
            ]
        )
        height_lookup = {
            int(row["effective_pair_index"]): row
            for row in variant["metrics"]["heights"]["pairs"]
        }
        for pair in variant["projection"]["pairs"]:
            floor = pair["floor_3d"]
            ceiling = pair["ceiling_3d"]
            height_row = height_lookup[int(pair["effective_pair_index"])]
            lines.append(
                "| {pair} | {source} | ({fx}, {fy}, {fz}) | ({cx}, {cy}, {cz}) | {height} | {residual} | {warnings} |".format(
                    pair=pair["effective_pair_index"],
                    source=pair.get("source_preview_order_index"),
                    fx=_fmt(floor["x"]),
                    fy=_fmt(floor["y"]),
                    fz=_fmt(floor["z"]),
                    cx=_fmt(ceiling["x"]),
                    cy=_fmt(ceiling["y"]),
                    cz=_fmt(ceiling["z"]),
                    height=_fmt(pair["wall_height"]),
                    residual=_fmt(height_row["height_residual"]),
                    warnings=", ".join(pair["warnings"]) or "none",
                )
            )
        lines.extend(["", f"## Wall Metrics — {variant['name']}", ""])
        lines.extend(
            [
                "| wall | from-to | length | direction | nearest axis | residual | short |",
                "| ---: | --- | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for wall in variant["metrics"]["floorprint"]["walls"]:
            lines.append(
                f"| {wall['wall_index']} | {wall['from_pair']}-{wall['to_pair']} | {_fmt(wall['floor_wall_length'])} | {_fmt(wall['direction_deg'])} | {_fmt(wall['nearest_manhattan_axis_deg'])} | {_fmt(wall['angle_residual_deg'])} | {wall['short_wall']} |"
            )
        lines.extend(["", f"## Corner Metrics — {variant['name']}", ""])
        lines.extend(
            [
                "| pair | prev wall | next wall | turn angle | residual to 90 | warning |",
                "| ---: | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for corner in variant["metrics"]["corner_turns"]["corners"]:
            lines.append(
                f"| {corner['corner_pair_index']} | {corner['prev_wall_index']} | {corner['next_wall_index']} | {_fmt(corner['turn_angle_deg'])} | {_fmt(corner['angle_to_90_residual_deg'])} | {corner['warning_far_from_90']} |"
            )

    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "This report is expert-side, offline, local-only, sidecar, and dry-run only. It does not edit annotations, optimize coordinates, reorder corners, score workers, or create formal experiment artifacts.",
            "",
        ]
    )
    return "\n".join(lines)


def _relative_asset_url(target: Path, out_dir: Path, local_server_root: Path | None) -> str | None:
    target = target.resolve()
    out_dir = out_dir.resolve()
    if local_server_root is not None:
        root = local_server_root.resolve()
        try:
            target.relative_to(root)
            out_dir.relative_to(root)
        except ValueError:
            return None
    try:
        return Path(os.path.relpath(target, out_dir)).as_posix()
    except ValueError:
        # Windows cannot form a relative path across drive letters.  This is
        # still local-only; localhost serving should instead use a common root.
        return target.as_uri()


def render_review_html(
    payload: Mapping[str, Any],
    *,
    viewer_url: str,
    image_url: str | None,
) -> str:
    minimal_variants = []
    for variant in payload["variants"]:
        corners = [
            {
                "x": pair["normalized"]["x"],
                "y_ceiling": pair["normalized"]["top_y"],
                "y_floor": pair["normalized"]["bottom_y"],
            }
            for pair in variant["projection"]["pairs"]
        ]
        minimal_variants.append(
            {"name": variant["name"], "corners": corners, "summary": variant["summary"]}
        )
    data = {
        "width": payload["width"],
        "height": payload["height"],
        "imageUrl": image_url,
        "variants": minimal_variants,
        "provenance": {
            "input": payload["input_provenance"]["input_file"],
            "inputSha256": payload["input_provenance"]["input_sha256"],
            "imageSha256": payload["input_provenance"]["image"].get("image_sha256"),
            "coordinateMode": payload["variants"][0]["projection"]["coordinate_mode"],
        },
    }
    encoded = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    safe_viewer = html.escape(viewer_url, quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Local 3D Projection Review</title>
  <style>
    :root {{ color-scheme: dark; font-family: system-ui, sans-serif; }}
    body {{ margin:0; background:#0b1020; color:#e5e7eb; }}
    header {{ padding:12px 16px; border-bottom:1px solid #334155; display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
    button, select {{ padding:7px 10px; border-radius:6px; border:1px solid #475569; background:#172033; color:#fff; }}
    button {{ cursor:pointer; }}
    #warning {{ color:#fbbf24; font-size:13px; }}
    main {{ display:grid; grid-template-columns:minmax(0,1fr) 310px; min-height:calc(100vh - 58px); }}
    #views {{ display:grid; grid-template-columns:1fr; gap:8px; padding:8px; }}
    #views.side {{ grid-template-columns:1fr 1fr; }}
    iframe {{ width:100%; min-height:620px; border:1px solid #334155; border-radius:8px; background:#111; }}
    #right-view {{ display:none; }}
    #views.side #right-view {{ display:block; }}
    aside {{ padding:14px; border-left:1px solid #334155; background:#111827; overflow:auto; }}
    pre {{ white-space:pre-wrap; overflow-wrap:anywhere; font-size:12px; }}
    .muted {{ color:#94a3b8; font-size:12px; }}
  </style>
</head>
<body>
  <header>
    <strong>M15.19 Local 3D Review</strong>
    <label>Variant <select id="variant"></select></label>
    <button id="side" type="button">Side-by-side</button>
    <button id="labels" type="button">Hide labels</button>
    <span id="warning"></span>
  </header>
  <main>
    <section id="views">
      <iframe id="left-view" title="selected geometry" src="{safe_viewer}"></iframe>
      <iframe id="right-view" title="original geometry" src="{safe_viewer}"></iframe>
    </section>
    <aside>
      <h3>Metric summary</h3><pre id="metrics"></pre>
      <h3>Provenance</h3><pre id="provenance"></pre>
      <p class="muted">Read-only local diagnostic. If a texture is blocked under file://, run <code>python -m http.server &lt;repo_or_review_root&gt;</code> and open this page through localhost.</p>
    </aside>
  </main>
  <script>
    const REVIEW = {encoded};
    const select = document.getElementById('variant');
    const views = document.getElementById('views');
    const left = document.getElementById('left-view');
    const right = document.getElementById('right-view');
    const metrics = document.getElementById('metrics');
    let labelsVisible = true;
    REVIEW.variants.forEach((variant, index) => {{
      const option = document.createElement('option'); option.value = index; option.textContent = variant.name; select.appendChild(option);
    }});
    if (!REVIEW.imageUrl) document.getElementById('warning').textContent = 'Texture unavailable; geometry remains reviewable.';
    function sendLayout(frame, variant) {{
      if (!frame.contentWindow) return;
      frame.contentWindow.postMessage({{
        type: 'update_layout', corners: variant.corners, baseCorners: variant.corners,
        previewOrder: variant.corners.map((_, i) => i), previewOrderActive: true,
        preserveOrder: true, width: REVIEW.width, height: REVIEW.height,
        imageUrl: REVIEW.imageUrl, previewSignature: 'm15-19-' + variant.name
      }}, '*');
      frame.contentWindow.postMessage({{type:'set_label_visibility', visible:labelsVisible}}, '*');
    }}
    function refresh() {{
      const selected = REVIEW.variants[Number(select.value || 0)];
      sendLayout(left, selected); sendLayout(right, REVIEW.variants[0]);
      metrics.textContent = JSON.stringify(selected.summary, null, 2);
    }}
    left.addEventListener('load', refresh); right.addEventListener('load', refresh); select.addEventListener('change', refresh);
    document.getElementById('side').addEventListener('click', () => {{ views.classList.toggle('side'); refresh(); }});
    document.getElementById('labels').addEventListener('click', (event) => {{
      labelsVisible = !labelsVisible; event.currentTarget.textContent = labelsVisible ? 'Hide labels' : 'Show labels'; refresh();
    }});
    document.getElementById('provenance').textContent = JSON.stringify(REVIEW.provenance, null, 2);
    setTimeout(refresh, 300);
  </script>
</body>
</html>
"""


def run_local_review(
    *,
    input_path: Path,
    out_dir: Path,
    image_root: Path | None = None,
    image_path: Path | None = None,
    candidate_json: Path | None = None,
    candidate_report: Path | None = None,
    case_name: str | None = None,
    width: int = 1024,
    height: int = 512,
    coordinate_mode: str = "auto",
    camera_height: float = DEFAULT_CAMERA_HEIGHT,
    local_server_root: Path | None = None,
) -> dict[str, Path]:
    input_path = input_path.resolve()
    payload = _read_json(input_path)
    ordered_pairs, pair_source = extract_ordered_pairs(payload)
    image_info, resolved_image = resolve_local_image(
        payload, image_root=image_root, image_path=image_path
    )

    candidate_rows: list[dict[str, Any]] = []
    candidate_provenance: dict[str, Any] | None = None
    if candidate_json is not None:
        candidate_json = candidate_json.resolve()
        candidate_payload = _read_json(candidate_json)
        candidate_rows = extract_candidate_rows(candidate_payload)
        mapping = _mapping_lookup(candidate_payload)
        for index, pair in enumerate(ordered_pairs, start=1):
            if mapping.get(index) is not None:
                pair["source_preview_order_index"] = mapping[index]
        candidate_provenance = {
            "file": candidate_json.name,
            "sha256": _sha256(candidate_json),
            "source": "candidate_json",
        }
    elif candidate_report is not None:
        candidate_report = candidate_report.resolve()
        candidate_rows = extract_candidate_rows_from_report(candidate_report)
        candidate_provenance = {
            "file": candidate_report.name,
            "sha256": _sha256(candidate_report),
            "source": "candidate_report_fallback",
        }

    variants = [
        build_projection_variant(
            "original",
            ordered_pairs,
            width=width,
            height=height,
            coordinate_mode=coordinate_mode,
            camera_height=camera_height,
        )
    ]
    for index, row in enumerate(candidate_rows, start=1):
        candidate_pairs = apply_candidate_row(ordered_pairs, row)
        variant = build_projection_variant(
            f"candidate_{index}",
            candidate_pairs,
            width=width,
            height=height,
            coordinate_mode=coordinate_mode,
            camera_height=camera_height,
            candidate_row=row,
        )
        variant["delta_from_original"] = _summary_delta(
            variants[0]["summary"], variant["summary"]
        )
        variant["metric_comparison"] = _metric_comparison(
            variants[0], variant, row
        )
        variants.append(variant)

    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    review_payload: dict[str, Any] = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "case_name": case_name or input_path.stem,
        "coordinate_mode_requested": coordinate_mode,
        "width": width,
        "height": height,
        "camera_height": camera_height,
        "input_provenance": {
            "input_file": input_path.name,
            "input_sha256": _sha256(input_path),
            "ordered_pair_source": pair_source,
            "candidate": candidate_provenance,
            "image": image_info,
        },
        "safety_boundary": SAFETY_BOUNDARY,
        "variants": variants,
    }

    json_path = out_dir / "projection_metrics.json"
    report_path = out_dir / "projection_review_report.md"
    html_path = out_dir / "local_3d_review.html"
    viewer_path = Path(__file__).resolve().parents[1] / "label_studio" / "vis_3d.html"
    viewer_url = _relative_asset_url(viewer_path, out_dir, local_server_root)
    if viewer_url is None:
        raise ValueError("vis_3d.html is outside --local-server-root")
    image_url = (
        _relative_asset_url(resolved_image, out_dir, local_server_root)
        if resolved_image is not None
        else None
    )
    if resolved_image is not None and image_url is None:
        review_payload["input_provenance"]["image"]["warnings"].append(
            "resolved_image_outside_local_server_root_texture_unavailable"
        )

    json_path.write_text(
        json.dumps(review_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report_path.write_text(render_markdown_report(review_payload), encoding="utf-8")
    html_path.write_text(
        render_review_html(review_payload, viewer_url=viewer_url, image_url=image_url),
        encoding="utf-8",
    )
    return {"json": json_path, "report": report_path, "html": html_path}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--image-root", type=Path)
    parser.add_argument("--image-path", type=Path)
    parser.add_argument("--candidate-json", type=Path)
    parser.add_argument("--candidate-report", type=Path)
    parser.add_argument("--case-name")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument(
        "--coordinate-mode", choices=("auto", "ls_percent", "vis_pixels"), default="auto"
    )
    parser.add_argument("--camera-height", type=float, default=DEFAULT_CAMERA_HEIGHT)
    parser.add_argument("--local-server-root", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    paths = run_local_review(
        input_path=args.input,
        out_dir=args.out_dir,
        image_root=args.image_root,
        image_path=args.image_path,
        candidate_json=args.candidate_json,
        candidate_report=args.candidate_report,
        case_name=args.case_name,
        width=args.width,
        height=args.height,
        coordinate_mode=args.coordinate_mode,
        camera_height=args.camera_height,
        local_server_root=args.local_server_root,
    )
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
