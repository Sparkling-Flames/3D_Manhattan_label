"""Build a read-only, point-identity-preserving order review gallery."""

import html
import json
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "analysis_results/consensus_visual_review_20260923"
OUT = ROOT / "analysis_results/order_preliminary_review_20260923"
CASES = {
    "UwV83HsGsw3-16": ["W028", "W036"],
    "jh4fc5c5qoQ-09": ["W028", "W037"],
    "UwV83HsGsw3-01": ["W015", "W034"],
    "q9vSo1VnCiC-16": ["W033"],
    "VFuaQ6m2Qom-04": ["W032"],
    "S9hNv5qa7GM-08": ["W036", "W037"],
    "q9vSo1VnCiC-24": ["W018"],
    "uNb9QFRL6hY-81": ["W031", "W037"],
    "B6ByNegPMKs-43": ["W036", "W032"],
    "e9zR4mvMWw7-09": ["W006"],
}

NOTES = {
    "UwV83HsGsw3-16": ("远处厨房与电视墙被近处转折及家具部分遮挡；GT来源环在远处有多次回折。", {"W028": "无法确定", "W036": "无法确定"}),
    "jh4fc5c5qoQ-09": ("卧室位于厨房和卫浴之间；门洞与近处墙段遮住部分转角，GT来源环明显非方位角单调。", {"W028": "无法确定", "W037": "无法确定"}),
    "UwV83HsGsw3-01": ("客厅通向厨房，右侧近处墙体遮住后方角点；W015还涉及既有配对身份变化。", {"W015": "无法确定", "W034": "无法确定"}),
    "q9vSo1VnCiC-16": ("横梁、露台门和右侧通道造成回折；W033原点击连线穿过房间，现有配对环已按可见外边界排列。", {"W033": "无需调整"}),
    "VFuaQ6m2Qom-04": ("浴室门洞与壁龛多，W032局部点先后颠倒，但现有配对环沿可见边界排列；多余/共线角点问题与换序分开。", {"W032": "无需调整"}),
    "S9hNv5qa7GM-08": ("洗衣区与卫生间门框互相遮挡；GT有门洞回折，人员少标的转角无法通过重排补回。", {"W036": "无法确定", "W037": "无需调整"}),
    "q9vSo1VnCiC-24": ("厨房和入口相连，GT来源环在隔墙两侧回折；W018四对点的范围选择与连接都需分辨。", {"W018": "无法确定"}),
    "uNb9QFRL6hY-81": ("卧室壁龛及台面遮住地面墙脚；W031现有配对环已连成可见轮廓，W037把局部台面点当角点的语义未定。", {"W031": "无需调整", "W037": "无法确定"}),
    "B6ByNegPMKs-43": ("办公室门框与玻璃隔墙形成近远两层，四对点无法证明唯一闭合墙环；W032配对身份还不同于原连续点对。", {"W036": "无法确定", "W032": "无法确定"}),
    "e9zR4mvMWw7-09": ("近处曲面墙完全遮住其后走廊一段；W006原点击上下角色混杂，现有配对已整理，未见可据此提出的新换序。", {"W006": "无需调整"}),
}

AUDITED_GT = {"S9hNv5qa7GM-08": 4, "q9vSo1VnCiC-24": 5, "uNb9QFRL6hY-81": 2}


def load_json_js(path, prefix):
    return json.loads(path.read_text(encoding="utf-8").removeprefix(prefix).rstrip(";\n"))


def ordered_pairs(obj, reference=False, raw_sequence=False):
    points = obj["raw_points"] if reference else obj["raw_points_1024x512"]
    links = [[i, i + 1] for i in range(0, len(points), 2)] if reference or raw_sequence else obj["links_zero_based"]
    return [[points[a], points[b]] for a, b in links], links


def draw_layer(image, obj, title, reference=False, raw_sequence=False):
    layer = image.copy().convert("RGB")
    d = ImageDraw.Draw(layer)
    pairs, links = ordered_pairs(obj, reference, raw_sequence)
    for side, color in [(0, "#00efff"), (1, "#ffad36")]:
        nodes = [tuple(p[side]) for p in pairs]
        for i, a in enumerate(nodes):
            b = nodes[(i + 1) % len(nodes)]
            bx = b[0] + (1024 if b[0] - a[0] < -512 else -1024 if b[0] - a[0] > 512 else 0)
            for shift in (-1024, 0, 1024):
                d.line([(a[0] + shift, a[1]), (bx + shift, b[1])], fill=color, width=3)
        for i, p in enumerate(nodes):
            x, y = p
            d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=color, outline="black", width=1)
            pid = links[i][side] + 1
            d.text((x + 5, y - 12), str(pid), fill="white", stroke_width=2, stroke_fill="black")
    banner = Image.new("RGB", (1024, 32), "#17212c")
    roles = "raw first=cyan raw second=orange" if raw_sequence else "top=cyan bottom=orange"
    ImageDraw.Draw(banner).text((8, 8), title + f" | {roles}; IDs=original; straight connectors only show identity", fill="white")
    result = Image.new("RGB", (1024, 544))
    result.paste(banner, (0, 0))
    result.paste(layer, (0, 32))
    return result


