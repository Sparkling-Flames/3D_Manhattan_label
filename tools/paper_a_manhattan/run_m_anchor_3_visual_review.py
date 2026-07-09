"""Generate review-only 2D overlays for M-Anchor.3 candidates."""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.run_m_anchor_1_3741 import _load, _sha, _write_text_lf
from tools.paper_a_manhattan.run_m_anchor_3_footprint_solver import (
    M1_AUDIT_PATH,
    OUT_DIR as M3_DIR,
)

M3_AUDIT_PATH = M3_DIR / "m_anchor_3_footprint_solver_audit.json"
OUT_DIR = M3_DIR / "visual_review"


def _polyline(rows: Sequence[Mapping[str, Any]], endpoint: str) -> str:
    return " ".join(
        f"{float(row[endpoint]['x']):.4f},{float(row[endpoint]['y']):.4f}" for row in rows
    )


def _point_layers(rows: Sequence[Mapping[str, Any]], css_class: str) -> str:
    parts = []
    for row in rows:
        sid = int(row["source_pair_id"])
        top = row["top"]
        bottom = row["bottom"]
        parts.append(
            f'<g class="{css_class}" data-source="{sid}">'
            f'<line x1="{top["x"]}" y1="{top["y"]}" x2="{bottom["x"]}" y2="{bottom["y"]}"/>'
            f'<circle cx="{top["x"]}" cy="{top["y"]}" r=".55"/>'
            f'<circle cx="{bottom["x"]}" cy="{bottom["y"]}" r=".65"/>'
            f'<text x="{float(top["x"]) + .7}" y="{float(top["y"]) - .7}">s{sid}</text>'
            "</g>"
        )
    return "\n".join(parts)


def _residual_table(candidate: Mapping[str, Any]) -> str:
    rows = []
    for wall in candidate["per_wall_residual_diagnostic"]["walls"]:
        edge = f"{wall['source_edge_ids'][0]}→{wall['source_edge_ids'][1]}"
        rows.append(
            "<tr>"
            f"<td>{html.escape(edge)}</td>"
            f"<td>{wall['manhattan_residual_before_deg']:.3f}</td>"
            f"<td>{wall['manhattan_residual_after_deg']:.3f}</td>"
            f"<td>{wall['residual_delta_deg']:.3f}</td>"
            f"<td>{wall['length_after']:.3f}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>edge</th><th>residual before</th><th>residual after</th>"
        "<th>delta</th><th>length after</th></tr></thead><tbody>"
        + "\n".join(rows)
        + "</tbody></table>"
    )


