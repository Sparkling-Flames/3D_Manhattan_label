#!/usr/bin/env python3
"""Concrete discovery examples, explicitly selected for reporting after search.

The complete exact-stratum and LOOW ledgers remain available. These highlights
include quality improvements, losses, multi-class changes and a counterexample.
They do not redefine validation rules or recalculate personnel labels.
"""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
from summarize_grid import canonical_counts, labels_from_files, sha


DEFINITIONS = [
    ("Q_low_to_high_n5m2", "F_rule_Q_threshold_K3", "all", 5, 2, {"C01": 2}, {"C03": 2}),
    ("Q_mid_to_high_n9m4", "F_rule_Q_threshold_K3", "all", 9, 4, {"C02": 4}, {"C03": 4}),
    ("Q_high_to_low_n5m2", "F_rule_Q_threshold_K3", "all", 5, 2, {"C03": 2}, {"C01": 2}),
    ("Q_two_classes_to_high_n5m2", "F_rule_Q_threshold_K3", "all", 5, 2, {"C01": 1, "C02": 1}, {"C03": 2}),
    ("Qdetail_low_sparse_to_two_high_n5m2", "F_rule_Q2xDetail2", "all", 5, 2, {"C02": 2}, {"C03": 1, "C04": 1}),
    ("relation_low_to_high_n5m2", "R_geo9_source_signed_p2_K2", "all", 5, 2, {"C01": 2}, {"C02": 2}),
    ("role_common_to_detail_n5m2", "R_role_ward_K5", "all", 5, 2, {"C02": 2}, {"C05": 2}),
    ("role_lower_to_detail_n9m4", "R_role_ward_K5", "all", 9, 4, {"C01": 4}, {"C05": 4}),
    ("role_detail_to_common_n5m2", "R_role_ward_K5", "all", 5, 2, {"C05": 2}, {"C02": 2}),
    ("hard_low_to_detail_n5m2", "R_role_ward_difficulty_K2", "hard", 5, 2, {"C01": 2}, {"C02": 2}),
    ("hard_low_to_detail_n9m4", "R_role_ward_difficulty_K2", "hard", 9, 4, {"C01": 4}, {"C02": 4}),
    ("hard_two_classes_to_detail_n5m2", "R_role_ward_difficulty_K2", "hard", 5, 2, {"C01": 1, "C02": 1}, {"C02": 2}),
    ("hard_detail_to_mixed_counterexample_n13m2", "R_role_ward_difficulty_K2", "hard", 13, 2, {"C02": 2}, {"C01": 1, "C02": 1}),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("analysis/composition"))
    ap.add_argument("--labels", type=Path, action="append", required=True)
    ap.add_argument("--phase", choices=("discovery", "validation"), default="discovery")
    ap.add_argument("--out", type=Path, default=Path("analysis/composition/block_discovery_specific"))
    args = ap.parse_args()
    labels = labels_from_files(args.labels)
    events = pd.read_csv(args.root / ("block_" + args.phase) / "block_events.csv.gz", low_memory=False)
    table = pd.read_csv(args.out / "directed_exact_summary.csv.gz", low_memory=False)
    table = table[table.view.eq("exact_counts_k_m")]
    loow = pd.read_csv(args.out / "leave_one_worker_summary.csv.gz", low_memory=False)
    assert set(events.phase) == {args.phase}
    keys = ["method_id", "domain", "outgoing_counts", "incoming_counts", "k", "m"]
    rows, selected_events, definitions, source_rows = [], [], [], []
    for tag, method, domain, k, m, oc, ic in DEFINITIONS:
        classes = sorted(set(labels[method, domain].values()))
        outgoing = canonical_counts({c: oc.get(c, 0) for c in classes})
        incoming = canonical_counts({c: ic.get(c, 0) for c in classes})
        key = dict(method_id=method, domain=domain, outgoing_counts=outgoing, incoming_counts=incoming, k=k, m=m)
        definitions.append(dict(highlight_id=tag, **key, information_stage="discovery_report_selection_after_broad_search"))
        def take(frame):
            mask = np.ones(len(frame), bool)
            for col, value in key.items():
                mask &= frame[col].eq(value).to_numpy()
            return frame.loc[mask]
        chosen = take(table)
        event_group = take(events)
        lw = take(loow)
        source_masks = {
            "all_events": np.ones(len(event_group), bool),
            "actual_source_matched": event_group.actual_source_match,
            "matched_new_incoming_blocks": event_group.actual_source_match & event_group.outgoing_new_n.eq(m),
            "matched_v1_incoming_blocks": event_group.actual_source_match & event_group.outgoing_new_n.eq(0),
            "all_new_teams": event_group.A_new_n.eq(k) & event_group.B_new_n.eq(k) & event_group.C_new_n.eq(k),
            "incoming_history_Q_close_3": event_group.incoming_Q_close_3,
            "source_and_incoming_Q_close_3": event_group.actual_source_match & event_group.incoming_Q_close_3,
            "matched_new_and_Q_close_3": event_group.actual_source_match & event_group.outgoing_new_n.eq(m) & event_group.incoming_Q_close_3,
            "matched_v1_and_Q_close_3": event_group.actual_source_match & event_group.outgoing_new_n.eq(0) & event_group.incoming_Q_close_3,
        }
        metrics = ["net_B8L2_change", "net_D10_change", "within_abs_B8L2_change", "changed_abs_B8L2_change", "excess_abs_B8L2_change",
                   "within_floor_jaccard_difference", "changed_floor_jaccard_difference", "excess_floor_jaccard_difference",
                   "net_ref_edge_recall_9_change", "net_diag_wall_coverage_05_change", "within_joint_stable_main", "changed_joint_stable_main"]
        for subset, mask in source_masks.items():
            g = event_group.loc[mask]
            workers = set()
            for column in ("core_workers_json", "outgoing_workers_json", "within_incoming_json", "cross_incoming_json"):
                for v in g[column]:
                    workers.update(json.loads(v))
            teams = set(g.A_team_key) | set(g.B_team_key) | set(g.C_team_key)
            sr = dict(highlight_id=tag, phase=args.phase, **key, subset=subset, events=len(g), images=g.pool_id.nunique(),
                      buildings=g.building.nunique(), workers=len(workers), unique_teams=len(teams),
                      status="no_matching_member_opportunity" if not len(g) else "descriptive_supported_events",
                      historical_Q_column="theta_hard" if domain == "hard" else "q_beta")
            bm = g.groupby(["pool_id", "building"])[metrics].mean().reset_index().groupby("building")[metrics].mean()
            for metric in metrics:
                sr[metric + "_equal_building_mean"] = float(bm[metric].mean()) if len(bm) else None
                sr[metric + "_finite_events"] = int(g[metric].notna().sum())
                sr[metric + "_finite_images"] = int(g.loc[g[metric].notna(), "pool_id"].nunique())
                sr[metric + "_finite_buildings"] = int(bm[metric].notna().sum())
            q = g.net_B8L2_change.dropna()
            sr["net_B8L2_change_event_p10"] = float(q.quantile(.1)) if len(q) else None
            sr["positive_Q_buildings"] = int(bm.net_B8L2_change.gt(0).sum())
            sr["negative_Q_buildings"] = int(bm.net_B8L2_change.lt(0).sum())
            sr["net_restored_complete_events"] = int(g.net_complete_restored.eq(True).sum())
            sr["net_lost_complete_events"] = int(g.net_complete_lost.eq(True).sum())
            sr["B_score_missing_events"] = int(g.B_B8L2.isna().sum())
            sr["C_score_missing_events"] = int(g.C_B8L2.isna().sum())
            sr["incoming_historical_Q_difference_event_mean"] = float(g.cross_minus_within_history_Q.mean()) if len(g) else None
            source_rows.append(sr)
        for record in chosen.to_dict("records"):
            subset = record["subset"]
            g = event_group if subset == "all_events" else event_group[event_group.actual_source_match] if subset == "actual_source_matched" else event_group[event_group.incoming_Q_close_3] if subset == "incoming_history_Q_close_3" else event_group[event_group.incoming_Q_close_3 & event_group.actual_source_match]
            assert len(g) == record["events"]
            record["highlight_id"] = tag
            for arm in "ABC":
                record[arm + "_incomplete_events"] = int(g[arm + "_complete"].eq(False).sum())
                record[arm + "_score_missing_events"] = int(g[arm + "_B8L2"].isna().sum())
            record["net_restored_complete_events"] = int(g.net_complete_restored.eq(True).sum())
            record["net_lost_complete_events"] = int(g.net_complete_lost.eq(True).sum())
            record["incoming_Q_close_3_events"] = int(g.incoming_Q_close_3.sum())
            record["historical_incoming_Q_difference_event_mean"] = float(g.cross_minus_within_history_Q.mean())
            lr = lw[lw.subset == subset]
            assert len(lr) <= 1
            if len(lr):
                for col in ("removed_workers_tested", "base_workers", "min_remaining_events", "max_removed_event_fraction",
                            "min_remaining_images", "min_remaining_buildings", "removals_retaining_three_Q_buildings",
                            "removals_losing_three_Q_buildings", "retained3b_net_B8L2_change_min", "retained3b_net_B8L2_change_max",
                            "retained3b_net_ref_edge_recall_9_change_min", "retained3b_net_ref_edge_recall_9_change_max",
                            "retained3b_Q_direction_reversals", "largest_Q_gain_removed_worker", "smallest_Q_gain_removed_worker"):
                    record["loow_" + col] = lr.iloc[0][col]
            rows.append(record)
        finite = event_group[event_group.net_B8L2_change.notna()]
        if len(finite):
            for kind, idx in (("largest_Q_gain", finite.net_B8L2_change.idxmax()), ("smallest_Q_gain", finite.net_B8L2_change.idxmin())):
                e = finite.loc[idx].to_dict()
                e.update(highlight_id=tag, case_kind=kind, selected_from="all_" + args.phase + "_events_in_this_exact_count_stratum")
                selected_events.append(e)
            similar = finite[finite.similar_Q2_changed_structure.eq(True)]
            if len(similar):
                e = similar.iloc[0].to_dict()
                e.update(highlight_id=tag, case_kind="similar_Q_structural_change", selected_from="first_event_id_order_matching_explicit_condition")
                selected_events.append(e)
    pd.DataFrame(rows).to_csv(args.out / "highlight_summary.csv", index=False)
    pd.DataFrame(source_rows).to_csv(args.out / "highlight_source_Q_comparison.csv", index=False)
    pd.DataFrame(selected_events).to_csv(args.out / "highlight_event_candidates.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    receipt = dict(phase=args.phase, selection_stage="Illustrative count strata chosen from discovery only; same definitions reused for validation", definitions=definitions,
                   summary_rows=len(rows), representative_event_candidates=len(selected_events),
                   full_search_tables_retained=True, source_code_sha256=sha(__file__))
    (args.out / "HIGHLIGHT_DEFINITIONS.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    cols = ["highlight_id", "subset", "events", "images", "buildings", "net_B8L2_change_n", "net_B8L2_change_equal_building_mean",
            "net_B8L2_change_event_p10", "within_abs_B8L2_change_equal_building_mean", "changed_abs_B8L2_change_equal_building_mean",
            "net_lost_complete_events", "net_restored_complete_events", "loow_retained3b_net_B8L2_change_min", "loow_retained3b_net_B8L2_change_max",
            "loow_removals_losing_three_Q_buildings"]
    print(pd.DataFrame(rows).loc[lambda z: z.subset.eq("all_events"), cols].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
