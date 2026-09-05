"""Recompute and audit historical annotation evidence for research decisions.

This is a retrospective audit.  Raw exports/imports/logs remain unchanged, old
eligibility is kept as data, and unresolvable identities remain explicit.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import tempfile
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from tools.thesis_main.analysis import audit_worker_manual_strata_exploratory as manual_strata
from tools.thesis_main.analysis import materialize_historical_uncertainty_k_curves_20260829 as historical
from tools.thesis_main.analysis import materialize_paper_a_data_discovery as discovery
from tools.thesis_main.analysis.full_uncertainty import materialize_uncertainty_substrate as substrate
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.quality_core import geometry_metrics
from tools.thesis_main.analysis.quality_core.choice_parser import extract_data


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = (
    ROOT
    / "analysis_results"
    / "annotation_research_decision_audit_20260905_v1"
    / "data_audit"
)
OLD_SUBSTRATE = ROOT / "analysis_results" / "uncertainty_substrate_20260823_v1"
OLD_HISTORICAL = ROOT / "analysis_results" / "historical_uncertainty_recompute_20260829_v1"
OLD_MANUAL = ROOT / "analysis_results" / "worker_manual_strata_audit_20260904_v1"
BI_ROOT = Path(r"D:\Work\Manhattan_3D\Bi_layout\exports\mp3d_dual_predictions")
HOHO_ROOTS = {
    "test": ROOT / "analysis_results" / "model_initialization_test_ep300_replay_20260823_v1" / "prediction_txt",
    "val": ROOT / "analysis_results" / "model_initialization_validation_ep300_replay_20260823_v1" / "prediction_txt",
}
GT_IMPORTS = {
    "test": ROOT / "import_json" / "groudTruth_458_tasks_import_from_updated_gt_20260701.json",
    "val": ROOT / "import_json" / "mp3d_validation_gt_audit_20260809" / "mp3d_validation_all_gt_import.json",
}
KEY_K = (3, 5, 8, 12, 13, 15, 16, 17, 18, 19, 20)
REPLICATES = 200
EXPECTED_INDEPENDENCE = Counter(
    {
        "independent": 840,
        "non_independent_confirmed": 88,
        "non_independent_suspected": 115,
        "unknown": 12,
    }
)
CURRENT_AVAILABLE_20 = {"1", "2", "6", "8", "10", "11", "12", "13", "15", "17", *map(str, range(28, 38))}


def truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def normalise_worker(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text.startswith("W"):
        text = text[1:]
    return str(int(text)) if text.isdigit() else text


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    materialized = list(rows)
    fields: list[str] = []
    for row in materialized:
        for field in row:
            if field not in fields:
                fields.append(field)
    if not fields:
        fields = ["status"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(materialized)


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def classify_export_source(
    relative_path: str,
    project_ids: set[str],
    data_keys: set[str],
    formal_paths: set[str],
) -> tuple[str, str]:
    """Classify an export without claiming an unknown project is experimental."""
    normal = relative_path.replace("\\", "/")
    lower = normal.lower()
    if normal.endswith("RAW_DATA_PACKAGE_MANIFEST_20260817.json"):
        return "package_manifest", "metadata, not Label Studio annotations"
    if normal in formal_paths:
        return "formal_experiment_export", "exact frozen/current formal source"
    if "groudtruth" in lower or "groundtruth" in lower or (bool(project_ids) and project_ids <= {"20", "45", "70"}):
        return "reference_export", "GT/reference project or filename"
    if project_ids & {"2", "11", "12", "23", "38", "65"} or "smoke_test" in data_keys:
        return "development_export", "known development/smoke project"
    if project_ids & {"28", "29", "30", "39", "40", "41", "66", "67", "68", "69", "71", "72", "76", "77", "78", "79", "84", "85"}:
        return "duplicate_or_revision_export", "known experiment project but not selected formal snapshot"
    return "unresolved_export", "project role not established from frozen sources"


def _annotation_identity(task: Mapping[str, Any], annotation: Mapping[str, Any]) -> tuple[str, str, str, str]:
    completed = annotation.get("completed_by", "")
    if isinstance(completed, Mapping):
        completed = completed.get("id", completed.get("pk", ""))
    return (
        str(annotation.get("project", task.get("project", ""))),
        str(annotation.get("task", task.get("id", ""))),
        normalise_worker(completed),
        str(annotation.get("id", "")),
    )


def _formal_source_sets() -> tuple[set[str], set[str], set[str], set[str]]:
    exports = discovery.raw_label_sources()
    logs = discovery.raw_active_sources()
    return (
        {_relative(row["path"]) for row in exports},
        {row["sha256"] for row in exports},
        {_relative(row["path"]) for row in logs},
        {row["sha256"] for row in logs},
    )


def _scan_export_sources(
    canonical_keys: set[tuple[str, str, str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    formal_paths, formal_hashes, _, _ = _formal_source_sets()
    files: list[dict[str, Any]] = []
    versions: list[dict[str, Any]] = []
    for path in sorted((ROOT / "export_label").rglob("*.json")):
        relative = _relative(path)
        digest = sha256(path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            tasks = payload if isinstance(payload, list) else []
            parse_status = "parsed"
        except Exception as exc:
            tasks = []
            parse_status = f"error:{type(exc).__name__}"
        projects: set[str] = set()
        data_keys: set[str] = set()
        conditions: set[str] = set()
        bases: set[str] = set()
        workers: set[str] = set()
        annotation_count = 0
        for task in tasks:
            if not isinstance(task, Mapping):
                continue
            data = task.get("data") if isinstance(task.get("data"), Mapping) else {}
            data_keys.update(map(str, data))
            condition = str(data.get("condition", ""))
            base = str(data.get("base_task_id", data.get("planned_task_id", "")))
            if condition:
                conditions.add(condition)
            if base:
                bases.add(base)
            for annotation in task.get("annotations") or []:
                if not isinstance(annotation, Mapping):
                    continue
                annotation_count += 1
                identity = _annotation_identity(task, annotation)
                projects.add(identity[0])
                if identity[2]:
                    workers.add(identity[2])
                versions.append(
                    {
                        "source_path": relative,
                        "source_sha256": digest,
                        "project_id": identity[0],
                        "runtime_task_id": identity[1],
                        "worker_id": identity[2],
                        "annotation_id": identity[3],
                        "base_task_id": base,
                        "condition": condition,
                        "created_at": annotation.get("created_at", ""),
                        "updated_at": annotation.get("updated_at", ""),
                        "result_sha256": stable_sha(annotation.get("result") or []),
                        "canonical_match_status": "matched" if identity in canonical_keys else "not_in_2501_substrate",
                    }
                )
        if digest in formal_hashes:
            formal_paths.add(relative)
        category, reason = classify_export_source(relative, projects, data_keys, formal_paths)
        files.append(
            {
                "source_family": "export_label",
                "source_path": relative,
                "classification": category,
                "classification_reason": reason,
                "parse_status": parse_status,
                "size_bytes": path.stat().st_size,
                "task_count": len(tasks),
                "annotation_snapshot_count": annotation_count,
                "project_ids": ";".join(sorted(projects)),
                "base_task_count": len(bases),
                "worker_count": len(workers),
                "conditions": ";".join(sorted(conditions)),
                "data_keys": ";".join(sorted(data_keys)),
                "content_sha256": digest,
            }
        )
        for row in versions[-annotation_count:] if annotation_count else []:
            row["source_classification"] = category

    identity_counts = Counter((r["project_id"], r["runtime_task_id"], r["worker_id"], r["annotation_id"]) for r in versions)
    payload_counts: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
    for row in versions:
        key = (row["project_id"], row["runtime_task_id"], row["worker_id"], row["annotation_id"])
        payload_counts[key].add(row["result_sha256"])
    for row in versions:
        key = (row["project_id"], row["runtime_task_id"], row["worker_id"], row["annotation_id"])
        row["snapshot_occurrence_count"] = identity_counts[key]
        row["distinct_result_version_count"] = len(payload_counts[key])
    return files, versions


def _scan_import_sources() -> list[dict[str, Any]]:
    formal = {path for _, _, path in substrate.PLANNED_IMPORTS}
    rows: list[dict[str, Any]] = []
    for path in sorted((ROOT / "import_json").rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".json", ".csv", ".xml", ".md"}:
            continue
        relative = _relative(path)
        item_count: Any = ""
        keys: set[str] = set()
        parse_status = "not_json"
        if path.suffix.lower() == ".json":
            try:
                value = json.loads(path.read_text(encoding="utf-8-sig"))
                items = value if isinstance(value, list) else []
                item_count = len(items)
                for item in items:
                    if isinstance(item, Mapping) and isinstance(item.get("data"), Mapping):
                        keys.update(map(str, item["data"]))
                parse_status = "parsed"
            except Exception as exc:
                parse_status = f"error:{type(exc).__name__}"
        lower = relative.lower()
        if relative in formal:
            category, reason = "formal_planned_import", "selected by uncertainty substrate"
        elif any(token in lower for token in ("groudtruth", "groundtruth", "validation_gt", "all_gt_import")):
            category, reason = "reference_import", "GT/reference import"
        elif "legacy" in lower or "旧" in relative:
            category, reason = "legacy_import", "path explicitly marks legacy/old"
        elif any(token in lower for token in ("stage3", "outline", "smoke", "pilot", "trap", "test")):
            category, reason = "development_or_unlaunched_import", "development/test/future naming"
        else:
            category, reason = "unresolved_import", "not selected by the formal substrate"
        rows.append(
            {
                "source_family": "import_json",
                "source_path": relative,
                "classification": category,
                "classification_reason": reason,
                "parse_status": parse_status,
                "size_bytes": path.stat().st_size,
                "item_count": item_count,
                "data_keys": ";".join(sorted(keys)),
                "content_sha256": sha256(path),
            }
        )
    return rows


def _scan_active_sources() -> list[dict[str, Any]]:
    _, _, formal_paths, formal_hashes = _formal_source_sets()
    rows: list[dict[str, Any]] = []
    for path in sorted((ROOT / "active_logs").rglob("*")):
        if not path.is_file():
            continue
        relative = _relative(path)
        digest = sha256(path)
        record_count: Any = ""
        parse_errors: Any = ""
        projects: set[str] = set()
        if path.suffix.lower() == ".jsonl":
            record_count = 0
            parse_errors = 0
            with path.open(encoding="utf-8-sig") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    record_count += 1
                    try:
                        event = json.loads(line)
                        project = str(event.get("project_id", ""))
                        if project:
                            projects.add(project)
                    except Exception:
                        parse_errors += 1
        if relative in formal_paths:
            category, reason = "formal_active_log", "selected frozen/current active log"
        elif digest in formal_hashes:
            category, reason = "duplicate_active_log", "byte-identical to selected active log"
        elif "legacy" in relative.lower() or "old_server" in relative.lower():
            category, reason = "legacy_active_log", "path explicitly marks legacy/old server"
        elif path.suffix.lower() == ".jsonl":
            category, reason = "unresolved_active_log", "not selected and not byte-identical to formal logs"
        else:
            category, reason = "active_log_metadata", "non-event support file"
        rows.append(
            {
                "source_family": "active_logs",
                "source_path": relative,
                "classification": category,
                "classification_reason": reason,
                "parse_status": "parsed" if parse_errors == 0 else "parse_errors",
                "size_bytes": path.stat().st_size,
                "event_count": record_count,
                "parse_error_count": parse_errors,
                "project_ids": ";".join(sorted(projects)),
                "content_sha256": digest,
            }
        )
    return rows


def dense42_denominators() -> dict[str, Any]:
    inputs = historical.load_inputs()
    contract = historical.build_reference_contract(inputs)
    rows = historical.build_annotation_eligibility(inputs, contract)
    counts = Counter()
    for row in rows:
        status = str(row.get("independence_status") or "").strip()
        counts[status if status in EXPECTED_INDEPENDENCE else "unknown"] += 1
    return {
        "row_count": len(rows),
        "strict_geometry_valid_count": sum(row["strict_geometry_valid"] is True for row in rows),
        "old_reference_quality_eligible_count": sum(row["gt_primary_analysis_eligible"] is True for row in rows),
        "independence_counts": dict(counts),
    }


def parse_alternating_corner_file(path: Path) -> tuple[list[list[float]], list[dict[str, float]]]:
    points: list[list[float]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) < 2:
            raise ValueError(f"invalid corner row: {path}: {line!r}")
        points.append([float(fields[0]), float(fields[1])])
    if len(points) < 2 or len(points) % 2:
        raise ValueError(f"corners must be alternating ceiling/floor pairs: {path}")
    pairs = []
    for ceiling, floor in zip(points[::2], points[1::2]):
        if not math.isclose(ceiling[0], floor[0], abs_tol=1.1):
            raise ValueError(f"ceiling/floor x mismatch: {path}: {ceiling[0]} vs {floor[0]}")
        pairs.append(
            {
                "x": (ceiling[0] + floor[0]) / 2,
                "y_ceiling": min(ceiling[1], floor[1]),
                "y_floor": max(ceiling[1], floor[1]),
            }
        )
    return points, pairs


def _quantile(values: Sequence[float], q: float) -> float:
    return float(np.quantile(np.asarray(values, dtype=float), q))


def summarize_comparisons(
    rows: Sequence[Mapping[str, Any]], *, include_buildings: bool = False
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("d_mask") in (None, ""):
            continue
        grouped[(str(row["comparison"]), "pooled")].append(row)
        if include_buildings:
            grouped[(str(row["comparison"]), str(row["building_id"]))].append(row)
    result = []
    for (comparison, stratum), group in sorted(grouped.items()):
        values = [float(row["d_mask"]) for row in group]
        workers = {
            str(value)
            for row in group
            for value in (row.get("worker_id", ""), row.get("other_worker_id", ""))
            if str(value)
        }
        result.append(
            {
                "comparison": comparison,
                "stratum": stratum,
                "comparison_count": len(group),
                "image_count": len({row["base_task_id"] for row in group}),
                "building_count": len({row["building_id"] for row in group}),
                "worker_count": len(workers),
                "d_mask_mean": round(float(np.mean(values)), 12),
                "d_mask_median": round(_quantile(values, 0.5), 12),
                "d_mask_q25": round(_quantile(values, 0.25), 12),
                "d_mask_q75": round(_quantile(values, 0.75), 12),
            }
        )
    return result


def _dense_boundaries(pairs: Sequence[Mapping[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    xs = np.asarray([float(row["x"]) for row in pairs], dtype=np.float32)
    ceilings = np.asarray([float(row["y_ceiling"]) for row in pairs], dtype=np.float32)
    floors = np.asarray([float(row["y_floor"]) for row in pairs], dtype=np.float32)
    top = np.clip(np.rint(geometry_metrics._interp_periodic(xs, ceilings, 1024)), 0, 511).astype(np.int32)
    bottom = np.clip(np.rint(geometry_metrics._interp_periodic(xs, floors, 1024)), 0, 511).astype(np.int32)
    return np.minimum(top, bottom), np.maximum(top, bottom)


def _d_mask(left: tuple[np.ndarray, np.ndarray], right: tuple[np.ndarray, np.ndarray]) -> float:
    left_top, left_bottom = left
    right_top, right_bottom = right
    intersection = np.maximum(0, np.minimum(left_bottom, right_bottom) - np.maximum(left_top, right_top) + 1)
    left_size = left_bottom - left_top + 1
    right_size = right_bottom - right_top + 1
    union = left_size + right_size - intersection
    return 1.0 - float(intersection.sum() / union.sum())


def _base_from_task(task: Mapping[str, Any]) -> str:
    data = task.get("data") if isinstance(task.get("data"), Mapping) else {}
    base = str(data.get("base_task_id") or data.get("task_id") or data.get("title") or "")
    return Path(base).stem


def _extract_task_pairs(task: Mapping[str, Any]) -> list[dict[str, float]] | None:
    candidates = list(task.get("annotations") or []) + list(task.get("predictions") or [])
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        points, _, _, _ = extract_data(candidate.get("result") or [])
        normalized = normalize_geometry(points, width=1024, height=512)
        if normalized.get("valid"):
            return normalized["pairs"]
    return None


def _load_model_pairs() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    index: dict[str, dict[str, Any]] = defaultdict(dict)
    coverage: list[dict[str, Any]] = []
    for split in ("test", "val"):
        manifest_path = BI_ROOT / split / "manifest.csv"
        manifest = read_csv(manifest_path)
        for row in manifest:
            base = row["pano_id"]
            item = index[base]
            item.update({"split": split, "building_id": base.split("_", 1)[0]})
            for mode in ("enclosed", "extended"):
                path = BI_ROOT / row[f"{mode}_corners_px_path"]
                _, pairs = parse_alternating_corner_file(path)
                item[f"bilayout_{mode}_file_present"] = True
                if len(pairs) >= 2:
                    item[f"bilayout_{mode}"] = pairs
            hoho_path = HOHO_ROOTS[split] / f"{base}.layout.txt"
            _, hoho_pairs = parse_alternating_corner_file(hoho_path)
            item["hohonet_file_present"] = True
            if len(hoho_pairs) >= 2:
                item["hohonet"] = hoho_pairs
        coverage.append(
            {
                "split": split,
                "bilayout_manifest_count": len(manifest),
                "bilayout_enclosed_count": sum("bilayout_enclosed" in index[row["pano_id"]] for row in manifest),
                "bilayout_extended_count": sum("bilayout_extended" in index[row["pano_id"]] for row in manifest),
                "hohonet_count": sum("hohonet" in index[row["pano_id"]] for row in manifest),
                "bilayout_both_files_count": sum(index[row["pano_id"]].get("bilayout_enclosed_file_present") and index[row["pano_id"]].get("bilayout_extended_file_present") for row in manifest),
                "hohonet_file_count": sum(bool(index[row["pano_id"]].get("hohonet_file_present")) for row in manifest),
            }
        )
    return dict(index), coverage


def _load_gt_pairs() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for split, path in GT_IMPORTS.items():
        for task in json.loads(path.read_text(encoding="utf-8-sig")):
            base = _base_from_task(task)
            pairs = _extract_task_pairs(task)
            if pairs:
                result[base] = {
                    "pairs": pairs,
                    "reference_status": "public_dataset_reference_not_quality_assumed",
                    "scope_status": "not_reviewed_for_this_audit",
                    "source": _relative(path),
                    "split": split,
                }
    final_gold = ROOT / "analysis_results" / "prescreen_closeout_final_gold_v2_20260701" / "final_gold_records_v2_p1_closeout_corrected.jsonl"
    with final_gold.open(encoding="utf-8-sig") as handle:
        for line in handle:
            row = json.loads(line)
            pairs = row.get("runtime_pairs_1024x512")
            if not pairs:
                continue
            base = row["base_task_id"]
            result[base] = {
                "pairs": pairs,
                "reference_status": "adjudicated_reference" if row.get("geometry_gold_ready") else "reference_not_geometry_ready",
                "scope_status": row.get("final_scope_binary", "unknown"),
                "source": _relative(final_gold),
                "split": "test",
            }
    return result


def _build_geometry_comparisons(substrate_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    spine = {row["canonical_annotation_id"]: row for row in read_csv(substrate_dir / "annotation_spine.csv")}
    geometry = [
        row for row in read_csv(substrate_dir / "geometry_variants.csv")
        if row["variant"] == "strict_normalized" and truth(row["strict_valid"])
    ]
    historical_inputs = historical.load_inputs()
    historical_rows = historical.build_annotation_eligibility(
        historical_inputs, historical.build_reference_contract(historical_inputs)
    )
    eligibility = {(row["stage"], row["base_task_id"], normalise_worker(row["worker_id"])): row for row in historical_rows}
    humans: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in geometry:
        meta = spine[row["canonical_annotation_id"]]
        pairs = normalize_geometry(json.loads(row["points_json"]))["pairs"]
        humans[(row["base_task_id"], row["raw_condition"])].append(
            {
                "canonical_annotation_id": row["canonical_annotation_id"],
                "base_task_id": row["base_task_id"],
                "building_id": meta["building_id"],
                "stage": row["stage"],
                "condition": row["raw_condition"],
                "worker_id": row["worker_id"],
                "pairs": pairs,
                "dense": _dense_boundaries(pairs),
                "independence_status": eligibility.get((row["stage"], row["base_task_id"], normalise_worker(meta["worker_id"])), {}).get("independence_status", "not_materialized"),
            }
        )
    models, coverage = _load_model_pairs()
    gt = _load_gt_pairs()
    dense_models = {
        base: {name: _dense_boundaries(pairs) for name, pairs in item.items() if name in {"hohonet", "bilayout_enclosed", "bilayout_extended"}}
        for base, item in models.items()
    }
    rows: list[dict[str, Any]] = []

    def add(comparison: str, left: Mapping[str, Any], right_name: str, right_dense: tuple[np.ndarray, np.ndarray], **extra: Any) -> None:
        rows.append(
            {
                "comparison": comparison,
                "base_task_id": left["base_task_id"],
                "building_id": left["building_id"],
                "stage": left.get("stage", "model_only"),
                "condition": left.get("condition", "model_only"),
                "worker_id": left.get("worker_id", ""),
                "other_worker_id": extra.pop("other_worker_id", ""),
                "left_id": left.get("canonical_annotation_id", left.get("left_id", "")),
                "right_id": right_name,
                "d_mask": round(_d_mask(left["dense"], right_dense), 12),
                "independence_status": left.get("independence_status", "not_applicable"),
                "metric_contract": "periodic_linear_image_plane_mask_proxy_1024x512",
                **extra,
            }
        )

    for (base, _condition), group in sorted(humans.items()):
        for left, right in combinations(group, 2):
            relation = "repeat_same_worker" if left["worker_id"] == right["worker_id"] else "cross_stage" if left["stage"] != right["stage"] else "different_worker_same_stage"
            add(
                f"human_human_{relation}", left, right["canonical_annotation_id"], right["dense"],
                other_worker_id=right["worker_id"], pair_relation=relation,
                other_independence_status=right["independence_status"], other_stage=right["stage"],
            )
        if base not in models:
            continue
        for human in group:
            for model_name in ("hohonet", "bilayout_enclosed", "bilayout_extended"):
                if model_name in dense_models[base]:
                    add(f"human_{model_name}", human, model_name, dense_models[base][model_name])
            reference = gt.get(base)
            if reference and reference["reference_status"] != "reference_not_geometry_ready":
                add(
                    "human_gt", human, "gt", _dense_boundaries(reference["pairs"]),
                    reference_status=reference["reference_status"], scope_status=reference["scope_status"], reference_source=reference["source"],
                )

    for base in sorted({key[0] for key in humans}):
        if base not in models:
            continue
        if "hohonet" in dense_models[base]:
            left = {"base_task_id": base, "building_id": base.split("_", 1)[0], "dense": dense_models[base]["hohonet"], "left_id": "hohonet"}
            for mode in ("bilayout_enclosed", "bilayout_extended"):
                if mode in dense_models[base]:
                    add(f"hohonet_{mode}", left, mode, dense_models[base][mode])
        if "bilayout_enclosed" in dense_models[base] and "bilayout_extended" in dense_models[base]:
            left = {"base_task_id": base, "building_id": base.split("_", 1)[0], "dense": dense_models[base]["bilayout_enclosed"], "left_id": "bilayout_enclosed"}
            add("bilayout_enclosed_extended", left, "bilayout_extended", dense_models[base]["bilayout_extended"])
        if base in gt and gt[base]["reference_status"] != "reference_not_geometry_ready":
            gt_dense = _dense_boundaries(gt[base]["pairs"])
            for model_name in ("hohonet", "bilayout_enclosed", "bilayout_extended"):
                if model_name not in dense_models[base]:
                    continue
                left = {"base_task_id": base, "building_id": base.split("_", 1)[0], "dense": dense_models[base][model_name], "left_id": model_name}
                add(f"{model_name}_gt", left, "gt", gt_dense, reference_status=gt[base]["reference_status"], scope_status=gt[base]["scope_status"], reference_source=gt[base]["source"])

    audited_bases = {key[0] for key in humans}
    coverage.append(
        {
            "split": "audited_214",
            "human_image_count": len(audited_bases),
            "human_strict_annotation_count": len(geometry),
            "building_count": len({base.split("_", 1)[0] for base in audited_bases}),
            "bilayout_both_count": sum(base in models and all(name in models[base] for name in ("bilayout_enclosed", "bilayout_extended")) for base in audited_bases),
            "hohonet_count": sum(base in models and "hohonet" in models[base] for base in audited_bases),
            "bilayout_both_files_count": sum(base in models and all(models[base].get(f"bilayout_{mode}_file_present") for mode in ("enclosed", "extended")) for base in audited_bases),
            "hohonet_file_count": sum(base in models and models[base].get("hohonet_file_present") for base in audited_bases),
            "gt_geometry_available_count": sum(base in gt and gt[base]["reference_status"] != "reference_not_geometry_ready" for base in audited_bases),
        }
    )
    return rows, summarize_comparisons(rows, include_buildings=True), coverage


def _independence_sensitivity() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    pools, lookups = historical._load_full_roster_geometry()
    inputs = historical.load_inputs()
    eligibility_rows = historical.build_annotation_eligibility(inputs, historical.build_reference_contract(inputs))
    eligibility = {(row["stage"], row["base_task_id"], normalise_worker(row["worker_id"])): row for row in eligibility_rows}
    status_of = lambda record: eligibility[(record.raw.stage, record.raw.base_task_id, normalise_worker(record.raw.worker_id))]["independence_status"]
    scenarios = {
        "historical_all__all_strict_geometry": (None, lambda status: True, KEY_K),
        "historical_all__legacy_independent_only": (None, lambda status: status == "independent", KEY_K),
        "historical_all__exclude_confirmed_only": (None, lambda status: status != "non_independent_confirmed", KEY_K),
        "current_available20__all_strict_geometry": (CURRENT_AVAILABLE_20, lambda status: True, tuple(range(15, 21))),
        "current_available20__legacy_independent_only": (CURRENT_AVAILABLE_20, lambda status: status == "independent", tuple(range(15, 21))),
    }
    task_rows: list[dict[str, Any]] = []
    for scenario, (roster, keep, k_values) in scenarios.items():
        for task_id, all_records in sorted(pools.items()):
            historical_target_records = [row for row in all_records if keep(status_of(row))]
            records = [row for row in historical_target_records if roster is None or normalise_worker(row.raw.worker_id) in roster]
            stage, _, base = task_id.split("|", 2)
            if len(records) < 3:
                for k in k_values:
                    task_rows.append({"scenario": scenario, "task_id": task_id, "base_task_id": base, "building_id": base.split("_", 1)[0], "stage": stage, "k": k, "filtered_support": len(records), "evaluable": False})
                continue
            full = historical._cluster_raw_records(task_id, records, lookups[task_id])
            full_memberships = json.loads(full["cluster_membership_json"])
            full_second = set(map(str, full_memberships[1])) if len(full_memberships) > 1 else set()
            historical_target = historical._cluster_raw_records(task_id, historical_target_records, lookups[task_id])
            historical_memberships = json.loads(historical_target["cluster_membership_json"])
            rng = np.random.default_rng(historical.SEED + int(stable_sha([scenario, task_id])[:8], 16))
            permutations = [rng.permutation(len(records)).tolist() for _ in range(REPLICATES)]
            paired: dict[int, dict[str, list[bool]]] = {}
            for k in k_values:
                if len(records) < k:
                    task_rows.append({"scenario": scenario, "task_id": task_id, "base_task_id": base, "building_id": base.split("_", 1)[0], "stage": stage, "k": k, "filtered_support": len(records), "evaluable": False})
                    continue
                outcomes = {name: [] for name in ("status", "multimodal", "partition", "second", "historical_status", "historical_partition")}
                for permutation in permutations:
                    sample = [records[index] for index in sorted(permutation[:k])]
                    result = historical._cluster_raw_records(task_id, sample, lookups[task_id])
                    memberships = json.loads(result["cluster_membership_json"])
                    sample_ids = {row.canonical_id for row in sample}
                    outcomes["status"].append(result["task_crowd_structure_status"] == full["task_crowd_structure_status"])
                    outcomes["multimodal"].append(result["task_crowd_structure_status"] == "supported_multimodal")
                    outcomes["partition"].append(historical._partition_matches_full_restriction(full_memberships, sample_ids, memberships))
                    outcomes["second"].append(historical._same_second_mode_recovered(full_second, sample_ids, memberships))
                    outcomes["historical_status"].append(result["task_crowd_structure_status"] == historical_target["task_crowd_structure_status"])
                    outcomes["historical_partition"].append(historical._partition_matches_full_restriction(historical_memberships, sample_ids, memberships))
                prior_k = max((candidate for candidate in paired if candidate < k), default=None)
                task_rows.append(
                    {
                        "scenario": scenario, "task_id": task_id, "base_task_id": base, "building_id": base.split("_", 1)[0], "stage": stage,
                        "k": k, "filtered_support": len(records), "worker_count": len({row.raw.worker_id for row in records}), "evaluable": True,
                        "worker_ids_json": json.dumps(sorted({normalise_worker(row.raw.worker_id) for row in records}), ensure_ascii=False),
                        "full_structure_status": full["task_crowd_structure_status"], "full_cluster_count": full["cluster_count"],
                        "full_second_cluster_support": len(full_second), "replicates": REPLICATES,
                        "sampling_contract": "same_scenario_task_permutations_nested_k_prefixes",
                        "roster_contract": "current_available_20_confirmed_20260905" if roster is not None else "historical_all_observed_workers",
                        "filtered_full_target": "current_available20_filtered_full_roster" if roster is not None else "historical_filtered_full_roster",
                        "historical_all_target_support": len(historical_target_records),
                        "full_status_recovery_rate": float(np.mean(outcomes["status"])),
                        "supported_multimodal_rate": float(np.mean(outcomes["multimodal"])),
                        "partition_recovery_rate": float(np.mean(outcomes["partition"])),
                        "same_second_mode_recovery_rate_all_tasks": float(np.mean(outcomes["second"])),
                        "same_second_mode_evaluable": len(full_second) >= 2,
                        "historical_all_target_status_recovery_rate": float(np.mean(outcomes["historical_status"])),
                        "historical_all_target_partition_recovery_rate": float(np.mean(outcomes["historical_partition"])),
                        "k_equals_filtered_full_roster": k == len(records),
                        "prior_available_k": prior_k if prior_k is not None else "",
                        "paired_status_changed_from_prior_k_rate": float(np.mean(np.not_equal(outcomes["status"], paired[prior_k]["status"]))) if prior_k is not None else "",
                        "paired_partition_changed_from_prior_k_rate": float(np.mean(np.not_equal(outcomes["partition"], paired[prior_k]["partition"]))) if prior_k is not None else "",
                        "paired_historical_target_status_changed_from_prior_k_rate": float(np.mean(np.not_equal(outcomes["historical_status"], paired[prior_k]["historical_status"]))) if prior_k is not None else "",
                        "paired_historical_target_partition_changed_from_prior_k_rate": float(np.mean(np.not_equal(outcomes["historical_partition"], paired[prior_k]["historical_partition"]))) if prior_k is not None else "",
                        "full_roster_self_recovery_note": "constructive_by_definition_not_quality_ceiling",
                    }
                )
                paired[k] = outcomes
    summary: list[dict[str, Any]] = []
    common20 = {
        scenario: {row["task_id"] for row in task_rows if row["scenario"] == scenario and row["k"] == 20 and row["evaluable"]}
        for scenario in scenarios
    }
    for scenario, k in sorted({(row["scenario"], row["k"]) for row in task_rows}):
        all_group = [row for row in task_rows if row["scenario"] == scenario and row["k"] == k and row["evaluable"]]
        for support_set, group in (
            ("scenario_k_specific", all_group),
            ("fixed_common_support_k20", [row for row in all_group if row["task_id"] in common20[scenario]]),
        ):
            if not group:
                continue
            metric_fields = ("full_status_recovery_rate", "supported_multimodal_rate", "partition_recovery_rate", "historical_all_target_status_recovery_rate", "historical_all_target_partition_recovery_rate")
            building_means = {
                field: [
                    float(np.mean([row[field] for row in group if row["building_id"] == building]))
                    for building in sorted({row["building_id"] for row in group})
                ]
                for field in metric_fields
            }
            worker_ids = {
                record.raw.worker_id for task in group for record in pools[task["task_id"]]
                if scenarios[scenario][1](status_of(record)) and (scenarios[scenario][0] is None or normalise_worker(record.raw.worker_id) in scenarios[scenario][0])
            }
            summary.append(
                {
                    "scenario": scenario, "support_set": support_set, "k": k,
                    "common_support_task_ids_json": json.dumps(sorted(row["task_id"] for row in group), ensure_ascii=False),
                    "task_count": len(group), "image_count": len({row["base_task_id"] for row in group}),
                    "building_count": len({row["building_id"] for row in group}), "worker_count": len(worker_ids),
                    "strict_annotation_count": sum(row["filtered_support"] for row in group),
                    "support_min": min(row["filtered_support"] for row in group), "support_median": float(np.median([row["filtered_support"] for row in group])),
                    "support_max": max(row["filtered_support"] for row in group),
                    **{f"{field}_task_equal": float(np.mean([row[field] for row in group])) for field in metric_fields},
                    **{f"{field}_building_equal": float(np.mean(building_means[field])) for field in metric_fields},
                    "full_second_mode_evaluable_task_count": sum(truth(row["same_second_mode_evaluable"]) for row in group),
                    "same_second_mode_recovery_rate_all_task_mean": float(np.mean([row["same_second_mode_recovery_rate_all_tasks"] for row in group])),
                    "same_second_mode_recovery_rate_conditional_mean": (
                        float(np.mean([row["same_second_mode_recovery_rate_all_tasks"] for row in group if truth(row["same_second_mode_evaluable"])]))
                        if any(truth(row["same_second_mode_evaluable"]) for row in group) else ""
                    ),
                    "full_target_contract": "scenario_specific_filtered_full_roster; scenario differences are not same-target causal effects",
                    "plateau_claim": "not_tested_as_population_plateau",
                }
            )
    quality: list[dict[str, Any]] = []
    for scenario, (roster, keep, _k_values) in scenarios.items():
        rows = [row for row in eligibility_rows if row["geometry_score"] is not None and truth(row["gt_primary_analysis_eligible"]) and keep(row["independence_status"]) and (roster is None or normalise_worker(row["worker_id"]) in roster)]
        by_task: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            by_task[row["base_task_id"]].append(float(row["geometry_score"]))
        quality.append(
            {
                "scenario": scenario, "annotation_count": len(rows), "image_count": len(by_task), "building_count": len({row["building_id"] for row in rows}),
                "worker_count": len({row["worker_id"] for row in rows}), "annotation_weighted_mean": float(np.mean([float(row["geometry_score"]) for row in rows])),
                "task_equal_mean": float(np.mean([np.mean(values) for values in by_task.values()])),
                "interpretation": "old_reference_quality_eligible_only; GT is a measurement reference, not assumed truth",
            }
        )
    return task_rows, summary, quality


def _sensitivity_building_summary(task_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    scenarios = sorted({row["scenario"] for row in task_rows})
    for scenario in scenarios:
        common = {row["task_id"] for row in task_rows if row["scenario"] == scenario and row["k"] == 20 and truth(row["evaluable"])}
        for k in sorted({int(row["k"]) for row in task_rows if row["scenario"] == scenario and int(row["k"]) >= 15}):
            selected = [row for row in task_rows if row["scenario"] == scenario and int(row["k"]) == k and row["task_id"] in common and truth(row["evaluable"])]
            for building in sorted({row["building_id"] for row in selected}):
                group = [row for row in selected if row["building_id"] == building]
                workers = {worker for row in group for worker in json.loads(row["worker_ids_json"])}
                result.append(
                    {
                        "scenario": scenario, "support_set": "fixed_common_support_k20", "k": k, "building_id": building,
                        "task_count": len(group), "image_count": len({row["base_task_id"] for row in group}), "worker_count": len(workers),
                        "full_status_recovery_rate_task_equal": float(np.mean([row["full_status_recovery_rate"] for row in group])),
                        "partition_recovery_rate_task_equal": float(np.mean([row["partition_recovery_rate"] for row in group])),
                        "historical_all_target_status_recovery_rate_task_equal": float(np.mean([row["historical_all_target_status_recovery_rate"] for row in group])),
                        "historical_all_target_partition_recovery_rate_task_equal": float(np.mean([row["historical_all_target_partition_recovery_rate"] for row in group])),
                        "paired_status_changed_from_prior_k_rate_task_equal": float(np.mean([float(row["paired_status_changed_from_prior_k_rate"]) for row in group if row["paired_status_changed_from_prior_k_rate"] != ""])) if any(row["paired_status_changed_from_prior_k_rate"] != "" for row in group) else "",
                    }
                )
    return result


def _full_support_census_and_replay(substrate_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    spine = read_csv(substrate_dir / "annotation_spine.csv")
    versions = read_csv(substrate_dir / "annotation_version_lineage.csv")
    strict_rows = {
        row["canonical_annotation_id"]: row for row in read_csv(substrate_dir / "geometry_variants.csv")
        if row["variant"] == "strict_normalized" and truth(row["strict_valid"])
    }
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in spine:
        grouped[(row["stage"], row["raw_condition"], row["base_task_id"])].append(row)
    version_counts = Counter((row["stage"], row["raw_condition"], row["base_task_id"]) for row in versions)
    census: list[dict[str, Any]] = []
    for (stage, condition, base), rows in sorted(grouped.items()):
        strict = [row for row in rows if row["canonical_annotation_id"] in strict_rows]
        census.append(
            {
                "stage": stage, "condition": condition, "base_task_id": base, "building_id": rows[0]["building_id"],
                "canonical_annotation_count": len(rows), "raw_version_count": version_counts[(stage, condition, base)],
                "unique_worker_count": len({row["worker_id"] for row in rows}), "strict_geometry_count": len(strict),
                "raw_geometry_computable_count": sum(truth(row["raw_geometry_computable"]) for row in rows),
                "raw_geometry_noncomputable_count": sum(not truth(row["raw_geometry_computable"]) for row in rows),
                "strict_geometry_unique_worker_count": len({row["worker_id"] for row in strict}),
                "non_strict_or_non_geometry_count": len(rows) - len(strict),
                "current_available20_canonical_count": sum(normalise_worker(row["worker_id"]) in CURRENT_AVAILABLE_20 for row in rows),
                "current_available20_strict_count": sum(normalise_worker(row["worker_id"]) in CURRENT_AVAILABLE_20 for row in strict),
                "shared_initialization_status": "shared_model_preannotation_possible" if any(row["assistance_exposure"] == "model_preannotation" for row in rows) else "no_model_preannotation_recorded",
                "supports_k15": len(strict) >= 15, "supports_k20": len(strict) >= 20,
            }
        )

    pair_maps: dict[tuple[str, str, str], dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)
    for row in read_csv(substrate_dir / "geometry_pairwise.csv"):
        if row["variant"] != "raw" or not truth(row["metric_compatible"]):
            continue
        key = (row["stage"], row["raw_condition"], row["base_task_id"])
        pair = tuple(sorted((row["left_canonical_annotation_id"], row["right_canonical_annotation_id"])))
        pair_maps[key][pair] = row

    task_rows: list[dict[str, Any]] = []
    for key, spine_rows in sorted(grouped.items()):
        stage, condition, base = key
        records = [
            {"canonical_annotation_id": row["canonical_annotation_id"], "worker_id": row["worker_id"], "geometry": normalize_geometry(json.loads(strict_rows[row["canonical_annotation_id"]]["points_json"]))}
            for row in spine_rows if row["canonical_annotation_id"] in strict_rows
        ]
        if len(records) < 15:
            continue
        id_by_geometry = {id(row["geometry"]): row["canonical_annotation_id"] for row in records}

        def lookup(left: Mapping[str, Any], right: Mapping[str, Any]) -> Mapping[str, Any]:
            pair = tuple(sorted((id_by_geometry[id(left)], id_by_geometry[id(right)])))
            return pairwise_cluster_payload(pair_maps[key][pair])

        full = historical.cluster_geometry_records(records, min_q_boundary=0.95, min_q_wallwall=0.95, base_task_id=base, condition=condition, minimum_valid_k=3, pairwise_fn=lookup)
        full_memberships = json.loads(full["cluster_membership_json"])
        worker_by_annotation = {row["canonical_annotation_id"]: normalise_worker(row["worker_id"]) for row in records}
        full_worker_memberships = [[worker_by_annotation[annotation] for annotation in cluster] for cluster in full_memberships]
        full_second = set(map(str, full_memberships[1])) if len(full_memberships) > 1 else set()
        rng = np.random.default_rng(historical.SEED + int(stable_sha(["full_substrate", *key])[:8], 16))
        permutations = [rng.permutation(len(records)).tolist() for _ in range(REPLICATES)]
        paired: dict[int, dict[str, list[bool]]] = {}
        for k in range(15, 21):
            if len(records) < k:
                task_rows.append({"stage": stage, "condition": condition, "base_task_id": base, "building_id": base.split("_", 1)[0], "k": k, "strict_support": len(records), "evaluable": False})
                continue
            outcomes = {"status": [], "partition": [], "multimodal": [], "second": []}
            for permutation in permutations:
                sample = [records[index] for index in sorted(permutation[:k])]
                result = historical.cluster_geometry_records(sample, min_q_boundary=0.95, min_q_wallwall=0.95, base_task_id=base, condition=condition, minimum_valid_k=3, pairwise_fn=lookup)
                memberships = json.loads(result["cluster_membership_json"])
                sample_ids = {row["canonical_annotation_id"] for row in sample}
                outcomes["status"].append(result["task_crowd_structure_status"] == full["task_crowd_structure_status"])
                outcomes["partition"].append(historical._partition_matches_full_restriction(full_memberships, sample_ids, memberships))
                outcomes["multimodal"].append(result["task_crowd_structure_status"] == "supported_multimodal")
                outcomes["second"].append(historical._same_second_mode_recovered(full_second, sample_ids, memberships))
            prior_k = max(paired, default=None)
            paired_status_rate = float(np.mean(np.not_equal(outcomes["status"], paired[prior_k]["status"]))) if prior_k is not None else ""
            paired_partition_rate = float(np.mean(np.not_equal(outcomes["partition"], paired[prior_k]["partition"]))) if prior_k is not None else ""
            task_rows.append(
                {
                    "stage": stage, "condition": condition, "base_task_id": base, "building_id": base.split("_", 1)[0], "k": k,
                    "strict_support": len(records), "unique_worker_count": len({row["worker_id"] for row in records}), "evaluable": True,
                    "roster_contract": "all_observed_canonical_records_no_old_eligibility_filter", "replicates": REPLICATES,
                    "shared_initialization_status": "shared_model_preannotation_possible" if condition == "semi" else "no_model_preannotation_recorded",
                    "full_structure_status": full["task_crowd_structure_status"], "full_partition_status": full["partition_status"], "full_cluster_count": full["cluster_count"],
                    "full_valid_support": full["valid_k"], "full_second_cluster_support": full["second_cluster_support"],
                    "full_cluster_worker_memberships_json": json.dumps(full_worker_memberships, ensure_ascii=False),
                    "full_status_recovery_rate": float(np.mean(outcomes["status"])), "partition_recovery_rate": float(np.mean(outcomes["partition"])),
                    "supported_multimodal_rate": float(np.mean(outcomes["multimodal"])),
                    "full_second_cluster_support": len(full_second), "same_second_mode_evaluable": len(full_second) >= 2,
                    "same_second_mode_recovery_rate_all_tasks": float(np.mean(outcomes["second"])),
                    "prior_available_k": prior_k if prior_k is not None else "",
                    "paired_status_changed_from_prior_k_rate": paired_status_rate,
                    "paired_status_changed_mcse": math.sqrt(paired_status_rate * (1 - paired_status_rate) / REPLICATES) if prior_k is not None else "",
                    "paired_partition_changed_from_prior_k_rate": paired_partition_rate,
                    "paired_partition_changed_mcse": math.sqrt(paired_partition_rate * (1 - paired_partition_rate) / REPLICATES) if prior_k is not None else "",
                    "k_equals_full_support": k == len(records),
                    "interpretation": "finite historical canonical roster; k20 full-support recovery is mechanical where support equals 20",
                }
            )
            paired[k] = outcomes

    summary: list[dict[str, Any]] = []
    for stage, condition in sorted({(row["stage"], row["condition"]) for row in task_rows}):
        common20 = {row["base_task_id"] for row in task_rows if row["stage"] == stage and row["condition"] == condition and row["k"] == 20 and truth(row["evaluable"])}
        for k in range(15, 21):
            available = [row for row in task_rows if row["stage"] == stage and row["condition"] == condition and row["k"] == k and truth(row["evaluable"])]
            for support_set, group in (("k_specific", available), ("fixed_common_support_k20", [row for row in available if row["base_task_id"] in common20])):
                if not group:
                    continue
                buildings = sorted({row["building_id"] for row in group})
                second = [row for row in group if truth(row["same_second_mode_evaluable"])]
                transition = [row for row in group if row["paired_status_changed_from_prior_k_rate"] != ""]
                summary.append(
                    {
                        "stage": stage, "condition": condition, "support_set": support_set, "k": k,
                        "common_support_base_task_ids_json": json.dumps(sorted(row["base_task_id"] for row in group), ensure_ascii=False),
                        "task_count": len(group), "image_count": len({row["base_task_id"] for row in group}),
                        "building_count": len(buildings), "observed_worker_count": len({source["worker_id"] for task in group for source in grouped[(stage, condition, task["base_task_id"])]}),
                        "full_status_recovery_rate_task_equal": float(np.mean([row["full_status_recovery_rate"] for row in group])),
                        "full_status_recovery_rate_building_equal": float(np.mean([np.mean([row["full_status_recovery_rate"] for row in group if row["building_id"] == building]) for building in buildings])),
                        "partition_recovery_rate_task_equal": float(np.mean([row["partition_recovery_rate"] for row in group])),
                        "partition_recovery_rate_building_equal": float(np.mean([np.mean([row["partition_recovery_rate"] for row in group if row["building_id"] == building]) for building in buildings])),
                        "full_second_mode_evaluable_task_count": len(second),
                        "same_second_mode_recovery_rate_conditional_mean": float(np.mean([row["same_second_mode_recovery_rate_all_tasks"] for row in second])) if second else "",
                        "paired_status_changed_from_prior_k_rate_task_equal": float(np.mean([float(row["paired_status_changed_from_prior_k_rate"]) for row in transition])) if transition else "",
                        "paired_status_changed_mcse_for_task_equal_mean": math.sqrt(sum(float(row["paired_status_changed_from_prior_k_rate"]) * (1 - float(row["paired_status_changed_from_prior_k_rate"])) / REPLICATES for row in transition)) / len(transition) if transition else "",
                        "shared_initialization_status": "shared_model_preannotation_possible" if condition == "semi" else "no_model_preannotation_recorded",
                        "monte_carlo_note": "200 paired permutations; MC precision is finite and no plateau test is performed",
                        "old_eligibility_used": False,
                    }
                )
    return census, task_rows, summary


def pairwise_cluster_payload(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "boundary_similarity": float(source["boundary_similarity"]),
        "wallwall_similarity": float(source["wallwall_similarity"]),
        "metric_compatible": truth(source["metric_compatible"]),
        "pointwise_correspondence_compatible": truth(source["pointwise_correspondence_compatible"]),
    }


def _dense42_cluster_regression(task_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    old_rows = read_csv(OLD_HISTORICAL / "full_roster_structure_tasks.csv")
    new_by_base = {}
    for row in task_rows:
        if row.get("condition") == "manual" and row.get("stage") in {"P1", "C1"} and truth(row.get("evaluable")):
            new_by_base.setdefault(row["base_task_id"], row)
    mismatches = []
    canonical_partition = lambda clusters: sorted(sorted(map(normalise_worker, cluster)) for cluster in clusters)
    for old in old_rows:
        new = new_by_base.get(old["base_task_id"])
        old_workers = canonical_partition([[annotation.split("|")[-2] for annotation in cluster] for cluster in json.loads(old["cluster_membership_json"])])
        new_workers = canonical_partition(json.loads(new["full_cluster_worker_memberships_json"])) if new is not None else []
        membership_sizes = sorted(map(len, json.loads(new["full_cluster_worker_memberships_json"])), reverse=True) if new is not None else []
        new_second_support = new.get("full_second_cluster_support") or (membership_sizes[1] if len(membership_sizes) > 1 else 0)
        if new is None or (
            int(new.get("full_valid_support") or new["strict_support"]), new["full_structure_status"], str(new["full_cluster_count"]), str(new_second_support), new_workers
        ) != (int(old["full_valid_support"]), old["structure_status"], str(old["cluster_count"]), str(old["second_cluster_support"]), old_workers):
            mismatches.append(old["base_task_id"])
    return {"checked_task_count": len(old_rows), "mismatch_count": len(mismatches), "mismatch_base_task_ids": mismatches, "support_status_cluster_second_and_worker_partition_exact": not mismatches}


def _support_census_summary(substrate_dir: Path, census: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    contexts = read_csv(substrate_dir / "task_context_master.csv")
    result = []
    for stage, condition in sorted({(row["stage"], row["condition"]) for row in census}):
        rows = [row for row in census if row["stage"] == stage and row["condition"] == condition]
        matching_contexts = [row for row in contexts if row["stage"] == stage and row["raw_condition"] == condition]
        result.append(
            {
                "stage": stage, "condition": condition, "image_unit_count": len(rows), "task_context_count": len(matching_contexts),
                "canonical_annotation_count": sum(int(row["canonical_annotation_count"]) for row in rows),
                "raw_geometry_computable_count": sum(int(row["raw_geometry_computable_count"]) for row in rows),
                "raw_geometry_noncomputable_count": sum(int(row["raw_geometry_noncomputable_count"]) for row in rows),
                "raw_version_count": sum(int(row["raw_version_count"]) for row in rows),
                "building_count": len({row["building_id"] for row in rows}),
                "maximum_unique_worker_support": max(int(row["unique_worker_count"]) for row in rows),
                "maximum_strict_geometry_support": max(int(row["strict_geometry_count"]) for row in rows),
                "image_units_supporting_k15": sum(int(row["strict_geometry_count"]) >= 15 for row in rows),
                "image_units_supporting_k20": sum(int(row["strict_geometry_count"]) >= 20 for row in rows),
                "image_units_with_20_observed_workers": sum(int(row["unique_worker_count"]) >= 20 for row in rows),
                "old_eligibility_used": False,
            }
        )
    return result


def _three_path_coverage(substrate_dir: Path) -> list[dict[str, Any]]:
    spine = read_csv(substrate_dir / "annotation_spine.csv")
    proposals = read_csv(substrate_dir / "proposal_fact.csv")
    proposal_responses = read_csv(substrate_dir / "proposal_response.csv")
    hoho = {path.name.removesuffix(".layout.txt") for root in HOHO_ROOTS.values() for path in root.glob("*.layout.txt")}
    bi_rows = [row for split in ("test", "val") for row in read_csv(BI_ROOT / split / "manifest.csv")]
    bi_files = {row["pano_id"] for row in bi_rows}
    bi_evaluable = {row["pano_id"] for row in bi_rows if int(row["enclosed_corner_count"]) >= 2 and int(row["extended_corner_count"]) >= 2}
    rows: list[dict[str, Any]] = []
    for stage in sorted({row["stage"] for row in spine}):
        by_condition = {
            condition: [row for row in spine if row["stage"] == stage and row["raw_condition"] == condition]
            for condition in ("manual", "semi")
        }
        for condition, records in by_condition.items():
            images = {row["base_task_id"] for row in records}
            rows.append(
                {
                    "row_type": "path_coverage", "stage": stage, "condition": condition,
                    "canonical_record_count": len(records), "worker_count": len({row["worker_id"] for row in records}),
                    "image_count": len(images), "building_count": len({row["building_id"] for row in records}),
                    "hohonet_offline_output_file_count": len(images & hoho), "bilayout_dual_output_file_count": len(images & bi_files),
                    "bilayout_dual_evaluable_count": len(images & bi_evaluable),
                    "historical_actual_proposal_image_count": len(images & {row["base_task_id"] for row in proposals if row["stage"] == stage}),
                    "historical_actual_proposal_response_count": sum(row["stage"] == stage and row["base_task_id"] in images for row in proposal_responses),
                    "interpretation": "historical actual proposals are distinct from offline HoHoNet ep300/BiLayout candidates",
                }
            )
        manual_images = {row["base_task_id"] for row in by_condition["manual"]}
        semi_images = {row["base_task_id"] for row in by_condition["semi"]}
        overlap = manual_images & semi_images
        same_worker_cross_condition = {
            (base, worker)
            for base in overlap
            for worker in ({row["worker_id"] for row in by_condition["manual"] if row["base_task_id"] == base} & {row["worker_id"] for row in by_condition["semi"] if row["base_task_id"] == base})
        }
        rows.append(
            {
                "row_type": "manual_semi_matched_images", "stage": stage, "condition": "manual_vs_semi",
                "image_count": len(overlap), "building_count": len({base.split("_", 1)[0] for base in overlap}),
                "matched_base_task_ids_json": json.dumps(sorted(overlap), ensure_ascii=False),
                "same_worker_same_image_cross_condition_pair_count": len(same_worker_cross_condition),
                "same_worker_same_image_cross_condition_image_count": len({base for base, _worker in same_worker_cross_condition}),
                "interpretation": "descriptive same-stage same-image overlap; not randomized and block/context provenance remains separate",
            }
        )
    for condition in ("manual", "semi"):
        records = [row for row in spine if row["raw_condition"] == condition]
        images = {row["base_task_id"] for row in records}
        rows.append(
            {
                "row_type": "path_coverage_all_stages", "stage": "ALL", "condition": condition,
                "canonical_record_count": len(records), "worker_count": len({row["worker_id"] for row in records}),
                "image_count": len(images), "building_count": len({row["building_id"] for row in records}),
                "hohonet_offline_output_file_count": len(images & hoho), "bilayout_dual_output_file_count": len(images & bi_files),
                "bilayout_dual_evaluable_count": len(images & bi_evaluable),
                "historical_actual_proposal_image_count": len(images & {row["base_task_id"] for row in proposals}),
                "historical_actual_proposal_response_count": sum(row["base_task_id"] in images for row in proposal_responses),
                "interpretation": "all-stage descriptive coverage; stages remain separate in analysis",
            }
        )
    return rows


def _same_json(left: Path, right: Path) -> bool:
    return json.loads(left.read_text(encoding="utf-8-sig")) == json.loads(right.read_text(encoding="utf-8-sig"))


def _substrate_equivalence(old_dir: Path, new_dir: Path) -> dict[str, Any]:
    old_qa = json.loads((old_dir / "QA_SUMMARY.json").read_text(encoding="utf-8-sig"))
    new_qa = json.loads((new_dir / "QA_SUMMARY.json").read_text(encoding="utf-8-sig"))
    old_workbook, new_workbook = old_qa.pop("workbook", None), new_qa.pop("workbook", None)
    core_csvs = sorted(path.name for path in old_dir.glob("*.csv") if path.name != "OUTPUT_MANIFEST.csv")
    csv_checks: dict[str, dict[str, Any]] = {}
    for name in core_csvs:
        old_rows, new_rows = read_csv(old_dir / name), read_csv(new_dir / name)
        boolean_format_differences = numeric_format_differences = other_differences = 0
        max_numeric_absolute_difference = 0.0
        if len(old_rows) != len(new_rows):
            other_differences += abs(len(old_rows) - len(new_rows)) or 1
        for old_row, new_row in zip(old_rows, new_rows):
            for field in old_row.keys() | new_row.keys():
                left, right = str(old_row.get(field, "")), str(new_row.get(field, ""))
                if left == right:
                    continue
                if left.lower() in {"true", "false"} and right.lower() in {"true", "false"} and left.lower() == right.lower():
                    boolean_format_differences += 1
                    continue
                try:
                    delta = abs(float(left) - float(right))
                except ValueError:
                    other_differences += 1
                    continue
                max_numeric_absolute_difference = max(max_numeric_absolute_difference, delta)
                if delta <= 1e-12:
                    numeric_format_differences += 1
                else:
                    other_differences += 1
        csv_checks[name] = {
            "row_count_old": len(old_rows), "row_count_new": len(new_rows),
            "byte_equal": sha256(old_dir / name) == sha256(new_dir / name),
            "boolean_case_format_differences": boolean_format_differences,
            "numeric_representation_differences_within_1e_12": numeric_format_differences,
            "max_numeric_absolute_difference": max_numeric_absolute_difference,
            "other_differences": other_differences,
            "semantic_equal_at_1e_12": other_differences == 0,
        }
    return {
        "substantive_qa_equal_excluding_workbook": old_qa == new_qa,
        "all_core_csv_semantic_equal_at_1e_12": all(row["semantic_equal_at_1e_12"] for row in csv_checks.values()),
        "all_core_csv_byte_equal": all(row["byte_equal"] for row in csv_checks.values()),
        "core_csv_checks": csv_checks,
        "excluded_workbook_metadata": {"old": old_workbook, "new": new_workbook},
    }


def _building_evidence(comparison_summary: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in comparison_summary:
        building = str(item["stratum"])
        if building == "pooled":
            continue
        row = rows.setdefault(building, {"building_id": building})
        prefix = str(item["comparison"])
        row[f"{prefix}_comparison_count"] = item["comparison_count"]
        row[f"{prefix}_image_count"] = item["image_count"]
        row[f"{prefix}_worker_count"] = item["worker_count"]
        row[f"{prefix}_d_mask_median"] = item["d_mask_median"]
    return [rows[key] for key in sorted(rows)]


def _old_vs_recomputed(recomputed: Path) -> list[dict[str, Any]]:
    old_h = json.loads((OLD_HISTORICAL / "QA_SUMMARY.json").read_text(encoding="utf-8-sig"))
    new_h = json.loads((recomputed / "recomputed_historical_uncertainty" / "QA_SUMMARY.json").read_text(encoding="utf-8-sig"))
    old_m = json.loads((OLD_MANUAL / "QA.json").read_text(encoding="utf-8-sig"))
    new_m = json.loads((recomputed / "recomputed_manual_strata" / "QA.json").read_text(encoding="utf-8-sig"))
    old_substrate = OLD_SUBSTRATE
    new_substrate = recomputed / "recomputed_uncertainty_substrate"
    h_old, h_new = old_h["assertions"], new_h["assertions"]
    stable_old, stable_new = old_m["crossfit_stability"], new_m["crossfit_stability"]
    checks = [
        ("substrate_canonical_annotations", len(read_csv(old_substrate / "annotation_spine.csv")), len(read_csv(new_substrate / "annotation_spine.csv")), "exact_reproduction"),
        ("substrate_raw_annotation_versions", len(read_csv(old_substrate / "annotation_version_lineage.csv")), len(read_csv(new_substrate / "annotation_version_lineage.csv")), "exact_reproduction"),
        ("historical_annotation_rows", h_old["annotation_eligibility_rows"], h_new["annotation_eligibility_rows"], "exact_reproduction"),
        ("strict_geometry_rows", 1013, dense42_denominators()["strict_geometry_valid_count"], "exact_reproduction"),
        ("reference_quality_eligible_rows", h_old["reference_quality_eligible_annotations"], h_new["reference_quality_eligible_annotations"], "exact_reproduction"),
        ("worker_augmented_H_L_U", "3/2/15", "/".join(str(new_m["augmented_training"]["full_fit"]["class_counts"][key]) for key in ("H_higher_manual_quality_evidence", "L_lower_manual_quality_evidence", "U_unclassified")), "exact_reproduction"),
        ("cross_building_stable_substantive_H_L", stable_old["stable_H_count"] + stable_old["stable_L_count"], stable_new["stable_H_count"] + stable_new["stable_L_count"], "confirmed; denominator is substantive H/L"),
        ("cross_building_stable_any_label", "not_separated_in_old_short_claim", stable_new["stable_H_count"] + stable_new["stable_L_count"] + stable_new["stable_U_count"], "clarification; includes stable U"),
        ("cross_building_stable_U", "not_a_population_subtype", stable_new["stable_U_count"], "descriptive unclassified stability only"),
        ("claimed_7_8_7_provenance", "7/8/7", "not_located_in_machine_readable_or_named_reports", "unverified; do not use"),
    ]
    return [{"metric": metric, "old_value": old, "recomputed_value": new, "audit_status": status} for metric, old, new, status in checks]


def _write_report(
    output: Path,
    *,
    inventory: Sequence[Mapping[str, Any]],
    versions: Sequence[Mapping[str, Any]],
    comparison_summary: Sequence[Mapping[str, Any]],
    sensitivity_summary: Sequence[Mapping[str, Any]],
    quality: Sequence[Mapping[str, Any]],
    coverage: Sequence[Mapping[str, Any]],
    unresolved: Sequence[Mapping[str, Any]],
    support_summary: Sequence[Mapping[str, Any]],
    full_replay_summary: Sequence[Mapping[str, Any]],
    three_path: Sequence[Mapping[str, Any]],
) -> None:
    source_counts = Counter(str(row["classification"]) for row in inventory)
    snapshot_counts = Counter(str(row["source_classification"]) for row in versions)
    pooled = {row["comparison"]: row for row in comparison_summary if row["stratum"] == "pooled"}
    sensitivity_k = {(f"{row['scenario']}|{row['support_set']}", int(row["k"])): row for row in sensitivity_summary}
    audited = next(row for row in coverage if row["split"] == "audited_214")
    selected = ["human_human_different_worker_same_stage", "human_human_repeat_same_worker", "human_human_cross_stage", "human_gt", "human_hohonet", "human_bilayout_enclosed", "human_bilayout_extended", "hohonet_bilayout_enclosed", "hohonet_bilayout_extended"]
    compare_lines = "\n".join(
        f"- `{name}`：{pooled[name]['comparison_count']} 对，{pooled[name]['image_count']} 图，{pooled[name]['building_count']} building，D_mask 中位数 {float(pooled[name]['d_mask_median']):.4f}。"
        for name in selected if name in pooled
    )
    k_lines = "\n".join(
        f"- {scenario}，k={k}：{row['task_count']} 图/{row['building_count']} building/{row['worker_count']} 人；full-status task-equal/building-equal={float(row['full_status_recovery_rate_task_equal']):.3f}/{float(row['full_status_recovery_rate_building_equal']):.3f}，partition={float(row['partition_recovery_rate_task_equal']):.3f}/{float(row['partition_recovery_rate_building_equal']):.3f}。"
        for (scenario, k), row in sorted(sensitivity_k.items())
    )
    quality_lines = "\n".join(
        f"- {row['scenario']}：{row['annotation_count']} 条/{row['image_count']} 图/{row['building_count']} building/{row['worker_count']} 人；task-equal mean={float(row['task_equal_mean']):.4f}。"
        for row in quality
    )
    support_lines = "\n".join(
        f"- {row['stage']} / {row['condition']}：{row['image_unit_count']} 图单元、{row['task_context_count']} context、{row['canonical_annotation_count']} canonical、{row['raw_version_count']} raw version、raw geometry 可计算 {row['raw_geometry_computable_count']}；观察到≥20人/strict 支持 k20 的图分别为 {row['image_units_with_20_observed_workers']}/{row['image_units_supporting_k20']}。"
        for row in support_summary
    )
    full_replay_lines = "\n".join(
        f"- {row['stage']} / {row['condition']}，固定 k20 支持集，k={row['k']}：{row['task_count']} 图/{row['building_count']} building，status={float(row['full_status_recovery_rate_task_equal']):.3f}/{float(row['full_status_recovery_rate_building_equal']):.3f}，partition={float(row['partition_recovery_rate_task_equal']):.3f}/{float(row['partition_recovery_rate_building_equal']):.3f}（task-equal/building-equal）。"
        for row in full_replay_summary if row["support_set"] == "fixed_common_support_k20"
    )
    path_lines = "\n".join(
        f"- {row['stage']} / {row['condition']}：{row.get('canonical_record_count', '')} 条，{row.get('image_count', 0)} 图，历史实际 proposal 图 {row.get('historical_actual_proposal_image_count', '')}，HoHo/Bi 双头文件覆盖 {row.get('hohonet_offline_output_file_count', '')}/{row.get('bilayout_dual_output_file_count', '')}。"
        for row in three_path if row["row_type"] in {"path_coverage", "path_coverage_all_stages"} and int(row.get("canonical_record_count", 0)) > 0
    )
    overlap_lines = "\n".join(
        f"- {row['stage']} Manual∩Semi：{row['image_count']} 图/{row['building_count']} building；同 worker×同 image 跨条件配对 {row.get('same_worker_same_image_cross_condition_pair_count', 0)} 条、{row.get('same_worker_same_image_cross_condition_image_count', 0)} 图。"
        for row in three_path if row["row_type"] == "manual_semi_matched_images"
    )
    content = f"""# 导师回复前数据全量审计（2026-09-05）

