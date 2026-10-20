"""Image/building-level benefit summaries for the frozen speed-mixture requests."""
from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from speed_study import clean, read, write, modules, source_pools, rng_for


def finite(value):
    return value is not None and np.isfinite(value)


def paired(row, base, candidate, compare_corners):
    result = dict(row)
    qa, qb = base.get("B8L2"), candidate.get("B8L2")
    ta, tb = base.get("source_time_total_seconds"), candidate.get("source_time_total_seconds")
    ma, mb = base.get("source_parallel_active_seconds"), candidate.get("source_parallel_active_seconds")
    complete = bool(base.get("complete_evaluable") and candidate.get("complete_evaluable"))
    scored = finite(qa) and finite(qb)
    timed = finite(ta) and finite(tb) and ta > 0 and tb > 0
    result.update(base_team_key=base["team_key"], candidate_team_key=candidate["team_key"],
                  base_Q=qa, candidate_Q=qb, both_complete=complete, both_scored=scored,
                  base_failed=not bool(base.get("complete_evaluable")),
                  candidate_failed=not bool(candidate.get("complete_evaluable")),
                  base_nodes=base.get("nodes"), candidate_nodes=candidate.get("nodes"),
                  quality_difference=qb-qa if scored else None,
                  D10_difference=candidate["D10"]-base["D10"] if scored else None,
                  loss_over_5=float(qb < qa-5) if scored else None,
                  source_base_seconds=ta, source_candidate_seconds=tb,
                  source_time_difference=tb-ta if timed else None,
                  source_time_ratio=tb/ta if timed else None,
                  log_source_time_ratio=np.log(tb/ta) if timed else None,
                  parallel_base_seconds=ma, parallel_candidate_seconds=mb,
                  log_parallel_active_ratio=np.log(mb/ma) if finite(ma) and finite(mb) and ma > 0 and mb > 0 else None,
                  quality_within_2=float(abs(qb-qa) <= 2) if scored else None,
                  joint_save20_lose_at_most2=float(complete and scored and timed and tb/ta <= .8 and qb >= qa-2),
                  actual_replaced=len(set(base["member_workers"])-set(candidate["member_workers"])),
                  common_members=len(set(base["member_workers"]) & set(candidate["member_workers"])))
    for column, output in (("diag_corner_recall_05", "corner_recall_difference"),
                           ("diag_wall_coverage_05", "wall_coverage_difference"),
                           ("diag_unmatched_candidate_corners", "unmatched_corner_difference"),
                           ("omission", "omission_difference"), ("extension", "extension_difference")):
        a, b = base.get(column), candidate.get(column)
        result[output] = b-a if finite(a) and finite(b) else None
    if (base.get("geometry") or {}).get("points") is not None and (candidate.get("geometry") or {}).get("points") is not None:
        distance, _ = compare_corners(base, candidate)
    else:
        distance = dict(status="missing_connected_geometry", same_count=False)
    result.update(corner_distance_status=distance["status"], same_count=distance.get("same_count", False),
                  bev_corner_mean_h=distance.get("bev_mean_h"), bev_corner_max_h=distance.get("bev_max_h"),
                  top_corner_mean_h=distance.get("top_mean_h"), bound_angle_deg=distance.get("angle_deg"))
    return result


MEAN_METRICS = ["base_Q", "candidate_Q", "quality_difference", "D10_difference", "both_complete", "both_scored",
                "base_failed", "candidate_failed", "loss_over_5", "source_base_seconds", "source_candidate_seconds",
                "source_time_difference", "log_source_time_ratio", "parallel_base_seconds", "parallel_candidate_seconds",
                "log_parallel_active_ratio", "quality_within_2", "joint_save20_lose_at_most2", "same_count",
                "corner_recall_difference", "wall_coverage_difference", "unmatched_corner_difference",
                "omission_difference", "extension_difference", "bev_corner_mean_h", "bev_corner_max_h",
                "top_corner_mean_h", "actual_replaced", "historical_Q_difference"]
BASE_KEYS = ["layer", "condition", "origin", "domain", "n", "n_fast", "contrast"]


