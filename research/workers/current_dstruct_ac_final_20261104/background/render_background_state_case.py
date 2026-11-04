"""Show the frozen first example of each existing background output state.

Reads six saved native endpoints. Missing rings are drawn only as selected
node pairs (ERP) or individual projected bottom points (BEV); no ring is made,
and missing Q is never shown as zero. No endpoint is recalculated.
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from PIL import Image

from render_fixed_xz_case import HERE, TASK, REPO, COLORS, erp, set_font, fetch_original, write_json, sha

CODE = "yqstnuAEVhm-27"
STEM = "FIXED_XZ_BACKGROUND_OUTPUT_STATES"


def finite(v):
    return v is not None and np.isfinite(float(v))


def number(v, digits=3):
    return f"{float(v):.{digits}f}" if finite(v) else "不可评"


def selected_centers(endpoint):
    return [g for g in endpoint["full_state"]["identity_groups"] if g["selected"] and g.get("center")]


def bottom_points(endpoint):
    if (endpoint.get("geometry") or {}).get("footprint"):
        return np.asarray(endpoint["geometry"]["footprint"])
    result = []
    for g in selected_centers(endpoint):
        p = np.asarray(g["center"])[1]
        v = (p[1] / 512 - .5) * np.pi
        if not 0 < v < np.pi / 2:
            continue
        u, r = p[0] * 2 * np.pi / 1024, 1 / np.tan(v)
        result.append([-np.sin(u) * r, np.cos(u) * r])
    return np.asarray(result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", default=os.environ.get("HOHONET_CJK_FONT"))
    args = parser.parse_args()
    font = set_font(args.font)
    selection_path = HERE / "ILLUSTRATIVE_OUTPUT_STATE_CASE.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    rows = selection["selected_records"]
    expected = ["ACG_0c1a7fcfd9abeb0b3c4c588e", "ACG_2fc2366ff5f8db7ac821a73b", "ACG_858d5a854aa57f276ce6107c"]
    assert [r["event_id"] for r in rows] == expected
    assert selection["registered_backgrounds"] == 32 and selection["common_Q_backgrounds"] == 29
    raw_path = TASK / selection["native_endpoint_pool"]
    raw = json.loads(gzip.decompress(raw_path.read_bytes()))
    teams = {e["team_key"]: e for e in raw["teams"]}
    pool_path = TASK / "supplement/inputs/SELECTED_POOLS.json.gz"
    pools = json.loads(gzip.decompress(pool_path.read_bytes()))["images"]
    pool = next(p for p in pools if p["pool_id"] == rows[0]["pool_id"])
    ref = pool["reference"]["points_1024x512"]
    ref_floor = np.asarray(pool["reference"]["floor_xz_h"])
    photo_path, photo_receipt = fetch_original(CODE)
    photo = Image.open(photo_path)
    selected = []
    checks = []
    metric_rows = []
    for row in rows:
        D, X, Z = [set(row[c + "_workers"].split("|")) for c in ["D", "X", "Z"]]
        assert not (D & X or D & Z or X & Z) and len(D) == len(X) == len(Z) == 7
        arms = {}
        for arm, members in [("A", D | X), ("C", D | Z)]:
            endpoint = teams[row[arm + "_team_key"]]
            assert set(endpoint["member_workers"]) == members
            assert endpoint["reference_id"] == row["reference_id"] == pool["reference"]["target_id"]
            assert endpoint["score_status"] == row[arm + "_score_status"]
            q = row["Q_" + arm]
            assert (q is None and not finite(endpoint["B8L2"])) or (finite(q) and abs(q - endpoint["B8L2"]) < 1e-10)
            assert endpoint["minimum_support"] == 7
            if not finite(q):
                assert endpoint["score_status"] == "no_connection"
                assert endpoint["geometry"]["points"] is None and endpoint["geometry"]["footprint"] is None
            arms[arm] = endpoint
            checks.append(dict(event_id=row["event_id"], arm=arm, team_key=endpoint["team_key"], binding="passed", score_status=endpoint["score_status"], missing_Q_preserved=q is None))
            fields = ["B8L2", "D10", "IoU3D100", "iou_2d", "nodes", "S_bottom_deg", "dir", "Hmean", "Hcenter", "minimum_support", "score_status", "geometry_reason"]
            metric_rows.append(dict(event_id=row["event_id"], background_id=row["background_id"], arm=arm, team_key=endpoint["team_key"], D_workers=row["D_workers"], X_workers=row["X_workers"], Z_workers=row["Z_workers"], **{k: endpoint.get(k) for k in fields}))
        selected.append(dict(event=row, arms=arms))
    all_floor = np.vstack([ref_floor] + [bottom_points(s["arms"][a]) for s in selected for a in ["A", "C"]])
    xlim = [all_floor[:, 0].min() - .3, all_floor[:, 0].max() + .3]
    ylim = [all_floor[:, 1].min() - .3, all_floor[:, 1].max() + .3]
    fig = plt.figure(figsize=(18, 16.7))
    grid = fig.add_gridspec(4, 3, height_ratios=[1.1, 1, 1, 1], width_ratios=[1, 1, .82], hspace=.40, wspace=.15)
    fig.suptitle("同一换人块与纯C2背景：换具体成员也可改变连接状态", x=.035, y=.988, ha="left", fontsize=19, weight="bold")
    fig.text(.035, .958, f"{CODE} · 当前DSTRUCT C1→C3 · n=14，m=7 · 32个既有背景：29对双端Q、2对C无连接、1对A无连接", fontsize=12, color="#46576b")
    ax = fig.add_subplot(grid[0, 0:2]); ax.imshow(photo, extent=[0, 1024, 512, 0]); ax.set_xticks([]); ax.set_yticks([])
    ax.set_title("原图（Release原PNG，未改字节）", loc="left", fontsize=12)
    ax = fig.add_subplot(grid[0, 2]); ax.axis("off")
    labels = ["两块固定成员，不再选队", "X：7名C1", "  ".join(selection["fixed_X_members"]), "Z：7名C3", "  ".join(selection["fixed_Z_members"]), "D始终7名C2；未知0", "固定名义阈值：7票", "逐状态取event_id排序首例", "无连接端只画保存节点，不补闭环", "Q缺失时不报ΔQ，也不按0计算"]
    y = .98
    for i, txt in enumerate(labels):
        ax.text(0, y, txt, va="top", fontsize=11 if i in [0, 1, 3, 5] else 9.4, color="#263b52")
        y -= .095
    state_names = {"complete_conditional": "可评", "no_connection": "无连接"}
    for i, case in enumerate(selected):
        row, arms = case["event"], case["arms"]
        dlabel = row["background_id"].split("_")[-1]
        for j, arm in enumerate(["A", "C"]):
            endpoint = arms[arm]
            ax = fig.add_subplot(grid[i + 1, j])
            ax.imshow(photo, extent=[0, 1024, 512, 0])
            erp(ax, ref, COLORS["R"], "--", 1.1)
            geometry = endpoint.get("geometry") or {}
            if geometry.get("points"):
                erp(ax, geometry["points"], COLORS[arm], lw=1.7)
                p = np.asarray(geometry["points"])
                ax.scatter(p[:, 0], p[:, 1], s=14, color=COLORS[arm], edgecolors="white", linewidths=.5)
            else:
                for g in selected_centers(endpoint):
                    p = np.asarray(g["center"])
                    ax.scatter(p[:, 0], p[:, 1], s=26, marker="x", c=COLORS[arm], linewidths=1.6)
                    ax.text(p[1, 0] + 2, p[1, 1] + 12, f"{g['feature_id'].replace('node_', 'g')}({g['support']})", color=COLORS[arm], fontsize=7,
                            bbox=dict(facecolor="white", alpha=.9, edgecolor="none", pad=1))
                ax.text(.02, .06, "仅节点与票数；无可用连接／Q缺失", transform=ax.transAxes, fontsize=10, color=COLORS[arm], bbox=dict(facecolor="white", edgecolor="none", alpha=.92))
            ax.set_xlim(0, 1024); ax.set_ylim(512, 0); ax.set_xticks([]); ax.set_yticks([])
            ax.set_title(f"{dlabel} · {arm}：{state_names[endpoint['score_status']]}  |  Q {number(endpoint.get('B8L2'))}  ·  {endpoint['nodes']}节点", loc="left", fontsize=11, color=COLORS[arm], weight="bold")
            subtitle = f"3D IoU {number(endpoint.get('IoU3D100'))}% · 方向误差 {number(endpoint.get('dir'))}° · 底边误差 {number(endpoint.get('S_bottom_deg'))}°"
            if not finite(endpoint.get('B8L2')):
                subtitle = "原状态原因：no_source_ring_covering_all_selected_nodes"
            ax.text(0, -.06, subtitle, transform=ax.transAxes, va="top", fontsize=8.6, color="#40546b")
            if arm == "A":
                ax.text(0, -.14, f"{dlabel}成员：" + row["D_workers"].replace("|", "  "), transform=ax.transAxes, va="top", fontsize=8.5, color="#40546b")
        ax = fig.add_subplot(grid[i + 1, 2])
        closed = np.vstack([ref_floor, ref_floor[0]])
        ax.plot(closed[:, 0], closed[:, 1], color=COLORS["R"], ls="--", lw=1.2)
        for arm in ["A", "C"]:
            endpoint = arms[arm]
            floor = bottom_points(endpoint)
            if (endpoint.get("geometry") or {}).get("footprint"):
                closed = np.vstack([floor, floor[0]])
                ax.plot(closed[:, 0], closed[:, 1], color=COLORS[arm], lw=1.6)
                ax.scatter(floor[:, 0], floor[:, 1], s=14, color=COLORS[arm])
            else:
                ax.scatter(floor[:, 0], floor[:, 1], s=25, marker="x", color=COLORS[arm])
        ax.scatter([0], [0], marker="^", s=18, color="#566779")
        ax.set_xlim(xlim); ax.set_ylim(ylim); ax.set_aspect("equal", adjustable="box"); ax.grid(alpha=.2)
        ax.set_xlabel("x/h", fontsize=8.5); ax.set_ylabel("z/h", fontsize=8.5); ax.tick_params(labelsize=8)
        state = state_names[arms["A"]["score_status"]] + "→" + state_names[arms["C"]["score_status"]]
        ax.set_title(state + "；ΔQ " + number(row.get("dQ")), loc="left", fontsize=11)
        if i == 0:
            ax.legend(handles=[Line2D([0],[0],color=COLORS["R"],ls="--",label="GT"),Line2D([0],[0],color=COLORS["A"],label="A"),Line2D([0],[0],color=COLORS["C"],label="C")], ncol=3, fontsize=8, frameon=True,loc="upper right")
    fig.text(.035, .055, "这些是同一冻结32背景块的三种既有输出状态，每种按event_id排序取首例；不是重新选队，也不是按Q挑出的改善样本。\n失败端点的叉号来自保存的入选节点中心，底面仅作点投影显示，不排序、不闭合、不修复；两端都有Q时才计算ΔQ。", fontsize=10.2, color="#3d526b", linespacing=1.5)
    fig.text(.035, .018, f"原图：{photo_receipt['archive']} / {photo_receipt['bytes']}字节 / CRC32 {photo_receipt['zip_crc32']}。完整32背景、原生full_state与具体成员见冻结JSON及源池链接。\n原图SHA256、六端身份核验与可复现代码见 OUTPUT_STATE_FIGURE_RECEIPT.json；原图文件保持2048×1024且字节未改。", fontsize=9, color="#53677d")
    fig.subplots_adjust(left=.035, right=.975, top=.92, bottom=.12)
    for ext in ["png", "svg"]:
        out = io.BytesIO(); fig.savefig(out, format=ext, dpi=170, bbox_inches="tight", facecolor="white")
        (HERE / (STEM + "." + ext)).write_bytes(out.getvalue())
    plt.close(fig)
    pd.DataFrame(metric_rows).to_csv(HERE / "OUTPUT_STATE_SIX_ENDPOINT_METRICS.csv", index=False)
    compact = dict(selection=selection, reference=pool["reference"], examples=selected, original=photo_receipt)
    (HERE / "OUTPUT_STATE_RENDER_EVIDENCE.json.gz").write_bytes(gzip.compress(json.dumps(compact, ensure_ascii=False).encode(), mtime=0))
    write_json(HERE / "OUTPUT_STATE_FIGURE_RECEIPT.json", dict(status="generated", events=expected, endpoint_bindings=checks,
               sources=[dict(path=str(p.relative_to(REPO)), sha256=sha(p)) for p in [selection_path, raw_path, pool_path]],
               original_sha256=photo_receipt["sha256"], original_crc32=photo_receipt["zip_crc32"], font_family=font,
               figure=STEM + ".png", no_missing_Q_imputation=True, unconnected_nodes_display_only=True,
               new_fusions=0, new_team_selections=0, new_scores=0, new_closed_rings=0, frozen_analysis_or_mechanism_files_modified=False))
    print("three frozen background output states rendered", flush=True)


if __name__ == "__main__":
    main()
