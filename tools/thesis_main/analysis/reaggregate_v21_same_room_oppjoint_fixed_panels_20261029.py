"""Reconnect OPPJOINT to saved same-room teams; no selection, fitting or fusion.

The finite panels were selected using V3_BEHAVIOR. This conditional reanalysis
uses their unchanged endpoints, with common K3/K4 label and outcome support.
"""
from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
RELEASE = ROOT / "research/data/releases/v2.1"
OUT = RELEASE / "same_room_oppjoint_fixed_panels"
METHODS = ("OPPJOINT_K3", "OPPJOINT_K4")
DESIGN = RELEASE / "same_room_current_extended_design"
ENDPOINTS = RELEASE / "same_room_current_results/finite/native/ENDPOINT_SCALARS.csv.gz"
LABELS = ROOT / "research/workers/personnel_v21_reselection_20261029/stage07_adoption/PERSONNEL_LOBO_LABELS_AND_SUPPORT.csv.gz"
ENGINE = ROOT / "research/same_room/same_room_current_classes_v2_20261023/code/taxonomy_response/analyze_response.py"


def load_engine():
    spec = importlib.util.spec_from_file_location("saved_same_room_response", ENGINE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SCHEMES = {m: m + "_vector" for m in METHODS}
    return module


def as_bool(series):
    result = series.map({True: True, False: False, "True": True, "False": False})
    if result.isna().any():
        raise ValueError("Missing or invalid boolean state")
    return result.astype(bool)


def annotate_compositions(panels, links, labels):
    """Count the entire actual team, including an explicit unknown category."""
    use = labels[labels.method.isin(METHODS)].copy()
    assert len(use) and not use.heldout_building.eq("ALL").any()
    assert use.label_stage.eq("leave_target_building_out").all()
    assert use.input_conditions.eq("manual").all()
    assert use.evaluation_condition.eq("manual").all()
    assert not use.duplicated(["method", "heldout_building", "worker_id"]).any()
    use["known"] = as_bool(use.known)
    assert use.loc[use.known, "class_id"].notna().all()
    known = use[use.known].pivot(index=["heldout_building", "worker_id"], columns="method", values="class_id").dropna()
    nested = known.reset_index().groupby(["heldout_building", "OPPJOINT_K4"]).OPPJOINT_K3.nunique()
    assert nested.eq(1).all()
    roster = {(r.method, r.heldout_building, r.worker_id): str(r.class_id)
              for r in use.itertuples() if r.known}
    pm = panels.set_index("panel_id").to_dict("index")
    assert not panels.panel_id.duplicated().any()
    assert not links.duplicated(["panel_id", "member_set_key"]).any()
    result = links.copy()
    for method in METHODS:
        vectors, known = [], []
        for row in links.itertuples():
            panel = pm[row.panel_id]
            workers = row.member_set_key.split("|")
            assert len(workers) == len(set(workers)) == panel["n"]
            counts = Counter()
            for worker in workers:
                key = (method, panel["building"], worker)
                counts[roster.get(key, "unknown")] += 1
            assert sum(counts.values()) == panel["n"]
            vectors.append(json.dumps(dict(sorted(counts.items())), separators=(",", ":")))
            known.append("unknown" not in counts)
        result[method + "_vector"] = vectors
        result[method + "_all_known"] = known
    result["both_methods_all_known"] = result[[m + "_all_known" for m in METHODS]].all(axis=1)
    return result


def join_endpoints(panels, links, endpoints, metrics):
    """Verify identities before joining scalar responses; never impute failures."""
    assert not endpoints.team_key.duplicated().any()
    meta = panels.set_index("panel_id")
    identity = endpoints.set_index("team_key")
    expected = links.join(meta[["building", "n", "pool_id_a", "pool_id_b", "reference_id_a", "reference_id_b"]], on="panel_id")
    for side in ("a", "b"):
        keys = expected["team_key_" + side]
        assert keys.isin(identity.index).all()
        got = identity.loc[keys].reset_index(drop=True)
        assert got.member_workers.map(lambda s: "|".join(sorted(s.split("|")))).eq(expected.member_set_key.reset_index(drop=True)).all()
        assert got.k.eq(expected.n.to_numpy()).all()
        assert got.building.eq(expected.building.to_numpy()).all()
        assert got.pool_id.eq(expected["pool_id_" + side].to_numpy()).all()
        assert got.reference_id.eq(expected["reference_id_" + side].to_numpy()).all()
        assert got.condition.eq("manual").all()
    e = endpoints.copy()
    e["failure"] = 1 - as_bool(e.complete_evaluable).astype(float)
    time = pd.to_numeric(e.recorded_time_total_seconds, errors="coerce")
    valid_time = as_bool(e.recorded_time_eligible) & time.gt(0)
    e["log_recorded_time"] = np.log(time.where(valid_time))
    assert set(metrics).issubset(e.columns)
    selected = e[["team_key"] + metrics]
    joined = links.copy()
    for side in ("a", "b"):
        joined = joined.merge(selected.add_suffix("_" + side), on="team_key_" + side, how="left", validate="many_to_one")
    assert len(joined) == len(links)
    return joined


def summarize(panels, paired, engine):
    pm = panels.set_index("panel_id", drop=False)
    rows, supports = [], []
    for panel_id, group in paired.groupby("panel_id", sort=False):
        p = pm.loc[panel_id]
        meta = {c: p[c] for c in engine.META}
        meta["panel_selection_method"] = meta.pop("method")
        meta["analysis_layer"] = engine.analysis_layer(meta)
        common = group[group.both_methods_all_known]
        support = dict(meta, requested_team_pairs=len(group), common_known_team_pairs=len(common))
        for method in METHODS:
            support[method + "_known_team_pairs"] = int(group[method + "_all_known"].sum())
            support[method + "_compositions"] = common[method + "_vector"].nunique()
        supports.append(support)
        if len(common) < 2:
            continue
        for metric in engine.METRICS:
            for method in METHODS:
                rows.append(meta | engine.moments(common, metric, method))
    return engine.numeric_indicators(pd.DataFrame(rows)), pd.DataFrame(supports)


def aggregate(moments, engine):
    usable = moments[moments.n_joint_finite.ge(2)].copy()
    budgets = engine.budget_rows(usable)
    keys = ["budget", "analysis_layer", "scheme", "metric"]
    values = [c for c in usable if c.startswith(("mean_", "total_", "between_", "within_", "composition_", "member_residual_", "both_", "exact_team_"))]
    frames = [engine.derive_pooled(f) for f in engine.hierarchy(budgets, keys, values)]
    counts = budgets.groupby(keys, dropna=False).agg(
        panels=("panel_id", "nunique"),
        valid_team_pair_occurrences=("n_joint_finite", "sum"),
        panels_with_repeated_composition=("n_compositions_with_replicates", lambda s: int(s.gt(0).sum())),
        panels_with_positive_total_cov=("total_cov", lambda s: int(s.gt(1e-12).sum())),
        panels_with_negative_total_cov=("total_cov", lambda s: int(s.lt(-1e-12).sum())),
    ).reset_index()
    frames[-1] = frames[-1].merge(counts, on=keys, validate="one_to_one")
    return frames


def verify_nested_moments(moments):
    columns = ["n_joint_finite", "total_var_a", "total_var_b", "total_cov", "between_var_a", "between_var_b"]
    comparison = moments.pivot(index=["panel_id", "metric"], columns="scheme", values=columns)
    for column in columns[:4]:
        pd.testing.assert_series_equal(comparison[column][METHODS[0]], comparison[column][METHODS[1]], check_names=False)
    for column in columns[4:]:
        delta = comparison[column][METHODS[1]] - comparison[column][METHODS[0]]
        scale = comparison[column].abs().max(axis=1).clip(lower=1)
        assert (delta.dropna() >= -1e-10 * scale[delta.notna()]).all()


def run(out=OUT):
    inputs = [DESIGN / "PANELS.csv", DESIGN / "PANEL_TEAM_LINKS.csv.gz", ENDPOINTS, LABELS, ENGINE]
    original_bytes = {p: p.read_bytes() for p in inputs}
    engine = load_engine()
    panels = engine.annotate_budget(pd.read_csv(inputs[0]))
    for column in ["ordinary_comparable", "scope_comparable"]:
        panels[column] = as_bool(panels[column])
    links = pd.read_csv(inputs[1])
    labels = pd.read_csv(LABELS)
    annotated = annotate_compositions(panels, links, labels)
    endpoints = pd.read_csv(ENDPOINTS, low_memory=False)
    paired = join_endpoints(panels, annotated, endpoints, engine.METRICS)
    moments, support = summarize(panels, paired, engine)
    # K3 and K4 use the same teams and finite outcome mask, including failures.
    verify_nested_moments(moments)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    engine.write_csv(out / "TEAM_COMPOSITIONS.csv.gz", annotated)
    engine.write_csv(out / "PANEL_COMMON_SUPPORT.csv", support)
    engine.write_csv(out / "PANEL_DECOMPOSITION.csv.gz", moments)
    availability = endpoints.assign(finite_B8L2=np.isfinite(endpoints.B8L2)).groupby(
        ["complete_evaluable", "score_status", "geometry_status"], dropna=False
    ).agg(unique_endpoints=("team_key", "size"), finite_B8L2=("finite_B8L2", "sum")).reset_index()
    engine.write_csv(out / "ENDPOINT_AVAILABILITY.csv", availability)
    for name, frame in zip(["PAIR", "GROUP", "BUILDING", "SUMMARY"], aggregate(moments, engine)):
        engine.write_csv(out / ("DECOMPOSITION_" + name + ".csv"), frame)
    assert all(p.read_bytes() == content for p, content in original_bytes.items())
    checks = {
        "complete": True, "data_release": "v2.1", "methods": list(METHODS),
        "panel_selection_method": "V3_BEHAVIOR", "new_team_selection": 0,
        "new_classification_fit": 0, "new_fusion": 0, "new_scoring": 0,
        "panels": len(panels), "primary_panels": int(panels.is_primary_budget.sum()),
        "direct_pairs": int(panels.pair_key.nunique()), "buildings": int(panels.building.nunique()),
        "paired_team_rows": len(links), "source_unique_endpoints": len(endpoints),
        "common_known_team_rows": int(annotated.both_methods_all_known.sum()),
        "unknown_team_rows": int((~annotated.both_methods_all_known).sum()),
        "both_methods_equal_outcome_denominators": True,
        "same_total_moments_and_nested_variance_verified": True,
        "team_members_counts_pool_building_reference_verified": True,
        "full_team_composition_counts_verified": True, "source_bytes_unchanged": True,
        "outcome_missingness": "per metric, finite in both views; no zero imputation",
        "failure_metric": "1 - complete_evaluable: complete-output unevaluable, not necessarily native fusion failure",
        "time_support": "recorded_time_eligible and positive total seconds in both views",
        "label_support": "both K3 and K4 all team members known in the target-building-excluded fold",
        "input_files": [p.relative_to(ROOT).as_posix() for p in inputs],
        "scope": "conditional reaggregation on existing V3-selected finite panels, not OPPJOINT-selected strict ABC",
    }
    (out / "CHECKS.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return checks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    run(parser.parse_args().out)
