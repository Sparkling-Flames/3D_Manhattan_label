"""Bounded stage-2 real-prefix experiment registered before its outcomes."""
from collections import Counter
import gzip
import hashlib
from itertools import combinations
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from analyze_fusion_profiles import (
    HERE, OUT as MAIN_OUT, REPO, W, F, POP, OLDW, PRIMARY, init, enrich, footprint, fuse,
    WORKING_GAP, avg,
)
from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine
from tools.thesis_main.analysis.quality_b8l2_d10_20261017 import model_parameters
from tools.thesis_main.analysis.wall_consensus_population_20261014 import summarize_state, transition, compact

REG = json.loads((HERE / "STAGE2_REGISTRATION.json").read_text())
OUT = MAIN_OUT / "stage2"
STRATEGIES = REG["strategies"]
COMPONENTS = ["iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter"]


def csv(name, rows):
    d = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    d.to_csv(OUT / name, index=False, encoding="utf-8-sig")
    return d


def save(name, obj):
    def clean(x):
        if isinstance(x, dict): return {str(k): clean(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)): return [clean(v) for v in x]
        if isinstance(x, np.generic): return clean(x.item())
        if isinstance(x, float) and not np.isfinite(x): return None
        return x
    (OUT / name).write_text(json.dumps(clean(obj), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def sample_orders(images, alias, lookup):
    rows = []
    rng = np.random.default_rng(REG["seed"])
    for image in PRIMARY:
        pool = sorted(alias[image])
        ishigh = {p: lookup[(image, alias[image][p])]["B8L2_Q2"] == "high" for p in pool}
        n_high = sum(ishigh.values()); n_low = len(pool) - n_high
        assert min(n_high, n_low) >= 8
        for repeat in range(REG["paths_per_image_strategy"]):
            order = rng.permutation(pool).tolist()
            high = [p for p in order if ishigh[p]]
            low = [p for p in order if not ishigh[p]]
            mixed = rng.permutation(high[:4] + low[:4]).tolist()
            strategies = dict(zip(STRATEGIES, [high[:8], mixed, low[:8], order[:8]]))
            for strategy, selected in strategies.items():
                assert len(selected) == len(set(selected)) == 8
                high_n = sum(ishigh[p] for p in selected)
                if strategy == "8_high": assert high_n == 8
                if strategy == "8_low": assert high_n == 0
                if strategy == "4_high_4_low": assert high_n == 4
                workers = [alias[image][p] for p in selected]
                row = dict(image=image, building_id=images[image]["building"], strategy=strategy, path=repeat,
                           public_worker_order="|".join(selected), worker_order="|".join(workers),
                           object_order="|".join(lookup[(image, w)]["object_id"] for w in workers),
                           source_pool_size=24, high_pool_size=n_high, low_pool_size=n_low,
                           terminal_high_n=high_n, terminal_low_n=8-high_n, H=8,
                           mean_Q_effect=np.mean([lookup[(image, w)]["B8L2_effect"] for w in workers]),
                           ordering_source="seed_20261017_frozen_before_geometry")
                rows.append(row)
    return csv("PERMUTATIONS.csv", rows)


def measure(state, refgeom, engine, models):
    summary = summarize_state(state)
    result = dict(B8L2=np.nan, D10=np.nan, IoU3D100=np.nan, **{k: np.nan for k in COMPONENTS})
    if state["n"] == 2:
        result["score_status"] = "two_person_deferred"
    elif summary["below_four"]:
        result["score_status"] = "below_four"
    elif not summary["connection_available"]:
        result["score_status"] = "no_connection"
    elif not summary["complete_evaluable"]:
        result["score_status"] = "invalid_full_geometry"
    else:
        data = engine.measure(engine.geometry(state["candidate"]["points"]), refgeom)
        if data["status"] != "complete":
            result["score_status"] = "invalid_full_measurement"
            result["measurement_reasons"] = json.dumps(data.get("reasons"), ensure_ascii=False)
        else:
            result.update(data["metrics"])
            values = [data["metrics"][k] for k in COMPONENTS]
            for axis, params in zip(["B8L2", "D10"], model_parameters(models)):
                result[axis] = float(models.score(*values, params=params))
            result["IoU3D100"] = 100*data["metrics"]["iou_3d_corner_mean"]
            result["score_status"] = "complete_conditional"
    return result


def aggregate(frame, pairs, steps):
    metrics = ["B8L2", "D10", "IoU3D100", "raw_R", "complete_evaluable", "source_time_total_seconds", "target_matched_time_total_seconds", "B8L2_high_n", "B8L2_mean_effect"]
    summaries = []
    for (image, strategy, k), g in frame.groupby(["image", "strategy", "k"]):
        p = pairs[(pairs.image == image) & (pairs.strategy == strategy) & (pairs.k == k)]
        s = steps[(steps.image == image) & (steps.strategy == strategy) & (steps.k_to == k)]
        r = dict(image=image, building_id=g.building_id.iloc[0], strategy=strategy, k=int(k), attempts=len(g),
                 unique_subsets=g.subset.nunique(), complete_n=int(g.complete_evaluable.sum()), quality_n=int(g.B8L2.notna().sum()),
                 source_time_n=int(g.source_time_total_seconds.notna().sum()), target_time_n=int(g.target_matched_time_total_seconds.notna().sum()),
                 k2_policy_deferred=int(g.k.eq(2).sum()), below_four_n=int(g.below_four.sum()),
                 no_connection_n=int((~g.connection_available).sum()), high_pool_size=int(g.high_pool_size.iloc[0]), low_pool_size=int(g.low_pool_size.iloc[0]),
                 class_pool_exhausted_n=int(g.class_pool_exhausted.sum()),
                 V_pairs=len(p), V_valid_pairs=int(p.both_complete_floor.sum()), V_floor=p.floor_difference.mean(),
                 shared_members_mean=p.shared_members.mean(), same_subset_pairs=int(p.same_subset.sum()),
                 step_attempts=len(s), step_floor_valid=int(s.floor_change.notna().sum()),
                 adjacent_floor_change=s.floor_change.mean(), adjacent_B8L2_change=s.B8L2_change.mean(),
                 changed_identity_steps=int(s.changed_coidentity_pairs.gt(0).sum()),
                 unchanged_identity_vote_losses=int(s.unchanged_identity_vote_losses.sum()),
                 connection_losses=int(s.connection_lost.sum()))
        for metric in metrics: r[metric + "_mean"] = g[metric].mean()
        summaries.append(r)
    byimage = csv("strategy_by_image_k.csv", summaries)
    contrasts = [("8_high", "random_8_from_24"), ("4_high_4_low", "random_8_from_24"),
                 ("8_low", "random_8_from_24"), ("8_high", "8_low"), ("8_high", "4_high_4_low")]
    outcomes = [m+"_mean" for m in metrics] + ["V_floor", "shared_members_mean", "adjacent_floor_change", "changed_identity_steps", "connection_losses"]
    differences = []
    for (image, k), g in byimage.groupby(["image", "k"]):
        g = g.set_index("strategy")
        for a, b in contrasts:
            r = dict(image=image, building_id=g.building_id.iloc[0], k=k, contrast=a+"_minus_"+b,
                     strategy_a=a, strategy_b=b, attempts_a=int(g.loc[a, "attempts"]), attempts_b=int(g.loc[b, "attempts"]),
                     quality_n_a=int(g.loc[a, "quality_n"]), quality_n_b=int(g.loc[b, "quality_n"]),
                     source_time_n_a=int(g.loc[a, "source_time_n"]), source_time_n_b=int(g.loc[b, "source_time_n"]))
            for out in outcomes: r[out+"_difference"] = g.loc[a, out] - g.loc[b, out]
            differences.append(r)
    im = csv("paired_strategy_differences_by_image.csv", differences)
    cols = [x for x in im if x.endswith("_difference")]
    building = im.groupby(["k", "contrast", "building_id"], as_index=False)[cols].mean()
    csv("paired_strategy_differences_by_building.csv", building)
    results = []
    for (k, contrast), g in building.groupby(["k", "contrast"]):
        image_rows = im[(im.k == k) & (im.contrast == contrast)]
        for outcome in cols:
            vals = g[outcome].dropna(); valid_im = image_rows.dropna(subset=[outcome])
            results.append(dict(k=k, contrast=contrast, outcome=outcome, paired_images=len(valid_im), buildings=len(vals),
                                mean=vals.mean(), median=vals.median(), minimum=vals.min(), maximum=vals.max(),
                                positive_buildings=int(vals.gt(0).sum()),
                                leave_one_building_min=min([vals.drop(ix).mean() for ix in vals.index], default=np.nan),
                                leave_one_building_max=max([vals.drop(ix).mean() for ix in vals.index], default=np.nan)))
    csv("paired_strategy_summary.csv", results)
    both = []
    for (image, strategy), g in frame.groupby(["image", "strategy"]):
        for lo, hi in [(3, 4), (4, 8), (3, 8)]:
            a = g[g.k == lo].set_index("path"); b = g[g.k == hi].set_index("path")
            r = dict(image=image, building_id=g.building_id.iloc[0], strategy=strategy, k_from=lo, k_to=hi, paths=12,
                     complete_from=int(a.complete_evaluable.sum()), complete_to=int(b.complete_evaluable.sum()))
            for metric in ["B8L2", "D10", "raw_R"]:
                p = a[[metric]].join(b[[metric]], lsuffix="_a", rsuffix="_b").dropna()
                r[metric+"_paired_n"] = len(p); r[metric+"_paired_change"] = (p[metric+"_b"] - p[metric+"_a"]).mean()
            both.append(r)
    csv("matched_true_path_intervals.csv", both)
    # Shared member count is kept explicitly; pure subpools and the full pool have different finite-pool overlap.
    csv("V_by_overlap.csv", pairs.groupby(["image", "building_id", "strategy", "k", "shared_members"], as_index=False).agg(
        attempted_pairs=("path_a", "size"), valid_pairs=("both_complete_floor", "sum"), V_floor=("floor_difference", "mean"),
        abs_B8L2_difference=("abs_B8L2_difference", "mean")))
    return byimage


def exact_raw_disagreement(images, alias, lookup, rawdist):
    """Exact finite-pool E[R]; no extra fusion or Monte Carlo is required."""
    rows = []
    for image in PRIMARY:
        pool = sorted(alias[image])
        high = [p for p in pool if lookup[(image, alias[image][p])]["B8L2_Q2"] == "high"]
        low = [p for p in pool if p not in high]
        def R(pairs): return avg(rawdist[image][tuple(sorted((a, b)))] for a, b in pairs)
        rh = R(combinations(high, 2)); rl = R(combinations(low, 2))
        cross = R((a, b) for a in high for b in low); full = R(combinations(pool, 2))
        mixed = (6*rh + 6*rl + 16*cross) / 28
        for strategy, value in [("8_high", rh), ("8_low", rl), ("4_high_4_low", mixed), ("random_8_from_24", full)]:
            rows.append(dict(image=image, building_id=images[image]["building"], strategy=strategy,
                             high_pool_size=len(high), low_pool_size=len(low), exact_expected_R=value,
                             exact_R_minus_full_random=value-full, valid_for_k="2..8",
                             unit="symmetric_difference / fixed_full_24_pool_union"))
    csv("exact_expected_raw_R.csv", rows)


def run():
    start = time.monotonic(); OUT.mkdir(exist_ok=True); (OUT / "states").mkdir(exist_ok=True)
    (oldtraj, allteams, ledger, folds, images, alias, members, lookup, rawdist, geometry, payloads) = init()
    schedules = sample_orders(images, alias, lookup)  # Written before any new outputs are computed.
    assert len(schedules) == 7*4*12
    raw_manifest = (OUT / "PERMUTATIONS.csv").read_bytes()
    refs = {im["image"]: im["reference"] for im in json.loads((REPO / "research/fusion/wall_consensus_b8l2_20261016/input_snapshot.json").read_text(encoding="utf-8-sig"))["images"]}
    oldscore = pd.read_csv(F / "subset_scores.csv")
    old_extra = pd.read_csv(W / "team_scores.csv")
    scores = {image: oldscore[oldscore.image.eq(image)].set_index("subset").to_dict("index") for image in PRIMARY}
    for image in PRIMARY:
        assert oldtraj[oldtraj.image.eq(image)].reference_id.eq(refs[image]["target_id"]).all()
        extra_path = OLDW / "new_states" / (image + ".json.gz")
        if extra_path.exists():
            extra = json.load(gzip.open(extra_path, "rt", encoding="utf-8"))
            for s in extra["states"]: geometry[image].setdefault("|".join(sorted(s["workers"])), s["automatic"])
        for r in old_extra[old_extra.image.eq(image)].to_dict("records"):
            if r["subset"] in scores[image]:
                previous = scores[image][r["subset"]]
                for ax in ["B8L2", "D10"]:
                    assert (pd.isna(previous[ax]) and pd.isna(r[ax])) or abs(previous[ax]-r[ax]) < 1e-8
            else: scores[image][r["subset"]] = r
    rows, pairrows, steprows, score_checks = [], [], [], []
    new_fusions = new_measurements = reused_geometry = reused_scores = 0
    with scoring_engine() as (engine, models):
        for image in PRIMARY:
            record_by = {r["worker"]: r for r in images[image]["records"]}
            refgeom = engine.geometry(refs[image]["points_1024x512"])
            # Reproduce an existing scored full state before scoring any new state on this image.
            old = oldtraj[(oldtraj.image == image) & (oldtraj.path == 0) & (oldtraj.k == 3)].iloc[0]
            verified = measure(geometry[image][old.subset], refgeom, engine, models)
            for ax in ["B8L2", "D10"]:
                assert (pd.isna(old[ax]) and pd.isna(verified[ax])) or abs(old[ax]-verified[ax]) < 1e-8
            score_checks.append(dict(image=image, published_B8L2=old.B8L2, recomputed_B8L2=verified["B8L2"], published_D10=old.D10, recomputed_D10=verified["D10"]))
            used = {}; image_rows = []; measurement_cache = {}
            for schedule in schedules[schedules.image.eq(image)].to_dict("records"):
                order = schedule["public_worker_order"].split("|"); previous = None; previous_row = None
                for k in range(1, 9):
                    ps = sorted(order[:k]); key = "|".join(ps)
                    if key in geometry[image]: reused_geometry += 1
                    else:
                        geometry[image][key] = compact(fuse([record_by[p] for p in ps], gap=WORKING_GAP)["automatic"])
                        new_fusions += 1
                    state = geometry[image][key]; used[key] = state
                    assert {m["worker"] for g in state["identity_groups"] for m in g["members"]} == set(ps)
                    summary = summarize_state(state)
                    if key in scores[image]:
                        score = scores[image][key]; reused_scores += 1
                    else:
                        mkey = json.dumps([state["n"] == 2, state["candidate"], summary["below_four"]], sort_keys=True)
                        if mkey not in measurement_cache:
                            measurement_cache[mkey] = measure(state, refgeom, engine, models); new_measurements += 1
                        score = measurement_cache[mkey]; scores[image][key] = score
                    workers = [alias[image][p] for p in ps]
                    r = dict(image=image, building_id=images[image]["building"], strategy=schedule["strategy"], path=schedule["path"],
                             subset=key, worker_ids="|".join(sorted(workers)),
                             member_object_ids="|".join(sorted(lookup[(image, w)]["object_id"] for w in workers)),
                             reference_id=refs[image]["target_id"], reference_version=refs[image]["reference_version"],
                             high_pool_size=schedule["high_pool_size"], low_pool_size=schedule["low_pool_size"], source_pool_size=24,
                             class_pool_exhausted=(schedule["strategy"] == "8_high" and k == schedule["high_pool_size"]) or
                                                  (schedule["strategy"] == "8_low" and k == schedule["low_pool_size"]),
                             declared_selected_team_complete=k == 8, data_release="v1", fusion_version="MV50_gap7.5_all_members_median_frozen", **summary)
                    for col in ["B8L2", "D10", "IoU3D100", "score_status", *COMPONENTS]: r[col] = score.get(col, np.nan)
                    assert pd.isna(r["B8L2"]) == pd.isna(r["D10"])
                    assert pd.notna(r["B8L2"]) == r["complete_evaluable"]
                    image_rows.append(r)
                    if previous is not None:
                        pa, pb = footprint(previous["candidate"]["footprint"]), footprint(state["candidate"]["footprint"])
                        both = previous_row["complete_floor_evaluable"] and summary["complete_floor_evaluable"]
                        s = dict(image=image, building_id=r["building_id"], strategy=r["strategy"], path=r["path"],
                                 k_from=k-1, k_to=k, added_worker_id=alias[image][order[k-1]],
                                 previous_subset=previous_row["subset"], current_subset=key,
                                 complete_from=previous_row["complete_evaluable"], complete_to=r["complete_evaluable"],
                                 B8L2_change=r["B8L2"]-previous_row["B8L2"], D10_change=r["D10"]-previous_row["D10"],
                                 floor_change=1-pa.intersection(pb).area/pa.union(pb).area if both else np.nan,
                                 connection_lost=previous_row["connection_available"] and not r["connection_available"],
                                 **transition(previous, state))
                        steprows.append(s)
                    previous, previous_row = state, r
            frame = pd.DataFrame(image_rows)
            frame = enrich(frame, alias, lookup, rawdist, "worker_ids")
            rows.extend(frame.to_dict("records"))
            for (strategy, k), g in frame.groupby(["strategy", "k"]):
                for a, b in combinations(g.itertuples(), 2):
                    sa, sb = used[a.subset], used[b.subset]
                    pa, pb = footprint(sa["candidate"]["footprint"]), footprint(sb["candidate"]["footprint"])
                    both = a.complete_floor_evaluable and b.complete_floor_evaluable
                    d = 1-pa.intersection(pb).area/pa.union(pb).area if both else np.nan
                    same = a.subset == b.subset
                    if same and both: assert abs(d) < 1e-12
                    pairrows.append(dict(image=image, building_id=a.building_id, strategy=strategy, k=k,
                                         path_a=a.path, path_b=b.path, subset_a=a.subset, subset_b=b.subset,
                                         shared_members=len(set(a.subset.split("|")) & set(b.subset.split("|"))), same_subset=same,
                                         both_complete_floor=both, floor_difference=d,
                                         abs_B8L2_difference=abs(a.B8L2-b.B8L2), abs_D10_difference=abs(a.D10-b.D10)))
            with gzip.open(OUT / "states" / (image + ".json.gz"), "wt", encoding="utf-8") as f:
                json.dump(dict(image=image, reference=refs[image], schedules=schedules[schedules.image.eq(image)].to_dict("records"),
                               states=[dict(workers=key.split("|"), automatic=state) for key, state in used.items()]), f, ensure_ascii=False)
            print(image, "states", len(frame), "unique", len(used), "complete", int(frame.B8L2.notna().sum()),
                  "elapsed_s", round(time.monotonic()-start, 2), flush=True)
    frame = csv("path_states.csv", rows); pairs = csv("same_k_pairs.csv", pairrows); steps = csv("prefix_transitions.csv", steprows)
    csv("score_parity_checks.csv", score_checks)
    summaries = aggregate(frame, pairs, steps)
    exact_raw_disagreement(images, alias, lookup, rawdist)
    assert len(frame) == REG["planned_path_attempts"] == 2688
    assert len(steps) == 2352 and len(pairs) == 14784
    assert (OUT / "PERMUTATIONS.csv").read_bytes() == raw_manifest
    assert not frame.class_pool_exhausted.any()
    receipt = dict(data_release="v1", stage="stage2_developmental_extension", repository_commit=REG["repository_commit"],
                   seed=REG["seed"], images=7, buildings=6, strategies=4, paths_per_image_strategy=12, path_attempts=len(frame),
                   unique_used_subsets=frame.drop_duplicates(["image", "subset"]).shape[0], new_fusions=new_fusions,
                   reused_state_lookups=reused_geometry, new_unique_score_evaluations=new_measurements, reused_score_lookups=reused_scores,
                   score_evaluation_definition="Calls to scoring wrapper, including explicit missing-status returns; not all are full geometry measurements.",
                   complete_quality_states=int(frame.B8L2.notna().sum()), k2_deferred=int(frame.k.eq(2).sum()),
                   other_incomplete_states=int((frame.B8L2.isna() & frame.k.ne(2)).sum()),
                   explicit_prefix_transitions=len(steps), same_k_pairs=len(pairs), score_parity_images=len(score_checks),
                   permutation_sha256=hashlib.sha256(raw_manifest).hexdigest(), current_members_only=True,
                   external_building_labels=True, target_score_used_for_selection=False, reference_optimized=False,
                   full_source_class_boundary_reached=False, attempts_with_all_source_time=int(frame.source_time_total_seconds.notna().sum()),
                   attempts_with_all_target_time=int(frame.target_matched_time_total_seconds.notna().sum()),
                   total_elapsed_seconds=time.monotonic()-start)
    save("RUN_RECEIPT.json", receipt)
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == "__main__": run()
