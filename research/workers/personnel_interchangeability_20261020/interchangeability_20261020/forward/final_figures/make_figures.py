#!/usr/bin/env python3
"""Three exact-table scientific figures for the frozen F / common-panel study.

By default, redraw from the small, retained *_plot_data.csv.gz tables beside
this script.  --rebuild-data explicitly regenerates those tables from the full
statistical outputs, which are reproducible but omitted from the lean package.
Neither mode reruns fusion, fits categories, or changes scientific definitions.
"""
from pathlib import Path
import argparse
import os
import sys
import json
os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl_interchangeability_f20")
for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[k] = "1"
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, ticker

HERE = Path(__file__).resolve().parent
FORWARD = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(FORWARD / "common_panel"))
from summarize_common_panel import write_csv, write_json, sha

FONT = ROOT / "analysis/fonts/NotoSansSC-Regular.ttf"
font_manager.fontManager.addfont(str(FONT))
plt.rcParams.update({"font.family": font_manager.FontProperties(fname=str(FONT)).get_name(), "font.size": 10,
                     "axes.unicode_minus": False, "axes.titlesize": 13, "axes.labelsize": 11,
                     "figure.facecolor": "white", "savefig.facecolor": "white"})
BLUE, ORANGE, GREEN = "#2868A8", "#D47620", "#168875"

MID_LABELS = {
    "F20_newCommon_Full_balanced_K2": "七域 Full 二类",
    "F20_newCommon_Full_balanced_K3": "七域 Full 三类",
    "F_rule_Q_quantile_K2": "历史 Q 分位二类",
    "F_rule_Q_quantile_K3": "历史 Q 分位三类",
    "F20_all_QTG_balanced_medoids_K4": "Q／T／几何四类",
    "R_directswap_geometry_partition_b0_K2__ordinary_new__mixed_history_v1": "反向新来源无 Q 二类",
    "R_directswap_geometry_partition_b0_K7__ordinary_new__mixed_history_v1": "反向新来源无 Q 七类",
    "R_directswap_geometry_partition_b0_K7__ordinary__mixed_history_v1": "反向普通无 Q 七类*",
}
ROUTE_LABELS = {
    "F01": "高 Q23：慢→快", "F02": "高 Q18：慢→快", "F03": "高 Q新：T／编辑 C02→C01",
    "F04": "Q／T／几何：C04→C02", "F05": "Q／T／几何：C02→C04", "F06": "高 Q23：多点→少点",
    "F07": "困难：T／适应／几何 C03→C02", "F08": "scope：高 OUT→低 OUT",
    "F09": "Semi：低编辑→高编辑", "F10": "Manual：低未改→高未改", "F11": "Semi：低未改→高未改",
}

def clean(ax, vertical=True):
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#BBBBBB")
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x" if vertical else "y", color="#E4E8EC", linewidth=.7)
    ax.set_axisbelow(True)

def save(fig, name):
    path = HERE / name
    fig.savefig(path, dpi=155, bbox_inches="tight")
    plt.close(fig)
    return path

def retained_table(name):
    path = HERE / name
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing retained plotting table: {path}. Restore this packaged "
            "table, or use --rebuild-data after reconstructing the full "
            "statistical outputs; default plotting does not read those outputs."
        )
    return pd.read_csv(path)


