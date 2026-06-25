"""Run the expert-side deterministic segment-aware Manhattan refit for 3741."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.run_local_3d_projection_review import run_local_review
from tools.paper_a_manhattan.run_single_image_manhattan_assist import (
    build_single_image_assist,
)
from tools.paper_a_manhattan.segment_aware_manhattan_refit import (
    VERIFIED_ORDER_SOURCE_IDS,
    solve_segment_aware_refit,
)

GT_PATH = Path("export_label/groudTruth.json")
DEFAULT_OUT_DIR = Path(
    "analysis_results/paper_a_manhattan/segment_aware_manhattan_refit/"
    "task218_ann3741"
)
SAFETY = {
    "expert_side_only": True,
    "accepted": False,
    "downstream_recommendation": False,
    "candidate_preference_authorized": False,
    "annotation_writeback": False,
    "annotation_patch_generated": False,
    "active_ranking_role": False,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_record() -> tuple[dict[str, Any], dict[str, Any]]:
    for task in json.loads(GT_PATH.read_text(encoding="utf-8")):
        for annotation in task.get("annotations", []):
            if annotation.get("id") == 3741:
                return task, annotation
    raise ValueError("annotation 3741 not found")


def _assist(task: dict[str, Any], annotation: dict[str, Any]) -> dict[str, Any]:
    return build_single_image_assist(
        {
            "task_id": task["id"],
            "annotation_id": annotation["id"],
            "result": annotation["result"],
            "data": task["data"],
            "width": 1024,
            "height": 512,
            "order_verified_by_expert": True,
            "preview_order_override": VERIFIED_ORDER_SOURCE_IDS,
            "order_override_note": "C6.5a.7.1 verified order",
        }
    )


def _point_ids_by_source_pair_id(
    assist: dict[str, Any],
) -> dict[int, dict[str, str]]:
    table = {row["preview_pair_index"]: row for row in assist["preview_pair_table"]}
    return {
        source_pair_id: {
            "top_id": table[source_pair_id]["top_id"],
            "bottom_id": table[source_pair_id]["bottom_id"],
        }
        for source_pair_id in VERIFIED_ORDER_SOURCE_IDS
    }


def _attach_id_semantics(
    ordered_pairs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            **pair,
            "source_pair_id": source_pair_id,
            "solver_position": solver_position,
            "verified_order_source_id": source_pair_id,
            "source_preview_order_index": source_pair_id,
            "effective_pair_index": solver_position,
        }
        for solver_position, (pair, source_pair_id) in enumerate(
            zip(ordered_pairs, VERIFIED_ORDER_SOURCE_IDS), start=1
        )
    ]


def _changes(
    before: list[dict[str, Any]], after: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    for index, (left, right) in enumerate(zip(before, after), start=1):
        fields = {}
        for field, endpoint, axis in (
            ("top_x", "top", "x"),
            ("top_y", "top", "y"),
            ("bottom_x", "bottom", "x"),
            ("bottom_y", "bottom", "y"),
        ):
            old, new = float(left[endpoint][axis]), float(right[endpoint][axis])
            fields[field] = {"before": old, "after": new, "delta": new - old}
        source_pair_id = VERIFIED_ORDER_SOURCE_IDS[index - 1]
        rows.append(
            {
                "source_pair_id": source_pair_id,
                "solver_position": index,
                "verified_order_source_id": source_pair_id,
                "source_preview_order_index": source_pair_id,
                "effective_pair_index": index,
                "fields": fields,
            }
        )
    return rows


def _summary(payload: dict[str, Any]) -> str:
    top = payload["top_candidate"]
    metrics = top["metrics"]
    return "\n".join(
        [
            "# Segment-aware Manhattan Refit 3741",
            "",
            f"- Top candidate: `{top['variant_id']}`",
            "- Method: deterministic weighted Manhattan wall-line offsets/intersections.",
            "- Main adjustment scope: pair 2, chain 5–6–7–8, chain 12–11–1.",
            f"- Strong anchor 3–4 movement: `{metrics['strong_anchor_movement']:.4f}` (basically preserved).",
            f"- Chain 5–6–7–8 preserved: `{str(metrics['chain_5_6_7_8_preserved']).lower()}`.",
            f"- Chain 12–11–1 preserved: `{str(metrics['chain_12_11_1_preserved']).lower()}`.",
            "- ID semantics: all segment/weight/report labels use source_pair_id; "
            "geometry uses solver_position after explicit mapping.",
            "- Source pair 2 maps to solver position "
            f"`{metrics['suspect_source_pair_2_solver_position']}`.",
            f"- Source pair 2 movement: `{metrics['suspect_source_pair_2_movement']:.4f}`.",
            "- Pairs 9–10 height was reprojected from the 3–4 height anchor; manual confirmation remains required.",
            f"- Self-intersection: `{str(metrics['self_intersection']).lower()}`.",
            f"- Recommendation: `{metrics['recommendation_label']}`.",
            "- Automatic writeback is forbidden because this is an expert-side candidate and image evidence remains incomplete.",
            "- accepted/downstream/preference/writeback: `false/false/false/false`.",
        ]
    ) + "\n"


def _review_wrapper() -> str:
    return """<!doctype html>
