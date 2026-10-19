#!/usr/bin/env python3
"""Small classification evidence tables; never inspect fusion outcomes."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--d10", type=Path, required=True)
    args = ap.parse_args()
    a = pd.read_csv(args.out / "worker_labels.csv.gz")
    b = pd.read_csv(args.d10 / "worker_labels.csv.gz")
    paired = a.merge(b, on=["method_id", "domain", "worker_id"], suffixes=("_B8", "_D10"), validate="one_to_one")
    rows = []
    for (mid, domain), g in paired.groupby(["method_id", "domain"]):
        common = g[g.known_B8 & g.known_D10]
        y0, y1 = common.class_id_B8.to_numpy(), common.class_id_D10.to_numpy()
        upper = np.triu_indices(len(common), 1)
        p0 = (y0[:, None] == y0[None, :])[upper]
        p1 = (y1[:, None] == y1[None, :])[upper]
        rows.append({"method_id": mid, "domain": domain, "known_B8": int(g.known_B8.sum()), "known_D10": int(g.known_D10.sum()), "common_workers": len(common), "worker_pairs": len(p0), "changed_coassignment_pairs": int((p0 != p1).sum()), "changed_coassignment_fraction": float((p0 != p1).mean()) if len(p0) else np.nan, "adjusted_rand": adjusted_rand_score(y0, y1) if len(common) >= 2 else np.nan})
    pd.DataFrame(rows).to_csv(args.out / "D10_class_sensitivity.csv", index=False)
    f = pd.read_csv(args.out / "features_train.csv.gz")
    groups = {"ordinary_manual_core": ("core_supported", "core_tasks", "core_buildings"), "easy": ("easy_supported", "easy_tasks", "easy_buildings"), "medium": ("medium_supported", "medium_tasks", "medium_buildings"), "hard": ("hard_supported", "hard_tasks", "hard_buildings"), "time": ("t_supported", "t_images", "t_buildings"), "old_confirmed_error": ("semi_old_error_nonedit_supported", "semi_old_error_nonedit_records", "semi_old_error_nonedit_buildings"), "new_reported_error": ("semi_new_error_nonedit_supported", "semi_new_error_nonedit_records", "semi_new_error_nonedit_buildings"), "old_edit": ("semi_old_edit_supported", "semi_old_edit_records", "semi_old_edit_buildings"), "new_edit": ("semi_new_edit_supported", "semi_new_edit_records", "semi_new_edit_buildings"), "scope_propensity": ("scope_supported", "scope_tasks", "scope_buildings")}
    for cond in ["doorway", "semi_v1", "semi_new", "special_manual", "special_semi"]:
        groups[cond] = (cond + "_supported", cond + "_tasks", cond + "_buildings")
    coverage = []
    for name, (flag, n, buildings) in groups.items():
        for source, g in f.groupby("person_origin"):
            h = g[g[flag]]
            coverage.append({"domain": name, "origin": source, "personnel": len(g), "supported": int(g[flag].sum()), "unsupported": int((~g[flag]).sum()), "all_person_opportunities": g[n].sum(), "supported_min_opportunities": h[n].min(), "supported_median_opportunities": h[n].median(), "supported_min_buildings": h[buildings].min(), "supported_median_buildings": h[buildings].median()})
    pd.DataFrame(coverage).to_csv(args.out / "history_feature_support.csv", index=False)
    manifest = json.loads((args.out / "method_manifest.json").read_text())
    profiles = []
    for mid, method in manifest["methods"].items():
        for cl, data in method["classes"].items():
            profiles.append({"method_id": mid, "domain": method["domain"], "class_id": cl, "name_zh": data["name_zh"], "n_workers": data["n"], "n_new": data["origin_counts"].get("new", 0), "n_v1": data["origin_counts"].get("v1", 0), "worker_ids": ";".join(data["members"]), **data["feature_means"]})
    pd.DataFrame(profiles).to_csv(args.out / "class_profiles.csv.gz", index=False)
    print(json.dumps({"D10_rows": len(rows), "coverage_rows": len(coverage), "class_profile_rows": len(profiles)}))


if __name__ == "__main__":
    main()
