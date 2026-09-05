from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw
from scipy.optimize import linear_sum_assignment


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.thesis_main.analysis.materialize_model_gt_threshold_screen import (  # noqa: E402
    _ordered_pairs,
    _read_test_gt,
    _read_txt,
)
from tools.thesis_main.data_prep.build_annotation_uncertainty_batch1_review import (  # noqa: E402
    HEIGHT,
    LABEL_FONT,
    WIDTH,
    _panel,
    _reference_pairs,
    _sha256,
)


DEFAULT_OUTPUT = ROOT / "analysis_results/annotation_uncertainty_prescreen_20260903_v1"
IMAGE_ID_RE = re.compile(r"[A-Za-z0-9]{11}_[0-9a-fA-F]{32}")
HISTORY_EXCLUDED_TOKENS = ("groudtruth", "groundtruth", "raw_data_package_manifest", "人工精标")
SCOPE_HINTS = {"core", "boundary", "reject_candidate"}
BOUNDARY_FAMILIES = (
    "open_or_multiroom",
    "curved_or_non_manhattan",
    "seam",
    "mirror_or_glass",
    "severe_occlusion",
    "reference_prelabel_structural_conflict",
)
FLAG_REASONS = {
    "order_provenance_unavailable": "原始环序来源不可恢复；仅提示表示来源，不据此判断几何。",
    "non_cyclic_reordering": "近邻角点对应关系不是循环移位或反向环序。",
    "reversed_winding": "反向环序拟合更好；这属于表示诊断。",
    "alignment_ambiguous": "多个环序对齐的代价接近，需要人工查看。",
    "pair_count_difference": "参考标注候选与模型预标注的角点对数量不同。",
    "visible_boundary_difference": "两者的边界差异达到机器提示阈值。",
}


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _id_set_sha256(image_ids: list[str] | set[str]) -> str:
    return hashlib.sha256(("\n".join(sorted(image_ids)) + "\n").encode()).hexdigest()


def _flag(code: str, reason: str | None = None) -> dict[str, str]:
    return {"code": code, "reason": reason or FLAG_REASONS.get(code, code)}


def _pair_distance(a: dict[str, float], b: dict[str, float], width: float) -> float:
    dx = abs((float(a["x"]) - float(b["x"])) % width)
    dx = min(dx, width - dx)
    return float(np.sqrt(dx * dx + (a["y_ceiling"] - b["y_ceiling"]) ** 2 + (a["y_floor"] - b["y_floor"]) ** 2))


def diagnose_pair_order(
    reference: list[dict[str, float]],
    candidate: list[dict[str, float]],
    *,
    width: float = WIDTH,
) -> dict[str, Any]:
    """Compare complete ceiling/floor pairs on a circular x-axis.

    Cyclic starting-point changes are normalized silently. Reversal is only a
    representation diagnostic; a non-cyclic warning is emitted only when a
    close one-to-one pair match makes the permutation identifiable.
    """
    if len(reference) != len(candidate):
        return {
            "status": "not_comparable_pair_count",
            "reference_pair_count": len(reference),
            "candidate_pair_count": len(candidate),
            "warnings": [],
        }
    count = len(reference)
    if count < 2:
        return {
            "status": "not_comparable_too_few_pairs",
            "reference_pair_count": count,
            "candidate_pair_count": count,
            "warnings": [],
        }

    fits: list[dict[str, Any]] = []
    for orientation, sequence in (("forward", candidate), ("reversed", list(reversed(candidate)))):
        for shift in range(count):
            aligned = sequence[shift:] + sequence[:shift]
            distances = [_pair_distance(a, b, width) for a, b in zip(reference, aligned)]
            fits.append({
                "orientation": orientation,
                "shift": shift,
                "rmse": float(np.sqrt(np.mean(np.square(distances)))),
            })
    fits.sort(key=lambda item: (item["rmse"], item["orientation"] != "forward", item["shift"]))
    best, second = fits[0], fits[1]
    warnings: list[str] = []

    cost = np.asarray([[_pair_distance(a, b, width) for b in candidate] for a in reference])
    row_indices, column_indices = linear_sum_assignment(cost)
    permutation = [0] * count
    matched = []
    for row_index, column_index in zip(row_indices.tolist(), column_indices.tolist()):
        permutation[row_index] = column_index
        matched.append(float(cost[row_index, column_index]))
    steps = [int((permutation[(index + 1) % count] - permutation[index]) % count) for index in range(count)]
    is_dihedral = all(step == 1 for step in steps) or all(step == count - 1 for step in steps)
    if max(matched, default=float("inf")) <= 10.0 and not is_dihedral:
        warnings.append("non_cyclic_reordering")
    elif best["orientation"] == "reversed" and best["rmse"] <= 10.0:
        warnings.append("reversed_winding")
    if count >= 3 and second["rmse"] <= 10.0 and second["rmse"] - best["rmse"] <= 0.25:
        warnings.append("alignment_ambiguous")

    return {
        "status": "comparable",
        "reference_pair_count": count,
        "candidate_pair_count": count,
        "best_orientation": best["orientation"],
        "best_shift": int(best["shift"]),
        "best_rmse_px": round(float(best["rmse"]), 6),
        "second_best_rmse_px": round(float(second["rmse"]), 6),
        "assignment_max_distance_px": round(max(matched), 6),
        "assignment_permutation": permutation,
        "warnings": warnings,
    }


