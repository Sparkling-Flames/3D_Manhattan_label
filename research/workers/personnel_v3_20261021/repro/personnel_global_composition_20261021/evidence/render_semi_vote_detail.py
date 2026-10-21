#!/usr/bin/env python3
"""Show the observed final answers and exact 11-vote discontinuity in C02."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np
from PIL import Image
from render_evidence import HERE, RENDERER, DEFAULT_FONT, read, original_photo


def observations(group):
    return {(m["id"], m["pair_index"]) for m in group["members"]}


def main():
    path = HERE / "cases/C02_rPc17_semi_same_class.json.gz"
    case = read(path)
    a, b = case["teams"][:2]
    assert a["k"] == b["k"] == 21
    assert a["minimum_support"] == b["minimum_support"] == 11
    lookup = {m["worker_id"]: m for m in case["members"]}
    ga, gb = a["full_state"]["identity_groups"], b["full_state"]["identity_groups"]
    critical_a = next(g for g in ga if any(m["worker"] == "W002" and m["pair_index"] == 6 for m in g["members"]))
    critical_b = max(gb, key=lambda g: len(observations(g) & observations(critical_a)))
    alternative_b = next(g for g in gb if any(m["worker"] == "W010" and m["pair_index"] == 6 for m in g["members"]))
    alternative_a = max(ga, key=lambda g: len(observations(g) & observations(alternative_b)))
    assert [g["support"] for g in [critical_a, critical_b, alternative_a, alternative_b]] == [11, 10, 6, 7]
    assert np.array_equal(np.array(lookup["W002"]["points"])[:12], np.array(lookup["W010"]["points"])[:12])
    photo_path = original_photo(case, HERE / "originals")
    spec = importlib.util.spec_from_file_location("frozen_visuals", RENDERER)
    v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)
    v._configure_font(DEFAULT_FONT)
    fig = v.plt.figure(figsize=(12, 6.6))
    grid = fig.add_gridspec(1, 3, width_ratios=[.85, 1.25, 1.4], left=.04, right=.985,
                          top=.80, bottom=.20, wspace=.27)
    colors = {"W002": "#16859b", "W010": "#c66b19"}
    ax = fig.add_subplot(grid[0])
    v._erp_background(ax, np.asarray(Image.open(photo_path).convert("RGB")), bounds=[840,985,50,465])
    for w in ["W002", "W010"]:
        v._erp_edges(ax, lookup[w]["points"], colors[w], linewidth=1.7, markers=True)
    ref = case["reference"]
    v._erp_edges(ax, ref["points_1024x512"], v.REF_ERP_COLOR, reference=True, linewidth=1.4)
    ax.set_title("同一开口附近的原答位置\nW002：x907；W010：x931.90", fontsize=10)
    ax = fig.add_subplot(grid[1])
    refg = v.viewer_geometry(ref["points_1024x512"], ref.get("floor_xz_h"))
    geoms = {w: v.viewer_geometry(lookup[w]["points"], lookup[w].get("footprint")) for w in colors}
    for w in colors:
        v._bev_ring(ax, geoms[w]["floor"], colors[w], linewidth=1.8)
    v._bev_ring(ax, refg["floor"], v.REF_COLOR, reference=True)
    v._style_bev(ax, v._bounds([refg] + list(geoms.values())))
    ax.set_title("个人原答均为7角，前6对完全相同\nQ：85.975与85.794", fontsize=10)
    ax = fig.add_subplot(grid[2])
    groups = [(critical_a, critical_b), (alternative_a, alternative_b)]
    yy = np.array([1., 0.])
    for offset, index, w, label in [(.17, 0, "W002", "保留W002的21人队"), (-.17, 1, "W010", "保留W010的21人队")]:
        vals = [pair[index]["support"] for pair in groups]
        ax.barh(yy + offset, vals, height=.29, color=colors[w], label=label, alpha=.9)
        for y, val in zip(yy + offset, vals):
            ax.text(val + .12, y, str(val), va="center", fontsize=10, color=colors[w])
    ax.axvline(11, color="#434c59", linewidth=1.5, linestyle="--")
    ax.text(10.93, 1.52, "固定门槛11票", ha="right", fontsize=9, color="#434c59")
    ax.set_yticks(yy, ["约x907组", "约x933组"], fontsize=10)
    ax.set_xlim(0, 12.1); ax.set_ylim(-.5, 1.6)
    ax.set_xticks([0, 3, 6, 9, 11]); ax.set_xlabel("实际支持人数", fontsize=10)
    ax.grid(axis="x", color="#e7eaf0"); ax.set_axisbelow(True)
    for sp in ax.spines.values(): sp.set_color("#d0d5dc")
    ax.set_title("20人共同背景；共有人分组未变\n11→10失选，6→7仍未达门槛", fontsize=10)
    ax.legend(loc="lower left", bbox_to_anchor=(-.1,-.3), frameon=False, fontsize=9)
    fig.suptitle("同类、个人质量接近，局部位置改变关键第11票", x=.04, y=.965, ha="left", fontsize=16)
    fig.text(.04,.89,"rPc-17 · Semi · 两人均为楼外SP_T与A2 A01；固定n=21、实际换1人；冻结参考位置x917.64",
             fontsize=10,color="#637386")
    fig.text(.04,.07,"照片与原答只支持可见位置差异；不据此推断编辑动机或认定某人选择了唯一正确的物理边界。\n"
             "ERP黄色／BEV黑虚线为冻结参考；两人原答的相近Q不能代替这次实际投票结果。融合Q为85.975与33.843。",
             fontsize=9,color="#536475")
    output = HERE / "figures/C02_rPc17_semi_same_class/raw_position_and_votes.png"
    fig.savefig(output, dpi=165, bbox_inches="tight", facecolor="white"); v.plt.close(fig)
    receipt = {"case_id": case["case_id"], "source_case_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
               "image_sha256": case["image_sha256"], "figure_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
               "shared_first_six_pairs_exact": True, "critical_supports": [11,10], "alternative_supports": [6,7],
               "threshold": 11, "no_fusion_or_score_recompute": True}
    (output.parent / "POSITION_VOTE_DETAIL_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n")
    print(str(output))


if __name__ == "__main__": main()
