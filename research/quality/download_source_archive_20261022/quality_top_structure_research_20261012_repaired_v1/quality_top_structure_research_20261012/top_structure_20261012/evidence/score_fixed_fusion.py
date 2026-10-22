#!/usr/bin/env python3
"""Evaluate already frozen endpoints and their unchanged full source pools.

This script evaluates geometry only. It never calls or reimplements fusion.
No classification labels, optimal thresholds, or holdout outputs enter it.
"""
from __future__ import annotations
import argparse,csv,hashlib,importlib.util,itertools,json,math,sys
from pathlib import Path
import numpy as np
from audit_qualification import read,dump,csvout,digest

def module(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m

def rays(points):
    p=np.asarray(points,float);u=2*np.pi*(p[:,0]/1024-.5);v=np.pi*(.5-p[:,1]/512)
    return np.c_[np.cos(v)*np.sin(u),np.sin(v),-np.cos(v)*np.cos(u)]

def features(W,O):
    E=W/'top_structure_20261012/evidence';B=W/'previous_research/quality_calibration_research_20261011/inputs_extracted/quality_cloud_compute_review_20261010'
    engine=B/'frozen/scope_engine';sys.path.insert(0,str(engine/'core'))
    from quality_v11 import score_geometry
    from traditional_metrics import frozen_to_hohonet_pixels
    from geometric_components import spherical_sym_distance
    import height_revision
    from shapely.geometry import Polygon
    hpath=W/'top_structure_20261012/mechanisms/centered_height.py';hc=module(hpath,'fusion_demo_centered_height')
    offpath=B/'frozen/Pro_selected_original/official_audit/audit_official_controls.py'
    off=module(offpath,'fusion_demo_official_audit');official_manifest=off.verify_official_sources();fn,_,_=off.load_official_iou_branch(Polygon)
    member_path=O/'fixed_fusion_member_inputs_67.json';end_path=O/'fixed_fusion_endpoint_inputs.json'
    members=read(member_path);endpoints=read(end_path);allrows=[];detail=[];checks=[]
    sources=[member_path,end_path,hpath,engine/'core/quality_v11.py',offpath]
    hashes={str(p.relative_to(W)):digest(p) for p in sources}
    jobs=[('member',r) for r in members]+[('endpoint',r) for r in endpoints if r.get('score_available')]
    for j,(kind,r) in enumerate(jobs):
        identity=r['record_id'] if kind=='member' else r['endpoint_id'];a,g=r['geometry'],r['reference_geometry']
        out=score_geometry(a,g);assert out['status']=='available',(identity,out)
        m=out['metrics'];cc=hc.centered_height_components(a,g,height_module=height_revision)
        compat=off.run_compatibility(fn,frozen_to_hohonet_pixels(a),frozen_to_hohonet_pixels(g));assert compat['official_branch_status']=='returned_finite'
        err=abs(compat['official_iou3d_raw']-m['iou_3d_corner_mean']);assert err<1e-9
        row=dict(kind=kind,identity=identity,image_code=r['image_code'],worker_id=r.get('worker_id'),record_id=r.get('record_id'),
            n=(1 if kind=='member' else r['n']),reference_object_id=r['reference_object_id'],geometry_hash=r['geometry_hash'],
            independent_output=True if kind=='member' else r['independent_output'],duplicate_of=r.get('duplicate_of'),
            endpoint_status=None if kind=='member' else r['source_candidate_status'],
            reference_status=r['reference_acceptance'],**{k:m[k] for k in ['iou_2d','iou_3d_corner_mean','S_top_deg','S_bottom_deg','Hmean','Hlocal','Hstar','dir','flat']},
            Hcenter=cc['Hcenter'],X_rms_deg=r.get('Xrms'),X_max_deg=r.get('Xmax'),
            engine_v11=out['quality_score'],official_iou3d_direct=compat['official_iou3d_raw'])
        if kind=='member':
            p=np.asarray(r['before_preprocessing_points'],float)[r['ordered_source_point_indices']];rp=rays(p)
            row.update(S_top_raw_deg=float(spherical_sym_distance(rp[::2],g['top3d'],2048)),
                S_bottom_raw_deg=float(spherical_sym_distance(rp[1::2],g['bottom3d'],2048)))
            inherited=r['inherited_components'];qe=abs(out['quality_score']-inherited['Q']);assert qe<1e-9
            checks.append(dict(identity=identity,engine_v11_parity_error=qe,official_direct_parity_error=err,
                max_base_component_error=max(abs(row[k]-inherited[k]) for k in ['iou_2d','S_top_deg','S_bottom_deg','Hstar','Hmean','Hlocal','dir','flat'])))
        else:
            row.update(S_top_raw_deg=None,S_bottom_raw_deg=None)
            checks.append(dict(identity=identity,engine_v11_parity_error=None,official_direct_parity_error=err,max_base_component_error=None))
        allrows.append(row);detail.append(dict(identity=identity,engine=out,centered_height=cc,official=compat))
        if (j+1)%10==0:print(f'features {j+1}/{len(jobs)}',flush=True)
    assert hashes=={str(p.relative_to(W)):digest(p) for p in sources}
    dump(O/'fixed_demo_features.json',allrows);csvout(O/'fixed_demo_features.csv',allrows);dump(O/'fixed_demo_feature_details.json',detail)
    csvout(O/'fixed_demo_engine_checks.csv',checks)
    dump(O/'fixed_demo_feature_manifest.json',dict(n_members=len(members),n_endpoint_rows=len(endpoints),n_distinct_endpoint_coordinates=3,
        rows_actually_computed=len(jobs),raw_boundary_members_actually_computed=len(members),no_fusion_rerun=True,
        independent_validation=False,source_sha256=hashes,official_source_manifest=official_manifest,
        max_member_v11_error=max(x['engine_v11_parity_error'] for x in checks if x['engine_v11_parity_error'] is not None),
        max_official_error=max(x['official_direct_parity_error'] for x in checks),
        endpoint_raw_input_metrics='None: absent raw paired source for the aggregate is not zero original error'))

def scores(W,O):
    cp=W/'top_structure_20261012/analysis/candidate_functions.py';cfg_hash=digest(cp);cand=module(cp,'fusion_demo_candidates')
    fs=O/'fixed_demo_features.json';rows=read(fs);scored=[]
    for r in rows:
        if r['kind']=='endpoint':
            # A common-x fused output has no observed current edited,
            # pre-average human input of its own. Its representation cannot
            # supply a zero original annotation-error measurement.
            assert r.get('X_rms_deg') is None and r.get('X_max_deg') is None
        s=cand.score(r);assert abs(s['Q_v11']-r['engine_v11'])<1e-9
        if r['kind']=='endpoint':
            assert s['Q_no_top_Xrms8'] is None and s['Q_no_top_Xmax8'] is None
        scored.append(dict(**r,**s))
    methods=list(cand.PRIMARY_METHODS)+list(cand.DIAGNOSTIC_METHODS)
    if 'Q_rawS_same_parameters' in scored[0]:methods.append('Q_rawS_same_parameters')
    assert cfg_hash==digest(cp)
    changes=[];endpoint_ranks=[];member_rank=[]
    for im in sorted({r['image_code'] for r in scored}):
        mr=[r for r in scored if r['kind']=='member' and r['image_code']==im];er=[r for r in scored if r['kind']=='endpoint' and r['image_code']==im]
        for meth in methods:
            eligible=[r for r in mr if r.get(meth) is not None]
            pairs=list(itertools.combinations(eligible,2));strict=0;flips=0;newtie=0;oldtie=0
            for a,b in pairs:
                d0=a['Q_v11']-b['Q_v11'];d1=a[meth]-b[meth]
                if abs(d0)<=1e-10:oldtie+=1
                else:
                    strict+=1
                    if abs(d1)<=1e-10:newtie+=1
                    elif d0*d1<0:flips+=1
            changes.append(dict(image_code=im,method=meth,n_members=len(mr),n_available=len(eligible),n_pairs=len(pairs),
                old_strict_pairs=strict,old_ties=oldtie,new_ties_of_old_strict=newtie,strict_rank_reversals_vs_v11=flips,
                interpretation='Formula disagreement only; unreviewed members have no new quality labels.'))
            for r in eligible:
                rank=1+sum(x[meth]>r[meth]+1e-10 for x in eligible)
                base_rank=1+sum(x['Q_v11']>r['Q_v11']+1e-10 for x in mr)
                member_rank.append(dict(image_code=im,record_id=r['record_id'],worker_id=r['worker_id'],method=meth,score=r[meth],
                    within_image_rank=rank,v11_rank=base_rank,rank_difference=rank-base_rank,scope='selected single-image performance; not long-term personnel ability'))
            for e in er:
                value=e.get(meth)
                endpoint_ranks.append(dict(image_code=im,endpoint_id=e['identity'],n=e['n'],method=meth,score=value,
                    n_member_scores=len(eligible),members_scoring_below=None if value is None else sum(r[meth]<value-1e-10 for r in eligible),
                    members_scoring_above=None if value is None else sum(r[meth]>value+1e-10 for r in eligible),
                    members_tied=None if value is None else sum(abs(r[meth]-value)<=1e-10 for r in eligible),
                    member_mean=None if not eligible else sum(r[meth] for r in eligible)/len(eligible),
                    independent_output=e['independent_output'],duplicate_of=e['duplicate_of'],
                    interpretation='All-person fixed endpoint versus member outputs; not a k trajectory or evidence of score validity.'))
    csvout(O/'fixed_demo_candidate_scores.csv',scored);dump(O/'fixed_demo_candidate_scores.json',scored)
    csvout(O/'fixed_demo_within_image_reversals.csv',changes);csvout(O/'fixed_demo_endpoint_relative_to_members.csv',endpoint_ranks)
    csvout(O/'fixed_demo_member_rank_changes.csv',member_rank)
    summary=dict(candidate_function_sha256=cfg_hash,feature_sha256=digest(fs),methods=methods,n_scored_rows=len(scored),
        n_members=67,n_endpoint_rows=4,n_distinct_endpoint_coordinates=3,root_formula_not_refit_here=True,
        no_new_label_or_personnel_group=True,no_quality_accuracy_estimated=True,
        endpoint_comparison_scope='Reconstructed-output candidates only; original-input X candidates remain None for every endpoint.',
        endpoint_scores=[{k:r.get(k) for k in ['identity','image_code','n','endpoint_status','independent_output','duplicate_of']+methods} for r in scored if r['kind']=='endpoint'],
        within_image_reversals=changes)
    dump(O/'fixed_demo_summary.json',summary)
    print(json.dumps(summary['endpoint_scores'],ensure_ascii=False,indent=2))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workspace',type=Path,default=Path.cwd());ap.add_argument('--out',type=Path)
    g=ap.add_mutually_exclusive_group();g.add_argument('--features-only',action='store_true');g.add_argument('--scores-only',action='store_true')
    a=ap.parse_args();W=a.workspace.resolve();O=a.out or W/'top_structure_20261012/evidence/results';O.mkdir(parents=True,exist_ok=True)
    if not a.scores_only:features(W,O)
    if not a.features_only:scores(W,O)

if __name__=='__main__':main()
