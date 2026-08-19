"""Materialize diagnostic PreScreen reviewer profiles and C1 validation sidecars."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import sys
import warnings
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any, Callable

import numpy as np
from scipy.stats import ConstantInputWarning, kendalltau, spearmanr

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.geometry_consensus.representation import (
    normalize_geometry,
    normalize_geometry_for_c1_calculation,
)
from tools.thesis_main.analysis.materialize_c1_operational_reference import _gt_references
from tools.thesis_main.analysis.prescreen_worker_gold_alignment_audit import (
    _load_final_gold,
    _load_source_gt_from_scope_summary,
    _reference_points,
)
from tools.thesis_main.analysis.quality_core.choice_parser import extract_data
from tools.thesis_main.analysis.quality_core.geometry_metrics import (
    compute_layout_mask_iou,
    compute_layout_mask_iou_from_normalized_pairs,
    compute_pointwise_rmse_cyclic,
)
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file, sha256_json


RULE_VERSION = "reviewer_profile_dual_stage_diagnostic_v2"
EPSILONS = (0.0, 0.01, 0.02, 0.05)
BOOTSTRAP_SEED = 20260819
BOOTSTRAP_DRAWS = 1000
FLAGS: dict[str, bool] = {
    "diagnostic_pre_stage3": True,
    "development_only": True,
    "scientific_conclusion_prohibited": True,
    "formal_profile_frozen": False,
    "reviewer_policy_frozen": False,
    "main_launch_authorized": False,
}
REQUIRED_OUTPUTS = (
    "SEMI_INITIALIZATION_BINDING_AUDIT.csv",
    "SEMI_CANONICAL_RECONCILIATION.csv",
    "SEMI_ROW_LEVEL_REVIEWER_EVIDENCE.csv",
    "P1_REVIEWER_PROFILE.csv",
    "C1_REVIEWER_VALIDATION_PROFILE.csv",
    "CROSS_STAGE_REVIEWER_VALIDATION.csv",
    "REVIEWER_PROFILE_THRESHOLD_SENSITIVITY.csv",
    "REVIEWER_PROFILE_READINESS.csv",
    "REVIEWER_PROFILE_DATA_AND_PROVENANCE.md",
    "analysis_manifest.json",
)
DEFAULT_OUTPUT_DIR = Path("analysis_results/reviewer_profile_dual_stage_processing_20260819_v2")


def _paths(root: Path) -> dict[str, Path]:
    p1 = root / "analysis_results/prescreen_closeout_final_gold_v2_20260701"
    c1 = root / "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03"
    return {
        "processing_script": root / "tools/thesis_main/analysis/materialize_reviewer_profile_dual_stage.py",
        "processing_test": root / "tests/test_materialize_reviewer_profile_dual_stage.py",
        "method_contract": root / "docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json",
        "p1_canonical": p1 / "prescreen_canonical_annotations.csv",
        "p1_duplicates": p1 / "prescreen_duplicate_annotation_audit.csv",
        "p1_admission": p1 / "prescreen_worker_admission.csv",
        "p1_selection": root / "analysis_results/phase1_progress_20260324/prescreen_semi_final_selection_v10.json",
        "p1_synthetic_review": p1 / "raw_inputs/prescreen_semi_synthetic_trap_issue_review.csv",
        "p1_gold_status": p1 / "prescreen_gold_status_audit.csv",
        "p1_synthetic_binding": p1 / "prescreen_synthetic_geometry_gt_binding_audit.csv",
        "p1_scope_summary": p1 / "prescreen_scope_summary.json",
        "p1_final_gold": p1 / "final_gold_records_v2_p1_closeout_corrected.jsonl",
        "p1_import_zh": root / "import_json/stage1_prescreen_final_20260325/stage1_prescreen_semi_import_v5.json",
        "p1_import_en": root / "import_json/stage1_prescreen_foreign_https_20260609/stage1_prescreen_semi_import_v5_foreign_https.json",
        "p1_runtime_zh": root / "export_label/stage1_chinese/project-29-at-2026-06-30-09-00-e7ea6931.json",
        "p1_runtime_en": root / "export_label/stage1_English/project-40-at-2026-06-28-05-14-bb74a057.json",
        "c1_canonical": c1 / "c1_canonical_annotations.csv",
        "c1_eligibility": c1 / "c1_row_analysis_eligibility.csv",
        "c1_quality": c1 / "c1_gt_quality_analysis.csv",
        "c1_failure": c1 / "failure_disposition.csv",
        "c1_harmonization": c1 / "model_issue_harmonization_C1.csv",
        "c1_outcome_reference": c1 / "c1_task_outcome_reference.csv",
        "c1_import_zh": root / "import_json/calibration_c1_v3_1_formal/c1_v3_1_semi_import_zh.json",
        "c1_import_en": root / "import_json/calibration_c1_v3_1_formal/c1_v3_1_semi_import_foreign_https.json",
        "c1_runtime_zh": root / "export_label/stage2_Chinese/project-72-at-2026-07-30-13-02-f69c5ac4.json",
        "c1_runtime_en": root / "export_label/stage2_English/project-68-at-2026-07-30-13-02-cf7d8306.json",
        "c1_snapshot_zh": c1 / "raw_snapshots/exports/40f9dd7d1efb_project-72-at-2026-07-30-13-02-f69c5ac4.json",
        "c1_snapshot_en": c1 / "raw_snapshots/exports/455a0f2e543d_project-68-at-2026-07-30-13-02-cf7d8306.json",
        "c1_gt": root / "export_label/groudTruth.json",
        "c2a_closeout": root / "analysis_results/c2a_rp_terminal_closeout_20260817_v1/c2a_rp_closeout_v2.json",
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _completed_by(annotation: dict[str, Any]) -> str:
    value = annotation.get("completed_by")
    if isinstance(value, dict):
        value = value.get("id")
    return str(value or "").strip()


def _epsilon_slug(value: float) -> str:
    return f"{value:g}".replace(".", "_")


def _stable_seed(*parts: Any) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def _flagged(row: dict[str, Any]) -> dict[str, Any]:
    return {**row, **FLAGS}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"empty_output_not_allowed:{path.name}")
    rows = [_flagged(row) for row in rows]
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: str(value).lower() if isinstance(value, bool) else "" if value is None else value for key, value in row.items()})


def _points(result: list[dict[str, Any]]) -> list[list[float]]:
    corners, _polygon, _choices, _all = extract_data(result or [])
    return [[float(x), float(y)] for x, y in corners.tolist()]


def _geometry_hash(points: list[list[float]]) -> str:
    return sha256_json(points)


def _prediction_payload(prediction: dict[str, Any]) -> dict[str, Any]:
    return {"model_version": prediction.get("model_version", ""), "result": prediction.get("result") or []}


def validate_import_pair(stage: str, imports: dict[str, Path], *, expected_count: int) -> list[dict[str, Any]]:
    """Validate unique predictions and exact cross-language proposal geometry."""
    by_language: dict[str, dict[str, dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []
    for language, path in sorted(imports.items()):
        tasks = _read_json(path)
        if not isinstance(tasks, list) or len(tasks) != expected_count:
            raise ValueError(f"{stage}:{language}:import_task_count")
        seen: dict[str, dict[str, Any]] = {}
        for task in tasks:
            data = task.get("data") or {}
            base = str(data.get("base_task_id") or Path(str(data.get("title") or "")).stem).strip()
            predictions = task.get("predictions") or []
            if len(predictions) != 1:
                raise ValueError(f"{stage}:{language}:{base}:prediction_count")
            if not base or base in seen:
                raise ValueError(f"{stage}:{language}:duplicate_or_missing_base_task_id")
            prediction = predictions[0]
            points = _points(prediction.get("result") or [])
            if not points:
                raise ValueError(f"{stage}:{language}:{base}:prediction_geometry_missing")
            payload_sha = sha256_json(_prediction_payload(prediction))
            record = {
                "stage": stage,
                "language_cohort": language,
                "base_task_id": base,
                "planned_task_id": str(data.get("task_id") or ""),
                "import_path": str(path),
                "import_sha256": sha256_file(path),
                "model_version": str(prediction.get("model_version") or ""),
                "prediction_count": 1,
                "prediction_payload_sha256": payload_sha,
                "prediction_geometry_hash": _geometry_hash(points),
                "initialization_artifact_id": f"init:{stage.lower()}:{payload_sha[:20]}",
                "_prediction": prediction,
                "_prediction_points": points,
                "_data": data,
            }
            seen[base] = record
            rows.append(record)
        by_language[language] = seen
    languages = sorted(by_language)
    if len(languages) != 2 or set(by_language[languages[0]]) != set(by_language[languages[1]]):
        raise ValueError(f"{stage}:language_task_set_conflict")
    for base in by_language[languages[0]]:
        left, right = by_language[languages[0]][base], by_language[languages[1]][base]
        if left["prediction_geometry_hash"] != right["prediction_geometry_hash"]:
            raise ValueError(f"{stage}:{base}:language_prediction_geometry_conflict")
        if left["model_version"] != right["model_version"]:
            raise ValueError(f"{stage}:{base}:language_model_version_conflict")
    return sorted(rows, key=lambda row: (row["stage"], row["language_cohort"], row["base_task_id"]))


def load_runtime(path: Path, project_id: str, *, expected_sha256: str | None = None) -> dict[str, dict[str, Any]]:
    digest = sha256_file(path)
    if expected_sha256 and digest != expected_sha256:
        raise ValueError(f"runtime_export_sha256_mismatch:{path}")
    tasks = _read_json(path)
    result: dict[str, dict[str, Any]] = {}
    for task in tasks:
        actual_project = str(task.get("project") or project_id)
        if actual_project != str(project_id):
            raise ValueError(f"runtime_project_mismatch:{path}")
        data = task.get("data") or {}
        base = str(data.get("base_task_id") or Path(str(data.get("title") or "")).stem).strip()
        if not base or base in result:
            raise ValueError(f"runtime_duplicate_or_missing_base_task_id:{path}")
        result[base] = {
            "project_id": str(project_id),
            "runtime_task_id": str(task.get("id") or ""),
            "runtime_path": str(path),
            "runtime_sha256": digest,
            "task": task,
        }
    return result


def validate_c1_reference(frozen: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    if not _bool(frozen.get("geometry_reference_ready")):
        return reference
    if not reference or not reference.get("points"):
        raise ValueError("reference_missing")
    if str(frozen.get("reference_identity") or "") != str(reference.get("identity") or ""):
        raise ValueError("reference_identity_mismatch")
    if str(frozen.get("reference_sha256") or "") != str(reference.get("sha256") or ""):
        raise ValueError("reference_sha256_mismatch")
    if reference.get("structural_status") != "valid":
        raise ValueError("reference_structurally_invalid")
    return reference


def classify_behavior(
    *, stage: str, role: str, issue_reported: bool | None, acceptable: bool | None,
    exact_equal: bool | None, delta_u: float | None, epsilon: float,
) -> dict[str, bool | None]:
    harmful = None if delta_u is None else delta_u < -epsilon
    edited = None if exact_equal is None else not exact_equal
    consistent = None if issue_reported is None or edited is None else issue_reported == edited
    if stage == "C1":
        return {
            "proposal_accepted_unchanged": None if acceptable is None or exact_equal is None else acceptable and exact_equal,
            "issue_reported": issue_reported,
            "geometry_edited": edited,
            "issue_geometry_edit_concordant": consistent,
            "harmful_correction": harmful,
            "non_harmful_handling": None if harmful is None else not harmful,
        }
    is_trap, is_control = role == "trap", role == "control"
    return {
        "unmodified_trap_submission": None if not is_trap or exact_equal is None else exact_equal,
        "strict_blind_trust": None if not is_trap or acceptable is None or exact_equal is None else acceptable and exact_equal,
        "issue_reported_without_quality_improvement": None if not is_trap or issue_reported is None or delta_u is None else issue_reported and delta_u <= epsilon,
        "quality_improving_correction": None if not is_trap or delta_u is None else delta_u > epsilon,
        "harmful_correction": harmful,
        "control_false_alarm": None if not is_control or issue_reported is None else issue_reported,
        "control_overcorrection": None if not is_control or harmful is None else harmful,
        "non_harmful_control_handling": None if not is_control or harmful is None else not harmful,
        "issue_geometry_edit_concordant": consistent,
    }


def bootstrap_ci(
    values: list[float], *, draws: int = BOOTSTRAP_DRAWS, seed: int = BOOTSTRAP_SEED,
    statistic: str = "mean",
) -> tuple[float | None, float | None, int]:
    if not values or draws <= 0:
        return None, None, 0
    array = np.asarray(values, dtype=float)
    samples = np.random.default_rng(seed).choice(array, size=(draws, len(array)), replace=True)
    estimates = np.median(samples, axis=1) if statistic == "median" else np.mean(samples, axis=1)
    lower, upper = np.quantile(estimates, [0.025, 0.975])
    return float(lower), float(upper), int(draws)


def _score_geometry(stage: str, points: list[list[float]], reference: dict[str, Any] | None) -> tuple[float | None, bool, str]:
    normalized = normalize_geometry_for_c1_calculation(points) if stage == "C1" else normalize_geometry(points)
    valid = bool(normalized.get("valid"))
    if not reference or not reference.get("points"):
        return None, valid, "reference_not_evaluable"
    if not valid:
        return 0.0, False, "proposal_structural_failure" if stage == "C1" else "worker_or_proposal_structural_failure"
    if reference.get("structural_status") not in {None, "valid"}:
        return None, valid, "reference_structurally_invalid"
    if stage == "C1" and reference.get("geometry_mode") == "ordered_consecutive_pairs_with_duplicate_x":
        score, meta = compute_layout_mask_iou_from_normalized_pairs(normalized.get("pairs") or [], reference.get("pairs") or [])
    else:
        ref_normalized = normalize_geometry(reference["points"])
        if not ref_normalized.get("valid"):
            return None, valid, "reference_structurally_invalid"
        score, meta = compute_layout_mask_iou(np.asarray(points, dtype=float), np.asarray(reference["points"], dtype=float))
    return score, valid, str(meta.get("reason") or "")


def _choice(result: list[dict[str, Any]]) -> tuple[str, bool | None, bool | None]:
    _corners, _polygon, choices, _all = extract_data(result or [])
    values = sorted(set(choices.get("model_issue") or []))
    if not values:
        return "", None, None
    acceptable = values == ["acceptable"]
    return ";".join(values), not acceptable, acceptable


def _edit_distance(initial: list[list[float]], final: list[list[float]]) -> tuple[float | None, float | None, str]:
    value, used, meta = compute_pointwise_rmse_cyclic(np.asarray(initial, dtype=float), np.asarray(final, dtype=float))
    if not used or value is None:
        return None, None, str(meta.get("gate_reason") or "not_evaluable")
    return float(value), float(value / math.hypot(1024, 512)), ""


def _raw_reconciliation(
    stage: str, canonical: list[dict[str, str]], runtimes: dict[str, dict[str, dict[str, Any]]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], int]:
    selected: dict[tuple[str, str, str], dict[str, str]] = {}
    duplicates: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in canonical:
        project = row.get("project_id", "")
        task = row.get("task_id", "") if stage == "P1" else row.get("ls_runtime_task_id", "")
        raw_id = row.get("raw_canonical_annotation_id") or row.get("annotation_id", "")
        selected[(project, task, raw_id)] = row
        for annotation_id in filter(None, row.get("duplicate_annotation_ids", "").split(";")):
            duplicates[(project, task, annotation_id)] = row
    by_canonical: dict[str, dict[str, Any]] = {}
    audit: list[dict[str, Any]] = []
    raw_count = 0
    for language, runtime_by_base in runtimes.items():
        for runtime in runtime_by_base.values():
            task = runtime["task"]
            project, task_id = runtime["project_id"], runtime["runtime_task_id"]
            for annotation in task.get("annotations") or []:
                raw_count += 1
                annotation_id = str(annotation.get("id") or "")
                key = (project, task_id, annotation_id)
                row = selected.get(key) or duplicates.get(key)
                if not row:
                    raise ValueError(f"{stage}:raw_annotation_orphan:{project}:{task_id}:{annotation_id}")
                expected_worker = row.get("annotator_id", "") if stage == "P1" else row.get("worker_id", "")
                if _completed_by(annotation) != expected_worker:
                    raise ValueError(f"{stage}:raw_annotation_worker_mismatch:{annotation_id}")
                status = "canonical_selected" if key in selected else "superseded_duplicate"
                canonical_id = row["canonical_annotation_id"]
                if status == "canonical_selected":
                    if canonical_id in by_canonical:
                        raise ValueError(f"{stage}:canonical_annotation_bound_twice:{canonical_id}")
                    by_canonical[canonical_id] = annotation
                    if stage == "C1" and sha256_json(annotation.get("result") or []) != row.get("response_hash", ""):
                        raise ValueError(f"C1:canonical_response_sha256_mismatch:{canonical_id}")
                audit.append({
                    "stage": stage,
                    "language_cohort": language,
                    "project_id": project,
                    "runtime_task_id": task_id,
                    "base_task_id": str((task.get("data") or {}).get("base_task_id") or Path(str((task.get("data") or {}).get("title") or "")).stem),
                    "worker_id": expected_worker,
                    "raw_annotation_id": annotation_id,
                    "canonical_annotation_id": canonical_id,
                    "reconciliation_status": status,
                    "duplicate_geometry_type": row.get("duplicate_geometry_type", ""),
                    "raw_result_sha256": sha256_json(annotation.get("result") or []),
                    "runtime_export_path": runtime["runtime_path"],
                    "runtime_export_sha256": runtime["runtime_sha256"],
                })
    if len(by_canonical) != len(canonical):
        raise ValueError(f"{stage}:canonical_runtime_binding_incomplete")
    return by_canonical, audit, raw_count


def _bind_initializations(
    stage: str,
    imports: list[dict[str, Any]],
    runtimes: dict[str, dict[str, dict[str, Any]]],
    canonical: list[dict[str, str]],
    projects: dict[str, str],
    *, original_runtime_paths: dict[str, Path] | None = None,
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    canonical_by_context: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in canonical:
        base = row.get("base_task_id") or Path(row.get("task_label", "")).stem
        canonical_by_context[(row.get("project_id", ""), base)].append(row)
    audit: list[dict[str, Any]] = []
    bindings: dict[tuple[str, str], dict[str, Any]] = {}
    bound_ids: set[str] = set()
    for item in imports:
        language, base = item["language_cohort"], item["base_task_id"]
        project = projects[language]
        runtime = runtimes[language].get(base)
        context_rows = canonical_by_context.get((project, base), [])
        if runtime is None:
            if context_rows:
                raise ValueError(f"{stage}:{language}:{base}:runtime_task_missing_for_canonical")
            binding_status = "not_deployed_no_runtime_task"
            runtime_task_id = runtime_path = runtime_sha = ""
            embedded_count = 0
        else:
            runtime_task_id = runtime["runtime_task_id"]
            runtime_path, runtime_sha = runtime["runtime_path"], runtime["runtime_sha256"]
            annotations = runtime["task"].get("annotations") or []
            if not annotations:
                raise ValueError(f"{stage}:{language}:{base}:runtime_task_without_annotation_evidence")
            for annotation in annotations:
                embedded = annotation.get("prediction")
                if not isinstance(embedded, dict):
                    raise ValueError(f"{stage}:{language}:{base}:runtime_embedded_prediction_missing")
                if sha256_json(_prediction_payload(embedded)) != item["prediction_payload_sha256"]:
                    raise ValueError(f"{stage}:{language}:{base}:runtime_prediction_sha256_mismatch")
            for row in context_rows:
                row_task = row.get("task_id", "") if stage == "P1" else row.get("ls_runtime_task_id", "")
                if row_task != runtime_task_id:
                    raise ValueError(f"{stage}:{language}:{base}:runtime_task_crosswalk_mismatch")
                bound_ids.add(row["canonical_annotation_id"])
            embedded_count = len(annotations)
            binding_status = "recovered_unique_crosswalk_and_sha"
            bindings[(project, base)] = item
        original_path = (original_runtime_paths or {}).get(language)
        original_sha = sha256_file(original_path) if original_path else runtime_sha
        if original_path and runtime and original_sha != runtime_sha:
            raise ValueError(f"{stage}:{language}:runtime_snapshot_sha256_mismatch")
        audit.append({
            **{key: value for key, value in item.items() if not key.startswith("_")},
            "runtime_project_id": project,
            "runtime_task_id": runtime_task_id,
            "runtime_export_path": runtime_path,
            "runtime_export_sha256": runtime_sha,
            "original_runtime_export_path": str(original_path or runtime_path),
            "original_runtime_export_sha256": original_sha,
            "runtime_embedded_prediction_match_count": embedded_count,
            "canonical_annotation_count": len(context_rows),
            "binding_basis": "base_task_id+language_cohort+runtime_project/task+canonical_annotation+prediction_payload_sha256",
            "binding_status": binding_status,
            "source_presence_interpretation": "source_present_consumer_previously_unbound",
        })
    if bound_ids != {row["canonical_annotation_id"] for row in canonical}:
        raise ValueError(f"{stage}:observed_canonical_initialization_binding_incomplete")
    return audit, bindings


def _metric(
    output: dict[str, Any], name: str, values: list[float], expected: int,
    *, draws: int, seed: int, statistic: str = "mean",
) -> None:
    value = (median(values) if statistic == "median" else mean(values)) if values else None
    lower, upper, valid_draws = bootstrap_ci(values, draws=draws, seed=seed, statistic=statistic)
    output.update({
        name: value,
        f"{name}_n": len(values),
        f"{name}_missing": expected - len(values),
        f"{name}_ci_lower": lower,
        f"{name}_ci_upper": upper,
        f"{name}_bootstrap_valid_draws": valid_draws,
    })


def _youden_ci(trap: list[float], control_specific: list[float], draws: int, seed: int) -> tuple[float | None, float | None, int]:
    if not trap or not control_specific or draws <= 0:
        return None, None, 0
    rng = np.random.default_rng(seed)
    t = np.asarray(trap, dtype=float)
    c = np.asarray(control_specific, dtype=float)
    estimates = rng.choice(t, (draws, len(t))).mean(axis=1) + rng.choice(c, (draws, len(c))).mean(axis=1) - 1
    lower, upper = np.quantile(estimates, [0.025, 0.975])
    return float(lower), float(upper), draws


def _task_centered_residuals(
    rows: list[dict[str, Any]], field: str, workers: set[str] | None = None,
) -> dict[str, list[float]]:
    valid = [
        (row, value) for row in rows
        if (workers is None or row["worker_id"] in workers)
        and (value := _float(row.get(field))) is not None
    ]
    task_values: dict[str, list[float]] = defaultdict(list)
    for row, value in valid:
        task_values[row["base_task_id"]].append(value)
    task_means = {task: mean(values) for task, values in task_values.items()}
    residuals: dict[str, list[float]] = defaultdict(list)
    for row, value in valid:
        residuals[row["worker_id"]].append(value - task_means[row["base_task_id"]])
    return dict(residuals)


def _p1_profiles(
    evidence: list[dict[str, Any]], c1_eligible: set[str], current20: set[str], draws: int,
) -> tuple[list[dict[str, Any]], dict[tuple[str, float], dict[str, Any]]]:
    by_worker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evidence:
        if row["stage"] == "P1":
            by_worker[row["worker_id"]].append(row)
    computed: dict[tuple[str, float], dict[str, Any]] = {}
    for worker, rows in sorted(by_worker.items(), key=lambda item: int(item[0])):
        trap = [row for row in rows if row["semi_role"] == "trap"]
        control = [row for row in rows if row["semi_role"] == "control"]
        for epsilon in EPSILONS:
            slug = _epsilon_slug(epsilon)
            out: dict[str, Any] = {"stage": "P1", "worker_id": worker, "epsilon": epsilon, "total_support": len(rows), "trap_support": len(trap), "control_support": len(control)}
            seed = _stable_seed(BOOTSTRAP_SEED, "P1", worker, epsilon)
            sensitivity = [float(row["issue_reported"]) for row in trap if row["issue_reported"] is not None]
            specificity = [float(not row["issue_reported"]) for row in control if row["issue_reported"] is not None]
            _metric(out, "trap_detection_sensitivity", sensitivity, len(trap), draws=draws, seed=seed + 1)
            _metric(out, "control_specificity", specificity, len(control), draws=draws, seed=seed + 2)
            youden = mean(sensitivity) + mean(specificity) - 1 if sensitivity and specificity else None
            yl, yu, yd = _youden_ci(sensitivity, specificity, draws, seed + 3)
            out.update({"detection_youden_index": youden, "detection_youden_index_n": len(sensitivity) + len(specificity), "detection_youden_index_missing": len(rows) - len(sensitivity) - len(specificity), "detection_youden_index_ci_lower": yl, "detection_youden_index_ci_upper": yu, "detection_youden_index_bootstrap_valid_draws": yd})
            metrics = {
                "strict_blind_trust_rate": (trap, f"strict_blind_trust_eps_{slug}"),
                "quality_improving_correction_rate": (trap, f"quality_improving_correction_eps_{slug}"),
                "control_harmful_edit_rate": (control, f"control_overcorrection_eps_{slug}"),
                "issue_geometry_edit_concordance_rate": (rows, f"issue_geometry_edit_concordant_eps_{slug}"),
            }
            for index, (name, (source, field)) in enumerate(metrics.items(), start=4):
                values = [float(row[field]) for row in source if row[field] is not None]
                _metric(out, name, values, len(source), draws=draws, seed=seed + index)
            trap_delta = [row["delta_U"] for row in trap if row["delta_U"] is not None]
            _metric(out, "trap_delta_u_mean", trap_delta, len(trap), draws=draws, seed=seed + 9)
            _metric(out, "trap_delta_u_median", trap_delta, len(trap), draws=draws, seed=seed + 10, statistic="median")
            for family in ("overextend_adjacent", "over_parsing", "corner_drift", "corner_duplicate", "unknown_trap"):
                family_rows = [row for row in trap if row["trap_family"] == family]
                detected = [float(row["issue_reported"]) for row in family_rows if row["issue_reported"] is not None]
                success = [float(row[f"quality_improving_correction_eps_{slug}"]) for row in family_rows if row[f"quality_improving_correction_eps_{slug}"] is not None]
                out[f"family_{family}_support"] = len(family_rows)
                out[f"family_{family}_detection_rate"] = mean(detected) if detected else None
                out[f"family_{family}_quality_improving_correction_rate"] = mean(success) if success else None
                out[f"family_{family}_support_status"] = "support_gated_weak" if family_rows else "not_evaluable"
            computed[(worker, epsilon)] = out
    profiles: list[dict[str, Any]] = []
    memberships = (
        ("all26_sensitivity", set(by_worker), False),
        ("c1_eligible23_primary", c1_eligible, True),
        ("current20_sensitivity", current20, False),
    )
    for (worker, epsilon), row in computed.items():
        for cohort, workers, primary in memberships:
            if worker in workers:
                profiles.append({**row, "analysis_cohort": cohort, "primary_cohort": primary, "c1_eligible_worker": worker in c1_eligible, "current20_worker": worker in current20, "profile_interpretation": "diagnostic_no_score_no_tier"})
    return profiles, computed


def _c1_profiles(evidence: list[dict[str, Any]], current20: set[str], draws: int) -> tuple[list[dict[str, Any]], dict[tuple[str, float], dict[str, Any]]]:
    by_worker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evidence:
        if row["stage"] == "C1":
            by_worker[row["worker_id"]].append(row)
    eligible_rows = [row for rows in by_worker.values() for row in rows if row["analysis_eligible"]]
    centered: dict[tuple[float, str], dict[str, list[float]]] = {}
    for epsilon in EPSILONS:
        slug = _epsilon_slug(epsilon)
        for name, field in {
            "delta_u": "delta_U",
            "acceptable_unchanged_proposal": f"proposal_accepted_unchanged_eps_{slug}",
            "issue_geometry_edit_concordance": f"issue_geometry_edit_concordant_eps_{slug}",
            "harmful_edit": f"harmful_correction_eps_{slug}",
        }.items():
            centered[(epsilon, name)] = _task_centered_residuals(eligible_rows, field)
    profiles: list[dict[str, Any]] = []
    computed: dict[tuple[str, float], dict[str, Any]] = {}
    for worker, all_rows in sorted(by_worker.items(), key=lambda item: int(item[0])):
        rows = [row for row in all_rows if row["analysis_eligible"]]
        for epsilon in EPSILONS:
            slug = _epsilon_slug(epsilon)
            seed = _stable_seed(BOOTSTRAP_SEED, "C1", worker, epsilon)
            out: dict[str, Any] = {
                "stage": "C1", "worker_id": worker, "epsilon": epsilon,
                "total_support": len(all_rows), "eligible_support": len(rows),
                "eligible_missing_or_excluded": len(all_rows) - len(rows), "current20_worker": worker in current20,
            }
            metric_fields = {
                "acceptable_unchanged_proposal_rate": f"proposal_accepted_unchanged_eps_{slug}",
                "issue_report_rate": "issue_reported",
                "issue_geometry_edit_concordance_rate": f"issue_geometry_edit_concordant_eps_{slug}",
                "harmful_edit_rate": f"harmful_correction_eps_{slug}",
                "non_harmful_handling_rate": f"non_harmful_handling_eps_{slug}",
                "initial_structural_valid_rate": "initial_structurally_valid",
                "final_structural_valid_rate": "final_structurally_valid",
            }
            for index, (name, field) in enumerate(metric_fields.items(), start=1):
                values = [float(row[field]) for row in rows if row[field] is not None]
                _metric(out, name, values, len(rows), draws=draws, seed=seed + index)
            for index, (name, field, statistic) in enumerate((
                ("delta_u_mean", "delta_U", "mean"), ("delta_u_median", "delta_U", "median"),
                ("initial_quality_mean", "U_initial", "mean"), ("final_quality_mean", "U_final", "mean"),
            ), start=10):
                values = [row[field] for row in rows if row[field] is not None]
                _metric(out, name, values, len(rows), draws=draws, seed=seed + index, statistic=statistic)
            for index, name in enumerate(("delta_u", "acceptable_unchanged_proposal", "issue_geometry_edit_concordance", "harmful_edit"), start=20):
                _metric(
                    out, f"task_centered_{name}_mean", centered[(epsilon, name)].get(worker, []), len(rows),
                    draws=draws, seed=seed + index,
                )
            out["task_adjustment"] = "partial_task_centering_then_worker_mean"
            out["validation_interpretation"] = "behavioral_validation_only_not_reviewer_ability_stability"
            profiles.append(out)
            computed[(worker, epsilon)] = out
    return profiles, computed


def _correlation(x: list[float], y: list[float]) -> tuple[float | None, float | None]:
    if len(x) < 3 or len(set(x)) < 2 or len(set(y)) < 2:
        return None, None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConstantInputWarning)
        return float(spearmanr(x, y).statistic), float(kendalltau(x, y).statistic)


def _correlation_bootstrap(x: list[float], y: list[float], draws: int, seed: int) -> tuple[float | None, float | None, int, float | None, float | None, int]:
    if len(x) < 3 or draws <= 0:
        return None, None, 0, None, None, 0
    rng = random.Random(seed)
    spearman_values: list[float] = []
    kendall_values: list[float] = []
    for _ in range(draws):
        indices = [rng.randrange(len(x)) for _ in x]
        sx, sy = [x[index] for index in indices], [y[index] for index in indices]
        s, k = _correlation(sx, sy)
        if s is not None:
            spearman_values.append(s)
        if k is not None:
            kendall_values.append(k)
    def interval(values: list[float]) -> tuple[float | None, float | None, int]:
        if not values:
            return None, None, 0
        lower, upper = np.quantile(values, [0.025, 0.975])
        return float(lower), float(upper), len(values)
    sl, su, sn = interval(spearman_values)
    kl, ku, kn = interval(kendall_values)
    return sl, su, sn, kl, ku, kn


def _task_centered_correlation_bootstrap(
    p1_values: dict[str, float | None], c1_rows: list[dict[str, Any]], c1_field: str,
    workers: set[str], *, draws: int, seed: int,
) -> dict[str, Any]:
    rows = [row for row in c1_rows if row["worker_id"] in workers and _float(row.get(c1_field)) is not None]
    by_worker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_worker[row["worker_id"]].append(row)
    effective = sorted(
        (worker for worker in workers if _float(p1_values.get(worker)) is not None and by_worker.get(worker)),
        key=int,
    )
    residuals = _task_centered_residuals(rows, c1_field, set(effective))
    pairs = [
        (worker, float(p1_values[worker]), mean(residuals[worker]))
        for worker in effective if residuals.get(worker)
    ]
    x, y = [row[1] for row in pairs], [row[2] for row in pairs]
    spearman, kendall = _correlation(x, y)
    if not effective or draws <= 0:
        return {
            "pairs": pairs, "spearman": spearman, "kendall": kendall,
            "spearman_ci_lower": None, "spearman_ci_upper": None, "spearman_bootstrap_valid_draws": 0,
            "kendall_ci_lower": None, "kendall_ci_upper": None, "kendall_bootstrap_valid_draws": 0,
        }
    rng = random.Random(seed)
    spearman_values: list[float] = []
    kendall_values: list[float] = []
    for _ in range(draws):
        sampled = [rng.choice(effective) for _ in effective]
        expanded = [
            {"worker_id": str(index), "base_task_id": row["base_task_id"], "value": row[c1_field]}
            for index, worker in enumerate(sampled)
            for row in by_worker[worker]
        ]
        centered = _task_centered_residuals(expanded, "value")
        sx = [float(p1_values[worker]) for worker in sampled]
        sy = [mean(centered[str(index)]) for index in range(len(sampled))]
        s, k = _correlation(sx, sy)
        if s is not None:
            spearman_values.append(s)
        if k is not None:
            kendall_values.append(k)

    def interval(values: list[float]) -> tuple[float | None, float | None, int]:
        if not values:
            return None, None, 0
        lower, upper = np.quantile(values, [0.025, 0.975])
        return float(lower), float(upper), len(values)

    sl, su, sn = interval(spearman_values)
    kl, ku, kn = interval(kendall_values)
    return {
        "pairs": pairs, "spearman": spearman, "kendall": kendall,
        "spearman_ci_lower": sl, "spearman_ci_upper": su, "spearman_bootstrap_valid_draws": sn,
        "kendall_ci_lower": kl, "kendall_ci_upper": ku, "kendall_bootstrap_valid_draws": kn,
    }


def _cross_stage(
    p1: dict[tuple[str, float], dict[str, Any]], c1: dict[tuple[str, float], dict[str, Any]],
    evidence: list[dict[str, Any]], c1_eligible: set[str], current20: set[str], draws: int,
) -> list[dict[str, Any]]:
    mappings = (
        ("fixed_1_p1_trap_delta_to_c1_delta", "trap_delta_u_mean", "trap_delta_u_mean", "delta_u_mean", "task_centered_delta_u_mean", "delta_U", "quality-gain association; not reviewer ability stability"),
        ("fixed_2_p1_blind_trust_to_c1_acceptable_unchanged", "strict_blind_trust_rate", "strict_blind_trust_rate", "acceptable_unchanged_proposal_rate", "task_centered_acceptable_unchanged_proposal_mean", "proposal_accepted_unchanged", "acceptance/low-edit tendency; constructs are not equivalent"),
        ("fixed_3_p1_youden_to_c1_issue_geometry_edit_concordance", "detection_youden_index", "detection_youden_index", "issue_geometry_edit_concordance_rate", "task_centered_issue_geometry_edit_concordance_mean", "issue_geometry_edit_concordant", "trap discrimination versus binary issue/edit concordance; constructs are not equivalent"),
        ("fixed_4_p1_control_harm_to_c1_harmful_edit", "control_harmful_edit_rate", "control_harmful_edit_rate", "harmful_edit_rate", "task_centered_harmful_edit_mean", "harmful_correction", "harm-avoidance behavioral association; not reviewer ability stability"),
    )
    output: list[dict[str, Any]] = []
    c1_rows = [row for row in evidence if row["stage"] == "C1" and row["analysis_eligible"]]
    for epsilon in EPSILONS:
        for cohort, workers, primary in (("c1_eligible23_primary", c1_eligible, True), ("current20_sensitivity", current20, False)):
            slug = _epsilon_slug(epsilon)
            for mapping, p1_raw_field, p1_adjusted_field, c1_raw_field, c1_adjusted_field, c1_row_base, interpretation in mappings:
                c1_row_field = f"{c1_row_base}_eps_{slug}" if c1_row_base != "delta_U" else c1_row_base
                pairs = [
                    (worker, p1[(worker, epsilon)].get(p1_raw_field), c1[(worker, epsilon)].get(c1_raw_field))
                    for worker in sorted(workers, key=int)
                    if (worker, epsilon) in p1 and (worker, epsilon) in c1
                ]
                pairs = [(worker, x, y) for worker, x, y in pairs if x is not None and y is not None]
                x, y = [float(row[1]) for row in pairs], [float(row[2]) for row in pairs]
                spearman, kendall = _correlation(x, y)
                seed = _stable_seed(BOOTSTRAP_SEED, mapping, cohort, epsilon, "raw")
                sl, su, sn, kl, ku, kn = _correlation_bootstrap(x, y, draws, seed)
                direction = "not_evaluable" if spearman is None else "positive" if spearman > 0 else "negative" if spearman < 0 else "zero"
                output.append({
                    "mapping_id": mapping, "epsilon": epsilon, "analysis_cohort": cohort, "primary_mapping_cohort": primary,
                    "analysis_variant": "unadjusted_descriptive", "primary_diagnostic_variant": False,
                    "p1_metric": p1_raw_field, "c1_metric": c1_raw_field, "effective_worker_n": len(pairs),
                    "worker_ids": ";".join(row[0] for row in pairs), "spearman_rho": spearman,
                    "spearman_ci_lower": sl, "spearman_ci_upper": su, "spearman_bootstrap_valid_draws": sn,
                    "kendall_tau": kendall, "kendall_ci_lower": kl, "kendall_ci_upper": ku,
                    "kendall_bootstrap_valid_draws": kn, "direction": direction,
                    "task_adjustment": "none", "bootstrap_task_center_reestimated_each_draw": False,
                    "construct_interpretation": interpretation, "validation_claim_status": "not_ready_behavioral_diagnostic_only",
                    "mapping_selection_status": "fixed_a_priori_no_significance_selection",
                })
                p1_values = {
                    worker: p1[(worker, epsilon)].get(p1_adjusted_field)
                    for worker in workers if (worker, epsilon) in p1
                }
                adjusted = _task_centered_correlation_bootstrap(
                    p1_values, c1_rows, c1_row_field, workers, draws=draws,
                    seed=_stable_seed(BOOTSTRAP_SEED, mapping, cohort, epsilon, "task_centered"),
                )
                adjusted_pairs = adjusted["pairs"]
                adjusted_spearman = adjusted["spearman"]
                adjusted_direction = "not_evaluable" if adjusted_spearman is None else "positive" if adjusted_spearman > 0 else "negative" if adjusted_spearman < 0 else "zero"
                output.append({
                    "mapping_id": mapping, "epsilon": epsilon, "analysis_cohort": cohort, "primary_mapping_cohort": primary,
                    "analysis_variant": "c1_task_centered_primary_diagnostic", "primary_diagnostic_variant": True,
                    "p1_metric": p1_adjusted_field, "c1_metric": c1_adjusted_field, "effective_worker_n": len(adjusted_pairs),
                    "worker_ids": ";".join(row[0] for row in adjusted_pairs), "spearman_rho": adjusted_spearman,
                    "spearman_ci_lower": adjusted["spearman_ci_lower"], "spearman_ci_upper": adjusted["spearman_ci_upper"], "spearman_bootstrap_valid_draws": adjusted["spearman_bootstrap_valid_draws"],
                    "kendall_tau": adjusted["kendall"], "kendall_ci_lower": adjusted["kendall_ci_lower"], "kendall_ci_upper": adjusted["kendall_ci_upper"],
                    "kendall_bootstrap_valid_draws": adjusted["kendall_bootstrap_valid_draws"], "direction": adjusted_direction,
                    "task_adjustment": "partial_within_cohort_task_centering_then_worker_mean",
                    "bootstrap_task_center_reestimated_each_draw": True,
                    "construct_interpretation": interpretation, "validation_claim_status": "not_ready_behavioral_diagnostic_only",
                    "mapping_selection_status": "fixed_a_priori_no_significance_selection",
                })
    return output


def _threshold_sensitivity(evidence: list[dict[str, Any]], c1_eligible: set[str], current20: set[str]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    p1_metrics = ("unmodified_trap_submission", "strict_blind_trust", "issue_reported_without_quality_improvement", "quality_improving_correction", "harmful_correction", "control_false_alarm", "control_overcorrection", "non_harmful_control_handling")
    c1_metrics = ("proposal_accepted_unchanged", "issue_reported", "geometry_edited", "issue_geometry_edit_concordant", "harmful_correction", "non_harmful_handling")
    cohorts = (
        ("P1", "all26_sensitivity", {row["worker_id"] for row in evidence if row["stage"] == "P1"}),
        ("P1", "c1_eligible23_primary", c1_eligible),
        ("P1", "current20_sensitivity", current20),
        ("C1", "c1_all23_validation", c1_eligible),
        ("C1", "current20_sensitivity", current20),
    )
    for stage, cohort, workers in cohorts:
        source = [row for row in evidence if row["stage"] == stage and row["worker_id"] in workers and (stage == "P1" or row["analysis_eligible"])]
        for epsilon in EPSILONS:
            slug = _epsilon_slug(epsilon)
            for metric in p1_metrics if stage == "P1" else c1_metrics:
                field = "issue_reported" if stage == "C1" and metric == "issue_reported" else f"{metric}_eps_{slug}"
                candidates = source
                if stage == "P1" and metric in {"unmodified_trap_submission", "strict_blind_trust", "issue_reported_without_quality_improvement", "quality_improving_correction"}:
                    candidates = [row for row in source if row["semi_role"] == "trap"]
                elif stage == "P1" and metric in {"control_false_alarm", "control_overcorrection", "non_harmful_control_handling"}:
                    candidates = [row for row in source if row["semi_role"] == "control"]
                values = [row[field] for row in candidates if row.get(field) is not None]
                output.append({
                    "stage": stage, "analysis_cohort": cohort, "epsilon": epsilon, "metric": metric,
                    "numerator": sum(bool(value) for value in values), "denominator": len(values),
                    "missing": len(candidates) - len(values), "metric_value": mean(float(value) for value in values) if values else None,
                    "threshold_grid_status": "fixed_full_grid_no_posthoc_selection",
                })
    return output


def materialize(root: Path, output_dir: Path, *, bootstrap_draws: int = BOOTSTRAP_DRAWS) -> dict[str, Any]:
    root, output_dir = root.resolve(), output_dir.resolve()
    paths = _paths(root)
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing_required_inputs:" + ";".join(missing))
    output_dir.mkdir(parents=True, exist_ok=True)

    p1_canonical = [row for row in _read_csv(paths["p1_canonical"]) if row.get("condition", "").lower() == "semi"]
    c1_canonical = [row for row in _read_csv(paths["c1_canonical"]) if row.get("condition", "").lower() == "semi"]
    if len(p1_canonical) != 468 or len(c1_canonical) != 106:
        raise ValueError("canonical_denominator_mismatch")

    c1_runtime_sha = {language: sha256_file(paths[f"c1_runtime_{language}"]) for language in ("en", "zh")}
    c1_snapshot_sha = {language: sha256_file(paths[f"c1_snapshot_{language}"]) for language in ("en", "zh")}
    if c1_runtime_sha != c1_snapshot_sha:
        raise ValueError("c1_runtime_and_frozen_snapshot_sha256_mismatch")
    p1_runtimes = {
        "en": load_runtime(paths["p1_runtime_en"], "40"),
        "zh": load_runtime(paths["p1_runtime_zh"], "29"),
    }
    c1_runtimes = {
        language: load_runtime(paths[f"c1_snapshot_{language}"], {"en": "68", "zh": "72"}[language], expected_sha256=c1_runtime_sha[language])
        for language in ("en", "zh")
    }
    p1_raw_by_id, p1_reconciliation, p1_raw_count = _raw_reconciliation("P1", p1_canonical, p1_runtimes)
    c1_raw_by_id, c1_reconciliation, c1_raw_count = _raw_reconciliation("C1", c1_canonical, c1_runtimes)
    if p1_raw_count != 469 or sum(row["reconciliation_status"] == "superseded_duplicate" for row in p1_reconciliation) != 1:
        raise ValueError("p1_raw_469_to_canonical_468_reconciliation_failed")
    p1_duplicate_rows = [
        row for row in _read_csv(paths["p1_duplicates"])
        if row.get("project_id") in {"29", "40"} and int(row.get("duplicate_group_size") or 0) > 1
    ]
    if len(p1_duplicate_rows) != 1 or p1_duplicate_rows[0].get("duplicate_geometry_type") != "duplicate_same_geometry":
        raise ValueError("p1_frozen_duplicate_disposition_mismatch")
    p1_extra_raw_disposition = p1_duplicate_rows[0]["duplicate_geometry_type"]

    p1_imports = validate_import_pair("P1", {"en": paths["p1_import_en"], "zh": paths["p1_import_zh"]}, expected_count=18)
    c1_imports = validate_import_pair("C1", {"en": paths["c1_import_en"], "zh": paths["c1_import_zh"]}, expected_count=25)
    p1_binding_audit, p1_bindings = _bind_initializations("P1", p1_imports, p1_runtimes, p1_canonical, {"en": "40", "zh": "29"})
    c1_binding_audit, c1_bindings = _bind_initializations(
        "C1", c1_imports, c1_runtimes, c1_canonical, {"en": "68", "zh": "72"},
        original_runtime_paths={"en": paths["c1_runtime_en"], "zh": paths["c1_runtime_zh"]},
    )

    admission = _read_csv(paths["p1_admission"])
    c1_eligible_workers = {row["worker_id"] for row in admission if _bool(row.get("eligible_for_C1"))}
    c2a = _read_json(paths["c2a_closeout"])
    current20 = {str(row["worker_id"]) for row in c2a.get("worker_outcomes", []) if row.get("terminal_state") != "not_evaluable"}
    if len(c1_eligible_workers) != 23 or len(current20) != 20 or not current20 <= c1_eligible_workers:
        raise ValueError("worker_cohort_denominator_mismatch")

    selection = _read_json(paths["p1_selection"])
    planned_meta: dict[str, dict[str, str]] = {}
    for row in selection["selected_control_rows"]:
        planned_meta[row["base_task_id"]] = {"semi_role": "control", "trap_family": "acceptable", "source_type": "control_natural"}
    for row in selection["selected_trap_rows"]:
        planned_meta[row["base_task_id"]] = {"semi_role": "trap", "trap_family": row["family"], "source_type": row["source_type"]}
    if set(planned_meta) != {row["base_task_id"] for row in p1_imports}:
        raise ValueError("p1_selection_import_task_set_mismatch")
    planned_family_counts = {row["family"]: int(row["current_selected_count"]) for row in selection["family_allocations"] if row["role"] == "trap_core"}
    if planned_family_counts != {name: 3 for name in ("overextend_adjacent", "over_parsing", "corner_drift", "corner_duplicate")}:
        raise ValueError("p1_planned_family_quota_mismatch")
    synthetic_reviews = _read_csv(paths["p1_synthetic_review"])
    reviewed_by_runtime: dict[str, list[str]] = defaultdict(list)
    for row in synthetic_reviews:
        for field in ("en_task_id", "zh_task_id"):
            reviewed_by_runtime[row[field]].append(row.get("reviewed_primary_issue", ""))

    p1_gold_status = {(row["project_id"], row["task_id"]): row for row in _read_csv(paths["p1_gold_status"]) if row.get("condition") == "semi"}
    final_gold = _load_final_gold(paths["p1_final_gold"])
    synthetic_by_task = {row["runtime_task_id"]: row for row in _read_csv(paths["p1_synthetic_binding"])}
    source_gt = _load_source_gt_from_scope_summary(paths["p1_scope_summary"])
    c1_eligibility = {row["canonical_annotation_id"]: row for row in _read_csv(paths["c1_eligibility"]) if row.get("condition") == "semi"}
    c1_quality = {row["canonical_annotation_id"]: row for row in _read_csv(paths["c1_quality"]) if row.get("condition") == "semi"}
    c1_failure = {row["canonical_annotation_id"]: row for row in _read_csv(paths["c1_failure"])}
    c1_harmonization = {row["canonical_annotation_id"]: row for row in _read_csv(paths["c1_harmonization"]) if row.get("condition") == "semi"}
    c1_outcomes = {(row["project_id"], row["ls_runtime_task_id"]): row for row in _read_csv(paths["c1_outcome_reference"]) if row.get("condition") == "semi"}
    c1_references = _gt_references(paths["c1_gt"])
    if not (len(c1_eligibility) == len(c1_quality) == len(c1_harmonization) == 106):
        raise ValueError("c1_frozen_sidecar_binding_incomplete")

    evidence: list[dict[str, Any]] = []
    for row in p1_canonical:
        project, task_id = row["project_id"], row["task_id"]
        language = {"29": "zh", "40": "en"}.get(project)
        if not language:
            raise ValueError(f"P1:unexpected_project:{project}")
        base = Path(row["task_label"]).stem
        binding = p1_bindings[(project, base)]
        annotation = p1_raw_by_id[row["canonical_annotation_id"]]
        final_points = _points(annotation.get("result") or [])
        initial_points = binding["_prediction_points"]
        gold = p1_gold_status.get((project, task_id), {})
        reference_points, reference_reason, reference_type = _reference_points(gold, final_gold, synthetic_by_task, source_gt)
        reference = None if reference_reason else {"identity": gold.get("geometry_gold_task_id", ""), "sha256": sha256_json(reference_points), "points": reference_points, "structural_status": "valid", "geometry_mode": "strict_normalized_geometry"}
        u_initial, initial_valid, initial_reason = _score_geometry("P1", initial_points, reference)
        u_final, final_valid, final_reason = _score_geometry("P1", final_points, reference)
        model_issue, issue_reported, acceptable = _choice(annotation.get("result") or [])
        exact_equal = _geometry_hash(initial_points) == _geometry_hash(final_points)
        edit_px, edit_norm, edit_reason = _edit_distance(initial_points, final_points)
        meta = planned_meta[base]
        family, family_source = meta["trap_family"], "frozen_selection"
        if "synthetic" in meta["source_type"]:
            reviewed = [value for value in reviewed_by_runtime.get(task_id, []) if value]
            family = reviewed[0] if len(reviewed) == 1 else "unknown_trap"
            family_source = "manual_reviewed_primary_issue" if len(reviewed) == 1 else "unknown_missing_unique_manual_review"
        item: dict[str, Any] = {
            "stage": "P1", "language_cohort": language, "project_id": project, "runtime_task_id": task_id,
            "base_task_id": base, "building_id": base.split("_", 1)[0], "worker_id": row["annotator_id"],
            "canonical_annotation_id": row["canonical_annotation_id"], "raw_annotation_id": row["raw_canonical_annotation_id"],
            "initialization_artifact_id": binding["initialization_artifact_id"], "initialization_import_sha256": binding["import_sha256"],
            "initialization_prediction_sha256": binding["prediction_payload_sha256"], "initial_geometry_hash": _geometry_hash(initial_points),
            "final_geometry_hash": _geometry_hash(final_points), "exact_geometry_equal": exact_equal,
            "geometry_edit_rmse_px": edit_px, "geometry_edit_rmse_panorama_diagonal_normalized": edit_norm, "geometry_edit_distance_not_evaluable_reason": edit_reason,
            "U_initial": u_initial, "U_final": u_final, "delta_U": None if u_initial is None or u_final is None else u_final - u_initial,
            "initial_structurally_valid": initial_valid, "final_structurally_valid": final_valid,
            "initial_quality_status": initial_reason or "evaluable", "final_quality_status": final_reason or "evaluable",
            "proposal_failure": not initial_valid, "model_issue_choice": model_issue, "issue_reported": issue_reported, "acceptable_reported": acceptable,
            "semi_role": meta["semi_role"], "planned_trap_family": meta["trap_family"], "trap_family": family,
            "trap_family_source": family_source, "trap_source_type": meta["source_type"],
            "reference_identity": "" if reference is None else reference["identity"], "reference_sha256": "" if reference is None else reference["sha256"],
            "reference_type": reference_type, "reference_eligible": reference is not None,
            "formal_assignment_eligible": "not_applicable_p1", "process_eligible": _bool(row.get("eligible_for_primary_analysis")),
            "independence_eligible": "not_formally_adjudicated_p1", "analysis_eligible": _bool(row.get("eligible_for_primary_analysis")),
            "c1_eligible_worker": row["annotator_id"] in c1_eligible_workers, "current20_worker": row["annotator_id"] in current20,
            "stage_role": "profile_development_only",
        }
        for epsilon in EPSILONS:
            for key, value in classify_behavior(stage="P1", role=meta["semi_role"], issue_reported=issue_reported, acceptable=acceptable, exact_equal=exact_equal, delta_u=item["delta_U"], epsilon=epsilon).items():
                item[f"{key}_eps_{_epsilon_slug(epsilon)}"] = value
        evidence.append(item)

    for row in c1_canonical:
        project, task_id, base = row["project_id"], row["ls_runtime_task_id"], row["base_task_id"]
        language = {"68": "en", "72": "zh"}.get(project)
        if not language:
            raise ValueError(f"C1:unexpected_project:{project}")
        binding = c1_bindings[(project, base)]
        annotation = c1_raw_by_id[row["canonical_annotation_id"]]
        final_points, initial_points = _points(annotation.get("result") or []), binding["_prediction_points"]
        outcome = c1_outcomes.get((project, task_id), {})
        reference = c1_references.get(base, {})
        if _bool(outcome.get("geometry_reference_ready")) and outcome.get("final_scope") == "in_scope":
            reference = validate_c1_reference(outcome, reference)
        else:
            reference = None
        quality, eligibility = c1_quality[row["canonical_annotation_id"]], c1_eligibility[row["canonical_annotation_id"]]
        if _bool(quality.get("gt_reference_resolved")) and reference:
            validate_c1_reference({"geometry_reference_ready": True, "reference_identity": quality["reference_identity"], "reference_sha256": quality["reference_sha256"]}, reference)
        u_initial, initial_valid, initial_reason = _score_geometry("C1", initial_points, reference)
        if _bool(quality.get("quality_evaluable")):
            u_final, final_status = _float(quality.get("iou_to_gt")), "frozen_quality_evaluable"
        elif _bool(quality.get("worker_caused_structural_failure")) and reference:
            u_final, final_status = 0.0, "frozen_worker_caused_structural_invalid_delivery_zero"
        else:
            u_final, final_status = None, "frozen_reference_or_outcome_not_evaluable"
        final_valid = _bool(quality.get("structurally_valid"))
        model_issue, issue_reported, acceptable = _choice(annotation.get("result") or [])
        exact_equal = _geometry_hash(initial_points) == _geometry_hash(final_points)
        edit_px, edit_norm, edit_reason = _edit_distance(initial_points, final_points)
        harmonized = c1_harmonization[row["canonical_annotation_id"]]
        failure = c1_failure.get(row["canonical_annotation_id"], {})
        item = {
            "stage": "C1", "language_cohort": language, "project_id": project, "runtime_task_id": task_id,
            "base_task_id": base, "building_id": quality.get("building_id") or base.split("_", 1)[0], "worker_id": row["worker_id"],
            "canonical_annotation_id": row["canonical_annotation_id"], "raw_annotation_id": row["raw_canonical_annotation_id"],
            "initialization_artifact_id": binding["initialization_artifact_id"], "initialization_import_sha256": binding["import_sha256"],
            "initialization_prediction_sha256": binding["prediction_payload_sha256"], "initial_geometry_hash": _geometry_hash(initial_points),
            "final_geometry_hash": _geometry_hash(final_points), "exact_geometry_equal": exact_equal,
            "geometry_edit_rmse_px": edit_px, "geometry_edit_rmse_panorama_diagonal_normalized": edit_norm, "geometry_edit_distance_not_evaluable_reason": edit_reason,
            "U_initial": u_initial, "U_final": u_final, "delta_U": None if u_initial is None or u_final is None else u_final - u_initial,
            "initial_structurally_valid": initial_valid, "final_structurally_valid": final_valid,
            "initial_quality_status": initial_reason or "evaluable", "final_quality_status": final_status,
            "proposal_failure": not initial_valid, "model_issue_choice": model_issue, "issue_reported": issue_reported, "acceptable_reported": acceptable,
            "semi_role": "calibration_validation_no_trap_truth", "planned_trap_family": "", "trap_family": "", "trap_family_source": "not_applicable_c1",
            "reference_identity": outcome.get("reference_identity", ""), "reference_sha256": outcome.get("reference_sha256", ""),
            "reference_type": outcome.get("geometry_reference_mode", ""), "reference_eligible": reference is not None,
            "formal_assignment_eligible": _bool(eligibility.get("formal_assignment_eligible")), "process_eligible": _bool(eligibility.get("process_eligible")),
            "independence_eligible": _bool(eligibility.get("independence_eligible")), "analysis_eligible": _bool(eligibility.get("semi_correction_analysis_eligible")),
            "worker_caused_structural_failure": _bool(quality.get("worker_caused_structural_failure")),
            "failure_attribution": quality.get("failure_attribution") or failure.get("failure_attribution", ""),
            "frozen_harmonization_validity_status": harmonized.get("harmonization_validity_status", ""),
            "frozen_harmonization_assertion_source": harmonized.get("assertion_source", ""),
            "frozen_initialization_provenance_status": harmonized.get("original_provenance_status", ""),
            "c1_eligible_worker": row["worker_id"] in c1_eligible_workers, "current20_worker": row["worker_id"] in current20,
            "stage_role": "cross_stage_validation_only_no_blind_trust_label",
        }
        for epsilon in EPSILONS:
            for key, value in classify_behavior(stage="C1", role="", issue_reported=issue_reported, acceptable=acceptable, exact_equal=exact_equal, delta_u=item["delta_U"], epsilon=epsilon).items():
                item[f"{key}_eps_{_epsilon_slug(epsilon)}"] = value
        evidence.append(item)

    p1_workers = {row["worker_id"] for row in evidence if row["stage"] == "P1"}
    p1_trap = sum(row["semi_role"] == "trap" for row in evidence if row["stage"] == "P1")
    p1_control = sum(row["semi_role"] == "control" for row in evidence if row["stage"] == "P1")
    p1_c1_support = sum(row["worker_id"] in c1_eligible_workers for row in evidence if row["stage"] == "P1")
    p1_current_support = sum(row["worker_id"] in current20 for row in evidence if row["stage"] == "P1")
    c1_workers = {row["worker_id"] for row in evidence if row["stage"] == "C1"}
    formal_count = sum(row["formal_assignment_eligible"] is True for row in evidence if row["stage"] == "C1")
    correction_count = sum(row["analysis_eligible"] is True for row in evidence if row["stage"] == "C1")
    c1_tasks = {row["base_task_id"] for row in evidence if row["stage"] == "C1"}
    c1_eligible_rows = [row for row in evidence if row["stage"] == "C1" and row["analysis_eligible"]]
    c1_delta_rows = [row for row in c1_eligible_rows if row["delta_U"] is not None]
    c1_delta_workers = {row["worker_id"] for row in c1_delta_rows}
    c1_initial_only_missing = sum(row["U_initial"] is None and row["U_final"] is not None for row in c1_eligible_rows)
    c1_final_only_missing = sum(row["U_initial"] is not None and row["U_final"] is None for row in c1_eligible_rows)
    c1_both_missing = sum(row["U_initial"] is None and row["U_final"] is None for row in c1_eligible_rows)
    if (len(p1_workers), p1_trap, p1_control, p1_c1_support, p1_current_support) != (26, 312, 156, 414, 360):
        raise ValueError("p1_support_closure_failed")
    if (len(c1_workers), len(c1_tasks), formal_count, correction_count) != (23, 25, 104, 88):
        raise ValueError("c1_support_closure_failed")

    p1_profiles, p1_profile_map = _p1_profiles(evidence, c1_eligible_workers, current20, bootstrap_draws)
    c1_profiles, c1_profile_map = _c1_profiles(evidence, current20, bootstrap_draws)
    cross_stage = _cross_stage(p1_profile_map, c1_profile_map, evidence, c1_eligible_workers, current20, bootstrap_draws)
    threshold = _threshold_sensitivity(evidence, c1_eligible_workers, current20)
    actual_family_counts = defaultdict(int)
    actual_family_tasks: dict[str, set[str]] = defaultdict(set)
    for row in evidence:
        if row["stage"] == "P1" and row["semi_role"] == "trap":
            actual_family_counts[row["trap_family"]] += 1
            actual_family_tasks[row["trap_family"]].add(row["base_task_id"])
    actual_family_task_counts = {name: len(tasks) for name, tasks in sorted(actual_family_tasks.items())}
    p1_trap_task_initial = {
        row["base_task_id"]: row["U_initial"] for row in evidence
        if row["stage"] == "P1" and row["semi_role"] == "trap" and row["U_initial"] is not None
    }
    trap_initial_min, trap_initial_max = min(p1_trap_task_initial.values()), max(p1_trap_task_initial.values())
    readiness = [
        {"check_id": "p1_canonical_denominator", "status": "pass", "observed": 468, "expected": 468, "notes": "frozen Semi canonical rows"},
        {"check_id": "p1_raw_reconciliation", "status": "pass", "observed": f"{p1_raw_count}->468", "expected": "469->468", "notes": "one superseded duplicate; no double count"},
        {"check_id": "p1_extra_annotation_truth", "status": "warning", "observed": p1_extra_raw_disposition, "expected": "user plan called it revision", "notes": "frozen duplicate audit shows same geometry, not a geometry revision"},
        {"check_id": "p1_worker_task_matrix", "status": "pass", "observed": "26x18", "expected": "26x18", "notes": "complete balanced Semi matrix"},
        {"check_id": "p1_role_support", "status": "pass", "observed": f"trap={p1_trap};control={p1_control}", "expected": "trap=312;control=156", "notes": "frozen roles"},
        {"check_id": "p1_planned_family_quota", "status": "pass", "observed": json.dumps(planned_family_counts, sort_keys=True), "expected": "3 planned tasks per family", "notes": "planned operator quota only"},
        {"check_id": "p1_reviewed_family_distribution", "status": "warning", "observed": json.dumps(actual_family_task_counts, sort_keys=True), "expected": "manual reviewed issue overrides planned operator", "notes": "actual reviewed task allocation is 2/5/2/3; family-specific rates remain weak/support-gated"},
        {"check_id": "p1_trap_quality_headroom", "status": "warning", "observed": f"initial_U_range={trap_initial_min:.12g}..{trap_initial_max:.12g}", "expected": "interpret delta_U with task baseline/headroom", "notes": "failure to increase IoU is not evidence of absent correction ability; detection remains separately reported"},
        {"check_id": "c1_denominators", "status": "pass", "observed": f"canonical=106;tasks=25;workers=23;formal={formal_count};correction={correction_count}", "expected": "106;25;23;104;88", "notes": "consumed frozen eligibility"},
        {"check_id": "c1_delta_u_row_support", "status": "warning", "observed": f"{len(c1_delta_rows)}/{correction_count}", "expected": "explicit complete-case support", "notes": f"initial-only missing={c1_initial_only_missing};final-only missing={c1_final_only_missing};both missing={c1_both_missing};missing is never zero-filled"},
        {"check_id": "cross_stage_worker_support", "status": "warning", "observed": f"{len(c1_delta_workers)}/{len(c1_eligible_workers)}", "expected": "explicit worker support", "notes": "W14 has zero semi-correction support; correlations retain only evaluable workers"},
        {"check_id": "c1_task_adjustment", "status": "warning", "observed": "partial_task_centering", "expected": "worker+task fixed effects or prespecified equivalent before formal use", "notes": "one-step task centering remains sensitive to worker composition in the sparse unbalanced design; bootstrap re-estimates task means"},
        {"check_id": "import_prediction_uniqueness", "status": "pass", "observed": "P1=18/18 each;C1=25/25 each", "expected": "one prediction per import task", "notes": "cross-language geometry hashes exact"},
        {"check_id": "observed_canonical_initialization_binding", "status": "pass", "observed": "574/574 recovered", "expected": "all observed canonical Semi rows", "notes": "unique crosswalk plus embedded prediction payload SHA"},
        {"check_id": "append_only_audit_history", "status": "warning", "observed": "v2_separated_after_prior_v1_directory_overwrite", "expected": "append-only versioned output directories", "notes": "the original v1 manifest is not recoverable from this package; future revisions must use a new versioned directory"},
        {"check_id": "c1_zh_import_runtime_coverage", "status": "warning", "observed": "25 import;24 deployed runtime tasks", "expected": "all observed canonical rows bound", "notes": "one planned zh import task was not deployed and has no canonical row"},
        {"check_id": "stage_separation", "status": "pass", "observed": "P1 profile;C1 validation", "expected": "no pooled estimator", "notes": "C1 outcomes do not alter P1 thresholds or metrics"},
        {"check_id": "cross_stage_construct_alignment", "status": "warning", "observed": "behavioral mappings are non-equivalent constructs", "expected": "no reviewer ability stability claim", "notes": "blind-trust vs acceptable-unchanged and Youden vs issue/edit concordance remain behavioral diagnostics only"},
        {"check_id": "cross_stage_reviewer_ability_validation", "status": "not_ready", "observed": "partial task-centered diagnostic associations only", "expected": "prospective supported validation before ability claim", "notes": "do not claim cross-stage reviewer ability stability"},
        {"check_id": "expert_or_m1_selection", "status": "no_go", "observed": "not authorized", "expected": "independent policy review/freeze", "notes": "do not select experts, freeze profiles, or activate M1 escalation"},
        {"check_id": "policy_boundary", "status": "pass", "observed": "no score/top-k/tier/dispatch", "expected": "diagnostic only", "notes": "Main launch remains unauthorized"},
    ]

    _write_csv(output_dir / REQUIRED_OUTPUTS[0], p1_binding_audit + c1_binding_audit)
    _write_csv(output_dir / REQUIRED_OUTPUTS[1], p1_reconciliation + c1_reconciliation)
    _write_csv(output_dir / REQUIRED_OUTPUTS[2], evidence)
    _write_csv(output_dir / REQUIRED_OUTPUTS[3], p1_profiles)
    _write_csv(output_dir / REQUIRED_OUTPUTS[4], c1_profiles)
    _write_csv(output_dir / REQUIRED_OUTPUTS[5], cross_stage)
    _write_csv(output_dir / REQUIRED_OUTPUTS[6], threshold)
    _write_csv(output_dir / REQUIRED_OUTPUTS[7], readiness)

    summary = {
        "p1_canonical": 468, "p1_raw": p1_raw_count, "p1_workers": len(p1_workers), "p1_trap": p1_trap,
        "p1_control": p1_control, "p1_c1_eligible_support": p1_c1_support, "p1_current20_support": p1_current_support,
        "c1_canonical": 106, "c1_raw": c1_raw_count, "c1_tasks": len(c1_tasks), "c1_workers": len(c1_workers),
        "c1_formal_assignment_eligible": formal_count, "c1_semi_correction_eligible": correction_count,
        "c1_delta_u_evaluable": len(c1_delta_rows), "c1_delta_u_missing": correction_count - len(c1_delta_rows),
        "c1_delta_u_missing_initial_only": c1_initial_only_missing, "c1_delta_u_missing_final_only": c1_final_only_missing,
        "c1_delta_u_missing_both": c1_both_missing, "cross_stage_worker_evaluable": len(c1_delta_workers),
        "cross_stage_worker_missing": len(c1_eligible_workers) - len(c1_delta_workers),
        "observed_canonical_initialization_binding": "recovered", "p1_extra_raw_disposition": p1_extra_raw_disposition,
        "bootstrap_draws": bootstrap_draws,
    }
    input_manifest = [
        {"role": role, "path": str(path.relative_to(root)).replace("\\", "/"), "sha256": sha256_file(path)}
        for role, path in sorted(paths.items())
    ]
    provenance = [
        "# Reviewer 画像双阶段诊断数据与来源", "",
        *[f"- `{key}={str(value).lower()}`" for key, value in FLAGS.items()], "",
        "## 边界", "",
        "本包仅用于 Stage 3 前的开发诊断：PreScreen 形成画像，Calibration 仅作固定行为映射验证。跨阶段 reviewer 能力验证为 NOT READY，专家/M1 escalation 为 NO-GO。不得据此作科学结论、宣称能力稳定、筛选专家、冻结 reviewer 政策、生成 score/top-k/tier，或授权 Main 启动。", "",
        "## 关键分母", "",
        f"- PreScreen：468 canonical / {p1_raw_count} raw，26×18；trap={p1_trap}，control={p1_control}；C1 合格 23 人支持={p1_c1_support}；当前 20 人支持={p1_current_support}。",
        f"- Calibration：106 canonical / {c1_raw_count} raw，25 base task，23 人；formal-assignment eligible={formal_count}；semi-correction eligible={correction_count}。",
        f"- 88 条 semi-correction eligible 中，ΔU 可计算 {len(c1_delta_rows)} 条、缺失 {correction_count - len(c1_delta_rows)} 条（仅初始缺失 {c1_initial_only_missing}、仅最终缺失 {c1_final_only_missing}、两侧均缺失 {c1_both_missing}）；跨阶段有效 worker={len(c1_delta_workers)}/{len(c1_eligible_workers)}，W14 为零支持。缺失不补零。", "",
        "## 初始化绑定解释", "",
        "C1 初始化不是 source absent，而是既有消费者未绑定。此包只在新 sidecar 内通过 `base_task_id + language cohort + runtime project/task + canonical annotation` 唯一 crosswalk，并逐 annotation 核对 import prediction payload SHA 与 runtime annotation 内嵌 prediction payload SHA 后，标记 observed canonical binding 为 recovered。原正式 C1 工件未改写。", "",
        "两个 C1 import 均为 25/25 且各任务唯一 prediction。Project 72 运行时实际部署 24 个任务；未部署的第 25 个 import 任务没有 canonical submission，因此标记为 `not_deployed_no_runtime_task`，不计入 106 条 observed binding 的恢复声明。", "",
        "## 数据真值说明", "",
        "PreScreen 多出的第 469 条 raw annotation 在冻结 duplicate audit 中是 `duplicate_same_geometry`，不是几何 revision；它仅进入 reconciliation audit，未重复计数。Synthetic trap 的 family 使用人工 `reviewed_primary_issue`；与 planned operator 冲突时不回填预期 family。", "",
        "P1 不调用 C1-only 孤立点修复。C1 `U_final` 直接消费冻结 quality/failure/reference disposition；reference failure 与 not-evaluable 保持 missing，worker-caused structural invalid 才按 delivery-adjusted 规则记 0。", "",
        "## 指标命名与构念限制", "",
        "- `unmodified_trap_submission` 只表示 trap 几何未修改，不表示工人接受 proposal；真正的盲信使用 `strict_blind_trust=acceptable AND exact_geometry_equal`。",
        "- `quality_improving_correction` 仅表示 `delta_U > epsilon`，不表示最终质量已达到可接受门槛。`non_harmful_handling` 包含未编辑提交；`non_harmful_control_handling` 不要求选择 acceptable。",
        "- `issue_geometry_edit_concordant` 只比较是否报告 issue 与 exact geometry hash 是否改变；它不区分微小编辑和实质修正。",
        "- P1 blind trust 与 C1 acceptable+unchanged 主要映射接受/少编辑倾向；P1 Youden 与 C1 issue/edit concordance 不是同一能力构念。四个映射均为行为诊断，不能解释为 reviewer 能力稳定。",
        f"- 12 个 P1 trap 的初始化 U 范围为 {trap_initial_min:.12g}–{trap_initial_max:.12g}；接近天花板的任务缺少 IoU 改善空间，因此未提高 IoU 不自动表示没有纠错能力。人工 reviewed family 的实际任务分配为 `{json.dumps(actual_family_task_counts, sort_keys=True)}`，family-specific rate 仅作 weak/support-gated 描述。", "",
        "## 方法与可复现性", "",
        f"- rule_version: `{RULE_VERSION}`；epsilon 全网格：{', '.join(map(str, EPSILONS))}；bootstrap seed={BOOTSTRAP_SEED}，draws={bootstrap_draws}。",
        "- C1 partial task centering：在每个分析 cohort 内，对 eligible 行按 base_task_id 减去任务均值，再按 worker 取均值；worker bootstrap 每次重抽后重新估计任务均值。稀疏不平衡设计下它仍受同题 worker composition 影响，不等同于 worker+task 双向固定效应；正式使用前必须改用预先规定的双向固定效应或等价模型。未调整结果只保留为 descriptive sensitivity。",
        "- 审计历史：v2 默认写入独立 `_v2` 目录。此前开发运行曾以 v2 规则覆盖 `_v1` 目录，原 v1 manifest 无法从本包恢复；后续版本不得继续复用既有版本目录。",
        "- 复用仓库现有 geometry normalizer、C1-only repair、layout IoU、cyclic pointwise RMSE 与冻结 GT identity/SHA；未新增 scoring method。",
        "- `analysis_manifest.json` 将处理脚本和本测试文件作为 code provenance 输入并记录 SHA，同时列出其余输入与除 manifest 自身外的输出 SHA；manifest 自身因递归哈希不可定义而明确排除。", "",
        "## 输入 SHA", "",
        "| role | path | sha256 |", "|---|---|---|",
        *[f"| {item['role']} | `{item['path']}` | `{item['sha256']}` |" for item in input_manifest], "",
    ]
    (output_dir / REQUIRED_OUTPUTS[8]).write_text("\n".join(provenance), encoding="utf-8")
    outputs = [
        {"path": name, "sha256": sha256_file(output_dir / name)}
        for name in REQUIRED_OUTPUTS[:-1]
    ]
    manifest = {
        "schema_version": RULE_VERSION,
        **FLAGS,
        "method_contract_version": _read_json(paths["method_contract"]).get("contract_version", ""),
        "method_contract_sha256": sha256_file(paths["method_contract"]),
        "bootstrap": {"seed": BOOTSTRAP_SEED, "draws": bootstrap_draws, "resampling_unit": "within_worker_tasks_for_profiles;workers_for_cross_stage;task_means_reestimated_per_partial_task_centered_worker_draw"},
        "code_provenance": {
            role: {"path": item["path"], "sha256": item["sha256"]}
            for role in ("processing_script", "processing_test")
            for item in input_manifest if item["role"] == role
        },
        "epsilon_grid": list(EPSILONS), "summary": summary, "inputs": input_manifest, "outputs": outputs,
        "manifest_self_sha256_policy": "excluded_to_avoid_recursive_hash",
    }
    (output_dir / REQUIRED_OUTPUTS[9]).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_PROJECT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--bootstrap-draws", type=int, default=BOOTSTRAP_DRAWS)
    args = parser.parse_args(argv)
    output = args.output_dir if args.output_dir.is_absolute() else args.repo_root / args.output_dir
    print(json.dumps(materialize(args.repo_root, output, bootstrap_draws=args.bootstrap_draws), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
