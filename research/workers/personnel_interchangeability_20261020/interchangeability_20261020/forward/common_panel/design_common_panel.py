#!/usr/bin/env python3
"""Freeze a label-independent, common-personnel, actual m=2 replacement panel.

Selection uses only the previously frozen history support set plus target pool
metadata and member IDs. No target score, geometry, time or candidate labels
participate in choosing a core, block, team or pair.
"""
from __future__ import annotations
import argparse
import collections
import datetime
import gzip
import hashlib
import itertools
import json
import math
import random
from pathlib import Path

SEED = 2026102013
NODES = [5, 9, 13, 17]
CORES = 2
MAX_BLOCKS = 48
RANDOM_REPLICATES = 20


def read(path):
    with (gzip.open(path, "rt") if str(path).endswith(".gz") else open(path)) as f:
        return json.load(f)


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    path.write_bytes(gzip.compress(raw, compresslevel=6, mtime=0) if path.suffix == ".gz" else raw)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def team_key(pid, workers):
    return pid + "__" + digest(sorted(workers))[:20]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--split", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--labels", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--phase", choices=["discovery", "assessment"], default="discovery")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--label-seed", type=int, default=SEED,
                    help="Keep the original 40 fixed random-label partitions when resampling assessment teams")
    a = ap.parse_args()
    snapshot, split, manifest = read(a.snapshot), read(a.split), read(a.manifest)
    mids = sorted(mid for mid, method in manifest["methods"].items()
                  if (method.get("ablation") or {}).get("family") in ("newCommon_K2", "newCommon_K3"))
    assert len(mids) == 16
    population = sorted(manifest["methods"][mids[0]]["known_workers"])
    assert len(population) == 26
    for mid in mids:
        method = manifest["methods"][mid]
        assert sorted(method["known_workers"]) == population
        assert sorted(method["ablation"]["common_workers"]) == population
        assert method["pool_filter"] == "ordinary_manual"
    discovery = set(split["discovery_buildings"] if a.phase == "discovery" else split["validation_buildings"])
    requests, anchors, skips = {}, [], []
    candidate_pools = []
    for pool in sorted(snapshot["images"], key=lambda p: p["pool_id"]):
        meta = pool["meta"]
        if meta["building"] not in discovery or meta["layer"] != "ordinary_manual":
            continue
        pid = pool["pool_id"]
        by = {r["worker_id"]: r for r in pool["records"]}
        ws = sorted(set(population) & by.keys())
        assert all(by[w]["origin"] == "new" for w in ws)
        candidate_pools.append(dict(pool_id=pid, building=meta["building"], image=meta["image"],
                                    difficulty=meta["difficulty"], eligible_workers=ws))
        for n in NODES:
            if len(ws) < n + 2:
                skips.append(dict(pool_id=pid, building=meta["building"], n=n,
                                  pool_common_people=len(ws), reason="fewer_than_four_remaining_workers_for_disjoint_m2_blocks"))
                continue
            rng = random.Random(int(digest([a.seed, "core", pid, n])[:16], 16))
            selected_cores = set()
            while len(selected_cores) < CORES:
                selected_cores.add(tuple(sorted(rng.sample(ws, n - 2))))
            for rep, core in enumerate(sorted(selected_cores)):
                remaining = sorted(set(ws) - set(core))
                all_blocks = list(itertools.combinations(remaining, 2))
                exhaustive = len(all_blocks) <= MAX_BLOCKS
                blocks = all_blocks if exhaustive else sorted(all_blocks, key=lambda b: digest([a.seed, "block", pid, n, list(core), b]))[:MAX_BLOCKS]
                blocks = sorted(blocks)
                aid = "CP20_" + digest([a.seed, pid, n, list(core)])[:20]
                block_rows = []
                for block in blocks:
                    members = sorted(list(core) + list(block))
                    tk = team_key(pid, members)
                    requests.setdefault(tk, dict(request_id=tk, pool_id=pid, k=n, worker_ids=members))
                    block_rows.append(dict(block_id=digest([pid, block])[:16], worker_ids=list(block), team_key=tk))
                pairs = [(i, j) for i, j in itertools.combinations(range(len(blocks)), 2)
                         if set(blocks[i]).isdisjoint(blocks[j])]
                assert pairs and len(core) == n - 2
                anchors.append(dict(anchor_id=aid, pool_id=pid, building=meta["building"], image=meta["image"],
                                    difficulty=meta["difficulty"], layer=meta["layer"], n=n, m=2, replicate=rep,
                                    core_workers=list(core), available_workers=ws, remaining_workers=remaining,
                                    possible_blocks=len(all_blocks), sampled_blocks=len(blocks), exhaustive_blocks=exhaustive,
                                    possible_disjoint_unordered_pairs=3 * math.comb(len(remaining), 4),
                                    sampled_disjoint_unordered_pairs=len(pairs), blocks=block_rows,
                                    disjoint_pair_indices=pairs))
    assert len(requests) <= 30000
    assert len({x["anchor_id"] for x in anchors}) == len(anchors)
    for r in requests.values():
        assert set(r["worker_ids"]) <= set(population)
        assert len(r["worker_ids"]) == len(set(r["worker_ids"])) == r["k"]
        assert r["request_id"] == team_key(r["pool_id"], r["worker_ids"])

    random_methods, random_rows = {}, []
    for k in (2, 3):
        base = manifest["methods"][f"F20_newCommon_Full_balanced_K{k}"]
        sizes = base["class_sizes"]
        multiset = [c for c in sorted(sizes) for _ in range(sizes[c])]
        assert len(multiset) == len(population)
        for rep in range(RANDOM_REPLICATES):
            mid = f"CP20_random_size_K{k}_s{rep + 1:02d}"
            key = [a.label_seed, "random_size_labels", k, rep]
            labels = multiset.copy()
            random.Random(int(digest(key)[:16], 16)).shuffle(labels)
            members = {c: [w for w, label in zip(population, labels) if label == c] for c in sorted(sizes)}
            random_methods[mid] = dict(method_id=mid, domain="all", pool_filter="ordinary_manual", class_sizes=sizes,
                                       random_seed_key=key, class_workers=members, baseline="fixed_size_random_partition_of_the_same_26_new_workers")
            random_rows.extend(dict(worker_id=w, method_id=mid, domain="all", class_id=c, known=True) for w, c in zip(population, labels))

    common = dict(schema="common_26_m2_label_independent_panel_v1", seed=a.seed, phase=a.phase, n_nodes=NODES,
                  m=2, distinct_cores_per_pool_n=CORES, max_blocks_per_core=MAX_BLOCKS,
                  population=population, method_ids=mids, random_method_ids=sorted(random_methods),
                  buildings=sorted(discovery), pool_filter="ordinary_manual",
                  input_sha256={"snapshot": sha(a.snapshot), "split": sha(a.split), "forward_manifest": sha(a.manifest), "forward_labels": sha(a.labels)},
                  selection="Previously frozen history common-26 support set; target metadata/IDs only; 2 distinct seeded cores; all two-worker blocks if <=48, otherwise the 48 lowest deterministic hashes; enumerate every disjoint selected block pair.")
    a.out.mkdir(parents=True, exist_ok=True)
    write(a.out / "common_requests.json.gz", dict(common, requests=[requests[k] for k in sorted(requests)]))
    write(a.out / "common_anchors.json.gz", dict(common, anchors=anchors))
    write(a.out / "capacity_ledger.json.gz", dict(candidate_pools=candidate_pools, skipped_pool_n=skips))
    write(a.out / "random_methods.json", random_methods)
    import csv
    import io
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=["worker_id", "method_id", "domain", "class_id", "known"])
    writer.writeheader()
    writer.writerows(random_rows)
    (a.out / "random_labels.csv.gz").write_bytes(gzip.compress(stream.getvalue().encode(), compresslevel=6, mtime=0))
    comparisons = dict(
        primary="For each base block A, use all disjoint B blocks with identical class count vector and all disjoint C blocks with a different vector under the same method/core/n/m. Keep A only if both sets are nonempty. Compare A-to-B vs A-to-C means within that same A. Failures count as unstable; missing scores remain missing.",
        direction="Also retain outgoing A vector -> incoming C vector separately, against the same within-A vector B support. Quality direction is C-minus-A or C-minus-B average; never pool directed quality gains and losses as a mechanism claim.",
        aggregation="Equal base-A weights within each core, equal available cores within pool/n, equal pool weights within building/n, equal building weights. Also save exact core/n/vector support and separate complete score/geometry denominators.",
        all_method_support="Native eligible A differs by partition. Primary additionally compares all 16 feature methods on their common eligible A intersection, determined by labels and member availability only; random controls use the corresponding full-K2/full-K3 eligible-A intersection for a fair paired difference.",
        quality_control="Report total classification information first. Secondary neighbor support requires absolute history q_beta mean(block)-mean(A) <=3 for both within and cross neighbors. This is A-centered prior-Q restriction, not a claim all three pairwise gaps <=3. Same 26 people and all-new source throughout. No target individual Q used as a selection covariate.",
        main="Inherited actual pair criteria: both complete; |B8L2 difference|<=2; same node count; floor 1-IoU<=0.05; maximum bound cyclic spherical endpoint distance<=3 degrees.",
        strict="Inherited thresholds |B8L2|<=1, floor<=0.02, cyclic angle<=2 degrees, same nodes and both complete.",
        wide="Inherited thresholds |B8L2|<=5, floor<=0.10, cyclic angle<=5 degrees, same nodes and both complete.",
        noQ="Drop only the B8L2-difference test from each inherited joint criterion; retain geometry completeness and same-node test.",
        continuous="Retain floor 1-IoU, cyclic angle (available only for equal node count), absolute/signed B8L2 and D10 differences, node-count differences, prism proxy IoU, reference-node/edge matched-set changes; no change to frozen fusion/reference/scoring.",
        efficiency="Source and target time separately: use the two-worker block totals only if both workers have a finite time. Report directed log ratios and second differences separately from quality and geometry; the common core cancels from block net time.",
        random_control="20 fixed size-preserving random personnel partitions for each K2/K3, same real teams, no extra fusion. Descriptive baseline range, not randomized people, independent samples, or a significance threshold.",
        inference_limit="This is a label-independent systematic sample of cores/blocks at four n values, not all possible teams/cores/n. Blocks, base comparisons and repeated teams are not independent images or people. Feature deletion refits a multivariate partition and is not a single-variable causal effect. Retrospective discovery within previously explored v2.")
    if a.phase == "assessment":
        comparisons["inference_limit"] = comparisons["inference_limit"].replace("Retrospective discovery within previously explored v2.", "Post-freeze assessment on the six previously designated within-v2 evaluation buildings; not external blind data.")
    write(a.out / "REGISTERED_COMPARISON.json", comparisons)
    receipt = dict(common, registered_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   unique_teams=len(requests), requested_team_rows=sum(len(x["blocks"]) for x in anchors),
                   anchors=len(anchors), pools=len({x["pool_id"] for x in anchors}), buildings_n=len({x["building"] for x in anchors}),
                   people_n=len(set().union(*(set(r["worker_ids"]) for r in requests.values()))),
                   disjoint_pair_observations=sum(x["sampled_disjoint_unordered_pairs"] for x in anchors),
                   by_n=dict(collections.Counter(x["n"] for x in anchors)),
                   by_difficulty=dict(collections.Counter(x["difficulty"] for x in anchors)),
                   capacity_skips=len(skips), exhaustive_block_anchors=sum(x["exhaustive_blocks"] for x in anchors),
                   request_sha256=sha(a.out / "common_requests.json.gz"), anchor_sha256=sha(a.out / "common_anchors.json.gz"),
                   comparison_sha256=sha(a.out / "REGISTERED_COMPARISON.json"), random_labels_sha256=sha(a.out / "random_labels.csv.gz"),
                   design_code_sha256=sha(__file__))
    write(a.out / "COMMON_PANEL_REGISTRATION.json", receipt)
    if a.phase == "assessment":
        write(a.out / "ASSESSMENT_REGISTRATION.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
