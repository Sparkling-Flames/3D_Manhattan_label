"""Connect current-label AC registry to frozen endpoints and legal labor.

No fusion or scoring occurs. The only new geometric measurements are pairwise
distances and retained reference diagnostics of the already-run gap supplement.
Original scalar/coordinate/reference files remain unchanged.
"""
from __future__ import annotations

import argparse
import collections
from functools import lru_cache
import gzip
import json
import sys

import numpy as np
import pandas as pd

from ac_common import *

sys.path.insert(0, str(REPO / "research/workers/personnel_v21_reselection_20261029/analysis"))
from legacy_geometry_diagnostics import geometry_metrics, refdiagnostic

REGISTRY = OUT / "registry/REUSED_CURRENT_AC_REGISTRY.csv.gz"
LEGACY_METRICS = HERE / "LEGACY_TARGET_METRICS_AUTOMATIC.csv.gz"
ASSISTED_METRICS = REPO / "research/fusion/manual_order_acceptance_20261104/ac/AFFECTED_EVENTS_RECHECKED.csv.gz"
ASSISTED_ENDPOINTS = REPO / "research/fusion/manual_order_impact_20261104/endpoints/ENDPOINT_SCORES.csv"
B12 = REPO / "research/workers/mixture_patterns_and_c13_half_20261104/c13_half"
LABOR_SOURCE = REPO / "research/workers/current_class_interpretation_20261104/dstruct/ORDINARY_RECORDS_WITH_COMPONENTS.csv.gz"
PURPOSE_SOURCE = REPO / "research/statistics/room_type_similarity_scoping_20261027/IMAGE_TYPE_INDEX.csv"

REG_META = ["event_id", "source_event_id", "source_leg", "source_registry", "analysis_source",
            "sampling_interpretation", "pool_id", "image", "image_id", "building", "scope", "condition", "layer",
            "reference_id", "reference_version", "source_commit", "registration_source", "design_family",
            "A_team_key", "C_team_key", "A_workers", "C_workers", "D_workers", "X_workers", "Z_workers",
            "current_source_class", "current_target_class", "current_direction", "current_class_pair",
            "current_n", "current_m", "current_replacement_fraction", "current_direction_changed",
            "canonical_physical_pair_id", "orientation_sign", "orientation_origin", "current_D_class_counts",
            "D_current_C1", "D_current_C2", "D_current_C3", "D_current_unknown", "current_D_is_mixed", "current_D_is_empty",
            "original_design_current_valid", "historical_background_profiles", "current_valid_specific_link_count",
            "source_class", "target_class", "study", "bundle_id", "block_id", "background_id", "target_slot"]


def metadata(reg: pd.DataFrame, cohort: str) -> pd.DataFrame:
    d = reg.reindex(columns=REG_META).copy()
    d["analysis_cohort"] = cohort
    d["n"] = pd.to_numeric(d.current_n).astype(int)
    d["m"] = pd.to_numeric(d.current_m).astype(int)
    d["replacement_fraction"] = d.m / d.n
    d["class_pair"] = d.current_class_pair
    d["direction"] = d.current_direction
    d["original_event_id"] = d.source_event_id.fillna(d.event_id)
    for c in ["D_current_C1", "D_current_C2", "D_current_C3", "D_current_unknown"]:
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0).astype(int)
    d["D_n"] = d.n - d.m
    d["D_category"] = "mixed_known_classes"
    d.loc[d.D_n.eq(0), "D_category"] = "empty_background"
    for c in ["C1", "C2", "C3"]:
        d.loc[d["D_current_" + c].eq(d.D_n) & d.D_n.gt(0), "D_category"] = "pure_" + c
    d.loc[d.D_current_unknown.gt(0), "D_category"] = "contains_unknown_class"
    d["design_status"] = np.where(truth(d.original_design_current_valid), "original_contract_retained", "generic_AC_only_after_label_update")
    return d