def _test_ids(path: Path) -> set[str]:
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) != 2:
            raise ValueError(f"invalid Test split line: {line!r}")
        image_id = f"{fields[0]}_{fields[1]}"
        if image_id in ids:
            raise ValueError(f"duplicate Test image_id: {image_id}")
        ids.add(image_id)
    return ids


def _history_annotations(root: Path, test_ids: set[str]) -> tuple[dict[str, list[str]], list[dict[str, str]]]:
    sources: dict[str, set[str]] = defaultdict(set)
    source_artifacts = []
    for path in sorted((root / "export_label").rglob("*.json")):
        relative = _relative(root, path)
        if any(token in relative.lower() for token in HISTORY_EXCLUDED_TOKENS):
            continue
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, list):
            continue
        source_artifacts.append({"path": relative, "sha256": _sha256(path)})
        for task in payload:
            if not isinstance(task, dict):
                raise ValueError(f"non-object task in {relative}")
            annotations = task.get("annotations") or []
            if not isinstance(annotations, list):
                raise ValueError(f"annotations is not a list in {relative}")
            active = [item for item in annotations if isinstance(item, dict) and not bool(item.get("was_cancelled"))]
            if not active:
                continue
            text = json.dumps(task.get("data") or {}, ensure_ascii=False)
            for image_id in set(IMAGE_ID_RE.findall(text)) & test_ids:
                sources[image_id].add(relative)
    return {key: sorted(value) for key, value in sources.items()}, source_artifacts


def _load_metrics(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row.get("split") == "test"]
    result = {}
    for row in rows:
        image_id = row["image_id"]
        if image_id in result:
            raise ValueError(f"duplicate Test metrics row: {image_id}")
        result[image_id] = row
    return result


def _manual_order(row: dict[str, str], path: Path) -> tuple[list[dict[str, float]] | None, bool]:
    if row["gt_source_type"] != "confirmed_user_manual_gt_correction":
        return _ordered_pairs(_read_txt(path), source=path), True
    points = _read_test_gt(path).get(row["image_id"])
    if points is None:
        raise ValueError(f"manual reference member missing: {row['image_id']}")
    try:
        return _ordered_pairs(points, source=path), True
    except ValueError:
        return None, False


def _validate_model_json(path: Path, image_id: str, expected_pairs: int) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    corners = ((payload.get("layout") or {}).get("corners") or []) if isinstance(payload, dict) else []
    if Path(str(payload.get("image_filename") or "")).stem != image_id:
        raise ValueError(f"model JSON image mismatch: {path}")
    if not isinstance(corners, list) or len(corners) != expected_pairs:
        raise ValueError(f"model JSON pair count mismatch: {path}")
    for item in corners:
        if not all(key in item for key in ("x", "y_ceiling", "y_floor")):
            raise ValueError(f"invalid model JSON corner: {path}")
    return payload


