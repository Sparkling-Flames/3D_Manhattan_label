#!/usr/bin/env python3
"""Apply the frozen model fitting protocol to new scalar candidates and ablations."""
from __future__ import annotations
import argparse
import importlib.util
from pathlib import Path
import numpy as np
from apply_exposure_and_audit import read,write,sha,exposure_barriers
from recheck_comparisons import csvout
from monotone_ordinal_probe import run_cv,fit,evaluate


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workspace',type=Path,default=Path(__file__).resolve().parents[2]);a=ap.parse_args();W=a.workspace.resolve()
    E=W/'structure_height_preference_20261012/evidence';O=E/'model_extensions';O.mkdir(parents=True,exist_ok=True)
    protocol=read(E/'model_addendum_after_initial_fits.json');sp=W/'structure_height_preference_20261012/height/results/initial15_before_log_addendum/candidate_scores_39.json'
    assert sha(sp)==protocol['source_scores_sha256']
    assert sha(W/'structure_height_preference_20261012/height/candidate_config.json')==protocol['candidate_config_sha256']
    scores={r['record_id']:r for r in read(sp)};old=read(W/'study_borderline/results/old24_evidence.json')
    eligible={r['record_id']:r for r in read(E/'results/numerical_evidence_39.json')}
    ex=read(W/'structure_height_preference_20261012/inputs/main_snapshot/research/quality_holdout_exposure_correction_20261011/exposure_registry.json')
    for r in old:
        assert not eligible[r['record_id']]['explicit_exposure_barriers']
        assert not exposure_barriers(r['record_id'],r['room_group'],r['held_out'],ex)
    spec=importlib.util.spec_from_file_location('height_candidates',W/'structure_height_preference_20261012/height/candidate_functions.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    rows=[scores[r['record_id']] for r in old];y=np.array([r['quality_ordinal_original'] for r in old])
    names=[c['name'] for c in read(W/'structure_height_preference_20261012/height/candidate_config.json')['candidates']]
    assert len(names)==15
    defs={n:['1 - '+n+'/100'] for n in names};mats={n:np.array([[1-r[n]/100] for r in rows]) for n in names}
    d=np.array([r['dir'] for r in rows]);dl=d*d/(d*d+25);il=1-np.array([r['iou_2d'] for r in rows])
    defs['D_only']=['direction'];mats['D_only']=dl[:,None]
    defs['geometry2']=['floor','direction'];mats['geometry2']=np.c_[il,dl]
    summary,folds,cases=run_cv(old,y,defs,mats,1.)
    csvout(O/'grouped_summary.csv',summary);write(O/'grouped_fits.json',folds);csvout(O/'grouped_predictions.csv',cases)
    keep=np.array([r['case_id']!='T20' for r in old]);ss=[r for r,k in zip(old,keep) if k]
    su,fu,cu=run_cv(ss,y[keep],defs,{k:X[keep] for k,X in mats.items()},1.)
    csvout(O/'without_T20_grouped_summary.csv',su);write(O/'without_T20_grouped_fits.json',fu);csvout(O/'without_T20_predictions.csv',cu)
    fs=[]
    for method,X in mats.items():fs.append(dict(method=method,features=defs[method],**fit(X,y,1.)))
    write(O/'full_fit_parameters.json',fs)
    import csv
    initial=list(csv.DictReader((E/'model_results/grouped_summary.csv').open(encoding='utf-8-sig')))
    initial_without=list(csv.DictReader((E/'model_results/without_T20_grouped_summary.csv').open(encoding='utf-8-sig')))
    csvout(O/'all_model_summaries.csv',initial+summary);csvout(O/'all_model_summaries_without_T20.csv',initial_without+su)
    manifest=dict(addendum_sha256=sha(E/'model_addendum_after_initial_fits.json'),scores_sha256=sha(sp),
        frozen_source_path=str(sp.relative_to(W)),methods=names+['D_only','geometry2'],grouped_fits=len(folds),without_T20_grouped_fits=len(fu),
        same_fixed_lambda=1.0,hyperparameter_searches=0,independent_validation=False,
        fitting_protocol='Identical proportional odds fitting to initial scalar and multi-input models; degrees of freedom explicitly reported.',
        exposed_holdout_or_pending_or_severe_or_unreviewed_fit_rows=0)
    write(O/'run_manifest.json',manifest)
    print(__import__('json').dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
