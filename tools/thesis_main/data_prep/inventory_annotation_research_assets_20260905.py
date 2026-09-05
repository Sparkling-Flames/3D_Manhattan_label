"""盘点标注不确定性研究资产，不修改任何输入真源。"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "analysis_results/annotation_research_decision_audit_20260905_v1/inventory"
PRESCREEN = ROOT / "analysis_results/annotation_uncertainty_prescreen_20260903_v1"
BI_ROOT = Path(r"D:/Work/Manhattan_3D/Bi_layout/exports/mp3d_dual_predictions")

TARGET_PACKAGES = (
    "uncertainty_substrate_20260823_v1",
    "full_uncertainty_data_mining_20260821_v5",
    "historical_uncertainty_recompute_20260829_v1",
    "rq1_corrections_20260826",
    "rq1_raw_recompute_20260826",
    "rq1_stratified_uncertainty_20260827_v1",
    "worker_manual_strata_audit_20260904_v1",
    "worker_behavior_mixture_exploratory_20260904_v1",
    "manual_semi_correctness_oos_20260823",
    "annotation_uncertainty_prescreen_20260903_v1",
)
OLD_REVIEW_PACKAGES = (
    "annotation_uncertainty_batch1_broad_review_20260828_v1",
    "annotation_uncertainty_batch1_candidate_review_20260827_v2",
    "annotation_uncertainty_batch1_supplement_review_20260828_v1",
)

PACKAGE_ROLES = {
    "uncertainty_substrate_20260823_v1": "不确定性事实底座；支持性数据，不是原始真源",
    "full_uncertainty_data_mining_20260821_v5": "全量派生数据整理；支持性/探索性输出",
    "historical_uncertainty_recompute_20260829_v1": "历史复算讨论包；支持性输出",
    "rq1_corrections_20260826": "RQ1 修正与边界审计；支持性输出",
    "rq1_raw_recompute_20260826": "RQ1 raw 复算；42 高密图成员来源",
    "rq1_stratified_uncertainty_20260827_v1": "RQ1 分层探索性分析；支持性输出",
    "worker_manual_strata_audit_20260904_v1": "worker strata 探索性审计；不支持离散 taxonomy",
    "worker_behavior_mixture_exploratory_20260904_v1": "worker mixture 探索性 replay；非正式 taxonomy",
    "manual_semi_correctness_oos_20260823": "Manual/Semi 与 OOS 探索性审计；不改 T1",
    "annotation_uncertainty_prescreen_20260903_v1": "prescreen 机器/人工记录；成员当前可读但未冻结",
    **{
        name: "旧研究者候选审图包；仅作重叠记录，非当前池"
        for name in OLD_REVIEW_PACKAGES
    },
}

REF_PREFIXES = (
    "analysis_results/",
    "data/",
    "export_label/",
    "import_json/",
    "active_logs/",
    "output/",
    "docs/",
    "tools/",
    "tests/",
)
REPO_REF_RE = re.compile(
    r"(?<![A-Za-z0-9:/\\])((?:analysis_results|data|export_label|import_json|active_logs|output|docs|tools|tests)[/\\][^\"'<>|`\s,;、]*)"
)
ABS_REF_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]:[/\\][^\"'<>|`\s,;、]+)")
REMOTE_URL_RE = re.compile(r"https?://[^\"'<>|`\s,;、]+", re.IGNORECASE)
REFERENCE_SUFFIX_RE = re.compile(r"^(?P<path>.+?\.(?:csv|json|jsonl|xlsx|xls|py|md|txt|ndjson|yaml|yml))(?P<suffix>::?[^/\\\s]+|#[0-9]+)$", re.IGNORECASE)
TRAILING_REF_CHARS = ".:)]}>，。；、`"
STATUS_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:CURRENT|SUPPORTING|SUPERSEDED|FROZEN|NOT[_ -]?FROZEN|FORMAL|EXPLORATORY|HISTORICAL|LEGACY|"
    r"PASS_WITH_KNOWN_GAPS|NOT[_ -]?FORMAL|NOT[_ -]?EVALUABLE|DEGENERATE)(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
KEY_CANDIDATES = (
    ("image_id",),
    ("review_id",),
    ("task_cell_id",),
    ("high_density_task_id",),
    ("pano_id",),
    ("base_task_id",),
    ("task_id",),
    ("id",),
    ("source_path",),
    ("stage", "condition", "dataset_group", "base_task_id", "threshold"),
    ("stage", "condition", "dataset_group", "base_task_id"),
    ("threshold", "base_task_id"),
)
ROOM_REGION_IMAGE_KEYS = ("image_id", "pano_id", "panorama_id", "image_filename")
ROOM_REGION_VALUE_KEYS = ("room_id", "region_id", "room_name", "region_name")
ROOM_REGION_LOCAL_CHECKS = (
    "analysis_results/uncertainty_substrate_20260823_v1/image_registry.csv",
    "analysis_results/uncertainty_substrate_20260823_v1/task_context_master.csv",
    "analysis_results/uncertainty_substrate_20260823_v1/annotation_spine.csv",
    "analysis_results/annotation_uncertainty_prescreen_20260903_v1/machine_manifest.json",
    "analysis_results/annotation_uncertainty_prescreen_20260903_v1/human_review_export_20260905.json",
    "analysis_results/annotation_research_decision_audit_20260905_v1/review50/selected50_manifest.json",
)
ROOM_REGION_FILENAME_SEARCH_ROOTS = (
    "data",
    "D:/Work/Manhattan_3D/Bi_layout/dataset",
    "D:/Work/Manhattan_3D/Bi_layout/exports",
    "D:/Work/Manhattan_3D/mp3d_layout_gt_sources",
    "D:/Work/Manhattan_3D/data_hoho",
)
ROOM_REGION_FILENAME_PATTERNS = ("*.house", "*house_segmentations*", "*panorama_to_region*", "*region*", "*room*")
ROOM_REGION_FILENAME_CANDIDATES = (
    "D:/Work/Manhattan_3D/mp3d_layout_gt_sources/Matterport_official/tasks/region_classification/data/train_room_single_label.txt",
    "D:/Work/Manhattan_3D/mp3d_layout_gt_sources/Matterport_official/tasks/region_classification/data/train_room_single_image.txt",
    "D:/Work/Manhattan_3D/mp3d_layout_gt_sources/Matterport_official/tasks/region_classification/data/train_room_pano_label.txt",
    "D:/Work/Manhattan_3D/mp3d_layout_gt_sources/Matterport_official/tasks/region_classification/data/train_room_pano_image.txt",
    "D:/Work/Manhattan_3D/mp3d_layout_gt_sources/Matterport_official/tasks/region_classification/data/test_room_single_label.txt",
    "D:/Work/Manhattan_3D/mp3d_layout_gt_sources/Matterport_official/tasks/region_classification/data/test_room_single_image.txt",
    "D:/Work/Manhattan_3D/mp3d_layout_gt_sources/Matterport_official/tasks/region_classification/data/test_room_pano_label.txt",
    "D:/Work/Manhattan_3D/mp3d_layout_gt_sources/Matterport_official/tasks/region_classification/data/test_room_pano_image.txt",
)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def _clean_ref(value: str) -> str:
    return value.strip().strip("'\"`").rstrip(TRAILING_REF_CHARS)


def _is_repo_ref(value: str) -> bool:
    value = value.replace("\\", "/")
    return value.startswith(REF_PREFIXES)


def _find_refs(value: str) -> list[tuple[str, str]]:
    value = str(value).strip()
    found: list[tuple[str, str]] = []
    for match in REMOTE_URL_RE.findall(value):
        token = _clean_ref(match)
        if token and token not in {item[1] for item in found}:
            found.append(("remote_url", token))
    for match in ABS_REF_RE.findall(value) + REPO_REF_RE.findall(value):
        token = _clean_ref(match)
        if token and token not in {item[1] for item in found}:
            found.append(("absolute_path" if Path(token).drive else "repo_path", token))
    return found


def _split_reference_suffix(token: str) -> tuple[str, str]:
    token = _clean_ref(token)
    match = REFERENCE_SUFFIX_RE.match(token)
    if not match:
        return token, ""
    return match.group("path"), match.group("suffix").lstrip(":#")


def _resolve_ref(root: Path, raw: str, kind: str, consumer: Path) -> Path | None:
    if kind == "remote_url":
        return None
    path = Path(raw.replace("/", "\\")) if Path(raw).drive else Path(raw.replace("/", "\\"))
    if path.is_absolute():
        return path
    if _is_repo_ref(raw):
        return root / Path(raw.replace("/", "\\"))
    return (consumer.parent / path).resolve()


def _package_from_path(root: Path, path: Path | None, raw: str) -> str:
    if path is None:
        return "remote"
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        if str(path).replace("\\", "/").startswith(str(BI_ROOT).replace("\\", "/")):
            return "external:Bi_layout/mp3d_dual_predictions"
        return "external:" + str(path).replace("\\", "/")
    parts = rel.split("/")
    if parts and parts[0] == "analysis_results" and len(parts) > 1:
        return parts[1]
    return parts[0] if parts else "workspace"


def _walk_scalars(value: Any, path: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}" if path else str(key)
            if isinstance(item, str):
                yield child, item
            else:
                yield from _walk_scalars(item, child)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            child = f"{path}[{index}]"
            if isinstance(item, str):
                yield child, item
            else:
                yield from _walk_scalars(item, child)


def _declarations(path: Path) -> str:
    values: list[str] = []
    try:
        if path.suffix.lower() == ".json":
            payload = _json(path)
            for field, value in _walk_scalars(payload):
                if any(token in field.lower() for token in ("status", "role", "authority", "frozen", "contract", "eligibility")):
                    values.append(f"{field}={value}")
        elif path.suffix.lower() in {".md", ".txt"}:
            for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                if STATUS_RE.search(line):
                    values.append(line.strip())
    except Exception as exc:
        values.append(f"读取声明失败:{type(exc).__name__}")
    labels = []
    for value in values:
        labels.extend(match.group(0).upper().replace("-", "_").replace(" ", "_") for match in STATUS_RE.finditer(value))
    unique_labels = sorted(set(labels))
    details = " | ".join(dict.fromkeys(values))
    if len(details) > 800:
        details = details[:797] + "..."
    return ";".join(unique_labels) + (" :: " + details if details else "")


def _candidate_key(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, Any]:
    if not rows:
        return {"key_candidate": "", "key_status": "not_applicable", "duplicate_key_count": 0, "missing_key_value_count": 0}
    for candidate in KEY_CANDIDATES:
        if not set(candidate).issubset(fields):
            continue
        missing = sum(1 for row in rows if any(str(row.get(field, "")).strip() == "" for field in candidate))
        keys = [tuple(str(row.get(field, "")).strip() for field in candidate) for row in rows]
        counts = Counter(key for key in keys if all(key))
        duplicate = sum(count - 1 for count in counts.values() if count > 1)
        if missing == 0 and duplicate == 0:
            return {
                "key_candidate": "+".join(candidate),
                "key_status": "pass_unique" if len(candidate) == 1 else "pass_composite_unique",
                "duplicate_key_count": 0,
                "missing_key_value_count": 0,
            }
    available = next((candidate for candidate in KEY_CANDIDATES if set(candidate).issubset(fields)), ())
    if not available:
        return {"key_candidate": "", "key_status": "not_applicable", "duplicate_key_count": 0, "missing_key_value_count": 0}
    keys = [tuple(str(row.get(field, "")).strip() for field in available) for row in rows]
    counts = Counter(key for key in keys if all(key))
    return {
        "key_candidate": "+".join(available),
        "key_status": "review_required_not_unique",
        "duplicate_key_count": sum(count - 1 for count in counts.values() if count > 1),
        "missing_key_value_count": sum(1 for key in keys if not all(key)),
    }


def _csv_profile(path: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    fields: list[str] = []
    count = 0
    errors: list[str] = []
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            if header is None:
                errors.append("empty_csv")
            elif not header or any(not str(field).strip() for field in header):
                errors.append("empty_header_field")
            elif len(set(header)) != len(header):
                errors.append("duplicate_header_field")
            else:
                fields = [str(field) for field in header]
                for raw_row in reader:
                    if not raw_row:
                        continue
                    if len(raw_row) != len(fields):
                        errors.append(f"row_width:{count + 2}:{len(raw_row)}!={len(fields)}")
                        continue
                    count += 1
                    if len(rows) < 3:
                        rows.append(dict(zip(fields, raw_row)))
    except Exception as exc:
        errors.append(f"{type(exc).__name__}:{exc}")
    key_rows = rows
    if count > len(rows) and fields:
        # 主键检查只需保留值；重新读取一次，避免把所有表行留在内存中。
        key_rows = []
        try:
            with path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                key_rows = [row for row in reader if row and any(str(value).strip() for value in row.values())]
        except Exception as exc:
            errors.append(f"key_read:{type(exc).__name__}:{exc}")
    result = {
        "format": "csv",
        "row_count": count,
        "fields": fields,
        "json_type": "",
        "sheet_names": "",
        "format_status": "pass" if not errors else "error",
        "format_errors": ";".join(errors),
    }
    result.update(_candidate_key(key_rows, fields))
    return result


def _json_rows(payload: Any) -> tuple[str, list[dict[str, Any]] | None]:
    if isinstance(payload, list):
        return "root", payload if all(isinstance(item, dict) for item in payload) else None
    if isinstance(payload, dict):
        for key in ("items", "records", "sources", "outputs", "assertions", "rows", "tasks"):
            value = payload.get(key)
            if isinstance(value, list) and all(isinstance(item, dict) for item in value):
                return key, value
    return "", None


def _json_profile(path: Path) -> dict[str, Any]:
    try:
        payload = _json(path)
        collection, rows = _json_rows(payload)
        fields = sorted({key for row in (rows or []) for key in row})
        result = {
            "format": "json",
            "row_count": len(rows) if rows is not None else "",
            "fields": fields,
            "json_type": type(payload).__name__ + (f"/{collection}" if collection else ""),
            "sheet_names": "",
            "format_status": "pass",
            "format_errors": "",
        }
        result.update(_candidate_key(rows or [], fields))
        return result
    except Exception as exc:
        return {
            "format": "json",
            "row_count": "",
            "fields": [],
            "json_type": "",
            "sheet_names": "",
            "format_status": "error",
            "format_errors": f"{type(exc).__name__}:{exc}",
            "key_candidate": "",
            "key_status": "not_applicable",
            "duplicate_key_count": 0,
            "missing_key_value_count": 0,
        }


def _jsonl_profile(path: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    count = 0
    errors: list[str] = []
    try:
        with path.open(encoding="utf-8-sig") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except Exception as exc:
                    errors.append(f"line_{line_number}:{type(exc).__name__}")
                    continue
                if not isinstance(value, dict):
                    errors.append(f"line_{line_number}:not_object")
                    continue
                count += 1
                if len(rows) < 3:
                    rows.append(value)
    except Exception as exc:
        errors.append(f"{type(exc).__name__}:{exc}")
    fields = sorted({key for row in rows for key in row})
    result = {
        "format": "jsonl",
        "row_count": count,
        "fields": fields,
        "json_type": "jsonl",
        "sheet_names": "",
        "format_status": "pass" if not errors else "error",
        "format_errors": ";".join(errors),
    }
    result.update(_candidate_key(rows, fields))
    return result


def _xlsx_profile(path: Path) -> dict[str, Any]:
    names: list[str] = []
    rows: list[str] = []
    errors: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
            ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            names = [item.attrib.get("name", "") for item in workbook.findall("x:sheets/x:sheet", ns)]
            for name in sorted(item for item in archive.namelist() if item.startswith("xl/worksheets/") and item.endswith(".xml")):
                root = ElementTree.fromstring(archive.read(name))
                rows.append(f"{name.rsplit('/', 1)[-1]}:{len(root.findall('x:sheetData/x:row', ns))}")
    except Exception as exc:
        errors.append(f"{type(exc).__name__}:{exc}")
    return {
        "format": "xlsx",
        "row_count": "",
        "fields": [],
        "json_type": "",
        "sheet_names": ";".join(names),
        "sheet_row_counts": ";".join(rows),
        "format_status": "pass" if not errors else "error",
        "format_errors": ";".join(errors),
        "key_candidate": "",
        "key_status": "not_applicable",
        "duplicate_key_count": 0,
        "missing_key_value_count": 0,
    }


def _profile(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "format": path.suffix.lower().lstrip("."),
            "row_count": "",
            "fields": [],
            "json_type": "",
            "sheet_names": "",
            "sheet_row_counts": "",
            "format_status": "missing",
            "format_errors": "missing_file",
            "key_candidate": "",
            "key_status": "not_applicable",
            "duplicate_key_count": 0,
            "missing_key_value_count": 0,
        }
    suffix = path.suffix.lower()
    if suffix == ".csv":
        result = _csv_profile(path)
    elif suffix == ".json":
        result = _json_profile(path)
    elif suffix == ".jsonl":
        result = _jsonl_profile(path)
    elif suffix == ".xlsx":
        result = _xlsx_profile(path)
    else:
        result = {
            "format": suffix.lstrip("."),
            "row_count": "",
            "fields": [],
            "json_type": "",
            "sheet_names": "",
            "sheet_row_counts": "",
            "format_status": "not_applicable",
            "format_errors": "",
            "key_candidate": "",
            "key_status": "not_applicable",
            "duplicate_key_count": 0,
            "missing_key_value_count": 0,
        }
    result.setdefault("sheet_row_counts", "")
    return result


def _file_role(package: str, path: Path) -> str:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if name in {"readme.md", "readme_先看这里.md"} or "report" in name or "brief" in name:
        return "说明/边界声明"
    if "manifest" in name or "inventory" in name or "validation" in name or name.startswith("qa"):
        return "manifest/QA/来源声明"
    if suffix in {".csv", ".jsonl"}:
        return "数据表"
    if suffix == ".json":
        return "JSON 数据或元数据"
    if suffix == ".xlsx":
        return "工作簿"
    if suffix in {".png", ".jpg", ".jpeg"}:
        return "预览/图表"
    return "其他资产"


def _package_files(root: Path, package: str) -> Iterable[Path]:
    folder = root / "analysis_results" / package
    if folder.is_dir():
        yield from sorted(path for path in folder.rglob("*") if path.is_file())


def _source_strings(path: Path) -> Iterable[tuple[str, str]]:
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            yield from _walk_scalars(_json(path))
        elif suffix == ".csv":
            with path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    for field, value in row.items():
                        if value:
                            yield field, value
        elif suffix == ".jsonl":
            with path.open(encoding="utf-8-sig") as handle:
                for line_number, line in enumerate(handle, 1):
                    if line.strip():
                        try:
                            yield from _walk_scalars(json.loads(line), f"line[{line_number}]")
                        except json.JSONDecodeError:
                            continue
        elif suffix in {".md", ".txt"}:
            yield "text", path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        return


def _reference_rows(root: Path, packages: Iterable[str]) -> list[dict[str, Any]]:
    rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    for package in packages:
        for path in _package_files(root, package):
            if path.suffix.lower() not in {".json", ".csv", ".jsonl", ".md", ".txt"}:
                continue
            consumer = _rel(root, path)
            for context, value in _source_strings(path):
                for kind, token in _find_refs(value):
                    physical_token, field_reference = _split_reference_suffix(token)
                    resolved = _resolve_ref(root, physical_token, kind, path)
                    if kind == "remote_url":
                        status = "remote_url_not_local_checked"
                        resolved_text = ""
                    else:
                        exists = bool(resolved and (resolved.is_file() or resolved.is_dir()))
                        status = "exists" if exists else "missing"
                        if resolved and not resolved.is_file() and not resolved.is_dir():
                            status = "missing_historical_or_temp_path" if "analysis_results" in physical_token else "missing"
                        resolved_text = _rel(root, resolved) if resolved else ""
                    key = (consumer, context, token)
                    rows[key] = {
                        "consumer_package": package,
                        "consumer_file": consumer,
                        "consumer_context": context,
                        "reference_kind": kind,
                        "reference_text": token,
                        "physical_reference_path": physical_token,
                        "reference_field": field_reference,
                        "resolved_path": resolved_text,
                        "resolved_package": _package_from_path(root, resolved, physical_token),
                        "existence_status": status,
                        "consumer_role": _file_role(package, path),
                    }
    return sorted(rows.values(), key=lambda row: (row["consumer_package"], row["consumer_file"], row["reference_text"], row["consumer_context"]))


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _parse_points(path: Path) -> tuple[bool, str, int]:
    try:
        points = []
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            values = line.split()
            if not values:
                continue
            if len(values) != 2:
                return False, "not_two_columns", len(points)
            numbers = [float(value) for value in values]
            if not all(math.isfinite(value) for value in numbers):
                return False, "nan_or_inf", len(points)
            points.append(numbers)
        if len(points) < 4 or len(points) % 2:
            return False, "point_count_not_even_ge4", len(points)
        for first, second in zip(points[::2], points[1::2]):
            dx = min(abs(first[0] - second[0]), 1024.0 - abs(first[0] - second[0]))
            if dx > 1.0 or abs(first[1] - second[1]) < 1.0:
                return False, "invalid_ceiling_floor_pair", len(points)
        return True, "ok", len(points)
    except Exception as exc:
        return False, type(exc).__name__, 0


def _manual_gt_map(path: Path) -> dict[str, tuple[bool, str, int]]:
    result: dict[str, tuple[bool, str, int]] = {}
    try:
        payload = _json(path)
        for task in payload:
            title = str((task.get("data") or {}).get("title", ""))
            image_id = Path(title).stem
            annotations = task.get("annotations") or []
            points = []
            if len(annotations) == 1:
                for item in annotations[0].get("result") or []:
                    if item.get("type") != "keypointlabels":
                        continue
                    value = item.get("value") or {}
                    points.append([float(value["x"]) * 10.24, float(value["y"]) * 5.12])
            if not image_id or image_id in result:
                result[image_id] = (False, "duplicate_or_empty_image_id", len(points))
            elif len(points) < 4 or len(points) % 2:
                result[image_id] = (False, "point_count_not_even_ge4", len(points))
            else:
                result[image_id] = (True, "ok", len(points))
    except Exception:
        return {}
    return result


def _asset(path: Path, kind: str, image_id: str, manual_map: dict[str, tuple[bool, str, int]] | None = None) -> dict[str, Any]:
    if not path.is_file():
        return {"status": "missing", "reason": "missing_file", "points": ""}
    if kind == "image":
        try:
            signature = path.read_bytes()[:8]
            if signature.startswith(b"\x89PNG") or signature[:2] == b"\xff\xd8":
                return {"status": "valid", "reason": "known_image_signature", "points": ""}
            return {"status": "degraded", "reason": "unknown_image_signature", "points": ""}
        except Exception as exc:
            return {"status": "degraded", "reason": type(exc).__name__, "points": ""}
    if kind == "manual_json":
        ok, reason, points = (manual_map or {}).get(image_id, (False, "image_id_not_found", 0))
        return {"status": "valid" if ok else "degraded", "reason": reason, "points": points}
    if kind in {"points", "bi_corners"}:
        ok, reason, points = _parse_points(path)
        return {"status": "valid" if ok else "degraded", "reason": reason, "points": points}
    if kind == "bi_floor_uv":
        try:
            rows = [line.split() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
            valid = bool(rows) and all(len(row) == 2 and all(math.isfinite(float(value)) for value in row) for row in rows)
            return {"status": "valid" if valid else "degraded", "reason": "ok" if valid else "invalid_uv", "points": len(rows)}
        except Exception as exc:
            return {"status": "degraded", "reason": type(exc).__name__, "points": 0}
    if kind == "model_json":
        try:
            payload = _json(path)
            corners = ((payload.get("layout") or {}).get("corners") or []) if isinstance(payload, dict) else []
            filename = Path(str(payload.get("image_filename", ""))).stem
            valid = filename == image_id and isinstance(corners, list) and len(corners) >= 3 and all(
                all(math.isfinite(float(item[field])) for field in ("x", "y_ceiling", "y_floor")) for item in corners
            )
            return {"status": "valid" if valid else "degraded", "reason": "ok" if valid else "invalid_layout_json", "points": len(corners)}
        except Exception as exc:
            return {"status": "degraded", "reason": type(exc).__name__, "points": 0}
    return {"status": "valid", "reason": "file_present", "points": ""}


def _bi_manifests() -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    by_id: dict[str, dict[str, str]] = {}
    summary: dict[str, Any] = {}
    for split, expected in (("test", 458), ("val", 190)):
        path = BI_ROOT / split / "manifest.csv"
        rows = _read_csv_rows(path) if path.is_file() else []
        summary[split] = {
            "path": str(path).replace("\\", "/"),
            "expected_rows": expected,
            "rows": len(rows),
            "unique_pano_id": len({row.get("pano_id", "") for row in rows}),
            "status_counts": dict(Counter(row.get("status", "") for row in rows)),
        }
        for row in rows:
            by_id[row["pano_id"]] = row
    return by_id, summary


def _bi_assets(image_id: str, row: dict[str, str] | None) -> dict[str, Any]:
    result: dict[str, Any] = {"bi_split": "", "bi_manifest_status": "missing", "bi_extended_status": "missing", "bi_enclosed_status": "missing"}
    if not row:
        return result
    split = row["split"]
    result.update({"bi_split": split, "bi_manifest_status": row.get("status", "")})
    for branch in ("extended", "enclosed"):
        corner_path = BI_ROOT / row[f"{branch}_corners_px_path"]
        floor_path = BI_ROOT / row[f"{branch}_floor_uv_path"]
        corner = _asset(corner_path, "bi_corners", image_id)
        floor = _asset(floor_path, "bi_floor_uv", image_id)
        manifest_ok = row.get("status") == "ok" and str(row.get(f"{branch}_is_polygon", "")).lower() == "true" and int(row.get(f"{branch}_corner_count", "0")) >= 3
        result[f"bi_{branch}_status"] = "valid" if manifest_ok and corner["status"] == "valid" and floor["status"] == "valid" else "degenerate"
        result[f"bi_{branch}_reason"] = "ok" if result[f"bi_{branch}_status"] == "valid" else f"manifest={row.get('status')};corner={corner['reason']};floor={floor['reason']}"
        result[f"bi_{branch}_corner_count"] = row.get(f"{branch}_corner_count", "")
        result[f"bi_{branch}_corner_path"] = str(corner_path).replace("\\", "/")
        result[f"bi_{branch}_floor_path"] = str(floor_path).replace("\\", "/")
    return result


def _prescreen_rows() -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, str]], dict[str, dict[str, str]]]:
    machine = _json(PRESCREEN / "machine_manifest.json")
    human = _json(PRESCREEN / "human_review_export_20260905.json")
    items = machine.get("items") or []
    reviews = human.get("items") or []
    machine_by_id = {item["image_id"]: item for item in items}
    review_by_id = {item["image_id"]: item for item in reviews}
    manual_map = _manual_gt_map(ROOT / "export_label/groudTruth.json")
    bi_by_id, bi_summary = _bi_manifests()
    rows: list[dict[str, Any]] = []
    for item in items:
        image_id = item["image_id"]
        assets = item.get("assets") or {}
        reference = assets.get("reference") or {}
        original = _asset(ROOT / assets["image"]["path"], "image", image_id)
        if reference.get("source_type") == "confirmed_user_manual_gt_correction":
            gt = _asset(ROOT / reference["path"], "manual_json", image_id, manual_map)
        else:
            gt = _asset(ROOT / reference["path"], "points", image_id)
        hohonet = _asset(ROOT / assets["model_txt"]["path"], "points", image_id)
        hohonet_json = _asset(ROOT / assets["model_json"]["path"], "model_json", image_id)
        review = review_by_id.get(image_id, {})
        review_data = review.get("review") or {}
        bi = _bi_assets(image_id, bi_by_id.get(image_id))
        layer = item.get("history_layer", "")
        pool = "historical_148" if layer == "historical_annotation_record_exists" else "no_history_166"
        if image_id in review_by_id:
            pool = "human_reviewed_30"
        issue_codes = []
        for name, value in (("original", original), ("gt", gt), ("hohonet", hohonet), ("hohonet_json", hohonet_json)):
            if value["status"] != "valid":
                issue_codes.append(f"{name}:{value['status']}:{value['reason']}")
        for branch in ("extended", "enclosed"):
            if bi[f"bi_{branch}_status"] != "valid":
                issue_codes.append(f"bi_{branch}:{bi[f'bi_{branch}_status']}")
        rows.append({
            "image_id": image_id,
            "building_id": item.get("building_id", image_id.split("_", 1)[0]),
            "machine_id": item.get("machine_id", ""),
            "history_layer": layer,
            "pool": pool,
            "review_id": review.get("review_id", ""),
            "human_scope_raw": review_data.get("scope", ""),
            "human_prelabel_verdict_raw": review_data.get("prelabel_verdict", ""),
            "human_notes_raw": review_data.get("notes", ""),
            "dense42": "false",
            "old214_registry": "false",
            "original_status": original["status"],
            "original_reason": original["reason"],
            "gt_status": gt["status"],
            "gt_reason": gt["reason"],
            "gt_source_type": reference.get("source_type", ""),
            "gt_point_count": gt["points"],
            "hohonet_txt_status": hohonet["status"],
            "hohonet_txt_reason": hohonet["reason"],
            "hohonet_point_count": hohonet["points"],
            "hohonet_json_status": hohonet_json["status"],
            "hohonet_json_reason": hohonet_json["reason"],
            "bi_manifest_status": bi["bi_manifest_status"],
            "bi_extended_status": bi["bi_extended_status"],
            "bi_extended_reason": bi.get("bi_extended_reason", ""),
            "bi_enclosed_status": bi["bi_enclosed_status"],
            "bi_enclosed_reason": bi.get("bi_enclosed_reason", ""),
            "bi_split": bi["bi_split"],
            "model_asset_issue_codes": ";".join(issue_codes),
            "asset_overall_status": "valid" if not issue_codes else "known_asset_issue",
            "image_path": assets.get("image", {}).get("path", ""),
            "gt_path": reference.get("path", ""),
            "hohonet_txt_path": assets.get("model_txt", {}).get("path", ""),
            "hohonet_json_path": assets.get("model_json", {}).get("path", ""),
        } | bi)
    review_ids = set(review_by_id)
    no_history_ids = {item["image_id"] for item in items if item.get("history_layer") == "no_existing_annotation_record"}
    remaining_ids = no_history_ids - review_ids
    summary = {
        "machine_items": len(items),
        "machine_unique_image_ids": len(machine_by_id),
        "history_existing": sum(item.get("history_layer") == "historical_annotation_record_exists" for item in items),
        "history_missing": sum(item.get("history_layer") == "no_existing_annotation_record" for item in items),
        "human_review_items": len(reviews),
        "human_unique_image_ids": len(review_by_id),
        "human_scope_counts": dict(Counter((item.get("review") or {}).get("scope", "") for item in reviews)),
        "remaining_candidate_ids": len(remaining_ids),
        "review_not_machine": sorted(review_ids - set(machine_by_id)),
        "review_not_no_history": sorted(review_ids - no_history_ids),
        "bi_manifest": bi_summary,
    }
    return rows, summary, reviews, machine_by_id


def _dense_rows(root: Path, prescreen: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], set[str], set[str]]:
    dense_path = root / "analysis_results/rq1_raw_recompute_20260826/high_density_task_metrics.csv"
    old_path = root / "analysis_results/uncertainty_substrate_20260823_v1/image_registry.csv"
    dense = _read_csv_rows(dense_path)
    old = _read_csv_rows(old_path)
    dense_ids = {row["base_task_id"] for row in dense}
    old_ids = {row["image_id"] for row in old}
    manual_map = _manual_gt_map(root / "export_label/groudTruth.json")
    bi_by_id, _ = _bi_manifests()
    rows: list[dict[str, Any]] = []
    for image_id in sorted(dense_ids):
        building_id = image_id.split("_", 1)[0]
        image_path = root / f"data/mp3d_layout/test/img/{image_id}.png"
        gt_path = root / f"data/mp3d_layout/test/label_cor/{image_id}.txt"
        if image_id in manual_map:
            gt = _asset(root / "export_label/groudTruth.json", "manual_json", image_id, manual_map)
            gt_ref = "export_label/groudTruth.json"
        else:
            gt = _asset(gt_path, "points", image_id)
            gt_ref = _rel(root, gt_path)
        hohonet_path = root / f"output/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34/{image_id}.txt"
        hohonet_json_path = root / f"output/layout_json/{image_id}.json"
        original = _asset(image_path, "image", image_id)
        hohonet = _asset(hohonet_path, "points", image_id)
        hohonet_json = _asset(hohonet_json_path, "model_json", image_id)
        bi = _bi_assets(image_id, bi_by_id.get(image_id))
        issues = []
        for name, value in (("original", original), ("gt", gt), ("hohonet", hohonet), ("hohonet_json", hohonet_json)):
            if value["status"] != "valid":
                issues.append(f"{name}:{value['status']}:{value['reason']}")
        for branch in ("extended", "enclosed"):
            if bi[f"bi_{branch}_status"] != "valid":
                issues.append(f"bi_{branch}:{bi[f'bi_{branch}_status']}")
        rows.append({
            "image_id": image_id,
            "building_id": building_id,
            "old214_registry": str(image_id in old_ids).lower(),
            "original_status": original["status"],
            "gt_status": gt["status"],
            "gt_reason": gt["reason"],
            "gt_path": gt_ref,
            "hohonet_txt_status": hohonet["status"],
            "hohonet_json_status": hohonet_json["status"],
            "bi_manifest_status": bi["bi_manifest_status"],
            "bi_extended_status": bi["bi_extended_status"],
            "bi_enclosed_status": bi["bi_enclosed_status"],
            "bi_split": bi["bi_split"],
            "model_asset_issue_codes": ";".join(issues),
            "asset_overall_status": "valid" if not issues else "known_asset_issue",
            "dense_source": _rel(root, dense_path),
        } | bi)
    return rows, dense_ids, old_ids


def _old_review_overlap(root: Path, remaining_ids: set[str], machine_by_id: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for package in OLD_REVIEW_PACKAGES:
        path = root / "analysis_results" / package / "candidate_manifest.json"
        if not path.is_file():
            continue
        payload = _json(path)
        for item in payload.get("items") or []:
            if item.get("image_id") not in remaining_ids:
                continue
            rows.append({
                "image_id": item["image_id"],
                "building_id": machine_by_id[item["image_id"]].get("building_id", ""),
                "current_pool": "candidate_remaining_136",
                "old_review_package": package,
                "old_manifest_path": _rel(root, path),
                "old_review_id": item.get("review_id", ""),
                "old_candidate_role": item.get("candidate_role", ""),
                "old_split": item.get("split", ""),
                "old_screen_stratum": item.get("screen_stratum", ""),
                "record_only_no_pool_change": "true",
            })
    return sorted(rows, key=lambda row: (row["image_id"], row["old_review_package"]))


def _structured_room_region_records(value: Any) -> tuple[list[tuple[str, str]], set[str]]:
    records: list[tuple[str, str]] = []
    fields: set[str] = set()

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            fields.update(str(key) for key in node)
            image = next((str(node[key]).strip() for key in ROOM_REGION_IMAGE_KEYS if str(node.get(key, "")).strip()), "")
            location = next((str(node[key]).strip() for key in ROOM_REGION_VALUE_KEYS if str(node.get(key, "")).strip()), "")
            if image and location:
                image = Path(image).stem if Path(image).suffix else image
                records.append((image, location))
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return records, fields


def _room_region_file_records(path: Path) -> tuple[list[tuple[str, str]], set[str], str]:
    if path.suffix.lower() == ".csv":
        rows = _read_csv_rows(path)
        fields = set(rows[0]) if rows else set()
        image_field = next((field for field in ROOM_REGION_IMAGE_KEYS if field in fields), "")
        location_field = next((field for field in ROOM_REGION_VALUE_KEYS if field in fields), "")
        if not image_field or not location_field:
            return [], fields, "no_explicit_image_room_region_columns"
        return [(str(row.get(image_field, "")).strip(), str(row.get(location_field, "")).strip()) for row in rows if row.get(image_field) and row.get(location_field)], fields, "ok"
    if path.suffix.lower() == ".json":
        records, fields = _structured_room_region_records(_json(path))
        return records, fields, "ok" if records else "no_structured_image_room_region_records"
    return [], set(), "unsupported_format"


def _aligned_pano_region_records(image_path: Path, label_path: Path) -> tuple[list[tuple[str, str]], str]:
    images = [line.strip() for line in image_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    labels = [line.strip() for line in label_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if len(images) != len(labels):
        return [], f"line_count_mismatch:{len(images)}!={len(labels)}"
    records = []
    for image, label in zip(images, labels):
        match = re.search(r"(?:^|/)data/mp_sb/([^/]+)/([^/]+)\.jpg$", image)
        if match and label:
            records.append((f"{match.group(1)}_{match.group(2)}", f"region_class:{label}"))
    return records, "aligned_pano_region_class" if records else "no_matching_pano_paths"


def _room_region_mapping_audit(
    root: Path,
    old_ids: set[str],
    dense_ids: set[str],
    remaining_ids: set[str],
    review_ids: set[str],
    selected_ids: set[str],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    paths = [root / relative for relative in ROOM_REGION_LOCAL_CHECKS]
    paths += [BI_ROOT / "test/manifest.csv", BI_ROOT / "val/manifest.csv"]
    paths += [Path(path) for path in ROOM_REGION_FILENAME_CANDIDATES]
    mappings: dict[str, set[str]] = defaultdict(set)
    source_by_id: dict[str, set[str]] = defaultdict(set)
    mapping_kind_by_id: dict[str, set[str]] = defaultdict(set)
    checked: list[str] = []
    missing: list[str] = []
    field_candidates: set[str] = set()
    file_status: list[dict[str, str]] = []
    for path in paths:
        display = _rel(root, path)
        if not path.is_file():
            missing.append(display)
            continue
        checked.append(display)
        if path.suffix.lower() in {".csv", ".json"}:
            try:
                records, fields, status = _room_region_file_records(path)
            except Exception as exc:
                records, fields, status = [], set(), f"read_error:{type(exc).__name__}"
        else:
            records, fields, status = [], set(), "filename_candidate_only"
        field_candidates.update(field for field in fields if field in ROOM_REGION_IMAGE_KEYS + ROOM_REGION_VALUE_KEYS)
        for image_id, location in records:
            if image_id and location:
                mappings[image_id].add(location)
                source_by_id[image_id].add(display)
                mapping_kind_by_id[image_id].add("structured_room_or_region")
        file_status.append({"path": display, "status": status, "record_count": str(len(records))})
    pano_image = Path(ROOM_REGION_FILENAME_CANDIDATES[-1])
    pano_label = Path(ROOM_REGION_FILENAME_CANDIDATES[-2])
    if pano_image.is_file() and pano_label.is_file():
        try:
            records, status = _aligned_pano_region_records(pano_image, pano_label)
        except Exception as exc:
            records, status = [], f"read_error:{type(exc).__name__}"
        pair_source = f"{_rel(root, pano_image)};{_rel(root, pano_label)}"
        field_candidates.add("aligned:pano_image+label")
        for image_id, location in records:
            mappings[image_id].add(location)
            source_by_id[image_id].add(pair_source)
            mapping_kind_by_id[image_id].add("region_class_only")
        file_status.append({"path": pair_source, "status": status, "record_count": str(len(records))})
    scopes = {
        "old_registry_214": old_ids,
        "high_density_42": dense_ids,
        "candidate_remaining_136": remaining_ids,
        "human_reviewed_30": review_ids,
        "selected50": selected_ids,
    }
    rows = []
    def scope_status(mapped: set[str]) -> str:
        if not mapped:
            return "no_matching_image_ids" if mappings else "not_found"
        kinds = {kind for image_id in mapped for kind in mapping_kind_by_id[image_id]}
        if kinds == {"region_class_only"}:
            return "found_region_class_only"
        if kinds == {"structured_room_or_region"}:
            return "found_structured_room_or_region"
        return "found_mixed"

    for scope, image_ids in scopes.items():
        mapped = image_ids & set(mappings)
        source_paths = sorted({path for image_id in mapped for path in source_by_id[image_id]})
        kinds = sorted({kind for image_id in mapped for kind in mapping_kind_by_id[image_id]})
        rows.append({
            "mapping_scope": scope,
            "image_count": len(image_ids),
            "mapped_image_count": len(mapped),
            "unmapped_image_count": len(image_ids - mapped),
            "unique_room_region_value_count": len({value for image_id in mapped for value in mappings[image_id]}),
            "mapping_status": scope_status(mapped),
            "mapping_kind": ";".join(kinds),
            "mapping_source_paths": ";".join(source_paths),
            "mapping_fields": ";".join(sorted(field_candidates)),
            "checked_paths": ";".join(checked),
            "missing_candidate_paths": ";".join(missing),
            "no_inference_from_visual_similarity": "true",
        })
    detail_rows = []
    target_ids = old_ids | dense_ids | remaining_ids | review_ids | selected_ids
    for image_id in sorted(target_ids & set(mappings)):
        values = sorted(mappings[image_id])
        kinds = sorted(mapping_kind_by_id[image_id])
        for value in values:
            detail_rows.append({
                "image_id": image_id,
                "building_id": image_id.split("_", 1)[0],
                "mapping_kind": ";".join(kinds),
                "room_region_value": value,
                "region_class": value.removeprefix("region_class:"),
                "mapping_conflict_count": len(values),
                "mapping_conflict_status": "conflict" if len(values) > 1 else "no_conflict",
                "mapping_source_paths": ";".join(sorted(source_by_id[image_id])),
                "source_is_instance_mapping": "false" if "region_class_only" in kinds and len(kinds) == 1 else "unknown",
            })
    meta = {
        "mapping_status": scope_status(set(mappings)) if mappings else "not_found",
        "checked_path_count": len(checked),
        "missing_candidate_path_count": len(missing),
        "mapping_record_count": sum(len(values) for values in mappings.values()),
        "mapping_image_count": len(mappings),
        "detail_rows": len(detail_rows),
        "mapping_kind_counts": dict(Counter(kind for kinds in mapping_kind_by_id.values() for kind in kinds)),
        "mapping_source_paths": sorted({path for paths_for_id in source_by_id.values() for path in paths_for_id}),
        "file_status": file_status,
        "policy": "仅接受结构化 image/pano 与 room/region 字段或明确行对齐的 pano→region_class；不从同楼栋或视觉相似性推断房间。",
        "search_scope": {
            "roots": list(ROOM_REGION_FILENAME_SEARCH_ROOTS),
            "patterns": list(ROOM_REGION_FILENAME_PATTERNS),
            "candidate_paths": list(ROOM_REGION_FILENAME_CANDIDATES),
            "interpretation": "这些有界检查来源未提供 room-instance/空间拓扑映射；其中 test_room_pano_* 提供数值 region class 对齐，不能替代 room-instance ID。",
        },
    }
    return rows, meta, detail_rows


def _model_asset_summary(root: Path) -> list[dict[str, Any]]:
    bi_by_id, bi_summary = _bi_manifests()
    test_ids = {image_id for image_id, row in bi_by_id.items() if row.get("split") == "test"}
    val_ids = {image_id for image_id, row in bi_by_id.items() if row.get("split") == "val"}
    hoho_txt_dir = root / "output/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34"
    hoho_json_dir = root / "output/layout_json"
    hoho_txt_ids = {path.stem for path in hoho_txt_dir.glob("*.txt")} if hoho_txt_dir.is_dir() else set()
    hoho_json_ids = {path.stem for path in hoho_json_dir.glob("*.json")} if hoho_json_dir.is_dir() else set()
    rows: list[dict[str, Any]] = []

    def add(model_family: str, asset_kind: str, split: str, source_path: str, observed: int | str, covered: int | str, status: str, notes: str) -> None:
        rows.append({
            "model_family": model_family,
            "asset_kind": asset_kind,
            "split": split,
            "source_path": source_path,
            "observed_count": observed,
            "coverage_count_against_known_split": covered,
            "status": status,
            "notes": notes,
            "dual_head_is_one_model": "true" if model_family == "Bi-Layout" else "",
        })

    replay_dirs = {
        "test": root / "analysis_results/model_initialization_test_ep300_replay_20260823_v1/prediction_txt",
        "val": root / "analysis_results/model_initialization_validation_ep300_replay_20260823_v1/prediction_txt",
    }
    for split, expected_ids in (("test", test_ids), ("val", val_ids)):
        replay_ids = {re.sub(r"\.layout$", "", path.stem) for path in replay_dirs[split].glob("*.layout.txt")} if replay_dirs[split].is_dir() else set()
        add("HoHoNet", "model_initialization_replay", split, _rel(root, replay_dirs[split]), len(replay_ids), len(replay_ids & expected_ids), "present" if replay_ids else "not_found", f"known Bi {split} denominator={len(expected_ids)}; split/训练数据仅按路径与现有 manifest 记录，不扩展解释")
    add("HoHoNet", "legacy_inference_txt", "test", _rel(root, hoho_txt_dir), len(hoho_txt_ids), len(hoho_txt_ids & test_ids), "present" if hoho_txt_ids else "not_found", f"历史 output 版本；JSON sibling count={len(hoho_json_ids)}")
    add("HoHoNet", "legacy_inference_json", "test", _rel(root, hoho_json_dir), len(hoho_json_ids), len(hoho_json_ids & test_ids), "present" if hoho_json_ids else "not_found", "历史 output 版本，不与 replay 版本合并")
    add("HoHoNet", "inference_outputs", "train", _rel(root, hoho_txt_dir), 0, 0, "not_found", "未找到独立 train 推理输出；不补推理")
    hoho_checkpoint = root / "ckpt/mp3d_layout_HOHO_layout_aug_efficienthc_Transen1_resnet34/ep300.pth"
    add("HoHoNet", "checkpoint", "mp3d", _rel(root, hoho_checkpoint), 1 if hoho_checkpoint.is_file() else 0, "", "present" if hoho_checkpoint.is_file() else "not_found", "已找到 ep300 checkpoint；未加载、未训练")
    for split, ids in (("test", test_ids), ("val", val_ids)):
        summary = bi_summary.get(split, {})
        add("Bi-Layout", "dual_head_prediction_manifest", split, summary.get("path", ""), summary.get("unique_pano_id", 0), len(ids), "present" if summary.get("rows") else "not_found", f"status_counts={json.dumps(summary.get('status_counts', {}), ensure_ascii=False)}; extended/enclosed 是同一模型的两个分支")
    add("Bi-Layout", "dual_head_prediction_manifest", "train", str((BI_ROOT / "train/manifest.csv")).replace("\\", "/"), 0, 0, "not_found", "未找到 train manifest；不从文件名推断训练数据覆盖")
    checkpoint = Path(r"D:/Work/Manhattan_3D/Bi_layout/checkpoints/Bi_Layout_Net/mp3d/mp3d_best_model.pkl")
    add("Bi-Layout", "weights", "mp3d", str(checkpoint).replace("\\", "/"), 1 if checkpoint.is_file() else 0, "", "present" if checkpoint.is_file() else "not_found", "已找到 checkpoint；未加载、未训练")
    bi_configs = [
        Path(r"D:/Work/Manhattan_3D/Bi_layout/src/config/other/horizon_net_mp3d.yaml"),
        Path(r"D:/Work/Manhattan_3D/Bi_layout/config/defaults.py"),
    ]
    existing_configs = [str(path).replace("\\", "/") for path in bi_configs if path.is_file()]
    add("Bi-Layout", "training_or_runtime_config", "mp3d", ";".join(existing_configs), len(existing_configs), "", "present" if existing_configs else "not_found", "仅确认配置文件存在；训练数据/split 未由文件名推断；不把 dual head 拆成两个独立模型")
    horizon_dependency = [
        Path(r"D:/Work/Manhattan_3D/Bi_layout/models/modules/horizon_net_feature_extractor.py"),
        Path(r"D:/Work/Manhattan_3D/Bi_layout/src/config/other/horizon_net_mp3d.yaml"),
        Path(r"D:/Work/Manhattan_3D/mp3d_layout_gt_sources/uLayout/lsun_pred_horizon.py"),
    ]
    existing_horizon = [str(path).replace("\\", "/") for path in horizon_dependency if path.is_file()]
    add("HorizonNet", "bounded_search", "all", ";".join(existing_horizon), len(existing_horizon), "", "dependency_only" if existing_horizon else "not_found", "仅找到实现/配置依赖；未找到独立推理输出或权重，覆盖未知，不下载不训练")
    return rows


def _coverage(root: Path, prescreen: list[dict[str, Any]], dense: list[dict[str, Any]], old: list[dict[str, str]]) -> list[dict[str, Any]]:
    old_counts = Counter(row["building_id"] for row in old)
    dense_counts = Counter(row["building_id"] for row in dense)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in prescreen:
        groups[row["building_id"]].append(row)
    buildings = sorted(set(old_counts) | set(dense_counts) | set(groups))
    result = []
    for building in buildings:
        rows = groups[building]
        reviewed = [row for row in rows if row["pool"] == "human_reviewed_30"]
        remaining = [row for row in rows if row["history_layer"] == "no_existing_annotation_record" and row["pool"] != "human_reviewed_30"]
        historical = [row for row in rows if row["history_layer"] == "historical_annotation_record_exists"]
        no_history = [row for row in rows if row["history_layer"] == "no_existing_annotation_record"]
        def count_status(field: str, status: str) -> int:
            return sum(row.get(field) == status for row in rows)
        result.append({
            "building_id": building,
            "old_registry_214_count": old_counts[building],
            "high_density_42_count": dense_counts[building],
            "prescreen_manifest_314_count": len(rows),
            "prescreen_no_history_166_count": len(no_history),
            "human_reviewed_30_count": len(reviewed),
            "human_in_scope_count": sum(row["human_scope_raw"] == "in_scope" for row in reviewed),
            "human_out_of_scope_count": sum(row["human_scope_raw"] == "out_of_scope" for row in reviewed),
            "candidate_remaining_136_count": len(remaining),
            "historical_annotation_record_148_count": len(historical),
            "no_existing_annotation_record_166_count": len(no_history),
            "original_missing_or_degraded_count": len(rows) - count_status("original_status", "valid"),
            "gt_missing_or_degraded_count": len(rows) - count_status("gt_status", "valid"),
            "hohonet_txt_missing_or_degraded_count": len(rows) - count_status("hohonet_txt_status", "valid"),
            "hohonet_json_missing_or_degraded_count": len(rows) - count_status("hohonet_json_status", "valid"),
            "bi_manifest_degenerate_or_missing_count": sum(row["bi_manifest_status"] != "ok" for row in rows),
            "bi_extended_degenerate_or_missing_count": len(rows) - count_status("bi_extended_status", "valid"),
            "bi_enclosed_degenerate_or_missing_count": len(rows) - count_status("bi_enclosed_status", "valid"),
            "any_asset_issue_count": sum(row["asset_overall_status"] != "valid" for row in rows),
        })
    return result


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str] | None = None) -> None:
    rows = list(rows)
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _catalog(root: Path, packages: list[str], refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    paths: dict[str, tuple[Path, str, str]] = {}
    for package in packages:
        for path in _package_files(root, package):
            paths[str(path.resolve()).lower()] = (path, package, "requested_package")
    for row in refs:
        if row["reference_kind"] == "remote_url" or not row["resolved_path"]:
            continue
        path = root / Path(row["resolved_path"]) if not Path(row["resolved_path"]).drive else Path(row["resolved_path"])
        package = row["resolved_package"]
        scope = "explicit_upstream_reference" if package not in packages else "requested_package"
        key = str(path).lower()
        if key not in paths:
            paths[key] = (path, package, scope)
    extras = [
        BI_ROOT / "test/manifest.csv",
        BI_ROOT / "test/run_metadata.json",
        BI_ROOT / "val/manifest.csv",
        BI_ROOT / "val/run_metadata.json",
        root / "data/mp3d_test.txt",
    ]
    for path in extras:
        paths.setdefault(str(path.resolve()).lower(), (path, _package_from_path(root, path, str(path)), "explicit_asset_source"))
    result = []
    for path, package, scope in sorted(paths.values(), key=lambda item: str(item[0]).lower()):
        profile = _profile(path)
        result.append({
            "package_id": package,
            "package_scope": scope,
            "package_role": PACKAGE_ROLES.get(package, "明确引用的上游文件"),
            "file_path": _rel(root, path),
            "file_exists": str(path.is_file()).lower(),
            "file_role": _file_role(package, path),
            "format": profile.get("format", ""),
            "size_bytes": path.stat().st_size if path.is_file() else "",
            "row_count": profile.get("row_count", ""),
            "field_count": len(profile.get("fields", [])),
            "fields": json.dumps(profile.get("fields", []), ensure_ascii=False),
            "json_type": profile.get("json_type", ""),
            "sheet_names": profile.get("sheet_names", ""),
            "sheet_row_counts": profile.get("sheet_row_counts", ""),
            "declared_status_or_role": _declarations(path) if path.is_file() else "missing_file",
            "format_status": profile.get("format_status", ""),
            "format_errors": profile.get("format_errors", ""),
            "key_candidate": profile.get("key_candidate", ""),
            "key_status": profile.get("key_status", ""),
            "duplicate_key_count": profile.get("duplicate_key_count", ""),
            "missing_key_value_count": profile.get("missing_key_value_count", ""),
        })
    return result


def _report(
    output: Path,
    prescreen_summary: dict[str, Any],
    dense_rows: list[dict[str, Any]],
    old_rows: list[dict[str, str]],
    coverage: list[dict[str, Any]],
    refs: list[dict[str, Any]],
    overlaps: list[dict[str, str]],
    room_rows: list[dict[str, Any]],
    model_assets: list[dict[str, Any]],
    catalog: list[dict[str, Any]],
    qa: dict[str, Any],
) -> None:
    package_summary = Counter(row["package_id"] for row in catalog)
    missing_refs = [row for row in refs if row["existence_status"].startswith("missing")]
    lines = [
        "# 标注研究决策审计：资产盘点与引用核对",
        "",
        "生成日期：2026-09-05。此目录只做重复性资产清点、键/格式/引用核对和逻辑归档，不做视觉判断、不改原始数据、不代定实验结论。",
        "",
        "## 关键计数",
        "",
        f"- machine manifest：{prescreen_summary['machine_items']} 条，唯一 image_id {prescreen_summary['machine_unique_image_ids']}；历史记录层 {prescreen_summary['history_existing']}，无现有 annotation 记录层 {prescreen_summary['history_missing']}。",
        f"- human review export：{prescreen_summary['human_review_items']} 条唯一记录；scope 原文计数为 `in_scope={prescreen_summary['human_scope_counts'].get('in_scope', 0)}`、`out_of_scope={prescreen_summary['human_scope_counts'].get('out_of_scope', 0)}`。",
        f"- 从无记录层扣除已审 30 条后，剩余候选池为 {prescreen_summary['remaining_candidate_ids']} 条；该池未因历史重叠或资产警告删减。",
        f"- 旧 image registry：{len(old_rows)} 条；42 高密图：{len(dense_rows)} 条，42 集合属于 registry：{qa['count_checks']['dense42_is_subset_of_old_registry']}；两集合完全相等：{qa['count_checks']['dense42_equals_old_registry_membership']}。",
        "",
        "## 数据包与状态声明",
        "",
        "`package_catalog.csv` 逐文件记录行数、字段、格式、主键候选、已出现的 status/role 声明和支持性角色。目录中的旧日期不作为作废依据；CURRENT/SUPPORTING/SUPERSEDED 只按文件中实际出现的声明记录，不替历史文件改名或升格。",
        "",
        "| package | 文件数 | 盘点角色 |",
        "|---|---:|---|",
    ]
    for package, count in sorted(package_summary.items()):
        lines.append(f"| `{package}` | {count} | {PACKAGE_ROLES.get(package, '明确引用的上游文件')} |")
    lines += [
        "",
        "## 人工 30 条的保留边界",
        "",
        "`human_review_export_20260905_raw.json` 与 `HUMAN_REVIEW_RECORD_20260905_raw.md` 是输入原文的字节复制。`prescreen_asset_audit.csv` 中的 `human_scope_raw`、`human_prelabel_verdict_raw`、`human_notes_raw` 仅作连接字段，未替换原文。缺少 `prelabel_verdict` 或 `reference_verdict` 不被解释为“无问题”；本批没有自动补写 reference 裁决。",
        "",
        "## 资产核对",
        "",
        "`prescreen_asset_audit.csv` 覆盖 314 条 machine manifest；`high_density_asset_audit.csv` 覆盖 42 条高密图。原图、GT、HoHoNet txt/JSON 和 Bi extended/enclosed 分支分别记录存在、可解析和退化状态。Bi 的 `degenerate` 是 manifest/分支资产事实，不是视觉判断。",
        "",
        "## 模型资产边界",
        "",
        f"`model_asset_summary.csv` 记录 HoHoNet、Bi-Layout 和 HorizonNet 的已有输出/权重/配置来源；当前只确认 HoHoNet test 输出与 Bi test/val manifest，HorizonNet 仅找到依赖实现/配置。Bi extended/enclosed 是一个模型的两个分支。",
        "",
        "## 历史审图包重叠",
        "",
        f"`candidate_historical_review_overlap.csv` 记录剩余 136 池与三个旧研究者候选审图包的 {len(overlaps)} 条 package-image 重叠记录；仅记录，不改变 136 池。",
        "",
        "## room/region 定位核查",
        "",
        "`room_region_mapping_audit.csv` 记录有界元数据搜索结果；`room_region_mapping_records.csv` 保留本次214/42/136/30/50并集的实际 image_id→region_class 连接、来源与冲突。数值 region class 不是 room-instance/空间拓扑 ID；本次不从同楼栋或视觉相似性推断房间。",
        "",
        "| pool | image 数 | 明确映射数 | 映射类型 | 状态 |",
        "|---|---:|---:|---|---|",
    ]
    for row in room_rows:
        lines.append(f"| `{row['mapping_scope']}` | {row['image_count']} | {row['mapped_image_count']} | `{row['mapping_kind']}` | `{row['mapping_status']}` |")
    lines += [
        "",
        "本次有界文件名搜索的根目录和模式保存在 `QA.json` 的 `room_region_mapping.search_scope`；结论仅适用于这些已检查来源。",
        "",
        "## 引用与缺口",
        "",
        f"`reference_link_audit.csv` 共 {len(refs)} 条去重后的消费者—引用记录，其中本地存在 {sum(row['existence_status'] == 'exists' for row in refs)} 条、远程 URL {sum(row['existence_status'] == 'remote_url_not_local_checked' for row in refs)} 条、缺失 {len(missing_refs)} 条。缺失的历史临时路径保留在审计表中，未修复。",
        "",
        "已知边界：",
        "",
        "- 按用户要求未做 SHA-256 核查；manifest 中的 SHA 只作为输入声明保留，不作为本次 QA 结论。",
        "- `Bi test` manifest 的 458 条中有 2 条状态为 `degenerate`；本次没有从 42 高密图或任何既定池删除它们。",
        "- 外部 `D:/Work/Manhattan_3D/Bi_layout/exports/mp3d_dual_predictions` 只读核对，不复制、不修改。",
        "- 本审计不判断 GT 谁对谁错，不把机器 prelabel 提示转换为人工结论。",
        "",
        "## QA",
        "",
        f"`QA.json` 状态：`{qa['status']}`；CSV/JSON/JSONL 格式检查 {qa['format_checks']['checked']} 个，格式错误 {len(qa['format_checks']['errors'])} 个。",
        "",
        "输出文件：`package_catalog.csv`、`reference_link_audit.csv`、`building_asset_coverage.csv`、`prescreen_asset_audit.csv`、`high_density_asset_audit.csv`、`candidate_historical_review_overlap.csv`、`room_region_mapping_audit.csv`、`room_region_mapping_records.csv`、`model_asset_summary.csv`、`QA.json`。",
    ]
    (output / "INVENTORY_REPORT_ZH.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(root: Path = ROOT, output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    prescreen_rows, prescreen_summary, reviews, machine_by_id = _prescreen_rows()
    dense_rows, dense_ids, old_ids = _dense_rows(root, prescreen_rows)
    old_rows = _read_csv_rows(root / "analysis_results/uncertainty_substrate_20260823_v1/image_registry.csv")
    review_ids = {item["image_id"] for item in reviews}
    remaining_ids = {row["image_id"] for row in prescreen_rows if row["history_layer"] == "no_existing_annotation_record"} - review_ids
    for row in prescreen_rows:
        row["dense42"] = str(row["image_id"] in dense_ids).lower()
        row["old214_registry"] = str(row["image_id"] in old_ids).lower()
        if row["pool"] == "no_history_166" and row["image_id"] not in review_ids:
            row["pool"] = "candidate_remaining_136"
    coverage = _coverage(root, prescreen_rows, dense_rows, old_rows)
    refs = _reference_rows(root, TARGET_PACKAGES + OLD_REVIEW_PACKAGES)
    # 外部 Bi manifest 的相对分支路径是重要消费者引用，单独登记其文件存在性。
    for split in ("test", "val"):
        manifest = BI_ROOT / split / "manifest.csv"
        for field in ("extended_floor_uv_path", "enclosed_floor_uv_path", "extended_corners_px_path", "enclosed_corners_px_path"):
            for row in _read_csv_rows(manifest) if manifest.is_file() else []:
                token = row.get(field, "")
                resolved = BI_ROOT / token
                refs.append({
                    "consumer_package": "external:Bi_layout/mp3d_dual_predictions",
                    "consumer_file": str(manifest).replace("\\", "/"),
                    "consumer_context": field,
                    "reference_kind": "external_relative_path",
                    "reference_text": token,
                    "resolved_path": str(resolved).replace("\\", "/"),
                    "resolved_package": "external:Bi_layout/mp3d_dual_predictions",
                    "existence_status": "exists" if resolved.is_file() else "missing",
                    "consumer_role": "Bi 双头模型 manifest",
                })
    ref_key = lambda row: (row["consumer_file"], row["consumer_context"], row["reference_text"])
    refs = sorted({ref_key(row): row for row in refs}.values(), key=lambda row: ref_key(row))
    overlaps = _old_review_overlap(root, remaining_ids, machine_by_id)
    selected_path = root / "analysis_results/annotation_research_decision_audit_20260905_v1/review50/selected50_manifest.json"
    selected_ids = {item.get("image_id", "") for item in (_json(selected_path).get("items") or [])} if selected_path.is_file() else set()
    room_rows, room_meta, room_detail_rows = _room_region_mapping_audit(root, old_ids, dense_ids, remaining_ids, review_ids, selected_ids)
    model_assets = _model_asset_summary(root)
    packages = list(TARGET_PACKAGES + OLD_REVIEW_PACKAGES)
    catalog = _catalog(root, packages, refs)
    catalog_by_key = {(row["file_path"], row["package_id"]): row for row in catalog}
    for path in (root / "analysis_results/uncertainty_substrate_20260823_v1/image_registry.csv", root / "analysis_results/rq1_raw_recompute_20260826/high_density_task_metrics.csv"):
        _ = catalog_by_key.get((_rel(root, path), _package_from_path(root, path, str(path))))
    format_rows = [row for row in catalog if row["format"] in {"csv", "json", "jsonl"} and row["file_exists"] == "true"]
    format_errors = [
        {"file_path": row["file_path"], "format_errors": row["format_errors"]}
        for row in format_rows
        if row["format_status"] == "error"
    ]
    missing_refs = [row for row in refs if row["existence_status"].startswith("missing")]
    qa = {
        "schema_version": "annotation_research_decision_audit_inventory_v1",
        "status": "pass_with_known_gaps" if not format_errors else "format_check_failed",
        "scope": {"requested_packages": list(TARGET_PACKAGES), "old_review_packages": list(OLD_REVIEW_PACKAGES), "sha_check": "not_run_by_user_request"},
        "count_checks": {
            "machine_manifest_items": prescreen_summary["machine_items"],
            "machine_manifest_unique_image_ids": prescreen_summary["machine_unique_image_ids"],
            "history_existing_148": prescreen_summary["history_existing"],
            "no_existing_annotation_166": prescreen_summary["history_missing"],
            "human_review_30": prescreen_summary["human_review_items"],
            "remaining_candidate_136": len(remaining_ids),
            "old_registry_214": len(old_rows),
            "dense42": len(dense_rows),
            "selected50": len(selected_ids),
            "dense42_is_subset_of_old_registry": dense_ids <= old_ids,
            "dense42_equals_old_registry_membership": dense_ids == old_ids,
            "review_ids_subset_machine": not prescreen_summary["review_not_machine"],
            "review_ids_subset_no_history": not prescreen_summary["review_not_no_history"],
            "bi_target_rows": sum(row["bi_split"] == "test" for row in prescreen_rows),
        },
        "human_scope_counts": prescreen_summary["human_scope_counts"],
        "bi_manifest": prescreen_summary["bi_manifest"],
        "asset_checks": {
            "prescreen_rows": len(prescreen_rows),
            "prescreen_asset_issue_rows": sum(row["asset_overall_status"] != "valid" for row in prescreen_rows),
            "high_density_rows": len(dense_rows),
            "high_density_asset_issue_rows": sum(row["asset_overall_status"] != "valid" for row in dense_rows),
            "high_density_issue_examples": [
                {"image_id": row["image_id"], "issues": row["model_asset_issue_codes"]}
                for row in dense_rows if row["model_asset_issue_codes"]
            ],
        },
        "format_checks": {"checked": len(format_rows), "errors": format_errors},
        "reference_checks": {
            "total_links": len(refs),
            "exists": sum(row["existence_status"] == "exists" for row in refs),
            "remote_url_not_local_checked": sum(row["existence_status"] == "remote_url_not_local_checked" for row in refs),
            "missing": len(missing_refs),
            "missing_examples": missing_refs[:50],
            "consumer_file_count": len({row["consumer_file"] for row in refs}),
        },
        "old_review_overlap": {"rows": len(overlaps), "unique_remaining_image_ids": len({row["image_id"] for row in overlaps}), "packages": list(OLD_REVIEW_PACKAGES)},
        "room_region_mapping": room_meta,
        "model_assets": {"rows": len(model_assets), "families": sorted({row["model_family"] for row in model_assets})},
        "known_gaps": [
            "未运行 SHA-256 核查；只保留声明字段。",
            "Bi test manifest 有 2 条 degenerate；保留并标记，不从既定池删除。",
            "缺失历史/临时引用未修复，见 reference_link_audit.csv。",
            "人工审阅缺少 reference_verdict 的记录未自动补值。",
            "HorizonNet 仅在有界搜索中找到依赖实现/配置；未确认独立权重或推理覆盖。",
        ],
    }
    _write_csv(output / "package_catalog.csv", catalog)
    _write_csv(output / "reference_link_audit.csv", refs)
    _write_csv(output / "building_asset_coverage.csv", coverage)
    _write_csv(output / "prescreen_asset_audit.csv", prescreen_rows)
    _write_csv(output / "high_density_asset_audit.csv", dense_rows)
    _write_csv(output / "candidate_historical_review_overlap.csv", overlaps)
    _write_csv(output / "room_region_mapping_audit.csv", room_rows)
    _write_csv(output / "room_region_mapping_records.csv", room_detail_rows)
    _write_csv(output / "model_asset_summary.csv", model_assets)
    (output / "QA.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(PRESCREEN / "human_review_export_20260905.json", output / "human_review_export_20260905_raw.json")
    shutil.copyfile(PRESCREEN / "HUMAN_REVIEW_RECORD_20260905.md", output / "HUMAN_REVIEW_RECORD_20260905_raw.md")
    _report(output, prescreen_summary, dense_rows, old_rows, coverage, refs, overlaps, room_rows, model_assets, catalog, qa)
    return qa


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    qa = run(args.root.resolve(), args.output_dir.resolve())
    print(json.dumps({"status": qa["status"], "output_dir": str(args.output_dir.resolve()), "counts": qa["count_checks"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