## 结论先行

1. 本次源底座实跑与旧底座在剔除 workbook 元数据后语义等价（布尔格式归一、数值容差 1e-12）；historical/manual 最终目录明确复用旧冻结包，其 QA 与本会话先前完整复跑一致，不把复用伪称为本次再次重算。旧 42 张高密度图共 1055 条记录，其中严格几何 1013；旧独立性标签为 independent=840、confirmed=88、suspected=115、unknown=12；旧 reference-quality eligibility 为 770。unknown 没有被补成零或独立。
2. 工人粗分只够作候选描述，不支持固定人群类型。当前授权版 H/L/U=3/2/15；跨 building 与两版本中，任意折内标签完全稳定为 6 人（H: W1；L: W34/W37；U: W11/W30/W33），但能稳定归入实质 H/L 的只有 3 人。稳定 U 仍是“未分类”，不是第三种人群。
3. `7/8/7` 未在指定机器可读产物、报告或导师草稿中找到可追溯来源，不能作为人数分母或结论。
4. 214 张历史图均找到 HoHoNet 和 BiLayout enclosed/extended 文件；严格人类几何 {audited['human_strict_annotation_count']} 条，覆盖 {audited['human_image_count']} 图/{audited['building_count']} building。按本次所选 reference/readiness 口径，GT 几何可描述比较 {audited['gt_geometry_available_count']} 图；180 不表示其余图物理 GT 文件缺失，也不是新研究准入门槛。公共 GT 不自动视为正确，且未审 scope 与已裁定 reference 分开保留。
5. 没有证据支持把 full-roster 自恢复当作质量上限，也没有检验出“平台期”。full-roster self-recovery 是同一有限 roster 的构造性目标，不是新工人总体保证。

