#!/usr/bin/env python3
"""Fixed, small nonnegative proportional-odds development experiment.

Model probabilities are model outputs, never per-case human confidence. This
does not infer a severe fourth grade, worker skill or causal noise components.
"""
from __future__ import annotations
import argparse
import importlib.util
import itertools
import math
from pathlib import Path
import numpy as np
from scipy.optimize import minimize, check_grad
from scipy.special import expit

from apply_exposure_and_audit import read, write, sha, exposure_barriers
from recheck_comparisons import csvout


def probabilities(params, X):
    beta=params[2:]; thresholds=np.array([params[0],params[0]+params[1]])
    cdf=expit(thresholds[None,:]-X@beta[:,None])
    return np.c_[cdf[:,0],cdf[:,1]-cdf[:,0],1-cdf[:,1]],cdf


def objective(params, X, y, lam):
    probs,cdf=probabilities(params,X); n=len(y)
    py=np.maximum(probs[np.arange(n),y],1e-14)
    f=cdf*(1-cdf); f0,f1=f.T
    deta=np.choose(y,[-f0,f0-f1,f1])
    dt0=np.where(y==0,f0,np.where(y==1,-f0,0.))
    dt1=np.where(y==1,f1,np.where(y==2,-f1,0.))
    le=-deta/py;lt0=-dt0/py;lt1=-dt1/py
    beta=params[2:]
    value=-np.log(py).sum()+.5*lam*float(beta@beta)
    grad=np.r_[np.sum(lt0+lt1),np.sum(lt1),X.T@le+lam*beta]
    return float(value),grad


def fit(X,y,lam=1.):
    n,p=X.shape
    freq=(np.bincount(y,minlength=3)+.5)/(n+1.5)
    cum=np.cumsum(freq)[:2]
    theta=np.log(cum/(1-cum))
    x0=np.r_[theta[0],theta[1]-theta[0],np.full(p,.1)]
    opt=minimize(objective,x0,args=(X,y,lam),method='L-BFGS-B',jac=True,
        bounds=[(-20.,20.),(1e-4,40.)]+[(0.,None)]*p,
        options=dict(ftol=1e-12,gtol=1e-8,maxiter=1500,maxls=40))
    assert opt.success,(opt.message,opt.fun)
    pclass,cdf=probabilities(opt.x,X)
    assert np.isfinite(pclass).all() and np.min(pclass)>=-1e-13
    assert np.max(abs(pclass.sum(axis=1)-1))<1e-12
    return dict(params=opt.x.tolist(),coefficients=opt.x[2:].tolist(),thresholds=[float(opt.x[0]),float(opt.x[0]+opt.x[1])],
                optimizer_success=bool(opt.success),iterations=int(opt.nit),objective=float(opt.fun),
                at_zero_boundary=[bool(v<1e-7) for v in opt.x[2:]],
                training_nll=float(-np.log(np.maximum(pclass[np.arange(n),y],1e-14)).sum()))


def evaluate(fitted,X,y):
    p,cdf=probabilities(np.asarray(fitted['params']),X)
    med=(cdf<.5).sum(axis=1)
    return dict(p=p,median=med,expected=2-cdf.sum(axis=1),
                nll=-np.log(np.maximum(p[np.arange(len(y)),y],1e-14)),steps=np.abs(med-y))


def build_models(rows,methods):
    definitions={}; matrices={}
    for m in methods:
        definitions[m]=['1 - '+m+'/100']
        matrices[m]=np.array([[1-r[m]/100] for r in rows],float)
    D=np.array([r['dir'] for r in rows]);hg=np.array([r['Hmean'] for r in rows]);hl=np.array([r['Hcenter'] for r in rows]);st=np.array([r['S_top_deg'] for r in rows])
    X=np.column_stack([1-np.array([r['iou_2d'] for r in rows]),D*D/(D*D+25),hg*hg/(hg*hg+.25),hl*hl/(hl*hl+.0625),st*st/(st*st+32)])
    names=['floor','direction','global_height','centered_height','top_boundary']
    for m,p in [('geom4',4),('geom5_top',5)]:
        definitions[m]=names[:p];matrices[m]=X[:,:p]
    return definitions,matrices


