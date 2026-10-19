#!/usr/bin/env python3
"""Direct matched block composition comparisons on exact requested fused teams.

A = shared core + outgoing; B = core + new members of the same classes;
C = core + new members with a different class-count vector. Distances A/B and
A/C compare equal actual replacement m. Quality direction C-B compares the two
new arms. Their mutual turnover is measured and can be smaller than m.

Only the explicitly requested phase and exact teams are read. Fixed labels,
references, fusion, scoring, and historical features are never changed here.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from fusion_runner import read, write, team_key, digest
from summarize_grid import (CsvSink, DIAG_METRICS, META, PAIR_METRICS, MAIN_TOLERANCES,
                            canonical_counts, compact_json, delta, labels_from_files,
                            number, pair_metrics, sha, signature)

ARM_METRICS = ("B8L2", "D10", "iou_2d", "IoU3D100", "omission", "extension", "S_bottom_deg", "dir",
               "Hmean", "Hcenter", "height_mean_ratio", "nodes", "new_n", "old_n",
               "ref_node_recall_5", "ref_edge_recall_5", "ref_node_recall_9", "ref_edge_recall_9",
               "candidate_pair_count", "floor_area_camera_h2") + DIAG_METRICS
GAPS = ("abs_B8L2_change", "abs_D10_change", "floor_jaccard_difference", "floor_symdiff_h2",
        "structure_bound_cyclic_deg", "node_count_difference", "height_ratio_pair_abs_logdiff",
        "ref_node_set_jaccard_difference_9", "ref_edge_set_jaccard_difference_9")
SUMMARY_METRICS = (
    "A_complete", "B_complete", "C_complete", "A_score_available", "B_score_available", "C_score_available",
    "within_quality_comparable", "changed_quality_comparable", "net_quality_comparable",
    "within_joint_stable_main", "changed_joint_stable_main", "changed_less_stable_main",
    "within_abs_B8L2_change", "changed_abs_B8L2_change", "excess_abs_B8L2_change", "net_B8L2_change", "net_D10_change",
    "within_floor_jaccard_difference", "changed_floor_jaccard_difference", "excess_floor_jaccard_difference",
    "within_structure_bound_cyclic_deg", "changed_structure_bound_cyclic_deg", "excess_structure_bound_cyclic_deg",
    "within_node_count_difference", "changed_node_count_difference", "net_node_count_change",
    "net_ref_node_recall_9_change", "net_ref_edge_recall_9_change", "net_iou_2d_change", "net_IoU3D100_change",
    "net_omission_change", "net_extension_change", "net_diag_wall_coverage_03_change", "net_diag_wall_coverage_05_change",
    "net_diag_corner_recall_05_change", "net_floor_jaccard_difference", "net_mean_height_prism_pair_iou",
    "net_complete_restored", "net_complete_lost", "net_improve_Q2", "net_worsen_Q2", "similar_Q2_changed_structure",
    "net_turnover", "cross_minus_within_history_Q", "cross_minus_outgoing_history_Q", "within_minus_outgoing_history_Q",
)
TAIL_METRICS = ("within_abs_B8L2_change", "changed_abs_B8L2_change", "net_B8L2_change", "net_D10_change",
                "within_floor_jaccard_difference", "changed_floor_jaccard_difference", "net_ref_edge_recall_9_change")


def q_column(domain):
    if domain in ("easy", "medium", "hard"):
        return "theta_" + domain
    if domain in ("doorway", "semi_new", "semi_v1", "special_manual", "special_semi"):
        return domain + "_q_effect"
    return "q_beta"


def fixed_composition(workers, mapping):
    assert set(workers) <= mapping.keys(), "unknown worker cannot be a fitted class"
    count = collections.Counter(mapping[w] for w in workers)
    return {c: count[c] for c in sorted(set(mapping.values()))}


def validate_event(event, arm_requests, labels, phase, origins):
    e = event
    assert e["phase"] == phase
    assert set(arm_requests) == {"A", "B", "C"}, "each event must have three explicit requests"
    mapping = labels[e["method_id"], e["domain"]]
    k, m = e["k"], e["m"]
    assert 0 < m < k
    core = set(e["core_workers"])
    blocks = [set(e[key]) for key in ("outgoing_workers", "within_incoming", "cross_incoming")]
    assert len(core) == k - m and all(len(w) == m and not (core & w) for w in blocks)
    assert not (blocks[0] & blocks[1]) and not (blocks[0] & blocks[2])
    arms = {arm: set(e[arm + "_workers"]) for arm in "ABC"}
    for arm, block in zip("ABC", blocks):
        request = arm_requests[arm]
        workers = e[arm + "_workers"]
        expected_counts = e["C_counts"] if arm == "C" else e["A_counts"]
        assert len(workers) == len(arms[arm]) == k and arms[arm] == core | block
        assert request["family"] == "matched_block" and request["phase"] == phase
        assert request["event_id"] == e["event_id"] and request["arm"] == arm
        assert request["pool_id"] == e["pool_id"] and request["k"] == k
        assert (request["method_id"], request["domain"]) == (e["method_id"], e["domain"])
        assert sorted(request["worker_ids"]) == sorted(workers)
        actual = fixed_composition(workers, mapping)
        assert actual == request["counts"] == expected_counts
        assert canonical_counts(actual) == request["composition"]
        assert team_key(e["pool_id"], workers) == request["team_key"] == e[arm + "_team_key"]
    assert e["A_counts"] != e["C_counts"]
    assert arms["A"] & arms["B"] == arms["A"] & arms["C"] == core
    assert len(arms["A"] - arms["B"]) == len(arms["A"] - arms["C"]) == m
    assert fixed_composition(e["outgoing_workers"], mapping) == e["outgoing_counts"]
    assert fixed_composition(e["within_incoming"], mapping) == e["outgoing_counts"]
    assert fixed_composition(e["cross_incoming"], mapping) == e["incoming_counts"]
    actual_slots = sum(abs(e["A_counts"][c] - e["C_counts"][c]) for c in e["A_counts"]) // 2
    assert actual_slots == e["changed_category_slots"] <= m
    if e["matching"] == "source_matched":
        assert all(origins[w] == e["matched_origin"] for block in blocks for w in block)
        assert len({sum(origins[w] == "new" for w in workers) for workers in arms.values()}) == 1


def historical_block(workers, feature_map, column):
    values = [number(feature_map[w].get(column)) for w in workers]
    valid = [v for v in values if v is not None]
    return dict(mean=float(np.mean(valid)) if len(valid) == len(values) and valid else None,
                known_n=len(valid), n=len(values))


def blank_pair():
    dummy = {"pool_id": "missing", "reference_id": "missing", "k": 1,
             "member_workers": ["dummy"], "complete_evaluable": False, "geometry": {}}
    out = pair_metrics(dummy, dummy)
    return {k: None for k in out}


BLANK_PAIR = blank_pair()


def event_row(event, teams, signatures, meta, feature_map, origins):
    e = event
    row = {key: e.get(key) for key in ("event_id", "phase", "method_id", "domain", "pool_id", "k", "m", "matching", "matched_origin",
                                      "pattern", "changed_category_slots", "replaced_classes", "incoming_classes")}
    row.update({key: meta.get(key) for key in META if key != "pool_id"})
    row["scale"] = "primary_m_ge_2" if e["m"] >= 2 else "auxiliary_m_1"
    for key, value in (("A_composition", e["A_counts"]), ("C_composition", e["C_counts"]),
                       ("outgoing_counts", e["outgoing_counts"]), ("incoming_counts", e["incoming_counts"])):
        row[key] = canonical_counts(value)
    row["directed_count_change"] = row["outgoing_counts"] + " -> " + row["incoming_counts"]
    row["A_active_classes"] = sum(n > 0 for n in e["A_counts"].values())
    row["C_active_classes"] = sum(n > 0 for n in e["C_counts"].values())
    row["composition_transition"] = ("pure" if row["A_active_classes"] == 1 else "mixed") + "_to_" + ("pure" if row["C_active_classes"] == 1 else "mixed")
    row["replaced_entire_categories"] = compact_json(e["replaced_entire_categories"])
    row["core_composition_options"] = e["core_composition_options"]
    row["core_vectors_considered"] = e["core_vectors_considered"]
    for arm in "ABC":
        row[arm + "_team_key"] = e[arm + "_team_key"]
    row["core_workers_json"] = compact_json(e["core_workers"])
    for key in ("outgoing_workers", "within_incoming", "cross_incoming"):
        row[key + "_json"] = compact_json(e[key])
    row["history_Q_column"] = column = q_column(e["domain"])
    for name, key in (("outgoing", "outgoing_workers"), ("within", "within_incoming"), ("cross", "cross_incoming")):
        stats = historical_block(e[key], feature_map, column)
        row[name + "_history_Q"] = stats["mean"]
        row[name + "_history_Q_known_n"] = stats["known_n"]
        row[name + "_new_n"] = sum(origins[w] == "new" for w in e[key])
        row[name + "_origin_counts"] = compact_json(dict(collections.Counter(origins[w] for w in e[key])))
    for a, b in (("within", "cross"), ("outgoing", "cross"), ("outgoing", "within")):
        va, vb = row[a + "_history_Q"], row[b + "_history_Q"]
        row[b + "_minus_" + a + "_history_Q"] = vb - va if va is not None and vb is not None else None
    qdelta = row["cross_minus_within_history_Q"]
    row["incoming_Q_close_3"] = qdelta is not None and abs(qdelta) <= 3
    row["all_blocks_Q_close_3"] = all(row[x] is not None and abs(row[x]) <= 3 for x in (
        "cross_minus_within_history_Q", "cross_minus_outgoing_history_Q", "within_minus_outgoing_history_Q"))
    row["actual_source_match"] = len({row[x + "_origin_counts"] for x in ("outgoing", "within", "cross")}) == 1
    present = {arm: teams.get(e[arm + "_team_key"]) for arm in "ABC"}
    row["computed_arms_n"] = sum(value is not None for value in present.values())
    row["event_status"] = "computed" if row["computed_arms_n"] == 3 else "missing_computation"
    for arm, team in present.items():
        row[arm + "_score_status"] = team.get("score_status") if team else None
        row[arm + "_geometry_reason"] = team.get("geometry_reason") if team else None
        row[arm + "_complete"] = bool(team.get("complete_evaluable")) if team else None
        row[arm + "_score_available"] = number(team.get("B8L2")) is not None if team else None
        row[arm + "_diag_status"] = signatures[team["team_key"]].get("diag_status") if team else None
        for metric in ARM_METRICS:
            row[arm + "_" + metric] = number(signatures[team["team_key"]].get(metric) if metric in ("candidate_pair_count", "floor_area_camera_h2") + DIAG_METRICS else team.get(metric)) if team else None
    pairs = {}
    for name, aa, bb in (("within", "A", "B"), ("changed", "A", "C"), ("net", "B", "C")):
        a, b = present[aa], present[bb]
        metrics = pair_metrics(a, b, signatures[a["team_key"]], signatures[b["team_key"]]) if a is not None and b is not None else BLANK_PAIR.copy()
        pairs[name] = metrics
        row.update({name + "_" + key: value for key, value in metrics.items()})
    if row["computed_arms_n"] == 3:
        assert pairs["within"]["turnover"] == pairs["changed"]["turnover"] == e["m"]
    for metric in GAPS:
        row["excess_" + metric] = delta(pairs["within"], pairs["changed"], metric)
    for metric in ARM_METRICS:
        row["net_" + metric + "_change"] = delta({metric: row["B_" + metric]}, {metric: row["C_" + metric]}, metric)
    b, c = present["B"], present["C"]
    bc_present = b is not None and c is not None
    row["net_complete_restored"] = bool(not row["B_complete"] and row["C_complete"]) if bc_present else None
    row["net_complete_lost"] = bool(row["B_complete"] and not row["C_complete"]) if bc_present else None
    dq = row["net_B8L2_change"]
    row["net_improve_Q2"] = dq > 2 if dq is not None else None
    row["net_worsen_Q2"] = dq < -2 if dq is not None else None
    row["changed_less_stable_main"] = bool(row["within_joint_stable_main"] and not row["changed_joint_stable_main"]) if row["computed_arms_n"] == 3 else None
    structure_changed = (pairs["net"]["node_count_difference"] is not None and pairs["net"]["node_count_difference"] > 0) or (
        pairs["net"]["structure_bound_cyclic_deg"] is not None and pairs["net"]["structure_bound_cyclic_deg"] > 3)
    row["similar_Q2_changed_structure"] = abs(dq) <= 2 and structure_changed if dq is not None else None
    row["_workers"] = set().union(*(set(e[arm + "_workers"]) for arm in "ABC"))
    row["_teams"] = {e[arm + "_team_key"] for arm in "ABC"}
    row["_observed_teams"] = {t["team_key"] for t in present.values() if t is not None}
    row["_core"] = tuple(e["core_workers"])
    return row


def union_size(series):
    return len(set().union(*series)) if len(series) else 0


def aggregate(frame, group_columns, view, subset):
    """Finite-score summaries plus support; means give equal weight to buildings.

    Events first average within the actual image, then images within building.
    Descriptive event tails are separately labeled and never independent N.
    """
    if frame.empty:
        return pd.DataFrame()
    columns = list(dict.fromkeys(group_columns))
    by = frame.groupby(columns, observed=True, dropna=False, sort=True)
    support = by.agg(events=("event_id", "size"), unique_event_ids=("event_id", "nunique"),
                     images=("image_id", "nunique"), pools=("pool_id", "nunique"), buildings=("building", "nunique"),
                     workers=("_workers", union_size), requested_unique_teams=("_teams", union_size),
                     observed_unique_teams=("_observed_teams", union_size), unique_cores=("_core", "nunique"),
                     computed_events=("computed_arms_n", lambda v: int(v.eq(3).sum())))
    additions = {}
    for metric in SUMMARY_METRICS:
        if metric not in frame:
            continue
        additions[metric + "_n"] = by[metric].count()
        additions[metric + "_event_mean"] = by[metric].mean()
    support = pd.concat([support, pd.DataFrame(additions)], axis=1)
    pool_columns = list(dict.fromkeys(columns + ["pool_id", "building"]))
    building_columns = list(dict.fromkeys(columns + ["building"]))
    metrics = [m for m in SUMMARY_METRICS if m in frame]
    pool_means = frame.groupby(pool_columns, observed=True, dropna=False)[metrics].mean().reset_index()
    building_means = pool_means.groupby(building_columns, observed=True, dropna=False)[metrics].mean().reset_index()
    weights = building_means.groupby(columns, observed=True, dropna=False)[metrics].mean()
    weights.columns = [m + "_equal_building_mean" for m in metrics]
    support = support.join(weights)
    for metric in TAIL_METRICS:
        for q, name in ((.1, "p10"), (.5, "median"), (.9, "p90")):
            support[metric + "_event_" + name] = by[metric].quantile(q)
    for metric in ("net_B8L2_change", "excess_abs_B8L2_change", "excess_floor_jaccard_difference", "net_ref_edge_recall_9_change"):
        d = building_means.groupby(columns, observed=True, dropna=False)[metric]
        support[metric + "_positive_buildings"] = d.apply(lambda x: int((x > 0).sum()))
        support[metric + "_negative_buildings"] = d.apply(lambda x: int((x < 0).sum()))
        support[metric + "_finite_buildings"] = d.count()
    result = support.reset_index()
    result.insert(0, "subset", subset)
    result.insert(0, "view", view)
    return result


def summarize(args):
    args.out.mkdir(parents=True, exist_ok=True)
    manifest, split = read(args.requests), read(args.split)
    assert manifest["spec"]["phase"] == args.phase
    allowed = set(split[args.phase + "_buildings"])
    labels = labels_from_files(args.labels)
    features = pd.read_csv(args.features)
    assert features.worker_id.is_unique and features.train_key.nunique() == 1
    expected_train_key = "history_" + hashlib.sha256("|".join(sorted(split["history_buildings"])).encode()).hexdigest()[:16]
    assert set(features.train_key) == {expected_train_key}, "history feature key differs from frozen split"
    feature_map = features.set_index("worker_id").to_dict("index")
    origins = features.set_index("worker_id").person_origin.to_dict()
    pools = {p["pool_id"]: p for p in read(args.snapshot)["images"]}
    requests = manifest["requests"]
    assert len({r["request_id"] for r in requests}) == len(requests)
    arm_requests = collections.defaultdict(dict)
    for request in requests:
        assert request["arm"] not in arm_requests[request["event_id"]]
        arm_requests[request["event_id"]][request["arm"]] = request
    by_pool = collections.defaultdict(list)
    assert len({e["event_id"] for e in manifest["events"]}) == len(manifest["events"])
    assert set(arm_requests) == {e["event_id"] for e in manifest["events"]}
    for event in manifest["events"]:
        validate_event(event, arm_requests[event["event_id"]], labels, args.phase, origins)
        assert event["building"] in allowed and event["building"] == pools[event["pool_id"]]["meta"]["building"]
        if not args.pool or event["pool_id"] in args.pool:
            by_pool[event["pool_id"]].append(event)
    if args.pool:
        assert set(args.pool) <= set(by_pool)
    rows, receipts, all_requested, all_observed = [], [], set(), set()
    sink = CsvSink(args.out / "block_events.csv.gz")
    try:
        for pid, events in sorted(by_pool.items()):
            wanted = {e[arm + "_team_key"] for e in events for arm in "ABC"}
            path = args.runs / "pools" / (pid + ".json.gz")
            if not path.exists():
                raise FileNotFoundError("Uncomputed pool is not fusion failure: " + str(path))
            cache, pool = read(path), pools[pid]
            assert cache["context"]["pool_digest"] == digest(pool), "frozen pool/reference mismatch"
            allteams = {t["team_key"]: t for t in cache["teams"]}
            assert len(allteams) == len(cache["teams"])
            teams = {key: allteams[key] for key in wanted & allteams.keys()}
            missing = wanted - allteams.keys()
            if missing and not args.allow_partial:
                raise RuntimeError(f"{pid}: {len(missing)} requested teams not computed; no failure/zero substitution")
            meta = dict(pool["meta"], reference_nodes=len(pool["reference"]["points_1024x512"]) // 2)
            assert meta["building"] in allowed
            unique_request = {r["team_key"]: r for e in events for r in arm_requests[e["event_id"]].values()}
            for key, team in teams.items():
                req = unique_request[key]
                assert sorted(team["member_workers"]) == sorted(req["worker_ids"])
                assert team["k"] == req["k"] and key == team_key(pid, team["member_workers"])
                assert team["reference_id"] == meta["reference_id"] and team["reference_version"] == meta["reference_version"]
                assert len(set(team["member_object_ids"])) == len(team["member_workers"])
                assert team["new_n"] == sum(origins[w] == "new" for w in team["member_workers"])
            diagnostic_cache = {}
            signatures = {key: signature(t, pool["reference"]["floor_xz_h"], diagnostic_cache) for key, t in teams.items()}
            for event in events:
                row = event_row(event, teams, signatures, meta, feature_map, origins)
                sink.append({k: v for k, v in row.items() if not k.startswith("_")})
                rows.append(row)
            all_requested.update(wanted)
            all_observed.update(teams)
            receipt = dict(pool_id=pid, events=len(events), requested_teams=len(wanted), observed_teams=len(teams),
                           missing_teams=len(missing), diagnostic_geometries=len(diagnostic_cache))
            receipts.append(receipt)
            print(compact_json(receipt), flush=True)
        sink.close()
    except BaseException:
        sink.abort()
        raise
    frame = pd.DataFrame(rows)
    for metric in SUMMARY_METRICS:
        frame[metric] = pd.to_numeric(frame[metric], errors="raise")
    summaries = []
    base = ["phase", "method_id", "domain", "scale"]
    views = {
        "method": base,
        "number_scale": base + ["k", "m"],
        "condition": base + ["k", "difficulty", "scene"],
        "directed_block": base + ["outgoing_counts", "incoming_counts", "k", "m", "matching", "matched_origin", "difficulty", "scene"],
        "full_composition": base + ["A_composition", "C_composition", "k", "m", "matching", "difficulty"],
    }
    subsets = {
        "all_events": np.ones(len(frame), bool),
        "actual_source_matched": frame.actual_source_match.to_numpy(bool),
        "incoming_history_Q_close_3": frame.incoming_Q_close_3.to_numpy(bool),
        "source_and_incoming_Q_close_3": (frame.actual_source_match & frame.incoming_Q_close_3).to_numpy(bool),
    }
    for subset, mask in subsets.items():
        for view, grouping in views.items():
            table = aggregate(frame.loc[mask].copy(), grouping, view, subset)
            summaries.append(table)
            print(compact_json(dict(summary_subset=subset, view=view, rows=len(table))), flush=True)
    out = pd.concat(summaries, ignore_index=True)
    out.to_csv(args.out / "block_summary.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    compact = out[out.view.isin(["method", "number_scale", "condition"])].copy()
    compact.to_csv(args.out / "block_core_summary.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    ledger = pd.DataFrame(manifest["ledger"])
    for column in ledger:
        if ledger[column].map(lambda x: isinstance(x, (dict, list))).any():
            ledger[column] = ledger[column].map(compact_json)
    ledger.to_csv(args.out / "block_search_ledger.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    receipt = {
        "schema": "personnel_composition_matched_blocks_summary_v1", "phase": args.phase,
        "events": len(frame), "primary_m_ge_2": int(frame.m.ge(2).sum()), "auxiliary_m_1": int(frame.m.eq(1).sum()),
        "images": int(frame.image_id.nunique()), "pools": int(frame.pool_id.nunique()), "buildings": int(frame.building.nunique()),
        "workers": union_size(frame._workers), "requested_unique_teams": len(all_requested), "observed_unique_teams": len(all_observed),
        "missing_computation_teams": len(all_requested - all_observed), "computed_events": int(frame.computed_arms_n.eq(3).sum()),
        "source_matched_by_design_events": int(frame.matching.eq("source_matched").sum()),
        "source_matched_actual_events": int(frame.actual_source_match.sum()),
        "incoming_Q_close_3_events": int(frame.incoming_Q_close_3.sum()),
        "B_C_turnover_less_than_matched_A_B_A_C_m": int((frame.net_turnover < frame.m).sum()),
        "summary_rows": len(out), "core_summary_rows": len(compact), "exact_members_and_compositions_rebuilt": True,
        "allowed_buildings": sorted(allowed), "observed_buildings": sorted(frame.building.unique()),
        "validation_read": args.phase == "validation", "full_manifest_pool_coverage": not bool(args.pool),
        "independence": "Overlapping teams and events are not independent samples. Counts deduplicate real images, buildings, workers and exact teams; headline means average images within buildings then buildings.",
        "net_direction": "C minus B, with real mutual turnover retained. A-B and A-C have exactly the same replacement m and shared core.",
        "Q_control": "Incoming C-versus-B historical mean Q difference within 3. Uses q_beta globally, theta_easy/medium/hard in difficulty domains and own-condition q_effect elsewhere. Missing history Q excludes the controlled subset, not the overall utility. No target Q used.",
        "source_control": "Same complete outgoing/within/cross origin-count vector; includes unrestricted events that happen to match, and explicit source_matched events. Explicit design mode is also retained in detailed summary.",
        "joint_stability_main": MAIN_TOLERANCES,
        "quality_tails": "Finite scores only; p10/p90 and direction flags are conditional on observed comparable scores. Computation missing and computed fusion/measurement failures remain separate.",
        "reference_diagnostics": "Nearest-angle reference nodes/adjacency and separate wall/corner geometry diagnostics are not semantic necessary-structure correctness.",
        "selection_coverage": "Finite class-count candidate frame stratified by source mode, outgoing/incoming pattern and m, capped by event quota; one deterministic member draw per accepted pattern. Not exhaustive actual teams.",
        "input_hashes": {str(p): sha(p) for p in [args.requests, args.features, args.snapshot, args.split] + args.labels},
        "code_hashes": {str(p): sha(p) for p in [Path(__file__), Path(__file__).with_name("summarize_grid.py"), Path(__file__).with_name("geometry_diagnostics.py")]},
        "by_pool": receipts,
    }
    write(args.out / "BLOCK_SUMMARY_RECEIPT.json", receipt)
    print(compact_json({k: v for k, v in receipt.items() if k not in ("by_pool", "input_hashes", "code_hashes")}))
    return receipt


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--requests", type=Path, required=True)
    ap.add_argument("--runs", type=Path, required=True)
    ap.add_argument("--labels", type=Path, action="append", required=True)
    ap.add_argument("--features", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--split", type=Path, required=True)
    ap.add_argument("--phase", choices=("discovery", "validation"), default="discovery")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--pool", action="append", help="Explicit completed-pool pilot filter")
    ap.add_argument("--allow-partial", action="store_true", help="Count uncomputed teams separately, never as failed fusion")
    summarize(ap.parse_args())


if __name__ == "__main__":
    main()
