#!/usr/bin/env python3
"""Audit six already executed strict ABC cases; no fitting or extra fusion.

All metrics are joined from frozen event results. Derived source-ring coverage,
vote membership, and common-D correspondences are computed from exact traces.
Cross-arm groups are linked through original (object_id, source_pair_index),
never by the local node_XXX identifier. The cases were selected after the full
new experiment for mechanism explanation, not as a probability sample.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import math
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

CASES = [
    ("2978172ce6fe180ffe50e2dc", "high_Q_concentration_and_position_change"),
    ("8ffd905ec3a4770f8606cd93", "shared_position_direction_bias_full_votes"),
    ("7881ea8d8b010028bc505a47", "within_class_member_variation_threshold"),
    ("ce5e6ff5c300c3022395c8d6", "half_vote_competing_corners_no_connection"),
    ("0836672f35ad7742021ab716", "positive_short_fold_and_correspondence_change"),
    ("bd186f9502bc8688246f76d7", "fixed_scope_partial_old_branch_no_connection"),
]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for x in iter(lambda: f.read(1024 * 1024), b""):
            h.update(x)
    return h.hexdigest()


def load_json(path: Path):
    with (gzip.open(path, "rt") if path.suffix == ".gz" else path.open()) as f:
        return json.load(f)


def save_csv(path: Path, rows):
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def angular_matrix(a, b):
    def rays(p):
        p = np.asarray(p, float)
        az = p[:, 0] * 2 * np.pi / 1024
        el = (.5 - p[:, 1] / 512) * np.pi
        return np.column_stack([-np.sin(az) * np.cos(el),
                                np.cos(az) * np.cos(el), np.sin(el)])
    return np.rad2deg(np.arccos(np.clip(rays(a) @ rays(b).T, -1, 1)))


def finite(x):
    return x is not None and np.isfinite(float(x))


def delta(a, b):
    return float(a) - float(b) if finite(a) and finite(b) else np.nan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--labels-original", type=Path, required=True)
    parser.add_argument("--labels-new", type=Path, required=True)
    parser.add_argument("--scope-adjudication", type=Path, required=True)
    args = parser.parse_args()
    work = args.work
    results = work / "results"
    results.mkdir(parents=True, exist_ok=True)
    source_paths = {
        "events": args.stage / "EVENTS_EXACT.csv.gz",
        "metrics": args.stage / "metrics/EVENT_METRICS.csv.gz",
        "original_labels": args.labels_original,
        "new_labels": args.labels_new,
        "existing_S9_scope": args.scope_adjudication,
    }
    ids = {x[0] for x in CASES}
    events = pd.read_csv(source_paths["events"], dtype=str).set_index("event_id")
    event_metrics = pd.concat(
        [c[c.event_id.isin(ids)] for c in pd.read_csv(source_paths["metrics"], chunksize=4000)],
        ignore_index=True,
    ).set_index("event_id")
    labels = pd.concat([pd.read_csv(args.labels_original), pd.read_csv(args.labels_new)])
    labels = labels[labels.method.isin(["TARGET_DSTRUCT_K3", "V21_DSTRUCT_RAW3_K3"])]
    label_lookup = {(r.method, r.heldout_building, r.worker_id): str(r.class_id)
                    for r in labels.itertuples() if str(r.known).lower() in {"true", "1"}}
    snapshots = []
    arm_rows = []
    group_rows = []
    member_rows = []
    common_rows = []
    reference_rows = []
    strict_checks = []
    summaries = []

    for event_id, purpose in CASES:
        path = work / "traces" / (event_id + ".json.gz")
        trace = load_json(path)
        e = trace["event"]
        assert e["event_id"] == event_id and event_id in events.index
        for key in ["A_team_key", "B_team_key", "C_team_key", "D", "X", "Y", "Z", "method"]:
            assert str(e[key]) == str(events.loc[event_id, key]), (event_id, key)
        blocks = {k: set(e[k].split("|")) - {""} for k in "DXYZ"}
        assert all(not blocks[a] & blocks[b] for a, b in itertools.combinations("DXYZ", 2))
        n, m = int(e["n"]), int(e["m"])
        assert n == 16 and m == 8
        assert len(blocks["D"]) == n - m and all(len(blocks[x]) == m for x in "XYZ")
        assert e["condition"] == "manual" and e["layer"] == "ordinary_manual"
        for block in "XYZ":
            expected = e["target_class"] if block == "Z" else e["source_class"]
            actual = {label_lookup.get((e["method"], e["building"], w), "UNKNOWN")
                      for w in blocks[block]}
            # Historical files represent class identifiers either as C2 or 2.
            assert {x.removeprefix("C").removesuffix(".0") for x in actual} == {
                str(expected).removeprefix("C").removesuffix(".0")}, (event_id, block, actual)
        strict_checks.append(dict(event_id=event_id, all_four_blocks_disjoint=True,
                                  exact_team_sizes=True, LOBO_source_X_Y_pure=True,
                                  LOBO_target_Z_pure=True, source_and_target_different=True))
        snapshots.append(dict(event_id=event_id, image=e["image"], purpose=purpose,
                              method=e["method"], n=n, m=m,
                              source_class=e["source_class"], target_class=e["target_class"],
                              heldout_building=e["building"], reference_id=e["reference_id"],
                              reference_version=e["reference_version"],
                              selection="after_full_results_for_mechanism_not_random_sample",
                              trace_sha256=digest(path)))
        maps = {}
        ref = np.asarray(trace["reference"]["points_1024x512"], float).reshape((-1, 2, 2))
        for arm, block in zip("ABC", "XYZ"):
            a = trace["arms"][arm]
            fs = a["full_state"]
            assert set(a["member_workers"]) == blocks["D"] | blocks[block]
            selected = {g["feature_id"] for g in fs["identity_groups"] if g["selected"]}
            cover = [r["worker"] for r in fs["assignments"] if selected <= set(r["feature_ids"])]
            assert len(selected) == int(a["nodes"])
            if a["score_status"] == "no_connection":
                assert not cover and a["B8L2"] is None
            row = {k: v for k, v in a.items()
                   if k not in {"full_state", "geometry", "parity"} and not isinstance(v, (dict, list))}
            row.update(event_id=event_id, arm=arm, image=e["image"],
                       source_ring_covering_all_selected_n=len(cover),
                       source_ring_covering_all_selected_workers="|".join(sorted(cover)))
            arm_rows.append(row)
            obs_map = {}
            for g in fs["identity_groups"]:
                who = {member["worker"] for member in g["members"]}
                assert len(who) == int(g["support"])
                assert who <= blocks["D"] | blocks[block]
                assert bool(g["selected"]) == (len(who) >= int(fs["minimum_support"]))
                center = np.asarray(g["center"], float)
                group_rows.append(dict(event_id=event_id, arm=arm, feature_id=g["feature_id"],
                                       support=len(who), selected=bool(g["selected"]),
                                       minimum_support=int(fs["minimum_support"]),
                                       D_support=len(who & blocks["D"]),
                                       replacement_support=len(who & blocks[block]),
                                       D_workers="|".join(sorted(who & blocks["D"])),
                                       replacement_workers="|".join(sorted(who & blocks[block])),
                                       top_x_px=center[0, 0], top_y_px=center[0, 1],
                                       bottom_x_px=center[1, 0], bottom_y_px=center[1, 1]))
                for member in g["members"]:
                    obs = (str(member["id"]), int(member["source_pair_index"]))
                    actual_block = "D" if member["worker"] in blocks["D"] else block
                    member_rows.append(dict(event_id=event_id, arm=arm, feature_id=g["feature_id"],
                                            block=actual_block, worker=member["worker"],
                                            object_id=obs[0], source_pair_index=obs[1],
                                            points_json=json.dumps(member["points"], separators=(",", ":"))))
                    if actual_block == "D":
                        assert obs not in obs_map
                        obs_map[obs] = g["feature_id"]
            maps[arm] = obs_map
            selected_groups = [g for g in fs["identity_groups"] if g["selected"]]
            if len(selected_groups) == len(ref):
                points = np.array([g["center"] for g in selected_groups], float)
                cost = angular_matrix(points[:, 1, :], ref[:, 1, :])
                gi, ri = linear_sum_assignment(cost)
                for ii, jj in zip(gi, ri):
                    pred = points[ii]
                    actual = ref[jj]
                    reference_rows.append(dict(event_id=event_id, arm=arm,
                        feature_id=selected_groups[ii]["feature_id"],
                        reference_index_1based=int(jj) + 1,
                        selected_and_reference_counts_equal=True,
                        bottom_spherical_angle_deg=float(cost[ii, jj]),
                        top_signed_vertical_offset_px=float(pred[0, 1] - actual[0, 1]),
                        bottom_signed_vertical_offset_px=float(pred[1, 1] - actual[1, 1]),
                        signed_azimuth_offset_deg=float(((pred[1, 0] - actual[1, 0] + 512) % 1024 - 512) * 360 / 1024),
                        matching="minimum_total_bottom_spherical_angle_diagnostic_only"))
        for other in "BC":
            a, b = maps["A"], maps[other]
            assert set(a) == set(b), (event_id, other, "background observations changed")
            changed = []
            for u, v in itertools.combinations(sorted(a), 2):
                if (a[u] == a[v]) != (b[u] == b[v]):
                    changed.append({"observation_1": list(u), "observation_2": list(v),
                                    "coassigned_A": a[u] == a[v],
                                    "coassigned_other": b[u] == b[v]})
            common_rows.append(dict(event_id=event_id, other_arm=other,
                                    common_D_observations_n=len(a),
                                    pairwise_coassignment_changed_n=len(changed),
                                    changed_pairs_json=json.dumps(changed, separators=(",", ":")),
                                    local_group_names_not_used_as_cross_arm_identity=True))
        qa, qb, qc = [trace["arms"][x]["B8L2"] for x in "ABC"]
        within = abs(delta(qb, qa))
        ac = abs(delta(qc, qa))
        cross = (ac + abs(delta(qc, qb))) / 2
        summary = dict(event_id=event_id, image=e["image"], method=e["method"],
                       source_class=e["source_class"], target_class=e["target_class"], n=n, m=m,
                       Q_A=qa, Q_B=qb, Q_C=qc, Q_B_minus_A=delta(qb, qa),
                       Q_C_minus_A=delta(qc, qa), Q_C_minus_B=delta(qc, qb),
                       Q_within_pairwise_AB=within, Q_cross_symmetric=cross,
                       Q_symmetric_gap=cross - within, Q_cross_direct_AC=ac,
                       Q_direct_gap=ac - within, Q_ABC_evaluable=finite(qc) and finite(qa) and finite(qb))
        for metric in ["nodes", "IoU3D100", "iou_2d", "dir", "S_bottom_deg", "Hmean",
                       "boundary_loss", "direction_loss", "height_loss", "geometry_area_h2",
                       "source_time_known_n", "source_time_total_seconds", "recorded_time_total_seconds"]:
            for arm in "ABC":
                summary[f"{metric}_{arm}"] = trace["arms"][arm].get(metric)
        for key in ["time_comparable_ABC", "time_source_signature_A", "time_source_signature_B",
                    "time_source_signature_C", "record_time_BA_pct_source_matched",
                    "record_time_CA_pct_source_matched", "record_time_CB_pct_source_matched",
                    "geometry_pair_angle_AB", "geometry_pair_angle_AC",
                    "geometry_bev_distance_AB", "geometry_bev_distance_AC"]:
            summary[key] = event_metrics.loc[event_id, key]
        summaries.append(summary)

    save_csv(results / "CASE_SELECTION.csv", snapshots)
    save_csv(results / "CASE_SUMMARY.csv", summaries)
    save_csv(results / "CASE_ARM_METRICS_AND_RING_COVERAGE.csv", arm_rows)
    save_csv(results / "CASE_EXACT_VOTE_GROUPS.csv", group_rows)
    save_csv(results / "CASE_VOTE_MEMBERS.csv.gz", member_rows)
    save_csv(results / "COMMON_D_COASSIGNMENT_DIAGNOSTIC.csv", common_rows)
    save_csv(results / "SAME_COUNT_REFERENCE_POSITION_DIAGNOSTIC.csv", reference_rows)
    save_csv(results / "STRICT_ABC_CASE_CHECKS.csv", strict_checks)
    save_csv(results / "CASE_EXACT_EVENT_ROWS.csv", events.loc[[x[0] for x in CASES]].reset_index())
    save_csv(results / "CASE_FULL_EVENT_METRICS.csv.gz", event_metrics.loc[[x[0] for x in CASES]].reset_index())
    shutil.copy2(args.scope_adjudication, work / "source/S9_09_EXISTING_SCOPE_ADJUDICATION.json")
    receipt = {
        "source_sha256": {k: {"path": str(p), "sha256": digest(p)} for k, p in source_paths.items()},
        "case_n": len(CASES), "arms_n": len(arm_rows), "groups_n": len(group_rows),
        "vote_observations_n": len(member_rows), "additional_physical_teams": 0,
        "replay_purpose": "trace only, exact scalar parity checked separately",
        "selection_phase": "after complete new experiment, explanatory selection, no population inference",
        "cross_symmetric": "(|C-A|+|C-B|)/2", "within": "|B-A|",
        "cross_direct": "|C-A|", "Q_missing_policy": "missing, never zero",
        "reference_change": "none", "all_cases_strict_ABC_checks_passed": True,
    }
    (results / "MECHANISM_AUDIT_RECEIPT.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: receipt[k] for k in ["case_n", "arms_n", "groups_n", "vote_observations_n", "additional_physical_teams"]}))


if __name__ == "__main__":
    main()
