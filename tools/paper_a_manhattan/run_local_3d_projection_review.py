"""Generate M15.19 local 3D projection metrics and a read-only review page."""

from __future__ import annotations

import argparse
import base64
import copy
import datetime as dt
import hashlib
import json
import mimetypes
import os
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import quote, unquote, urlparse

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


REVIEW_SCHEMA_VERSION = "local_3d_projection_review_m15_27_1_bridge_v1"
INSPECTION_SCHEMA_VERSION = "local_3d_inspection_m15_23_4_v1"
HYPOTHESIS_CORE_SCHEMA_VERSION = "manhattan_constrained_hypothesis_ranking_core_v1"
CANONICAL_REVIEW_ROOT = Path(
    "analysis_results/paper_a_manhattan/hypothesis_local_review"
)
MAX_EMBEDDED_IMAGE_BYTES = 8 * 1024 * 1024
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


def canonical_review_out_dir(case_or_stage: str) -> Path:
    return CANONICAL_REVIEW_ROOT / case_or_stage


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


def _embedded_image_data_url(
    path: Path | None, *, max_bytes: int = MAX_EMBEDDED_IMAGE_BYTES
) -> tuple[str | None, dict[str, Any]]:
    if path is None or not path.is_file():
        return None, {
            "embedded": False,
            "reason": "local_image_unavailable",
            "mime_type": None,
            "source_bytes": None,
        }
    size = path.stat().st_size
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if size > max_bytes:
        return None, {
            "embedded": False,
            "reason": "image_exceeds_embed_limit",
            "mime_type": mime_type,
            "source_bytes": size,
            "max_bytes": max_bytes,
        }
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}", {
        "embedded": True,
        "reason": "embedded_for_file_protocol",
        "mime_type": mime_type,
        "source_bytes": size,
        "max_bytes": max_bytes,
    }


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


def extract_m1522_candidate_rows(
    payload: Mapping[str, Any], *, limit: int = 5
) -> list[dict[str, Any]]:
    """Extract executable M15.22 candidates without changing their ranking."""

    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return []
    rows: list[dict[str, Any]] = []
    for raw in candidates:
        if not isinstance(raw, Mapping):
            continue
        if raw.get("family") == "local_order_topology_hypothesis":
            continue
        if raw.get("hard_gate") or raw.get("assertion_violations"):
            continue
        if raw.get("decision_class") == "blocked" or str(
            raw.get("disposition", "")
        ).startswith("suppressed"):
            continue
        if not isinstance(raw.get("coordinate_changes"), list) or not raw["coordinate_changes"]:
            continue
        rows.append(copy.deepcopy(dict(raw)))
        if len(rows) >= max(0, limit):
            break
    return rows


def extract_hypothesis_core_candidate_rows(
    payload: Mapping[str, Any], *, limit: int = 5
) -> list[dict[str, Any]]:
    """Normalize ranked core candidates for expert-side visual review only."""

    candidates = {
        row.get("candidate_id"): row
        for row in payload.get("candidate_set", [])
        if isinstance(row, Mapping) and row.get("candidate_id")
    }
    geometry = payload.get("candidate_review_geometry", {})
    evaluations = payload.get("constrained_evaluations", {})
    portfolio = payload.get("portfolio_ranking", {})
    if not all(isinstance(value, Mapping) for value in (geometry, evaluations, portfolio)):
        return []

    selected: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(candidate: Any, role: str) -> None:
        if not isinstance(candidate, Mapping):
            return
        candidate_id = candidate.get("candidate_id")
        if candidate_id and candidate_id not in seen:
            seen.add(str(candidate_id))
            selected.append((str(candidate_id), role))

    bucket_names = (
        "best_balanced",
        "best_short_wall_preserving",
        "best_low_movement",
        "best_height_consistent",
    )
    for bucket in bucket_names:
        entry = portfolio.get(bucket)
        add(entry.get("candidate") if isinstance(entry, Mapping) else None, bucket)
    for candidate in payload.get("candidate_set", []):
        if isinstance(candidate, Mapping) and candidate.get("recommended_review_candidate") is True:
            add(candidate, "recommended_review_candidate")

    preferred_ids = [candidate_id for candidate_id, _ in selected[:3]]
    rows: list[dict[str, Any]] = []
    for rank, (candidate_id, role) in enumerate(selected[: max(0, limit)], start=1):
        candidate = candidates.get(candidate_id)
        review_geometry = geometry.get(candidate_id)
        if not isinstance(candidate, Mapping) or not isinstance(review_geometry, Mapping):
            continue
        coordinate_changes = review_geometry.get("coordinate_changes")
        if not isinstance(coordinate_changes, list) or not coordinate_changes:
            continue
        evaluation = evaluations.get(candidate_id, {})
        evidence = evaluation.get("evidence_consistency", {}) if isinstance(evaluation, Mapping) else {}
        plausibility = evaluation.get("layout_plausibility", {}) if isinstance(evaluation, Mapping) else {}
        evidence_status = evidence.get("evidence_status") if isinstance(evidence, Mapping) else None
        missing_fields = evidence.get("missing_fields", []) if isinstance(evidence, Mapping) else []
        image_evidence_missing = (
            isinstance(missing_fields, list)
            and "image_edge_support_optional" in missing_fields
        ) or (
            isinstance(evidence, Mapping)
            and evidence.get("image_edge_support_optional") is None
        )
        evidence_warning = (
            "evidence unavailable; expert visual confirmation required"
            if evidence_status == "unavailable" or image_evidence_missing
            else None
        )
        row = copy.deepcopy(dict(candidate))
        row.update(
            {
                "family": row.get("action_family"),
                "source_stage": "manhattan_core",
                "source_rank": rank,
                "review_role": role,
                "coordinate_changes": copy.deepcopy(coordinate_changes),
                "manual_review_candidate": bool(row.get("recommended_review_candidate")),
                "automatic_fix_claimed": False,
                "best_candidate_requires_visual_review": True,
                "direct_ls_trial_allowed": False,
                "ls_trial_candidate": False,
                "primary_unresolved_edges": [],
                "short_wall_edges_after": [],
                "evidence_status": evidence_status,
                "evidence_warning": evidence_warning,
                "short_wall_deficit_delta": plausibility.get("short_wall_deficit_delta") if isinstance(plausibility, Mapping) else None,
                "short_wall_plausibility_warning": (
                    "metric worsened; expert visual confirmation required"
                    if isinstance(plausibility.get("short_wall_deficit_delta"), (int, float))
                    and plausibility["short_wall_deficit_delta"] > 0
                    else None
                ),
                "preferred_panel": candidate_id in preferred_ids,
            }
        )
        rows.append(row)
    return rows


def extract_probe_candidate_rows(
    payload: Mapping[str, Any], *, source_stage: str, limit: int
) -> list[dict[str, Any]]:
    """Normalize ranked M15.26/M15.27 rows for the existing read-only bridge."""

    candidates = payload.get("top_candidates")
    if not isinstance(candidates, list):
        return []
    baseline_primary = (
        payload.get("baseline", {})
        .get("score_breakdown", {})
        .get("primary_edge_6_7_residual")
    )
    rows: list[dict[str, Any]] = []
    for rank, raw in enumerate(candidates[: max(0, limit)], start=1):
        if not isinstance(raw, Mapping) or not isinstance(raw.get("coordinate_changes"), list):
            continue
        row = copy.deepcopy(dict(raw))
        row["source_stage"] = source_stage
        row["source_rank"] = rank
        row["review_role"] = f"{source_stage}_best" if rank == 1 else (
            f"{source_stage}_second" if rank == 2 else f"{source_stage}_additional"
        )
        row["family"] = row.get("action_family") or row.get("family") or "adaptive_probe"
        score = row.get("score_breakdown", {})
        after_primary = score.get("primary_edge_6_7_residual") if isinstance(score, Mapping) else None
        row["primary_edge_residual_before"] = baseline_primary
        row["primary_edge_residual_after"] = after_primary
        row["primary_unresolved_edges"] = ["6-7"] if after_primary is not None and float(after_primary) > 15.0 else []
        row["manual_review_candidate"] = bool(row.get("direct_ls_trial_allowed"))
        row["automatic_fix_claimed"] = False
        row["best_candidate_requires_visual_review"] = source_stage == "m15.27"
        rows.append(row)
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


