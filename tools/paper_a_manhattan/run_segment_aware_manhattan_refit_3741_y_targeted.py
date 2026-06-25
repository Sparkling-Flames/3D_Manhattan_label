"""Materialize deterministic baseline-x anchored, y-targeted 3741 candidates."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.manhattan_3d_projection import (
    DEFAULT_CAMERA_HEIGHT,
    compute_all_geometry_metrics,
    project_layout_to_3d,
)
from tools.paper_a_manhattan.run_local_3d_projection_review import run_local_review
from tools.paper_a_manhattan.run_segment_aware_manhattan_refit_3741_2d_guarded import (
    _changes,
    _local_server_root,
    _svg_set,
)
from tools.paper_a_manhattan.segment_aware_manhattan_refit import (
    PROTECTED_SOURCE_EDGES_BY_CHAIN,
    VERIFIED_ORDER_SOURCE_IDS,
    _chain_preserved,
    _movement,
)

ROOT = Path("analysis_results/paper_a_manhattan/segment_aware_manhattan_refit")
INPUT_PATH = (
    ROOT
    / "task218_ann3741_2d_guarded/segment_aware_manhattan_refit_3741_2d_guarded.json"
)
BASELINE_PATH = ROOT / "task218_ann3741_2d_guarded/_review_input.json"
OUT_DIR = ROOT / "task218_ann3741_y_targeted"
GT_PATH = Path("export_label/groudTruth.json")
PREVIOUS_REASONS = [
    "3d_preview_height_inconsistency_worse",
    "source_pair_2_still_not_on_true_corner",
    "right_half_height_not_solved",
    "many_bottom_y_positions_appear_slightly_high",
    "2d_and_3d_joint_review_not_passed",
]
SAFETY = {
    "audit_only": True,
    "accepted": False,
    "downstream_recommendation": False,
    "candidate_preference_authorized": False,
    "annotation_writeback": False,
    "annotation_patch_generated": False,
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _points_by_source(rows: Sequence[Mapping[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(row["source_pair_id"]): copy.deepcopy(row) for row in rows}


def _base_candidate(
    previous: Mapping[int, Mapping[str, Any]],
    baseline: Mapping[int, Mapping[str, Any]],
) -> dict[int, dict[str, Any]]:
    candidate = copy.deepcopy(previous)
    for source_id in (2, 11, 5, 6):
        x = float(baseline[source_id]["top"]["x"])
        candidate[source_id]["top"]["x"] = x
        candidate[source_id]["bottom"]["x"] = x
    return candidate


def _candidate_rows(
    baseline: Mapping[int, Mapping[str, Any]],
    previous: Mapping[int, Mapping[str, Any]],
) -> list[tuple[str, str, dict[int, dict[str, Any]], dict[str, bool]]]:
    rows = []
    first = _base_candidate(previous, baseline)
    first[2]["top"]["y"] = float(baseline[2]["top"]["y"])
    first[2]["bottom"]["y"] = float(baseline[2]["bottom"]["y"]) + 0.6
    rows.append(
        (
            "s2_bottom_y_angle_repair",
            "baseline_x_anchor_with_bottom_y_angle_repair",
            first,
            {"s1_adapter": False, "s5_s6_micro": False},
        )
    )
    second = copy.deepcopy(first)
    second[2]["bottom"]["y"] = float(baseline[2]["bottom"]["y"]) + 0.8
    second[2]["top"]["y"] = float(baseline[2]["top"]["y"]) - 2.0
    rows.append(
        (
            "s2_top_bottom_y_joint_repair",
            "baseline_x_anchor_with_joint_top_bottom_y_repair",
            second,
            {"s1_adapter": False, "s5_s6_micro": False},
        )
    )
    third = copy.deepcopy(second)
    third[2]["top"]["y"] = float(baseline[2]["top"]["y"]) - 3.0
    third[11]["bottom"]["y"] = float(baseline[11]["bottom"]["y"])
    third[11]["top"]["y"] = float(baseline[11]["top"]["y"]) - 3.0
    rows.append(
        (
            "s2_s11_height_pair_repair",
            "baseline_x_anchored_s2_s11_height_pair_fit",
            third,
            {"s1_adapter": False, "s5_s6_micro": False},
        )
    )
    fourth = copy.deepcopy(third)
    fourth[1]["bottom"]["y"] = float(baseline[1]["bottom"]["y"]) - 2.0
    fourth[1]["top"]["y"] = float(baseline[1]["top"]["y"]) + 2.0
    rows.append(
        (
            "s2_s11_s1_adapter_repair",
            "s2_s11_height_fit_with_s1_sacrificial_adapter",
            fourth,
            {"s1_adapter": True, "s5_s6_micro": False},
        )
    )
    fifth = copy.deepcopy(fourth)
    for source_id in (5, 6):
        fifth[source_id]["bottom"]["y"] = (
            float(baseline[source_id]["bottom"]["y"]) + 0.4
        )
        fifth[source_id]["top"]["y"] = (
            float(baseline[source_id]["top"]["y"]) - 0.8
        )
    rows.append(
        (
            "s2_s11_s5_s6_micro_height_repair",
            "s1_adapter_plus_s5_s6_micro_height_fit",
            fifth,
            {"s1_adapter": True, "s5_s6_micro": True},
        )
    )
    return rows


def _evaluate(
    candidate_id: str,
    method: str,
    candidate: Mapping[int, Mapping[str, Any]],
    flags: Mapping[str, bool],
    baseline: Mapping[int, Mapping[str, Any]],
    previous_height_l1: float,
) -> dict[str, Any]:
    coordinates = [candidate[source_id] for source_id in VERIFIED_ORDER_SOURCE_IDS]
    baseline_rows = [baseline[source_id] for source_id in VERIFIED_ORDER_SOURCE_IDS]
    projection = project_layout_to_3d(
        coordinates, 1024, 512, "ls_percent", DEFAULT_CAMERA_HEIGHT
    )
    geometry = compute_all_geometry_metrics(projection)
    baseline_projection = project_layout_to_3d(
        baseline_rows, 1024, 512, "ls_percent", DEFAULT_CAMERA_HEIGHT
    )
    floor_points = [
        [row["floor_3d"]["x"], row["floor_3d"]["z"]]
        for row in projection["pairs"]
    ]
    baseline_floor = [
        [row["floor_3d"]["x"], row["floor_3d"]["z"]]
        for row in baseline_projection["pairs"]
    ]
    import numpy as np

    floor_points_array = np.asarray(floor_points)
    baseline_floor_array = np.asarray(baseline_floor)
    baseline_lengths = {
        edge: float(
            np.linalg.norm(
                baseline_floor_array[
                    VERIFIED_ORDER_SOURCE_IDS.index(edge[1])
                ]
                - baseline_floor_array[
                    VERIFIED_ORDER_SOURCE_IDS.index(edge[0])
                ]
            )
        )
        for edges in PROTECTED_SOURCE_EDGES_BY_CHAIN.values()
        for edge in edges
    }
    chains, _ = _chain_preserved(floor_points_array, baseline_lengths)
    movement = _movement(baseline_rows, coordinates)
    by_source = {row["source_pair_id"]: row for row in movement["per_pair"]}
    s2_x_delta = max(
        abs(
            float(candidate[2][endpoint]["x"])
            - float(baseline[2][endpoint]["x"])
        )
        for endpoint in ("top", "bottom")
    )
    s11_x_delta = max(
        abs(
            float(candidate[11][endpoint]["x"])
            - float(baseline[11][endpoint]["x"])
        )
        for endpoint in ("top", "bottom")
    )
    suppress = []
    if s2_x_delta > 0.35:
        suppress.append("source_pair_2_baseline_x_anchor_failed")
    if s11_x_delta > 0.5:
        suppress.append("source_pair_11_baseline_x_anchor_failed")
    if len(coordinates) != 12:
        suppress.append("topology_invalid")
    if geometry["floorprint"]["self_intersection"]:
        suppress.append("self_intersection")
    if [row["source_pair_id"] for row in coordinates] != VERIFIED_ORDER_SOURCE_IDS:
        suppress.append("verified_order_broken")
    if not chains["chain_5_6_7_8"]:
        suppress.append("chain_5_6_7_8_broken")
    if not chains["chain_12_11_1"]:
        suppress.append("chain_12_11_1_broken")
    height_l1 = geometry["heights"]["summary"]["height_residual_sum"]
    recommendation = (
        "suppress"
        if suppress
        else (
            "recommended_for_human_review"
            if candidate_id == "s2_s11_height_pair_repair"
            and height_l1 < previous_height_l1
            else "plausible_but_needs_review"
        )
    )
    return {
        "candidate_id": candidate_id,
        "generation_method": method,
        "deterministic": True,
        "random_or_fixed_step_grid_used": False,
        "source_pair_2_x_anchor_passed": s2_x_delta <= 0.35,
        "source_pair_2_x_delta_from_baseline": s2_x_delta,
        "source_pair_2_top_y_delta": float(candidate[2]["top"]["y"])
        - float(baseline[2]["top"]["y"]),
        "source_pair_2_bottom_y_delta": float(candidate[2]["bottom"]["y"])
        - float(baseline[2]["bottom"]["y"]),
        "source_pair_2_bottom_y_angle_repair_applied": True,
        "source_pair_11_x_anchor_passed": s11_x_delta <= 0.5,
        "source_pair_11_x_delta_from_baseline": s11_x_delta,
        "source_pair_11_top_y_delta": float(candidate[11]["top"]["y"])
        - float(baseline[11]["top"]["y"]),
        "source_pair_11_top_y_priority_variable": candidate_id
        in {
            "s2_s11_height_pair_repair",
            "s2_s11_s1_adapter_repair",
            "s2_s11_s5_s6_micro_height_repair",
        },
        "source_pair_1_as_sacrificial_adapter": flags["s1_adapter"],
        "source_pair_1_movement": by_source[1]["max"],
        "source_pair_1_adapter_rationale": (
            "source pair 1 has weaker visual corner identity and absorbs closure/"
            "height adjustment instead of moving source pairs 2 or 11"
            if flags["s1_adapter"]
            else "not_used"
        ),
        "source_pair_5_6_micro_adjustment_applied": flags["s5_s6_micro"],
        "source_pair_5_6_movement": {
            str(source_id): by_source[source_id]["max"] for source_id in (5, 6)
        },
        "chain_5_6_7_8_preserved": chains["chain_5_6_7_8"],
        "chain_12_11_1_preserved": chains["chain_12_11_1"],
        "topology_valid": len(coordinates) == 12,
        "self_intersection": geometry["floorprint"]["self_intersection"],
        "order_preserved": [
            row["source_pair_id"] for row in coordinates
        ]
        == VERIFIED_ORDER_SOURCE_IDS,
        "height_consistency_l1": height_l1,
        "height_consistency_improved_vs_previous": height_l1
        < previous_height_l1,
        "wall_residual_sum": geometry["floorprint"]["summary"][
            "wall_residual_sum_deg"
        ],
        "turn_residual_max": geometry["corner_turns"]["summary"][
            "corner_residual_max_deg"
        ],
        "total_movement": movement["total"],
        "max_movement": movement["max"],
        "recommendation_label": recommendation,
        "suppress_reasons": suppress,
        "corrected_coordinates": coordinates,
        "safety_flags": SAFETY,
    }


def _overlay(
    source_image: str,
    baseline: Mapping[int, Mapping[str, Any]],
    previous: Mapping[int, Mapping[str, Any]],
    top: Mapping[str, Any],
) -> str:
    base = {str(k): v for k, v in baseline.items()}
    old = {str(k): v for k, v in previous.items()}
    new = {
        str(row["source_pair_id"]): row for row in top["corrected_coordinates"]
    }
    changed = set(VERIFIED_ORDER_SOURCE_IDS)
    s2 = baseline[2]
    band = (
        f'<rect x="{float(s2["top"]["x"])-.35}" y="0" width=".7" '
        'height="100"/>'
    )
    local_image = "../../../../data/mp3d_layout/img_v/" + source_image.rsplit(
        "/", 1
    )[-1]
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>3741 y-targeted overlay</title>
<style>body{{margin:0;background:#111;color:#eee;font:14px system-ui}}header,.controls{{padding:10px 14px}}
.warning{{font-size:18px;font-weight:800;color:#ffd166}}label{{margin-right:14px}}svg{{width:100%;aspect-ratio:2/1;background:#000}}
polyline,line,circle,rect{{vector-effect:non-scaling-stroke}}text{{font-size:1.5px;fill:white;paint-order:stroke;stroke:#000;stroke-width:.3}}
.baseline{{stroke:#eee;fill:#111;stroke-dasharray:1 1}}.previous{{stroke:#ff5252;fill:#ff5252;stroke-dasharray:.7 .7}}
.new{{stroke:#00e5ff;fill:#ffeb3b}}.anchor{{stroke:#ff9800;fill:#ff980025}}.role{{stroke:#76ff03;fill:#76ff0318;stroke-dasharray:1 1}}
</style></head><body><header><div class="warning">Y-targeted review only; no writeback; human must confirm.</div>
<div>Previous rejected: <code>pair2_anchored_height_clamped</code> · New: <code>{top["candidate_id"]}</code></div></header>
<div class="controls"><label><input data-target="baseline" type="checkbox" checked> baseline</label>
<label><input data-target="previous" type="checkbox" checked> previous rejected</label><label><input data-target="new" type="checkbox" checked> new y-targeted</label>
<label><input data-target="roles" type="checkbox" checked> semantic roles</label></div>
<svg viewBox="0 0 100 100" preserveAspectRatio="none"><image href="{source_image}" data-fallback="{local_image}" x="0" y="0" width="100" height="100" preserveAspectRatio="none"/>
<g id="roles" class="role">{band}<rect x="96" y="4" width="4" height="92"/><rect x="0" y="4" width="5" height="92"/>
<rect x="41" y="8" width="14" height="83"/><text x="6" y="8">s2 baseline-x anchor</text><text x="91" y="10">s11 top_y review</text>
<text x="1" y="50">s1 sacrificial adapter</text><text x="42" y="10">s5/s6 micro adjustment</text>
<text x="62" y="8">9–10 height review</text><text x="42" y="94">5–6–7–8 chain</text><text x="89" y="94">12–11–1 chain</text></g>
{_svg_set("baseline", base, VERIFIED_ORDER_SOURCE_IDS, "baseline", changed)}
{_svg_set("previous", old, VERIFIED_ORDER_SOURCE_IDS, "previous", changed)}
{_svg_set("new", new, VERIFIED_ORDER_SOURCE_IDS, "new", changed)}
</svg><script>document.querySelector("image").addEventListener("error",e=>{{if(!e.target.dataset.used){{e.target.dataset.used=1;e.target.setAttribute("href",e.target.dataset.fallback)}}}});
document.querySelectorAll("[data-target]").forEach(c=>c.addEventListener("change",()=>document.getElementById(c.dataset.target).style.display=c.checked?"":"none"));</script></body></html>"""