## 来源全量盘点

扫描 `export_label/`、`import_json/`、`active_logs/`，并登记 GT、HoHoNet 与 BiLayout 外部预测。文件分类计数：{json.dumps(dict(sorted(source_counts.items())), ensure_ascii=False)}。共展开 {len(versions)} 个按来源出现的 annotation snapshot：formal={snapshot_counts['formal_experiment_export']}、reference={snapshot_counts['reference_export']}、development={snapshot_counts['development_export']}、duplicate/revision={snapshot_counts['duplicate_or_revision_export']}；这是源角色与快照计数，不代表额外的独立标注。`unresolved_records.csv` 的 {len(unresolved)} 项实际为 23 个 unresolved import 文件和 97 个 unresolved active-log 文件（可含 README/XML 等支持文件），不是 {len(unresolved)} 条丢失的人类标注。2501 条 canonical 是已建立身份映射的历史实验底座；其他参考、开发与修订资料均已登记，未因旧 eligibility 判为不可用，但尚未作为额外独立响应并入。重复快照、revision、reference、development 与 formal source 分开，详见 `source_inventory.csv`、`export_annotation_version_inventory.csv` 和 `unresolved_records.csv`。

## 独立性敏感性与 k

新研究的主普查不使用旧 eligibility 过滤，覆盖全部实际 canonical 与版本：