def apply_m1522_candidate(
    ordered_pairs: Sequence[Mapping[str, Any]], row: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Apply coordinate_changes to a copy; never mutate or reorder input."""

    output = copy.deepcopy(list(ordered_pairs))
    lookup = {int(pair["effective_pair_index"]): pair for pair in output}
    field_map = {
        "top_x": ("top", "x"),
        "top_y": ("top", "y"),
        "bottom_x": ("bottom", "x"),
        "bottom_y": ("bottom", "y"),
    }
    changes = row.get("coordinate_changes")
    if not isinstance(changes, list) or not changes:
        raise ValueError("M15.22 candidate requires coordinate_changes")
    for change in changes:
        if not isinstance(change, Mapping):
            raise ValueError("coordinate_changes entries must be objects")
        pair_index = int(change["effective_pair_index"])
        pair = lookup.get(pair_index)
        if pair is None:
            raise ValueError(f"candidate pair {pair_index} is absent from ordered pairs")
        fields = change.get("fields")
        if not isinstance(fields, Mapping):
            raise ValueError("coordinate change fields must be an object")
        for field, values in fields.items():
            if field not in field_map or not isinstance(values, Mapping) or "after" not in values:
                raise ValueError(f"unsupported M15.22 coordinate change field {field!r}")
            endpoint, axis = field_map[field]
            if not isinstance(pair.get(endpoint), dict):
                raise ValueError("M15.22 candidate application requires top/bottom shape")
            pair[endpoint][axis] = float(values["after"])
    return output


def _candidate_display_label(row: Mapping[str, Any], fallback: str) -> str:
    candidate_id = str(row.get("candidate_id") or fallback)
    family = str(row.get("family") or row.get("action_family") or row.get("probe_mode") or "candidate")
    decision = str(row.get("decision_class") or row.get("disposition") or "review")
    decision = decision.removesuffix("_diagnostic").removesuffix("_review")
    walls = row.get("required_wall_residuals")
    if isinstance(walls, list):
        wall = next(
            (
                item
                for item in walls
                if isinstance(item, Mapping) and item.get("edge") == "6-7"
            ),
            None,
        )
        if wall and wall.get("before_residual_deg") is not None and wall.get(
            "after_residual_deg"
        ) is not None:
            return (
                f"{candidate_id} | {family} | {decision} | 6-7 "
                f"{float(wall['before_residual_deg']):.3f}→"
                f"{float(wall['after_residual_deg']):.3f}"
            )
    primary_before = row.get("primary_edge_residual_before")
    primary_after = row.get("primary_edge_residual_after")
    if primary_before is not None and primary_after is not None:
        return f"{candidate_id} | {family} | {decision} | 6-7 {float(primary_before):.3f}→{float(primary_after):.3f}"
    return f"{candidate_id} | {family} | {decision}"


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
    assets = payload.get("local_review_assets", {})
    variants = payload["variants"]
    original = variants[0]
    auto_ls_warning = (
        payload["coordinate_mode_requested"] == "auto"
        and "auto_coordinate_mode_ambiguous_values_fit_both_ls_percent_and_small_pixel_range"
        in original["projection"].get("warnings", [])
    )
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
        f"- Viewer URL: `{assets.get('viewer_url')}`",
        f"- Image URL for viewer: `{assets.get('image_url_for_viewer')}`",
        f"- Texture expected: `{assets.get('texture_expected')}`",
        "- Network access used: `False`",
        "",
        *(
            [
                "> **Coordinate warning:** input was inferred as LS percent from an ambiguous 0–100 range. For Label Studio inputs, rerun with `--coordinate-mode ls_percent`.",
                "",
            ]
            if auto_ls_warning
            else []
        ),
        "## Human Review Summary",
        "",
        "This is an expert-side local visual review.",
        "Candidate previews are diagnostic only.",
        "No automatic fix is claimed.",
        "Texture toggle and ghost are display controls only.",
        "No annotation patch or Label Studio writeback is produced.",
        "",
    ]
    candidates = variants[1:]
    if not candidates:
        lines.extend(
            [
                "No eligible executable candidate was supplied. Review covers original geometry only.",
                "",
            ]
        )
    for index, candidate in enumerate(candidates, start=1):
        row = candidate["candidate_row"]
        if isinstance(row.get("coordinate_changes"), list):
            lines.extend(
                [
                    f"### {_candidate_display_label(row, f'candidate_{index}')}",
                    "",
                    f"- decision_class: `{row.get('decision_class')}`",
                    *(
                        [
                            "> **SENSITIVITY ONLY:** not a micro-refinement candidate; final_refinement_eligible=`False`; cannot enter M4.2.",
                        ]
                        if row.get("sensitivity_only")
                        else []
                    ),
                    f"- improves: `{row.get('improves', [])}`",
                    f"- fails_because: `{row.get('fails_because', [])}`",
                    f"- direct_ls_trial_allowed: `{row.get('direct_ls_trial_allowed')}`",
                    f"- evidence_status: `{row.get('evidence_status')}`",
                    f"- evidence_warning: `{row.get('evidence_warning')}`",
                    f"- primary_unresolved_edges: `{row.get('primary_unresolved_edges', [])}`",
                    f"- short_wall_edges_after: `{row.get('short_wall_edges_after', [])}`",
                    "- Applied coordinate changes:",
                ]
            )
            for change in row["coordinate_changes"]:
                fields = change.get("fields", {})
                changed_fields = [
                    f"{field} {_fmt(values.get('before'))}→{_fmt(values.get('after'))} (Δ {_fmt(values.get('delta'))})"
                    for field, values in fields.items()
                    if isinstance(values, Mapping)
                    and (
                        bool(values["changed"])
                        if "changed" in values
                        else (
                            abs(float(values["delta"])) > 1e-12
                            if isinstance(values.get("delta"), (int, float))
                            else values.get("before") != values.get("after")
                        )
                    )
                ]
                source_pair_id = change.get("source_pair_id")
                solver_position = change.get(
                    "solver_position", change.get("effective_pair_index")
                )
                pair_label = (
                    f"source pair {source_pair_id} "
                    f"(solver position {solver_position})"
                    if source_pair_id is not None
                    else f"pair {change.get('effective_pair_index')}"
                )
                lines.append(
                    f"  - {pair_label}: "
                    + (", ".join(changed_fields) if changed_fields else "no numeric change")
                )
            lines.extend(
                [
                    f"- wall residual sum: {_fmt(original['summary']['wall_residual_sum_deg'])} -> {_fmt(candidate['summary']['wall_residual_sum_deg'])}",
                    "- Preview only; this is not correctness evidence and cannot write back.",
                    "",
                ]
            )
            continue
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


def _relative_asset_url(target: Path, base_dir: Path) -> str:
    target = target.resolve()
    base_dir = base_dir.resolve()
    try:
        relative = Path(os.path.relpath(target, base_dir)).as_posix()
        return quote(relative, safe="/.")
    except ValueError:
        # Windows cannot form a relative path across drive letters.  This is
        # still local-only; localhost serving should instead use a common root.
        return target.as_uri()


def _server_root_asset_url(target: Path, local_server_root: Path) -> str | None:
    try:
        relative = target.resolve().relative_to(local_server_root.resolve())
    except ValueError:
        return None
    return "/" + quote(relative.as_posix(), safe="/.")


def _build_review_asset_urls(
    *,
    viewer_path: Path,
    resolved_image: Path | None,
    out_dir: Path,
    local_server_root: Path | None,
) -> tuple[str, str | None]:
    """Build URLs against the document that actually consumes each asset.

    The wrapper consumes ``viewer_url``.  The iframe document consumes
    ``image_url_for_viewer``.  They therefore cannot share the same relative
    base unless both are emitted as server-root URLs.
    """

    if local_server_root is not None:
        root = local_server_root.resolve()
        try:
            out_dir.resolve().relative_to(root)
        except ValueError as exc:
            raise ValueError("output directory is outside --local-server-root") from exc
        viewer_url = _server_root_asset_url(viewer_path, root)
        if viewer_url is None:
            raise ValueError("vis_3d.html is outside --local-server-root")
        image_url = (
            _server_root_asset_url(resolved_image, root)
            if resolved_image is not None
            else None
        )
        return viewer_url, image_url

    viewer_url = _relative_asset_url(viewer_path, out_dir)
    image_url = (
        _relative_asset_url(resolved_image, viewer_path.parent)
        if resolved_image is not None
        else None
    )
    return viewer_url, image_url


def _inspection_metadata(variant: Mapping[str, Any]) -> dict[str, Any]:
    projection_pairs = list(variant["projection"]["pairs"])
    heights = {
        int(row["effective_pair_index"]): row
        for row in variant["metrics"]["heights"]["pairs"]
    }
    corner_turns = {
        int(row["corner_pair_index"]): row
        for row in variant["metrics"]["corner_turns"]["corners"]
    }
    pairs: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for pair in projection_pairs:
        pair_index = int(pair["effective_pair_index"])
        height = heights.get(pair_index, {})
        turn = corner_turns.get(pair_index, {})
        pairs.append(
            {
                "effective_pair_index": pair_index,
                "source_preview_order_index": pair.get("source_preview_order_index"),
                "input": pair["input"],
                "normalized": pair["normalized"],
                "floor_3d": pair["floor_3d"],
                "ceiling_3d": pair["ceiling_3d"],
                "wall_height": pair["wall_height"],
                "top_bottom_x_residual": pair["top_bottom_x_residual"],
                "height_residual": height.get("height_residual"),
                "local_height_residual": height.get("local_height_residual"),
                "suspicious_low_height": height.get("suspicious_low_height", False),
                "suspicious_high_height": height.get("suspicious_high_height", False),
                "previous_wall_index": turn.get("prev_wall_index"),
                "next_wall_index": turn.get("next_wall_index"),
                "junction_angle_deg": turn.get("turn_angle_deg"),
                "junction_residual_to_90_deg": turn.get(
                    "angle_to_90_residual_deg"
                ),
                "junction_angle_kind": "unsigned_smaller_floorprint_angle_0_180",
                "turn_warning": turn.get("warning_far_from_90", False),
                "warnings": pair.get("warnings", []),
            }
        )
        if height.get("suspicious_low_height") or height.get("suspicious_high_height"):
            issues.append(
                {
                    "priority": 3,
                    "type": "height",
                    "pair_index": pair_index,
                    "severity": abs(float(height.get("height_residual", 0.0))),
                }
            )
        if turn.get("warning_far_from_90"):
            issues.append(
                {
                    "priority": 2,
                    "type": "corner",
                    "pair_index": pair_index,
                    "severity": float(turn.get("angle_to_90_residual_deg", 0.0)),
                }
            )

    walls = [dict(row) for row in variant["metrics"]["floorprint"]["walls"]]
    for wall in walls:
        if wall.get("angle_warning"):
            issues.append(
                {
                    "priority": 1,
                    "type": "wall",
                    "wall_index": int(wall["wall_index"]),
                    "severity": float(wall["angle_residual_deg"]),
                }
            )
        if wall.get("short_wall"):
            issues.append(
                {
                    "priority": 4,
                    "type": "wall",
                    "wall_index": int(wall["wall_index"]),
                    "severity": max(
                        0.0,
                        float(wall.get("short_wall_threshold", 0.0))
                        - float(wall["floor_wall_length"]),
                    ),
                    "reason": "short_wall",
                }
            )
    if variant["metrics"]["floorprint"].get("self_intersection"):
        issues.append(
            {"priority": 0, "type": "layout", "severity": 1.0, "reason": "self_intersection"}
        )
    issues.sort(key=lambda row: (int(row["priority"]), -float(row["severity"])))
    return {
        "schema_version": INSPECTION_SCHEMA_VERSION,
        "variant_name": variant["name"],
        "pairs": pairs,
        "walls": walls,
        "issues": issues,
    }


def _windows_launcher_text(out_dir: Path, html_path: Path) -> str:
    repo_relative_from_output = Path(os.path.relpath(REPO_ROOT, out_dir)).as_posix()
    review_relative = html_path.resolve().relative_to(REPO_ROOT).as_posix()
    repo_windows = repo_relative_from_output.replace("/", "\\")
    review_windows = review_relative.replace("/", "\\")
    return (
        "@echo off\r\n"
        "setlocal\r\n"
        f'for %%I in ("%~dp0{repo_windows}") do set "REPO_ROOT=%%~fI"\r\n'
        'cd /d "%REPO_ROOT%"\r\n'
        "python tools\\paper_a_manhattan\\serve_local_3d_projection_review.py "
        f'--repo-root "%REPO_ROOT%" --review "{review_windows}"\r\n'
        "if errorlevel 1 pause\r\n"
    )


def render_review_html(
    payload: Mapping[str, Any],
    *,
    file_image_data_url: str | None,
) -> str:
    minimal_variants = []
    for variant in payload["variants"]:
        candidate_row = variant.get("candidate_row") or {}
        coordinate_changes = candidate_row.get("coordinate_changes")
        changed_pair_indices = (
            sorted(
                {
                    int(change["effective_pair_index"])
                    for change in coordinate_changes
                    if isinstance(change, Mapping)
                    and change.get("effective_pair_index") is not None
                }
            )
            if isinstance(coordinate_changes, list)
            else []
        )
        overlay_pairs = []
        for raw_pair, projected_pair in zip(
            variant["ordered_pairs"], variant["projection"]["pairs"]
        ):
            normalized = projected_pair["normalized"]
            effective_pair_index = int(projected_pair["effective_pair_index"])
            source_pair_id = (
                raw_pair.get("source_pair_id")
                or raw_pair.get("source_preview_order_index")
                or projected_pair.get("source_preview_order_index")
                or effective_pair_index
            )
            overlay_pairs.append(
                {
                    "source_pair_id": int(source_pair_id),
                    "solver_position": int(raw_pair.get("solver_position") or effective_pair_index),
                    "effective_pair_index": effective_pair_index,
                    "top": {
                        "x": float(normalized["top_x"]) / float(payload["width"]) * 100.0,
                        "y": float(normalized["top_y"]) / float(payload["height"]) * 100.0,
                    },
                    "bottom": {
                        "x": float(normalized["bottom_x"]) / float(payload["width"]) * 100.0,
                        "y": float(normalized["bottom_y"]) / float(payload["height"]) * 100.0,
                    },
                }
            )
        corners = [
            {
                "x": pair["normalized"]["x"],
                "y_ceiling": pair["normalized"]["top_y"],
                "y_floor": pair["normalized"]["bottom_y"],
            }
            for pair in variant["projection"]["pairs"]
        ]
        changed_pair_set = set(changed_pair_indices)
        changed_wall_indices = [
            wall_index
            for wall_index in range(1, len(corners) + 1)
            if wall_index in changed_pair_set
            or (wall_index % len(corners)) + 1 in changed_pair_set
        ]
        minimal_variants.append(
            {
                "name": variant["name"],
                "displayName": variant.get("display_name", variant["name"]),
                "changedPairIndices": changed_pair_indices,
                "changedWallIndices": changed_wall_indices,
                "corners": corners,
                "overlayPairs": overlay_pairs,
                "summary": variant["summary"],
                "triage": {
                    key: candidate_row.get(key)
                    for key in (
                        "decision_class",
                        "improves",
                        "fails_because",
                        "direct_ls_trial_allowed",
                        "primary_unresolved_edges",
                        "short_wall_edges_after",
                        "source_stage",
                        "source_rank",
                        "manual_review_candidate",
                        "automatic_fix_claimed",
                        "best_candidate_requires_visual_review",
                        "action_family",
                        "evidence_status",
                        "evidence_warning",
                        "ls_trial_candidate",
                        "short_wall_deficit_delta",
                        "short_wall_plausibility_warning",
                        "sensitivity_only",
                        "final_refinement_eligible",
                        "requires_explicit_human_visual_verdict",
                        "m_anchor_4_2_input_eligible",
                    )
                    if candidate_row.get(key) is not None
                },
                "inspection": _inspection_metadata(variant),
            }
        )
    assets = payload["local_review_assets"]
    data = {
        "width": payload["width"],
        "height": payload["height"],
        "assets": {
            "server": {
                "viewerUrl": assets["server"]["viewer_url"],
                "imageUrl": assets["server"]["image_url_for_viewer"],
                "textureExpected": assets["server"]["texture_expected"],
            },
            "file": {
                "viewerUrl": assets["file"]["viewer_url"],
                "imageUrl": file_image_data_url,
                "textureExpected": bool(file_image_data_url),
                "embed": assets["file"]["embed"],
            },
        },
        "coordinateModeRequested": payload["coordinate_mode_requested"],
        "coordinateWarnings": payload["variants"][0]["projection"].get("warnings", []),
        "variants": minimal_variants,
        "preferredPanelVariants": list(payload.get("preferred_panel_variants", [])),
        "provenance": {
            "workbench_version": "m15.23.7",
            "review_schema": payload["schema_version"],
            "input": payload["input_provenance"]["input_file"],
            "input_sha256": payload["input_provenance"]["input_sha256"],
            "image_exists": payload["input_provenance"]["image"].get("image_exists"),
            "image_sha256": payload["input_provenance"]["image"].get("image_sha256"),
            "coordinate_mode_requested": payload["coordinate_mode_requested"],
            "coordinate_mode_effective": payload["variants"][0]["projection"]["coordinate_mode"],
        },
    }
    encoded = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>M15.23.7 Scrollable Flexible Compare Grid</title>
  <style>
    :root {{ color-scheme: dark; font-family: system-ui, sans-serif; }}
    body {{ margin:0; height:100vh; overflow:hidden; background:#0b1020; color:#e5e7eb; display:flex; flex-direction:column; }}
    header {{ flex:0 0 auto; padding:12px 16px; border-bottom:1px solid #334155; display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
    button, select {{ padding:7px 10px; border-radius:6px; border:1px solid #475569; background:#172033; color:#fff; }}
    button {{ cursor:pointer; }}
    #warning {{ display:none; flex-basis:100%; color:#fde68a; background:#78350f; border:1px solid #b45309; border-radius:6px; padding:8px 10px; font-size:13px; font-weight:650; }}
    main {{ flex:1 1 auto; min-height:0; display:grid; grid-template-columns:minmax(0,1fr) 430px; }}
    #views {{ min-height:0; display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; padding:8px; overflow-y:auto; align-content:start; }}
    .review-panel {{ min-height:0; display:grid; grid-template-rows:auto minmax(0,1fr); border:2px solid #334155; border-radius:8px; background:#0f172a; overflow:hidden; }}
    .review-panel.active-panel {{ border-color:#facc15; box-shadow:0 0 0 1px #facc15; }}
    .panel-header {{ display:grid; grid-template-columns:auto minmax(120px,1fr) minmax(0,150px) auto; gap:7px; align-items:center; padding:7px; background:#172033; cursor:pointer; }}
    .panel-header select {{ min-width:0; width:100%; }}
    .panel-status {{ min-width:0; max-width:150px; color:#cbd5e1; font-size:11px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
    .remove-panel {{ min-width:68px; padding:5px 8px; }}
    .review-panel iframe {{ width:100%; height:100%; min-height:0; border:0; background:#111; display:block; }}
    aside {{ min-height:0; padding:14px; border-left:1px solid #334155; background:#111827; overflow:auto; }}
    #original-panorama {{ margin-bottom:12px; border:1px solid #334155; border-radius:6px; background:#0f172a; }}
    #original-panorama summary {{ cursor:pointer; padding:8px; font-weight:700; }}
    #original-panorama img {{ display:block; width:100%; max-height:240px; object-fit:contain; background:#020617; }}
    #original-panorama-status {{ display:block; padding:6px 8px; }}
    #focus-review {{ display:none; position:fixed; inset:0; z-index:50; background:#020617; color:#e5e7eb; flex-direction:column; }}
    #focus-review.open {{ display:flex; }}
    #focus-toolbar {{ flex:0 0 auto; display:flex; gap:8px; align-items:center; flex-wrap:wrap; padding:10px 12px; border-bottom:1px solid #334155; background:#0f172a; }}
    #focus-overlay-controls {{ display:flex; flex-wrap:wrap; gap:6px 10px; font-size:11px; }}
    #focus-stage {{ --focus-2d-size:50%; flex:1 1 auto; min-height:0; display:grid; gap:8px; padding:8px; }}
    #focus-stage[data-placement="right"] {{ grid-template-columns:minmax(0,calc(100% - var(--focus-2d-size))) 8px minmax(0,var(--focus-2d-size)); grid-template-areas:"three resize two"; }}
    #focus-stage[data-placement="left"] {{ grid-template-columns:minmax(0,var(--focus-2d-size)) 8px minmax(0,calc(100% - var(--focus-2d-size))); grid-template-areas:"two resize three"; }}
    #focus-stage[data-placement="top"] {{ grid-template-rows:minmax(0,var(--focus-2d-size)) 8px minmax(0,calc(100% - var(--focus-2d-size))); grid-template-areas:"two" "resize" "three"; }}
    #focus-stage[data-placement="bottom"] {{ grid-template-rows:minmax(0,calc(100% - var(--focus-2d-size))) 8px minmax(0,var(--focus-2d-size)); grid-template-areas:"three" "resize" "two"; }}
    #focus-stage.drag-over {{ outline:2px dashed #facc15; outline-offset:-6px; }}
    .focus-pane {{ min-width:0; min-height:0; display:grid; grid-template-rows:auto minmax(0,1fr) auto; border:1px solid #334155; border-radius:8px; overflow:hidden; background:#0f172a; }}
    #focus-3d-pane {{ grid-area:three; }}
    #focus-2d-pane {{ grid-area:two; }}
    #focus-resize-handle {{ grid-area:resize; border-radius:8px; background:#334155; cursor:col-resize; }}
    #focus-stage[data-placement="top"] #focus-resize-handle,
    #focus-stage[data-placement="bottom"] #focus-resize-handle {{ cursor:row-resize; }}
    .focus-drag-handle {{ padding:7px 9px; background:#172033; cursor:grab; user-select:none; font-weight:700; }}
    .focus-drag-handle:active {{ cursor:grabbing; }}
    .focus-2d-shell {{ min-height:0; display:grid; place-items:center; overflow:hidden; background:#020617; }}
    #focus-2d-viewbox {{ aspect-ratio:2/1; background:#111; }}
    #focus-3d-frame, #focus-2d-canvas {{ width:100%; height:100%; min-height:0; border:0; display:block; background:#111; }}
    #focus-2d-canvas {{ cursor:crosshair; }}
    #focus-2d-status, #focus-drop-hint {{ padding:5px 8px; }}
    .overlay-baseline {{ stroke:#e5e7eb; fill:#111827; stroke-dasharray:.9 .7; vector-effect:non-scaling-stroke; }}
    .overlay-candidate {{ stroke:#22d3ee; fill:#fde047; vector-effect:non-scaling-stroke; }}
    .overlay-changed {{ stroke:#f472b6; fill:#fb7185; vector-effect:non-scaling-stroke; }}
    .overlay-arrow {{ stroke:#fb7185; stroke-dasharray:.8 .6; vector-effect:non-scaling-stroke; }}
    .overlay-label {{ fill:#fff; paint-order:stroke; stroke:#000; stroke-width:.35; font-size:1.55px; }}
    table {{ width:100%; border-collapse:collapse; font-size:11px; }}
    th, td {{ border:1px solid #334155; padding:4px; text-align:left; vertical-align:top; }}
    pre {{ white-space:pre-wrap; overflow-wrap:anywhere; font-size:12px; }}
    .muted {{ color:#94a3b8; font-size:12px; }}
    .active {{ background:#2563eb; border-color:#60a5fa; }}
    .toolbar-group {{ display:flex; gap:5px; align-items:center; }}
    #triage-warning {{ display:none; color:#fff7ed; background:#9a3412; border:2px solid #fb923c; border-radius:6px; padding:10px; font-weight:800; }}
  </style>
</head>
<body>
  <header>
    <strong>M15.23.7 Scrollable Flexible Compare Grid</strong>
    <button id="add-panel" type="button">+ Panel</button>
    <span id="panel-count-status" class="muted">Panels 0 / 6</span>
    <button id="labels" type="button">Hide corners</button>
    <button id="texture" class="active" type="button">Texture: ON</button>
    <button id="ghost" class="active" type="button">Ghost original</button>
    <button id="measure" type="button">Measure</button>
    <button id="next-issue" type="button">Next issue</button>
    <button id="open-2d-review" type="button">2D Review</button>
    <span class="toolbar-group">
      <button data-camera="top" type="button">Top</button>
      <button data-camera="isometric" type="button">Isometric</button>
      <button data-camera="inside" type="button">Inside</button>
      <button data-camera="reset" type="button">Reset view</button>
    </span>
    <span id="warning"></span>
  </header>
  <main>
    <section id="views"></section>
    <template id="panel-template">
      <article class="review-panel">
        <div class="panel-header">
          <strong class="panel-number"></strong>
          <select class="panel-variant" aria-label="Panel variant"></select>
          <span class="panel-status"></span>
          <button class="remove-panel" type="button">Remove</button>
        </div>
        <iframe title="candidate geometry panel"></iframe>
      </article>
    </template>
    <aside>
      <details id="original-panorama" open>
        <summary>Original panorama</summary>
        <img id="original-panorama-image" alt="Original panorama for geometry review" hidden>
        <span id="original-panorama-status" class="muted">Loading original panorama…</span>
      </details>
      <h3>Inspector</h3><pre id="inspector">Click a corner or wall.</pre>
      <h3>Measurement</h3><pre id="measurement">Measure mode is off.</pre>
      <div id="triage-warning"></div>
      <h3>Candidate triage</h3><pre id="triage"></pre>
      <h3>Metric summary</h3><pre id="metrics"></pre>
      <h3>Viewer / texture status</h3><pre id="texture-status"></pre>
      <h3>Compare summary</h3>
      <table id="compare-table"><thead><tr><th>Panel</th><th>Variant</th><th>Decision</th><th>Manual review</th><th>Unresolved</th><th>Wall residual</th><th>Short walls</th></tr></thead><tbody></tbody></table>
      <h3>Provenance</h3><pre id="provenance"></pre>
      <h3>Visual feature summary</h3>
      <ul class="muted">
        <li>Candidate changed walls = red dashed.</li>
        <li>Changed pairs = magenta markers.</li>
        <li>Current layout = green solid.</li>
        <li>Original ghost = low-opacity grey dashed.</li>
        <li>Texture ON/OFF affects display only; imageUrl remains loaded.</li>
        <li>Camera presets broadcast; live OrbitControls are not synchronized.</li>
        <li>Candidate previews are diagnostic only; no automatic fix is claimed.</li>
        <li>No annotation patch or Label Studio writeback is produced.</li>
      </ul>
      <p class="muted">Wall click: global-XZ heading and Manhattan-axis deviation. Corner click: angle between its previous and next wall. Red dashed walls mark candidate-modified geometry.</p>
      <p class="muted">Read-only local diagnostic. Open this HTML directly to use its embedded local texture, or double-click <code>open_local_3d_review.cmd</code> for localhost mode.</p>
    </aside>
  </main>
  <div id="focus-review" aria-hidden="true">
    <div id="focus-toolbar">
      <strong>Focus 2D/3D Review</strong>
      <span id="focus-variant-name" class="muted"></span>
      <span id="focus-coordinate-readout" class="muted">Click 2D to show LS/pixel coordinates.</span>
      <button id="close-2d-review" type="button">Close</button>
      <button id="focus-layout-cycle" type="button">Move 2D</button>
      <div id="focus-overlay-controls">
        <label><input id="overlay-show-baseline" type="checkbox" checked> baseline</label>
        <label><input id="overlay-show-candidate" type="checkbox" checked> candidate</label>
        <label><input id="overlay-show-labels" type="checkbox" checked> labels</label>
        <label><input id="overlay-show-arrows" type="checkbox" checked> arrows</label>
        <label><input id="overlay-show-top" type="checkbox" checked> top</label>
        <label><input id="overlay-show-bottom" type="checkbox" checked> bottom</label>
        <label><input id="overlay-show-vertical" type="checkbox" checked> vertical</label>
        <label>point size <input id="overlay-point-size" type="range" min=".35" max="1.6" step=".05" value=".75"></label>
      </div>
    </div>
    <div id="focus-stage" data-placement="right">
      <section id="focus-3d-pane" class="focus-pane">
        <div class="focus-drag-handle" data-focus-pane="3d">3D preview · drag here to reposition</div>
        <iframe id="focus-3d-frame" title="focused candidate geometry panel"></iframe>
        <span class="muted">Read-only 3D preview; display only.</span>
      </section>
      <div id="focus-resize-handle" title="Drag to resize 2D/3D panes"></div>
      <section id="focus-2d-pane" class="focus-pane">
        <div class="focus-drag-handle" data-focus-pane="2d">2D annotation overlay · drag here to dock left/right/top/bottom</div>
        <div class="focus-2d-shell">
          <div id="focus-2d-viewbox">
            <svg id="focus-2d-canvas" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="read-only focused 2D image point overlay">
              <defs><marker id="overlay-arrowhead" markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto"><path d="M0,0 L5,2.5 L0,5z" fill="#fb7185"></path></marker></defs>
              <image id="focus-2d-panorama" x="0" y="0" width="100" height="100" preserveAspectRatio="none"></image>
              <g id="focus-2d-root"></g>
            </svg>
          </div>
        </div>
        <span id="focus-2d-status" class="muted">Read-only 2D overlay.</span>
      </section>
    </div>
    <span id="focus-drop-hint" class="muted">Drag either pane title toward left/right/top/bottom to rearrange the 2D/3D layout.</span>
  </div>
  <script>
    const REVIEW = {encoded};
    const views = document.getElementById('views');
    const addPanelButton = document.getElementById('add-panel');
    const panelCountStatus = document.getElementById('panel-count-status');
    const panelTemplate = document.getElementById('panel-template');
    const compareTableBody = document.querySelector('#compare-table tbody');
    const metrics = document.getElementById('metrics');
    const triage = document.getElementById('triage');
    const triageWarning = document.getElementById('triage-warning');
    const inspector = document.getElementById('inspector');
    const measurement = document.getElementById('measurement');
    const warning = document.getElementById('warning');
    const textureStatus = document.getElementById('texture-status');
    const provenance = document.getElementById('provenance');
    const originalPanoramaImage = document.getElementById('original-panorama-image');
    const originalPanoramaStatus = document.getElementById('original-panorama-status');
    const focusReview = document.getElementById('focus-review');
    const focusStage = document.getElementById('focus-stage');
    const focusFrame = document.getElementById('focus-3d-frame');
    const focusVariantName = document.getElementById('focus-variant-name');
    const focusCoordinateReadout = document.getElementById('focus-coordinate-readout');
    const focusOverlayCanvas = document.getElementById('focus-2d-canvas');
    const focus2DViewbox = document.getElementById('focus-2d-viewbox');
    const focusOverlayPanorama = document.getElementById('focus-2d-panorama');
    const focusOverlayRoot = document.getElementById('focus-2d-root');
    const focusOverlayStatus = document.getElementById('focus-2d-status');
    const focusDropHint = document.getElementById('focus-drop-hint');
    const activeMode = window.location.protocol === 'file:' ? 'file' : 'server';
    const activeAssets = REVIEW.assets[activeMode];
    const MAX_COMPARE_PANELS = 6;
    const preferredPanelVariants = REVIEW.preferredPanelVariants.length
      ? REVIEW.preferredPanelVariants
      : ['original', 'candidate_1', 'candidate_2', 'candidate_5'];
    let panels = [];
    let activePanelIndex = 0;
    let labelsVisible = true;
    let textureVisible = true;
    let ghostVisible = true;
    let measureMode = false;
    let issueCursor = -1;
    let focusVariantIndex = 0;
    let focusViewerReady = false;
    let focusDraggingPane = null;
    let focusResizing = false;

    if (REVIEW.variants.some((variant) => variant.triage?.sensitivity_only)) {{
      warning.textContent = 'SENSITIVITY ONLY candidates are display diagnostics, not final refinements and cannot enter M4.2.';
      warning.hidden = false;
    }}

    if (activeAssets.imageUrl) {{
      originalPanoramaImage.src = activeAssets.imageUrl;
      originalPanoramaImage.hidden = false;
      originalPanoramaStatus.textContent = activeMode === 'file'
        ? 'Embedded local panorama · read-only'
        : 'Repository-local panorama · read-only';
      originalPanoramaImage.addEventListener('error', () => {{
        originalPanoramaImage.hidden = true;
        originalPanoramaStatus.textContent = 'Original panorama failed to load; 3D geometry remains available.';
      }});
      focusOverlayPanorama.setAttribute('href', activeAssets.imageUrl);
      focusOverlayPanorama.addEventListener('load', renderFocus2DOverlay);
      focusOverlayPanorama.addEventListener('error', () => {{
        focusOverlayStatus.textContent = '2D overlay image failed to load; point geometry remains available.';
      }});
    }} else {{
      originalPanoramaStatus.textContent = 'Original panorama unavailable; 3D geometry remains available.';
      focusOverlayStatus.textContent = '2D overlay image unavailable; point geometry remains available.';
    }}

    function defaultPanelAssignments() {{
      const assignments = preferredPanelVariants
        .map((name) => REVIEW.variants.findIndex((variant) => variant.name === name))
        .filter((index, position, rows) => index >= 0 && rows.indexOf(index) === position);
      REVIEW.variants.forEach((_, index) => {{ if (!assignments.includes(index)) assignments.push(index); }});
      return assignments;
    }}
    const panelAssignments = defaultPanelAssignments();
    const defaultPanelCount = REVIEW.variants.length >= 4 ? 4 : (REVIEW.variants.length >= 2 ? 2 : 1);
    let nextPanelId = 1;

    function activePanel() {{ return panels[activePanelIndex] || panels[0] || null; }}
    function panelVariant(panel) {{ return REVIEW.variants[panel.variantIndex] || REVIEW.variants[0]; }}
    function activeVariant() {{ return panelVariant(activePanel()); }}
    function focusVariant() {{ return REVIEW.variants[focusVariantIndex] || activeVariant(); }}
    function overlayEnabled(id) {{
      const node = document.getElementById(id);
      return !node || node.checked;
    }}
    function overlayPointRadius() {{
      return Number(document.getElementById('overlay-point-size')?.value || 0.75);
    }}
    function sourceLabel(pair) {{
      return 's' + pair.source_pair_id + ' / p' + pair.solver_position;
    }}
    function endpointDistance(a, b) {{
      return Math.hypot(Number(a.x) - Number(b.x), Number(a.y) - Number(b.y));
    }}
    function overlayPath(pairs, endpoint) {{
      let d = '';
      pairs.forEach((pair, index) => {{
        const point = pair[endpoint];
        const previous = index ? pairs[index - 1][endpoint] : null;
        const command = index && previous && Math.abs(point.x - previous.x) <= 50 ? ' L' : ' M';
        d += command + point.x + ' ' + point.y;
      }});
      return d.trim();
    }}
    function svgNode(tag, attrs = {{}}) {{
      const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
      Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
      return node;
    }}
    function appendOverlayPath(target, pairs, endpoint, className) {{
      const d = overlayPath(pairs, endpoint);
      if (d) target.root.appendChild(svgNode('path', {{d, class: className, fill: 'none', 'stroke-width': 0.35}}));
    }}
    function appendOverlayPair(target, pair, className, changed) {{
      const radius = overlayPointRadius();
      const markerClass = changed ? 'overlay-changed' : className;
      if (overlayEnabled('overlay-show-vertical')) {{
        target.root.appendChild(svgNode('line', {{
          x1: pair.top.x, y1: pair.top.y, x2: pair.bottom.x, y2: pair.bottom.y,
          class: markerClass, 'stroke-width': 0.3
        }}));
      }}
      ['top', 'bottom'].forEach((endpoint) => {{
        const point = pair[endpoint];
        target.root.appendChild(svgNode('circle', {{
          cx: point.x, cy: point.y, r: radius,
          class: markerClass, 'stroke-width': 0.35
        }}));
      }});
      if (overlayEnabled('overlay-show-labels')) {{
        const label = svgNode('text', {{
          x: Number(pair.top.x) + 0.8, y: Number(pair.top.y) - 0.8,
          class: 'overlay-label'
        }});
        label.textContent = sourceLabel(pair);
        target.root.appendChild(label);
      }}
    }}
    function render2DOverlayTarget(target, variant) {{
      if (!target?.root) return;
      target.root.replaceChildren();
      const baseline = REVIEW.variants[0];
      if (!variant || !baseline?.overlayPairs?.length) return;
      const candidatePairs = variant.overlayPairs || [];
      const baselinePairs = baseline.overlayPairs || [];
      const changed = new Set(variant.changedPairIndices || []);
      if (overlayEnabled('overlay-show-top')) {{
        if (overlayEnabled('overlay-show-baseline')) appendOverlayPath(target, baselinePairs, 'top', 'overlay-baseline');
        if (overlayEnabled('overlay-show-candidate')) appendOverlayPath(target, candidatePairs, 'top', 'overlay-candidate');
      }}
      if (overlayEnabled('overlay-show-bottom')) {{
        if (overlayEnabled('overlay-show-baseline')) appendOverlayPath(target, baselinePairs, 'bottom', 'overlay-baseline');
        if (overlayEnabled('overlay-show-candidate')) appendOverlayPath(target, candidatePairs, 'bottom', 'overlay-candidate');
      }}
      if (overlayEnabled('overlay-show-baseline')) {{
        baselinePairs.forEach((pair) => appendOverlayPair(target, pair, 'overlay-baseline', false));
      }}
      candidatePairs.forEach((pair, index) => {{
        const isChanged = changed.has(pair.effective_pair_index);
        if (overlayEnabled('overlay-show-candidate')) appendOverlayPair(target, pair, 'overlay-candidate', isChanged);
        const base = baselinePairs[index];
        if (base && overlayEnabled('overlay-show-arrows') && variant.name !== 'original') {{
          ['top', 'bottom'].forEach((endpoint) => {{
            if (endpointDistance(base[endpoint], pair[endpoint]) <= 0.01) return;
            target.root.appendChild(svgNode('line', {{
              x1: base[endpoint].x, y1: base[endpoint].y, x2: pair[endpoint].x, y2: pair[endpoint].y,
              class: 'overlay-arrow', 'stroke-width': 0.28, 'marker-end': 'url(#overlay-arrowhead)'
            }}));
          }});
        }}
      }});
      if (target.status) target.status.textContent = '2D overlay: ' + variant.name + ' | read-only | click image for LS-percent coordinates.';
    }}
    function renderFocus2DOverlay() {{
      render2DOverlayTarget({{root:focusOverlayRoot, status:focusOverlayStatus}}, focusVariant());
      requestAnimationFrame(sizeFocus2DViewbox);
    }}
    function pointToLsPercent(event, canvas = focusOverlayCanvas) {{
      const rect = canvas.getBoundingClientRect();
      return {{
        x: Math.max(0, Math.min(100, (event.clientX - rect.left) / rect.width * 100)),
        y: Math.max(0, Math.min(100, (event.clientY - rect.top) / rect.height * 100)),
      }};
    }}
    function nearestEndpoint(x, y, variant = activeVariant()) {{
      let best = null;
      (variant?.overlayPairs || []).forEach((pair) => {{
        ['top', 'bottom'].forEach((endpoint) => {{
          const point = pair[endpoint];
          const distance = Math.hypot(point.x - x, point.y - y);
          if (!best || distance < best.distance) {{
            best = {{
              source_pair_id: pair.source_pair_id,
              solver_position: pair.solver_position,
              effective_pair_index: pair.effective_pair_index,
              endpoint,
              distance_ls_percent: distance,
              point,
            }};
          }}
        }});
      }});
      return best;
    }}
    function inspect2DOverlayClick(event, canvas, variant) {{
      const point = pointToLsPercent(event, canvas);
      const nearest = nearestEndpoint(point.x, point.y, variant);
      const payload = {{
        type: '2d_image_overlay_click',
        variant: variant?.name || null,
        ls_percent: {{x: Number(point.x.toFixed(4)), y: Number(point.y.toFixed(4))}},
        pixel: {{
          x_px: Number((point.x / 100 * REVIEW.width).toFixed(2)),
          y_px: Number((point.y / 100 * REVIEW.height).toFixed(2)),
        }},
        nearest_endpoint: nearest ? {{
          ...nearest,
          distance_ls_percent: Number(nearest.distance_ls_percent.toFixed(4)),
        }} : null,
        read_only: true,
      }};
      inspector.textContent = JSON.stringify(payload, null, 2);
      focusCoordinateReadout.textContent =
        'LS x=' + payload.ls_percent.x + ', y=' + payload.ls_percent.y +
        ' | px x=' + payload.pixel.x_px + ', y=' + payload.pixel.y_px +
        (payload.nearest_endpoint
          ? ' | nearest s' + payload.nearest_endpoint.source_pair_id + ' ' + payload.nearest_endpoint.endpoint +
            ' d=' + payload.nearest_endpoint.distance_ls_percent
          : '');
    }}
    focusOverlayCanvas.addEventListener('click', (event) => {{
      inspect2DOverlayClick(event, focusOverlayCanvas, focusVariant());
    }});
    function oppositePlacement(placement) {{
      return {{left:'right', right:'left', top:'bottom', bottom:'top'}}[placement] || 'right';
    }}
    function placementFromPointer(event) {{
      const rect = focusStage.getBoundingClientRect();
      const x = (event.clientX - rect.left) / Math.max(1, rect.width);
      const y = (event.clientY - rect.top) / Math.max(1, rect.height);
      if (y < 0.25) return 'top';
      if (y > 0.75) return 'bottom';
      return x < 0.5 ? 'left' : 'right';
    }}
    function setFocusPlacement(placement, draggedPane = '2d') {{
      const next = draggedPane === '3d' ? oppositePlacement(placement) : placement;
      focusStage.dataset.placement = next;
      focusDropHint.textContent = '2D is docked ' + next + ' of the 3D preview. Drag either pane title to rearrange.';
      sizeFocus2DViewbox();
    }}
    function sizeFocus2DViewbox() {{
      const shell = focus2DViewbox.parentElement;
      const width = Math.max(1, shell.clientWidth);
      const height = Math.max(1, shell.clientHeight);
      const viewWidth = Math.min(width, height * 2);
      focus2DViewbox.style.width = viewWidth + 'px';
      focus2DViewbox.style.height = (viewWidth / 2) + 'px';
    }}
    function resizeFocusFromPointer(event) {{
      const rect = focusStage.getBoundingClientRect();
      const placement = focusStage.dataset.placement || 'right';
      let ratio = 0.5;
      if (placement === 'left') ratio = (event.clientX - rect.left) / Math.max(1, rect.width);
      if (placement === 'right') ratio = (rect.right - event.clientX) / Math.max(1, rect.width);
      if (placement === 'top') ratio = (event.clientY - rect.top) / Math.max(1, rect.height);
      if (placement === 'bottom') ratio = (rect.bottom - event.clientY) / Math.max(1, rect.height);
      ratio = Math.max(0.2, Math.min(0.8, ratio));
      focusStage.style.setProperty('--focus-2d-size', (ratio * 100).toFixed(1) + '%');
      sizeFocus2DViewbox();
    }}
    function updatePanelHeader(panel) {{
      const variant = panelVariant(panel);
      const triage = variant.triage || {{}};
      const statusText = `${{triage.decision_class || 'original'}} · manual review ${{triage.manual_review_candidate ?? false}}`;
      panel.status.textContent = statusText;
      panel.status.title = statusText;
      panel.frame.title = `Panel ${{panel.index + 1}}: ${{variant.name}}`;
    }}
    function updateCompareTable() {{
      compareTableBody.innerHTML = '';
      panels.forEach((panel) => {{
        const variant = panelVariant(panel);
        const triage = variant.triage || {{}};
        const values = [
          panel === activePanel() ? `${{panel.index + 1}} (active)` : String(panel.index + 1),
          variant.name,
          triage.decision_class || 'original',
          String(triage.manual_review_candidate ?? false),
          JSON.stringify(triage.primary_unresolved_edges || []),
          Number(variant.summary?.wall_residual_sum_deg ?? 0).toFixed(3),
          JSON.stringify(triage.short_wall_edges_after || []),
        ];
        const row = document.createElement('tr');
        values.forEach((value) => {{ const cell = document.createElement('td'); cell.textContent = value; row.appendChild(cell); }});
        compareTableBody.appendChild(row);
      }});
    }}
    function updateTextureUi() {{
      const warnings = [];
      if (REVIEW.coordinateModeRequested === 'auto' && REVIEW.coordinateWarnings.includes('auto_coordinate_mode_ambiguous_values_fit_both_ls_percent_and_small_pixel_range')) {{
        warnings.push('Coordinate mode was inferred as LS percent. For Label Studio inputs, rerun with --coordinate-mode ls_percent.');
      }}
      if (panels.some((panel) => panel.viewerState === 'failed')) {{
        warnings.push('At least one 3D panel did not load. Use open_local_3d_review.cmd or verify the viewer path.');
      }} else if (!activeAssets.textureExpected) {{
        warnings.push('Texture unavailable; geometry remains reviewable.');
      }} else if (panels.some((panel) => panel.textureState === 'failed' || panel.textureState === 'unavailable')) {{
        warnings.push('Local image exists but at least one panel did not load its texture. Do not treat this review as visually verified.');
      }}
      warning.textContent = warnings.join(' ');
      warning.style.display = warnings.length ? 'block' : 'none';
      textureStatus.textContent = JSON.stringify(panels.map((panel) => ({{
        panel: panel.index + 1, variant: panelVariant(panel).name,
        viewer: panel.viewerState, viewer_reason: panel.viewerReason,
        texture: panel.textureState, texture_reason: panel.textureReason,
      }})), null, 2);
      const active = activePanel();
      provenance.textContent = JSON.stringify({{
        ...REVIEW.provenance,
        active_mode: activeMode,
        viewer_url: activeAssets.viewerUrl,
        image_url_for_viewer: activeMode === 'file' ? 'embedded_data_url' : activeAssets.imageUrl,
        texture_expected: activeAssets.textureExpected,
        active_panel: active ? active.index + 1 : null,
        active_variant: active ? panelVariant(active).name : null,
        viewer_load_status: active?.viewerState || null,
        texture_load_status: active?.textureState || null
      }}, null, 2);
    }}
    window.addEventListener('message', (event) => {{
      const data = event.data;
      if (!data || typeof data !== 'object') return;
      if (event.source === focusFrame.contentWindow) {{
        if (data.type === 'hohonet_viewer_ready') {{
          focusViewerReady = true;
          sendFocusLayout();
          return;
        }}
        if (data.type === 'hohonet_geometry_selection') {{
          inspector.textContent = JSON.stringify(data.selection || {{}}, null, 2);
          return;
        }}
        if (data.type === 'hohonet_measurement_status') {{
          measurement.textContent = JSON.stringify(data.measurement || {{}}, null, 2);
          return;
        }}
        return;
      }}
      const panel = panels.find((row) => event.source === row.frame.contentWindow);
      if (!panel) return;
      if (data.type === 'hohonet_viewer_ready') {{
        clearTimeout(panel.viewerTimeout);
        panel.viewerState = 'ready';
        panel.viewerReason = data.version || 'viewer_ready';
        sendLayout(panel);
        updateTextureUi();
        return;
      }}
      if (data.type === 'hohonet_geometry_selection') {{
        setActivePanel(panel.index);
        inspector.textContent = JSON.stringify(data.selection || {{}}, null, 2);
        return;
      }}
      if (data.type === 'hohonet_measurement_status') {{
        if (panel === activePanel()) measurement.textContent = JSON.stringify(data.measurement || {{}}, null, 2);
        return;
      }}
      if (data.type !== 'hohonet_texture_status') return;
      panel.textureState = data.status || (data.hasTexture ? 'loaded' : 'failed');
      panel.textureReason = data.reason || null;
      if (['loaded', 'failed', 'unavailable'].includes(panel.textureState)) {{
        clearTimeout(panel.textureTimeout);
        panel.textureTimeout = null;
      }}
      updateTextureUi();
    }});
    function updateTriageUi(variant) {{
      const data = variant.triage || {{}};
      triage.textContent = JSON.stringify(data, null, 2);
      const manualReview = data.manual_review_candidate === true;
      const sensitivityOnly = data.sensitivity_only === true;
      const blocked = data.decision_class === 'partial_diagnostic' || data.direct_ls_trial_allowed === false;
      triageWarning.textContent = sensitivityOnly
        ? 'SENSITIVITY ONLY — not a micro-refinement candidate; cannot enter M4.2.'
        : manualReview
        ? 'MANUAL-REVIEW CANDIDATE — visual review required; no automatic fix is claimed.'
        : blocked
          ? 'PARTIAL DIAGNOSTIC ONLY — do not apply directly in LS. Primary unresolved edges: ' + JSON.stringify(data.primary_unresolved_edges || [])
          : '';
      triageWarning.style.display = sensitivityOnly || manualReview || blocked ? 'block' : 'none';
    }}
    function updateActiveUi() {{
      const panel = activePanel(); if (!panel) return;
      const variant = panelVariant(panel);
      metrics.textContent = JSON.stringify(variant.summary, null, 2);
      updateTriageUi(variant);
      updateCompareTable();
    }}
    function postPanelCommand(panel, command, payload = {{}}) {{
      if (!panel || panel.viewerState !== 'ready') return;
      panel.frame.contentWindow.postMessage({{type:'hohonet_inspection_command', command, ...payload}}, '*');
    }}
    function postActiveInspectionCommand(command, payload = {{}}) {{ postPanelCommand(activePanel(), command, payload); }}
    function broadcastInspectionCommand(command, payload = {{}}) {{
      panels.forEach((panel) => postPanelCommand(panel, command, payload));
    }}
    function syncMeasureMode() {{
      panels.forEach((panel) => postPanelCommand(panel, 'set_measure_mode', {{enabled: measureMode && panel === activePanel()}}));
    }}
    function setActivePanel(index) {{
      if (!panels[index]) return;
      activePanelIndex = index;
      panels.forEach((panel) => panel.element.classList.toggle('active-panel', panel.index === index));
      inspector.textContent = 'Click a corner or wall.';
      measurement.textContent = measureMode ? 'Select two corner points.' : 'Measure mode is off.';
      issueCursor = -1;
      syncMeasureMode();
      updateActiveUi();
      updateTextureUi();
    }}
    function sendLayout(panel) {{
      const variant = panelVariant(panel);
      if (!panel.frame.contentWindow || panel.viewerState !== 'ready') return;
      if (activeAssets.textureExpected) {{
        clearTimeout(panel.textureTimeout);
        panel.textureState = 'pending';
        panel.textureReason = 'waiting_for_viewer_texture_status';
      }}
      panel.frame.contentWindow.postMessage({{
        type: 'update_layout', corners: variant.corners, baseCorners: variant.corners,
        previewOrder: variant.corners.map((_, i) => i), previewOrderActive: true,
        preserveOrder: true, width: REVIEW.width, height: REVIEW.height,
        imageUrl: activeAssets.imageUrl, previewSignature: 'm15-23-6-' + panel.id + '-' + variant.name,
        variantName: variant.name, inspectionMode: true,
        inspectionMetadata: variant.inspection,
        changedPairIndices: variant.changedPairIndices || [],
        changedWallIndices: variant.changedWallIndices || [],
        ghostCorners: ghostVisible && variant.name !== 'original' ? REVIEW.variants[0].corners : null,
        displayOptions: {{ghost:ghostVisible, measureMode:measureMode && panel === activePanel(), texture:textureVisible}}
      }}, '*');
      panel.frame.contentWindow.postMessage({{type:'set_label_visibility', visible:labelsVisible}}, '*');
      if (activeAssets.textureExpected) {{
        panel.textureTimeout = setTimeout(() => {{
          if (panel.textureState === 'pending' || panel.textureState === 'loading') {{
            panel.textureState = 'failed';
            panel.textureReason = 'texture_status_timeout';
            updateTextureUi();
          }}
        }}, 5000);
      }}
      updatePanelHeader(panel);
      updateTextureUi();
    }}
    function sendFocusLayout() {{
      const variant = focusVariant();
      if (!focusFrame.contentWindow || !focusViewerReady) return;
      focusFrame.contentWindow.postMessage({{
        type: 'update_layout', corners: variant.corners, baseCorners: variant.corners,
        previewOrder: variant.corners.map((_, i) => i), previewOrderActive: true,
        preserveOrder: true, width: REVIEW.width, height: REVIEW.height,
        imageUrl: activeAssets.imageUrl, previewSignature: 'm15-23-7-focus-' + variant.name,
        variantName: variant.name, inspectionMode: true,
        inspectionMetadata: variant.inspection,
        changedPairIndices: variant.changedPairIndices || [],
        changedWallIndices: variant.changedWallIndices || [],
        ghostCorners: ghostVisible && variant.name !== 'original' ? REVIEW.variants[0].corners : null,
        displayOptions: {{ghost:ghostVisible, measureMode:false, texture:textureVisible}}
      }}, '*');
      focusFrame.contentWindow.postMessage({{type:'set_label_visibility', visible:labelsVisible}}, '*');
      focusVariantName.textContent = variant.name + ' | drag pane titles to dock left/right/top/bottom';
      renderFocus2DOverlay();
    }}
    function refreshAllPanels() {{
      panels.forEach((panel) => sendLayout(panel));
      updateActiveUi();
      sendFocusLayout();
    }}
    function layoutPanels() {{
      const count = panels.length;
      const rowCount = count % 2 === 0 ? count / 2 : (count + 1) / 2;
      const visibleRows = Math.min(rowCount, 2);
      const styles = getComputedStyle(views);
      const verticalPadding = parseFloat(styles.paddingTop) + parseFloat(styles.paddingBottom);
      const rowGap = parseFloat(styles.rowGap) || 8;
      const innerHeight = Math.max(0, views.clientHeight - verticalPadding);
      const rowHeight = Math.max(180, (innerHeight - rowGap * (visibleRows - 1)) / visibleRows);
      views.style.gridTemplateRows = `repeat(${{rowCount}}, ${{rowHeight}}px)`;
      panels.forEach((panel, index) => {{
        panel.element.style.gridColumn = count % 2 === 1 && index === 0 ? '1 / -1' : 'auto';
      }});
    }}
    function reindexPanels() {{
      panels.forEach((panel, index) => {{
        panel.index = index;
        panel.number.textContent = `P${{index + 1}}`;
        panel.removeButton.setAttribute('aria-label', `Remove panel ${{index + 1}}`);
        updatePanelHeader(panel);
      }});
    }}
    function updatePanelControls() {{
      const limit = Math.min(MAX_COMPARE_PANELS, REVIEW.variants.length);
      panelCountStatus.textContent = `Panels ${{panels.length}} / ${{limit}}`;
      addPanelButton.disabled = panels.length >= limit;
      panels.forEach((panel) => {{ panel.removeButton.disabled = panels.length <= 1; }});
    }}
    function nextUnusedVariantIndex() {{
      const used = new Set(panels.map((panel) => panel.variantIndex));
      return panelAssignments.find((variantIndex) => !used.has(variantIndex)) ?? 0;
    }}
    function createPanel(variantIndex) {{
      const element = panelTemplate.content.firstElementChild.cloneNode(true);
      const frame = element.querySelector('iframe');
      const selector = element.querySelector('.panel-variant');
      const panel = {{
        id: nextPanelId++, index: panels.length, element, frame, selector,
        number: element.querySelector('.panel-number'), status: element.querySelector('.panel-status'),
        removeButton: element.querySelector('.remove-panel'), variantIndex,
        viewerState: 'loading', viewerReason: 'waiting_for_viewer_ready', viewerTimeout: null,
        textureState: activeAssets.textureExpected ? 'pending' : 'unavailable', textureReason: null, textureTimeout: null,
      }};
      REVIEW.variants.forEach((variant, optionIndex) => {{
        const option = document.createElement('option'); option.value = optionIndex; option.textContent = variant.displayName; selector.appendChild(option);
      }});
      selector.value = String(panel.variantIndex);
      element.querySelector('.panel-header').addEventListener('click', () => setActivePanel(panels.indexOf(panel)));
      selector.addEventListener('click', (event) => event.stopPropagation());
      selector.addEventListener('change', () => {{
        panel.variantIndex = Number(selector.value); setActivePanel(panels.indexOf(panel)); sendLayout(panel); updateActiveUi();
      }});
      panel.removeButton.addEventListener('click', (event) => {{ event.stopPropagation(); removePanel(panel); }});
      panels.push(panel); views.appendChild(element); reindexPanels(); layoutPanels(); updatePanelControls();
      panel.viewerTimeout = setTimeout(() => {{
        if (panel.viewerState !== 'ready') {{
          panel.viewerState = 'failed'; panel.viewerReason = 'viewer_ready_timeout'; updateTextureUi();
        }}
      }}, 5000);
      frame.src = activeAssets.viewerUrl;
      return panel;
    }}
    function addPanel() {{
      if (panels.length >= Math.min(MAX_COMPARE_PANELS, REVIEW.variants.length)) return;
      createPanel(nextUnusedVariantIndex());
      updateCompareTable(); updateTextureUi();
    }}
    function removePanel(panel) {{
      if (panels.length <= 1) return;
      const activeBefore = activePanel();
      const removeIndex = panels.indexOf(panel);
      if (removeIndex < 0) return;
      clearTimeout(panel.viewerTimeout); clearTimeout(panel.textureTimeout);
      panels.splice(removeIndex, 1); panel.element.remove();
      reindexPanels(); layoutPanels(); updatePanelControls();
      if (panel === activeBefore) {{
        setActivePanel(Math.max(0, removeIndex - 1));
      }} else {{
        activePanelIndex = panels.indexOf(activeBefore);
        panels.forEach((row) => row.element.classList.toggle('active-panel', row === activeBefore));
        updateCompareTable(); updateTextureUi();
      }}
    }}
    function setFocusReviewOpen(open) {{
      focusReview.classList.toggle('open', open);
      focusReview.setAttribute('aria-hidden', open ? 'false' : 'true');
      if (!open) return;
      const panel = activePanel();
      focusVariantIndex = panel ? panel.variantIndex : 0;
      focusVariantName.textContent = focusVariant().name + ' | drag pane titles to dock left/right/top/bottom';
      focusCoordinateReadout.textContent = 'Click 2D to show LS/pixel coordinates.';
      renderFocus2DOverlay();
      if (!focusFrame.getAttribute('src')) focusFrame.src = activeAssets.viewerUrl;
      sendFocusLayout();
      requestAnimationFrame(sizeFocus2DViewbox);
    }}
    function cycleFocusPlacement() {{
      const order = ['right', 'bottom', 'left', 'top'];
      const current = focusStage.dataset.placement || 'right';
      setFocusPlacement(order[(order.indexOf(current) + 1) % order.length] || 'right');
    }}
    addPanelButton.addEventListener('click', addPanel);
    window.addEventListener('resize', layoutPanels);
    window.addEventListener('resize', sizeFocus2DViewbox);
    document.getElementById('open-2d-review').addEventListener('click', () => setFocusReviewOpen(true));
    document.getElementById('close-2d-review').addEventListener('click', () => setFocusReviewOpen(false));
    document.getElementById('focus-layout-cycle').addEventListener('click', cycleFocusPlacement);
    document.addEventListener('keydown', (event) => {{
      if (event.key === 'Escape' && focusReview.classList.contains('open')) setFocusReviewOpen(false);
    }});
    document.querySelectorAll('.focus-drag-handle').forEach((handle) => {{
      handle.addEventListener('pointerdown', (event) => {{
        focusDraggingPane = handle.dataset.focusPane || '2d';
        handle.setPointerCapture(event.pointerId);
        focusStage.classList.add('drag-over');
      }});
      handle.addEventListener('pointermove', (event) => {{
        if (!focusDraggingPane) return;
        setFocusPlacement(placementFromPointer(event), focusDraggingPane);
      }});
      handle.addEventListener('pointerup', (event) => {{
        if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
        focusStage.classList.remove('drag-over');
        focusDraggingPane = null;
      }});
    }});
    const focusResizeHandle = document.getElementById('focus-resize-handle');
    focusResizeHandle.addEventListener('pointerdown', (event) => {{
      focusResizing = true;
      focusResizeHandle.setPointerCapture(event.pointerId);
      resizeFocusFromPointer(event);
    }});
    focusResizeHandle.addEventListener('pointermove', (event) => {{
      if (focusResizing) resizeFocusFromPointer(event);
    }});
    focusResizeHandle.addEventListener('pointerup', (event) => {{
      if (focusResizeHandle.hasPointerCapture(event.pointerId)) focusResizeHandle.releasePointerCapture(event.pointerId);
      focusResizing = false;
    }});
    document.getElementById('labels').addEventListener('click', (event) => {{
      labelsVisible = !labelsVisible; event.currentTarget.textContent = labelsVisible ? 'Hide corners' : 'Show corners';
      panels.forEach((panel) => {{ if (panel.viewerState === 'ready') panel.frame.contentWindow.postMessage({{type:'set_label_visibility', visible:labelsVisible}}, '*'); }});
      if (focusViewerReady) focusFrame.contentWindow.postMessage({{type:'set_label_visibility', visible:labelsVisible}}, '*');
    }});
    document.getElementById('texture').addEventListener('click', (event) => {{
      textureVisible = !textureVisible;
      event.currentTarget.textContent = textureVisible ? 'Texture: ON' : 'Texture: OFF';
      event.currentTarget.classList.toggle('active', textureVisible);
      refreshAllPanels();
    }});
    document.getElementById('ghost').addEventListener('click', (event) => {{
      ghostVisible = !ghostVisible; event.currentTarget.classList.toggle('active', ghostVisible); refreshAllPanels();
    }});
    document.getElementById('measure').addEventListener('click', (event) => {{
      measureMode = !measureMode; event.currentTarget.classList.toggle('active', measureMode);
      measurement.textContent = measureMode ? 'Select two corner points.' : 'Measure mode is off.'; syncMeasureMode();
    }});
    document.getElementById('next-issue').addEventListener('click', () => {{
      const panel = activePanel(); if (!panel) return;
      const issues = panelVariant(panel).inspection.issues || []; if (!issues.length) return;
      issueCursor = (issueCursor + 1) % issues.length; postActiveInspectionCommand('select_issue', {{issue:issues[issueCursor]}});
    }});
    document.querySelectorAll('[data-camera]').forEach((button) => button.addEventListener('click', () => {{
      broadcastInspectionCommand('camera_preset', {{preset:button.dataset.camera}});
    }}));
    document.querySelectorAll('#focus-overlay-controls input').forEach((input) => input.addEventListener('input', renderFocus2DOverlay));
    for (let index = 0; index < defaultPanelCount; index += 1) {{
      createPanel(panelAssignments[index] ?? index);
    }}
    setActivePanel(0);
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
    adaptive_probe_json: Path | None = None,
    semantic_search_json: Path | None = None,
    case_name: str | None = None,
    width: int = 1024,
    height: int = 512,
    coordinate_mode: str = "auto",
    camera_height: float = DEFAULT_CAMERA_HEIGHT,
    local_server_root: Path | None = None,
    candidate_limit: int = 5,
) -> dict[str, Path]:
    input_path = input_path.resolve()
    payload = _read_json(input_path)
    ordered_pairs, pair_source = extract_ordered_pairs(payload)
    image_info, resolved_image = resolve_local_image(
        payload, image_root=image_root, image_path=image_path
    )

    candidate_rows: list[dict[str, Any]] = []
    m1522_candidates = False
    candidate_provenance: dict[str, Any] | None = None
    candidate_sources: list[dict[str, Any]] = []
    if candidate_json is not None:
        candidate_json = candidate_json.resolve()
        candidate_payload = _read_json(candidate_json)
        hypothesis_core_candidates = (
            candidate_payload.get("schema_version") == HYPOTHESIS_CORE_SCHEMA_VERSION
        )
        m1522_candidates = isinstance(candidate_payload.get("candidates"), list)
        candidate_rows = (
            extract_hypothesis_core_candidate_rows(candidate_payload, limit=candidate_limit)
            if hypothesis_core_candidates
            else (
                extract_m1522_candidate_rows(
                    {**candidate_payload, "candidates": [
                        *candidate_payload.get("candidates", []),
                        *candidate_payload.get("visibility_candidates", []),
                    ]}, limit=candidate_limit
                )
                if m1522_candidates
                else extract_candidate_rows(candidate_payload, limit=candidate_limit)
            )
        )
        mapping = _mapping_lookup(candidate_payload)
        for index, pair in enumerate(ordered_pairs, start=1):
            if mapping.get(index) is not None:
                pair["source_preview_order_index"] = mapping[index]
        candidate_provenance = {
            "file": candidate_json.name,
            "sha256": _sha256(candidate_json),
            "source": (
                "manhattan_hypothesis_ranking_core_json"
                if hypothesis_core_candidates
                else (
                    "m15_22_candidate_search_json"
                    if m1522_candidates
                    else "candidate_json"
                )
            ),
        }
        candidate_sources.append(candidate_provenance)
    elif candidate_report is not None:
        candidate_report = candidate_report.resolve()
        candidate_rows = extract_candidate_rows_from_report(candidate_report)
        candidate_provenance = {
            "file": candidate_report.name,
            "sha256": _sha256(candidate_report),
            "source": "candidate_report_fallback",
        }
        candidate_sources.append(candidate_provenance)

    for source_path, source_stage, limit in (
        (adaptive_probe_json, "m15.26", 1),
        (semantic_search_json, "m15.27", 5),
    ):
        if source_path is None:
            continue
        resolved_source = source_path.resolve()
        source_payload = _read_json(resolved_source)
        candidate_rows.extend(
            extract_probe_candidate_rows(source_payload, source_stage=source_stage, limit=limit)
        )
        candidate_sources.append(
            {
                "file": resolved_source.name,
                "sha256": _sha256(resolved_source),
                "source": f"{source_stage}_top_candidates",
            }
        )

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
        candidate_pairs = apply_m1522_candidate(ordered_pairs, row) if isinstance(
            row.get("coordinate_changes"), list
        ) else apply_candidate_row(ordered_pairs, row)
        variant_name = str(row.get("candidate_id") or f"candidate_{index}")
        variant = build_projection_variant(
            variant_name,
            candidate_pairs,
            width=width,
            height=height,
            coordinate_mode=coordinate_mode,
            camera_height=camera_height,
            candidate_row=row,
        )
        variant["display_name"] = _candidate_display_label(row, variant_name)
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
            "candidate_sources": candidate_sources,
            "image": image_info,
        },
        "safety_boundary": SAFETY_BOUNDARY,
        "variants": variants,
        "preferred_panel_variants": [
            "original",
            *[
                str(row["candidate_id"])
                for row in candidate_rows
                if (
                    row.get("preferred_panel")
                    or row.get("review_role")
                    in {"m15.26_best", "m15.27_best", "m15.27_second"}
                )
                and row.get("candidate_id") is not None
            ],
        ][:4],
    }

    json_path = out_dir / "projection_metrics.json"
    report_path = out_dir / "projection_review_report.md"
    html_path = out_dir / "local_3d_review.html"
    launcher_path = out_dir / "open_local_3d_review.cmd"
    viewer_path = Path(__file__).resolve().parents[1] / "label_studio" / "vis_3d.html"
    server_viewer_url, server_image_url = _build_review_asset_urls(
        viewer_path=viewer_path,
        resolved_image=resolved_image,
        out_dir=out_dir,
        local_server_root=local_server_root,
    )
    file_viewer_url, _ = _build_review_asset_urls(
        viewer_path=viewer_path,
        resolved_image=resolved_image,
        out_dir=out_dir,
        local_server_root=None,
    )
    file_image_data_url, embed_info = _embedded_image_data_url(resolved_image)
    if resolved_image is not None and server_image_url is None:
        review_payload["input_provenance"]["image"]["warnings"].append(
            "resolved_image_outside_local_server_root_texture_unavailable"
        )
    server_texture_expected = bool(
        resolved_image is not None
        and review_payload["input_provenance"]["image"]["image_exists"]
        and server_image_url
    )
    review_payload["local_review_assets"] = {
        "viewer_url": server_viewer_url,
        "image_url_for_viewer": server_image_url,
        "texture_expected": server_texture_expected,
        "server": {
            "viewer_url": server_viewer_url,
            "image_url_for_viewer": server_image_url,
            "texture_expected": server_texture_expected,
        },
        "file": {"viewer_url": file_viewer_url, "embed": embed_info},
    }

    json_path.write_text(
        json.dumps(review_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    report_path.write_text(render_markdown_report(review_payload), encoding="utf-8", newline="\n")
    html_path.write_text(
        render_review_html(review_payload, file_image_data_url=file_image_data_url), encoding="utf-8", newline="\n"
    )
    output_paths = {
        "json": json_path,
        "report": report_path,
        "html": html_path,
    }
    try:
        launcher_text = _windows_launcher_text(out_dir, html_path)
    except ValueError:
        pass
    else:
        launcher_path.write_text(launcher_text, encoding="utf-8", newline="")
        output_paths["launcher"] = launcher_path
    return output_paths


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--image-root", type=Path)
    parser.add_argument("--image-path", type=Path)
    parser.add_argument("--candidate-json", type=Path)
    parser.add_argument("--candidate-report", type=Path)
    parser.add_argument("--adaptive-probe-json", type=Path)
    parser.add_argument("--semantic-search-json", type=Path)
    parser.add_argument("--candidate-limit", type=int, default=5)
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
        adaptive_probe_json=args.adaptive_probe_json,
        semantic_search_json=args.semantic_search_json,
        case_name=args.case_name,
        width=args.width,
        height=args.height,
        coordinate_mode=args.coordinate_mode,
        camera_height=args.camera_height,
        local_server_root=args.local_server_root,
        candidate_limit=args.candidate_limit,
    )
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
