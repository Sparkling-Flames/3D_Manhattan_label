#!/usr/bin/env python3
"""Independent aggregation checks and history-building deletion sensitivity.

This audits frozen candidates. No candidate is selected or refitted using a
discovery/validation fusion outcome. Building deletion measures label fragility;
its ten overlapping fits are not ten independent validation datasets.
"""
from __future__ import annotations
import argparse
import json
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score
import discover_reverse_composition as d


def bundle(rec, workers):
    pairs = d.pair_observations(rec)
    matrices = {p: d.relation_matrices(pairs, workers, p)[0] for p in (0., 2.)}
    supports = {dom: d.support(rec, workers, dom) for dom in ("global",) + d.DIFFICULTIES}
    roles = {dom: d.role_features(rec, workers, dom) for dom in ("global",) + d.DIFFICULTIES}
    return pairs, matrices, supports, roles


def all_labels(workers, matrices, supports, roles):
    result = {}
    for spec in d.specifications():
        for dom in d.DIFFICULTIES if spec["conditional"] else ["global"]:
            labels, _ = d.fit_one(spec, workers, supports, roles, matrices, dom)
            result[(spec["method_id"], dom)] = labels
    return result


def independent_pair_check(rec, relations):
    errors = []
    selected = relations[relations.supported].sort_values(["worker_a", "worker_b"]).iloc[::113].head(16)
    for row in selected.itertuples():
        common = rec[rec.worker_id.eq(row.worker_a)][["pool_id", "building", "cluster_id9"]].merge(
            rec[rec.worker_id.eq(row.worker_b)][["pool_id", "cluster_id9"]], on="pool_id", suffixes=("_a", "_b"))
        matches = {}
        for x in common.itertuples():
            matches.setdefault(x.building, []).append(float(x.cluster_id9_a == x.cluster_id9_b))
        manual = sum(sum(v) / len(v) for v in matches.values()) / len(matches)
        errors.append(abs(manual - row.same9_observed))
        assert len(common) == row.n_images and len(matches) == row.n_buildings
    return dict(pairs=len(errors), max_absolute_error=max(errors), support_counts_match=True)


