"""Read-only, full-corpus geometric recall for manual order review."""

import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, Polygon

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lib.misc.panostretch import pano_connect_points

SOURCE = ROOT / "analysis_results/consensus_visual_review_20260923"
OUT = ROOT / "analysis_results/order_screening_20260923"
THRESHOLDS = {
    "curve_kink_deg": 60,
    "curve_very_sharp_kink_deg": 120,
    "near_pole_margin_px_1024x512": 24,
    "near_pole_fraction": 0.03,
    "floor_radius_ratio": 12,
    "floor_edge_ratio": 20,
    "floor_compactness": 0.04,
}


def read_js(path, prefix):
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith(prefix):
        raise ValueError(f"Unexpected JS prefix: {path}")
    return json.loads(raw[len(prefix):].rstrip(";\n"))


def nonadjacent_crossings(points):
    if points is None or len(points) < 4 or any(p is None for p in points):
        return None
    edges = [LineString((points[i], points[(i + 1) % len(points)])) for i in range(len(points))]
    return sum(edges[i].crosses(edges[j]) for i in range(len(edges)) for j in range(i + 1, len(edges))
               if (j - i) not in (1, len(edges) - 1))


def curve_metrics(bands, pairs):
    if not bands or len(bands) != 512:
        return None
    arr = np.asarray(bands, dtype=float)
    if arr.shape != (512, 2) or not np.isfinite(arr).all():
        return None
    # Bands are the stored output of the existing panorama curve constructor at 512x256.
    max_kink = 0.0
    kink_pair = None
    for i, pair in enumerate(pairs or []):
        x = int(round((pair[0][0] + .5) * .5 - .5)) % 512
        for side in range(2):
            left = (arr[x, side] - arr[(x - 4) % 512, side]) / 4
            right = (arr[(x + 4) % 512, side] - arr[x, side]) / 4
            kink = abs(math.degrees(math.atan(right) - math.atan(left)))
            if kink > max_kink:
                max_kink, kink_pair = kink, i + 1
    top_margin = float(np.min(arr[:, 0]) * 2)
    bottom_margin = float(np.min(255 - arr[:, 1]) * 2)
    fraction = float(np.mean((arr[:, 0] * 2 <= THRESHOLDS["near_pole_margin_px_1024x512"]) |
                             ((255 - arr[:, 1]) * 2 <= THRESHOLDS["near_pole_margin_px_1024x512"])))
    return {"max_kink_deg": round(max_kink, 2), "max_kink_pair_position_1based": kink_pair,
            "min_pole_margin_px_1024x512": round(min(top_margin, bottom_margin), 2),
            "near_pole_fraction": round(fraction, 4)}


def projected_curve_crossings(pairs):
    """Crossings between nonadjacent current-ring edges, with ERP seam split."""
    if not pairs or len(pairs) < 4:
        return 0 if pairs else None
    p = (np.asarray(pairs, dtype=float) + .5) * .5 - .5
    p[:, :, 0] %= 512
    n = len(p)
    segments = [[], []]
    for side, z in ((0, -50), (1, 50)):
        for i in range(n):
            try:
                sample = np.asarray(pano_connect_points(p[i, side], p[(i + 1) % n, side], z=z, w=512, h=256))
            except (ValueError, FloatingPointError, ZeroDivisionError):
                return None
            if sample.ndim != 2 or sample.shape[1] != 2 or len(sample) < 2 or not np.isfinite(sample).all():
                return None
            cuts = np.where(abs(np.diff(sample[:, 0])) > 256)[0] + 1
            parts = np.split(sample, cuts)
            segments[side].append([LineString(part) for part in parts if len(part) >= 2])
    return sum(a.crosses(b) for side in segments for i in range(n) for j in range(i + 1, n)
               if (j - i) not in (1, n - 1) for a in side[i] for b in side[j])


