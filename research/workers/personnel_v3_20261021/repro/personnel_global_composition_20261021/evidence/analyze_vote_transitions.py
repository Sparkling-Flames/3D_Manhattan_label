#!/usr/bin/env python3
"""Audit exact observations across selected native vote states, without re-fusion.

Node numbers are local to each member set. Correspondence here is by immutable
(record id, pair index) overlap, never by assuming node_007 means the same thing
in another endpoint. The counterfactual counts are diagnostics only, not scores.
"""
from __future__ import annotations
import collections
import itertools
import math
from pathlib import Path
import sys

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "composition"))
import global_study as gs


def obs(g):
    return {(m["id"], int(m["pair_index"])) for m in g["members"]}


def main():
    label = pd.read_csv(ROOT / "research/workers/personnel_taxonomy_20261021/labels/lobo_labels.csv")
    multivariate = pd.read_csv(HERE.parent / "multivariate/labels_lobo.csv.gz")
    features = pd.read_csv(HERE.parent / "multivariate/continuous_features_lobo.csv.gz")
    transitions, group_links, scores, worker_support, group_votes, exact_members = [], [], [], [], [], []
    for path in sorted((HERE / "cases").glob("*.json.gz")):
        case = gs.read(path)
        lookup = {m["worker_id"]: m for m in case["members"]}
        by_class = {w: m["class_id"] for w, m in lookup.items()}
        for member in case["members"]:
            exact_members.append(dict(case_id=case["case_id"], method_id=case["method_id"], tier=case["tier"],
                worker_id=member["worker_id"], object_id=member["id"], origin=member["origin"], class_id=member["class_id"],
                target_B8L2=member.get("B8L2"), target_D10=member.get("D10"), target_pair_count=len(member["points"])//2,
                source_time_seconds=member.get("source_time_seconds"), source_time_kind=member.get("time_source_kind"),
                arms="|".join(t["label"] for t in case["teams"] if member["worker_id"] in t["member_workers"])))
        for team in case["teams"]:
            row = {k: team.get(k) for k in ["team_key", "image", "condition", "k", "nodes", "minimum_support", "B8L2", "D10", "IoU3D100", "iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter", "omission", "extension", "height_mean_ratio", "score_status", "ref_node_recall_9", "ref_edge_recall_9", "source_time_total_seconds", "source_time_known_n", "target_time_total_seconds", "target_time_known_n", "geometry_status", "below_four", "location_unresolved", "connection_available"]}
            row.update(case_id=case["case_id"], method_id=case["method_id"], tier=case["tier"], arm=team["label"], composition=gs.canonical_counts(team["counts"]))
            scores.append(row)
            for g in team["full_state"]["identity_groups"]:
                group_votes.append(dict(case_id=case["case_id"], arm=team["label"], feature_id=g["feature_id"],
                    support=g["support"], threshold=team["minimum_support"], selected=g["selected"],
                    top_x=g["center"][0][0], top_y=g["center"][0][1], bottom_x=g["center"][1][0], bottom_y=g["center"][1][1],
                    class_votes=gs.canonical_counts(collections.Counter(by_class[m["worker"]] for m in g["members"])),
                    member_workers="|".join(sorted(m["worker"] for m in g["members"])),
                    observation_keys="|".join(f"{x[0]}:{x[1]}" for x in sorted(obs(g)))))
        for a, b in itertools.combinations(case["teams"], 2):
            analyze_pair(case, a, b, transitions, group_links)
        selected_workers = set(case.get("raw_overlay_workers", []))
        selected_workers.update(w for g in case.get("raw_overlay_groups", []) for w in g["workers"])
        for w in sorted(selected_workers):
            row = dict(case_id=case["case_id"], worker_id=w, method_id=case["method_id"], tier=case["tier"],
                heldout_building=case["pool_meta"]["building"], condition=case["pool_meta"]["condition"],
                target_B8L2=lookup[w].get("B8L2"), target_D10=lookup[w].get("D10"), target_pairs=len(lookup[w]["points"])//2)
            if case["method_id"].startswith("MV_"):
                lab = multivariate[(multivariate.condition == row["condition"]) & (multivariate.heldout_building == row["heldout_building"]) & (multivariate.worker_id == w) & (multivariate.method_id == case["method_id"])]
                assert len(lab) == 1
                rr = lab.iloc[0]
                assert rr.fine_class == by_class[w] if case["tier"] == "fine" else rr.coarse_class == by_class[w]
                row.update(coarse_class=rr.coarse_class, fine_class=rr.fine_class, support=rr.support,
                    label_status=rr.label_status, label_source="multivariate/labels_lobo.csv.gz")
                ff = features[(features.condition == row["condition"]) & (features.heldout_building == row["heldout_building"]) & (features.worker_id == w)]
                assert len(ff) == 1
                for field in ["q_tasks", "q_buildings", "q_records", "Q_supported", "q_effect", "q_downside", "t_tasks", "t_buildings", "t_records", "T_supported", "t_effect", "t_tail", "time_source_kind", "time_unit", "easy_tasks", "easy_buildings", "easy_supported", "medium_tasks", "medium_buildings", "medium_supported", "hard_tasks", "hard_buildings", "hard_supported", "D_supported", "hard_minus_easy", "medium_minus_easy"]:
                    row[field] = ff.iloc[0][field]
            else:
                lab = label[(label.condition == row["condition"]) & (label.heldout_building == row["heldout_building"]) & (label.worker_id == w)]
                assert len(lab) == 1
                rr = lab.iloc[0]
                row.update(coarse_class=rr.primary_coarse_class, fine_class=rr.primary_fine_class, A2_class=rr.geometry_relation_class,
                    structure_train_images=rr.n_images, structure_train_buildings=rr.n_buildings,
                    position_train_images=rr.position_n_train_images, position_train_buildings=rr.position_n_train_buildings,
                    A2_train_images=rr.geometry_n_train_images, A2_train_buildings=rr.geometry_n_train_buildings,
                    label_source="personnel_taxonomy_20261021/labels/lobo_labels.csv")
            worker_support.append(row)
    for name, rows in [("OBSERVATION_TRANSITIONS.csv", transitions), ("GROUP_OVERLAP_LINKS.csv", group_links),
                       ("CASE_ENDPOINT_METRICS.csv", scores), ("REPRESENTATIVE_WORKER_SUPPORT.csv", worker_support),
                       ("GROUP_CLASS_VOTES.csv", group_votes), ("EXACT_CASE_MEMBERS.csv", exact_members)]:
        gs.csv(HERE / name, pd.DataFrame(rows))
    gs.save(HERE / "VOTE_TRANSITION_RECEIPT.json", dict(schema="exact_observation_transition_v2",
            node_ids_not_assumed_portable=True, membership_key="record id + pair index",
            comparisons="all arm pairs; actual replacement count only for equal n", no_score_or_geometry_recompute=True,
            transitions=transitions))
    print(pd.DataFrame(transitions).to_string(index=False))


def analyze_pair(case, a, b, transitions, group_links):
        ga, gb = a["full_state"]["identity_groups"], b["full_state"]["identity_groups"]
        oa, ob = {g["feature_id"]: obs(g) for g in ga}, {g["feature_id"]: obs(g) for g in gb}
        common = set().union(*oa.values()) & set().union(*ob.values())
        pa = {i: frozenset(s & common) for s in oa.values() for i in s & common}
        pb = {i: frozenset(s & common) for s in ob.values() for i in s & common}
        same_a = sum(math.comb(len(s & common), 2) for s in oa.values())
        same_b = sum(math.comb(len(s & common), 2) for s in ob.values())
        same_both = sum(math.comb(len(x & y & common), 2) for x in oa.values() for y in ob.values())
        shared_workers = set(a["member_workers"]) & set(b["member_workers"])
        # Hold A's groups, remove outgoing observations, use B's actual threshold.
        # This count deliberately does not invent assignments for incoming people.
        fixed_a_without_outgoing = [sum(m["worker"] in shared_workers for m in g["members"]) for g in ga]
        row = dict(case_id=case["case_id"], image=case["pool_meta"]["image"],
                   method_id=case["method_id"], tier=case["tier"],
                   arm_A=a["label"], arm_B=b["label"], n_A=a["k"], n_B=b["k"],
                   actual_replacement_m=len(set(a["member_workers"])-set(b["member_workers"])) if a["k"] == b["k"] else None,
                   removed_n=len(set(a["member_workers"])-set(b["member_workers"])), incoming_n=len(set(b["member_workers"])-set(a["member_workers"])),
                   common_people=len(shared_workers), removed_workers="|".join(sorted(set(a["member_workers"])-set(b["member_workers"]))),
                   incoming_workers="|".join(sorted(set(b["member_workers"])-set(a["member_workers"]))),
                   threshold_A=a["minimum_support"], threshold_B=b["minimum_support"],
                   common_observations=len(common), common_observations_with_changed_groupmates=sum(pa[i] != pb[i] for i in common),
                   common_observation_pair_relation_changes=same_a + same_b - 2*same_both,
                   fixed_A_partition_outgoing_removed_B_threshold_node_count=sum(s >= b["minimum_support"] for s in fixed_a_without_outgoing),
                   actual_B_partition_A_threshold_node_count=sum(g["support"] >= a["minimum_support"] for g in gb),
                   delta_B8L2=b["B8L2"] - a["B8L2"], delta_D10=b["D10"] - a["D10"],
                   delta_iou_2d=b["iou_2d"] - a["iou_2d"], delta_direction_error=b["dir"] - a["dir"],
                   same_class_counts=a["counts"] == b["counts"],
                   counterfactual_counts_not_rescored=True)
        transitions.append(row)
        for ag in ga:
            for bg in gb:
                overlap = oa[ag["feature_id"]] & ob[bg["feature_id"]]
                if not overlap:
                    continue
                group_links.append(dict(case_id=case["case_id"], arm_A=a["label"], arm_B=b["label"], A_feature_id=ag["feature_id"], B_feature_id=bg["feature_id"],
                    shared_observations=len(overlap), A_support=ag["support"], B_support=bg["support"],
                    A_selected=ag["selected"], B_selected=bg["selected"],
                    A_center_x=ag["center"][0][0], B_center_x=bg["center"][0][0],
                    A_workers="|".join(sorted(m["worker"] for m in ag["members"])),
                    B_workers="|".join(sorted(m["worker"] for m in bg["members"])),
                    A_observation_keys="|".join(f"{x[0]}:{x[1]}" for x in sorted(oa[ag["feature_id"]])),
                    B_observation_keys="|".join(f"{x[0]}:{x[1]}" for x in sorted(ob[bg["feature_id"]]))))


if __name__ == "__main__":
    main()
