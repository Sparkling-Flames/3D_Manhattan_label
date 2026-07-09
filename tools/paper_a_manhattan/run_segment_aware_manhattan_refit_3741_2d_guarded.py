"""Materialize deterministic, human-guided 2D-guarded refit candidates for 3741."""

from __future__ import annotations

import hashlib
import html
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.run_local_3d_projection_review import (
    canonical_review_out_dir,
    run_local_review,
)
from tools.paper_a_manhattan.segment_aware_manhattan_refit import (
    PAIR2_GUARD,
    RIGHT_TOP_Y_GUARDS,
    build_2d_guarded_candidates,
)

ROOT = Path(
    "analysis_results/paper_a_manhattan/segment_aware_manhattan_refit"
)
REFIT_PATH = ROOT / "task218_ann3741/segment_aware_manhattan_refit_3741.json"
OVERLAY_PATH = (
    ROOT
    / "task218_ann3741/segment_aware_manhattan_refit_3741_2d_overlay_payload.json"
)
OUT_DIR = ROOT / "task218_ann3741_2d_guarded"
GT_PATH = Path("export_label/groudTruth.json")
REJECT_REASONS = [
    "source_pair_2_over_moved_from_true_corner",
    "right_half_top_y_too_high",
    "source_pairs_7_9_10_11_12_top_y_too_high",
    "2d_alignment_not_human_confirmed",
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


def _local_server_root(out_dir: Path) -> Path | None:
    try:
        out_dir.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        return None
    return REPO_ROOT


def _changes(
    before: Mapping[str, Mapping[str, Any]],
    after: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for row in after:
        source_id = str(row["source_pair_id"])
        old = before[source_id]
        fields = {}
        for field, endpoint, axis in (
            ("top_x", "top", "x"),
            ("top_y", "top", "y"),
            ("bottom_x", "bottom", "x"),
            ("bottom_y", "bottom", "y"),
        ):
            left, right = float(old[endpoint][axis]), float(row[endpoint][axis])
            fields[field] = {
                "before": left,
                "after": right,
                "delta": right - left,
                "changed": abs(right - left) > 1e-9,
            }
        rows.append(
            {
                "source_pair_id": int(source_id),
                "solver_position": int(row["solver_position"]),
                "verified_order_source_id": int(source_id),
                "source_preview_order_index": int(source_id),
                "effective_pair_index": int(row["solver_position"]),
                "fields": fields,
            }
        )
    return rows


def _old_reference(refit: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    old = refit["top_candidate"]
    deltas = overlay["deltas_by_source_pair_id"]
    violations = [
        source_id
        for source_id, limit in RIGHT_TOP_Y_GUARDS.items()
        if deltas[str(source_id)]["fields"]["top_y"]["delta"] < -limit
    ]
    return {
        "candidate_id": refit["top_candidate_id"],
        "rejected_by_2d_review": True,
        "reject_reasons": REJECT_REASONS,
        "recommendation_label": "diagnostic_only",
        "source_pair_2_guard_passed": False,
        "source_pair_2_top_movement": deltas["2"]["top_movement"],
        "source_pair_2_bottom_movement": deltas["2"]["bottom_movement"],
        "right_half_top_y_guard_passed": False,
        "right_half_top_y_violations": violations,
        "chain_5_6_7_8_preserved": old["metrics"][
            "chain_5_6_7_8_preserved"
        ],
        "chain_12_11_1_preserved": old["metrics"][
            "chain_12_11_1_preserved"
        ],
        "topology_valid": old["metrics"]["topology_valid"],
        "self_intersection": old["metrics"]["self_intersection"],
        "order_preserved": old["metrics"]["order_preserved"],
        "strong_anchor_3_4_movement": old["metrics"][
            "strong_anchor_movement"
        ],
        "height_moderation_applied": False,
        "top_y_changes_by_source_pair_id": {
            source_id: row["fields"]["top_y"]["delta"]
            for source_id, row in deltas.items()
        },
        "total_movement": old["metrics"]["total_movement"],
        "max_movement": old["metrics"]["max_movement"],
        "suppress_reasons": REJECT_REASONS,
        "corrected_coordinates": refit["corrected_coordinates"],
        "safety_flags": SAFETY,
    }


def _svg_polyline(
    points: Mapping[str, Mapping[str, Any]],
    order: Sequence[int],
    endpoint: str,
) -> str:
    chunks, current = [], []
    previous_x = None
    for source_id in order:
        point = points[str(source_id)][endpoint]
        if previous_x is not None and abs(float(point["x"]) - previous_x) > 50:
            chunks.append(" ".join(current))
            current = []
        current.append(f'{float(point["x"]):.4f},{float(point["y"]):.4f}')
        previous_x = float(point["x"])
    chunks.append(" ".join(current))
    return "".join(
        f'<polyline points="{chunk}" fill="none"/>' for chunk in chunks if chunk
    )


def _svg_set(
    name: str,
    points: Mapping[str, Mapping[str, Any]],
    order: Sequence[int],
    css_class: str,
    changed_ids: set[int],
) -> str:
    rows = [
        f'<g id="{name}" class="{css_class}">',
        _svg_polyline(points, order, "top"),
        _svg_polyline(points, order, "bottom"),
    ]
    for source_id in order:
        pair = points[str(source_id)]
        rows.append(
            f'<g data-source="{source_id}" data-changed="{str(source_id in changed_ids).lower()}">'
            f'<line x1="{pair["top"]["x"]}" y1="{pair["top"]["y"]}" '
            f'x2="{pair["bottom"]["x"]}" y2="{pair["bottom"]["y"]}"/>'
            f'<circle cx="{pair["top"]["x"]}" cy="{pair["top"]["y"]}" r=".55"/>'
            f'<circle cx="{pair["bottom"]["x"]}" cy="{pair["bottom"]["y"]}" r=".55"/>'
            f'<text class="labels" x="{float(pair["top"]["x"])+.7}" '
            f'y="{float(pair["top"]["y"])-.7}">s{source_id}</text></g>'
        )
    rows.append("</g>")
    return "".join(rows)


def _guarded_overlay(
    overlay: dict[str, Any],
    old: dict[str, Any],
    top: dict[str, Any],
) -> str:
    order = overlay["verified_order_source_ids"]
    baseline = overlay["baseline_points_by_source_pair_id"]
    old_points = {str(row["source_pair_id"]): row for row in old["corrected_coordinates"]}
    new_points = {str(row["source_pair_id"]): row for row in top["corrected_coordinates"]}
    changed_ids = {
        source_id
        for source_id in order
        if any(
            abs(
                float(new_points[str(source_id)][endpoint][axis])
                - float(baseline[str(source_id)][endpoint][axis])
            )
            > 1e-9
            for endpoint in ("top", "bottom")
            for axis in ("x", "y")
        )
    }
    pair2 = baseline["2"]
    guard_boxes = "".join(
        f'<rect x="{float(pair2[endpoint]["x"])-PAIR2_GUARD["x"]}" '
        f'y="{float(pair2[endpoint]["y"])-PAIR2_GUARD[endpoint+"_y"]}" '
        f'width="{PAIR2_GUARD["x"]*2}" '
        f'height="{PAIR2_GUARD[endpoint+"_y"]*2}"/>'
        for endpoint in ("top", "bottom")
    )
    guard_lines = "".join(
        f'<line x1="{max(50,float(baseline[str(source_id)]["top"]["x"])-3)}" '
        f'x2="{min(100,float(baseline[str(source_id)]["top"]["x"])+3)}" '
        f'y1="{float(baseline[str(source_id)]["top"]["y"])-limit}" '
        f'y2="{float(baseline[str(source_id)]["top"]["y"])-limit}"/>'
        for source_id, limit in RIGHT_TOP_Y_GUARDS.items()
    )
    data = html.escape(json.dumps({"top_candidate_id": top["candidate_id"]}))
    local_image = "../../../../data/mp3d_layout/img_v/" + overlay[
        "source_image"
    ].rsplit("/", 1)[-1]
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>3741 2D-guarded refit overlay</title><style>
body{{margin:0;background:#111;color:#eee;font:14px system-ui}}header,.controls{{padding:10px 14px}}
.warning{{font-size:18px;font-weight:800;color:#ffd166}}label{{margin-right:14px}}
svg{{width:100%;height:auto;aspect-ratio:2/1;background:#000}}g{{vector-effect:non-scaling-stroke}}
polyline,line{{vector-effect:non-scaling-stroke}}circle{{vector-effect:non-scaling-stroke}}
text{{font-size:1.5px;fill:#fff;paint-order:stroke;stroke:#000;stroke-width:.3px}}
.baseline{{stroke:#eee;fill:#111;stroke-dasharray:1 1}}.old{{stroke:#ff5252;fill:#ff5252;stroke-dasharray:.7 .7}}
.new{{stroke:#00e5ff;fill:#ffeb3b}}.guards{{stroke:#ff9800;fill:#ff980020;stroke-dasharray:.8 .5}}
.chain{{stroke:#76ff03;fill:#76ff0318;stroke-dasharray:1 1}}.height{{stroke:#ff00cc;stroke-width:.5}}
</style></head><body><header><div class="warning">2D-guarded review only; no writeback; human must confirm.</div>
<div>Old rejected: <code>{old["candidate_id"]}</code> · New review candidate: <code>{top["candidate_id"]}</code></div></header>
<div class="controls">
<label><input type="checkbox" data-target="baseline" checked> baseline</label>
<label><input type="checkbox" data-target="old" checked> rejected old candidate</label>
<label><input type="checkbox" data-target="new" checked> new guarded candidate</label>
<label><input type="checkbox" data-target="arrows" checked> arrows</label>
<label><input type="checkbox" data-target="labels" checked> source_pair_id labels</label>
<label><input id="onlyChanged" type="checkbox"> only changed pairs</label>
<label><input type="checkbox" data-target="pair2Guard" checked> pair2 guard region</label>
<label><input type="checkbox" data-target="rightGuard" checked> right-half top_y guard</label>
<label><input type="checkbox" data-target="chainA" checked> chain 5–6–7–8</label>
<label><input type="checkbox" data-target="chainB" checked> chain 12–11–1</label>
<label><input type="checkbox" data-target="heightReview" checked> height review points</label>
</div><svg viewBox="0 0 100 100" preserveAspectRatio="none">
<image href="{overlay["source_image"]}" data-fallback="{local_image}" x="0" y="0" width="100" height="100" preserveAspectRatio="none"/>
<g id="chainA" class="chain"><rect x="41" y="8" width="14" height="83"/></g>
<g id="chainB" class="chain"><rect x="0" y="4" width="16" height="92"/><rect x="94" y="4" width="6" height="92"/></g>
<g id="pair2Guard" class="guards">{guard_boxes}</g>
<g id="rightGuard" class="guards">{guard_lines}</g>
<g id="heightReview" class="height">{guard_lines}<text x="62" y="8">9–10 height review</text><text x="91" y="12">11–12 seam height review</text></g>
{_svg_set("baseline", baseline, order, "baseline", changed_ids)}
{_svg_set("old", old_points, order, "old", changed_ids)}
{_svg_set("new", new_points, order, "new", changed_ids)}
<g id="arrows" class="new">{"".join(f'<g data-source="{s}" data-changed="{str(s in changed_ids).lower()}"><line x1="{baseline[str(s)][e]["x"]}" y1="{baseline[str(s)][e]["y"]}" x2="{new_points[str(s)][e]["x"]}" y2="{new_points[str(s)][e]["y"]}"/></g>' for s in order for e in ("top","bottom"))}</g>
</svg><script>const META="{data}";document.querySelector("image").addEventListener("error",e=>{{if(!e.target.dataset.used){{e.target.dataset.used=1;e.target.setAttribute("href",e.target.dataset.fallback)}}}});
document.querySelectorAll("[data-target]").forEach(c=>c.addEventListener("change",()=>{{const one=document.getElementById(c.dataset.target);if(one)one.style.display=c.checked?"":"none";else document.querySelectorAll("."+c.dataset.target).forEach(n=>n.style.display=c.checked?"":"none")}}));
document.getElementById("onlyChanged").addEventListener("change",e=>document.querySelectorAll("[data-source]").forEach(n=>n.style.display=e.target.checked&&n.dataset.changed!=="true"?"none":""));
</script></body></html>"""


def _review_wrapper() -> str:
    return """<!doctype html><meta charset="utf-8"><title>3741 2D-guarded 3D review</title>
<style>body{font-family:system-ui;margin:12px;background:#111;color:#eee}iframe{width:100%;height:86vh;border:1px solid #555}</style>
<h1>3741 baseline / rejected old / new 2D-guarded candidate</h1>
<p>Review only. No acceptance, patch, or writeback.</p><iframe src="local_3d_review.html"></iframe>"""


def _summary(payload: dict[str, Any], out_dir: Path) -> str:
    top = payload["top_candidate"]
    return "\n".join(
        [
            "# 3741 Human-guided 2D-guarded Segment Refit",
            "",
            f"- Rejected old candidate: `{payload['rejected_candidate_id']}` (`rejected_by_2d_review=true`).",
            f"- New top candidate: `{payload['top_candidate_id']}`.",
            f"- Source pair 2 movement: top `{top['source_pair_2_top_movement']:.4f}`, bottom `{top['source_pair_2_bottom_movement']:.4f}`; guard passed `{str(top['source_pair_2_guard_passed']).lower()}`.",
            f"- Right-half top_y guard passed: `{str(top['right_half_top_y_guard_passed']).lower()}`; violations `{top['right_half_top_y_violations']}`.",
            f"- Chain 5–6–7–8 preserved: `{str(top['chain_5_6_7_8_preserved']).lower()}`.",
            f"- Chain 12–11–1 preserved: `{str(top['chain_12_11_1_preserved']).lower()}`.",
            "- Source pairs 9–10 require height review; 11–12 require seam-height review; source pair 7 requires chain-height review.",
            "- Old candidate remains only as rejected diagnostic reference.",
            "- 2D visual review is not candidate-specific C4 image evidence.",
            f"- 2D overlay: `{(out_dir / 'segment_aware_manhattan_refit_3741_2d_guarded_overlay.html').as_posix()}`",
            f"- 3D review: `{(out_dir / 'segment_aware_manhattan_refit_3741_2d_guarded_review.html').as_posix()}`",
            "- accepted/downstream/preference/writeback/patch: `false/false/false/false/false`.",
        ]
    ) + "\n"


def run(out_dir: Path = OUT_DIR) -> dict[str, Path]:
    gt_sha = _sha(GT_PATH)
    refit = json.loads(REFIT_PATH.read_text(encoding="utf-8"))
    overlay = json.loads(OVERLAY_PATH.read_text(encoding="utf-8"))
    if refit["top_candidate_id"] != "robust_all_long_edges":
        raise ValueError("unexpected rejected candidate id")
    candidates = build_2d_guarded_candidates(
        overlay["baseline_points_by_source_pair_id"],
        overlay["corrected_points_by_source_pair_id"],
    )
    top = next(
        (
            row
            for row in candidates
            if row["recommendation_label"] == "recommended_for_human_review"
        ),
        None,
    )
    if top is None:
        raise RuntimeError("no 2D-guarded candidate passed fail-closed guards")
    for row in candidates:
        row["safety_flags"] = SAFETY
    old = _old_reference(refit, overlay)
    payload = {
        "schema_version": "segment_aware_manhattan_refit_3741_2d_guarded_v1",
        "case_name": "task218_ann3741",
        "source_image": overlay["source_image"],
        "id_semantics": refit["id_semantics"],
        "verified_order_source_ids": refit["verified_order_source_ids"],
        "source_pair_to_solver_position": refit[
            "source_pair_to_solver_position"
        ],
        "solver_position_to_verified_order_source_id": refit[
            "solver_position_to_verified_order_source_id"
        ],
        "human_2d_review_constraints": {
            "source_pair_2_guard": PAIR2_GUARD,
            "right_half_top_y_guards": RIGHT_TOP_Y_GUARDS,
            "height_review_roles": {
                "7": "chain_height_review_required",
                "9": "height_review_required",
                "10": "height_review_required",
                "11": "seam_height_review_required",
                "12": "seam_height_review_required",
            },
        },
        "rejected_candidate_id": old["candidate_id"],
        "rejected_by_2d_review": True,
        "reject_reasons": REJECT_REASONS,
        "rejected_diagnostic_reference": old,
        "candidates": candidates,
        "top_candidate_id": top["candidate_id"],
        "top_candidate": top,
        "safety_flags": SAFETY,
        **SAFETY,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "segment_aware_manhattan_refit_3741_2d_guarded.json"
    summary_path = (
        out_dir / "segment_aware_manhattan_refit_3741_2d_guarded_summary.md"
    )
    overlay_html = (
        out_dir / "segment_aware_manhattan_refit_3741_2d_guarded_overlay.html"
    )
    default_out_dir = ROOT / "task218_ann3741_2d_guarded"
    review_out_dir = (
        canonical_review_out_dir("task218_ann3741_2d_guarded")
        if out_dir == default_out_dir
        else out_dir
    )
    review_html = (
        review_out_dir / "segment_aware_manhattan_refit_3741_2d_guarded_review.html"
    )
    manual_path = (
        out_dir / "corrected_points_for_manual_copy_3741_2d_guarded.json"
    )
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(_summary(payload, out_dir), encoding="utf-8")
    overlay_html.write_text(_guarded_overlay(overlay, old, top), encoding="utf-8")
    manual_path.write_text(
        json.dumps(
            {
                "schema_version": "manual_copy_candidate_3741_2d_guarded_v1",
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
                "rejected_old_candidate_reference": old["candidate_id"],
                "guard_pass_summary": {
                    "source_pair_2_guard_passed": top[
                        "source_pair_2_guard_passed"
                    ],
                    "right_half_top_y_guard_passed": top[
                        "right_half_top_y_guard_passed"
                    ],
                    "chain_5_6_7_8_preserved": top[
                        "chain_5_6_7_8_preserved"
                    ],
                    "chain_12_11_1_preserved": top[
                        "chain_12_11_1_preserved"
                    ],
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    input_path = out_dir / "_review_input.json"
    candidates_path = out_dir / "_review_candidates.json"
    input_path.write_text(
        json.dumps(
            {
                "source_image": overlay["source_image"],
                "ordered_pairs": [
                    overlay["baseline_points_by_source_pair_id"][str(source_id)]
                    for source_id in overlay["verified_order_source_ids"]
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    candidates_path.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "candidate_id": old["candidate_id"],
                        "action_family": "rejected_2d_diagnostic_reference",
                        "decision_class": "diagnostic_only",
                        "coordinate_changes": _changes(
                            overlay["baseline_points_by_source_pair_id"],
                            old["corrected_coordinates"],
                        ),
                    },
                    {
                        "candidate_id": top["candidate_id"],
                        "action_family": "human_guided_2d_guarded_refit",
                        "decision_class": "manual_review_candidate",
                        "coordinate_changes": _changes(
                            overlay["baseline_points_by_source_pair_id"],
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
        input_path=input_path,
        candidate_json=candidates_path,
        candidate_limit=2,
        out_dir=review_out_dir,
        image_root=Path("data/mp3d_layout/img_v"),
        case_name="task218_ann3741_2d_guarded",
        coordinate_mode="ls_percent",
        local_server_root=_local_server_root(review_out_dir),
    )
    review_html.write_text(_review_wrapper(), encoding="utf-8")
    if _sha(GT_PATH) != gt_sha:
        raise RuntimeError("source GT changed during audit-only run")
    return {
        "json": json_path,
        "summary": summary_path,
        "overlay": overlay_html,
        "review": review_html,
        "manual_copy": manual_path,
    }


if __name__ == "__main__":
    print(run()["json"])