def footprint_metrics(geometry):
    floor = geometry.get("floor") if geometry else None
    if not floor or any(p is None for p in floor):
        return None
    p = np.asarray(floor, dtype=float)[:, [0, 2]]
    if not np.isfinite(p).all() or len(p) < 3:
        return None
    lengths = np.linalg.norm(np.roll(p, -1, axis=0) - p, axis=1)
    radius = np.linalg.norm(p, axis=1)
    poly = Polygon(p)
    perimeter = float(np.sum(lengths))
    return {"nonadjacent_crossings": nonadjacent_crossings(p.tolist()),
            "radius_ratio": round(float(np.max(radius) / max(np.min(radius), 1e-12)), 3),
            "edge_ratio": round(float(np.max(lengths) / max(np.min(lengths), 1e-12)), 3),
            "compactness_4piA_over_P2": round(float(4 * math.pi * abs(poly.area) / max(perimeter * perimeter, 1e-12)), 4),
            "area_relative_units2": round(float(abs(poly.area)), 4),
            "perimeter_relative_units": round(perimeter, 4)}


def screen(row, annotation):
    geometry = annotation["screening"].get("geometry") or {}
    issues = geometry.get("issues") or []
    curve = curve_metrics((annotation.get("views") or {}).get("curve", {}).get("bands"), annotation.get("pairs_shared_x"))
    projected_crossings = projected_curve_crossings(annotation.get("pairs_shared_x")) if curve else None
    floor = footprint_metrics(geometry)
    reasons = []

    def add(channel, code, value, threshold, note):
        reasons.append({"channel": channel, "code": code, "value": value, "threshold": threshold, "note": note})

    if annotation.get("pairing_status") != "existing_accepted_pairing" or not annotation.get("links_zero_based"):
        add("point_or_pairing", "pairing_unavailable", annotation.get("pairing_status"), None, "先核对点对，不能用换序修复")
    if annotation.get("imputed_point"):
        add("point_or_pairing", "imputed_point", True, None, "有效点含既有补点；保留来源身份")
    for issue in issues:
        add("geometry_construction", "raw_3d_" + issue, True, None, "原始射线脚印；未做曼哈顿优化")
    if floor is None:
        add("geometry_construction", "raw_3d_missing", None, None, "原始3D脚印不可计算，不能当作几何正常")
    if floor:
        if floor["nonadjacent_crossings"]:
            add("geometry_construction", "floor_nonadjacent_crossing", floor["nonadjacent_crossings"], ">0", "当前配对环3D脚印边相交")
        for field, threshold, code in (("radius_ratio", THRESHOLDS["floor_radius_ratio"], "floor_radius_ratio"),
                                       ("edge_ratio", THRESHOLDS["floor_edge_ratio"], "floor_edge_ratio")):
            if floor[field] > threshold:
                add("geometry_construction", code, floor[field], f">{threshold}", "3D极端形状量；相机高度取相对单位1")
        if floor["compactness_4piA_over_P2"] < THRESHOLDS["floor_compactness"]:
            add("geometry_construction", "floor_low_compactness", floor["compactness_4piA_over_P2"],
                f"<{THRESHOLDS['floor_compactness']}", "3D面积/周长形状量，凹形真实房间也可触发")
    if curve:
        curve["current_ring_nonadjacent_crossings"] = projected_crossings
        if projected_crossings:
            add("geometry_construction", "projected_curve_nonadjacent_crossing", projected_crossings, ">0",
                "当前配对环的真实空间直线投影曲线，按ERP接缝拆分；遮挡时交叉也可能合理")
        if curve["max_kink_deg"] >= THRESHOLDS["curve_kink_deg"]:
            add("curve_construction", "sharp_curve_junction", curve["max_kink_deg"],
                f">={THRESHOLDS['curve_kink_deg']} deg", "墙线曲线接头突变；真实墙角也可触发")
        if curve["max_kink_deg"] >= THRESHOLDS["curve_very_sharp_kink_deg"]:
            add("curve_construction", "very_sharp_curve_junction", curve["max_kink_deg"],
                f">={THRESHOLDS['curve_very_sharp_kink_deg']} deg", "更尖锐的投影接头，仅供优先复核")
        if curve["near_pole_fraction"] >= THRESHOLDS["near_pole_fraction"]:
            add("curve_construction", "curve_near_pole", curve["near_pole_fraction"],
                f">={THRESHOLDS['near_pole_fraction']}", "墙线贴近ERP极区，可能是投影分支风险")
    else:
        add("geometry_construction", "curve_unavailable", annotation.get("views", {}).get("curve", {}).get("status"),
            None, "现有曲线墙带不可评价，需先辨认表示/点位原因")
    if curve and projected_crossings is None:
        add("geometry_construction", "projected_curve_crossing_unavailable", None, None, "逐边曲线投影未能生成")
    if "order" in annotation["screening"].get("cues", []):
        add("low_priority_order_hint", "raw_click_differs_from_current_ring", True, None,
            "原点号先后与当前配对环不同；点击顺序不是真实墙环")
    primary = any(r["channel"] != "low_priority_order_hint" for r in reasons)
    priority = any(r["code"] not in ("sharp_curve_junction", "raw_click_differs_from_current_ring") for r in reasons)
    return {"canonical_annotation_id": row["id"], "code": row["code"], "image_id": row["image_id"],
            "worker_id": row["worker"], "condition": row["condition"],
            "candidate": primary, "priority_candidate": priority, "reasons": reasons, "curve": curve, "raw_3d": floor,
            "raw_3d_issues": issues, "pairing_status": annotation.get("pairing_status"),
            "current_pair_original_point_ids_1based": [[a + 1, b + 1] for a, b in (annotation.get("links_zero_based") or [])],
            "human_order_decision": None, "human_suggested_order": None, "pending_user_confirmation": True}