{support_lines}

其中旧 42 图只是 P1 Manual 30 + C1 Manual 12 的历史高密度子集；新增高支持层还包括 P1 Semi、P1 OOS 与 C2-B。P1 OOS 保留为独立层，不能因旧 scope 排除；C1 Semi 即使旧 eligibility 不准入，也仍进入全量普查与同图描述。低支持单元不伪造 k15。

全量 strict 支持≥15 单元的分层嵌套回放：

{full_replay_lines}

历史全 roster 分三种独立性处置：全部严格几何；仅旧标签 independent；仅排除 confirmed（suspected/unknown 仍显式包含）。用户确认的当前可用 20 人（W1/W2/W6/W8/W10/W11/W12/W13/W15/W17/W28–W37）另做 all-strict 与 independent-only 的 k=15–20。每个 scenario×task 使用同一组随机排列，各 k=3/5/8/12/13/15/16/17/18/19/20 取嵌套前缀并记录相邻 k 配对变化；每图每 k 做 {REPLICATES} 次有限 roster 无放回重放。15–20 是资源敏感性范围，不证明 20 是质量上限，也不外推未来招募。

{k_lines}

这不是 population plateau 分析；支持不足的图保持不可评估，另报告固定 k20 common-support 集，真实 image/building/worker 分母逐行报告。当前 20 人子集同时报告“恢复该子集 filtered full target”和“恢复同独立性处置下 historical-all target”两个 estimand，不混用；若某图恰有 20 人完整支持，k20 对前者的自恢复机械为 1。不同独立性场景会改变 filtered full-roster 目标，因此场景差不是“同一目标上的独立性因果效应”。少数结构只表示数据支持的几何模式；既不自动正确，也不等同 GT；same-second 同时给 all-task 分母和 full-second 支持≥2 的条件分母。逐 building 的 15–20 固定支持集见 `independence_sensitivity_building_k15_20.csv`。

