"""Describe existing OOS evidence by adopted visible factors; no scoring or fusion."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tools.thesis_main.analysis.personnel_marking_patterns_20261020 import geometry_features, v

ROOT = Path(__file__).resolve().parents[3]
TOPIC = ROOT / "research/difficulty/difficulty_mechanisms_v2_20261020/scope_closeout_20261022"
OUT = TOPIC / "oos_statistics_20261024"
EVIDENCE = ROOT / "research/statistics/v2_evidence_audit_20261019/records.json.gz"
TABLES = ROOT / "research/statistics/v2_integrated_analysis_20261019/tables.json.gz"
FACTORS = ["斜墙／平面非正交", "多标高地面／楼梯挑空", "斜顶", "多标高天花板", "曲面边界", "原因未定", "严重遮挡"]


def adopted_factors(records, drafts):
    rows = []
    images = {r["image_id"]: r for r in records}
    overrides = {
        "b8cTxDM8gDG-04": [FACTORS[1]], "b8cTxDM8gDG-19": [FACTORS[0]],
        "uNb9QFRL6hY-69": [FACTORS[1], FACTORS[3]],
        "x8F5xyUWy9e-01": [FACTORS[0]], "x8F5xyUWy9e-09": [FACTORS[0]],
        "UwV83HsGsw3-23": [FACTORS[6]],
    }
    for image_id, r in sorted(images.items(), key=lambda item: item[1]["image_code"]):
        draft = drafts.get(image_id, {})
        factors = overrides.get(r["image_code"], draft.get("visible", []))
        assert factors and set(factors) <= set(FACTORS), r["image_code"]
        rows.append(dict(image_id=image_id, image_code=r["image_code"], room_id=r["room_id"],
                         building_id=r["building_id"], factors="|".join(factors),
                         factor_basis="conversation_and_visual_review" if r["image_code"] in overrides else "user_export_and_visual_review",
                         target_factor_status="not_adjudicated", angle_degrees=None))
    return pd.DataFrame(rows)


def record_row(r):
    scope = r["scope_evidence"]
    history = scope.get("historical_evidence") or {}
    eligible = r["pool_analysis_eligible"] and r["independent_vote_eligible"]
    # Preserve existing analysis holds: only count inventory/time/choices outside the pool.
    features = {"feature_status": "outside_existing_pool"}
    if eligible:
        features, geometry = geometry_features(r["points_1024x512"])
        ceiling = geometry["ceiling_xyz"]
        if features.get("feature_status") == "valid_floor" and ceiling is not None:
            heights = ceiling[:, 1] + 1
            features["implied_height_within_relative_range"] = float(np.ptp(heights) / heights.mean())
    row = {key: r[key] for key in ["object_id", "image_id", "image_code", "worker_id", "building_id", "room_id",
                                   "condition", "origin", "cleaning_disposition", "quality_usable", "pool_analysis_eligible",
                                   "independent_vote_eligible", "ring_confirmed", "geometry_status", "declared_pair_count", "is_doorway"]}
    row.update(features)
    row.update(analysis_pool=eligible, time_source=r["time_evidence"]["source_kind"],
               time_status=r["time_evidence"]["source_status"], source_seconds=r["source_active_time_seconds"],
               scope_response=scope["response"], historical_raw_scope=history.get("raw_scope"),
               compatible_scope_gold=scope["compatible_gold"])
    if features.get("feature_status") == "valid_floor":
        row["turns_over_5deg"] = features["pair_n"] - features["near_straight_nodes_5deg"]
    return row


def pair_summary(pairs):
    valid = pairs.loc[pairs.floor_pair_measurable.eq(True) & pairs.R_union_normalized.notna()]
    counts = pairs.same_pair_count.dropna()
    return dict(pair_n=len(pairs), measurable_pair_n=len(valid), comparable_node_pair_n=len(counts),
                R_pair_union_mean=valid.R_union_normalized.mean(),
                different_node_count_rate=counts.eq(False).mean() if len(counts) else np.nan)


def image_summaries(records, pairs):
    rows = []
    for (code, condition, origin, source), g in records.groupby(["image_code", "condition", "origin", "time_source"]):
        pool = g[g.analysis_pool]
        ids = set(pool.object_id)
        p = pairs[pairs.object_id_a.isin(ids) & pairs.object_id_b.isin(ids)]
        observed = g[g.scope_response.notna()]
        rows.append(dict(image_code=code, image_id=g.image_id.iloc[0], building_id=g.building_id.iloc[0],
                         condition=condition, origin=origin, time_source=source,
                         is_doorway=bool(g.is_doorway.iloc[0]),
                         inventory_n=len(g), retained_n=int(g.cleaning_disposition.eq("retained").sum()),
                         pool_n=len(pool), valid_floor_n=int(pool.feature_status.eq("valid_floor").sum()),
                         confirmed_order_n=int(pool.ring_confirmed.sum()),
                         pair_count_median=pool.declared_pair_count.median(),
                         turns_over_5deg_median=pool.turns_over_5deg.median(),
                         near_straight_median=pool.near_straight_nodes_5deg.median(),
                         short_edges_median=pool.short_turn_edges.median(),
                         implied_height_n=int(pool.height_camera_height.notna().sum()),
                         implied_height_median=pool.height_camera_height.median(),
                         implied_height_P10=pool.height_camera_height.quantile(.1),
                         implied_height_P90=pool.height_camera_height.quantile(.9),
                         implied_height_within_range_median=pool.implied_height_within_relative_range.dropna().median(),
                         time_n=int(g.source_seconds.notna().sum()), source_seconds_median=g.source_seconds.median(),
                         scope_normalized_n=len(observed), scope_out_n=int(observed.scope_response.eq("out_of_scope").sum()),
                         # v1 harmonization only keeps the normal choices. Its raw OOS choices
                         # remain in historical_raw_scope; a normalized 0% would be misleading.
                         scope_out_rate=observed.scope_response.eq("out_of_scope").mean() if origin == "new" else np.nan,
                         historical_raw_scope_n=int(g.historical_raw_scope.notna().sum()), **pair_summary(p)))
    return pd.DataFrame(rows)


def factor_summaries(images, labels):
    expanded = labels.assign(factor=labels.factors.str.split("|")).explode("factor")
    rows = []
    for (factor, condition, origin, source), g in images.merge(expanded[["image_code", "factor"]], on="image_code").groupby(
            ["factor", "condition", "origin", "time_source"]):
        rows.append(dict(factor=factor, condition=condition, origin=origin, time_source=source,
                         image_n=len(g), building_n=g.building_id.nunique(),
                         inventory_n=int(g.inventory_n.sum()), pool_n=int(g.pool_n.sum()),
                         geometry_image_n=int(g.valid_floor_n.gt(0).sum()), R_image_n=int(g.R_pair_union_mean.notna().sum()),
                         pair_count_image_mean=g.pair_count_median.mean(), turns_image_mean=g.turns_over_5deg_median.mean(),
                         near_straight_image_mean=g.near_straight_median.mean(), short_edges_image_mean=g.short_edges_median.mean(),
                         implied_height_within_range_image_mean=g.implied_height_within_range_median.mean(),
                         R_image_mean=g.R_pair_union_mean.mean(), node_count_disagreement_image_mean=g.different_node_count_rate.mean(),
                         source_seconds_image_mean=g.source_seconds_median.mean(), time_n=int(g.time_n.sum()),
                         scope_n=int(g.scope_normalized_n.sum()), scope_out_n=int(g.scope_out_n.sum()),
                         scope_out_image_mean=g.scope_out_rate.mean(),
                         scope_comparable_image_n=int(g.scope_out_rate.notna().sum()),
                         scope_out_majority_images=int(g.scope_out_rate.gt(.5).sum()),
                         scope_tied_images=int(g.scope_out_rate.eq(.5).sum())))
    return pd.DataFrame(rows)


def legacy_fusion(labels):
    codes = set(labels.image_code)
    path = ROOT / "research/fusion/wall_consensus_v1_process_20261017/random_baseline/by_pool_k.csv"
    wall = pd.read_csv(path)
    wall = wall[wall.image.isin(codes)].copy()
    rows = []
    for (pool, image, condition), g in wall.groupby(["pool_id", "image", "condition"]):
        end = g[g.k.eq(g.k.max())].iloc[0]
        rows.append(dict(source="v1_wall_random", image_code=image, condition=condition, pool_id=pool,
                         N=int(g.k.max()), paths=int(end.path_states), states=int(g.path_states.sum()),
                         complete_geometry_states=int(g.complete_geometry.sum()),
                         full_pool_complete=bool(end.complete_geometry == end.path_states),
                         formal_Q_allowed=False, source_path=path.relative_to(ROOT).as_posix()))
    path = ROOT / "research/fusion/wall_consensus_quality_20261015/special/by_image_k.csv"
    special = pd.read_csv(path)
    special = special[special.image.isin(codes)]
    for code, g in special.groupby("image"):
        rows.append(dict(source="historical_wall_special", image_code=code, condition="manual", pool_id=code,
                         N=int(g.k.max()), paths=int(g.total_paths.max()), states=int(g.total_paths.sum()),
                         floor_evaluable_states=int(g.floor_evaluable_paths.sum()), formal_Q_allowed=False,
                         source_path=path.relative_to(ROOT).as_posix()))
    path = ROOT / "analysis_results/difficulty_full_20261007/updated/endpoints.csv"
    lee = pd.read_csv(path)
    lee = lee[lee.image.isin(codes) & lee.method.eq("mv50") & lee.version.eq("original")]
    for _, r in lee.iterrows():
        rows.append(dict(source="historical_lee_mv50_original", image_code=r.image, condition=r.condition,
                         pool_id=r.pool, N=int(r.n), states=1, formal_Q_allowed=False,
                         source_path=path.relative_to(ROOT).as_posix()))
    actual = pd.read_csv(ROOT / "research/workers/personnel_population_curves_v2_20261023/design/ACTUAL_POOLS.csv")
    # The newer v2 count experiment deliberately uses non-OOS pools.
    assert not any(str(value) in codes for value in actual.to_numpy().ravel())
    return pd.DataFrame(rows), wall


def main():
    OUT.mkdir(exist_ok=True)
    records = [r for r in json.load(gzip.open(EVIDENCE, "rt", encoding="utf8"))["records"] if r["is_oos"]]
    drafts = json.loads((TOPIC / "OOS_USER_REVIEW_20261024.json").read_text("utf8"))["records"]
    labels = adopted_factors(records, drafts)
    labels.to_csv(OUT / "adopted_factors.csv", index=False, encoding="utf-8-sig")
    data = pd.DataFrame([record_row(r) for r in records])
    assert len(data) == 1222 and data.object_id.is_unique and len(labels) == 28
    assert data.analysis_pool.sum() == 1051 and not data.quality_usable.any()
    assert data.compatible_scope_gold.isna().all()
    data.to_csv(OUT / "record_diagnostics.csv.gz", index=False, compression="gzip")
    tables = json.load(gzip.open(TABLES, "rt", encoding="utf8"))["tables"]
    pairs = pd.DataFrame(tables["statistics__raw_answer_pairs"])
    pairs = pairs[pairs.image_id.isin(labels.image_id)]
    assert len(pairs) == 16408
    images = image_summaries(data, pairs)
    images.to_csv(OUT / "image_condition_source.csv", index=False, encoding="utf-8-sig")
    factors = factor_summaries(images, labels)
    factors.to_csv(OUT / "factor_condition_source.csv", index=False, encoding="utf-8-sig")
    worker = data.groupby(["worker_id", "condition", "origin", "time_source"]).agg(
        image_n=("image_id", "nunique"), inventory_n=("object_id", "size"), pool_n=("analysis_pool", "sum"),
        valid_floor_n=("feature_status", lambda s: int(s.eq("valid_floor").sum())),
        turns_median=("turns_over_5deg", "median"), source_seconds_median=("source_seconds", "median"),
        time_n=("source_seconds", "count"), scope_n=("scope_response", "count"),
        scope_out_n=("scope_response", lambda s: int(s.eq("out_of_scope").sum()))).reset_index()
    worker.to_csv(OUT / "worker_condition_source.csv", index=False, encoding="utf-8-sig")
    choices = data.groupby(["condition", "origin", "scope_response", "historical_raw_scope"], dropna=False).size().reset_index(name="n")
    choices.to_csv(OUT / "scope_response_sources.csv", index=False, encoding="utf-8-sig")
    fusion, wall = legacy_fusion(labels)
    fusion.to_csv(OUT / "legacy_fusion_coverage.csv", index=False, encoding="utf-8-sig")
    wall.drop(columns=["B8L2_mean", "D10_mean"]).to_csv(OUT / "legacy_wall_by_pool_k.csv", index=False, encoding="utf-8-sig")
    primary = factors[factors.condition.eq("manual") & factors.origin.eq("new")].set_index("factor").loc[FACTORS].reset_index()
    v._configure_font(Path("C:/Windows/Fonts/msyh.ttc"))
    fig, axes = v.plt.subplots(1, 3, figsize=(14, 6))
    names = ["斜墙", "地面高差", "斜顶", "顶面高差", "曲线/折转玻璃", "原因未定", "严重遮挡"]
    for ax, metric, title in zip(axes, ["R_image_mean", "source_seconds_image_mean", "scope_out_image_mean"],
                                 ["原答底面分歧（0—1）", "每图记录时间中位数的均值（秒）", "选择不可标的比例（图片等权）"]):
        counts = primary.R_image_n if metric == "R_image_mean" else primary.image_n
        ax.barh([f"{name}（{int(n)}图）" for name, n in zip(names, counts)], primary[metric], color="#287c8e")
        ax.invert_yaxis()
        ax.set_title(title, fontsize=11)
        ax.grid(axis="x", alpha=.2)
        for i, value in enumerate(primary[metric]):
            ax.text(value, i, f" {value:.3f}" if metric != "source_seconds_image_mean" else f" {value:.0f}", va="center", fontsize=9)
        ax.margins(x=.2)
    fig.suptitle("OOS子类诊断 · 新批Manual · 同来源分层 · 因素允许重叠", fontsize=14)
    fig.tight_layout(rect=(0, .12, 1, .94))
    fig.text(.02, .065, "OOS超出标注标准；GT可能为满足曼哈顿约束而近似。本图不评价谁正确，也不证明场景符合标准。", fontsize=10)
    fig.text(.02, .025, "底面分歧只描述保存作答的单平面近似；时间/选择覆盖28图，几何沿既有资格覆盖24图。曲线类5图均来自同一房间。", fontsize=10)
    fig.savefig(OUT / "oos_subtypes.png", dpi=150)
    v.plt.close(fig)
    summary = dict(schema="oos_closeout_v1", release="v2", inventory=len(data), images=len(labels), workers=data.worker_id.nunique(),
                   buildings=data.building_id.nunique(), pool_records=int(data.analysis_pool.sum()),
                   retained=int(data.cleaning_disposition.eq("retained").sum()),
                   source_time_records=int(data.source_seconds.notna().sum()),
                   original_pairs=len(pairs), primary=data.origin.eq("new").sum().item(),
                   factor_counts=labels.factors.str.split("|").explode().value_counts().to_dict(),
                   no_existing_fusion_images=sorted(set(labels.image_code)-set(fusion.image_code)),
                   sources=[EVIDENCE.relative_to(ROOT).as_posix(), TABLES.relative_to(ROOT).as_posix()])
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(primary.to_string(index=False))


if __name__ == "__main__":
    main()
