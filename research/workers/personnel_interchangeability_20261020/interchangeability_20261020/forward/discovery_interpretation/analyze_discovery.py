#!/usr/bin/env python3
"""Read only the complete frozen discovery block panel; do not refit labels.

Report quality, actual geometry interchangeability and source-task report time
on separate axes. Native per-method requests differ; direct feature-group
ablation contrasts must use forward/common_panel, not this sampled table.
"""
from __future__ import annotations
import argparse
import collections
import functools
import gzip
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
KEY_METRICS = [
    "within_joint_stable_main", "cross_joint_stable_main", "gap_joint_stable_main",
    "within_joint_stable_strict", "cross_joint_stable_strict", "gap_joint_stable_strict",
    "within_joint_stable_wide", "cross_joint_stable_wide", "gap_joint_stable_wide",
    "within_geometry_noQ_main", "cross_geometry_noQ_main", "gap_geometry_noQ_main",
    "within_geometry_shape_main", "cross_geometry_shape_main", "gap_geometry_shape_main",
    "within_floor_jaccard_difference", "cross_floor_jaccard_difference", "excess_floor_jaccard_difference",
    "within_structure_bound_cyclic_deg", "cross_structure_bound_cyclic_deg", "excess_structure_bound_cyclic_deg",
    "within_node_count_difference", "cross_node_count_difference", "excess_node_count_difference",
    "within_abs_B8L2_change", "cross_abs_B8L2_change", "excess_abs_B8L2_change",
    "within_Q_drop_gt5", "cross_Q_drop_gt5", "within_absQ_gt5", "cross_absQ_gt5",
    "net_B8L2_change", "net_D10_change", "net_Q_improve_gt2", "net_Q_worsen_gt2", "net_Q_worsen_gt5",
    "net_complete_lost", "net_complete_restored", "A_complete", "B_complete", "C_complete",
    "A_score_missing", "B_score_missing", "C_score_missing", "B_B8L2", "C_B8L2",
    "net_IoU3D100_delta", "net_ref_node_recall_9_delta", "net_ref_edge_recall_9_delta",
    "net_diag_wall_coverage_05_delta", "net_diag_corner_recall_05_delta", "net_omission_delta", "net_extension_delta",
    "within_bottom_y_absdiff_deg_p95", "cross_bottom_y_absdiff_deg_p95", "within_top_y_absdiff_deg_p95", "cross_top_y_absdiff_deg_p95",
    "within_boundary_distance_normalized_p95", "cross_boundary_distance_normalized_p95",
    "source_block_log_ratio", "net_source_block_seconds", "source_seconds_change_per_replaced_person",
    "within_source_seconds_per_replaced_person", "cross_source_seconds_per_replaced_person",
    "source_time_comparable", "target_time_comparable", "target_block_log_ratio", "net_target_block_seconds",
    "source_save20", "source_save20_Q_not_worse2", "source_save20_Q_not_worse2_same_noQ_geometry",
    "cross_minus_within_history_Q", "history_Q_excess_abs", "all_blocks_history_Q_close3", "actual_source_match",
    "within_history_t_source_origin_effect", "cross_history_t_source_origin_effect",
    "net_Q_close2_shape_changed"]
SUPPORT_METRICS = ["gap_joint_stable_main", "gap_geometry_noQ_main", "gap_geometry_shape_main", "net_B8L2_change",
                   "excess_floor_jaccard_difference", "excess_structure_bound_cyclic_deg", "source_block_log_ratio", "target_block_log_ratio"]


def read(path):
    with (gzip.open(path, "rt") if str(path).endswith(".gz") else open(path)) as f:
        return json.load(f)


def stream_events(path):
    """Stream the first, sorted-key events array without loading team requests.

    The exact registered request file starts with {"events":[...]. Decoding
    one event at a time avoids retaining ~600 MB of duplicate team arrays.
    """
    decoder = json.JSONDecoder()
    with gzip.open(path, "rt") as f:
        buf = f.read(65536)
        prefix = '{"events":['
        assert buf.startswith(prefix), "Unexpected request schema/key order"
        pos = len(prefix)
        while True:
            while pos < len(buf) and (buf[pos].isspace() or buf[pos] == ","):
                pos += 1
            if pos < len(buf) and buf[pos] == "]":
                return
            try:
                event, end = decoder.raw_decode(buf, pos)
            except json.JSONDecodeError:
                more = f.read(65536)
                if not more:
                    raise
                buf = buf[pos:] + more
                pos = 0
                continue
            yield event
            pos = end
            if pos > 65536:
                buf = buf[pos:]
                pos = 0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))


