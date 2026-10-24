"""Common-support metric audit of saved v2 swap and population endpoints."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine


ROOT = Path(__file__).resolve().parents[3]
ROOM = ROOT / "research/same_room/same_room_large_block_rebuilt_20261023"
POP = ROOT / "research/workers/personnel_population_curves_v2_20261023"
ENGINE = ROOT / "research/statistics/b8l2_shared_v6_20261016/inputs"
OUT = ROOT / "research/quality/personnel_metric_dependence_20261024"
EXCHANGE = ROOT / "research/workers/personnel_mixture_comparison_20261022"
METRICS = ("B8L2", "D10", "iou_2d", "IoU3D100", "S_bottom_deg", "dir", "Hmean",
           "Hcenter", "ref_node_recall_5", "ref_edge_recall_5", "fusion_turn_n",
           "fusion_short_turn_edges", "B8L2_no_direction")
SCALAR_COLUMNS = ["team_key", "complete_evaluable", "B8L2", "D10", "iou_2d", "IoU3D100",
                  "S_bottom_deg", "dir", "Hmean", "Hcenter", "ref_node_recall_5",
                  "ref_edge_recall_5", "fusion_turn_n", "fusion_short_turn_edges"]


def read_scalars(path: Path, keys: set[str]) -> pd.DataFrame:
    chunks = []
    for chunk in pd.read_csv(path, usecols=SCALAR_COLUMNS, chunksize=30000, low_memory=False):
        match = chunk[chunk.team_key.isin(keys)]
        if not match.empty:
            chunks.append(match)
    result = pd.concat(chunks, ignore_index=True).drop_duplicates("team_key")
    missing = keys - set(result.team_key)
    assert not missing, (path, len(missing))
    with scoring_engine(ENGINE / "measurement_engine.zip", ENGINE / "working_models.py") as (_, models):
        valid = result[["B8L2", "iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter"]].notna().all(axis=1)
        x = result.loc[valid]
        parameter = models.MODELS["B8L2"]
        actual = models.score(x.iou_2d.to_numpy(), x.S_bottom_deg.to_numpy(), x.dir.to_numpy(),
                              x.Hmean.to_numpy(), x.Hcenter.to_numpy(), parameter)
        assert np.max(np.abs(actual - x.B8L2.to_numpy())) < 1e-7
        result.loc[valid, "B8L2_no_direction"] = models.score(
            x.iou_2d.to_numpy(), x.S_bottom_deg.to_numpy(), np.zeros(len(x)),
            x.Hmean.to_numpy(), x.Hcenter.to_numpy(), parameter)
    return result.set_index("team_key", verify_integrity=True)


def swap_audit() -> None:
    columns = ["event_id", "config_id", "pair_key", "building", "method", "condition",
               "ordinary_comparable", "difficulty_a", "difficulty_b", "n", "m", "D_n"]
    keys = [f"team_key_{arm}_{view}" for view in ("a", "b") for arm in ("A", "B", "C")]
    events = pd.read_csv(ROOM / "design/STRICT_ABC_EVENTS.csv.gz", usecols=columns + keys)
    events = events[events.ordinary_comparable & events.condition.eq("manual")].copy()
    source = read_scalars(ROOM / "native_endpoints/ENDPOINT_SCALARS.csv.gz",
                          set(events[keys].stack().dropna()))
    rows = []
    for view in ("a", "b"):
        frame = events[columns + [f"team_key_{arm}_{view}" for arm in ("A", "B", "C")]].copy()
        frame["view"] = view
        for arm in ("A", "B", "C"):
            mapped = source.reindex(frame[f"team_key_{arm}_{view}"])
            assert mapped.B8L2.notna().sum() > 0
            for metric in METRICS:
                frame[f"{metric}_{arm}"] = mapped[metric].to_numpy()
            frame[f"complete_{arm}"] = mapped.complete_evaluable.to_numpy()
        rows.append(frame)
    views = pd.concat(rows, ignore_index=True)
    views["failure_B"] = (~views.complete_B.astype(bool)).astype(int)
    views["failure_C"] = (~views.complete_C.astype(bool)).astype(int)
    views[["event_id", "config_id", "D_n", "pair_key", "building", "method", "difficulty_a", "difficulty_b", "view",
           "failure_B", "failure_C"]].to_csv(OUT / "SWAP_ATTEMPTS.csv", index=False)
    effects = []
    for metric in METRICS:
        a, b, c = (views[f"{metric}_{arm}"] for arm in ("A", "B", "C"))
        good = a.notna() & b.notna() & c.notna()
        d = views.loc[good, ["event_id", "config_id", "D_n", "pair_key", "building", "method", "difficulty_a", "difficulty_b", "view"]].copy()
        d["metric"] = metric
        d["within_abs"] = (b[good] - a[good]).abs().to_numpy()
        d["cross_abs"] = ((c[good] - a[good]).abs() + (c[good] - b[good]).abs()).to_numpy() / 2
        d["extra_abs"] = d.cross_abs - d.within_abs
        d["net_C_minus_B"] = (c[good] - b[good]).to_numpy()
        effects.append(d)
    details = pd.concat(effects, ignore_index=True)
    details.to_csv(OUT / "SWAP_VIEW_METRICS.csv.gz", index=False, compression="gzip")
    pair = details.groupby(["event_id", "config_id", "D_n", "pair_key", "building", "method", "difficulty_a", "difficulty_b", "metric"]).agg(
        views=("view", "nunique"), within_abs=("within_abs", "mean"), cross_abs=("cross_abs", "mean"),
        extra_abs=("extra_abs", "mean"), net_C_minus_B=("net_C_minus_B", "mean")).reset_index()
    pair = pair[pair.views.eq(2)]
    pair.to_csv(OUT / "SWAP_EVENT_COMMON_VIEWS.csv.gz", index=False, compression="gzip")
    image_pairs = []
    for subset, selected in (("ordinary_all", pair), ("ordinary_mixed", pair[pair.D_n.gt(0)])):
        configuration = selected.groupby(["config_id", "pair_key", "building", "method", "difficulty_a", "difficulty_b", "metric"]).agg(
            events=("event_id", "nunique"), within_abs=("within_abs", "mean"),
            cross_abs=("cross_abs", "mean"), extra_abs=("extra_abs", "mean"),
            net_C_minus_B=("net_C_minus_B", "mean")).reset_index()
        by_pair = configuration.groupby(["pair_key", "building", "method", "difficulty_a", "difficulty_b", "metric"]).agg(
            configurations=("config_id", "nunique"), events=("events", "sum"),
            within_abs=("within_abs", "mean"), cross_abs=("cross_abs", "mean"),
            extra_abs=("extra_abs", "mean"), net_C_minus_B=("net_C_minus_B", "mean")).reset_index()
        by_pair["subset"] = subset
        image_pairs.append(by_pair)
    image_pairs = pd.concat(image_pairs, ignore_index=True)
    main = image_pairs[(image_pairs.subset == "ordinary_mixed") &
                       (image_pairs.method == "V3_BEHAVIOR") & (image_pairs.metric == "B8L2")]
    reference = pd.read_csv(ROOT / "research/statistics/same_room_rebuilt_audit_20261023/results/INDEPENDENT_MAIN_RESULTS.csv")
    reference = reference[(reference.subset == "ordinary_mixed") & (reference.method == "V3_BEHAVIOR")].iloc[0]
    assert len(main) == 78 and int((main.extra_abs > 0).sum()) == int(reference.positive_pairs)
    assert abs(main.extra_abs.mean() - reference["pair_equal__B8L2_extra"]) < 1e-9
    image_pairs.to_csv(OUT / "SWAP_IMAGE_PAIRS.csv", index=False)
    buildings = image_pairs.groupby(["subset", "building", "method", "difficulty_a", "difficulty_b", "metric"]).agg(
        pairs=("pair_key", "nunique"), extra_abs=("extra_abs", "mean"),
        net_C_minus_B=("net_C_minus_B", "mean")).reset_index()
    buildings.to_csv(OUT / "SWAP_BUILDINGS.csv", index=False)
    summary = buildings.groupby(["subset", "method", "difficulty_a", "difficulty_b", "metric"]).agg(
        buildings=("building", "nunique"), pairs=("pairs", "sum"),
        extra_abs=("extra_abs", "mean"), positive_buildings=("extra_abs", lambda x: int((x > 0).sum())),
        net_C_minus_B=("net_C_minus_B", "mean")).reset_index()
    summary.to_csv(OUT / "SWAP_SUMMARY.csv", index=False)
    # The fixed comparison uses events whose six A/B/C endpoints have formal Q in both views.
    base = pair[pair.metric.eq("B8L2")][["event_id", "config_id", "pair_key", "method"]].drop_duplicates()
    fixed = pair.merge(base, on=["event_id", "config_id", "pair_key", "method"], validate="many_to_one")
    fixed.to_csv(OUT / "SWAP_FIXED_Q_EVENTS.csv.gz", index=False, compression="gzip")
    compared = fixed[fixed.metric.isin(("B8L2", "D10", "iou_2d", "IoU3D100", "S_bottom_deg", "dir", "Hmean", "Hcenter", "B8L2_no_direction"))]
    complete_ids = compared.groupby(["event_id", "config_id", "pair_key", "method"]).metric.nunique()
    complete_ids = complete_ids[complete_ids.eq(9)].reset_index()[["event_id", "config_id", "pair_key", "method"]]
    compared = compared.merge(complete_ids, on=["event_id", "config_id", "pair_key", "method"], validate="many_to_one")
    fixed_rows = []
    for subset, selected in (("ordinary_all", compared), ("ordinary_mixed", compared[compared.D_n.gt(0)])):
        config = selected.groupby(["config_id", "pair_key", "building", "method", "metric"]).agg(
            events=("event_id", "nunique"), extra_abs=("extra_abs", "mean"), net_C_minus_B=("net_C_minus_B", "mean")).reset_index()
        image = config.groupby(["pair_key", "building", "method", "metric"]).agg(
            configurations=("config_id", "nunique"), events=("events", "sum"),
            extra_abs=("extra_abs", "mean"), net_C_minus_B=("net_C_minus_B", "mean")).reset_index()
        image["subset"] = subset
        fixed_rows.append(image)
    fixed_images = pd.concat(fixed_rows, ignore_index=True)
    fixed_images.to_csv(OUT / "SWAP_FIXED_Q_IMAGE_PAIRS.csv", index=False)
    fixed_summary = fixed_images.groupby(["subset", "method", "metric"]).agg(
        pairs=("pair_key", "nunique"), buildings=("building", "nunique"), events=("events", "sum"),
        extra_abs=("extra_abs", "mean"), positive_pairs=("extra_abs", lambda x: int((x > 0).sum()))).reset_index()
    fixed_summary.to_csv(OUT / "SWAP_FIXED_Q_SUMMARY.csv", index=False)
    print("swap", len(events), len(pair), len(image_pairs), flush=True)


def prefix_audit() -> None:
    columns = ["pool_id", "path_id", "base_path_id", "replicate", "policy", "k", "team_key",
               "paired_for_policy", "image", "building", "condition", "layer", "difficulty", "pool_n"]
    prefix = pd.read_csv(POP / "stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz", usecols=columns)
    prefix = prefix[prefix.policy.isin(("natural_random", "joint_highq_first", "structure_moreturn_first"))
                   & prefix.k.isin((3, 6, 10, 20))].copy()
    source = read_scalars(POP / "results/ENDPOINT_SCALARS.csv.gz", set(prefix.team_key.dropna()))
    for metric in METRICS:
        prefix[metric] = prefix.team_key.map(source[metric])
    prefix["complete"] = prefix.team_key.map(source.complete_evaluable).astype(bool)
    natural = prefix[prefix.policy.eq("natural_random")].copy()
    pairs = []
    for start, end in ((3, 6), (10, 20)):
        a = natural[natural.k.eq(start)]
        b = natural[natural.k.eq(end)]
        joined = a.merge(b, on=["pool_id", "path_id"], suffixes=("_a", "_b"), validate="one_to_one")
        for metric in METRICS:
            valid = joined[f"{metric}_a"].notna() & joined[f"{metric}_b"].notna()
            d = joined.loc[valid, ["image_a", "building_a", "condition_a", "layer_a", "difficulty_a", "pool_id", "path_id"]].copy()
            d["interval"] = f"{start}_to_{end}"
            d["metric"] = metric
            d["delta"] = joined.loc[valid, f"{metric}_b"].to_numpy() - joined.loc[valid, f"{metric}_a"].to_numpy()
            pairs.append(d)
        failures = joined[["image_a", "building_a", "condition_a", "layer_a", "difficulty_a", "pool_id", "path_id", "complete_a", "complete_b"]].copy()
        failures["interval"] = f"{start}_to_{end}"
        failures.to_csv(OUT / f"NATURAL_FAILURE_{start}_{end}.csv", index=False)
    all_pairs = pd.concat(pairs, ignore_index=True)
    all_pairs.to_csv(OUT / "NATURAL_PATH_METRICS.csv.gz", index=False, compression="gzip")
    common_metrics = ("B8L2", "D10", "iou_2d", "IoU3D100", "S_bottom_deg", "dir", "Hmean", "Hcenter", "B8L2_no_direction")
    eligible_pools = set(natural[natural.condition.eq("manual") & natural.layer.eq("ordinary_manual") &
                                 natural.difficulty.eq("困难") & natural.pool_n.ge(20)].pool_id)
    hard = all_pairs[all_pairs.pool_id.isin(eligible_pools) & all_pairs.condition_a.eq("manual") & all_pairs.layer_a.eq("ordinary_manual") &
                     all_pairs.difficulty_a.eq("困难") & all_pairs.metric.isin(common_metrics)].copy()
    path_cols = ["interval", "pool_id", "path_id"]
    counts = hard.groupby(path_cols).metric.nunique()
    keys = counts[counts.eq(len(common_metrics))].reset_index()[path_cols]
    fixed = hard.merge(keys, on=path_cols, validate="many_to_one")
    supports = [set(map(tuple, fixed.loc[fixed.metric.eq(metric), path_cols].itertuples(index=False, name=None)))
                for metric in common_metrics]
    assert all(support == supports[0] for support in supports[1:]), "Natural metrics do not share exact paths"
    assert fixed.groupby(path_cols + ["metric"]).size().eq(1).all()
    assert fixed.groupby("interval").image_a.nunique().eq(29).all()
    fixed.to_csv(OUT / "NATURAL_FIXED_Q_PATH_METRICS.csv.gz", index=False, compression="gzip")
    fixed_image = fixed.groupby(["image_a", "building_a", "interval", "metric"]).agg(
        paired_paths=("path_id", "nunique"), mean_delta=("delta", "mean"),
        positive_paths=("delta", lambda x: int((x > 0).sum()))).reset_index()
    fixed_image.to_csv(OUT / "NATURAL_FIXED_Q_IMAGE_METRICS.csv", index=False)
    fixed_image.groupby(["interval", "metric"]).agg(
        images=("image_a", "nunique"), buildings=("building_a", "nunique"),
        paired_paths=("paired_paths", "sum"), image_equal_mean=("mean_delta", "mean"),
        positive_images=("mean_delta", lambda x: int((x > 0).sum()))).reset_index().to_csv(
            OUT / "NATURAL_FIXED_Q_SUMMARY.csv", index=False)
    by_image = all_pairs.groupby(["image_a", "building_a", "condition_a", "layer_a", "difficulty_a", "interval", "metric"]).agg(
        paired_paths=("path_id", "nunique"), mean_delta=("delta", "mean"),
        median_delta=("delta", "median"), positive_paths=("delta", lambda x: int((x > 0).sum())),
        negative_paths=("delta", lambda x: int((x < 0).sum()))).reset_index()
    by_image.to_csv(OUT / "NATURAL_IMAGE_METRICS.csv", index=False)
    by_building = by_image.groupby(["building_a", "condition_a", "layer_a", "difficulty_a", "interval", "metric"]).agg(
        images=("image_a", "nunique"), mean_delta=("mean_delta", "mean"),
        positive_images=("mean_delta", lambda x: int((x > 0).sum())),
        negative_images=("mean_delta", lambda x: int((x < 0).sum()))).reset_index()
    by_building.to_csv(OUT / "NATURAL_BUILDING_METRICS.csv", index=False)
    # Priority policies are paired to natural paths by the saved replicate, not by endpoint value.
    base = prefix[prefix.policy.eq("natural_random") & prefix.paired_for_policy]
    priorities = prefix[~prefix.policy.eq("natural_random") & prefix.paired_for_policy]
    paired = priorities.merge(base, on=["pool_id", "replicate", "k"], suffixes=("_priority", "_natural"), validate="many_to_one")
    policy_rows = []
    for metric in METRICS:
        good = paired[f"{metric}_priority"].notna() & paired[f"{metric}_natural"].notna()
        d = paired.loc[good, ["image_priority", "building_priority", "difficulty_priority", "layer_priority", "pool_id", "replicate", "k", "policy_priority"]].copy()
        d["metric"] = metric
        d["delta"] = paired.loc[good, f"{metric}_priority"].to_numpy() - paired.loc[good, f"{metric}_natural"].to_numpy()
        policy_rows.append(d)
    policies = pd.concat(policy_rows, ignore_index=True)
    policies.to_csv(OUT / "POLICY_PAIRED_METRICS.csv.gz", index=False, compression="gzip")
    policies.groupby(["image_priority", "building_priority", "difficulty_priority", "layer_priority", "pool_id", "k", "policy_priority", "metric"]).agg(
        pairs=("replicate", "nunique"), mean_delta=("delta", "mean"), median_delta=("delta", "median"),
        positive_pairs=("delta", lambda x: int((x > 0).sum())),
        negative_pairs=("delta", lambda x: int((x < 0).sum()))).reset_index().to_csv(OUT / "POLICY_IMAGE_METRICS.csv", index=False)
    print("prefix", len(prefix), len(all_pairs), len(policies), flush=True)


def directional_difficulty_audit() -> None:
    # Preserve the original oriented ABC events and their D -> class pair -> image -> building weights.
    cid = "ca2a651478a2ab2966a4"
    folder = EXCHANGE / "exchanges/manual_joint_A"
    links = pd.read_csv(folder / "EXACT_EVENT_LINKS.csv.gz")
    links = links[links.condition_id.eq(cid)].drop_duplicates(["condition_id", "actual_oriented_ABC"])
    outcomes = pd.read_csv(folder / "EVENT_OUTCOMES.csv.gz", usecols=["event_id", "condition_id", "A_B8L2", "B_B8L2", "C_B8L2"])
    event = links.merge(outcomes, on=["event_id", "condition_id"], validate="one_to_one")
    source = read_scalars(ROOT / "research/workers/personnel_exchange_closure_20261022/delivery/endpoints/ALL_REQUIRED_ENDPOINT_SCALARS.csv.gz",
                          set(event[["team_A", "team_B", "team_C"]].stack()))
    for arm in "ABC":
        saved_q = event[f"{arm}_B8L2"].copy()
        for metric in ("B8L2", "D10", "iou_2d", "IoU3D100", "S_bottom_deg", "dir", "Hmean", "Hcenter", "B8L2_no_direction"):
            event[f"{arm}_{metric}"] = event[f"team_{arm}"].map(source[metric])
        assert np.allclose(event[f"{arm}_B8L2"], saved_q, equal_nan=True)
    scope = pd.read_csv(EXCHANGE / "difficulty/exchange_difficulty_join.csv", usecols=["condition_id", "image", "current_difficulty"])
    event = event.merge(scope[scope.condition_id.eq(cid)], on=["condition_id", "image"], validate="many_to_one")
    group = ["condition_id", "pool_id", "building", "image", "current_difficulty", "source_class", "target_class", "background_key"]
    parts = []
    scored = event[[f"{arm}_B8L2" for arm in "ABC"]].notna().all(axis=1)
    for metric in ("B8L2", "D10", "iou_2d", "IoU3D100", "S_bottom_deg", "dir", "Hmean", "Hcenter", "B8L2_no_direction"):
        a, b, c = (event[f"{arm}_{metric}"] for arm in "ABC")
        good = scored & a.notna() & b.notna() & c.notna()
        d = event.loc[good, group + ["event_id", "team_A", "team_B", "team_C"]].copy()
        d["metric"] = metric
        d["net_C_minus_B"] = (c[good] - b[good]).to_numpy()
        d["within_abs"] = (b[good] - a[good]).abs().to_numpy()
        d["cross_abs"] = (((c[good] - a[good]).abs() + (c[good] - b[good]).abs()) / 2).to_numpy()
        d["extra_abs"] = d.cross_abs - d.within_abs
        parts.append(d)
    detail = pd.concat(parts, ignore_index=True)
    detail.to_csv(OUT / "DIRECTIONAL_SWAP_EVENTS.csv.gz", index=False, compression="gzip")
    values = ["net_C_minus_B", "within_abs", "cross_abs", "extra_abs"]
    bg = detail.groupby(group + ["metric"], dropna=False)[values].mean().reset_index()
    cell = bg.groupby(group[:-1] + ["metric"], dropna=False)[values].mean().reset_index()
    images = cell.groupby(["condition_id", "building", "image", "current_difficulty", "metric"], dropna=False)[values].mean().reset_index()
    images.to_csv(OUT / "DIRECTIONAL_SWAP_IMAGES.csv", index=False)
    buildings = images.groupby(["current_difficulty", "building", "metric"], dropna=False)[values].mean().reset_index()
    summary = buildings.groupby(["current_difficulty", "metric"]).agg(
        buildings=("building", "nunique"), net_C_minus_B=("net_C_minus_B", "mean"),
        extra_abs=("extra_abs", "mean"), positive_buildings=("net_C_minus_B", lambda x: int((x > 0).sum()))).reset_index()
    counts = images.groupby(["current_difficulty", "metric"]).agg(
        images=("image", "nunique"), positive_images=("net_C_minus_B", lambda x: int((x > 0).sum())),
        negative_images=("net_C_minus_B", lambda x: int((x < 0).sum()))).reset_index()
    summary = summary.merge(counts, on=["current_difficulty", "metric"], validate="one_to_one")
    old = pd.read_csv(EXCHANGE / "difficulty/exchange_difficulty_core.csv")
    old = old[old.condition_id.eq(cid)].set_index("current_difficulty")
    for row in summary.itertuples():
        if row.metric == "B8L2_no_direction":
            continue
        assert abs(row.net_C_minus_B - old.loc[row.current_difficulty, f"net_{row.metric}"]) < 1e-9
        if row.metric == "B8L2":
            assert row.images == old.loc[row.current_difficulty, "net_B8L2_images"]
    summary.to_csv(OUT / "DIRECTIONAL_SWAP_SUMMARY.csv", index=False)
    print("directional", len(event), len(images), flush=True)


def original_policy_domain_audit() -> None:
    original = pd.read_csv(POP / "stability_rebuilt_20261023/results/POLICY_EARLY_IMAGE_REBUILT.csv",
                           usecols=["pool_id", "condition", "layer", "pool_n", "policy"])
    original = original[(original.condition == "manual") & (original.layer == "ordinary_manual") & (original.pool_n >= 20)]
    common = original.groupby("pool_id").policy.nunique()
    pools = set(common[common.eq(4)].index)
    assert len(pools) == 157
    columns = ["pool_id", "path_id", "replicate", "policy", "k", "team_key", "paired_for_policy",
               "image", "building", "condition", "layer", "difficulty", "pool_n"]
    prefix = pd.read_csv(POP / "stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz", usecols=columns)
    prefix = prefix[prefix.pool_id.isin(pools) & prefix.paired_for_policy & prefix.k.ge(3) &
                    prefix.k.le(prefix.pool_n // 2)].copy()
    assert prefix.policy.nunique() == 5
    source = read_scalars(POP / "results/ENDPOINT_SCALARS.csv.gz", set(prefix.team_key))
    for metric in ("B8L2", "D10", "iou_2d", "IoU3D100", "S_bottom_deg", "dir", "Hmean", "Hcenter", "B8L2_no_direction"):
        prefix[metric] = prefix.team_key.map(source[metric])
    natural = prefix[prefix.policy.eq("natural_random")]
    priority = prefix[~prefix.policy.eq("natural_random")]
    pairs = priority.merge(natural, on=["pool_id", "replicate", "k"], suffixes=("_priority", "_natural"), validate="many_to_one")
    assert pairs.pool_id.nunique() == 157 and pairs.groupby(["pool_id", "policy_priority", "k"]).size().eq(8).all()
    # Every reported metric is compared on the same paired paths with formal Q at both ends.
    pairs = pairs[pairs.B8L2_priority.notna() & pairs.B8L2_natural.notna()].copy()
    paired_paths = len(pairs)
    pieces = []
    for metric in ("B8L2", "D10", "iou_2d", "IoU3D100", "S_bottom_deg", "dir", "Hmean", "Hcenter", "B8L2_no_direction"):
        a, b = pairs[f"{metric}_priority"], pairs[f"{metric}_natural"]
        d = pairs.loc[a.notna() & b.notna(), ["pool_id", "image_priority", "building_priority", "difficulty_priority",
                                             "policy_priority", "k", "replicate", "path_id_priority", "path_id_natural",
                                             "team_key_priority", "team_key_natural"]].copy()
        d["metric"] = metric
        d["delta"] = (a[a.notna() & b.notna()] - b[a.notna() & b.notna()]).to_numpy()
        pieces.append(d)
    detail = pd.concat(pieces, ignore_index=True)
    detail.to_csv(OUT / "POLICY_ORIGINAL_COMMON_PATHS.csv.gz", index=False, compression="gzip")
    by_k = detail.groupby(["pool_id", "image_priority", "building_priority", "difficulty_priority", "policy_priority", "k", "metric"]).agg(
        paired_paths=("replicate", "nunique"), mean_delta=("delta", "mean")).reset_index()
    by_k.to_csv(OUT / "POLICY_ORIGINAL_COMMON_K.csv", index=False)
    by_image = by_k.groupby(["pool_id", "image_priority", "building_priority", "difficulty_priority", "policy_priority", "metric"]).agg(
        valid_k=("k", "nunique"), paired_paths=("paired_paths", "sum"), mean_delta=("mean_delta", "mean")).reset_index()
    by_image.to_csv(OUT / "POLICY_ORIGINAL_COMMON_IMAGES.csv", index=False)
    summary = by_image.groupby(["policy_priority", "metric"]).agg(
        images=("image_priority", "nunique"), buildings=("building_priority", "nunique"),
        image_equal_mean=("mean_delta", "mean"), positive_images=("mean_delta", lambda x: int((x > 0).sum())),
        negative_images=("mean_delta", lambda x: int((x < 0).sum())), valid_k=("valid_k", "sum"),
        paired_paths=("paired_paths", "sum")).reset_index()
    old = pd.read_csv(POP / "stability_rebuilt_20261023/results/KEY_POLICY_EARLY_EFFECTS.csv")
    old = old[(old.condition == "manual") & (old.layer == "ordinary_manual") & (old.policy_support == "common_four_policy_pools") &
              (old.metric == "paired_Q_delta") & (old.weighting == "image_equal") & (old.resampling == "path_resampling_fixed_images")]
    for row in summary[summary.metric.eq("B8L2")].itertuples():
        expected = old.loc[old.policy.eq(row.policy_priority), "estimate"].iloc[0]
        assert row.images == 157 and abs(row.image_equal_mean - expected) < 1e-9, (row.policy_priority, row.image_equal_mean, expected)
    support = summary.pivot(index="policy_priority", columns="metric", values="paired_paths")
    assert support.nunique(axis=1).eq(1).all(), "A reported metric lacks the common formal-Q path support"
    summary.to_csv(OUT / "POLICY_ORIGINAL_COMMON_SUMMARY.csv", index=False)
    print("original policy", paired_paths, len(detail), flush=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    swap_audit()
    prefix_audit()
    directional_difficulty_audit()
    original_policy_domain_audit()


if __name__ == "__main__":
    main()