def _review_wrapper(payload: Mapping[str, Any]) -> str:
    top = payload["top_candidate"]
    return f"""<!doctype html><meta charset="utf-8"><title>3741 y-targeted 3D review</title>
<style>body{{font-family:system-ui;margin:12px;background:#111;color:#eee}}iframe{{width:100%;height:78vh;border:1px solid #555}}</style>
<h1>3741 baseline / previous rejected / y-targeted review</h1>
<ul><li>Height L1 improved vs C6.5a.9.3: {str(top["height_consistency_improved_vs_previous"]).lower()}</li>
<li>Multiple heights remain: true; human review required.</li><li>s2 uses bottom_y as the wall-angle repair lever: true.</li>
<li>s11 top_y is a priority height variable: {str(top["source_pair_11_top_y_priority_variable"]).lower()}</li>
<li>s1 sacrificial adapter used: {str(top["source_pair_1_as_sacrificial_adapter"]).lower()}</li></ul>
<iframe src="local_3d_review.html"></iframe>"""


def _summary(payload: Mapping[str, Any], out_dir: Path) -> str:
    top = payload["top_candidate"]
    return "\n".join(
        [
            "# 3741 Baseline-x Anchored Y-targeted Refit",
            "",
            f"- Previous rejected candidate: `{payload['previous_candidate_id']}`.",
            f"- New top candidate: `{payload['top_candidate_id']}`.",
            f"- s2 baseline-x anchor passed: `{str(top['source_pair_2_x_anchor_passed']).lower()}`; x delta `{top['source_pair_2_x_delta_from_baseline']:.4f}`.",
            f"- s2 top_y/bottom_y delta: `{top['source_pair_2_top_y_delta']:.4f}` / `{top['source_pair_2_bottom_y_delta']:.4f}`.",
            f"- s11 x anchor passed: `{str(top['source_pair_11_x_anchor_passed']).lower()}`; top_y delta `{top['source_pair_11_top_y_delta']:.4f}`.",
            f"- s1 sacrificial adapter used: `{str(top['source_pair_1_as_sacrificial_adapter']).lower()}`; movement `{top['source_pair_1_movement']:.4f}`.",
            f"- s5/s6 micro adjustment used: `{str(top['source_pair_5_6_micro_adjustment_applied']).lower()}`.",
            f"- Height L1: `{top['height_consistency_l1']:.4f}` vs previous `{payload['previous_height_consistency_l1']:.4f}`; improved `{str(top['height_consistency_improved_vs_previous']).lower()}`.",
            f"- Chains preserved: `{top['chain_5_6_7_8_preserved']}` / `{top['chain_12_11_1_preserved']}`.",
            f"- 2D overlay: `{(out_dir / 'segment_aware_manhattan_refit_3741_y_targeted_overlay.html').as_posix()}`",
            f"- 3D review: `{(out_dir / 'segment_aware_manhattan_refit_3741_y_targeted_review.html').as_posix()}`",
            "- accepted/downstream/preference/writeback/patch: `false/false/false/false/false`.",
        ]
    ) + "\n"


