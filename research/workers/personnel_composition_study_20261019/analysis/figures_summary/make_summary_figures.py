#!/usr/bin/env python3
"""Two compact, data-derived scientific summaries of frozen composition research.

No model, type, comparison or hypothesis is fitted here. Figure 2 uses the exact
13 discovery-selected strata stored before validation in HIGHLIGHT_DEFINITIONS.
The validation panel is populated only when its completed summary is present.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os

import numpy as np
import pandas as pd


METHODS = [
    ("F_rule_Q_threshold_K3", "Q 阈值三类"),
    ("F_rule_Q_quantile_K5", "Q 五等分类"),
    ("F_rule_Q2xDetail2", "Q × 点数四类"),
    ("F_medoids_S_K4", "结构习惯四类"),
    ("R_geo9_source_signed_p2_K2", "来源残差关系二类"),
    ("R_geo9_spectral_p2_K3", "关系谱三类"),
    ("R_role_ward_K5", "几何角色五类"),
]
HARD = "R_role_ward_difficulty_K2"
HIGHLIGHT_NAMES = [
    "Q 阈值三类：低 → 高",
    "Q 阈值三类：中 → 高",
    "Q 阈值三类：高 → 低",
    "Q 阈值三类：低＋中 → 高",
    "Q × 点数：低 Q 少点 → 两种较高 Q 类",
    "来源残差关系二类：C01 → C02",
    "几何角色五类：C02 → C05",
    "几何角色五类：C01 → C05",
    "几何角色五类：C05 → C02",
    "困难图角色二类：C01 → C02",
    "困难图角色二类：C01 → C02",
    "困难图角色二类：混类 → C02",
    "困难图角色二类：C02 → 混类（反例）",
]
BLUE = "#226b9b"
ORANGE = "#c76532"
GREEN = "#268679"
PURPLE = "#7b5aa6"
GRAY = "#64717e"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def exact_one(df, **where):
    mask = np.ones(len(df), bool)
    for key, value in where.items():
        mask &= df[key].eq(value).to_numpy()
    rows = df.loc[mask]
    assert len(rows) == 1, (where, len(rows))
    return rows.iloc[0]


def clean_axis(ax):
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#afb7be")
    ax.tick_params(axis="both", length=0, labelsize=10)
    ax.grid(axis="x", color="#e5e9ed", lw=.7)
    ax.set_axisbelow(True)


def screen_figure(args, plt, Line2D, Patch):
    p = args.root / "analysis/forward/screen_final"
    if args.from_sources:
        files = [args.out / "01_plot_source.csv", args.out / "01_candidate_coverage_source.csv"]
        df, cov = [pd.read_csv(x) for x in files]
        hard = df[df.control_definition.notna()].copy()
        receipt = json.loads((args.out / "01_screen_manifest.json").read_text())
        files.append(args.out / "01_screen_manifest.json")
    else:
        files = [p / "screen_outcomes.csv.gz", p / "screen_coverage.csv", p / "hard_control_sensitivity.csv"]
        df, cov, hard = [pd.read_csv(x) for x in files]
        receipt = json.loads((p / "FINAL_SCREEN_RECEIPT.json").read_text())
    source_rows = []

    def row(method, outcome, model="linear", controlled=False,
            panel="native_support", domain="all"):
        r = exact_one(df, method_id=method, outcome=outcome, model=model,
                      controlled=controlled, panel=panel, domain=domain,
                      status="screened")
        source_rows.append(r.to_dict())
        return r

    def value(method, outcome, **kwargs):
        r = row(method, outcome, **kwargs)
        metric = ("additional_reduction_over_Q_origin"
                  if kwargs.get("controlled", False) else "mse_reduction_fraction")
        return 100 * r[metric]

    fig = plt.figure(figsize=(15.8, 11.7), facecolor="white")
    gs = fig.add_gridspec(2, 2, left=.18, right=.965, bottom=.30, top=.875,
                         wspace=.46, hspace=.51)
    ax_a, ax_b, ax_c, ax_d = [fig.add_subplot(gs[i, j]) for i, j in ((0, 0), (0, 1), (1, 0), (1, 1))]
    fig.suptitle("类别组成的实际融合效用：质量信号、结构信息与真实支持", x=.05,
                 y=.974, ha="left", fontsize=20, fontweight="bold")
    fig.text(.05, .928,
             "发现侧固定团队面板 · 类别仅由历史建筑拟合 · 同一图片的新成员团队预测，不是新独立图片验证",
             color=GRAY, fontsize=12)

    yy = np.arange(len(METHODS))[::-1]
    random = df[df.method_id.str.startswith("B_random_") & df.domain.eq("all") &
                df.panel.eq("native_support") & df.model.eq("linear") &
                ~df.controlled & df.outcome.eq("B8L2")]
    assert len(random) == 9
    source_rows.extend(random.to_dict("records"))
    rand_min, rand_max = 100 * random.mse_reduction_fraction.min(), 100 * random.mse_reduction_fraction.max()
    ax_a.axvspan(rand_min, rand_max, color="#e8ecef", zorder=0)
    origin = value("B_origin", "B8L2")
    ax_a.axvline(origin, color=GRAY, ls=(0, (3, 2)), lw=1.1)
    for y, (method, label) in zip(yy, METHODS):
        total = value(method, "B8L2")
        new = value(method, "B8L2", panel="shared_new35")
        extra = value(method, "B8L2", controlled=True)
        ax_a.plot([extra, total], [y, y], color="#cbd3da", lw=1.3)
        ax_a.scatter([total], [y+.11], color=BLUE, s=45, zorder=4)
        ax_a.scatter([new], [y-.13], edgecolor=BLUE, facecolor="white", s=45, zorder=4)
        ax_a.scatter([extra], [y], color=ORANGE, marker="s", s=35, zorder=5)
        ax_a.text(total+.22, y+.12, f"{total:.1f}", fontsize=9, color=BLUE, va="center")
    ax_a.set(yticks=yy, yticklabels=[label for _, label in METHODS], ylim=(-.65, 6.65),
             xlim=(-1.7, 12.5), xlabel="预测均方误差降低 (%)")
    ax_a.set_title("A  全域 B8L2：组成比例线性模型", loc="left", fontsize=13.5, pad=16)
    clean_axis(ax_a)
    ax_a.axvline(0, color="#a7afb6", lw=.9)

    for y, (method, label) in zip(yy, METHODS):
        total = value(method, "ref_edge_recall_9", model="condition_linear")
        extra = value(method, "ref_edge_recall_9", model="condition_linear", controlled=True)
        ax_b.plot([extra, total], [y, y], color="#cbd3da", lw=1.4)
        ax_b.scatter([total], [y], color=BLUE, s=45, zorder=4)
        ax_b.scatter([extra], [y], color=ORANGE, marker="s", s=35, zorder=5)
        ax_b.text(total+.35, y, f"{total:.1f}", fontsize=9, color=BLUE, va="center")
    ax_b.set(yticks=yy, yticklabels=[label for _, label in METHODS], ylim=(-.65, 6.65),
             xlim=(-1.7, 22.0), xlabel="参考边对应率的预测误差降低 (%)")
    ax_b.set_title("B  结构诊断：组成 × 难度／scope 条件", loc="left", fontsize=13.5, pad=16)
    clean_axis(ax_b)
    ax_b.axvline(0, color="#a7afb6", lw=.9)

    metrics = [("B8L2", "B8L2"), ("ref_node_recall_9", "参考节点对应率"),
               ("ref_edge_recall_9", "参考边对应率")]
    controls = [("q_beta_plus_source", "全域 Q＋来源", ORANGE),
                ("theta_hard_plus_source", "困难 Q＋来源", GREEN),
                ("q_beta_theta_hard_plus_source", "两种 Q＋来源", PURPLE)]
    for j, (metric, label) in enumerate(metrics):
        y = 2-j
        total = value(HARD, metric, domain="hard")
        ax_c.scatter([total], [y], color=BLUE, s=62, zorder=5)
        ax_c.text(total+.4, y, f"{total:.1f}", fontsize=10, color=BLUE, va="center")
        for offset, (definition, _, color) in zip([.22, 0, -.22], controls):
            r = exact_one(hard, domain="hard", panel="native_support", model="linear",
                          outcome=metric, control_definition=definition)
            source_rows.append(r.to_dict())
            assert int(r.tested_teams) == 876 and int(r.images) == 6 and int(r.buildings) == 3
            x = 100 * r.additional_reduction_over_Q_origin
            ax_c.scatter([x], [y+offset], marker="s", s=36, color=color, zorder=5)
            ax_c.text(x+.35, y+offset, f"{x:.2f}", fontsize=9, color=color, va="center")
    ax_c.set(yticks=[2, 1, 0], yticklabels=[l for _, l in metrics], ylim=(-.63, 2.58),
             xlim=(-1.2, 29), xlabel="预测均方误差降低 (%)")
    ax_c.set_title("C  困难图角色二类：相同 876 队／6 图／3 楼", loc="left", fontsize=13.2, pad=16)
    clean_axis(ax_c)
    ax_c.axvline(0, color="#a7afb6", lw=.9)

    global_cov = exact_one(cov, method_id="F_rule_Q_threshold_K3", domain="all")
    hard_cov = exact_one(cov, method_id=HARD, domain="hard")
    coverage_rows = []
    for pos, (label, workers, eligible, r) in enumerate([
        ("全域已知人员", 55, int(global_cov.eligible_teams), row(METHODS[0][0], "B8L2")),
        ("共同新批次", 35, int(global_cov.all_new_eligible_teams), row(METHODS[0][0], "B8L2", panel="shared_new35")),
        ("困难图角色", 37, int(hard_cov.eligible_teams), row(HARD, "B8L2", domain="hard")),
    ]):
        y = 2-pos
        tested = int(r.tested_teams)
        pct = 100 * tested / eligible
        ax_d.barh(y, 100, height=.31, color="#e4e9ed", zorder=1)
        ax_d.barh(y, pct, height=.31, color=BLUE, alpha=.85, zorder=2)
        ax_d.text(0, y+.27, f"{label}  {workers} 人", fontsize=10.4, color="#263a48")
        ax_d.text(102, y, f"{tested:,} / {eligible:,}\n{int(r.images)} 图 / {int(r.buildings)} 楼", fontsize=9.5,
                  va="center", ha="left", color="#263a48")
        coverage_rows.append(dict(panel=label, known_workers=workers, eligible_teams=eligible,
                                  tested_teams=tested, tested_images=int(r.images), tested_buildings=int(r.buildings)))
    ax_d.set(xlim=(0, 134), ylim=(-1.45, 2.68), yticks=[], xticks=[0, 25, 50, 75, 100],
             xlabel="可进行两折质量预测的比例 (%)")
    ax_d.set_title("D  支持与排除：团队数不等于独立样本数", loc="left", fontsize=13.2, pad=16)
    clean_axis(ax_d)
    ax_d.text(0, -.50,
              "245 个方法×域（含 10 基线）；229 有普通图机会，16 无此机会。\n"
              "全域 110／12,250 队缺主分；hard 93／1,000 队缺主分。\n"
              "其余排除来自池×人数单元的训练／测试支持不足。",
              fontsize=9.2, color=GRAY, va="top", linespacing=1.45)

    handles = [Line2D([], [], marker="o", ls="", color=BLUE, markersize=6),
               Line2D([], [], marker="o", ls="", markeredgecolor=BLUE, markerfacecolor="white", markersize=6),
               Line2D([], [], marker="s", ls="", color=ORANGE, markersize=6),
               Line2D([], [], marker="s", ls="", color=GREEN, markersize=6),
               Line2D([], [], marker="s", ls="", color=PURPLE, markersize=6),
               Patch(facecolor="#e8ecef"),
               Line2D([], [], color=GRAY, ls="--", lw=1.2)]
    fig.legend(handles, ["组成整体效用", "限共同新批次的整体效用（A）", "全域 Q＋来源之外的增量", 
                         "困难 Q＋来源之外的增量（C）", "两种 Q＋来源之外的增量（C）",
                         f"9 个随机分区范围（A：{rand_min:.2f}～{rand_max:.2f}%）", f"仅来源分组（A：{origin:.2f}%）"],
               loc="lower left", bbox_to_anchor=(.045, .171), ncol=3, frameon=False,
               fontsize=10.1, columnspacing=1.65, labelspacing=.65, handletextpad=.5)
    fig.text(.05, .082,
             "蓝点 = 1 − MSE(组成模型) / MSE(池×人数基线)；橙／绿／紫点 = 1 − MSE(控制＋组成) / MSE(控制)。分母不同，不能相减。\n"
             "基线与控制仅在训练折拟合；B 的控制保留相同难度／scope 条件交互。Q 均来自历史建筑，没有读取目标图质量。\n"
             "B 模型的原 scene 字段是 OOS／doorway 标记，不是功能房型；节点／边对应是几何诊断，并非必要结构语义真值。\n"
             "难度分层包含用户采纳的非盲参考几何复核，仅支持该条件下的解释／规则，不能视为新图自动采集前的难度识别与选人验证。\n"
             "困难图只支持较小子集；全域射线轮廓的线性增益接近零。全域历史 Q 规则不依赖目标图难度；以上均为发现侧筛查。",
             fontsize=10.1, color=GRAY, va="center", linespacing=1.55)
    output = args.out / "01_candidate_utility_coverage.png"
    fig.savefig(output, dpi=args.dpi, facecolor="white", pil_kwargs={"compress_level": 9})
    plt.close(fig)
    pd.DataFrame(source_rows).drop_duplicates().to_csv(args.out / "01_plot_source.csv", index=False)
    pd.DataFrame(coverage_rows).to_csv(args.out / "01_coverage_source.csv", index=False)
    pd.DataFrame([global_cov.to_dict(), hard_cov.to_dict()]).to_csv(args.out / "01_candidate_coverage_source.csv", index=False)
    (args.out / "01_screen_manifest.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n")
    return dict(figure=output.name, bytes=output.stat().st_size,
                inputs={str(x.relative_to(args.root)): sha(x) for x in files},
                candidates=receipt["candidate_method_domain_instances"], validation_used=False)


def compact_counts(s):
    return "+".join(f"{int(v)}{k}" for k, v in (x.split(":") for x in s.split("|")) if int(v))


def block_figure(args, plt, Line2D):
    comp = args.root / "analysis/composition"
    definition_path = comp / "block_discovery_specific/HIGHLIGHT_DEFINITIONS.json"
    if args.from_sources:
        source_summary_path = args.out / "02_plot_source.csv"
        source_building_path = args.out / "02_building_points.csv"
        source_summary = pd.read_csv(source_summary_path)
        source_building = pd.read_csv(source_building_path)
        defs = source_summary[source_summary.phase.eq("discovery")][["highlight_id", "method_id", "domain", "outgoing_counts", "incoming_counts", "k", "m"]].to_dict("records")
        source_proof = json.loads((args.out / "02_comparison_manifest.json").read_text())
        assert defs == source_proof["definitions"]
        files = [source_summary_path, source_building_path, args.out / "02_comparison_manifest.json"]
    else:
        defs = json.loads(definition_path.read_text())["definitions"]
        files = [definition_path]
    assert len(defs) == len(HIGHLIGHT_NAMES) == 13
    phases, src, building_src = {}, [], []
    for phase in ("discovery", "validation"):
        directory = comp / ("block_" + phase + "_specific")
        sf, bf = directory / "highlight_summary.csv", directory / "directed_exact_by_building.csv.gz"
        if args.from_sources:
            if not source_summary.phase.eq(phase).any():
                assert phase == "validation"
                continue
            summary = source_summary[source_summary.phase.eq(phase)].copy()
            by_building = source_building[source_building.phase.eq(phase)].drop(columns="highlight_id").copy()
            if phase == "validation":
                assert source_proof["validation_used"]
        elif not sf.exists():
            assert phase == "validation", str(sf)
            continue
        else:
            if phase == "validation":
                assert (comp / "runs_final/RUN_FINAL_REQUESTS.json").exists(), "Validation run receipt required"
            summary, by_building = pd.read_csv(sf), pd.read_csv(bf)
            files.extend([sf, bf])
        summary = summary[summary.subset.eq("all_events")]
        by_building = by_building[by_building.subset.eq("all_events")]
        phase_rows = []
        for definition in defs:
            key = {c: definition[c] for c in ["method_id", "domain", "outgoing_counts", "incoming_counts", "k", "m"]}
            s = exact_one(summary, highlight_id=definition["highlight_id"])
            for c, val in key.items():
                assert s[c] == val, (phase, c)
            mask = np.ones(len(by_building), bool)
            for c, val in key.items():
                mask &= by_building[c].eq(val).to_numpy()
            b = by_building.loc[mask].copy()
            b["highlight_id"] = definition["highlight_id"]
            assert np.isclose(b.net_B8L2_change.mean(), s.net_B8L2_change_equal_building_mean, atol=1e-10)
            phase_rows.append((s, b))
            src.append(s.to_dict())
            building_src.extend(b.to_dict("records"))
        phases[phase] = phase_rows

    fig = plt.figure(figsize=(18.8, 12.8), facecolor="white")
    gs = fig.add_gridspec(1, 4, width_ratios=[3.35, 3.6, 3.6, 2.6], left=.028,
                         right=.978, top=.844, bottom=.172, wspace=.08)
    label_ax, d_ax, v_ax, n_ax = [fig.add_subplot(gs[0, j]) for j in range(4)]
    fig.suptitle("固定的 13 组类别块替换：平均方向、低尾与建筑间差异", x=.033,
                 y=.970, ha="left", fontsize=20.5, fontweight="bold")
    fig.text(.033, .927,
             "每个事件中同图、同人数、同公共成员；每行固定换人规模 m 和类别块，并在多个背景上复查",
             fontsize=12.2, color=GRAY)
    points = [r[1].net_B8L2_change.dropna().to_numpy() for phase in phases.values() for r in phase]
    points += [np.array([r[0].net_B8L2_change_event_p10]) for phase in phases.values() for r in phase]
    finite = np.concatenate(points)
    lo, hi = min(-25, 5*np.floor(np.nanmin(finite)/5)-5), max(45, 5*np.ceil(np.nanmax(finite)/5)+5)
    for ax in [label_ax, d_ax, v_ax, n_ax]:
        ax.set_ylim(12.58, -.62)
        for y in range(13):
            ax.axhspan(y-.46, y+.46, color="#fff4e4" if y >= 9 else ("#f4f7f9" if y % 2 == 0 else "white"), zorder=0)
        for border in [3.5, 4.5, 5.5, 8.5]:
            ax.axhline(border, color="#d9e0e5", lw=.75)
    for ax in [label_ax, n_ax]:
        ax.set_xlim(0, 1)
        ax.axis("off")
    label_ax.set_title("具体类别块（C 是类别编号）", loc="left", fontsize=12.4, pad=19)
    n_ax.set_title("ΔQ 均值 | 有限事件／图／楼", loc="left", fontsize=12.1, pad=19)
    for y, (definition, name) in enumerate(zip(defs, HIGHLIGHT_NAMES)):
        label_ax.text(.015, y-.13, name, fontsize=10.5, va="center", color="#223645")
        label_ax.text(.015, y+.18,
                      f"n={definition['k']}, m={definition['m']}  |  {compact_counts(definition['outgoing_counts'])} → {compact_counts(definition['incoming_counts'])}",
                      fontsize=9.2, color=GRAY, va="center")
    for phase, ax, color, title in [("discovery", d_ax, BLUE, "发现：已参与模式筛选的建筑"),
                                  ("validation", v_ax, ORANGE, "复查：冻结后的内部留出建筑")]:
        ax.set(xlim=(lo, hi), yticks=[], xlabel="C − B 的 B8L2 变化（分）")
        clean_axis(ax)
        ax.axvline(0, color="#8797a2", lw=1.15)
        ax.set_title(title, loc="left", fontsize=12.6, pad=19)
        if phase not in phases:
            ax.text(.5, .5, "等待已冻结请求实算完成\n比较规则与标签保持原样", transform=ax.transAxes,
                    ha="center", va="center", fontsize=13, color=GRAY, linespacing=1.8)
            continue
        for y, (s, b) in enumerate(phases[phase]):
            finite_b = b[b.net_B8L2_change.notna()].sort_values("building")
            for _, r in finite_b.iterrows():
                jitter = (int(hashlib.sha256(r.building.encode()).hexdigest()[:6], 16) % 101 - 50) / 400
                ax.scatter([r.net_B8L2_change], [y+jitter], s=21, color=color, alpha=.46,
                           edgecolors="white", linewidths=.3, zorder=3)
            mean, tail = s.net_B8L2_change_equal_building_mean, s.net_B8L2_change_event_p10
            ax.scatter([tail], [y+.20], marker="<", s=47, color=color, alpha=.85, zorder=4)
            ax.scatter([mean], [y-.06], marker="D", s=54, color=color, edgecolor="white", linewidth=.7, zorder=6)
            finite_n = int(s.net_B8L2_change_n)
            imgs = int(s.net_B8L2_change_finite_images)
            buildings = int(s.net_B8L2_change_finite_buildings)
            missing = int(s.events)-finite_n
            offset = -.16 if phase == "discovery" else .19
            prefix = "发现" if phase == "discovery" else "复查"
            n_ax.text(.014, y+offset, f"{prefix} {mean:+.2f} | {finite_n}/{imgs}/{buildings}" + (f"  缺{missing}" if missing else ""),
                      fontsize=9.6, color=color, va="center")
    fig.legend([Line2D([], [], ls="", marker="D", color=GRAY, markersize=7),
                Line2D([], [], ls="", marker="o", color=GRAY, alpha=.55, markersize=5),
                Line2D([], [], ls="", marker="<", color=GRAY, markersize=7)],
               ["图片内平均，再建筑等权的均值", "各建筑均值（同楼各图等权）", "配对事件 ΔQ 的第 10 百分位（不是置信区间）"],
               loc="lower left", bbox_to_anchor=(.035, .105), ncol=3, frameon=False,
               fontsize=10.7, columnspacing=2.0)
    fig.text(.033, .063,
             "A = 公共背景＋原类别块；B = 保持原类别人数、换入其他人员；C = 同规模换入另一类别人数块。横轴比较 C−B 的净质量方向。\n"
             "类别在历史建筑中冻结；13 行从发现搜索中选作正例、下降例、多类替换与反例。复查为现有 v2 的内部建筑留出，不是全新外部盲测。\n"
             "右表仅列 B、C 都有主分的事件／图片／建筑；“缺”是尝试事件中 ΔQ 缺失的数量，不补零。建筑点的离散与负低尾保留。橙底仅适用于困难图。",
             fontsize=10.5, color=GRAY, va="center", linespacing=1.55)
    output = args.out / "02_specific_replacements_discovery_validation.png"
    fig.savefig(output, dpi=args.dpi, facecolor="white", pil_kwargs={"compress_level": 9})
    plt.close(fig)
    pd.DataFrame(src).to_csv(args.out / "02_plot_source.csv", index=False)
    pd.DataFrame(building_src).to_csv(args.out / "02_building_points.csv", index=False)
    pure_defs = [{c: d[c] for c in ["highlight_id", "method_id", "domain", "outgoing_counts", "incoming_counts", "k", "m"]} for d in defs]
    (args.out / "02_comparison_manifest.json").write_text(json.dumps(dict(definitions=pure_defs, validation_used="validation" in phases,
                                                                       selection="Fixed discovery definitions; no validation selection"), ensure_ascii=False, indent=2)+"\n")
    return dict(figure=output.name, bytes=output.stat().st_size,
                validation_used="validation" in phases,
                comparison_count=len(defs), selection="same 13 discovery strata; no validation selection",
                inputs={str(x.relative_to(args.root)): sha(x) for x in files})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--font", type=Path)
    ap.add_argument("--dpi", type=int, default=160)
    ap.add_argument("--from-sources", action="store_true", help="Redraw only from the small CSV/JSON tables distributed beside the figures.")
    args = ap.parse_args()
    args.root = args.root.resolve()
    args.out = (args.out or args.root / "analysis/figures_summary").resolve()
    args.font = args.font or args.root / "analysis/fonts/NotoSansSC-Regular.ttf"
    args.out.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(args.out / "mplconfig"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    font_manager.fontManager.addfont(str(args.font))
    family = font_manager.FontProperties(fname=args.font).get_name()
    plt.rcParams.update({"font.family": family, "font.size": 11, "axes.unicode_minus": False,
                         "axes.labelcolor": "#334a59", "text.color": "#263a48",
                         "xtick.color": "#50616e", "ytick.color": "#334a59"})
    results = [screen_figure(args, plt, Line2D, Patch), block_figure(args, plt, Line2D)]
    metadata = dict(code_sha256=sha(__file__), font=args.font.name, font_sha256=sha(args.font), from_compact_sources=args.from_sources,
                    dpi=args.dpi, figures=results, inference="descriptive figures only; no new fit or hypothesis",
                    reproduction="python analysis/figures_summary/make_summary_figures.py --root /path/to/project --from-sources")
    (args.out / "FIGURE_RECEIPT.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+"\n")
    if not args.from_sources:
        (args.out / "FIGURE_SOURCE_RECEIPT.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
