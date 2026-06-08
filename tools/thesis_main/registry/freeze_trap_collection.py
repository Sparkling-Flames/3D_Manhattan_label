from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from tools.thesis_main.registry.perturbation_operators import (
        OPERATOR_REGISTRY,
        canonical_corners_to_runtime_pairs,
        ls_keypoints_to_canonical_corners,
    )
except ModuleNotFoundError:  # pragma: no cover
    from perturbation_operators import (
        OPERATOR_REGISTRY,
        canonical_corners_to_runtime_pairs,
        ls_keypoints_to_canonical_corners,
    )


CLASS_ACCEPTABLE = "\u6a21\u578b\u6807\u6ce8\u8d28\u91cf\u597d"
CLASS_OVER_PARSING = "\u8fc7\u5ea6\u89e3\u6790"
CLASS_CORNER_DRIFT = "\u89d2\u70b9\u9519\u4f4d"
CLASS_CORNER_DUPLICATE = "\u89d2\u70b9\u91cd\u590d"
CLASS_OVEREXTEND = "\u8de8\u95e8\u6269\u5f20"
CLASS_UNDEREXTEND = "\u6f0f\u6807"
CLASS_FAIL = "\u6a21\u578b\u9884\u6807\u6ce8\u5931\u8d25"
CLASS_TOPOLOGY = "\u62d3\u6251\u5d29\u6e83"

LAYOUT_TXT_WIDTH = 1024
LAYOUT_TXT_HEIGHT = 512
LAYOUT_COORD_CONTRACT = "hohonet_layout_txt_pixel_coords_point_pairs_or_x_yceil_yfloor@1024x512"

DEFAULT_SYNTHETIC_PRESET = [
    {"family": "overextend_adjacent", "lambda_level": "medium"},
    {"family": "over_parsing", "lambda_level": "weak"},
    {"family": "corner_drift", "lambda_level": "weak"},
    {"family": "corner_duplicate", "lambda_level": "weak"},
]

SEMI_CLASS_TO_FAMILY = {
    CLASS_ACCEPTABLE: "acceptable",
    CLASS_OVER_PARSING: "over_parsing",
    CLASS_CORNER_DRIFT: "corner_drift",
    CLASS_CORNER_DUPLICATE: "corner_duplicate",
    CLASS_OVEREXTEND: "overextend_adjacent",
    CLASS_UNDEREXTEND: "underextend",
    CLASS_FAIL: "fail",
    CLASS_TOPOLOGY: "topology_failure",
}

MANUAL_POOL_FIELDNAMES = [
    "collection_class",
    "task_folder_name",
    "task_id",
    "base_task_id",
    "layout_txt_path",
    "image_path",
    "layout_coord_contract",
    "priority_annotation",
    "has_layout_txt",
    "has_image",
]

SEED_POOL_FIELDNAMES = [
    "seed_class",
    "task_folder_name",
    "task_id",
    "base_task_id",
    "layout_txt_path",
    "image_path",
    "layout_coord_contract",
    "priority_annotation",
    "n_corners",
    "control_candidate_status",
    "synthetic_seed_status",
]

SYNTHETIC_BANK_FIELDNAMES = [
    "candidate_id",
    "seed_task_id",
    "seed_base_task_id",
    "seed_priority_annotation",
    "family",
    "lambda_level",
    "status",
    "failure_code",
    "seed_corner_count",
    "generated_corner_count",
    "audit_hash",
]

DISJOINT_SYNTHETIC_BANK_FIELDNAMES = [
    "candidate_id",
    "source_candidate_id",
    "source_base_task_id",
    "source_title",
    "family",
    "lambda_level",
    "status",
    "failure_code",
    "source_corner_count",
    "generated_corner_count",
    "audit_hash",
]

SEMI_CANDIDATE_REGISTRY_FIELDNAMES = [
    "candidate_id",
    "base_task_id",
    "task_id",
    "family",
    "source_type",
    "repairability",
    "ambiguity_risk",
    "manual_anchor_eligible",
    "prescreen_trap_eligible",
    "selection_policy_bucket",
    "priority_annotation",
    "overlap_with_tentative_control_pool",
    "notes",
]


