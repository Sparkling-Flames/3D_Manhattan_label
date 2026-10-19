#!/usr/bin/env python3
"""Freeze conditional composition requests using history labels/metadata only."""
import argparse
import itertools
import json
import math
from pathlib import Path
import pandas as pd

SELECTION = {
    "doorway": ["F_doorway_finalQ_K2", "F_doorway_finalQ_K3"],
    "semi_new": ["F_semi_new_finalQ_K2", "F_semi_new_nonedit_K2"],
    "semi_v1": ["F_semi_v1_finalQ_K2", "F_semi_old_edit_K2"],
}


def vectors(capacities, total):
    if len(capacities) == 1:
        if 0 <= total <= capacities[0]:
            yield [total]
        return
    for n in range(min(capacities[0], total) + 1):
        for rest in vectors(capacities[1:], total - n):
            yield [n] + rest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=Path("repo"))
    ap.add_argument("--split", type=Path, default=Path("analysis/composition/SPLIT.json"))
    ap.add_argument("--forward", type=Path, default=Path("analysis/forward/results"))
    ap.add_argument("--out", type=Path, default=Path("analysis/forward/condition_experiment_spec.json"))
    args = ap.parse_args()
    source = args.repo / "research/workers/personnel_composition_handoff_20261019"
    pools = pd.read_csv(source / "POOL_INVENTORY.csv")
    members = pd.read_csv(source / "POOL_MEMBERS.csv.gz")
    labels = pd.read_csv(args.forward / "worker_labels.csv.gz")
    manifest = json.loads((args.forward / "method_manifest.json").read_text())
    split = json.loads(args.split.read_text())
    stagemap = {b: stage for stage in ["discovery", "validation"] for b in split[stage + "_buildings"]}
    bypool = dict(tuple(members.groupby("pool_id")))
    rules, unsupported, summaries = [], [], []
    for domain, methods in SELECTION.items():
        allowed = pools[pools.layer.eq("doorway_manual" if domain == "doorway" else "ordinary_semi") & pools.building.isin(stagemap)]
        for mid in methods:
            labs = labels[(labels.method_id == mid) & labels.known].set_index("worker_id").class_id.to_dict()
            cls = sorted(set(labs.values()))
            for _, p in allowed.iterrows():
                mm = bypool[p.pool_id]
                if domain.startswith("semi_"):
                    mm = mm[mm.origin.eq(domain.split("_", 1)[1])]
                groups = {c: sorted(w for w in mm.worker_id if labs.get(w) == c) for c in cls}
                capacities = [len(groups[c]) for c in cls]
                if sum(c > 0 for c in capacities) < 2:
                    unsupported.append({"method_id": mid, "domain": domain, "stage": stagemap[p.building], "pool_id": p.pool_id, "available_classes": sum(c > 0 for c in capacities), "known_workers": sum(capacities), "reason": "fewer_than_two_supported_classes_in_target_pool"})
                    continue
                n_rules = []
                for n in [3, 4, 5, 7, 9]:
                    if n > sum(capacities):
                        continue
                    compositions = []
                    for count in vectors(capacities, n):
                        concrete = math.prod(math.comb(c, take) for c, take in zip(capacities, count))
                        compositions.append({"counts": count, "possible_distinct_teams": str(concrete), "sample_teams": min(4, concrete), "sample_exhaustive": concrete <= 4})
                    n_rules.append({"n": n, "composition_vectors_exhaustive": True, "compositions": compositions})
                rule = {"method_id": mid, "domain": domain, "stage": stagemap[p.building], "pool_id": p.pool_id, "image": p.image, "building": p.building, "difficulty": p.difficulty, "reference_id": p.reference_id, "class_order": cls, "class_members": groups, "available_class_counts": capacities, "known_workers": sum(capacities), "pool_qualified_workers_in_origin_domain": len(mm), "n_rules": n_rules}
                rules.append(rule)
                summaries.append({"method_id": mid, "domain": domain, "stage": stagemap[p.building], "pool_id": p.pool_id, "building": p.building, "known_workers": sum(capacities), "vectors": sum(len(v["compositions"]) for v in n_rules), "teams_requested": sum(c["sample_teams"] for v in n_rules for c in v["compositions"]), "pure_vectors": sum(sum(x > 0 for x in c["counts"]) == 1 for v in n_rules for c in v["compositions"])})
    summary = pd.DataFrame(summaries)
    summary.to_csv(args.out.with_name("condition_support_summary.csv"), index=False)
    selections = {}
    for domain, methods in SELECTION.items():
        selections[domain] = [{"method_id": m, "known_history_workers": manifest["methods"][m]["known_workers"], "history_class_sizes": manifest["methods"][m]["class_sizes"], "feature_columns": manifest["methods"][m]["features"], "selection_basis": "historical own-condition opportunity plus interpretable Q/evidence tendency; no condition-target fusion outcomes read"} for m in methods]
    spec = {"schema": "conditional_composition_experiment_v1", "seed": 2026101981, "status": "frozen_from_history_labels_and_target_membership_metadata_before_condition_fusion", "selections": selections, "sizes": [3, 4, 5, 7, 9], "concrete_team_replicates": 4, "sampling": "all feasible class-count vectors at each n; up to four distinct uniformly sampled concrete teams per vector with exact identities retained; if <=4 possibilities enumerate all; new members do not create new independent images", "scoring": "unchanged frozen pool reference/fusion/B8L2; D10 sensitivity; missing failures retained", "target_outcomes_read": False, "source_semantics": {"doorway": "own doorway-qualified final-Q histories, 4 tasks/3 buildings; compare coarse/finer ordinal rules", "semi_new": "new-source qualified final-Q versus reported-error-opportunity non-edit propensity; no per-record initial geometry => no invented net improvement", "semi_v1": "old-source qualified final-Q versus editing propensity; modifying is not confirmed repair, confirmed-error non-edit class lacks historical opportunities"}, "special_conditions": {"type_discovery": "not supported at 4 tasks/3 buildings in history", "allowed_descriptive_work": "full qualified pool fusion and selected uniform teams can be described separately, with actual member IDs and special reference; no unsupported personnel category claims"}, "unsupported_pool_candidates": unsupported, "rules": rules}
    args.out.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n")
    print(summary.groupby(["domain", "method_id", "stage"]).agg(pools=("pool_id", "nunique"), buildings=("building", "nunique"), vectors=("vectors", "sum"), teams=("teams_requested", "sum"), pure_vectors=("pure_vectors", "sum")).to_string())
    print(json.dumps({"rules": len(rules), "unsupported_pool_candidates": len(unsupported), "requested_teams": int(summary.teams_requested.sum()), "spec_bytes": args.out.stat().st_size}))


if __name__ == "__main__": main()
