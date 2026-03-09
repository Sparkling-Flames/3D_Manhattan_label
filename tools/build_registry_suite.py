import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

from build_task_registry import DEFAULT_IMPORT_DIR, build_registry


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPORT_JSON = PROJECT_ROOT / "analysis_results" / "rerun_20260308" / "export_filtered_from_20260101.json"
DEFAULT_ACTIVE_LOG_DIR = PROJECT_ROOT / "active_logs" / "active_logs"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "analysis_results" / "registry_20260308"
LABEL_STUDIO_CONFIG = PROJECT_ROOT / "tools" / "label_studio_view_config.xml"
COMPAT_RULE_VERSION = "registry_suite_v1"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build A-line registries from split imports, export JSON, and active logs.")
    parser.add_argument("--import-dir", default=str(DEFAULT_IMPORT_DIR), help="Directory containing split import JSON files")
    parser.add_argument("--export-json", nargs="+", default=[str(DEFAULT_EXPORT_JSON)], help="One or more Label Studio export JSON files")
    parser.add_argument("--active-log-dir", default=str(DEFAULT_ACTIVE_LOG_DIR), help="Directory containing active time JSONL logs")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory for registry CSV/JSON files")
    return parser


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_iso8601(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def pick_latest_iso8601(values) -> str:
    latest_dt = None
    latest_text = ""
    for value in values:
        parsed = parse_iso8601(value)
        if parsed is None:
            continue
        if latest_dt is None or parsed > latest_dt:
            latest_dt = parsed
            latest_text = str(value)
    return latest_text


def write_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        output_path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_export_tasks(export_json_paths: list[Path]) -> tuple[list[dict], list[dict]]:
    combined_tasks: list[dict] = []
    source_summaries: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()

    for path in export_json_paths:
        tasks = load_json(path)
        project_ids: set[str] = set()
        dataset_groups: set[str] = set()
        init_types: set[str] = set()
        task_updated_candidates: list[str] = []
        annotation_updated_candidates: list[str] = []
        annotation_count = 0
        duplicate_task_count = 0

        for task in tasks:
            project_ids.add(str(task.get("project") or ""))
            task_data = task.get("data") or {}
            dataset_group = str(task_data.get("dataset_group") or "").strip()
            init_type = str(task_data.get("init_type") or "").strip()
            if dataset_group:
                dataset_groups.add(dataset_group)
            if init_type:
                init_types.add(init_type)
            task_updated_candidates.append(str(task.get("updated_at") or ""))

            annotations = task.get("annotations", []) or []
            annotation_count += len(annotations)
            for annotation in annotations:
                annotation_updated_candidates.append(str(annotation.get("updated_at") or ""))

            task_copy = dict(task)
            task_copy["_export_source_file"] = path.name
            task_copy["_export_source_path"] = str(path)

            dedupe_key = (str(task.get("project") or ""), str(task.get("id") or ""))
            if dedupe_key in seen_keys:
                duplicate_task_count += 1
                continue
            seen_keys.add(dedupe_key)
            combined_tasks.append(task_copy)

        source_summaries.append(
            {
                "export_source_file": path.name,
                "export_source_path": str(path),
                "task_count": len(tasks),
                "annotation_count": annotation_count,
                "project_ids": sorted([value for value in project_ids if value]),
                "dataset_groups": sorted(dataset_groups),
                "init_types": sorted(init_types),
                "max_task_updated_at": pick_latest_iso8601(task_updated_candidates),
                "max_annotation_updated_at": pick_latest_iso8601(annotation_updated_candidates),
                "duplicate_task_count_skipped": duplicate_task_count,
            }
        )

    return combined_tasks, source_summaries


def normalize_title_key(value: str) -> str:
    return Path(str(value or "").strip()).stem.lower()


def normalize_image_basename(value: str) -> str:
    return Path(str(value or "").strip()).name.lower()


def normalize_choice_values(values) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [part.strip() for part in values.split(";") if part.strip()]
    out: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in out:
            out.append(text)
    return out


def join_choices(values) -> str:
    return ";".join(normalize_choice_values(values))


def parse_completed_by(value) -> str:
    if isinstance(value, dict):
        return str(value.get("id", "unknown"))
    if value is None:
        return "unknown"
    return str(value)


def parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def load_choice_alias_map(xml_path: Path) -> dict[str, dict[str, str]]:
    if not xml_path.exists():
        return {}
    root = ET.parse(str(xml_path)).getroot()
    out: dict[str, dict[str, str]] = {}
    for node in root.iter():
        if node.tag != "Choices":
            continue
        field_name = str(node.attrib.get("name") or "").strip()
        if not field_name:
            continue
        field_map = out.setdefault(field_name, {})
        for child in list(node):
            if child.tag != "Choice":
                continue
            value_text = str(child.attrib.get("value") or "").strip()
            alias = str(child.attrib.get("alias") or "").strip()
            if value_text and alias:
                field_map[value_text] = alias
    return out


CHOICE_ALIAS_MAP = load_choice_alias_map(LABEL_STUDIO_CONFIG)
MODEL_ISSUE_TAG_REMAP = {"corner_mismatch": "topology_failure"}


def map_choice_value(field_name: str, value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    mapping = CHOICE_ALIAS_MAP.get(field_name, {})
    if text in mapping.values():
        return text
    return mapping.get(text, text)


def extract_choice_map(results: list[dict]) -> tuple[dict[str, list[str]], str, bool]:
    choice_map: defaultdict[str, list[str]] = defaultdict(list)
    choice_fields: list[str] = []
    geometry_present = False
    for result in results or []:
        result_type = result.get("type")
        if result_type in {"keypointlabels", "keypointregion", "polygonlabels", "polygonregion"}:
            geometry_present = True
        if result_type != "choices":
            continue
        field_name = str(result.get("from_name") or result.get("name") or "quality")
        choice_fields.append(field_name)
        raw_choices = ((result.get("value") or {}).get("choices") or [])
        for raw_choice in raw_choices:
            alias = map_choice_value(field_name, raw_choice)
            if alias and alias not in choice_map[field_name]:
                choice_map[field_name].append(alias)
    raw_field_profile = ";".join(sorted(set(choice_fields))) if choice_fields else ""
    return dict(choice_map), raw_field_profile, geometry_present


def scope_is_oos(scope_values: list[str]) -> bool:
    for value in normalize_choice_values(scope_values):
        value_lower = value.lower()
        if value_lower.startswith("oos") or "out-of-scope" in value_lower or "out of scope" in value_lower:
            return True
        if any(token in value for token in ["边界不可判定", "几何假设不成立", "错层", "多平面", "证据不足"]):
            return True
    return False


def has_prediction_failure(model_issue_values: list[str]) -> bool:
    for value in normalize_choice_values(model_issue_values):
        lower = value.lower()
        if lower == "fail" or "prediction failure" in lower:
            return True
        if "预标注失效" in value or "模型预标注失效" in value:
            return True
    return False


def normalize_model_issue(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in normalize_choice_values(values):
        remapped = MODEL_ISSUE_TAG_REMAP.get(value, value)
        if remapped and remapped not in out:
            out.append(remapped)
    return out


def determine_schema_version(choice_map: dict[str, list[str]], raw_field_profile: str, geometry_present: bool, results: list[dict]) -> str:
    has_quality = bool(choice_map.get("quality"))
    has_structured = any(choice_map.get(field) for field in ["scope", "difficulty", "model_issue", "tool_issue"])
    if has_structured and has_quality:
        return "mixed"
    if has_structured:
        return "v2_structured"
    if has_quality:
        return "legacy_quality_only"
    if results or geometry_present or raw_field_profile:
        return "malformed"
    return "malformed"


def infer_runtime_condition(task: dict) -> str:
    preds_list = task.get("predictions") or []
    if parse_bool(task.get("prediction")):
        return "semi"
    if isinstance(preds_list, list) and preds_list:
        return "semi"
    for ann in task.get("annotations", []) or []:
        if isinstance(ann.get("prediction"), dict) or ann.get("prediction"):
            return "semi"
        for result in ann.get("result", []) or []:
            if str(result.get("origin") or "").lower() == "prediction":
                return "semi"
    return "manual"


def load_active_logs(log_dir: Path) -> tuple[dict[tuple[str, str], dict], dict[str, dict]]:
    session_max: dict[tuple[str, str, str], float] = {}
    session_files: defaultdict[tuple[str, str, str], set[str]] = defaultdict(set)
    session_events: Counter = Counter()
    for path in sorted(log_dir.glob("active_times_*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                try:
                    record = json.loads(text)
                except json.JSONDecodeError:
                    continue
                task_id = str(record.get("task_id") or "")
                if not task_id:
                    continue
                annotator_id = str(record.get("annotator_id", "unknown"))
                session_id = str(record.get("session_id", "default"))
                active_seconds = float(record.get("active_seconds") or 0)
                key = (task_id, annotator_id, session_id)
                if active_seconds > session_max.get(key, 0.0):
                    session_max[key] = active_seconds
                session_files[key].add(path.name)
                session_events[key] += 1

    per_task_annotator: defaultdict[tuple[str, str], dict] = defaultdict(lambda: {
        "active_time_value": 0.0,
        "active_time_source_file": set(),
        "active_time_session_count": 0,
        "active_time_event_count": 0,
    })
    per_task: defaultdict[str, dict] = defaultdict(lambda: {
        "source_files": set(),
        "session_count": 0,
        "event_count": 0,
    })

    for (task_id, annotator_id, _session_id), max_seconds in session_max.items():
        target = per_task_annotator[(task_id, annotator_id)]
        target["active_time_value"] += max_seconds
        target["active_time_source_file"].update(session_files[(task_id, annotator_id, _session_id)])
        target["active_time_session_count"] += 1
        target["active_time_event_count"] += session_events[(task_id, annotator_id, _session_id)]

        task_bucket = per_task[task_id]
        task_bucket["source_files"].update(session_files[(task_id, annotator_id, _session_id)])
        task_bucket["session_count"] += 1
        task_bucket["event_count"] += session_events[(task_id, annotator_id, _session_id)]

    for value in per_task_annotator.values():
        value["active_time_source_file"] = ";".join(sorted(value["active_time_source_file"]))
    for value in per_task.values():
        value["source_files"] = ";".join(sorted(value["source_files"]))

    return dict(per_task_annotator), dict(per_task)


def build_planned_registry(import_dir: Path) -> tuple[list[dict], dict, dict[str, list[dict]]]:
    rows, summary = build_registry(import_dir)
    enriched_rows: list[dict] = []
    title_index: defaultdict[str, list[dict]] = defaultdict(list)
    for row in rows:
        enriched = dict(row)
        enriched.setdefault("planned_task_key", f"{row['manifest_stage_key']}:{row['base_task_id']}:{row['import_index']}")
        enriched.setdefault("normalized_title", normalize_title_key(row.get("title") or row.get("image") or row.get("base_task_id")))
        enriched.setdefault("condition", row.get("planned_condition", ""))
        enriched["runtime_task_id_available"] = False
        enriched_rows.append(enriched)
        title_index[enriched["normalized_title"]].append(enriched)
    return enriched_rows, summary, dict(title_index)


def match_planned_task(task: dict, title_index: dict[str, list[dict]]) -> tuple[dict | None, str, int]:
    normalized_title = normalize_title_key((task.get("data") or {}).get("title") or (task.get("data") or {}).get("image"))
    candidates = list(title_index.get(normalized_title, []))
    if not candidates:
        return None, "unmatched", 0
    if len(candidates) == 1:
        return candidates[0], "matched_by_title", 1

    runtime_condition = infer_runtime_condition(task)
    filtered = [candidate for candidate in candidates if candidate.get("condition") == runtime_condition]
    if len(filtered) == 1:
        return filtered[0], "matched_by_title_condition", len(candidates)

    return None, "ambiguous", len(candidates)


def build_compat_fields(choice_map: dict[str, list[str]], schema_version: str) -> dict:
    scope_values = normalize_choice_values(choice_map.get("scope", []))
    difficulty_values = normalize_choice_values(choice_map.get("difficulty", []))
    model_issue_values = normalize_model_issue(choice_map.get("model_issue", []))
    quality_values = normalize_choice_values(choice_map.get("quality", []))

    compat_scope = join_choices(scope_values)
    compat_scope_source = "direct_v2" if compat_scope else "missing"
    compat_difficulty = join_choices(difficulty_values)
    compat_difficulty_source = "direct_v2" if compat_difficulty else "missing"
    compat_model_issue = join_choices(model_issue_values)
    compat_model_issue_source = "direct_v2" if compat_model_issue else "missing"
    compat_notes: list[str] = []

    if not compat_scope and quality_values:
        if "split_level" in quality_values:
            compat_scope = "oos_split_level"
            compat_scope_source = "legacy_quality_map"
        elif "normal" in quality_values:
            compat_scope = "normal"
            compat_scope_source = "legacy_quality_map"
        if compat_scope_source == "legacy_quality_map":
            compat_notes.append("scope mapped from legacy quality")

    if not compat_model_issue and quality_values and "fail" in quality_values:
        compat_model_issue = "fail"
        compat_model_issue_source = "legacy_quality_map"
        compat_notes.append("model_issue mapped from legacy quality")

    compat_review_needed = bool(
        schema_version in {"legacy_quality_only", "mixed", "malformed"}
        or compat_scope_source == "legacy_quality_map"
        or compat_model_issue_source == "legacy_quality_map"
    )

    return {
        "compat_scope": compat_scope,
        "compat_scope_source": compat_scope_source,
        "compat_difficulty": compat_difficulty,
        "compat_difficulty_source": compat_difficulty_source,
        "compat_model_issue": compat_model_issue,
        "compat_model_issue_source": compat_model_issue_source,
        "compat_rule_version": COMPAT_RULE_VERSION,
        "compat_review_needed": compat_review_needed,
        "compat_notes": ";".join(compat_notes),
    }


def build_registries(tasks: list[dict], title_index: dict[str, list[dict]], active_logs: dict[tuple[str, str], dict], task_log_rollup: dict[str, dict]) -> tuple[list[dict], list[dict], list[dict], list[dict], dict]:

    annotation_rows: list[dict] = []
    compat_rows: list[dict] = []
    active_time_rows: list[dict] = []
    merged_rows: list[dict] = []

    join_status_counter: Counter = Counter()
    schema_counter: Counter = Counter()

    for task in tasks:
        task_id = str(task.get("id") or "")
        task_data = task.get("data") or {}
        runtime_title = str(task_data.get("title") or "").strip()
        runtime_image = str(task_data.get("image") or "").strip()
        normalized_title = normalize_title_key(runtime_title or runtime_image)
        runtime_condition = infer_runtime_condition(task)
        runtime_condition_source = "derived_from_prediction_presence"
        export_source_file = str(task.get("_export_source_file") or "")
        export_source_path = str(task.get("_export_source_path") or "")
        export_project_id = str(task.get("project") or "")
        export_dataset_group = str(task_data.get("dataset_group") or "").strip()
        export_init_type = str(task_data.get("init_type") or "").strip()
        matched_row, join_status, candidate_count = match_planned_task(task, title_index)
        join_status_counter[join_status] += 1

        planned_stage = matched_row.get("planned_stage", "") if matched_row else ""
        planned_condition = matched_row.get("condition", "") if matched_row else ""
        planned_dataset_group = matched_row.get("dataset_group", "") if matched_row else ""
        dataset_group = planned_dataset_group or export_dataset_group
        dataset_group_source = (
            "planned_registry_match"
            if planned_dataset_group
            else ("export_task_data" if export_dataset_group else "missing")
        )
        source_pool = matched_row.get("source_pool", "") if matched_row else ""
        base_task_id = matched_row.get("base_task_id", normalized_title) if matched_row else normalized_title
        is_anchor = matched_row.get("is_anchor", False) if matched_row else False
        has_expert_ref = matched_row.get("has_expert_ref", False) if matched_row else False
        planned_init_type = matched_row.get("init_type", "") if matched_row else ""
        init_type = planned_init_type or export_init_type
        matched_registry_uid = matched_row.get("registry_uid", "") if matched_row else ""

        for annotation in task.get("annotations", []) or []:
            annotation_id = str(annotation.get("id") or "")
            annotator_id = parse_completed_by(annotation.get("completed_by"))
            results = annotation.get("result", []) or []
            choice_map, raw_field_profile, geometry_present = extract_choice_map(results)
            schema_version = determine_schema_version(choice_map, raw_field_profile, geometry_present, results)
            schema_counter[schema_version] += 1

            scope_values = normalize_choice_values(choice_map.get("scope", []))
            difficulty_values = normalize_choice_values(choice_map.get("difficulty", []))
            model_issue_values = normalize_model_issue(choice_map.get("model_issue", []))
            quality_values = normalize_choice_values(choice_map.get("quality", []))
            tool_issue_values = normalize_choice_values(choice_map.get("tool_issue", []))

            compat = build_compat_fields(choice_map, schema_version)

            direct_active = active_logs.get((task_id, annotator_id))
            per_task_log = task_log_rollup.get(task_id, {})
            lead_time_seconds = float(annotation.get("lead_time") or 0)
            if direct_active:
                active_time_value = round(float(direct_active["active_time_value"]), 6)
                active_time_source = "log"
                active_time_source_file = direct_active["active_time_source_file"]
                active_time_match_status = "task+annotator"
                active_time_session_count = int(direct_active["active_time_session_count"])
                active_time_event_count = int(direct_active["active_time_event_count"])
            elif lead_time_seconds > 0:
                active_time_value = round(lead_time_seconds, 6)
                active_time_source = "lead_time_fallback"
                active_time_source_file = per_task_log.get("source_files", "")
                active_time_match_status = "fallback_no_direct_log" if not per_task_log else "fallback_log_present_but_no_direct_match"
                active_time_session_count = int(per_task_log.get("session_count", 0))
                active_time_event_count = int(per_task_log.get("event_count", 0))
            else:
                active_time_value = 0.0
                active_time_source = "missing"
                active_time_source_file = per_task_log.get("source_files", "")
                active_time_match_status = "missing"
                active_time_session_count = int(per_task_log.get("session_count", 0))
                active_time_event_count = int(per_task_log.get("event_count", 0))

            scope_missing = not bool(scope_values)
            difficulty_missing = not bool(difficulty_values)
            model_issue_missing = not bool(model_issue_values)
            is_oos = "" if scope_missing and not compat["compat_scope"] else str(scope_is_oos(scope_values or normalize_choice_values(compat["compat_scope"]))).lower()
            is_fail = str(has_prediction_failure(model_issue_values or normalize_choice_values(compat["compat_model_issue"]))).lower()

            annotation_row = {
                "task_id": task_id,
                "annotation_id": annotation_id,
                "annotator_id": annotator_id,
                "base_task_id": base_task_id,
                "normalized_title": normalized_title,
                "title": runtime_title,
                "image": runtime_image,
                "total_annotations": int(task.get("total_annotations") or 0),
                "total_predictions": int(task.get("total_predictions") or 0),
                "runtime_condition": runtime_condition,
                "runtime_condition_source": runtime_condition_source,
                "task_join_status": join_status,
                "matched_registry_uid": matched_registry_uid,
                "matched_registry_candidate_count": candidate_count,
                "planned_stage": planned_stage,
                "planned_condition": planned_condition,
                "planned_dataset_group": planned_dataset_group,
                "export_dataset_group": export_dataset_group,
                "dataset_group": dataset_group,
                "dataset_group_source": dataset_group_source,
                "source_pool": source_pool,
                "planned_init_type": planned_init_type,
                "export_init_type": export_init_type,
                "resolved_init_type": init_type,
                "export_project_id": export_project_id,
                "export_source_file": export_source_file,
                "export_source_path": export_source_path,
                "schema_version": schema_version,
                "annotation_created_at": str(annotation.get("created_at") or ""),
                "annotation_updated_at": str(annotation.get("updated_at") or ""),
                "raw_field_profile": raw_field_profile,
                "raw_choice_fields": ";".join(sorted(choice_map.keys())),
                "quality_choices": join_choices(quality_values),
                "scope_choices": join_choices(scope_values),
                "difficulty_choices": join_choices(difficulty_values),
                "model_issue_choices": join_choices(model_issue_values),
                "tool_issue_choices": join_choices(tool_issue_values),
                "normalized_scope": compat["compat_scope"] if compat["compat_scope_source"] == "direct_v2" else "",
                "normalized_difficulty": compat["compat_difficulty"] if compat["compat_difficulty_source"] == "direct_v2" else "",
                "normalized_model_issue": compat["compat_model_issue"] if compat["compat_model_issue_source"] == "direct_v2" else "",
                "scope_missing": scope_missing,
                "difficulty_missing": difficulty_missing,
                "model_issue_missing": model_issue_missing,
                "is_oos": is_oos,
                "is_fail": is_fail,
                "lead_time_seconds": round(lead_time_seconds, 6),
                "geometry_present": geometry_present,
                "result_count": int(annotation.get("result_count") or len(results)),
            }
            annotation_rows.append(annotation_row)

            compat_row = {
                "task_id": task_id,
                "annotation_id": annotation_id,
                "annotator_id": annotator_id,
                "schema_version": schema_version,
                "quality_choices": join_choices(quality_values),
                "scope_choices": join_choices(scope_values),
                "difficulty_choices": join_choices(difficulty_values),
                "model_issue_choices": join_choices(model_issue_values),
                **compat,
            }
            compat_rows.append(compat_row)

            active_time_row = {
                "task_id": task_id,
                "annotation_id": annotation_id,
                "annotator_id": annotator_id,
                "lead_time_seconds": round(lead_time_seconds, 6),
                "active_time_value": active_time_value,
                "active_time_source": active_time_source,
                "active_time_source_file": active_time_source_file,
                "active_time_match_status": active_time_match_status,
                "active_time_session_count": active_time_session_count,
                "active_time_event_count": active_time_event_count,
            }
            active_time_rows.append(active_time_row)

            merged_rows.append(
                {
                    "task_id": task_id,
                    "annotation_id": annotation_id,
                    "annotator_id": annotator_id,
                    "base_task_id": base_task_id,
                    "title": runtime_title,
                    "normalized_title": normalized_title,
                    "planned_stage": planned_stage,
                    "planned_condition": planned_condition,
                    "runtime_condition": runtime_condition,
                    "runtime_condition_source": runtime_condition_source,
                    "planned_dataset_group": planned_dataset_group,
                    "export_dataset_group": export_dataset_group,
                    "dataset_group": dataset_group,
                    "dataset_group_source": dataset_group_source,
                    "source_pool": source_pool,
                    "is_anchor": is_anchor,
                    "has_expert_ref": has_expert_ref,
                    "init_type": init_type,
                    "export_source_file": export_source_file,
                    "schema_version": schema_version,
                    "compat_scope": compat["compat_scope"],
                    "compat_difficulty": compat["compat_difficulty"],
                    "compat_model_issue": compat["compat_model_issue"],
                    "compat_review_needed": compat["compat_review_needed"],
                    "is_oos": is_oos,
                    "is_fail": is_fail,
                    "lead_time_seconds": round(lead_time_seconds, 6),
                    "active_time_value": active_time_value,
                    "active_time_source": active_time_source,
                    "task_join_status": join_status,
                    "matched_registry_uid": matched_registry_uid,
                    "matched_registry_candidate_count": candidate_count,
                }
            )

    summary = {
        "task_count": len(tasks),
        "annotation_count": len(annotation_rows),
        "counts_by_schema_version": dict(schema_counter),
        "counts_by_task_join_status": dict(join_status_counter),
        "legacy_quality_annotation_count": int(schema_counter.get("legacy_quality_only", 0)),
    }
    return annotation_rows, compat_rows, active_time_rows, merged_rows, summary


def main() -> int:
    args = build_parser().parse_args()

    import_dir = Path(args.import_dir).resolve()
    export_json_paths = [Path(value).resolve() for value in args.export_json]
    active_log_dir = Path(args.active_log_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    task_rows, task_summary, title_index = build_planned_registry(import_dir)
    active_logs, task_log_rollup = load_active_logs(active_log_dir)
    export_tasks, export_source_summaries = load_export_tasks(export_json_paths)
    annotation_rows, compat_rows, active_time_rows, merged_rows, suite_summary = build_registries(
        export_tasks,
        title_index,
        active_logs,
        task_log_rollup,
    )

    write_csv(task_rows, output_dir / "task_registry_v2.csv")
    write_csv(annotation_rows, output_dir / "annotation_registry_v1.csv")
    write_csv(compat_rows, output_dir / "compat_registry_v1.csv")
    write_csv(active_time_rows, output_dir / "active_time_registry_v1.csv")
    write_csv(merged_rows, output_dir / "merged_all_v0.csv")
    (output_dir / "registry_source_manifest_v1.json").write_text(
        json.dumps(
            {
                "export_sources": export_source_summaries,
                "notes": [
                    "runtime_condition is derived from prediction presence on export-side tasks.",
                    "dataset_group preserves both planned_registry and export_task_data provenance when available.",
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    summary_payload = {
        "task_registry": task_summary,
        "registry_suite": suite_summary,
        "export_sources": export_source_summaries,
        "notes": [
            "task_registry_v2 remains a planned split registry; runtime task_id is only available on export-side tables.",
            "ambiguous export-to-plan joins are preserved as explicit task_join_status values instead of forced matches.",
            "runtime_condition is a derived export-side field based on prediction presence, not split-side planned truth.",
        ],
    }
    (output_dir / "registry_suite_summary_v1.json").write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[registry-suite] task_registry_v2: {len(task_rows)} rows")
    print(f"[registry-suite] annotation_registry_v1: {len(annotation_rows)} rows")
    print(f"[registry-suite] compat_registry_v1: {len(compat_rows)} rows")
    print(f"[registry-suite] active_time_registry_v1: {len(active_time_rows)} rows")
    print(f"[registry-suite] merged_all_v0: {len(merged_rows)} rows")
    print(f"[registry-suite] summary: {output_dir / 'registry_suite_summary_v1.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())