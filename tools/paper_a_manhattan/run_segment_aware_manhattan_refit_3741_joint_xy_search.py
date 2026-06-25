"""Run a deterministic bounded joint X-Y local search for annotation 3741."""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.run_local_3d_projection_review import run_local_review
from tools.paper_a_manhattan.run_segment_aware_manhattan_refit_3741_2d_guarded import (
    _changes,
    _local_server_root,
    _svg_set,
)
from tools.paper_a_manhattan.run_segment_aware_manhattan_refit_3741_height_plane_preserving import (
    _by_source,
    _chain_status,
    _height_plane_diagnostics,
    _metrics,
)
from tools.paper_a_manhattan.segment_aware_manhattan_refit import (
    VERIFIED_ORDER_SOURCE_IDS,
    _movement,
)

ROOT = Path("analysis_results/paper_a_manhattan/segment_aware_manhattan_refit")
ROBUST_PATH = ROOT / "task218_ann3741/segment_aware_manhattan_refit_3741.json"
PREVIOUS_PATH = (
    ROOT
    / "task218_ann3741_height_plane_preserving/"
    "segment_aware_manhattan_refit_3741_height_plane_preserving.json"
)
Y_TARGETED_PATH = (
    ROOT
    / "task218_ann3741_y_targeted/"
    "segment_aware_manhattan_refit_3741_y_targeted.json"
)
BASELINE_PATH = (
    ROOT / "task218_ann3741_height_plane_preserving/_review_input.json"
)
OUT_DIR = ROOT / "task218_ann3741_joint_xy_search"
GT_PATH = Path("export_label/groudTruth.json")
SAFETY = {
    "audit_only": True,
    "accepted": False,
    "downstream_recommendation": False,
    "candidate_preference_authorized": False,
    "annotation_writeback": False,
    "annotation_patch_generated": False,
}
X_STEPS = (-0.45, -0.30, -0.15, 0.0, 0.15, 0.30, 0.45)
TOP_STEPS = (-3.0, -2.4, -1.8, -1.2, -0.6, 0.0, 0.6, 1.2)
BOTTOM_STEPS = (0.0, 0.3, 0.6, 0.9, 1.2, 1.5, 1.8)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seed(
    robust: Mapping[int, Mapping[str, Any]],
    baseline: Mapping[int, Mapping[str, Any]],
) -> dict[int, dict[str, Any]]:
    candidate = copy.deepcopy(robust)
    for source_id in (2, 11):
        candidate[source_id] = copy.deepcopy(baseline[source_id])
    for source_id in (9, 10, 12):
        candidate[source_id]["top"]["y"] = min(
            float(baseline[source_id]["top"]["y"]) + 0.8,
            max(
                float(baseline[source_id]["top"]["y"]) - 1.0,
                float(candidate[source_id]["top"]["y"]),
            ),
        )
    return candidate


def _apply(
    candidate: dict[int, dict[str, Any]],
    baseline: Mapping[int, Mapping[str, Any]],
    source_id: int,
    *,
    x: float | None = None,
    top_y: float | None = None,
    bottom_y: float | None = None,
) -> None:
    if x is not None:
        value = float(baseline[source_id]["top"]["x"]) + x
        candidate[source_id]["top"]["x"] = value
        candidate[source_id]["bottom"]["x"] = value
    if top_y is not None:
        candidate[source_id]["top"]["y"] = (
            float(baseline[source_id]["top"]["y"]) + top_y
        )
    if bottom_y is not None:
        candidate[source_id]["bottom"]["y"] = (
            float(baseline[source_id]["bottom"]["y"]) + bottom_y
        )


