#!/usr/bin/env python3
"""Recheck scalar evidence on the explicit new eligible ID set.

The reused ordinal-cutpoint evaluator gives every scalar the same two-cutpoint
budget and preserves every training-optimal threshold interval. Nothing here
uses an unreviewed screen record as a negative or refits a quality formula.
"""
from __future__ import annotations
import argparse
import csv
import importlib.util
import itertools
import json
from pathlib import Path
import sys
import numpy as np

from apply_exposure_and_audit import read, sha, write, exposure_barriers


def csvout(path, rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open('w', encoding='utf-8-sig', newline='') as f:
        writer=csv.DictWriter(f, fieldnames=keys); writer.writeheader()
        for r in rows:
            writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})


def load_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path); mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod); return mod


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--workspace',type=Path,default=Path(__file__).resolve().parents[2])
    ap.add_argument('--scores',type=Path)
    ap.add_argument('--methods',nargs='+')
    ap.add_argument('--out',type=Path)
    a=ap.parse_args();W=a.workspace.resolve()
    score_path=a.scores or W/'top_structure_20261012/analysis/results/candidate_scores_39.json'
    O=a.out or W/'structure_height_preference_20261012/evidence/prior_candidate_recheck';O.mkdir(parents=True,exist_ok=True)
    ev=W/'structure_height_preference_20261012/evidence/results'
    eligible=read(ev/'numerical_evidence_39.json'); byid={r['record_id']:r for r in eligible}
    ex=read(W/'structure_height_preference_20261012/inputs/main_snapshot/research/quality_holdout_exposure_correction_20261011/exposure_registry.json')
    for r in eligible:
        assert not r['explicit_exposure_barriers']
        assert not exposure_barriers(r['record_id'],r['room_group'],False,ex)
    old=read(W/'study_borderline/results/old24_evidence.json')
    screen=read(W/'study_borderline/results/screen_evidence_115.json')
    allowed=set(read(ev/'allowed_screen_numerical_ids.json'))
    source=read(score_path); rows={r['record_id']:r for r in source}
    assert len(source)==len(rows)==39 and set(rows)==set(byid), 'Require the audited 39 IDs, no hidden eligibility filtering.'
    prior=load_module(W/'top_structure_20261012/analysis/candidate_functions.py','prior_candidates')
    methods=a.methods or prior.PRIMARY_METHODS+prior.DIAGNOSTIC_METHODS
    scores={rid:{m:float(row[m]) for m in methods} for rid,row in rows.items()}
    assert np.isfinite([v for r in scores.values() for v in r.values()]).all()
    compare=load_module(W/'study_borderline/scripts/compare_candidates.py','old_comparison')
    severe=[r for r in screen if r['record_id'] in allowed and r['original_judgment']=='severe']
    pending=[r for r in screen if r['record_id'] in allowed and r['original_judgment']=='borderline']
    assert len(old)==24 and len(severe)==9 and len(pending)==6
    grades={r['record_id']:r['quality_ordinal_original'] for r in old}
    allpairs=[]; summaries=[]
    for method in methods:
        pairs=compare.pair_counts(old,scores,method,grades)
        allpairs+=pairs
        row=dict(method=method,records=24,pairs=len(pairs),inversions=sum(x['inversion'] for x in pairs),ties=sum(x['tie'] for x in pairs))
        for key in ['image_code','room_group','building_id','worker_id']:
            own=[x for x in pairs if byid[x['better_record_id']][key]==byid[x['worse_record_id']][key]]
            row['same_'+key+'_pairs']=len(own);row['same_'+key+'_inversions']=sum(x['inversion'] for x in own)
        summaries.append(row)
    csvout(O/'old24_rank_summary.csv',summaries);csvout(O/'old24_pairs.csv',allpairs)
    cal,folds,preds=compare.grouped_calibration(old,scores,methods)
    write(O/'same_budget_two_cutpoint_summary.json',cal);write(O/'same_budget_two_cutpoint_folds.json',folds)
    csvout(O/'same_budget_predictions.csv',preds)
    bridge,bpairs=compare.severe_bridge(old,severe,scores,methods)
    csvout(O/'cross_protocol_bridge_summary.csv',bridge);csvout(O/'cross_protocol_bridge_pairs.csv',bpairs)
    bs,scenarios,decisions=compare.borderline_scenarios(severe,pending,scores,methods)
    write(O/'pending_scenario_summary.json',bs);csvout(O/'pending_scenarios.csv',scenarios)
    csvout(O/'pending_decision_influence.csv',decisions)

    labels=np.array([grades[r['record_id']] for r in old]);q=np.array([[scores[r['record_id']][m] for r in old] for m in methods])
    ij=np.array(list(itertools.combinations(range(len(old)),2)));ia,ib=ij.T
    qdelta=q[:,ia]-q[:,ib];qsign=np.where(np.abs(qdelta)<=compare.EPS,0,np.sign(qdelta))
    def inv(y,keep=None):
        sign=np.sign(y[ib]-y[ia]);mask=sign!=0
        if keep is not None:mask&=keep[ia]&keep[ib]
        return ((qsign[:,mask]*sign[mask])<0).sum(axis=1),int(mask.sum())
    iv,den=inv(labels);assert den==164
    assert all(int(v)==r['inversions'] for v,r in zip(iv,summaries)), 'Independent matrix pair-count implementation mismatch.'
    options={i:[v for v in (int(labels[i])-1,int(labels[i])+1) if 0<=v<=3] for i in range(24)}
    adjacency=[]
    for n in [1,2]:
        for inds in itertools.combinations(range(24),n):
            for vals in itertools.product(*(options[i] for i in inds)):
                y=labels.copy();y[list(inds)]=vals;v,d=inv(y)
                adjacency.append(dict(changed_count=n,changes=[dict(case_id=old[i]['case_id'],received=int(labels[i]),scenario=int(g)) for i,g in zip(inds,vals)],pairs=d,**{m:int(z) for m,z in zip(methods,v)}))
    csvout(O/'all24_adjacent_scenarios.csv',adjacency)
    sensitivity=[]
    for baseline in ['Q_v11','Q_official_iou3d','Q_floor_iou','Q_no_topS']:
        if baseline not in methods:continue
        for method in methods:
            if method==baseline:continue
            for n in [1,2]:
                rr=[r for r in adjacency if r['changed_count']==n];diff=[r[method]-r[baseline] for r in rr]
                sensitivity.append(dict(method=method,baseline=baseline,changed_count=n,scenarios=len(rr),difference_min=min(diff),difference_max=max(diff),scenario_frequency_is_probability=False))
    csvout(O/'adjacent_sensitivity_summary.csv',sensitivity)
    omissions=[]
    for key in ['case_id','image_code','room_group','building_id']:
        for unit in sorted({r[key] for r in old}):
            keep=np.array([r[key]!=unit for r in old]);v,d=inv(labels,keep)
            omissions.append(dict(omitted_unit=key,omitted_id=unit,remaining_records=int(keep.sum()),pairs=d,**{m:int(z) for m,z in zip(methods,v)}))
    csvout(O/'case_image_group_omissions.csv',omissions)

    # Different-version sanity check: the prior historical 39 metric values
    # must reproduce every old scalar, but new candidate columns are allowed.
    parity=[]
    for r in source:
        pred=prior.score(r)
        for m in methods:
            if m in pred and pred[m] is not None:
                parity.append(abs(float(r[m])-pred[m]))
    manifest=dict(scores_path=str(score_path.relative_to(W)) if score_path.is_relative_to(W) else str(score_path),scores_sha256=sha(score_path),
        exposure_registry_sha256=sha(W/'structure_height_preference_20261012/inputs/main_snapshot/research/quality_holdout_exposure_correction_20261011/exposure_registry.json'),
        eligible39_sha256=sha(ev/'numerical_evidence_39.json'),allowed15_sha256=sha(ev/'allowed_screen_numerical_ids.json'),
        old_scalar_formula_parity_checks=len(parity),old_scalar_formula_max_abs_error=max(parity,default=None),
        old24=24,images=18,buildings=11,cross_grade_pairs=164,same_image_pairs=2,
        severe=9,pending_numeric=6,unreviewed_used_as_negatives=0,original_holdout_or_exposed_groups_used=0,
        methods=methods,one_adjacent_scenarios=sum(r['changed_count']==1 for r in adjacency),two_adjacent_scenarios=sum(r['changed_count']==2 for r in adjacency),
        parameter_fitting_done=False,independent_validation=False,cutpoint_calibration_budget_per_scalar=2,
        caveats=['Pairs share records/images/groups and are not independent samples.','Adjacent labels apply to all24, not only commented cases; grade3 in sensitivity is hypothetical and not fitted.','Pending 2/3 scenarios do not turn into labels or probabilities.','Cross-protocol severe comparisons are compatibility checks, not FPR, prevalence or accuracy.'])
    write(O/'run_manifest.json',manifest)
    print(json.dumps(dict(rank=summaries,manifest=manifest),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