def pollution_check(args, history, original_rec, base_labels):
    raw = pd.read_csv(args.records, usecols=d.RECORD_FIELDS)
    target = ~raw.building_id.isin(history)
    raw.loc[target, "pair_count"] = 9999
    raw.loc[target, "mean_height"] = 9999.
    raw.loc[target, "minimum_bottom_depression_deg"] = -9999.
    assignments = pd.read_csv(args.assignments, usecols=d.ASSIGNMENT_FIELDS)
    tamper = assignments.pool_id.isin(raw.loc[target, "pool_id"])
    assignments.loc[tamper, "cluster_id"] = "corrupted_target_cluster"
    assignments.loc[tamper, "cluster_size"] = 9999
    assignments.loc[tamper, "cluster_diameter_deg"] = 9999.
    with tempfile.TemporaryDirectory(prefix="reverse_history_audit_", dir="/tmp") as tmp:
        tmp = Path(tmp)
        rp, ap = tmp / "records.csv.gz", tmp / "assignments.csv.gz"
        raw.to_csv(rp, index=False)
        assignments.to_csv(ap, index=False)
        modified, _, workers, _ = d.load_inputs(rp, ap, history)
        pd.testing.assert_frame_equal(original_rec, modified)
        _, matrices, supports, roles = bundle(modified, workers)
        changed = all_labels(workers, matrices, supports, roles)
    differences = sum(base_labels[key] != value for key, value in changed.items())
    assert differences == 0
    return dict(target_records_mutated=int(target.sum()), target_partition_rows_mutated=int(tamper.sum()),
                fitted_method_domains_checked=len(base_labels), personnel_partitions_changed=differences,
                original_input_files_unchanged=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", type=Path, required=True)
    ap.add_argument("--assignments", type=Path, required=True)
    ap.add_argument("--split", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--history-deletion", action="store_true")
    args = ap.parse_args()
    split = json.loads(args.split.read_text())
    history = split["history_buildings"]
    rec, _, workers, _ = d.load_inputs(args.records, args.assignments, history)
    pairs, matrices, supports, roles = bundle(rec, workers)
    fitted = all_labels(workers, matrices, supports, roles)
    saved = pd.read_csv(args.output / "worker_labels.csv.gz")
    saved_maps = {(mid, dom): g[g.known].set_index("worker_id").class_id.to_dict()
                  for (mid, dom), g in saved.groupby(["method_id", "domain"])}
    assert fitted == saved_maps
    _, rel = d.relation_matrices(pairs, workers, 2.)
    check = independent_pair_check(rec, rel)
    pollution = pollution_check(args, history, rec, fitted)
    rows = []
    if args.history_deletion:
        for removed in history:
            reduced = rec[rec.building.ne(removed)].copy()
            _, ma, su, ro = bundle(reduced, workers)
            fits = all_labels(workers, ma, su, ro)
            for (mid, dom), new in fits.items():
                base = fitted[(mid, dom)]
                common = sorted(set(base) & set(new))
                x, y = [base[w] for w in common], [new[w] for w in common]
                changed = sum((x[i] == x[j]) != (y[i] == y[j])
                              for i in range(len(common)) for j in range(i + 1, len(common)))
                pairs_n = len(common) * (len(common) - 1) // 2
                rows.append(dict(method_id=mid, domain=dom, removed_history_building=removed,
                                 original_known_n=len(base), reduced_known_n=len(new), common_workers=len(common),
                                 ari=adjusted_rand_score(x, y) if len(common) > 1 else np.nan,
                                 changed_coassigned_pairs=changed, common_worker_pairs=pairs_n,
                                 coassignment_disagreement=changed / pairs_n if pairs_n else np.nan))
            print(json.dumps(dict(deleted_building=removed, fits=len(fits))), flush=True)
        r = pd.DataFrame(rows)
        r.to_csv(args.output / "history_deletion_stability.csv", index=False)
        r.groupby(["method_id", "domain"]).agg(
            refits=("ari", "size"), ari_mean=("ari", "mean"), ari_min=("ari", "min"),
            coassignment_disagreement_mean=("coassignment_disagreement", "mean"),
            coassignment_disagreement_max=("coassignment_disagreement", "max"),
            reduced_known_min=("reduced_known_n", "min"), common_workers_min=("common_workers", "min")
        ).reset_index().to_csv(args.output / "history_stability_summary.csv", index=False)
    prior = []
    for algorithm in ("average", "complete"):
        for k in d.K_VALUES:
            a = fitted[(f"R_geo9_{algorithm}_p0_K{k}", "global")]
            b = fitted[(f"R_geo9_{algorithm}_p2_K{k}", "global")]
            common = sorted(set(a) & set(b))
            prior.append(dict(algorithm=algorithm, k=k, common_workers=len(common),
                              ari=adjusted_rand_score([a[w] for w in common], [b[w] for w in common])))
    pd.DataFrame(prior).to_csv(args.output / "prior_sensitivity.csv", index=False)
    eligible = set(supports["global"].query("supported").index)
    er = rel[rel.worker_a.isin(eligible) & rel.worker_b.isin(eligible)]
    d.write_json(args.output / "AUDIT_RECEIPT.json", dict(
        exact_label_replay_method_domains=len(fitted), exact_replay_passed=True,
        independent_pair_aggregation=check, target_pollution=pollution,
        eligible_workers=len(eligible), eligible_pairs=len(er), observed_eligible_pairs=int(er.observed.sum()),
        supported_eligible_pairs=int(er.supported.sum()),
        unsigned_missing_prior_imputations_used_for_eligible_pairs=int((~er.observed).sum()),
        history_building_deletion_rows=len(rows),
        sensitivity_interpretation="Ten overlapping history refits measure partition fragility, not independent outcome replication.",
        code_sha256=d.sha(Path(__file__)), classification_code_sha256=d.sha(Path(d.__file__))))


if __name__ == "__main__":
    main()
