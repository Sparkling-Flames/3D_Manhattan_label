"""Materialize the audit-only 2D panorama overlay for the 3741 segment refit."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

REFIT_PATH = Path(
    "analysis_results/paper_a_manhattan/segment_aware_manhattan_refit/"
    "task218_ann3741/segment_aware_manhattan_refit_3741.json"
)
BASELINE_PATH = REFIT_PATH.with_name("_review_input.json")
OUT_DIR = REFIT_PATH.parent
SAFETY = {
    "audit_only": True,
    "accepted": False,
    "downstream_recommendation": False,
    "candidate_preference_authorized": False,
    "annotation_writeback": False,
    "annotation_patch_generated": False,
}
FOCUS_GROUPS = {
    "pair2": {"label": "source pair 2", "source_pair_ids": [2]},
    "pair1": {"label": "source pair 1", "source_pair_ids": [1]},
    "pair3_4": {"label": "source pairs 3–4", "source_pair_ids": [3, 4]},
    "pair5_6_7_8": {
        "label": "source pairs 5–6–7–8",
        "source_pair_ids": [5, 6, 7, 8],
    },
    "pair12_11_1": {
        "label": "source pairs 12–11–1",
        "source_pair_ids": [12, 11, 1],
    },
    "pair9_10": {"label": "source pairs 9–10", "source_pair_ids": [9, 10]},
}


def _roles(source_pair_id: int) -> list[str]:
    roles = []
    if source_pair_id == 2:
        roles.append("suspect_source_pair_2")
    if source_pair_id in {3, 4}:
        roles.append("strong_anchor_3_4")
    if source_pair_id in {5, 6, 7, 8}:
        roles.append("complex_short_wall_chain_5_6_7_8")
    if source_pair_id in {12, 11, 1}:
        roles.append("complex_short_wall_chain_12_11_1")
    if source_pair_id in {9, 10}:
        roles.append("height_review_required_9_10")
    return roles or ["context"]


def _point_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_pair_id": int(row["source_pair_id"]),
        "solver_position": int(row["solver_position"]),
        "verified_order_source_id": int(row["verified_order_source_id"]),
        "top": {"x": float(row["top"]["x"]), "y": float(row["top"]["y"])},
        "bottom": {
            "x": float(row["bottom"]["x"]),
            "y": float(row["bottom"]["y"]),
        },
        "effective_pair_index": int(row["effective_pair_index"]),
    }


def _range_check(*point_maps: dict[str, dict[str, Any]]) -> dict[str, Any]:
    warnings = []
    for name, points in zip(("baseline", "corrected"), point_maps):
        for source_id, pair in points.items():
            for endpoint in ("top", "bottom"):
                for axis in ("x", "y"):
                    value = pair[endpoint][axis]
                    if not 0.0 <= value <= 100.0:
                        warnings.append(
                            {
                                "set": name,
                                "source_pair_id": int(source_id),
                                "endpoint": endpoint,
                                "axis": axis,
                                "value": value,
                            }
                        )
    return {
        "expected_min": 0.0,
        "expected_max": 100.0,
        "all_coordinates_in_range": not warnings,
        "warnings": warnings,
    }


def build_payload(
    refit_path: Path = REFIT_PATH, baseline_path: Path = BASELINE_PATH
) -> dict[str, Any]:
    refit = json.loads(refit_path.read_text(encoding="utf-8"))
    baseline_input = json.loads(baseline_path.read_text(encoding="utf-8"))
    required = {
        "source_image",
        "id_semantics",
        "verified_order_source_ids",
        "source_pair_to_solver_position",
        "solver_position_to_verified_order_source_id",
        "corrected_coordinates",
        "before_after_delta",
        "top_candidate_id",
        "safety_flags",
    }
    missing = sorted(required - refit.keys())
    if missing:
        raise ValueError(f"refit artifact missing fields: {missing}")

    baseline = {
        str(row["source_pair_id"]): _point_row(row)
        for row in baseline_input["ordered_pairs"]
    }
    corrected = {
        str(row["source_pair_id"]): _point_row(row)
        for row in refit["corrected_coordinates"]
    }
    if set(baseline) != set(corrected):
        raise ValueError("baseline/corrected source_pair_id sets differ")
    deltas = {
        str(row["source_pair_id"]): {
            "source_pair_id": int(row["source_pair_id"]),
            "solver_position": int(row["solver_position"]),
            "fields": row["fields"],
            "top_movement": math.hypot(
                float(row["fields"]["top_x"]["delta"]),
                float(row["fields"]["top_y"]["delta"]),
            ),
            "bottom_movement": math.hypot(
                float(row["fields"]["bottom_x"]["delta"]),
                float(row["fields"]["bottom_y"]["delta"]),
            ),
            "max_abs_delta": max(
                abs(float(value["delta"])) for value in row["fields"].values()
            ),
        }
        for row in refit["before_after_delta"]
    }
    payload = {
        "schema_version": "segment_refit_2d_overlay_review_3741_v1",
        "case_name": "task218_ann3741",
        "source_image": refit["source_image"],
        "top_candidate_id": refit["top_candidate_id"],
        "id_semantics": refit["id_semantics"],
        "verified_order_source_ids": refit["verified_order_source_ids"],
        "source_pair_to_solver_position": refit[
            "source_pair_to_solver_position"
        ],
        "solver_position_to_verified_order_source_id": refit[
            "solver_position_to_verified_order_source_id"
        ],
        "baseline_points_by_source_pair_id": baseline,
        "corrected_points_by_source_pair_id": corrected,
        "deltas_by_source_pair_id": deltas,
        "segment_roles_by_source_pair_id": {
            source_id: _roles(int(source_id)) for source_id in baseline
        },
        "focus_groups": FOCUS_GROUPS,
        "coordinate_mode": "ls_percent",
        "coordinate_mapping": {
            "x": "x_percent / 100 * image_width",
            "y": "y_percent / 100 * image_height",
        },
        "coordinate_range_check": _range_check(baseline, corrected),
        "safety_flags": {**refit["safety_flags"], **SAFETY},
        "human_must_confirm": True,
        **SAFETY,
    }
    return payload


def _html(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    local_image = "../../../../data/mp3d_layout/img_v/" + payload[
        "source_image"
    ].rsplit("/", 1)[-1]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>3741 Segment Refit 2D Overlay</title>
<style>
:root{{color-scheme:dark}}body{{margin:0;font:14px system-ui;background:#101318;color:#eee}}
header,.controls{{padding:10px 14px;background:#1a2028}}header{{border-bottom:1px solid #48515d}}
.warning{{font-size:18px;font-weight:800;color:#ffd166}}.controls{{display:flex;flex-wrap:wrap;gap:10px 16px}}
label,button{{white-space:nowrap}}button,input{{cursor:pointer}}button{{padding:5px 9px}}
#viewport{{margin:12px;overflow:hidden;border:1px solid #637083;background:#050607}}
#canvas{{display:block;width:100%;height:auto;aspect-ratio:2/1}}
.baseline{{stroke:#e8e8e8;fill:#111;stroke-dasharray:1.2 1;vector-effect:non-scaling-stroke}}
.corrected{{stroke:#00e5ff;fill:#ffea00;vector-effect:non-scaling-stroke}}
.arrow{{stroke:#ff4d8d;stroke-dasharray:.8 .6;vector-effect:non-scaling-stroke}}
.topline{{fill:none;stroke:#f4a261;vector-effect:non-scaling-stroke}}
.bottomline{{fill:none;stroke:#2a9d8f;vector-effect:non-scaling-stroke}}
.vertical{{fill:none;vector-effect:non-scaling-stroke}}.label{{fill:white;paint-order:stroke;stroke:#000;stroke-width:.35}}
.highlight{{fill:#ffcc0030;stroke:#ffcc00;stroke-dasharray:1 1;vector-effect:non-scaling-stroke}}
.suspect{{fill:#ff174440;stroke:#ff1744;stroke-width:2;vector-effect:non-scaling-stroke}}
#legend{{padding:0 14px 12px;color:#c7d0da}}code{{color:#9ee7ff}}
</style></head><body>
<header><div class="warning">2D visual review only; no writeback; human must confirm.</div>
<div>Candidate: <code>{payload["top_candidate_id"]}</code> · LS percent coordinates · hover points for details</div></header>
<div class="controls" aria-label="overlay controls">
<label><input id="showBaseline" type="checkbox" checked> baseline</label>
<label><input id="showCorrected" type="checkbox" checked> corrected</label>
<label><input id="showArrows" type="checkbox" checked> arrows</label>
<label><input id="showLabels" type="checkbox" checked> source_pair_id labels</label>
<label><input id="showVertical" type="checkbox" checked> vertical lines</label>
<label><input id="showBottom" type="checkbox" checked> floor/bottom polyline</label>
<label><input id="showTop" type="checkbox" checked> ceiling/top polyline</label>
<label><input id="showChainA" type="checkbox" checked> chain 5–6–7–8</label>
<label><input id="showChainB" type="checkbox" checked> chain 12–11–1</label>
<label><input id="showAnchor" type="checkbox" checked> strong anchor 3–4</label>
<label><input id="showSuspect" type="checkbox" checked> suspect source pair 2</label>
<label><input id="onlyChanged" type="checkbox"> only changed pairs</label>
<label>opacity <input id="opacity" type="range" min=".15" max="1" step=".05" value=".85"></label>
<label>point size <input id="pointSize" type="range" min=".3" max="1.5" step=".1" value=".65"></label>
</div>
<div class="controls" id="focus"></div>
<div id="viewport"><svg id="canvas" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="3741 baseline and corrected 2D panorama overlay">
<defs><marker id="arrowhead" markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto"><path d="M0,0 L5,2.5 L0,5z" fill="#ff4d8d"/></marker></defs>
<image id="panorama" href="{payload["source_image"]}" x="0" y="0" width="100" height="100" preserveAspectRatio="none"/>
<g id="overlay"></g></svg></div>
<div id="legend">Baseline: dashed white square points. Corrected: cyan solid lines/yellow circular points. Magenta dashed arrows show before → after. Pair 2 is red warning-highlighted; chain regions use boxed highlights.</div>
<script>const P={data};const localImage={json.dumps(local_image)};
const svg=document.getElementById("canvas"),root=document.getElementById("overlay"),NS="http://www.w3.org/2000/svg";
document.getElementById("panorama").addEventListener("error",e=>{{if(!e.target.dataset.fallback){{e.target.dataset.fallback=1;e.target.setAttribute("href",localImage)}}}});
const $=id=>document.getElementById(id), el=(tag,a={{}})=>{{const n=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(a))n.setAttribute(k,v);return n}};
const order=P.verified_order_source_ids.map(String), base=P.baseline_points_by_source_pair_id, corr=P.corrected_points_by_source_pair_id;
const changed=id=>P.deltas_by_source_pair_id[id].max_abs_delta>1e-6;
function roleVisible(id){{const r=P.segment_roles_by_source_pair_id[id];return (!r.includes("complex_short_wall_chain_5_6_7_8")||$("showChainA").checked)&&(!r.includes("complex_short_wall_chain_12_11_1")||$("showChainB").checked)&&(!r.includes("strong_anchor_3_4")||$("showAnchor").checked)&&(!r.includes("suspect_source_pair_2")||$("showSuspect").checked)}}
function ids(){{return order.filter(id=>roleVisible(id)&&(!$("onlyChanged").checked||changed(id)))}}
function path(points,endpoint){{let d="";points.forEach((p,i)=>{{const q=p[endpoint],prev=i&&points[i-1][endpoint];d+=(i&&Math.abs(q.x-prev.x)<=50?" L":" M")+q.x+" "+q.y}});return d}}
function addPath(points,endpoint,cls){{root.append(el("path",{{d:path(points,endpoint),class:cls,"stroke-width":.45}}))}}
function box(sourceIds,cls){{let pts=sourceIds.flatMap(id=>[base[id].top,base[id].bottom,corr[id].top,corr[id].bottom]);for(const side of [pts.filter(p=>p.x<50),pts.filter(p=>p.x>=50)])if(side.length){{const xs=side.map(p=>p.x),ys=side.map(p=>p.y);root.append(el("rect",{{x:Math.max(0,Math.min(...xs)-1),y:Math.max(0,Math.min(...ys)-2),width:Math.min(100,Math.max(...xs)+1)-Math.max(0,Math.min(...xs)-1),height:Math.min(100,Math.max(...ys)+2)-Math.max(0,Math.min(...ys)-2),rx:1,class:cls}}))}}}}
function tooltip(id){{const b=base[id],c=corr[id],d=P.deltas_by_source_pair_id[id];return `source_pair_id: ${{id}}\\nsolver_position: ${{b.solver_position}}\\nbefore top: (${{b.top.x.toFixed(3)}}, ${{b.top.y.toFixed(3)}}) bottom: (${{b.bottom.x.toFixed(3)}}, ${{b.bottom.y.toFixed(3)}})\\nafter top: (${{c.top.x.toFixed(3)}}, ${{c.top.y.toFixed(3)}}) bottom: (${{c.bottom.x.toFixed(3)}}, ${{c.bottom.y.toFixed(3)}})\\nmax |delta|: ${{d.max_abs_delta.toFixed(3)}}\\nrole: ${{P.segment_roles_by_source_pair_id[id].join(", ")}}`}}
function pair(id,set,cls,shape){{const p=set[id],g=el("g",{{class:cls}});if($("showVertical").checked)g.append(el("line",{{x1:p.top.x,y1:p.top.y,x2:p.bottom.x,y2:p.bottom.y,class:"vertical","stroke-width":.4}}));for(const endpoint of ["top","bottom"]){{const q=p[endpoint],n=shape==="circle"?el("circle",{{cx:q.x,cy:q.y,r:$("pointSize").value,class:cls}}):el("rect",{{x:q.x-$("pointSize").value/2,y:q.y-$("pointSize").value/2,width:$("pointSize").value,height:$("pointSize").value,class:cls}});const t=el("title");t.textContent=tooltip(id);n.append(t);g.append(n)}}root.append(g)}}
function render(){{root.replaceChildren();root.setAttribute("opacity",$("opacity").value);const visible=ids(),bp=visible.map(id=>base[id]),cp=visible.map(id=>corr[id]);
if($("showChainA").checked)box(["5","6","7","8"],"highlight");if($("showChainB").checked)box(["12","11","1"],"highlight");if($("showAnchor").checked)box(["3","4"],"highlight");if($("showSuspect").checked)box(["2"],"suspect");
if($("showTop").checked){{if($("showBaseline").checked)addPath(bp,"top","baseline topline");if($("showCorrected").checked)addPath(cp,"top","corrected topline")}}
if($("showBottom").checked){{if($("showBaseline").checked)addPath(bp,"bottom","baseline bottomline");if($("showCorrected").checked)addPath(cp,"bottom","corrected bottomline")}}
for(const id of visible){{if($("showArrows").checked)for(const e of ["top","bottom"]){{const a=base[id][e],b=corr[id][e];root.append(el("line",{{x1:a.x,y1:a.y,x2:b.x,y2:b.y,class:"arrow","stroke-width":.35,"marker-end":"url(#arrowhead)"}}))}}if($("showBaseline").checked)pair(id,base,"baseline","square");if($("showCorrected").checked)pair(id,corr,"corrected","circle");if($("showLabels").checked){{const p=corr[id].top,d=P.deltas_by_source_pair_id[id],t=el("text",{{x:p.x+1,y:p.y-1,class:"label","font-size":"1.5"}});t.textContent=`s${{id}} / p${{corr[id].solver_position}} Δ${{d.max_abs_delta.toFixed(2)}}`;root.append(t)}}}}}}
function focus(sourceIds){{const pts=sourceIds.flatMap(id=>[base[id].top,base[id].bottom,corr[id].top,corr[id].bottom]),xs=pts.map(p=>p.x),ys=pts.map(p=>p.y),pad=5;let x=Math.max(0,Math.min(...xs)-pad),y=Math.max(0,Math.min(...ys)-pad),w=Math.min(100-x,Math.max(15,Math.max(...xs)-Math.min(...xs)+2*pad)),h=Math.min(100-y,Math.max(20,Math.max(...ys)-Math.min(...ys)+2*pad));svg.setAttribute("viewBox",`${{x}} ${{y}} ${{w}} ${{h}}`)}}
for(const [key,g] of Object.entries(P.focus_groups)){{const b=document.createElement("button");b.textContent="Focus "+g.label;b.onclick=()=>focus(g.source_pair_ids.map(String));$("focus").append(b)}}const reset=document.createElement("button");reset.textContent="Reset zoom";reset.onclick=()=>svg.setAttribute("viewBox","0 0 100 100");$("focus").append(reset);
document.querySelectorAll("input").forEach(n=>n.addEventListener("input",render));render();</script></body></html>"""


