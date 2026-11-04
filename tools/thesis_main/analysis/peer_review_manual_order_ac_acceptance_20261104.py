"""Independent peer review of the AC sign-reversal acceptance.

No fusion/scoring/selection is performed and the AC producer is not imported.
This writes only manual_order_acceptance_20261104/ac_peer.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from fractions import Fraction
from functools import lru_cache
import gzip
import hashlib
import json
import math
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "research/fusion/manual_order_acceptance_20261104"
AC = BASE / "ac"
OUT = BASE / "ac_peer"
CACHE = AC / "source_cache"
OLD = ROOT / "research/fusion/manual_order_impact_20261104/ac"
GROUP = ["analysis_view", "scope", "condition", "layer", "method", "role_direction", "n_condition", "m_condition"]
CHECKS = []


def save(frame, name):
    (OUT / name).parent.mkdir(parents=True, exist_ok=True)
    data = pd.DataFrame(frame).to_csv(index=False).encode("utf-8-sig")
    if name.endswith(".gz"):
        data = gzip.compress(data, mtime=0)
    (OUT / name).write_bytes(data)


def record(name, passed, **detail):
    assert bool(passed), (name, detail)
    CHECKS.append(dict(check=name, passed=True, **detail))


def normalized(value):
    if pd.isna(value):
        return ""
    if isinstance(value, (bool, np.bool_)):
        return str(bool(value)).lower()
    try:
        return format(float(value), ".12g")
    except (TypeError, ValueError):
        return str(value)


def condition(frame, criteria):
    keep = pd.Series(True, index=frame.index)
    for key, value in criteria.items():
        keep &= frame[key].map(normalized).eq(normalized(value))
    return frame[keep].copy()


@lru_cache(maxsize=30)
def read(path):
    return pd.read_csv(path, low_memory=False)


def patch(before, after, keys):
    before = before.copy()
    bk = before[keys].apply(lambda r: tuple(map(normalized, r)), axis=1)
    ak = after[keys].apply(lambda r: tuple(map(normalized, r)), axis=1)
    assert bk.is_unique and ak.is_unique
    index = {key: i for i, key in bk.items()}
    accepted = ak.map(lambda key: key in index)
    positions = [index[key] for key in ak[accepted]]
    before.loc[positions, after.columns] = after.loc[accepted].to_numpy()
    return before


def exact_weights(frame, hierarchy):
    """Assign unit mass top-down; returned weights are exact Fractions."""
    rows = frame.to_dict("records")
    result = {}

    def descend(items, level, mass):
        if level == len(hierarchy):
            for item in items:
                assert item["event_id"] not in result
                result[item["event_id"]] = mass / len(items)
            return
        groups = defaultdict(list)
        for item in items:
            groups[tuple(normalized(item[k]) for k in hierarchy[level])].append(item)
        for child in groups.values():
            descend(child, level+1, mass / len(groups))

    if rows:
        descend(rows, 0, Fraction(1))
        assert sum(result.values(), Fraction(0)) == 1
    return result


def main_q_pools():
    cols = GROUP + ["pool_id", "image", "building", "B8L2_CA__mean", "B8L2_CA__valid_pairs", "registered_pairs"]
    subset_path = OUT / "inputs/MAIN_Q_REVIEW_POOLS.csv.gz"
    if subset_path.exists():
        original = pd.read_csv(subset_path, dtype={k: str for k in GROUP})
    else:
        source = CACHE / "POOL_CONDITION_EFFECTS.csv.gz"
        original = pd.read_csv(source, usecols=cols, dtype={k: str for k in GROUP})
        q = read(AC / "Q_REVERSALS.csv")
        wanted = {tuple(normalized(json.loads(row.source_keys)[k]) for k in GROUP)
                  for row in q[q.family.eq("main")].itertuples()}
        identities = original[GROUP].apply(lambda row: tuple(map(normalized, row)), axis=1)
        original = original[identities.isin(wanted)].copy()
        save(original, "inputs/MAIN_Q_REVIEW_POOLS.csv.gz")
        (OUT / "inputs/MAIN_Q_SOURCE_EXTRACTION.json").write_text(json.dumps(dict(
            source="research/workers/personnel_ac_v21_20261030/stage05_main/POOL_CONDITION_EFFECTS.csv.gz",
            frozen_commit="ac395e703d1fef573d1ef3e105df0286d62a0468",
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            extracted_rows=len(original), selected_complete_conditions=len(wanted),
            selection="all registered pools in every main Q reversal condition, not only the changed nine pools",
            extracted_sha256=hashlib.sha256(subset_path.read_bytes()).hexdigest()), indent=2)+"\n")
    info = json.loads((OUT / "inputs/MAIN_Q_SOURCE_EXTRACTION.json").read_text())
    assert hashlib.sha256(subset_path.read_bytes()).hexdigest() == info["extracted_sha256"]
    assisted_patch = pd.read_csv(OLD / "AFFECTED_POOLS_ASSISTED.csv.gz", usecols=cols, dtype={k: str for k in GROUP})
    revised = patch(original, assisted_patch, GROUP + ["pool_id", "image", "building"])
    return original, revised


def verify_building_only_cases(pools):
    cases = [
        ("other_OPPSTRUCT_external_building_flip", "OPPSTRUCT_K3", "whole_unequal_all_external_background"),
        ("other_TARGETK3_zeroD_building_flip", "TARGET_DSTRUCT_K3", "whole_unequal_no_background"),
    ]
    images, source_rows, summaries = [], [], []
    for case, method, view in cases:
        criteria = dict(scope="other_admitted", condition="manual", layer="ordinary_manual", method=method,
                        analysis_view=view, role_direction="1->2")
        values = []
        for version, source in zip(["automatic", "assisted"], pools):
            pool = condition(source, criteria)
            image = pool.groupby(["image", "building"], dropna=False)["B8L2_CA__mean"].mean().dropna().reset_index()
            building = image.groupby("building")["B8L2_CA__mean"].mean()
            row = dict(case=case, version=version, method=method, analysis_view=view,
                       image_mean=image.B8L2_CA__mean.mean(), building_balanced_mean=building.mean(),
                       images=len(image), buildings=len(building), valid_pairs=int(pool.B8L2_CA__valid_pairs.sum()))
            summaries.append(row)
            values.append(row)
            images.append(image.assign(case=case, version=version))
            source_rows.append(pool.assign(case=case, version=version))
        record(case, values[0]["image_mean"] > 0 and values[1]["image_mean"] > 0 and
               values[0]["building_balanced_mean"] > 0 and values[1]["building_balanced_mean"] < 0)
    save(pd.concat(images), "BUILDING_ONLY_FLIP_IMAGE_DETAILS.csv")
    save(pd.concat(source_rows), "BUILDING_ONLY_FLIP_POOL_DETAILS.csv")
    save(summaries, "BUILDING_ONLY_FLIP_SUMMARIES.csv")


def verify_exact_aliases(pools):
    # The second pure-class pool was not among the nine changed pools. Retrieve
    # its immutable original shard once so aliases are checked on the COMPLETE
    # 16-event registered support, rather than only their six newly valid rows.
    extra = OUT / "source_cache/rPc6DW4iMge-22__manual__other_space_11.csv.gz"
    data = extra.read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    record("unaffected_pure_pool_source_git_blob", blob == "b112d1ea392067a6ff4fff5db6133de79391bab6", sha=blob)
    names = [extra.name, "wc2JMjhGNzB-26__manual__other_space_25.csv.gz"]
    columns = ["event_id", "physical_pair_id", "pool_id", "image", "building", "method", "scope", "condition", "layer",
               "n", "m", "D_n", "source_class", "target_class", "source_role_rank", "target_role_rank",
               "equal_team_size", "pure_cross_class_blocks", "A_team_key", "C_team_key", "D_workers", "X_workers", "Z_workers",
               "A_B8L2", "C_B8L2", "B8L2_CA"]
    original = pd.concat([pd.read_csv(extra, usecols=columns),
                          pd.read_csv(CACHE / "original_metric_shards" / names[1], usecols=columns)], ignore_index=True)
    revised = pd.concat([pd.read_csv(extra, usecols=columns),
                         pd.read_csv(OLD / "metric_shards" / names[1], usecols=columns)], ignore_index=True)
    criteria = dict(method="V21_DSTRUCT_RAW3_K3", scope="other_admitted", condition="manual", layer="ordinary_manual",
                    n=4, m=4, D_n=0, source_role_rank=1, target_role_rank=2)
    frames = [condition(d, criteria) for d in [original, revised]]
    ids = set(frames[0].event_id)
    record("pure_alias_full_registration", len(ids) == len(frames[0]) == len(frames[1]) == 16 and
           ids == set(frames[1].event_id), registered_events=len(ids))
    wanted_pools = set(frames[0].pool_id)
    for source in pools:
        for view in ["A_fixed_n_pure_class", "whole_equal_fixed_n_pure_class", "whole_equal_fixed_n_all_m_pure_class"]:
            pool = condition(source, dict(scope="other_admitted", condition="manual", layer="ordinary_manual",
                                          method="V21_DSTRUCT_RAW3_K3", role_direction="1->2", n_condition=4, analysis_view=view))
            assert set(pool.pool_id) == wanted_pools and int(pool.registered_pairs.sum()) == 16
    linkcols = ["event_id", "pool_id", "design_family", "background_profile", "n", "m", "method"]
    links_path = OUT / "inputs/RAW3_ALIAS_COMPLETE_POOL_LINKS.csv.gz"
    if links_path.exists():
        links = pd.read_csv(links_path)
    else:
        source = CACHE / "DESIGN_LINKS.csv.gz"
        pieces = []
        for chunk in pd.read_csv(source, usecols=linkcols, chunksize=100000, low_memory=False):
            pieces.append(chunk[chunk.pool_id.isin(wanted_pools)])
        links = pd.concat(pieces, ignore_index=True)
        save(links, "inputs/RAW3_ALIAS_COMPLETE_POOL_LINKS.csv.gz")
        (OUT / "inputs/RAW3_ALIAS_LINK_EXTRACTION.json").write_text(json.dumps(dict(
            source="research/workers/personnel_ac_v21_20261030/stage01_registered/DESIGN_LINKS.csv.gz",
            frozen_commit="ac395e703d1fef573d1ef3e105df0286d62a0468",
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            extracted_rows=len(links), complete_pool_ids=sorted(wanted_pools),
            extracted_sha256=hashlib.sha256(links_path.read_bytes()).hexdigest()), indent=2)+"\n")
    info = json.loads((OUT / "inputs/RAW3_ALIAS_LINK_EXTRACTION.json").read_text())
    assert hashlib.sha256(links_path.read_bytes()).hexdigest() == info["extracted_sha256"]
    for family in ["A_equal_AC", "B_equal_whole_class"]:
        d = links[links.design_family.eq(family) & links.background_profile.fillna("neutral_members_0").eq("neutral_members_0")]
        selected = set(d.event_id) & ids
        record("pure_alias_membership_"+family, selected == ids, selected_events=len(selected))
    panels = read(OLD / "sensitivity/member_variability_v2/automatic/SOURCE_ROWS.csv.gz")
    panel = condition(panels, {k: v for k, v in criteria.items() if k in panels})
    panel = panel[panel.panel_kind.eq("class_count_preserving_members_D_not_fixed") & panel.role_direction.eq("1->2")]
    panel_ids = {eid for text in panel.event_ids for eid in str(text).split("|")}
    record("pure_alias_member_panel_full_ids", panel_ids == ids and len(panel) == 2)

    semantic_aliases = [
        ("A_fixed_n_pure_class", [("building", "image"), ("pool_id",)]),
        ("whole_equal_fixed_n_pure_class", [("building", "image"), ("pool_id",)]),
        ("whole_equal_fixed_n_all_m_pure_class", [("building", "image"), ("pool_id",)]),
        ("MEMBER_PANELS_mean", [("building", "image"), ("pool_id",)]),
        ("funnel_1/3->2/3", [("pool_id",), ("X_workers", "Z_workers")]),
    ]
    weight_rows, alias_rows = [], []
    for side, frame in zip(["automatic", "assisted"], frames):
        valid = frame[frame.B8L2_CA.notna()]
        record("pure_alias_support_"+side, len(valid) == (7 if side == "automatic" else 13))
        baseline = exact_weights(valid, semantic_aliases[0][1])
        # Each image is one pool and each valid building is one image in this
        # specific cohort; image- and building-balanced means are exact aliases.
        building = exact_weights(valid, [("building",), ("image",), ("pool_id",)])
        record("pure_alias_building_image_weights_"+side, baseline == building)
        for label, hierarchy in semantic_aliases:
            weights = exact_weights(valid, hierarchy)
            record("pure_alias_exact_weights_"+side+"/"+label, weights == baseline)
            estimate = math.fsum(float(weights[r.event_id])*r.B8L2_CA for r in valid.itertuples())
            fingerprint = hashlib.sha256(json.dumps(sorted((eid, str(w)) for eid, w in weights.items())).encode()).hexdigest()
            alias_rows.append(dict(alias=label, version=side, registered_events=len(frame), valid_events=len(valid),
                                   valid_pools=valid.pool_id.nunique(), valid_images=valid.image.nunique(),
                                   valid_buildings=valid.building.nunique(), effect=estimate,
                                   full_registered_event_set_sha256=hashlib.sha256("|".join(sorted(ids)).encode()).hexdigest(),
                                   complete_valid_event_weights_sha256=fingerprint, same_full_cohort_and_weights=True))
            for r in frame.itertuples():
                weight_rows.append(dict(alias=label, version=side, event_id=r.event_id, physical_pair_id=r.physical_pair_id,
                                        pool_id=r.pool_id, image=r.image, building=r.building,
                                        A_team_key=r.A_team_key, C_team_key=r.C_team_key,
                                        A_Q=r.A_B8L2, C_Q=r.C_B8L2, delta_Q=r.B8L2_CA,
                                        weight=float(weights.get(r.event_id, Fraction(0))),
                                        exact_weight=str(weights.get(r.event_id, Fraction(0)))))
    save(alias_rows, "RAW3_PURE_CLASS_EXACT_ALIAS_VERIFICATION.csv")
    save(weight_rows, "RAW3_PURE_CLASS_COMPLETE_EVENT_WEIGHTS.csv")
    # The two funnel labels select the same complete registered pool cells;
    # matching only the set of newly evaluable events would not prove this.
    f0 = read(CACHE / "POOL_DIRECTION_N_M_METRIC_SUPPORT.csv.gz")
    f1 = patch(f0, read(OLD / "funnel/POOL_DIRECTION_N_M_ASSISTED_PATCH.csv.gz"),
               ["pool_id", "method", "n", "m", "source_class", "target_class", "metric"])
    funnel_rows = []
    for version, table in zip(["automatic", "assisted"], [f0, f1]):
        all_directions = condition(table, dict(scope="primary", method="OPPSTRUCT_K3", n=28, m=1, metric="B8L2"))
        named = all_directions[all_directions.role_direction.eq("1/3->3/3")]
        record("funnel_named_ALL_complete_cohort_"+version,
               len(all_directions) == len(named) == 2 and all_directions.index.equals(named.index) and
               int(named.registered_events.sum()) == 14)
        for label, selected in [("1/3->3/3", named), ("ALL_CANONICAL_DIRECTIONS", all_directions)]:
            selected = selected.copy()
            selected["version"] = version
            selected["display_role_direction"] = label
            funnel_rows.append(selected)
    save(pd.concat(funnel_rows, ignore_index=True), "FUNNEL_N28_M1_EXACT_ALIAS_COHORT.csv")
    x8_name = "x8F5xyUWy9e-08__manual__0b13997fd3.csv.gz"
    x8 = []
    for version, path in [("automatic", CACHE / "original_metric_shards" / x8_name),
                          ("assisted", OLD / "metric_shards" / x8_name)]:
        d = pd.read_csv(path, usecols=columns+["A_nodes", "C_nodes", "A_score_status", "C_score_status"])
        d = condition(d, dict(method="OPPSTRUCT_K3", scope="primary", condition="manual", layer="ordinary_manual",
                              n=28, m=1, source_role_rank=1, target_role_rank=3))
        assert len(d) == 7
        x8.append(d.assign(version=version))
    record("funnel_new_pool_six_pairs_one_node_failure",
           x8[0].A_B8L2.isna().all() and x8[1].A_B8L2.notna().all() and
           x8[1].A_team_key.nunique() == 1 and x8[1].B8L2_CA.notna().sum() == 6 and
           x8[1].loc[x8[1].B8L2_CA.isna(), "C_nodes"].eq(3).all() and
           x8[1].loc[x8[1].B8L2_CA.isna(), "C_score_status"].eq("below_four").all())
    block_mean = x8[1].groupby(["X_workers", "Z_workers"], dropna=False).B8L2_CA.mean().mean()
    pool_mean = pd.concat(funnel_rows).query("version == 'assisted'")
    pool_mean = pool_mean[pool_mean.pool_id.eq(x8_name[:-7])].mean_change.iloc[0]
    record("funnel_new_pool_block_weighted_value", abs(block_mean-pool_mean) < 1e-9,
           reconstructed_new_pool_mean=block_mean)
    save(pd.concat(x8, ignore_index=True), "FUNNEL_N28_M1_X8_ALL_EVENTS.csv")


def row_identity(family, statistic, mapping):
    return family, statistic, tuple(sorted((k, normalized(v)) for k, v in mapping.items()))


def verify_catalogue():
    """Enumerate every saved sign reversal independently from paired tables."""
    actual = read(AC / "ALL_EFFECT_MEAN_REVERSALS.csv.gz")
    expected = {}

    def add(family, old, new, keys, stats):
        assert not old.duplicated(keys).any() and not new.duplicated(keys).any()
        joined = old.merge(new, on=keys, how="outer", suffixes=("_0", "_1"), indicator=True, validate="one_to_one")
        assert joined._merge.eq("both").all(), family
        for statistic in stats:
            a, b = joined[statistic+"_0"], joined[statistic+"_1"]
            eligible = (a.abs() > 1e-7) & (b.abs() > 1e-7) & (np.sign(a) != np.sign(b)) & a.notna() & b.notna()
            for _, row in joined[eligible].iterrows():
                ident = row_identity(family, statistic, {k: row[k] for k in keys})
                assert ident not in expected
                expected[ident] = float(row[statistic+"_0"]), float(row[statistic+"_1"])

    def changed(family, path, keys, stats):
        d = read(OLD / path)
        left = d[keys].copy()
        right = left.copy()
        for stat in stats:
            left[stat], right[stat] = d["automatic_"+stat], d["assisted_"+stat]
        add(family, left, right, keys, stats)

    add("main", read(OLD / "main_automatic_reproduced/CONDITION_METRIC_SUMMARY.csv.gz"),
        read(OLD / "main_assisted_affected_conditions/CONDITION_METRIC_SUMMARY.csv.gz"),
        GROUP+["metric"], ["image_mean", "building_balanced_mean"])
    add("context", read(OLD / "context_common/automatic/FROZEN_CONTEXT_EFFECT_SUMMARY.csv.gz"),
        read(OLD / "context_common/assisted/FROZEN_CONTEXT_EFFECT_SUMMARY.csv.gz"),
        GROUP+["context_axis", "context_value", "metric"], ["image_mean", "building_balanced_mean"])
    common = ["scope", "condition", "layer", "method"]
    specs = {
        "MEMBER_PANELS": common+["panel_kind", "role_direction", "n", "m"],
        "BACKGROUND_CHANGES": common+["comparison", "background_profile", "role_direction", "n", "m"],
        "FIXED_BLOCK_BACKGROUND_STEPS": common+["role_direction", "n_from", "n_to", "m_from", "m_to"],
        "FIXED_A_REPLACEMENT_STEPS": common+["role_direction", "n_from", "m_from", "m_to"],
        "UNEQUAL_DECOMPOSITION": common+["role_direction", "background_profile"],
        "COMPLETE_COALITIONS": common+["role_direction", "number_condition", "unknown_background_included"],
        "SAMPLING_BATCHES": common+["role_direction", "n", "m"],
    }
    left = read(OLD / "sensitivity/automatic_affected_conditions/SENSITIVITY_IMAGE_BALANCED_SUMMARY_V2.csv.gz")
    right = read(OLD / "sensitivity/assisted_affected_conditions/SENSITIVITY_IMAGE_BALANCED_SUMMARY_V2.csv.gz")
    for table, keys in specs.items():
        add("sensitivity", left[left.analysis_table.eq(table)], right[right.analysis_table.eq(table)],
            keys+["analysis_table", "metric"], ["image_mean", "building_balanced_mean"])
    add("three_leg", read(OLD / "sensitivity/three_leg_common_support_v2/automatic/COMMON_VALID_THREE_LEG_IMAGE_SUMMARY.csv.gz"),
        read(OLD / "sensitivity/three_leg_common_support_v2/assisted/COMMON_VALID_THREE_LEG_IMAGE_SUMMARY.csv.gz"),
        common+["role_direction", "background_profile", "parent_background_stratum", "metric"],
        [part+"_"+weight for part in ["total", "equal", "addition"] for weight in ["image_mean", "building_balanced_mean"]])
    add("exact_background", read(OLD / "sensitivity/exact_outside_background/automatic/EXACT_NEUTRAL_OUTSIDE_IMAGE_BALANCED_SUMMARY.csv.gz"),
        read(OLD / "sensitivity/exact_outside_background/assisted/EXACT_NEUTRAL_OUTSIDE_IMAGE_BALANCED_SUMMARY.csv.gz"),
        common+["role_direction", "n", "m", "background_change_type", "metric"],
        ["image_mean", "building_balanced_mean"])
    changed("method_comparison", "context_common/COMMON_POOL_METHOD_COMPARISON_CHANGES.csv.gz",
            ["method_left", "method_right", "n", "m", "metric"], ["right_minus_left_absolute_change"])
    changed("funnel", "funnel/FUNNEL_CHANGES.csv.gz", ["method", "scope", "role_direction", "n", "m", "metric"], ["mean_change"])
    changed("strict_bridge", "strict_bridge/STRICT_BRIDGE_SUMMARY_CHANGES.csv.gz",
            ["strict_source_family", "new_reference_set", "method", "n", "m", "strict_role_direction", "metric"],
            ["strict_signed_or_distance_mean", "strict_G_A_mean", "strict_G_S_mean"])
    found = {}
    for r in actual.itertuples():
        ident = row_identity(r.family, r.statistic, json.loads(r.source_keys))
        assert ident not in found
        found[ident] = r.reversal_id
        assert ident in expected, ("unmatched_catalogue_row", ident)
        a, b = expected[ident]
        assert abs(a-r.old_effect) < 1e-9 and abs(b-r.expanded_effect) < 1e-9
        expected_unit = "building" if "building" in r.statistic else (
            "pool" if r.family in ["method_comparison", "funnel", "strict_bridge"] else "image")
        assert r.aggregation_unit == expected_unit, (r.reversal_id, r.aggregation_unit, expected_unit)
    record("complete_reversal_catalogue", set(found) == set(expected), rows=len(found))
    save(actual.groupby(["family", "aggregation_unit"], dropna=False).size().rename("catalogue_rows").reset_index(),
         "CATALOGUE_CENSUS_RECHECKED.csv")
    return actual


def complete_q_units(r, side, pools):
    """Read the complete earlier lower-level support for a Q estimand."""
    folder = "automatic" if side == 0 else "assisted"
    keys = json.loads(r.source_keys)
    family, metric = r.family, r.metric
    if family == "main":
        d = condition(pools[side], {k: keys[k] for k in GROUP})
        d = d[["pool_id", "image", "building", metric+"__mean"]].rename(columns={metric+"__mean": "value"})
    elif family == "sensitivity":
        d = read(OLD / f"sensitivity/{folder}_affected_conditions/pool_summaries/affected/{r.analysis_table}.csv.gz")
        d = condition(d, {k: v for k, v in keys.items() if k in d and k != "metric"})
        field = metric+"__pool_mean"
        d = d[["pool_id", "image", "building", field]].rename(columns={field: "value"})
    elif family == "three_leg":
        raw = read(OLD / f"sensitivity/three_leg_common_support_v2/{folder}/SOURCE_ROWS.csv.gz").copy()
        cap = read(CACHE / "POOL_METHOD_CAPACITY.csv.gz").drop_duplicates("pool_id").set_index("pool_id").pool_n
        shared = raw.parent_D_workers.fillna("").map(lambda value: len(value.split("|")) if value else 0)
        union_size = raw.n_small+raw.n_large-shared
        assert (union_size <= raw.pool_id.map(cap)).all()
        raw["parent_background_stratum"] = np.where(shared.eq(0), "zero_D",
            np.where(union_size.eq(raw.pool_id.map(cap)), "all_outside_D", "partial_outside_D"))
        raw = condition(raw, {k: v for k, v in keys.items() if k != "metric"})
        columns = [metric+"__"+leg for leg in ["total", "equal", "addition"]]
        raw = raw[np.isfinite(raw[columns]).all(axis=1)]
        field = metric+"__"+r.statistic.split("_")[0]
        parents = raw.groupby(["pool_id", "image", "building", "parent_contrast_id"], dropna=False)[field].mean().reset_index()
        d = parents.groupby(["pool_id", "image", "building"], dropna=False)[field].mean().reset_index().rename(columns={field: "value"})
    elif family == "exact_background":
        d = read(OLD / f"sensitivity/exact_outside_background/{folder}/EXACT_NEUTRAL_OUTSIDE_POOL_SUMMARY.csv.gz")
        d = condition(d, {k: v for k, v in keys.items() if k != "metric"})
        field = metric+"__pool_mean"
        d = d[["pool_id", "image", "building", field]].rename(columns={field: "value"})
    elif family == "method_comparison":
        original = read(CACHE / "METHOD_POOL_ALL_DIRECTION_EFFECTS.csv.gz")
        d = original
        if side:
            changes = read(OLD / "context_common/METHOD_POOL_ALL_DIRECTION_CHANGES.csv.gz")
            identity = ["pool_id", "image", "building", "method", "n_condition", "m_condition"]
            columns = [c for c in changes if c.startswith("assisted_")]
            changed = changes[identity+columns].rename(columns={c: c[len("assisted_"):] for c in columns})
            d = patch(original, changed, identity)
        d = condition(d, dict(n_condition=r.n, m_condition=r.m))
        field = metric+"__mean_absolute"
        identity = ["pool_id", "image", "building"]
        left = d[d.method.eq(r.method_left)][identity+[field]].rename(columns={field: "left"})
        right = d[d.method.eq(r.method_right)][identity+[field]].rename(columns={field: "right"})
        d = left.merge(right, on=identity, validate="one_to_one")
        d["value"] = d.right-d.left
    elif family == "funnel":
        d = read(CACHE / "POOL_DIRECTION_N_M_METRIC_SUPPORT.csv.gz")
        if side:
            d = patch(d, read(OLD / "funnel/POOL_DIRECTION_N_M_ASSISTED_PATCH.csv.gz"),
                      ["pool_id", "method", "n", "m", "source_class", "target_class", "metric"])
        d = condition(d, {k: v for k, v in keys.items() if k != "role_direction"})
        if r.role_direction != "ALL_CANONICAL_DIRECTIONS":
            d = d[d.role_direction.eq(r.role_direction)]
        d = d.groupby(["pool_id", "image", "building"], dropna=False).mean_change.mean().reset_index().rename(columns={"mean_change": "value"})
    else:
        raise AssertionError(("unexpected_Q_family", family))
    if r.aggregation_unit == "pool":
        u = d[["pool_id", "image", "building", "value"]].rename(columns={"pool_id": "unit_id"})
    else:
        u = d.groupby(["image", "building"], dropna=False).value.mean().reset_index()
        if r.aggregation_unit == "building":
            u = u.groupby("building", dropna=False).value.mean().reset_index()
            u["unit_id"], u["image"] = u.building, ""
        else:
            u["unit_id"] = u.image
    assert u.unit_id.is_unique
    return u


def verify_units_and_traces(catalogue, pools):
    units = read(AC / "REVERSAL_UNIT_CONTRIBUTIONS.csv.gz")
    decomposed = read(AC / "REVERSAL_SUPPORT_DECOMPOSITION.csv.gz").set_index("reversal_id")
    by = {rid: group for rid, group in units.groupby("reversal_id", sort=False)}
    max_error = 0.0
    for r in catalogue.itertuples():
        group = by[r.reversal_id]
        assert group.unit_id.is_unique
        old = group[group.old_value.notna()]
        new = group[group.expanded_value.notna()]
        assert set(old.unit_id) <= set(new.unit_id)
        additions = group[group.old_value.isna() & group.expanded_value.notna()]
        retained = group[group.old_value.notna() & group.expanded_value.notna()]
        m0, m1 = old.old_value.mean(), new.expanded_value.mean()
        within = math.fsum(retained.expanded_value-retained.old_value)/len(new)
        entered = math.fsum(additions.expanded_value-m0)/len(new)
        expected_contribution = np.where(group.expanded_value.notna(), group.expanded_value/len(new), 0)-np.where(group.old_value.notna(), group.old_value/len(old), 0)
        errors = [abs(m0-r.old_effect), abs(m1-r.expanded_effect), abs(within+entered-(m1-m0)),
                  np.max(np.abs(group.contribution_change.to_numpy()-expected_contribution)),
                  np.max(np.abs(group.old_weight-np.where(group.old_value.notna(), 1/len(old), 0))),
                  np.max(np.abs(group.expanded_weight-np.where(group.expanded_value.notna(), 1/len(new), 0))),
                  abs(decomposed.loc[r.reversal_id, "within_original_units_contribution"]-within),
                  abs(decomposed.loc[r.reversal_id, "new_units_composition_contribution"]-entered)]
        assert max(errors) < 1e-9, (r.reversal_id, errors)
        max_error = max(max_error, *errors)
        assert additions.old_value.isna().all()
    record("all_unit_support_contributions", True, reversals=len(catalogue), rows=len(units), maximum_error=max_error)

    # Q rows receive a separate lower-level value/identity check, not merely
    # an algebraic closure check on the newly written contribution table.
    q = catalogue[catalogue.metric.astype(str).str.contains("B8L2")]
    qsource = []
    for r in q.itertuples():
        group = by[r.reversal_id].set_index("unit_id")
        for side, field in enumerate(["old_value", "expanded_value"]):
            expected = complete_q_units(r, side, pools)
            expected = expected[expected.value.notna()].set_index("unit_id")
            actual = group[group[field].notna()]
            assert set(expected.index) == set(actual.index), (r.reversal_id, side, "unit_ids")
            actual = actual.loc[expected.index]
            error = float(np.max(np.abs(actual[field].to_numpy()-expected.value.to_numpy())))
            assert error < 1e-9, (r.reversal_id, side, error)
            assert (actual.building.map(normalized) == expected.building.map(normalized)).all()
            for unit_id, row in expected.iterrows():
                qsource.append(dict(reversal_id=r.reversal_id, version="automatic" if side == 0 else "assisted",
                                    unit_type=r.aggregation_unit, unit_id=unit_id, image=row.image,
                                    building=row.building, value=row.value))
    save(qsource, "Q_REVERSAL_LOWER_LEVEL_VALUES_RECALCULATED.csv.gz")
    record("Q_reversals_from_complete_lower_level_support", True, estimands=len(q), source_units=len(qsource))

    # The event trace must retain canonical identities and both actual endpoint
    # scores, including missing old scores. Cross-family orientation stays in
    # the linked analysis rows and is not silently applied to this raw trace.
    fields = ["event_id", "physical_pair_id", "pool_id", "image", "building", "scope", "method",
              "source_class", "target_class", "source_role_rank", "target_role_rank", "n_A", "n_C", "m_X", "m_Z",
              "D_workers", "X_workers", "Z_workers", "A_team_key", "C_team_key", "A_B8L2", "C_B8L2", "B8L2_CA"]
    raw = [[], []]
    for path in sorted((CACHE / "original_metric_shards").glob("*.csv.gz")):
        raw[0].append(pd.read_csv(path, usecols=fields))
        raw[1].append(pd.read_csv(OLD / "metric_shards" / path.name, usecols=fields))
    raw = [pd.concat(parts, ignore_index=True).set_index("event_id") for parts in raw]
    assert raw[0].index.is_unique and raw[1].index.is_unique and set(raw[0].index) == set(raw[1].index)
    for metric in ["A_B8L2", "C_B8L2", "B8L2_CA"]:
        old, new = raw[0][metric], raw[1].loc[raw[0].index, metric]
        finite = old.notna()
        assert new[finite].notna().all()
        assert np.max(np.abs(old[finite]-new[finite])) < 1e-9
    trace = read(AC / "Q_REVERSAL_EVENT_TEAM_TRACE.csv.gz")
    assert not trace.duplicated(["reversal_id", "event_id"]).any()
    identity = fields[1:-3]
    for row in trace.to_dict("records"):
        eid = row["event_id"]
        old, new = raw[0].loc[eid], raw[1].loc[eid]
        for field in identity:
            assert normalized(row[field]) == normalized(old[field]) == normalized(new[field]), (eid, field)
        for field, scalar in [("A_Q", "A_B8L2"), ("C_Q", "C_B8L2"), ("delta_Q", "B8L2_CA")]:
            for prefix, source in [("original_", old), ("expanded_", new)]:
                actual, expected = row[prefix+field], source[scalar]
                assert pd.isna(actual) == pd.isna(expected)
                if pd.notna(expected):
                    assert abs(actual-expected) < 1e-9
        gained = pd.isna(old.B8L2_CA) and pd.notna(new.B8L2_CA)
        if gained:
            assert row["source_Q_support"] == "newly_evaluable_pair" and pd.isna(row["original_delta_Q"])
        elif pd.notna(old.B8L2_CA):
            assert row["source_Q_support"] == "original_common_pair"
        else:
            assert row["source_Q_support"] == "still_without_pair_Q"
    atoms = read(AC / "Q_REVERSAL_CHANGED_ANALYSIS_ROWS.csv.gz")
    for rid, group in atoms.groupby("reversal_id", sort=False):
        expected = {eid for value in group.event_ids for eid in str(value).split("|") if eid}
        observed = set(trace.loc[trace.reversal_id.eq(rid), "event_id"])
        assert expected == observed
    record("Q_event_trace_identity_and_missing_scores", True, traced_event_references=len(trace),
           unique_events=trace.event_id.nunique(), changed_analysis_rows=len(atoms),
           full_source_metric_events=len(raw[0]))


def verify_final_outputs(pools):
    catalogue = verify_catalogue()
    verify_units_and_traces(catalogue, pools)
    # New-event overlap labels must not be mistaken for complete cohort aliases.
    aliases = read(AC / "Q_REVERSAL_EVIDENCE_ALIASES.csv")
    assert set(aliases.reversal_id) == set(catalogue.loc[catalogue.metric.astype(str).str.contains("B8L2"), "reversal_id"])
    record("new_event_overlap_labels_are_not_independent_trial_counts", True,
           evidence_rows=len(aliases), overlap_sets=aliases.new_event_evidence_set_id.nunique(),
           interpretation="These are overlapping new-event sets. Exact full-cohort aliases are separately proven in RAW3 and funnel tables.")


def verify_raw3_residuals_and_bounds():
    """Check the three unreviewed opponents without inventing orders or Q values.

    This is a small source/coverage audit and a mathematical range calculation,
    separate from the already-passed core numeric acceptance.
    """
    source_manifest = json.loads((OUT / "source_cache/EXTRA_CODE_SOURCE_MANIFEST.json").read_text())
    for entry in source_manifest:
        data = (OUT / "source_cache" / entry["name"]).read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        assert blob == entry["git_blob_sha"], (entry["name"], blob)
    cols = ["event_id", "physical_pair_id", "pool_id", "image", "building", "method", "scope", "condition", "layer",
            "n", "m", "D_n", "source_role_rank", "target_role_rank", "source_class", "target_class",
            "A_team_key", "C_team_key", "A_nodes", "C_nodes", "A_score_status", "C_score_status",
            "A_order_status", "C_order_status", "A_connection_available", "C_connection_available",
            "A_insufficient_nodes", "C_insufficient_nodes", "A_B8L2", "C_B8L2", "B8L2_CA", "D_workers", "X_workers", "Z_workers"]
    extra = OUT / "source_cache/rPc6DW4iMge-22__manual__other_space_11.csv.gz"
    pool_name = "wc2JMjhGNzB-26__manual__other_space_25.csv.gz"
    raw = [pd.concat([pd.read_csv(extra, usecols=cols), pd.read_csv(path / pool_name, usecols=cols)], ignore_index=True)
           for path in [CACHE / "original_metric_shards", OLD / "metric_shards"]]
    select = dict(method="V21_DSTRUCT_RAW3_K3", scope="other_admitted", condition="manual", layer="ordinary_manual",
                  n=4, m=4, D_n=0, source_role_rank=1, target_role_rank=2)
    original, expanded = [condition(frame, select).sort_values("event_id").reset_index(drop=True) for frame in raw]
    assert len(original) == len(expanded) == 16 and original.event_id.equals(expanded.event_id)
    assert original.B8L2_CA.notna().sum() == 7 and expanded.B8L2_CA.notna().sum() == 13
    orders = read(ROOT / "research/fusion/missing_ring_review_20261104/user_order_return/VALIDATED_ENDPOINT_ORDERS.csv.gz")
    references = read(ROOT / "research/fusion/missing_ring_review_20261104/user_order_return/AFFECTED_CURRENT_REFERENCES.csv.gz")
    complete = expanded.copy()
    for field in ["A_B8L2", "C_B8L2", "B8L2_CA", "A_score_status", "C_score_status", "A_connection_available", "C_connection_available"]:
        complete["automatic_"+field] = original[field].to_numpy()
    for arm in ["A", "C"]:
        complete[arm+"_in_confirmed57"] = complete[arm+"_team_key"].isin(orders.team_key)
        complete[arm+"_in_affected_reference_mapping"] = complete[arm+"_team_key"].isin(references.team_key)
    complete["support_origin"] = np.where(complete.automatic_B8L2_CA.notna(), "original_common_pair",
        np.where(complete.B8L2_CA.notna(), "newly_evaluable_pair", "still_unscored_pair"))
    save(complete, "RAW3_PURE_CLASS_FULL16_EVENT_STATUS.csv")
    residual = complete[complete.B8L2_CA.isna()].copy()
    assert len(residual) == 3 and residual.C_score_status.eq("no_connection").all()
    assert residual.C_nodes.ge(4).all() and residual.A_B8L2.notna().all() and residual.C_B8L2.isna().all()
    assert not residual.C_in_confirmed57.any() and not residual.C_in_affected_reference_mapping.any()
    residual["review_interpretation"] = "outside confirmed57; residual no_connection; conditional opportunity coverage remains incomplete"
    save(residual, "RAW3_PURE_CLASS_RESIDUAL_UNSCORED_ENDPOINTS.csv")

    accepted = json.loads((OUT / "source_cache/order_import.json").read_text())["accepted"]
    assert len(accepted) == 33
    records = {r["record"]["team_key"]: r for r in json.loads((OUT / "RAW3_RESIDUAL_FROZEN_ENDPOINT_RECORDS.json").read_text())}
    prepared_manifest = json.loads((OUT / "source_cache/RAW3_PREPARED_SOURCE_MANIFEST.json").read_text())
    prepared = {r["team_key"]: r for r in prepared_manifest}
    diagnostic = read(OUT / "RAW3_RESIDUAL_CURRENT_LINKED_DIAGNOSTIC_CHECKS.csv").set_index("team_key")
    links = read(OUT / "RAW3_RESIDUAL_CURRENT_INVENTORY_LINKS.csv")
    manifests = json.loads((OUT / "source_cache/RAW3_EXISTING_DIAGNOSTIC_EXTRACTION.json").read_text())
    for entry in manifests:
        assert hashlib.sha256((OUT / entry["subset_file"]).read_bytes()).hexdigest() == entry["subset_sha256"]
    known_parts = {e["path"]: e for e in json.loads((OUT / "source_cache/ENDPOINT_PART_DIRECTORY.json").read_text())["entries"]}
    binding_rows = []
    signatures = []
    for row in residual.to_dict("records"):
        key = row["C_team_key"]
        origin = records[key]
        part_path = OUT / "source_cache/endpoint_parts" / Path(origin["source"]).parent.name / Path(origin["source"]).name
        part = part_path.read_bytes()
        assert hashlib.sha1(b"blob "+str(len(part)).encode()+b"\0"+part).hexdigest() == known_parts[origin["source"]]["git_blob_sha"]
        saved = json.loads(gzip.decompress(part).decode().splitlines()[origin["source_line"]-1])
        assert saved == origin["record"] and saved["team_key"] == key
        data = (OUT / "source_cache/prepared" / (prepared[key]["review_id"]+".json.gz")).read_bytes()
        assert hashlib.sha256(data).hexdigest() == prepared[key]["entry_sha256"]
        case = json.loads(gzip.decompress(data))
        assert case["team_key"] == key and len(case["nodes"]) == saved["nodes"] == row["C_nodes"]
        assert case["reference_id"] == saved["reference_id"] and case["reference_version"] == saved["reference_version"]
        assert {r["id"] for r in case["records"]} == set(saved["member_object_ids"])
        supports = saved["node_supports"]
        if isinstance(supports, str): supports = json.loads(supports) if supports.startswith("[") else supports.split("|")
        assert [n["support"] for n in case["nodes"]] == list(map(int, supports))
        assert np.isfinite(np.array([n["points"] for n in case["nodes"]], dtype=float)).all()
        assert saved["score_status"] == "no_connection" and saved["order_status"] == "needs_manual_order"
        signature = sorted(n["points"] for n in case["nodes"])
        exact = {n["feature_id"]: n["points"] for n in case["nodes"]}
        same57 = orders[orders.image.eq(case["image"])]
        previous = [o for o in accepted if o["image"] == case["image"]]
        check_bindings = [json.loads(b) for b in same57.order_binding]
        matches57 = sum(sorted(n["points"] for n in b) == signature for b in check_bindings)
        matches33 = sum(sorted(n["points"] for n in o["order_binding"]) == signature for o in previous)
        id_matches33 = sum({n["feature_id"]: n["points"] for n in o["order_binding"]} == exact for o in previous)
        assert matches57 == matches33 == id_matches33 == 0
        modules = sorted(set(links.loc[links.team_key.eq(key), "module"]))
        # This is the exact 57-case queue rule in the frozen closeout source.
        queue_modules = {"current_half", "current_same_room_half", "q_only", "changed_alliances"}
        assert not set(modules) & queue_modules and "natural_ordinary_manual_main" not in modules
        assert diagnostic.loc[key, "disposition"] == "current_no_source_ring_nodes_ready"
        assert diagnostic.loc[key, "exact_existing_orders"] == diagnostic.loc[key, "coordinate_existing_orders"] == 0
        signatures.append(json.dumps([case["image"], case["reference_id"], signature], sort_keys=True))
        binding_rows.append(dict(event_id=row["event_id"], team_key=key, review_id=case["review_id"], image=case["image"],
            nodes=len(case["nodes"]), frozen_coordinates_available=True, fixed_votes_and_members_bound=True,
            reference_id=case["reference_id"], reference_version=case["reference_version"],
            same_image_confirmed57=len(same57), confirmed57_same_image_node_counts="|".join(str(len(b)) for b in check_bindings),
            same_image_legacy33=len(previous), exact_coordinate_matches_confirmed57=matches57,
            exact_coordinate_matches_legacy33=matches33, exact_id_and_coordinate_matches_legacy33=id_matches33,
            current_modules="|".join(modules), frozen_diagnostic_disposition=diagnostic.loc[key, "disposition"],
            why_not_in_targeted57="Only AC and/or extra-target natural references; neither selected by the frozen 57-case queue rule",
            conclusion="No reusable order in the confirmed57 or legacy33; new human judgment needed only if complete endpoint effects are requested",
            prepared_source=prepared[key]["archive"]+"::"+prepared[key]["entry"], endpoint_source=origin["source"], endpoint_source_line=origin["source_line"]))
    assert len(set(signatures)) == 3
    save(binding_rows, "RAW3_RESIDUAL_ORDER_REUSE_CHECK.csv")

    # Fixed ordering is explicit so q0/q1/q2 can never be mistaken for scores
    # belonging to an arbitrary row order.
    event_order = ["a63415f78c6f8edd39b5ac22", "554c5483aab8ad2fdb45b595", "dfd1596297c00f22af034a1d"]
    missing = residual.set_index("event_id").loc[event_order]
    mapping = [dict(variable=f"q{i}", event_id=eid, C_team_key=row.C_team_key, image=row.image,
                    fixed_A_Q=float(row.A_B8L2), current_C_Q=None, current_state="no_connection", nodes=int(row.C_nodes))
               for i, (eid, row) in enumerate(missing.iterrows())]
    scenarios = []
    for scenario_id, values in enumerate(product([None, 0.0, 100.0], repeat=3), 1):
        frame = expanded.copy()
        result = dict(scenario_id=scenario_id)
        for i, (eid, value) in enumerate(zip(event_order, values)):
            result[f"q{i}"] = value
            result[f"q{i}_state"] = "still_unevaluable" if value is None else ("hypothetical_legal_lower_bound" if value == 0 else "hypothetical_legal_upper_bound")
            result[f"q{i}_team_key"] = mapping[i]["C_team_key"]
            if value is not None:
                keep = frame.event_id.eq(eid)
                frame.loc[keep, "B8L2_CA"] = value-float(frame.loc[keep, "A_B8L2"].iloc[0])
        pool_values = frame.groupby("pool_id").B8L2_CA.mean()
        result.update(effect=float(pool_values.mean()), scored=int(frame.B8L2_CA.notna().sum()),
                      registered_events=16, evaluated_pools=len(pool_values),
                      scenario="mathematical missing-score bound, NOT measured Q; blank q means still unevaluable")
        scenarios.append(result)
    table = pd.DataFrame(scenarios)
    assert len(table) == 27 and table.effect.lt(0).all()
    save(table, "RAW3_PURE_CLASS_MISSING_Q_BOUNDS_SCENARIOS.csv")
    original_effect = float(original.groupby("pool_id").B8L2_CA.mean().mean())
    current_effect = float(expanded.groupby("pool_id").B8L2_CA.mean().mean())
    count = expanded.groupby("pool_id").size()
    assert count.eq(8).all() and len(count) == 2
    numerator_constant = float(expanded.B8L2_CA.sum()-missing.A_B8L2.sum())
    full = table[table.scored.eq(16)]
    assert abs(full.effect.min()-numerator_constant/16) < 1e-12
    assert abs(full.effect.max()-(numerator_constant+300)/16) < 1e-12
    receipt = dict(status="PASS_WITH_EXPLICIT_OPPORTUNITY_LIMIT", frozen_commit="ac395e703d1fef573d1ef3e105df0286d62a0468",
        condition=select, original_evaluable_events=7, expanded_evaluable_events=13, registered_events=16,
        original_effect=original_effect, expanded_effect=current_effect, aggregation="two pools/images/buildings equally weighted; events equal within each pool",
        missing_score_variables=mapping, legal_Q_range=[0, 100],
        range_source="research/quality/quality_ab_feedback_handoff_20261015/prior_AB/src/working_models.py",
        range_source_git_blob="fb9c5788f4e2ab5035343a45426ca966eb6bc4ac",
        range_proof="checked() requires I in [0,1] and nonnegative losses. score=100*I/(I+pooled+I*(g+l)); pooled,g,l are nonnegative; I=0 returns 0. Hence 0<=Q<=100 for an available score.",
        scenario_count=27, support_subsets=8, full16_boundary_combinations=8,
        scenario_extremum_proof="Each fixed evaluability subset has a mean affine in its available unknown C scores with positive weights; its extrema lie at the 0/100 vertices. The 3^3 enumeration covers all eight evaluability subsets and all their vertices.",
        all_subsets_effect_lower=float(table.effect.min()), all_subsets_effect_upper=float(table.effect.max()),
        complete16_effect_lower=float(full.effect.min()), complete16_effect_upper=float(full.effect.max()),
        complete16_formula=f"({numerator_constant:.15g} + q0 + q1 + q2) / 16",
        unavailable_old_Q_imputed=False, available_score_rows_changed=False,
        hypothetical_0_and_100_are_observations=False, blank_q_semantics="endpoint remains unevaluable and is omitted from this metric-specific support",
        negative_direction_survives_all_legal_completions=True,
        does_not_establish=["actual scores of the three missing C endpoints", "an exact complete16 mean", "equal human-treatment opportunity", "validity of an arbitrary new order", "repairability outside this fixed condition"],
        reusability=dict(confirmed57_matches=0, legacy33_matches=0, distinct_residual_geometries=3),
        existing_order_missed_propagation_found=False,
        complete_opportunity_coverage=False,
        human_judgment_required_for_this_direction_verdict=False,
        new_orders_generated=0, new_fusions=0, new_endpoint_scores=0,
        additional_global_opportunity_audit="Separately owned by the AC acceptance producer; this receipt covers only this exact RAW3 condition")
    (OUT / "RAW3_RESIDUAL_AND_BOUNDS_CHECKS.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true", help="Build source-level special-case and alias evidence before the AC producer finishes")
    parser.add_argument("--residual-only", action="store_true", help="Check the three RAW3 residual bindings and legal-Q bounds without rerunning the passed core review")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.residual_only:
        result = verify_raw3_residuals_and_bounds()
        print(json.dumps(dict(status=result["status"], scenarios=result["scenario_count"],
                             effect_lower=result["all_subsets_effect_lower"], effect_upper=result["all_subsets_effect_upper"])))
        return
    pools = main_q_pools()
    verify_building_only_cases(pools)
    verify_exact_aliases(pools)
    if not args.prepare:
        verify_final_outputs(pools)
    save(CHECKS, "PEER_CHECKS.csv")
    (OUT / "PEER_CHECKS.json").write_text(json.dumps(dict(
        status="PASS_PREPARATION" if args.prepare else "PASS", checks=CHECKS,
        new_teams=0, new_fusions=0, new_endpoint_scores=0,
        scope="Independent source, identity, aggregation, support, and alias review; no AC production files changed"),
        ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(dict(status="PASS_PREPARATION" if args.prepare else "PASS", checks=len(CHECKS))))


if __name__ == "__main__":
    main()