def common8(rebuild_data=False):
    if rebuild_data:
        phases = []
        for phase in ("discovery", "assessment"):
            path = FORWARD / "common_panel/competitors" / phase / "core_aggregate.csv.gz"
            d = pd.read_csv(path)
            d = d.loc[d.support.eq("common8") & d.n.eq("ALL")].copy()
            d["phase"] = phase
            phases.append(d)
        d = pd.concat(phases, ignore_index=True)
        cols = ["phase", "method_id", "support", "restriction", "n", "pools", "buildings", "cores", "eligible_A_observations", "unique_teams",
                "within_joint_stable_main", "cross_joint_stable_main", "gap_joint_stable_main", "gap_geometry_noQ_main",
                "excess_floor_jaccard_difference", "within_quality_drop_gt5", "cross_quality_drop_gt5"]
        write_csv(HERE / "01_common8_plot_data.csv.gz", d[cols])
    else:
        d = retained_table("01_common8_plot_data.csv.gz")
    mids = list(MID_LABELS)
    fig, axes = plt.subplots(2, 2, figsize=(15.2, 10.8))
    fig.subplots_adjust(left=.24, right=.98, bottom=.17, top=.88, hspace=.52, wspace=.14)
    fig.suptitle("同 26 名新来源人员、同一 A 团队：八种冻结分类的公平竞争", x=.51, y=.98, fontsize=18, weight="bold")
    fig.text(.24, .923, "稳定率差 = 同构成 A→B − 异构成 A→C；单位：百分点。正值表示同构成更稳定。", fontsize=11)
    support_notes = []
    for ri, restriction in enumerate(("all", "history_A_Qclose3")):
        points = d.loc[d.restriction.eq(restriction)]
        note = []
        for phase, label in (("discovery", "发现"), ("assessment", "评估复查")):
            x = points.loc[points.phase.eq(phase)].iloc[0]
            assert points.loc[points.phase.eq(phase), "eligible_A_observations"].nunique() == 1
            note.append(f"{label} {int(x.pools)}图／6楼，{int(x.eligible_A_observations):,}个A")
        support_notes.append("；".join(note))
        for ci, metric in enumerate(("gap_joint_stable_main", "gap_geometry_noQ_main")):
            ax = axes[ri, ci]
            clean(ax)
            ax.axvline(0, color="#444444", linewidth=1)
            for phase, label, offset, color in (("discovery", "发现", .13, BLUE), ("assessment", "评估复查", -.13, ORANGE)):
                values = points.loc[points.phase.eq(phase)].set_index("method_id").loc[mids, metric].to_numpy() * 100
                y = np.arange(8)[::-1] + offset
                ax.scatter(values, y, s=33, color=color, label=label, zorder=3)
                for value, yy in zip(values, y):
                    ax.plot([0, value], [yy, yy], color=color, alpha=.24, lw=1.7)
                    dx = .09 if ri == 0 else .16
                    ax.text(value + (dx if value >= 0 else -dx), yy, f"{value:+.2f}", va="center", ha="left" if value >= 0 else "right", fontsize=8.4, color=color)
            ax.set_yticks(np.arange(8)[::-1], [MID_LABELS[m] for m in mids] if ci == 0 else [""] * 8)
            ax.set_ylim(-.6, 7.6)
            ax.set_xlim((-0.5, 3.65) if ri == 0 else (-6.1, 6.1))
            ax.set_xlabel("同构成优势（百分点）")
            ax.set_title(("A  整体分类效用" if ri == 0 else "B  同来源 + 历史 Q 近似子集") + ("｜主联合" if ci == 0 else "｜去 Q 阈值的几何"), loc="left", pad=12)
            if ri == 0 and ci == 1:
                ax.legend(loc="lower right", frameon=False, fontsize=10)
    fig.text(.02, .104, "整体共同支持：" + support_notes[0], fontsize=10.5)
    fig.text(.02, .078, "Q 近似共同支持：" + support_notes[1] + "。这是邻块对 A 的历史 Q 差≤3，不是三块任意两两都≤3。", fontsize=10)
    fig.text(.02, .051, "人数节点5／9／13／17，换2人；按共同背景、图片、建筑等权。两阶段为不同建筑，均属于既有 v2；重复A／团队不增加独立样本。", fontsize=9.5)
    fig.text(.02, .025, "* 普通反向七类投影到26人后仅6个非空类，含单人类。同类替换容量损失保留；原16项七域消融另表，不与不同A支持混排。", fontsize=9.5)
    return save(fig, "01_common8_fair_competition.png")

