"""联合复核两份Pro：当前输入、重跑一致性和同样本组合比较；不调参或改资格。"""
import argparse
from itertools import combinations
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle

ROOT = Path(__file__).resolve().parents[3]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def scores(i, d, b, hc, hm):
    # 前一份Pro的冻结映射：方向、底边、局部、整体；范围项单独处理以支持I=0。
    p = np.stack([1.5 * d**2 / (d**2 + 37.5), b**2 / 32,
                  (hc / .25)**2, (hm / .8)**2], axis=-1)
    w = np.array([.35, .10, .20, .05])
    v = w / .7
    total = p.sum(axis=-1)
    return dict(WQ=100 * i / (1 + i * total),
                current=100 * i / (1 + total),
                A=100 * ((w**2 / (w + p)).sum(axis=-1) + .09 * i / (1 - .7 * i)),
                RA=100 * i * (v**2 / (v + p)).sum(axis=-1))


def self_check():
    ideal = scores(np.array(1.), np.array(0.), np.array(0.), np.array(0.), np.array(0.))
    assert all(abs(v - 100) < 1e-10 for v in ideal.values())
    zero = scores(np.array(0.), np.array(0.), np.array(0.), np.array(0.), np.array(0.))
    assert zero["WQ"] == zero["RA"] == 0 and abs(zero["A"] - 70) < 1e-10
    tall = scores(np.array(1.), np.array(0.), np.array(0.), np.array(0.), np.array(3.))
    assert tall["WQ"] < 7 and tall["A"] > 95 and tall["RA"] > 92
    nonorthogonal = scores(np.array(1.), np.array(5.), np.array(0.), np.array(0.), np.array(0.))
    assert abs(nonorthogonal["WQ"] - 62.5) < 1e-10


