#!/usr/bin/env python3
"""Metadata-only composition capacity: possible is not experimentally tested."""
import argparse
import itertools
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

SIZES = [2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32]


def coefficients(counts, nmax, only_unique_realization=False):
    coef = [1] + [0] * nmax
    for count in counts:
        terms = [0, count] if only_unique_realization and count > 0 else list(range(min(count, nmax) + 1))
        out = [0] * (nmax + 1)
        for n, value in enumerate(coef):
            if value:
                for t in terms:
                    if n + t <= nmax:
                        out[n + t] += value
        coef = out
    return coef


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--split", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    source = args.repo / "research/workers/personnel_composition_handoff_20261019"
    pools = pd.read_csv(source / "POOL_INVENTORY.csv")
    pools["difficulty"] = pools.difficulty.replace({"简单": "easy", "中等": "medium", "困难": "hard", "单列": "special"})
    members = pd.read_csv(source / "POOL_MEMBERS.csv.gz")
    labels = pd.read_csv(args.out / "worker_labels.csv.gz")
    split = json.loads(args.split.read_text())
    stage = {building: name for name in ["history", "discovery", "validation"] for building in split[name + "_buildings"]}
    pools["stage"] = pools.building.map(stage)
    bypool = dict(tuple(members.groupby("pool_id")))
    rows = []
    for (mid, domain), labs in labels.groupby(["method_id", "domain"]):
        mp = labs[labs.known].set_index("worker_id").class_id.to_dict()
        if not mp:
            continue
        applicable = pools.layer.eq("ordinary_manual")
        if domain in ["easy", "medium", "hard"]:
            applicable &= pools.difficulty.eq(domain)
        elif domain == "doorway":
            applicable = pools.layer.eq("doorway_manual")
        elif domain in ["semi_v1", "semi_new"]:
            applicable = pools.layer.eq("ordinary_semi")
        elif domain.startswith("special_"):
            applicable = pools.layer.eq(domain)
        for _, pool in pools[applicable].iterrows():
            m = bypool[pool.pool_id]
            if domain in ["semi_v1", "semi_new"]:
                m = m[m.origin.eq(domain.split("_", 1)[1])]
            c = m.worker_id.map(mp).dropna().value_counts().to_numpy(int)
            total = int(sum(c))
            dp = coefficients(c, max(SIZES))
            single = coefficients(c, max(SIZES), only_unique_realization=True)
            for n in SIZES:
                rows.append({"method_id": mid, "domain": domain, "stage": pool.stage, "pool_id": pool.pool_id, "building": pool.building, "n": n, "known_workers": total, "represented_classes": len(c), "eligible_pool": total >= n, "feasible_category_compositions": dp[n], "compositions_with_multiple_concrete_teams": dp[n] - single[n], "pure_category_compositions": int(sum(c >= n)), "different_concrete_teams": str(math.comb(total, n) if total >= n else 0)})
    d = pd.DataFrame(rows)
    # Compact stage-level capacity report; it is not a fusion search ledger.
    summary = d.groupby(["method_id", "domain", "stage", "n"], as_index=False).agg(pools=("pool_id", "nunique"), buildings=("building", "nunique"), eligible_pools=("eligible_pool", "sum"), median_available_known_workers=("known_workers", "median"), feasible_category_compositions=("feasible_category_compositions", "sum"), compositions_with_multiple_concrete_teams=("compositions_with_multiple_concrete_teams", "sum"), pure_category_compositions=("pure_category_compositions", "sum"))
    summary.to_csv(args.out / "composition_capacity_summary.csv.gz", index=False)
    msg = {"purpose": "Metadata-only eligibility/capacity, no fusion outcomes or team identities sampled", "sizes": SIZES, "note": "Counts sum separately over pools. Possible compositions/teams have not thereby been evaluated. Unknown workers cannot create a category.", "rows": len(summary), "candidate_methods_with_any_supported_history": d.method_id.nunique()}
    (args.out / "CAPACITY_README.json").write_text(json.dumps(msg, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(msg))


if __name__ == "__main__":
    main()