def attach_fields(meta: pd.DataFrame, raw: pd.DataFrame, a_arm: str = "A", c_arm: str = "C", pair_code: str = "AC") -> pd.DataFrame:
    raw = raw.reset_index(drop=True)
    meta = meta.reset_index(drop=True)
    if len(meta) != len(raw):
        raise ValueError("Endpoint rows and event metadata length differ")
    extra = {}
    for dest, source in [("A", a_arm), ("C", c_arm)]:
        for field in SCALARS + STATES:
            column = source + "_" + field
            extra[dest + "_" + field] = raw[column] if column in raw else np.nan
    for field in GEOMETRY:
        source = field[:-2] + pair_code
        extra[field] = raw[source] if source in raw else np.nan
    return pd.concat([meta, pd.DataFrame(extra)], axis=1)


def build_legacy(reg: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    m = read_csv(LEGACY_METRICS).set_index("event_id", verify_integrity=True)
    e = reg.loc[reg.analysis_source.eq("legacy_target_stock_current_label_conditional")].copy().reset_index(drop=True)
    raw = m.loc[e.event_id].reset_index()
    for field in ["A_team_key", "C_team_key", "pool_id", "reference_id", "reference_version", "A_workers", "C_workers"]:
        if not raw[field].fillna("").astype(str).eq(e[field].fillna("").astype(str)).all():
            raise ValueError("Registry/original metric binding mismatch: " + field)
    meta = metadata(e, LEGACY)
    auto = attach_fields(meta, raw)
    changed = read_csv(ASSISTED_METRICS)
    changed = changed.loc[changed.method.eq("TARGET_DSTRUCT_K3") & changed.event_id.isin(e.event_id)].set_index("event_id", verify_integrity=True)
    assisted_raw = raw.set_index("event_id").copy()
    for field in ["A_team_key", "C_team_key", "pool_id", "reference_id", "reference_version", "A_workers", "C_workers"]:
        if not assisted_raw.loc[changed.index, field].fillna("").astype(str).eq(changed[field].fillna("").astype(str)).all():
            raise ValueError("Assisted event identity changed: " + field)
    # No DataFrame.update: it would silently retain an obsolete nonmissing value
    # when an assisted field correctly becomes missing.
    same_columns = assisted_raw.columns.intersection(changed.columns)
    assisted_raw.loc[changed.index, same_columns] = changed[same_columns].to_numpy()
    assisted = attach_fields(meta, assisted_raw.reset_index())
    approved = read_csv(ASSISTED_ENDPOINTS)
    identities = {(r.image, r.condition, r.reference_id, r.reference_version, tuple(sorted(members(r.member_workers)))) for r in approved.itertuples()}
    approved_hits = set()
    for row in e.itertuples():
        for arm in ["A", "C"]:
            identity = (row.image, row.condition, row.reference_id, row.reference_version, tuple(sorted(members(getattr(row, arm + "_workers")))))
            if identity in identities:
                approved_hits.add(row.event_id)
    unexpected = approved_hits - set(changed.index)
    if unexpected:
        raise ValueError("Approved endpoint match missing from accepted AC consumer rows: " + str(sorted(unexpected)))
    original_common = auto.A_B8L2.notna() & auto.C_B8L2.notna()
    common_delta = np.nanmax(np.abs(assisted.loc[original_common, ["A_B8L2", "C_B8L2"]].to_numpy(float) - auto.loc[original_common, ["A_B8L2", "C_B8L2"]].to_numpy(float))) if original_common.any() else 0.
    if common_delta > 1e-10:
        raise ValueError("Original common-support Q was altered")
    checks = dict(legacy_legal_events=len(e), legacy_affected_legal_events=len(changed),
                  independently_matched_approved_event_ids=len(approved_hits),
                  missing_approved_consumer_events=len(unexpected), original_common_Q_max_change=float(common_delta),
                  source_target_rows=len(m), automatic_q_pair_events=int(original_common.sum()))
    csv(HERE / "ASSISTED_CHANGED_LEGAL_EVENTS_SOURCE.csv.gz", changed.reset_index())
    return auto, assisted, checks


def build_batch12(reg: pd.DataFrame) -> pd.DataFrame:
    e = reg.loc[reg.analysis_source.eq("batch12_strictABC_reused_direct_leg")].copy()
    raw = read_csv(B12 / "analysis/EVENT_METRICS.csv.gz").set_index("event_id", verify_integrity=True)
    parts = []
    for leg, z in e.groupby("source_leg", sort=True):
        source = raw.loc[z.source_event_id].reset_index()
        arm = "A" if leg == "AC" else "B"
        if not source[arm + "_team_key"].to_numpy().tolist() == z.A_team_key.to_numpy().tolist():
            raise ValueError("Batch12 direct leg identity mismatch")
        if not source.C_team_key.to_numpy().tolist() == z.C_team_key.to_numpy().tolist():
            raise ValueError("Batch12 C endpoint identity mismatch")
        parts.append(attach_fields(metadata(z, BATCH12), source, a_arm=arm, pair_code=leg))
    return pd.concat(parts, ignore_index=True)


def build_gap() -> pd.DataFrame:
    base = OUT / "supplement"
    e = read_csv(base / "EVENTS.csv.gz")
    raw = read_csv(base / "endpoints/ENDPOINT_SCALARS.csv.gz").set_index("team_key", verify_integrity=True)
    geo = read_csv(base / "endpoints/ENDPOINT_GEOMETRY.csv.gz").set_index("team_key", verify_integrity=True)
    pools = {p["pool_id"]: p for p in json.loads(gzip.decompress((base / "inputs/SELECTED_POOLS.json.gz").read_bytes()))["images"]}
    endpoints = raw.to_dict("index")
    for key, record in endpoints.items():
        record["geometry"] = json.loads(geo.loc[key, "geometry_json"])
        refdiagnostic(record, pools[record["pool_id"]])
        if record.get("nodes") is not None:
            refn = len(pools[record["pool_id"]]["reference"]["points_1024x512"]) // 2
            record["reference_node_shortfall"] = max(0, refn - record["nodes"])
            record["reference_node_excess"] = max(0, record["nodes"] - refn)
    rows = []
    for r in e.to_dict("records"):
        a, c = endpoints[r["A_team_key"]], endpoints[r["C_team_key"]]
        for end, workers in [(a, r["A_workers"]), (c, r["C_workers"])]:
            if sorted(members(end["member_workers"])) != sorted(members(workers)) or end["reference_id"] != r["reference_id"] or end["reference_version"] != r["reference_version"]:
                raise ValueError("Supplement endpoint binding mismatch")
        row = dict(r)
        row.update(source_event_id=r["event_id"], source_leg="AC", source_registry=str((base / "EVENTS.csv.gz").relative_to(REPO)),
                   analysis_source=GAP, sampling_interpretation=r["sampling_identity"], source_commit="48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b",
                   registration_source="20261104_frozen_capacity_gap", design_family="current_capacity_gap",
                   D_workers=r["D"], X_workers=r["X"], Z_workers=r["Z"], current_source_class=r["source_class"],
                   current_target_class=r["target_class"], current_class_pair=r["pair"], current_n=r["n"], current_m=r["m"],
                   current_replacement_fraction=r["replacement_fraction"], current_direction_changed=False,
                   canonical_physical_pair_id=digest([r["pool_id"], sorted([r["A_team_key"], r["C_team_key"]])])[:24],
                   orientation_sign=1, orientation_origin="registered", current_D_class_counts=r["D_class_vector"],
                   current_D_is_empty=False, current_D_is_mixed=sum(r.get("D_" + x, 0) > 0 for x in ["C1", "C2", "C3"]) > 1,
                   original_design_current_valid=True, historical_background_profiles="predefined_mixed_D")
        for cls in ["C1", "C2", "C3", "unknown"]:
            row["D_current_" + cls] = r.get("D_" + cls, 0)
        for arm, end in [("A", a), ("C", c)]:
            for field in SCALARS + STATES:
                row[arm + "_" + field] = end.get(field, np.nan)
        row.update({k + "_AC": v for k, v in geometry_metrics(a, c).items()})
        rows.append(row)
    d = pd.DataFrame(rows)
    return attach_fields(metadata(d, GAP), d)


def add_context(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    d = frame.copy()
    original = read_csv(LABOR_SOURCE)
    purpose = read_csv(PURPOSE_SOURCE)
    if purpose.image_code.duplicated().any():
        raise ValueError("Room-purpose index has duplicate image keys")
    pmap = purpose.set_index("image_code").room_type.to_dict()
    fields = ["pool_id", "image_id", "official_difficulty", "structural_condition", "ref_turn5", "ref_H", "ref_short_edges", "geometric_challenge"]
    ctx = original[fields].drop_duplicates()
    if ctx.pool_id.duplicated().any():
        raise ValueError("Current original-answer context differs inside a target pool")
    ctx = ctx.set_index("pool_id")
    if not set(d.pool_id).issubset(set(ctx.index)):
        raise ValueError("No current context for pools: " + str(set(d.pool_id) - set(ctx.index)))
    for field in fields[1:]:
        d[field] = d.pool_id.map(ctx[field])
    d["room_type"] = d.image.map(pmap).fillna("未登记")
    # Time is independently reconstructed from member-level frozen records.
    columns = ["pool_id", "worker_id", "object_id", "image", "building", "scope", "condition", "origin", "time_source", "source_active_time_seconds", "target_time_seconds"]
    rec = original[columns].copy()
    if rec.duplicated(["pool_id", "worker_id"]).any():
        raise ValueError("Nonunique current pool-worker time identity")
    rec = rec.loc[rec.pool_id.isin(set(d.pool_id))].copy()
    csv(HERE / "CURRENT_RECORD_LABOR_INDEX.csv.gz", rec)
    rmap = rec.set_index(["pool_id", "worker_id"]).to_dict("index")

    @lru_cache(None)
    def time_block(pid, workers):
        names = tuple(sorted(members(workers)))
        records = [rmap.get((pid, w)) for w in names]
        values = [r.get("source_active_time_seconds", np.nan) if r is not None else np.nan for r in records]
        good = bool(names) and all(np.isfinite(v) and v > 0 for v in values)
        sources = collections.Counter(str(r["time_source"]) if r is not None and pd.notna(r["time_source"]) else "unknown" for r in records)
        known = sum(np.isfinite(v) and v > 0 for v in values)
        target_values = [r.get("target_time_seconds", np.nan) if r is not None else np.nan for r in records]
        target_good = bool(names) and all(np.isfinite(v) and v > 0 for v in target_values)
        return dict(n=len(names), known_positive=known, missing_member_binding=sum(r is None for r in records),
                    complete=good, single_source=good and len(sources) == 1 and "unknown" not in sources,
                    source_kind=next(iter(sources)) if len(sources) == 1 else "mixed",
                    source_count_json=json.dumps(dict(sorted(sources.items())), sort_keys=True, separators=(",", ":")),
                    total=sum(values) if good else np.nan, target_total=sum(target_values) if target_good else np.nan,
                    known_sum=sum(v for v in values if np.isfinite(v) and v > 0))

    labor = []
    endpoint_rows = {}
    for r in d.to_dict("records"):
        v = {arm: time_block(r["pool_id"], str(r[arm + "_workers"]) if pd.notna(r[arm + "_workers"]) else "") for arm in ["A", "C", "D", "X", "Z"]}
        whole = v["A"]["single_source"] and v["C"]["single_source"] and v["A"]["source_kind"] == v["C"]["source_kind"]
        blocks = v["X"]["single_source"] and v["Z"]["single_source"] and v["X"]["source_kind"] == v["Z"]["source_kind"]
        balanced = v["A"]["complete"] and v["C"]["complete"] and v["A"]["source_count_json"] == v["C"]["source_count_json"]
        out = dict(time_whole_single_source=whole, time_blocks_single_source=blocks, time_whole_source_count_matched=balanced,
                   whole_time_source=v["A"]["source_kind"] if whole else "", block_time_source=v["X"]["source_kind"] if blocks else "",
                   dT_whole=v["C"]["total"] - v["A"]["total"] if whole else np.nan,
                   log_T_ratio_whole=np.log(v["C"]["total"] / v["A"]["total"]) if whole else np.nan,
                   dT_blocks=v["Z"]["total"] - v["X"]["total"] if blocks else np.nan,
                   log_T_ratio_blocks=np.log(v["Z"]["total"] / v["X"]["total"]) if blocks else np.nan,
                   dT_source_count_matched=v["C"]["total"] - v["A"]["total"] if balanced else np.nan,
                   D_labor_complete=(v["D"]["complete"] or not v["D"]["n"]),
                   labor_scope="source_record_labor_not_target_specific" if r["scope"] != "primary" else "source_annotation_record_labor")
        for arm in ["A", "C", "D", "X", "Z"]:
            out[arm + "_recorded_labor_total"] = v[arm]["total"]
            out[arm + "_known_positive_time_n"] = v[arm]["known_positive"]
            out[arm + "_time_source_counts"] = v[arm]["source_count_json"]
        if whole and blocks and abs(out["dT_whole"] - out["dT_blocks"]) > 1e-8:
            raise ValueError("Common-D labor cancellation failed")
        labor.append(out)
        for arm in ["A", "C"]:
            key = r[arm + "_team_key"]
            erow = dict(team_key=key, pool_id=r["pool_id"], image=r["image"], building=r["building"], scope=r["scope"],
                        member_workers=r[arm + "_workers"], **v[arm])
            if key in endpoint_rows and endpoint_rows[key]["member_workers"] != erow["member_workers"]:
                raise ValueError("Team key has different labor member identity")
            endpoint_rows[key] = erow
    d = pd.concat([d.reset_index(drop=True), pd.DataFrame(labor)], axis=1)
    csv(HERE / "ENDPOINT_RECORDED_LABOR.csv.gz", pd.DataFrame(endpoint_rows.values()))
    return d, {"time_index_records": len(rec), "time_index_unique_pool_workers": len(rmap),
               "unique_physical_endpoints_with_labor_audit": len(endpoint_rows),
               "missing_time_member_bindings": sum(x["missing_member_binding"] for x in endpoint_rows.values())}


def recompute_columns(frame: pd.DataFrame) -> pd.DataFrame:
    d = frame.copy()
    values = {}
    for metric in SCALARS:
        a, c = pd.to_numeric(d["A_" + metric], errors="coerce"), pd.to_numeric(d["C_" + metric], errors="coerce")
        d["A_" + metric], d["C_" + metric] = a, c
        values["delta_" + metric] = c - a
    d = pd.concat([d, pd.DataFrame(values)], axis=1)
    d["Q_A"], d["Q_C"] = d.A_B8L2, d.C_B8L2
    d["dQ"] = d.Q_C - d.Q_A
    d["abs_dQ"] = d.dQ.abs()
    d["common_Q"] = d.Q_A.notna() & d.Q_C.notna()
    d["midpoint_Q"] = (d.Q_A + d.Q_C) / 2
    d["both_Q_ge90"] = d.Q_A.ge(90) & d.Q_C.ge(90)
    d["symmetric_Q_band"] = pd.cut(d.midpoint_Q, [-np.inf, 60, 80, 90, np.inf], right=False,
                                   labels=["M<60", "60<=M<80", "80<=M<90", "M>=90"]).astype(str)
    d["ceiling_abs_bound"] = 2 * np.minimum(d.midpoint_Q, 100 - d.midpoint_Q)
    d["abs_difference_fraction_of_bound"] = d.abs_dQ / d.ceiling_abs_bound.where(d.ceiling_abs_bound > 1e-10)
    if (d.abs_dQ > d.ceiling_abs_bound + 1e-8).fillna(False).any():
        raise ValueError("Q bounds or algebraic absolute-difference bound violated")
    d["same_node_count"] = d.A_nodes.eq(d.C_nodes) & d.A_nodes.notna() & d.C_nodes.notna()
    d["node_count_group"] = np.where(d.same_node_count, "same_node_count", "different_node_count")
    d["nominal_threshold_equal"] = d.A_minimum_support.eq(d.C_minimum_support)
    if (~d.nominal_threshold_equal & d.A_minimum_support.notna() & d.C_minimum_support.notna()).any():
        raise ValueError("Fixed-n AC has unequal native nominal thresholds")
    d["Q_state_transition"] = np.select([d.Q_A.notna() & d.Q_C.notna(), d.Q_A.isna() & d.Q_C.notna(),
                                         d.Q_A.notna() & d.Q_C.isna()], ["both_Q", "missing_to_Q", "Q_to_missing"], default="both_missing")
    d["native_status_transition"] = d.A_score_status.fillna("unrecorded").astype(str) + " -> " + d.C_score_status.fillna("unrecorded").astype(str)
    d["difficulty_x_room_type"] = d.official_difficulty.astype(str) + " | " + d.room_type.astype(str)
    return d


def canonical_pairs(events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = events.copy()
    flip = pd.to_numeric(d.orientation_sign).lt(0)
    original_direction = d.direction.copy()
    a_columns = [c for c in d if c.startswith("A_") and "C_" + c[2:] in d]
    for a in a_columns:
        c = "C_" + a[2:]
        tmp = d.loc[flip, a].copy()
        d.loc[flip, a] = d.loc[flip, c].to_numpy()
        d.loc[flip, c] = tmp.to_numpy()
    for x, z in [("X_workers", "Z_workers"), ("X_recorded_labor_total", "Z_recorded_labor_total"),
                 ("X_known_positive_time_n", "Z_known_positive_time_n"), ("X_time_source_counts", "Z_time_source_counts")]:
        tmp = d.loc[flip, x].copy()
        d.loc[flip, x] = d.loc[flip, z].to_numpy()
        d.loc[flip, z] = tmp.to_numpy()
    for metric in ["dT_whole", "dT_blocks", "dT_source_count_matched", "log_T_ratio_whole", "log_T_ratio_blocks"]:
        d.loc[flip, metric] = -d.loc[flip, metric]
    d["source_class_current"] = d.class_pair.str.split("_").str[0]
    d["target_class_current"] = d.class_pair.str.split("_").str[1]
    d["direction"] = d.source_class_current + "_to_" + d.target_class_current
    d["registered_current_source_class"] = d.current_source_class
    d["registered_current_target_class"] = d.current_target_class
    d["registered_current_direction"] = original_direction
    d["current_source_class"] = d.source_class_current
    d["current_target_class"] = d.target_class_current
    d["current_direction"] = d.direction
    alias_columns = ["event_id", "original_event_id", "source_leg", "analysis_cohort", "analysis_source", "source_registry", "pool_id", "image", "building", "scope", "n", "m", "canonical_physical_pair_id", "orientation_sign", "design_family", "original_design_current_valid", "historical_background_profiles"]
    aliases = d.reindex(columns=alias_columns).copy()
    aliases["registered_current_direction"] = original_direction
    keys = ["analysis_cohort", "canonical_physical_pair_id"]
    consistency = d.groupby(keys, dropna=False)[["A_B8L2", "C_B8L2", "n", "m"]].nunique(dropna=False)
    if (consistency > 1).any().any():
        raise ValueError("Multiple inconsistent scalar values for the same physical pair")
    counts = d.groupby(keys, dropna=False).agg(method_event_aliases=("event_id", "size"),
                                             original_design_any_valid=("original_design_current_valid", lambda x: bool(truth(x).any())))
    d = d.sort_values("event_id").drop_duplicates(keys).merge(counts, left_on=keys, right_index=True, how="left", validate="one_to_one")
    return recompute_columns(d.reset_index(drop=True)), aliases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--without-supplement", action="store_true")
    args = parser.parse_args()
    reg = read_csv(REGISTRY)
    automatic, assisted, checks = build_legacy(reg)
    b12 = build_batch12(reg)
    frames_a, frames_h = [automatic, b12], [assisted, b12.copy()]
    if not args.without_supplement:
        gap = build_gap()
        frames_a.append(gap)
        frames_h.append(gap.copy())
    automatic = pd.concat(frames_a, ignore_index=True)
    assisted = pd.concat(frames_h, ignore_index=True)
    # Context/labor is invariant to connection order; calculate it once.
    automatic, tcheck = add_context(automatic)
    invariant_columns = [c for c in automatic if c not in assisted]
    assisted = pd.concat([assisted.reset_index(drop=True), automatic[invariant_columns].reset_index(drop=True)], axis=1)
    if not automatic.event_id.equals(assisted.event_id):
        raise ValueError("Version event order differs")
    auto_pairs, aliases = canonical_pairs(automatic)
    aux_pairs, aux_aliases = canonical_pairs(assisted)
    if not auto_pairs[["analysis_cohort", "canonical_physical_pair_id"]].equals(aux_pairs[["analysis_cohort", "canonical_physical_pair_id"]]):
        raise ValueError("Version physical pair identities differ")
    for version, d in [("automatic", auto_pairs), ("manual_order_assisted", aux_pairs)]:
        d["version"] = version
        d["original_common_Q"] = auto_pairs.common_Q.to_numpy()
        d["new_common_Q"] = (~auto_pairs.common_Q & aux_pairs.common_Q).to_numpy()
        d["approved_order_touched"] = (auto_pairs.A_order_status.fillna("").ne(aux_pairs.A_order_status.fillna("")) |
                                        auto_pairs.C_order_status.fillna("").ne(aux_pairs.C_order_status.fillna(""))).to_numpy()
    csv(HERE / "PAIR_EVENT_ALIASES.csv.gz", aliases)
    csv(HERE / "PHYSICAL_PAIRS_AUTOMATIC.csv.gz", auto_pairs)
    csv(HERE / "PHYSICAL_PAIRS_ASSISTED.csv.gz", aux_pairs)
    # Native registered orientations are retained independently of canonical
    # low-to-high physical views. They are not synthetic additional experiments.
    native_cols = ["event_id", "analysis_cohort", "current_direction", "canonical_physical_pair_id", "orientation_sign", "A_team_key", "C_team_key", "A_workers", "C_workers", "D_workers", "X_workers", "Z_workers", "pool_id", "image", "building", "scope", "n", "m", "A_B8L2", "C_B8L2", "A_score_status", "C_score_status"]
    csv(HERE / "REGISTERED_ORIENTATION_ENDPOINTS.csv.gz", automatic[native_cols])
    checks.update(tcheck)
    checks.update(status="passed", method_event_aliases=len(automatic), unique_physical_pairs=len(auto_pairs),
                  pairs_by_cohort=auto_pairs.groupby("analysis_cohort").size().to_dict(),
                  automatic_common_pairs=int(auto_pairs.common_Q.sum()), assisted_common_pairs=int(aux_pairs.common_Q.sum()),
                  new_common_pairs=int(aux_pairs.new_common_Q.sum()), same_node_count_common_pairs=int((auto_pairs.same_node_count & auto_pairs.common_Q).sum()),
                  nominal_threshold_changes=int((~auto_pairs.nominal_threshold_equal).sum()),
                  all_reused_Q_coordinates_references_unchanged=True, new_fusions_in_this_statistics_module=0,
                  new_scores_in_this_statistics_module=0, additional_pair_diagnostics_only=not args.without_supplement)
    write_json(HERE / "DATASET_CHECKS.json", checks)
    sources = [REGISTRY, LEGACY_METRICS, ASSISTED_METRICS, ASSISTED_ENDPOINTS, B12 / "analysis/EVENT_METRICS.csv.gz", LABOR_SOURCE, PURPOSE_SOURCE,
               REPO / "research/workers/personnel_v21_reselection_20261029/analysis/legacy_geometry_diagnostics.py"]
    if not args.without_supplement:
        sources += [OUT / "supplement/EVENTS.csv.gz", OUT / "supplement/endpoints/ENDPOINT_SCALARS.csv.gz", OUT / "supplement/endpoints/ENDPOINT_GEOMETRY.csv.gz", OUT / "supplement/inputs/SELECTED_POOLS.json.gz"]
    csv(HERE / "ANALYSIS_INPUT_MANIFEST.csv", pd.DataFrame([dict(path=str(p.relative_to(REPO)), bytes=p.stat().st_size, sha256=sha(p)) for p in sources]))
    print(json.dumps(checks, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