def run_cv(records,ys,definitions,matrices,lam):
    groups=np.array([r['building_id'] for r in records]); folds=[];cases=[];summary=[]
    for method,X in matrices.items():
        for group in sorted(set(groups)):
            train=groups!=group;test=~train
            f=fit(X[train],ys[train],lam);ev=evaluate(f,X[test],ys[test])
            folds.append(dict(method=method,held_development_building=group,
                training_record_ids=[r['record_id'] for r,keep in zip(records,train) if keep],
                evaluation_record_ids=[r['record_id'] for r,keep in zip(records,test) if keep],
                features=definitions[method],**f,
                held_nll=float(ev['nll'].sum()),held_grade_step_loss=int(ev['steps'].sum())))
            ix=np.flatnonzero(test)
            for i,j in enumerate(ix):
                cases.append(dict(method=method,case_id=records[j]['case_id'],record_id=records[j]['record_id'],building_id=group,
                    received_grade=int(ys[j]),model_median_grade=int(ev['median'][i]),model_expected_grade=float(ev['expected'][i]),
                    model_class_probabilities_not_human_confidence=ev['p'][i].tolist(),
                    grade_step_loss=int(ev['steps'][i]),negative_log_likelihood=float(ev['nll'][i]),
                    independent_validation=False))
        ss=[r for r in cases if r['method']==method];ff=[r for r in folds if r['method']==method]
        coeff=np.array([r['coefficients'] for r in ff])
        summary.append(dict(method=method,n=len(ss),development_buildings=len(ff),features=definitions[method],
            fitted_parameters=matrices[method].shape[1]+2,
            total_nll=sum(r['negative_log_likelihood'] for r in ss),mean_nll=np.mean([r['negative_log_likelihood'] for r in ss]),
            grade_step_loss=sum(r['grade_step_loss'] for r in ss),
            coefficient_fold_min=coeff.min(axis=0).tolist(),coefficient_fold_max=coeff.max(axis=0).tolist(),
            coefficient_zero_folds=(coeff<1e-7).sum(axis=0).tolist()))
    return summary,folds,cases


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workspace',type=Path,default=Path(__file__).resolve().parents[2]);ap.add_argument('--out',type=Path)
    a=ap.parse_args();W=a.workspace.resolve();O=a.out or W/'structure_height_preference_20261012/evidence/model_results';O.mkdir(parents=True,exist_ok=True)
    ep=W/'structure_height_preference_20261012/evidence/model_protocol_before_results.json';protocol=read(ep)
    assert protocol['fixed_lambda']==1 and protocol['hyperparameter_search_budget']==0
    sp=W/'top_structure_20261012/analysis/results/candidate_scores_39.json'
    assert sha(sp)==protocol['source_scores_sha256']
    source={r['record_id']:r for r in read(sp)};old=read(W/'study_borderline/results/old24_evidence.json')
    ex=read(W/'structure_height_preference_20261012/inputs/main_snapshot/research/quality_holdout_exposure_correction_20261011/exposure_registry.json')
    eligible={r['record_id']:r for r in read(W/'structure_height_preference_20261012/evidence/results/numerical_evidence_39.json')}
    for r in old:
        assert not r['held_out'] and not eligible[r['record_id']]['explicit_exposure_barriers']
        assert not exposure_barriers(r['record_id'],r['room_group'],r['held_out'],ex)
    spec=importlib.util.spec_from_file_location('old_candidates',W/'top_structure_20261012/analysis/candidate_functions.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    methods=mod.PRIMARY_METHODS+mod.DIAGNOSTIC_METHODS
    rows=[source[r['record_id']] for r in old];y=np.array([r['quality_ordinal_original'] for r in old])
    defs,mats=build_models(rows,methods)
    # One independent central-finite-difference check of the analytic gradient;
    # controlled random numbers do not represent a human error distribution.
    rng=np.random.default_rng(18427);Xcheck=rng.uniform(0,1,(12,5));ycheck=np.tile([0,1,2],4)
    par=np.r_[-.7,1.2,.2,.8,.4,.6,.3]
    err=check_grad(lambda z:objective(z,Xcheck,ycheck,1)[0],lambda z:objective(z,Xcheck,ycheck,1)[1],par)
    assert err<1e-5,err
    summary,folds,cases=run_cv(old,y,defs,mats,1.)
    csvout(O/'grouped_summary.csv',summary);write(O/'grouped_fits.json',folds);csvout(O/'grouped_case_predictions.csv',cases)
    fits=[];fullpred=[]
    for method,X in mats.items():
        f=fit(X,y,1.);ev=evaluate(f,X,y)
        fits.append(dict(method=method,features=defs[method],**f))
        for i,r in enumerate(old):
            fullpred.append(dict(method=method,case_id=r['case_id'],record_id=r['record_id'],received_grade=int(y[i]),
                latent_severity=float(X[i]@np.array(f['coefficients'])),expected_grade=float(ev['expected'][i]),
                median_grade=int(ev['median'][i]),resubstitution=True))
    write(O/'full_fit_parameters.json',fits);csvout(O/'full_fit_predictions.csv',fullpred)
    # Exact same fixed model families after removing the explicitly discussed
    # high-influence case, not a new inclusion policy or parameter search.
    keep=np.array([r['case_id']!='T20' for r in old]);sub=[r for r,k in zip(old,keep) if k]
    sm={m:X[keep] for m,X in mats.items()}
    so,fo,co=run_cv(sub,y[keep],defs,sm,1.)
    csvout(O/'without_T20_grouped_summary.csv',so);write(O/'without_T20_grouped_fits.json',fo);csvout(O/'without_T20_case_predictions.csv',co)
    # Full-fit sensitivity only: every existing label can move to its neighbor
    # within this three-category model. This is not a new independent validation.
    perturbed=[]
    for i,r in enumerate(old):
        for alt in [int(y[i])-1,int(y[i])+1]:
            if not 0<=alt<=2:continue
            yy=y.copy();yy[i]=alt
            for method in ['geom4','geom5_top']:
                f=fit(mats[method],yy,1.)
                perturbed.append(dict(changed_case_id=r['case_id'],received_grade=int(y[i]),scenario_grade=alt,
                    method=method,features=defs[method],**f,scenario_is_probability=False))
    write(O/'all24_neighbor_label_full_fit_sensitivity.json',perturbed)
    sens=[]
    for m in ['geom4','geom5_top']:
        arr=np.array([r['coefficients'] for r in perturbed if r['method']==m])
        sens.append(dict(method=m,scenarios=len(arr),features=defs[m],coefficient_min=arr.min(axis=0).tolist(),
            coefficient_max=arr.max(axis=0).tolist(),coefficient_zero_scenarios=(arr<1e-7).sum(axis=0).tolist(),
            scenario_frequencies_not_probabilities=True))
    write(O/'label_sensitivity_summary.json',sens)
    write(O/'training_feature_coverage.json',dict(old24_Hmean_over_point1=sum(r['Hmean']>.1 for r in rows),
        old24_Hcenter_over_point1=sum(r['Hcenter']>.1 for r in rows),
        geometric_coverage_cuts_are_not_quality_thresholds=True,
        features={k:dict(minimum=min(r[k] for r in rows),maximum=max(r[k] for r in rows),
                        population_sd=float(np.std([r[k] for r in rows]))) for k in ['Hmean','Hcenter','dir','S_top_deg']}))
    # Paired evaluation differences remain grouped, with no iid-pair p-values.
    bycase={(r['method'],r['case_id']):r for r in cases};diffs=[]
    for method in ['geom4','geom5_top']:
        for baseline in methods+(['geom4'] if method=='geom5_top' else []):
            for group in sorted({r['building_id'] for r in old}):
                ss=[r for r in old if r['building_id']==group]
                diffs.append(dict(method=method,baseline=baseline,building_id=group,records=len(ss),
                    nll_difference=sum(bycase[(method,r['case_id'])]['negative_log_likelihood']-bycase[(baseline,r['case_id'])]['negative_log_likelihood'] for r in ss),
                    grade_step_difference=sum(bycase[(method,r['case_id'])]['grade_step_loss']-bycase[(baseline,r['case_id'])]['grade_step_loss'] for r in ss)))
    csvout(O/'paired_building_differences.csv',diffs)
    # Monotonicity is guaranteed by the sign constraint and checked numerically
    # on feature space, without claiming every independent perturbation is a room.
    max_violation=0.
    for f in fits:
        X=mats[f['method']];base=evaluate(f,X,y)['expected']
        for j in range(X.shape[1]):
            pert=X.copy();pert[:,j]+=.1
            out=evaluate(f,pert,y)['expected'];max_violation=max(max_violation,float(np.max(base-out)))
    assert max_violation<1e-10
    manifest=dict(protocol_sha256=sha(ep),scores_sha256=sha(sp),fitting_records=24,images=18,buildings=11,
        new_severe_used_in_fit=0,pending_used_in_fit=0,unreviewed_used_as_negative=0,original_holdout_or_exposed_groups_used=0,
        fixed_ridge_lambda=1.0,hyperparameter_search_runs=0,methods=methods+['geom4','geom5_top'],
        base_grouped_fits=len(folds),without_T20_grouped_fits=len(fo),full_neighbor_scenario_fits=len(perturbed),
        analytic_gradient_finite_difference_error=float(err),maximum_feature_monotonicity_violation=max_violation,
        model_probabilities_are_human_confidence=False,calibrated_severe_threshold=False,independent_validation=False,
        raw_predictions_preserved=True)
    write(O/'run_manifest.json',manifest)
    print(__import__('json').dumps(dict(summary=summary,without_T20=so,label_sensitivity=sens,manifest=manifest),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