def build_inventory(root: Path = ROOT) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    test_path = root / "data/mp3d_test.txt"
    registry_path = root / "analysis_results/uncertainty_substrate_20260823_v1/image_registry.csv"
    metrics_path = root / "analysis_results/model_initialization_audit_hybrid_gt_20260823_v4/model_initialization_metrics.csv"
    test_ids = _test_ids(test_path)
    with registry_path.open(encoding="utf-8-sig", newline="") as handle:
        exposed = {row["image_id"] for row in csv.DictReader(handle)} & test_ids
    target_ids = test_ids - exposed
    history, history_artifacts = _history_annotations(root, test_ids)
    metrics = _load_metrics(metrics_path)
    if set(metrics) != test_ids:
        raise ValueError(f"Test metrics set mismatch: {len(metrics)} != {len(test_ids)}")

    rows = []
    unique_assets: dict[str, set[str]] = defaultdict(set)
    for index, image_id in enumerate(sorted(target_ids), 1):
        metric = metrics[image_id]
        image_path = root / metric["image_path"]
        model_path = root / metric["model_path"]
        reference_path = root / metric["gt_path"]
        model_json_path = root / f"output/layout_json/{image_id}.json"
        for path in (image_path, model_path, reference_path, model_json_path):
            if not path.is_file():
                raise FileNotFoundError(path)
        if str(metric.get("model_pair_encoding_valid", "")).lower() != "true":
            raise ValueError(f"invalid model pair encoding: {image_id}")
        if metric.get("model_sha256") and _sha256(model_path) != metric["model_sha256"]:
            raise ValueError(f"model SHA mismatch: {image_id}")
        if metric.get("gt_sha256") and _sha256(reference_path) != metric["gt_sha256"]:
            raise ValueError(f"reference SHA mismatch: {image_id}")
        with Image.open(image_path) as source:
            source.verify()
        model_pairs = _ordered_pairs(_read_txt(model_path), source=model_path)
        reference_pairs = _reference_pairs(metric, reference_path)
        if len(model_pairs) != int(metric["model_pair_count"]) or len(reference_pairs) != int(metric["gt_pair_count"]):
            raise ValueError(f"pair count drift: {image_id}")
        _validate_model_json(model_json_path, image_id, len(model_pairs))
        ordered_reference, order_available = _manual_order(metric, reference_path)
        if ordered_reference is None:
            order_diagnostic = {
                "status": "reference_order_unavailable",
                "reference_pair_count": len(reference_pairs),
                "candidate_pair_count": len(model_pairs),
                "warnings": ["order_provenance_unavailable"],
            }
        else:
            order_diagnostic = diagnose_pair_order(ordered_reference, model_pairs)

        pair_delta = len(model_pairs) - len(reference_pairs)
        mask_difference = float(metric["layout_mask_difference"])
        boundary_rmse = float(metric["boundary_rmse_px"])
        reference_flags = []
        prelabel_flags = []
        risk_families = []
        if not order_available:
            reference_flags.append(_flag("order_provenance_unavailable"))
        for warning in order_diagnostic["warnings"]:
            if warning != "order_provenance_unavailable":
                prelabel_flags.append(_flag(warning))
        if pair_delta:
            prelabel_flags.append(_flag("pair_count_difference"))
            risk_families.append("reference_prelabel_structural_conflict")
        if mask_difference >= 0.08 or boundary_rmse >= 15.0:
            prelabel_flags.append(_flag("visible_boundary_difference"))

        assets = {
            "image": {"path": _relative(root, image_path), "sha256": _sha256(image_path)},
            "reference": {
                "path": _relative(root, reference_path),
                "sha256": _sha256(reference_path),
                "source_type": metric["gt_source_type"],
                "member_image_id": image_id,
            },
            "model_txt": {"path": _relative(root, model_path), "sha256": _sha256(model_path)},
            "model_json": {"path": _relative(root, model_json_path), "sha256": _sha256(model_json_path)},
        }
        for name in ("image", "model_txt", "model_json"):
            if assets[name]["path"] in unique_assets[name]:
                raise ValueError(f"duplicate {name} asset: {assets[name]['path']}")
            unique_assets[name].add(assets[name]["path"])
        history_sources = history.get(image_id, [])
        rows.append({
            "machine_id": f"M{index:03d}",
            "image_id": image_id,
            "building_id": image_id.split("_", 1)[0],
            "history_layer": "historical_annotation_record_exists" if history_sources else "no_existing_annotation_record",
            "history_annotation_source_paths": history_sources,
            "assets": assets,
            "reference_lineage": {
                "source_type": metric["gt_source_type"],
                "raw_ring_order_available": order_available,
                "special_manual_reference": metric["gt_source_type"] == "confirmed_user_manual_gt_correction",
            },
            "geometry_summary": {
                "reference_pair_count": len(reference_pairs),
                "prelabel_pair_count": len(model_pairs),
                "pair_count_delta": pair_delta,
                "layout_mask_difference": mask_difference,
                "boundary_rmse_px": boundary_rmse,
            },
            "ordering_diagnostic": order_diagnostic,
            "machine": {
                "scope_hint": "core",
                "scope_reason": "待接触表机器初查。",
                "risk_families": risk_families,
                "reference_flags": reference_flags,
                "prelabel_flags": prelabel_flags,
                "visual_review_status": "pending",
                "advisory_only": True,
            },
            "_image_path": image_path,
            "_reference_pairs": reference_pairs,
            "_model_pairs": model_pairs,
        })

    summary = {
        "test_total": len(test_ids),
        "formal_exposed": len(exposed),
        "formal_unsubmitted": len(rows),
        "history_layer_counts": dict(Counter(row["history_layer"] for row in rows)),
        "reference_source_counts": dict(Counter(row["reference_lineage"]["source_type"] for row in rows)),
        "building_counts_no_existing_annotation": dict(sorted(Counter(
            row["building_id"] for row in rows if row["history_layer"] == "no_existing_annotation_record"
        ).items())),
        "asset_checks": {
            "image_unique": len(unique_assets["image"]) == len(rows),
            "model_txt_unique": len(unique_assets["model_txt"]) == len(rows),
            "model_json_unique": len(unique_assets["model_json"]) == len(rows),
            "all_parsed": True,
        },
        "source_artifacts": {
            "test_split": {"path": _relative(root, test_path), "sha256": _sha256(test_path)},
            "formal_exposure_registry": {"path": _relative(root, registry_path), "sha256": _sha256(registry_path)},
            "model_initialization_metrics": {"path": _relative(root, metrics_path), "sha256": _sha256(metrics_path)},
            "history_export_files": history_artifacts,
        },
    }
    if summary["test_total"] != 458 or summary["formal_exposed"] != 144 or summary["formal_unsubmitted"] != 314:
        raise ValueError(f"closed-set count drift: {summary}")
    if summary["history_layer_counts"] != {"no_existing_annotation_record": 166, "historical_annotation_record_exists": 148}:
        raise ValueError(f"history layer drift: {summary['history_layer_counts']}")
    return rows, summary


