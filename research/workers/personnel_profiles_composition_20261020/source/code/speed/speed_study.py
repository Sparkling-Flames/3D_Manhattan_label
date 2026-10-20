"""Q-matched, source-separated worker-speed mixtures using frozen HOHONET fusion.

Preparation reads only history outside each target building and target membership.
All outcomes and target durations are read later, in evaluate/analyze. This is a
finite historical-pool experiment; durations are source-task active/report seconds.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

SEED = 2026102081


def read(path):
    with (gzip.open(path, "rt", encoding="utf-8") if str(path).endswith(".gz")
          else open(path, encoding="utf-8-sig")) as stream:
        return json.load(stream)


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(clean(value), ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    path.write_bytes(gzip.compress(raw, compresslevel=5, mtime=0) if str(path).endswith(".gz") else raw)


def rng_for(*parts):
    digest = hashlib.sha256(json.dumps(clean([SEED, *parts]), sort_keys=True).encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "big"))


def team_key(pool_id, workers):
    # Same key construction as the already-used compact native runner.
    digest = hashlib.sha256(json.dumps(sorted(workers), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return pool_id + "__" + digest[:20]


def modules(repo):
    repo = Path(repo).resolve()
    sys.path.insert(0, str(repo))
    from tools.thesis_main.analysis.fusion_change_mechanisms_20261020 import engine
    fe = engine()
    sys.path.insert(0, str(repo / "research/workers/personnel_interchangeability_20261020/analysis/composition"))
    import fusion_runner as fr
    import geometry_diagnostics as gd
    fr.FE = fe
    return fe, fr, gd


def source_pools(repo):
    return read(Path(repo) / "research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz")["images"]


def matched_pairs(frame):
    """Maximize independent fast/slow pairs, then minimize historical Q gap.

    Both sides come from the median split of historical task-adjusted log time.
    Accepted edges require |Q_peer difference| <= 3 and >= 1.5x time contrast.
    The small tie preference for larger time contrast is fixed before outcomes.
    """
    frame = frame.sort_values("worker_id")
    if len(frame) < 2:
        return []
    median = frame.log_time_peer.median()
    fast = frame[frame.log_time_peer <= median]
    slow = frame[frame.log_time_peer > median]
    if fast.empty or slow.empty:
        return []
    dq = fast.Q_peer.to_numpy()[:, None] - slow.Q_peer.to_numpy()[None, :]
    dt = slow.log_time_peer.to_numpy()[None, :] - fast.log_time_peer.to_numpy()[:, None]
    ok = (abs(dq) <= 3) & (dt >= np.log(1.5))
    cost = np.where(ok, abs(dq) - 0.05 * dt, 1e6)
    ii, jj = linear_sum_assignment(cost)
    pairs = []
    for i, j in zip(ii, jj):
        if not ok[i, j]:
            continue
        a, b = fast.iloc[i], slow.iloc[j]
        pairs.append(dict(fast=a.worker_id, slow=b.worker_id,
                          fast_Q_peer=a.Q_peer, slow_Q_peer=b.Q_peer,
                          fast_log_time_peer=a.log_time_peer, slow_log_time_peer=b.log_time_peer,
                          historical_Q_difference=float(dq[i, j]), historical_time_ratio=float(np.exp(-dt[i, j])),
                          fast_quality_n=int(a.n_quality_images), slow_quality_n=int(b.n_quality_images),
                          fast_time_n=int(a.n_time_images), slow_time_n=int(b.n_time_images)))
    assert len({p[k] for p in pairs for k in ("fast", "slow")}) == 2 * len(pairs)
    return pairs


def prepare(repo, features, out):
    out = Path(out)
    frame = pd.read_csv(features)
    pools = source_pools(repo)
    old_split = read(Path(repo) / "research/workers/personnel_composition_study_20261019/analysis/composition/SPLIT.json")
    building_sets = {b: phase for phase in ("history", "discovery", "validation") for b in old_split[phase + "_buildings"]}
    requests, panels, matches, capacity = [], [], [], []
    for pool in pools:
        meta = pool["meta"]
        eligible_workers = {r["worker_id"] for r in pool["records"]}
        for origin in ("new", "v1"):
            f = frame[(frame.target_building == meta["building"]) & (frame.condition == meta["condition"])
                      & (frame.origin == origin) & (frame.panel == "ordinary")
                      & frame.worker_id.isin(eligible_workers)
                      & frame.Q_supported_8images_3buildings & frame.T_supported_8images_3buildings].copy()
            for domain in ("allQ", "above_peer_Q"):
                candidate = f if domain == "allQ" else f[f.Q_peer >= 0]
                pairs = matched_pairs(candidate)
                context = dict(pool_id=pool["pool_id"], image=meta["image"], image_id=meta["image_id"],
                               building=meta["building"], condition=meta["condition"], layer=meta["layer"],
                               difficulty=meta["difficulty"], difficulty_aligned=meta["difficulty_aligned"],
                               origin=origin, domain=domain, historical_building_subset=building_sets[meta["building"]],
                               time_source_kind="|".join(sorted(set(candidate.time_source_kind.dropna()))))
                capacity.append(dict(context, eligible_workers=len(candidate), matched_pairs=len(pairs)))
                matches.extend(dict(context, pair_index=i, **pair) for i, pair in enumerate(pairs))
                # Capacity was inspected before outcomes: full 3..9 range in the
                # better-supported new all-Q pool; sparse sizes in other panels.
                sizes = range(3, 10) if origin == "new" and domain == "allQ" else (3, 5, 7)
                by_worker = candidate.set_index("worker_id")
                for n in sizes:
                    if n > len(pairs):
                        continue
                    for replicate in range(4):
                        random = rng_for(pool["pool_id"], origin, domain, n, replicate)
                        selected = [pairs[i] for i in random.choice(len(pairs), n, replace=False)]
                        panel_id = f'{pool["pool_id"]}__{origin}__{domain}__n{n}__r{replicate}'
                        panel = dict(context, panel_id=panel_id, n=n, replicate=replicate,
                                     member_stage="exploration" if replicate < 2 else "member_check",
                                     pairs=selected, fast_workers=[p["fast"] for p in selected],
                                     slow_workers=[p["slow"] for p in selected])
                        panels.append(panel)
                        arms = []
                        for nfast in range(n + 1):
                            workers = [p["fast"] if i < nfast else p["slow"] for i, p in enumerate(selected)]
                            arms.append((f"fast{nfast}", nfast, workers))
                        union = [p[k] for p in selected for k in ("fast", "slow")]
                        workers = random.choice(union, n, replace=False).tolist()
                        arms.append(("random", sum(w in panel["fast_workers"] for w in workers), workers))
                        for arm, nfast, workers in arms:
                            assert len(set(workers)) == n and set(workers) <= eligible_workers
                            q = by_worker.loc[workers]
                            requests.append(dict(context, panel_id=panel_id, n=n, replicate=replicate,
                                                 member_stage=panel["member_stage"], arm=arm, n_fast=nfast,
                                                 n_slow=n-nfast, worker_ids=sorted(workers),
                                                 team_key=team_key(pool["pool_id"], workers),
                                                 historical_Q_mean=float(q.Q_peer.mean()),
                                                 historical_log_time_mean=float(q.log_time_peer.mean())))
    write(out / "requests.json.gz", requests)
    write(out / "panels.json.gz", panels)
    pd.DataFrame(matches).to_csv(out / "matched_workers.csv", index=False)
    pd.DataFrame(capacity).to_csv(out / "capacity.csv", index=False)
    expected = read(Path(repo) / "research/workers/personnel_interchangeability_20261020/interchangeability_20261020/core_replay/EXPECTED_FINAL_FIELDS.json.gz")
    old_keys = {row["team_key"] for row in expected}
    new_keys = {row["team_key"] for row in requests}
    registration = dict(seed=SEED, status="prepared_before_new_outcomes", requests=len(requests),
                        exact_teams=len(new_keys), panels=len(panels), pools=len({r["pool_id"] for r in requests}),
                        old_core_result_overlap=len(new_keys & old_keys),
                        old_result_use="Existing F01 efficiency results are contextual reuse; historical final-field-only archive lacks geometry for these new Q-matched comparisons. Overlap is recorded; reused exact saved geometries are recorded during execution.",
                        selection="Each condition/source separately; ordinary history excludes the target building. Both Q and T require >=8 images and >=3 other buildings. Doorway/special outcomes are separate application panels, not refitted from target outcomes.",
                        q_matching="one-to-one source-matched pairs; absolute historical peer Q gap <=3 B8L2 points; speed >=1.5x; no target quality or duration used for selection",
                        random_baseline="same n sampled from this panel's 2n eligible matched workers",
                        stages="replicates 0/1 exploration, 2/3 new-member check; repeated exact teams identified, not called new observations",
                        time="sum source task reported/active seconds; max only a simultaneous-start active-time scenario; no queue/wait inference; target-matched seconds separate",
                        inference="finite-pool retrospective comparison, target-building-excluded selection, within-image then within-building averaging; old building split labels are reporting strata, not a claim all six old validation buildings are excluded from LOBO history",
                        fusion="unchanged current MV50 ceil(n/2), gap7.5, median location, existing ordering and reference; B8L2 primary/D10 sensitivity")
    write(out / "REGISTRATION.json", registration)
    print(json.dumps(registration, ensure_ascii=False, indent=2), flush=True)


def run_pool(repo, pool, requests, out):
    fe, fr, gd = modules(repo)
    target = Path(out) / "final_teams" / (pool["pool_id"] + ".json.gz")
    rows = {r["team_key"]: r for r in read(target)} if target.exists() else {}
    wanted = {r["team_key"]: r["worker_ids"] for r in requests}
    initial = len(rows)
    by = {r["worker_id"]: r for r in pool["records"]}
    cache = {}
    start = time.monotonic()
    with fe.cached_matching(), fe.scoring_engine(fe.ENGINE / "measurement_engine.zip", fe.ENGINE / "working_models.py") as (scorer, models):
        for key, workers in wanted.items():
            if key in rows:
                continue
            row = fr.evaluate_one(pool, workers, scorer, models, score_cache=cache)
            selected = [by[w] for w in workers]
            ts = [r["source_time_seconds"] for r in selected]
            row["source_parallel_active_seconds"] = max(ts) if all(t is not None for t in ts) else None
            row["time_source_kinds"] = sorted({r["time_source_kind"] for r in selected})
            geometry = row.get("geometry") or {}
            diag = gd.diagnose(geometry.get("footprint"), pool["reference"]["floor_xz_h"])
            keep = ("diag_status", "diag_wall_coverage_05", "diag_corner_recall_05",
                    "diag_reference_corner_n", "diag_candidate_corner_n", "diag_matched_corner_n")
            row.update({k: diag.get(k) for k in keep})
            nc, nm = diag.get("diag_candidate_corner_n"), diag.get("diag_matched_corner_n")
            row["diag_unmatched_candidate_corners"] = nc - nm if nc is not None and nm is not None else None
            row["computed_in_this_study"] = True
            rows[key] = row
    write(target, list(rows.values()))
    return dict(pool_id=pool["pool_id"], requested=len(requests), exact_teams=len(wanted),
                newly_evaluated=len(rows)-initial, previously_reused=initial,
                seconds=round(time.monotonic()-start, 3), failures=sum(rows[k].get("B8L2") is None for k in wanted))


def run(repo, out, jobs, only_layer=None):
    pools = {p["pool_id"]: p for p in source_pools(repo)}
    requests = read(Path(out) / "requests.json.gz")
    grouped = defaultdict(list)
    for row in requests:
        if only_layer is None or row["layer"] == only_layer:
            grouped[row["pool_id"]].append(row)
    start = time.monotonic()
    receipts = []
    with ProcessPoolExecutor(max_workers=jobs) as executor:
        futures = {executor.submit(run_pool, str(repo), pools[pid], rows, str(out)): pid for pid, rows in grouped.items()}
        for future in as_completed(futures):
            receipt = future.result()
            receipts.append(receipt)
            print(json.dumps(dict(receipt, done=len(receipts), pools=len(grouped), elapsed=round(time.monotonic()-start, 1))), flush=True)
    write(Path(out) / ("RUN_" + (only_layer or "all") + ".json"), dict(receipts=receipts,
          newly_evaluated=sum(r["newly_evaluated"] for r in receipts), seconds=time.monotonic()-start))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--features", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--layer")
    args = parser.parse_args()
    if args.prepare:
        prepare(args.repo, args.features, args.out)
    if args.run:
        run(args.repo, args.out, args.jobs, args.layer)


if __name__ == "__main__":
    main()
