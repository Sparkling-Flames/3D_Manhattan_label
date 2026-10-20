"""Redraw mixed-composition and P05 figures from compact audited tables only."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "personnel_mplconfig"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    a = ap.parse_args()
    root = a.root.resolve()
    base = root / "interchangeability_20261020"
    ind = base / "independent"
    font = root / "analysis/fonts/NotoSansSC-Regular.ttf"
    if font.exists():
        font_manager.fontManager.addfont(str(font))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=font).get_name()
    plt.rcParams.update({"axes.unicode_minus": False, "font.size": 11, "axes.titlesize": 13,
                         "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 170})
    used = []
    outputs = []

    def load(path):
        used.append(path)
        return pd.read_csv(path)

    def save(fig, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, facecolor="white")
        plt.close(fig)
        outputs.append(path)

    mixed = ind / "mixed_challenge"
    d = load(mixed / "both_effects/ROUTE_CONTEXT.csv")
    methods = [
        ("F20_highQ23_T_qK2", "高 Q 23 人：来源内时间二类"),
        ("F20_new_Scope_qK2", "新批：OUT 回答倾向二类"),
        ("F20_new_NewNonedit_qK2", "新批：报告错误未改倾向二类"),
        ("F20_semi_new_QTGEditReport_balanced_K3", "新批 Semi：条件画像三类"),
        ("R_directswap_continuous_partition_b2_K3__ordinary__mixed_history_v1", "反向：连续风险三类"),
        ("R_directswap_geometry_partition_b0_K7__ordinary__mixed_history_v1", "反向：几何风险七类"),
        ("R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1", "新批反向：几何风险二类"),
    ]
    maincol = "dedup_within_joint_stable_main_building_mean"
    shapecol = "dedup_within_geometry_shape_main_building_mean"
    fig, axes = plt.subplots(1, 2, figsize=(16.5, 6.8), sharey=True)
    for ax, phase, title in zip(axes, ["discovery", "assessment"], ["发现：51 真图／6 楼", "冻结后评估：45 真图／6 楼"]):
        for i, (mid, _) in enumerate(methods):
            whole = d[(d.phase == phase) & (d.method_id == mid) & (d.context_id == "whole_team")].iloc[0]
            partial = d[(d.phase == phase) & (d.method_id == mid) & (d.context_id == "partial_mixed_block")].iloc[0]
            ax.hlines(i, whole[maincol] * 100, partial[maincol] * 100, color="#b9c3cc", lw=1.4, zorder=1)
            ax.scatter(whole[maincol] * 100, i, color="#2877b8", s=74, label="整队：主判据" if i == 0 else None, zorder=3)
            ax.scatter(partial[maincol] * 100, i, color="#d87a28", marker="D", s=54, label="部分替换：主判据" if i == 0 else None, zorder=3)
            ax.scatter(whole[shapecol] * 100, i + .15, color="#299d8f", marker="^", s=50, label="整队：新 shape" if i == 0 else None, zorder=3)
            ax.text(99.5, i, f"{int(whole.images)} 图 / {int(whole.buildings)} 楼", va="center", ha="right", fontsize=9, color="#596672")
        ax.set(xlim=(0, 100), yticks=range(len(methods)), yticklabels=[name for _, name in methods], xlabel="同构成换人稳定率（%，建筑等权）", title=title)
        ax.grid(axis="x", alpha=.18)
        ax.set_ylim(len(methods)-.45, -.65)
    axes[0].legend(loc="lower left", bbox_to_anchor=(-.42, 1.12), ncol=3, frameon=False, fontsize=10)
    fig.suptitle("整队构成挑战：相同类别计数仍有可观的人员波动", fontsize=17, x=.57, y=.96)
    fig.text(.02, .025, "每条路线内 A/B 类别计数完全相同；整队 n=m，部分替换 n>m。两组人数、比例和图片支持不同，横线只表示描述差值。\n失败保留为不稳定；独立样本单位是图片／建筑。Semi 覆盖较少；现有 v2 的评估不是新外部盲测。", fontsize=10, color="#48525b")
    fig.subplots_adjust(left=.265, right=.99, bottom=.17, top=.77, wspace=.12)
    save(fig, mixed / "figures/mixed_whole_partial_stability.png")

    f = load(mixed / "both_effects/FOCUSED_CONDITIONS.csv")
    f = f[f.subset == "all"]
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 6.2), sharey=True)
    specs = [("HQ_T_n7_5fast2slow_within", "n=7，5 快＋2 慢", "#267db5"),
             ("HQ_T_n5_2fast3slow_within", "n=5，2 快＋3 慢", "#c76c36")]
    for ax, col, title in zip(axes, [maincol, shapecol], ["原主稳定判据", "新 shape 几何判据"]):
        for focus_id, label, color in specs:
            s = f[f.focus_id == focus_id].set_index("phase").loc[["discovery", "assessment"]]
            y = s[col].to_numpy() * 100
            ax.plot([0, 1], y, "o-", color=color, lw=2.5, ms=8, label=label)
            for x, (_, row), yy in zip([0, 1], s.iterrows(), y):
                labeltext = f"{yy:.1f}%\n{int(row.images)} 图／{int(row.buildings)} 楼"
                offset_y = -45 if focus_id == "HQ_T_n5_2fast3slow_within" and x == 0 else 12
                ax.annotate(labeltext, (x, yy), (8 if x == 0 else -8, offset_y), textcoords="offset points",
                            ha="left" if x == 0 else "right", fontsize=10, color=color,
                            bbox=dict(facecolor="white", edgecolor="none", alpha=.92, pad=1.2))
        ax.set(xticks=[0, 1], xticklabels=["发现", "冻结后评估"], xlim=(-.18, 1.18), ylim=(-3, 103), title=title,
               ylabel="同构成整队换人稳定率（%）")
        ax.grid(axis="y", alpha=.18)
    axes[0].legend(frameon=False, loc="upper left", fontsize=10)
    fig.suptitle("固定配比的正例与反例一起复查：高 Q 人员内的时间二类", fontsize=16, y=.965)
    fig.text(.025, .035, "两种构成都在读取评估结果前冻结保留，图中是各自实际 n 和配比，不能解释为仅改变比例的因果效果。\nn=7 的支持大多为简单图；删除若干特定人员后全部对照消失，尚未独立于现有具体人员验证。", fontsize=10, color="#48525b")
    fig.subplots_adjust(left=.075, right=.98, top=.82, bottom=.20, wspace=.16)
    save(fig, mixed / "figures/mixed_frozen_HQ_ratios.png")

    p05 = ind / "p05_local"
    pop = load(p05 / "FINAL_TEAM_GEOMETRY_DIAGNOSTICS.csv.gz")
    pop = pop[pop.phase == "census"]
    wall = load(p05 / "REFERENCE_WALL_OFFSETS.csv")
    wall = wall[(wall.phase == "census") & (wall.reference_edge == 1)]
    pairs = load(base / "ratio_grid/local_census/results/finite_population_summary.csv")
    winner = load(base / "ratio_grid/confirmation_results/discovery_winners_followed_without_reselection.csv")
    winner = winner[winner.rule_id == "P05"].iloc[0]
    auditpath = p05 / "P05_LOCAL_AUDIT.json"
    audit = json.loads(auditpath.read_text()); used.append(auditpath)
    gain = {r["phase"]: r["gain"] for r in audit["gains"]}
    pairs["vector"] = pairs.class_counts.map(lambda x: "|".join(c + ":" + str(ast.literal_eval(x).get(c, 0)) for c in ["C01", "C02", "C03"]))
    series = [("C01:5|C02:0|C03:0", "C01 纯类（56 队）", "#967447"),
              ("C01:0|C02:5|C03:0", "C02 纯类（56 队）", "#377eb8"),
              ("C01:0|C02:0|C03:5", "C03 纯类（56 队）", "#d26755"),
              ("C01:1|C02:3|C03:1", "1:3:1 混类（3,584 队）", "#30978c")]
    fig, axes = plt.subplots(2, 2, figsize=(14.3, 9.0))
    ax = axes[0, 0]
    ys = [float(winner.discovery), gain["replication16"], gain["census"]]
    ax.plot(range(3), ys, "o-", color="#30978c", lw=2.5, ms=8)
    for i, v in enumerate(ys):
        ax.annotate(f"+{v:.3f}", (i, v), (0, 8), textcoords="offset points", ha="center", fontsize=12, fontweight="bold")
    ax.axhline(0, color="#888888", lw=1)
    ax.set(xticks=range(3), xticklabels=["发现筛选", "同图新成员\n每构成 16 队", "固定有限总体\n全部 3,752 队"],
           xlim=(-.3, 2.3), ylim=(-.8, 14), ylabel="混类减最佳观测纯类的 Q 均值", title="A  互补幅度随完整复查收缩")
    ax.grid(axis="y", alpha=.15)
    ax = axes[0, 1]
    for vector, label, color in series:
        values = np.sort(pop[pop.vector == vector].B8L2.to_numpy())
        ax.step(values, np.arange(1, len(values)+1)/len(values), where="post", label=label, color=color, lw=2)
    ax.set(xlabel="每支精确团队的 B8L2", ylabel="有限总体累积比例", title="B  全部团队质量分布与低尾", xlim=(40, 100), ylim=(0, 1.02))
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    ax.grid(alpha=.15)
    ax = axes[1, 0]
    for i, (vector, label, color) in enumerate(series):
        value = float(wall[wall.vector == vector].signed_outward_offset_ref_scale.iloc[0])
        ax.barh(i, value, color=color, height=.55)
        ax.text(value + (.004 if value >= 0 else -.004), i, f"{value:+.4f}", ha="left" if value >= 0 else "right", va="center", fontsize=10)
    ax.axvline(0, color="#666666", lw=1)
    ax.set(yticks=range(4), yticklabels=["C01 纯类", "C02 纯类", "C03 纯类", "1:3:1 混类"],
           xlim=(-.17, .10), xlabel="远墙平均偏移 / √参考面积（负：向内；正：向外）", title="C  远侧参考墙的范围偏差")
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=.15)
    ax = axes[1, 1]
    for i, (vector, label, color) in enumerate(series):
        row = pairs[pairs.vector == vector].iloc[0]
        ax.bar(i-.18, 100*row.within_joint_stable_main, width=.33, color=color, alpha=.5)
        ax.bar(i+.18, 100*row.within_geometry_shape_main, width=.33, color=color)
    ax.set(xticks=range(4), xticklabels=["C01 纯类", "C02 纯类", "C03 纯类", "1:3:1 混类"],
           ylim=(0, 30), ylabel="同构成配对稳定率（%）", title="D  微小平均优势没有带来普遍互换性")
    ax.text(.03, .94, "浅色：原主判据　深色：新 shape", transform=ax.transAxes, va="top", fontsize=10)
    ax.grid(axis="y", alpha=.15)
    fig.suptitle("P05 · jtcxE69GiFV-03：固定 n=5 的单图配比普查", fontsize=18, y=.97)
    fig.text(.02, .025, "正向综合画像三类；1 图／1 楼／24 人，所有团队完整可评价。远墙位置接近仅是平均诊断，所有结果仍为 4 节点。\n三个纯类各 1,540 对全部计算；混类只固定抽 2,000 / 6,420,736 对。普查是发现结果后的局部机制复核，不是新验证。", fontsize=10, color="#48525b")
    fig.subplots_adjust(left=.09, right=.98, bottom=.16, top=.88, hspace=.48, wspace=.28)
    save(fig, p05 / "figures/p05_local_population.png")

    receipt = dict(schema="compact_mixed_P05_figures_v1", scientific_native_calls=0,
        inputs={str(p.relative_to(root)): sha(p) for p in used}, code_sha256=sha(Path(__file__).resolve()),
        font_path=str(font.relative_to(root)),
        outputs=[dict(path=str(p.relative_to(root)), bytes=p.stat().st_size, sha256=sha(p)) for p in outputs],
        interpretation="No uncertainty intervals are implied. Building-weighted rates and finite-team distributions retain their distinct units. No native fusion or scientific rule was changed.")
    target = ind / "COMPACT_EXPLANATION_FIGURE_RECEIPT.json"
    target.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    print(json.dumps(receipt["outputs"], ensure_ascii=False))


if __name__ == "__main__":
    main()