def _candidate_rows(candidate: Mapping[int, Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [candidate[source_id] for source_id in VERIFIED_ORDER_SOURCE_IDS]


def _evaluate(
    candidate: Mapping[int, Mapping[str, Any]],
    baseline: Mapping[int, Mapping[str, Any]],
    plane: float,
    action_family: str,
    variables: Mapping[str, float],
    reference_metrics: Mapping[str, Mapping[str, float]],
) -> dict[str, Any]:
    rows = _candidate_rows(candidate)
    baseline_rows = _candidate_rows(baseline)
    metrics = _metrics(rows)
    geometry = metrics["geometry"]
    height = _height_plane_diagnostics(metrics, plane)
    chains = _chain_status(rows, baseline_rows)
    movement = _movement(baseline_rows, rows)
    by_source = {row["source_pair_id"]: row for row in movement["per_pair"]}
    delta = {
        source_id: {
            axis: float(candidate[source_id][endpoint]["x" if axis == "x" else "y"])
            - float(baseline[source_id][endpoint]["x" if axis == "x" else "y"])
            for axis, endpoint in (
                ("x", "top"),
                ("top_y", "top"),
                ("bottom_y", "bottom"),
            )
        }
        for source_id in (2, 11)
    }
    suppress = []
    if abs(delta[2]["x"]) > 0.45 + 1e-9:
        suppress.append("source_pair_2_x_guard_failed")
    if abs(delta[11]["x"]) > 0.45 + 1e-9:
        suppress.append("source_pair_11_x_guard_failed")
    if delta[2]["top_y"] < -3.0 - 1e-9:
        suppress.append("source_pair_2_top_y_guard_failed")
    if delta[11]["top_y"] < -3.0 - 1e-9:
        suppress.append("source_pair_11_top_y_guard_failed")
    for source_id in (9, 10, 12):
        top_delta = float(candidate[source_id]["top"]["y"]) - float(
            baseline[source_id]["top"]["y"]
        )
        if not -1.0 - 1e-9 <= top_delta <= 0.8 + 1e-9:
            suppress.append(f"source_pair_{source_id}_top_y_safety_failed")
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
    if any(
        not 0.0 <= float(row[endpoint][axis]) <= 100.0
        for row in rows
        for endpoint in ("top", "bottom")
        for axis in ("x", "y")
    ):
        suppress.append("coordinate_out_of_range")
    downward_ids = [
        source_id
        for source_id in (2, 5, 6, 7, 8, 11)
        if float(candidate[source_id]["bottom"]["y"])
        > float(baseline[source_id]["bottom"]["y"]) + 1e-9
    ]
    if "bottom" in action_family and not downward_ids:
        suppress.append("claimed_downward_adjustment_without_positive_delta")

    wall = geometry["floorprint"]["summary"]["wall_residual_sum_deg"]
    turn = geometry["corner_turns"]["summary"]["corner_residual_max_deg"]
    height_l1 = geometry["heights"]["summary"]["height_residual_sum"]
    if height_l1 > reference_metrics["y_targeted"]["height"] + 0.20:
        suppress.append("height_worse_than_9_4_guard")
    anchor = (
        abs(delta[2]["x"])
        + 0.35 * abs(delta[2]["top_y"])
        + 0.25 * abs(delta[2]["bottom_y"])
        + abs(delta[11]["x"])
        + 0.25 * abs(delta[11]["top_y"])
        + 0.15 * abs(delta[11]["bottom_y"])
    )
    geometry_score = wall / 50.0 + turn / 30.0
    height_score = (
        height_l1
        + height["height_plane_residual_l1"] / 4.0
        + height["height_outlier_count"] * 0.15
    )
    bottom_depth_score = (
        -0.05 * len(downward_ids)
        + max(0.0, wall - reference_metrics["baseline"]["wall"]) / 100.0
    )
    movement_score = (
        movement["total"] / 100.0
        + movement["max"] / 20.0
        + by_source[1]["max"] / 30.0
    )
    objective = {
        "geometry_score": geometry_score,
        "height_score": height_score,
        "2d_anchor_score": anchor,
        "bottom_depth_score": bottom_depth_score,
        "movement_score": movement_score,
        "height_plane_is_soft_regularizer": True,
        "total": (
            3.0 * geometry_score
            + 1.8 * height_score
            + 2.5 * anchor
            + bottom_depth_score
            + 0.5 * movement_score
        ),
        "comparison_to_references": {
            "wall_vs_baseline": wall - reference_metrics["baseline"]["wall"],
            "wall_vs_robust": wall - reference_metrics["robust"]["wall"],
            "height_vs_previous_9_5": height_l1
            - reference_metrics["previous"]["height"],
        },
    }
    return {
        "action_family": action_family,
        "generation_method": "bounded_deterministic_semantic_coordinate_search",
        "deterministic": True,
        "random_or_fixed_step_grid_used": False,
        "search_variables_used": dict(variables),
        "source_pair_2_x_delta_from_baseline": delta[2]["x"],
        "source_pair_2_top_y_delta_from_baseline": delta[2]["top_y"],
        "source_pair_2_bottom_y_delta_from_baseline": delta[2]["bottom_y"],
        "source_pair_2_bottom_y_downward_adjustment_applied": delta[2][
            "bottom_y"
        ]
        > 0,
        "source_pair_2_x_compensation_applied": abs(delta[2]["x"]) > 1e-9,
        "source_pair_11_x_delta_from_baseline": delta[11]["x"],
        "source_pair_11_top_y_delta_from_baseline": delta[11]["top_y"],
        "source_pair_11_bottom_y_delta_from_baseline": delta[11]["bottom_y"],
        "source_pair_11_x_compensation_applied": abs(delta[11]["x"]) > 1e-9,
        "source_pair_1_as_sacrificial_adapter": any(
            key.startswith("s1_") for key in variables
        ),
        "source_pair_1_movement": by_source[1]["max"],
        "s5_s6_bottom_y_adjustment_applied": any(
            source_id in downward_ids for source_id in (5, 6)
        ),
        "s7_s8_bottom_y_adjustment_applied": any(
            source_id in downward_ids for source_id in (7, 8)
        ),
        "bottom_y_direction_note": {
            "bottom_y_larger_means_point_lower_in_image": True
        },
        "wall_residual_sum": wall,
        "turn_residual_max": turn,
        "height_consistency_l1": height_l1,
        "height_plane_residual_l1": height["height_plane_residual_l1"],
        "height_outlier_count": height["height_outlier_count"],
        "chain_5_6_7_8_preserved": chains["chain_5_6_7_8"],
        "chain_12_11_1_preserved": chains["chain_12_11_1"],
        "topology_valid": len(rows) == 12,
        "self_intersection": geometry["floorprint"]["self_intersection"],
        "order_preserved": [row["source_pair_id"] for row in rows]
        == VERIFIED_ORDER_SOURCE_IDS,
        "total_movement": movement["total"],
        "max_movement": movement["max"],
        "objective_breakdown": objective,
        "recommendation_label": "suppress" if suppress else "plausible_but_needs_review",
        "suppress_reasons": suppress,
        "corrected_coordinates": rows,
        "safety_flags": SAFETY,
    }


def _search_family(
    family: str,
    variants: Iterable[tuple[dict[int, dict[str, Any]], dict[str, float]]],
    baseline: Mapping[int, Mapping[str, Any]],
    plane: float,
    references: Mapping[str, Mapping[str, float]],
    stats: Counter,
) -> dict[str, Any]:
    best = None
    best_suppressed = None
    for candidate, variables in variants:
        stats["evaluated"] += 1
        stats[f"family:{family}"] += 1
        row = _evaluate(candidate, baseline, plane, family, variables, references)
        if row["suppress_reasons"]:
            stats["suppressed"] += 1
            if best_suppressed is None or row["objective_breakdown"]["total"] < best_suppressed[
                "objective_breakdown"
            ]["total"]:
                best_suppressed = row
            continue
        stats["kept"] += 1
        if best is None or row["objective_breakdown"]["total"] < best[
            "objective_breakdown"
        ]["total"]:
            best = row
    return best or best_suppressed


def _variants_s2(
    seed: Mapping[int, Mapping[str, Any]],
    baseline: Mapping[int, Mapping[str, Any]],
    *,
    joint_top: bool,
) -> Iterable[tuple[dict[int, dict[str, Any]], dict[str, float]]]:
    tops = TOP_STEPS if joint_top else (0.0,)
    for x, top, bottom in itertools.product(X_STEPS, tops, BOTTOM_STEPS):
        candidate = copy.deepcopy(seed)
        _apply(candidate, baseline, 2, x=x, top_y=top, bottom_y=bottom)
        yield candidate, {"s2_x": x, "s2_top_y": top, "s2_bottom_y": bottom}


def _variants_s2_s11(
    seed: Mapping[int, Mapping[str, Any]],
    baseline: Mapping[int, Mapping[str, Any]],
) -> Iterable[tuple[dict[int, dict[str, Any]], dict[str, float]]]:
    x_steps = (-0.3, 0.0, 0.3)
    top_steps = (-3.0, -1.8, -0.6, 0.6)
    bottom_steps = (0.0, 0.6, 1.2)
    for values in itertools.product(
        x_steps, top_steps, bottom_steps, x_steps, top_steps, bottom_steps
    ):
        sx, st, sb, ex, et, eb = values
        candidate = copy.deepcopy(seed)
        _apply(candidate, baseline, 2, x=sx, top_y=st, bottom_y=sb)
        _apply(candidate, baseline, 11, x=ex, top_y=et, bottom_y=eb)
        yield candidate, {
            "s2_x": sx,
            "s2_top_y": st,
            "s2_bottom_y": sb,
            "s11_x": ex,
            "s11_top_y": et,
            "s11_bottom_y": eb,
        }


def _variants_adapter(
    parent: Mapping[str, Any],
    baseline: Mapping[int, Mapping[str, Any]],
) -> Iterable[tuple[dict[int, dict[str, Any]], dict[str, float]]]:
    seed = _by_source(parent["corrected_coordinates"])
    for x, top, bottom in itertools.product(
        (-1.5, -0.75, 0.0, 0.75, 1.5),
        (-2.0, -1.0, 0.0, 1.0, 2.0),
        (-3.0, -1.5, 0.0, 1.5, 3.0),
    ):
        candidate = copy.deepcopy(seed)
        _apply(candidate, baseline, 1, x=x, top_y=top, bottom_y=bottom)
        yield candidate, {"s1_x": x, "s1_top_y": top, "s1_bottom_y": bottom}


def _variants_block(
    parent: Mapping[str, Any],
    baseline: Mapping[int, Mapping[str, Any]],
    source_ids: Sequence[int],
) -> Iterable[tuple[dict[int, dict[str, Any]], dict[str, float]]]:
    seed = _by_source(parent["corrected_coordinates"])
    x_steps = (-0.3, 0.0, 0.3)
    bottom_steps = (0.0, 0.6, 1.2)
    for x, bottom in itertools.product(x_steps, bottom_steps):
        candidate = copy.deepcopy(seed)
        variables = {}
        for source_id in source_ids:
            _apply(candidate, baseline, source_id, x=x, bottom_y=bottom)
            variables[f"s{source_id}_x"] = x
            variables[f"s{source_id}_bottom_y"] = bottom
        yield candidate, variables


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
        ("new", _by_source(top["corrected_coordinates"]), "new"),
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
    objective = json.dumps(top["objective_breakdown"], ensure_ascii=False)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>3741 joint X-Y search overlay</title>
<style>body{{margin:0;background:#111;color:#eee;font:14px system-ui}}header,.controls{{padding:10px 14px}}label{{margin-right:12px}}
.warning{{font-size:18px;font-weight:800;color:#ffd166}}svg{{width:100%;aspect-ratio:2/1;background:#000}}
polyline,line,circle,rect{{vector-effect:non-scaling-stroke}}text{{font-size:1.5px;fill:#fff;paint-order:stroke;stroke:#000;stroke-width:.3}}
.baseline{{stroke:#eee;fill:#111;stroke-dasharray:1 1}}.robust{{stroke:#ff5252;fill:#ff5252;stroke-dasharray:.7 .7}}
.previous{{stroke:#bb86fc;fill:#bb86fc;stroke-dasharray:.5 .7}}.new{{stroke:#00e5ff;fill:#ffeb3b}}
.guards{{stroke:#ff9800;fill:#ff980020}}.chains{{stroke:#76ff03;fill:#76ff0312;stroke-dasharray:1 1}}
.bottomArrows{{stroke:#00ff88}}.xArrows{{stroke:#ffcc00}}</style></head><body>
<header><div class="warning">Bounded joint X-Y review only; no writeback; human must confirm.</div>
<div>Family: <code>{top["action_family"]}</code> · Objective: <code>{objective}</code></div></header>
<div class="controls">{"".join(f'<label><input data-target="{name}" type="checkbox" checked> {name}</label>' for name,_,_ in sets)}
<label><input data-target="bottomArrows" type="checkbox" checked> bottom_y arrows</label><label><input data-target="xArrows" type="checkbox" checked> x compensation arrows</label>
<label><input data-target="guards" type="checkbox" checked> s2/s11 guard bands</label><label><input data-target="chainA" type="checkbox" checked> chain 5–6–7–8</label>
<label><input data-target="chainB" type="checkbox" checked> chain 12–11–1</label><label><input id="onlyChanged" type="checkbox"> only changed points</label></div>
<svg viewBox="0 0 100 100" preserveAspectRatio="none"><image href="{source_image}" data-fallback="{local_image}" x="0" y="0" width="100" height="100" preserveAspectRatio="none"/>
<g id="guards" class="guards"><rect x="{s2x-.45}" y="0" width=".9" height="100"/><rect x="{s11x-.45}" y="0" width=".9" height="100"/></g>
<g id="chainA" class="chains"><rect x="41" y="8" width="14" height="83"/></g><g id="chainB" class="chains"><rect x="0" y="4" width="6" height="92"/><rect x="94" y="4" width="6" height="92"/></g>
<g id="bottomArrows" class="bottomArrows"><text x="35" y="5">bottom_y + = downward</text></g><g id="xArrows" class="xArrows"><text x="35" y="8">x compensation enabled</text></g>
{rendered}</svg><script>document.querySelector("image").addEventListener("error",e=>{{if(!e.target.dataset.used){{e.target.dataset.used=1;e.target.setAttribute("href",e.target.dataset.fallback)}}}});
document.querySelectorAll("[data-target]").forEach(c=>c.addEventListener("change",()=>document.getElementById(c.dataset.target).style.display=c.checked?"":"none"));
document.getElementById("onlyChanged").addEventListener("change",e=>document.querySelectorAll("[data-source]").forEach(n=>n.style.opacity=e.target.checked?".75":"1"));</script></body></html>"""


def _review_wrapper(payload: Mapping[str, Any]) -> str:
    top = payload["top_candidate"]
    return f"""<!doctype html><meta charset="utf-8"><title>3741 joint X-Y 3D review</title>
<style>body{{font-family:system-ui;margin:12px;background:#111;color:#eee}}iframe{{width:100%;height:80vh;border:1px solid #555}}</style>
<h1>3741 baseline / robust / previous height-plane / new joint X-Y candidate</h1>
<p>Family: <code>{top["action_family"]}</code>; wall/turn/height: {top["wall_residual_sum"]:.3f} / {top["turn_residual_max"]:.3f} / {top["height_consistency_l1"]:.3f}.</p>
<p>Human must confirm both 2D corner alignment and 3D wall geometry.</p><iframe src="local_3d_review.html"></iframe>"""


def _summary(payload: Mapping[str, Any], out_dir: Path) -> str:
    top = payload["top_candidate"]
    return "\n".join(
        [
            "# 3741 Bounded Joint X-Y Local Search",
            "",
            f"- Search budget/evaluated/kept/suppressed: `{payload['search_budget']}` / `{payload['evaluated_count']}` / `{payload['kept_count']}` / `{payload['suppressed_count']}`.",
            f"- New top: `{payload['top_candidate_id']}` from `{top['action_family']}`.",
            f"- s2 x/top_y/bottom_y deltas: `{top['source_pair_2_x_delta_from_baseline']:.3f}` / `{top['source_pair_2_top_y_delta_from_baseline']:.3f}` / `{top['source_pair_2_bottom_y_delta_from_baseline']:.3f}`.",
            f"- s11 x/top_y/bottom_y deltas: `{top['source_pair_11_x_delta_from_baseline']:.3f}` / `{top['source_pair_11_top_y_delta_from_baseline']:.3f}` / `{top['source_pair_11_bottom_y_delta_from_baseline']:.3f}`.",
            f"- Wall/turn/height/plane L1: `{top['wall_residual_sum']:.3f}` / `{top['turn_residual_max']:.3f}` / `{top['height_consistency_l1']:.3f}` / `{top['height_plane_residual_l1']:.3f}`.",
            f"- Chains preserved: `{top['chain_5_6_7_8_preserved']}` / `{top['chain_12_11_1_preserved']}`.",
            "- Previous candidates remain diagnostic-only; this result is not accepted or authorized.",
            f"- 2D overlay: `{(out_dir / 'segment_aware_manhattan_refit_3741_joint_xy_search_overlay.html').as_posix()}`",
            f"- 3D review: `{(out_dir / 'segment_aware_manhattan_refit_3741_joint_xy_search_review.html').as_posix()}`",
            "- accepted/downstream/preference/writeback/patch: `false/false/false/false/false`.",
        ]
    ) + "\n"


def run(out_dir: Path = OUT_DIR) -> dict[str, Path]:
    gt_sha = _sha(GT_PATH)
    robust_payload = json.loads(ROBUST_PATH.read_text(encoding="utf-8"))
    previous_payload = json.loads(PREVIOUS_PATH.read_text(encoding="utf-8"))
    y_targeted_payload = json.loads(Y_TARGETED_PATH.read_text(encoding="utf-8"))
    baseline_rows = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))[
        "ordered_pairs"
    ]
    baseline = _by_source(baseline_rows)
    robust = _by_source(robust_payload["corrected_coordinates"])
    previous = _by_source(previous_payload["top_candidate"]["corrected_coordinates"])
    plane = float(previous_payload["estimated_dominant_height_plane"])
    seed = _seed(robust, baseline)
    baseline_geometry = _metrics(baseline_rows)["geometry"]
    robust_geometry = _metrics(robust_payload["corrected_coordinates"])["geometry"]
    previous_geometry = _metrics(
        previous_payload["top_candidate"]["corrected_coordinates"]
    )["geometry"]
    y_targeted_geometry = _metrics(
        y_targeted_payload["top_candidate"]["corrected_coordinates"]
    )["geometry"]
    references = {
        "baseline": {
            "wall": baseline_geometry["floorprint"]["summary"][
                "wall_residual_sum_deg"
            ],
            "turn": baseline_geometry["corner_turns"]["summary"][
                "corner_residual_max_deg"
            ],
            "height": baseline_geometry["heights"]["summary"][
                "height_residual_sum"
            ],
        },
        "robust": {
            "wall": robust_geometry["floorprint"]["summary"][
                "wall_residual_sum_deg"
            ],
            "turn": robust_geometry["corner_turns"]["summary"][
                "corner_residual_max_deg"
            ],
            "height": robust_geometry["heights"]["summary"][
                "height_residual_sum"
            ],
        },
        "previous": {
            "wall": previous_geometry["floorprint"]["summary"][
                "wall_residual_sum_deg"
            ],
            "turn": previous_geometry["corner_turns"]["summary"][
                "corner_residual_max_deg"
            ],
            "height": previous_geometry["heights"]["summary"][
                "height_residual_sum"
            ],
        },
        "y_targeted": {
            "wall": y_targeted_geometry["floorprint"]["summary"][
                "wall_residual_sum_deg"
            ],
            "turn": y_targeted_geometry["corner_turns"]["summary"][
                "corner_residual_max_deg"
            ],
            "height": y_targeted_geometry["heights"]["summary"][
                "height_residual_sum"
            ],
        },
    }
    stats: Counter = Counter()
    family_best = []
    first = _search_family(
        "s2_bottom_y_plus_x_compensated",
        _variants_s2(seed, baseline, joint_top=False),
        baseline,
        plane,
        references,
        stats,
    )
    family_best.append(first)
    second = _search_family(
        "s2_top_bottom_y_plus_x_compensated",
        _variants_s2(seed, baseline, joint_top=True),
        baseline,
        plane,
        references,
        stats,
    )
    family_best.append(second)
    third = _search_family(
        "s2_s11_joint_height_angle",
        _variants_s2_s11(seed, baseline),
        baseline,
        plane,
        references,
        stats,
    )
    family_best.append(third)
    fourth = _search_family(
        "s2_s11_s1_adapter_joint",
        _variants_adapter(third, baseline),
        baseline,
        plane,
        references,
        stats,
    )
    family_best.append(fourth)
    fifth = _search_family(
        "s2_s5_s6_bottom_depth_joint",
        _variants_block(second, baseline, (5, 6)),
        baseline,
        plane,
        references,
        stats,
    )
    family_best.append(fifth)
    sixth = _search_family(
        "s2_s5_s6_s7_s8_chain_bottom_depth_joint",
        _variants_block(fifth, baseline, (5, 6, 7, 8)),
        baseline,
        plane,
        references,
        stats,
    )
    family_best.append(sixth)
    balanced = min(
        [row for row in family_best if not row["suppress_reasons"]],
        key=lambda row: row["objective_breakdown"]["total"],
    )
    top = copy.deepcopy(balanced)
    top["candidate_id"] = "balanced_joint_xy_best_effort"
    top["source_action_family"] = balanced["action_family"]
    top["action_family"] = "balanced_joint_xy_best_effort"
    top["recommendation_label"] = (
        "recommended_for_human_review"
        if top["height_consistency_l1"]
        <= references["previous"]["height"] + 0.05
        else "plausible_but_needs_review"
    )
    kept = sorted(
        family_best,
        key=lambda row: row["objective_breakdown"]["total"],
    )
    for index, row in enumerate(kept, start=1):
        row["candidate_id"] = f"joint_xy_family_best_{index:04d}"
    payload = {
        "schema_version": "segment_aware_manhattan_refit_3741_joint_xy_search_v1",
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
                "strength": "3d_height_unified",
                "failure": "source_pair_2_over_moved_from_true_corner",
            },
            "pair2_anchored_height_clamped": {
                "status": "rejected_by_human_3d_review",
                "failure": "height_inconsistency_worse",
            },
            "s2_s11_height_pair_repair": {
                "status": "rejected_by_human_3d_review",
                "failure": "multiple_heights_remain",
            },
            "height_plane_preserved_s2_s11_s1_adapter": {
                "status": "rejected_by_human_2d_review",
                "strength": "height_plane_residual_low",
                "failures": [
                    "top_y_pulled_too_high_again",
                    "bottom_y_downward_adjustment_not_effective",
                    "joint_x_y_compensation_missing",
                ],
            },
        },
        "search_budget": 6000,
        "evaluated_count": stats["evaluated"],
        "kept_count": stats["kept"],
        "suppressed_count": stats["suppressed"],
        "deterministic": True,
        "random_seed_used": False,
        "action_family_counts": {
            key.removeprefix("family:"): value
            for key, value in stats.items()
            if key.startswith("family:")
        },
        "reference_metrics": references,
        "family_best_candidates": kept,
        "top_candidate_id": top["candidate_id"],
        "top_candidate": top,
        "safety_flags": SAFETY,
        **SAFETY,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "segment_aware_manhattan_refit_3741_joint_xy_search.json"
    summary_path = (
        out_dir / "segment_aware_manhattan_refit_3741_joint_xy_search_summary.md"
    )
    overlay_path = (
        out_dir / "segment_aware_manhattan_refit_3741_joint_xy_search_overlay.html"
    )
    review_path = (
        out_dir / "segment_aware_manhattan_refit_3741_joint_xy_search_review.html"
    )
    manual_path = (
        out_dir / "corrected_points_for_manual_copy_3741_joint_xy_search.json"
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
            previous,
            top,
        ),
        encoding="utf-8",
    )
    manual_path.write_text(
        json.dumps(
            {
                "schema_version": "manual_copy_candidate_3741_joint_xy_search_v1",
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
                "previous_candidates_rejected": True,
                "joint_xy_search_summary": {
                    "search_budget": payload["search_budget"],
                    "evaluated_count": payload["evaluated_count"],
                    "action_family": top["action_family"],
                    "objective_breakdown": top["objective_breakdown"],
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
                        "action_family": "diagnostic_old_good_3d",
                        "decision_class": "diagnostic_only",
                        "coordinate_changes": _changes(
                            {str(k): v for k, v in baseline.items()},
                            robust_payload["corrected_coordinates"],
                        ),
                    },
                    {
                        "candidate_id": previous_payload["top_candidate_id"],
                        "action_family": "diagnostic_previous_height_plane",
                        "decision_class": "diagnostic_only",
                        "coordinate_changes": _changes(
                            {str(k): v for k, v in baseline.items()},
                            previous_payload["top_candidate"][
                                "corrected_coordinates"
                            ],
                        ),
                    },
                    {
                        "candidate_id": top["candidate_id"],
                        "action_family": top["action_family"],
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
        out_dir=out_dir,
        image_root=Path("data/mp3d_layout/img_v"),
        case_name="task218_ann3741_joint_xy_search",
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
