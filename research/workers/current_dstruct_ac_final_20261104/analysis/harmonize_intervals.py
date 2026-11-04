"""Reuse the exact same intervals when image/building values are identical.

The first frozen automatic estimate supplies its bootstrap interval. An
assisted/original or assisted/expanded row with exactly the same image values
must inherit that interval; a new source label is not a new resampling study.
No point estimate, support, event, source metric or changed-support interval is
modified. Reverse directions have already been calculated algebraically.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ac_common import HERE, csv, read_csv, write_json, digest, sha
import json

BASE = ["analysis_cohort", "version", "scope", "condition", "n", "m", "class_pair"]
CI = ["cluster_bootstrap_low", "cluster_bootstrap_high", "building_equal_bootstrap_low", "building_equal_bootstrap_high"]


def harmonize(table_name, image_name, extra, metric_selector):
    table = read_csv(HERE / table_name)
    image = read_csv(HERE / image_name)
    keys = BASE + extra
    lookup = {key: g for key, g in image.groupby(keys, dropna=False, observed=True, sort=False)}
    order = table.assign(_version_order=table.version.map({"automatic": 0, "manual_order_assisted": 1}).fillna(2))
    if "support" in table:
        order["_support_order"] = table.support.map({"original_common": 0, "expanded_common": 1, "new_common_after_approved_order": 2}).fillna(3)
    else:
        order["_support_order"] = 0
    order = order.sort_values(["_version_order", "_support_order"], kind="stable")
    cache = {}
    reused, changed, max_before = 0, 0, 0.
    for idx, row in order.iterrows():
        if not all(c in table for c in CI) or not np.isfinite(pd.to_numeric(row.get(CI[0]), errors="coerce")):
            continue
        key = tuple(row[k] for k in keys)
        if key not in lookup:
            raise KeyError("Interval has no image evidence: " + str((table_name, key)))
        metric = metric_selector(row)
        z = lookup[key][["image", "building", metric]].dropna().sort_values(["image", "building"])
        sign = 1
        direction = str(row.get("direction", ""))
        if direction:
            a, c = direction.split("_to_")
            sign = 1 if a < c else -1
        signed = metric == "dQ" or metric.startswith("delta_") or metric.startswith("dT_")
        values = z[metric].to_numpy(float) * (sign if signed else 1)
        # Numeric rounding only creates candidate matches. The subsequent
        # unrounded allclose check is required before an interval is reused.
        signature = digest([metric, z.image.tolist(), z.building.tolist(), np.round(values, 10).tolist()])
        if signature in cache:
            old_values, old_ci = cache[signature]
            if len(values) != len(old_values) or not np.allclose(values, old_values, rtol=0, atol=1e-10):
                raise ValueError("Identical-support interval cache collision")
            old = table.loc[idx, CI].to_numpy(float)
            delta = float(np.nanmax(np.abs(old - old_ci)))
            reused += 1
            if delta > 1e-12:
                changed += 1
                max_before = max(max_before, delta)
            table.loc[idx, CI] = old_ci
        else:
            cache[signature] = (values, row[CI].to_numpy(float))
    csv(HERE / table_name, table)
    return dict(table=table_name, reused_identical_image_value_intervals=reused,
                intervals_with_previous_Monte_Carlo_only_differences=changed,
                maximum_removed_interval_only_difference=max_before, point_estimates_changed=0)


def harmonize_all():
    tasks = [
        ("SIX_DIRECTION_Q_BY_BUDGET.csv", "MAIN_IMAGE_EFFECTS.csv.gz", ["support"], lambda r: "dQ"),
        ("COMPONENT_SUMMARIES.csv.gz", "COMPONENT_IMAGE_EFFECTS.csv.gz", ["support"], lambda r: r["metric"]),
        ("CONDITION_STRATIFIED_Q.csv", "CONDITION_IMAGE_EFFECTS.csv.gz", ["stratum_type", "stratum"], lambda r: "dQ"),
        ("RECORDED_LABOR_AND_JOINT_Q.csv", "RECORDED_LABOR_IMAGE_EFFECTS.csv.gz", ["labor_support", "Q_labor_support"], lambda r: "dT_whole" if r["labor_support"] == "whole_team_single_source" else "dT_blocks"),
        ("GAP_WEIGHTING_SENSITIVITY.csv", "GAP_WEIGHTING_IMAGE_EFFECTS.csv.gz", ["weighting"], lambda r: "dQ"),
    ]
    receipt_path = HERE / "MAIN_SAME_SUPPORT_INTERVAL_CHECKS.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    main_already_verified = receipt.get("final_main_sha256") == sha(HERE / "SIX_DIRECTION_Q_BY_BUDGET.csv")
    results = []
    for task in tasks:
        if task[0] == "SIX_DIRECTION_Q_BY_BUDGET.csv" and main_already_verified:
            results.append(dict(table=task[0], status="already_verified_unchanged", sha256=receipt["final_main_sha256"]))
        else:
            result = harmonize(*task)
            results.append(result)
            if task[0] == "SIX_DIRECTION_Q_BY_BUDGET.csv":
                write_json(receipt_path, dict(status="passed", **result, final_main_sha256=sha(HERE / task[0])))
    from summarize_ac import capacity_completion
    if not main_already_verified:
        capacity_completion(read_csv(HERE / "SIX_DIRECTION_Q_BY_BUDGET.csv"))
    results.append(align_Q_component_to_main())
    write_json(HERE / "SAME_SUPPORT_INTERVAL_CHECKS.json", {"status": "passed", "point_estimates_changed": 0, "tables": results})
    return results


def align_Q_component_to_main():
    """Q as a component is the same estimand as main Q, including its CI."""
    keys = BASE + ["support", "direction"]
    main = read_csv(HERE / "SIX_DIRECTION_Q_BY_BUDGET.csv").set_index(keys, verify_integrity=True)
    comp = read_csv(HERE / "COMPONENT_SUMMARIES.csv.gz")
    qrows = comp.loc[comp.metric.eq("delta_B8L2")]
    mi = read_csv(HERE / "MAIN_IMAGE_EFFECTS.csv.gz")
    ci = read_csv(HERE / "COMPONENT_IMAGE_EFFECTS.csv.gz")
    image_keys = BASE + ["support", "image", "building"]
    v = mi.set_index(image_keys)["dQ"].to_frame("main_Q")
    v = v.join(ci.set_index(image_keys)["delta_B8L2"].rename("component_Q"), how="outer")
    if not v.main_Q.isna().equals(v.component_Q.isna()) or not np.allclose(v.main_Q.dropna(), v.component_Q.dropna(), rtol=0, atol=1e-10):
        raise ValueError("Main Q and component Q have different per-image support or values")
    changed, max_delta = 0, 0.
    for idx, row in qrows.iterrows():
        r = main.loc[tuple(row[k] for k in keys)]
        for name in ["images", "buildings", "image_equal_mean", "building_equal_mean"]:
            if not np.isclose(row[name], r[name], rtol=0, atol=1e-10, equal_nan=True):
                raise ValueError("Main Q/component Q estimand mismatch: " + str(name))
        previous = comp.loc[idx, CI].to_numpy(float)
        fixed = r[CI].to_numpy(float)
        delta = float(np.nanmax(np.abs(previous - fixed))) if np.isfinite(previous - fixed).any() else 0.
        if delta > 1e-12:
            changed += 1
            max_delta = max(max_delta, delta)
        comp.loc[idx, CI] = fixed
    csv(HERE / "COMPONENT_SUMMARIES.csv.gz", comp)
    result = dict(table="COMPONENT_SUMMARIES.csv.gz", metric="delta_B8L2", identity="same Q as SIX_DIRECTION_Q_BY_BUDGET.csv",
                  aligned_rows=len(qrows), intervals_corrected=changed, maximum_removed_interval_only_difference=max_delta,
                  point_estimates_changed=0, per_image_support_and_value_check="passed")
    write_json(HERE / "Q_COMPONENT_INTERVAL_IDENTITY_CHECKS.json", dict(status="passed", **result))
    return result


if __name__ == "__main__":
    print(harmonize_all())