def f11(rebuild_data=False):
    if rebuild_data:
        path = FORWARD / "assessment_interpretation"
        d = pd.read_csv(path / "F11_aggregate.csv.gz")
        d = d.loc[d.setting.eq("fixed_n_m")].copy()
        coverage = pd.read_csv(path / "F11_coverage_and_failures.csv.gz")
        coverage = coverage.loc[coverage.setting.eq("fixed_n_m")]
        loow = pd.read_csv(path / "F11_leave_one_worker_out_summary.csv.gz")
        loow = loow.loc[loow.control.eq("overall")].set_index("route_id")
        keep = ["route_id", "method_id", "outgoing_class", "incoming_class", "control", "events", "images", "buildings", "net_B8L2_change", "net_D10_change",
                "within_Q_drop_gt5", "cross_Q_drop_gt5", "source_block_geometric_ratio", "source_block_log_ratio_known_events", "source_block_log_ratio_known_images",
                "within_joint_stable_main", "cross_joint_stable_main", "within_geometry_shape_main", "cross_geometry_shape_main", "gap_geometry_noQ_main"]
        write_csv(HERE / "02_F11_plot_data.csv.gz", d[keep])
        write_csv(HERE / "02_F11_empty_support.csv.gz", coverage)
        write_csv(HERE / "02_F11_LOOW_ranges.csv.gz", loow.reset_index())
    else:
        d = retained_table("02_F11_plot_data.csv.gz")
        coverage = retained_table("02_F11_empty_support.csv.gz")
        loow = retained_table("02_F11_LOOW_ranges.csv.gz").set_index("route_id")
    overall = d.loc[d.control.eq("overall")].set_index("route_id")
    qnear = d.loc[d.control.eq("source_Qclose3")].set_index("route_id")
    cov = coverage.loc[coverage.control.eq("source_Qclose3")].set_index("route_id")
    fig, axes = plt.subplots(1, 3, figsize=(18, 9.7), sharey=True)
    fig.subplots_adjust(left=.31, right=.98, top=.84, bottom=.19, wspace=.27)
    fig.suptitle("十一条冻结前向方向：质量、来源报告效率和同类坏尾分别判断", x=.52, y=.98, fontsize=18, weight="bold")
    fig.text(.31, .915, "评估固定 n=13、m=2；两条 Semi 规则固定 n=7、m=2。压力人数／替换规模另表。", fontsize=11)
    labels = []
    ids = list(ROUTE_LABELS)
    for i, rid in enumerate(ids):
        r = overall.loc[rid]; q = qnear.loc[rid] if rid in qnear.index else None
        y = 10 - i
        labels.append(f"{rid}  {ROUTE_LABELS[rid]}   {int(r.images)}/{int(r.buildings)}｜{int(cov.loc[rid, 'images'])}/{int(cov.loc[rid, 'buildings'])}")
        lo, hi = loow.loc[rid, ["net_B8L2_change_min", "net_B8L2_change_max"]]
        axes[0].plot([lo, hi], [y, y], color="#A9B8C7", lw=2.6, alpha=.75)
        axes[0].scatter(r.net_B8L2_change, y, color=BLUE, s=38, zorder=4)
        axes[0].text(r.net_B8L2_change, y + .21, f"{r.net_B8L2_change:+.2f}", ha="center", fontsize=9, color=BLUE)
        axes[1].scatter(r.source_block_geometric_ratio, y + .11, color=BLUE, s=36, label="整体" if i == 0 else None)
        axes[1].text(r.source_block_geometric_ratio, y + .27, f"{r.source_block_geometric_ratio:.3f}", ha="center", fontsize=8.6, color=BLUE)
        if q is not None and np.isfinite(q.source_block_geometric_ratio):
            axes[1].scatter(q.source_block_geometric_ratio, y - .14, edgecolors=ORANGE, facecolors="white", marker="s", s=30, linewidths=1.4,
                            label="同来源 + 历史Q近似" if i == 0 else None)
        else:
            axes[1].text(1.55, y - .15, "空", color=ORANGE, fontsize=9, ha="center")
        axes[2].plot([100*r.within_Q_drop_gt5, 100*r.cross_Q_drop_gt5], [y, y], color="#CBD2D8", lw=2)
        axes[2].scatter(100*r.within_Q_drop_gt5, y + .10, s=33, color=BLUE, label="同构成 A→B" if i == 0 else None)
        axes[2].scatter(100*r.cross_Q_drop_gt5, y - .10, s=33, marker="D", color=ORANGE, label="跨构成 A→C" if i == 0 else None)
    axes[0].set_yticks(np.arange(11)[::-1], labels)
    axes[0].set_ylim(-.6, 10.8)
    axes[0].set_xlim(-7.1, 4.2); axes[0].axvline(0, color="#444444", lw=1)
    axes[0].set_title("A  C−B 质量方向", loc="left"); axes[0].set_xlabel("B8L2 分数差（正值改善）")
    axes[1].set_xscale("log"); axes[1].set_xlim(.24, 1.85)
    axes[1].set_xticks([.25, .4, .6, 1, 1.5], ["0.25", "0.4", "0.6", "1", "1.5"])
    axes[1].xaxis.set_minor_locator(ticker.NullLocator())
    axes[1].axvline(1, color="#444444", lw=1); axes[1].set_title("B  来源报告两人块 C/B", loc="left")
    axes[1].set_xlabel("用时比的几何均值（<1 更少）")
    axes[1].legend(loc="upper left", bbox_to_anchor=(-.01, -.10), frameon=False, fontsize=9)
    axes[2].set_xlim(0, 26); axes[2].set_title("C  有符号 Q 下降 >5", loc="left")
    axes[2].set_xlabel("符合下降条件的比例（%）")
    axes[2].legend(loc="upper left", bbox_to_anchor=(-.01, -.10), frameon=False, fontsize=9)
    for ax in axes:
        clean(ax)
    fig.text(.03, .882, "行末支持：整体图/楼｜同来源+Q近似图/楼；0/0 = 无该控制子集，未补零", fontsize=10.5)
    fig.text(.03, .101, "质量灰线：删去任一涉及人员后的现有事件估计范围；不是置信区间，图／楼支持会随删人改变。时间控制子集仅在有实际支持时绘制。", fontsize=10)
    fig.text(.03, .074, "时间来自来源任务报告；先对每事件 log(C/B) 在图内均值，再楼内均值、楼等权后取exp。新来源 target_time 全为null，不是目标重做成本。", fontsize=9.6)
    fig.text(.03, .047, "主分数与几何分别保留；完整失败计不稳定，缺分不补0。Q近似要求三块任意两两历史条件Q差≤3；极小子集见随图表。", fontsize=9.6)
    fig.text(.03, .020, "F07使用既有非盲复核困难口径，不能当作新图自动选人验证。scope是回答倾向；新报告未改与编辑均不等于已裁定纠错能力。", fontsize=9.6)
    return save(fig, "02_F11_quality_efficiency_risk.png")

