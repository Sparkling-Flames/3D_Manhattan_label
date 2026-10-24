"""Cross-score fixed 12-choose-6 panels after B8L2/D10 taxonomy formation."""

from __future__ import annotations

import hashlib
import csv
import gzip
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from tools.thesis_main.analysis.personnel_d10_formation_sensitivity_20261024 import OUT, ROOT, SOURCE


CONFIG = ROOT / "research/workers/personnel_mixture_comparison_20261022/configurations"
METRICS = ("B8L2", "D10", "iou_2d", "IoU3D100", "S_bottom_deg", "dir", "Hmean", "Hcenter",
           "fusion_turn_n", "fusion_short_turn_edges")
ARMS = ("B8L2_original", "D10_fixed_old_model", "D10_reselected")


def names(value: str) -> tuple[str, ...]:
    return tuple(value.split("|"))


def vector(workers: tuple[str, ...], label: dict[str, str]) -> str:
    counts = Counter(label[w] for w in workers)
    return "|".join(f"{k}:{counts[k]}" for k in sorted(counts))


def seed(value: str) -> int:
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:8], "big")


def center(counts: str, means: dict[str, float]) -> float:
    parts = [(name, int(number)) for name, number in (item.split(":") for item in counts.split("|"))]
    return sum(means[name] * number for name, number in parts) / sum(number for _, number in parts)