def _risk_count(row: dict[str, Any]) -> int:
    machine = row["machine"]
    return len(machine["risk_families"]) + len(machine["reference_flags"]) + len(machine["prelabel_flags"])


def _available_by_building(
    rows: list[dict[str, Any]],
    scope: str,
    selected_ids: set[str],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["image_id"] not in selected_ids and row["machine"]["scope_hint"] == scope:
            result[row["building_id"]].append(row)
    for values in result.values():
        values.sort(key=lambda row: (_risk_count(row), row["image_id"]))
    return result


def select_human_batch(
    rows: list[dict[str, Any]],
    *,
    core_target: int = 24,
    boundary_target: int = 6,
    max_per_building: int = 3,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pool = [row for row in rows if row["history_layer"] == "no_existing_annotation_record"]
    buildings = sorted({row["building_id"] for row in pool})
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    building_counts: Counter[str] = Counter()
    composition_deviation: list[str] = []

    def add(row: dict[str, Any]) -> None:
        selected.append(row)
        selected_ids.add(row["image_id"])
        building_counts[row["building_id"]] += 1

    # Cover every building first, preferring low-risk core images.
    for building in buildings:
        candidates = sorted(
            (row for row in pool if row["building_id"] == building and row["machine"]["scope_hint"] in {"core", "boundary"}),
            key=lambda row: (row["machine"]["scope_hint"] != "core", _risk_count(row), row["image_id"]),
        )
        if not candidates:
            raise RuntimeError(f"building has no core/boundary candidate: {building}")
        add(candidates[0])

    def fill_round_robin(scope: str, target: int, family: str | None = None, at_most_one: bool = False) -> None:
        while sum(row["machine"]["scope_hint"] == scope for row in selected) < target:
            available = _available_by_building(pool, scope, selected_ids)
            progressed = False
            for building in buildings:
                if building_counts[building] >= max_per_building:
                    continue
                candidates = available.get(building, [])
                if family:
                    candidates = [row for row in candidates if family in row["machine"]["risk_families"]]
                if not candidates:
                    continue
                add(candidates[0])
                progressed = True
                if at_most_one or sum(row["machine"]["scope_hint"] == scope for row in selected) == target:
                    return
            if not progressed:
                return

    total_target = core_target + boundary_target
    initial_boundary = sum(row["machine"]["scope_hint"] == "boundary" for row in selected)
    fill_round_robin("core", min(core_target, total_target - initial_boundary))
    desired_boundary = total_target - sum(row["machine"]["scope_hint"] == "core" for row in selected)
    covered_families = {family for row in selected if row["machine"]["scope_hint"] == "boundary" for family in row["machine"]["risk_families"]}
    for family in BOUNDARY_FAMILIES:
        if family not in covered_families:
            fill_round_robin("boundary", desired_boundary, family=family, at_most_one=True)
            covered_families = {item for row in selected if row["machine"]["scope_hint"] == "boundary" for item in row["machine"]["risk_families"]}
    fill_round_robin("boundary", desired_boundary)

    # If one visual stratum is too small, fill the remaining slots from the
    # adjacent stratum and record the resulting composition instead of failing.
    if len(selected) < total_target:
        fill_round_robin("core", sum(row["machine"]["scope_hint"] == "core" for row in selected) + total_target - len(selected))
    if len(selected) < total_target:
        fill_round_robin("boundary", sum(row["machine"]["scope_hint"] == "boundary" for row in selected) + total_target - len(selected))
    covered_families = {item for row in selected if row["machine"]["scope_hint"] == "boundary" for item in row["machine"]["risk_families"]}

    core_count = sum(row["machine"]["scope_hint"] == "core" for row in selected)
    boundary_count = sum(row["machine"]["scope_hint"] == "boundary" for row in selected)
    if len(selected) != total_target:
        raise RuntimeError(f"insufficient adjacent-category candidates: {len(selected)}/{total_target}")
    if core_count != core_target or boundary_count != boundary_target:
        composition_deviation.append(f"available composition produced core={core_count}, boundary={boundary_count}")
    if set(building_counts) != set(buildings):
        raise RuntimeError("selection size or building coverage failed")
    if max(building_counts.values()) > max_per_building:
        raise RuntimeError("selection exceeded building cap")

    core_rows = [row for row in selected if row["machine"]["scope_hint"] == "core"]
    boundary_rows = [row for row in selected if row["machine"]["scope_hint"] == "boundary"]
    selected = core_rows + boundary_rows
    for index, row in enumerate(selected, 1):
        row["review_id"] = f"P30-{index:03d}"
    return selected, {
        "pool_definition": "formal_unsubmitted_test_without_existing_annotation_record",
        "pool_count": len(pool),
        "selected_count": len(selected),
        "core_count": core_count,
        "boundary_count": boundary_count,
        "building_count": len(building_counts),
        "building_counts": dict(sorted(building_counts.items())),
        "max_per_building": max(building_counts.values()),
        "covered_boundary_families": sorted(covered_families),
        "composition_deviation": composition_deviation,
    }


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not key.startswith("_")}


def _render_contact_sheets(rows: list[dict[str, Any]], output_dir: Path) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    panel_width, panel_height = 640, 320
    columns, rows_per_sheet = 2, 4
    per_sheet = columns * rows_per_sheet
    sheet_index = []
    for start in range(0, len(rows), per_sheet):
        subset = rows[start:start + per_sheet]
        canvas = Image.new("RGB", (columns * panel_width * 3, rows_per_sheet * (panel_height + 34)), "white")
        mapping = []
        for offset, row in enumerate(subset):
            source = Image.open(row["_image_path"]).convert("RGB").resize((WIDTH, HEIGHT))
            panels = [
                _panel(source, "原图", []),
                _panel(source, "参考标注候选", [(row["_reference_pairs"], (0, 230, 90))]),
                _panel(source, "模型预标注", [(row["_model_pairs"], (255, 70, 120))]),
            ]
            tile_x = (offset % columns) * panel_width * 3
            tile_y = (offset // columns) * (panel_height + 34)
            draw = ImageDraw.Draw(canvas)
            draw.rectangle((tile_x, tile_y, tile_x + panel_width * 3, tile_y + 34), fill=(25, 30, 36))
            draw.text((tile_x + 8, tile_y + 5), f"{row['machine_id']}  {row['image_id']}", fill="white", font=LABEL_FONT)
            for panel_index, panel in enumerate(panels):
                panel = panel.resize((panel_width, panel_height))
                canvas.paste(panel, (tile_x + panel_index * panel_width, tile_y + 34))
            mapping.append({"machine_id": row["machine_id"], "image_id": row["image_id"]})
        path = output_dir / f"sheet_{start // per_sheet + 1:03d}.jpg"
        canvas.save(path, quality=90)
        sheet_index.append({"path": path.name, "sha256": _sha256(path), "items": mapping})
    return sheet_index


def prepare_visual_review(rows: list[dict[str, Any]], summary: dict[str, Any], output_dir: Path) -> None:
    contact_sheets = _render_contact_sheets(rows, output_dir / "contact_sheets")
    id_hash = _id_set_sha256({row["image_id"] for row in rows})
    (output_dir / "contact_sheet_index.json").write_text(json.dumps({
        "schema_version": "annotation_uncertainty_prescreen_contact_sheets_v1",
        "image_count": len(rows),
        "image_ids_sha256": id_hash,
        "sheets": contact_sheets,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "machine_visual_review.template.json").write_text(json.dumps({
        "schema_version": "annotation_uncertainty_prescreen_machine_visual_review_v1",
        "reviewed_all_contact_sheets": False,
        "reviewed_image_ids_sha256": id_hash,
        "default": {
            "scope_hint": "core",
            "scope_reason": "接触表初查未记录明显 scope 边界信号；仍待人工最终判断。",
            "risk_families": [],
            "reference_flags": [],
            "prelabel_flags": [],
        },
        "overrides": {},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "inventory_preflight.json").write_text(json.dumps({
        "status": "machine_visual_review_pending",
        "summary": summary,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_flags(values: Any) -> list[dict[str, str]]:
    result = []
    for value in values or []:
        if isinstance(value, str):
            result.append(_flag(value))
        elif isinstance(value, dict) and value.get("code"):
            result.append(_flag(str(value["code"]), str(value.get("reason") or "") or None))
        else:
            raise ValueError(f"invalid flag: {value!r}")
    return result


def apply_visual_review(rows: list[dict[str, Any]], path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected_ids = {row["image_id"] for row in rows}
    if payload.get("reviewed_all_contact_sheets") is not True:
        raise ValueError("machine visual review is not marked complete")
    if payload.get("reviewed_image_ids_sha256") != _id_set_sha256(expected_ids):
        raise ValueError("machine visual review image set mismatch")
    default = payload.get("default") or {}
    by_machine_id = {row["machine_id"]: row["image_id"] for row in rows}
    overrides = payload.get("overrides") or {}
    normalized_overrides = {
        by_machine_id.get(key, key): value
        for key, value in overrides.items()
    }
    groups_by_image: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in payload.get("groups") or []:
        for machine_id in group.get("machine_ids") or []:
            image_id = by_machine_id.get(machine_id)
            if image_id is None:
                raise ValueError(f"unknown machine visual-review id: {machine_id}")
            groups_by_image[image_id].append(group)
    unknown = set(normalized_overrides) - expected_ids
    if unknown:
        raise ValueError(f"unknown visual-review image ids: {sorted(unknown)}")
    for row in rows:
        visual = dict(default)
        for group in groups_by_image.get(row["image_id"], []):
            visual.update({key: value for key, value in group.items() if key not in {"machine_ids", "risk_families", "reference_flags", "prelabel_flags"}})
            visual["risk_families"] = sorted(set(visual.get("risk_families") or []) | set(group.get("risk_families") or []))
            visual["reference_flags"] = list(visual.get("reference_flags") or []) + list(group.get("reference_flags") or [])
            visual["prelabel_flags"] = list(visual.get("prelabel_flags") or []) + list(group.get("prelabel_flags") or [])
        override = normalized_overrides.get(row["image_id"]) or {}
        visual.update({key: value for key, value in override.items() if key not in {"risk_families", "reference_flags", "prelabel_flags"}})
        visual["risk_families"] = sorted(set(visual.get("risk_families") or []) | set(override.get("risk_families") or []))
        visual["reference_flags"] = list(visual.get("reference_flags") or []) + list(override.get("reference_flags") or [])
        visual["prelabel_flags"] = list(visual.get("prelabel_flags") or []) + list(override.get("prelabel_flags") or [])
        scope_hint = visual.get("scope_hint")
        if scope_hint not in SCOPE_HINTS:
            raise ValueError(f"invalid scope hint for {row['image_id']}: {scope_hint}")
        if not str(visual.get("scope_reason") or "").strip():
            raise ValueError(f"missing scope reason for {row['image_id']}")
        machine = row["machine"]
        machine["scope_hint"] = scope_hint
        machine["scope_reason"] = str(visual["scope_reason"])
        risk_families = set(machine["risk_families"]) | set(visual.get("risk_families") or [])
        if risk_families - set(BOUNDARY_FAMILIES):
            raise ValueError(f"unknown risk families for {row['image_id']}: {sorted(risk_families - set(BOUNDARY_FAMILIES))}")
        machine["risk_families"] = sorted(risk_families)
        machine["reference_flags"] = machine["reference_flags"] + _normalize_flags(visual.get("reference_flags"))
        machine["prelabel_flags"] = machine["prelabel_flags"] + _normalize_flags(visual.get("prelabel_flags"))
        machine["visual_review_status"] = "reviewed_in_contact_sheet"


def _render_previews(rows: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for row in rows:
        source = Image.open(row["_image_path"]).convert("RGB").resize((WIDTH, HEIGHT))
        panels = {
            "original": _panel(source, "原图", []),
            "reference": _panel(source, "参考标注候选", [(row["_reference_pairs"], (0, 230, 90))]),
            "prelabel": _panel(source, "模型预标注", [(row["_model_pairs"], (255, 70, 120))]),
            "alignment": _panel(source, "对齐叠加：参考=绿色，模型=粉色", [
                (row["_reference_pairs"], (0, 230, 90)),
                (row["_model_pairs"], (255, 70, 120)),
            ]),
        }
        preview_assets = {}
        for name, panel in panels.items():
            path = output_dir / f"{row['review_id']}_{name}.jpg"
            panel.save(path, quality=92)
            preview_assets[name] = {"path": f"previews/{path.name}", "sha256": _sha256(path)}
        row["preview_assets"] = preview_assets
        row["preview_sha256"] = preview_assets["original"]["sha256"]


def write_review_html(rows: list[dict[str, Any]], output_dir: Path) -> None:
    items = []
    template_items = []
    for row in rows:
        item = _public_row(row)
        previews = item.get("preview_assets") or {
            name: {"path": f"previews/{row['review_id']}_{name}.jpg", "sha256": row.get("preview_sha256", "")}
            for name in ("original", "reference", "prelabel", "alignment")
        }
        item["preview_assets"] = previews
        item["image_href"] = "../../" + item["assets"]["image"]["path"]
        item["required_fields"] = ["scope"]
        if item["machine"]["reference_flags"]:
            item["required_fields"].append("reference_verdict")
        if item["machine"]["prelabel_flags"]:
            item["required_fields"].append("prelabel_verdict")
        items.append(item)
        template_items.append({
            "review_id": item["review_id"],
            "image_id": item["image_id"],
            "required_fields": item["required_fields"],
            "review": {"scope": "", "reference_verdict": "", "prelabel_verdict": "", "notes": ""},
        })
    (output_dir / "human_review_template.json").write_text(json.dumps({
        "schema_version": "annotation_uncertainty_prescreen_human_review_v1",
        "status": "empty_template_not_a_completed_review",
        "items": template_items,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    payload = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    page = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>导师定稿前 30 张图片初筛</title>
<style>
body{{font-family:system-ui,sans-serif;margin:0;background:#f4f6f8;color:#18212a}}header{{position:sticky;top:0;z-index:2;background:white;padding:12px 18px;border-bottom:1px solid #ccd3da}}main{{max-width:1120px;margin:auto;padding:16px}}.notice{{background:#fff4ce;border:1px solid #d8b64a;padding:11px}}.card{{background:white;border:1px solid #ccd3da;border-radius:8px;padding:14px;margin:16px 0}}img{{max-width:100%;height:auto;border:1px solid #d8dde3}}.meta{{font-size:13px;color:#44515d}}.hint{{padding:9px;background:#edf5ff;border-left:5px solid #4285c5}}fieldset{{border:1px solid #aeb8c2;margin:12px 0}}label.option{{display:inline-flex;gap:5px;margin:5px 14px 5px 0}}textarea{{width:100%;min-height:64px;box-sizing:border-box}}details{{margin:10px 0}}.overlays{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:8px}}button{{font:inherit;padding:7px 12px}}code{{word-break:break-all}}.flags{{font-size:13px;color:#704d00}}
</style></head><body><header><b>导师定稿前 30 张图片初筛</b>　<span id="progress"></span>　<button id="export">导出人工审阅 JSON</button></header>
<main><p class="notice">本包只是可撤回的候选初筛，不冻结样本、不进入正式实验。机器内容都是提示；最终判断由你完成。每张始终只需填写 scope 和可选备注，只有机器提示标注疑点时才需追加一个裁决。</p><div id="cards"></div></main>
<script>
const items={payload};const key='annotation-uncertainty-prescreen-30-v1';const saved=JSON.parse(localStorage.getItem(key)||'{{}}');
const scopeOptions=[['in_scope','范围内'],['out_of_scope','范围外'],['uncertain','不确定']];
const verdictOptions=[['no_obvious_issue','无明显问题'],['representation_or_order_only','仅表示/顺序问题'],['material_geometry_issue','存在实质几何问题'],['uncertain','看不准']];
function choices(name,options,value){{return options.map(([code,label])=>`<label class="option"><input type="radio" data-name="${{name}}" name="${{name}}-${{currentId}}" value="${{code}}" ${{value===code?'checked':''}}>${{label}}</label>`).join('')}}
let currentId='';
function flagText(flags){{return flags.map(x=>x.reason||x.code).join('；')}}
function render(){{const root=document.getElementById('cards');for(const x of items){{currentId=x.review_id;const s=saved[x.review_id]||{{}};const card=document.createElement('section');card.className='card';const p=x.preview_assets;card.innerHTML=`<h2>${{x.review_id}} · <code>${{x.image_id}}</code></h2><p class="meta">建筑：${{x.building_id}}</p><p class="hint">机器 scope 提示：<b>${{x.machine.scope_hint}}</b>。${{x.machine.scope_reason}}</p><a href="${{x.image_href}}"><img loading="lazy" src="${{p.original.path}}?v=${{p.original.sha256.slice(0,12)}}" alt="${{x.image_id}} 原图"></a><details><summary>展开参考、模型与对齐叠加图</summary><div class="overlays"><img loading="lazy" src="${{p.reference.path}}?v=${{p.reference.sha256.slice(0,12)}}" alt="参考标注候选"><img loading="lazy" src="${{p.prelabel.path}}?v=${{p.prelabel.sha256.slice(0,12)}}" alt="模型预标注"><img loading="lazy" src="${{p.alignment.path}}?v=${{p.alignment.sha256.slice(0,12)}}" alt="对齐叠加"></div></details><fieldset><legend>scope（必填）</legend>${{choices('scope',scopeOptions,s.scope)}}</fieldset>${{x.machine.reference_flags.length?`<fieldset><legend>参考标注候选裁决（必填）</legend><p class="flags">机器提示：${{flagText(x.machine.reference_flags)}}</p>${{choices('reference_verdict',verdictOptions,s.reference_verdict)}}</fieldset>`:''}}${{x.machine.prelabel_flags.length?`<fieldset><legend>模型预标注裁决（必填）</legend><p class="flags">机器提示：${{flagText(x.machine.prelabel_flags)}}</p>${{choices('prelabel_verdict',verdictOptions,s.prelabel_verdict)}}</fieldset>`:''}}<label>备注（可选）<textarea data-name="notes">${{s.notes||''}}</textarea></label>`;for(const el of card.querySelectorAll('[data-name]')){{el.addEventListener(el.tagName==='TEXTAREA'?'input':'change',()=>{{saved[x.review_id]=saved[x.review_id]||{{}};saved[x.review_id][el.dataset.name]=el.value;localStorage.setItem(key,JSON.stringify(saved));progress()}})}}root.appendChild(card)}}progress()}}
function progress(){{document.getElementById('progress').textContent=`已填 scope ${{items.filter(x=>saved[x.review_id]?.scope).length}} / ${{items.length}}`}}
document.getElementById('export').addEventListener('click',()=>{{const validationWarnings=items.filter(x=>x.required_fields.some(name=>!saved[x.review_id]?.[name])).map(x=>x.review_id);const result={{schema_version:'annotation_uncertainty_prescreen_human_review_v1',exported_at:new Date().toISOString(),validation_warnings:validationWarnings,items:items.map(x=>({{review_id:x.review_id,image_id:x.image_id,required_fields:x.required_fields,review:saved[x.review_id]||{{}}}}))}};const blob=new Blob([JSON.stringify(result,null,2)],{{type:'application/json'}});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='annotation_uncertainty_prescreen_human_review_v1.json';a.click();URL.revokeObjectURL(a.href)}});render();
</script></body></html>"""
    (output_dir / "review.html").write_text(page, encoding="utf-8")


def _run_info(root: Path) -> dict[str, Any]:
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=True).stdout)
    except (OSError, subprocess.CalledProcessError):
        head, dirty = "unavailable", None
    script_path = Path(__file__).resolve()
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "git_head": head,
        "git_worktree_dirty": dirty,
        "generator": {"path": _relative(root, script_path), "sha256": _sha256(script_path)},
    }


def build_review_package(rows: list[dict[str, Any]], summary: dict[str, Any], output_dir: Path, visual_review: Path) -> None:
    apply_visual_review(rows, visual_review)
    selected, selection = select_human_batch(rows)
    _render_previews(selected, output_dir / "previews")
    selected_ids = {row["image_id"] for row in selected}
    for row in rows:
        row["selected_for_human_review"] = row["image_id"] in selected_ids
        if not row["selected_for_human_review"]:
            row.pop("review_id", None)
    public_rows = [_public_row(row) for row in rows]
    manifest = {
        "schema_version": "annotation_uncertainty_prescreen_machine_manifest_v1",
        "status": "preliminary_advisory_not_frozen_not_worker_facing",
        "scope_definition": "single_dominant_indoor_space_interpretable_boundary_approximately_manhattan",
        "machine_language_guard": "hints_only_never_asserts_reference_correct_or_prelabel_wrong",
        "visual_review_source": {"path": _relative(ROOT, visual_review), "sha256": _sha256(visual_review)},
        "run_info": _run_info(ROOT),
        "summary": {
            **{key: value for key, value in summary.items() if key != "source_artifacts"},
            "machine_scope_counts": dict(Counter(row["machine"]["scope_hint"] for row in rows)),
            "selected_for_human_review": len(selected),
        },
        "source_artifacts": summary["source_artifacts"],
        "selection": selection,
        "items": public_rows,
    }
    (output_dir / "machine_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "human_batch_manifest.json").write_text(json.dumps({
        "schema_version": "annotation_uncertainty_prescreen_human_batch_v1",
        "status": "researcher_prescreen_candidate_not_frozen_not_worker_facing",
        "selection": selection,
        "items": [_public_row(row) for row in selected],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    write_review_html(selected, output_dir)
    (output_dir / "README.md").write_text(
        "# 导师定稿前 30 张图片准备包\n\n"
        "打开 `review.html`。每张只需填写 scope 与可选备注；机器对参考标注候选或模型预标注给出提示时，页面才增加对应裁决。\n\n"
        "本目录是可撤回的研究者初筛材料：未冻结正式样本、未导入 Label Studio、未修改论文协议或统计计划。"
        "`machine_manifest.json` 覆盖 314 张，`human_batch_manifest.json` 只含来自 166 张无现有 annotation 记录池的 30 张。\n\n"
        "“无现有 annotation 记录”只描述当前仓库记录，不声称图片绝对从未被查看；24+6 只是本轮筛图配比，不是正式实验分层。\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the non-normative 314-image machine prescreen and 30-image human review package.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "build"):
        command = subparsers.add_parser(name)
        command.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
        if name == "build":
            command.add_argument("--visual-review", type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rows, summary = build_inventory(ROOT)
    if args.command == "prepare":
        prepare_visual_review(rows, summary, output_dir)
        print(f"prepared {len(rows)} images in {output_dir}")
        return
    visual_review = (args.visual_review or output_dir / "machine_visual_review.json").resolve()
    build_review_package(rows, summary, output_dir, visual_review)
    print(f"built 314-image manifest and 30-image review package in {output_dir}")


if __name__ == "__main__":
    main()
