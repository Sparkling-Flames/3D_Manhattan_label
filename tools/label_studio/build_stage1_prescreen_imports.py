from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

try:
    from tools.thesis_main.registry.freeze_trap_collection import read_layout_txt_as_corners
    from tools.thesis_main.registry.perturbation_operators import canonical_corners_to_runtime_pairs
except ModuleNotFoundError:  # pragma: no cover
    from freeze_trap_collection import read_layout_txt_as_corners
    from perturbation_operators import canonical_corners_to_runtime_pairs


IMAGE_WIDTH = 1024
IMAGE_HEIGHT = 512
DEFAULT_IMAGE_BASE_URL = os.environ.get(
    "HOHONET_IMAGE_BASE_URL",
    "https://label-images-1389474327.cos.ap-guangzhou.myqcloud.com/data/mp3d_layout/img_v",
)
DEFAULT_VIS_BASE_URL = os.environ.get(
    "HOHONET_VIS_BASE_URL",
    os.environ.get("HOHONET_BASE_URL", "http://175.178.71.217:8000"),
)

PHASE1_DIR = "analysis_results/phase1_progress_20260324"
FINAL_GOLD_DIR = "analysis_results/final_gold_layer_20260325"
TRAP_COLLECTION_DIR = "analysis_results/trap_collection_freeze_20260320"
OUTPUT_DIR = "import_json/stage1_prescreen_final_20260325"
MODEL_OUTPUT_TXT_DIR = "output/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34"
CURRENT_SEMI_SELECTION_NAME = "prescreen_semi_final_selection_v10.json"
OOS_FAMILY_TO_SCOPE_ALIAS = {
    "边界不可判定": "oos_open_boundary",
    "几何假设不成立(弧形墙)": "oos_geometry",
    "错层,天花板下凸": "oos_split_level",
    "证据不足": "oos_insufficient",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_image_url(base_task_id: str) -> str:
    return f"{DEFAULT_IMAGE_BASE_URL.rstrip('/')}/{base_task_id}.jpg"


def _build_vis3d_url(runtime_pairs: list[dict[str, Any]]) -> str:
    payload = quote(json.dumps(runtime_pairs, ensure_ascii=False))
    return (
        f"{DEFAULT_VIS_BASE_URL.rstrip('/')}/tools/vis_3d.html"
        f"?w={IMAGE_WIDTH}&h={IMAGE_HEIGHT}&data={payload}"
    )


def _prediction_from_corners(corners_norm: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, corner in enumerate(corners_norm):
        x_pct = float(corner["x_pct"])
        y_top_pct = float(corner["y_top_pct"])
        y_bottom_pct = float(corner["y_bottom_pct"])
        result.append(
            {
                "id": f"kp_{index * 2}",
                "from_name": "kp",
                "to_name": "img",
                "type": "keypointlabels",
                "original_width": IMAGE_WIDTH,
                "original_height": IMAGE_HEIGHT,
                "value": {
                    "x": x_pct,
                    "y": y_top_pct,
                    "width": 0.5,
                    "keypointlabels": ["Corner"],
                },
            }
        )
        result.append(
            {
                "id": f"kp_{index * 2 + 1}",
                "from_name": "kp",
                "to_name": "img",
                "type": "keypointlabels",
                "original_width": IMAGE_WIDTH,
                "original_height": IMAGE_HEIGHT,
                "value": {
                    "x": x_pct,
                    "y": y_bottom_pct,
                    "width": 0.5,
                    "keypointlabels": ["Corner"],
                },
            }
        )
    return result


def _prediction_payload(corners_norm: list[dict[str, Any]], *, model_version: str) -> list[dict[str, Any]]:
    return [{"model_version": model_version, "score": 0.99, "result": _prediction_from_corners(corners_norm)}]


def _sort_by_task_id(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: int(str(row["task_id"])))


def _scan_model_output_txt_map(repo_root: Path) -> dict[str, dict[str, str]]:
    output_root = repo_root / MODEL_OUTPUT_TXT_DIR
    out: dict[str, dict[str, str]] = {}
    for txt_path in sorted(output_root.glob("*.txt")):
        out[txt_path.stem] = {
            "txt_path": str(txt_path),
            "base_task_id": txt_path.stem,
            "title": f"{txt_path.stem}.jpg",
            "proposal_source_path": str(txt_path.relative_to(repo_root)),
        }
    return out


def load_inputs(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or _repo_root()
    phase1_dir = root / PHASE1_DIR
    final_gold_dir = root / FINAL_GOLD_DIR
    trap_collection_dir = root / TRAP_COLLECTION_DIR

    final_gold_rows = _read_jsonl(final_gold_dir / "final_gold_records_v1.jsonl")
    final_gold_by_task = {str(row["task_id"]): row for row in final_gold_rows}
    synthetic_rows = _read_jsonl(trap_collection_dir / "semi_synthetic_disjoint_candidate_bank_v2.jsonl")
    synthetic_by_candidate = {str(row["candidate_id"]): row for row in synthetic_rows}

    return {
        "repo_root": root,
        "manual_binding_v2": _read_json(phase1_dir / "manual_binding_audit_v2.json"),
        "semi_current": _read_json(phase1_dir / CURRENT_SEMI_SELECTION_NAME),
        "oos_binding_v2": _read_json(phase1_dir / "oos_final_quota_binding_v2.json"),
        "final_gold_by_task": final_gold_by_task,
        "synthetic_by_candidate": synthetic_by_candidate,
        "model_output_txt_map": _scan_model_output_txt_map(root),
    }


def _manual_task(row: dict[str, Any], gold_row: dict[str, Any]) -> dict[str, Any]:
    runtime_pairs = gold_row["runtime_pairs_1024x512"]
    base_task_id = str(row["base_task_id"])
    final_role = str(row["final_role"])
    return {
        "data": {
            "image": _build_image_url(base_task_id),
            "vis_3d": _build_vis3d_url(runtime_pairs),
            "title": f"{base_task_id}.jpg",
            "dataset_group": "PreScreen_manual",
            "condition": "manual",
            "task_id": str(row["task_id"]),
            "base_task_id": base_task_id,
            "final_role": final_role,
            "is_anchor": final_role == "expert_anchor",
            "has_expert_ref": final_role == "expert_anchor",
            "scope_gold": str(gold_row["final_scope_alias"]),
        }
    }


def _semi_task_from_txt(
    *,
    row: dict[str, Any],
    family: str,
    source_type: str,
    init_type: str,
    dataset_group: str,
    condition: str,
    semi_role: str,
    model_version: str,
    model_output_txt_map: dict[str, dict[str, str]],
) -> dict[str, Any]:
    task_id = str(row["task_id"])
    base_task_id = str(row["base_task_id"])
    txt_meta = model_output_txt_map.get(base_task_id)
    if not txt_meta:
        raise KeyError(f"Missing model output txt source for base_task_id {base_task_id}")
    corners_norm = read_layout_txt_as_corners(Path(txt_meta["txt_path"]))
    runtime_pairs = canonical_corners_to_runtime_pairs(corners_norm, IMAGE_WIDTH, IMAGE_HEIGHT)
    return {
        "data": {
            "image": _build_image_url(txt_meta["base_task_id"]),
            "vis_3d": _build_vis3d_url(runtime_pairs),
            "title": txt_meta["title"],
            "dataset_group": dataset_group,
            "condition": condition,
            "task_id": task_id,
            "base_task_id": base_task_id,
            "semi_role": semi_role,
            "trap_family": family,
            "init_type": init_type,
            "source_type": source_type,
            "proposal_source_kind": "model_output_txt",
            "proposal_source_path": txt_meta["proposal_source_path"],
            "proposal_coord_contract": "hohonet_model_output_layout_txt@1024x512",
        },
        "predictions": _prediction_payload(corners_norm, model_version=model_version),
    }


def _semi_task_from_synthetic(row: dict[str, Any], synthetic_row: dict[str, Any]) -> dict[str, Any]:
    corners_norm = synthetic_row["generated_corners_norm"]
    runtime_pairs = synthetic_row["generated_runtime_pairs"]
    base_task_id = str(synthetic_row["source_base_task_id"])
    return {
        "data": {
            "image": _build_image_url(base_task_id),
            "vis_3d": _build_vis3d_url(runtime_pairs),
            "title": str(synthetic_row["source_title"]),
            "dataset_group": "PreScreen_semi",
            "condition": "semi",
            "task_id": f"synthetic::{row['candidate_id']}",
            "base_task_id": base_task_id,
            "semi_role": "trap",
            "trap_family": str(row["family"]),
            "init_type": "misleading",
            "source_type": "trap_synthetic",
            "synthetic_candidate_id": str(row["candidate_id"]),
            "synthetic_rebind_status": str(row["rebind_status"]),
            "proposal_source_kind": "frozen_synthetic_asset",
            "proposal_coord_contract": "canonical_corners_norm_to_prediction_payload",
        },
        "predictions": _prediction_payload(corners_norm, model_version="HoHoNet_stage1_prescreen_v5"),
    }


def _oos_task(
    row: dict[str, Any],
    gold_row: dict[str, Any],
    *,
    final_role: str | None = None,
    scope_alias: str | None = None,
) -> dict[str, Any]:
    runtime_pairs = gold_row["runtime_pairs_1024x512"]
    base_task_id = str(row["base_task_id"])
    return {
        "data": {
            "image": _build_image_url(base_task_id),
            "vis_3d": _build_vis3d_url(runtime_pairs),
            "title": f"{base_task_id}.jpg",
            "dataset_group": "PreScreen_oos",
            "condition": "oos",
            "task_id": str(row["task_id"]),
            "base_task_id": base_task_id,
            "final_role": final_role or str(row["final_role"]),
            "family_dir": str(gold_row.get("family_dir", "")),
            "scope_target": scope_alias or str(row["gold_scope_alias"]),
            "scope_target_source": "final_gold_scope",
        }
    }


def build_import_payloads(inputs: dict[str, Any]) -> dict[str, Any]:
    manual_rows = _sort_by_task_id(inputs["manual_binding_v2"]["checked_rows"])
    semi_selection = inputs["semi_current"]
    semi_control_rows = semi_selection["selected_control_rows"]
    semi_trap_rows = semi_selection["selected_trap_rows"]
    oos_rows = _sort_by_task_id(inputs["oos_binding_v2"]["selected_oos_gate_rows"])
    audit_only_task_ids = {
        str(task_id) for task_id in inputs["oos_binding_v2"].get("low_priority_audit_only_task_ids", [])
    }
    audit_stress = semi_selection.get("audit_stress_candidates", {})
    audit_holdout = semi_selection.get("audit_stress_holdout_candidates", {})

    manual_tasks = [
        _manual_task(row, inputs["final_gold_by_task"][str(row["task_id"])]) for row in manual_rows
    ]

    semi_tasks: list[dict[str, Any]] = []
    for row in semi_control_rows:
        semi_tasks.append(
            _semi_task_from_txt(
                row=row,
                family="acceptable",
                source_type="control_natural",
                init_type="clean",
                dataset_group="PreScreen_semi",
                condition="semi",
                semi_role="control",
                model_version="HoHoNet_stage1_prescreen_v5",
                model_output_txt_map=inputs["model_output_txt_map"],
            )
        )
    for row in semi_trap_rows:
        source_type = str(row["source_type"])
        if source_type == "trap_natural":
            semi_tasks.append(
                _semi_task_from_txt(
                    row=row,
                    family=str(row["family"]),
                    source_type="trap_natural",
                    init_type="misleading",
                    dataset_group="PreScreen_semi",
                    condition="semi",
                    semi_role="trap",
                    model_version="HoHoNet_stage1_prescreen_v5",
                    model_output_txt_map=inputs["model_output_txt_map"],
                )
            )
            continue
        if source_type != "trap_synthetic_disjoint_source":
            raise ValueError(f"Unsupported semi trap source_type: {source_type}")
        synthetic_row = inputs["synthetic_by_candidate"].get(str(row["candidate_id"]))
        if not synthetic_row:
            raise KeyError(f"Missing synthetic asset: {row['candidate_id']}")
        semi_tasks.append(_semi_task_from_synthetic(row=row, synthetic_row=synthetic_row))

    semi_audit_stress_tasks: list[dict[str, Any]] = []
    for task_id in sorted({str(task_id) for task_id in audit_stress.get("fail_task_ids", [])}, key=int):
        gold_row = inputs["final_gold_by_task"].get(task_id)
        if not gold_row or str(gold_row.get("final_scope_binary")) != "in_scope":
            continue
        semi_audit_stress_tasks.append(
            _semi_task_from_txt(
                row={"task_id": task_id, "base_task_id": gold_row["base_task_id"]},
                family="fail",
                source_type="trap_natural_audit_only",
                init_type="misleading",
                dataset_group="PreScreen_semi_audit_stress",
                condition="semi_audit_stress",
                semi_role="audit_only",
                model_version="HoHoNet_stage1_prescreen_audit_v3",
                model_output_txt_map=inputs["model_output_txt_map"],
            )
        )
    for task_id in sorted(
        {str(task_id) for task_id in audit_stress.get("topology_failure_task_ids", [])},
        key=int,
    ):
        gold_row = inputs["final_gold_by_task"].get(task_id)
        if not gold_row or str(gold_row.get("final_scope_binary")) != "in_scope":
            continue
        semi_audit_stress_tasks.append(
            _semi_task_from_txt(
                row={"task_id": task_id, "base_task_id": gold_row["base_task_id"]},
                family="topology_failure",
                source_type="trap_natural_audit_only",
                init_type="misleading",
                dataset_group="PreScreen_semi_audit_stress",
                condition="semi_audit_stress",
                semi_role="audit_only",
                model_version="HoHoNet_stage1_prescreen_audit_v3",
                model_output_txt_map=inputs["model_output_txt_map"],
            )
        )

    semi_audit_holdout_tasks: list[dict[str, Any]] = []
    for task_id in sorted({str(task_id) for task_id in audit_holdout.get("fail_task_ids", [])}, key=int):
        gold_row = inputs["final_gold_by_task"].get(task_id)
        if not gold_row or str(gold_row.get("final_scope_binary")) != "in_scope":
            continue
        semi_audit_holdout_tasks.append(
            _semi_task_from_txt(
                row={"task_id": task_id, "base_task_id": gold_row["base_task_id"]},
                family="fail",
                source_type="trap_natural_holdout",
                init_type="misleading",
                dataset_group="PreScreen_semi_audit_holdout",
                condition="semi_audit_holdout",
                semi_role="holdout",
                model_version="HoHoNet_stage1_prescreen_holdout_v2",
                model_output_txt_map=inputs["model_output_txt_map"],
            )
        )

    oos_tasks = [_oos_task(row, inputs["final_gold_by_task"][str(row["task_id"])]) for row in oos_rows]
    oos_audit_only_tasks = [
        _oos_task(
            row,
            inputs["final_gold_by_task"][str(row["task_id"])],
            final_role="audit_only",
            scope_alias=str(row["final_scope_alias"]),
        )
        for row in _sort_by_task_id(
            [
                row
                for row in inputs["final_gold_by_task"].values()
                if str(row["task_id"]) in audit_only_task_ids
            ]
        )
    ]

    oos_directory_subtype_reconciliation_task_ids = sorted(
        {
            str(task["data"]["task_id"])
            for task in (oos_tasks + oos_audit_only_tasks)
            if OOS_FAMILY_TO_SCOPE_ALIAS.get(str(task["data"].get("family_dir", "")), "")
            and OOS_FAMILY_TO_SCOPE_ALIAS.get(str(task["data"].get("family_dir", "")), "")
            != str(task["data"].get("scope_target", ""))
        },
        key=int,
    )

    summary = {
        "summary_name": "stage1_prescreen_import_summary_v4",
        "manual_count": len(manual_tasks),
        "semi_count": len(semi_tasks),
        "semi_control_count": len(semi_control_rows),
        "semi_natural_trap_count": sum(1 for row in semi_trap_rows if row["source_type"] == "trap_natural"),
        "semi_synthetic_trap_count": sum(
            1 for row in semi_trap_rows if row["source_type"] == "trap_synthetic_disjoint_source"
        ),
        "semi_audit_stress_count": len(semi_audit_stress_tasks),
        "semi_audit_fail_count": sum(1 for task in semi_audit_stress_tasks if task["data"]["trap_family"] == "fail"),
        "semi_audit_topology_count": sum(
            1 for task in semi_audit_stress_tasks if task["data"]["trap_family"] == "topology_failure"
        ),
        "semi_audit_holdout_count": len(semi_audit_holdout_tasks),
        "oos_gate_count": len(oos_tasks),
        "oos_audit_only_count": len(oos_audit_only_tasks),
        "oos_directory_subtype_reconciliation_task_ids": oos_directory_subtype_reconciliation_task_ids,
        "manual_has_predictions": False,
        "semi_all_have_predictions": all("predictions" in task for task in semi_tasks),
        "semi_audit_all_have_predictions": all("predictions" in task for task in semi_audit_stress_tasks),
        "semi_holdout_all_have_predictions": all("predictions" in task for task in semi_audit_holdout_tasks),
        "oos_has_predictions": False,
        "source_contract": {
            "manual": "final_gold_records_v1.jsonl + manual_binding_audit_v2.json",
            "semi_natural_and_control": f"output/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34/*.txt as model proposal + {CURRENT_SEMI_SELECTION_NAME}",
            "semi_synthetic": f"semi_synthetic_disjoint_candidate_bank_v2.jsonl carry-forward assets + {CURRENT_SEMI_SELECTION_NAME}",
            "semi_audit_stress": f"output/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34/*.txt + {CURRENT_SEMI_SELECTION_NAME} audit_stress_candidates",
            "semi_audit_holdout": f"output/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34/*.txt + {CURRENT_SEMI_SELECTION_NAME} audit_stress_holdout_candidates",
            "oos": "final_gold_records_v1.jsonl + oos_final_quota_binding_v2.json",
        },
        "notes": [
            "manual 和 OOS 不附带 predictions。",
            "semi 的 control 与 natural trap 初始化来自 output 目录下的模型 proposal txt，而不是 trap 任务目录里的 legacy txt。",
            "semi synthetic trap 继续沿用 frozen synthetic asset。",
            "task668 现在替换 task580，作为更干净的第三条 natural overextend。",
            "task580 保留为 special-review reserve；task475 仍只保留在 fail holdout 层。",
            "OOS 导入以 final gold scope subtype 为准；task560 虽在“边界不可判定”目录下，但当前 scope_target 仍按 final gold 记为 oos_geometry，并继续只作 audit-only。",
        ],
    }
    return {
        "manual": manual_tasks,
        "semi": semi_tasks,
        "semi_audit_stress": semi_audit_stress_tasks,
        "semi_audit_holdout": semi_audit_holdout_tasks,
        "oos": oos_tasks,
        "oos_audit_only": oos_audit_only_tasks,
        "summary": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=OUTPUT_DIR)
    args = parser.parse_args()

    repo_root = _repo_root()
    output_dir = repo_root / args.output_dir
    payloads = build_import_payloads(load_inputs(repo_root))

    _write_json(output_dir / "stage1_prescreen_manual_import_v2.json", payloads["manual"])
    _write_json(output_dir / "stage1_prescreen_semi_import_v5.json", payloads["semi"])
    _write_json(output_dir / "stage1_prescreen_semi_audit_stress_import_v3.json", payloads["semi_audit_stress"])
    _write_json(output_dir / "stage1_prescreen_semi_audit_holdout_v2.json", payloads["semi_audit_holdout"])
    _write_json(output_dir / "stage1_prescreen_oos_import_v2.json", payloads["oos"])
    _write_json(output_dir / "stage1_prescreen_oos_audit_only_import_v1.json", payloads["oos_audit_only"])
    _write_json(output_dir / "stage1_prescreen_import_summary_v4.json", payloads["summary"])


if __name__ == "__main__":
    main()