def _stable_hash(payload: Any) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _stable_seed_from_task_and_family(token: str, family: str) -> int:
    digest = hashlib.sha256(f"{token}:{family}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


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


def load_phase1_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_list(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError(f"Expected a JSON list: {path}")
    return payload


def _task_id_from_folder_name(folder_name: str) -> str:
    match = re.search(r"task(\d+)", folder_name)
    return match.group(1) if match else ""


def _priority_annotation_from_folder_name(folder_name: str) -> str:
    match = re.search(r"\(([^)]*)\)", folder_name)
    return match.group(1).strip() if match else ""


def _find_layout_txt(task_dir: Path) -> Path | None:
    txt_files = sorted(task_dir.glob("*.txt"))
    return txt_files[0] if txt_files else None


def _find_primary_image(task_dir: Path, base_task_id: str) -> Path | None:
    candidates = sorted(
        [path for ext in ("*.png", "*.jpg", "*.jpeg") for path in task_dir.glob(ext)]
    )
    if not candidates:
        return None
    for image_path in candidates:
        if image_path.stem == base_task_id:
            return image_path
    return max(candidates, key=lambda item: item.stat().st_size)


def _sort_corners(corners_norm: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        corners_norm,
        key=lambda item: (
            float(item["x_pct"]),
            float(item["y_top_pct"]),
            float(item["y_bottom_pct"]),
        ),
    )
    normalized = []
    for index, item in enumerate(ordered):
        normalized.append(
            {
                "id": index,
                "x_pct": float(item["x_pct"]) % 100.0,
                "y_top_pct": max(0.0, min(100.0, float(item["y_top_pct"]))),
                "y_bottom_pct": max(0.0, min(100.0, float(item["y_bottom_pct"]))),
            }
        )
    return normalized


def read_layout_txt_as_corners(txt_path: Path) -> list[dict[str, Any]]:
    parsed_rows: list[list[float]] = []
    for raw in txt_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) not in {2, 3}:
            raise ValueError(f"Invalid layout txt row in {txt_path}: {raw!r}")
        parsed_rows.append([float(part) for part in parts])

    if not parsed_rows:
        return []

    corners = []
    if all(len(parts) == 3 for parts in parsed_rows):
        for index, (x_px, y_top_px, y_bottom_px) in enumerate(parsed_rows):
            corners.append(
                {
                    "id": index,
                    "x_pct": 100.0 * x_px / float(LAYOUT_TXT_WIDTH),
                    "y_top_pct": 100.0 * y_top_px / float(LAYOUT_TXT_HEIGHT),
                    "y_bottom_pct": 100.0 * y_bottom_px / float(LAYOUT_TXT_HEIGHT),
                }
            )
        return _sort_corners(corners)

    if not all(len(parts) == 2 for parts in parsed_rows):
        raise ValueError(f"Mixed layout txt formats are not supported: {txt_path}")

    keypoints = [{"x_px": parts[0], "y_px": parts[1]} for parts in parsed_rows]
    keypoints.sort(key=lambda item: (item["x_px"], item["y_px"]))
    threshold_px = 0.05 * float(LAYOUT_TXT_WIDTH)
    used = [False] * len(keypoints)

    for index, point in enumerate(keypoints):
        if used[index]:
            continue
        best_j = -1
        for j in range(index + 1, len(keypoints)):
            if used[j]:
                continue
            if abs(keypoints[j]["x_px"] - point["x_px"]) < threshold_px:
                best_j = j
                break
        if best_j == -1:
            continue
        used[index] = True
        used[best_j] = True
        other = keypoints[best_j]
        corners.append(
            {
                "id": len(corners),
                "x_pct": 100.0
                * (0.5 * (point["x_px"] + other["x_px"]))
                / float(LAYOUT_TXT_WIDTH),
                "y_top_pct": 100.0 * min(point["y_px"], other["y_px"]) / float(LAYOUT_TXT_HEIGHT),
                "y_bottom_pct": 100.0 * max(point["y_px"], other["y_px"]) / float(LAYOUT_TXT_HEIGHT),
            }
        )
    return _sort_corners(corners)


def build_task_folder_inventory(class_dir: Path, trap_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task_dir in sorted(path for path in class_dir.iterdir() if path.is_dir()):
        task_id = _task_id_from_folder_name(task_dir.name)
        txt_path = _find_layout_txt(task_dir)
        base_task_id = txt_path.stem if txt_path else ""
        image_path = _find_primary_image(task_dir, base_task_id) if base_task_id else None
        rows.append(
            {
                "collection_class": class_dir.name,
                "seed_class": class_dir.name,
                "task_folder_name": task_dir.name,
                "task_id": task_id,
                "base_task_id": base_task_id,
                "layout_txt_path": str(txt_path.relative_to(trap_root)) if txt_path else "",
                "image_path": str(image_path.relative_to(trap_root)) if image_path else "",
                "layout_coord_contract": LAYOUT_COORD_CONTRACT,
                "priority_annotation": _priority_annotation_from_folder_name(task_dir.name),
                "has_layout_txt": bool(txt_path),
                "has_image": bool(image_path),
            }
        )
    return rows


def build_manual_pool(manual_root: Path, trap_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for class_dir in sorted(path for path in manual_root.iterdir() if path.is_dir()):
        rows.extend(build_task_folder_inventory(class_dir, trap_root))
    return rows


def build_acceptable_seed_pool(semi_root: Path, trap_root: Path) -> list[dict[str, Any]]:
    acceptable_dir = semi_root / CLASS_ACCEPTABLE
    rows = build_task_folder_inventory(acceptable_dir, trap_root)
    for row in rows:
        txt_path = trap_root / row["layout_txt_path"] if row["layout_txt_path"] else None
        corners = read_layout_txt_as_corners(txt_path) if txt_path and txt_path.exists() else []
        row.update(
            {
                "n_corners": len(corners),
                "control_candidate_status": "candidate_only_not_frozen",
                "synthetic_seed_status": "candidate_only_not_frozen",
            }
        )
    return rows


def build_semi_natural_trap_pool(semi_root: Path, trap_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for class_dir in sorted(path for path in semi_root.iterdir() if path.is_dir()):
        family = SEMI_CLASS_TO_FAMILY.get(class_dir.name)
        if family in {None, "acceptable"}:
            continue
        for row in build_task_folder_inventory(class_dir, trap_root):
            row["family"] = family
            rows.append(row)
    return rows


def build_oos_candidate_pool(oos_root: Path, trap_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for class_dir in sorted(path for path in oos_root.iterdir() if path.is_dir()):
        rows.extend(build_task_folder_inventory(class_dir, trap_root))
    return rows


def _default_operator_config(family: str, seed_corner_count: int) -> dict[str, Any]:
    default_corner_index = 1 if seed_corner_count > 1 else 0
    if family == "corner_drift":
        return {"corner_index": default_corner_index}
    if family == "corner_duplicate":
        return {"corner_index": default_corner_index, "new_points": 1}
    if family in {"overextend_adjacent", "over_parsing"}:
        return {
            "approved_edge_index": min(default_corner_index, max(seed_corner_count - 1, 0)),
            "surrogate_mode": True,
        }
    return {}


def _apply_operator_family(
    *,
    corners_norm: list[dict[str, Any]],
    image_width: int,
    image_height: int,
    seed_token: str,
    family: str,
    lambda_level: str,
) -> dict[str, Any]:
    operator = OPERATOR_REGISTRY[family]
    config = _default_operator_config(family, len(corners_norm))
    result = operator.apply(
        corners_norm=corners_norm,
        image_width=image_width,
        image_height=image_height,
        seed=_stable_seed_from_task_and_family(seed_token, family),
        lambda_level=lambda_level,
        config=config,
    )
    return {
        "config": config,
        "status": result["status"],
        "failure_code": result.get("failure_code"),
        "audit": result.get("audit", {}),
        "generated_corners_norm": result.get("corners_norm", []),
        "generated_runtime_pairs": canonical_corners_to_runtime_pairs(
            result.get("corners_norm", []),
            image_width,
            image_height,
        ),
    }


def build_synthetic_candidate_bank(
    trap_root: Path,
    seed_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    detail_rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()

    for seed_row in seed_rows:
        txt_path = trap_root / seed_row["layout_txt_path"]
        corners = read_layout_txt_as_corners(txt_path)
        for preset in DEFAULT_SYNTHETIC_PRESET:
            family = preset["family"]
            lambda_level = preset["lambda_level"]
            generated = _apply_operator_family(
                corners_norm=corners,
                image_width=LAYOUT_TXT_WIDTH,
                image_height=LAYOUT_TXT_HEIGHT,
                seed_token=seed_row["task_id"],
                family=family,
                lambda_level=lambda_level,
            )
            detail = {
                "candidate_id": f"seed{seed_row['task_id']}_{family}",
                "seed_task_id": seed_row["task_id"],
                "seed_base_task_id": seed_row["base_task_id"],
                "seed_priority_annotation": seed_row["priority_annotation"],
                "family": family,
                "lambda_level": lambda_level,
                "status": generated["status"],
                "failure_code": generated["failure_code"],
                "seed_corner_count": len(corners),
                "generated_corner_count": len(generated["generated_corners_norm"]),
                "config": generated["config"],
                "audit": generated["audit"],
                "source_layout_txt_path": seed_row["layout_txt_path"],
                "generated_corners_norm": generated["generated_corners_norm"],
                "generated_runtime_pairs": generated["generated_runtime_pairs"],
            }
            detail["audit_hash"] = _stable_hash(
                {
                    "candidate_id": detail["candidate_id"],
                    "generated_corners_norm": detail["generated_corners_norm"],
                    "audit": detail["audit"],
                }
            )
            detail_rows.append(detail)
            status_counts[generated["status"]] += 1

    return detail_rows, dict(status_counts)


def _phase1_item_by_id(phase1_manifest: dict[str, Any], item_id: str) -> dict[str, Any]:
    for item in phase1_manifest.get("items", []):
        if item.get("item_id") == item_id:
            return item
    raise KeyError(f"Missing phase1 item: {item_id}")


def build_summary(
    *,
    manual_rows: list[dict[str, Any]],
    seed_rows: list[dict[str, Any]],
    synthetic_detail_rows: list[dict[str, Any]],
    synthetic_status_counts: dict[str, int],
    phase1_manifest: dict[str, Any],
    semi_family_target: dict[str, Any],
) -> dict[str, Any]:
    manual_anchor_item = _phase1_item_by_id(
        phase1_manifest, "stage1_prescreen_manual_expert_anchor"
    )
    manual_counts = Counter(row["collection_class"] for row in manual_rows)
    control_target = 0
    for family_item in semi_family_target.get("family_target_allocations", []):
        if family_item.get("family") == "acceptable":
            control_target = int(family_item.get("target_count", 0))
            break

    return {
        "freeze_name": "trap_collection_candidate_freeze_v1",
        "source_root": "trap集",
        "layout_coord_contract": LAYOUT_COORD_CONTRACT,
        "manual": {
            "collected_candidate_count": len(manual_rows),
            "target_anchor_min": int(manual_anchor_item["thesis_target"]["min"]),
            "target_anchor_max": int(manual_anchor_item["thesis_target"]["max"]),
            "collection_count_satisfies_anchor_target": len(manual_rows)
            >= int(manual_anchor_item["thesis_target"]["min"]),
            "subclass_counts": dict(manual_counts),
            "priority_annotated_count": sum(
                1 for row in manual_rows if row.get("priority_annotation")
            ),
            "notes": [
                "This reflects the currently collected manual candidate pool in trap集/manual.",
                "Collection count satisfying the thesis target does not imply that expert annotation or Stage 1 joinable binding is already complete.",
            ],
        },
        "semi": {
            "acceptable_seed_count": len(seed_rows),
            "control_target": control_target,
            "acceptable_seed_count_satisfies_control_target": len(seed_rows) >= control_target
            if control_target
            else False,
            "default_synthetic_family_count": len(DEFAULT_SYNTHETIC_PRESET),
            "synthetic_candidate_count": len(synthetic_detail_rows),
            "synthetic_status_counts": synthetic_status_counts,
            "notes": [
                "The acceptable seed pool is candidate-only and not yet a thesis-facing final control freeze.",
                "The layout txt parser supports the current trap collection's pixel-coordinate point pairs and the older x y_ceil y_floor format under the same 1024x512 contract.",
                "The synthetic bank is generated from acceptable seeds as a candidate bank, not a final Stage 1 semi selection freeze.",
            ],
        },
    }


def build_family_policy(semi_family_target: dict[str, Any]) -> dict[str, Any]:
    target_by_family = {
        item.get("family"): int(item.get("target_count", 0))
        for item in semi_family_target.get("family_target_allocations", [])
    }
    policy_rows = []
    ordered_families = [
        "acceptable",
        "overextend_adjacent",
        "underextend",
        "over_parsing",
        "corner_drift",
        "corner_duplicate",
        "topology_failure",
        "fail",
    ]
    for family in ordered_families:
        if family == "acceptable":
            policy_rows.append(
                {
                    "family": family,
                    "role": "control",
                    "is_prescreen_core_family": False,
                    "natural_required_min": 0,
                    "synthetic_allowed": False,
                    "synthetic_only_if_absent": False,
                    "default_target_count": target_by_family.get(family, 0),
                    "notes": "Control family only; not part of the misleading-trap family allocation.",
                }
            )
            continue
        if family in {
            "overextend_adjacent",
            "over_parsing",
            "corner_drift",
            "corner_duplicate",
        }:
            policy_rows.append(
                {
                    "family": family,
                    "role": "trap_core",
                    "is_prescreen_core_family": True,
                    "natural_required_min": 1,
                    "synthetic_allowed": True,
                    "synthetic_only_if_absent": False,
                    "default_target_count": target_by_family.get(family, 0),
                    "notes": "Current thesis-facing core family: keep at least one natural case when available, then backfill with synthetic candidates.",
                }
            )
            continue
        if family == "underextend":
            policy_rows.append(
                {
                    "family": family,
                    "role": "trap_extension",
                    "is_prescreen_core_family": False,
                    "natural_required_min": 0,
                    "synthetic_allowed": True,
                    "synthetic_only_if_absent": False,
                    "default_target_count": target_by_family.get(family, 0),
                    "notes": "Extension family only in the current thesis-facing protocol; natural exemplars may be retained for audit or overflow, but it is not part of the default 4-family x 3 trap target.",
                }
            )
            continue
        if family == "topology_failure":
            policy_rows.append(
                {
                    "family": family,
                    "role": "audit_small_quota",
                    "is_prescreen_core_family": False,
                    "natural_required_min": 0,
                    "synthetic_allowed": True,
                    "synthetic_only_if_absent": True,
                    "default_target_count": target_by_family.get(family, 0),
                    "notes": "Optional audit-small-quota family; current protocol allows synthetic-only backfill when natural cases are absent.",
                }
            )
            continue
        policy_rows.append(
            {
                "family": family,
                "role": "optional_small_quota",
                "is_prescreen_core_family": False,
                "natural_required_min": 0,
                "synthetic_allowed": True,
                "synthetic_only_if_absent": False,
                "default_target_count": target_by_family.get(family, 0),
                "notes": "Optional / small-quota family, not a default prescreen core family.",
            }
        )

    return {
        "policy_name": "prescreen_semi_family_policy_v1",
        "policy_basis": [
            "docs/thesis_main/manuscript/overleaf_project/sections/02_方法.tex",
            "docs/thesis_main/manuscript/overleaf_project/sections/03_实验设置.tex",
            "analysis_results/c_manifests_20260311/prescreen_semi_family_target_v1.json",
        ],
        "families": policy_rows,
        "notes": [
            "Natural-first applies to currently thesis-facing core trap families only.",
            "This policy does not promote underextend to a default prescreen core family, because the current thesis-facing text still prioritizes the 4-family x 3 trap structure.",
        ],
    }


def _policy_row_by_family(family_policy: dict[str, Any], family: str) -> dict[str, Any]:
    for row in family_policy.get("families", []):
        if row.get("family") == family:
            return row
    raise KeyError(f"Missing family policy for {family}")


def _ambiguity_risk_from_priority_annotation(priority_annotation: str) -> str:
    text = str(priority_annotation or "")
    if any(token in text for token in ["不确定", "歧义"]):
        return "flagged_by_folder_annotation"
    if text:
        return "priority_flag_present"
    return "not_flagged_from_folder_name"


def build_semi_candidate_registry(
    *,
    seed_rows: list[dict[str, Any]],
    natural_trap_rows: list[dict[str, Any]],
    synthetic_detail_rows: list[dict[str, Any]],
    family_policy: dict[str, Any],
    tentative_control_base_task_ids: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for seed_row in seed_rows:
        rows.append(
            {
                "candidate_id": f"control_{seed_row['task_id']}",
                "base_task_id": seed_row["base_task_id"],
                "task_id": seed_row["task_id"],
                "family": "acceptable",
                "source_type": "control_natural",
                "repairability": "not_applicable_control",
                "ambiguity_risk": _ambiguity_risk_from_priority_annotation(
                    seed_row["priority_annotation"]
                ),
                "manual_anchor_eligible": False,
                "prescreen_trap_eligible": False,
                "selection_policy_bucket": _policy_row_by_family(
                    family_policy, "acceptable"
                )["role"],
                "priority_annotation": seed_row["priority_annotation"],
                "overlap_with_tentative_control_pool": True,
                "notes": "Acceptable natural seed; candidate control row only.",
            }
        )

    for natural_row in natural_trap_rows:
        family = natural_row["family"]
        policy_row = _policy_row_by_family(family_policy, family)
        rows.append(
            {
                "candidate_id": f"natural_{family}_{natural_row['task_id']}",
                "base_task_id": natural_row["base_task_id"],
                "task_id": natural_row["task_id"],
                "family": family,
                "source_type": "trap_natural",
                "repairability": "review_required_natural_case",
                "ambiguity_risk": _ambiguity_risk_from_priority_annotation(
                    natural_row["priority_annotation"]
                ),
                "manual_anchor_eligible": False,
                "prescreen_trap_eligible": True,
                "selection_policy_bucket": policy_row["role"],
                "priority_annotation": natural_row["priority_annotation"],
                "overlap_with_tentative_control_pool": False,
                "notes": f"Natural semi candidate from trap集/semi/{natural_row['collection_class']}.",
            }
        )

    for synthetic_row in synthetic_detail_rows:
        family = synthetic_row["family"]
        policy_row = _policy_row_by_family(family_policy, family)
        rows.append(
            {
                "candidate_id": synthetic_row["candidate_id"],
                "base_task_id": synthetic_row["seed_base_task_id"],
                "task_id": synthetic_row["seed_task_id"],
                "family": family,
                "source_type": "trap_synthetic",
                "repairability": "expected_repairable_by_operator_design",
                "ambiguity_risk": _ambiguity_risk_from_priority_annotation(
                    synthetic_row["seed_priority_annotation"]
                ),
                "manual_anchor_eligible": False,
                "prescreen_trap_eligible": True,
                "selection_policy_bucket": policy_row["role"],
                "priority_annotation": synthetic_row["seed_priority_annotation"],
                "overlap_with_tentative_control_pool": synthetic_row["seed_base_task_id"]
                in tentative_control_base_task_ids,
                "notes": "Synthetic candidate generated from acceptable seed pool; candidate-only until overlap with the control freeze is resolved.",
            }
        )

    return rows


def build_control_freeze(
    *,
    seed_rows: list[dict[str, Any]],
    manual_rows: list[dict[str, Any]],
    oos_rows: list[dict[str, Any]],
    synthetic_detail_rows: list[dict[str, Any]],
    control_target: int,
) -> dict[str, Any]:
    ordered_seed_rows = sorted(
        seed_rows,
        key=lambda row: (
            1 if row["priority_annotation"] else 0,
            int(row["task_id"] or 0),
        ),
    )
    selected_rows = ordered_seed_rows[:control_target]
    selected_base_task_ids = {row["base_task_id"] for row in selected_rows}
    manual_base_task_ids = {row["base_task_id"] for row in manual_rows}
    oos_base_task_ids = {row["base_task_id"] for row in oos_rows}
    synthetic_source_base_task_ids = {
        row["seed_base_task_id"] for row in synthetic_detail_rows
    }

    manual_overlap = sorted(selected_base_task_ids & manual_base_task_ids)
    oos_overlap = sorted(selected_base_task_ids & oos_base_task_ids)
    synthetic_source_overlap = sorted(
        selected_base_task_ids & synthetic_source_base_task_ids
    )
    flagged_rows = [
        row["task_folder_name"] for row in selected_rows if row["priority_annotation"]
    ]

    blocked_reasons = []
    if len(selected_rows) != control_target:
        blocked_reasons.append(
            f"selected control count = {len(selected_rows)}, below target = {control_target}"
        )
    if flagged_rows:
        blocked_reasons.append(
            "selected control pool still contains folder-level priority flags, so final keep/drop freeze remains pending"
        )
    if manual_overlap:
        blocked_reasons.append(
            "selected control rows overlap with the current manual candidate pool"
        )
    if oos_overlap:
        blocked_reasons.append(
            "selected control rows overlap with the current OOS candidate pool"
        )
    if synthetic_source_overlap:
        blocked_reasons.append(
            "current synthetic candidate bank is generated from the same base_task_ids tentatively selected as controls"
        )

    return {
        "freeze_name": "prescreen_semi_control_freeze_v3",
        "target_count": control_target,
        "selected_control_rows": [
            {
                "candidate_id": f"control_{row['task_id']}",
                "task_id": row["task_id"],
                "base_task_id": row["base_task_id"],
                "priority_annotation": row["priority_annotation"],
            }
            for row in selected_rows
        ],
        "selected_control_count": len(selected_rows),
        "manual_pool_overlap_count": len(manual_overlap),
        "manual_pool_overlap_base_task_ids": manual_overlap,
        "oos_pool_overlap_count": len(oos_overlap),
        "oos_pool_overlap_base_task_ids": oos_overlap,
        "synthetic_source_overlap_count": len(synthetic_source_overlap),
        "synthetic_source_overlap_base_task_ids": synthetic_source_overlap,
        "selection_ready": len(blocked_reasons) == 0,
        "blocked_reasons": blocked_reasons,
        "notes": [
            "This artifact freezes the current control-first default selection from the acceptable seed pool.",
            "It remains separate from the final trap freeze.",
        ],
    }


def build_natural_preselection(
    *,
    natural_trap_rows: list[dict[str, Any]],
    family_policy: dict[str, Any],
) -> dict[str, Any]:
    rows_by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in natural_trap_rows:
        rows_by_family[row["family"]].append(row)

    selected_natural_cases = []
    family_natural_coverage = []
    family_gap_after_natural_selection: dict[str, int] = {}
    excluded_for_ambiguity = []
    excluded_for_not_repairable = []

    for policy_row in family_policy.get("families", []):
        family = policy_row["family"]
        if not policy_row["is_prescreen_core_family"]:
            continue
        family_rows = sorted(
            rows_by_family.get(family, []),
            key=lambda row: (
                1 if row["priority_annotation"] else 0,
                int(row["task_id"] or 0),
            ),
        )
        available_count = len(family_rows)
        selected_row = family_rows[0] if family_rows else None
        selected_count = 1 if selected_row else 0
        gap = max(int(policy_row["default_target_count"]) - selected_count, 0)
        family_gap_after_natural_selection[family] = gap

        if selected_row:
            selected_natural_cases.append(
                {
                    "candidate_id": f"natural_{family}_{selected_row['task_id']}",
                    "task_id": selected_row["task_id"],
                    "base_task_id": selected_row["base_task_id"],
                    "family": family,
                    "priority_annotation": selected_row["priority_annotation"],
                }
            )

        for extra_row in family_rows[1:]:
            if (
                _ambiguity_risk_from_priority_annotation(extra_row["priority_annotation"])
                == "flagged_by_folder_annotation"
            ):
                excluded_for_ambiguity.append(
                    {
                        "task_id": extra_row["task_id"],
                        "base_task_id": extra_row["base_task_id"],
                        "family": family,
                        "reason": "folder-level ambiguity flag",
                    }
                )

        family_natural_coverage.append(
            {
                "family": family,
                "default_target_count": int(policy_row["default_target_count"]),
                "available_natural_count": available_count,
                "selected_natural_count": selected_count,
                "natural_required_min": int(policy_row["natural_required_min"]),
            }
        )

    extension_family_notes = []
    for family in ["underextend", "fail", "topology_failure"]:
        policy_row = _policy_row_by_family(family_policy, family)
        extension_family_notes.append(
            {
                "family": family,
                "available_natural_count": len(rows_by_family.get(family, [])),
                "role": policy_row["role"],
                "notes": policy_row["notes"],
            }
        )

    return {
        "selection_name": "prescreen_semi_trap_natural_preselection_v3",
        "selected_natural_cases": selected_natural_cases,
        "family_natural_coverage": family_natural_coverage,
        "family_gap_after_natural_selection": family_gap_after_natural_selection,
        "extension_family_notes": extension_family_notes,
        "excluded_for_ambiguity": excluded_for_ambiguity,
        "excluded_for_not_repairable": excluded_for_not_repairable,
        "notes": [
            "This natural-first preselection only fills the existence slot for current core trap families.",
            "Extension or optional-small-quota families are recorded separately and are not promoted to core by this artifact.",
        ],
    }


def build_synthetic_backfill(
    *,
    synthetic_detail_rows: list[dict[str, Any]],
    family_policy: dict[str, Any],
    control_freeze: dict[str, Any],
    natural_preselection: dict[str, Any],
) -> dict[str, Any]:
    del family_policy
    selected_control_base_task_ids = {
        row["base_task_id"] for row in control_freeze.get("selected_control_rows", [])
    }
    synthetic_by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in synthetic_detail_rows:
        synthetic_by_family[row["family"]].append(row)

    selected_synthetic_backfill = []
    remaining_gap_after_backfill = dict(
        natural_preselection.get("family_gap_after_natural_selection", {})
    )
    blocked_reasons = []

    for family, gap in list(remaining_gap_after_backfill.items()):
        if gap <= 0:
            continue
        candidates = [
            row
            for row in synthetic_by_family.get(family, [])
            if row["seed_base_task_id"] not in selected_control_base_task_ids
            and row["status"] == "success"
        ]
        candidates = sorted(
            candidates,
            key=lambda row: (
                1 if row["seed_priority_annotation"] else 0,
                int(row["seed_task_id"] or 0),
            ),
        )
        selected = candidates[:gap]
        for row in selected:
            selected_synthetic_backfill.append(
                {
                    "candidate_id": row["candidate_id"],
                    "seed_task_id": row["seed_task_id"],
                    "base_task_id": row["seed_base_task_id"],
                    "family": family,
                    "lambda_level": row["lambda_level"],
                }
            )
        remaining_gap_after_backfill[family] = max(gap - len(selected), 0)
        if gap > 0 and not candidates:
            blocked_reasons.append(
                f"family {family} has no synthetic backfill candidates disjoint from the tentative control freeze"
            )

    if control_freeze.get("synthetic_source_overlap_count", 0) > 0:
        blocked_reasons.append(
            "current synthetic candidate bank reuses the same base_task_ids tentatively selected for control, so backfill cannot be finalized until source/control overlap is resolved"
        )

    return {
        "selection_name": "prescreen_semi_trap_backfill_v3",
        "selected_synthetic_backfill": selected_synthetic_backfill,
        "remaining_gap_after_backfill": remaining_gap_after_backfill,
        "blocked_reasons": blocked_reasons,
        "notes": [
            "Synthetic backfill is only allowed to fill the current core-family gap after natural-first preselection.",
            "This artifact does not produce a final trap freeze when the available synthetic source pool overlaps the tentative control freeze.",
        ],
    }


def _base_task_id_from_title_or_image(task_payload: dict[str, Any]) -> str:
    data = task_payload.get("data", {})
    title = str(data.get("title") or "").strip()
    if title:
        return Path(title).stem

    image_url = str(data.get("image") or "").strip()
    if image_url:
        parsed = urlparse(image_url)
        return Path(parsed.path or image_url).stem
    return ""


def load_label_studio_import_lookup(path: Path) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for task_payload in load_json_list(path):
        base_task_id = _base_task_id_from_title_or_image(task_payload)
        if base_task_id and base_task_id not in lookup:
            lookup[base_task_id] = task_payload
    return lookup


def build_legacy_disjoint_source_pool(
    *,
    legacy_perturbation_plan: dict[str, Any],
    semi_import_lookup: dict[str, dict[str, Any]],
    manual_rows: list[dict[str, Any]],
    control_freeze: dict[str, Any],
    oos_rows: list[dict[str, Any]],
    natural_preselection: dict[str, Any],
) -> dict[str, Any]:
    manual_base_task_ids = {row["base_task_id"] for row in manual_rows}
    control_base_task_ids = {
        row["base_task_id"] for row in control_freeze.get("selected_control_rows", [])
    }
    oos_base_task_ids = {row["base_task_id"] for row in oos_rows}
    natural_selected_base_task_ids = {
        row["base_task_id"] for row in natural_preselection.get("selected_natural_cases", [])
    }

    source_refs: dict[str, dict[str, Any]] = {}
    for perturbation in legacy_perturbation_plan.get("perturbations", []):
        base_task_id = str(perturbation.get("base_task_id") or "").strip()
        if not base_task_id:
            continue
        row = source_refs.setdefault(
            base_task_id,
            {
                "base_task_id": base_task_id,
                "title": str(perturbation.get("title") or "").strip(),
                "legacy_manifest_row_ids": [],
                "legacy_operator_ids": [],
            },
        )
        if perturbation.get("manifest_row_id") not in row["legacy_manifest_row_ids"]:
            row["legacy_manifest_row_ids"].append(perturbation.get("manifest_row_id"))
        if perturbation.get("operator_id") not in row["legacy_operator_ids"]:
            row["legacy_operator_ids"].append(perturbation.get("operator_id"))

    included_rows: list[dict[str, Any]] = []
    excluded_rows: list[dict[str, Any]] = []

    for base_task_id, source_ref in source_refs.items():
        exclusion_reason = ""
        if base_task_id in control_base_task_ids:
            exclusion_reason = "overlap_with_current_control_pool"
        elif base_task_id in manual_base_task_ids:
            exclusion_reason = "overlap_with_current_manual_candidate_pool"
        elif base_task_id in oos_base_task_ids:
            exclusion_reason = "overlap_with_current_oos_candidate_pool"
        elif base_task_id in natural_selected_base_task_ids:
            exclusion_reason = "overlap_with_current_natural_trap_selection"

        task_payload = semi_import_lookup.get(base_task_id)
        if not exclusion_reason and not task_payload:
            exclusion_reason = "missing_stage1_prescreen_semi_import_task"

        predictions = task_payload.get("predictions", []) if task_payload else []
        prediction_result = predictions[0].get("result", []) if predictions else []
        prediction_score = float(predictions[0].get("score") or 0.0) if predictions else 0.0
        corners_norm, prediction_meta = ls_keypoints_to_canonical_corners(prediction_result)

        if not exclusion_reason and not prediction_result:
            exclusion_reason = "missing_prediction_result"
        elif not exclusion_reason and not corners_norm:
            exclusion_reason = "unparseable_prediction_keypoints"
        elif not exclusion_reason and prediction_meta.get("pair_coverage", 0.0) < 1.0:
            exclusion_reason = "incomplete_keypoint_pair_coverage"
        elif not exclusion_reason and len(corners_norm) < 4:
            exclusion_reason = "insufficient_prediction_corners"

        if exclusion_reason:
            excluded_rows.append(
                {
                    "base_task_id": base_task_id,
                    "title": source_ref["title"],
                    "legacy_manifest_row_ids": source_ref["legacy_manifest_row_ids"],
                    "legacy_operator_ids": source_ref["legacy_operator_ids"],
                    "exclusion_reason": exclusion_reason,
                }
            )
            continue

        included_rows.append(
            {
                "source_candidate_id": f"legacy_disjoint_source_{len(included_rows) + 1:03d}",
                "base_task_id": base_task_id,
                "title": source_ref["title"],
                "legacy_manifest_row_ids": source_ref["legacy_manifest_row_ids"],
                "legacy_operator_ids": source_ref["legacy_operator_ids"],
                "image_url": str(task_payload.get("data", {}).get("image") or ""),
                "image_width": int(prediction_meta["width"]),
                "image_height": int(prediction_meta["height"]),
                "n_corners": len(corners_norm),
                "pair_coverage": float(prediction_meta["pair_coverage"]),
                "prediction_score": prediction_score,
                "source_selection_basis": "legacy_reviewed_20260311_perturbation_source_filtered_disjoint",
                "corners_norm": corners_norm,
                "runtime_pairs": canonical_corners_to_runtime_pairs(
                    corners_norm,
                    int(prediction_meta["width"]),
                    int(prediction_meta["height"]),
                ),
            }
        )

    excluded_counts_by_reason = Counter(row["exclusion_reason"] for row in excluded_rows)
    return {
        "freeze_name": "prescreen_semi_source_pool_freeze_v1",
        "source_basis": [
            "analysis_results/c_manifests_20260311/perturbation_plan_frozen_v1.json",
            "import_json/outline_v2_seed20260228/stage1_prescreen_semi_import.json",
        ],
        "source_candidate_count": len(included_rows),
        "source_base_task_ids": [row["base_task_id"] for row in included_rows],
        "current_source_rows": [
            {
                "source_candidate_id": row["source_candidate_id"],
                "base_task_id": row["base_task_id"],
                "title": row["title"],
                "image_width": row["image_width"],
                "image_height": row["image_height"],
                "n_corners": row["n_corners"],
                "pair_coverage": row["pair_coverage"],
                "prediction_score": row["prediction_score"],
                "legacy_manifest_row_ids": row["legacy_manifest_row_ids"],
                "legacy_operator_ids": row["legacy_operator_ids"],
            }
            for row in included_rows
        ],
        "control_overlap_count": int(
            excluded_counts_by_reason.get("overlap_with_current_control_pool", 0)
        ),
        "manual_overlap_count": int(
            excluded_counts_by_reason.get("overlap_with_current_manual_candidate_pool", 0)
        ),
        "oos_overlap_count": int(
            excluded_counts_by_reason.get("overlap_with_current_oos_candidate_pool", 0)
        ),
        "natural_trap_overlap_count": int(
            excluded_counts_by_reason.get("overlap_with_current_natural_trap_selection", 0)
        ),
        "excluded_counts_by_reason": dict(excluded_counts_by_reason),
        "excluded_rows": excluded_rows,
        "source_pool_ready": len(included_rows) > 0,
        "source_rows_full": included_rows,
        "notes": [
            "This source pool is derived from the 20260311 reviewed perturbation plan, then filtered against the current control/manual/OOS/natural-trap selections.",
            "The source pool is a synthetic-generation asset only; it is not itself a final Stage 1 selection freeze.",
        ],
    }


def build_disjoint_synthetic_candidate_bank(
    source_pool_freeze: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    detail_rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()

    for source_row in source_pool_freeze.get("source_rows_full", []):
        corners = source_row["corners_norm"]
        for preset in DEFAULT_SYNTHETIC_PRESET:
            family = preset["family"]
            lambda_level = preset["lambda_level"]
            generated = _apply_operator_family(
                corners_norm=corners,
                image_width=int(source_row["image_width"]),
                image_height=int(source_row["image_height"]),
                seed_token=source_row["base_task_id"],
                family=family,
                lambda_level=lambda_level,
            )
            detail = {
                "candidate_id": f"{source_row['source_candidate_id']}_{family}",
                "source_candidate_id": source_row["source_candidate_id"],
                "source_base_task_id": source_row["base_task_id"],
                "source_title": source_row["title"],
                "family": family,
                "lambda_level": lambda_level,
                "status": generated["status"],
                "failure_code": generated["failure_code"],
                "source_corner_count": len(corners),
                "generated_corner_count": len(generated["generated_corners_norm"]),
                "config": generated["config"],
                "audit": generated["audit"],
                "generated_corners_norm": generated["generated_corners_norm"],
                "generated_runtime_pairs": generated["generated_runtime_pairs"],
            }
            detail["audit_hash"] = _stable_hash(
                {
                    "candidate_id": detail["candidate_id"],
                    "generated_corners_norm": detail["generated_corners_norm"],
                    "audit": detail["audit"],
                }
            )
            detail_rows.append(detail)
            status_counts[generated["status"]] += 1

    return detail_rows, dict(status_counts)


def build_synthetic_backfill_v4(
    *,
    synthetic_detail_rows: list[dict[str, Any]],
    control_freeze: dict[str, Any],
    natural_preselection: dict[str, Any],
) -> dict[str, Any]:
    selected_control_base_task_ids = {
        row["base_task_id"] for row in control_freeze.get("selected_control_rows", [])
    }
    selected_natural_base_task_ids = {
        row["base_task_id"] for row in natural_preselection.get("selected_natural_cases", [])
    }
    remaining_gap_after_backfill = dict(
        natural_preselection.get("family_gap_after_natural_selection", {})
    )
    synthetic_by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in synthetic_detail_rows:
        synthetic_by_family[row["family"]].append(row)

    selected_synthetic_backfill = []
    blocked_reasons = []
    used_source_base_task_ids: set[str] = set()

    family_order = sorted(
        remaining_gap_after_backfill,
        key=lambda family: (
            len(
                [
                    row
                    for row in synthetic_by_family.get(family, [])
                    if row["source_base_task_id"] not in selected_control_base_task_ids
                    and row["source_base_task_id"] not in selected_natural_base_task_ids
                    and row["status"] == "success"
                ]
            ),
            -int(remaining_gap_after_backfill[family]),
            family,
        ),
    )

    for family in family_order:
        gap = int(remaining_gap_after_backfill.get(family, 0))
        if gap <= 0:
            continue
        candidates = [
            row
            for row in synthetic_by_family.get(family, [])
            if row["source_base_task_id"] not in selected_control_base_task_ids
            and row["source_base_task_id"] not in selected_natural_base_task_ids
            and row["status"] == "success"
        ]
        candidates = sorted(candidates, key=lambda row: (row["source_base_task_id"], row["candidate_id"]))
        selected = []
        for row in candidates:
            source_base_task_id = row["source_base_task_id"]
            if source_base_task_id in used_source_base_task_ids:
                continue
            selected.append(row)
            used_source_base_task_ids.add(source_base_task_id)
            if len(selected) >= gap:
                break
        for row in selected:
            selected_synthetic_backfill.append(
                {
                    "candidate_id": row["candidate_id"],
                    "source_candidate_id": row["source_candidate_id"],
                    "base_task_id": row["source_base_task_id"],
                    "family": family,
                    "lambda_level": row["lambda_level"],
                }
            )
        remaining_gap_after_backfill[family] = max(gap - len(selected), 0)
        if remaining_gap_after_backfill[family] > 0:
            blocked_reasons.append(
                f"family {family} still lacks {remaining_gap_after_backfill[family]} synthetic backfill rows after applying the disjoint source pool"
            )

    return {
        "selection_name": "prescreen_semi_trap_backfill_v4",
        "source_pool_freeze_name": "prescreen_semi_source_pool_freeze_v1",
        "selected_synthetic_backfill": selected_synthetic_backfill,
        "selected_source_base_task_ids": sorted(used_source_base_task_ids),
        "remaining_gap_after_backfill": remaining_gap_after_backfill,
        "blocked_reasons": blocked_reasons,
        "notes": [
            "This backfill uses only the filtered legacy disjoint source pool.",
            "Natural existence slots remain occupied by the natural-first preselection and are not replaced by synthetic rows.",
            "Synthetic backfill now prefers globally unique source base_task_id values across families.",
        ],
    }


def build_final_selection_v4(
    *,
    control_freeze: dict[str, Any],
    natural_preselection: dict[str, Any],
    synthetic_backfill_v4: dict[str, Any],
    family_policy: dict[str, Any],
    manual_rows: list[dict[str, Any]],
    oos_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    selected_control_rows = [
        {
            "candidate_id": row["candidate_id"],
            "task_id": row["task_id"],
            "base_task_id": row["base_task_id"],
            "priority_annotation": row.get("priority_annotation", ""),
            "selection_status": "tentative_control_selected",
        }
        for row in control_freeze.get("selected_control_rows", [])
    ]

    selected_trap_rows = []
    for row in natural_preselection.get("selected_natural_cases", []):
        selected_trap_rows.append(
            {
                "candidate_id": row["candidate_id"],
                "base_task_id": row["base_task_id"],
                "family": row["family"],
                "source_type": "trap_natural",
                "selection_status": "natural_first_selected",
            }
        )
    for row in synthetic_backfill_v4.get("selected_synthetic_backfill", []):
        selected_trap_rows.append(
            {
                "candidate_id": row["candidate_id"],
                "base_task_id": row["base_task_id"],
                "family": row["family"],
                "source_type": "trap_synthetic_disjoint_source",
                "selection_status": "synthetic_backfill_selected",
            }
        )

    control_base_task_ids = [row["base_task_id"] for row in selected_control_rows]
    trap_base_task_ids = [row["base_task_id"] for row in selected_trap_rows]
    manual_base_task_ids = {row["base_task_id"] for row in manual_rows}
    oos_base_task_ids = {row["base_task_id"] for row in oos_rows}
    natural_base_task_ids = {
        row["base_task_id"] for row in natural_preselection.get("selected_natural_cases", [])
    }
    synthetic_base_task_ids = {
        row["base_task_id"] for row in synthetic_backfill_v4.get("selected_synthetic_backfill", [])
    }

    control_priority_flag_rows = [
        row["base_task_id"] for row in selected_control_rows if row.get("priority_annotation")
    ]
    control_trap_overlap = sorted(set(control_base_task_ids) & set(trap_base_task_ids))
    trap_manual_overlap = sorted(set(trap_base_task_ids) & manual_base_task_ids)
    trap_oos_overlap = sorted(set(trap_base_task_ids) & oos_base_task_ids)
    natural_synthetic_overlap = sorted(natural_base_task_ids & synthetic_base_task_ids)
    duplicate_trap_base_task_ids = sorted(
        base_task_id
        for base_task_id, count in Counter(trap_base_task_ids).items()
        if count > 1
    )

    family_counts = Counter(row["family"] for row in selected_trap_rows)
    family_source_breakdown: dict[str, dict[str, int]] = defaultdict(
        lambda: {"natural": 0, "synthetic": 0}
    )
    for row in selected_trap_rows:
        source_key = "natural" if row["source_type"] == "trap_natural" else "synthetic"
        family_source_breakdown[row["family"]][source_key] += 1

    family_allocations = []
    for policy_row in family_policy.get("families", []):
        family = policy_row["family"]
        if family == "acceptable":
            family_allocations.append(
                {
                    "family": family,
                    "target_count": int(policy_row["default_target_count"]),
                    "current_selected_count": len(selected_control_rows),
                    "current_natural_count": len(selected_control_rows),
                    "current_synthetic_count": 0,
                    "role": policy_row["role"],
                }
            )
            continue
        if policy_row["role"] != "trap_core":
            continue
        family_allocations.append(
            {
                "family": family,
                "target_count": int(policy_row["default_target_count"]),
                "current_selected_count": int(family_counts.get(family, 0)),
                "current_natural_count": int(
                    family_source_breakdown.get(family, {}).get("natural", 0)
                ),
                "current_synthetic_count": int(
                    family_source_breakdown.get(family, {}).get("synthetic", 0)
                ),
                "role": policy_row["role"],
            }
        )

    blocked_reasons = []
    if len(selected_control_rows) != 6:
        blocked_reasons.append(f"selected control count = {len(selected_control_rows)}, below target = 6")
    if len(selected_trap_rows) != 12:
        blocked_reasons.append(f"selected trap count = {len(selected_trap_rows)}, below target = 12")
    for row in family_allocations:
        if row["family"] == "acceptable":
            continue
        if row["current_selected_count"] != row["target_count"]:
            blocked_reasons.append(
                f"family {row['family']} selected count = {row['current_selected_count']}, target = {row['target_count']}"
            )
        if row["current_natural_count"] < 1:
            blocked_reasons.append(f"family {row['family']} lacks the required natural existence slot")
    if control_priority_flag_rows:
        blocked_reasons.append(
            "selected control pool still contains folder-level priority flags, so the control keep/drop freeze remains pending"
        )
    if control_trap_overlap:
        blocked_reasons.append("control and trap selections overlap by base_task_id")
    if trap_manual_overlap:
        blocked_reasons.append("selected trap rows overlap with the current manual candidate pool")
    if trap_oos_overlap:
        blocked_reasons.append("selected trap rows overlap with the current OOS candidate pool")
    if natural_synthetic_overlap:
        blocked_reasons.append("natural and synthetic trap selections overlap by base_task_id")
    if duplicate_trap_base_task_ids:
        blocked_reasons.append("selected trap rows contain duplicated base_task_id values")

    return {
        "selection_name": "prescreen_semi_final_selection_v4",
        "selection_scope": "stage1_prescreen_semi",
        "target_total": 18,
        "control_target": 6,
        "trap_target": 12,
        "selected_control_rows": selected_control_rows,
        "selected_trap_rows": selected_trap_rows,
        "current_selected_control_count": len(selected_control_rows),
        "current_selected_trap_count": len(selected_trap_rows),
        "family_allocations": family_allocations,
        "control_priority_flag_rows": control_priority_flag_rows,
        "control_trap_overlap_count": len(control_trap_overlap),
        "control_trap_overlap_base_task_ids": control_trap_overlap,
        "trap_manual_overlap_count": len(trap_manual_overlap),
        "trap_manual_overlap_base_task_ids": trap_manual_overlap,
        "trap_oos_overlap_count": len(trap_oos_overlap),
        "trap_oos_overlap_base_task_ids": trap_oos_overlap,
        "natural_synthetic_overlap_count": len(natural_synthetic_overlap),
        "natural_synthetic_overlap_base_task_ids": natural_synthetic_overlap,
        "duplicate_trap_base_task_id_count": len(duplicate_trap_base_task_ids),
        "duplicate_trap_base_task_ids": duplicate_trap_base_task_ids,
        "control_binding_ready": len(selected_control_rows) == 6 and not control_priority_flag_rows,
        "trap_binding_ready": len(selected_trap_rows) == 12
        and not control_trap_overlap
        and not trap_manual_overlap
        and not trap_oos_overlap
        and not natural_synthetic_overlap
        and not duplicate_trap_base_task_ids,
        "selection_ready": len(blocked_reasons) == 0,
        "blocked_reasons": blocked_reasons,
        "notes": [
            "Trap-side family coverage is now selected through natural-first plus disjoint synthetic backfill.",
            "This artifact still does not claim Stage 1 executable readiness when the control keep/drop freeze remains pending.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze trap collection candidate pools from trap集 and build acceptable-seed synthetic semi candidates."
    )
    parser.add_argument("--trap-root", default="trap集")
    parser.add_argument(
        "--phase1-manifest",
        default="analysis_results/phase1_progress_20260311/phase1_target_vs_realized_manifest_v1.json",
    )
    parser.add_argument(
        "--semi-family-target",
        default="analysis_results/c_manifests_20260311/prescreen_semi_family_target_v1.json",
    )
    parser.add_argument(
        "--legacy-perturbation-plan",
        default="analysis_results/c_manifests_20260311/perturbation_plan_frozen_v1.json",
    )
    parser.add_argument(
        "--semi-import-json",
        default="import_json/outline_v2_seed20260228/stage1_prescreen_semi_import.json",
    )
    parser.add_argument(
        "--output-dir", default="analysis_results/trap_collection_freeze_20260320"
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    trap_root = root / args.trap_root
    output_dir = root / args.output_dir
    phase1_manifest = load_phase1_manifest(root / args.phase1_manifest)
    semi_family_target = load_json(root / args.semi_family_target)
    legacy_perturbation_plan = load_json(root / args.legacy_perturbation_plan)
    semi_import_lookup = load_label_studio_import_lookup(root / args.semi_import_json)

    manual_rows = build_manual_pool(trap_root / "manual", trap_root)
    seed_rows = build_acceptable_seed_pool(trap_root / "semi", trap_root)
    natural_trap_rows = build_semi_natural_trap_pool(trap_root / "semi", trap_root)
    oos_rows = build_oos_candidate_pool(trap_root / "OOS", trap_root)
    synthetic_detail_rows, synthetic_status_counts = build_synthetic_candidate_bank(
        trap_root, seed_rows
    )
    family_policy = build_family_policy(semi_family_target)

    control_target = 0
    for row in semi_family_target.get("family_target_allocations", []):
        if row.get("family") == "acceptable":
            control_target = int(row.get("target_count", 0))
            break

    control_freeze = build_control_freeze(
        seed_rows=seed_rows,
        manual_rows=manual_rows,
        oos_rows=oos_rows,
        synthetic_detail_rows=synthetic_detail_rows,
        control_target=control_target,
    )
    candidate_registry_rows = build_semi_candidate_registry(
        seed_rows=seed_rows,
        natural_trap_rows=natural_trap_rows,
        synthetic_detail_rows=synthetic_detail_rows,
        family_policy=family_policy,
        tentative_control_base_task_ids={
            row["base_task_id"] for row in control_freeze["selected_control_rows"]
        },
    )
    natural_preselection = build_natural_preselection(
        natural_trap_rows=natural_trap_rows,
        family_policy=family_policy,
    )
    source_pool_freeze = build_legacy_disjoint_source_pool(
        legacy_perturbation_plan=legacy_perturbation_plan,
        semi_import_lookup=semi_import_lookup,
        manual_rows=manual_rows,
        control_freeze=control_freeze,
        oos_rows=oos_rows,
        natural_preselection=natural_preselection,
    )
    disjoint_synthetic_rows, _ = build_disjoint_synthetic_candidate_bank(
        source_pool_freeze
    )
    synthetic_backfill_v3 = build_synthetic_backfill(
        synthetic_detail_rows=synthetic_detail_rows,
        family_policy=family_policy,
        control_freeze=control_freeze,
        natural_preselection=natural_preselection,
    )
    synthetic_backfill_v4 = build_synthetic_backfill_v4(
        synthetic_detail_rows=disjoint_synthetic_rows,
        control_freeze=control_freeze,
        natural_preselection=natural_preselection,
    )
    final_selection_v4 = build_final_selection_v4(
        control_freeze=control_freeze,
        natural_preselection=natural_preselection,
        synthetic_backfill_v4=synthetic_backfill_v4,
        family_policy=family_policy,
        manual_rows=manual_rows,
        oos_rows=oos_rows,
    )
    summary = build_summary(
        manual_rows=manual_rows,
        seed_rows=seed_rows,
        synthetic_detail_rows=synthetic_detail_rows,
        synthetic_status_counts=synthetic_status_counts,
        phase1_manifest=phase1_manifest,
        semi_family_target=semi_family_target,
    )

    manual_csv_rows = [
        {key: row.get(key, "") for key in MANUAL_POOL_FIELDNAMES} for row in manual_rows
    ]
    seed_csv_rows = [
        {key: row.get(key, "") for key in SEED_POOL_FIELDNAMES} for row in seed_rows
    ]
    synthetic_csv_rows = [
        {key: row.get(key, "") for key in SYNTHETIC_BANK_FIELDNAMES}
        for row in synthetic_detail_rows
    ]
    disjoint_synthetic_csv_rows = [
        {key: row.get(key, "") for key in DISJOINT_SYNTHETIC_BANK_FIELDNAMES}
        for row in disjoint_synthetic_rows
    ]

    _write_csv(
        output_dir / "manual_candidate_pool_v1.csv",
        manual_csv_rows,
        MANUAL_POOL_FIELDNAMES,
    )
    _write_csv(
        output_dir / "semi_acceptable_seed_pool_v1.csv",
        seed_csv_rows,
        SEED_POOL_FIELDNAMES,
    )
    _write_csv(
        output_dir / "semi_synthetic_candidate_bank_v1.csv",
        synthetic_csv_rows,
        SYNTHETIC_BANK_FIELDNAMES,
    )
    _write_csv(
        output_dir / "semi_synthetic_disjoint_candidate_bank_v2.csv",
        disjoint_synthetic_csv_rows,
        DISJOINT_SYNTHETIC_BANK_FIELDNAMES,
    )
    _write_csv(
        output_dir / "prescreen_semi_candidate_registry_v2.csv",
        [
            {key: row.get(key, "") for key in SEMI_CANDIDATE_REGISTRY_FIELDNAMES}
            for row in candidate_registry_rows
        ],
        SEMI_CANDIDATE_REGISTRY_FIELDNAMES,
    )
    _write_jsonl(output_dir / "semi_synthetic_candidate_bank_v1.jsonl", synthetic_detail_rows)
    _write_jsonl(
        output_dir / "semi_synthetic_disjoint_candidate_bank_v2.jsonl",
        disjoint_synthetic_rows,
    )
    _write_json(output_dir / "prescreen_semi_family_policy_v1.json", family_policy)
    _write_json(output_dir / "prescreen_semi_control_freeze_v3.json", control_freeze)
    _write_json(
        output_dir / "prescreen_semi_trap_natural_preselection_v3.json",
        natural_preselection,
    )
    _write_json(
        output_dir / "prescreen_semi_source_pool_freeze_v1.json",
        {
            key: value
            for key, value in source_pool_freeze.items()
            if key != "source_rows_full"
        },
    )
    _write_json(output_dir / "prescreen_semi_trap_backfill_v3.json", synthetic_backfill_v3)
    _write_json(output_dir / "prescreen_semi_trap_backfill_v4.json", synthetic_backfill_v4)
    _write_json(output_dir / "prescreen_semi_final_selection_v4.json", final_selection_v4)
    _write_json(output_dir / "trap_collection_summary_v1.json", summary)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
