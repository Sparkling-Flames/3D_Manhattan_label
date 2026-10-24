"""Targeted raw-answer-to-label replay of four current classification schemes."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "research/workers/personnel_v3_20261021/raw_answer_evidence/taxonomy"
OUT = ROOT / "research/workers/personnel_supplement_20261024/taxonomy_replay"
sys.path.insert(0, str(SOURCE))
behavior = types.ModuleType("discover_behavior_classes")
behavior.__file__ = str(SOURCE / "discover_behavior_classes.py")
sys.modules[behavior.__name__] = behavior
# The archived script moved one directory deeper; rebase its read-only input root in memory.
source_code = (SOURCE / "discover_behavior_classes.py").read_text(encoding="utf-8")
assert "REPO = HERE.parents[3]" in source_code
exec(compile(source_code.replace("REPO = HERE.parents[3]", "REPO = HERE.parents[4]"),
             behavior.__file__, "exec"), behavior.__dict__)
import discover_joint_qt as joint  # noqa: E402


def numeric_parity(actual: pd.DataFrame, saved: pd.DataFrame, fields: list[str]) -> tuple[int, float]:
    a = actual.set_index("worker_id").sort_index()
    b = saved.set_index("worker_id").sort_index()
    assert a.index.equals(b.index)
    mismatches = 0
    maximum = 0.0
    for field in fields:
        av, bv = pd.to_numeric(a[field], errors="coerce"), pd.to_numeric(b[field], errors="coerce")
        mismatches += int((av.isna() != bv.isna()).sum())
        delta = (av - bv).abs().dropna()
        if len(delta):
            maximum = max(maximum, float(delta.max()))
            mismatches += int((delta > 1e-9).sum())
    return mismatches, maximum


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = behavior.load()
    assert raw.object_id.is_unique
    studies = {"V3_BEHAVIOR": behavior.Study(raw), "V3_JOINT_QT": joint.Joint(raw)}
    rows, inner_rows = [], []
    for method, study in studies.items():
        suffix = "" if method == "V3_BEHAVIOR" else "JOINT_"
        choices = json.loads((SOURCE / f"{suffix}SELECTED_MODELS.json").read_text(encoding="utf-8"))
        saved_labels = pd.concat([pd.read_csv(SOURCE / f"{suffix}LABELS_ALL_DATA.csv"),
                                  pd.read_csv(SOURCE / f"{suffix}LABELS_LOBO.csv.gz")], ignore_index=True)
        candidates = pd.read_csv(SOURCE / f"{suffix}CANDIDATE_SELECTION_ALL.csv")
        saved_inner = pd.read_csv(SOURCE / f"{suffix}INNER_BUILDING_CANDIDATE_LOSSES.csv.gz")
        for condition in ("manual", "semi"):
            for outer in ("ALL", "7y3sRwLe3Va"):
                choice = next(c for c in choices if c["condition"] == condition and c["heldout_building"] == outer)
                excluded = () if outer == "ALL" else (outer,)
                training = study.fit_by[condition][~study.fit_by[condition].building_id.isin(excluded)]
                assert outer == "ALL" or not training.building_id.eq(outer).any()
                features = study.features(condition, excluded)
                saved = saved_labels[(saved_labels.condition == condition) &
                                     (saved_labels.heldout_building == outer) &
                                     (saved_labels.method == method)]
                assert len(features) == len(saved) == 62
                fields = ["turn_history", "short_history", "redundancy_history", "area_history",
                          "height_history", "simple_turn_history", "complex_turn_history",
                          "complex_short_history", "n_records", "n_images", "n_buildings",
                          "simple_images", "simple_buildings", "complex_images", "complex_buildings"]
                if method == "V3_JOINT_QT":
                    fields += ["q_history", "q_downside", "t_history", "q_images", "q_buildings",
                               "t_images", "t_buildings"]
                mismatches, maximum = numeric_parity(features, saved, fields)
                assert mismatches == 0, (method, condition, outer, mismatches, maximum)
                fit = study.fitted(condition, excluded, choice["family"])
                ari = []
                for tier in ("coarse", "fine"):
                    model = fit[choice[f"{tier}_k"]]
                    observed = saved.set_index("worker_id").loc[model["workers"], f"{tier}_label"]
                    assert (observed != "unknown").all()
                    ari.append(adjusted_rand_score(observed, model["labels"]))
                assert all(np.isclose(value, 1) for value in ari)
                ledger = candidates[(candidates.condition == condition) &
                                    (candidates.heldout_building == outer) & candidates.eligible_selection]
                winner = ledger.sort_values(["score", "k", "family"]).iloc[0]
                assert (winner.family, int(winner.k)) == (choice["family"], choice["fine_k"])
                assert choice["coarse_k"] == min(d["k"] for d in choice["coarse_choice"] if d["within_one_se"])
                rows.append(dict(method=method, condition=condition, outer=outer, source_records=len(raw),
                                 training_records=len(training),
                                 heldout_records_excluded=0 if outer == "ALL" else
                                 int(study.fit_by[condition].building_id.eq(outer).sum()),
                                 heldout_records_in_training=0,
                                 workers=len(features), known_workers=int(saved.known.sum()),
                                 feature_values_checked=len(fields) * len(features), feature_mismatches=mismatches,
                                 max_feature_difference=maximum, coarse_partition_ARI=ari[0],
                                 fine_partition_ARI=ari[1], selected_family=choice["family"],
                                 coarse_k=choice["coarse_k"], fine_k=choice["fine_k"],
                                 saved_candidate_winner_checked=True))
                for inner in [b for b in study.bb[condition] if b != outer]:
                    train_excluded = tuple(sorted(set([inner] + ([] if outer == "ALL" else [outer]))))
                    actual = study.evaluate(condition, train_excluded, inner, choice["family"], choice["fine_k"])
                    old = saved_inner[(saved_inner.heldout_building == outer) &
                                      (saved_inner.condition == condition) &
                                      (saved_inner.target_building == inner) &
                                      (saved_inner.family == choice["family"]) &
                                      (saved_inner.k == choice["fine_k"])]
                    assert len(old) == 1
                    delta = abs(actual["loss"] - float(old.iloc[0].loss))
                    assert delta < 1e-9, (method, condition, outer, inner, delta)
                    inner_rows.append(dict(method=method, condition=condition, outer=outer,
                                           inner=inner, family=choice["family"], k=choice["fine_k"],
                                           loss=actual["loss"], saved_loss=float(old.iloc[0].loss),
                                           abs_difference=delta, records=actual["records"],
                                           images=actual["images"], workers=actual["workers"]))
                print(method, condition, outer, "inner", len(study.bb[condition]) - (outer != "ALL"), flush=True)
    pd.DataFrame(rows).to_csv(OUT / "FEATURE_LABEL_SELECTION_CHECKS.csv", index=False)
    pd.DataFrame(inner_rows).to_csv(OUT / "SELECTED_INNER_REPLAY.csv", index=False)
    print("replayed", len(rows), "fits", len(inner_rows))


if __name__ == "__main__":
    main()