def main():
    OUT.mkdir(exist_ok=True)
    data = read_js(SOURCE / "data.js", "window.REVIEW_DATA=")
    if data["manifest"]["contract_version"] != "consensus_research_20260923_v1" or len(data["rows"]) != 3019:
        raise ValueError("Unexpected source contract or annotation count")
    by_image = {}
    for row in data["rows"]:
        by_image.setdefault(row["image_id"], {})[row["id"]] = row
    results = []
    for image_id, rows in by_image.items():
        case = read_js(SOURCE / "cases" / f"{image_id}.js", "window.REVIEW_CASE=")
        if case["image_id"] != image_id:
            raise ValueError(f"Case identity drift: {image_id}")
        annotations = {a["canonical_annotation_id"]: a for a in case["annotations"]}
        if annotations.keys() != rows.keys():
            raise ValueError(f"Canonical annotation identity drift: {image_id}")
        results.extend(screen(row, annotations[cid]) for cid, row in rows.items())
    results.sort(key=lambda r: (not r["priority_candidate"], not r["candidate"],
                                -sum(x["channel"] == "geometry_construction" for x in r["reasons"]),
                                -sum(x["channel"] == "curve_construction" for x in r["reasons"]), r["code"], r["worker_id"]))
    counts = Counter(x["channel"] for r in results for x in r["reasons"])
    payload = {"schema": "order_screening_v1", "contract_version": data["manifest"]["contract_version"],
               "source": "consensus_visual_review_20260923 read-only canonical cases", "thresholds": THRESHOLDS,
               "notes": ["候选只召回人工复核，不判断错标或自动修序", "原点击次序差异仅低优先线索",
                         "当前x排序的单值墙带会掩盖某些真实遮挡交叉；二维交叉、尖角和3D极端形状可来自真实结构"],
               "coverage": {"annotations": len(results), "images": len(by_image),
                            "primary_candidates": sum(r["candidate"] for r in results),
                            "priority_candidates": sum(r["priority_candidate"] for r in results),
                            "curve_evaluable": sum(r["curve"] is not None for r in results),
                            "raw_3d_evaluable": sum(r["raw_3d"] is not None for r in results),
                            "by_channel": dict(counts)}, "rows": results}
    (OUT / "screening.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUT / "data.js").write_text("window.ORDER_SCREENING=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";", encoding="utf-8")
    (OUT / "index.html").write_text("""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>全量顺序风险筛选</title>
<style>body{font:15px/1.5 system-ui;margin:auto;max-width:1400px;padding:24px;color:#17212c;background:#f6f8f8}h1{margin-bottom:8px}
.bar{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}.bar label{display:grid;gap:3px}select,input{padding:7px;min-width:180px}
table{width:100%;border-collapse:collapse;background:white}th,td{padding:9px;border:1px solid #dce2e3;vertical-align:top;text-align:left}
small{color:#5e6b72}pre{white-space:pre-wrap;max-width:650px}button{margin:12px 8px 0 0;padding:8px}</style>
<h1>3019份作答 · 顺序风险机器筛选</h1><p>候选仅供人工复核；二维曲线尖角、交叉和3D极端形状可由真实遮挡或墙角造成。检测的是<b>当前计算配对环（真实邻接未确认）</b>，未知真实连接仍未知；原点击先后仅为低优先线索。这里不提供自动修序。</p>
<p><a href="screening.json">下载完整数值、触发原因和空白人工修序字段</a> · 进入独立排序工作台查看单份作答的原图、俯视与3D，并导出预览顺序。</p>
<div class="bar"><label>队列<select id="level"><option value="priority">优先候选</option><option value="candidate">宽筛候选</option><option value="all">全部3019份</option></select></label>
<label>原因类型<select id="channel"><option value="all">全部类型</option><option value="geometry_construction">几何构造</option><option value="curve_construction">曲线接头/极区</option><option value="point_or_pairing">点位/配对</option><option value="low_priority_order_hint">低优先点击线索</option></select></label>
<label>图片/人员/canonical ID<input id="search" type="search" autocomplete="off"></label></div><p id="count"></p>
<table><thead><tr><th>图片/人员</th><th>对象</th><th>触发原因与数值</th><th>人工审查</th></tr></thead><tbody id="rows"></tbody></table>
<button id="prev">上一页</button><button id="next">下一页</button><span id="page"></span>
<script src="data.js"></script><script>
const all=window.ORDER_SCREENING.rows, $=id=>document.getElementById(id);let page=0;
function filtered(){const q=$('search').value.trim().toLowerCase(),level=$('level').value,ch=$('channel').value;
 return all.filter(r=>(level==='all'||(level==='priority'?r.priority_candidate:r.candidate))&&(ch==='all'||r.reasons.some(x=>x.channel===ch))&&
 (!q||[r.code,r.worker_id,r.canonical_annotation_id].some(x=>x.toLowerCase().includes(q))));}
function td(tr,value){const e=document.createElement('td');e.textContent=value;tr.append(e);return e;}
function render(){const rows=filtered();page=Math.min(page,Math.max(0,Math.ceil(rows.length/50)-1));$('count').textContent=`显示${rows.length}份；优先${window.ORDER_SCREENING.coverage.priority_candidates}份，宽筛${window.ORDER_SCREENING.coverage.primary_candidates}份。`;
 $('rows').replaceChildren();for(const r of rows.slice(page*50,(page+1)*50)){const tr=document.createElement('tr');td(tr,`${r.code} · ${r.worker_id}`);
 td(tr,r.canonical_annotation_id);const reasons=td(tr,r.reasons.map(x=>`${x.note}（${x.code}: ${x.value===null?'missing':x.value}${x.threshold?' / '+x.threshold:''}）`).join('；')||'未触发');
 const detail=document.createElement('details'),summary=document.createElement('summary'),pre=document.createElement('pre');summary.textContent='查看原始量与解释';
 pre.textContent=JSON.stringify({curve:r.curve,raw_3d:r.raw_3d,raw_3d_issues:r.raw_3d_issues,reasons:r.reasons,current_pair_original_point_ids_1based:r.current_pair_original_point_ids_1based},null,2);
 detail.append(summary,pre);reasons.append(detail);const cell=td(tr,'');const link=document.createElement('a');link.href='../order_studio_20260926/index.html?annotation='+encodeURIComponent(r.canonical_annotation_id);
 link.textContent='打开独立3D排序';cell.append(link);$('rows').append(tr);} $('page').textContent=`第${page+1}/${Math.max(1,Math.ceil(rows.length/50))}页`;}
for(const id of ['level','channel','search'])$(id).addEventListener(id==='search'?'input':'change',()=>{page=0;render()});
$('prev').onclick=()=>{if(page>0){page--;render()}};$('next').onclick=()=>{if((page+1)*50<filtered().length){page++;render()}};render();
</script></html>""", encoding="utf-8")


if __name__ == "__main__":
    main()
