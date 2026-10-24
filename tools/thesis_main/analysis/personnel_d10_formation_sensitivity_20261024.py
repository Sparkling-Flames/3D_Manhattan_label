"""Replay the frozen joint taxonomy with D10 as its entire Q input."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import adjusted_rand_score

from tools.thesis_main.analysis.personnel_supplement_taxonomy_replay_20261024 import ROOT, SOURCE, behavior, joint
from tools.thesis_main.analysis.quality_b8l2_d10_20261017 import model_parameters
from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine


OUT = ROOT / "research/workers/personnel_d10_formation_sensitivity_20261024"
FOLDS = OUT / "formation/folds"


def match_labels(old: pd.Series, new: pd.Series) -> dict[str, str]:
    table = pd.crosstab(old, new)
    i, j = linear_sum_assignment(-table.to_numpy())
    return {str(table.columns[b]): str(table.index[a]) for a, b in zip(i, j)}


def main() -> None:
    FOLDS.mkdir(parents=True, exist_ok=True)
    engine_root = ROOT / "research/statistics/b8l2_shared_v6_20261016/inputs"
    with scoring_engine(engine_root / "measurement_engine.zip", engine_root / "working_models.py") as (_, models):
        original, changed = model_parameters(models)
        a, b = asdict(original), asdict(changed)
        assert (a.pop("direction_scale_deg"), b.pop("direction_scale_deg")) == (8.0, 10.0)
        a.pop("version"); b.pop("version")
        assert a == b
    raw = behavior.load()
    assert raw.object_id.is_unique
    assert raw.B8L2.notna().equals(raw.D10.notna())
    assert raw.loc[raw.B8L2.notna(), "quality_usable"].all()
    assert raw.loc[raw.B8L2.notna(), "reference_id"].notna().all()
    q = raw[raw.B8L2.notna()].copy()
    q["lift_D10_minus_B8L2"] = q.D10 - q.B8L2
    q["peer_shift"] = q.D10_peer_delta - q.B8L2_peer_delta
    components = pd.read_csv(ROOT / "research/quality/quality_b8l2_d10_20261017/quality_records.csv",
                             usecols=["object_id", "dir", "S_bottom_deg", "iou_2d", "Hmean", "Hcenter"])
    q = q.merge(components, on="object_id", how="left", validate="one_to_one")
    assert q.object_id.is_unique and len(q) == int(raw.B8L2.notna().sum())
    q[["object_id", "worker_id", "condition", "origin", "building_id", "image_id", "difficulty", "B8L2", "D10",
       "B8L2_peer_delta", "D10_peer_delta", "lift_D10_minus_B8L2", "peer_shift", "dir", "S_bottom_deg",
       "iou_2d", "Hmean", "Hcenter"]].to_csv(OUT / "QUALIFIED_RECORD_SCORE_INPUTS.csv.gz", index=False, compression="gzip")
    q.groupby(["condition", "origin", "difficulty"]).agg(
        records=("object_id", "size"), workers=("worker_id", "nunique"), images=("image_id", "nunique"),
        mean_lift=("lift_D10_minus_B8L2", "mean"), median_lift=("lift_D10_minus_B8L2", "median"),
        mean_centered_shift=("peer_shift", "mean"), direction_records=("dir", "count"), mean_dir=("dir", "mean")).reset_index().to_csv(
            OUT / "INPUT_SCORE_STRATA.csv", index=False)
    # The archived Joint implementation reads this column for both Q features and its inner loss.
    d10_raw = raw.copy()
    d10_raw["B8L2_peer_delta"] = d10_raw.D10_peer_delta
    study = joint.Joint(d10_raw)
    old_choices = {(c["condition"], c["heldout_building"]): c for c in
                   json.loads((SOURCE / "JOINT_SELECTED_MODELS.json").read_text(encoding="utf-8"))}
    old_labels = pd.concat([pd.read_csv(SOURCE / "JOINT_LABELS_ALL_DATA.csv"),
                            pd.read_csv(SOURCE / "JOINT_LABELS_LOBO.csv.gz")], ignore_index=True)
    assert len(old_choices) == 46
    choices, candidates, inners, labels, ranks, comparisons, transitions = [], [], [], [], [], [], []
    for condition in ("manual", "semi"):
        for outer in ["ALL", *study.buildings]:
            key = condition, outer
            old_choice = old_choices[key]
            fold = f"{condition}__{outer}"
            path = FOLDS / f"{fold}.json"
            if path.exists():
                saved = json.loads(path.read_text(encoding="utf-8"))
                chosen, inner_rows = saved["choice"], saved["inner"]
            else:
                inner_rows = study.inner(condition, outer)
                chosen, _ = study.choose(condition, outer, inner_rows)
                path.write_text(json.dumps({"choice": chosen, "inner": inner_rows}, ensure_ascii=False, allow_nan=False) + "\n",
                                encoding="utf-8")
            _, table = study.choose(condition, outer, inner_rows)
            choices.append(chosen)
            candidates.append(table)
            inners.extend(inner_rows)
            for arm, choice in (("fixed_old_model", old_choice), ("reselected", chosen)):
                d = study.labels(choice)
                assert outer == "ALL" or not study.fit_by[condition][~study.fit_by[condition].building_id.eq(outer)].building_id.eq(outer).any()
                d["score_basis"] = "D10"
                d["formation_arm"] = arm
                labels.append(d)
                old = old_labels[(old_labels.condition == condition) & old_labels.heldout_building.eq(outer)]
                z = old[["worker_id", "coarse_label", "fine_label", "q_history", "q_downside", "t_history", "known"]].merge(
                    d[["worker_id", "coarse_label", "fine_label", "q_history", "q_downside", "t_history", "known", "origin"]],
                    on="worker_id", suffixes=("_B8", "_D10"), validate="one_to_one")
                z["condition"], z["heldout_building"], z["formation_arm"] = condition, outer, arm
                for metric in ("coarse", "fine"):
                    mask = z[f"{metric}_label_B8"].ne("unknown") & z[f"{metric}_label_D10"].ne("unknown")
                    mapping = match_labels(z.loc[mask, f"{metric}_label_B8"], z.loc[mask, f"{metric}_label_D10"])
                    z[f"{metric}_matched_D10"] = z[f"{metric}_label_D10"].map(mapping).fillna("unmatched")
                    compared = z.loc[mask]
                    comparisons.append(dict(condition=condition, heldout_building=outer, formation_arm=arm, tier=metric,
                                            workers=len(compared), old_known=int(z[f"{metric}_label_B8"].ne("unknown").sum()),
                                            d10_known=int(z[f"{metric}_label_D10"].ne("unknown").sum()),
                                            ARI=adjusted_rand_score(compared[f"{metric}_label_B8"], compared[f"{metric}_label_D10"]),
                                            matched_same=int((compared[f"{metric}_label_B8"] == compared[f"{metric}_matched_D10"]).sum()),
                                            old_family=old_choice["family"], old_k=old_choice[f"{metric}_k"],
                                            d10_family=choice["family"], d10_k=choice[f"{metric}_k"]))
                    tab = z.groupby([f"{metric}_label_B8", f"{metric}_label_D10", f"{metric}_matched_D10"]).size().reset_index(name="workers")
                    tab["condition"], tab["heldout_building"], tab["formation_arm"], tab["tier"] = condition, outer, arm, metric
                    transitions.append(tab)
                z["rank_B8"] = z.q_history_B8.rank(ascending=False, method="min")
                z["rank_D10"] = z.q_history_D10.rank(ascending=False, method="min")
                z["rank_shift_D10_minus_B8"] = z.rank_D10 - z.rank_B8
                ranks.append(z)
            study.fitted.cache_clear()
            study.features.cache_clear()
            print("formed", condition, outer, chosen["family"], chosen["coarse_k"], chosen["fine_k"], flush=True)
    pd.DataFrame(choices).to_json(OUT / "D10_RESELECTED_CHOICES.json", orient="records", force_ascii=False, indent=2)
    pd.concat(candidates, ignore_index=True).to_csv(OUT / "D10_CANDIDATE_SELECTION.csv", index=False)
    pd.DataFrame(inners).to_csv(OUT / "D10_INNER_BUILDING_LOSSES.csv.gz", index=False, compression="gzip")
    fitted_labels = pd.concat(labels, ignore_index=True)
    fitted_labels.to_csv(OUT / "D10_LABELS_FIXED_AND_RESELECTED.csv.gz", index=False, compression="gzip")
    class_rows = []
    for tier in ("coarse", "fine"):
        known = fitted_labels[fitted_labels.known].copy()
        for key, group in known.groupby(["condition", "heldout_building", "formation_arm", f"{tier}_label"]):
            class_rows.append(dict(condition=key[0], heldout_building=key[1], formation_arm=key[2], tier=tier,
                                   class_label=key[3], workers=len(group), members="|".join(sorted(group.worker_id)),
                                   q_history=group.q_history.mean(), q_downside=group.q_downside.mean(),
                                   t_history=group.t_history.mean(), turn_history=group.turn_history.mean(),
                                   short_history=group.short_history.mean(), origin_v1=int(group.origin.eq("v1").sum()),
                                   origin_new=int(group.origin.eq("new").sum())))
    pd.DataFrame(class_rows).to_csv(OUT / "D10_CLASS_CAPACITIES_AND_CENTERS.csv", index=False)
    pd.concat(ranks, ignore_index=True).to_csv(OUT / "WORKER_RANK_AND_LABELS.csv.gz", index=False, compression="gzip")
    pd.DataFrame(comparisons).to_csv(OUT / "PARTITION_COMPARISON.csv", index=False)
    pd.concat(transitions, ignore_index=True).to_csv(OUT / "LABEL_TRANSITIONS.csv", index=False)
    exclusions = []
    for condition in ("manual", "semi"):
        records = study.fit_by[condition]
        for outer in ["ALL", *study.buildings]:
            for inner in ["ALL", *[b for b in study.bb[condition] if b != outer]]:
                withheld = set(() if outer == "ALL" else (outer,)) | set(() if inner == "ALL" else (inner,))
                train = records[~records.building_id.isin(withheld)]
                exclusions.append(dict(condition=condition, outer=outer, inner=inner,
                                       excluded_buildings="|".join(sorted(withheld)),
                                       training_records=len(train), excluded_records=len(records)-len(train),
                                       target_outer_in_training=int(train.building_id.eq(outer).sum()) if outer != "ALL" else 0,
                                       target_inner_in_training=int(train.building_id.eq(inner).sum()) if inner != "ALL" else 0))
    pd.DataFrame(exclusions).to_csv(OUT / "TRAINING_EXCLUSION_LEDGER.csv", index=False)
    print("complete", len(choices), len(inners), flush=True)


if __name__ == "__main__":
    main()