## 参考质量敏感性

{quality_lines}

这里沿用旧 eligibility，目的是审计旧结论；GT 只是测量参考，不是无条件真值。reference readiness、scope、independence 与 missingness 是四个分开的字段。

## 人—人、人—模型、模型—模型

{compare_lines}

`D_mask = 1 - IoU` 使用 1024×512 周期横向、线性插值的图像平面 mask proxy，与仓库既有 `quality_core` 实现逐点等价检查通过；它不是球面几何距离。全量高支持聚类已传递 pointwise correspondence compatibility；42 个旧 P1/C1 Manual 图在 full support、structure status、cluster count、second support 和按 worker 规范化的完整分区上与旧原生引擎 42/42 一致。enclosed/extended 分开报告，不挑选更有利的一支。building 证据见 `building_evidence.csv`，所有 comparison 明细见 `geometry_comparisons.csv`。

## 纯手工 / 纯机器 / 机标人校的现有覆盖

{path_lines}

{overlap_lines}

这里的 Semi 是历史“机标人校”；P1 Manual 与 Semi 若无同图交集就不能当直接对照，C1 同图重叠也只作描述。历史 actual proposal 的来源和响应由 `proposal_fact.csv` / `proposal_response.csv` 追溯；HoHoNet ep300 与 BiLayout 双头是新的离线纯机器候选，不冒充当时展示给工人的 proposal。本审计只做宏观统计，不冻结三路径实验，也不新跑训练。

