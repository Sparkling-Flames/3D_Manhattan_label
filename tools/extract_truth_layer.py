from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

try:
    from perturbation_operators import (
        canonical_corners_to_runtime_pairs,
        ls_keypoints_to_canonical_corners,
    )
except ModuleNotFoundError:  # pragma: no cover
    from tools.perturbation_operators import (
        canonical_corners_to_runtime_pairs,
        ls_keypoints_to_canonical_corners,
    )


BUCKET_NAMES = {"manual", "semi", "OOS"}
TASK_ID_PATTERN = re.compile(r"task(\d+)")
LATEST_EXPORT_GLOB = "project-20-at-*.json"
OUTPUT_DIRNAME = "truth_layer_extraction_20260324"

REGISTRY_FIELDNAMES = [
    "task_id",
    "base_task_id",
    "bucket_dir",
    "trap_family",
    "current_scope_alias",
    "scope_binary",
    "difficulty_tags",
    "model_issue_tags",
    "has_kp",
    "has_poly",
    "has_txt",
    "txt_role",
    "geometry_truth_source",
    "priority_annotation",
    "priority_flag",
    "has_folder_note",
    "recommended_role",
    "review_note_flag",
    "needs_manual_review",
    "default_eligible",
    "directory_scope_mismatch",
    "notes",
]

# 当前 manual 侧不再靠括号语义泛化降级，而是按逐条复核后的显式角色冻结。
MANUAL_ROLE_OVERRIDES = {
    "462": "audit_only",
    "533": "audit_only",
    "567": "manual_non_anchor_candidate",
    "635": "manual_non_anchor_candidate",
    "676": "manual_non_anchor_candidate",
    "696": "manual_non_anchor_candidate",
    "711": "manual_non_anchor_candidate",
}


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _find_child_dir(root: Path, prefix: str) -> Path:
    matches = sorted(
        [path for path in root.iterdir() if path.is_dir() and path.name.startswith(prefix)],
        key=lambda item: item.name,
    )
    if not matches:
        raise FileNotFoundError(f"Cannot find child directory with prefix {prefix!r} under {root}")
    return matches[0]