def _summary(payload: dict[str, Any], html_path: Path) -> str:
    pair2 = payload["deltas_by_source_pair_id"]["2"]
    return "\n".join(
        [
            "# 3741 Segment-aware Refit 2D Overlay Review",
            "",
            f"- Top candidate: `{payload['top_candidate_id']}`",
            f"- Source pair 2 movement in LS-percent coordinates: top `{pair2['top_movement']:.4f}`, bottom `{pair2['bottom_movement']:.4f}`.",
            "- Strong anchor 3–4: solver reports it as basically preserved; confirm against image corners.",
            "- Chain 5–6–7–8: highlighted for focused human review.",
            "- Chain 12–11–1: highlighted for focused human review.",
            "- Source pairs 9–10: marked `height_review_required`; human confirmation remains required.",
            "- This overlay is visual review only and is not candidate-specific C4 image evidence.",
            "- Automatic writeback is forbidden because 2D image alignment has not been human-confirmed.",
            f"- HTML: `{html_path.as_posix()}`",
            "- accepted/downstream/preference/writeback/patch: `false/false/false/false/false`.",
        ]
    ) + "\n"


def run(
    out_dir: Path = OUT_DIR,
    refit_path: Path = REFIT_PATH,
    baseline_path: Path = BASELINE_PATH,
) -> dict[str, Path]:
    payload = build_payload(refit_path, baseline_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "segment_aware_manhattan_refit_3741_2d_overlay.html"
    payload_path = (
        out_dir / "segment_aware_manhattan_refit_3741_2d_overlay_payload.json"
    )
    summary_path = (
        out_dir / "segment_aware_manhattan_refit_3741_2d_overlay_summary.md"
    )
    payload_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    html_path.write_text(_html(payload), encoding="utf-8")
    summary_path.write_text(_summary(payload, html_path), encoding="utf-8")
    return {"html": html_path, "payload": payload_path, "summary": summary_path}


if __name__ == "__main__":
    print(run()["html"])