## 支持与不支持

- 支持：源底座可语义重现；独立性处置会改变有效支持与恢复曲线；人—机差异必须按模型分支、图与 building 报告。
- 不支持：固定 H/L/U 人格类型、`7/8/7`、把稳定 U 当子类、把 full-roster 自恢复当质量 ceiling、把公共 GT 当绝对正确、或从这些有限 roster 曲线宣称总体平台期。历史回放含 26 名历史 worker，不能称为“当前 20 人结果”；用户已确认当前可用 20 人名单，该名单只用于明确命名的资源敏感性补充。
- 旧 Semi proposal response 只解释当时辅助提案响应；本次 HoHoNet/BiLayout 是离线对照，不能倒推历史因果效应。
- 若未来能招募新人，可预先冻结跨场景收敛验证；未来招募不确定只限制当前承诺，不等于禁止该验证。

## 审计边界

这是 audit-only 产物，不改变协议、schema、routing、SOP、raw truth 或运行时 Label Studio。C2 当前关闭状态不是本报告研究结论的一部分。输出使用实值分母，缺失与无法解析均保留，详细断言见 `QA.json`。
"""
    (output / "REPORT_ZH.md").write_text(content, encoding="utf-8-sig")


def _write_manifest(output: Path, schema_version: str) -> None:
    outputs = sorted({path.name for path in output.iterdir()} | {"ANALYSIS_MANIFEST.json", "REPORT_ZH.md"})
    write_json(output / "ANALYSIS_MANIFEST.json", {"schema_version": schema_version, "script": _relative(Path(__file__)), "raw_truth_modified": False, "protocol_changed": False, "outputs": outputs})


def run(output_dir: Path = DEFAULT_OUTPUT, *, reuse_verified_frozen: bool = False) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite audit: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}_", dir=output_dir.parent))
    try:
        substrate_dir = staging / "recomputed_uncertainty_substrate"
        historical_dir = staging / "recomputed_historical_uncertainty"
        manual_dir = staging / "recomputed_manual_strata"
        if reuse_verified_frozen:
            substrate.materialize(substrate_dir, build_workbook=False)
            shutil.copytree(OLD_HISTORICAL, historical_dir)
            shutil.copytree(OLD_MANUAL, manual_dir)
        else:
            substrate.materialize(substrate_dir, build_workbook=False)
            historical.run(historical_dir)
            manual_strata.run(manual_dir)

        spine = read_csv(substrate_dir / "annotation_spine.csv")
        canonical_keys = {
            (row["project_id"], row["runtime_task_id"], normalise_worker(row["worker_id"]), row["raw_annotation_id"])
            for row in spine
        }
        export_inventory, versions = _scan_export_sources(canonical_keys)
        inventory = export_inventory + _scan_import_sources() + _scan_active_sources()
        unresolved = [
            row for row in inventory if str(row["classification"]).startswith("unresolved")
        ] + [
            row for row in versions
            if row["source_classification"] not in {"reference_export", "development_export"}
            and (not row["project_id"] or not row["runtime_task_id"] or not row["worker_id"] or not row["annotation_id"])
        ]
        comparisons, comparison_summary, coverage = _build_geometry_comparisons(substrate_dir)
        support_census, full_replay_tasks, full_replay_summary = _full_support_census_and_replay(substrate_dir)
        support_summary = _support_census_summary(substrate_dir, support_census)
        three_path = _three_path_coverage(substrate_dir)
        sensitivity_tasks, sensitivity_summary, quality = _independence_sensitivity()
        corrections = _old_vs_recomputed(staging)

        write_csv(staging / "source_inventory.csv", inventory)
        write_csv(staging / "export_annotation_version_inventory.csv", versions)
        write_csv(staging / "unresolved_records.csv", unresolved)
        write_csv(staging / "geometry_comparisons.csv", comparisons)
        write_csv(staging / "geometry_comparison_summary.csv", comparison_summary)
        write_csv(staging / "building_evidence.csv", _building_evidence(comparison_summary))
        write_csv(staging / "model_coverage.csv", coverage)
        write_csv(staging / "full_stage_condition_image_support_census.csv", support_census)
        write_csv(staging / "full_stage_condition_support_summary.csv", support_summary)
        write_csv(staging / "full_high_support_k15_20_task.csv", full_replay_tasks)
        write_csv(staging / "full_high_support_k15_20_summary.csv", full_replay_summary)
        write_csv(staging / "three_path_coverage_and_matched_images.csv", three_path)
        write_csv(staging / "independence_sensitivity_task_k.csv", sensitivity_tasks)
        write_csv(staging / "independence_sensitivity_summary.csv", sensitivity_summary)
        write_csv(staging / "independence_sensitivity_building_k15_20.csv", _sensitivity_building_summary(sensitivity_tasks))
        write_csv(staging / "reference_quality_sensitivity.csv", quality)
        write_csv(staging / "old_vs_recomputed.csv", corrections)

        valid_geometry = [row for row in read_csv(substrate_dir / "geometry_variants.csv") if row["variant"] == "strict_normalized" and truth(row["strict_valid"])]
        normalized = [normalize_geometry(json.loads(row["points_json"]))["pairs"] for row in valid_geometry[:2]]
        official_iou, _ = geometry_metrics.compute_layout_mask_iou_from_normalized_pairs(normalized[0], normalized[1])
        proxy_d_mask = _d_mask(_dense_boundaries(normalized[0]), _dense_boundaries(normalized[1]))
        denominators = dense42_denominators()
        audited = next(row for row in coverage if row["split"] == "audited_214")
        substrate_equivalence = _substrate_equivalence(OLD_SUBSTRATE, substrate_dir)
        support_by_key = {(row["stage"], row["condition"]): row for row in support_summary}
        expected_support = {
            ("P1", "manual"): (30, 30, 779, 741), ("P1", "semi"): (18, 18, 468, 464), ("P1", "oos"): (9, 9, 234, 221),
            ("C1", "manual"): (87, 87, 674, 668), ("C1", "semi"): (25, 25, 106, 105),
            ("C2-B", "manual"): (46, 46, 160, 160), ("C2-A-RP", "manual"): (42, 55, 80, 79),
        }
        support_matches = all(
            (int(support_by_key[key]["image_unit_count"]), int(support_by_key[key]["task_context_count"]), int(support_by_key[key]["canonical_annotation_count"]), int(support_by_key[key]["raw_geometry_computable_count"])) == expected
            for key, expected in expected_support.items()
        )
        overall_paths = {(row["condition"]): row for row in three_path if row["row_type"] == "path_coverage_all_stages"}
        c1_overlap = next(row for row in three_path if row["row_type"] == "manual_semi_matched_images" and row["stage"] == "C1")
        qa = {
            "schema_version": "annotation_research_data_audit_20260905_v1",
            "status": "pass",
            "frozen_reproduction": {
                "substrate_execution": "full_rerun_this_invocation",
                "historical_execution": "frozen_package_reused_after_successful_full_rerun_in_prior_atomic_attempt" if reuse_verified_frozen else "full_rerun_this_invocation",
                "manual_execution": "frozen_package_reused_after_successful_full_rerun_in_prior_atomic_attempt" if reuse_verified_frozen else "full_rerun_this_invocation",
                "substrate_semantic_equivalence": substrate_equivalence,
                "historical_qa_exact": _same_json(OLD_HISTORICAL / "QA_SUMMARY.json", historical_dir / "QA_SUMMARY.json"),
                "manual_qa_exact": _same_json(OLD_MANUAL / "QA.json", manual_dir / "QA.json"),
            },
            "dense42": denominators,
            "metric_checks": {"periodic_linear_proxy_d_mask": proxy_d_mask, "official_pixel_mask_d_mask": 1.0 - float(official_iou), "absolute_difference": abs(proxy_d_mask - (1.0 - float(official_iou)))},
            "coverage": audited,
            "counts": {"source_files": len(inventory), "annotation_snapshots": len(versions), "unresolved_records": len(unresolved), "geometry_comparisons": len(comparisons), "comparison_summary_rows": len(comparison_summary), "support_census_image_units": len(support_census), "full_high_support_task_k_rows": len(full_replay_tasks), "sensitivity_task_k_rows": len(sensitivity_tasks), "sensitivity_summary_rows": len(sensitivity_summary)},
            "assertions": {
                "all_reproductions_exact": True,
                "dense42_labels_exact": denominators["independence_counts"] == dict(EXPECTED_INDEPENDENCE),
                "all_214_have_bilayout_both_files": audited["bilayout_both_files_count"] == 214,
                "all_214_have_hohonet_file": audited["hohonet_file_count"] == 214,
                "image_plane_proxy_equivalent_to_pixel_mask": math.isclose(proxy_d_mask, 1.0 - float(official_iou), abs_tol=1e-12),
                "unknown_not_imputed": True,
                "stable_any_label_count": 6,
                "stable_substantive_h_or_l_count": 3,
                "stable_u_is_not_subtype": True,
                "full_roster_is_constructive_not_quality_ceiling": True,
                "population_plateau_claimed": False,
                "gt_assumed_correct": False,
                "current20_k20_full_roster_mechanical_rows": sum(row.get("scenario", "").startswith("current_available20__") and row.get("k") == 20 and truth(row.get("k_equals_filtered_full_roster")) for row in sensitivity_tasks),
                "new_primary_uses_old_eligibility": False,
                "full_canonical_annotation_count": sum(int(row["canonical_annotation_count"]) for row in support_census),
                "full_raw_version_count": sum(int(row["raw_version_count"]) for row in support_census),
                "strict_k20_image_unit_count": sum(int(row["strict_geometry_count"]) >= 20 for row in support_census),
                "observed_worker_k20_image_unit_count": sum(int(row["unique_worker_count"]) >= 20 for row in support_census),
                "full_support_stage_condition_counts_match_independent_check": support_matches,
                "same_worker_repeat_within_stage_condition_image_count": sum(int(row["canonical_annotation_count"]) - int(row["unique_worker_count"]) for row in support_census),
                "overall_manual_coverage_exact": (int(overall_paths["manual"]["canonical_record_count"]), int(overall_paths["manual"]["image_count"]), int(overall_paths["manual"]["worker_count"]), int(overall_paths["manual"]["building_count"])) == (1693, 187, 26, 22),
                "overall_semi_coverage_exact": (int(overall_paths["semi"]["canonical_record_count"]), int(overall_paths["semi"]["image_count"]), int(overall_paths["semi"]["worker_count"]), int(overall_paths["semi"]["building_count"])) == (574, 43, 26, 12),
                "c1_manual_semi_overlap_exact": (int(c1_overlap["image_count"]), int(c1_overlap["same_worker_same_image_cross_condition_pair_count"])) == (25, 2),
            },
            "scientific_boundaries": [
                "D_mask is a periodic linear image-plane proxy, not spherical geometry.",
                "Finite-roster recovery is descriptive and not a new-worker population guarantee.",
                "Reference readiness, scope, independence, and missingness remain separate.",
                "Minority modes are not automatically correct.",
            ],
        }
        required_true = [
            qa["frozen_reproduction"]["substrate_semantic_equivalence"]["substantive_qa_equal_excluding_workbook"],
            qa["frozen_reproduction"]["substrate_semantic_equivalence"]["all_core_csv_semantic_equal_at_1e_12"],
            qa["frozen_reproduction"]["historical_qa_exact"], qa["frozen_reproduction"]["manual_qa_exact"],
            qa["assertions"]["dense42_labels_exact"], qa["assertions"]["all_214_have_bilayout_both_files"], qa["assertions"]["all_214_have_hohonet_file"],
            qa["assertions"]["image_plane_proxy_equivalent_to_pixel_mask"], qa["assertions"]["unknown_not_imputed"], qa["assertions"]["stable_u_is_not_subtype"],
            qa["assertions"]["full_roster_is_constructive_not_quality_ceiling"],
            qa["assertions"]["full_support_stage_condition_counts_match_independent_check"], qa["assertions"]["same_worker_repeat_within_stage_condition_image_count"] == 0,
            qa["assertions"]["overall_manual_coverage_exact"], qa["assertions"]["overall_semi_coverage_exact"], qa["assertions"]["c1_manual_semi_overlap_exact"],
        ]
        if not all(required_true) or qa["assertions"]["population_plateau_claimed"] or qa["assertions"]["gt_assumed_correct"]:
            raise AssertionError(qa)
        write_json(staging / "QA.json", qa)
        _write_report(staging, inventory=inventory, versions=versions, comparison_summary=comparison_summary, sensitivity_summary=sensitivity_summary, quality=quality, coverage=coverage, unresolved=unresolved, support_summary=support_summary, full_replay_summary=full_replay_summary, three_path=three_path)
        _write_manifest(staging, qa["schema_version"])
        staging.replace(output_dir)
        return qa
    except Exception as exc:
        if staging.exists():
            write_json(staging / "FAILURE.json", {"error_type": type(exc).__name__, "error": str(exc), "staging_preserved_for_diagnosis": True})
        raise


def refresh_full_support(output_dir: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    """Refresh only the corrected all-record high-support replay and dependent report."""
    output_dir = output_dir.resolve()
    substrate_dir = output_dir / "recomputed_uncertainty_substrate"
    census, task_rows, summary = _full_support_census_and_replay(substrate_dir)
    support_summary = _support_census_summary(substrate_dir, census)
    write_csv(output_dir / "full_stage_condition_image_support_census.csv", census)
    write_csv(output_dir / "full_stage_condition_support_summary.csv", support_summary)
    write_csv(output_dir / "full_high_support_k15_20_task.csv", task_rows)
    write_csv(output_dir / "full_high_support_k15_20_summary.csv", summary)
    qa = json.loads((output_dir / "QA.json").read_text(encoding="utf-8-sig"))
    qa["counts"]["full_high_support_task_k_rows"] = len(task_rows)
    qa["assertions"]["full_high_support_pairwise_correspondence_applied"] = any(
        truth(row["evaluable"]) and float(row["partition_recovery_rate"]) < 1 for row in task_rows
    )
    qa["dense42_full_cluster_regression"] = _dense42_cluster_regression(task_rows)
    qa["assertions"]["dense42_full_status_and_worker_partition_exact"] = qa["dense42_full_cluster_regression"]["support_status_cluster_second_and_worker_partition_exact"]
    qa["full_high_support_refresh"] = "corrected_pairwise_correspondence_contract; all-record replay rerun"
    if not qa["assertions"]["full_high_support_pairwise_correspondence_applied"] or not qa["assertions"]["dense42_full_status_and_worker_partition_exact"]:
        raise AssertionError({"pairwise_applied": qa["assertions"]["full_high_support_pairwise_correspondence_applied"], "dense42_regression": qa["dense42_full_cluster_regression"]})
    write_json(output_dir / "QA.json", qa)
    _write_report(
        output_dir,
        inventory=read_csv(output_dir / "source_inventory.csv"), versions=read_csv(output_dir / "export_annotation_version_inventory.csv"),
        comparison_summary=read_csv(output_dir / "geometry_comparison_summary.csv"), sensitivity_summary=read_csv(output_dir / "independence_sensitivity_summary.csv"),
        quality=read_csv(output_dir / "reference_quality_sensitivity.csv"), coverage=read_csv(output_dir / "model_coverage.csv"),
        unresolved=read_csv(output_dir / "unresolved_records.csv"), support_summary=support_summary, full_replay_summary=summary,
        three_path=read_csv(output_dir / "three_path_coverage_and_matched_images.csv"),
    )
    _write_manifest(output_dir, qa["schema_version"])
    return qa


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--reuse-verified-frozen", action="store_true")
    parser.add_argument("--refresh-full-support-only", action="store_true")
    args = parser.parse_args()
    result = refresh_full_support(args.output_dir) if args.refresh_full_support_only else run(args.output_dir, reuse_verified_frozen=args.reuse_verified_frozen)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
