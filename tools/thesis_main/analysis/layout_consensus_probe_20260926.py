"""合成布局共识探针：解析 BEV tiles 与 ERP 可见墙带，不涉及真人裁决。

模式标签来自合成生成器，只作 oracle 分组诊断；GT 仅进入评价器。
复用的 EM / greedy 是项目适配，不是 Lee 完整复现。不修复非法 polygon。
"""
from collections import Counter, defaultdict
from itertools import combinations
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import label
from shapely.geometry import GeometryCollection, LineString, Point, Polygon, box
from shapely.ops import polygonize, unary_union

from tools.thesis_main.analysis.consensus_region_20260923 import aggregate

SEED = 20260926
BEV_METHODS = ("mv50", "mv_strict", "medoid")
ERP_METHODS = BEV_METHODS + ("em_correct_probability", "greedy_empirical")
NAMES = {"agreement": "一致正确", "independent_noise": "独立边界扰动",
         "common_bias": "共同偏差", "two_reasonable_scopes": "两种合理范围",
         "minority_detail": "多数漏细节、少数保留"}


def _valid(p):
    if not isinstance(p, Polygon) or not p.is_valid or p.is_empty or p.area <= 0:
        raise ValueError("invalid_polygon")


def polygon_iou(a, b):
    union = a.union(b).area
    return float(a.intersection(b).area / union) if union else 1.0


def supported_tiles(polygons):
    if not polygons:
        raise ValueError("empty_workers")
    for p in polygons:
        _valid(p)
    tiles = list(polygonize(unary_union([p.boundary for p in polygons])))
    return [(t, sum(p.covers(t.representative_point()) for p in polygons) / len(polygons))
            for t in tiles]


def bev_aggregate(polygons, method):
    """一人一票，精确几何面积；不接收 GT 或模式标签。"""
    if not polygons:
        raise ValueError("empty_workers")
    for p in polygons:
        _valid(p)
    if method == "medoid":
        scores = [sum(polygon_iou(a, b) for b in polygons) for a in polygons]
        return polygons[int(np.argmax(scores))]
    if method not in ("mv50", "mv_strict"):
        raise ValueError("unknown_bev_method")
    selected = [t for t, s in supported_tiles(polygons)
                if s >= .5 and (method == "mv50" or s > .5)]
    return unary_union(selected) if selected else GeometryCollection()


def visible_wall_mask(polygon, width=128, height=64):
    """相机在(0,0)、离地1、层高2.5；逐方位取首次墙面交点。

    这是可见墙带投影，隐藏地面范围不能从这个 mask 唯一恢复。
    """
    _valid(polygon)
    camera = Point(0, 0)
    if not polygon.contains(camera):
        raise ValueError("camera_not_inside")
    if min(width, height) < 2:
        raise ValueError("invalid_raster")
    radius = 4 * max(abs(x) for x in polygon.bounds) + 1
    theta = ((np.arange(width) + .5) / width - .5) * 2 * np.pi
    distances = []
    for t in theta:
        hit = polygon.boundary.intersection(
            LineString([(0, 0), (radius * np.sin(t), radius * np.cos(t))]))
        if hit.is_empty:
            raise ValueError("ray_no_wall")
        distances.append(camera.distance(hit))
    d = np.asarray(distances)
    if np.any(d <= 0) or not np.isfinite(d).all():
        raise ValueError("invalid_visible_depth")
    top = (-np.arctan2(1.5, d) / np.pi + .5) * height - .5
    bottom = (np.arctan2(1, d) / np.pi + .5) * height - .5
    yy = np.arange(height)[:, None]
    return (yy >= top) & (yy <= bottom)


def _periodic_components(mask):
    labels, count = label(mask)
    parent = list(range(count + 1))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in zip(labels[:, 0], labels[:, -1]):
        if a and b:
            parent[root(int(a))] = root(int(b))
    roots = {root(i) for i in range(1, count + 1)}
    touches = {root(int(i)) for i in np.r_[labels[0], labels[-1]] if i}
    return roots, touches


def periodic_topology(mask):
    """ERP 采用水平周期、四邻接；孔洞为不接触上下边界的背景分量。"""
    foreground, _ = _periodic_components(mask)
    background, exterior = _periodic_components(~mask)
    return dict(components=len(foreground), holes=len(background - exterior),
                empty=not bool(mask.any()))


