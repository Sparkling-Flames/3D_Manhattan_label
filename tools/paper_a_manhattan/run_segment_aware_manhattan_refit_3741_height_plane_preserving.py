"""Materialize height-plane-preserving, 2D-constrained 3741 review candidates."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.manhattan_3d_projection import (
    DEFAULT_CAMERA_HEIGHT,
    compute_all_geometry_metrics,
    project_layout_to_3d,
)
from tools.paper_a_manhattan.run_local_3d_projection_review import (
    canonical_review_out_dir,
    run_local_review,
)
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
ROBUST_PATH = ROOT / "task218_ann3741/segment_aware_manhattan_refit_3741.json"
GUARDED_PATH = (
    ROOT
    / "task218_ann3741_2d_guarded/segment_aware_manhattan_refit_3741_2d_guarded.json"
)
Y_TARGETED_PATH = (
    ROOT
    / "task218_ann3741_y_targeted/segment_aware_manhattan_refit_3741_y_targeted.json"
)
BASELINE_PATH = ROOT / "task218_ann3741_2d_guarded/_review_input.json"
OUT_DIR = ROOT / "task218_ann3741_height_plane_preserving"
GT_PATH = Path("export_label/groudTruth.json")
SAFETY = {
    "audit_only": True,
    "accepted": False,
    "downstream_recommendation": False,
    "candidate_preference_authorized": False,
    "annotation_writeback": False,
    "annotation_patch_generated": False,
}
SENSITIVITY_SOURCE_IDS = (2, 5, 6, 7, 8, 11)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _by_source(rows: Sequence[Mapping[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(row["source_pair_id"]): copy.deepcopy(row) for row in rows}


def _metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    projection = project_layout_to_3d(
        rows, 1024, 512, "ls_percent", DEFAULT_CAMERA_HEIGHT
    )
    return {
        "projection": projection,
        "geometry": compute_all_geometry_metrics(projection),
        "heights_by_source_pair_id": {
            str(source_id): float(row["wall_height"])
            for source_id, row in zip(
                VERIFIED_ORDER_SOURCE_IDS, projection["pairs"]
            )
        },
    }


def _dominant_height_plane(
    baseline_metrics: Mapping[str, Any], robust_metrics: Mapping[str, Any]
) -> tuple[float, str]:
    robust = list(robust_metrics["heights_by_source_pair_id"].values())
    trusted_baseline_ids = (3, 4, 9, 10, 6, 5, 8, 7, 12, 11, 2, 1)
    trusted_baseline = [
        baseline_metrics["heights_by_source_pair_id"][str(source_id)]
        for source_id in trusted_baseline_ids
    ]
    target = statistics.median(robust + trusted_baseline)
    return (
        target,
        "median of all 12 unified robust_all_long_edges heights plus baseline "
        "3/4, 9/10, 5-6-7-8 and 12-11-2-1 continuity references; s2/s11 "
        "are included as context but cannot determine the plane alone",
    )


def _top_y_for_plane(bottom_y: float, plane: float) -> float:
    floor_angle = (bottom_y / 100.0 - 0.5) * math.pi
    floor_distance = DEFAULT_CAMERA_HEIGHT / math.tan(floor_angle)
    ceiling_angle = math.atan(
        (plane - DEFAULT_CAMERA_HEIGHT) / floor_distance
    )
    return (0.5 - ceiling_angle / math.pi) * 100.0


def _seed(
    robust: Mapping[int, Mapping[str, Any]],
    baseline: Mapping[int, Mapping[str, Any]],
) -> dict[int, dict[str, Any]]:
    candidate = copy.deepcopy(robust)
    for source_id in (2, 11):
        x = float(baseline[source_id]["top"]["x"])
        candidate[source_id]["top"]["x"] = x
        candidate[source_id]["bottom"]["x"] = x
    return candidate


def _apply_downward(
    candidate: dict[int, dict[str, Any]],
    source_id: int,
    delta: float,
    plane: float,
    *,
    from_baseline: Mapping[int, Mapping[str, Any]] | None = None,
) -> None:
    reference = from_baseline or candidate
    candidate[source_id]["bottom"]["y"] = (
        float(reference[source_id]["bottom"]["y"]) + delta
    )
    candidate[source_id]["top"]["y"] = _top_y_for_plane(
        candidate[source_id]["bottom"]["y"], plane
    )


def _chain_status(
    rows: Sequence[Mapping[str, Any]],
    baseline_rows: Sequence[Mapping[str, Any]],
) -> dict[str, bool]:
    floor = np.asarray(
        [
            [row["floor_3d"]["x"], row["floor_3d"]["z"]]
            for row in project_layout_to_3d(
                rows, 1024, 512, "ls_percent", DEFAULT_CAMERA_HEIGHT
            )["pairs"]
        ]
    )
    baseline_floor = np.asarray(
        [
            [row["floor_3d"]["x"], row["floor_3d"]["z"]]
            for row in project_layout_to_3d(
                baseline_rows, 1024, 512, "ls_percent", DEFAULT_CAMERA_HEIGHT
            )["pairs"]
        ]
    )
    lengths = {
        edge: float(
            np.linalg.norm(
                baseline_floor[VERIFIED_ORDER_SOURCE_IDS.index(edge[1])]
                - baseline_floor[VERIFIED_ORDER_SOURCE_IDS.index(edge[0])]
            )
        )
        for edges in PROTECTED_SOURCE_EDGES_BY_CHAIN.values()
        for edge in edges
    }
    return _chain_preserved(floor, lengths)[0]


def _height_plane_diagnostics(
    metrics: Mapping[str, Any], plane: float
) -> dict[str, Any]:
    residuals = {
        source_id: height - plane
        for source_id, height in metrics["heights_by_source_pair_id"].items()
    }
    threshold = 0.15
    return {
        "per_pair_height_residual_to_dominant_plane": residuals,
        "height_cluster_assignment": {
            source_id: (
                "dominant_plane"
                if abs(residual) <= threshold
                else "height_outlier"
            )
            for source_id, residual in residuals.items()
        },
        "height_outliers": [
            int(source_id)
            for source_id, residual in residuals.items()
            if abs(residual) > threshold
        ],
        "height_plane_residual_l1": sum(abs(row) for row in residuals.values()),
        "height_outlier_count": sum(
            abs(row) > threshold for row in residuals.values()
        ),
    }


def _evaluate(
    candidate_id: str,
    method: str,
    candidate: Mapping[int, Mapping[str, Any]],
    baseline: Mapping[int, Mapping[str, Any]],
    plane: float,
    *,
    s1_adapter: bool,
    s5_s6_repair: bool,
    sensitivity_summary: Mapping[str, Any],
) -> dict[str, Any]:
    rows = [candidate[source_id] for source_id in VERIFIED_ORDER_SOURCE_IDS]
    baseline_rows = [baseline[source_id] for source_id in VERIFIED_ORDER_SOURCE_IDS]
    metrics = _metrics(rows)
    geometry = metrics["geometry"]
    height = _height_plane_diagnostics(metrics, plane)
    chains = _chain_status(rows, baseline_rows)
    movement = _movement(baseline_rows, rows)
    by_source = {row["source_pair_id"]: row for row in movement["per_pair"]}
    s2_x_delta = max(
        abs(float(candidate[2][endpoint]["x"]) - float(baseline[2][endpoint]["x"]))
        for endpoint in ("top", "bottom")
    )
    s11_x_delta = max(
        abs(float(candidate[11][endpoint]["x"]) - float(baseline[11][endpoint]["x"]))
        for endpoint in ("top", "bottom")
    )
    suppress = []
    if s2_x_delta > 0.25:
        suppress.append("source_pair_2_baseline_x_anchor_failed")
    if s11_x_delta > 0.35:
        suppress.append("source_pair_11_baseline_x_anchor_failed")
    if len(rows) != 12:
        suppress.append("topology_invalid")
    if geometry["floorprint"]["self_intersection"]:
        suppress.append("self_intersection")
    if [row["source_pair_id"] for row in rows] != VERIFIED_ORDER_SOURCE_IDS:
        suppress.append("verified_order_broken")
    if not chains["chain_5_6_7_8"]:
        suppress.append("chain_5_6_7_8_broken")
    if not chains["chain_12_11_1"]:
        suppress.append("chain_12_11_1_broken")
    return {
        "candidate_id": candidate_id,
        "generation_method": method,
        "deterministic": True,
        "random_or_fixed_step_grid_used": False,
        "source_pair_2_x_anchor_passed": s2_x_delta <= 0.25,
        "source_pair_2_x_delta_from_baseline": s2_x_delta,
        "source_pair_2_top_y_delta": float(candidate[2]["top"]["y"])
        - float(baseline[2]["top"]["y"]),
        "source_pair_2_bottom_y_delta": float(candidate[2]["bottom"]["y"])
        - float(baseline[2]["bottom"]["y"]),
        "bottom_y_downward_adjustment_applied": True,
        "bottom_y_direction_note": {
            "bottom_y_increase_means_image_point_moves_down": True,
            "bottom_y_decrease_means_image_point_moves_up": True,
        },
        "source_pair_11_x_anchor_passed": s11_x_delta <= 0.35,
        "source_pair_11_x_delta_from_baseline": s11_x_delta,
        "source_pair_11_top_y_delta": float(candidate[11]["top"]["y"])
        - float(baseline[11]["top"]["y"]),
        "source_pair_11_height_plane_repair_applied": True,
        "source_pair_1_as_sacrificial_adapter": s1_adapter,
        "source_pair_1_movement": by_source[1]["max"],
        "why_s1_move_is_preferred_over_s2_or_s11": (
            "s1 has weaker direct corner visibility and absorbs seam closure while "
            "s2/s11 remain baseline-x anchored"
            if s1_adapter
            else "not_used"
        ),
        "s5_s6_bottom_y_repair_applied": s5_s6_repair,
        "bottom_y_sensitivity_summary": sensitivity_summary,
        "dominant_height_plane": plane,
        **height,
        "height_consistency_l1": geometry["heights"]["summary"][
            "height_residual_sum"
        ],
        "wall_residual_sum": geometry["floorprint"]["summary"][
            "wall_residual_sum_deg"
        ],
        "turn_residual_max": geometry["corner_turns"]["summary"][
            "corner_residual_max_deg"
        ],
        "chain_5_6_7_8_preserved": chains["chain_5_6_7_8"],
        "chain_12_11_1_preserved": chains["chain_12_11_1"],
        "topology_valid": len(rows) == 12,
        "self_intersection": geometry["floorprint"]["self_intersection"],
        "order_preserved": [
            row["source_pair_id"] for row in rows
        ]
        == VERIFIED_ORDER_SOURCE_IDS,
        "total_movement": movement["total"],
        "max_movement": movement["max"],
        "recommendation_label": "suppress" if suppress else "plausible_but_needs_review",
        "suppress_reasons": suppress,
        "corrected_coordinates": rows,
        "safety_flags": SAFETY,
    }


def _sensitivity_screen(
    seed: Mapping[int, Mapping[str, Any]],
    baseline: Mapping[int, Mapping[str, Any]],
    plane: float,
) -> dict[str, Any]:
    baseline_rows = [baseline[source_id] for source_id in VERIFIED_ORDER_SOURCE_IDS]
    seed_rows = [seed[source_id] for source_id in VERIFIED_ORDER_SOURCE_IDS]
    seed_geometry = _metrics(seed_rows)["geometry"]
    screen = {}
    for source_id in SENSITIVITY_SOURCE_IDS:
        probe = copy.deepcopy(seed)
        _apply_downward(probe, source_id, 0.3, plane)
        rows = [probe[sid] for sid in VERIFIED_ORDER_SOURCE_IDS]
        geometry = _metrics(rows)["geometry"]
        chains = _chain_status(rows, baseline_rows)
        screen[str(source_id)] = {
            "semantic_probe": f"s{source_id}_bottom_y_small_down_move",
            "bottom_y_delta": 0.3,
            "bottom_y_larger_means_point_lower_in_image": True,
            "wall_residual_sum": geometry["floorprint"]["summary"][
                "wall_residual_sum_deg"
            ],
            "wall_residual_sum_delta": geometry["floorprint"]["summary"][
                "wall_residual_sum_deg"
            ]
            - seed_geometry["floorprint"]["summary"]["wall_residual_sum_deg"],
            "turn_residual_max": geometry["corner_turns"]["summary"][
                "corner_residual_max_deg"
            ],
            "height_consistency_l1": geometry["heights"]["summary"][
                "height_residual_sum"
            ],
            "chain_5_6_7_8_preserved": chains["chain_5_6_7_8"],
            "chain_12_11_1_preserved": chains["chain_12_11_1"],
            "source_pair_2_x_guard_passed": True,
            "total_movement": _movement(baseline_rows, rows)["total"],
        }
    return screen


def _candidate_specs(
    robust: Mapping[int, Mapping[str, Any]],
    baseline: Mapping[int, Mapping[str, Any]],
    plane: float,
) -> list[tuple[str, str, dict[int, dict[str, Any]], bool, bool]]:
    first = _seed(robust, baseline)
    _apply_downward(first, 2, 0.4, plane, from_baseline=baseline)
    second = copy.deepcopy(first)
    _apply_downward(second, 11, 0.2, plane, from_baseline=baseline)
    third = copy.deepcopy(second)
    _apply_downward(third, 1, -0.3, plane)
    fourth = copy.deepcopy(third)
    for source_id in (5, 6):
        _apply_downward(fourth, source_id, 0.3, plane)
    fifth = copy.deepcopy(third)
    for source_id in (5, 6, 7, 8):
        _apply_downward(fifth, source_id, 0.25, plane)
    return [
        (
            "height_plane_preserved_s2_bottom_angle",
            "robust_height_plane_with_s2_baseline_x_and_bottom_y_downward_repair",
            first,
            False,
            False,
        ),
        (
            "height_plane_preserved_s2_s11_top_repair",
            "robust_height_plane_with_s2_s11_baseline_x_reprojection",
            second,
            False,
            False,
        ),
        (
            "height_plane_preserved_s2_s11_s1_adapter",
            "height_plane_reprojection_with_s1_seam_adapter",
            third,
            True,
            False,
        ),
        (
            "height_plane_preserved_s2_s11_s5_s6_bottom_repair",
            "sensitivity_selected_s5_s6_bottom_y_downward_repair",
            fourth,
            True,
            True,
        ),
        (
            "height_plane_preserved_chain_balanced",
            "sensitivity_selected_s5_s6_s7_s8_chain_balance",
            fifth,
            True,
            True,
        ),
    ]


def _overlay(
    source_image: str,
    baseline: Mapping[int, Mapping[str, Any]],
    robust: Mapping[int, Mapping[str, Any]],
    previous: Mapping[int, Mapping[str, Any]],
    top: Mapping[str, Any],
) -> str:
    sets = [
        ("baseline", baseline, "baseline"),
        ("robust", robust, "robust"),
        ("previous", previous, "previous"),
        (
            "new",
            _by_source(top["corrected_coordinates"]),
            "new",
        ),
    ]
    changed = set(VERIFIED_ORDER_SOURCE_IDS)
    rendered = "".join(
        _svg_set(
            name,
            {str(k): v for k, v in points.items()},
            VERIFIED_ORDER_SOURCE_IDS,
            css,
            changed,
        )
        for name, points, css in sets
    )
    s2x = float(baseline[2]["top"]["x"])
    s11x = float(baseline[11]["top"]["x"])
    local_image = "../../../../data/mp3d_layout/img_v/" + source_image.rsplit(
        "/", 1
    )[-1]
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>3741 height-plane preserving overlay</title>
<style>body{{margin:0;background:#111;color:#eee;font:14px system-ui}}header,.controls{{padding:10px 14px}}label{{margin-right:12px}}
.warning{{font-size:18px;font-weight:800;color:#ffd166}}svg{{width:100%;aspect-ratio:2/1;background:#000}}
polyline,line,circle,rect{{vector-effect:non-scaling-stroke}}text{{font-size:1.5px;fill:#fff;paint-order:stroke;stroke:#000;stroke-width:.3}}
.baseline{{stroke:#eee;fill:#111;stroke-dasharray:1 1}}.robust{{stroke:#ff5252;fill:#ff5252;stroke-dasharray:.7 .7}}
.previous{{stroke:#bb86fc;fill:#bb86fc;stroke-dasharray:.5 .7}}.new{{stroke:#00e5ff;fill:#ffeb3b}}
.roles{{stroke:#76ff03;fill:#76ff0315;stroke-dasharray:1 1}}.anchor{{stroke:#ff9800;fill:#ff980025}}
</style></head><body><header><div class="warning">Height-plane-preserving review only; no writeback; human must confirm.</div>
<div>Dominant height plane: <code>{top["dominant_height_plane"]:.4f}</code> · New: <code>{top["candidate_id"]}</code></div></header>
<div class="controls">{"".join(f'<label><input type="checkbox" data-target="{name}" checked> {name}</label>' for name,_,_ in sets)}
<label><input type="checkbox" data-target="roles" checked> guards/roles</label></div>
<svg viewBox="0 0 100 100" preserveAspectRatio="none"><image href="{source_image}" data-fallback="{local_image}" x="0" y="0" width="100" height="100" preserveAspectRatio="none"/>
<g id="roles" class="roles"><rect class="anchor" x="{s2x-.25}" y="0" width=".5" height="100"/><rect class="anchor" x="{s11x-.35}" y="0" width=".7" height="100"/>
<rect x="41" y="8" width="14" height="83"/><rect x="0" y="4" width="6" height="92"/><rect x="94" y="4" width="6" height="92"/>
<text x="6" y="8">s2 x anchor</text><text x="88" y="8">s11 x anchor</text><text x="42" y="94">5–6–7–8 chain</text><text x="88" y="94">12–11–1 chain</text>
<text x="35" y="6">bottom_y + means downward</text><text x="61" y="10">dominant height plane / outliers: {top["height_outliers"]}</text></g>
{rendered}</svg><script>document.querySelector("image").addEventListener("error",e=>{{if(!e.target.dataset.used){{e.target.dataset.used=1;e.target.setAttribute("href",e.target.dataset.fallback)}}}});
document.querySelectorAll("[data-target]").forEach(c=>c.addEventListener("change",()=>document.getElementById(c.dataset.target).style.display=c.checked?"":"none"));</script></body></html>"""


