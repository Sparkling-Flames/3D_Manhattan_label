#!/usr/bin/env python3
"""Exact directed block strata and leave-one-worker-out sensitivity.

Consumes the already verified small event table, not fusion caches. Fixed
outgoing/incoming count vectors, k and m remain separate. All strata are kept;
LOOW priority uses only attempted building/event support, never effect sign.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

import numpy as np
import pandas as pd

from summarize_grid import compact_json, labels_from_files, sha
from summarize_blocks import aggregate, SUMMARY_METRICS

STRATUM = ["method_id", "domain", "outgoing_counts", "incoming_counts", "k", "m"]
METRICS = ["net_B8L2_change", "within_abs_B8L2_change", "changed_abs_B8L2_change", "excess_abs_B8L2_change",
           "within_floor_jaccard_difference", "changed_floor_jaccard_difference", "excess_floor_jaccard_difference",
           "net_ref_node_recall_9_change", "net_ref_edge_recall_9_change", "net_diag_wall_coverage_05_change",
           "within_joint_stable_main", "changed_joint_stable_main", "net_complete_lost", "net_complete_restored"]
SUPPORT_METRICS = ["net_B8L2_change", "net_D10_change", "within_abs_B8L2_change", "changed_abs_B8L2_change",
                   "within_floor_jaccard_difference", "changed_floor_jaccard_difference",
                   "net_ref_edge_recall_9_change", "net_diag_wall_coverage_05_change"]


def load_events(path, phase):
    d = pd.read_csv(path, low_memory=False)
    assert set(d.phase) == {phase}
    assert d.event_id.is_unique
    parsed = {key: d[key].map(json.loads) for key in ("core_workers_json", "outgoing_workers_json", "within_incoming_json", "cross_incoming_json")}
    d["_workers"] = [set(c) | set(o) | set(w) | set(x) for c, o, w, x in zip(*parsed.values())]
    d["_teams"] = [{a, b, c} for a, b, c in zip(d.A_team_key, d.B_team_key, d.C_team_key)]
    d["_observed_teams"] = [set(t for t, present in zip(ts, ps) if present)
        for ts, ps in zip(zip(d.A_team_key, d.B_team_key, d.C_team_key),
                          zip(d.A_complete.notna(), d.B_complete.notna(), d.C_complete.notna()))]
    # A common background is an actual image plus exact people.
    d["_core"] = [(p, tuple(ws)) for p, ws in zip(d.pool_id, parsed["core_workers_json"])]
    for column in set(SUMMARY_METRICS) | set(METRICS):
        d[column] = pd.to_numeric(d[column], errors="raise")
    return d


def summaries(frame, out):
    tables, by_building = [], []
    masks = {
        "all_events": np.ones(len(frame), bool),
        "actual_source_matched": frame.actual_source_match.to_numpy(bool),
        "incoming_history_Q_close_3": frame.incoming_Q_close_3.to_numpy(bool),
        "source_and_incoming_Q_close_3": (frame.actual_source_match & frame.incoming_Q_close_3).to_numpy(bool),
    }
    for subset, mask in masks.items():
        d = frame.loc[mask]
        for view, cols in (("exact_counts_k_m", ["phase"] + STRATUM), ("exact_counts_k_m_difficulty", ["phase"] + STRATUM + ["difficulty"])):
            table = aggregate(d, cols, view, subset)
            if table.empty:
                continue
            support = []
            for metric in SUPPORT_METRICS:
                finite = d.loc[d[metric].notna()]
                x = finite.groupby(cols, observed=True, dropna=False).agg(**{
                    metric + "_finite_images": ("pool_id", "nunique"),
                    metric + "_finite_buildings": ("building", "nunique")})
                support.append(x)
            tails = d.groupby(cols, observed=True, dropna=False)[["B_B8L2", "C_B8L2"]].quantile(.1)
            tails.columns = ["B_B8L2_event_p10", "C_B8L2_event_p10"]
            # The aggregate already reports finite buildings for some metrics.
            extra = pd.concat(support + [tails], axis=1)
            table = table.merge(extra.reset_index(), on=cols, how="left", suffixes=("", "_support_check"), validate="one_to_one")
            for column in table.columns:
                if column.endswith("_support_check"):
                    original = column.removesuffix("_support_check")
                    assert np.allclose(table[original].fillna(0), table[column].fillna(0))
                    table = table.drop(columns=column)
            tables.append(table)
            if view == "exact_counts_k_m":
                pool = d.groupby(cols + ["pool_id", "building"], observed=True, dropna=False)[METRICS].mean().reset_index()
                build = pool.groupby(cols + ["building"], observed=True, dropna=False)[METRICS].mean().reset_index()
                cnt = d.groupby(cols + ["building"], observed=True, dropna=False).agg(events=("event_id", "size"), images=("pool_id", "nunique"))
                build = build.merge(cnt.reset_index(), on=cols + ["building"], validate="one_to_one")
                build.insert(0, "subset", subset)
                by_building.append(build)
            print(compact_json(dict(step="exact_summary", subset=subset, view=view, rows=len(table))), flush=True)
    full = pd.concat(tables, ignore_index=True)
    full.to_csv(out / "directed_exact_summary.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    pd.concat(by_building, ignore_index=True).to_csv(out / "directed_exact_by_building.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    return full


def finite_mean(a, axis):
    valid = np.isfinite(a)
    n = valid.sum(axis=axis)
    s = np.where(valid, a, 0.).sum(axis=axis)
    return np.divide(s, n, out=np.full(np.shape(s), np.nan), where=n > 0)


def loow_group(group, labels, subset):
    """Recompute all omitted-worker image/building means together, without refits."""
    first = group.iloc[0]
    key = {c: first[c] for c in ["phase"] + STRATUM}
    workers = sorted(set().union(*group._workers))
    pools = sorted(group.pool_id.unique())
    pool_building = group.groupby("pool_id").building.first().reindex(pools).to_numpy()
    buildings = sorted(set(pool_building))
    incident = np.asarray([[w in ws for w in workers] for ws in group._workers], float)
    vals = group[METRICS].to_numpy(float)
    valid = np.isfinite(vals).astype(float)
    nums = np.where(np.isfinite(vals), vals, 0.)
    W, P, M = len(workers), len(pools), len(METRICS)
    retained_sums = np.zeros((W + 1, P, M))
    retained_counts = np.zeros_like(retained_sums)
    retained_events = np.zeros((W + 1, P))
    for j, pid in enumerate(pools):
        keep = group.pool_id.eq(pid).to_numpy()
        total_sum, total_count = nums[keep].sum(0), valid[keep].sum(0)
        removed_sum, removed_count = incident[keep].T @ nums[keep], incident[keep].T @ valid[keep]
        retained_sums[0, j], retained_counts[0, j] = total_sum, total_count
        retained_sums[1:, j], retained_counts[1:, j] = total_sum - removed_sum, total_count - removed_count
        retained_events[0, j] = keep.sum()
        retained_events[1:, j] = keep.sum() - incident[keep].sum(0)
    pool_means = np.divide(retained_sums, retained_counts, out=np.full_like(retained_sums, np.nan), where=retained_counts > 0)
    building_means = np.stack([finite_mean(pool_means[:, pool_building == b], axis=1) for b in buildings], axis=1)
    means = finite_mean(building_means, axis=1)
    base = dict(key, subset=subset, base_events=len(group), base_images=P, base_buildings=len(buildings), base_workers=W,
                base_teams=len(set().union(*group._teams)))
    base.update({"base_" + metric: means[0, j] for j, metric in enumerate(METRICS)})
    result = []
    mapping = labels[(first.method_id, first.domain)]
    class_sizes = collections.Counter(mapping.values())
    for i, worker in enumerate(workers, 1):
        keep = ~incident[:, i - 1].astype(bool)
        retained = group.loc[keep]
        cls = mapping.get(worker)
        row = dict(base, removed_worker=worker, worker_class=cls, class_history_workers=class_sizes.get(cls, 0),
                   class_workers_remaining_after_removal=class_sizes.get(cls, 0) - int(cls is not None),
                   retained_events=int(retained_events[i].sum()), removed_event_fraction=1 - float(keep.mean()),
                   retained_images=int((retained_events[i] > 0).sum()),
                   retained_buildings=int(sum(np.any(retained_events[i, pool_building == b] > 0) for b in buildings)),
                   retained_workers=len(set().union(*retained._workers)) if len(retained) else 0,
                   retained_teams=len(set().union(*retained._teams)) if len(retained) else 0)
        for j, metric in enumerate(METRICS):
            row["retained_" + metric] = means[i, j]
            row[metric + "_change_after_worker_removal"] = means[i, j] - means[0, j]
            if metric in ("net_B8L2_change", "excess_abs_B8L2_change", "excess_floor_jaccard_difference", "net_ref_edge_recall_9_change"):
                row[metric + "_finite_events"] = int(retained_counts[i, :, j].sum())
                row[metric + "_finite_images"] = int((retained_counts[i, :, j] > 0).sum())
                row[metric + "_finite_buildings"] = int(np.isfinite(building_means[i, :, j]).sum())
        row["supports_three_building_Q_comparison_after_removal"] = row["net_B8L2_change_finite_buildings"] >= 3
        result.append(row)
    return result


def loow(frame, labels, out, minimum_buildings, minimum_events):
    rows, ledger = [], []
    for subset, mask in (("all_events", np.ones(len(frame), bool)), ("actual_source_matched", frame.actual_source_match.to_numpy(bool))):
        for index, (key, g) in enumerate(frame.loc[mask].groupby(STRATUM, observed=True, dropna=False, sort=True)):
            eligible = g.building.nunique() >= minimum_buildings and len(g) >= minimum_events
            info = dict(zip(STRATUM, key))
            ledger.append(dict(info, subset=subset, events=len(g), images=g.pool_id.nunique(), buildings=g.building.nunique(),
                               analyzed=eligible, reason="metadata_support_eligible" if eligible else "below_predefined_building_or_event_support"))
            if not eligible:
                continue
            rows.extend(loow_group(g, labels, subset))
        print(compact_json(dict(step="loow", subset=subset, cumulative_person_stratum_rows=len(rows))), flush=True)
    detail = pd.DataFrame(rows)
    detail.to_csv(out / "leave_one_worker_out.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    pd.DataFrame(ledger).to_csv(out / "leave_one_worker_support_ledger.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    summary = []
    for key, group in detail.groupby(["phase", "subset"] + STRATUM, observed=True, dropna=False):
        info = dict(zip(["phase", "subset"] + STRATUM, key))
        first = group.iloc[0]
        row = dict(info, removed_workers_tested=len(group), base_events=first.base_events, base_images=first.base_images,
                   base_buildings=first.base_buildings, base_workers=first.base_workers, base_teams=first.base_teams,
                   min_remaining_events=int(group.retained_events.min()), max_removed_event_fraction=float(group.removed_event_fraction.max()),
                   min_remaining_images=int(group.retained_images.min()), min_remaining_buildings=int(group.retained_buildings.min()),
                   removals_retaining_three_Q_buildings=int(group.supports_three_building_Q_comparison_after_removal.sum()),
                   removals_losing_three_Q_buildings=int((~group.supports_three_building_Q_comparison_after_removal).sum()))
        kept = group[group.supports_three_building_Q_comparison_after_removal]
        for metric in METRICS:
            v = kept["retained_" + metric].dropna()
            row["base_" + metric] = first["base_" + metric]
            row["retained3b_" + metric + "_min"] = float(v.min()) if len(v) else None
            row["retained3b_" + metric + "_max"] = float(v.max()) if len(v) else None
        base_sign = np.sign(first.base_net_B8L2_change)
        row["retained3b_Q_direction_reversals"] = int((np.sign(kept.retained_net_B8L2_change) * base_sign < 0).sum())
        for sign, name in ((1, "largest_Q_gain"), (-1, "smallest_Q_gain")):
            choices = kept.retained_net_B8L2_change * sign
            row[name + "_removed_worker"] = kept.loc[choices.idxmax(), "removed_worker"] if choices.notna().any() else None
        summary.append(row)
    pd.DataFrame(summary).to_csv(out / "leave_one_worker_summary.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    return len(detail), len(summary), len(ledger)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--events", type=Path, required=True)
    ap.add_argument("--labels", type=Path, action="append", required=True)
    ap.add_argument("--phase", choices=("discovery", "validation"), default="discovery")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--loow-min-buildings", type=int, default=3)
    ap.add_argument("--loow-min-events", type=int, default=12)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    frame = load_events(args.events, args.phase)
    frame = frame.loc[frame.m.ge(2)].copy()
    labels = labels_from_files(args.labels)
    table = summaries(frame, args.out)
    n, nsummary, nledger = loow(frame, labels, args.out, args.loow_min_buildings, args.loow_min_events)
    receipt = dict(phase=args.phase, primary_events=len(frame), directed_summary_rows=len(table), loow_person_stratum_rows=n,
                   loow_analyzed_strata=nsummary, loow_candidate_strata=nledger,
                   loow_gate=dict(minimum_attempted_buildings=args.loow_min_buildings, minimum_attempted_events=args.loow_min_events,
                                  effect_sign_or_outcome_value_used=False),
                   unit="Exact method/domain outgoing/incoming class counts, k, and m. Overall and source-matched strata remain separate.",
                   within="A/B same counts and same m as A/C; net quality C-B, not a within-minus-changed magnitude",
                   tails="p10 of paired C-B differs from C p10 minus B p10; both provided with distinct names. Finite-only support/failures retained.",
                   loow="Delete every event whose A, B or C includes the omitted worker; never refit classes or alter fixed comparisons. Recompute equal-image/equal-building means.",
                   retained3b="LOOW effect ranges describe only removals retaining at least 3 buildings with finite paired B8; removed cases and their smaller support also remain in the detailed table.",
                   input_hashes={str(p): sha(p) for p in [args.events] + args.labels}, source_code_sha256=sha(__file__))
    (args.out / "BLOCK_SPECIFIC_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(compact_json(receipt))


if __name__ == "__main__":
    main()
