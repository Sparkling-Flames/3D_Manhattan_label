"""Fixed-panel label randomization for the four current v2 classifications."""

from __future__ import annotations

import gzip
import itertools
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "research/workers/personnel_mixture_comparison_20261022/configurations"
OUT = ROOT / "research/workers/personnel_supplement_20261024/random_reference"
SEED = 20261024
REPEATS = 99
METRICS = ("B8L2", "fusion_turn_n", "recorded_time_total_seconds", "failure")
COMBINATIONS = list(itertools.combinations(range(12), 6))
SELECT = np.zeros((924, 12), dtype=np.int8)
for row, indices in enumerate(COMBINATIONS):
    SELECT[row, list(indices)] = 1


def explained(y: np.ndarray, composition: np.ndarray) -> float:
    good = np.isfinite(y)
    if good.sum() < 2:
        return np.nan
    values = y[good]
    total = np.sum((values - values.mean()) ** 2)
    if total == 0:
        return np.nan
    _, group = np.unique(composition[good], return_inverse=True)
    sizes = np.bincount(group)
    means = np.bincount(group, weights=values) / sizes
    return float(np.sum(sizes * (means - values.mean()) ** 2) / total)


def main() -> None:
    assert abs(explained(np.array([0., 1., 2., 3.]), np.array([0, 0, 1, 1])) - .8) < 1e-12
    OUT.mkdir(parents=True, exist_ok=True)
    panels = pd.read_csv(SOURCE / "PANELS_USED.csv").set_index("panel_id")
    support = pd.read_csv(SOURCE / "PANEL_SUPPORT.csv")
    support = support[support.status.eq("complete_924_labelled")]
    labels = pd.read_csv(SOURCE / "LOBO_LABELS_USED.csv.gz")
    labels = labels.set_index(["condition", "heldout_building", "method", "worker_id"])
    teams = pd.read_csv(SOURCE / "PANEL_TEAMS.csv.gz")
    endpoints = pd.concat(
        [pd.read_csv(SOURCE / f"ENDPOINT_OUTCOMES_{condition}.csv.gz", usecols=["team_key", *METRICS])
         for condition in ("manual", "semi")],
        ignore_index=True,
    ).drop_duplicates("team_key").set_index("team_key")
    rng = np.random.default_rng(SEED)
    rows = []
    null_rows = []
    for panel_id, panel_teams in teams.groupby("panel_id", sort=True):
        chosen = support[support.panel_id.eq(panel_id)]
        if chosen.empty:
            continue
        panel = panels.loc[panel_id]
        workers = panel.variable_workers.split("|")
        assert len(workers) == 12 and len(panel_teams) == 924
        memberships = {frozenset(w.split("|")): k for k, w in
                       panel_teams[["team_key", "selected_variable_workers"]].itertuples(index=False, name=None)}
        ordered_keys = [memberships[frozenset(workers[i] for i in pick)] for pick in COMBINATIONS]
        outcome = endpoints.loc[ordered_keys]
        for method, tier in chosen[["method", "tier"]].itertuples(index=False, name=None):
            worker_labels = [labels.loc[(panel.condition, panel.building, method, w), f"{tier}_label"]
                             for w in workers]
            assert all(isinstance(label, str) for label in worker_labels)
            labels_int = np.unique(worker_labels, return_inverse=True)[1]
            weights = 7 ** labels_int
            observed_code = SELECT @ weights
            origins = [labels.loc[(panel.condition, panel.building, method, w), "origin"]
                       for w in workers]
            assert all(isinstance(origin, str) for origin in origins)
            strata = [np.flatnonzero(np.array(origins) == origin) for origin in sorted(set(origins))]
            possible = 1
            for indices in strata:
                counts = np.unique(weights[indices], return_counts=True)[1]
                possible *= math.factorial(len(indices)) // math.prod(math.factorial(int(n)) for n in counts)
            # Whole-worker labels are shuffled only among candidates from the same source.
            unique = {tuple(weights)}
            attempts = 0
            while len(unique) < min(REPEATS, possible) and attempts < 10000:
                shuffled = weights.copy()
                for indices in strata:
                    shuffled[indices] = rng.permutation(shuffled[indices])
                unique.add(tuple(shuffled))
                attempts += 1
            assert len(unique) <= possible and all(
                sorted(np.array(assignment)[indices]) == sorted(weights[indices])
                for assignment in unique for indices in strata)
            permutations = [np.array(assignment) for assignment in sorted(unique)]
            for metric in METRICS:
                y = outcome[metric].to_numpy(float)
                actual = explained(y, observed_code)
                randomized = np.array([explained(y, SELECT @ perm) for perm in permutations])
                if not np.isfinite(actual):
                    continue
                assert np.isfinite(randomized).all()
                total_variance = float(np.nanvar(y))
                base = dict(panel_id=panel_id, image=panel.image, building=panel.building,
                            condition=panel.condition, difficulty=panel.difficulty,
                            source_domain=panel.source_domain, n=int(panel.n), method=method,
                            tier=tier, metric=metric, valid_teams=int(np.isfinite(y).sum()),
                            configurations=int(np.unique(observed_code).size),
                            source_strata="|".join(f"{origin}:{sum(o == origin for o in origins)}"
                                                   for origin in sorted(set(origins))),
                            possible_assignments=possible, distinct_assignments=len(permutations))
                rows.append({**base, "observed_eta2": actual,
                             "total_variance": total_variance,
                             "observed_between_variance": total_variance * actual,
                             "observed_within_variance": total_variance * (1 - actual),
                             "random_between_mean": total_variance * float(randomized.mean()),
                             "random_within_mean": total_variance * (1 - float(randomized.mean())),
                             "random_mean_eta2": float(randomized.mean()),
                             "random_p05_eta2": float(np.quantile(randomized, .05)),
                             "random_p95_eta2": float(np.quantile(randomized, .95)),
                             "observed_minus_random": float(actual - randomized.mean()),
                             "random_rank_ge_observed": int(np.sum(randomized >= actual))})
                null_rows.extend({"panel_id": panel_id, "method": method, "tier": tier,
                                  "metric": metric, "repeat": j + 1, "eta2": float(v)}
                                 for j, v in enumerate(randomized))
    result = pd.DataFrame(rows)
    assert not result.empty and result.panel_id.nunique() <= 336
    result.to_csv(OUT / "PANEL_REFERENCE.csv", index=False)
    with gzip.open(OUT / "RANDOM_DRAWS.csv.gz", "wt", encoding="utf-8", newline="") as stream:
        pd.DataFrame(null_rows).to_csv(stream, index=False)
    by_building = result.groupby(["condition", "method", "tier", "metric", "building"], dropna=False).agg(
        panels=("panel_id", "nunique"), observed_eta2=("observed_eta2", "mean"),
        random_eta2=("random_mean_eta2", "mean"), delta=("observed_minus_random", "mean"),
        informative_panels=("possible_assignments", lambda x: int((x > 1).sum())),
        positive_panels=("observed_minus_random", lambda x: int((x > 0).sum())),
    ).reset_index()
    by_building.to_csv(OUT / "BUILDING_REFERENCE.csv", index=False)
    summary = by_building.groupby(["condition", "method", "tier", "metric"]).agg(
        buildings=("building", "nunique"), panels=("panels", "sum"),
        informative_panels=("informative_panels", "sum"),
        observed_eta2=("observed_eta2", "mean"), random_eta2=("random_eta2", "mean"),
        delta=("delta", "mean"), positive_buildings=("delta", lambda x: int((x > 0).sum())),
    ).reset_index()
    summary.to_csv(OUT / "SUMMARY.csv", index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