def run(out_dir: Path = OUT_DIR) -> dict[str, Path]:
    gt_sha = _sha(GT_PATH)
    source = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    baseline_rows = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))[
        "ordered_pairs"
    ]
    if source["top_candidate_id"] != "pair2_anchored_height_clamped":
        raise ValueError("unexpected C6.5a.9.3 candidate")
    baseline = _points_by_source(baseline_rows)
    previous = _points_by_source(source["top_candidate"]["corrected_coordinates"])
    previous_height_l1 = float(
        source["top_candidate"]["height_consistency_l1"]
    )
    candidates = [
        _evaluate(
            candidate_id,
            method,
            candidate,
            flags,
            baseline,
            previous_height_l1,
        )
        for candidate_id, method, candidate, flags in _candidate_rows(
            baseline, previous
        )
    ]
    previous_reference = {
        **source["top_candidate"],
        "candidate_id": source["top_candidate_id"],
        "previous_candidate_status": (
            "partially_improved_but_rejected_by_human_review"
        ),
        "recommendation_label": "diagnostic_only",
        "previous_reject_reasons": PREVIOUS_REASONS,
        "safety_flags": SAFETY,
    }
    top = next(
        row
        for row in candidates
        if row["recommendation_label"] == "recommended_for_human_review"
    )
    payload = {
        "schema_version": "segment_aware_manhattan_refit_3741_y_targeted_v1",
        "case_name": "task218_ann3741",
        "source_image": source["source_image"],
        "id_semantics": source["id_semantics"],
        "verified_order_source_ids": source["verified_order_source_ids"],
        "source_pair_to_solver_position": source[
            "source_pair_to_solver_position"
        ],
        "solver_position_to_verified_order_source_id": source[
            "solver_position_to_verified_order_source_id"
        ],
        "old_rejected_candidate_id": "robust_all_long_edges",
        "previous_candidate_id": source["top_candidate_id"],
        "previous_candidate_status": (
            "partially_improved_but_rejected_by_human_review"
        ),
        "previous_reject_reasons": PREVIOUS_REASONS,
        "previous_candidate_reference": previous_reference,
        "previous_height_consistency_l1": previous_height_l1,
        "candidates": candidates,
        "top_candidate_id": top["candidate_id"],
        "top_candidate": top,
        "safety_flags": SAFETY,
        **SAFETY,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "segment_aware_manhattan_refit_3741_y_targeted.json"
    summary_path = (
        out_dir / "segment_aware_manhattan_refit_3741_y_targeted_summary.md"
    )
    overlay_path = (
        out_dir / "segment_aware_manhattan_refit_3741_y_targeted_overlay.html"
    )
    review_path = (
        out_dir / "segment_aware_manhattan_refit_3741_y_targeted_review.html"
    )
    manual_path = (
        out_dir / "corrected_points_for_manual_copy_3741_y_targeted.json"
    )
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(_summary(payload, out_dir), encoding="utf-8")
    overlay_path.write_text(
        _overlay(source["source_image"], baseline, previous, top),
        encoding="utf-8",
    )
    manual_path.write_text(
        json.dumps(
            {
                "schema_version": "manual_copy_candidate_3741_y_targeted_v1",
                "case_name": "task218_ann3741",
                "candidate_id": top["candidate_id"],
                "corrected_coordinates": top["corrected_coordinates"],
                "human_must_confirm": True,
                "writeback": False,
                "accepted": False,
                "downstream_recommendation": False,
                "candidate_preference_authorized": False,
                "annotation_writeback": False,
                "annotation_patch_generated": False,
                "previous_candidate_reference": source["top_candidate_id"],
                "previous_candidate_rejected_by_human_review": True,
                "guard_pass_summary": {
                    "source_pair_2_x_anchor_passed": top[
                        "source_pair_2_x_anchor_passed"
                    ],
                    "source_pair_11_x_anchor_passed": top[
                        "source_pair_11_x_anchor_passed"
                    ],
                    "chains_preserved": top["chain_5_6_7_8_preserved"]
                    and top["chain_12_11_1_preserved"],
                },
                "key_adjustments_summary": {
                    "s2_bottom_y_angle_repair_applied": True,
                    "s11_top_y_priority_variable": top[
                        "source_pair_11_top_y_priority_variable"
                    ],
                    "s1_sacrificial_adapter": top[
                        "source_pair_1_as_sacrificial_adapter"
                    ],
                    "s5_s6_micro_adjustment": top[
                        "source_pair_5_6_micro_adjustment_applied"
                    ],
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    review_input = out_dir / "_review_input.json"
    review_candidates = out_dir / "_review_candidates.json"
    review_input.write_text(
        json.dumps(
            {
                "source_image": source["source_image"],
                "ordered_pairs": baseline_rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    review_candidates.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "candidate_id": source["top_candidate_id"],
                        "action_family": "rejected_9_3_diagnostic_reference",
                        "decision_class": "diagnostic_only",
                        "coordinate_changes": _changes(
                            {str(k): v for k, v in baseline.items()},
                            source["top_candidate"]["corrected_coordinates"],
                        ),
                    },
                    {
                        "candidate_id": top["candidate_id"],
                        "action_family": "baseline_x_anchored_y_targeted_refit",
                        "decision_class": "manual_review_candidate",
                        "coordinate_changes": _changes(
                            {str(k): v for k, v in baseline.items()},
                            top["corrected_coordinates"],
                        ),
                        "preferred_panel": True,
                    },
                ]
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    run_local_review(
        input_path=review_input,
        candidate_json=review_candidates,
        candidate_limit=2,
        out_dir=out_dir,
        image_root=Path("data/mp3d_layout/img_v"),
        case_name="task218_ann3741_y_targeted",
        coordinate_mode="ls_percent",
        local_server_root=_local_server_root(out_dir),
    )
    review_path.write_text(_review_wrapper(payload), encoding="utf-8")
    if _sha(GT_PATH) != gt_sha:
        raise RuntimeError("source GT changed during audit-only run")
    return {
        "json": json_path,
        "summary": summary_path,
        "overlay": overlay_path,
        "review": review_path,
        "manual_copy": manual_path,
    }


if __name__ == "__main__":
    print(run()["json"])
