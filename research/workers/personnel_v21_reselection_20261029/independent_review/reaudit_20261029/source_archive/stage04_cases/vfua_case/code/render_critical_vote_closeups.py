#!/usr/bin/env python3
"""Exact original-image closeups with frozen vote-group centers and references.

Scientific annotation only: no image synthesis, ring repair, or target change.
ERP seam is explicitly wrapped so the uNb case's two close azimuths remain visible.
"""
from pathlib import Path
import gzip
import json
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from render_exact_abc_case import COLORS, great_arc, save_figure

ROOT = Path(__file__).resolve().parents[1]
CROPS = {"f48b5b2dcce86d87b6ce5ece": (600, 735, 190, 345)}
CRITICAL = {"A": {"node_002", "node_005", "node_007", "node_008"},
            "B": {"node_002", "node_004", "node_005", "node_006"},
            "C": {"node_002", "node_005", "node_006", "node_007"}}



for event_id, (left, right, top, bottom) in CROPS.items():
    with gzip.open(ROOT / "traces" / f"{event_id}.json.gz", "rt") as f:
        t = json.load(f)
    e = t["event"]
    picture = np.array(Image.open(ROOT / "originals" / (e["image"] + ".png")).convert("RGB")
                       .resize((1024, 512), Image.Resampling.LANCZOS))
    wrapped = np.concatenate([picture, picture, picture], axis=1)
    ref = np.array(t["reference"]["points_1024x512"], float).reshape(-1, 2, 2)
    D = set(e["D"].split("|"))
    fig, axs = plt.subplots(1, 3, figsize=(12, 8.5))
    for ax, arm, replacement in zip(axs, "ABC", "XYZ"):
        a = t["arms"][arm]
        ax.imshow(wrapped, extent=(-1024, 2048, 512, 0))
        for level in (0, 1):
            ring = ref[:, level, :]
            for i in range(len(ring)):
                for segment in great_arc(ring[i], ring[(i + 1) % len(ring)]):
                    for shift in (-1024, 0, 1024):
                        ax.plot(segment[:, 0] + shift, segment[:, 1], color="black", lw=1.2, ls="--")
        for i, pair in enumerate(ref):
            x = pair[:, 0] + 1024 * round(((left + right) / 2 - pair[1, 0]) / 1024)
            ax.plot(x, pair[:, 1], color="black", lw=1, ls="--")
            if left <= x[1] <= right:
                ax.scatter(x, pair[:, 1], color="black", marker="s", s=25, zorder=8)
                ax.annotate(f"参考 r{i + 1}", (x[1], pair[1, 1]), xytext=(4, 3),
                            textcoords="offset points", fontsize=8, color="black",
                            bbox=dict(facecolor="white", edgecolor="none", alpha=.7), zorder=10)
        groups = []
        for g in a["full_state"]["identity_groups"]:
            if g["feature_id"] not in CRITICAL[arm]:
                continue
            pair = np.array(g["center"], float)
            x = pair[:, 0] + 1024 * round(((left + right) / 2 - pair[1, 0]) / 1024)
            if left <= x[1] <= right:
                groups.append((g, pair, x))
        for i, (g, pair, x) in enumerate(sorted(groups, key=lambda item: item[1][1, 1])):
            who = {m["worker"] for m in g["members"]}
            d, z = len(who & D), len(who - D)
            selected = bool(g["selected"])
            color = COLORS[arm] if selected else "#555555"
            ax.plot(x, pair[:, 1], color=color, lw=1.8 if selected else .9, alpha=.9)
            ax.scatter(x, pair[:, 1], s=42, facecolors=color if selected else "white",
                       edgecolors=color, lw=1.3, zorder=9)
            # Deliberately spread labels vertically; leader lines retain the exact coordinates.
            tx = .03 if i % 2 == 0 else .55
            ty = .91 - .16 * i
            label = f"{g['feature_id']}\n{g['support']} = D{d}+{replacement}{z}"
            ax.annotate(label, (x[1], pair[1, 1]), xytext=(tx, ty),
                        textcoords="axes fraction", fontsize=8, ha="left", va="top",
                        color=color, bbox=dict(facecolor="white", edgecolor=color, alpha=.90, pad=2),
                        arrowprops=dict(arrowstyle="-", color=color, lw=.9), zorder=12)
        ax.set_xlim(left, right)
        ax.set_ylim(bottom, top)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("ERP 水平像素（负数按 1024 回绕）" if left < 0 else "ERP 水平像素")
        ax.set_ylabel("ERP 竖直像素")
        ax.set_title(f"{arm}：D+{replacement}；门槛 {a['minimum_support']}\n实心入选，空心未入选", fontsize=11)
    fig.suptitle(f"{e['image']} | {e['method']} | n=16，m=8\n右侧四个关注对应组的中位位置及支持票；事件 {event_id}", fontsize=12)
    fig.text(.5, .025, "仅显示右侧四个关注对应组；其余全部候选请查完整票账。黑虚线为当前固定参考。\n局部节点名称只在各臂内有效，跨臂关系请查 COMMON_D_GROUP_LINKS.csv。", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .07, 1, .91))
    out = ROOT / "figures" / event_id
    save_figure(fig, out / "LOCAL_CRITICAL_VOTES.png", dpi=180)
    save_figure(fig, out / "LOCAL_CRITICAL_VOTES.pdf")
    plt.close(fig)
    print(event_id, flush=True)