def ring_edges(order):
    return sorted([sorted((order[i], order[(i + 1) % len(order)])) for i in range(len(order))])


def record_for(code, case, obj, verdict, evidence, reference=False):
    points = obj["raw_points"] if reference else obj["raw_points_1024x512"]
    if not points or len(points) % 2:
        raise ValueError(f"Missing or odd raw point count: {code}")
    raw_links = [[i, i + 1] for i in range(0, len(points), 2)]
    current_links = (sorted(raw_links, key=lambda pair: (points[pair[0]][0] + points[pair[1]][0]) / 2)
                     if reference else obj["links_zero_based"])
    if not current_links or sorted(i for pair in current_links for i in pair) != list(range(len(points))):
        raise ValueError(f"Point identity drift: {code}")
    raw_pair_lookup = {frozenset(pair): f"p{i+1}" for i, pair in enumerate(raw_links)}
    same_pairing = {frozenset(pair) for pair in current_links} == set(raw_pair_lookup)
    current_groups = [{"group_id": raw_pair_lookup[frozenset(pair)] if same_pairing else f"g{i+1}",
                       "original_point_ids_1based": [v + 1 for v in pair]}
                      for i, pair in enumerate(current_links)]
    current_order = [group["group_id"] for group in current_groups]
    raw_order = [f"p{i+1}" for i in range(len(raw_links))]
    proposed = raw_order if reference else current_order if verdict == "无需调整" else None
    if reference:
        changed = len(set(map(tuple, ring_edges(raw_order))) - set(map(tuple, ring_edges(current_order))))
        if changed != AUDITED_GT[code]:
            raise ValueError(f"GT edge audit mismatch: {code}: {changed}")
    return {
        "image_code": code, "image_id": case["image_id"],
        "object_type": "mp3d_gt_original" if reference else "canonical_annotation",
        "object_id": obj["source"] if reference else obj["canonical_annotation_id"],
        "worker_id": None if reference else obj["worker_id"],
        "source": obj["source"] if reference else obj["raw_export_path"],
        "source_raw_click_or_gt_pair_order": raw_order,
        "source_raw_pair_point_ids_1based": [[i + 1, i + 2] for i in range(0, len(points), 2)],
        "current_ring_groups": current_groups,
        "current_ring_order": current_order,
        "current_ring_edges": ring_edges(current_order),
        "suggested_ring_order": proposed,
        "suggested_ring_edges": ring_edges(proposed) if proposed else None,
        "pairing_same_as_contiguous_raw_pairs": same_pairing,
        "source_gt_edge_replacements": AUDITED_GT[code] if reference else None,
        "verdict": verdict,
        "evidence": evidence,
        "uncertainty": ("来源GT有环序，仍须核实遮挡后的可见边界和表示方法。" if reference else
                        "点击先后不是已确认房间环序；图像不能唯一恢复被墙体遮住的连接。" if verdict == "无法确定" else
                        "仅指现有配对环无需再换序，不裁定点位、范围或GT质量。"),
        "pending_user_confirmation": True,
        "applied": False,
    }