def review(source, replay, output):
    self_check()
    output.mkdir(parents=True, exist_ok=False)
    bundle = load_current_bundle()
    snapshot = read(source / "source/historical_current_formal_loader_data.json")
    assert bundle["data"] == snapshot, "当前统一入口已变化，须先解释来源差异"
    execution = read(replay / "REPRODUCTION.json")
    assert execution["passed"] and all(s["exit_code"] == 0 for s in execution["steps"])
    current = read(replay / "results/all_scores.json")
    supplied = read(source / "results/all_scores.json")
    assert current["canonical"] == supplied["canonical"] and not current["failures"]
    key = lambda r: (r["record_id"], r["reference_id"], r["score_kind"])
    old = {key(r): r for r in supplied["records"]}
    errors = []
    for row in current["records"]:
        before = old.pop(key(row))
        for section in ("metrics", "scores"):
            assert row[section].keys() == before[section].keys()
            for field, value in row[section].items():
                original = before[section][field]
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    errors.append(abs(value - original))
                else:
                    assert value == original, (key(row), section, field)
        assert {k: v for k, v in row.items() if k not in ("metrics", "scores", "IoU3D100")} == {
            k: v for k, v in before.items() if k not in ("metrics", "scores", "IoU3D100")}
        if row["IoU3D100"] is not None:
            errors.append(abs(row["IoU3D100"] - before["IoU3D100"]))
        else:
            assert before["IoU3D100"] is None
    assert not old and max(errors) < 1e-8

    ledger = pd.read_csv(replay / "results/ALL_3152_LEDGER.csv")
    assert len(ledger) == 3152 and ledger.record_id.is_unique
    full = ledger[ledger.WQ.notna()].copy()
    assert len(full) == 1145 and not full.formal_eligibility_newly_granted.any()
    assert full.latest_step_reference_pending.sum() == 3 and full.same_target_quality_hold.sum() == 13
    predicted = scores(*(full[name].to_numpy() for name in
                         ("iou_2d", "dir", "S_bottom_deg", "Hcenter", "Hmean")))
    formula_errors = {name: float(np.max(np.abs(predicted[name] - full[name])))
                      for name in ("WQ", "current")}
    assert max(formula_errors.values()) < 1e-8
    full["A"], full["RA"] = predicted["A"], predicted["RA"]
    assert (full.A >= full.WQ - 1e-8).all()
    assert (full.RA <= 100 * full.iou_2d + 1e-8).all()

    previous = pd.read_csv(ROOT / "research/quality/quality_component_return_review_20261014/FULL_COMPARISON.csv")
    previous = previous[previous.execution_status == "scored"].rename(columns={
        "reference_object_id": "reference_id", "WQ_LS08": "previous_WQ",
        "arithmetic_candidate": "previous_A", "range_anchored_A": "previous_RA"})
    same = full.merge(previous, on=["record_id", "object_id", "image_id", "reference_id"],
                      validate="one_to_one", suffixes=("", "_previous"))
    assert len(same) == 718
    previous_errors = {name: float(np.max(np.abs(same[name] - same["previous_" + name])))
                       for name in ("WQ", "A", "RA")}
    assert max(previous_errors.values()) < 1e-8
    ordinary = full[(full.role == "manual_development_candidate") & (full.score_status == "full")]
    assert len(ordinary) == 962 and not ordinary.original_holdout.any()
    baseline = ["WQ", "current", "IoU3D100", "WQ_no_D", "WQ_no_B", "WQ_no_H"]
    models = ["current", "A", "RA", "IoU3D100"]
    reversals = dict.fromkeys(models, 0)
    substantial = dict.fromkeys(models, 0)
    count = tied = 0
    for _, group in ordinary.groupby(["image_id", "reference_id", "condition"]):
        assert group.worker_id.is_unique
        for a, b in combinations(group.index, 2):
            delta = ordinary.loc[a, baseline + ["A", "RA"]] - ordinary.loc[b, baseline + ["A", "RA"]]
            if np.max(np.abs(delta[baseline].to_numpy(dtype=float))) < 1e-10:
                tied += 1
                continue
            count += 1
            for name in models:
                reverse = delta.WQ * delta[name] < -1e-10
                reversals[name] += int(reverse)
                substantial[name] += int(reverse and abs(delta.WQ) >= 5 and abs(delta[name]) >= 5)
    assert count == 6829 and tied == 107
    assert reversals["current"] == 75 and reversals["IoU3D100"] == 1388
    masks = dict(ordinary_962=full.index.isin(ordinary.index),
                 severe_9=full.role == "severe_exception_candidate",
                 semi_39=full.role == "semi_secondary_candidate",
                 doorway_115=full.score_status == "conditional_full",
                 scope_diagnostic_10=full.score_status == "conditional_scope_diagnostic",
                 historical_10=full.score_status == "historical_only")
    summaries = {}
    for name, mask in masks.items():
        rows = full[mask]
        summaries[name] = dict(n=len(rows), images=rows.image_id.nunique(),
                               means={k: float(rows[k].mean()) for k in ["WQ", *models]})
    assert sum(s["n"] for s in summaries.values()) == 1145
    fields = ["record_id", "object_id", "image_id", "image_code", "reference_id", "reference_binding",
              "worker_id", "building_id", "condition", "role", "stage", "score_status",
              "same_target_unconfirmed", "route_uncertainty", "scope_diagnostic_reason",
              "latest_step_reference_pending", "same_target_quality_hold", "numerical_score_does_not_resolve_target",
              "original_holdout", "personnel_barriers", "context_barriers", "formal_eligibility_newly_granted",
              "iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter", "WQ", "current", "A", "RA", "IoU3D100"]
    full[fields].to_csv(output / "JOINT_COMPARISON_1145.csv", index=False, encoding="utf-8-sig")
    audit = dict(schema="quality_joint_closeout_independent_review_v1", date="2026-10-15",
                 native_data_equals_pro_snapshot=True, native_validation=bundle["validation"],
                 local_reproduction=execution, pairs=len(current["records"]), complete=1145,
                 replay_max_numeric_difference=max(errors), independent_formula_errors=formula_errors,
                 complete_with_explicit_target_hold=13, ordinary_step_pending=3,
                 previous_component_718_errors=previous_errors, summaries=summaries,
                 ordinary_same_cell_pairs=count, identical_baseline_pairs_excluded=tied,
                 reversals_against_WQ=reversals, both_gap_at_least_5_reversals=substantial,
                 not_human_validation=True, parameters_changed=False, formal_eligibility_changed=False,
                 floor_only_and_held_excluded_from_joint_full_table=True,
                 caveat="反序是指标敏感性；同图配对不独立，5分只是描述界线，不是人类效度阈值。")
    (output / "AUDIT.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    review(args.source.resolve(), args.replay.resolve(), args.output.resolve())