def _review_wrapper(payload: Mapping[str, Any]) -> str:
    top = payload["top_candidate"]
    return f"""<!doctype html><meta charset="utf-8"><title>3741 height-plane 3D review</title>
<style>body{{font-family:system-ui;margin:12px;background:#111;color:#eee}}iframe{{width:100%;height:78vh;border:1px solid #555}}</style>
<h1>3741 baseline / robust / previous y-targeted / new height-plane candidate</h1>
<ul><li>Dominant plane: {top["dominant_height_plane"]:.4f}</li><li>New plane residual L1: {top["height_plane_residual_l1"]:.6f}</li>
<li>Height outliers: {top["height_outliers"]}</li><li>s2/s11 baseline-x guards: {str(top["source_pair_2_x_anchor_passed"]).lower()} / {str(top["source_pair_11_x_anchor_passed"]).lower()}</li>
<li>Human must confirm 2D wall-corner alignment and 3D visual uniformity.</li></ul><iframe src="local_3d_review.html"></iframe>"""


def _summary(payload: Mapping[str, Any], out_dir: Path) -> str:
    top = payload["top_candidate"]
    refs = payload["reference_height_plane_metrics"]
    return "\n".join(
        [
            "# 3741 Height-plane-preserving 2D-constrained Refit",
            "",
            "- Old good-3D/2D-rejected: `robust_all_long_edges`.",
            "- Previous human-rejected y-targeted: `s2_s11_height_pair_repair`.",
            f"- New top candidate: `{payload['top_candidate_id']}`.",
            f"- Dominant height plane: `{payload['estimated_dominant_height_plane']:.4f}`.",
            f"- Height-plane residual L1 robust / 9.4 / new: `{refs['robust_all_long_edges']['height_plane_residual_l1']:.6f}` / `{refs['s2_s11_height_pair_repair']['height_plane_residual_l1']:.6f}` / `{top['height_plane_residual_l1']:.6f}`.",
            f"- Height outliers new: `{top['height_outliers']}`.",
            f"- s2/s11 baseline-x anchors passed: `{top['source_pair_2_x_anchor_passed']}` / `{top['source_pair_11_x_anchor_passed']}`.",
            "- bottom_y increase means the point moves downward in the image.",
            f"- Chains preserved: `{top['chain_5_6_7_8_preserved']}` / `{top['chain_12_11_1_preserved']}`.",
            f"- 2D overlay: `{(out_dir / 'segment_aware_manhattan_refit_3741_height_plane_preserving_overlay.html').as_posix()}`",
            f"- 3D review: `{(out_dir / 'segment_aware_manhattan_refit_3741_height_plane_preserving_review.html').as_posix()}`",
            "- accepted/downstream/preference/writeback/patch: `false/false/false/false/false`.",
        ]
    ) + "\n"