def _polygon_topology(p):
    parts = [p] if p.geom_type == "Polygon" else list(p.geoms)
    polygons = [g for g in parts if g.geom_type == "Polygon"]
    return dict(components=len(polygons), holes=sum(len(g.interiors) for g in polygons),
                empty=bool(p.is_empty))


def _mask_iou(a, b):
    union = int((a | b).sum())
    return float((a & b).sum() / union) if union else 1.0


def make_scenarios():
    rng = np.random.default_rng(SEED)
    a, b = box(-3, -2, 3, 2), box(-2, -3, 2, 3)
    detail = a.union(box(1, 2, 2, 3))
    noisy = [box(*([-3, -2, 3, 2] + rng.normal(0, .18, 4))) for _ in range(12)]
    cases = {
        "agreement": ([a] * 12, ["one"] * 12, {"target": a}),
        "independent_noise": (noisy, ["one"] * 12, {"target": a}),
        "common_bias": ([box(-2.5, -2, 2.5, 2)] * 12, ["one"] * 12, {"target": a}),
        "two_reasonable_scopes": ([a] * 8 + [b] * 4, ["A"] * 8 + ["B"] * 4,
                                   {"scope_A": a, "scope_B": b}),
        "minority_detail": ([a] * 9 + [detail] * 3, ["omission"] * 9 + ["detail"] * 3,
                             {"target_with_detail": detail}),
    }
    return {name: dict(name=name, polygons=p, modes=m, references=r,
                       primary_reference=next(iter(r))) for name, (p, m, r) in cases.items()}


def evaluate_case(case, permutations, width=128, height=64, erp_methods=ERP_METHODS):
    """前缀相同、GT 隔离；已知模式只选择人员子集，不进入聚合器。"""
    polygons, modes = case["polygons"], case["modes"]
    masks = [visible_wall_mask(p, width, height) for p in polygons]
    refs = {"bev": case["references"], "erp":
            {key: visible_wall_mask(p, width, height) for key, p in case["references"].items()}}
    rows, outputs, cache = [], defaultdict(list), {}
    for repeat, permutation in enumerate(permutations):
        if sorted(permutation) != list(range(len(polygons))):
            raise ValueError("permutation_not_one_worker_one_vote")
        previous = {}
        for k in range(1, len(permutation) + 1):
            members = sorted(permutation[:k])
            counts = Counter(modes[i] for i in permutation[:k])
            groups = {mode: [i for i in members if modes[i] == mode] for mode in sorted(counts)}
            largest = max(counts, key=counts.get)  # 平票取当前前缀最先出现的模式，不用 GT。
            routes = [("all", None, members), ("largest_mode_oracle", None, groups[largest])]
            routes += [("each_mode_oracle", mode, group) for mode, group in groups.items()]
            for route, mode, selected in routes:
                for domain, methods in (("bev", BEV_METHODS), ("erp", erp_methods)):
                    for method in methods:
                        key = (domain, method, tuple(selected))
                        if key not in cache:
                            if domain == "bev":
                                output = bev_aggregate([polygons[i] for i in selected], method)
                                status, topology = "ok", _polygon_topology(output)
                            else:
                                result = aggregate([masks[i] for i in selected], method)
                                output, status = result["mask"], result["status"]
                                topology = periodic_topology(output)
                            compare = polygon_iou if domain == "bev" else _mask_iou
                            quality = {name: compare(output, ref) for name, ref in refs[domain].items()}
                            cache[key] = output, status, topology, quality
                        output, status, topology, quality = cache[key]
                        track = (domain, method, route, mode)
                        compare = polygon_iou if domain == "bev" else _mask_iou
                        change = 1 - compare(output, previous[track]) if track in previous else None
                        previous[track] = output
                        row = dict(scenario=case["name"], permutation=repeat, k=k, domain=domain,
                                   method=method, route=route, mode=mode, used_count=len(selected),
                                   selected_workers=selected, mode_counts=dict(counts),
                                   mode_support={m: n / k for m, n in counts.items()},
                                   selected_largest_mode=largest if route == "largest_mode_oracle" else None,
                                   q_primary=quality[case["primary_reference"]], q_references=quality,
                                   change=change, status=status, **topology)
                        rows.append(row)
                        outputs[(*track, k)].append(output)
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["domain"], row["method"], row["route"], row["mode"], row["k"])].append(row)
    summary = []
    for key, group in grouped.items():
        domain, method, route, mode, k = key
        compare = polygon_iou if domain == "bev" else _mask_iou
        pairs = [1 - compare(a, b) for a, b in combinations(outputs[key], 2)]
        changes = [r["change"] for r in group if r["change"] is not None]
        summary.append(dict(scenario=case["name"], domain=domain, method=method, route=route,
                            mode=mode, k=k, n_permutations=len(group),
                            q_mean=float(np.mean([r["q_primary"] for r in group])),
                            q_min=min(r["q_primary"] for r in group), q_max=max(r["q_primary"] for r in group),
                            change_mean=float(np.mean(changes)) if changes else None,
                            same_k_difference_mean=float(np.mean(pairs)) if pairs else None,
                            empty_count=sum(r["empty"] for r in group),
                            fragmented_count=sum(r["components"] > 1 for r in group),
                            with_holes_count=sum(r["holes"] > 0 for r in group),
                            statuses=dict(Counter(r["status"] for r in group))))
    return dict(rows=rows, summary=summary)