def summarize(frame, keys, bootstrap=False):
    summaries = []
    image_rows = []
    for values, group in frame.groupby(keys, dropna=False, sort=True):
        if not isinstance(values, tuple):
            values = (values,)
        label = dict(zip(keys, values))
        # Same image's reference-pool requests are averaged before building means.
        images = group.groupby(["building", "image_id"])[MEAN_METRICS].mean()
        buildings = images.groupby("building").mean()
        summary = dict(label, comparisons=len(group), pools=group.pool_id.nunique(),
                       images=group.image_id.nunique(), buildings=group.building.nunique(),
                       exact_comparisons=len(group[["base_team_key", "candidate_team_key"]].drop_duplicates()),
                       scored_comparisons=int(group.both_scored.sum()),
                       timed_comparisons=int(group.source_time_ratio.notna().sum()),
                       images_quality_positive=int((images.quality_difference > 0).sum()),
                       images_quality_within2=int((images.quality_difference.abs() <= 2).sum()),
                       buildings_quality_positive=int((buildings.quality_difference > 0).sum()),
                       **buildings.mean().to_dict())
        summary["source_time_ratio"] = np.exp(summary["log_source_time_ratio"])
        summary["parallel_active_ratio"] = np.exp(summary["log_parallel_active_ratio"])
        # The tails are empirical quantiles of the four planned member draws,
        # averaged by image/building; they are not a fitted individual risk model.
        for metric, key in (("base_Q", "base_Q_p10"), ("candidate_Q", "candidate_Q_p10")):
            tails = group.groupby(["building", "image_id"])[metric].quantile(.1)
            summary[key] = tails.groupby("building").mean().mean()
        if bootstrap:
            for metric in ("quality_difference", "log_source_time_ratio"):
                vector = buildings[metric].dropna().to_numpy()
                if len(vector) >= 3:
                    random = rng_for("speed-summary", label, metric)
                    means = vector[random.integers(0, len(vector), size=(2000, len(vector)))].mean(axis=1)
                    low, high = np.quantile(means, [.025, .975])
                    if metric.startswith("log_"):
                        low, high = np.exp([low, high])
                    summary[metric + "_ci_low"] = low
                    summary[metric + "_ci_high"] = high
                    if len(vector) > 1:
                        leave = (vector.sum()-vector)/(len(vector)-1)
                        summary[metric + "_leave_building_min"] = leave.min()
                        summary[metric + "_leave_building_max"] = leave.max()
        summaries.append(summary)
        for (building, image_id), row in images.iterrows():
            image_rows.append(dict(label, building=building, image_id=image_id, **row.to_dict()))
    return pd.DataFrame(summaries), pd.DataFrame(image_rows)


