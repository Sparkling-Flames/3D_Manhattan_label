#!/usr/bin/env python3
"""Render supplied new-study ABC cases without fusion, re-scoring or selection.

Uses the existing frozen-coordinate renderer.  Additional raw-answer three-view
overlays give an explicit, small representative membership list.  Case selection
must be recorded as post-result explanation and does not estimate effect size.
"""
from __future__ import annotations
import argparse
import copy
import csv
import gzip
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, "/tmp/hohonet_deps")

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RENDERER = ROOT / "research/workers/personnel_interchangeability_20261020/analysis/composition/case_visuals.py"
DEFAULT_FONT = ROOT / "research/workers/personnel_composition_study_20261019/analysis/fonts/NotoSansSC-Regular.ttf"


def read(path):
    with gzip.open(path, "rt") if str(path).endswith(".gz") else open(path) as f:
        return json.load(f)


def original_photo(case, directory):
    image_id = case.get("image_id") or case.get("pool_meta", {}).get("image_id")
    p = directory / f"{image_id}.png"
    if not p.is_file():
        raise FileNotFoundError(f"Original Release photo absent: {p}; this renderer requires the actual source image")
    case["image_id"] = image_id
    case["image_path"] = str(p.resolve())
    case["image_sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    return p


def raw_three_views(v, case, photo_path, out):
    members = case.get("members", [])
    if not members:
        return None
    explicit_groups = case.get("raw_overlay_groups")
    chosen_ids = list(dict.fromkeys(w for g in explicit_groups for w in g["workers"])) if explicit_groups else case.get("raw_overlay_workers")
    if chosen_ids is None:
        classes = sorted({m.get("class_id", "unknown") for m in members})
        chosen_ids = [m["worker_id"] for cl in classes for m in sorted(
            (x for x in members if x.get("class_id", "unknown") == cl), key=lambda x: x["worker_id"])[:3]]
        choice = "up to3 per supplied class in worker_id order; no score-based filtering"
    else:
        choice = "explicit explanatory worker list retained in case JSON"
    byworker = {m["worker_id"]: m for m in members}
    if not set(chosen_ids) <= byworker.keys():
        raise ValueError("raw_overlay_workers_not_in_exact_case_members")
    selected = [byworker[w] for w in chosen_ids]
    classes = sorted({m.get("class_id", "unknown") for m in selected})
    groups = [[m for m in selected if m.get("class_id", "unknown") == cl] for cl in classes]
    titles = [case.get("class_names", {}).get(cl, cl) for cl in classes]
    if explicit_groups:
        groups = [[byworker[w] for w in g["workers"]] for g in explicit_groups]
        classes = [g.get("class_id", group[0].get("class_id", "unknown")) for g, group in zip(explicit_groups, groups)]
        titles = [g["label"] for g in explicit_groups]
    geometries = {m["worker_id"]: v.viewer_geometry(m.get("points"), m.get("footprint")) for m in selected}
    ref = case["reference"]
    ref_geom = v.viewer_geometry(ref["points_1024x512"], ref.get("floor_xz_h"))
    bounds = v._bounds([ref_geom] + list(geometries.values()))
    heights = v._heights([ref_geom] + list(geometries.values()))
    photo = np.asarray(Image.open(photo_path).convert("RGB"))
    columns = min(4, len(classes))
    blocks = (len(classes) + columns - 1) // columns
    fig = v.plt.figure(figsize=(4.4 * columns, 9.5 * blocks + .8))
    grid = fig.add_gridspec(3 * blocks, columns, height_ratios=[1, 1.25, 1.5] * blocks,
                           left=.05, right=.985, top=.90 if blocks == 1 else .95,
                           bottom=.075 if blocks == 1 else .04, hspace=.24, wspace=.24)
    for i, (cl, group) in enumerate(zip(classes, groups)):
        block, col = divmod(i, columns)
        color = case.get("class_colors", {}).get(cl, v.CLASS_COLORS[i % len(v.CLASS_COLORS)])
        ax = fig.add_subplot(grid[3*block, col])
        v._erp_background(ax, photo)
        for member in group:
            v._erp_edges(ax, member.get("points"), color, linewidth=1.0, alpha=.67, markers=True)
        v._erp_edges(ax, ref["points_1024x512"], v.REF_ERP_COLOR, reference=True, linewidth=1.0)
        name = titles[i]
        ax.set_title(name + "\n" + " / ".join(m["worker_id"] for m in group), fontsize=10, color=color)
        ax = fig.add_subplot(grid[3*block+1, col])
        for member in group:
            v._bev_ring(ax, geometries[member["worker_id"]].get("floor"), color, alpha=.65)
        v._bev_ring(ax, ref_geom.get("floor"), v.REF_COLOR, reference=True)
        v._style_bev(ax, bounds)
        ax.set_title("原答BEV；同一坐标尺度", fontsize=9)
        ax = fig.add_subplot(grid[3*block+2, col], projection="3d")
        for member in group:
            v._wire3d(ax, geometries[member["worker_id"]], color)
        v._wire3d(ax, ref_geom, v.REF_COLOR, reference=True)
        v._style3d(ax, bounds, heights, case.get("view", {"elev": 26, "azim": -54}))
        ax.set_title("原答3D；相机高度=1", fontsize=9, pad=1)
    fig.suptitle(case.get("raw_overlay_title", case.get("title", "") + "：同类原答叠加"),
                 fontsize=14, y=.984, x=.05, ha="left")
    fig.text(.05, .025 if blocks == 1 else .015,
             "黄色ERP／黑色虚线为冻结参考；代表成员完整名单见JSON。类别由目标建筑外历史形成。\n"
             "3D顶部沿配对底点水平距离推导，非实测房高；本图为结果后的机制解释，不用于总体结论。",
             fontsize=8, color="#536475")
    path = out / "raw_three_views.png"
    fig.savefig(path, dpi=165, facecolor="white", bbox_inches="tight")
    v.plt.close(fig)
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "members": chosen_ids, "selection": choice, "shared_bev_bounds": bounds,
            "shared_height_bounds": heights}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--case", type=Path, required=True)
    p.add_argument("--photos", type=Path, default=HERE / "originals")
    p.add_argument("--out", type=Path)
    p.add_argument("--font", type=Path, default=DEFAULT_FONT)
    args = p.parse_args()
    case = copy.deepcopy(read(args.case))
    case.setdefault("selection", "post_result_explanatory_not_an_effect_estimator")
    if "reference_id" not in case["reference"]:
        case["reference"]["reference_id"] = case["reference"].get("target_id")
    photo = original_photo(case, args.photos)
    out = args.out or HERE / "figures" / case["case_id"]
    out.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location("archived_case_visuals", RENDERER)
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)
    v._configure_font(args.font)
    # This existing renderer verifies exact member sets, object IDs, class counts,
    # geometry coordinate convention and optional source image SHA before drawing.
    result = v.render_case(case, out, font_path=args.font)
    result["raw_three_views"] = raw_three_views(v, case, photo, out)
    members = []
    for m in case.get("members", []):
        rows = {"case_id": case["case_id"], "worker_id": m["worker_id"], "object_id": m.get("object_id"),
                "class_id": m.get("class_id"), "origin": m.get("origin"), "B8L2": m.get("B8L2"), "D10": m.get("D10")}
        for t in case["teams"]:
            rows["in_" + str(t.get("label", t["team_key"]))] = m["worker_id"] in t["member_workers"]
        members.append(rows)
    if members:
        with (out / "members.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(members[0]))
            w.writeheader(); w.writerows(members)
    receipt = dict(result, adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   source_case=str(args.case), source_case_sha256=hashlib.sha256(args.case.read_bytes()).hexdigest(),
                   no_fusion_or_score_rerun=True, no_point_or_reference_changes=True)
    (out / "EVIDENCE_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"case_id": case["case_id"], "out": str(out), "actual_original_image": str(photo),
                      "team_count": len(case["teams"]), "member_count": len(members)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