def _draw_polygon(ax, p, **kwargs):
    for polygon in ([p] if p.geom_type == "Polygon" else list(p.geoms)):
        if polygon.geom_type == "Polygon":
            xy = np.asarray(polygon.exterior.coords)
            ax.plot(xy[:, 0], xy[:, 1], **kwargs)


def _figures(out, cases, summary):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as Patch
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 5, figsize=(17, 7), constrained_layout=True)
    for column, (name, case) in enumerate(cases.items()):
        colors = {mode: plt.cm.tab10(i) for i, mode in enumerate(sorted(set(case["modes"])))}
        for p, mode in zip(case["polygons"], case["modes"]):
            _draw_polygon(axes[0, column], p, color=colors[mode], alpha=.55, linewidth=1.3)
        for p in case["references"].values():
            _draw_polygon(axes[0, column], p, color="black", linestyle="--", linewidth=2)
        for tile, support in supported_tiles(case["polygons"]):
            axes[1, column].add_patch(Patch(np.asarray(tile.exterior.coords), facecolor=plt.cm.Blues(support),
                                           edgecolor="white", linewidth=.6))
            bounds = tile.bounds
            if (min(bounds[2] - bounds[0], bounds[3] - bounds[1]) > .22 and
                    (name != "independent_noise" or support == 1)):
                c = tile.representative_point()
                text_y = c.y + .4 if abs(c.x) + abs(c.y) < .3 else c.y
                axes[1, column].text(c.x, text_y, f"{round(support * 12)}/12", ha="center", va="center",
                                    fontsize=8, color="white" if support > .65 else "black")
        axes[0, column].set_title(NAMES[name])
        for ax in axes[:, column]:
            ax.scatter([0], [0], marker="+", c="crimson", s=36, zorder=8)
            ax.set(xlim=(-3.8, 3.8), ylim=(-3.8, 3.8), aspect="equal", xlabel="地面 x（合成单位）")
            ax.grid(alpha=.15)
    axes[0, 0].set_ylabel("输入范围；黑虚线为评价参考")
    axes[1, 0].set_ylabel("精确 tile 人数支持（12 人）")
    fig.suptitle("合成输入与一人一票支持；模式标签仅作 oracle 诊断", fontsize=15)
    fig.savefig(out / "synthetic_regions_and_support.png", dpi=145)
    plt.close(fig)
    titles = [("q_mean", "对指定参考的 IoU ↑"), ("change_mean", "相邻人数输出变化 ↓"),
              ("same_k_difference_mean", "同人数、不同成员组合的差异 ↓")]
    for domain, methods in (("bev", BEV_METHODS), ("erp", ERP_METHODS)):
        fig, axes = plt.subplots(5, 3, figsize=(15, 16), constrained_layout=True)
        for row, name in enumerate(cases):
            for column, (field, title) in enumerate(titles):
                ax = axes[row, column]
                for method in methods:
                    values = sorted([s for s in summary if s["scenario"] == name and
                                     s["domain"] == domain and s["route"] == "all" and
                                     s["method"] == method], key=lambda s: s["k"])
                    ax.plot([s["k"] for s in values], [s[field] for s in values], marker=".", label=method)
                ax.set_title(f"{NAMES[name]} · {title}", fontsize=10)
                ax.set(xlabel="已收集合成人数 k", xlim=(1, 12), ylim=(-.025, 1.025))
                ax.grid(alpha=.2)
                if row == 0 and column == 0:
                    ax.legend(fontsize=7)
        fig.suptitle(f"{'精确 BEV tiles' if domain == 'bev' else 'ERP 可见墙带 128×64'}：全体聚合，固定前缀\n"
                     "两合理范围的 Q 仅相对 scope_A；稳定、接近单一参考、保留模式是不同问题", fontsize=13)
        fig.savefig(out / f"{domain}_three_curves.png", dpi=130)
        plt.close(fig)
    fig, axes = plt.subplots(2, 3, figsize=(15, 7), constrained_layout=True)
    for row, name in enumerate(("two_reasonable_scopes", "minority_detail")):
        for column, (field, title) in enumerate(titles):
            ax = axes[row, column]
            keys = [("all", None), ("largest_mode_oracle", None)]
            keys += [("each_mode_oracle", mode) for mode in sorted(set(cases[name]["modes"]))]
            for route, mode in keys:
                values = sorted([s for s in summary if s["scenario"] == name and s["domain"] == "bev"
                                 and s["method"] == "mv50" and s["route"] == route and s["mode"] == mode],
                                key=lambda s: s["k"])
                ax.plot([s["k"] for s in values], [s[field] for s in values], marker=".",
                        label=route + (f":{mode}" if mode else ""))
            ax.set_title(f"{NAMES[name]} · {title}", fontsize=10)
            ax.set(xlabel="已收集合成人数 k（不是簇内人数）", ylim=(-.025, 1.025))
            ax.grid(alpha=.2)
            if column == 0:
                ax.legend(fontsize=7)
    fig.suptitle("BEV MV≥50% 的三路线对照：已知模式 oracle 不能冒充实用聚类", fontsize=14)
    fig.savefig(out / "oracle_mode_routes.png", dpi=140)
    plt.close(fig)