def write_csv(path, frame):
    path = Path(path)
    raw = frame.to_csv(index=False).encode()
    packed = gzip.compress(raw, compresslevel=6, mtime=0)
    assert gzip.decompress(packed) == raw
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(packed)
    assert tmp.stat().st_size == len(packed) and gzip.decompress(tmp.read_bytes()) == raw
    tmp.replace(path)
    assert gzip.decompress(path.read_bytes()) == raw


def bit_count(values):
    return int(functools.reduce(int.__or__, (int(x) for x in values), 0)).bit_count()


def eligible_views(frame):
    primary = frame.loc[(frame.n >= 3) & (frame.m >= 2)]
    yield "primary_nge3_mge2_all", primary
    yield "primary_source_matched", primary.loc[primary.actual_source_match]
    yield "primary_source_Qclose3", primary.loc[primary.actual_source_match & primary.all_blocks_history_Q_close3]
    yield "single_person_supplement_nge3", frame.loc[(frame.n >= 3) & (frame.m == 1)]


def summarize(frame, keys, metrics=KEY_METRICS, tails=True):
    if frame.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    metrics = [m for m in metrics if m in frame]
    per_image = frame.groupby(keys + ["building", "pool_id"], dropna=False)[metrics].mean().reset_index()
    if tails:
        qs = frame.groupby(keys + ["building", "pool_id"], dropna=False)[["net_B8L2_change", "B_B8L2", "C_B8L2"]].quantile(.1).reset_index()
        qs = qs.rename(columns={m: m + "_per_image_p10" for m in ("net_B8L2_change", "B_B8L2", "C_B8L2")})
        per_image = per_image.merge(qs, on=keys + ["building", "pool_id"], validate="one_to_one")
    all_metrics = [c for c in per_image.columns if c not in keys + ["building", "pool_id"]]
    per_building = per_image.groupby(keys + ["building"], dropna=False)[all_metrics].mean().reset_index()
    aggregate = per_building.groupby(keys, dropna=False)[all_metrics].mean().reset_index()
    supp = []
    for key, g in frame.groupby(keys, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        r = dict(zip(keys, key))
        teams = set(g.A_team_key) | set(g.B_team_key) | set(g.C_team_key)
        r.update(events=len(g), pools=g.pool_id.nunique(), images=g.image.nunique(), buildings=g.building.nunique(), unique_teams=len(teams),
                 all_people=bit_count(g.all_worker_mask), block_people=bit_count(g.block_worker_mask),
                 outgoing_people=bit_count(g.out_worker_mask), within_incoming_people=bit_count(g.within_worker_mask),
                 cross_incoming_people=bit_count(g.cross_worker_mask), n_min=int(g.n.min()), n_max=int(g.n.max()),
                 m_min=int(g.m.min()), m_max=int(g.m.max()), replaced_fraction_min=float(g.replacement_fraction.min()),
                 replaced_fraction_max=float(g.replacement_fraction.max()))
        for m in SUPPORT_METRICS:
            z = g.loc[g[m].notna()]
            r[m + "_known_events"] = len(z)
            r[m + "_known_pools"] = z.pool_id.nunique()
            r[m + "_known_images"] = z.image.nunique()
            r[m + "_known_buildings"] = z.building.nunique()
        supp.append(r)
    aggregate = aggregate.merge(pd.DataFrame(supp), on=keys, validate="one_to_one")
    for m in ("gap_joint_stable_main", "gap_geometry_noQ_main", "gap_geometry_shape_main", "net_B8L2_change", "source_block_log_ratio"):
        sign = per_building.groupby(keys, dropna=False)[m].agg(
            **{m + "_positive_buildings": lambda x: int((x > 0).sum()), m + "_negative_buildings": lambda x: int((x < 0).sum()),
               m + "_building_min": "min", m + "_building_max": "max"}).reset_index()
        aggregate = aggregate.merge(sign, on=keys, validate="one_to_one")
    for table in (per_image, per_building, aggregate):
        table["source_block_geometric_ratio"] = np.exp(table.source_block_log_ratio)
        table["target_block_geometric_ratio"] = np.exp(table.target_block_log_ratio)
    return per_image, per_building, aggregate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--discovery", type=Path, default=ROOT / "interchangeability_20261020/discovery")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent)
    ap.add_argument("--wait", action="store_true")
    a = ap.parse_args()
    request_path = a.discovery / "forward_requests.json.gz"
    split = read(ROOT / "analysis/composition/SPLIT.json")
    universe = pd.read_csv(Path(__file__).resolve().parent.parent / "features_train.csv.gz", usecols=["worker_id"]).worker_id.tolist()
    assert len(universe) <= 64
    bits = {w: 1 << i for i, w in enumerate(sorted(universe))}
    masks, pools_set, used_people = {}, set(), set()
    for e in stream_events(request_path):
        assert e["phase"] == "discovery" and e["building"] in split["discovery_buildings"]
        assert e["event_id"] not in masks
        pools_set.add(e["pool_id"])
        A, B, C, core = [set(e[k]) for k in ("A_workers", "B_workers", "C_workers", "core_workers")]
        assert len(A) == len(B) == len(C) == e["n"]
        assert A & B == A & C == core
        assert len(A - B) == len(A - C) == e["m"]
        blocks = [set(e[k]) for k in ("outgoing_workers", "within_incoming", "cross_incoming")]
        assert blocks[0] == A - core and blocks[1] == B - core and blocks[2] == C - core
        used_people.update(A | B | C)
        assert A | B | C <= bits.keys()
        masks[e["event_id"]] = [sum(bits[w] for w in A | B | C), sum(bits[w] for w in set.union(*blocks))] + [sum(bits[w] for w in b) for b in blocks]
    expected_pools = sorted(pools_set)
    expected_events = set(masks)
    universe = sorted(used_people)
    parts = a.discovery / "forward_metrics/event_parts"
    while True:
        missing = [pid for pid in expected_pools if not (parts / (pid + ".csv.gz")).exists()]
        if not missing:
            break
        if not a.wait:
            raise RuntimeError(f"Discovery panel incomplete: {len(expected_pools) - len(missing)}/{len(expected_pools)} pools")
        time.sleep(10)
    needed = set(KEY_METRICS) | set(SUPPORT_METRICS) | {
        "event_id", "phase", "method_id", "domain", "pool_id", "building", "image", "difficulty", "condition", "layer", "n", "m", "outgoing_class", "incoming_class",
        "n_band", "replacement_fraction", "A_team_key", "B_team_key", "C_team_key", "A_B8L2", "B_B8L2", "C_B8L2", "within_B8L2_change", "cross_B8L2_change",
        "within_bad_Q_gt5", "cross_bad_Q_gt5", "within_source_block_seconds", "cross_source_block_seconds", "within_target_block_seconds", "cross_target_block_seconds",
        "cross_over_within_source_block_time", "net_geometry_noQ_main"}
    frame = pd.concat([pd.read_csv(parts / (pid + ".csv.gz"), usecols=lambda c: c in needed) for pid in expected_pools], ignore_index=True)
    assert set(frame.event_id) == expected_events and not frame.event_id.duplicated().any()
    assert (frame.phase == "discovery").all() and set(frame.building) <= set(split["discovery_buildings"])
    mask_frame = pd.DataFrame.from_dict(masks, orient="index", columns=["all_worker_mask", "block_worker_mask", "out_worker_mask", "within_worker_mask", "cross_worker_mask"]).astype(np.uint64)
    frame = frame.join(mask_frame, on="event_id", validate="one_to_one")
    del masks, mask_frame
    for arm in ("A", "B", "C"):
        frame[arm + "_score_missing"] = frame[arm + "_B8L2"].isna()
    for kind in ("within", "cross"):
        q = frame[kind + "_B8L2_change"]
        frame[kind + "_Q_drop_gt5"] = (q < -5).astype(float).where(q.notna())
        frame[kind + "_absQ_gt5"] = frame[kind + "_bad_Q_gt5"]
    frame["net_Q_worsen_gt5"] = (frame.net_B8L2_change < -5).astype(float).where(frame.net_B8L2_change.notna())
    for kind in ("source", "target"):
        x, y = frame["within_" + kind + "_block_seconds"], frame["cross_" + kind + "_block_seconds"]
        ok = (x > 0) & (y > 0) & x.notna() & y.notna()
        frame[kind + "_time_comparable"] = ok
        frame[kind + "_block_log_ratio"] = np.log((y / x).where(ok))
    frame["within_source_seconds_per_replaced_person"] = frame.within_source_block_seconds / frame.m
    frame["cross_source_seconds_per_replaced_person"] = frame.cross_source_block_seconds / frame.m
    frame["source_seconds_change_per_replaced_person"] = frame.net_source_block_seconds / frame.m
    source_ok = frame.source_time_comparable
    save = frame.cross_over_within_source_block_time <= .8
    frame["source_save20"] = save.astype(float).where(source_ok)
    qgood = frame.B_complete & frame.C_complete & frame.net_B8L2_change.notna() & (frame.net_B8L2_change >= -2)
    frame["source_save20_Q_not_worse2"] = (save & qgood).astype(float).where(source_ok)
    frame["source_save20_Q_not_worse2_same_noQ_geometry"] = (save & qgood & frame.net_geometry_noQ_main).astype(float).where(source_ok)
    a.out.mkdir(parents=True, exist_ok=True)
    subset_parts = a.out / "subset_parts"
    subset_parts.mkdir(exist_ok=True)
    # This explicitly separates frozen two-person deferral from failed eligible
    # fusion. It remains in attempted coverage and exact-member reconstruction.
    qualification = frame.groupby(["method_id", "domain", "n"], dropna=False).agg(events=("event_id", "size"),
        pools=("pool_id", "nunique"), images=("image", "nunique"), buildings=("building", "nunique"),
        A_complete=("A_complete", "mean"), B_complete=("B_complete", "mean"), C_complete=("C_complete", "mean"),
        A_score_known=("A_B8L2", "count"), B_score_known=("B_B8L2", "count"), C_score_known=("C_B8L2", "count")).reset_index()
    qualification["eligibility"] = np.where(qualification.n == 2, "two_person_deferred_not_failure_tail", "eligible_n_ge3")
    write_csv(a.out / "n_qualification.csv.gz", qualification)
    all_results = collections.defaultdict(list)
    for subset, data in eligible_views(frame):
        data = data.copy()
        data["subset"] = subset
        for level, keys in (
            ("method", ["subset", "method_id", "domain"]),
            ("direction", ["subset", "method_id", "domain", "outgoing_class", "incoming_class"]),
            ("direction_condition", ["subset", "method_id", "domain", "outgoing_class", "incoming_class", "difficulty"]),
            ("direction_nband", ["subset", "method_id", "domain", "outgoing_class", "incoming_class", "n_band"]),
        ):
            tables = summarize(data, keys)
            for name, table in zip(("per_image", "per_building", "aggregate"), tables):
                path = subset_parts / (level + "_" + name + "__" + subset + ".csv.gz")
                write_csv(path, table)
                all_results[level + "_" + name].append(path)
        if subset == "primary_nge3_mge2_all":
            # Keep the exact n and m strata including tiny/failed strata; their
            # support determines interpretation, never silently discard them.
            tables = summarize(data, ["subset", "method_id", "domain", "outgoing_class", "incoming_class", "n", "m"], tails=False)
            for name, table in zip(("per_image", "per_building", "aggregate"), tables):
                path = subset_parts / ("direction_exact_n_m_" + name + "__" + subset + ".csv.gz")
                write_csv(path, table)
                all_results["direction_exact_n_m_" + name].append(path)
        print(json.dumps({"completed_subset": subset, "events": len(data)}), flush=True)
    for name, pieces in all_results.items():
        table = pd.concat([pd.read_csv(path) for path in pieces], ignore_index=True)
        write_csv(a.out / (name + ".csv.gz"), table)
    # Compact case search index: exact event IDs and measured axes, retaining
    # both favorable and adverse examples; this is exploration, not validation.
    primary = frame.loc[(frame.n >= 3) & (frame.m >= 2)]
    case_keys = ["method_id", "domain", "outgoing_class", "incoming_class"]
    case_rows = []
    for key, g in primary.groupby(case_keys, dropna=False):
        for field, asc, reason in (("net_B8L2_change", False, "quality_gain"), ("net_B8L2_change", True, "quality_loss"),
                                   ("source_block_log_ratio", True, "source_report_time_saving"),
                                   ("within_floor_jaccard_difference", False, "same_class_floor_counterexample"),
                                   ("excess_floor_jaccard_difference", False, "cross_class_floor_separation")):
            candidates = g.dropna(subset=[field]).sort_values(field, ascending=asc).drop_duplicates("building").head(2)
            for r in candidates.itertuples():
                z = {c: getattr(r, c) for c in ["event_id", "pool_id", "building", "image", "n", "m", "actual_source_match", "all_blocks_history_Q_close3",
                      "net_B8L2_change", "net_D10_change", "within_joint_stable_main", "cross_joint_stable_main", "within_geometry_noQ_main", "cross_geometry_noQ_main",
                      "within_floor_jaccard_difference", "cross_floor_jaccard_difference", "within_structure_bound_cyclic_deg", "cross_structure_bound_cyclic_deg",
                      "within_B8L2_change", "cross_B8L2_change", "A_B8L2", "B_B8L2", "C_B8L2", "A_complete", "B_complete", "C_complete",
                      "cross_over_within_source_block_time", "net_source_block_seconds", "source_seconds_change_per_replaced_person", "cross_minus_within_history_Q"]}
                z.update(dict(zip(case_keys, key)), selection_reason=reason)
                case_rows.append(z)
    selected_event_ids = {r["event_id"] for r in case_rows}
    selected_members = {}
    for e in stream_events(request_path):
        if e["event_id"] in selected_event_ids:
            selected_members[e["event_id"]] = {k: "|".join(e[k]) for k in ("A_workers", "B_workers", "C_workers", "outgoing_workers", "within_incoming", "cross_incoming")}
    assert set(selected_members) == selected_event_ids
    for row in case_rows:
        row.update(selected_members[row["event_id"]])
    write_csv(a.out / "case_search_index.csv.gz", pd.DataFrame(case_rows))
    receipt = dict(schema="forward_discovery_direction_quality_geometry_efficiency_v1", request_sha256=sha(request_path), script_sha256=sha(__file__),
        input_pools=len(expected_pools), input_images=frame.image.nunique(), events=len(frame), unique_events=frame.event_id.nunique(),
        attempted_unique_teams=len(set(frame.A_team_key) | set(frame.B_team_key) | set(frame.C_team_key)),
        buildings=sorted(frame.building.unique()), people=universe,
        primary_events=len(primary), primary_pools=primary.pool_id.nunique(), primary_images=primary.image.nunique(), primary_buildings=primary.building.nunique(),
        n2_deferred_events=int((frame.n == 2).sum()), single_person_nge3_events=int(((frame.n >= 3) & (frame.m == 1)).sum()),
        outcome_training=False, aggregation="Event means within image -> image means within building -> buildings equal; p10 is within-image event/team-position quantile then same hierarchy. Repeat teams are not independent and the p10 is not a population-independent CI.",
        time="Source-task report seconds and source-specific historical relative time; target time is separate and missing remains unknown. Missing common-core time does not erase known incoming block time. No claim of raw-log replay or target redo cost.",
        ablation_warning="Native Full/NoX method panels share known people but differ in sampled actual ABC/core/n/m. Do not subtract their aggregate scores as an isolated feature effect; use the separately frozen common_panel.",
        bad_tail_warning="Inherited within_bad_Q_gt5/cross_bad_Q_gt5 mean absolute Q change>5, not a quality decline. This table adds signed within/cross_Q_drop_gt5 and net_Q_worsen_gt5 explicitly.",
        source_Q="Overall utility first, then actual source-count-matched subset, then additionally all three blocks pairwise history-Q distance<=3. The prior Q column is condition-specific where available; target individual annotation Q is not an adjustment variable.")
    write_json(a.out / "DISCOVERY_INTERPRETATION_RECEIPT.json", receipt)
    print(json.dumps({k: receipt[k] for k in ("events", "attempted_unique_teams", "primary_events", "n2_deferred_events", "primary_images", "primary_buildings")}), flush=True)


if __name__ == "__main__":
    main()
