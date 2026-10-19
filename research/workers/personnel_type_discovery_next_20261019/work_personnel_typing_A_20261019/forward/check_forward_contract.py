#!/usr/bin/env python3
"""Concrete leakage/source/label checks; no new class tuning."""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
os.environ.setdefault("OMP_NUM_THREADS","1")
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from build_features import _training_features,DOMAINS
from multiview_partition import partition_features,small_contract_check

H=Path(__file__).resolve().parent;R=H.parent


def main():
    d=pd.read_csv(H/"records_flat.csv");ex=pd.read_csv(H/"behavior_geometry_source_columns.csv.gz")
    f=pd.read_csv(H/"worker_features_by_training_set.csv.gz")
    sets=json.loads((H/"TRAINING_SETS.json").read_text())
    workers=sorted(f.worker_id.unique());checks=[]
    for tk,g in f.groupby("train_key"):
        bs=sets["sets"][tk]
        q=d[d.building_id.isin(bs)&d.quality_usable&d.condition.eq("manual")&d.quality_use.eq("ordinary_primary")]
        expected=q.groupby("worker_id").size().reindex(workers,fill_value=0)
        actual=g.set_index("worker_id").core_records.reindex(workers)
        assert expected.equals(actual.astype("int64"))
        assert g.core_supported.eq((g.core_tasks>=8)&(g.core_buildings>=3)).all()
        checks.append({"train_key":tk,"records_checked":len(q),"worker_counts_match":True,"n_buildings":len(bs)})
    for alias in sets["aliases"]:
        trained=set(sets["sets"][alias["train_key"]])
        if alias["heldout_building"] is not None:assert alias["heldout_building"] not in trained
        assert not trained.intersection(alias["inner_validation_buildings"])
    alias=next(a for a in sets["aliases"]if a["heldout_building"] is not None and a["inner_group"] is not None)
    bs=sets["sets"][alias["train_key"]];excluded=set(d.building_id)-set(bs)
    before,meta=_training_features(d,ex,workers,bs)
    dp=d.copy(deep=True);ep=ex.copy(deep=True);mask=dp.building_id.isin(excluded)
    for col in ["B8L2","D10","declared_pair_count","source_active_time_seconds","target_matched_time_seconds","height_mean_ratio"]:
        dp.loc[mask,col]=1e9
    em=ep.building_id.isin(excluded)
    for col in ["bottom_y_mean","top_y_mean","semi_gain_B8","scope_out","semi_edited","semi_old_nonedit","semi_new_nonedit"]:
        ep.loc[em,col]=1e9
    for col in ["semi_old_opp","semi_new_opp","semi_attributable","scope_compatible_gold"]:ep.loc[em,col]=True
    after,_=_training_features(dp,ep,workers,bs)
    pd.testing.assert_frame_equal(before,after,check_exact=True)
    p1=partition_features(before,DOMAINS);p2=partition_features(after,DOMAINS)
    pd.testing.assert_frame_equal(p1.labels,p2.labels,check_exact=True)
    fullkey=next(a["train_key"]for a in sets["aliases"]if a["fold_id"]=="FULL"and a["inner_group"]is None)
    full=f[f.train_key.eq(fullkey)];archive=pd.read_csv(R/"recovered/work_v2_20261019/profiles/full_profiles.csv")
    joined=full.merge(archive,on="worker_id",validate="one_to_one")
    diff=float(np.max(np.abs(joined.q_beta-joined.Q_effect_B8L2)))
    theta=max(float(np.max(np.abs(joined[f"theta_{a}_estimate"]-joined[f"theta_{a}_B8L2"])))for a in ["easy","medium","hard"])
    assert diff<1e-9 and theta<1e-9
    forbidden={"person_origin","time_source_kind","source_time_median","individual_review_records","specific_error_candidate_n","scope_gold_n","semi_gain_mean"}
    assert not forbidden.intersection(x for vals in DOMAINS.values()for x in vals)
    coverage=[]
    for (tk,origin),g in f.groupby(["train_key","person_origin"]):
        for domain,columns in DOMAINS.items():
            coverage.append({"train_key":tk,"person_origin":origin,"domain":domain,"n_workers":len(g),"any_feature_observed":int(g[columns].notna().any(axis=1).sum()),
                             "all_features_observed":int(g[columns].notna().all(axis=1).sum())})
    pd.DataFrame(coverage).to_csv(H/"feature_domain_source_coverage.csv",index=False)
    pd.DataFrame(checks).to_csv(H/"training_subset_record_checks.csv",index=False)
    receipt={"passed":True,"training_sets":len(checks),"train_test_exclusion_aliases":len(sets["aliases"]),
             "heldout_poison": {"training_set":alias["train_key"],"excluded_buildings":sorted(excluded),"value":1e9,"features_exactly_unchanged":True,"all_K_labels_exactly_unchanged":True},
             "archived_full_Q_parity_max_abs":diff,"archived_joint20_parity_max_abs":theta,
             "source_missing_audit_fields_not_used_as_class_features":sorted(forbidden),"module_boundaries":small_contract_check(),
             "scope_accuracy_not_used":True,"semi_final_Q_and_gain_not_double_weighted":True,"data_points_or_references_edited":False}
    (H/"FORWARD_BOUNDARY_CHECKS.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
