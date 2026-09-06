"""Common utilities for the all-stage annotation-uncertainty data-mining report.

This module deliberately separates *computability* from legacy/formal eligibility.
Administrative exit, later-stage eligibility, outside assignment and historical worker
status are retained as data-mining descriptors.  A record is omitted from a given
calculation only when the required variable is not computable.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import re
import subprocess
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
C1 = ROOT / "analysis_results" / "c1_formal_audit_20260802_v16_final" / "c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03"
V2 = ROOT / "analysis_results" / "annotation_uncertainty_manual_semi_20260820_v2"
PERSISTENT = ROOT / "analysis_results" / "persistent_disagreement_diagnostic_20260819_v1"
PACKAGE = ROOT / "analysis_results" / "paper_a_data_mining_package_20260820_v1" / "curated"

STAGE_SOURCES: list[tuple[str, Path]] = [
    ("P1", ROOT / "analysis_results" / "prescreen_closeout_final_gold_v2_20260701" / "prescreen_canonical_annotations.csv"),
    ("C1", C1 / "c1_canonical_annotations.csv"),
    ("C2-B", ROOT / "analysis_results" / "c2b_closeout_20260806_final" / "c2b_canonical_submissions.csv"),
    ("C2-A-RP-B1", ROOT / "analysis_results" / "c2a_rp_block1_reestimate_20260810_v1" / "c2a_rp_block1_canonical_submissions.csv"),
    ("C2-A-RP-B2", ROOT / "analysis_results" / "c2a_rp_block2_reestimate_20260814_v1" / "c2a_rp_block2_canonical_submissions.csv"),
]

MISSING_TOKENS = {"", "none", "null", "nan", "na", "n/a", "not_identifiable", "not_evaluable"}
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lstrip("\ufeff").strip()
    return "" if text.lower() in MISSING_TOKENS else text


def truth(value: Any) -> bool:
    return clean(value).lower() in {"1", "true", "yes", "y", "passed", "valid", "eligible", "matched"}


def number(value: Any) -> float | None:
    text = clean(value)
    if not text:
        return None
    try:
        result = float(text)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def integer(value: Any) -> int | None:
    result = number(value)
    return None if result is None else int(round(result))


def worker_id(value: Any) -> str:
    token = clean(value).upper()
    if token.startswith("W"):
        token = token[1:]
    if token.isdigit():
        return str(int(token))
    return token


def normalise_condition(value: Any) -> str:
    token = clean(value).lower().replace("-", "_")
    if "semi" in token or "assist" in token or "model" in token:
        return "semi"
    if "manual" in token:
        return "manual"
    return token or "unknown"


def read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig", low_memory=False, **kwargs)


def write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def first_value(row: pd.Series | dict[str, Any], names: Iterable[str]) -> Any:
    for name in names:
        if name in row:
            value = row[name]
            if clean(value):
                return value
    return ""


def choose_series(frame: pd.DataFrame, names: Iterable[str], default: Any = "") -> pd.Series:
    output = pd.Series([default] * len(frame), index=frame.index, dtype=object)
    for name in names:
        if name not in frame:
            continue
        source = frame[name].astype(str)
        missing = output.map(clean).eq("")
        usable = source.map(clean).ne("")
        output.loc[missing & usable] = source.loc[missing & usable]
    return output


def strip_image_name(value: Any) -> str:
    text = clean(value).replace("\\", "/").rsplit("/", 1)[-1]
    for suffix in IMAGE_SUFFIXES:
        if text.lower().endswith(suffix):
            return text[: -len(suffix)]
    return text


def building_from_base(value: Any) -> str:
    base = strip_image_name(value)
    if "_" in base:
        return base.split("_", 1)[0]
    return "not_identifiable"


def parse_jsonish(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return value
    text = clean(value)
    if not text:
        return None
    for loader in (json.loads, ast.literal_eval):
        try:
            return loader(text)
        except Exception:
            pass
    return None


def geometry_points(value: Any) -> list[list[float]]:
    payload = parse_jsonish(value)
    if payload is None:
        return []
    if isinstance(payload, dict):
        for key in ("corners_px", "ordered_geometry", "canonical_geometry", "points", "geometry"):
            if key in payload:
                found = geometry_points(payload[key])
                if found:
                    return found
        return []
    if isinstance(payload, (list, tuple)):
        if payload and all(isinstance(item, (list, tuple)) and len(item) >= 2 for item in payload):
            result = []
            for item in payload:
                x, y = number(item[0]), number(item[1])
                if x is None or y is None:
                    return []
                result.append([float(x), float(y)])
            return result
        for item in payload:
            found = geometry_points(item)
            if found:
                return found
    return []


def valid_point_ring(points: list[list[float]]) -> bool:
    if len(points) < 4 or len(points) % 2:
        return False
    array = np.asarray(points, dtype=float)
    return array.ndim == 2 and array.shape[1] == 2 and np.isfinite(array).all()


def cyclic_rmse(points_a: list[list[float]], points_b: list[list[float]], *, width: float = 1024.0, height: float = 512.0) -> float | None:
    """Minimum cyclic/reversed point RMSE, normalised by panorama diagonal.

    This is a descriptive same-topology dispersion measure.  It is not a substitute
    for the frozen C1 boundary/wall-wall similarity contract.
    """
    if not valid_point_ring(points_a) or not valid_point_ring(points_b) or len(points_a) != len(points_b):
        return None
    a = np.asarray(points_a, dtype=float)
    b = np.asarray(points_b, dtype=float)
    diagonal = math.hypot(width, height)

    def distance(candidate: np.ndarray) -> float:
        dx = np.abs(a[:, 0] - candidate[:, 0])
        dx = np.minimum(dx, width - np.minimum(dx, width))
        dy = a[:, 1] - candidate[:, 1]
        return float(np.sqrt(np.mean(dx * dx + dy * dy)) / diagonal)

    candidates = []
    for reverse in (False, True):
        base = b[::-1] if reverse else b
        for shift in range(len(base)):
            candidates.append(distance(np.roll(base, shift, axis=0)))
    return min(candidates) if candidates else None


def shannon_entropy(counts: Iterable[int | float]) -> float:
    array = np.asarray([float(value) for value in counts if float(value) > 0], dtype=float)
    if array.size == 0:
        return float("nan")
    probability = array / array.sum()
    return float(-(probability * np.log(probability)).sum())


def gini_simpson(counts: Iterable[int | float]) -> float:
    array = np.asarray([float(value) for value in counts if float(value) > 0], dtype=float)
    if array.size == 0:
        return float("nan")
    probability = array / array.sum()
    return float(1.0 - np.square(probability).sum())


def bernoulli_entropy(probability: float) -> float:
    p = float(probability)
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return float(-(p * math.log(p) + (1 - p) * math.log(1 - p)))


def pairwise_jaccard(sets: list[set[str]]) -> tuple[float | None, float | None, int]:
    values: list[float] = []
    for left, right in combinations(sets, 2):
        union = left | right
        values.append(1.0 if not union else len(left & right) / len(union))
    if not values:
        return None, None, 0
    return float(np.mean(values)), float(np.median(values)), len(values)


def recursive_strings(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for child in value.values():
            yield from recursive_strings(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from recursive_strings(child)
    elif isinstance(value, str):
        yield value


def extract_image_reference(task_data_json: Any) -> str:
    payload = parse_jsonish(task_data_json)
    for text in recursive_strings(payload):
        lower = text.lower().split("?", 1)[0]
        if lower.endswith(IMAGE_SUFFIXES):
            return text
    return ""


def extract_choice_records(result_json: Any) -> list[dict[str, str]]:
    payload = parse_jsonish(result_json)
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        from_name = clean(item.get("from_name"))
        to_name = clean(item.get("to_name"))
        result_type = clean(item.get("type"))
        value = item.get("value") if isinstance(item.get("value"), dict) else {}
        choices: list[Any] = []
        for key in ("choices", "labels", "taxonomy", "textarea"):
            candidate = value.get(key)
            if isinstance(candidate, list):
                choices.extend(candidate)
            elif clean(candidate):
                choices.append(candidate)
        for choice in choices:
            if isinstance(choice, (list, tuple)):
                token = " > ".join(map(str, choice))
            elif isinstance(choice, dict):
                token = clean(choice.get("label") or choice.get("value") or json.dumps(choice, ensure_ascii=False, sort_keys=True))
            else:
                token = clean(choice)
            if token:
                rows.append({"from_name": from_name, "to_name": to_name, "result_type": result_type, "choice_raw": token})
    return rows


def choice_group(from_name: str, choice: str) -> tuple[str, str, str]:
    """Map a raw choice to a broad group while preserving the original token."""
    joined = f"{from_name} {choice}".lower().replace("_", " ").replace("-", " ")
    # Difficulty / image-property labels
    if any(token in joined for token in ("reflect", "transparent", "glass", "mirror", "反射", "透明", "玻璃", "镜面")):
        return "difficulty", "reflection_transparency", "反射/透明"
    if any(token in joined for token in ("occlusion", "occluded", "blocked", "遮挡")):
        return "difficulty", "occlusion", "遮挡"
    if any(token in joined for token in ("low texture", "textureless", "低纹理")):
        return "difficulty", "low_texture", "低纹理"
    if any(token in joined for token in ("complex topology", "topology complex", "复杂拓扑")):
        return "difficulty", "complex_topology", "复杂拓扑"
    if any(token in joined for token in ("seam", "接缝")) and "issue" not in joined:
        return "difficulty", "seam", "全景接缝"

    # Scope observations
    if any(token in joined for token in ("in scope", "in-scope", "camera room only", "可标", "范围内")):
        return "scope", "in_scope", "范围内"
    if any(token in joined for token in ("non manhattan", "non-manhattan", "geometric assumption", "几何假设", "非曼哈顿")):
        return "scope", "oos_non_manhattan", "范围外：非曼哈顿/几何假设不适用"
    if any(token in joined for token in ("open boundary", "ambiguous boundary", "open or ambiguous", "开放边界", "边界歧义")):
        return "scope", "oos_open_or_ambiguous_boundary", "范围/边界开放或歧义"
    if any(token in joined for token in ("split level", "multi level", "split-level", "multi-level", "多层", "错层")):
        return "scope", "oos_split_or_multi_level", "范围外：错层/多层"
    if any(token in joined for token in ("insufficient geometric evidence", "insufficient evidence", "证据不足")):
        return "scope", "oos_insufficient_evidence", "几何证据不足"
    if re.search(r"\boos\b|out of scope|out-of-scope|范围外", joined):
        return "scope", "oos_other", "其他范围外"

    # Model issue / proposal response
    if any(token in joined for token in ("acceptable", "no issue", "looks good", "可接受", "无问题")):
        return "model_issue", "acceptable", "模型初始结果可接受"
    if any(token in joined for token in ("underextend", "under extend", "undercoverage", "漏标", "欠延伸")):
        return "model_issue", "underextension", "模型欠延伸/覆盖不足"
    if any(token in joined for token in ("overextend", "over extend", "adjacent", "过度延伸", "相邻空间")):
        return "model_issue", "overextension", "模型过度延伸/纳入相邻空间"
    if any(token in joined for token in ("corner drift", "corner", "角点漂移", "角点")):
        return "model_issue", "corner_issue", "角点问题"
    if any(token in joined for token in ("duplicate peak", "duplicate", "重复峰", "重复角")):
        return "model_issue", "duplicate_issue", "重复角点/峰"
    if any(token in joined for token in ("topology", "over parsing", "over-parsing", "拓扑", "过度解析")):
        return "model_issue", "topology_issue", "拓扑/过度解析问题"
    if any(token in joined for token in ("postprocess invalid", "invalid", "后处理无效")) and "scope" not in joined:
        return "model_issue", "invalid_output", "模型输出无效"
    if any(token in joined for token in ("seam instability", "seam issue", "接缝问题")):
        return "model_issue", "seam_issue", "接缝问题"
    if "issue" in joined or "problem" in joined or "模型问题" in joined:
        return "model_issue", "other_issue", "其他模型问题"

    return "other_choice", re.sub(r"\s+", "_", clean(choice).lower())[:120], "其他选择"


def load_c1_geometry_map() -> dict[str, list[list[float]]]:
    path = C1 / "c1_canonical_geometry.jsonl"
    result: dict[str, list[list[float]]] = {}
    if not path.is_file():
        return result
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            key = clean(row.get("canonical_annotation_id") or row.get("annotation_id"))
            points = geometry_points(row.get("corners_px") or row.get("geometry"))
            if key and points:
                result[key] = points
    return result


def load_stage_table(stage: str, path: Path, *, c1_geometry: dict[str, list[list[float]]] | None = None) -> pd.DataFrame:
    frame = read_csv(path)
    if frame.empty:
        return frame
    output = pd.DataFrame(index=frame.index)
    output["stage"] = stage
    output["record_role"] = "stage_canonical"
    output["project_id"] = choose_series(frame, ["project_id", "project"])
    output["runtime_task_id"] = choose_series(frame, ["runtime_task_id", "ls_runtime_task_id", "task_runtime_id"])
    output["task_id"] = choose_series(frame, ["task_id", "planned_task_id", "task_data_task_id"])
    raw_base = choose_series(frame, ["base_task_id", "planned_task_id", "task_label", "image_id", "task_id"])
    output["base_task_id"] = raw_base.map(strip_image_name)
    explicit_building = choose_series(frame, ["building_id"])
    output["building_id"] = [clean(explicit) or building_from_base(base) for explicit, base in zip(explicit_building, output["base_task_id"])]
    output["condition"] = choose_series(frame, ["condition", "mode", "annotation_mode"]).map(normalise_condition)
    output["worker_id"] = choose_series(frame, ["worker_id", "annotator_id", "completed_by"]).map(worker_id)
    output["annotation_id"] = choose_series(frame, ["annotation_id", "raw_annotation_id"])
    output["canonical_annotation_id"] = choose_series(frame, ["canonical_annotation_id", "annotation_version_id", "annotation_id"])
    output["assignment_provenance"] = choose_series(frame, ["assignment_provenance"], "not_recorded")
    output["dataset_group"] = choose_series(frame, ["dataset_group", "task_stratum", "round_id"])
    output["language_group"] = choose_series(frame, ["language_group", "upstream_language_group"])
    output["formal_use_allowed"] = choose_series(frame, ["formal_use_allowed", "eligible_for_primary_analysis", "formal_assignment_eligible"], "")
    output["canonical_valid_source"] = choose_series(frame, ["canonical_valid", "eligible_for_primary_analysis", "geometry_calculation_eligible"], "")
    output["parse_error"] = choose_series(frame, ["parse_error", "geometry_parse_status"], "")
    output["n_corners_source"] = choose_series(frame, ["n_corners", "corner_count", "repaired_point_count", "raw_point_count"], "")
    geometry_source = choose_series(frame, ["ordered_geometry", "canonical_geometry", "corners_px", "geometry"])
    geometries = [geometry_points(value) for value in geometry_source]
    if stage == "C1" and c1_geometry:
        geometries = [
            points or c1_geometry.get(clean(annotation), [])
            for points, annotation in zip(geometries, output["canonical_annotation_id"])
        ]
    output["geometry_points_json"] = [json.dumps(points, separators=(",", ":")) if points else "" for points in geometries]
    output["geometry_computable"] = [valid_point_ring(points) for points in geometries]
    output["n_corners"] = [len(points) if points else (integer(source) or 0) for points, source in zip(geometries, output["n_corners_source"])]
    output["topology_signature"] = [f"n_points:{value}" if value and value % 2 == 0 else "not_computable" for value in output["n_corners"]]

    output["active_time_observed_seconds"] = pd.to_numeric(
        choose_series(frame, ["active_time", "active_time_seconds", "task_worker_active_seconds"]), errors="coerce"
    )
    output["active_time_formal_eligible"] = choose_series(
        frame, ["primary_active_time_eligible", "task_worker_time_analysis_eligible", "eligible_for_active_time"], ""
    ).map(truth)
    output["active_time_source"] = choose_series(frame, ["active_time_source", "time_basis", "timing_rule_version"])
    output["active_time_source_file"] = choose_series(frame, ["active_time_source_file"])
    output["active_time_event_count"] = pd.to_numeric(choose_series(frame, ["active_time_event_count", "raw_event_count"]), errors="coerce")
    output["active_time_session_count"] = pd.to_numeric(choose_series(frame, ["active_time_session_count", "session_count"]), errors="coerce")
    output["timing_status"] = choose_series(frame, ["timing_status", "active_time_match_status", "active_time_integrity_status"])
    output["lead_time_seconds"] = pd.to_numeric(
        choose_series(frame, ["lead_time_seconds", "annotation_lead_time_seconds", "lead_time"]), errors="coerce"
    )
    output["source_artifact"] = path.relative_to(ROOT).as_posix()
    output["source_sha256"] = sha256_file(path)
    output["source_row_index"] = np.arange(1, len(output) + 1)
    return output.reset_index(drop=True)


def load_unified_stage_submissions() -> pd.DataFrame:
    c1_geometry = load_c1_geometry_map()
    frames = [load_stage_table(stage, path, c1_geometry=c1_geometry) for stage, path in STAGE_SOURCES]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True, sort=False)

    # C1 active time is replaced by the formal task-worker materialisation.
    c1_time = read_csv(V2 / "ACTIVE_TIME_TASK_WORKER.csv")
    if not c1_time.empty:
        for column in ("project_id", "runtime_task_id", "worker_id"):
            c1_time[column] = c1_time[column].map(worker_id if column == "worker_id" else clean)
        c1_time["task_worker_active_seconds"] = pd.to_numeric(c1_time["task_worker_active_seconds"], errors="coerce")
        c1_time["task_worker_time_analysis_eligible"] = c1_time["task_worker_time_analysis_eligible"].map(truth)
        keys = ["project_id", "runtime_task_id", "worker_id"]
        selected = c1_time[keys + ["task_worker_active_seconds", "task_worker_time_analysis_eligible", "timing_rule_version", "timing_status", "raw_event_count", "session_count"]].drop_duplicates(keys)
        mask = combined["stage"].eq("C1")
        c1_rows = combined.loc[mask].merge(selected, how="left", on=keys, suffixes=("", "_formal"))
        c1_rows["active_time_observed_seconds"] = c1_rows["task_worker_active_seconds"]
        c1_rows["active_time_formal_eligible"] = c1_rows["task_worker_time_analysis_eligible"].fillna(False)
        c1_rows["active_time_source"] = c1_rows["timing_rule_version"].fillna("")
        c1_rows["timing_status"] = c1_rows["timing_status_formal"].fillna(c1_rows["timing_status"])
        c1_rows["active_time_event_count"] = pd.to_numeric(c1_rows["raw_event_count"], errors="coerce")
        c1_rows["active_time_session_count"] = pd.to_numeric(c1_rows["session_count"], errors="coerce")
        drop = ["task_worker_active_seconds", "task_worker_time_analysis_eligible", "timing_rule_version", "timing_status_formal", "raw_event_count", "session_count"]
        c1_rows = c1_rows.drop(columns=[column for column in drop if column in c1_rows])
        combined = pd.concat([combined.loc[~mask], c1_rows], ignore_index=True, sort=False)

    # Append C1 auditable geometry records not present in the canonical stage table.
    inclusion = read_csv(V2 / "ROW_INCLUSION_CLASSIFICATION.csv")
    if not inclusion.empty:
        existing = set(combined.loc[combined["stage"].eq("C1"), "canonical_annotation_id"].map(clean))
        extra = inclusion[~inclusion["canonical_annotation_id"].map(clean).isin(existing)].copy()
        if not extra.empty:
            add = pd.DataFrame()
            add["stage"] = "C1"
            add["record_role"] = "c1_auditable_noncanonical_or_raw_only"
            for target, names in {
                "project_id": ["project_id"], "runtime_task_id": ["ls_runtime_task_id"], "task_id": ["task_id"],
                "base_task_id": ["base_task_id"], "building_id": ["building_id"], "condition": ["condition"],
                "worker_id": ["worker_id"], "annotation_id": ["annotation_id"], "canonical_annotation_id": ["canonical_annotation_id"],
                "assignment_provenance": ["assignment_provenance"], "dataset_group": ["dataset_group"],
            }.items():
                add[target] = choose_series(extra, names)
            add["worker_id"] = add["worker_id"].map(worker_id)
            add["condition"] = add["condition"].map(normalise_condition)
            add["formal_use_allowed"] = choose_series(extra, ["formal_use_allowed"])
            add["canonical_valid_source"] = choose_series(extra, ["canonical_eligible"])
            add["parse_error"] = ""
            add["n_corners"] = pd.to_numeric(choose_series(extra, ["repaired_point_count", "raw_point_count"]), errors="coerce").fillna(0).astype(int)
            add["geometry_points_json"] = ""
            add["geometry_computable"] = extra["geometry_normalization_valid"].map(truth)
            add["topology_signature"] = add["n_corners"].map(lambda value: f"n_points:{value}" if value and value % 2 == 0 else "not_computable")
            add["active_time_observed_seconds"] = pd.to_numeric(extra["task_worker_active_seconds"], errors="coerce")
            add["active_time_formal_eligible"] = extra["task_worker_time_analysis_eligible"].map(truth)
            add["active_time_source"] = "c1_task_worker_active_time_v1"
            add["active_time_source_file"] = ""
            add["active_time_event_count"] = np.nan
            add["active_time_session_count"] = np.nan
            add["timing_status"] = choose_series(extra, ["timing_status"])
            add["lead_time_seconds"] = np.nan
            add["source_artifact"] = (V2 / "ROW_INCLUSION_CLASSIFICATION.csv").relative_to(ROOT).as_posix()
            add["source_sha256"] = sha256_file(V2 / "ROW_INCLUSION_CLASSIFICATION.csv")
            add["source_row_index"] = np.arange(1, len(add) + 1)
            combined = pd.concat([combined, add], ignore_index=True, sort=False)

    combined["active_time_computable"] = pd.to_numeric(combined["active_time_observed_seconds"], errors="coerce").notna()
    combined["lead_time_computable"] = pd.to_numeric(combined["lead_time_seconds"], errors="coerce").notna()
    combined["data_mining_included"] = True
    combined["worker_status_class"] = combined["worker_id"].map(
        lambda value: "administrative_exclusion" if value == "14" else "historical_retained" if value in {"18", "27"} else "observed_worker"
    )
    return combined


def load_raw_annotation_fact() -> pd.DataFrame:
    path = PACKAGE / "raw_annotation_fact.csv"
    frame = read_csv(path)
    if frame.empty:
        return frame
    for column in ("stage", "project_id", "ls_runtime_task_id", "annotation_id", "canonical_annotation_id", "base_task_id", "condition", "worker_id"):
        if column not in frame:
            frame[column] = ""
    frame["stage"] = frame["stage"].map(clean)
    frame["worker_id"] = frame["worker_id"].map(worker_id)
    frame["condition"] = frame["condition"].map(normalise_condition)
    frame["base_task_id"] = frame["base_task_id"].map(strip_image_name)
    frame["image_reference"] = frame.get("task_data_json", pd.Series([""] * len(frame))).map(extract_image_reference)
    frame["lead_time_seconds"] = pd.to_numeric(frame.get("lead_time_seconds", pd.Series([np.nan] * len(frame))), errors="coerce")
    frame["source_artifact"] = path.relative_to(ROOT).as_posix()
    return frame


def manifest_for_directory(output: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(item for item in output.rglob("*") if item.is_file() and item.name != "OUTPUT_MANIFEST.csv"):
        rows.append({"path": path.relative_to(output).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return pd.DataFrame(rows)