def _overlay_html(
    image_url: str,
    before_rows: Sequence[Mapping[str, Any]],
    candidate: Mapping[str, Any],
) -> str:
    rows = candidate["corrected_coordinates"]
    cid = html.escape(candidate["candidate_id"])
    metrics = (
        f"delta={candidate['bottom_y_delta_by_pair']['6']}; "
        f"wall_sum {candidate['wall_residual_sum_before']:.3f} -> "
        f"{candidate['wall_residual_sum_after']:.3f}; "
        f"decision={candidate['decision']}"
    )
    s6_before = next(row for row in before_rows if int(row["source_pair_id"]) == 6)
    s6_after = next(row for row in rows if int(row["source_pair_id"]) == 6)
    arrow = (
        f'<line class="arrow" x1="{s6_before["bottom"]["x"]}" y1="{s6_before["bottom"]["y"]}" '
        f'x2="{s6_after["bottom"]["x"]}" y2="{s6_after["bottom"]["y"]}"/>'
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{cid}</title>
<style>
body{{margin:0;background:#111;color:#eee;font:14px system-ui}}
header{{padding:10px 14px}} svg{{width:100%;aspect-ratio:2/1;background:#000}}
table{{border-collapse:collapse;margin:10px 14px 16px}}td,th{{border:1px solid #555;padding:3px 6px;text-align:right}}th:first-child,td:first-child{{text-align:left}}
line,polyline,circle{{vector-effect:non-scaling-stroke}} text{{font-size:1.6px;fill:#fff;paint-order:stroke;stroke:#000;stroke-width:.35}}
.before{{stroke:#ddd;fill:#ddd;stroke-dasharray:1 1}} .cand{{stroke:#00e5ff;fill:#ffeb3b}}
.top{{fill:none;stroke-width:.28}} .bottom{{fill:none;stroke-width:.45}} .arrow{{stroke:#00ff88;stroke-width:.7;marker-end:url(#arrow)}}
.note{{color:#ffd166;font-weight:700}}
</style></head><body>
<header><div class="note">M-Anchor.3 visual review only; no acceptance, writeback, ranking, or patch.</div>
<div><code>{cid}</code> — {html.escape(metrics)}</div>
<div>Overlay: gray dashed = M-Anchor.1 reviewed candidate; cyan/yellow = M-Anchor.3 candidate. Only s6 bottom_y changes.</div></header>
<h2 style="margin-left:14px">Per-wall residuals, degrees</h2>
{_residual_table(candidate)}
<svg viewBox="0 0 100 100" preserveAspectRatio="none">
<defs><marker id="arrow" markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto"><path d="M0,0 L5,2.5 L0,5 z" fill="#00ff88"/></marker></defs>
<image href="{html.escape(image_url)}" x="0" y="0" width="100" height="100" preserveAspectRatio="none"/>
<g class="before"><polyline class="top" points="{_polyline(before_rows, "top")}"/><polyline class="bottom" points="{_polyline(before_rows, "bottom")}"/>{_point_layers(before_rows, "before")}</g>
<g class="cand"><polyline class="top" points="{_polyline(rows, "top")}"/><polyline class="bottom" points="{_polyline(rows, "bottom")}"/>{_point_layers(rows, "cand")}</g>
{arrow}
</svg></body></html>
"""


def _index_html(entries: Sequence[Mapping[str, str]]) -> str:
    links = "\n".join(
        f'<li><a href="{html.escape(row["html"])}">{html.escape(row["candidate_id"])}</a></li>'
        for row in entries
    )
    frames = "\n".join(
        f'<h2>{html.escape(row["candidate_id"])}</h2><iframe src="{html.escape(row["html"])}"></iframe>'
        for row in entries
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>M-Anchor.3 visual review</title>
<style>body{{background:#111;color:#eee;font:14px system-ui;margin:16px}}a{{color:#7dd3fc}}iframe{{width:100%;height:58vw;max-height:620px;border:1px solid #555}}</style>
</head><body><h1>M-Anchor.3 visual review</h1>
<p>Review-only overlays for the three generated candidates. No writeback, no ranking, no final acceptance.</p>
<ul>{links}</ul>{frames}</body></html>
"""


def run(out_dir: Path = OUT_DIR) -> dict[str, Path]:
    m1 = _load(M1_AUDIT_PATH)
    m3 = _load(M3_AUDIT_PATH)
    before = next(
        row for row in m1["solver_prototypes"] if row["candidate_id"] == m3["reviewed_candidate"]
    )["corrected_coordinates"]
    image_url = m1["source_image"]
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for candidate in m3["candidate_cards"]:
        filename = f"{candidate['candidate_id']}_overlay.html"
        _write_text_lf(out_dir / filename, _overlay_html(image_url, before, candidate))
        entries.append(
            {
                "candidate_id": candidate["candidate_id"],
                "html": filename,
                "decision": candidate["decision"],
                "annotation_writeback": False,
                "accepted": False,
            }
        )

    manifest = {
        "schema_version": "m_anchor_3_visual_review_manifest_v1",
        "case_name": m3["case_name"],
        "reviewed_candidate": m3["reviewed_candidate"],
        "source_audit": {"path": M3_AUDIT_PATH.as_posix(), "sha256": _sha(M3_AUDIT_PATH)},
        "candidate_count": len(entries),
        "entries": entries,
        "accepted": False,
        "downstream_recommendation": False,
        "annotation_writeback": False,
    }
    manifest_path = out_dir / "m_anchor_3_visual_review_manifest.json"
    index_path = out_dir / "m_anchor_3_visual_review_index.html"
    _write_text_lf(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    _write_text_lf(index_path, _index_html(entries))
    return {"manifest": manifest_path, "index": index_path}


if __name__ == "__main__":
    print(run()["index"])
