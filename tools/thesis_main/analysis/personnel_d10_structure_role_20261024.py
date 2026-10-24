"""Re-choose the high-Q role of unchanged structure classes on fixed panels."""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from tools.thesis_main.analysis.personnel_d10_formation_sensitivity_20261024 import OUT, ROOT, SOURCE
from tools.thesis_main.analysis.personnel_d10_panel_response_20261024 import CONFIG, METRICS, names


def main() -> None:
    panels = pd.read_csv(CONFIG / "PANELS_USED.csv")
    teams = pd.read_csv(CONFIG / "PANEL_TEAMS.csv.gz")
    endpoints = pd.concat([pd.read_csv(CONFIG / f"ENDPOINT_OUTCOMES_{c}.csv.gz") for c in ("manual", "semi")], ignore_index=True)
    endpoints = endpoints.set_index("team_key", verify_integrity=True)
    structure = pd.read_csv(SOURCE / "LABELS_LOBO.csv.gz")
    assert structure.method.eq("V3_BEHAVIOR").all()
    q = pd.read_csv(OUT / "WORKER_RANK_AND_LABELS.csv.gz")
    q = q[q.formation_arm.eq("reselected")]
    assert q.groupby(["condition", "heldout_building"]).worker_id.nunique().eq(62).all()
    roster = {(c, b): g.set_index("worker_id", verify_integrity=True) for (c, b), g in
              structure.groupby(["condition", "heldout_building"])}
    quality = {(c, b): g.set_index("worker_id", verify_integrity=True) for (c, b), g in
               q.groupby(["condition", "heldout_building"])}
    by_panel = {p: g for p, g in teams.groupby("panel_id")}
    rows = []
    for panel in panels.itertuples(index=False):
        c, b, p = panel.condition, panel.building, panel.panel_id
        labels, history = roster[c, b], quality[c, b]
        variable, background = names(panel.variable_workers), names(panel.background_workers)
        required = set(variable) | set(background)
        if any(w not in labels.index or not bool(labels.loc[w, "known"]) for w in required):
            for basis in ("B8L2", "D10"):
                rows.append(dict(panel_id=p, image=panel.image, building=b, condition=c, difficulty=panel.difficulty,
                                 source_domain=panel.source_domain, n=panel.n, score_basis=basis, available=False))
            continue
        lookup = {tuple(sorted(names(r.selected_variable_workers))): r.team_key for r in by_panel[p].itertuples(index=False)}
        assert len(lookup) == 924
        random_order = list(np.random.default_rng(int.from_bytes(hashlib.sha256(p.encode()).digest()[:8], "big")).permutation(variable))
        tie = {w: i for i, w in enumerate(random_order)}
        for basis, field in (("B8L2", "q_history_B8"), ("D10", "q_history_D10")):
            for tier in ("coarse", "fine"):
                joined = labels[[f"{tier}_label"]].join(history[[field]], how="left")
                centers = joined.groupby(f"{tier}_label")[field].mean().dropna()
                assert not centers.empty
                role = str(centers.idxmax())
                chosen = sorted(variable, key=lambda w: (labels.loc[w, f"{tier}_label"] != role, tie[w]))[:6]
                team_key = lookup[tuple(sorted(chosen))]
                endpoint = endpoints.loc[team_key]
                rows.append(dict(panel_id=p, image=panel.image, building=b, condition=c, difficulty=panel.difficulty,
                                 source_domain=panel.source_domain, n=panel.n, score_basis=basis, tier=tier, available=True,
                                 highq_structure_class=role, selected_workers="|".join(sorted(chosen)), team_key=team_key,
                                 **{metric: endpoint[metric] for metric in METRICS}, failure=endpoint.failure,
                                 recorded_time_eligible=endpoint.recorded_time_eligible,
                                 recorded_time_total_seconds=endpoint.recorded_time_total_seconds,
                                 time_source_kinds=endpoint.time_source_kinds))
    result = pd.DataFrame(rows)
    result.to_csv(OUT / "STRUCTURE_HIGHQ_ROLE_SELECTED.csv", index=False)
    base = result[result.score_basis.eq("B8L2")]
    newer = result[result.score_basis.eq("D10")]
    paired = base.merge(newer, on=["panel_id", "tier"], suffixes=("_B8", "_D10"), validate="one_to_one")
    paired["role_changed"] = paired.available_B8.astype(bool) & paired.available_D10.astype(bool) & \
        paired.highq_structure_class_B8.ne(paired.highq_structure_class_D10)
    paired["replacements"] = [6 - len(set(a.split("|")) & set(b.split("|"))) if isinstance(a, str) and isinstance(b, str) else np.nan
                              for a, b in zip(paired.selected_workers_B8, paired.selected_workers_D10)]
    good = paired[[f"{metric}_{side}" for metric in METRICS[:8] for side in ("B8", "D10")]].notna().all(axis=1)
    for metric in METRICS:
        paired[f"{metric}_delta"] = (paired[f"{metric}_D10"] - paired[f"{metric}_B8"]).where(good)
    paired.to_csv(OUT / "STRUCTURE_HIGHQ_ROLE_PAIRED.csv", index=False)
    paired.groupby(["condition_B8", "difficulty_B8", "tier"]).agg(
        panels=("panel_id", "size"), available_both=("replacements", "count"),
        role_changed=("role_changed", "sum"), changed_teams=("replacements", lambda x: int((x > 0).sum())),
        mean_replacements=("replacements", "mean"), B8L2_delta=("B8L2_delta", "mean"),
        D10_delta=("D10_delta", "mean")).reset_index().to_csv(OUT / "STRUCTURE_HIGHQ_ROLE_SUMMARY.csv", index=False)
    print("structure role", len(result), int(result.available.sum()), flush=True)


if __name__ == "__main__":
    main()
