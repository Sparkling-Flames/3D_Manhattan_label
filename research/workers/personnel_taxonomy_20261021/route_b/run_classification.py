"""Interpretable personnel marking taxonomy, independent Manual / Semi fits.

This uses existing frozen expression descriptors and changes no input geometry,
reference, quality score or voting eligibility. Training excludes each evaluated
building. All-data labels are descriptive final labels, never validation labels.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EXPRESSION = "research/workers/personnel_marking_patterns_20261020/record_expression.csv"
KEY = ["condition", "layer", "image_id", "reference_id"]
FEATURES = ["turn_n_peer_delta", "short_turn_edges_peer_delta"]
DESCRIPTORS = ["pair_n", "turn_n", "short_turn_edges", "near_straight_nodes_5deg", "log_area", "log_height"]
MIN_IMAGES = 12
MIN_BUILDINGS = 4
NAMES = {
    "M0": "常规或简化表达", "M1": "较多短转折表达",
    "M00": "较少转折", "M01": "常规转折",
    "M10": "条件性较多转折", "M11": "较强短转折表达",
    "S0": "常规或较少短转折终稿", "S1": "较多短转折终稿",
    "S00": "较少短转折终稿", "S01": "常规短转折终稿", "S10": "较多短转折终稿",
    "unassigned": "证据不足",
}


def json_write(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf8")


def load_expression(root):
    x = pd.read_csv(root / EXPRESSION)
    x["turn_n"] = x.pair_n - x.near_straight_nodes_5deg
    used = x.personal_comparison & x.peer_n.ge(3)
    for f in ["turn_n"]:
        med = x.loc[used].groupby(KEY, dropna=False)[f].transform("median")
        x[f + "_peer_delta"] = x[f] - med
    x["classification_observation"] = used & x.layer.eq("ordinary")
    return x


def worker_features(d):
    cols = [f + "_peer_delta" for f in DESCRIPTORS]
    b = d.groupby(["worker_id", "building_id"], dropna=False)[cols].mean()
    f = b.groupby("worker_id").mean()
    support = d.groupby("worker_id").agg(
        n_records=("object_id", "size"), n_images=("image_id", "nunique"),
        n_buildings=("building_id", "nunique"), n_quality_usable=("quality_usable", "sum"),
        n_independent_vote_eligible=("independent_vote_eligible", "sum"),
        origin=("origin", lambda s: "|".join(sorted(s.unique()))),
    )
    return f.join(support)


def ordered_ward(a, n_clusters=2):
    lab = AgglomerativeClustering(n_clusters=n_clusters, linkage="ward").fit_predict(a)
    order = sorted(np.unique(lab), key=lambda k: (a[lab == k, 0].mean(), a[lab == k, 1].mean()))
    mapping = {old: rank for rank, old in enumerate(order)}
    return np.asarray([mapping[i] for i in lab])


def fit_taxonomy(d, condition):
    f = worker_features(d)
    eligible = f.n_images.ge(MIN_IMAGES) & f.n_buildings.ge(MIN_BUILDINGS)
    a = f.loc[eligible, FEATURES]
    scaler = StandardScaler().fit(a)
    scaled = scaler.transform(a)
    coarse = ordered_ward(scaled)
    fine = np.array(["" for _ in coarse], dtype=object)
    prefix = "M" if condition == "manual" else "S"
    for group in [0, 1]:
        idx = np.flatnonzero(coarse == group)
        if condition == "semi" and group == 1:
            fine[idx] = "S10"
        else:
            sub = ordered_ward(scaled[idx])
            fine[idx] = [f"{prefix}{group}{i}" for i in sub]
    labels = f.copy()
    labels["coarse_class"] = "unassigned"
    labels["fine_class"] = "unassigned"
    labels.loc[eligible, "coarse_class"] = [f"{prefix}{i}" for i in coarse]
    labels.loc[eligible, "fine_class"] = fine
    labels["label_status"] = np.where(eligible, "assigned", "insufficient_support")
    labels["missing_reason"] = ""
    labels.loc[~eligible, "missing_reason"] = "fewer_than_12_comparable_images_or_4_buildings"
    labels["condition"] = condition
    labels["training_layer"] = "ordinary"
    labels["coarse_name_zh"] = labels.coarse_class.map(NAMES)
    labels["fine_name_zh"] = labels.fine_class.map(NAMES)
    centers = []
    for level in ["coarse_class", "fine_class"]:
        for class_id, g in labels[eligible].groupby(level):
            centers.append({"level": level, "class_id": class_id, "n": len(g),
                            "features": g[FEATURES].mean().to_dict(),
                            "members": list(g.index)})
    model = dict(condition=condition, features=FEATURES, standardizer_mean=scaler.mean_.tolist(),
                 standardizer_scale=scaler.scale_.tolist(), centers=centers,
                 n_fit=len(a), coarse_silhouette=float(silhouette_score(scaled, coarse)),
                 fine_silhouette=float(silhouette_score(scaled, fine)))
    return labels.reset_index(), model


def complete_inventory(labels, x, condition):
    workers = sorted(x.worker_id.unique())
    z = labels.set_index("worker_id").reindex(workers).rename_axis("worker_id").reset_index()
    unavailable = z.condition.isna()
    z.loc[unavailable, "condition"] = condition
    z.loc[unavailable, "training_layer"] = "ordinary"
    z.loc[unavailable, ["coarse_class", "fine_class"]] = "unassigned"
    z.loc[unavailable, ["coarse_name_zh", "fine_name_zh"]] = "证据不足"
    z.loc[unavailable, "label_status"] = "no_comparable_ordinary_history"
    z.loc[unavailable, "missing_reason"] = "no_comparable_ordinary_history_in_this_condition"
    for c in ["n_records", "n_images", "n_buildings", "n_quality_usable", "n_independent_vote_eligible"]:
        z[c] = z[c].fillna(0).astype(int)
    return z


def member_tables(final, x):
    rows = []
    for (condition, coarse, fine), g in final.groupby(["condition", "coarse_class", "fine_class"]):
        ds = x[(x.condition == condition) & x.layer.eq("ordinary") & x.worker_id.isin(g.worker_id)]
        d = ds[ds.classification_observation]
        rows.append(dict(condition=condition, coarse_class=coarse, fine_class=fine,
            coarse_name_zh=NAMES[coarse], fine_name_zh=NAMES[fine], n_people=len(g),
            members="|".join(g.worker_id), n_images=d.image_id.nunique(), n_buildings=d.building_id.nunique(),
            n_comparable_records=len(d), n_quality_usable=int(d.quality_usable.sum()),
            n_old=int(g.origin.eq("v1").sum()), n_new=int(g.origin.eq("new").sum()),
            **{f: g[f].mean() for f in [c + "_peer_delta" for c in DESCRIPTORS]}))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--output", type=Path, default=HERE)
    args = ap.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    x = load_expression(args.root)
    finals, lobos, models = [], [], []
    for cond in ["manual", "semi"]:
        d = x[x.classification_observation & x.condition.eq(cond)]
        label, model = fit_taxonomy(d, cond)
        label = complete_inventory(label, x, cond)
        label["heldout_building"] = "ALL_DATA"
        label["fit_scope"] = "all_data_descriptive"
        finals.append(label)
        models.append(dict(heldout_building="ALL_DATA", **model))
        # Every non-OOS building receives a frozen ordinary-history label set;
        # doorway outcomes can therefore also be evaluated without target-building leakage.
        for building in sorted(x.building_id.unique()):
            history = d[d.building_id.ne(building)]
            lb, md = fit_taxonomy(history, cond)
            lb = complete_inventory(lb, x, cond)
            lb["heldout_building"] = building
            lb["fit_scope"] = "leave_one_building_out"
            lb["target_condition_observed"] = bool(((x.condition == cond) & (x.building_id == building)).any())
            lobos.append(lb)
            models.append(dict(heldout_building=building, **md))
    final, lobo = pd.concat(finals, ignore_index=True), pd.concat(lobos, ignore_index=True)
    for level in ["coarse_class", "fine_class"]:
        j = lobo.merge(final[["worker_id", "condition", level]], on=["worker_id", "condition"], suffixes=("_lobo", "_final"))
        j = j[j.target_condition_observed & j[level + "_lobo"].ne("unassigned") & j[level + "_final"].ne("unassigned")]
        j["same"] = j[level + "_lobo"] == j[level + "_final"]
        summary = j.groupby(["worker_id", "condition"]).agg(**{level + "_lobo_agreement": ("same", "mean"), level + "_lobo_support": ("same", "size")})
        final = final.merge(summary.reset_index(), on=["worker_id", "condition"], how="left")
    final["fine_status"] = np.where(final.fine_class_lobo_agreement.ge(.8), "repeatable_working_subtype", "member_sensitive_working_subtype")
    final.loc[final.fine_class.eq("unassigned"), "fine_status"] = "unassigned"
    final.to_csv(out / "final_labels.csv", index=False, encoding="utf-8-sig")
    lobo.to_csv(out / "lobo_labels.csv", index=False, encoding="utf-8-sig")
    member_tables(final, x).to_csv(out / "class_members_and_features.csv", index=False, encoding="utf-8-sig")
    json_write(out / "fitted_models.json", models)
    stability = []
    for (condition, building), g in lobo.groupby(["condition", "heldout_building"]):
        full = final[final.condition.eq(condition)]
        j = g.merge(full[["worker_id", "coarse_class", "fine_class"]], on="worker_id", suffixes=("_lobo", "_final"))
        j = j[j.coarse_class_lobo.ne("unassigned") & j.coarse_class_final.ne("unassigned")]
        if not len(j):
            continue
        stability.append(dict(condition=condition, heldout_building=building, n_people=len(j),
            coarse_agreement=float((j.coarse_class_lobo == j.coarse_class_final).mean()),
            fine_agreement=float((j.fine_class_lobo == j.fine_class_final).mean()),
            coarse_ari=float(adjusted_rand_score(j.coarse_class_lobo, j.coarse_class_final)),
            fine_ari=float(adjusted_rand_score(j.fine_class_lobo, j.fine_class_final)),
            target_condition_observed=bool(((x.condition == condition) & (x.building_id == building)).any())))
    pd.DataFrame(stability).to_csv(out / "lobo_label_stability.csv", index=False, encoding="utf-8-sig")
    json_write(out / "FIELD_CONTRACT.json", {
        "schema": "personnel_taxonomy_route_b_v1", "source": EXPRESSION,
        "fit_domain": "ordinary non-OOS personal_comparison observations, peer_n>=3, independently per condition",
        "description_inventory": "all non-OOS records retained in source, doorway external condition; historical exclusions describe behaviour only",
        "fit_support": {"minimum_comparable_images": MIN_IMAGES, "minimum_buildings": MIN_BUILDINGS},
        "feature_definition": {"turn_n": "pair_n minus near_straight_nodes_5deg; count descriptor, no point deletion", "short_turn_edges": "existing perimeter fraction<0.04 and both endpoint turns>=15deg"},
        "normalization": "same image+condition+layer+reference peer median, worker-building mean then buildings equally averaged; z-score fitted over training worker histories",
        "classifier": "Ward Euclidean hierarchy on turn_n_peer_delta and short_turn_edges_peer_delta; coarse 2 independently for each condition; manual split both parents; semi split the lower-turn parent only",
        "names": NAMES,
        "model_selection": "descriptive exploration of 2-5 class structures and geometry/collinearity variants; selected meaningful multi-member hierarchy before fusion; subsequent LOBO checks are not a prospectively untouched discovery set",
        "validation": "lobo_labels only. The entire target building is excluded before worker features, scaling and clustering. ALL_DATA labels are descriptive only.",
        "non_oos_inventory_n": len(x), "all_worker_inventory_n": x.worker_id.nunique(),
        "coarse_fine_semantics": "conditional working marking types, no correctness or psychological motivation implied",
        "ring_reference_quality_fusion_changed": False,
    })
    lines = ["# 路线B阶段分类：实际成员已保存", "", "本版冻结结构分类后再开展融合。普通 Manual 与 Semi 分别建类；门洞用于楼外外推检验，不混入训练。", "", "## 类别与成员", ""]
    for row in member_tables(final, x).to_dict("records"):
        lines.append(f"- **{row['condition']} / {row['fine_class']} {row['fine_name_zh']}**（{row['n_people']}人；粗类 {row['coarse_class']}）：{row['members']}。")
    lines += ["", "## 方法", "", "对同图、同条件、同参考的非近共线转折数与短转折边取同行中位数残差，先在每栋建筑内求人员均值，再对建筑等权。仅≥12张可比图片且≥4栋建筑者建类。两项按训练人员标准化，Ward两粗类；Manual两父类各分两细类，Semi在较少转折父类内细分。Q、T、质量资格均不参与聚类。", "", "`final_labels.csv` 为全数据描述标签；`lobo_labels.csv` 为楼外标签，每次排除整栋目标建筑后重新计算人员特征、标准化与聚类。细类对成员和历史图片更敏感，标签内保存留一楼一致比例。", "", "类别解释的‘较多’仅指几何表达，真实必要细节、参考省略、冗余点、范围及错误另由语义案例区分。W037尽管转折数量较少，仍经常增加共线分段；这由辅助标法轴说明，不能把点数相同当作标法相同。", "", "这是阶段成果；楼外原答差异、Q/T/来源与实际替换结果随后独立保存。"]
    (out / "STAGE_REPORT_ZH.md").write_text("\n".join(lines) + "\n", encoding="utf8")
    print(member_tables(final, x)[["condition", "coarse_class", "fine_class", "n_people", "n_images", "n_buildings"]].to_string(index=False))


if __name__ == "__main__":
    main()