def run(out: Path):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    cases = make_scenarios()
    rng = np.random.default_rng(SEED)
    permutations = [rng.permutation(12).tolist() for _ in range(8)]
    rows, summary = [], []
    for case in cases.values():
        evaluated = evaluate_case(case, permutations)
        rows.extend(evaluated["rows"])
        summary.extend(evaluated["summary"])
    payload = dict(schema_version="synthetic_layout_consensus_probe_v1", seed=SEED,
                   synthetic_only=True, oracle_modes=True, workers=12, permutations=permutations,
                   erp_raster=[128, 64], camera_xy=[0, 0], camera_height=1, room_height=2.5,
                   construction="BEV: Shapely noded boundaries -> polygonize tiles; ERP: nearest ray hit",
                   methods={"bev": list(BEV_METHODS), "erp": list(ERP_METHODS)},
                   tie_policy="MV >=50 / >50; medoid smallest synthetic worker ID; largest mode first seen in current prefix",
                   notes=["模式标签为合成真值，仅作 oracle 分组对照；聚合接口不接收 GT。",
                          "ERP EM/greedy 复用项目适配，非 Lee 完整复现。",
                          "全体、最大模式和各模式共用前缀；横轴为收集人数，used_count 另记。",
                          "相邻变化是 1-IoU；同k差异是8个随机前缀输出的两两平均 1-IoU。",
                          "各模式在该前缀未出现时不输出；曲线统计同时保留 n_permutations。",
                          "ERP拓扑使用水平周期四邻接，BEV孔洞用精确polygon内部环。",
                          "输出为空保留；两个空输出的稳定性IoU定义为1，对非空参考质量为0。",
                          "这些图是合成算法行为例证，不估计真人能力、真实收敛人数或普遍改善。"],
                   scenarios={name: dict(modes=case["modes"],
                       polygons=[list(p.exterior.coords) for p in case["polygons"]],
                       references={key: list(p.exterior.coords) for key, p in case["references"].items()},
                       primary_reference=case["primary_reference"]) for name, case in cases.items()},
                   same_point_count_counterexample=dict(scenario="two_reasonable_scopes", corners=[4, 4],
                       areas=[24, 24], iou=.5, nested=False), rows=rows, summary=summary,
                   figures=["synthetic_regions_and_support.png", "bev_three_curves.png",
                            "erp_three_curves.png", "oracle_mode_routes.png"])
    (out / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    _figures(out, cases, summary)
    return payload


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("analysis_results/layout_algorithm_exploration_20260926/consensus"))
    result = run(parser.parse_args().out)
    print(json.dumps(dict(rows=len(result["rows"]), summary=len(result["summary"]),
                          figures=result["figures"]), ensure_ascii=False))