<meta charset="utf-8">
<title>Segment-aware Manhattan Refit 3741</title>
<style>body{font-family:system-ui;margin:16px;background:#111;color:#eee}iframe{width:100%;height:82vh;border:1px solid #555}.tag{margin-right:16px}</style>
<h1>3741 baseline vs corrected candidate</h1>
<p><span class="tag">strong anchor: 3–4</span><span class="tag">suspect: 2</span><span class="tag">chain A: 5–6–7–8</span><span class="tag">chain B: 12–11–1</span></p>
<p>Changed points are highlighted by the reused local 3D review viewer. Review only; no writeback.</p>
<iframe src="local_3d_review.html"></iframe>
"""


def _local_server_root(out_dir: Path) -> Path | None:
    try:
        out_dir.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        return None
    return REPO_ROOT


def run(out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Path]:
    source_sha_before = _sha256(GT_PATH)
    task, annotation = _source_record()
    assist = _assist(task, annotation)
    pairs = _attach_id_semantics(assist["ordered_pairs"])
    if len(pairs) != 12:
        raise ValueError("3741 verified order did not produce 12 pairs")
    result = solve_segment_aware_refit(
        pairs,
        point_ids_by_source_pair_id=_point_ids_by_source_pair_id(assist),
    )
    if result["fail_closed"]:
        raise RuntimeError(f"refit failed closed: {result['suppress_reasons']}")
    top = result["top_candidate"]
    changes = _changes(pairs, top["corrected_coordinates"])
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "segment_aware_manhattan_refit_3741_v1_1",
        "case_name": "task218_ann3741",
        "source_annotation_id": 3741,
        "source_task_id": task["id"],
        "source_gt": {"path": GT_PATH.as_posix(), "sha256": source_sha_before},
        "id_semantics": result["id_semantics"],
        "verified_order_source_ids": result["verified_order_source_ids"],
        "source_pair_to_solver_position": result[
            "source_pair_to_solver_position"
        ],
        "solver_position_to_verified_order_source_id": result[
            "solver_position_to_verified_order_source_id"
        ],
        "source_image": task["data"]["image"],
        "segment_definitions_by_source_pair_id": result[
            "segment_definitions_by_source_pair_id"
        ],
        "observation_weights_by_source_pair_id": result[
            "observation_weights_by_source_pair_id"
        ],
        "direction_variants": result["direction_variants"],
        "top_candidate_id": result["top_candidate_id"],
        "top_candidate": top,
        "corrected_coordinates": top["corrected_coordinates"],
        "before_after_delta": changes,
        "safety_flags": SAFETY,
    }
    json_path = out_dir / "segment_aware_manhattan_refit_3741.json"
    summary_path = out_dir / "segment_aware_manhattan_refit_3741_summary.md"
    review_path = out_dir / "segment_aware_manhattan_refit_3741_review.html"
    copy_path = out_dir / "corrected_points_for_manual_copy_3741.json"
    json_path.write_bytes(
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    summary_path.write_bytes(_summary(payload).encode("utf-8"))
    copy_path.write_bytes(
        (
            json.dumps(
                {
                    "schema_version": "manual_copy_candidate_3741_v1",
                    "case_name": "task218_ann3741",
                    "candidate_id": result["top_candidate_id"],
                    "id_semantics": result["id_semantics"],
                    "verified_order_source_ids": result[
                        "verified_order_source_ids"
                    ],
                    "source_pair_to_solver_position": result[
                        "source_pair_to_solver_position"
                    ],
                    "corrected_coordinates": top["corrected_coordinates"],
                    "before_after_delta": changes,
                    "human_must_confirm": True,
                    "writeback": False,
                    "annotation_writeback": False,
                    "accepted": False,
                    "downstream_recommendation": False,
                    "candidate_preference_authorized": False,
                    "annotation_patch_generated": False,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
    )
    input_manifest = out_dir / "_review_input.json"
    candidate_manifest = out_dir / "_review_candidate.json"
    input_manifest.write_bytes(
        (
            json.dumps(
                {"source_image": task["data"]["image"], "ordered_pairs": pairs},
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
    )
    candidate_manifest.write_bytes(
        (
            json.dumps(
                {
                    "candidates": [
                        {
                            "candidate_id": result["top_candidate_id"],
                            "action_family": "segment_aware_manhattan_wall_line_refit",
                            "coordinate_changes": changes,
                            "id_semantics": {
                                "source_pair_id": "Label Studio / preview original pair number",
                                "solver_position": "one-based position after verified-order sorting",
                                "effective_pair_index": "viewer compatibility alias of solver_position",
                            },
                            "changed_source_pair_ids": [
                                row["source_pair_id"]
                                for row in changes
                                if max(
                                    abs(value["delta"])
                                    for value in row["fields"].values()
                                )
                                > 1e-6
                            ],
                            "changed_solver_positions": [
                                row["solver_position"]
                                for row in changes
                                if max(
                                    abs(value["delta"])
                                    for value in row["fields"].values()
                                )
                                > 1e-6
                            ],
                            "changed_pair_indices": [
                                row["effective_pair_index"]
                                for row in changes
                                if max(
                                    abs(value["delta"])
                                    for value in row["fields"].values()
                                )
                                > 1e-6
                            ],
                            "changed_pair_indices_semantics": (
                                "deprecated viewer compatibility alias of "
                                "changed_solver_positions"
                            ),
                            "preferred_panel": True,
                            "manual_review_candidate": True,
                            "automatic_fix_claimed": False,
                        }
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
    )
    preview = run_local_review(
        input_path=input_manifest,
        candidate_json=candidate_manifest,
        candidate_limit=1,
        out_dir=out_dir,
        image_root=Path("data/mp3d_layout/img_v"),
        case_name="task218_ann3741_segment_refit",
        width=1024,
        height=512,
        coordinate_mode="ls_percent",
        camera_height=1.6,
        local_server_root=_local_server_root(out_dir),
    )
    review_path.write_bytes(_review_wrapper().encode("utf-8"))
    if _sha256(GT_PATH) != source_sha_before:
        raise RuntimeError("source GT changed during audit-only run")
    return {
        "json": json_path,
        "summary": summary_path,
        "review": review_path,
        "manual_copy": copy_path,
        "local_review": preview["html"],
    }


if __name__ == "__main__":
    print(run()["json"])