def t23_buildings(rebuild_data=False):
    if rebuild_data:
        tables = []
        for phase, root, stem in (("discovery", FORWARD / "discovery_interpretation", "frozen_directions"),
                                  ("assessment", FORWARD / "assessment_interpretation", "F11")):
            b = pd.read_csv(root / (stem + "_per_building.csv.gz"))
            p = pd.read_csv(root / (stem + "_per_image.csv.gz"))
            b = b.loc[b.route_id.eq("F01")].copy(); p = p.loc[p.route_id.eq("F01")].copy()
            if phase == "discovery":
                b = b.loc[b.view.eq("all_registered_nge3_mge2")]; p = p.loc[p.view.eq("all_registered_nge3_mge2")]
            else:
                b = b.loc[b.setting.eq("fixed_n_m")]; p = p.loc[p.setting.eq("fixed_n_m")]
            b["phase"] = phase
            support = p.groupby(["control", "building"]).agg(pools=("pool_id", "nunique"), finite_Q_images=("net_B8L2_change", "count"), finite_time_images=("source_block_log_ratio", "count")).reset_index()
            b = b.merge(support, on=["control", "building"], validate="one_to_one")
            tables.append(b)
        d = pd.concat(tables, ignore_index=True)
        keep = ["phase", "building", "control", "pools", "finite_Q_images", "finite_time_images", "net_B8L2_change", "net_D10_change", "source_block_log_ratio", "source_block_geometric_ratio",
                "within_joint_stable_main", "cross_joint_stable_main", "within_Q_drop_gt5", "cross_Q_drop_gt5"]
        write_csv(HERE / "03_T23_per_building_plot_data.csv.gz", d[keep])
    else:
        d = retained_table("03_T23_per_building_plot_data.csv.gz")
    fig, axes = plt.subplots(2, 2, figsize=(15.8, 10.5))
    fig.subplots_adjust(left=.12, right=.98, top=.85, bottom=.17, wspace=.24, hspace=.42)
    fig.suptitle("高 Q23 内慢→快：逐建筑质量与来源报告用时", fontsize=18, y=.98, weight="bold")
    fig.text(.12, .93, "每个点为一栋楼内图片等权结果。源匹配与历史Q近似保留各自支持；两阶段建筑不同。", fontsize=11)
    qmin, qmax = d.net_B8L2_change.min(), d.net_B8L2_change.max()
    time_min, time_max = d.source_block_geometric_ratio.min(), d.source_block_geometric_ratio.max()
    controls = [("overall", "整体已测", BLUE, "o", .19), ("source_matched", "块来源匹配", GREEN, "s", 0), ("source_Qclose3", "块来源 + 历史Q近似", ORANGE, "D", -.19)]
    for ci, (phase, title) in enumerate((("discovery", "发现：注册广框架 n≥3、m≥2"), ("assessment", "评估复查：固定 n=13、m=2"))):
        subset = d.loc[d.phase.eq(phase)]
        buildings = sorted(subset.building.unique())
        for ri, metric in enumerate(("net_B8L2_change", "source_block_geometric_ratio")):
            ax = axes[ri, ci]; clean(ax)
            for control, label, color, marker, offset in controls:
                g = subset.loc[subset.control.eq(control)].set_index("building")
                for i, building in enumerate(buildings):
                    y = 5 - i + offset
                    if building not in g.index or not np.isfinite(g.loc[building, metric]):
                        ax.text(qmax + .2 if ri == 0 else time_max * 1.07, y, "无支持", fontsize=8, color=color, ha="right", va="center")
                        continue
                    value = g.loc[building, metric]
                    ax.scatter(value, y, marker=marker, color=color, s=31, label=label if i == 0 and ri == 0 and ci == 0 else None, zorder=3)
                    if control == "overall":
                        ax.text(value + .07 if ri == 0 else value * 1.025, y, f"{value:+.2f}" if ri == 0 else f"{value:.3f}", fontsize=8.5, va="center", color=color)
            overall = subset.loc[subset.control.eq("overall")].set_index("building")
            names = [f"{b}  ({int(overall.loc[b, 'pools'])}图)" for b in buildings]
            ax.set_yticks(np.arange(6)[::-1], names); ax.set_ylim(-.6, 5.7)
            if ri == 0:
                ax.axvline(0, color="#444444", lw=1); ax.set_xlim(qmin - .55, qmax + .7)
                ax.set_xlabel("B8L2 C−B（正值改善）"); ax.set_title(title, loc="left", pad=11)
            else:
                ax.set_xscale("log"); ax.set_xlim(max(.08, time_min * .88), max(1.12, time_max * 1.18)); ax.axvline(1, color="#444444", lw=1)
                ticks = [x for x in [.1, .15, .25, .4, .6, 1, 1.5] if ax.get_xlim()[0] <= x <= ax.get_xlim()[1]]
                ax.set_xticks(ticks, [str(x) for x in ticks]); ax.set_xlabel("来源报告块用时比 C/B（几何均值）")
                ax.xaxis.set_minor_locator(ticker.NullLocator())
    fig.legend(*axes[0, 0].get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(.53, .904), ncol=3, frameon=False, fontsize=10.3)
    fig.text(.02, .105, "发现总体：474事件／50图6楼，B8 +0.309、用时比0.424；评估固定：480事件／42图6楼，B8 −0.029、用时比0.375。", fontsize=10.5)
    fig.text(.02, .078, "源／Q近似后，评估为97事件／35图6楼，B8 −0.745，用时89事件可比、比0.380；图上不同控制的图片支持可不同，精确分母随图CSV保留。", fontsize=10)
    fig.text(.02, .051, "人数与替换规模在发现广框架和固定复查之间不同；不能把两阶段差值解释成纯人数效应。省时比不是质量等效或普遍结构互换的证明。", fontsize=9.6)
    fig.text(.02, .025, "来源任务报告时间与目标重做成本分开；缺失不补零。时间比为楼内图均log比再取exp，固定背景用时缺失不抹去已知替换块的净差。", fontsize=9.6)
    return save(fig, "03_T23_building_quality_time.png")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild-data", action="store_true",
                        help="Rebuild the retained plotting tables from complete statistical outputs. Without this flag, use only the supplied plotting CSVs.")
    args = parser.parse_args()
    HERE.mkdir(exist_ok=True)
    paths = [common8(args.rebuild_data), f11(args.rebuild_data), t23_buildings(args.rebuild_data)]
    write_json(HERE / "FIGURE_RECEIPT.json", dict(script_sha256=sha(Path(__file__)), font_sha256=sha(FONT),
        figures=[dict(file=p.name, bytes=p.stat().st_size, sha256=sha(p)) for p in paths],
        data_files=[dict(file=p.name, bytes=p.stat().st_size, sha256=sha(p)) for p in sorted(HERE.glob("*.csv.gz"))],
        data_source="rebuilt_from_full_statistics" if args.rebuild_data else "retained_plot_tables",
        no_new_fusion_or_fitting=True, quality_and_time_distinct=True, labels_or_rules_changed=False))
    print(json.dumps({"figures": len(paths), "png_bytes": sum(p.stat().st_size for p in paths)}))

if __name__ == "__main__":
    main()