def main() -> None:
    panels = pd.read_csv(CONFIG / "PANELS_USED.csv")
    panel_teams = pd.read_csv(CONFIG / "PANEL_TEAMS.csv.gz")
    outcome = pd.concat([pd.read_csv(CONFIG / f"ENDPOINT_OUTCOMES_{c}.csv.gz") for c in ("manual", "semi")], ignore_index=True)
    assert outcome.team_key.is_unique
    endpoint = outcome.set_index("team_key", verify_integrity=True)
    old = pd.read_csv(SOURCE / "JOINT_LABELS_LOBO.csv.gz")
    old["formation_arm"] = ARMS[0]
    d10 = pd.read_csv(OUT / "D10_LABELS_FIXED_AND_RESELECTED.csv.gz")
    d10 = d10[d10.heldout_building.ne("ALL")].copy()
    d10.formation_arm = "D10_" + d10.formation_arm
    labels = pd.concat([old, d10], ignore_index=True)
    assert labels.groupby(["condition", "heldout_building", "formation_arm"]).worker_id.nunique().eq(62).all()
    roster = {(c, b, arm): g.set_index("worker_id", verify_integrity=True)
              for (c, b, arm), g in labels.groupby(["condition", "heldout_building", "formation_arm"])}
    per_panel = {k: g for k, g in panel_teams.groupby("panel_id")}
    coverage, cells, selected, abc_events, abc_coverage = [], [], [], [], []
    link_path = OUT / "COMPOSITION_TEAM_LINKS.csv.gz.partial"
    link_file = gzip.open(link_path, "wt", encoding="utf-8", newline="")
    link_writer = csv.writer(link_file)
    link_writer.writerow(["panel_id", "condition", "building", "formation_arm", "tier", "team_key", "class_counts", "known"])
    for panel in panels.itertuples(index=False):
        p = panel.panel_id
        teams = per_panel[p]
        assert len(teams) == 924 and teams.team_key.is_unique
        candidate = names(panel.variable_workers)
        background = names(panel.background_workers)
        assert len(candidate) == 12 and len(background) == panel.background_n
        team_lookup = {tuple(sorted(names(r.selected_variable_workers))): r.team_key for r in teams.itertuples(index=False)}
        assert len(team_lookup) == 924 and all(k in endpoint.index for k in team_lookup.values())
        workers_by_key = {v: k for k, v in team_lookup.items()}
        random_order = list(np.random.default_rng(seed(p)).permutation(candidate))
        rank_tie = {w: i for i, w in enumerate(random_order)}
        partitions = {}
        for m in (2, 3):
            rng = np.random.default_rng(seed(f"{p}|m{m}"))
            attempts = []
            for attempt in range(128):
                w = list(rng.permutation(candidate))
                common = w[:6 - m]
                groups = (w[6 - m:6], w[6:6 + m], w[6 + m:6 + 2 * m])
                keys = tuple(team_lookup[tuple(sorted((*common, *block)))] for block in groups)
                assert len(set(keys)) == 3
                attempts.append((attempt, keys))
            partitions[m] = attempts
        scheme_vectors = {}
        scheme_status = {}
        scheme_centers = {}
        for arm in ARMS:
            fold = roster[panel.condition, panel.building, arm]
            required = set(candidate) | set(background)
            known = {w for w in required if w in fold.index and bool(fold.loc[w, "known"])}
            complete = len(known) == len(required)
            background_known = set(background) <= known
            scheme_status[arm] = background_known
            known_teams = sum(set(workers) <= known for workers in team_lookup) if background_known else 0
            coverage.append(dict(panel_id=p, image=panel.image, building=panel.building, condition=panel.condition,
                                 difficulty=panel.difficulty, source_domain=panel.source_domain, n=panel.n,
                                 formation_arm=arm, required_workers=len(required), known_workers=len(known),
                                 background_known=background_known, complete_panel=complete,
                                 known_teams=known_teams, unknown_teams=924-known_teams, possible_teams=924))
            q = fold.q_history.to_dict()
            t = fold.t_history.to_dict()
            for tier in ("coarse", "fine"):
                label = fold[f"{tier}_label"].to_dict()
                qcenter = fold[fold.known].groupby(f"{tier}_label").q_history.mean()
                high_class = str(qcenter.idxmax())
                scheme_centers[arm, tier] = {field: fold[fold.known].groupby(f"{tier}_label")[field].mean().to_dict()
                                             for field in ("q_history", "t_history", "turn_history")}
                vec = {team_key: vector((*background, *workers), label) for workers, team_key in team_lookup.items()
                       if background_known and set(workers) <= known}
                scheme_vectors[arm, tier] = vec
                values = teams[["team_key"]].copy()
                values["class_counts"] = values.team_key.map(vec)
                values[["B8L2", "D10", "failure"]] = endpoint.loc[values.team_key, ["B8L2", "D10", "failure"]].to_numpy()
                link_writer.writerows((p, panel.condition, panel.building, arm, tier, r.team_key,
                                       r.class_counts if pd.notna(r.class_counts) else "", pd.notna(r.class_counts))
                                      for r in values.itertuples(index=False))
                for counts, group in values.groupby("class_counts"):
                    cells.append(dict(panel_id=p, image=panel.image, building=panel.building, condition=panel.condition,
                                      difficulty=panel.difficulty, source_domain=panel.source_domain, n=panel.n,
                                      formation_arm=arm, tier=tier, class_counts=counts, teams=len(group),
                                      failed=int(group.failure.sum()), B8L2_valid=int(group.B8L2.notna().sum()),
                                      D10_valid=int(group.D10.notna().sum()), B8L2_mean=group.B8L2.mean(),
                                      D10_mean=group.D10.mean(), B8L2_sd=group.B8L2.std(), D10_sd=group.D10.std()))
                if not complete:
                    continue
                qmed, tmed = fold.q_history.median(), fold.t_history.median()
                qs = fold.q_history.quantile(.75) - fold.q_history.quantile(.25)
                ts = fold.t_history.quantile(.75) - fold.t_history.quantile(.25)
                assert qs > 0 and ts > 0
                choices = {
                    "class_highq": sorted(candidate, key=lambda w: (label[w] != high_class, rank_tie[w]))[:6],
                    "continuous_q": sorted(candidate, key=lambda w: (-q[w], rank_tie[w]))[:6],
                    "continuous_qt_equal": sorted(candidate, key=lambda w: (-((q[w]-qmed)/qs-(t[w]-tmed)/ts), rank_tie[w]))[:6],
                }
                for policy, workers in choices.items():
                    team_key = team_lookup[tuple(sorted(workers))]
                    row = endpoint.loc[team_key]
                    selected.append(dict(panel_id=p, image=panel.image, building=panel.building, condition=panel.condition,
                                         difficulty=panel.difficulty, source_domain=panel.source_domain, n=panel.n,
                                         formation_arm=arm, tier=tier, policy=policy, target_class=high_class if policy == "class_highq" else "",
                                         selected_workers="|".join(sorted(workers)), team_key=team_key,
                                         **{m: row[m] for m in METRICS}, failure=row.failure,
                                         recorded_time_eligible=row.recorded_time_eligible,
                                         recorded_time_total_seconds=row.recorded_time_total_seconds,
                                         time_source_kinds=row.time_source_kinds))
        for tier in ("coarse", "fine"):
            for m, attempts in partitions.items():
                stats = Counter()
                for attempt, triple in attempts:
                    eligibility = {}
                    ordered = {}
                    for arm in ARMS:
                        if not scheme_status[arm] or any(k not in scheme_vectors[arm, tier] for k in triple):
                            eligibility[arm] = "unknown_labels"
                            continue
                        vectors = [scheme_vectors[arm, tier][k] for k in triple]
                        groups = Counter(vectors)
                        if sorted(groups.values()) == [1, 2]:
                            within = sorted(k for k, v in zip(triple, vectors) if groups[v] == 2)
                            changed = next(k for k, v in zip(triple, vectors) if groups[v] == 1)
                            ordered[arm] = (*within, changed)
                            eligibility[arm] = "strict_ABC"
                        elif len(groups) == 1:
                            eligibility[arm] = "all_same"
                        else:
                            eligibility[arm] = "all_different"
                    stats[tuple(eligibility[a] for a in ARMS)] += 1
                    for arm, keys in ordered.items():
                        a, b, c = (endpoint.loc[k] for k in keys)
                        all_scored = all(pd.notna(v[metric]) for v in (a, b, c) for metric in METRICS[:8])
                        item = dict(panel_id=p, image=panel.image, building=panel.building, condition=panel.condition,
                                    difficulty=panel.difficulty, source_domain=panel.source_domain, n=panel.n, m=m,
                                    attempt=attempt, formation_arm=arm, tier=tier, team_A=keys[0], team_B=keys[1], team_C=keys[2],
                                    A_selected_workers="|".join(workers_by_key[keys[0]]),
                                    B_selected_workers="|".join(workers_by_key[keys[1]]),
                                    C_selected_workers="|".join(workers_by_key[keys[2]]),
                                    A_class_counts=scheme_vectors[arm, tier][keys[0]], B_class_counts=scheme_vectors[arm, tier][keys[1]],
                                    C_class_counts=scheme_vectors[arm, tier][keys[2]], all_scored=all_scored,
                                    A_failure=int(a.failure), B_failure=int(b.failure), C_failure=int(c.failure))
                        for field in ("q_history", "t_history", "turn_history"):
                            means = scheme_centers[arm, tier][field]
                            item[f"class_center_{field}_C_minus_B"] = center(item["C_class_counts"], means) - center(item["B_class_counts"], means)
                        time_valid = all(bool(v.recorded_time_eligible) for v in (a, b, c)) and \
                            len({v.time_source_kinds for v in (a, b, c)}) == 1 and "|" not in str(a.time_source_kinds)
                        item["recorded_time_comparable"] = time_valid
                        if time_valid:
                            item["recorded_time_logratio_C_B"] = np.log(float(c.recorded_time_total_seconds) /
                                                                          float(b.recorded_time_total_seconds))
                        for metric in METRICS:
                            if all_scored and all(pd.notna(v[metric]) for v in (a, b, c)):
                                x, y, z = (float(v[metric]) for v in (a, b, c))
                                item[f"{metric}_within_abs"] = abs(y-x)
                                item[f"{metric}_cross_abs"] = (abs(z-x)+abs(z-y))/2
                                item[f"{metric}_extra_abs"] = item[f"{metric}_cross_abs"]-item[f"{metric}_within_abs"]
                                item[f"{metric}_net_C_minus_B"] = z-y
                        abc_events.append(item)
                for states, count in stats.items():
                    abc_coverage.append(dict(panel_id=p, image=panel.image, building=panel.building, condition=panel.condition,
                                             difficulty=panel.difficulty, source_domain=panel.source_domain, n=panel.n, m=m, tier=tier,
                                             attempts=count, **{f"{arm}_status": state for arm, state in zip(ARMS, states)}))
        print("panel", p, flush=True)
    link_file.close()
    link_path.replace(OUT / "COMPOSITION_TEAM_LINKS.csv.gz")
    pd.DataFrame(coverage).to_csv(OUT / "PANEL_LABEL_COVERAGE.csv", index=False)
    pd.DataFrame(cells).to_csv(OUT / "COMPOSITION_CELLS.csv.gz", index=False, compression="gzip")
    pd.DataFrame(selected).to_csv(OUT / "SELECTED_TEAMS.csv.gz", index=False, compression="gzip")
    pd.DataFrame(abc_events).drop_duplicates(["panel_id", "formation_arm", "tier", "m", "team_A", "team_B", "team_C"]).to_csv(
        OUT / "ABC_EVENTS.csv.gz", index=False, compression="gzip")
    pd.DataFrame(abc_coverage).to_csv(OUT / "ABC_COVERAGE.csv", index=False)
    print("done", len(cells), len(selected), len(abc_events), flush=True)


if __name__ == "__main__":
    main()