def _latest_project20_export(root: Path) -> Path:
    export_root = _find_child_dir(root, "export")
    matches = sorted(
        export_root.rglob(LATEST_EXPORT_GLOB),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        raise FileNotFoundError(f"Cannot find any {LATEST_EXPORT_GLOB!r} under {export_root}")
    return matches[0]


def _trap_root(root: Path) -> Path:
    return _find_child_dir(root, "trap")


def _iter_task_dirs(trap_root: Path) -> list[Path]:
    return sorted(
        [path for path in trap_root.rglob("*") if path.is_dir() and TASK_ID_PATTERN.search(path.name)],
        key=lambda item: item.as_posix(),
    )


def _task_id_from_dir_name(name: str) -> str:
    match = TASK_ID_PATTERN.search(name)
    return match.group(1) if match else ""


def _priority_annotation_from_dir_name(name: str) -> str:
    match = re.search(r"\(([^)]*)\)", name)
    return match.group(1).strip() if match else ""


def classify_priority_flag(priority_annotation: str) -> str:
    text = str(priority_annotation or "").strip()
    if not text:
        return "default"

    # 当前人工复核规则：
    # 1. 明确写了“低优先”的任务默认记为 low_priority；
    # 2. task711 的 “中低优先” 是人工保留例外，不按低优先自动排除；
    # 3. 其他括号说明只作为 special_review，不自动降级。
    if text == "中低优先,难标注":
        return "special_review"
    if "低优先" in text:
        return "low_priority"
    return "special_review"


def scope_binary(scope_alias: str) -> str:
    if scope_alias == "normal":
        return "in_scope"
    if scope_alias:
        return "oos"
    return "unknown"


def _bool_text(value: bool) -> str:
    return "True" if value else "False"


def _load_export_tasks(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError(f"Expected JSON list at {path}")
    return payload


def _build_export_index(tasks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for task in tasks:
        title = str(task.get("data", {}).get("title", "")).strip()
        if not title:
            continue
        index[title] = task
        index[Path(title).stem] = task
    return index


def _task_from_base_task_id(export_index: dict[str, dict[str, Any]], base_task_id: str) -> dict[str, Any] | None:
    return (
        export_index.get(base_task_id)
        or export_index.get(base_task_id + ".jpg")
        or export_index.get(base_task_id + ".png")
    )


def _extract_annotation(task: dict[str, Any]) -> dict[str, Any] | None:
    annotations = task.get("annotations") or []
    if not annotations:
        return None
    return annotations[0]


def _extract_choices_by_field(annotation: dict[str, Any], field_name: str) -> list[str]:
    out: list[str] = []
    for result in annotation.get("result") or []:
        if result.get("from_name") != field_name:
            continue
        choices = ((result.get("value") or {}).get("choices")) or []
        for choice in choices:
            token = str(choice).strip()
            if token and token not in out:
                out.append(token)
    return out


def _annotation_result_flags(annotation: dict[str, Any]) -> dict[str, Any]:
    has_kp = False
    has_poly = False
    kp_count = 0
    poly_count = 0
    for result in annotation.get("result") or []:
        from_name = result.get("from_name")
        if from_name == "kp":
            has_kp = True
            kp_count += 1
        elif from_name == "poly":
            has_poly = True
            poly_count += 1
    return {
        "has_kp": has_kp,
        "has_poly": has_poly,
        "kp_count": kp_count,
        "poly_count": poly_count,
    }


def _note_paths_for_task(task_dir: Path) -> list[Path]:
    note_paths = []
    note_paths.extend(sorted(task_dir.glob("*.md")))
    note_paths.extend(sorted(task_dir.parent.glob("*.md")))
    unique: list[Path] = []
    seen: set[str] = set()
    for path in note_paths:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _read_note_excerpt(note_paths: list[Path], max_chars: int = 220) -> str:
    parts: list[str] = []
    for path in note_paths:
        text = path.read_text(encoding="utf-8").strip().replace("\n", " ")
        if not text:
            continue
        parts.append(f"{path.name}: {text[:max_chars]}")
    return " | ".join(parts)


def _directory_scope_mismatch(bucket_dir: str, current_scope_binary: str) -> bool:
    if bucket_dir in {"manual", "semi"}:
        return current_scope_binary == "oos"
    if bucket_dir == "OOS":
        return current_scope_binary == "in_scope"
    return False


def recommend_role(
    *,
    task_id: str,
    bucket_dir: str,
    family_name: str,
    current_scope_binary: str,
) -> str:
    if bucket_dir == "manual":
        if task_id in MANUAL_ROLE_OVERRIDES:
            return MANUAL_ROLE_OVERRIDES[task_id]
        return "manual_anchor_candidate"

    if bucket_dir == "semi":
        if family_name == "模型标注质量好":
            return "semi_control_candidate"
        if family_name in {"模型预标注失败", "漏标"}:
            return "audit_only"
        return "semi_trap_natural"

    if bucket_dir == "OOS":
        if current_scope_binary == "oos":
            return "oos_gate_candidate"
        return "audit_only"

    return "audit_only"


def _default_eligible(recommended_role: str, priority_flag: str, directory_scope_mismatch: bool) -> bool:
    if directory_scope_mismatch:
        return False
    if recommended_role == "audit_only":
        return False
    if priority_flag == "low_priority":
        return False
    return True


def _bucket_and_family(task_dir: Path) -> tuple[str, str]:
    bucket = next((parent.name for parent in task_dir.parents if parent.name in BUCKET_NAMES), "")
    return bucket, task_dir.parent.name


def build_trap_registry_rows(root: Path, export_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    trap_root = _trap_root(root)
    export_tasks = _load_export_tasks(export_path)
    export_index = _build_export_index(export_tasks)

    registry_rows: list[dict[str, Any]] = []
    annotation_rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []

    for task_dir in _iter_task_dirs(trap_root):
        task_id = _task_id_from_dir_name(task_dir.name)
        priority_annotation = _priority_annotation_from_dir_name(task_dir.name)
        priority_flag = classify_priority_flag(priority_annotation)
        txt_paths = sorted(task_dir.glob("*.txt"))
        txt_path = txt_paths[0] if txt_paths else None
        base_task_id = txt_path.stem if txt_path else ""
        export_task = _task_from_base_task_id(export_index, base_task_id)
        if export_task is None:
            continue

        bucket_dir, family_name = _bucket_and_family(task_dir)
        annotation = _extract_annotation(export_task)
        if annotation is None:
            continue

        note_paths = _note_paths_for_task(task_dir)
        note_excerpt = _read_note_excerpt(note_paths)
        current_scope_choices = _extract_choices_by_field(annotation, "scope")
        current_scope_alias = current_scope_choices[0] if current_scope_choices else ""
        current_scope_binary = scope_binary(current_scope_alias)
        difficulty_tags = _extract_choices_by_field(annotation, "difficulty")
        model_issue_tags = _extract_choices_by_field(annotation, "model_issue")
        result_flags = _annotation_result_flags(annotation)
        folder_note_present = bool(note_paths)
        directory_scope_mismatch = _directory_scope_mismatch(bucket_dir, current_scope_binary)
        recommended_role_value = recommend_role(
            task_id=task_id,
            bucket_dir=bucket_dir,
            family_name=family_name,
            current_scope_binary=current_scope_binary,
        )
        review_note_flag = folder_note_present or priority_flag != "default"
        needs_manual_review = (
            review_note_flag
            or directory_scope_mismatch
            or result_flags["has_poly"]
            or recommended_role_value == "audit_only"
        )
        default_eligible = _default_eligible(recommended_role_value, priority_flag, directory_scope_mismatch)

        notes: list[str] = []
        if priority_annotation:
            notes.append(f"priority_annotation={priority_annotation}")
        if folder_note_present:
            notes.append(f"note_files={','.join(path.name for path in note_paths)}")
        if result_flags["has_poly"]:
            notes.append("poly_residue_present_in_raw_export")
        if directory_scope_mismatch:
            notes.append("directory_scope_mismatch")
        if note_excerpt:
            notes.append(note_excerpt)

        registry_rows.append(
            {
                "task_id": task_id,
                "base_task_id": base_task_id,
                "bucket_dir": bucket_dir,
                "trap_family": family_name,
                "current_scope_alias": current_scope_alias,
                "scope_binary": current_scope_binary,
                "difficulty_tags": ";".join(difficulty_tags),
                "model_issue_tags": ";".join(model_issue_tags),
                "has_kp": _bool_text(result_flags["has_kp"]),
                "has_poly": _bool_text(result_flags["has_poly"]),
                "has_txt": _bool_text(bool(txt_path)),
                "txt_role": "legacy_mp3d_reference" if txt_path else "none",
                "geometry_truth_source": "project20_kp" if result_flags["has_kp"] else "none",
                "priority_annotation": priority_annotation,
                "priority_flag": priority_flag,
                "has_folder_note": _bool_text(folder_note_present),
                "recommended_role": recommended_role_value,
                "review_note_flag": _bool_text(review_note_flag),
                "needs_manual_review": _bool_text(needs_manual_review),
                "default_eligible": _bool_text(default_eligible),
                "directory_scope_mismatch": _bool_text(directory_scope_mismatch),
                "notes": " | ".join(notes),
            }
        )

        corners_norm, corner_meta = ls_keypoints_to_canonical_corners(annotation.get("result") or [])
        runtime_pairs = canonical_corners_to_runtime_pairs(corners_norm, 1024, 512) if corners_norm else []

        annotation_rows.append(
            {
                "task_id": task_id,
                "base_task_id": base_task_id,
                "source_export": "project20",
                "export_snapshot": export_path.name,
                "consensus_mode": "working_consensus_single_account_export",
                "annotation_id": annotation.get("id"),
                "completed_by": annotation.get("completed_by"),
                "bucket_dir": bucket_dir,
                "family_dir": family_name,
                "priority_annotation": priority_annotation,
                "scope": current_scope_alias,
                "scope_binary": current_scope_binary,
                "difficulty": difficulty_tags,
                "model_issue": model_issue_tags,
                "canonical_corners_norm": corners_norm,
                "runtime_pairs_1024x512": runtime_pairs,
                "n_keypoints": int(corner_meta.get("n_keypoints", 0)),
                "n_corners": int(corner_meta.get("n_corners", 0)),
                "pair_coverage": float(corner_meta.get("pair_coverage", 0.0)),
                "original_width": int(corner_meta.get("width", 1024)),
                "original_height": int(corner_meta.get("height", 512)),
                "image_url": export_task.get("data", {}).get("image", ""),
                "poly_present": result_flags["has_poly"],
                "poly_residue_flag": result_flags["has_poly"],
                "poly_count": int(result_flags["poly_count"]),
                "legacy_txt_present": bool(txt_path),
                "legacy_txt_path": str(txt_path.relative_to(root)) if txt_path else "",
                "legacy_txt_role": "legacy_mp3d_reference" if txt_path else "none",
                "legacy_txt_not_authoritative": True,
                "geometry_truth_source": "project20_kp" if result_flags["has_kp"] else "none",
                "adjudication_status": "working_consensus_not_final_gold",
                "priority_flag": priority_flag,
                "recommended_role": recommended_role_value,
                "review_note_flag": review_note_flag,
                "default_eligible": default_eligible,
                "directory_scope_mismatch": directory_scope_mismatch,
                "note_paths": [str(path.relative_to(root)) for path in note_paths],
            }
        )

        if directory_scope_mismatch:
            mismatches.append(
                {
                    "task_id": task_id,
                    "base_task_id": base_task_id,
                    "bucket_dir": bucket_dir,
                    "current_scope_alias": current_scope_alias,
                    "priority_flag": priority_flag,
                    "recommended_role": recommended_role_value,
                    "note_excerpt": note_excerpt,
                }
            )

    registry_rows.sort(key=lambda row: (row["bucket_dir"], int(row["task_id"])))
    annotation_rows.sort(key=lambda row: (row["bucket_dir"], int(row["task_id"])))
    summary = build_summary(registry_rows, annotation_rows, export_path)
    return registry_rows, annotation_rows, {
        "summary": summary,
        "mismatches": mismatches,
    }


def build_summary(
    registry_rows: list[dict[str, Any]],
    annotation_rows: list[dict[str, Any]],
    export_path: Path,
) -> dict[str, Any]:
    def count_where(pred) -> int:
        return sum(1 for row in registry_rows if pred(row))

    return {
        "export_snapshot": export_path.name,
        "n_tasks_total": len(registry_rows),
        "n_manual": count_where(lambda row: row["bucket_dir"] == "manual"),
        "n_semi": count_where(lambda row: row["bucket_dir"] == "semi"),
        "n_oos": count_where(lambda row: row["bucket_dir"] == "OOS"),
        "n_in_scope": count_where(lambda row: row["scope_binary"] == "in_scope"),
        "n_oos_scope": count_where(lambda row: row["scope_binary"] == "oos"),
        "n_low_priority": count_where(lambda row: row["priority_flag"] == "low_priority"),
        "n_special_review": count_where(lambda row: row["priority_flag"] == "special_review"),
        "n_with_kp_authoritative_geometry": sum(
            1 for row in annotation_rows if row["geometry_truth_source"] == "project20_kp"
        ),
        "n_with_legacy_txt": sum(1 for row in annotation_rows if row["legacy_txt_present"]),
        "n_with_poly_residue": sum(1 for row in annotation_rows if row["poly_residue_flag"]),
        "n_review_note_flag": sum(1 for row in annotation_rows if row["review_note_flag"]),
        "n_directory_scope_mismatch": count_where(lambda row: row["directory_scope_mismatch"] == "True"),
        "n_tasks_needing_followup": count_where(lambda row: row["needs_manual_review"] == "True"),
        "summary_status": "working_consensus_extraction_ready_not_final_gold",
        "notes": [
            "Current project-20 export is treated as a working-consensus snapshot rather than final adjudicated gold.",
            "Keypoint labels are the authoritative geometry extraction source for this layer; poly is residue-only and legacy txt remains reference-only.",
            "Manual anchor eligibility is no longer inferred from generic bracket text; explicit low-priority rows and manually reviewed overrides control anchor exclusion.",
        ],
    }


def build_oos_reconciliation_case(
    mismatches: list[dict[str, Any]],
    export_path: Path,
) -> dict[str, Any]:
    if not mismatches:
        return {
            "case_status": "no_active_mismatch_after_directory_update",
            "export_snapshot": export_path.name,
            "task_id": None,
            "base_task_id": None,
            "previous_bucket_dir": None,
            "current_scope_alias": None,
            "priority_flag": None,
            "recommended_role": None,
            "why_not_oos_anymore": "Latest repo scan finds zero active OOS-directory tasks whose current scope is in-scope.",
            "why_low_priority_now": None,
            "directory_sync_needed": False,
            "final_keep_bucket": None,
            "needs_followup": False,
            "notes": [
                "Earlier discussion assumed one OOS-to-in-scope case remained active.",
                "After the latest directory and export updates, that active mismatch no longer exists in the working tree.",
            ],
        }

    case = mismatches[0]
    return {
        "case_status": "active_directory_scope_mismatch",
        "export_snapshot": export_path.name,
        "task_id": case["task_id"],
        "base_task_id": case["base_task_id"],
        "previous_bucket_dir": case["bucket_dir"],
        "current_scope_alias": case["current_scope_alias"],
        "priority_flag": case["priority_flag"],
        "recommended_role": case["recommended_role"],
        "why_not_oos_anymore": "Current scope annotation is in-scope, so the directory bucket no longer matches the working-consensus truth layer.",
        "why_low_priority_now": case["priority_flag"] if case["priority_flag"] != "default" else None,
        "directory_sync_needed": True,
        "final_keep_bucket": case["bucket_dir"],
        "needs_followup": True,
        "notes": [case["note_excerpt"]] if case["note_excerpt"] else [],
    }


def run(output_dir: Path | None = None, root: Path | None = None) -> dict[str, Path]:
    repo_root = (root or Path(__file__).resolve().parents[1]).resolve()
    export_path = _latest_project20_export(repo_root)
    target_dir = output_dir or (repo_root / "analysis_results" / OUTPUT_DIRNAME)

    registry_rows, annotation_rows, aux = build_trap_registry_rows(repo_root, export_path)
    summary = aux["summary"]
    reconciliation = build_oos_reconciliation_case(aux["mismatches"], export_path)

    registry_path = target_dir / "trap_task_registry_v1.csv"
    annotation_path = target_dir / "manual_annotation_records_v1.jsonl"
    reconciliation_path = target_dir / "oos_scope_reconciliation_case_v1.json"
    summary_path = target_dir / "truth_layer_extraction_summary_v1.json"

    _write_csv(registry_path, registry_rows, REGISTRY_FIELDNAMES)
    _write_jsonl(annotation_path, annotation_rows)
    _write_json(reconciliation_path, reconciliation)
    _write_json(summary_path, summary)

    return {
        "registry": registry_path,
        "annotation_records": annotation_path,
        "oos_reconciliation": reconciliation_path,
        "summary": summary_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract working-consensus truth-layer artifacts from the latest project-20 export."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional custom output directory. Defaults to analysis_results/truth_layer_extraction_20260324.",
    )
    args = parser.parse_args()
    run(output_dir=args.output_dir)


if __name__ == "__main__":
    main()
