#!/usr/bin/env python3
"""Meaningful scalar contracts and recomputation checks for the delivered study."""
from __future__ import annotations
import argparse, copy, hashlib, json, math
from pathlib import Path
import numpy as np
from score import BASELINE,score_metrics
from run_search import jload,dump
HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,default=HERE/'inputs/search_inputs.json')
    p.add_argument('--config',type=Path,default=HERE/'recommended_parameters.json');p.add_argument('--results',type=Path,default=HERE/'results')
    p.add_argument('--out',type=Path,default=HERE/'results/SCALAR_VERIFICATION.json');a=p.parse_args()
    data=jload(a.inputs);configs=jload(a.config)['candidates'];rows=data['rows']
    old=jload(a.results/'selected_scores_922.json')['rows'];expected={r['record_id']:r for r in old}
    maxd=0.;independent=0.;roundoff=0;checks=[]
    for r in rows:
      m=r['metrics'];I=min(m['iou_2d'],1.);b=m['S_bottom_deg']**2/32;d=m['dir'];hm=m['Hmean'];hc=m['Hcenter']
      baseline=100*I/(1+b+1.5*d*d/(d*d+37.5)+(hm/.8)**2+(hc/.25)**2)
      independent=max(independent,abs(baseline-r['baseline_scores']['P_tied_quad08']))
      for n,c in configs.items():
        q=score_metrics(m,c,r['descriptor']);assert q['status']=='complete',(r['id'],n,q)
        roundoff+=int(q['iou_roundoff_clamped']) if n==next(iter(configs)) else 0
        maxd=max(maxd,abs(q['score']-expected[r['id']]['scores'][n]))
      mainq=100*I/(1+b+1.5*d*d/(d*d+37.5)+(d/12)**4+hm*hm+(hc/.25)**2)
      independent=max(independent,abs(mainq-expected[r['id']]['scores']['J_main_hill_tail12_g1_l025']))
    assert maxd<1e-10 and independent<1e-10
    c=configs['J_main_hill_tail12_g1_l025'];valid={'I':.9,'Sb':1.,'D':3.,'Hm':.1,'Hc':.02}
    for key in ['I','Sb','D']:
      z=dict(valid);z[key]=None;v=score_metrics(z,c);assert v['score'] is None and v['floor_score'] is None;checks.append('missing_'+key)
    for key in ['Hm','Hc']:
      z=dict(valid);z[key]=None;v=score_metrics(z,c);assert v['status']=='floor_only' and v['score'] is None and v['floor_score'] is not None;checks.append('missing_height_'+key)
    v=score_metrics(valid,c,reference_height_available=False);assert v['status']=='floor_only' and v['score'] is None;checks.append('explicit_unconfirmed_top')
    for key in ['I','Sb','D']:
      z=dict(valid);z[key]=float('nan');assert score_metrics(z,c)['score'] is None;checks.append('nonfinite_'+key)
    for key in ['boundary_scale','direction_scale','global_scale','local_scale']:
      bad={**c,key:0};assert score_metrics(valid,bad)['status']=='unavailable';checks.append('invalid_config_'+key)
    for value in [1+1e-10,1.2,-.1]:
      assert score_metrics({**valid,'I':value},c)['score'] is None;checks.append('true_invalid_I_'+str(value))
    v=score_metrics({**valid,'I':1+np.finfo(float).eps},c);assert v['iou_roundoff_clamped'];checks.append('roundoff_I_clamp')
    v=score_metrics({**valid,'I':0},{**c,'combine':'max_floor'});assert v['score']==0 and v['zero_overlap_limit_evaluated'];json.dumps(v,allow_nan=False);checks.append('zero_overlap_valid_limit')
    v=score_metrics({**valid,'Hm':1e300},c);assert v['score'] is None;checks.append('height_overflow_unavailable')
    v=score_metrics({**valid,'Hc':-.1},c);assert v['status']=='height_unavailable' and v['score'] is None;checks.append('negative_height_diagnostic')
    local_cfg=configs['J_local_joint_hinge10_w2_s8']
    for label,descriptor in [('missing',None),('malformed',{'unrelated':1}),('negative',{'joint_hinge':{'t10_g2':-1}}),('nonfinite',{'joint_hinge':{'t10_g2':float('nan')}}),('nonscalar',{'joint_hinge':{'t10_g2':[1,2]}})]:
      v=score_metrics(valid,local_cfg,descriptor);assert v['status']=='unavailable' and v['score'] is None;checks.append('direction_descriptor_'+label)
    # Main is monotone in each error at fixed other terms, exact equality at ideal.
    ideal={'I':1.,'Sb':0.,'D':0.,'Hm':0.,'Hc':0.};assert score_metrics(ideal,c)['score']==100
    for key,end in [('Sb',20.),('D',25.98),('Hm',2.),('Hc',1.)]:
      q=np.array([score_metrics({**ideal,key:float(x)},c)['score'] for x in np.linspace(0,end,401)])
      assert np.max(np.diff(q))<=1e-12;checks.append('monotone_'+key)
    report=dict(status='passed',records=922,candidates=len(configs),same_reference_score_checks=len(rows)*len(configs),
                maximum_saved_score_difference=maxd,independent_main_and_baseline_maximum_difference=independent,
                roundoff_iou_records=roundoff,contract_checks=checks,
                source_input_sha256=hashlib.sha256(a.inputs.read_bytes()).hexdigest(),
                config_sha256=hashlib.sha256(a.config.read_bytes()).hexdigest(),
                did_not_certify_human_grades=True)
    dump(a.out,report);print(json.dumps(report))

if __name__=='__main__':main()