def analyze(repo, out, reuse_pairs=False):
    out = Path(out)
    modules(repo)
    from tools.thesis_main.analysis.personnel_corner_panel_20261020 import compare
    requests = read(out / "requests.json.gz")
    teams = {}
    for path in sorted((out / "final_teams").glob("*.json.gz")):
        teams.update({r["team_key"]: r for r in read(path)})
    requested_keys = {r["team_key"] for r in requests}
    missing = requested_keys - teams.keys()
    if missing:
        raise RuntimeError(f"{len(missing)} prepared teams not yet computed")
    q = pd.DataFrame(requests)
    pairs = []
    cache = {}
    for panel_id, group in ([] if reuse_pairs else q.groupby("panel_id", sort=False)):
        arms = {r["arm"]: r for r in group.to_dict("records")}
        n = int(group.iloc[0].n)
        slow, fast, random = arms["fast0"], arms[f"fast{n}"], arms["random"]
        for i in range(n + 1):
            candidate = arms[f"fast{i}"]
            baselines = [("versus_random", random)]
            if i > 0:
                baselines.append(("versus_slow", slow))
                baselines.append(("one_matched_replacement", arms[f"fast{i-1}"]))
            if i < n:
                baselines.append(("versus_fast", fast))
            if i >= 2:
                baselines.append(("two_matched_replacements", arms[f"fast{i-2}"]))
            for contrast, base in baselines:
                label = {k: candidate[k] for k in (*BASE_KEYS[:-1], "pool_id", "image", "image_id", "building",
                                                  "difficulty", "difficulty_aligned", "replicate", "member_stage",
                                                  "historical_building_subset", "panel_id")}
                label.update(contrast=contrast, historical_Q_difference=candidate["historical_Q_mean"]-base["historical_Q_mean"])
                a, b = teams[base["team_key"]], teams[candidate["team_key"]]
                key = (a["team_key"], b["team_key"])
                if key not in cache:
                    cache[key] = paired({}, a, b, compare)
                pairs.append(dict(label, **cache[key]))
    if reuse_pairs:
        frame = pd.read_csv(out / "paired_comparisons.csv.gz")
        geometry_pair_count = len(frame[["base_team_key", "candidate_team_key"]].drop_duplicates())
    else:
        frame = pd.DataFrame(pairs)
        frame.to_csv(out / "paired_comparisons.csv.gz", index=False)
        geometry_pair_count = len(cache)
    summary, images = summarize(frame, BASE_KEYS, bootstrap=True)
    summary.to_csv(out / "main_summary.csv", index=False)
    images.to_csv(out / "image_effects.csv.gz", index=False)
    for extra, filename in (("difficulty", "difficulty_summary.csv"),
                            ("member_stage", "member_check_summary.csv"),
                            ("historical_building_subset", "building_subset_summary.csv")):
        part = frame if extra != "difficulty" else frame[frame.difficulty_aligned]
        table, _ = summarize(part, BASE_KEYS + [extra])
        table.to_csv(out / filename, index=False)
    # Scalar-only final results are small enough to hand over; all exact requests
    # and selected case inputs remain separately available for native replay.
    scalar = []
    for t in teams.values():
        row = {k: v for k, v in t.items() if not isinstance(v, (list, dict))}
        row["member_workers"] = "|".join(t["member_workers"])
        row["member_object_ids"] = "|".join(t["member_object_ids"])
        scalar.append(row)
    pd.DataFrame(scalar).to_csv(out / "final_scalar_results.csv.gz", index=False)
    candidates = frame[(frame.contrast == "versus_fast") & frame.both_scored & (frame.n_fast > 0)
                       & (frame.n_fast < frame.n) & (frame.quality_difference.abs() >= 5)]
    candidates.sort_values("quality_difference", ascending=False).to_csv(out / "mechanism_candidates.csv", index=False)
    receipt = dict(exact_teams=len(teams), pools=q.pool_id.nunique(), images=q.image_id.nunique(), buildings=q.building.nunique(),
                   prepared_requests=len(requests), paired_comparisons=len(frame),
                   comparison_unique_geometry_pairs=geometry_pair_count,
                   quality_available=sum(finite(t.get("B8L2")) for t in teams.values()),
                   complete=sum(bool(t.get("complete_evaluable")) for t in teams.values()),
                   failure_status_counts=dict(Counter(t.get("score_status", "missing") for t in teams.values() if not finite(t.get("B8L2")))),
                   uncertainty="2,000 building bootstrap draws, descriptive heterogeneity of this historical pool; no independent-team sample-size claim",
                   node_diagnostic="Unmatched candidate corners are disagreement with the fixed reference, not automatically erroneous added structure",
                   shared_results_and_new_members="All four repeats retained, including exact repeats caused by capacity; exact_comparisons recorded separately")
    write(out / "ANALYSIS_RECEIPT.json", receipt)
    print(receipt, flush=True)
    view = summary[(summary.layer.isin(["ordinary_manual", "ordinary_semi"])) & (summary.n.isin([3, 5, 7]))
                   & (summary.n_fast == summary.n) & (summary.contrast == "versus_slow")]
    print(view[["layer", "origin", "domain", "n", "images", "buildings", "quality_difference", "source_time_ratio",
                "joint_save20_lose_at_most2", "candidate_failed", "corner_recall_difference"]].round(4).to_string(index=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--reuse-pairs", action="store_true", help="Reuse the frozen paired comparison file when only rebuilding summaries")
    args = parser.parse_args()
    analyze(args.repo, args.out, args.reuse_pairs)
