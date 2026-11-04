"""Standalone scientific figures from the delivered numerical tables."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from ac_common import HERE, read_csv, write_json, COMBINED
from create_analysis_deliverables import select


def setup_font(filename):
    if filename:
        font_manager.fontManager.addfont(filename)
        name = font_manager.FontProperties(fname=filename).get_name()
    else:
        available = set(font_manager.get_font_names())
        names = ["Noto Sans CJK SC", "Source Han Sans SC", "Microsoft YaHei", "SimHei"]
        name = next((n for n in names if n in available), None)
        if name is None:
            raise RuntimeError("Install Noto Sans CJK SC or pass --font /path/to/font.otf")
    plt.rcParams.update({"font.family": name, "axes.unicode_minus": False, "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False, "svg.fonttype": "none",
                         "figure.facecolor": "white", "axes.titleweight": "bold"})
    return name


def clean(ax):
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#dde3eb", linewidth=.6)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", default=os.environ.get("HOHONET_CJK_FONT"))
    args = parser.parse_args()
    font = setup_font(args.font)
    out = HERE / "figures"
    out.mkdir(exist_ok=True)
    meta = dict(analysis_cohort=COMBINED, version="automatic", scope="primary", n=20, m=7)
    cond = select(read_csv(HERE / "CONDITION_STRATIFIED_Q.csv"), **meta, direction="C2_to_C3", stratum_type="official_difficulty").set_index("stratum").loc[["简单", "中等", "困难"]]
    high = select(read_csv(HERE / "HIGH_SCORE_BAND_EFFECTS.csv"), **meta, direction="C2_to_C3", stratum_type="symmetric_Q_band").set_index("stratum").loc[["M<60", "60<=M<80", "80<=M<90", "M>=90"]]
    same = select(read_csv(HERE / "SAME_NODE_COUNT_COMPONENTS.csv.gz"), **meta, class_pair="C2_C3")
    image = select(read_csv(HERE / "COMPONENT_IMAGE_EFFECTS.csv.gz"), **meta, class_pair="C2_C3", support="original_common")

    fig, axs = plt.subplots(2, 2, figsize=(12.8, 9.2), gridspec_kw={"hspace": .48, "wspace": .27})
    fig.suptitle("当前 DSTRUCT C2→C3：变化幅度与几何取舍", x=.06, y=.98, ha="left", fontsize=17, weight="bold")
    fig.text(.06, .937, "20人换7人 · 普通Manual原目标 · 自动版原共同Q · 存量条件分析＋预定容量补缺", fontsize=10, color="#48546b")
    ax = axs[0, 0]
    x = np.arange(3)
    for offset, field, label, color in [(-.18, "image_equal_mean", "有符号ΔQ", "#287aa9"), (.18, "mean_absolute_pair_effect_image_equal", "平均绝对ΔQ", "#d48d39")]:
        values = cond[field].to_numpy(float)
        bars = ax.bar(x + offset, values, width=.34, label=label, color=color)
        ax.bar_label(bars, fmt="%.2f", padding=3, fontsize=9)
    ax.set_xticks(x, [f"{name}\n{int(r.images)}图/{int(r.buildings)}楼" for name, r in cond.iterrows()])
    ax.set_ylim(0, 19)
    ax.set_ylabel("Q分")
    ax.set_title("A  困难图的变化更大，方向也更分散", loc="left", fontsize=12)
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    clean(ax)

    ax = axs[0, 1]
    bars = ax.bar(np.arange(4), high.image_equal_mean, color=["#94b4cc", "#6f9aba", "#4e84ad", "#28709e"], width=.65)
    ax.bar_label(bars, fmt="%.2f", padding=3, fontsize=9)
    ax.set_xticks(np.arange(4), [f"{s}\n{int(r.images)}图" for s, (_, r) in zip(["M<60", "60≤M<80", "80≤M<90", "M≥90"], high.iterrows())])
    ax.set_ylim(0, 20)
    ax.set_ylabel("平均绝对ΔQ")
    ax.set_title("B  高分端幅度受限，完整区间并非单调", loc="left", fontsize=12)
    ax.text(.02, .97, "M=(QA+QC)/2\n|ΔQ|≤2 min(M,100−M)", transform=ax.transAxes, va="top", fontsize=9, bbox=dict(facecolor="white", edgecolor="#d4dee8", alpha=.9))
    clean(ax)

    ax = axs[1, 0]
    groups = ["same_node_count", "different_node_count"]
    vals = same.loc[same.metric.eq("dQ")].set_index("node_count_group").loc[groups]
    ab = same.loc[same.metric.eq("abs_dQ")].set_index("node_count_group").loc[groups]
    for offset, value, label, color in [(-.18, vals.image_equal_mean, "有符号ΔQ", "#287aa9"), (.18, ab.image_equal_mean, "平均绝对ΔQ", "#d48d39")]:
        bars = ax.bar(np.arange(2) + offset, value, width=.34, label=label, color=color)
        ax.bar_label(bars, fmt="%.2f", padding=3, fontsize=9)
    ax.set_xticks(np.arange(2), [f"同节点数\n{int(vals.loc[groups[0], 'images'])}图", f"不同节点数\n{int(vals.loc[groups[1], 'images'])}图"])
    ax.set_ylim(0, 21)
    ax.set_ylabel("Q分")
    ax.set_title("C  节点数相同，仍有可观几何与Q变化", loc="left", fontsize=12)
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    clean(ax)

    ax = axs[1, 1]
    negative = image.delta_B8L2.lt(0)
    ax.scatter(image.loc[~negative, "delta_dir"], image.loc[~negative, "delta_B8L2"], s=28, color="#287aa9", alpha=.65, label="Q升：77图")
    ax.scatter(image.loc[negative, "delta_dir"], image.loc[negative, "delta_B8L2"], s=48, color="#bd5547", label="Q降：7图", zorder=3)
    ax.axhline(0, color="#7d8897", linewidth=.7)
    ax.axvline(0, color="#7d8897", linewidth=.7)
    ax.set_xlabel("方向误差变化（°；右侧更差）")
    ax.set_ylabel("图均ΔQ")
    ax.set_title("D  7张降Q图均伴随方向误差增加", loc="left", fontsize=12)
    ax.legend(frameon=False, loc="upper right", fontsize=9)
    ax.text(.02, .03, "7张降Q图的3D IoU同时全部上升", transform=ax.transAxes, fontsize=9, color="#9b453b")
    clean(ax)
    fig.text(.06, .025, "各柱按同图汇总后等权；补缺图先D背景、再X/Z块等权。分层图池可重叠，不能相加；图间关联不是因果机制。\n来源：CONDITION_STRATIFIED_Q、HIGH_SCORE_BAND_EFFECTS、SAME_NODE_COUNT_COMPONENTS、COMPONENT_IMAGE_EFFECTS。", fontsize=9, color="#48546b")
    fig.subplots_adjust(left=.075, right=.97, top=.875, bottom=.13)
    for ext in ["png", "svg"]:
        fig.savefig(out / ("A01_CONDITIONAL_MAGNITUDE_AND_GEOMETRY." + ext), dpi=180, bbox_inches="tight")
    plt.close(fig)

    summary = select(read_csv(HERE / "Q_FORMULA_ATTRIBUTION_SUMMARY.csv"), **meta, direction="C2_to_C3").iloc[0]
    bad = read_csv(HERE / "C23_20_7_SEVEN_Q_DECLINE_IMAGES.csv")
    terms = ["range_2d_IoU", "bottom_boundary", "direction", "global_height", "local_height"]
    labels = ["范围（2D IoU）", "底边", "方向", "全局高度", "局部高度"]
    colors = ["#3e95b6", "#65ab82", "#df8a4d", "#866ab0", "#bd7ca0"]
    values = np.vstack([[summary["Q_term_" + t + "_image_equal_mean"] for t in terms], bad[["Q_term_" + t for t in terms]].to_numpy(float)])
    total = np.r_[summary.dQ_image_equal_mean, bad.dQ.to_numpy(float)]
    names = ["84图整体"] + bad.image.tolist()
    fig, ax = plt.subplots(figsize=(12, 7.8))
    y = np.arange(len(names))
    pos, neg = np.zeros(len(names)), np.zeros(len(names))
    for j, (label, color) in enumerate(zip(labels, colors)):
        value = values[:, j]
        left = np.where(value >= 0, pos, neg)
        ax.barh(y, value, left=left, height=.62, color=color, label=label)
        pos += np.maximum(value, 0)
        neg += np.minimum(value, 0)
    ax.axvline(0, color="#576578", linewidth=.8)
    ax.scatter(total, y, marker="D", color="#172b40", s=35, zorder=4, label="实际ΔQ（分项和）")
    ax.set_yticks(y, names)
    ax.invert_yaxis()
    lo, hi = float(neg.min()), float(pos.max())
    ax.set_xlim(lo - 1., hi + 3.)
    for i, value in enumerate(total):
        ax.text(hi + .5, i, f"ΔQ {value:+.3f}", va="center", fontsize=10, color="#172b40")
    ax.grid(axis="x", color="#dde3eb", linewidth=.6)
    ax.set_axisbelow(True)
    ax.set_xlabel("既有Q公式的五输入算术贡献（Q分）")
    ax.set_title("面积改善与方向损失可以同时发生", fontsize=16, loc="left", pad=45)
    ax.text(0, 1.035, "当前DSTRUCT C2→C3，20人换7人：整体与全部7张图均降Q的图片", transform=ax.transAxes, color="#48546b", fontsize=10)
    ax.legend(loc="lower center", bbox_to_anchor=(.5, -0.24), ncol=3, frameon=False, fontsize=10)
    fig.text(.08, .025, "所有120种输入代入次序等权平均；逐对分解后按冻结权重汇总。五项严格相加回实际ΔQ。\n中间混合输入不是新的真实几何，本图解释评分算术，不是因果中介分析。来源：Q_FORMULA_ATTRIBUTION_*。", fontsize=9, color="#48546b")
    fig.subplots_adjust(left=.19, right=.97, top=.83, bottom=.22)
    for ext in ["png", "svg"]:
        fig.savefig(out / ("A02_QUALITY_COMPONENT_TRADEOFFS." + ext), dpi=180, bbox_inches="tight")
    plt.close(fig)
    write_json(HERE / "FIGURES_RECEIPT.json", dict(status="generated", font_family=font, figures=["figures/A01_CONDITIONAL_MAGNITUDE_AND_GEOMETRY", "figures/A02_QUALITY_COMPONENT_TRADEOFFS"], numerical_sources="delivered frozen CSVs", new_endpoints=0, formats=["png", "svg"]))
    print("two scientific figures generated", flush=True)


if __name__ == "__main__":
    main()