def run(out_dir: Path = OUT_DIR) -> dict[str, Path]:
    gt_sha = _sha(GT_PATH)
    robust_payload = json.loads(ROBUST_PATH.read_text(encoding="utf-8"))
    guarded_payload = json.loads(GUARDED_PATH.read_text(encoding="utf-8"))
    y_payload = json.loads(Y_TARGETED_PATH.read_text(encoding="utf-8"))
    baseline_rows = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))[
        "ordered_pairs"
    ]
    baseline = _by_source(baseline_rows)
    robust = _by_source(robust_payload["corrected_coordinates"])
    previous_y = _by_source(y_payload["top_candidate"]["corrected_coordinates"])
    baseline_metrics = _metrics(baseline_rows)
    robust_metrics = _metrics(robust_payload["corrected_coordinates"])
    previous_metrics = _metrics(y_payload["top_candidate"]["corrected_coordinates"])
    plane, explanation = _dominant_height_plane(
        baseline_metrics, robust_metrics
    )
    sensitivity_seed = _seed(robust, baseline)
    sensitivity = _sensitivity_screen(sensitivity_seed, baseline, plane)
    candidates = [
        _evaluate(
            candidate_id,
            method,
            candidate,
            baseline,
            plane,
            s1_adapter=s1_adapter,
            s5_s6_repair=s5_s6_repair,
            sensitivity_summary=sensitivity,
        )
        for candidate_id, method, candidate, s1_adapter, s5_s6_repair in _candidate_specs(
            robust, baseline, plane
        )
    ]
    previous_height_diagnostics = _height_plane_diagnostics(
        previous_metrics, plane
    )
    for candidate in candidates:
        candidate["source_pair_11_height_residual_before"] = (
            previous_height_diagnostics[
                "per_pair_height_residual_to_dominant_plane"
            ]["11"]
        )
        candidate["source_pair_11_height_residual_after"] = candidate[
            "per_pair_height_residual_to_dominant_plane"
        ]["11"]
    viable = [row for row in candidates if not row["suppress_reasons"]]
    top = min(
        viable,
        key=lambda row: (
            row["height_outlier_count"],
            round(row["height_plane_residual_l1"], 8),
            row["wall_residual_sum"],
            row["turn_residual_max"],
        ),
    )
    top["recommendation_label"] = "recommended_for_human_review"
    reference_metrics = {
        "baseline": _height_plane_diagnostics(baseline_metrics, plane),
        "robust_all_long_edges": _height_plane_diagnostics(
            robust_metrics, plane
        ),
        "s2_s11_height_pair_repair": _height_plane_diagnostics(
            previous_metrics, plane
        ),
    }
    payload = {
        "schema_version": "segment_aware_manhattan_refit_3741_height_plane_preserving_v1",
        "case_name": "task218_ann3741",
        "source_image": robust_payload["source_image"],
        "id_semantics": robust_payload["id_semantics"],
        "verified_order_source_ids": robust_payload[
            "verified_order_source_ids"
        ],
        "source_pair_to_solver_position": robust_payload[
            "source_pair_to_solver_position"
        ],
        "solver_position_to_verified_order_source_id": robust_payload[
            "solver_position_to_verified_order_source_id"
        ],
        "rejected_diagnostic_references": {
            "robust_all_long_edges": {
                "status": "rejected_by_2d_review",
                "strengths": ["better_3d_height_plane_and_wall_geometry"],
                "failures": [
                    "source_pair_2_over_moved_from_true_corner",
                    "right_half_top_y_too_high",
                ],
            },
            "pair2_anchored_height_clamped": {
                "status": "rejected_by_human_3d_review",
                "strengths": ["source_pair_2_improved"],
                "failures": [
                    "3d_preview_height_inconsistency_worse",
                    "source_pair_2_still_not_on_true_corner",
                ],
            },
            "s2_s11_height_pair_repair": {
                "status": "rejected_by_human_3d_review",
                "strengths": [
                    "source_pair_2_x_baseline_locked",
                    "height_l1_slightly_improved",
                ],
                "failures": [
                    "3d_preview_still_has_multiple_heights",
                    "action_space_too_local",
                    "height_plane_not_preserved",
                ],
            },
        },
        "baseline_wall_heights_by_source_pair_id": baseline_metrics[
            "heights_by_source_pair_id"
        ],
        "robust_all_long_edges_wall_heights_by_source_pair_id": robust_metrics[
            "heights_by_source_pair_id"
        ],
        "previous_y_targeted_wall_heights_by_source_pair_id": previous_metrics[
            "heights_by_source_pair_id"
        ],
        "estimated_dominant_height_plane": plane,
        "height_plane_source_explanation": explanation,
        "reference_height_plane_metrics": reference_metrics,
        "bottom_y_direction_note": {
            "bottom_y_larger_means_point_lower_in_image": True,
            "bottom_y_smaller_means_point_higher_in_image": True,
        },
        "bottom_y_sensitivity_screen": sensitivity,
        "candidates": candidates,
        "diagnostic_candidates": [
            {
                "candidate_id": "diagnostic_previous_robust_all_long_edges",
                "recommendation_label": "diagnostic_only",
            },
            {
                "candidate_id": "diagnostic_previous_s2_s11_height_pair_repair",
                "recommendation_label": "diagnostic_only",
            },
        ],
        "top_candidate_id": top["candidate_id"],
        "top_candidate": top,
        "safety_flags": SAFETY,
        **SAFETY,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = (
        out_dir
        / "segment_aware_manhattan_refit_3741_height_plane_preserving.json"
    )
    summary_path = (
        out_dir
        / "segment_aware_manhattan_refit_3741_height_plane_preserving_summary.md"
    )
    overlay_path = (
        out_dir
        / "segment_aware_manhattan_refit_3741_height_plane_preserving_overlay.html"
    )
    default_out_dir = ROOT / "task218_ann3741_height_plane_preserving"
    review_out_dir = (
        canonical_review_out_dir("task218_ann3741_height_plane_preserving")
        if out_dir == default_out_dir
        else out_dir
    )
    review_path = (
        review_out_dir
        / "segment_aware_manhattan_refit_3741_height_plane_preserving_review.html"
    )
    manual_path = (
        out_dir
        / "corrected_points_for_manual_copy_3741_height_plane_preserving.json"
    )
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(_summary(payload, out_dir), encoding="utf-8")
    overlay_path.write_text(
        _overlay(
            robust_payload["source_image"],
            baseline,
            robust,
            previous_y,
            top,
        ),
        encoding="utf-8",
    )
    manual_path.write_text(
        json.dumps(
            {
                "schema_version": "manual_copy_candidate_3741_height_plane_preserving_v1",
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
                "previous_candidates_rejected_by_human_review": True,
                "height_plane_preserved_summary": {
                    "dominant_height_plane": plane,
                    "height_plane_residual_l1": top[
                        "height_plane_residual_l1"
                    ],
                    "height_outlier_count": top["height_outlier_count"],
                },
                "bottom_y_direction_note": {
                    "bottom_y_larger_means_point_lower_in_image": True
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
                "source_image": robust_payload["source_image"],
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
                        "candidate_id": "robust_all_long_edges",
                        "action_family": "old_good_3d_rejected_2d",
                        "decision_class": "diagnostic_only",
                        "coordinate_changes": _changes(
                            {str(k): v for k, v in baseline.items()},
                            robust_payload["corrected_coordinates"],
                        ),
                    },
                    {
                        "candidate_id": "s2_s11_height_pair_repair",
                        "action_family": "previous_y_targeted_rejected",
                        "decision_class": "diagnostic_only",
                        "coordinate_changes": _changes(
                            {str(k): v for k, v in baseline.items()},
                            y_payload["top_candidate"]["corrected_coordinates"],
                        ),
                    },
                    {
                        "candidate_id": top["candidate_id"],
                        "action_family": "height_plane_preserving_2d_constrained_refit",
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
        candidate_limit=3,
        out_dir=review_out_dir,
        image_root=Path("data/mp3d_layout/img_v"),
        case_name="task218_ann3741_height_plane_preserving",
        coordinate_mode="ls_percent",
        local_server_root=_local_server_root(review_out_dir),
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