def write_outputs(data, cases):
    records = []
    for code, case in cases.items():
        evidence, workers = NOTES[code]
        for worker, verdict in workers.items():
            obj = next(a for a in case["annotations"] if a["worker_id"] == worker)
            records.append(record_for(code, case, obj, verdict, evidence))
        if code in AUDITED_GT:
            obj = next(r for r in case["references"] if r["name"] == "gt_original")
            records.append(record_for(code, case, obj, "建议调整", evidence + " 来源GT原环序的无向边与现有按x构造不同，应保留来源连接身份。", True))
    all_codes = {row["code"]: row["image_id"] for row in data["rows"]}
    unreviewed = [{"code": code, "image_id": image_id} for code, image_id in sorted(all_codes.items()) if code not in cases]
    output = {
        "schema": "order_preliminary_review_v1", "contract_version": "consensus_research_20260923_v1",
        "state": "pending_user_confirmation", "source": "consensus_visual_review_20260923 read-only cases; original MP3D GT",
        "checked_images": [{"code": code, "image_id": case["image_id"], "workers": CASES[code],
                            "reference_checked": "gt_original"} for code, case in cases.items()],
        "unreviewed_images": unreviewed,
        "counts": {"checked_images": len(cases), "canonical_objects": sum(r["object_type"] == "canonical_annotation" for r in records),
                   "canonical_new_reorder_suggestions": 0, "gt_representation_suggestions": len(AUDITED_GT),
                   "cannot_determine_objects": sum(r["verdict"] == "无法确定" for r in records),
                   "no_change_objects": sum(r["verdict"] == "无需调整" for r in records),
                   "unreviewed_images": len(unreviewed)},
        "records": records,
    }
    (OUT / "建议清单.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    esc = html.escape
    sections = []
    for code, case in cases.items():
        selected = [r for r in records if r["image_code"] == code]
        rows = []
        for r in selected:
            who = r["worker_id"] or "原MP3D GT"
            current = ", ".join(r["current_ring_order"])
            proposed = ", ".join(r["suggested_ring_order"] or []) or "待定"
            mapping = "; ".join(f"{g['group_id']}=点{','.join(map(str,g['original_point_ids_1based']))}" for g in r["current_ring_groups"])
            edges = "; ".join("–".join(pair) for pair in r["current_ring_edges"])
            proposed_edges = "; ".join("–".join(pair) for pair in r["suggested_ring_edges"] or []) or "待定"
            rows.append(f"<tr><td>{esc(who)}<br><small>{esc(r['object_id'])}</small></td><td>{esc(r['verdict'])}</td>"
                        f"<td>{esc(', '.join(r['source_raw_click_or_gt_pair_order']))}</td><td>{esc(current)}<br><small>边：{esc(edges)}</small></td>"
                        f"<td>{esc(proposed)}<br><small>边：{esc(proposed_edges)}</small></td><td>{esc(mapping)}</td></tr>")
        sections.append(f"<section id='{esc(code)}'><h2>{esc(code)}</h2><p>{esc(NOTES[code][0])}</p>"
                        f"<p><a href='{esc(code)}.png'>打开完整对照图</a> · 原点击行蓝绿/橙色分别是原第1/第2端点，不代表已确认上下；现有配对行蓝绿/橙色才是上/下端。直线仅标示连接身份，非真实全景墙线。跨接缝连线已分段显示。</p>"
                        f"<img loading='lazy' src='{esc(code)}.png' alt='{esc(code)} 来源GT、人员原点击顺序与当前配对环对照'>"
                        "<div class='scroll'><table><thead><tr><th>对象</th><th>初审</th><th>原点击/来源序</th><th>当前环序及边</th><th>建议环序及边</th><th>当前组与原点号</th></tr></thead><tbody>"
                        + "".join(rows) + "</tbody></table></div></section>")
    page = ("<!doctype html><html lang='zh-CN'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>首批顺序初审</title><style>body{font:16px/1.6 system-ui;margin:auto;max-width:1100px;padding:24px;color:#17212c;background:#f7f8f9}"
            "section{background:white;padding:18px;margin:28px 0;border:1px solid #ddd;border-radius:9px}img{width:100%;height:auto}"
            "table{border-collapse:collapse;min-width:900px}th,td{padding:8px;border:1px solid #ddd;text-align:left;vertical-align:top}"
            "small{overflow-wrap:anywhere}.scroll{overflow-x:auto}nav a{margin-right:12px}</style>"
            "<h1>可能错序的首批视觉初审</h1><p>10张图，人员新修序建议0项；3项为来源GT环序保留／表示构造修复候选。全部待用户确认，未应用。"
            "人员原点击顺序不等于真实环序。点对、坐标与既有裁决均未更改。</p>"
            "<p><a href='建议清单.json'>机器可读清单与未审队列</a></p><nav>"
            + " ".join(f"<a href='#{esc(code)}'>{esc(code)}</a>" for code in cases) + "</nav>"
            + "".join(sections) + "</html>")
    (OUT / "index.html").write_text(page, encoding="utf-8")


def main():
    OUT.mkdir(exist_ok=True)
    data = load_json_js(SOURCE / "data.js", "window.REVIEW_DATA=")
    loaded_cases = {}
    for code, workers in CASES.items():
        row = next(row for row in data["rows"] if row["code"] == code)
        case = load_json_js(SOURCE / "cases" / f"{row['image_id']}.js", "window.REVIEW_CASE=")
        loaded_cases[code] = case
        original = Image.open(ROOT / case["image_src"].removeprefix("../../")).resize((1024, 512))
        layers = []
        for ref in case["references"]:
            if ref["name"] == "gt_original":
                layers.append(draw_layer(original, ref, "MP3D GT original", True))
                break
        for worker in workers:
            ann = next(a for a in case["annotations"] if a["worker_id"] == worker)
            layers.append(draw_layer(original, ann, f"{worker} / {ann['canonical_annotation_id']} / raw click sequence", raw_sequence=True))
            layers.append(draw_layer(original, ann, f"{worker} / {ann['canonical_annotation_id']} / existing accepted pairs x order"))
        sheet = Image.new("RGB", (1024, 544 * len(layers)))
        for i, layer in enumerate(layers):
            sheet.paste(layer, (0, i * 544))
        sheet.save(OUT / f"{code}.png", optimize=True)
    write_outputs(data, loaded_cases)


if __name__ == "__main__":
    main()
